"""GATE-02: no answer and no error text of any tool carries the canary marker (plan 28-10).

The canary world of plan 28-07 puts a marker into the name and the content of every tagged
node. This test calls every tool of the live registry through the in-memory ``Client(mcp)``,
the seven write tools included, and scans every surface of every answer for the marker: the
text parts, ``structuredContent``, the decoded blob and the unquoted URI of an embedded
resource, and the decoded paging cursors. It does so in the normal state and in three forced
outages of the tag REPORT (500, 412 always, timeout), so the fail closed path is scanned the
same way as the healthy one (D-28-07).

Four rules make a green run mean something:

*   **The marker is never an argument (D-28-06).** Every argument set is asserted free of the
    marker before its call, so a marker in an answer can only come from the instance.
*   **The registry is the plan.** ``set(PLAN) == registry`` against ``list_tools()``, and the
    output says ``KANARIE <mode> geprüft <n> von <registry>`` with ``n == 24``.
*   **The control marker must show.** The untagged control file and note carry a second
    marker; in the normal state every reader answer that has to show them must show it, or an
    empty index or a wrong container would end in a green canary (T-28-101).
*   **Every page is read.** Tools with a cursor follow ``next`` at their maximum limit until
    no ``next`` comes; ``unified_search`` has no cursor input, so its provider ``cursors`` are
    scanned and logged per provider with the hit count, and the count must stay below the
    limit, which means every hit was on the first page (A-27-04 / T-27-25).

The outage runs through ``respx`` with ``pass_through`` for every other request, never through
``occ app:disable``, which does not produce an outage (phase 25, K1).

Run it against nc35 with the environment of ``.env.nc35`` plus the ``NC_MCP_E2E_*`` exports
of ``topology.py``::

    PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_canary.py \\
        -m integration -s

Without that environment it skips.
"""

import dataclasses
import json
import subprocess
import time
from collections.abc import Iterable
from typing import Any

import canary_world as cw
import pytest
import topology
from mcp import Client
from mcp.types import CallToolResult, TextContent
from result_shapes import leaks, surfaces

from mcp_connector import paging
from mcp_connector.server import mcp
from mcp_connector.tools import files as files_tools
from mcp_connector.tools import mail as mail_tools
from mcp_connector.tools import search as search_tools
from mcp_connector.tools import tables as tables_tools
from mcp_connector.tools import talk as talk_tools
from mcp_connector.tools import withhold

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

RAW = cw.RAW_DIR / "28-10-canary.txt"
EXPECTED_TOOLS = 24
MAX_PAGES = 50
COMMAND = (
    "PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_canary.py "
    "-m integration -s"
)

#: The limit each paging tool is called with: its maximum, so few pages cover everything.
PAGED_LIMIT: dict[str, int] = {
    "files_search": files_tools.MAX_SEARCH_LIMIT,
    "files_list": files_tools.MAX_LIST_LIMIT,
    "talk_browse": talk_tools.MAX_LIMIT,
    "tables_browse": tables_tools.MAX_LIMIT,
    "mail_browse": mail_tools.MAX_LIMIT,
}

#: What a successful write tool leaves behind, as a kind of ``World.register_tool_write``.
WRITE_KINDS: dict[str, str] = {
    "calendar_create_event": "event",
    "deck_create_card": "card",
    "tables_create_row": "row",
    "notes_create": "note",
    "talk_send": "message",
}

#: The write tools that aim at a tagged target and therefore have to refuse.
MUST_REFUSE = ("files_upload", "files_create_folder", "notes_create", "talk_send")


def log(line: str) -> None:
    cw.record(RAW, line)


def git_head() -> str:
    finished = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return finished.stdout.strip() or "unbekannt"


def args_short(args: dict[str, Any]) -> str:
    return cw.short(json.dumps(args, ensure_ascii=False, sort_keys=True), 120)


def payload(result: CallToolResult) -> dict[str, Any]:
    """The answer as a dict: ``structuredContent`` or the JSON of the first text part."""
    if isinstance(result.structured_content, dict) and result.structured_content:
        return result.structured_content
    for part in result.content:
        if isinstance(part, TextContent):
            try:
                data = json.loads(part.text)
            except ValueError:
                return {}
            return data if isinstance(data, dict) else {}
    return {}


def cursor_surfaces(data: dict[str, Any]) -> list[str]:
    """The decoded paging cursors of one answer: ``next`` and the provider ``cursors``."""
    out: list[str] = []
    values: list[Any] = [data.get("next")]
    cursors = data.get("cursors")
    if isinstance(cursors, dict):
        values.extend(cursors.values())
    for value in values:
        if not value:
            continue
        out.append(json.dumps(value, ensure_ascii=False))
        if isinstance(value, str):
            try:
                out.append(json.dumps(paging.decode_cursor(value), ensure_ascii=False))
            except Exception as exc:  # a foreign cursor is scanned raw
                out.append(f"undekodierbar {type(exc).__name__}")
    return out


def around(surface: str, marker: str, width: int = 90) -> str:
    """The part of a leaking surface around the first marker, so the finding is readable."""
    at = surface.find(marker)
    start = max(at - width, 0)
    return f"@{at}: ...{surface[start : at + len(marker) + width]}..."


def plan(world: cw.World) -> dict[str, list[dict[str, Any]]]:
    """At least one argument set per tool; none of them carries the marker (D-28-06)."""
    fileid = world.fileids["tagged_file"]
    card = f"card:{world.board_id}:{world.stack_id}:{world.card_id}"
    event = f"event:{world.calendar_uri}:{world.event_uid}.ics"
    return {
        "files_search": [{"query": world.stamm}],
        "files_list": [{"path": world.root}, {"path": world.locked_dir}],
        "files_read": [{"path": world.locked_file}, {"path": world.control_file}],
        "files_download": [{"path": world.locked_file}],
        "files_read_as_markdown": [{"path": world.locked_doc}, {"path": world.control_doc}],
        "files_upload": [{"path": f"{world.locked_dir}/neu-{world.h}.txt", "content": "x"}],
        # Once without parents and once with: the chain must not probe or create a single
        # segment below the locked folder either (FOLD-04). Both paths are the ones the
        # world's cleanup removes and reads back, should a call create them after all.
        "files_create_folder": [
            {"path": world.refused_folder},
            {"path": f"{world.refused_chain}/b", "parents": True},
        ],
        "notes_search": [{"query": world.stamm}],
        "notes_read": [
            {"note_id": f"note:{world.note_id}"},
            {"note_id": f"note:{world.control_note_id}"},
        ],
        "notes_create": [
            {"title": f"{world.stamm}-neu", "content": "x", "category": world.tagged_category}
        ],
        "unified_search": [{"query": world.stamm, "limit": search_tools.MAX_LIMIT}],
        "prepare_context": [
            {"query": world.stamm, "detail": "full"},
            {"query": world.stamm, "detail": "short"},
        ],
        "talk_browse": [
            {"level": "conversations"},
            {"level": "messages", "token": world.talk_token},
            {"level": "messages", "token": world.file_room_token},
        ],
        "talk_send": [{"token": world.file_room_token, "message": f"{world.stamm} ping"}],
        "search": [{"query": world.stamm}],
        "fetch": [
            {"id": f"file:{fileid}"},
            {"id": f"note:{world.note_id}"},
            {"id": f"message:{world.file_room_token}:1"},
            {"id": f"table:{world.table_id}"},
            {"id": card},
            {"id": event},
        ],
        "calendar_list_events": [
            {
                "start": "2026-10-05T00:00:00+00:00",
                "end": "2026-10-06T00:00:00+00:00",
                "calendar": world.stamm,
            }
        ],
        "calendar_create_event": [
            {
                "summary": f"{world.stamm}-neu",
                "start": "2026-10-07T09:00:00+00:00",
                "end": "2026-10-07T10:00:00+00:00",
                "calendar": world.stamm,
            }
        ],
        "deck_browse": [
            {"level": "boards"},
            {"level": "stacks", "board_id": world.board_id},
            {"level": "cards", "board_id": world.board_id},
        ],
        "deck_create_card": [
            {"board_id": world.board_id, "stack_id": world.stack_id, "title": f"{world.stamm}-neu"}
        ],
        "contacts_search": [{"query": world.stamm}],
        "tables_browse": [
            {"level": "tables"},
            {"level": "columns", "table_id": world.table_id},
            {"level": "rows", "table_id": world.table_id},
        ],
        # The table has one column, the link column of the world; an empty value is the
        # neutral write that needs no file reference at all.
        "tables_create_row": [{"table_id": world.table_id, "values": json.dumps({"Verweis": ""})}],
        "mail_browse": [{"level": "accounts"}],
    }


def control_expected(world: cw.World, tool: str, args: dict[str, Any]) -> bool:
    """Whether this reader call must show the control marker in the normal state."""
    if tool in ("files_search", "notes_search", "unified_search", "search"):
        return True
    if tool == "files_list":
        return args.get("path") == world.root
    if tool == "files_read":
        return args.get("path") == world.control_file
    if tool == "files_read_as_markdown":
        return args.get("path") == world.control_doc
    if tool == "notes_read":
        return args.get("note_id") == f"note:{world.control_note_id}"
    if tool == "tables_browse":
        return args.get("level") == "rows"
    return False


@dataclasses.dataclass
class Sweep:
    """What one sweep saw, beyond the per call assertions it already made."""

    checked: set[str] = dataclasses.field(default_factory=set)
    unavailable: list[str] = dataclasses.field(default_factory=list)
    unified: list[dict[str, Any]] = dataclasses.field(default_factory=list)


async def run_tool(world: cw.World, tool: str, args: dict[str, Any]) -> list[CallToolResult]:
    """Call once, and follow ``next`` at the maximum limit for the tools that page."""
    base = dict(args)
    if tool in PAGED_LIMIT:
        base["limit"] = PAGED_LIMIT[tool]
    current = dict(base)
    pages: list[CallToolResult] = []
    for _ in range(MAX_PAGES):
        assert world.marker not in json.dumps(current), f"the marker is an argument: {tool}"
        result = await cw.call(tool, current)
        pages.append(result)
        following = payload(result).get("next") if tool in PAGED_LIMIT else None
        if not following:
            return pages
        current = {**base, "cursor": following}
    pytest.fail(f"{tool} {args_short(args)}: still a next page after {MAX_PAGES} pages")


def book_write(world: cw.World, tool: str, result: CallToolResult) -> str:
    """Book what a successful write tool created; returns the booked entry or ``-``."""
    if result.is_error or tool not in WRITE_KINDS:
        return "-"
    data = payload(result)
    kind = WRITE_KINDS[tool]
    raw_id = str(data.get("id") or "")
    ident = f"message:{data.get('token')}:{raw_id}" if kind == "message" else raw_id
    world.register_tool_write(kind, ident)
    return f"{kind} {ident}"


async def call_and_scan(
    world: cw.World, mode: str, tool: str, args: dict[str, Any], sweep: Sweep
) -> list[CallToolResult]:
    pages = await run_tool(world, tool, args)
    case = f"{mode} {args_short(args)}"
    for index, result in enumerate(pages, start=1):
        every = surfaces(result)
        scanned = every + cursor_surfaces(payload(result))
        found = [around(s, world.marker) for s in scanned if world.marker in s]
        # The shared scan of result_shapes is a subset of this one (plus the cursors).
        assert found or not leaks(result, world.marker), "the two scans disagree"
        if any(withhold.EXCLUSION_UNAVAILABLE in s for s in every):
            sweep.unavailable.append(f"{tool} {args_short(args)}")
        cw.check(
            RAW,
            "GATE-02",
            tool,
            f"{case} seite {index}",
            not found,
            " | ".join(found) if found else f"is_error={result.is_error} {every[-1][:120]}",
        )
    booked = [book_write(world, tool, result) for result in pages]
    log(
        f"AUFRUF {mode} {tool} {args_short(args)} seiten={len(pages)} "
        f"is_error={[bool(r.is_error) for r in pages]} gebucht={booked}"
    )
    if tool in MUST_REFUSE:
        # Review WR-05: an error is not enough, it has to be the refusal the gate claims.
        problems = [
            cw.refusal_problem(tool, args, mode, " ".join(surfaces(r)))
            if r.is_error
            else "no error"
            for r in pages
        ]
        cw.check(
            RAW,
            "ABWEISUNG",
            tool,
            case,
            not any(problems),
            f"is_error={[bool(r.is_error) for r in pages]} gebucht={booked} "
            f"befund={[p for p in problems if p]}",
        )
    if mode == "normal" and control_expected(world, tool, args):
        seen = any(world.control_marker in s for r in pages for s in surfaces(r))
        cw.check(
            RAW,
            "KONTROLLE",
            tool,
            case,
            seen,
            f"kontroll-marker {'gesehen' if seen else 'fehlt'} in {len(pages)} seite(n)",
        )
    if tool == "unified_search":
        sweep.unified.extend(payload(r) for r in pages)
    return pages


def first_ids(data: dict[str, Any]) -> list[str]:
    results = data.get("results")
    entries: Iterable[Any] = results if isinstance(results, list) else []
    return [str(e["id"]) for e in entries if isinstance(e, dict) and e.get("id") not in (None, "")]


async def sweep(world: cw.World, mode: str) -> Sweep:
    """Every tool of the registry, every argument set, every page, scanned."""
    async with Client(mcp) as client:
        listed = await client.list_tools()
    registry = {tool.name for tool in listed.tools}
    calls = plan(world)
    assert set(calls) == registry, sorted(set(calls) ^ registry)
    for sets in calls.values():
        for args in sets:
            assert world.marker not in json.dumps(args), f"the marker is an argument: {args}"

    result = Sweep()
    for tool, sets in calls.items():
        for args in sets:
            pages = await call_and_scan(world, mode, tool, args, result)
            if tool == "mail_browse" and args.get("level") == "accounts":
                await _mail_levels(world, mode, pages, result)
        result.checked.add(tool)

    line = f"KANARIE {mode} geprüft {len(result.checked)} von {len(registry)}"
    log(line)
    print(line)
    assert len(result.checked) == len(registry) == EXPECTED_TOOLS
    return result


async def _mail_levels(
    world: cw.World, mode: str, pages: list[CallToolResult], result: Sweep
) -> None:
    """Mailboxes of the first account and messages of its first mailbox, when there is one."""
    accounts = [i for page in pages for i in first_ids(payload(page))]
    if not accounts:
        log(f"MAIL {mode}: kein Konto, nur level=accounts geprüft")
        return
    boxes_pages = await call_and_scan(
        world, mode, "mail_browse", {"level": "mailboxes", "account_id": accounts[0]}, result
    )
    boxes = [i for page in boxes_pages for i in first_ids(payload(page))]
    if not boxes:
        log(f"MAIL {mode}: konto {accounts[0]} ohne Postfach")
        return
    await call_and_scan(
        world, mode, "mail_browse", {"level": "messages", "mailbox_id": boxes[0]}, result
    )


def log_provider_cursors(result: Sweep) -> None:
    """Per provider cursor with its hit count; every hit must have been on the first page."""
    for data in result.unified:
        cursors = data.get("cursors")
        hits = data.get("results")
        entries = hits if isinstance(hits, list) else []
        if not isinstance(cursors, dict) or not cursors:
            log(f"CURSOR keine provider-cursors (count={data.get('count')})")
            continue
        for provider, cursor in sorted(cursors.items()):
            count = sum(1 for e in entries if isinstance(e, dict) and e.get("provider") == provider)
            log(f"CURSOR provider={provider} cursor={cursor} treffer={count}")
            assert count < search_tools.MAX_LIMIT, f"{provider}: {count} hits, a second page"


def header(env: cw.LiveEnv, mode: str) -> None:
    log("")
    log(
        f"# 28-10 canary {mode} {time.strftime('%Y-%m-%d %H:%M:%S %z')} head={git_head()} "
        f"container={topology.NC_CONTAINER} user={env.user}"
    )
    log(f"# kommando: {COMMAND}")


def assert_cleanup(world: cw.World) -> None:
    lines = world.cleanup_lines
    tool_lines = [line for line in lines if line.startswith("CLEANUP tool ")]
    log(
        f"ZUSAMMENFASSUNG cleanup: {len(lines)} Zeilen, "
        f"{sum(1 for line in lines if cw.cleanup_ok(line))} gelesen ok, "
        f"{len(tool_lines)} Werkzeug-Einträge"
    )
    assert lines, "the cleanup registered nothing"
    assert len(tool_lines) == len(world.writes_ledger), (tool_lines, world.writes_ledger)
    bad = [line for line in lines if not cw.cleanup_ok(line)]
    assert not bad, bad
    # The two folders files_create_folder had to refuse are read back by name, so a
    # cleanup that lost their step cannot pass as a clean one.
    for folder in world.refused_folders:
        assert f"CLEANUP ordner {folder}: 404" in lines, (folder, lines)


async def test_no_tool_answer_carries_the_marker_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    env = cw.live_env()
    header(env, "normal")
    with cw.canary_world(env, raw=RAW) as world:
        log(f"# stamm={world.stamm} marker={world.marker} kontroll-marker={world.control_marker}")
        cw.mcp_env(monkeypatch, env)
        cw.fresh_guard()
        result = await sweep(world, "normal")
        log_provider_cursors(result)
    assert_cleanup(world)


@pytest.mark.parametrize("mode", ["500", "412", "timeout"])
async def test_no_tool_answer_carries_the_marker_in_an_outage(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    env = cw.live_env()
    header(env, f"ausfall-{mode}")
    with cw.canary_world(env, raw=RAW) as world:
        log(f"# stamm={world.stamm} marker={world.marker} kontroll-marker={world.control_marker}")
        cw.mcp_env(monkeypatch, env)
        cw.fresh_guard()
        with cw.guard_outage(env, mode) as failing:
            result = await sweep(world, f"ausfall-{mode}")
        log(f"AUSFALL {mode} report-route call_count={failing.call_count}")
        unavailable = result.unavailable
        log(f"AUSFALL {mode} nicht-prüfbar-antworten={len(unavailable)} {unavailable}")
        log_provider_cursors(result)
        assert failing.call_count >= 1, "the outage route was never hit"
        assert result.unavailable, "no answer named the unanswered exclusion check"
    assert_cleanup(world)

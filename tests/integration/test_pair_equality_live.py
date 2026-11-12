"""GATE-03 live: a tagged target answers like a missing one, against a real Nextcloud (28-11).

The unit pairs of plans 28-08 and 28-09 compare the two answers of every pair case in
``tool_classes.PAIR_CASES`` against mocked instances. This module makes the same comparison
with the answers of a running Nextcloud: every case is called twice through the in-memory
``Client(mcp)``, once with a target of the canary world of plan 28-07 that is tagged
``kein-ki`` and once with a target that does not exist, and the whole ``CallToolResult``
(text, ``structuredContent``, ``isError``) is compared after ``result_shapes.normalised``
replaced the requested id by ``<ID>``. That happens in the normal state and in the three
forced outages of the tag REPORT (500, 412 always, timeout), one fresh world per mode.

Three rules keep a green run honest:

*   **The list is the plan.** ``set(CASES) == set(PAIR_CASES)``, so a new pair case without a
    live measurement fails here instead of being skipped quietly.
*   **Both sides say why.** In the normal state every compared pair must be an error on both
    sides, and in an outage the tagged side must name the unanswered check (a listing may
    answer with its degraded entry instead of an error), so two answers cannot be equal
    because both ran into the same unrelated failure.
*   **An exception is measured, not skipped.** Every key of ``NAMED_EXCEPTIONS`` is called in
    the normal state and logged as an ``AUSNAHME`` line with exactly the pinned difference;
    in an outage it is an ordinary pair again and compared like every other case.

``fetch(table:)`` has no invented counterpart that would say anything (an invented table id
never reaches the link screen), so it is compared by its cell instead (D-28-14): the cell of
the row that links the tagged file is the empty value of the app in ``tables_browse`` and in
the ``fetch`` text, and the name of the tagged file is nowhere in the answer.

Run it against nc35 with the environment of ``.env.nc35`` plus the ``NC_MCP_E2E_*`` exports
of ``topology.py``::

    PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_pair_equality_live.py \\
        -m integration -s

Without that environment it skips.
"""

import base64
import dataclasses
import json
import subprocess
import time
from collections.abc import Callable
from typing import Any

import canary_world as cw
import pytest
import topology
from mcp.types import CallToolResult, TextContent
from result_shapes import normalised
from tool_classes import NAMED_EXCEPTIONS, PAIR_CASES

from mcp_connector.nextcloud.clients import dav
from mcp_connector.tools import files as files_tools
from mcp_connector.tools import withhold

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

RAW = cw.RAW_DIR / "28-11-pairs-live.txt"
COMMAND = (
    "PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_pair_equality_live.py "
    "-m integration -s"
)
#: The values of the live module of phase 27 (test_exclusion_live.py), taken over, not imported.
UNKNOWN_FILEID = "999999999"
INVENTED_TOKEN = "zz27nope"
MODES = ("normal", "500", "412", "timeout")
TABLE_CASE = ("fetch", "table")
#: What a successful write of a pair tool leaves behind, as a kind of the canary ledger.
WRITE_KINDS = {"notes_create": "note", "talk_send": "message"}


@dataclasses.dataclass(frozen=True)
class Pair:
    """The two calls of one pair case: the tool, and per side its arguments and id forms."""

    tool: str
    tagged: dict[str, Any]
    tagged_forms: tuple[str, ...]
    unknown: dict[str, Any]
    unknown_forms: tuple[str, ...]


def _missing(world: cw.World) -> str:
    return f"{world.root}/fehlt-{world.h}"


def _path_pair(tool: str, tagged: str, unknown: str, **extra: Any) -> Pair:
    return Pair(tool, {"path": tagged, **extra}, (tagged,), {"path": unknown, **extra}, (unknown,))


def _id_pair(tool: str, key: str, tagged: str, unknown: str, **extra: Any) -> Pair:
    return Pair(tool, {key: tagged, **extra}, (tagged,), {key: unknown, **extra}, (unknown,))


def _files_search(world: cw.World) -> Pair:
    """The scope is echoed as ``/files/<user><folder>`` (D-28-19), so both spellings count."""
    tagged, unknown = world.locked_dir, _missing(world)
    user = world.env.user
    return Pair(
        "files_search",
        {"query": world.stamm, "folder": tagged},
        (tagged, f"/files/{user}{tagged}"),
        {"query": world.stamm, "folder": unknown},
        (unknown, f"/files/{user}{unknown}"),
    )


def upload_id(world: cw.World) -> str:
    """One upload id for both sides; the staging folder still differs by the destination."""
    return f"{world.stamm}p"


def _binary_chunk1(world: cw.World) -> Pair:
    """Chunk 1 of several: a non-final first chunk has to carry 5 MiB to reach the guard."""
    chunk = b"k" * files_tools.MIN_UPLOAD_CHUNK_BYTES
    args = {
        "content_base64": base64.b64encode(chunk).decode("ascii"),
        "total_bytes": len(chunk) + 16,
        "chunk_index": 1,
        "final": False,
        "upload_id": upload_id(world),
    }
    return _path_pair(
        "files_upload", f"{world.locked_dir}/neu.bin", f"{_missing(world)}/neu.bin", **args
    )


def _notes_create(world: cw.World) -> Pair:
    title = f"{world.stamm}-neu"
    tagged, unknown = world.tagged_category, invented_category(world)
    return Pair(
        "notes_create",
        {"title": title, "content": "x", "category": tagged},
        (tagged,),
        {"title": title, "content": "x", "category": unknown},
        (unknown,),
    )


def invented_category(world: cw.World) -> str:
    return f"{world.stamm}-fehlt"


def _message(world: cw.World) -> Pair:
    return _id_pair(
        "fetch", "id", f"message:{world.file_room_token}:1", f"message:{INVENTED_TOKEN}:1"
    )


def _table(world: cw.World) -> Pair:
    """Compared by its cell in :func:`check_table_cell`; the pair is the same table twice."""
    table = f"table:{world.table_id}"
    return Pair("fetch", {"id": table}, (table,), {"id": table}, (table,))


#: Every pair case of ``PAIR_CASES`` with its two calls built from the canary world.
CASES: dict[tuple[str, str], Callable[[cw.World], Pair]] = {
    ("files_read", "path"): lambda w: _path_pair(
        "files_read", w.locked_file, f"{_missing(w)}/inhalt.txt"
    ),
    ("files_download", "path"): lambda w: _path_pair(
        "files_download", w.locked_file, f"{_missing(w)}/inhalt.txt"
    ),
    ("files_read_as_markdown", "path"): lambda w: _path_pair(
        "files_read_as_markdown", w.locked_doc, f"{_missing(w)}/inhalt.docx"
    ),
    ("files_list", "folder"): lambda w: _path_pair("files_list", w.locked_dir, _missing(w)),
    ("files_search", "folder"): _files_search,
    ("files_upload", "text"): lambda w: _path_pair(
        "files_upload", f"{w.locked_dir}/neu.txt", f"{_missing(w)}/neu.txt", content="x"
    ),
    ("files_upload", "binary_chunk1"): _binary_chunk1,
    ("files_create_folder", "path"): lambda w: _path_pair(
        "files_create_folder", f"{w.locked_dir}/neu-ordner", f"{_missing(w)}/neu-ordner"
    ),
    ("fetch", "file"): lambda w: _id_pair(
        "fetch", "id", f"file:{w.fileids['tagged_file']}", f"file:{UNKNOWN_FILEID}"
    ),
    ("notes_read", "note"): lambda w: _id_pair(
        "notes_read", "note_id", f"note:{w.note_id}", f"note:{UNKNOWN_FILEID}"
    ),
    ("fetch", "note"): lambda w: _id_pair(
        "fetch", "id", f"note:{w.note_id}", f"note:{UNKNOWN_FILEID}"
    ),
    ("notes_create", "category"): _notes_create,
    ("talk_browse", "messages"): lambda w: _id_pair(
        "talk_browse", "token", w.file_room_token, INVENTED_TOKEN, level="messages"
    ),
    ("talk_send", "token"): lambda w: _id_pair(
        "talk_send", "token", w.file_room_token, INVENTED_TOKEN, message=f"{w.stamm} ping"
    ),
    ("fetch", "message"): _message,
    TABLE_CASE: _table,
}


# --- protocol -------------------------------------------------------------------------


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


def header(env: cw.LiveEnv, what: str) -> None:
    log("")
    log(
        f"# 28-11 pairs {what} {time.strftime('%Y-%m-%d %H:%M:%S %z')} head={git_head()} "
        f"container={topology.NC_CONTAINER} user={env.user}"
    )
    log(f"# kommando: {COMMAND}")


def first_difference(a: str, b: str) -> str:
    """Where two normalised answers part, with a window of both, or ``gleich``."""
    if a == b:
        at = a.find('"text"')
        return f"gleich ({cw.short(a[max(at, 0) :], 200)})"
    at = next(
        (i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y), min(len(a), len(b))
    )
    start = max(at - 60, 0)
    return f"@{at} getaggt=...{a[start : at + 80]}... erfunden=...{b[start : at + 80]}..."


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


def raw(result: CallToolResult) -> str:
    return json.dumps(result.model_dump(mode="json", by_alias=True), ensure_ascii=False)


def book_write(world: cw.World, tool: str, result: CallToolResult) -> str:
    """Book what a successful write created, so the world's cleanup removes and reads it."""
    if result.is_error or tool not in WRITE_KINDS:
        return "-"
    data = payload(result)
    kind = WRITE_KINDS[tool]
    raw_id = str(data.get("id") or "")
    ident = f"message:{data.get('token')}:{raw_id}" if kind == "message" else raw_id
    world.register_tool_write(kind, ident)
    return f"{kind} {ident}"


async def call(world: cw.World, tool: str, args: dict[str, Any]) -> CallToolResult:
    assert world.marker not in json.dumps(args), f"the marker is an argument: {tool}"
    cw.fresh_guard()
    result = await cw.call(tool, args)
    booked = book_write(world, tool, result)
    if booked != "-":
        log(f"SCHREIBVORGANG {tool}: gebucht {booked}")
    return result


# --- cleanup beyond the world -----------------------------------------------------------


def cleanup_uploads(world: cw.World) -> list[str]:
    """The staging folders of the binary chunk, removed and read back (D-28-20).

    Nextcloud keeps the staging folder of the invented destination after refusing its chunk
    (measured in 28-01), and the world's cleanup does not know the upload id; so both
    folders are removed here and their status of now is the line.
    """
    creds = cw.credentials(world.env)
    pair = _binary_chunk1(world)
    lines: list[str] = []
    for label, args in (("getaggt", pair.tagged), ("erfunden", pair.unknown)):
        url = dav.uploads_url(creds, upload_id(world), path=args["path"])
        before, _ = world.harness.stat_url(url)
        if before == 207:
            world.harness.request("DELETE", url)
        after, _ = world.harness.stat_url(url)
        lines.append(f"CLEANUP uploads/{label} (vorher {before}): {after}")
    return lines


def cleanup_folders(world: cw.World) -> list[str]:
    """The two targets of the folder pair, read back while the world still stands.

    Neither call may create anything: the tagged side is refused before any request,
    and the invented parent does not exist. Both targets lie below the world's root,
    whose removal takes a folder with it and purges it from the trash bin by the stem;
    removing one here would leave a trash bin entry without the stem behind. So a
    folder found here is not removed a second time, it is a line that fails the
    cleanup check: the instance holds something the gate says cannot exist.
    """
    pair = CASES[("files_create_folder", "path")](world)
    lines: list[str] = []
    for label, args in (("getaggt", pair.tagged), ("erfunden", pair.unknown)):
        status, _ = world.harness.stat(args["path"])
        lines.append(f"CLEANUP ordner/{label} {args['path']}: {status}")
    return lines


def cleanup_category(world: cw.World) -> list[str]:
    """The category folder the Notes app created for the invented category, read back."""
    path = f"{world.notes_root}/{invented_category(world)}"
    before, _ = world.harness.stat(path)
    if before == 207:
        world.harness.delete(path)
    after, _ = world.harness.stat(path)
    return [f"CLEANUP notes-kategorie {path} (vorher {before}): {after}"]


def assert_cleanup(world: cw.World, extra: list[str]) -> None:
    lines = [*world.cleanup_lines, *extra]
    tool_lines = [line for line in world.cleanup_lines if line.startswith("CLEANUP tool ")]
    log(
        f"ZUSAMMENFASSUNG cleanup: {len(lines)} Zeilen, "
        f"{sum(1 for line in lines if cw.cleanup_ok(line))} gelesen ok, "
        f"{len(tool_lines)} Werkzeug-Einträge"
    )
    assert world.cleanup_lines, "the cleanup registered nothing"
    assert len(tool_lines) == len(world.writes_ledger), (tool_lines, world.writes_ledger)
    bad = [line for line in lines if not cw.cleanup_ok(line)]
    assert not bad, bad


# --- the comparisons --------------------------------------------------------------------


async def compare(world: cw.World, mode: str, key: tuple[str, str]) -> None:
    """Both calls of one pair case, normalised and compared as a whole."""
    pair = CASES[key](world)
    tagged = await call(world, pair.tool, pair.tagged)
    unknown = await call(world, pair.tool, pair.unknown)
    a = normalised(tagged, *pair.tagged_forms)
    b = normalised(unknown, *pair.unknown_forms)
    case = key[1]
    log(f"PAAR {mode} {pair.tool} {case}: {'gleich' if a == b else 'ungleich'}")
    cw.check(RAW, "GATE-03", pair.tool, f"{mode} {case}", a == b, first_difference(a, b))
    if mode == "normal":
        # With the check answered, both sides are a refusal; an outage may answer a listing
        # with its degraded entry instead, which is what the check below pins.
        refused = bool(tagged.is_error) and bool(unknown.is_error)
        cw.check(
            RAW,
            "ABWEISUNG",
            pair.tool,
            f"{mode} {case}",
            refused,
            f"is_error getaggt={tagged.is_error} erfunden={unknown.is_error}",
        )
    else:
        named = withhold.EXCLUSION_UNAVAILABLE in raw(tagged)
        cw.check(
            RAW,
            "AUSFALL-TEXT",
            pair.tool,
            f"{mode} {case}",
            named,
            "EXCLUSION_UNAVAILABLE genannt" if named else cw.short(a, 160),
        )


async def check_table_cell(world: cw.World, mode: str) -> None:
    """D-28-14 live: the cell that links the tagged file reads as the app's empty value."""
    tagged_fileid = world.fileids["tagged_file"]
    browse = await call(
        world, "tables_browse", {"level": "rows", "table_id": world.table_id, "limit": 50}
    )
    fetched = await call(world, "fetch", {"id": f"table:{world.table_id}"})
    rows = payload(browse).get("results") or []
    cell = rows[0].get("Verweis", "fehlt") if rows and isinstance(rows[0], dict) else "fehlt"
    text = str(payload(fetched).get("text") or "")
    lines = text.split("\n")
    fetch_cell = lines[3] if len(lines) > 3 else "fehlt"
    dumps = raw(browse) + raw(fetched)
    hidden = world.tagged_name not in dumps and f"/f/{tagged_fileid}" not in dumps
    empty = cell in (None, "") and fetch_cell == ""
    ok = hidden and empty and not browse.is_error and not fetched.is_error
    detail = (
        f"browse-zelle={cell!r} fetch-zeile={fetch_cell!r} name-im-json={not hidden} "
        f"zeilen={len(rows)}"
    )
    if mode == "normal":
        control = world.control_name in dumps
        ok = ok and control
        detail += f" kontrolle-sichtbar={control}"
    else:
        metadata = payload(fetched).get("metadata") or {}
        degraded = metadata.get("degraded") == withhold.EXCLUSION_UNAVAILABLE and bool(
            payload(browse).get("degraded")
        )
        ok = ok and degraded
        detail += f" degraded={degraded}"
    log(f"PAAR {mode} fetch table: Zelle leer {'ja' if ok else 'nein'}")
    cw.check(RAW, "GATE-03", "fetch", f"{mode} table", ok, detail)


async def run_mode(world: cw.World, mode: str) -> int:
    """Every pair case of the mode; returns how many were compared."""
    compared = 0
    for key in CASES:
        if key == TABLE_CASE:
            await check_table_cell(world, mode)
        elif mode == "normal" and key in NAMED_EXCEPTIONS:
            log(f"PAAR {mode} {key[0]} {key[1]}: benannte Ausnahme, gemessen als AUSNAHME")
            continue
        else:
            await compare(world, mode, key)
        compared += 1
    return compared


def test_every_pair_case_is_measured_live() -> None:
    """No pair case of the registry table goes without a live measurement."""
    assert set(CASES) == set(PAIR_CASES), sorted(set(CASES) ^ set(PAIR_CASES))


@pytest.mark.parametrize("mode", MODES)
async def test_tagged_answers_like_missing_live(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    env = cw.live_env()
    header(env, mode)
    extra: list[str] = []
    with cw.canary_world(env, raw=RAW) as world:
        log(f"# stamm={world.stamm} marker={world.marker}")
        cw.mcp_env(monkeypatch, env)
        monkeypatch.delenv("NC_MCP_FILES_ROOT", raising=False)
        monkeypatch.delenv("NC_MCP_TALK_SEND", raising=False)
        try:
            if mode == "normal":
                compared = await run_mode(world, mode)
            else:
                with cw.guard_outage(env, mode) as failing:
                    compared = await run_mode(world, mode)
                log(f"AUSFALL {mode} report-route call_count={failing.call_count}")
                assert failing.call_count >= 1, "the outage route was never hit"
            skipped = sum(1 for key in NAMED_EXCEPTIONS if mode == "normal" and key in CASES)
            line = f"PAARE {mode} verglichen {compared} von {len(CASES)} (ausnahmen {skipped})"
            log(line)
            print(line)
            assert compared + skipped == len(PAIR_CASES)
        finally:
            extra = cleanup_uploads(world) + cleanup_folders(world) + cleanup_category(world)
            for entry in extra:
                log(entry)
    assert_cleanup(world, extra)


def _brief(result: CallToolResult) -> str:
    """One short line of an answer: the error text or the id and title of a success."""
    if result.is_error:
        texts = [p.text for p in result.content if isinstance(p, TextContent)]
        return cw.short("is_error " + " ".join(texts), 200)
    data = payload(result)
    return f"erfolg id={data.get('id')} title={data.get('title')}"


async def test_named_exceptions_differ_exactly_as_pinned_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every named exception, measured in the normal state with its pinned difference.

    ``notes_create`` (D-28-16): the tagged category is refused with the sentence of a missing
    parent folder, the invented one is created by the Notes app. The created note is booked
    into the world's ledger and its category folder removed here, both read back.
    """
    assert set(NAMED_EXCEPTIONS) == {("notes_create", "category")}, "a new exception needs a pin"
    env = cw.live_env()
    header(env, "ausnahmen")
    extra: list[str] = []
    with cw.canary_world(env, raw=RAW) as world:
        log(f"# stamm={world.stamm} marker={world.marker}")
        cw.mcp_env(monkeypatch, env)
        monkeypatch.delenv("NC_MCP_FILES_ROOT", raising=False)
        try:
            for key in sorted(NAMED_EXCEPTIONS):
                pair = CASES[key](world)
                tagged = await call(world, pair.tool, pair.tagged)
                unknown = await call(world, pair.tool, pair.unknown)
                log(
                    f"AUSNAHME {pair.tool} {key[1]}: getaggt={_brief(tagged)} "
                    f"erfunden={_brief(unknown)}"
                )
                parent = f"The parent folder {world.notes_root}/{world.tagged_category} of "
                pinned_tagged = bool(tagged.is_error) and parent in raw(tagged)
                created = str(payload(unknown).get("id") or "")
                pinned_unknown = not unknown.is_error and created.startswith("note:")
                note_state = (
                    world.harness.note_status(created.split(":", 1)[1]) if pinned_unknown else 0
                )
                cw.check(
                    RAW,
                    "GATE-03",
                    pair.tool,
                    f"ausnahme {key[1]} getaggt abgewiesen",
                    pinned_tagged,
                    _brief(tagged),
                )
                cw.check(
                    RAW,
                    "GATE-03",
                    pair.tool,
                    f"ausnahme {key[1]} erfunden angelegt",
                    pinned_unknown and note_state == 200,
                    f"{_brief(unknown)} notes-GET {note_state}",
                )
        finally:
            extra = cleanup_category(world)
            for entry in extra:
                log(entry)
    assert_cleanup(world, extra)
    assert any(line.startswith("CLEANUP tool note ") for line in world.cleanup_lines)

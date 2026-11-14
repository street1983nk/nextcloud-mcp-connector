"""Phase acceptance: call every tool of the registry once, through a real MCP client over stdio.

This is the proof behind success criterion 1 of phase 1. Not a unit test and not a mock:
the script starts ``nc-mcp`` as a subprocess exactly as Claude Desktop does, speaks the
protocol over the pipe, and calls every tool of the curated set against a real Nextcloud.
A tool that is registered but broken shows up here and nowhere else, because every other
layer either skips the transport or skips the cloud.

Usage::

    docker compose -f compose.test.yml up -d --wait
    bash scripts/bootstrap_test_nc.sh
    set -a && . ./.env.test && set +a
    uv run python scripts/acceptance_all_tools.py

Exit code 0 only when every tool the running registry lists has answered. The expected set
is that list and never a copy of the names in this file: a second list here would be a
second truth about the tool surface, and this project keeps the number of tools in a test
(``tests/contract/test_tool_surface.py``) and never in a document or a script. The check
gets stronger by it rather than weaker, because a tool the registry gained and nobody
added to this run is named by it. The output is a matrix of tool name, verdict and the
first line of the answer, so a failure is attributable without a rerun.

Exit code 1 means a tool failed or was never called. Exit code 3 means that every tool
answered and one step met a missing prerequisite of the test instance (verdict ``PREREQ``):
that is neither a pass nor a tool failure, and the line names what the instance lacks. The
one such step is the full text of a mail. The Mail app lists messages out of its own cache,
so a mail server that lost them still shows a list; the GreenMail of the test topology keeps
mail in memory and is empty after every restart. When ``fetch`` fails on a listed message,
the script asks the Mail app of the instance for the same message with the same account,
past the connector. Only when the Mail app itself answers with a server error is the step a
``PREREQ``; if the Mail app answers and the tool did not, it is a ``FAIL``.

The calls build on each other on purpose: the file uploaded in step one is the file that
``files_read``, ``unified_search``, ``search`` and ``fetch`` look for later. A tool that
answers "no hits" for an object created seconds earlier is a failure, not an empty result,
and only a chained run can tell those two apart.

Deck, Tables and Talk are the three exceptions. A board, a stack, a table, a column and a
conversation are not connector features (the server cannot create any of them, by design),
so the script uses what the instance already holds and reports the write as skipped when
there is nothing to write into. For Tables that check has two halves, because two refusals
of the connector are correct behaviour rather than a defect: a table shared without a write
permission, and a row that leaves a mandatory column empty. The script therefore only
considers tables with ``can_create`` and only writes when a text marker fits into every
mandatory column of one. For Talk the same holds with one field, ``can_send``: a read only
conversation and the changelog conversation of the account are refused by design, so a run
without a conversation this account may write into is a skip and never a failure.

Mail is the fourth of that kind and the most likely to skip of them all, because a mail
account is not something this server can create either, and a test instance usually has none.
An account list that comes back empty is a success with zero accounts, so the run says so and
walks on; the same holds one level deeper for an account without a single mailbox. Nothing is
written in this family at all: there is no ``mail_send`` to call, by design.

Tasks are created without naming a list (the test account has one own task list), found by
their id with ``tasks_search``, and read twice, with ``tasks_read`` and with ``fetch``; the two
readers have to agree on id, title and status.

With ``NC_MCP_TASKS_UPDATE=on`` in the environment of this script the server is started with
it, and the chain goes on with the three modifying task tools: ``tasks_update`` with the ETag
of ``tasks_read``, ``tasks_complete`` with the ETag that answer handed back, ``tasks_move``
into the list the task is in (the test account has one own list, so this is the success
without a relocation; the real relocation between two lists is the canary's), and at the end
``tasks_update`` once more with the very first ETag, which is stale by then and has to be
refused. With the switch off the three are named as not registered and are not called.

``fetch`` is called once per id kind that needs an object of this instance, and every one of
those ids comes out of a read of the same run: a ``fetch("mail:<number>")`` on a guessed number
would be a request about somebody's mail, and ``message:`` and ``table:`` are no different. A
read that found nothing is a SKIP whose reason says which of the two dead ends it was, because
"this instance holds no such object" and "the call before this one failed" are answered by two
different next steps and only one of them is a defect.
"""

import asyncio
import base64
import io
import json
import os
import sys
import time
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

REQUIRED_ENV = ("NC_MCP_URL", "NC_MCP_USER", "NC_MCP_APP_PASSWORD")

#: Switches handed on to the server when they are set here; nothing else of this environment is.
FORWARDED_SWITCHES = ("NC_MCP_FILES_UPDATE", "NC_MCP_TASKS_UPDATE")

#: The modifying task tools, registered only behind ``NC_MCP_TASKS_UPDATE`` (TMOD-05).
MODIFY_TASK_TOOLS = ("tasks_update", "tasks_complete", "tasks_move")

#: The one tool of the mail family, called at three levels in a row. The name lives in a
#: constant because the chain below would otherwise carry the same string five times, and five
#: copies of a tool name are five places to miss when that tool is renamed.
MAIL_BROWSE = "mail_browse"

#: The verdict of a step that met a missing prerequisite of the test instance: not a pass,
#: not a tool failure. It has an exit code of its own, see the module docstring.
PREREQ = "PREREQ"
EXIT_PREREQ = 3
SERVER_ERROR = 500

#: The type of the one document this run converts with ``files_read_as_markdown``.
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

#: The conversation Talk creates for every account to announce its own new features. It is
#: read only by design, so a send into it is a refusal of the connector working correctly.
CHANGELOG_TYPE = 4


class Report:
    """Verdict per tool, in call order."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, tool: str, verdict: str, detail: str) -> None:
        flat = " ".join(str(detail).split())
        # A missing prerequisite keeps its whole reason: it is the one line somebody has
        # to act on outside this repository.
        self.rows.append((tool, verdict, flat if verdict == PREREQ else flat[:110]))
        print(f"  {verdict:<7} {tool:<22} {flat[:90]}", flush=True)

    def failures(self) -> list[str]:
        return [tool for tool, verdict, _ in self.rows if verdict == "FAIL"]

    def prerequisites(self) -> list[str]:
        """The full reason of every step that met a missing prerequisite of the instance."""
        return [f"{tool}: {detail}" for tool, verdict, detail in self.rows if verdict == PREREQ]

    def called(self) -> set[str]:
        return {tool for tool, verdict, _ in self.rows if verdict in ("OK", "SKIP")}


def text_of(result: Any) -> str:
    """First text block of a tool result, whatever the tool returns."""
    for block in result.content:
        if isinstance(block, TextContent):
            return block.text
    return ""


async def call(client: Client, report: Report, tool: str, arguments: dict[str, Any]) -> str:
    try:
        result = await client.call_tool(tool, arguments)
    # Broad on purpose: one broken tool must not end the run, it must land in the matrix.
    except Exception as exc:
        report.add(tool, "FAIL", f"{type(exc).__name__}: {exc}")
        return ""
    payload = text_of(result)
    if result.is_error:
        report.add(tool, "FAIL", payload)
        return ""
    report.add(tool, "OK", payload)
    return payload


def _minimal_docx(text: str) -> bytes:
    """The smallest Word file the converter opens: one paragraph, no styles part."""
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    body = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/word/document.xml" ContentType="{DOCX_TYPE}.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}" Target="word/document.xml"/></Relationships>',
        )
        archive.writestr("word/document.xml", body)
    return buffer.getvalue()


def loads(payload: str) -> dict[str, Any]:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def run(client: Client, report: Report) -> set[str]:
    """Call every tool once and hand back the names the registry answered ``tools/list`` with.

    That set is the expected set of this run. It is read here and not written down anywhere in
    this file on purpose: the number of tools lives in ``tests/contract/test_tool_surface.py``,
    and a copy of the names beside it would drift without a single test noticing. An empty
    answer is the one thing this reading cannot interpret, so it is a FAIL of its own rather
    than an expected set nothing can fall out of.
    """
    marker = f"abnahme{uuid.uuid4().hex[:10]}"
    stamp = time.strftime("%Y%m%d-%H%M%S")

    listed = await client.list_tools()
    names = sorted(tool.name for tool in listed.tools)
    print(f"tools/list: {len(names)} tools: {', '.join(names)}\n")
    if not names:
        report.add("tools/list", "FAIL", "the registry answered with no tool at all")

    # --- files ------------------------------------------------------------------------
    path = f"/{marker}-{stamp}.md"
    await call(
        client,
        report,
        "files_upload",
        {"path": path, "content": f"# {marker}\nAbnahmelauf Phase 1, Straßenbau.\n"},
    )
    # Twice on purpose: the first call creates the chain, the second finds it and has to
    # say so. A second created true would mean the tool does not see its own folder.
    folder = {"path": f"/{marker}-{stamp}-ordner/a/b", "parents": True}
    await call(client, report, "files_create_folder", folder)
    again = await call(client, report, "files_create_folder", folder)
    if again and loads(again).get("created") is not False:
        report.add(
            "files_create_folder",
            "FAIL",
            f"the second call did not answer created false: {again.splitlines()[0]}",
        )
    found = loads(await call(client, report, "files_search", {"query": marker}))
    # The hit of the uploaded file, by its path and never by its position: the folder
    # created above carries the marker as well and may be listed first, and a fetch of a
    # folder is refused by design.
    uploaded = [
        item
        for item in (found.get("items") or [])
        if isinstance(item, dict) and item.get("path") == path
    ]
    if not uploaded:
        report.add("files_search", "FAIL", "the file uploaded one second ago was not found")
    file_id = str(uploaded[0].get("id", "")) if uploaded else ""

    await call(client, report, "files_list", {"path": "/"})
    await call(client, report, "files_read", {"path": path})
    await call(client, report, "files_download", {"path": path})

    # files_read_as_markdown refuses text by design, so it needs a document of its own. The
    # smallest Word file goes up through the binary path of files_upload and is read back
    # as Markdown; a conversion that loses the marker is a failure, not an empty document.
    document = _minimal_docx(f"Abnahmelauf {marker}")
    document_path = f"/{marker}-{stamp}.docx"
    sent = await call(
        client,
        report,
        "files_upload",
        {
            "path": document_path,
            "content_base64": base64.b64encode(document).decode("ascii"),
            "total_bytes": len(document),
            "final": True,
            "content_type": DOCX_TYPE,
        },
    )
    if sent:
        converted = await call(client, report, "files_read_as_markdown", {"path": document_path})
        if converted and marker not in str(loads(converted).get("content") or ""):
            report.add(
                "files_read_as_markdown",
                "FAIL",
                f"the Markdown does not carry the marker: {converted.splitlines()[0]}",
            )
    else:
        report.add(
            "files_read_as_markdown",
            "FAIL",
            "the upload of the document failed, so there is nothing to convert",
        )

    # --- calendar ---------------------------------------------------------------------
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)
    end = start + timedelta(hours=1)
    await call(
        client,
        report,
        "calendar_create_event",
        {
            "summary": f"Abnahme {marker}",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": "Europe/Berlin",
        },
    )
    await call(
        client,
        report,
        "calendar_list_events",
        {
            "start": (start - timedelta(hours=1)).isoformat(),
            "end": (end + timedelta(hours=1)).isoformat(),
        },
    )

    # --- tasks ------------------------------------------------------------------------
    await _tasks(client, report, marker, registered=set(names))

    # --- notes ------------------------------------------------------------------------
    created = loads(
        await call(
            client,
            report,
            "notes_create",
            {"title": f"Abnahme {marker}", "content": f"Abnahmelauf {marker}"},
        )
    )
    note_id = str(created.get("id") or "").removeprefix("note:")
    await call(client, report, "notes_search", {"query": marker})
    if note_id:
        await call(client, report, "notes_read", {"note_id": note_id})
    else:
        report.add("notes_read", "FAIL", "notes_create returned no id to read back")

    # --- deck -------------------------------------------------------------------------
    boards = loads(await call(client, report, "deck_browse", {"level": "boards"}))
    board_id = _first_id(boards)
    stack_id = ""
    if board_id:
        stacks = loads(
            await call(client, report, "deck_browse", {"level": "stacks", "board_id": board_id})
        )
        stack_id = _first_id(stacks)
    if board_id and stack_id:
        await call(
            client,
            report,
            "deck_create_card",
            {"board_id": board_id, "stack_id": stack_id, "title": f"Abnahme {marker}"},
        )
    else:
        report.add(
            "deck_create_card",
            "SKIP",
            "no board or stack on this account; the connector cannot create either by design",
        )

    # --- tables -----------------------------------------------------------------------
    # Same exception as Deck, one family later: a table and its columns are not connector
    # features, so the script writes into the table the integration suite leaves behind and
    # reports the write as skipped when there is none.
    #
    # The table is not simply the first one listed, and the column is not simply the first
    # text column. Both shortcuts turn a correctly working connector into a FAIL: a table
    # shared without a write permission is refused by design, and a row that leaves a
    # mandatory column empty is refused by design as well. So only tables with ``can_create``
    # are candidates, and a candidate qualifies only when a text marker fits into every
    # mandatory column of it. If none does, this is a SKIP with a reason, exactly like Deck.
    listing = await call(client, report, "tables_browse", {"level": "tables"})
    tables = loads(listing)
    table_id = ""
    values: dict[str, str] = {}
    for candidate in _writable_tables(tables):
        columns = loads(
            await call(client, report, "tables_browse", {"level": "columns", "table_id": candidate})
        )
        fits = _text_row_for(columns, f"Abnahme {marker}")
        if fits:
            table_id, values = candidate, fits
            break
    if table_id and values:
        await call(
            client,
            report,
            "tables_create_row",
            {"table_id": table_id, "values": json.dumps(values)},
        )
    else:
        report.add(
            "tables_create_row",
            "SKIP",
            "no writable table whose mandatory columns are all text; the connector creates "
            "neither a table nor a column by design",
        )

    # --- talk -------------------------------------------------------------------------
    # The third exception, same reason as Deck and Tables: a conversation is not a connector
    # feature, so the script reads and writes what the instance already holds. The write goes
    # into the first conversation that reports ``can_send`` and is not the changelog
    # conversation of the account, because both of the refusals behind that field are correct
    # behaviour and would otherwise be reported as a broken tool.
    rooms = await call(client, report, "talk_browse", {"level": "conversations"})
    entries = [entry for entry in (loads(rooms).get("results") or []) if isinstance(entry, dict)]
    message_id, message_reason = await _talk_message_id(client, report, rooms, entries)

    writable = _sendable_conversation(entries)
    if writable:
        await call(
            client,
            report,
            "talk_send",
            {"token": writable, "message": f"Abnahmelauf {marker}, Straßenbau."},
        )
    else:
        report.add(
            "talk_send",
            "SKIP",
            "no conversation this account may write into; the connector creates none by design",
        )

    # --- mail -------------------------------------------------------------------------
    # The fourth exception, and the one that skips most often: a mail account is not a
    # connector feature either, and an account list that comes back empty is a success with
    # zero accounts rather than a defect. The walk down the three levels lives in a function of
    # its own, because each of its dead ends has to be told apart from a failed call.
    mail_id, mail_reason = await _mail_message_id(client, report)

    # --- contacts, search, chatgpt profile ---------------------------------------------
    await call(client, report, "contacts_search", {"query": "a"})
    await call(client, report, "unified_search", {"query": marker})
    await call(client, report, "prepare_context", {"query": marker})
    await call(client, report, "search", {"query": marker})
    if file_id:
        await call(client, report, "fetch", {"id": file_id})
    else:
        report.add("fetch", "FAIL", "no file id from files_search to resolve")

    # The three id kinds that need an object of this instance, each with an id that came out of
    # a read of this same run and never a guessed one: a fetch("mail:<number>") on a guessed
    # number would be a request about somebody's mail, and message: and table: are no
    # different. Where the id is missing, the reason says whether the instance holds no such
    # object or the read before it failed.
    if mail_id:
        await _fetch_mail(client, report, mail_id)
    else:
        report.add("fetch", "SKIP", mail_reason)
    for identifier, reason in (
        (message_id, message_reason),
        _table_to_fetch(listing),
    ):
        if identifier:
            await call(client, report, "fetch", {"id": identifier})
        else:
            report.add("fetch", "SKIP", reason)

    return set(names)


#: Part of the refusal of ``tasks_create`` without ``list`` when the account has more than one
#: own task list to write to. On the test instance that is a broken prerequisite of this run.
TASKS_MORE_THAN_ONE = "more than one task list"


async def _tasks(client: Client, report: Report, marker: str, *, registered: set[str]) -> None:
    """Create a task, find it by its id, read it with ``tasks_read`` and ``fetch``, compare.

    ``tasks_create`` names no list on purpose: the account of the test instance holds exactly
    one own task list (``personal``), and that is the one case in which the tool picks the
    target itself (E4). A refusal with "more than one" therefore fails with that sentence
    instead of hiding behind a list name. The hit is matched by id, never by position, and
    the two readers have to describe the same task: same title, same status.
    """
    summary = f"Abnahme {marker}"
    try:
        result = await client.call_tool("tasks_create", {"summary": summary})
    # Broad on purpose, as in call(): one broken tool must land in the matrix.
    except Exception as exc:
        report.add("tasks_create", "FAIL", f"{type(exc).__name__}: {exc}")
        result = None
    text = text_of(result) if result is not None else ""
    if result is not None and result.is_error:
        if TASKS_MORE_THAN_ONE in text:
            report.add(
                "tasks_create",
                "FAIL",
                f"the test account should hold one own task list and holds more: {text}",
            )
        else:
            report.add("tasks_create", "FAIL", text)
    elif result is not None:
        report.add("tasks_create", "OK", text)
    task_id = str(loads(text).get("id") or "") if result is not None and not result.is_error else ""
    if not task_id:
        for tool in ("tasks_search", "tasks_read"):
            report.add(tool, "FAIL", "tasks_create returned no id to look for")
        report.add("fetch", "FAIL", "tasks_create returned no task id to fetch")
        return

    found = loads(await call(client, report, "tasks_search", {"query": marker}))
    hits = [
        hit
        for hit in (found.get("tasks") or [])
        if isinstance(hit, dict) and hit.get("id") == task_id
    ]
    if not hits:
        report.add("tasks_search", "FAIL", f"the task created one second ago is no hit: {task_id}")

    read = loads(await call(client, report, "tasks_read", {"task_id": task_id}))
    fetched = loads(await call(client, report, "fetch", {"id": task_id}))
    if not read or not fetched:
        return
    metadata = fetched.get("metadata") if isinstance(fetched.get("metadata"), dict) else {}
    pairs = (
        ("id", read.get("id"), fetched.get("id")),
        ("summary", read.get("summary"), fetched.get("title")),
        ("status", read.get("status"), (metadata or {}).get("status")),
    )
    differing = [f"{name} {left!r} != {right!r}" for name, left, right in pairs if left != right]
    if differing:
        report.add("fetch", "FAIL", f"tasks_read and fetch disagree: {'; '.join(differing)}")

    await _modify_tasks(client, report, marker, task_id, read, registered=registered)


async def _modify_tasks(
    client: Client,
    report: Report,
    marker: str,
    task_id: str,
    read: dict[str, Any],
    *,
    registered: set[str],
) -> None:
    """update, complete and move with the ETag chain, then a stale ETag that must be refused.

    Each step takes the ETag the step before handed back, and reads the task again only when
    an answer carries none. The last call uses the ETag of the very first ``tasks_read``; the
    task changed three times since, so anything but a refusal is a ``FAIL``.
    """
    missing = [tool for tool in MODIFY_TASK_TOOLS if tool not in registered]
    if missing:
        for tool in missing:
            print(f"  {'-':<7} {tool:<22} not registered (switch off)", flush=True)
        return
    first_etag = str(read.get("etag") or "")
    if not first_etag:
        for tool in MODIFY_TASK_TOOLS:
            report.add(tool, "FAIL", "tasks_read handed back no etag to change the task with")
        return

    async def etag_after(answer: dict[str, Any]) -> str:
        if answer.get("etag"):
            return str(answer["etag"])
        again = loads(await call(client, report, "tasks_read", {"task_id": task_id}))
        return str(again.get("etag") or "")

    updated = loads(
        await call(
            client,
            report,
            "tasks_update",
            {"task_id": task_id, "etag": first_etag, "tags": [f"{marker}-tag"]},
        )
    )
    if not updated:
        return
    if updated.get("tags") not in (None, [f"{marker}-tag"]):
        report.add("tasks_update", "FAIL", f"the tag was not set: {updated.get('tags')!r}")
    completed = loads(
        await call(
            client,
            report,
            "tasks_complete",
            {"task_id": task_id, "etag": await etag_after(updated), "completed": True},
        )
    )
    if not completed:
        return
    list_name = str((read.get("list") or {}).get("name") or "")
    moved = loads(
        await call(
            client,
            report,
            "tasks_move",
            {"task_id": task_id, "etag": await etag_after(completed), "list": list_name},
        )
    )
    if moved and moved.get("already") is not True:
        report.add("tasks_move", "FAIL", f"the move into its own list was not a no-op: {moved}")

    stale = await client.call_tool(
        "tasks_update", {"task_id": task_id, "etag": first_etag, "tags": [f"{marker}-alt"]}
    )
    if stale.is_error:
        report.add("tasks_update", "OK", f"stale etag refused: {text_of(stale)}")
    else:
        report.add("tasks_update", "FAIL", f"a stale etag was accepted: {text_of(stale)}")


def _writable_tables(payload: dict[str, Any]) -> list[str]:
    """The ids of the tables this account may add a row to, in the order they were listed.

    ``can_create`` is the field ``tables_browse`` reports for exactly this question (K5). A
    table without it is refused by the connector on purpose, so trying it anyway would report
    a working refusal as a broken tool.
    """
    entries = payload.get("results")
    if not isinstance(entries, list):
        return []
    ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("can_create"):
            continue
        raw = str(entry.get("id", ""))
        if raw:
            ids.append(raw.rsplit(":", 1)[-1])
    return ids


def _text_row_for(payload: dict[str, Any], value: str) -> dict[str, str]:
    """One row that this table would accept, or an empty mapping when there is none.

    Two refusals of the connector are by design and would otherwise look like a failure: a
    text marker in a number column is a 400 of the Tables app, and a row that leaves a
    mandatory column empty never leaves this server at all. So a table qualifies only when all
    of its mandatory columns are text columns, and the row written covers every one of them.
    A table without any mandatory column needs one text column to write into.
    """
    entries = payload.get("results")
    if not isinstance(entries, list):
        return {}
    columns = [entry for entry in entries if isinstance(entry, dict)]
    mandatory = [column for column in columns if column.get("mandatory")]
    if any(column.get("type") != "text" for column in mandatory):
        return {}
    chosen = mandatory or [column for column in columns if column.get("type") == "text"][:1]
    titles = [str(column.get("title") or "") for column in chosen]
    if not titles or not all(titles):
        return {}
    return dict.fromkeys(titles, value)


def _sendable_conversation(entries: list[dict[str, Any]]) -> str:
    """The token of the first conversation this account may write into, or an empty string.

    ``can_send`` is the field ``talk_browse`` reports for exactly this question, and it already
    covers the read only case and the missing chat permission. The changelog conversation is
    excluded a second time by its type, because a run that tries it would report a correct
    refusal of the connector as a defect.
    """
    for entry in entries:
        if not entry.get("can_send") or entry.get("type") == CHANGELOG_TYPE:
            continue
        token = str(entry.get("token") or "")
        if token:
            return token
    return ""


async def _talk_message_id(
    client: Client, report: Report, rooms: str, entries: list[dict[str, Any]]
) -> tuple[str, str]:
    """A ``message:<token>:<id>`` out of two real reads, or an empty id and the true reason.

    Exactly one of the two strings is filled. A call that failed is already a FAIL line in the
    matrix, and this function stays quiet about it instead of adding a SKIP line that claims the
    instance holds no conversation: that reason would be false, and a false reason hides the
    failure it stands next to (review finding IN-04, one family over).
    """
    if not rooms:
        return "", "talk_browse level=conversations failed, so there is no token from a read"
    token = next((str(entry.get("token") or "") for entry in entries if entry.get("token")), "")
    if not token:
        report.add(
            "talk_browse",
            "SKIP",
            "no conversation on this account, so there is no history to read back",
        )
        return "", "no conversation on this account, so there is no Talk message to address"
    history = await call(client, report, "talk_browse", {"level": "messages", "token": token})
    if not history:
        return "", "talk_browse level=messages failed, so there is no message id from a read"
    messages = [item for item in (loads(history).get("results") or []) if isinstance(item, dict)]
    identifier = next((str(item.get("id") or "") for item in messages if item.get("id")), "")
    if not identifier:
        return "", "that conversation holds no readable message, so there is none to fetch"
    return f"message:{token}:{identifier}", ""


def _table_to_fetch(listing: str) -> tuple[str, str]:
    """A ``table:<id>`` out of the listing this run already read, or the true reason for none.

    No second request: the table level was called above, and the first table it listed is one
    this account may read by definition. Reading is enough here, unlike the write further up,
    which needs ``can_create`` and text columns.
    """
    if not listing:
        return "", "tables_browse level=tables failed, so there is no table id from a read"
    identifier = _first_id(loads(listing))
    if not identifier:
        return "", "no table on this account; the connector creates none by design"
    return f"table:{identifier}", ""


async def _mail_message_id(client: Client, report: Report) -> tuple[str, str]:
    """The id of one readable message, or an empty id and the reason there is none.

    Exactly one of the two strings is filled. The three dead ends of this chain are three
    different statements, and none of them is invented: a call that failed is already a FAIL
    line in the matrix, so no SKIP line is written for it at all. Before this shape, a failing
    ``level=mailboxes`` produced a FAIL line **and** a SKIP line saying "that mail account
    lists no mailbox", which was not the reason and covered up the one that was (IN-04).
    """
    accounts = await call(client, report, MAIL_BROWSE, {"level": "accounts"})
    if not accounts:
        return "", f"{MAIL_BROWSE} level=accounts failed, so there is no mail id from a read"
    account_id = _first_id(loads(accounts))
    if not account_id:
        report.add(
            MAIL_BROWSE,
            "SKIP",
            "this account has no mail account, so there are no mailboxes to read",
        )
        return "", "this account has no mail account, so there is no mail full text to fetch"

    mailboxes = await call(
        client, report, MAIL_BROWSE, {"level": "mailboxes", "account_id": account_id}
    )
    if not mailboxes:
        return "", f"{MAIL_BROWSE} level=mailboxes failed, so there is no mail id from a read"
    mailbox_id = _preferred_mailbox(loads(mailboxes))
    if not mailbox_id:
        report.add(
            MAIL_BROWSE,
            "SKIP",
            "that mail account lists no mailbox, so there are no messages to read",
        )
        return "", "that mail account lists no mailbox, so there is no mail full text to fetch"

    messages = await call(
        client, report, MAIL_BROWSE, {"level": "messages", "mailbox_id": mailbox_id}
    )
    if not messages:
        return "", f"{MAIL_BROWSE} level=messages failed, so there is no mail id from a read"
    entries = [item for item in (loads(messages).get("results") or []) if isinstance(item, dict)]
    identifier = next((str(item.get("id") or "") for item in entries if item.get("id")), "")
    if not identifier:
        return "", "that mailbox holds no message, so there is no mail full text to fetch"
    return identifier, ""


async def _fetch_mail(client: Client, report: Report, identifier: str) -> None:
    """``fetch`` of one listed mail, with a failure sorted into tool or test instance.

    A failed ``fetch`` of a mail has two possible owners. The connector, and then it is a
    FAIL like any other. Or the mail server behind the Mail app, which is not a connector
    feature: the Mail app lists messages from its cache and reads the text over IMAP, so
    a mail server that lost its mail (the GreenMail of the test topology after a restart)
    fails exactly here and nowhere before. The Mail app is therefore asked directly, past
    the connector. A server error from the Mail app itself makes this a PREREQ, a missing
    prerequisite of the instance, which is never counted as a pass; any other answer
    leaves the FAIL where it belongs.
    """
    try:
        result = await client.call_tool("fetch", {"id": identifier})
    # Broad on purpose, as in ``call``: one broken tool must land in the matrix.
    except Exception as exc:
        report.add("fetch", "FAIL", f"{type(exc).__name__}: {exc}")
        return
    payload = text_of(result)
    if not result.is_error:
        report.add("fetch", "OK", payload)
        return
    status = await _mail_app_status(identifier)
    if status is not None and status >= SERVER_ERROR:
        report.add(
            "fetch",
            PREREQ,
            f"the Mail app of this instance itself answers HTTP {status} for {identifier}: "
            "its mail server does not hand out a message it lists",
        )
        return
    asked = "did not answer" if status is None else f"answers HTTP {status}"
    report.add("fetch", "FAIL", f"{payload} (the Mail app itself {asked} for that message)")


async def _mail_app_status(identifier: str) -> int | None:
    """The status the Mail app gives for one message when asked past the connector.

    Same instance, same account, same app password as the server under test, and nothing
    of the answer but its status is used. ``None`` when the request itself failed.
    """
    number = identifier.rsplit(":", 1)[-1]
    url = f"{os.environ['NC_MCP_URL'].rstrip('/')}/ocs/v2.php/apps/mail/message/{number}"
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as direct:
            response = await direct.get(
                url,
                headers={"OCS-APIRequest": "true", "Accept": "application/json"},
                auth=(os.environ["NC_MCP_USER"], os.environ["NC_MCP_APP_PASSWORD"]),
            )
    except httpx.HTTPError:
        return None
    return response.status_code


def _preferred_mailbox(payload: dict[str, Any]) -> str:
    """The ``databaseId`` of the inbox of an account, or of the first mailbox it lists.

    The inbox is preferred because it is the one mailbox that carries messages on a test
    instance; a drafts or trash folder that happens to be listed first would answer with an
    empty window and make a working read look like an empty one. ``id`` is already the
    ``databaseId`` here: ``mail_browse`` never passes on the base64 ``id`` of the app.
    """
    entries = [entry for entry in (payload.get("results") or []) if isinstance(entry, dict)]
    inbox = [entry for entry in entries if entry.get("special_role") == "inbox"]
    for entry in [*inbox, *entries]:
        raw = str(entry.get("id", ""))
        if raw:
            return raw
    return ""


def _first_id(payload: dict[str, Any]) -> str:
    for key in ("results", "items", "boards", "stacks"):
        entries = payload.get(key)
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            raw = str(entries[0].get("id", ""))
            return raw.rsplit(":", 1)[-1] if raw else ""
    return ""


async def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(f"missing environment: {', '.join(missing)}", file=sys.stderr)
        print("run: set -a && . ./.env.test && set +a", file=sys.stderr)
        return 2

    command = "nc-mcp.exe" if os.name == "nt" else "nc-mcp"
    parameters = StdioServerParameters(
        command=command,
        args=[],
        env={
            name: os.environ[name]
            for name in (*REQUIRED_ENV, *FORWARDED_SWITCHES)
            if name in os.environ
        },
    )

    print(f"starting {command} over stdio against {os.environ['NC_MCP_URL']}\n")
    report = Report()
    # The transport is handed over unentered: mcp 2.x opens it inside the client.
    async with Client(stdio_client(parameters)) as client:
        registry = await run(client, report)

    print("\n=== acceptance matrix ===")
    for tool, verdict, detail in report.rows:
        print(f"{verdict:<7} {tool:<22} {detail}")

    # The expected set is the registry of the process that just answered, never a list in this
    # file: one truth about the tool surface, and it lives in a test
    # (tests/contract/test_tool_surface.py). A tool this registry gained since the run was
    # written therefore shows up here as never called, which is exactly the case a hand kept
    # list would have missed.
    never_called = registry - report.called()
    failures = report.failures()

    if never_called:
        print(f"\nFAIL: never called: {', '.join(sorted(never_called))}", file=sys.stderr)
    if failures:
        print(f"FAIL: {len(failures)} tools failed: {', '.join(failures)}", file=sys.stderr)
    prerequisites = report.prerequisites()
    for line in prerequisites:
        print(f"\nPREREQ: {line}", file=sys.stderr)
    if never_called or failures:
        return 1
    if prerequisites:
        print(
            f"\nINCOMPLETE: all {len(registry)} tools of the registry answered, but "
            f"{len(prerequisites)} step met a missing prerequisite of the test instance "
            "(see PREREQ above). This is not a pass.",
            file=sys.stderr,
        )
        return EXIT_PREREQ

    print(f"\nOK: all {len(registry)} tools of the registry answered over stdio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

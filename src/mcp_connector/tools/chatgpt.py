"""The ChatGPT compatibility profile: ``search`` and ``fetch`` (D-09, TOOL-07).

Two functions, and both of them are deliberately thin.

**``search`` owns no search.** It calls :func:`mcp_connector.tools.search.unified_search`
and renames its fields. A second hit source here would mean two answers to the same
question, two id schemes and two places to fix pitfall 10, so the only logic in it is the
projection onto the four names OpenAI reads.

**Every hit keeps a link.** ChatGPT renders a citation only while ``url`` is a non-empty
string, so an empty one does not degrade a hit, it removes it from the answer the user
sees. The unified search already guarantees an absolute URL on the configured instance;
the fallbacks below exist so a future provider cannot quietly take the citations away.

**``fetch`` owns no reader.** It parses the id once, through the central codec, and then
calls the tool that already knows how to read that kind. Eight properties of that routing
are load bearing:

* A prefix is never guessed. An unknown one is refused with the list of the valid ones,
  because resolving a Talk message as a note is worse than any error (threat T-01-77).
* A ``url`` id is answered, not fetched. This server never requests a URL that came out of
  a search entry; that is the SSRF door and it stays shut (threat T-01-75).
* The Deck short form is resolved by a sweep over the boards and their stacks, one request
  per board. Deck's internal single card route would be one request instead, but it is
  undocumented and unverified (assumption A4), so it is not used here at all. A unit test
  greps this file for it, which is why it is described rather than spelled out.
* The sweep cache lives inside one call and nowhere else (D-20). A module level cache would
  hand the board list of one user to the next request of another.
* A mail is read as text and as data at the same time. The body is converted, cut at a
  ceiling of its own and marked where it was cut; what Nextcloud believes about the sender
  travels beside that text in ``metadata`` and never inside it, because next to foreign
  content a sentence of this server is indistinguishable from a sentence of the sender
  (threat T-10-28).
* One Talk message is answered by exactly that message or by a sentence. The context route
  hands over a window, so the wanted id is filtered out of it and a missing one is refused;
  answering with the message next to it would be wrong in a way nobody can see (T-11-13). The
  token of that conversation is resolved through the account's own list, so an address out of
  a model answer never reaches the instance in a path (T-11-14).
* A table is answered as an excerpt that says how big the table is: title, row count, the
  first :data:`TABLE_ROWS` rows, cut at :data:`MAX_TABLE_BYTES`. ``tables_browse`` is the way
  to the rest, and a table without a row is a sentence rather than a title on its own.
* A task is read by ``tasks_read``'s own reader, so ``fetch`` and ``tasks_read`` answer one id
  with one task, and the id is resolved against the task discovery only: a Deck list is refused
  before any request, a subscription or an unknown list is an unknown id (E9, K2). Its link is
  the deep link into the Tasks app for an own list and the start page of the app for a shared
  one, because the deep link of a shared list carries the account id of the sharer (D-32-15).
  A description ``tasks_read`` had to cut is marked ``truncated``, and a time without a zone
  is named floating in its line and in the metadata, never read as UTC (W2 of plan 32-09).

**No text of an answer carries a marker this server did not write.** ``text`` is one field
for every kind, so the truncation note of a cut file and the content of a note, a card, a
mail, a chat message, a table cell or a task land in the same place a model reads. Every one of
the eight readers therefore filters the marker sequences out of the foreign text
(:mod:`mcp_connector.tools.marks`), and only the file, the mail and the table reader write one
back in, where a text actually ended; a cut chat message says so beside its text instead,
because phase 9 put no marker into a text every participant of a conversation may write. The
rule sits on all eight and not only on the three that append, because a note that forges the
sequence frames itself exactly the same way (BL-09, ME-03), and a mail is the cheapest place
of all to try it: anybody may write one.
"""

import asyncio
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from .. import ids, provider_map
from ..errors import ToolError
from ..nextcloud import NcClients, capabilities
from ..nextcloud.clients import caldav
from ..nextcloud.clients import dav as dav_client
from ..nextcloud.clients import deck as deck_client
from ..nextcloud.clients import mail as mail_client
from ..nextcloud.clients import tables as tables_client
from ..nextcloud.clients import talk as talk_client
from ..nextcloud.exclusion import TagScope
from . import deck as deck_tools
from . import files as files_tools
from . import html_text, marks, withhold
from . import mail as mail_tools
from . import notes as notes_tools
from . import search as search_tools
from . import tables as tables_tools
from . import talk as talk_tools
from . import tasks as tasks_tools

DEFAULT_LIMIT = search_tools.DEFAULT_LIMIT

#: Ceiling for the text of one fetched file. The cap is the one from ``files_read``, so a
#: fetched file and a read file cost the same context (threat T-01-79).
MAX_TEXT_BYTES = files_tools.DEFAULT_MAX_BYTES

#: Marked inside the text, not only in the metadata: a model that only reads ``text`` must
#: still be able to tell a complete document from the beginning of one. Defined in
#: :mod:`mcp_connector.tools.marks` together with the filter that keeps the sequence this
#: server's own (BL-09, ME-03), and re-exported here under its own name.
TRUNCATION_NOTE = marks.TRUNCATION_NOTE

#: The marker for a cut with nothing behind it, re-exported the same way and from the same
#: module. It is the one a fetched mail carries, because the two others would both lie there:
#: one sends a model to ``files_read`` with an offset a message does not have, the other to
#: ``fetch``, which is the very call that just did the cutting.
FINAL_TRUNCATION = marks.FINAL_TRUNCATION

#: Ceiling for the text of one fetched mail, in bytes of the UTF-8 encoding. Measured in plan
#: 10-01 against Mail 5.11.1 on a live instance: an ordinary 45 KB newsletter arrives as 48811
#: bytes of HTML and becomes 25582 bytes of text after the conversion, so a ceiling of 16 KiB
#: would have cut the normal case. It is deliberately not :data:`MAX_TEXT_BYTES`, because 512
#: KiB of one mail is a context write-off, and just as deliberately not the preview cap of
#: ``mail_browse``, because 400 bytes is half a sentence and not a letter. The number is the
#: smaller half of this decision. The larger half is that every cut is marked and that the
#: marking says something true (threat T-10-32).
MAX_MAIL_BYTES = 32 * 1024

#: The window the context route of Talk is asked for, in messages. One is the smallest window
#: that is guaranteed to carry the wanted message: spreed lifts the history half to
#: ``max(1, limit)`` and fetches it with ``includeLastKnown = true``, then hands the same number
#: to the newer half, so this reads the wanted message plus at most one message after it
#: (measured out of the source of spreed 24.0.4 in plan 11-02). A larger window would cost
#: payload and change nothing about the certainty, because the selection happens here.
MESSAGE_CONTEXT_LIMIT = 1

#: How many rows of a table a fetch hands over. The number 20 is a setting and not a
#: measurement, in the same sense as ``talk.MAX_MESSAGE_BYTES``: a table has no natural
#: excerpt, so somebody has to decide what "the first rows" means. Twenty is a screen of rows,
#: it is below the default window of ``tables_browse`` (25) on purpose, because this answer is
#: an excerpt beside a total and not a page of a walk, and the total beside it is what keeps
#: the excerpt honest. ``tables_browse`` is the way to the rest, and it pages.
TABLE_ROWS = 20

#: Ceiling for the text of one fetched table, in bytes of the UTF-8 encoding. Also a setting:
#: :data:`TABLE_ROWS` bounds the number of rows, and this one bounds what those rows may cost,
#: because a single cell of a text column carries up to 40.000 characters and twenty of them
#: would be one megabyte. Four KiB is roughly twenty rows of eight columns of twenty
#: characters, so the ordinary table arrives whole and the pathological wide one is cut. It is
#: deliberately an eighth of :data:`MAX_MAIL_BYTES`: a letter is meant to be read from
#: beginning to end, a table excerpt is meant to say what is in the table.
MAX_TABLE_BYTES = 4 * 1024

#: Month view of the Calendar app. The event itself is read over CalDAV and needs no app;
#: this link needs the Calendar web interface, which is what a human opens.
CALENDAR_WEB_PREFIX = "/index.php/apps/calendar/dayGridMonth"

#: The Mail app, as the page a human opens after reading a mail here. Mail 5.11.1 has no
#: verified web route to one single message, and a link built on a guess is worse than a link
#: to the app, because it opens an error page instead of a mail. Like every other link of this
#: module it is built from ``creds.base_url`` and never taken out of an answer: a message
#: carries several addresses that its sender chose, and this server neither requests one of
#: them nor hands one on as the link of a result (threat T-10-30).
MAIL_WEB_PREFIX = "/index.php/apps/mail"

#: A mail without a subject is an ordinary mail, and an empty title is not readable in a
#: citation list, which is the same reason the search projection falls back to the id.
_NO_SUBJECT = "(no subject)"

#: The same fallback for the two kinds of this phase. A conversation always has a display name
#: on a healthy instance, and a table always has a title, so both of these are what a deformed
#: answer produces; an empty title is not readable in a citation list either way.
_NO_CONVERSATION = "(conversation without a name)"
_NO_TABLE_TITLE = "(table without a title)"
_NO_TASK_SUMMARY = "(task without a summary)"

#: The key of a shared task list: ``s`` plus sixteen hex characters (``ids.task_list_key``). Such
#: a key is a hash and not a URI, so no deep link can be built from it, and the task gets the
#: start page of the Tasks app like every task of a shared list.
_HASHED_LIST_KEY = re.compile(r"s[0-9a-f]{16}")

#: The fields of a task that become a line of the fetched text, in this order, with their label.
_TASK_LINES: tuple[tuple[str, str], ...] = (
    ("status", "Status"),
    ("due", "Due"),
    ("start", "Start"),
    ("priority", "Priority"),
    ("completed", "Completed"),
)

#: Added to the line of a task time that carries no zone, as ``tasks_read`` marks it with
#: ``<field>_floating``: a floating time is a wall time and never UTC (W2 of plan 32-09).
_FLOATING_NOTE = " (floating, no time zone)"

#: A file id the batch lookup may take: ASCII digits, the same rule as the DAV layer.
#: Anything else goes the single lookup and gets the error it always got there.
_FILEID = re.compile(r"[0-9]+")

#: What a failed :func:`file_entries` may raise. A caller that catches exactly these takes
#: the single lookup instead, which then words the failure as it always did.
LOOKUP_FAILURES: tuple[type[Exception], ...] = (ToolError, httpx.HTTPError, ValueError)

_UNFETCHABLE = "This search result cannot be fetched: it belongs to an app this server cannot read."


async def search(
    clients: NcClients,
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, str]]:
    """Search the whole Nextcloud and project the hits onto the OpenAI field names.

    An empty query is refused by the unified search itself, with the hint that explains
    what a usable term looks like. Catching it here as well would only duplicate a message
    that is already right.
    """
    answer = await search_tools.unified_search(clients, query=query, limit=limit)
    return [_as_hit(clients, hit) for hit in _entries(answer)]


def _entries(answer: dict[str, Any]) -> list[dict[str, Any]]:
    results = answer.get("results")
    return [hit for hit in results if isinstance(hit, dict)] if isinstance(results, list) else []


def _as_hit(clients: NcClients, hit: dict[str, Any]) -> dict[str, str]:
    """One unified search hit as the four fields of the OpenAI contract.

    The two fallbacks are not cosmetic. A hit without a title is unreadable in a citation
    list, and the id at least names the resource; a hit without a url is not cited at all,
    and the instance root is still a page the user can open.
    """
    identifier = str(hit.get("id") or "")
    return {
        "id": identifier,
        "title": str(hit.get("title") or "") or identifier,
        "url": str(hit.get("url") or "") or clients.creds.base_url,
        "text": str(hit.get("subline") or ""),
    }


async def fetch(
    clients: NcClients,
    resource_id: str,
    *,
    max_bytes: int | None = None,
    resolved: Mapping[str, dict[str, Any] | None] | None = None,
    note_batch: notes_tools.NoteBatch | None = None,
) -> dict[str, Any]:
    """Read one search result in full and answer in the OpenAI fetch shape.

    The parameter is called ``resource_id`` inside the package and ``id`` on the wire: the
    wire name is the OpenAI contract, the Python name is not allowed to shadow a builtin.

    ``max_bytes`` exists for Python callers and is not on the wire: the registered tool has
    two parameters and keeps them (schema diet), so the ChatGPT contract is unchanged. It
    is how ``prepare_context`` reads a file for a two kilobyte excerpt without pulling the
    whole slice ceiling over the wire first (LO-06). ``None`` is the ceiling this tool
    always used, so every existing caller reads exactly what it read before. Only the file
    reader slices; for the other four kinds a document is one call and the limit has
    nothing to apply to. A mail is not an exception to that: it arrives whole or not at all,
    and what it is cut to is a ceiling of its own (:data:`MAX_MAIL_BYTES`), because a slice
    of it cannot be continued by a second call.

    ``resolved`` is Python only as well: the answer of :func:`file_entries` for the file
    ids of the same tool call, so a bundle of several file excerpts pays one file id
    SEARCH instead of one per excerpt (plan 27-09). An id it does not contain goes the
    single lookup; the other kinds ignore it.

    ``note_batch`` is the note side of the same idea (plan 27-10): an awaitable over that
    lookup, handed to ``notes.read`` so a note excerpt checks its path in the SEARCH of the
    bundle instead of one of its own. Only a note reads it, and only where it needs a path.
    """
    kind, parts = ids.parse(resource_id)
    match kind:
        case "file":
            return await _fetch_file(clients, parts[0], max_bytes, resolved)
        case "note":
            return await _fetch_note(clients, parts[0], note_batch)
        case "card":
            return await _fetch_card(clients, parts)
        case "event":
            return await _fetch_event(clients, parts[0], parts[1])
        case "mail":
            return await _fetch_mail(clients, parts[0])
        case "message":
            return await _fetch_message(clients, parts[0], parts[1])
        case "table":
            return await _fetch_table(clients, parts[0])
        case "task":
            return await _fetch_task(clients, resource_id)
        case _:
            raise ToolError(
                message=_UNFETCHABLE,
                hint=f"Open the url in a browser to read it: {parts[0]}",
            )


async def file_entries(
    clients: NcClients,
    identifiers: Sequence[str],
    *,
    kinds: tuple[str, ...] = ("file",),
) -> dict[str, dict[str, Any] | None]:
    """Resolve the file ids among ``identifiers`` with one lookup, for one tool call.

    Only ``<kind>:<digits>`` ids of a kind in ``kinds`` are taken, by default files only;
    every other or unparsable id is passed over and later goes its own way through
    :func:`fetch`, with exactly the error it always had. With ``"note"`` in ``kinds`` the
    note ids join the same SEARCH, because a note id is the file id of the note's file
    (25-MESSBERICHT K4, plan 27-10); an id that is both a file and a note id is asked once.
    The answer maps a file id onto its entry, onto ``None`` when it certainly belongs to
    no file inside the sandbox, and leaves out an id the batch could not settle
    (:func:`dav_client.entries_of_fileids`), which then goes the single lookup.

    A failure of the lookup (:data:`LOOKUP_FAILURES`) is left to the caller, whose answer
    is to take the single route. Nothing is kept: no module
    variable, no cache, the entries belong to this one call (E3, D-25-05).
    """
    wanted: list[str] = []
    for identifier in identifiers:
        try:
            kind, parts = ids.parse(identifier)
        except ToolError:
            continue
        if kind in kinds and _FILEID.fullmatch(parts[0]):
            wanted.append(parts[0])
    wanted = list(dict.fromkeys(wanted))
    if not wanted:
        return {}
    return await dav_client.entries_of_fileids(clients.client, clients.creds, wanted)


async def _fetch_file(
    clients: NcClients,
    fileid: str,
    max_bytes: int | None = None,
    resolved: Mapping[str, dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Turn a file id back into a path, then read that path with the ordinary reader.

    A file id known from before the tag answers like an unknown one (EXCL-03, success
    criterion 2). The guard and the lookup run side by side, and the answers are read in the
    order of ``files._visible_stat``: an error of the guard, then ``unverifiable``, then an
    error of the lookup, then the tag (D-28-17), because a failing lookup must answer a
    tagged id and an unknown one alike. A tagged id is refused before any path is looked at,
    a path below a tagged folder right after the lookup, both with :func:`_no_file`, the
    very error of an id that belongs to no file. When the check cannot be answered, every
    id gets ``withhold.unavailable_error()``, so the refusal itself tells nothing about the
    id. ``files_tools.read`` asks the same
    guard of the same ``clients`` afterwards and gets the fast path, not a second REPORT.

    ``MAX_TEXT_BYTES`` is read here and not bound as a default in the signature, so the
    ceiling stays one module level constant that a caller can lower and a test can lower
    for the whole module.

    With ``resolved`` holding this id, the lookup already happened for the whole bundle
    and only the guard is awaited; the decisions below run line for line the same. The
    entry then goes into ``files_tools.read`` as ``known`` on both routes, so the stat
    PROPFIND after the lookup is not asked again (plan 27-09).
    """
    scope: TagScope | BaseException
    entry: dict[str, Any] | BaseException | None
    if resolved is not None and fileid in resolved:
        entry = resolved[fileid]
        scope = await clients.exclusion.scope(clients)
    else:
        scope, entry = await asyncio.gather(
            clients.exclusion.scope(clients),
            dav_client.find_by_fileid(clients.client, clients.creds, fileid),
            return_exceptions=True,
        )
    if isinstance(scope, BaseException):
        raise scope
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    if isinstance(entry, BaseException):
        raise entry
    if scope.excludes(fileid=fileid):
        raise _no_file(fileid)
    if entry is None:
        raise _no_file(fileid)
    path = str(entry["path"])
    if scope.excludes(path=path, fileid=fileid):
        raise _no_file(fileid)

    limit = MAX_TEXT_BYTES if max_bytes is None else max_bytes
    answer = await files_tools.read(clients, path=path, max_bytes=limit, known=entry)

    # The document's own copy of either marker goes before this server writes one of its
    # own (BL-09, ME-03): a complete file that carries the note would claim to be cut, and
    # a cut one could point the model at an offset its author chose.
    text = marks.without_marks(str(answer["content"]))
    metadata = {"kind": "file", "path": path}
    if answer["content_type"]:
        metadata["content_type"] = str(answer["content_type"])
    if answer["truncated"]:
        offset = int(answer["next_offset"])
        text = f"{text}\n\n{TRUNCATION_NOTE.format(offset=offset)}"
        metadata["truncated"] = "true"
        metadata["next_offset"] = str(offset)

    return {
        "id": ids.encode_file(fileid),
        # The file name is foreign text like the content: whoever shares the file chose it,
        # and a marker sequence inside it would claim the framing right beside the filtered
        # text (ME-03, review finding WR-04). Same rule as _fetch_mail and _fetch_table.
        "title": marks.without_marks(path.rsplit("/", 1)[-1] or path),
        "text": text,
        "url": f"{clients.creds.base_url}{provider_map.FILE_WEB_PREFIX}/{fileid}",
        "metadata": metadata,
    }


def _no_file(fileid: str) -> ToolError:
    """The one answer for a file id this account cannot read, whatever the reason.

    An id that belongs to no file, a tagged file and a file below a tagged folder all
    build this very object, so the three cannot be told apart (the pairing tests of phase
    28 compare it byte for byte). No ``reason``, exactly as before phase 27.
    """
    return ToolError(
        message=f"This account has no file with the id {fileid}.",
        hint=(
            "Run search again and use the id from the fresh answer: a file id stops "
            "resolving once the file is deleted or the share is gone."
        ),
    )


async def _fetch_note(
    clients: NcClients,
    note_id: str,
    note_batch: notes_tools.NoteBatch | None = None,
) -> dict[str, Any]:
    """Read one note. The reader checks the Notes app itself, so a missing app is named."""
    note = await notes_tools.read(clients, note_id, batch=note_batch)

    metadata = {"kind": "note"}
    if note.get("category"):
        metadata["category"] = str(note["category"])
    if note.get("modified"):
        metadata["modified"] = str(note["modified"])

    return {
        "id": str(note["id"]),
        # A note title is written by every writer of the note, so it is foreign text like
        # the content beside it and runs through the same filter (review finding WR-04).
        "title": marks.without_marks(str(note["title"])),
        "text": marks.without_marks(str(note["content"])),
        "url": str(note["url"]),
        "metadata": metadata,
    }


async def _fetch_card(clients: NcClients, parts: tuple[str, ...]) -> dict[str, Any]:
    """Read one Deck card, from the canonical triple or from the short search form."""
    await capabilities.require_app(clients, deck_tools.APP)

    if len(parts) == 3:
        board, stack, card_id = parts
        card = await deck_client.get_card(clients.client, clients.creds, board, stack, card_id)
        stack = str(card.get("stackId") or stack)
    else:
        board, stack, card = await _resolve_card(clients, parts[0])

    identifier = str(card.get("id") or (parts[2] if len(parts) == 3 else parts[0]))
    metadata = {"kind": "card", "board": board, "stack": stack}
    if card.get("duedate"):
        metadata["duedate"] = str(card["duedate"])

    return {
        "id": ids.encode_card(board, stack, identifier),
        # A card title is written by every board member, so it is foreign text like the
        # description beside it and runs through the same filter (review finding WR-04).
        "title": marks.without_marks(str(card.get("title") or "")),
        "text": marks.without_marks(str(card.get("description") or "")),
        "url": deck_client.web_url(clients.creds, identifier),
        "metadata": metadata,
    }


async def _resolve_card(clients: NcClients, card_id: str) -> tuple[str, str, dict[str, Any]]:
    """Find board and stack of a card the search provider reported by its id alone.

    One request for the board list plus one per board, and the walk stops at the board that
    holds the card. ``GET /boards/{id}/stacks`` already contains the cards, so there is no
    request per stack and none per card.

    ``seen`` lives for exactly this call. It is not a cache in the sense of D-20 and must
    never become one: board titles and card contents are user data.
    """
    seen: dict[str, list[dict[str, Any]]] = {}
    for board in await deck_client.get_boards(clients.client, clients.creds):
        board_id = str(board.get("id") or "")
        if not board_id or board_id in seen:
            continue
        seen[board_id] = await deck_client.get_stacks(clients.client, clients.creds, board_id)
        for stack in seen[board_id]:
            cards = stack.get("cards")
            for card in cards if isinstance(cards, list) else []:
                if isinstance(card, dict) and str(card.get("id")) == card_id:
                    owning = str(card.get("stackId") or stack.get("id") or "")
                    return board_id, owning, card

    raise ToolError(
        message=f"No card with the id {card_id} is on any board of this account.",
        hint=(
            "Call deck_browse with level=cards to get a full card id of the form "
            "card:<board>:<stack>:<card>."
        ),
    )


async def _fetch_event(clients: NcClients, calendar_uri: str, object_name: str) -> dict[str, Any]:
    """Read one calendar object and render it as the few lines that describe an event."""
    events = await caldav.get_event(clients.client, clients.creds, calendar_uri, object_name)
    if not events:
        raise ToolError(
            message=f"The calendar object {object_name} holds no event.",
            hint="Call calendar_list_events for the window you are interested in.",
        )

    event = events[0]
    start = _instant(event["start"])
    end = _instant(event["end"])

    lines = [
        str(event["summary"]),
        f"Start: {start}",
        f"End: {end}",
        f"All day: {'yes' if event['all_day'] else 'no'}",
        f"Calendar: {event['calendar']}",
    ]
    metadata = {"kind": "event", "calendar": calendar_uri, "start": start, "end": end}
    if event.get("location"):
        lines.append(f"Location: {event['location']}")
        metadata["location"] = str(event["location"])
    if event.get("uid"):
        metadata["uid"] = str(event["uid"])
    if len(events) > 1:
        # One object, several instances: the series was not expanded for a direct GET.
        metadata["instances"] = str(len(events))

    return {
        "id": ids.encode_event(calendar_uri, object_name),
        "title": str(event["summary"]),
        "text": marks.without_marks("\n".join(lines)),
        "url": f"{clients.creds.base_url}{CALENDAR_WEB_PREFIX}/{start[:10]}",
        "metadata": metadata,
    }


async def _fetch_task(clients: NcClients, task_id: str) -> dict[str, Any]:
    """Read one task through ``tasks_read``'s reader and answer in the fetch shape.

    The reader does the whole resolution (discovery, Deck refusal, unknown id), so this
    function adds nothing but the shape: one line per field, the description last, the link
    and four metadata values. Two marks of the reader travel along (W2 of plan 32-09): a cut
    description sets ``truncated``, and a time without a zone carries
    ``(floating, no time zone)`` on its line and ``<field>_floating`` in the metadata. No
    URI of a list reaches the answer: the reader never hands one out, and the deep link is
    built only from the key of an own list, which is its URI.
    """
    task = await tasks_tools.read_task(clients, task_id=task_id)
    _, (list_key, object_name) = ids.parse(str(task["id"]))
    task_list = task["list"]
    shared = bool(task_list["shared"])
    list_name = str(task_list["name"])

    summary = marks.without_marks(str(task.get("summary") or ""))
    lines = [summary or _NO_TASK_SUMMARY]
    for field, label in _TASK_LINES:
        if task.get(field) not in (None, ""):
            note = _FLOATING_NOTE if task.get(f"{field}_floating") else ""
            lines.append(f"{label}: {task[field]}{note}")
    if task.get("tags"):
        lines.append(f"Tags: {', '.join(str(tag) for tag in task['tags'])}")
    lines.append(f"List: {list_name}")
    if task.get("description"):
        lines.append("")
        lines.append(str(task["description"]))

    base = f"{clients.creds.base_url}{provider_map.TASKS_WEB_PREFIX}"
    if shared or _HASHED_LIST_KEY.fullmatch(list_key):
        url = base
    else:
        url = f"{base}calendars/{quote(list_key, safe='')}/tasks/{quote(object_name, safe='')}"

    metadata = {
        "kind": "task",
        "list": list_name,
        "shared": "true" if shared else "false",
        "status": str(task.get("status") or ""),
    }
    if task.get("description_truncated"):
        metadata["truncated"] = "true"
    for field, _ in _TASK_LINES:
        if task.get(f"{field}_floating"):
            metadata[f"{field}_floating"] = "true"

    return {
        "id": str(task["id"]),
        "title": summary or _NO_TASK_SUMMARY,
        "text": marks.without_marks("\n".join(lines)),
        "url": url,
        "metadata": metadata,
    }


def _instant(value: Any) -> str:
    """An ISO 8601 string for a datetime and for a pure all day date alike."""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


async def _fetch_mail(clients: NcClients, message_id: str) -> dict[str, Any]:
    """Read one mail: the body as text, cut at a marked ceiling, the signals beside it.

    The app check is the first line, exactly as in :func:`_fetch_card`. Without it a Nextcloud
    without the Mail app would fall into the 404 branch of the shared status mapping, and that
    one tells a model to search for the message first, which means searching in an app that is
    not there.

    :func:`mail_client.get_message` is called exactly once, and there is no loop, no list and
    no second read for a detail. Every full message read opens an IMAP session inside the Mail
    app, which makes this the most expensive call this server has (threat T-10-33). The brute
    force counter of the app is explicitly not the reason: ``#[BruteForceProtection]`` sits on
    that controller, but ``throttle()`` is never called in the ``lib/`` tree of Mail 5.11.1,
    so the counter does not count.
    """
    await capabilities.require_app(clients, mail_tools.APP)
    message, body_missing = await mail_client.get_message(clients.client, clients.creds, message_id)

    # A message without a body is refused with a sentence rather than answered with an empty
    # success, and the two cases below are the two ways it happens. The pattern is the one of
    # ``_fetch_event``, which turns a calendar object without an event into an error: a
    # successful answer without content is the shape that invites a model to fill the gap
    # itself (threat T-10-34, T-01-75).
    if body_missing:
        raise ToolError(
            message=(
                f"The mail {message_id} was found, but its body could not be decrypted, so "
                "there is no text to read."
            ),
            hint=(
                "Open that message in the Mail app of Nextcloud: an encrypted mail can be "
                "read where its key is, and this connector holds no key."
            ),
        )

    # The body is HTML even when the mail was written as plain text, so the conversion is
    # unconditional and ``hasHtmlBody`` is not consulted at all: the app runs every body
    # through ``convertLinks``, which is ``htmlspecialchars`` plus HTMLPurifier (correction K2
    # of the phase research). A reader that trusted that flag would hand a model
    # ``Gr&uuml;&szlig;e`` and a bare ``<a href=...>`` for every text mail it ever saw.
    text = marks.without_marks(html_text.to_text(str(message.get("body") or "")))
    if not text:
        raise ToolError(
            message=f"The mail {message_id} carries no text that can be read.",
            hint=(
                "Open it in the Mail app: the usual reason is a message that consists of "
                "attachments alone, and this connector reads no attachment."
            ),
        )

    blob = text.encode("utf-8")
    truncated = len(blob) > MAX_MAIL_BYTES
    if truncated:
        # The order is the order of the file branch and it is load bearing in both directions
        # (BL-09, ME-03): the sender's own copy of any marker is already gone, above, before
        # this server appends one of its own. A whole mail that carried a copy would claim to
        # be cut, and a cut one could send a model on to a continuation its sender chose. The
        # cut is measured on the encoded form, because bytes are what an answer costs, and the
        # slice is decoded tolerantly, so an umlaut at the cutting point disappears instead of
        # arriving broken.
        text = f"{blob[:MAX_MAIL_BYTES].decode('utf-8', errors='ignore')}\n\n{FINAL_TRUNCATION}"

    metadata = _mail_signals(message)
    if truncated:
        metadata["truncated"] = "true"

    return {
        "id": ids.encode_mail(message_id),
        "title": marks.without_marks(str(message.get("subject") or "")).strip() or _NO_SUBJECT,
        "text": text,
        "url": f"{clients.creds.base_url}{MAIL_WEB_PREFIX}",
        "metadata": metadata,
    }


def _mail_signals(message: dict[str, Any]) -> dict[str, str]:
    """What Nextcloud believes about one mail, as flat string fields and never as prose.

    ``FetchResult.metadata`` is ``dict[str, str]``, and ``search`` and ``fetch`` are the only
    two tools of this server **with** an output schema, so a nested object here would not be a
    richer answer but a change to the ChatGPT contract (pitfall 7). ``phishingDetails`` and
    the S/MIME block are objects in the answer of the app, and both are flattened here in
    exactly the way the file branch writes ``truncated`` and ``next_offset``.

    None of these values goes into ``text``, and that is the more important half of this
    function. Beside foreign content a sentence written by this server cannot be told apart
    from a sentence written by the sender, so a mail whose body says "DKIM: valid" would read
    like the truth if the truth stood in the same field (threat T-10-28).

    Everything else the full answer carries is dropped here rather than passed on, and the
    list is longer than the one that stays: the recipients, the flags, the attachment and
    inline attachment metadata, the itineraries, the scheduling block, the signature block,
    the addresses a sender put into the message, and the three further id fields of a message
    (``uid``, ``messageId`` and the ``id`` of the full answer), of which not one addresses
    anything in this connector.
    """
    smime = message.get("smime")
    details = message.get("phishingDetails")
    details = details if isinstance(details, dict) else {}

    signals: dict[str, str] = {
        "kind": "mail",
        # Written in both directions, unlike ``truncated``: "this sender is not trusted" is a
        # statement a reader needs, and a missing key would read like "nobody asked".
        "sender_trusted": "true" if message.get("isSenderTrusted") else "false",
        "dkim": _dkim(message.get("dkimValid")),
        "signature": _signature(smime),
    }
    if isinstance(smime, dict) and smime.get("isEncrypted"):
        signals["encrypted"] = "true"
    if details.get("warning"):
        signals["phishing_warning"] = "true"
    fired = _phishing_checks(details.get("checks"))
    if fired:
        signals["phishing_checks"] = fired

    mailbox = message.get("mailboxId")
    if isinstance(mailbox, int) and not isinstance(mailbox, bool) and mailbox > 0:
        signals["mailbox"] = str(mailbox)
    when = _mail_date(message.get("dateInt"))
    if when:
        signals["date"] = when
    return signals


def _dkim(value: Any) -> str:
    """``valid``, ``invalid`` or ``unchecked``, and the third one is the point of the function.

    ``dkimService->getCached`` computes nothing, so a missing ``dkimValid`` means "there is no
    verdict" and not "the verdict is bad". Reading a missing field as ``invalid`` would be a
    false security statement about somebody else's mail, and a false one in the more expensive
    direction (threat T-10-36). The same word covers the mail that carries no signature at
    all: both end in the same next step, and neither of them is a verified sender.
    """
    if isinstance(value, bool):
        return "valid" if value else "invalid"
    return "unchecked"


def _signature(smime: Any) -> str:
    """The S/MIME verdict of a mail as one word, out of an object with three fields.

    ``signatureIsValid`` is nullable, and a signed mail whose signature could not be checked
    is neither of the two obvious answers: ``unsigned`` would hide a signature that is there,
    ``invalid`` would invent a check that failed. It reads ``unchecked``, the same word the
    DKIM verdict uses for the same situation, so one vocabulary covers both.
    """
    fields = smime if isinstance(smime, dict) else {}
    if not fields.get("isSigned"):
        return "unsigned"
    valid = fields.get("signatureIsValid")
    if isinstance(valid, bool):
        return "valid" if valid else "invalid"
    return "unchecked"


def _phishing_checks(checks: Any) -> str:
    """The types of the checks that fired, comma separated, and nothing else out of them.

    One check carries ``type``, ``isPhishing``, ``message`` and ``additionalData``, and only
    the first two are read. ``message`` is a sentence about a mail, so passing it on would put
    prose about foreign content into an answer that is otherwise data, and ``additionalData``
    is a nested object the flat metadata could not carry anyway.
    """
    if not isinstance(checks, list):
        return ""
    fired = [
        str(check.get("type") or "").strip()
        for check in checks
        if isinstance(check, dict) and check.get("isPhishing")
    ]
    return ", ".join(kind for kind in fired if kind)


def _mail_date(value: Any) -> str:
    """``dateInt`` as an ISO timestamp in UTC, or an empty string if there is no usable one.

    The same reading ``mail_browse`` gives an envelope one layer down. A field that arrives as
    a Unix number in one answer of this family and as a readable moment in the other would be
    two truths about the same thing, and a mail date is read by a person as often as by a
    program. A number the standard library cannot turn into a moment is answered with nothing
    rather than with a guess.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return ""
    try:
        return datetime.fromtimestamp(value, tz=UTC).isoformat()
    except (OSError, OverflowError, ValueError):
        return ""


async def _fetch_message(clients: NcClients, token: str, message_id: str) -> dict[str, Any]:
    """Read exactly one Talk message: the text of that message and never of a neighbour.

    The app check is the first line, exactly as in :func:`_fetch_card` and :func:`_fetch_mail`.
    Without it a Nextcloud without Talk falls into the 404 branch of the shared status mapping,
    and that one sends a model searching in an app that is not on the instance.

    The token is then resolved through the conversation list of this account, and the reason is
    **not** the brute force counter of phase 9: the context route carries no
    ``#[BruteForceProtection]``, its participant middleware answers a conversation this account
    is not in with a plain 404. Two reasons remain. The refusal becomes our own sentence
    instead of that foreign 404, and the display name of the conversation is what the title and
    the link of the answer are made of. The price is one additional request per ``fetch``, and
    it is the price the whole Talk family pays: ``talk_browse`` reads the same list before it
    reads a history.

    Two answers of the context route mean the same thing here, and both are refused rather than
    answered: a window that does not carry the wanted message, and the empty window of a 304. A
    message beside the wanted one would be a wrong answer nobody can see (threat T-11-13), and
    an empty success is the shape that invites a model to fill the gap itself (threat T-11-17).

    The selection runs through ``talk_tools.one_message``, so the text arrives with the message
    parameters resolved and the marker sequences of this server removed. A single fetch
    uses the existing fetched-text budget rather than the 800-byte history preview.
    Oversized resolved messages are refused explicitly, never returned as a partial
    success with no way to retrieve the missing tail.

    The ``kein-ki`` guard is inherited twice: ``one_room`` refuses a file conversation of a
    withheld file like an unknown token, and the file screen of the talk module keeps the
    placeholder of a withheld file raw. The title stays the conversation name; for a withheld
    file conversation this line is never reached.
    """
    await capabilities.require_app(clients, talk_tools.APP)
    room = await talk_tools.one_room(clients, token, include_last_message=False)
    window = await talk_client.get_message_context(
        clients.client, clients.creds, token, message_id, limit=MESSAGE_CONTEXT_LIMIT
    )

    # Only the wanted message is screened: a file beside it in the context window is never
    # shown, so it must neither cost a guard request nor mark this answer as degraded.
    wanted = str(message_id).strip()
    screen = await talk_tools.file_screen(
        clients, [raw for raw in window if str(raw.get("id")) == wanted]
    )
    entry = talk_tools.one_message(window, message_id, screen=screen, max_bytes=MAX_TEXT_BYTES)
    if entry is None:
        raise ToolError(
            message=(
                f"The message {message_id} cannot be read in the conversation {token}: either it "
                "was deleted, or it is a system message this server does not pass on as content."
            ),
            hint=(
                'Call talk_browse with level="messages" and this token to see what the '
                "conversation carries now; the ids in that answer can be fetched."
            ),
        )

    actor = str(entry.get("actor") or "")
    body = str(entry.get("message") or "")
    # The author as the first line, in the shape of ``_fetch_event``'s line list. A chat
    # message without the person who wrote it is barely readable, and unlike the trust signals
    # of a mail this is content of the conversation rather than a verdict of this server; it
    # stands in ``metadata`` as well, so a caller that reads only fields has it too.
    lines = [f"From: {actor}", body] if actor else [body]

    metadata = {
        "kind": "message",
        "conversation": token,
        "message_id": message_id,
        "actor": actor,
    }
    timestamp = entry.get("timestamp")
    if isinstance(timestamp, int) and not isinstance(timestamp, bool) and timestamp > 0:
        # The Unix number of the app, as ``talk_browse`` hands it over one level up: a second
        # reading of the same field would be a second truth about when this was written.
        metadata["timestamp"] = str(timestamp)
    if entry.get("message_truncated"):
        raise ToolError(
            message="The resolved Talk message exceeds the fetched-text byte budget.",
            hint="Open this message in Nextcloud Talk to read it in full.",
        )
    if screen.unavailable:
        # A message is not a file: it stays readable with its file placeholders raw, and the
        # one sentence says why (D-27-05, D-27-06).
        metadata["degraded"] = withhold.EXCLUSION_UNAVAILABLE

    return {
        "id": ids.encode_message(token, message_id),
        # The name of the conversation, and never the text of the message. A title reads like a
        # summary written by this server, and that text was written by somebody else.
        "title": marks.without_marks(str(room.get("displayName") or "")).strip()
        or _NO_CONVERSATION,
        "text": "\n".join(lines),
        "url": talk_client.web_url(clients.creds, token),
        "metadata": metadata,
    }


async def _fetch_table(clients: NcClients, table_id: str) -> dict[str, Any]:
    """Read one table as an excerpt: its title, how many rows it has, and its first rows.

    This answer shape is a decision and it is named as one (assumption A4 of the phase research,
    confirmed here). A table is not a document, so "the first rows" is a setting of this server
    (:data:`TABLE_ROWS`) and not a property of the thing being read. What keeps the excerpt
    honest is the total number beside it, so a model reads how much of the table it did not get,
    and ``tables_browse`` is the way to the rest: it pages, this does not.

    One request per statement. The table itself answers its title and its row count together
    (K11), and the rows are read exactly once, with the ceiling as a keyword. There is no
    second round for the column titles, because the compact row form ships them as its first
    list, and no paging, because ``fetch`` hands over an excerpt.

    A table without a single row is refused rather than answered, in the shape of
    :func:`_fetch_event`: an answer that consists of a title and nothing else is the empty
    success that invites a model to fill the gap itself (threat T-11-17). An answer that carries
    the header row alone is the same case, because that row is the shape of the table and not
    its content.

    The rows pass the same ``tables_tools.screen_links`` as ``tables_browse`` before a cell is
    rendered (D-28-14): a link cell of a file tagged ``kein-ki`` answers like an empty one, and
    when the check could not be answered every file link is withheld and ``metadata`` says so.
    A withheld cell is still a cell, so a row that carried nothing else still counts as a row.
    """
    await capabilities.require_app(clients, tables_tools.APP)
    table = await tables_client.get_table(clients.client, clients.creds, table_id)
    rows = await tables_client.get_rows_simple(
        clients.client, clients.creds, table_id, limit=TABLE_ROWS
    )
    screened = await tables_tools.screen_links(clients, rows)
    rows = screened.rows

    shown = max(len(rows) - 1, 0)
    if not shown:
        raise ToolError(
            message=f"The table {table_id} exists, but it carries no row.",
            hint=(
                "Call tables_browse with level=columns to see what this table expects, and "
                "level=rows once somebody has added a row to it."
            ),
        )

    total = _table_total(table, shown)
    # The order is the order of the mail branch and it is load bearing in both directions
    # (BL-09, ME-03): every cell has already lost its own copy of any marker inside
    # ``as_text``, before this server appends one of its own. A whole table that carried a copy
    # would claim to be cut, and a cut one could send a model on to a continuation whoever
    # writes into that table chose.
    text = "\n".join(tables_tools.as_text(str(table.get("title") or ""), rows, total))
    blob = text.encode("utf-8")
    truncated = len(blob) > MAX_TABLE_BYTES
    if truncated:
        # The same marker the mail branch uses, for the same reason: the other two would send a
        # model to ``files_read`` with an offset a table has not got, or back into the call that
        # just did the cutting. That there are more rows is said by the row count in the text,
        # not by the marker.
        text = f"{blob[:MAX_TABLE_BYTES].decode('utf-8', errors='ignore')}\n\n{FINAL_TRUNCATION}"

    metadata = {
        "kind": "table",
        "table_id": table_id,
        "rows_total": str(total),
        "rows_shown": str(shown),
    }
    if truncated:
        metadata["truncated"] = "true"
    if screened.unavailable:
        metadata["degraded"] = withhold.EXCLUSION_UNAVAILABLE

    return {
        "id": ids.encode_table(table_id),
        "title": marks.without_marks(str(table.get("title") or "")).strip() or _NO_TABLE_TITLE,
        "text": text,
        "url": tables_client.web_url(clients.creds, table_id),
        "metadata": metadata,
    }


def _table_total(table: dict[str, Any], shown: int) -> int:
    """The row count of a table, falling back to the number of rows actually read.

    ``tools/tables.py`` leaves its ``rowsCount`` field out when the app reports no usable one,
    because a wrong count there would make its own truncation check unreachable and turn a cut
    into a silent one. Here the number is part of the sentence that says how much of the table
    this excerpt is, so leaving it out is not an option and the fallback is the one number that
    is certainly true: what was just read. The same fallback catches a counter below the window,
    which is the one case in which the app's own number is demonstrably wrong (the counter of
    Tables drifts, which is why ``tables_browse`` guards its next handle with it).
    """
    count = table.get("rowsCount")
    if isinstance(count, bool) or not isinstance(count, int) or count < shown:
        return shown
    return count

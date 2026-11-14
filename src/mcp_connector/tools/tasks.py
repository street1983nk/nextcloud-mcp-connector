"""Task tools: searching and reading the VTODOs of the task lists of an account.

**Times come out the way the object holds them (TASK-04).** A task has no expansion and no
display zone, so every time field is written as it stands: a date stays a date (never
midnight, never the next day), a zoned time keeps its zone and offset, a UTC time stays UTC,
and a floating time stays floating and carries the flag ``<field>_floating``. A floating time
is never reinterpreted as UTC or as the zone of this server; that would move a deadline by
hours without anybody noticing.

**Field shapes.** ``status`` is ``open``, ``in_progress``, ``completed`` or ``cancelled``
(``CANCELLED`` wins, then ``STATUS:COMPLETED`` or a ``COMPLETED`` time, then ``IN-PROCESS``).
``due``, ``start`` and ``completed`` are ISO text. ``priority`` is 1 to 9 and absent for 0.
``tags`` is one flat list over every ``CATEGORIES`` line. ``recurring`` is ``true`` on a
master with ``RRULE`` or ``RDATE``; an override with ``RECURRENCE-ID`` is never a task of its
own. Empty fields are omitted: every key costs tokens in every hit of every answer.

**Foreign text.** Title, description, tags and list names can come from other people through
a shared list. The marker sequences of this server are removed from each of them before
anything else happens (ME-03). Attachments are never read.
"""

import asyncio
import dataclasses
import re
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from icalendar import Calendar as IcsCalendar
from icalendar import Timezone as IcsTimezone
from icalendar import Todo as IcsTodo

from .. import ids, paging
from ..errors import (
    REASON_GUARD_TRIPPED,
    REASON_PERMISSION_DENIED,
    REASON_TIMEOUT,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
from ..nextcloud import NcClients
from ..nextcloud.clients import caldav, dav
from ..nextcloud.clients import tasks as tasks_client
from . import calendar, ics_edit, marks

#: One page of ``tasks_search`` (D-32-08). Fixed on purpose: no ``limit`` parameter, which
#: saves schema bytes in every tool listing.
PAGE_SIZE = 25

#: Wall clock budget of one task list. A slow list becomes a ``degraded`` entry instead of
#: holding the answer hostage. Below this budget the size of the answer of one list is not
#: capped; above it the budget is the cap. Plan 32-02 measured the REPORT of 2000 tasks of which
#: 100 were open (at most 0.113 s, budget 1 s). Plan 32-10 measured a whole call with 2000 OPEN
#: tasks in one list (discovery, REPORT and parsing): at most 0.831 s, and with 1 s the first
#: page on Nextcloud 35 was cut off, so the budget follows the rule again. Plan 33-11 measured
#: the first search right after an install of the Tasks app and a restart, seven lists at
#: once: one list took 1.030 s on Nextcloud 32 (a plain restart: at most 0.373 s).
#: MESSWERT per_list_timeout_s=3 regel=max(1,ceil(2*max)) max_s=1.030 quelle=nc32-impersonation
#: (plan 33-11, 2026-11-14, erste Suche nach Installation, raw/33-11-kaltstart.txt,
#: docs/tasks-evidence.md)
PER_LIST_TIMEOUT = 3.0

#: Wall clock budget of the subtask query and the parent lookup of ``tasks_read`` (D-32-03).
#: MESSWERT subtask_timeout_s=1 regel=max(1,ceil(2*max)) max_s=0.107 quelle=nc35-impersonation
#: (plan 32-02, 2026-11-13, docs/tasks-evidence.md)
SUBTASK_TIMEOUT = 1.0

#: Hard ceiling of the paging window: 20 pages of 25, then an honest note.
#: MESSWERT max_results=500 bestaetigt (plan 32-02, 2026-11-13, docs/tasks-evidence.md)
MAX_RESULTS = 500

#: Appended when the answer stopped at :data:`MAX_RESULTS`; without it a capped answer
#: would read like a complete one.
SEARCH_CAP_NOTE = f"result window capped at {MAX_RESULTS} tasks; narrow with query, list or due_by"

#: Cap of the subtask list of ``tasks_read``; above it the answer names the total.
MAX_SUBTASKS = 50

#: Most descendants (children, grandchildren, ...) one call changes along with the named
#: task; above it the call is refused before the first write (D-33-10). Plan 33-01c measured
#: whole chains of 50 on Nextcloud 35 and 32, PUT and relocation, depth 1 and 3: at most
#: 3.688 s, budget 8 s against the limit of 30 s, so the value of D-33-10 stays.
#: MESSWERT chain_cap=50 regel=derive_budget(max_gesamt_s)<=30 budget_s=8 quelle=nc35+nc32
#: (D-33-10 bestätigt)
#: (plan 33-01c, 2026-11-13, raw/33-01-messung.txt, regel derive_budget(max)<=30 s)
CHAIN_CAP = 50

#: Cap of the description of ``tasks_read`` in UTF-8 bytes, the cut is a field beside the
#: text (pattern of the mail preview).
MAX_DESCRIPTION_BYTES = 4096

#: The values of the ``status`` parameter (D-32-09). ``open`` includes ``in_progress``.
STATUS_FILTERS = ("open", "completed", "all")

#: Shown instead of an error when the account has no task list at all (E6).
NO_LIST_HINT = (
    "This account has no task list yet. Create one in the Nextcloud Tasks app; "
    "tasks_search finds its tasks from then on."
)

#: ``tasks_create`` without any task list (E6): an error, because there is nowhere to write.
NO_LIST_MESSAGE = "This account has no task list."
NO_LIST_WAY_OUT = "Create a list in the Nextcloud Tasks app, then try again."

#: The values ``priority`` may take (RFC 5545: 0 undefined, 1 highest, 9 lowest).
PRIORITY_RANGE = range(10)

_TASK_TIME_HINT = (
    "Use a date such as 2026-11-20, or a time with a zone such as 2026-11-20T09:00:00+01:00."
)
_ZONE_HINT = "Use an IANA name such as Europe/Berlin, or leave timezone out."

_OPEN_STATES = frozenset({"open", "in_progress"})
_STATUS_RANK = {"open": 0, "in_progress": 0, "completed": 1, "cancelled": 2}
_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")
_DUE_BY_HINT = (
    "Use a date such as 2026-11-20 or a time with a zone such as 2026-11-20T09:00:00+01:00."
)

#: The time properties of a task and the field each one is written to.
_TIME_FIELDS = (("DUE", "due"), ("DTSTART", "start"), ("COMPLETED", "completed"))

_STATUS_IN_PROGRESS = "IN-PROCESS"


def _time_field(value: date | datetime) -> tuple[str, bool]:
    """ISO text of one time value and whether it is floating. A date never grows a time."""
    if isinstance(value, datetime):
        return value.isoformat(), value.tzinfo is None
    return value.isoformat(), False


def _with_named_zone(value: date | datetime, tzid: Any) -> date | datetime:
    """Attach the zone a ``TZID`` names when icalendar left the time without one.

    icalendar keeps ``TZID`` as a parameter but parses ``COMPLETED`` as a plain date-time,
    so a zoned completion time would read as floating. The wall time stays exactly as
    written; only the zone it was written in is attached. An unknown name leaves the value
    as it is.
    """
    if not isinstance(value, datetime) or value.tzinfo is not None or not tzid:
        return value
    try:
        return value.replace(tzinfo=ZoneInfo(str(tzid).strip()))
    except (ZoneInfoNotFoundError, ValueError):
        return value


def _read_todo(ics: bytes) -> dict[str, Any] | None:
    """Read the master VTODO of one object, or ``None`` when there is none to read.

    ``None`` stands for "skip this object": not valid iCalendar, no VTODO, only overrides,
    or a property in a shape this reader cannot use. One damaged object must not cost the
    whole list. ``uid`` and ``parents`` (the UIDs this task names as its parent) are for the
    parent and child lookups only and never reach an answer.
    """
    try:
        calendar = IcsCalendar.from_ical(ics)
        masters = [
            component
            for component in calendar.walk("VTODO")
            if component.get("RECURRENCE-ID") is None
        ]
        if not masters:
            return None
        return _fields(masters[0])
    except Exception:
        # A foreign object is data, not code: whatever icalendar trips over, the object is
        # skipped and counted by the caller instead of failing the list.
        return None


def _fields(todo: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "uid": str(todo.get("UID") or "").strip(),
        "summary": marks.without_marks(str(todo.get("SUMMARY") or "")),
        "status": _status(todo),
    }
    for prop, field in _TIME_FIELDS:
        raw = todo.get(prop)
        if raw is None:
            continue
        value = _with_named_zone(raw.dt, raw.params.get("TZID"))
        text, floating = _time_field(value)
        result[field] = text
        result[f"_{field}_value"] = value
        if floating:
            result[f"{field}_floating"] = True

    priority = _priority(todo.get("PRIORITY"))
    if priority:
        result["priority"] = priority
    tags = _tags(todo.get("CATEGORIES"))
    if tags:
        result["tags"] = tags
    if todo.get("RRULE") is not None or todo.get("RDATE") is not None:
        result["recurring"] = True
    result["description"] = marks.without_marks(str(todo.get("DESCRIPTION") or ""))
    result["parents"] = _parents(todo.get("RELATED-TO"))
    return result


def _status(todo: Any) -> str:
    status = str(todo.get("STATUS") or "").strip().upper()
    if status == "CANCELLED":
        return "cancelled"
    if status == "COMPLETED" or todo.get("COMPLETED") is not None:
        return "completed"
    if status == _STATUS_IN_PROGRESS:
        return "in_progress"
    return "open"


def _priority(raw: Any) -> int:
    try:
        value = int(str(raw).strip()) if raw is not None else 0
    except ValueError:
        return 0
    return value if 1 <= value <= 9 else 0


def _as_list(raw: Any) -> list[Any]:
    """One property or several lines of it, always as a list (pitfall 11)."""
    if raw is None:
        return []
    return list(raw) if isinstance(raw, list) else [raw]


def _tags(raw: Any) -> list[str]:
    tags: list[str] = []
    for line in _as_list(raw):
        values = getattr(line, "cats", None)
        for value in values if values is not None else [line]:
            tag = marks.without_marks(str(value)).strip()
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def _parents(raw: Any) -> list[str]:
    """The UIDs a task names as its parent: ``RELTYPE`` missing or ``PARENT``."""
    parents: list[str] = []
    for value in _as_list(raw):
        params = getattr(value, "params", {}) or {}
        reltype = str(params.get("RELTYPE", "PARENT")).strip().upper()
        uid = str(value).strip()
        if reltype == "PARENT" and uid and uid not in parents:
            parents.append(uid)
    return parents


async def search_tasks(
    clients: NcClients,
    *,
    query: str | None = None,
    status: str = "open",
    due_by: str | None = None,
    list_name: str | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Search the tasks of the account, own and shared lists, one page of 25 at a time.

    Every input is checked before the first request. Without ``list_name`` every list of the
    discovery is asked at once, each under its own budget; a list that fails is named under
    ``degraded`` and the others still answer. Text and due filters run here and not on the
    server: ``text-match`` cannot combine properties, and a ``time-range`` also returns
    tasks without a due date.
    """
    if status not in STATUS_FILTERS:
        raise ToolError(
            message=f"status must be one of {', '.join(STATUS_FILTERS)} (got {status!r}).",
            hint="Leave status out for open tasks, or pass completed or all.",
            reason=REASON_GUARD_TRIPPED,
        )
    term = (query or "").strip()
    bound_text = (due_by or "").strip()
    bound = _parse_due_by(bound_text) if bound_text else None
    wanted = (list_name or "").strip()

    offset = 0
    if cursor:
        state = paging.decode_cursor(cursor)
        for key, value in (("q", term), ("s", status), ("d", bound_text), ("l", wanted)):
            paging.check_scope(state, key, value, "search")
        offset = paging.read_offset(state)

    lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
    if not lists:
        return {"tasks": [], "hint": NO_LIST_HINT}
    selected = [_resolve_list(lists, wanted)] if wanted else lists

    outcomes = await asyncio.gather(
        *(_search_one(clients, task_list, status) for task_list in selected),
        return_exceptions=True,
    )
    found: list[dict[str, Any]] = []
    degraded: list[dict[str, str]] = []
    skipped = 0
    for task_list, outcome in zip(selected, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            degraded.append({"list": _list_name(task_list), "reason": _reason(outcome)})
            continue
        entries, dropped = outcome
        found.extend(entries)
        skipped += dropped

    if degraded and len(degraded) == len(selected):
        # Hits of other lists cannot exist here, so an empty answer would only hide that
        # nothing could be read.
        raise ToolError(
            message="None of the task lists could be read.",
            hint="; ".join(item["reason"] for item in degraded),
        )

    if term:
        needle = term.casefold()
        found = [entry for entry in found if _matches(entry, needle)]
    if bound is not None:
        found = [entry for entry in found if _due_within(entry, bound)]
    found.sort(key=_sort_key)

    end = min(offset + PAGE_SIZE, MAX_RESULTS)
    window = found[offset:end]
    result: dict[str, Any] = {"tasks": [_as_hit(entry) for entry in window]}
    if len(found) > end:
        result["truncated"] = True
        if end < MAX_RESULTS:
            result["next"] = paging.encode_cursor(
                {"o": end, "q": term, "s": status, "d": bound_text, "l": wanted}
            )
        else:
            result["note"] = SEARCH_CAP_NOTE
    if degraded:
        result["degraded"] = degraded
    if skipped:
        # Named, not swallowed: "some objects were unusable" is a sentence the model can pass
        # on, a shorter list without a word about it is not.
        result["skipped"] = skipped
    return result


def _parse_due_by(text: str) -> date | datetime:
    """A date, or an instant with a zone. Refused before any request otherwise."""
    if _DATE_ONLY.fullmatch(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            raise ToolError(
                message=f"due_by is not a valid date ({text!r}).",
                hint=_DUE_BY_HINT,
                reason=REASON_GUARD_TRIPPED,
            ) from None
    try:
        return calendar.parse_instant(text, field="due_by")
    except ToolError as exc:
        raise ToolError(
            message=exc.message, hint=_DUE_BY_HINT, reason=REASON_GUARD_TRIPPED
        ) from None


def _resolve_list(lists: list[tasks_client.TaskList], wanted: str) -> tasks_client.TaskList:
    """Pick one list by its key (the URI of an own list) or its name, casefolded.

    Only against the discovery, never as a URL: the parameter selects from what the server
    sent. The URI of a shared list does not resolve, and no message carries it.
    """
    matches = _list_matches(lists, wanted)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        available = ", ".join(sorted({_list_name(entry) for entry in lists}))
        raise ToolError(
            message=f"This account has no task list called {_quoted(wanted)}.",
            hint=f"Available task lists: {available}. Pass one of these names as list.",
        )
    candidates = ", ".join(sorted(_candidate(entry) for entry in matches))
    raise ToolError(
        message=f"{_quoted(wanted)} matches more than one task list.",
        hint=f"Pass the key of one of them as list: {candidates}.",
    )


def _list_matches(lists: list[tasks_client.TaskList], wanted: str) -> list[tasks_client.TaskList]:
    """Every list whose key or name equals ``wanted``, casefolded and stripped."""
    needle = wanted.strip().casefold()
    return [
        entry
        for entry in lists
        if entry.key.casefold() == needle or _list_name(entry).casefold() == needle
    ]


def _candidate(entry: tasks_client.TaskList) -> str:
    kind = "shared" if entry.shared else "own"
    return f"{_list_name(entry)} (key {entry.key}, {kind})"


def _quoted(value: str) -> str:
    """Echo a value the caller sent, unless it carries the account id of a list owner."""
    if tasks_client.SHARED_MARKER in value:
        return "that name"
    return repr(value.strip())


async def _search_one(
    clients: NcClients, task_list: tasks_client.TaskList, status: str
) -> tuple[list[dict[str, Any]], int]:
    """The matching tasks of one list and the number of objects that had to be skipped.

    Mode ``open`` asks with the prefilter "no COMPLETED" and sorts out cancelled tasks here,
    because the server lets them through. When an open task names a parent that this answer
    does not hold (usually a completed one), one more REPORT of the same list without
    prefilter looks it up (D-32-04, variant V-B). Both requests share the budget of the list.
    """
    prefiltered = status == "open"
    async with asyncio.timeout(PER_LIST_TIMEOUT):
        objects = await tasks_client.query_todos(
            clients.client,
            clients.creds,
            task_list,
            tasks_client.build_todo_query(False if prefiltered else None),
        )
        entries, skipped = _parse_objects(task_list, objects)
        kept = [entry for entry in entries if _status_matches(entry["status"], status)]
        known = {entry["uid"]: entry for entry in entries if entry["uid"]}
        if prefiltered and any(
            entry["parents"] and entry["parents"][0] not in known for entry in kept
        ):
            everything = await tasks_client.query_todos(
                clients.client, clients.creds, task_list, tasks_client.build_todo_query(None)
            )
            for entry in _parse_objects(task_list, everything)[0]:
                if entry["uid"]:
                    known.setdefault(entry["uid"], entry)

    for entry in kept:
        if entry["parents"]:
            parent = known.get(entry["parents"][0])
            entry["parent"] = (
                {"id": parent["id"], "summary": parent["summary"]}
                if parent is not None
                else {"found": False}
            )
    return kept, skipped


def _parse_objects(
    task_list: tasks_client.TaskList, objects: list[tasks_client.TodoObject]
) -> tuple[list[dict[str, Any]], int]:
    """Read every object of one answer; an object that cannot be read or addressed is skipped.

    Skipped: not valid iCalendar, no VTODO, and an object name the id codec refuses (a ':'
    in it). The list itself stays.
    """
    entries: list[dict[str, Any]] = []
    skipped = 0
    for item in objects:
        todo = _read_todo(item.ics)
        if todo is None:
            skipped += 1
            continue
        try:
            todo["id"] = ids.encode_task(task_list.key, item.object_name)
        except ToolError:
            skipped += 1
            continue
        todo["_list"] = task_list
        entries.append(todo)
    return entries, skipped


def _status_matches(state: str, wanted: str) -> bool:
    if wanted == "open":
        return state in _OPEN_STATES
    if wanted == "completed":
        return state == "completed"
    return True


def _matches(entry: dict[str, Any], needle: str) -> bool:
    texts = [entry["summary"], entry["description"], *entry.get("tags", [])]
    return any(needle in text.casefold() for text in texts)


def _due_within(entry: dict[str, Any], bound: date | datetime) -> bool:
    """Whether the due value lies at or before the bound; a task without due never does.

    A date bound compares the due date: a date as it is, a zoned time by the date in its own
    zone, a floating time by its wall date. An instant bound compares zoned times as
    instants, a date against the date of the bound in the zone of the bound, and a floating
    time by its wall time against the wall time of the bound.
    """
    value = entry.get("_due_value")
    if value is None:
        return False
    if isinstance(bound, datetime):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value <= bound.replace(tzinfo=None)
            return value <= bound
        return value <= bound.date()
    day = value.date() if isinstance(value, datetime) else value
    return day <= bound


def _sort_key(entry: dict[str, Any]) -> tuple[int, tuple[int, datetime], str, str]:
    """Open before completed before cancelled, then due, undated last, then summary and id."""
    value = entry.get("_due_value")
    due = (1, datetime.min) if value is None else (0, _order_point(value))
    return (_STATUS_RANK[entry["status"]], due, entry["summary"].casefold(), entry["id"])


def _order_point(value: date | datetime) -> datetime:
    """A naive UTC point used for the order only, never written to an answer.

    A date counts as the start of its day in UTC minus one microsecond, so it comes before
    every time of the same day. A floating time is taken as UTC here, for the order alone.
    """
    if isinstance(value, datetime):
        offset = value.utcoffset()
        naive = value.replace(tzinfo=None)
        return naive - offset if offset is not None else naive
    try:
        return datetime.combine(value, time.min) - timedelta(microseconds=1)
    except OverflowError:
        return datetime.min


def _as_hit(entry: dict[str, Any]) -> dict[str, Any]:
    """One hit of ``tasks_search``: never the description (D-32-07)."""
    hit: dict[str, Any] = {
        "id": entry["id"],
        "summary": entry["summary"],
        "status": entry["status"],
    }
    for field in ("due", "due_floating", "start", "start_floating", "priority", "tags"):
        if field in entry:
            hit[field] = entry[field]
    hit["list"] = _list_info(entry["_list"])
    if "parent" in entry:
        hit["parent"] = entry["parent"]
    if entry.get("recurring"):
        hit["recurring"] = True
    return hit


def _list_name(task_list: tasks_client.TaskList) -> str:
    return marks.without_marks(task_list.name)


def _list_info(task_list: tasks_client.TaskList) -> dict[str, Any]:
    """Name without the owner, shared, writable (D-32-06); never the URI of the list."""
    return {
        "name": _list_name(task_list),
        "shared": task_list.shared,
        "writable": task_list.writable,
    }


def _reason(exc: BaseException) -> str:
    """One sentence per failed list. Unknown failures are bugs and stay loud."""
    if isinstance(exc, ToolError):
        return exc.message
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return f"The task list did not answer within {_seconds(PER_LIST_TIMEOUT)}."
    if isinstance(exc, httpx.RequestError):
        return "The task list could not be reached."
    raise exc


def _seconds(value: float) -> str:
    return "1 second" if value == 1 else f"{value:g} seconds"


async def read_task(clients: NcClients, *, task_id: str) -> dict[str, Any]:
    """Read one task with its direct subtasks, one level deep (D-32-01, D-32-02).

    Public because ``fetch`` resolves a ``task:`` id through this reader as well (32-06).
    The id is resolved against the discovery only: a Deck list is refused before any
    request, and a key the discovery does not hold, a deleted object and an object that is
    not a task all get the same answer as an unknown id (E9). The subtask query and the
    parent lookup run side by side, each under :data:`SUBTASK_TIMEOUT`; when one of them
    fails, the task still comes back with an honest sentence instead of a guess (D-32-03).
    """
    kind, parts = ids.parse(task_id)
    if kind != "task":
        raise ToolError(
            message=f"{_quoted(task_id)} is not a task id.",
            hint="Pass an id of the form task:<list>:<object> from a tasks_search hit.",
            reason=REASON_GUARD_TRIPPED,
        )
    list_key, object_name = parts
    if list_key.startswith(tasks_client.DECK_PREFIX):
        # A Deck board is never asked, not even through the discovery (E9).
        raise _unknown_task(task_id)

    lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
    matches = [entry for entry in lists if entry.key == list_key]
    if len(matches) != 1:
        raise _unknown_task(task_id)
    task_list = matches[0]

    try:
        stored = await tasks_client.get_todo(clients.client, clients.creds, task_list, object_name)
    except ToolError as exc:
        if exc.reason == REASON_UNKNOWN_ID:
            raise _unknown_task(task_id) from None
        raise
    todo = _read_todo(stored.ics)
    if todo is None:
        raise _unknown_task(task_id)
    own_id = ids.encode_task(task_list.key, object_name)

    parent_uid = todo["parents"][0] if todo["parents"] else ""
    parent: dict[str, Any] | BaseException | None = None
    if parent_uid:
        children, parent = await asyncio.gather(
            _children(clients, task_list, todo["uid"], own_id),
            _parent(clients, task_list, parent_uid),
            return_exceptions=True,
        )
    else:
        (children,) = await asyncio.gather(
            _children(clients, task_list, todo["uid"], own_id), return_exceptions=True
        )

    result: dict[str, Any] = {"id": own_id, "summary": todo["summary"]}
    if todo["description"]:
        description, cut = _capped(todo["description"])
        result["description"] = description
        if cut:
            result["description_truncated"] = True
    result["status"] = todo["status"]
    for field in (
        "due",
        "due_floating",
        "start",
        "start_floating",
        "priority",
        "tags",
        "completed",
        "completed_floating",
        "recurring",
    ):
        if field in todo:
            result[field] = todo[field]
    result["list"] = _list_info(task_list)
    if stored.etag:
        # The ETag a change of this task needs, as the server sent it (D-33-03); no field
        # at all rather than an empty value a model would copy into the next call.
        result["etag"] = stored.etag

    if isinstance(parent, BaseException):
        result["parent_unavailable"] = _side_reason(parent, "The parent task could not be read")
    elif parent is not None:
        result["parent"] = parent

    if isinstance(children, BaseException):
        result["subtasks_unavailable"] = _subtask_reason(children)
    else:
        children.sort(key=_subtask_key)
        result["subtasks"] = [
            {"id": entry["id"], "summary": entry["summary"], "status": entry["status"]}
            for entry in children[:MAX_SUBTASKS]
        ]
        if len(children) > MAX_SUBTASKS:
            result["subtasks_truncated"] = True
            result["subtasks_total"] = len(children)
    return result


def _unknown_task(task_id: str) -> ToolError:
    """One answer for every id Nextcloud does not hold as a task of a visible list (E9)."""
    return ToolError(
        message=f"Nextcloud does not know the task {_quoted(task_id)}.",
        hint="Call tasks_search to find the task again; its hits carry valid ids.",
        reason=REASON_UNKNOWN_ID,
    )


async def _children(
    clients: NcClients, task_list: tasks_client.TaskList, uid: str, own_id: str
) -> list[dict[str, Any]]:
    """The direct subtasks of one task, checked exactly.

    The server matches ``RELATED-TO`` with "contains", so every hit is a candidate: it
    counts only with a ``RELATED-TO`` equal to the UID whose ``RELTYPE`` is missing or
    ``PARENT``, and never the task itself.
    """
    async with asyncio.timeout(SUBTASK_TIMEOUT):
        objects = await tasks_client.query_todos(
            clients.client,
            clients.creds,
            task_list,
            tasks_client.build_related_query("RELATED-TO", uid),
        )
    entries, _skipped = _parse_objects(task_list, objects)
    return [
        entry
        for entry in entries
        if uid in entry["parents"] and entry["uid"] != uid and entry["id"] != own_id
    ]


async def _parent(
    clients: NcClients, task_list: tasks_client.TaskList, parent_uid: str
) -> dict[str, Any]:
    """The parent named by ``RELATED-TO``, looked up by its UID in the same list."""
    async with asyncio.timeout(SUBTASK_TIMEOUT):
        objects = await tasks_client.query_todos(
            clients.client,
            clients.creds,
            task_list,
            tasks_client.build_related_query("UID", parent_uid),
        )
    for entry in _parse_objects(task_list, objects)[0]:
        if entry["uid"] == parent_uid:
            return {"id": entry["id"], "summary": entry["summary"]}
    return {"found": False}


def _subtask_key(entry: dict[str, Any]) -> tuple[int, str, str]:
    return (_STATUS_RANK[entry["status"]], entry["summary"].casefold(), entry["id"])


def _subtask_reason(exc: BaseException) -> str:
    return _side_reason(exc, "The subtasks could not be read")


def _side_reason(exc: BaseException, sentence: str) -> str:
    """The sentence for a side query that failed. Unknown failures are bugs and stay loud."""
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return f"{sentence} within {_seconds(SUBTASK_TIMEOUT)}."
    if isinstance(exc, ToolError | httpx.RequestError):
        return f"{sentence}."
    raise exc


def _capped(text: str) -> tuple[str, bool]:
    """One description at :data:`MAX_DESCRIPTION_BYTES`, and whether it had to be cut.

    Measured on the UTF-8 encoding; a character split by the cut is dropped instead of
    arriving broken. No marker inside the text: the cut is the field beside it.
    """
    blob = text.encode("utf-8")
    if len(blob) <= MAX_DESCRIPTION_BYTES:
        return text, False
    return blob[:MAX_DESCRIPTION_BYTES].decode("utf-8", errors="ignore"), True


async def create_task(
    clients: NcClients,
    *,
    summary: str,
    list_name: str | None = None,
    description: str | None = None,
    due: str | None = None,
    start: str | None = None,
    priority: int | None = None,
    tags: Sequence[str] | None = None,
    timezone: str | None = None,
    parent: str | None = None,
) -> dict[str, Any]:
    """Create one task, exactly where the caller said, or nowhere (E4, TASK-05, TASK-06).

    Every input is checked before the first request; a value that does not fit is refused,
    never quietly changed (D-31-08). The target list: ``list_name`` wins and is resolved
    against the discovery only; without it the task goes into the one own writable list of
    the account, and with more than one or none of them the caller has to name it. A shared
    list is only written to when it is named: a ``parent`` in a shared list does not count
    as naming it (D-32-16). A read only list is refused before the request; the 403 and 404
    of the server stay the last word. Deck calendars never appear in the discovery.

    The object is written create-only (fresh UUID, ``If-None-Match: *``) through
    ``caldav.put_new_object``, then read back once. ``confirmed`` is true only when the
    object could be read and carries the UID that was written; a failing read back never
    turns the write into a failure, or the model would create the task a second time.
    """
    if not summary or not summary.strip():
        raise _refused("A task needs a summary.", "Give a short title, for example 'Angebot'.")
    zone = _task_zone(timezone)
    due_value = _parse_task_time(due, "due")
    start_value = _parse_task_time(start, "start")
    _check_times(due_value, start_value, zone)
    _check_priority(priority)
    categories = _clean_tags(tags)
    parent_key, parent_object = _parse_parent(parent)

    # Written in the named zone with its VTIMEZONE, otherwise in UTC; a date stays a date.
    written_zone: Any = zone if zone is not None else UTC
    due_value = _in_zone(due_value, written_zone)
    start_value = _in_zone(start_value, written_zone)

    lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
    if not lists:
        raise ToolError(message=NO_LIST_MESSAGE, hint=NO_LIST_WAY_OUT)

    parent_list: tasks_client.TaskList | None = None
    if parent is not None:
        matches = [entry for entry in lists if entry.key == parent_key]
        if len(matches) != 1:
            raise _unknown_task(parent)
        parent_list = matches[0]
    target = _pick_target(lists, (list_name or "").strip(), parent_list)

    parent_uid = ""
    if parent is not None:
        parent_uid = await _parent_uid(clients, target, parent_object, parent)

    object_name = f"{uuid.uuid4()}.ics"
    uid = object_name.removesuffix(".ics")
    ics = _build_todo(
        uid=uid,
        summary=summary,
        description=description if description and description.strip() else None,
        due=due_value,
        start=start_value,
        priority=priority,
        tags=categories,
        parent_uid=parent_uid,
        zone=zone,
    )
    await caldav.put_new_object(
        clients.client,
        clients.creds,
        target.uri,
        object_name,
        ics,
        tasks_client.TASK_WORDING,
        _list_name(target),
    )
    confirmed = await _confirm(clients, target, object_name, uid)

    result: dict[str, Any] = {
        "id": ids.encode_task(target.key, object_name),
        "summary": summary,
        "list": _list_info(target),
        "created": True,
        "confirmed": confirmed,
    }
    if due_value is not None:
        result["due"] = _time_field(due_value)[0]
    if start_value is not None:
        result["start"] = _time_field(start_value)[0]
    return result


def _refused(message: str, hint: str) -> ToolError:
    """A refusal before the first request."""
    return ToolError(message=message, hint=hint, reason=REASON_GUARD_TRIPPED)


def _task_zone(name: str | None) -> ZoneInfo | None:
    if name is None or not name.strip():
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        raise _refused(f"{_quoted(name)} is not a known timezone.", _ZONE_HINT) from None


def _parse_task_time(text: str | None, field: str) -> date | datetime | None:
    """A date, or a time with a zone. A time without a zone is refused, never guessed."""
    raw = (text or "").strip()
    if not raw:
        return None
    if _DATE_ONLY.fullmatch(raw):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise _refused(f"{field} is not a valid date ({raw!r}).", _TASK_TIME_HINT) from None
    try:
        return calendar.parse_instant(raw, field=field)
    except ToolError as exc:
        raise _refused(exc.message, _TASK_TIME_HINT) from None


def _check_times(
    due: date | datetime | None, start: date | datetime | None, zone: ZoneInfo | None
) -> None:
    if zone is not None and not isinstance(due, datetime) and not isinstance(start, datetime):
        raise _refused(
            "timezone only applies to a due or start with a time.",
            "Leave timezone out, or give due or start with a time.",
        )
    if due is None or start is None:
        return
    if isinstance(due, datetime) != isinstance(start, datetime):
        raise _refused(
            "start and due must both be dates or both be times.",
            "Give both as dates such as 2026-11-20, or both as times with a zone.",
        )
    if not _before(start, due):
        raise _refused("start must lie before due.", "Give a start before the due date or time.")


def _before(first: date | datetime, second: date | datetime) -> bool:
    """``first < second`` for two dates or two times with a zone (checked by the caller)."""
    if isinstance(first, datetime) and isinstance(second, datetime):
        return first < second
    if not isinstance(first, datetime) and not isinstance(second, datetime):
        return first < second
    return False


def _check_priority(priority: int | None) -> None:
    if priority is None:
        return
    if isinstance(priority, bool) or priority not in PRIORITY_RANGE:
        raise _refused(
            f"priority must be a whole number from 0 to 9 (got {priority!r}).",
            "1 is the highest, 9 the lowest, 0 means none.",
        )


def _clean_tags(tags: Sequence[str] | None) -> list[str]:
    """Empty values and duplicates (casefolded) dropped, in the order of first mention."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags or ():
        value = str(tag).strip()
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            cleaned.append(value)
    return cleaned


def _parse_parent(parent: str | None) -> tuple[str, str]:
    """The list key and object name of a ``task:`` id; a Deck list is unknown at once."""
    if parent is None:
        return "", ""
    kind, parts = ids.parse(parent)
    if kind != "task":
        raise _refused(
            f"parent {_quoted(parent)} is not a task id.",
            "Pass an id of the form task:<list>:<object> from a tasks_search hit.",
        )
    list_key, object_name = parts
    if list_key.startswith(tasks_client.DECK_PREFIX):
        # A Deck board is never asked, not even through the discovery (E9).
        raise _unknown_task(parent)
    return list_key, object_name


def _in_zone(value: date | datetime | None, zone: Any) -> date | datetime | None:
    """A time expressed in the zone it is written in; a date stays that very day."""
    if isinstance(value, datetime):
        return value.astimezone(zone)
    return value


def _pick_target(
    lists: list[tasks_client.TaskList],
    wanted: str,
    parent_list: tasks_client.TaskList | None,
) -> tasks_client.TaskList:
    """The one list a create writes into, after E4 and D-32-16; never positional.

    A named list wins. Without one, the list of the parent if it is an own list nobody else
    sees; a parent in a shared list, or in an own list the account shares with others or
    publishes, is not a naming of that list (D-32-16, D-32-18). Without both, exactly one own
    writable list, and only when nobody else sees it; otherwise the caller has to choose
    from the real names. Two own lists stay "more than one" even when only one of them is
    private: a choice that depends on the share state of the others would be unforeseeable.
    No fallback on ``personal`` and none on "exactly one list at all": that one could be
    shared.
    """
    if wanted:
        target = _resolve_list(lists, wanted)
        if parent_list is not None and parent_list.key != target.key:
            raise _refused(
                "The parent task lives in another list.",
                "Leave list out to create the subtask in the list of its parent, "
                "or pick a parent from the named list.",
            )
    elif parent_list is not None:
        if parent_list.shared:
            raise _refused(
                "The parent task lives in a shared list, and a shared list is only written "
                "to when it is named.",
                "To create the subtask there, name that list with "
                f"list={_list_name(parent_list)!r}.",
            )
        if parent_list.shared_out:
            raise _refused(
                "The parent task lives in a list that is shared with others, and such a list "
                "is only written to when it is named.",
                "To create the subtask there, name that list with "
                f"list={_list_name(parent_list)!r}.",
            )
        target = parent_list
    else:
        own = [entry for entry in lists if entry.own and entry.writable]
        if len(own) == 1 and own[0].shared_out:
            raise _refused(
                f"The only own task list to write to, {_list_name(own[0])!r}, is shared with "
                "others, and a list others can see is only written to when it is named.",
                _writable_hint(lists),
            )
        if len(own) == 1:
            return own[0]
        raise _no_default_target(lists, own)

    if not target.writable:
        raise _refused(
            f"The task list {_list_name(target)!r} is read only for this account.",
            _writable_hint(lists),
        )
    return target


def _no_default_target(
    lists: list[tasks_client.TaskList], own: list[tasks_client.TaskList]
) -> ToolError:
    if not any(entry.writable for entry in lists):
        return ToolError(
            message="None of the task lists of this account can be written to.",
            hint=NO_LIST_WAY_OUT,
        )
    if own:
        message = "This account has more than one task list to write to, so list has to be named."
    else:
        message = (
            "This account has no own task list to write to, and a shared list is only "
            "written to when it is named."
        )
    return ToolError(message=message, hint=_writable_hint(lists))


def _writable_hint(lists: list[tasks_client.TaskList]) -> str:
    names = sorted(
        f"{_list_name(entry)} (shared, key {entry.key})" if entry.shared else _list_name(entry)
        for entry in lists
        if entry.writable
    )
    if not names:
        return NO_LIST_WAY_OUT
    return f"Name the list with list=<name>. Writable task lists: {', '.join(names)}."


async def _parent_uid(
    clients: NcClients, task_list: tasks_client.TaskList, object_name: str, parent: str
) -> str:
    """The UID of the parent task, read from the target list; unknown ids get one answer."""
    try:
        stored = await tasks_client.get_todo(clients.client, clients.creds, task_list, object_name)
    except ToolError as exc:
        if exc.reason == REASON_UNKNOWN_ID:
            raise _unknown_task(parent) from None
        raise
    todo = _read_todo(stored.ics)
    if todo is None or not todo["uid"]:
        raise _unknown_task(parent)
    return todo["uid"]


def _build_todo(
    *,
    uid: str,
    summary: str,
    description: str | None,
    due: date | datetime | None,
    start: date | datetime | None,
    priority: int | None,
    tags: list[str],
    parent_uid: str,
    zone: ZoneInfo | None,
) -> bytes:
    """One VCALENDAR with exactly one VTODO, always through icalendar.

    Never by string concatenation: escaping, folding and ``VALUE=DATE`` are where a hand
    written generator breaks, and a summary with a line break could open a second component
    (threat T-32-04b-03). The VTIMEZONE comes from the zoneinfo database, never by hand.
    ``RELATED-TO`` carries no ``RELTYPE``: ``PARENT`` is its default (RFC 5545).
    """
    ics = IcsCalendar()
    ics.add("prodid", calendar.PRODID)
    ics.add("version", "2.0")

    timed = next((value for value in (due, start) if isinstance(value, datetime)), None)
    if zone is not None and timed is not None:
        component = IcsTimezone.from_tzinfo(
            zone,
            tzid=zone.key,
            first_date=date(timed.year - 1, 1, 1),
            last_date=date(timed.year + 5, 1, 1),
        )
        component.pop("COMMENT", None)
        ics.add_component(component)

    now = datetime.now(UTC).replace(microsecond=0)
    todo = IcsTodo()
    todo.add("uid", uid)
    todo.add("created", now)
    todo.add("last-modified", now)
    todo.add("dtstamp", now)
    todo.add("summary", summary)
    if description is not None:
        todo.add("description", description)
    if start is not None:
        todo.add("dtstart", start)
    if due is not None:
        todo.add("due", due)
    if priority is not None:
        todo.add("priority", priority)
    if tags:
        todo.add("categories", tags)
    if parent_uid:
        todo.add("related-to", parent_uid)
    ics.add_component(todo)
    return ics.to_ical()


async def _confirm(
    clients: NcClients, task_list: tasks_client.TaskList, object_name: str, uid: str
) -> bool:
    """Read the new object once. A failure here never undoes or fails the write."""
    try:
        stored = await tasks_client.get_todo(clients.client, clients.creds, task_list, object_name)
    except (ToolError, TimeoutError, httpx.TimeoutException, httpx.RequestError):
        return False
    todo = _read_todo(stored.ics)
    return todo is not None and todo["uid"] == uid


# --- The chain of descendants (plan 33-05) -------------------------------------------------
# Shared by completing and relocating a task with its subtasks (D-33-00b, D-33-00c, D-33-09):
# one REPORT of the whole list, the descendants in post-order, a check before the first
# write, then one write after the other, the named task last.


def chain_entries(
    task_list: tasks_client.TaskList, objects: list[tasks_client.TodoObject]
) -> tuple[list[dict[str, Any]], int]:
    """Every readable object of one list with what a chain needs, and the number skipped.

    Each entry holds the fields of :func:`_read_todo` plus ``id``, ``object_name``, ``etag``
    (as the server sent it in the same REPORT) and ``text`` (the stored iCalendar). An
    object that cannot be read or addressed is skipped and counted, like in tasks_search.
    A text that is not UTF-8 gets ``text`` ``None`` instead of replacement characters, which
    a write would store for good; :func:`check_chain` refuses such a descendant.
    """
    entries: list[dict[str, Any]] = []
    skipped = 0
    for item in objects:
        parsed, missed = _parse_objects(task_list, [item])
        skipped += missed
        if not parsed:
            continue
        entry = parsed[0]
        entries.append(entry)
        entry["object_name"] = item.object_name
        entry["etag"] = item.etag
        try:
            entry["text"] = item.ics.decode("utf-8")
        except UnicodeDecodeError:
            entry["text"] = None
    return entries, skipped


def descendants_post_order(root_uid: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Children, grandchildren, ... of the task with ``root_uid``, each exactly once.

    An edge counts only with a ``RELATED-TO`` equal to the UID whose ``RELTYPE`` is missing
    or ``PARENT`` (``_parents``); never "contains", never ``CHILD`` or ``SIBLING``. Depth
    first in post-order, so every task comes after its whole subtree and the named task,
    which is not in the result, can safely go last; siblings in the stable order of their
    object names. A visited set keeps foreign cycles (also through the named task) and
    double edges from repeating anything. Iterative, so depth costs no recursion.
    """
    children: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        for parent in entry["parents"]:
            children.setdefault(parent, []).append(entry)
    for kids in children.values():
        kids.sort(key=lambda entry: entry["object_name"])

    order: list[dict[str, Any]] = []
    seen = {root_uid}
    stack: list[tuple[dict[str, Any] | None, Any]] = [(None, iter(children.get(root_uid, [])))]
    while stack:
        current, pending = stack[-1]
        for kid in pending:
            key = kid["uid"] or kid["id"]
            if key in seen:
                continue
            seen.add(key)
            stack.append((kid, iter(children.get(kid["uid"], []) if kid["uid"] else [])))
            break
        else:
            stack.pop()
            if current is not None:
                order.append(current)
    return order


def check_chain(task_list: tasks_client.TaskList, descendants: list[dict[str, Any]]) -> None:
    """Refuse a chain before its first write, on data already read (D-33-10, D-33-11).

    Refused: a read only list (descendants live in the list of the named task and share its
    permission), more than :data:`CHAIN_CAP` descendants, and a descendant that is
    recurring, holds several VTODO, is not UTF-8 or cannot be edited safely. So the frequent
    cases never leave half a chain behind. Never sends a request.
    """
    if not task_list.writable:
        raise _refused(
            f"The task list {_list_name(task_list)} is read only.",
            "Ask the owner of that task list for write permission in Nextcloud.",
        )
    if len(descendants) > CHAIN_CAP:
        raise _refused(
            f"The task has {len(descendants)} subtasks including their own subtasks; one call "
            f"changes at most {CHAIN_CAP}.",
            "Change some of the subtasks first, each with its own call, then try again.",
        )
    for entry in descendants:
        if entry["text"] is None:
            raise _refused(
                f"The subtask {entry['id']} cannot be changed safely: its text is not UTF-8.",
                "Nothing was changed. Fix that subtask in the Nextcloud Tasks app first.",
            )
        try:
            facts = ics_edit.inspect(entry["text"])
        except ics_edit.EditRefused as exc:
            raise _refused(
                f"The subtask {entry['id']} cannot be changed safely: {exc}.",
                "Nothing was changed. Fix that subtask in the Nextcloud Tasks app first.",
            ) from None
        if facts.recurring or entry.get("recurring"):
            raise _refused(
                f"The subtask {entry['id']} is a recurring task; this server does not change "
                "recurring tasks.",
                "Nothing was changed. Detach that subtask in the Nextcloud Tasks app first.",
            )


async def read_chain_list(
    clients: NcClients, task_list: tasks_client.TaskList
) -> tuple[list[dict[str, Any]], int]:
    """One REPORT of the whole list without prefilter, the entries of :func:`chain_entries`.

    A completed or cancelled subtask is a descendant as well, so nothing is filtered on the
    server. The budget :data:`PER_LIST_TIMEOUT` covers this read alone, never a write
    (pitfall 4); a list that does not answer in time is a refusal before any write.
    """
    try:
        async with asyncio.timeout(PER_LIST_TIMEOUT):
            objects = await tasks_client.query_todos(
                clients.client, clients.creds, task_list, tasks_client.build_todo_query(None)
            )
    except (TimeoutError, httpx.TimeoutException):
        raise ToolError(
            message=(
                f"The task list did not answer in time ({_seconds(PER_LIST_TIMEOUT)}): "
                f"nothing was changed in {_list_name(task_list)}."
            ),
            hint="Try again in a moment; the task and its subtasks are as they were.",
            reason=REASON_TIMEOUT,
        ) from None
    return chain_entries(task_list, objects)


class ChainSkip(Enum):
    """What a step of the chain does instead of a write."""

    #: Already in the target state: no request, counted in ``unchanged``.
    UNCHANGED = "unchanged"
    #: Deliberately not touched (a cancelled subtask when completing, D-33-14): no request,
    #: named in ``left_alone``.
    LEFT_ALONE = "left_alone"


#: Builds the new text of one entry, or says why there is nothing to write. Raises
#: ``ics_edit.EditRefused`` when the object cannot be edited safely.
ChainDecide = Callable[[dict[str, Any]], bytes | ChainSkip]

#: Writes one entry with the payload of :data:`ChainDecide` under the given ETag and returns
#: the new ETag or an empty text; ``clients/tasks.put_existing_todo`` or ``move_todo``.
ChainWrite = Callable[[dict[str, Any], bytes, str], Awaitable[str]]

#: The sentence of each stop reason; the report never carries a message of the server.
_CHAIN_STOPS = {
    "conflict": "it changed since it was read (412)",
    "uid_conflict": "the target list already holds a task with the same UID (409)",
    "not_found_or_read_only": "Nextcloud does not find it or gives no write permission (404)",
    "refused": "the change was refused",
    "server_error": "Nextcloud reported an error, so the outcome of that write is not known",
    "outcome_unknown": "Nextcloud did not answer, so the outcome of that write is not known",
    "changed_or_name_taken": (
        "it changed since it was read or its name is already taken in the target list (412)"
    ),
    "replaced": (
        "Nextcloud reports that it replaced an object of the same name in the target list "
        "(204), although this server forbids that with Overwrite: F"
    ),
}


@dataclass
class ChainReport:
    """What a chain did: task ids and the list only, never a URI or an owner."""

    task_list: tasks_client.TaskList
    root_id: str
    changed: list[str] = dataclasses.field(default_factory=list)
    unchanged: int = 0
    left_alone: list[str] = dataclasses.field(default_factory=list)
    skipped: int = 0
    failed: str | None = None
    reason: str | None = None
    #: The new ETag of the named task after its write; ``None`` when it was not written,
    #: empty when the server sent none (then only a new read tells it).
    root_etag: str | None = None

    def as_answer(self) -> dict[str, Any]:
        answer: dict[str, Any] = {
            "list": _list_info(self.task_list),
            "changed": list(self.changed),
            "unchanged": self.unchanged,
        }
        if self.left_alone:
            answer["left_alone"] = list(self.left_alone)
        if self.skipped:
            answer["skipped"] = self.skipped
        if self.failed is not None and self.reason is not None:
            answer["failed"] = self.failed
            answer["reason"] = self.reason
            answer["message"] = self._stop_sentence()
        return answer

    def _stop_sentence(self) -> str:
        sentence = f"Stopped at {self.failed}: {_CHAIN_STOPS[self.reason or 'refused']}."
        if self.failed != self.root_id:
            sentence += (
                f" {len(self.changed)} subtasks listed in changed were changed and stay so; "
                f"the named task {self.root_id} was not changed."
            )
        return sentence + (
            " Nothing was retried or undone: read the task again with tasks_read before the "
            "next call."
        )


def _chain_reason(exc: Exception) -> str:
    """The stop reason of one failed step, from the error of the conditional writers."""
    if isinstance(exc, ics_edit.EditRefused):
        return "refused"
    if isinstance(exc, httpx.RequestError):
        return "outcome_unknown"
    if isinstance(exc, ConflictError):
        # The two conflicts of clients/tasks.py name their status in the message.
        return "uid_conflict" if "(409)" in exc.message else "conflict"
    if isinstance(exc, ToolError):
        if exc.reason == REASON_UNKNOWN_ID:
            return "not_found_or_read_only"
        if exc.reason == REASON_PERMISSION_DENIED:
            return "refused"
        if exc.reason == REASON_TIMEOUT:
            return "outcome_unknown"
    return "server_error"


async def run_chain(
    task_list: tasks_client.TaskList,
    root: dict[str, Any],
    root_etag: str,
    descendants: list[dict[str, Any]],
    decide: ChainDecide,
    write: ChainWrite,
    *,
    skipped: int = 0,
) -> ChainReport:
    """Write the descendants one after the other, then the named task (D-33-09).

    Strictly sequential, never side by side (two writes of one account at once gave
    "database is locked" on SQLite, pitfall 7), and without a time budget around a write
    (pitfall 4). Every descendant carries ``If-Match`` on the ETag of the REPORT of this
    call, only the named task the ETag of the assistant. A step in the target state or
    marked to be left alone sends nothing. The first failure stops the chain: no further
    request, no second attempt, nothing undone; the named task, which comes last, then
    stays as it was, and the report names what was already changed and why it stopped.
    """
    report = ChainReport(task_list=task_list, root_id=root["id"], skipped=skipped)
    for entry in [*descendants, root]:
        is_root = entry is root
        try:
            step = decide(entry)
            if step is ChainSkip.UNCHANGED:
                report.unchanged += 1
                continue
            if step is ChainSkip.LEFT_ALONE:
                report.left_alone.append(entry["id"])
                continue
            new_etag = await write(entry, step, root_etag if is_root else entry["etag"])
        except (ToolError, ics_edit.EditRefused, httpx.RequestError) as exc:
            report.failed = entry["id"]
            report.reason = _chain_reason(exc)
            return report
        report.changed.append(entry["id"])
        if is_root:
            report.root_etag = new_etag
    return report


# --- Completing and reopening a task (plan 33-06) -------------------------------------------

#: The answer when the server stored a text other than the one it got and sent no ETag
#: (ENTSCHEID etag_nach_veraendertem_text=fehlt, plan 33-01c): only a new read tells it.
NEW_ETAG_NOTE = "read the task again for its new etag"

#: Stop reasons after which the named task is known to be as it was: the server refused
#: its write before storing anything.
_KEPT_ON_STOP = frozenset({"conflict", "not_found_or_read_only", "refused"})


def _crlf(text: str) -> str:
    """Line ends as RFC 5545 wants them, the same for every input.

    A REPORT can hand the text over with LF only (an XML parser turns CRLF into LF), and
    some clients store LF. Both become CRLF; a text that already has CRLF stays byte for
    byte, so the edit keeps every untouched line as it was stored.
    """
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def _completion_edit(completed: bool, now: datetime) -> tuple[dict[str, Any], tuple[str, ...]]:
    """The fields of completing or reopening, as the Tasks app 0.18.1 writes them (D-33-08).

    Completing sets STATUS, PERCENT-COMPLETE and COMPLETED; reopening sets STATUS and drops
    COMPLETED and PERCENT-COMPLETE. Both bring LAST-MODIFIED and DTSTAMP to the same UTC
    second; SEQUENCE is never touched.
    """
    stamps = {"LAST-MODIFIED": now, "DTSTAMP": now}
    if completed:
        return {"STATUS": "COMPLETED", "PERCENT-COMPLETE": 100, "COMPLETED": now, **stamps}, ()
    return {"STATUS": "NEEDS-ACTION", **stamps}, ("COMPLETED", "PERCENT-COMPLETE")


def _edited(text: str, completed: bool, now: datetime) -> bytes:
    """The new text of one task, checked before it may be written; refuses with EditRefused."""
    before = _crlf(text)
    set_fields, drop_fields = _completion_edit(completed, now)
    after = ics_edit.apply(before, set_fields=set_fields, drop_fields=drop_fields)
    expected: dict[str, Any] = dict(set_fields)
    expected.update(dict.fromkeys(drop_fields))
    ics_edit.verify(before, after, expected)
    return after.encode("utf-8")


def _cannot_change(task_id: str, why: str) -> ToolError:
    return _refused(
        f"The task {task_id} cannot be changed safely: {why}.",
        "Nothing was changed. Fix that task in the Nextcloud Tasks app first.",
    )


def _task_key(task_id: str) -> tuple[str, str]:
    """List key and object name of a task id a change names; before any request.

    An id that is not a task id is refused, a Deck key gets the answer of an unknown task
    (E9): a Deck board is never asked, not even through the discovery.
    """
    kind, parts = ids.parse(task_id)
    if kind != "task":
        raise _refused(
            f"{_quoted(task_id)} is not a task id.",
            "Pass an id of the form task:<list>:<object> from tasks_search or tasks_read.",
        )
    list_key, object_name = parts
    if list_key.startswith(tasks_client.DECK_PREFIX):
        raise _unknown_task(task_id)
    return list_key, object_name


@dataclass
class _Stored:
    """One task as a change found it: list, read fields, text and the check before the edit."""

    task_list: tasks_client.TaskList
    own_id: str
    object_name: str
    todo: dict[str, Any]
    text: str
    facts: ics_edit.TodoFacts
    #: The ETag of the GET, empty when the server sent none (then the one of the caller
    #: was never compared and must not be echoed as known).
    etag: str = ""


async def _read_for_change(
    clients: NcClients,
    task_id: str,
    list_key: str,
    object_name: str,
    wanted: str,
    lists: list[tasks_client.TaskList] | None = None,
) -> _Stored:
    """Discovery, write permission, GET, ETag comparison and the check before the edit.

    Everything a modifying tool refuses after the first request and before any write: an
    unknown list or task (one answer for all of it), a read only list, an ETag other than
    the one just read (the ETag still goes out as ``If-Match``, so the window after the
    comparison stays covered), a text that is not UTF-8, several VTODO, any text
    ``ics_edit.inspect`` refuses and a recurring task (D-33-00a, D-33-03, D-33-11).
    ``lists`` is the discovery of the caller when it already holds one, so a call never
    asks twice.
    """
    if lists is None:
        lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
    matches = [entry for entry in lists if entry.key == list_key]
    if len(matches) != 1:
        raise _unknown_task(task_id)
    task_list = matches[0]
    if not task_list.writable:
        raise _refused(
            f"The task list {_list_name(task_list)!r} is read only for this account.",
            "Ask the owner of that task list for write permission in Nextcloud.",
        )

    try:
        stored = await tasks_client.get_todo(clients.client, clients.creds, task_list, object_name)
    except ToolError as exc:
        if exc.reason == REASON_UNKNOWN_ID:
            raise _unknown_task(task_id) from None
        raise
    todo = _read_todo(stored.ics)
    if todo is None:
        raise _unknown_task(task_id)
    own_id = ids.encode_task(task_list.key, object_name)
    if stored.etag and stored.etag != wanted:
        raise ConflictError(
            message=f"The task {own_id} changed since it was read.",
            hint="Nothing was changed: read the task again with tasks_read and use its new etag.",
        )
    try:
        text = stored.ics.decode("utf-8")
        facts = ics_edit.inspect(_crlf(text))
    except UnicodeDecodeError:
        raise _cannot_change(own_id, "its text is not UTF-8") from None
    except ics_edit.EditRefused as exc:
        raise _cannot_change(own_id, str(exc)) from None
    if facts.recurring or todo.get("recurring"):
        raise _refused(
            f"The task {own_id} is a recurring task; this server does not change recurring tasks.",
            "Nothing was changed. Change it in the Nextcloud Tasks app.",
        )
    return _Stored(task_list, own_id, object_name, todo, text, facts, stored.etag)


def _in_target_state(status: str, completed: bool) -> bool:
    """Completed when completing, open or in progress when reopening; cancelled never."""
    if completed:
        return status == "completed"
    return status in _OPEN_STATES


async def complete_task(
    clients: NcClients, *, task_id: str, etag: str, completed: bool
) -> dict[str, Any]:
    """Complete (``completed`` true) or reopen (false) one task (TMOD-03, D-33-08).

    Refused before any request: an id that is not a task id, a Deck key (answered like an
    unknown task, E9), an ETag that is not one strong validator and a ``completed`` that is
    not a bool. Refused after the discovery and the GET, before any write: an unknown list
    or task (one answer for all of it), a read only list, an ETag other than the one just
    read (the ETag still goes out as ``If-Match``, so the window after the comparison stays
    covered), a recurring task, several VTODO and any text the check before the edit
    refuses (D-33-00a, D-33-03, D-33-11).

    A task already in the target state is a success without a write. Completing reads the
    list once and completes every descendant first, the named task last, through the chain
    of plan 33-05; a completed descendant is skipped and a cancelled one is left alone and
    named (D-33-00b, D-33-09, D-33-14). Every new text is built and checked before the first
    write, so a refusal never leaves half a chain. Reopening changes the named task only
    (D-33-05, ENTSCHEID wiederoeffnen_kinder=bleiben). A cancelled task may be completed
    and reopened directly (ENTSCHEID cancelled_direkt). The answer names task ids and the
    list, never a URI or an owner.
    """
    list_key, object_name = _task_key(task_id)
    wanted = dav.normalize_etag(etag)
    if not isinstance(completed, bool):
        raise _refused(
            "completed must be true or false.",
            "Pass completed=true to complete the task or completed=false to reopen it.",
        )

    loaded = await _read_for_change(clients, task_id, list_key, object_name, wanted)
    task_list, own_id, todo, text = loaded.task_list, loaded.own_id, loaded.todo, loaded.text

    status = todo["status"]
    if _in_target_state(status, completed):
        return {"id": own_id, "list": _list_info(task_list), "status": status, "already": True}

    now = datetime.now(UTC).replace(microsecond=0)
    try:
        payloads = {own_id: _edited(text, completed, now)}
    except ics_edit.EditRefused as exc:
        raise _cannot_change(own_id, str(exc)) from None
    descendants: list[dict[str, Any]] = []
    skipped = 0
    if completed:
        entries, skipped = await read_chain_list(clients, task_list)
        descendants = descendants_post_order(todo["uid"], entries)
        check_chain(task_list, descendants)
        for entry in descendants:
            if entry["status"] in ("completed", "cancelled"):
                continue
            try:
                payloads[entry["id"]] = _edited(entry["text"], True, now)
            except ics_edit.EditRefused as exc:
                raise _cannot_change(entry["id"], str(exc)) from None

    def decide(entry: dict[str, Any]) -> bytes | ChainSkip:
        if entry["id"] != own_id:
            if entry["status"] == "completed":
                return ChainSkip.UNCHANGED
            if entry["status"] == "cancelled":
                return ChainSkip.LEFT_ALONE
        return payloads[entry["id"]]

    async def write(entry: dict[str, Any], payload: bytes, entry_etag: str) -> str:
        return await tasks_client.put_existing_todo(
            clients.client, clients.creds, task_list, entry["object_name"], payload, entry_etag
        )

    root = {"id": own_id, "object_name": object_name, "status": status}
    report = await run_chain(task_list, root, wanted, descendants, decide, write, skipped=skipped)

    result: dict[str, Any] = {"id": own_id, "already": False}
    if report.failed is None:
        result["status"] = "completed" if completed else "open"
    elif report.failed != own_id or report.reason in _KEPT_ON_STOP:
        result["status"] = status
    result.update(report.as_answer())
    if report.root_etag:
        result["etag"] = report.root_etag
    elif report.root_etag == "":
        result["note"] = NEW_ETAG_NOTE
    return result


# --- Changing the named fields of a task (plan 33-07) ---------------------------------------

#: The fields of ``tasks_update`` in the order of every answer, with their iCalendar names.
_UPDATE_FIELDS = {
    "summary": "SUMMARY",
    "description": "DESCRIPTION",
    "due": "DUE",
    "start": "DTSTART",
    "priority": "PRIORITY",
    "tags": "CATEGORIES",
    "parent": ics_edit.PARENT,
}

_NO_FIELD_HINT = (
    "Pass summary, description, due, start, priority, tags or parent; an empty value clears "
    "a field."
)


def _one_line_end(text: str) -> str:
    """Line breaks of an input text as LF: RFC 5545 text cannot carry a carriage return
    (plan 33-04), so it would never read back as it was written."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _update_time(text: str, field: str) -> date | datetime:
    """A date stays a date; a time with an offset or Z is written in UTC (D-33-15)."""
    value = _parse_task_time(text, field)
    if value is None:
        raise _refused(f"{field} is empty.", _TASK_TIME_HINT)
    if not isinstance(value, datetime):
        return value
    if value.microsecond:
        raise _refused(f"{field} must be given in whole seconds.", _TASK_TIME_HINT)
    return value.astimezone(UTC)


def _wanted_fields(
    *,
    summary: str | None,
    description: str | None,
    due: str | None,
    start: str | None,
    priority: int | None,
    tags: Sequence[str] | None,
    parent: str | None,
) -> dict[str, Any]:
    """The named fields, checked before any request; ``None`` as a value means "clear".

    A field left out or ``None`` is not in the result and stays as it is; an empty value
    clears it (``""``, ``[]``, ``priority=0``); an empty summary is refused (D-33-07,
    D-33-15). ``parent`` stays the task id here, its UID comes from the list later.
    """
    wanted: dict[str, Any] = {}
    if summary is not None:
        if not summary.strip():
            raise _refused(
                "The summary of a task cannot be cleared.",
                "Give a short title, or leave summary out to keep it.",
            )
        wanted["summary"] = _one_line_end(summary)
    if description is not None:
        wanted["description"] = _one_line_end(description) if description.strip() else None
    for field, text in (("due", due), ("start", start)):
        if text is not None:
            wanted[field] = _update_time(text, field) if text.strip() else None
    if priority is not None:
        _check_priority(priority)
        wanted["priority"] = priority or None
    if tags is not None:
        if isinstance(tags, str):
            raise _refused("tags must be a list of texts.", "Pass tags=[...], or tags=[] to clear.")
        wanted["tags"] = _clean_tags([_one_line_end(str(tag)) for tag in tags]) or None
    if parent is not None:
        wanted["parent"] = parent.strip() or None
    if not wanted:
        raise _refused("Name at least one field to change.", _NO_FIELD_HINT)
    return wanted


def _is_utc(value: date | datetime) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
        and value.tzname() == "UTC"
    )


def _check_merged_times(
    wanted: dict[str, Any], todo: dict[str, Any], facts: ics_edit.TodoFacts, own_id: str
) -> None:
    """The time checks of ``tasks_create`` on the state after the change (TMOD-04).

    A new due date is checked against the stored start and the other way round: both dates
    or both times, the start before the due date. A stored floating time or a time in a
    named zone is not compared with a new UTC time by guessing: both have to be set. A
    DURATION stands beside DUE or DTSTART only under rules this tool does not keep, so
    neither may be changed then (RFC 5545).
    """
    if "due" not in wanted and "start" not in wanted:
        return
    if "DURATION" in facts.fields:
        raise _refused(
            f"The task {own_id} has a DURATION, so due and start cannot be changed here.",
            "Change its dates in the Nextcloud Tasks app.",
        )
    final = {
        field: wanted[field] if field in wanted else todo.get(f"_{field}_value")
        for field in ("due", "start")
    }
    if final["due"] is None or final["start"] is None:
        return
    for field, other in (("due", "start"), ("start", "due")):
        kept = final[other]
        new_time = field in wanted and isinstance(wanted[field], datetime)
        if new_time and other not in wanted and isinstance(kept, datetime) and not _is_utc(kept):
            kind = "a floating time" if kept.tzinfo is None else "a time in a named zone"
            raise _refused(
                f"The stored {other} of the task is {kind}, which cannot be compared with a "
                "time in UTC.",
                "Set due and start together, both with an offset or Z.",
            )
    _check_times(final["due"], final["start"], None)


def _raw_tags(prop: Any) -> list[str]:
    """Every tag as stored, over every CATEGORIES line and in order (pitfall 11)."""
    return [str(tag) for line in _as_list(prop) for tag in getattr(line, "cats", [line])]


def _same_time(old: date | datetime, new: date | datetime) -> bool:
    """The same moment in the same value type; a floating time never equals a UTC time."""
    if isinstance(new, datetime):
        return isinstance(old, datetime) and old.tzinfo is not None and old == new
    return not isinstance(old, datetime) and old == new


def _differs(field: str, value: Any, todo: Any, facts: ics_edit.TodoFacts) -> bool:
    """Whether the stored task differs from the wanted value (``None``: cleared)."""
    if field == "parent":
        return _parents(todo.get("RELATED-TO")) != ([] if value is None else [value])
    prop = todo.get(_UPDATE_FIELDS[field])
    if value is None:
        if field == "description":
            return bool(str(prop or "")) or "X-ALT-DESC" in facts.fields
        return prop is not None
    if prop is None:
        return True
    if field == "tags":
        return _raw_tags(prop) != value
    if field == "priority":
        return str(prop).strip() != str(value)
    if field in ("due", "start"):
        return not _same_time(prop.dt, value)
    return str(prop) != value


async def _parent_of_update(clients: NcClients, loaded: _Stored, parent: str) -> str:
    """The UID of the new parent: in the same list, not the task, none of its descendants.

    One REPORT of the list (the chain read of plan 33-05) finds the parent by its object
    name and the descendants of the task, so a cycle never starts here (TMOD-04).
    """
    _key, parent_object = _parse_parent(parent)
    entries, _skipped = await read_chain_list(clients, loaded.task_list)
    match = next((entry for entry in entries if entry["object_name"] == parent_object), None)
    if match is None or not match["uid"]:
        raise _unknown_task(parent)
    if match["uid"] == loaded.todo["uid"]:
        raise _refused("A task cannot be its own parent.", _OTHER_PARENT_HINT)
    descendants = descendants_post_order(loaded.todo["uid"], entries)
    if any(entry["object_name"] == parent_object for entry in descendants):
        raise _refused(
            f"The task {parent} is a subtask of {loaded.own_id}, so it cannot become its parent.",
            "Pick a task outside of its subtasks as parent.",
        )
    return match["uid"]


_OTHER_PARENT_HINT = "Pick another task of the same list as parent."


async def update_task(
    clients: NcClients,
    *,
    task_id: str,
    etag: str,
    summary: str | None = None,
    description: str | None = None,
    due: str | None = None,
    start: str | None = None,
    priority: int | None = None,
    tags: Sequence[str] | None = None,
    parent: str | None = None,
) -> dict[str, Any]:
    """Change or clear the named fields of one task, nothing else (TMOD-02, TMOD-04).

    A field left out or ``None`` stays; an empty value clears it (``""`` for description,
    due, start and parent, ``[]`` for tags, ``priority=0``); an empty summary is refused
    (D-33-07, D-33-15). Times with an offset or Z are written in UTC with Z, dates as
    ``VALUE=DATE``; there is no zone parameter. Status and list are not fields of this tool.

    Refused before any request: the checks of ``tasks_create`` on the new values, a parent
    in another list or the task itself, and a call that names no field. After the GET and
    before any write: everything :func:`_read_for_change` refuses, the time checks on the
    merged state and a parent that is unknown in the list or a descendant of the task.

    Without a difference to the stored task nothing is written (``changed`` empty);
    otherwise exactly one PUT with ``If-Match`` through the line editor, which keeps every
    untouched line and brings LAST-MODIFIED and DTSTAMP to the same UTC second (ENTSCHEID
    pflegefelder_entfernen). A changed description drops the HTML version (``X-ALT-DESC``,
    ``ALTREP``) and the answer says so (D-33-13). The answer names the fields, never a URI
    or an owner; ``etag`` comes from the PUT alone.
    """
    list_key, object_name = _task_key(task_id)
    wanted_etag = dav.normalize_etag(etag)
    wanted = _wanted_fields(
        summary=summary,
        description=description,
        due=due,
        start=start,
        priority=priority,
        tags=tags,
        parent=parent,
    )
    if wanted.get("parent") is not None:
        parent_key, parent_object = _parse_parent(wanted["parent"])
        if parent_key != list_key:
            raise _refused(
                "The parent task lives in another list.",
                "Pick a parent from the list of the task; an empty parent only detaches it.",
            )
        if parent_object == object_name:
            raise _refused("A task cannot be its own parent.", _OTHER_PARENT_HINT)
    if wanted.get("due") is not None and wanted.get("start") is not None:
        _check_times(wanted["due"], wanted["start"], None)

    loaded = await _read_for_change(clients, task_id, list_key, object_name, wanted_etag)
    _check_merged_times(wanted, loaded.todo, loaded.facts, loaded.own_id)
    values = dict(wanted)
    if wanted.get("parent") is not None:
        values["parent"] = await _parent_of_update(clients, loaded, wanted["parent"])

    before = _crlf(loaded.text)
    (stored,) = IcsCalendar.from_ical(before).walk("VTODO")
    changed = [
        name for name, value in values.items() if _differs(name, value, stored, loaded.facts)
    ]
    result: dict[str, Any] = {
        "id": loaded.own_id,
        "list": _list_info(loaded.task_list),
        "changed": changed,
    }
    if not changed:
        return result

    now = datetime.now(UTC).replace(microsecond=0)
    set_fields: dict[str, Any] = {}
    drop_fields: list[str] = []
    for name in changed:
        if values[name] is None:
            drop_fields.append(_UPDATE_FIELDS[name])
        else:
            set_fields[_UPDATE_FIELDS[name]] = values[name]
    set_fields.update({"LAST-MODIFIED": now, "DTSTAMP": now})
    html_removed = False
    if "description" in changed:
        old = stored.get("DESCRIPTION")
        altrep = old is not None and any(str(key).upper() == "ALTREP" for key in old.params)
        if "X-ALT-DESC" in loaded.facts.fields:
            drop_fields.append("X-ALT-DESC")
        html_removed = altrep or "X-ALT-DESC" in loaded.facts.fields

    expected: dict[str, Any] = dict(set_fields)
    expected.update(dict.fromkeys(drop_fields))
    try:
        after = ics_edit.apply(before, set_fields=set_fields, drop_fields=drop_fields)
        ics_edit.verify(before, after, expected)
    except ics_edit.EditRefused as exc:
        raise _cannot_change(loaded.own_id, str(exc)) from None
    new_etag = await tasks_client.put_existing_todo(
        clients.client,
        clients.creds,
        loaded.task_list,
        object_name,
        after.encode("utf-8"),
        wanted_etag,
    )

    removed = [name for name in changed if values[name] is None]
    if removed:
        result["removed"] = removed
    if html_removed:
        result["html_description_removed"] = True
    if new_etag:
        result["etag"] = new_etag
    else:
        result["note"] = NEW_ETAG_NOTE
    return result


# --- Relocating a task with its subtasks into a named list (plan 33-08) ---------------------

_TARGET_HINT = "Pass the name or key of a writable task list from tasks_search as list."

#: Stop reasons after which the task that failed is known to be where it was.
_STAYED_ON_STOP = frozenset(
    {"changed_or_name_taken", "uid_conflict", "not_found_or_read_only", "refused"}
)


def _target_wanted(target: Any) -> str:
    """The named target list, refused before any request when empty or a Deck key."""
    if not isinstance(target, str) or not target.strip():
        raise _refused("list must name the task list to relocate the task into.", _TARGET_HINT)
    if target.strip().startswith(tasks_client.DECK_PREFIX):
        # A Deck board is never a task list and never asked (E9).
        raise _refused(f"This account has no task list called {_quoted(target)}.", _TARGET_HINT)
    return target


def _relocation_target(lists: list[tasks_client.TaskList], wanted: str) -> tasks_client.TaskList:
    """The one writable task list ``wanted`` names, resolved like tasks_search does.

    Never positional and never a guess: a name that matches an own and a shared list is an
    ambiguity with keys, and a shared list is only a target when it is named uniquely
    (D-32-18). A calendar without tasks is not in the discovery and so unknown.
    """
    if not _list_matches(lists, wanted):
        raise ToolError(
            message=f"This account has no task list called {_quoted(wanted)}.",
            hint=_writable_hint(lists),
        )
    target = _resolve_list(lists, wanted)
    if not target.writable:
        raise _refused(
            f"The task list {_list_name(target)!r} is read only for this account.",
            _writable_hint(lists),
        )
    return target


async def _target_holdings(
    clients: NcClients, target: tasks_client.TaskList
) -> tuple[set[str], set[str]]:
    """Object names and UIDs the target list holds, from one REPORT under the list budget.

    A name counts even when its object cannot be read: the server refuses a relocation onto
    any taken name (412), so the check has to see them all.
    """
    try:
        async with asyncio.timeout(PER_LIST_TIMEOUT):
            objects = await tasks_client.query_todos(
                clients.client, clients.creds, target, tasks_client.build_todo_query(None)
            )
    except (TimeoutError, httpx.TimeoutException):
        raise ToolError(
            message=(
                f"The task list {_list_name(target)} did not answer in time "
                f"({_seconds(PER_LIST_TIMEOUT)}): nothing was relocated."
            ),
            hint="Try again in a moment; the task and its subtasks are where they were.",
            reason=REASON_TIMEOUT,
        ) from None
    names = {item.object_name for item in objects}
    uids: set[str] = set()
    for item in objects:
        todo = _read_todo(item.ics)
        if todo is not None and todo["uid"]:
            uids.add(todo["uid"])
    return names, uids


def _check_free(
    target: tasks_client.TaskList,
    holdings: tuple[set[str], set[str]],
    tasks: list[tuple[str, str, str]],
) -> None:
    """Refuse before the first relocation when the target holds a name or UID already.

    ``tasks`` holds (id, object name, UID) of everything that would be relocated. This
    turns the two answers of the server that leave nothing relocated (412 on a taken name,
    409 on a taken UID) into a refusal before the chain starts, so a later 412 almost
    always means "changed since read" (pitfall 2).
    """
    names, uids = holdings
    hint = "Nothing was relocated. Pick another list, or tidy up the target list first."
    for task_id, object_name, uid in tasks:
        if object_name in names:
            raise _refused(
                f"The task list {_list_name(target)} already holds an object with the name "
                f"of the task {task_id}.",
                hint,
            )
        if uid and uid in uids:
            raise _refused(
                f"The task list {_list_name(target)} already holds a task with the UID of "
                f"the task {task_id}.",
                hint,
            )


def _relocation_payload(entry: dict[str, Any]) -> bytes:
    """A relocation sends no text: every object goes as it is stored."""
    return b""


async def move_task(
    clients: NcClients, *, task_id: str, etag: str, list_name: str
) -> dict[str, Any]:
    """Relocate one task with all its subtasks into the named task list (TMOD-08).

    Refused before any request: an id that is not a task id, a Deck key of the task
    (answered like an unknown task, E9), an ETag that is not one strong validator, an empty
    target and a target with the Deck prefix. Refused after the discovery and before any
    relocation: an unknown target (the hint names the writable task lists), an ambiguous
    one (the hint names the keys), a read only target, and everything
    :func:`_read_for_change` refuses on the source (read only list, stale ETag, recurring,
    several VTODO, not UTF-8). The same list is a success without a relocation.

    Then one REPORT of the source finds the descendants (D-33-00c) and the check of the
    chain refuses more than :data:`CHAIN_CAP` or a recurring or unreadable one (D-33-10,
    D-33-11); one REPORT of the target refuses when it already holds the object name or the
    UID of anything to relocate (pitfall 2). Only then the chain of plan 33-05 relocates the
    descendants in post-order and the named task last, each under its own name with
    ``Overwrite: F`` and ``If-Match`` (D-33-09), and stops at the first failure.

    UID, object name and text stay; so does the ETag (spike 4.1), which the answer repeats
    only after a full success and only when the GET had sent it. The answer names old and
    new task ids and the target list, never a URI or an owner.
    """
    list_key, object_name = _task_key(task_id)
    wanted_etag = dav.normalize_etag(etag)
    wanted_list = _target_wanted(list_name)

    lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
    if len([entry for entry in lists if entry.key == list_key]) != 1:
        raise _unknown_task(task_id)
    target = _relocation_target(lists, wanted_list)
    loaded = await _read_for_change(
        clients, task_id, list_key, object_name, wanted_etag, lists=lists
    )
    source, own_id = loaded.task_list, loaded.own_id
    if target.key == source.key:
        return {"id": own_id, "list": _list_info(target), "already": True}

    entries, skipped = await read_chain_list(clients, source)
    descendants = descendants_post_order(loaded.todo["uid"], entries)
    check_chain(source, descendants)
    root: dict[str, Any] = {"id": own_id, "object_name": object_name, "uid": loaded.todo["uid"]}
    everything = [root, *descendants]
    _check_free(
        target,
        await _target_holdings(clients, target),
        [(entry["id"], entry["object_name"], entry["uid"] or "") for entry in everything],
    )

    errors: list[ToolError] = []

    async def write(entry: dict[str, Any], payload: bytes, entry_etag: str) -> str:
        try:
            await tasks_client.move_todo(
                clients.client, clients.creds, source, target, entry["object_name"], entry_etag
            )
        except ToolError as exc:
            errors.append(exc)
            raise
        return entry_etag

    report = await run_chain(
        source, root, wanted_etag, descendants, _relocation_payload, write, skipped=skipped
    )
    new_ids = {
        entry["id"]: ids.encode_task(target.key, entry["object_name"]) for entry in everything
    }
    moved = [new_ids[entry_id] for entry_id in report.changed if entry_id != own_id]
    result: dict[str, Any]
    if report.failed is None:
        result = {
            "id": new_ids[own_id],
            "previous_id": own_id,
            "list": _list_info(target),
            "moved": moved,
        }
        if skipped:
            result["skipped"] = skipped
        if loaded.etag:
            result["etag"] = loaded.etag
        else:
            result["note"] = NEW_ETAG_NOTE
        return result

    reason = report.reason or "refused"
    if reason == "conflict":
        reason = "changed_or_name_taken"
    elif reason == "server_error" and errors and "(status 204)" in errors[-1].message:
        reason = "replaced"
    sentence = f"Stopped at {report.failed}: {_CHAIN_STOPS[reason]}."
    if report.failed != own_id:
        sentence += (
            f" {len(moved)} subtasks listed in moved were relocated into "
            f"{_list_name(target)} and stay there; the named task {own_id} was not relocated."
        )
    if reason not in _STAYED_ON_STOP:
        sentence += (
            f" If {report.failed} was relocated after all, its id is now {new_ids[report.failed]}."
        )
    sentence += (
        " Nothing was retried or undone: read the task again with tasks_read before the next call."
    )
    result = {
        "id": own_id,
        "list": _list_info(target),
        "moved": moved,
        "failed": report.failed,
        "reason": reason,
        "message": sentence,
    }
    if skipped:
        result["skipped"] = skipped
    return result

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
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from icalendar import Calendar as IcsCalendar

from .. import ids, paging
from ..errors import REASON_GUARD_TRIPPED, ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import tasks as tasks_client
from . import calendar, marks

#: One page of ``tasks_search`` (D-32-08). Fixed on purpose: no ``limit`` parameter, which
#: saves schema bytes in every tool listing.
PAGE_SIZE = 25

#: Wall clock budget of one task list. A slow list becomes a ``degraded`` entry instead of
#: holding the answer hostage. Below this budget the size of the answer of one list is not
#: capped (2000 tasks answered in at most 0.113 s with 1.5 MB); above it the budget is the cap.
#: MESSWERT per_list_timeout_s=1 regel=max(1,ceil(2*max)) max_s=0.113 quelle=nc35-impersonation
#: (plan 32-02, 2026-11-13, docs/tasks-evidence.md)
PER_LIST_TIMEOUT = 1.0

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

#: The values of the ``status`` parameter (D-32-09). ``open`` includes ``in_progress``.
STATUS_FILTERS = ("open", "completed", "all")

#: Shown instead of an error when the account has no task list at all (E6).
NO_LIST_HINT = (
    "This account has no task list yet. Create one in the Nextcloud Tasks app; "
    "tasks_search finds its tasks from then on."
)

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
    needle = wanted.strip().casefold()
    matches = [
        entry
        for entry in lists
        if entry.key.casefold() == needle or _list_name(entry).casefold() == needle
    ]
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

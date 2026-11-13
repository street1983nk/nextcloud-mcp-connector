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

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from icalendar import Calendar as IcsCalendar

from . import marks

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

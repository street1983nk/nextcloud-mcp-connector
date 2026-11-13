"""Edit the named fields of one existing VTODO and keep every other byte (TMOD-02).

The editor works on logical lines, never through the icalendar object model, because a
round trip through the object model rewrites foreign lines: it reorders the parts of an
``RRULE`` in a ``VTIMEZONE``, refolds at 75 octets, writes ``\\N`` as ``\\n`` and upper cases
names (33-RESEARCH.md, "icalendar 7.3.0 gemessen"). So:

*   The text is split into logical lines, and each keeps its physical original (folding and
    line ends). Unfolding (a line break followed by a space or a tab) serves only to read the
    name of a line.
*   A component stack over ``BEGIN``/``END`` (any case) decides which lines are candidates:
    only lines whose stack is exactly ``[VCALENDAR, VTODO]``. A ``DESCRIPTION`` in a
    ``VALARM``, a ``DTSTART`` in a ``VTIMEZONE`` or anything inside an unknown component is
    never hit.
*   New lines come from icalendar alone, through a throwaway ``Todo`` and
    ``to_ical(sorted=False)``; there is no escaping and no folding of our own. Parameters of a
    replaced line are read with ``Contentline(...).parts()``.
*   Replacing happens at the place of the first line of the name; further lines of the same
    name are dropped (several ``CATEGORIES`` lines, several parent ``RELATED-TO`` lines).
    Inserting happens before the first subcomponent of the VTODO or before ``END:VTODO``.
    New lines take the line end of the original.

Clearing follows what the Tasks app 0.18.1 wrote in plan 33-01b (ENTSCHEID entfernen_*): the
line goes, except ``DESCRIPTION``, which stays as an empty ``DESCRIPTION:`` line.

Three public functions for the tools of plans 33-06 to 33-08: ``inspect`` (the check before
the edit), ``apply`` (the edit) and ``verify`` (the check of the result before any write). All
three refuse with ``EditRefused`` instead of guessing, so a broken object is never written.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from icalendar import Calendar, Todo
from icalendar.parser import Contentline

PARENT = "PARENT"
"""Special name for the parent relation: ``RELATED-TO`` without ``RELTYPE`` or with ``PARENT``."""

TEXT_FIELDS = frozenset({"SUMMARY", "DESCRIPTION", "STATUS"})
INT_FIELDS = frozenset({"PRIORITY", "PERCENT-COMPLETE"})
TIME_FIELDS = frozenset({"DUE", "DTSTART", "COMPLETED", "LAST-MODIFIED", "DTSTAMP"})
STAMP_FIELDS = frozenset({"COMPLETED", "LAST-MODIFIED", "DTSTAMP"})
SETTABLE = TEXT_FIELDS | INT_FIELDS | TIME_FIELDS | {"CATEGORIES", PARENT}
CLEARABLE = (SETTABLE - {"SUMMARY", "STATUS", "LAST-MODIFIED", "DTSTAMP"}) | {"X-ALT-DESC"}

SINGLE_VALUED = frozenset(
    {
        "UID",
        "SUMMARY",
        "DESCRIPTION",
        "DUE",
        "DTSTART",
        "PRIORITY",
        "STATUS",
        "COMPLETED",
        "PERCENT-COMPLETE",
        "DTSTAMP",
        "LAST-MODIFIED",
    }
)
"""Fields RFC 5545 allows once per VTODO; a second line means "refuse", never "pick one"."""

KEEP_PARAMETERS = frozenset({"SUMMARY", "DESCRIPTION", "CATEGORIES", "RELATED-TO"})
"""Replacing these keeps the parameters of the old line (``LANGUAGE``, unknown ``X-``)."""

LEFT_OUT_PARAMETERS = frozenset({"ALTREP", "VALUE"})
"""D-33-13: new text no longer matches its alternative representation; the value type is
always the one icalendar picks for the new value."""

CLEARED_TO_EMPTY = frozenset({"DESCRIPTION"})
"""ENTSCHEID entfernen_description=leer: the Tasks app writes ``DESCRIPTION:`` when cleared."""

RECURRENCE = frozenset({"RRULE", "RDATE", "RECURRENCE-ID"})
ROOT = ("VCALENDAR",)
IN_VTODO = ("VCALENDAR", "VTODO")

_PHYSICAL = re.compile(r"[^\n]*\n|[^\n]+\Z")
_NAME = re.compile(r"[A-Za-z0-9-]+")
_FOLD = re.compile(r"\r?\n[ \t]")


class EditRefused(ValueError):
    """The object cannot be edited safely; the message is a short English reason."""


@dataclass(frozen=True)
class TodoFacts:
    """What the check before the edit found in the one VTODO of an object."""

    uid: str
    recurring: bool
    line_end: str
    fields: frozenset[str]


@dataclass(frozen=True)
class _Line:
    raw: str
    """The physical original, folding and line ends included."""
    logical: str
    """The unfolded line without its line end, only for reading name and parameters."""
    name: str
    """Upper case name of a property; ``BEGIN`` or ``END`` for a component boundary."""
    component: str
    """Upper case component name of a ``BEGIN`` or ``END`` line, else empty."""
    stack: tuple[str, ...]
    """The components the line stands in; for ``BEGIN`` and ``END`` the ones around it."""

    @property
    def is_property(self) -> bool:
        return not self.component


def _lines(text: str) -> list[_Line]:
    """Logical lines with their component stack; refuses an unbalanced structure."""
    groups: list[str] = []
    for physical in _PHYSICAL.findall(text):
        if physical[:1] in (" ", "\t") and groups:
            groups[-1] += physical
        else:
            groups.append(physical)
    lines: list[_Line] = []
    stack: list[str] = []
    for raw in groups:
        logical = _FOLD.sub("", raw).rstrip("\r\n")
        match = _NAME.match(logical)
        name = match.group().upper() if match else ""
        rest = logical[match.end() :] if match else ""
        component = rest[1:].strip().upper() if rest.startswith(":") else ""
        if name == "BEGIN" and component:
            if not stack and component != "VCALENDAR":
                raise EditRefused("object must start with BEGIN:VCALENDAR")
            lines.append(_Line(raw, logical, name, component, tuple(stack)))
            stack.append(component)
        elif name == "END" and component:
            if not stack or stack[-1] != component:
                raise EditRefused("components are not balanced")
            stack.pop()
            lines.append(_Line(raw, logical, name, component, tuple(stack)))
        elif not stack:
            if logical.strip():
                raise EditRefused("content outside of VCALENDAR")
            lines.append(_Line(raw, logical, "", "", ()))
        elif not name:
            raise EditRefused("a line without a name")
        else:
            lines.append(_Line(raw, logical, name, "", tuple(stack)))
    if stack or not lines:
        raise EditRefused("components are not balanced")
    return lines


def _parse(text: str) -> Any:
    try:
        calendars: Any = Calendar.from_ical(text, multiple=True)
    except Exception as error:
        # Foreign text is data: whatever icalendar trips over is a refusal, never a crash.
        raise EditRefused("object is not valid iCalendar") from error
    if len(calendars) != 1:
        raise EditRefused("object must hold exactly one VCALENDAR")
    return calendars[0]


def _parts(line: _Line) -> tuple[str, Any, str]:
    try:
        name, params, value = Contentline(line.logical).parts()
    except Exception as error:
        raise EditRefused(f"cannot read the line {line.name}") from error
    return name, params, value


def _is_parent(line: _Line) -> bool:
    reltype = _parts(line)[1].get("RELTYPE", PARENT)
    return str(reltype).strip().upper() == PARENT


def _matches(line: _Line, name: str) -> bool:
    if name == PARENT:
        return line.name == "RELATED-TO" and _is_parent(line)
    return line.name == name


def _as_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    return list(raw) if isinstance(raw, list) else [raw]


def inspect(text: str) -> TodoFacts:
    """Check an object before an edit: it parses and holds exactly one VTODO.

    Refuses broken text, no or several VTODO components and a single valued field written
    twice. A recurring task (``RRULE``, ``RDATE`` or ``RECURRENCE-ID``) is reported, not
    refused here; ``apply`` refuses it.
    """
    if not text.strip():
        raise EditRefused("object is empty")
    lines = _lines(text)
    todo_begins = [x for x in lines if x.name == "BEGIN" and x.component == "VTODO"]
    if len(todo_begins) != 1 or todo_begins[0].stack != ROOT:
        raise EditRefused("object must hold exactly one VTODO")
    todos = list(_parse(text).walk("VTODO"))
    if len(todos) != 1:
        raise EditRefused("object must hold exactly one VTODO")
    names = [x.name for x in lines if x.is_property and x.stack == IN_VTODO]
    for name in sorted(SINGLE_VALUED):
        if names.count(name) > 1:
            raise EditRefused(f"field {name} appears more than once")
    uid = str(todos[0].get("UID") or "").strip()
    if not uid:
        raise EditRefused("task has no UID")
    return TodoFacts(
        uid=uid,
        recurring=any(name in RECURRENCE for name in names),
        line_end="\r\n" if "\r\n" in text else "\n",
        fields=frozenset(names),
    )


def _utc(name: str, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0) or value.tzname() != "UTC":
        raise EditRefused(f"time for {name} must be in UTC")
    if value.microsecond:
        raise EditRefused(f"time for {name} must be whole seconds")
    return value.replace(tzinfo=UTC)


def _checked(name: str, value: Any) -> Any:
    """The value in the form icalendar then writes as the Tasks app does (D-33-15)."""
    if name in TEXT_FIELDS:
        if not isinstance(value, str) or (name != "DESCRIPTION" and not value.strip()):
            raise EditRefused(f"field {name} needs text")
        return value
    if name in INT_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise EditRefused(f"field {name} needs a number")
        return value
    if name in TIME_FIELDS:
        if isinstance(value, datetime):
            return _utc(name, value)
        if isinstance(value, date) and name not in STAMP_FIELDS:
            return value
        raise EditRefused(f"field {name} needs a date or a time")
    if name == "CATEGORIES":
        tags: Any = value
        if not isinstance(tags, list) or not tags:
            raise EditRefused("field CATEGORIES needs a non-empty list of tags")
        if not all(isinstance(tag, str) and tag for tag in tags):
            raise EditRefused("field CATEGORIES needs a non-empty list of tags")
        return list(tags)
    if not isinstance(value, str) or not value.strip():
        raise EditRefused("parent needs a UID")
    return value


def _written(name: str, value: Any, params: Mapping[str, Any], line_end: str) -> str:
    """One property as icalendar writes it, in the line end of the original."""
    todo = Todo()
    todo.add(name, value, parameters=dict(params))
    produced = todo.to_ical(sorted=False).decode("utf-8").split("\r\n")
    # BEGIN:VTODO, the physical lines of the property, END:VTODO and the empty rest.
    return "".join(line + line_end for line in produced[1:-2])


def _kept_params(name: str, old: _Line | None) -> dict[str, Any]:
    if old is None or name not in KEEP_PARAMETERS:
        return {}
    return {
        str(key).upper(): value
        for key, value in _parts(old)[1].items()
        if str(key).upper() not in LEFT_OUT_PARAMETERS
    }


def apply(text: str, *, set_fields: Mapping[str, Any], drop_fields: Iterable[str] = ()) -> str:
    """Set and clear the named fields of the one VTODO; every other line stays as it is.

    ``set_fields`` maps names to values: ``str`` for text, ``int`` for ``PRIORITY`` and
    ``PERCENT-COMPLETE``, ``date`` (written as ``VALUE=DATE``) or ``datetime`` in UTC (written
    with ``Z``), a list of ``str`` for ``CATEGORIES`` and the UID of the parent for ``PARENT``.
    ``drop_fields`` names fields to clear, ``PARENT`` and ``X-ALT-DESC`` included; clearing a
    field that is not there changes nothing.
    """
    facts = inspect(text)
    if facts.recurring:
        raise EditRefused("recurring task")
    wanted = {str(name).upper(): value for name, value in set_fields.items()}
    cleared = [str(name).upper() for name in drop_fields]
    unknown = sorted(set(wanted) - SETTABLE) + sorted(set(cleared) - CLEARABLE)
    if unknown:
        raise EditRefused(f"field {unknown[0]} cannot be changed")
    if set(wanted) & set(cleared):
        raise EditRefused("a field cannot be set and cleared at once")
    values = {name: _checked(name, value) for name, value in wanted.items()}
    end = facts.line_end

    def render(name: str, old: _Line | None) -> str:
        target = "RELATED-TO" if name == PARENT else name
        return _written(target, values[name], _kept_params(target, old), end)

    out: list[str] = []
    written: set[str] = set()
    inserted = False
    for line in _lines(text):
        boundary = (line.name == "BEGIN" and line.stack == IN_VTODO) or (
            line.name == "END" and line.component == "VTODO"
        )
        if boundary and not inserted:
            # New fields go before the first subcomponent or before END:VTODO (RFC 5545).
            out.extend(render(name, None) for name in values if name not in written)
            written.update(values)
            inserted = True
        if not line.is_property or line.stack != IN_VTODO:
            out.append(line.raw)
            continue
        hit = next((name for name in values if _matches(line, name)), None)
        if hit is not None:
            if hit not in written:
                written.add(hit)
                out.append(render(hit, line))
            continue
        clear = next((name for name in cleared if _matches(line, name)), None)
        if clear is None:
            out.append(line.raw)
        elif clear in CLEARED_TO_EMPTY:
            out.append(_written(clear, "", {}, end))
    return "".join(out)


def _shows(todo: Any, name: str, value: Any) -> bool:
    if name == PARENT:
        return _parents(todo) == ([] if value is None else [value])
    if value is None:
        if name in CLEARED_TO_EMPTY:
            return str(todo.get(name) or "") == ""
        return todo.get(name) is None
    if name == "CATEGORIES":
        tags = [str(tag) for line in _as_list(todo.get(name)) for tag in line.cats]
        return tags == list(value)
    prop = todo.get(name)
    if prop is None:
        return False
    if isinstance(value, (date, datetime)):
        got = getattr(prop, "dt", None)
        return type(got) is type(value) and got == value
    if isinstance(value, int):
        return str(prop).strip() == str(value)
    return str(prop) == value


def _parents(todo: Any) -> list[str]:
    parents: list[str] = []
    for value in _as_list(todo.get("RELATED-TO")):
        params = getattr(value, "params", {}) or {}
        if str(params.get("RELTYPE", PARENT)).strip().upper() == PARENT:
            parents.append(str(value).strip())
    return parents


def verify(before: str, after: str, expected: Mapping[str, Any]) -> None:
    """Check a result before it is written: it parses, holds exactly one VTODO with the UID
    of ``before`` and shows every value of ``expected`` (``None`` means cleared)."""
    old = inspect(before)
    new = inspect(after)
    if new.uid != old.uid:
        raise EditRefused("the edit changed the UID")
    todo = _parse(after).walk("VTODO")[0]
    for name, value in expected.items():
        if not _shows(todo, str(name).upper(), value):
            raise EditRefused(f"the edit did not produce field {str(name).upper()}")

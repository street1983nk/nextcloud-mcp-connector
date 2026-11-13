"""Round trip proofs for the line editor of one existing VTODO (TMOD-02, plan 33-04).

The editor in ``tools/ics_edit.py`` changes the named fields of one task and nothing else.
Two proofs hold it to that, and neither walks the way of the editor (house rule: a counter
check never uses the pattern of the implementation):

*   **Byte proof, never unfolding the original:** every physical line, folding and line end
    included, of every property the edit does not name stands verbatim and in the same order
    in the result, and every byte outside ``BEGIN:VTODO`` to ``END:VTODO`` is the same. It
    works on raw bytes with a substring search; the editor works on logical lines.
*   **Semantic proof with icalendar:** both texts are parsed, and per component path the
    multiset of ``(NAME, parameters, to_ical(value))`` is built. The difference may only hold
    the named fields plus ``LAST-MODIFIED`` and ``DTSTAMP``. The editor never parses into the
    object model to edit.

The positive control plants a broken editor that drops one ``X-`` line and requires both
proofs to name exactly that line. The objects are every fixture the Tasks app wrote
(``tests/fixtures/tasks_app/``) plus rich objects built by hand: the probe object of the spike
(VTIMEZONE with ``RRULE BYMONTH=3;BYDAY=-1SU``, VALARM with a DESCRIPTION, X- properties, a
parameter on SUMMARY), its LF variant, folding at 40 characters, lower case names, two
CATEGORIES lines, ``RELATED-TO;RELTYPE=SIBLING`` next to a parent, an unknown component, an
HTML description with ``ALTREP`` and ``SUMMARY;LANGUAGE=de``.

``ics_edit`` is imported inside the test functions, never at module level, so the file can be
collected before the module exists (TDD step RED of plan 33-04).
"""

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from icalendar import Calendar as IcsCalendar

pytestmark = pytest.mark.filterwarnings("error")

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tasks_app"
EDITOR_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "mcp_connector" / "tools" / "ics_edit.py"
)

# The one moment of every edit case. The tools write LAST-MODIFIED and DTSTAMP with the same
# UTC second as COMPLETED (D-33-08, ENTSCHEID pflegefelder_entfernen=DTSTAMP,LAST-MODIFIED).
NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=UTC)
MAINTENANCE = ("LAST-MODIFIED", "DTSTAMP")

# The form of clearing, taken word for word from the ENTSCHEID lines of plan 33-01b in
# .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt, lines 470 to 475:
#   ENTSCHEID entfernen_due=zeile-weg quelle=M2
#   ENTSCHEID entfernen_start=zeile-weg quelle=M2
#   ENTSCHEID entfernen_description=leer quelle=M2 rohzeile=DESCRIPTION:
#   ENTSCHEID entfernen_parent=zeile-weg quelle=M2
#   ENTSCHEID entfernen_priority=zeile-weg quelle=M2 (wie D-33-07)
#   ENTSCHEID entfernen_tags=zeile-weg quelle=M2 (wie D-33-07)
# and line 733: OWNERFRAGE entfaellt grund=keine-abweichung.
CLEAR_FORM = {
    "DUE": "zeile-weg",
    "DTSTART": "zeile-weg",
    "DESCRIPTION": "leer",
    "PARENT": "zeile-weg",
    "PRIORITY": "zeile-weg",
    "CATEGORIES": "zeile-weg",
}
EMPTY_DESCRIPTION_LINE = b"DESCRIPTION:"

LONG_TEXT = (
    "Neuer Titel mit Komma, Semikolon; Zeilenumbruch\nund Umlauten äöü ß, "
    "länger als fünfundsiebzig Oktette, damit icalendar falten muss"
)


# --- Objects ------------------------------------------------------------------------------


def _crlf(lines: Iterable[str]) -> bytes:
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


SPIKE_LINES = [
    # The probe object of the spike, scripts/tasks_spike.py lines 604 to 650.
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//spike30//tasks_spike//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Berlin",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
    "BEGIN:VTODO",
    "UID:spike-probe-uid",
    "DTSTAMP:20261111T100000Z",
    "CREATED:20261111T100000Z",
    "LAST-MODIFIED:20261111T100000Z",
    "SUMMARY;X-SPIKE30-PARAM=abc:spike30 probe",
    "DESCRIPTION:Eine Beschreibung mit mehr als fuenfundsiebzig Zeichen\\, damit die Zeil",
    " e gefaltet werden muss und der Server sie beim Speichern nicht neu umbrechen d",
    " arf.",
    "DTSTART;TZID=Europe/Berlin:20261119T090000",
    "DUE;TZID=Europe/Berlin:20261120T101500",
    "CATEGORIES:spike30,wichtig",
    "CLASS:CONFIDENTIAL",
    "PRIORITY:1",
    "SEQUENCE:2",
    "X-SPIKE30-FOO:bar",
    "X-APPLE-SORT-ORDER:123",
    "X-OC-HIDESUBTASKS:1",
    "BEGIN:VALARM",
    "ACTION:DISPLAY",
    "DESCRIPTION:spike30 Erinnerung",
    "TRIGGER:-PT15M",
    "END:VALARM",
    "END:VTODO",
    "END:VCALENDAR",
]
SPIKE = _crlf(SPIKE_LINES)
SPIKE_LF = ("\n".join(SPIKE_LINES) + "\n").encode("utf-8")

FOLDED_40 = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//other client//EN",
        "BEGIN:VTODO",
        "UID:folded-40",
        "DTSTAMP:20261111T100000Z",
        "SUMMARY:ein Titel, der bei vierzig Zeichen",
        "  gefaltet wurde",
        "DESCRIPTION:eine Beschreibung, gefaltet bei",
        "\tvierzig Zeichen mit einem Tabulator",
        "X-FOREIGN-NOTE:auch diese fremde Zeile ist",
        "  bei vierzig Zeichen gefaltet",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)

LOWER_CASE = _crlf(
    [
        "begin:vcalendar",
        "version:2.0",
        "prodid:-//lower case client//EN",
        "begin:vtodo",
        "uid:lower-case",
        "dtstamp:20261111T100000Z",
        "last-modified:20261111T100000Z",
        "summary:klein geschrieben",
        "description:auch klein",
        "due:20261120T090000Z",
        "priority:4",
        "categories:a,b",
        "x-lower:bleibt",
        "end:vtodo",
        "end:vcalendar",
    ]
)

TWO_CATEGORIES = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//other client//EN",
        "BEGIN:VTODO",
        "UID:two-categories",
        "DTSTAMP:20261111T100000Z",
        "LAST-MODIFIED:20261111T100000Z",
        "SUMMARY:zwei Tag-Zeilen",
        "CATEGORIES:eins,zwei",
        "X-BETWEEN:zwischen den Tags",
        "CATEGORIES:drei",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)

RELATIONS = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//other client//EN",
        "BEGIN:VTODO",
        "UID:relations",
        "DTSTAMP:20261111T100000Z",
        "LAST-MODIFIED:20261111T100000Z",
        "SUMMARY:Bezüge",
        "RELATED-TO;RELTYPE=SIBLING:sibling-uid",
        "RELATED-TO:parent-uid-a",
        "RELATED-TO;RELTYPE=CHILD:child-uid",
        "RELATED-TO;RELTYPE=PARENT:parent-uid-b",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)

UNKNOWN_COMPONENT = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//other client//EN",
        "BEGIN:VTODO",
        "UID:unknown-component",
        "DTSTAMP:20261111T100000Z",
        "LAST-MODIFIED:20261111T100000Z",
        "SUMMARY:mit fremder Komponente",
        "DESCRIPTION:außen",
        "BEGIN:X-THING",
        "SUMMARY:innen bleibt",
        "DESCRIPTION:innen bleibt auch",
        "DUE:20261120T090000Z",
        "X-INNER:1",
        "END:X-THING",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)

HTML_DESCRIPTION = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//other client//EN",
        "BEGIN:VTODO",
        "UID:html-description",
        "DTSTAMP:20261111T100000Z",
        "LAST-MODIFIED:20261111T100000Z",
        "SUMMARY;LANGUAGE=de:Titel auf Deutsch",
        'DESCRIPTION;ALTREP="cid:part1.0001@example.org";LANGUAGE=de;X-KEEP=yes:Text',
        "X-ALT-DESC;FMTTYPE=text/html:<p>Text</p>",
        "PRIORITY:2",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)

WITHOUT_MAINTENANCE = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//other client//EN",
        "BEGIN:VTODO",
        "UID:without-maintenance",
        "SUMMARY:ohne DTSTAMP und LAST-MODIFIED",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:Erinnerung",
        "TRIGGER:-PT15M",
        "END:VALARM",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)

HAND_OBJECTS: dict[str, bytes] = {
    "spike": SPIKE,
    "spike_lf": SPIKE_LF,
    "folded_40": FOLDED_40,
    "lower_case": LOWER_CASE,
    "two_categories": TWO_CATEGORIES,
    "relations": RELATIONS,
    "unknown_component": UNKNOWN_COMPONENT,
    "html_description": HTML_DESCRIPTION,
    "without_maintenance": WITHOUT_MAINTENANCE,
}

RECURRING_FIXTURES = {"recurring.ics"}
FIXTURE_FILES = sorted(path.name for path in FIXTURES.glob("*.ics"))


def _objects() -> dict[str, bytes]:
    objects = {
        name: (FIXTURES / name).read_bytes()
        for name in FIXTURE_FILES
        if name not in RECURRING_FIXTURES
    }
    objects.update(HAND_OBJECTS)
    return objects


OBJECTS = _objects()

# --- Edit cases ---------------------------------------------------------------------------

Value = Any


def _case(set_fields: Mapping[str, Value], drop_fields: Iterable[str] = ()) -> dict[str, Any]:
    fields = dict(set_fields)
    for name in MAINTENANCE:
        fields[name] = NOW
    return {"set": fields, "drop": tuple(drop_fields)}


CASES: dict[str, dict[str, Any]] = {
    # D-33-08: completing and reopening.
    "complete": _case({"STATUS": "COMPLETED", "PERCENT-COMPLETE": 100, "COMPLETED": NOW}),
    "reopen": _case({"STATUS": "NEEDS-ACTION"}, ("COMPLETED", "PERCENT-COMPLETE")),
    # Every field of tasks_update set (D-33-15: UTC with Z, dates as VALUE=DATE).
    "set_summary": _case({"SUMMARY": LONG_TEXT}),
    "set_description": _case({"DESCRIPTION": LONG_TEXT}),
    "set_due_time": _case({"DUE": datetime(2026, 11, 21, 8, 30, tzinfo=UTC)}),
    "set_due_date": _case({"DUE": date(2026, 11, 22)}),
    "set_start_time": _case({"DTSTART": datetime(2026, 11, 18, 7, 0, tzinfo=UTC)}),
    "set_start_date": _case({"DTSTART": date(2026, 11, 17)}),
    "set_priority": _case({"PRIORITY": 5}),
    "set_tags": _case({"CATEGORIES": ["neu", "mit,komma", "äöü"]}),
    "set_parent": _case({"PARENT": "new-parent-uid"}),
    # Every field of tasks_update cleared (D-33-07 in the measured form).
    "drop_due": _case({}, ("DUE",)),
    "drop_start": _case({}, ("DTSTART",)),
    "drop_description": _case({}, ("DESCRIPTION",)),
    "drop_priority": _case({}, ("PRIORITY",)),
    "drop_tags": _case({}, ("CATEGORIES",)),
    "drop_parent": _case({}, ("PARENT",)),
    # D-33-13: the HTML version can be dropped on purpose.
    "drop_html": _case({}, ("X-ALT-DESC",)),
}

MATRIX = [pytest.param(obj, case, id=f"{obj}-{case}") for obj in sorted(OBJECTS) for case in CASES]


def _touched(case: Mapping[str, Any]) -> set[str]:
    return {*case["set"], *case["drop"]}


# --- Proof helpers, built without the editor ------------------------------------------------

_LINE = re.compile(rb"[^\n]*\n|[^\n]+\Z")
_NAME = re.compile(rb"[A-Za-z0-9-]+")
_RELTYPE = re.compile(rb";RELTYPE=([A-Za-z-]+)", re.IGNORECASE)


def _groups(data: bytes) -> list[bytes]:
    """Physical lines grouped per property: a line starting with space or tab continues."""
    groups: list[bytes] = []
    for line in _LINE.findall(data):
        if line[:1] in (b" ", b"\t") and groups:
            groups[-1] += line
        else:
            groups.append(line)
    return groups


def _unfolded(group: bytes) -> bytes:
    return re.sub(rb"\r?\n[ \t]", b"", group).rstrip(b"\r\n")


def _name(group: bytes) -> str:
    match = _NAME.match(_unfolded(group))
    return match.group().decode("ascii").upper() if match else ""


def _is_parent_relation(group: bytes) -> bool:
    head = _unfolded(group).split(b":", 1)[0]
    match = _RELTYPE.search(head)
    return match is None or match.group(1).upper() == b"PARENT"


def _is_touched(group: bytes, touched: set[str]) -> bool:
    name = _name(group)
    if name == "RELATED-TO":
        return "PARENT" in touched and _is_parent_relation(group)
    return name in touched


def _vtodo_span(groups: list[bytes]) -> tuple[int, int]:
    """Index of ``BEGIN:VTODO`` and of its ``END:VTODO`` among the groups."""
    start = next(i for i, g in enumerate(groups) if _unfolded(g).upper() == b"BEGIN:VTODO")
    depth = 0
    for index in range(start, len(groups)):
        line = _unfolded(groups[index]).upper()
        if line.startswith(b"BEGIN:"):
            depth += 1
        elif line.startswith(b"END:"):
            depth -= 1
            if depth == 0:
                return start, index
    raise AssertionError("no END:VTODO")


def _find_at_line_start(haystack: bytes, needle: bytes, pos: int) -> int:
    while True:
        found = haystack.find(needle, pos)
        if found <= 0 or haystack[found - 1 : found] == b"\n":
            return found
        pos = found + 1


def byte_proof(before: bytes, after: bytes, touched: set[str]) -> list[str]:
    """The physical lines of untouched properties of ``before`` missing in ``after``.

    Everything outside the VTODO must be byte equal (reported as ``outside: ...``); inside,
    every group of an untouched property, of a nested component and the BEGIN/END lines must
    appear verbatim and in order. Nested lines are never touched, whatever their name.
    """
    problems: list[str] = []
    old, new = _groups(before), _groups(after)
    old_start, old_end = _vtodo_span(old)
    new_start, new_end = _vtodo_span(new)
    if old[:old_start] != new[:new_start]:
        problems.append("outside: before BEGIN:VTODO")
    if old[old_end:] != new[new_end:]:
        problems.append("outside: from END:VTODO on")
    inside = b"".join(new[new_start : new_end + 1])
    pos = 0
    depth = 0
    for group in old[old_start : old_end + 1]:
        line = _unfolded(group).upper()
        nested = depth > 1
        if line.startswith(b"BEGIN:"):
            depth += 1
        elif line.startswith(b"END:"):
            depth -= 1
        structural = line.startswith((b"BEGIN:", b"END:"))
        if not nested and not structural and _is_touched(group, touched):
            continue
        found = _find_at_line_start(inside, group, pos)
        if found < 0:
            problems.append(group.decode("utf-8"))
        else:
            pos = found + len(group)
    return problems


Entry = tuple[str, str, tuple[tuple[str, str], ...], bytes]


def _entries(data: bytes) -> Counter[Entry]:
    calendar = IcsCalendar.from_ical(data)
    found: Counter[Entry] = Counter()

    def walk(component: Any, path: str) -> None:
        for name, raw in component.items():
            for value in raw if isinstance(raw, list) else [raw]:
                params = tuple(
                    sorted((str(k).upper(), str(v)) for k, v in (value.params or {}).items())
                )
                found[(path, str(name).upper(), params, value.to_ical())] += 1
        counts: Counter[str] = Counter()
        for sub in component.subcomponents:
            label = f"{path}/{sub.name}#{counts[sub.name]}"
            counts[sub.name] += 1
            walk(sub, label)

    walk(calendar, "VCALENDAR")
    return found


VTODO_PATH = "VCALENDAR/VTODO#0"


def _allowed(entry: Entry, touched: set[str]) -> bool:
    path, name, params, _ = entry
    if path != VTODO_PATH:
        return False
    if name == "RELATED-TO":
        reltype = dict(params).get("RELTYPE", "PARENT").upper()
        return "PARENT" in touched and reltype == "PARENT"
    return name in touched


def semantic_proof(before: bytes, after: bytes, touched: set[str]) -> list[Entry]:
    """Entries that differ between both texts and are not explained by a named field."""
    old, new = _entries(before), _entries(after)
    diff = list(((old - new) + (new - old)).elements())
    return sorted(entry for entry in diff if not _allowed(entry, touched))


def _todo(data: bytes) -> Any:
    todos = IcsCalendar.from_ical(data).walk("VTODO")
    assert len(todos) == 1
    return todos[0]


def _parent_uids(todo: Any) -> list[str]:
    raw = todo.get("RELATED-TO")
    values = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    return [
        str(v) for v in values if str((v.params or {}).get("RELTYPE", "PARENT")).upper() == "PARENT"
    ]


def _categories(todo: Any) -> list[str]:
    raw = todo.get("CATEGORIES")
    values = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    return [str(cat) for line in values for cat in line.cats]


def check_values(after: bytes, case: Mapping[str, Any]) -> None:
    """The wanted values stand in the result, read back with icalendar, not by the editor."""
    todo = _todo(after)
    for name, value in case["set"].items():
        if name == "PARENT":
            assert _parent_uids(todo) == [value]
        elif name == "CATEGORIES":
            assert _categories(todo) == value
        elif isinstance(value, (date, datetime)):
            got = todo[name].dt
            assert type(got) is type(value), name
            assert got == value, name
        elif isinstance(value, int):
            assert int(todo[name]) == value, name
        else:
            assert str(todo[name]) == value, name
    for name in case["drop"]:
        if name == "PARENT":
            assert _parent_uids(todo) == []
        elif CLEAR_FORM.get(name) == "leer":
            assert str(todo.get(name, "")) == ""
        else:
            assert name not in todo, name


def _run(obj: str, case_name: str) -> tuple[bytes, bytes, dict[str, Any]]:
    from mcp_connector.tools import ics_edit

    before = OBJECTS[obj]
    case = CASES[case_name]
    after = ics_edit.apply(
        before.decode("utf-8"), set_fields=case["set"], drop_fields=case["drop"]
    ).encode("utf-8")
    return before, after, case


# --- Positive control: the proofs catch a planted fault ------------------------------------


def _broken_editor(data: bytes) -> bytes:
    """Test aid: an editor that loses one X- line and does nothing else."""
    assert b"X-SPIKE30-FOO:bar\r\n" in data
    return data.replace(b"X-SPIKE30-FOO:bar\r\n", b"", 1)


def test_positive_control_byte_proof_names_the_lost_line() -> None:
    assert byte_proof(SPIKE, _broken_editor(SPIKE), set()) == ["X-SPIKE30-FOO:bar\r\n"]


def test_positive_control_semantic_proof_names_the_lost_line() -> None:
    assert semantic_proof(SPIKE, _broken_editor(SPIKE), set()) == [
        (VTODO_PATH, "X-SPIKE30-FOO", (), b"bar")
    ]


def test_positive_control_both_proofs_are_quiet_on_an_unchanged_object() -> None:
    for data in (*HAND_OBJECTS.values(), *(FIXTURES / n for n in FIXTURE_FILES)):
        raw = data.read_bytes() if isinstance(data, Path) else data
        assert byte_proof(raw, raw, set()) == []
        assert semantic_proof(raw, raw, set()) == []


def test_positive_control_byte_proof_sees_a_refolded_line_the_semantics_do_not() -> None:
    refolded = FOLDED_40.replace(
        b"SUMMARY:ein Titel, der bei vierzig Zeichen\r\n  gefaltet wurde\r\n",
        b"SUMMARY:ein Titel, der bei vierzig Zeichen gefaltet wurde\r\n",
    )
    assert refolded != FOLDED_40
    assert byte_proof(FOLDED_40, refolded, set()) == [
        "SUMMARY:ein Titel, der bei vierzig Zeichen\r\n  gefaltet wurde\r\n"
    ]
    assert semantic_proof(FOLDED_40, refolded, set()) == []


def test_positive_control_a_touched_line_inside_valarm_is_reported() -> None:
    changed = SPIKE.replace(b"DESCRIPTION:spike30 Erinnerung", b"DESCRIPTION:anders")
    assert byte_proof(SPIKE, changed, {"DESCRIPTION"}) == ["DESCRIPTION:spike30 Erinnerung\r\n"]
    assert {e[0] for e in semantic_proof(SPIKE, changed, {"DESCRIPTION"})} == {
        "VCALENDAR/VTODO#0/VALARM#0"
    }


def test_positive_control_a_lost_sibling_relation_is_reported_for_a_parent_edit() -> None:
    lost = RELATIONS.replace(b"RELATED-TO;RELTYPE=SIBLING:sibling-uid\r\n", b"")
    assert byte_proof(RELATIONS, lost, {"PARENT"}) == ["RELATED-TO;RELTYPE=SIBLING:sibling-uid\r\n"]
    assert semantic_proof(RELATIONS, lost, {"PARENT"}) == [
        (VTODO_PATH, "RELATED-TO", (("RELTYPE", "SIBLING"),), b"sibling-uid")
    ]


# --- The round trip over every object and every edit case ---------------------------------


def test_every_fixture_of_the_tasks_app_is_covered() -> None:
    assert len(FIXTURE_FILES) >= 16
    assert set(FIXTURE_FILES) - RECURRING_FIXTURES <= set(OBJECTS)


@pytest.mark.parametrize(("obj", "case_name"), MATRIX)
def test_round_trip_keeps_every_untouched_property(obj: str, case_name: str) -> None:
    before, after, case = _run(obj, case_name)
    touched = _touched(case)
    assert byte_proof(before, after, touched) == []
    assert semantic_proof(before, after, touched) == []
    check_values(after, case)


@pytest.mark.parametrize(("obj", "case_name"), MATRIX)
def test_round_trip_passes_the_editors_own_verify(obj: str, case_name: str) -> None:
    from mcp_connector.tools import ics_edit

    before, after, case = _run(obj, case_name)
    expected = {**case["set"], **dict.fromkeys(case["drop"])}
    ics_edit.verify(before.decode("utf-8"), after.decode("utf-8"), expected)


def test_a_broken_editor_after_a_real_edit_is_caught_at_that_line() -> None:
    before, after, case = _run("spike", "complete")
    broken = _broken_editor(after)
    touched = _touched(case)
    assert byte_proof(before, broken, touched) == ["X-SPIKE30-FOO:bar\r\n"]
    assert semantic_proof(before, broken, touched) == [(VTODO_PATH, "X-SPIKE30-FOO", (), b"bar")]


# --- Single rules of the editor -------------------------------------------------------------


def _apply(data: bytes, set_fields: Mapping[str, Value], drop: Iterable[str] = ()) -> bytes:
    from mcp_connector.tools import ics_edit

    return ics_edit.apply(
        data.decode("utf-8"), set_fields=set_fields, drop_fields=tuple(drop)
    ).encode("utf-8")


def _vtodo_lines(data: bytes) -> list[bytes]:
    groups = _groups(data)
    start, end = _vtodo_span(groups)
    return [_unfolded(g) for g in groups[start : end + 1]]


def test_complete_writes_one_utc_moment_and_no_sequence() -> None:
    after = _apply(SPIKE, CASES["complete"]["set"])
    lines = _vtodo_lines(after)
    for name in ("COMPLETED", "LAST-MODIFIED", "DTSTAMP"):
        assert f"{name}:20261113T120000Z".encode() in lines
    assert lines.count(b"SEQUENCE:2") == 1
    assert not any(line.startswith(b"SEQUENCE") and line != b"SEQUENCE:2" for line in lines)
    plain = _apply((FIXTURES / "all_day.ics").read_bytes(), CASES["complete"]["set"])
    assert b"SEQUENCE" not in plain


def test_missing_maintenance_fields_are_inserted_before_the_alarm() -> None:
    after = _apply(WITHOUT_MAINTENANCE, CASES["complete"]["set"])
    lines = _vtodo_lines(after)
    alarm = lines.index(b"BEGIN:VALARM")
    for name in ("LAST-MODIFIED", "DTSTAMP", "STATUS", "PERCENT-COMPLETE", "COMPLETED"):
        index = next(i for i, line in enumerate(lines) if line.startswith(name.encode() + b":"))
        assert index < alarm, name


def test_insertion_goes_before_an_unknown_component() -> None:
    after = _apply(UNKNOWN_COMPONENT, {"PRIORITY": 3})
    lines = _vtodo_lines(after)
    assert lines.index(b"PRIORITY:3") < lines.index(b"BEGIN:X-THING")


def test_insertion_without_subcomponent_goes_before_end_vtodo() -> None:
    after = _apply((FIXTURES / "all_day.ics").read_bytes(), {"PRIORITY": 3})
    lines = _vtodo_lines(after)
    assert lines[-2:] == [b"PRIORITY:3", b"END:VTODO"]


def test_replacement_stays_at_the_place_of_the_first_line() -> None:
    after = _apply(TWO_CATEGORIES, {"CATEGORIES": ["neu"]})
    lines = _vtodo_lines(after)
    assert lines.index(b"CATEGORIES:neu") < lines.index(b"X-BETWEEN:zwischen den Tags")
    assert sum(line.startswith(b"CATEGORIES") for line in lines) == 1


def test_nested_lines_are_never_hit() -> None:
    after = _apply(UNKNOWN_COMPONENT, {"SUMMARY": "neu", "DUE": date(2026, 12, 1)}, ["DESCRIPTION"])
    assert b"SUMMARY:innen bleibt\r\n" in after
    assert b"DESCRIPTION:innen bleibt auch\r\n" in after
    assert b"DUE:20261120T090000Z\r\n" in after
    spike = _apply(SPIKE, {}, ["DESCRIPTION", "DTSTART"])
    assert b"DESCRIPTION:spike30 Erinnerung\r\n" in spike
    assert b"DTSTART:19700329T020000\r\n" in spike
    assert b"RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\r\n" in spike


def test_lower_case_names_are_recognised() -> None:
    after = _apply(LOWER_CASE, {"SUMMARY": "neu"}, ["DUE", "PRIORITY", "CATEGORIES"])
    lines = [line.upper() for line in _vtodo_lines(after)]
    assert sum(line.startswith(b"SUMMARY") for line in lines) == 1
    assert not any(line.startswith((b"DUE", b"PRIORITY", b"CATEGORIES")) for line in lines)
    assert b"x-lower:bleibt\r\n" in after


def test_lf_object_stays_lf_also_for_new_lines() -> None:
    after = _apply(SPIKE_LF, {"SUMMARY": LONG_TEXT, "STATUS": "COMPLETED"})
    assert b"\r" not in after
    crlf = _apply(SPIKE, {"SUMMARY": LONG_TEXT, "STATUS": "COMPLETED"})
    assert crlf.count(b"\n") == crlf.count(b"\r\n")


def test_summary_and_description_keep_language_but_lose_altrep() -> None:
    after = _apply(HTML_DESCRIPTION, {"SUMMARY": "neu", "DESCRIPTION": "neu"})
    lines = _vtodo_lines(after)
    summary = next(line for line in lines if line.startswith(b"SUMMARY"))
    description = next(line for line in lines if line.startswith(b"DESCRIPTION"))
    assert b"LANGUAGE=de" in summary
    assert b"LANGUAGE=de" in description
    assert b"X-KEEP=yes" in description
    assert b"ALTREP" not in description
    assert b"X-ALT-DESC;FMTTYPE=text/html:<p>Text</p>" in lines
    spike = _apply(SPIKE, {"SUMMARY": "neu"})
    assert b"SUMMARY;X-SPIKE30-PARAM=abc:neu\r\n" in spike


def test_html_version_can_be_dropped_with_the_description() -> None:
    after = _apply(HTML_DESCRIPTION, {"DESCRIPTION": "neu"}, ["X-ALT-DESC"])
    assert b"X-ALT-DESC" not in after
    assert "X-ALT-DESC" not in _todo(after)


def test_description_is_cleared_to_an_empty_line_as_the_app_does() -> None:
    after = _apply(SPIKE, {}, ["DESCRIPTION"])
    lines = _vtodo_lines(after)
    assert lines.count(EMPTY_DESCRIPTION_LINE) == 1
    absent = _apply((FIXTURES / "all_day.ics").read_bytes(), {}, ["DESCRIPTION"])
    assert absent == (FIXTURES / "all_day.ics").read_bytes()


def test_parent_is_replaced_and_dropped_but_other_relations_stay() -> None:
    after = _apply(RELATIONS, {"PARENT": "new-parent"})
    todo = _todo(after)
    assert _parent_uids(todo) == ["new-parent"]
    assert b"RELATED-TO;RELTYPE=SIBLING:sibling-uid\r\n" in after
    assert b"RELATED-TO;RELTYPE=CHILD:child-uid\r\n" in after
    dropped = _apply(RELATIONS, {}, ["PARENT"])
    assert _parent_uids(_todo(dropped)) == []
    assert b"RELATED-TO;RELTYPE=SIBLING:sibling-uid\r\n" in dropped
    added = _apply((FIXTURES / "all_day.ics").read_bytes(), {"PARENT": "p-uid"})
    assert b"RELATED-TO:p-uid\r\n" in added


def test_dates_and_times_are_written_as_the_tasks_app_writes_them() -> None:
    after = _apply(
        SPIKE, {"DUE": date(2026, 11, 22), "DTSTART": datetime(2026, 11, 18, 7, tzinfo=UTC)}
    )
    lines = _vtodo_lines(after)
    assert b"DUE;VALUE=DATE:20261122" in lines
    assert b"DTSTART:20261118T070000Z" in lines
    utc_zone = _apply(SPIKE, {"DUE": datetime(2026, 11, 18, 7, tzinfo=ZoneInfo("UTC"))})
    assert b"DUE:20261118T070000Z\r\n" in utc_zone


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 11, 18, 7),
        datetime(2026, 11, 18, 7, tzinfo=ZoneInfo("Europe/Berlin")),
        datetime(2026, 1, 18, 7, tzinfo=ZoneInfo("Europe/London")),
    ],
    ids=["naive", "berlin", "london-winter"],
)
def test_a_time_not_in_utc_is_refused(value: datetime) -> None:
    from mcp_connector.tools import ics_edit

    with pytest.raises(ics_edit.EditRefused):
        ics_edit.apply(SPIKE.decode(), set_fields={"DUE": value}, drop_fields=())


def test_text_is_escaped_and_folded_by_icalendar() -> None:
    after = _apply(SPIKE, {"SUMMARY": LONG_TEXT})
    assert str(_todo(after)["SUMMARY"]) == LONG_TEXT
    groups = [g for g in _groups(after) if _name(g) == "SUMMARY"]
    assert len(groups) == 1
    assert b"\r\n " in groups[0]
    assert all(len(line) <= 77 for line in groups[0].split(b"\r\n"))
    assert b"\\," in groups[0]
    assert b"\\;" in groups[0]
    assert b"\\n" in groups[0]


def test_smuggled_component_lines_stay_a_value() -> None:
    from mcp_connector.tools import ics_edit

    evil = "x\r\nEND:VTODO\r\nBEGIN:VTODO\r\nUID:evil\nEND:VCALENDAR"
    before = SPIKE.decode()
    after = ics_edit.apply(before, set_fields={"SUMMARY": evil}, drop_fields=())
    ics_edit.verify(before, after, {"SUMMARY": evil})
    todo = _todo(after.encode())
    assert str(todo["UID"]) == "spike-probe-uid"
    assert str(todo["SUMMARY"]) == evil
    assert len(IcsCalendar.from_ical(after).walk("VTODO")) == 1


def test_unknown_or_conflicting_field_names_are_refused() -> None:
    from mcp_connector.tools import ics_edit

    for set_fields, drop in (
        ({"UID": "other"}, ()),
        ({"BEGIN": "VTODO"}, ()),
        ({}, ("UID",)),
        ({"SUMMARY": "a"}, ("SUMMARY",)),
        ({"SUMMARY": ""}, ()),
        ({"PRIORITY": True}, ()),
        ({"CATEGORIES": []}, ()),
        ({"DUE": "20261120"}, ()),
    ):
        with pytest.raises(ics_edit.EditRefused):
            ics_edit.apply(SPIKE.decode(), set_fields=set_fields, drop_fields=drop)


# --- inspect ------------------------------------------------------------------------------


def test_inspect_reports_uid_line_end_fields_and_recurrence() -> None:
    from mcp_connector.tools import ics_edit

    facts = ics_edit.inspect(SPIKE.decode())
    assert facts.uid == "spike-probe-uid"
    assert facts.line_end == "\r\n"
    assert facts.recurring is False
    assert {"SUMMARY", "DESCRIPTION", "X-SPIKE30-FOO", "CATEGORIES"} <= facts.fields
    assert "TRIGGER" not in facts.fields
    assert ics_edit.inspect(SPIKE_LF.decode()).line_end == "\n"
    assert ics_edit.inspect(LOWER_CASE.decode()).uid == "lower-case"
    assert ics_edit.inspect((FIXTURES / "recurring.ics").read_text("utf-8")).recurring is True


@pytest.mark.parametrize(
    "line", ["RRULE:FREQ=DAILY", "RDATE:20261121T090000Z", "RECURRENCE-ID:20261121T090000Z"]
)
def test_inspect_flags_recurrence_and_apply_refuses_it(line: str) -> None:
    from mcp_connector.tools import ics_edit

    text = SPIKE.decode().replace("X-SPIKE30-FOO:bar", f"X-SPIKE30-FOO:bar\r\n{line}")
    assert ics_edit.inspect(text).recurring is True
    with pytest.raises(ics_edit.EditRefused):
        ics_edit.apply(text, set_fields={"STATUS": "COMPLETED"}, drop_fields=())


def test_apply_refuses_the_recurring_fixture_of_the_tasks_app() -> None:
    from mcp_connector.tools import ics_edit

    with pytest.raises(ics_edit.EditRefused):
        ics_edit.apply(
            (FIXTURES / "recurring.ics").read_text("utf-8"),
            set_fields=CASES["complete"]["set"],
            drop_fields=(),
        )


def _second_vtodo() -> str:
    return SPIKE.decode().replace(
        "END:VTODO\r\n", "END:VTODO\r\nBEGIN:VTODO\r\nUID:second\r\nEND:VTODO\r\n"
    )


@pytest.mark.parametrize(
    "text",
    [
        "not a calendar",
        "",
        SPIKE.decode().replace("DUE;TZID=Europe/Berlin:20261120T101500", "DUE:notadate"),
        _second_vtodo(),
        SPIKE.decode().replace("PRIORITY:1", "PRIORITY:1\r\nSUMMARY:zweiter Titel"),
        SPIKE.decode().replace("PRIORITY:1", "PRIORITY:1\r\nPRIORITY:2"),
        SPIKE.decode().replace("PRIORITY:1", "PRIORITY:1\r\nstatus:COMPLETED\r\nSTATUS:X"),
        SPIKE.decode()
        .replace("BEGIN:VTODO", "BEGIN:VEVENT", 1)
        .replace("END:VTODO", "END:VEVENT", 1),
        SPIKE.decode().replace("END:VALARM\r\n", ""),
    ],
    ids=[
        "garbage",
        "empty",
        "bad-value",
        "two-vtodo",
        "two-summary",
        "two-priority",
        "two-status-mixed-case",
        "no-vtodo",
        "unbalanced",
    ],
)
def test_inspect_and_apply_refuse_what_they_cannot_edit_safely(text: str) -> None:
    from mcp_connector.tools import ics_edit

    with pytest.raises(ics_edit.EditRefused) as refused:
        ics_edit.inspect(text)
    assert str(refused.value).isascii()
    assert str(refused.value)
    with pytest.raises(ics_edit.EditRefused):
        ics_edit.apply(text, set_fields={"PRIORITY": 2}, drop_fields=())


# --- verify -------------------------------------------------------------------------------


def test_verify_refuses_a_result_that_does_not_hold() -> None:
    from mcp_connector.tools import ics_edit

    before = SPIKE.decode()
    good = ics_edit.apply(before, set_fields={"PRIORITY": 7}, drop_fields=("DUE",))
    ics_edit.verify(before, good, {"PRIORITY": 7, "DUE": None})
    for after, expected in (
        ("broken", {"PRIORITY": 7}),
        (good.replace("UID:spike-probe-uid", "UID:other"), {"PRIORITY": 7}),
        (good.replace("END:VTODO\r\n", "END:VTODO\r\nBEGIN:VTODO\r\nUID:x\r\nEND:VTODO\r\n"), {}),
        (good, {"PRIORITY": 8}),
        (good, {"DUE": date(2026, 11, 20)}),
        (good, {"SUMMARY": None}),
        (good, {"CATEGORIES": ["spike30"]}),
        (good, {"PARENT": "nobody"}),
    ):
        with pytest.raises(ics_edit.EditRefused):
            ics_edit.verify(before, after, expected)


# --- Alignment with the Tasks app -----------------------------------------------------------

# State a of completed.ics and reopened.ics, the objects the app wrote before round B of the
# browser session of phase 30: .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/ui-a/
# 4BFE626B-9A78-493B-9A99-78CC0FFC7D38.ics and 2D4850EC-8E4C-4BDF-A1E5-58559950667D.ics,
# copied line for line (the app writes CRLF).
COMPLETED_STATE_A = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Nextcloud Tasks v0.18.1",
        "BEGIN:VTODO",
        "UID:ab52abca-f7b2-43a7-bdbe-42bd1965e8aa",
        "CREATED:20261111T125045Z",
        "LAST-MODIFIED:20261111T125045Z",
        "DTSTAMP:20261111T125045Z",
        "SUMMARY:s30 abhaken",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)
REOPENED_STATE_A = _crlf(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Nextcloud Tasks v0.18.1",
        "BEGIN:VTODO",
        "UID:ba6d1850-cbd4-4c61-b504-5f03aad83885",
        "CREATED:20261111T125046Z",
        "LAST-MODIFIED:20261111T125046Z",
        "DTSTAMP:20261111T125046Z",
        "SUMMARY:s30 wieder-oeffnen",
        "END:VTODO",
        "END:VCALENDAR",
    ]
)


def _at(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def _complete(at: datetime) -> dict[str, Value]:
    return {"STATUS": "COMPLETED", "PERCENT-COMPLETE": 100, "COMPLETED": at, **_stamps(at)}


def _stamps(at: datetime) -> dict[str, Value]:
    return {"LAST-MODIFIED": at, "DTSTAMP": at}


def line_diff(before: bytes, after: bytes) -> set[str]:
    """Names of the logical lines that differ, the measure of plan 33-01."""
    old = Counter(_unfolded(g) for g in _groups(before))
    new = Counter(_unfolded(g) for g in _groups(after))
    return {_name(line) for line in ((old - new) + (new - old)).elements()}


def _app(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


APP_PAIRS = [
    pytest.param(
        COMPLETED_STATE_A, "completed.ics", _complete(_at("20261111T125947Z")), (), id="complete"
    ),
    pytest.param(
        _app("cancelled.ics"),
        "cancelled_completed.ics",
        _complete(_at("20261113T203854Z")),
        (),
        id="cancelled-complete",
    ),
    pytest.param(
        _app("cleared_due.ics"),
        "cleared_start.ics",
        _stamps(_at("20261113T203538Z")),
        ("DTSTART",),
        id="clear-start",
    ),
    pytest.param(
        _app("cleared_start.ics"),
        "cleared_description.ics",
        _stamps(_at("20261113T203608Z")),
        ("DESCRIPTION",),
        id="clear-description",
    ),
    pytest.param(
        _app("cleared_description.ics"),
        "cleared_priority.ics",
        _stamps(_at("20261113T203630Z")),
        ("PRIORITY",),
        id="clear-priority",
    ),
    pytest.param(
        _app("cleared_priority.ics"),
        "cleared_tags.ics",
        _stamps(_at("20261113T203652Z")),
        ("CATEGORIES",),
        id="clear-tags",
    ),
]


@pytest.mark.parametrize(("before", "app_file", "set_fields", "drop"), APP_PAIRS)
def test_editor_writes_what_the_tasks_app_wrote(
    before: bytes, app_file: str, set_fields: dict[str, Value], drop: tuple[str, ...]
) -> None:
    app = _app(app_file)
    ours = _apply(before, set_fields, drop)
    assert line_diff(before, ours) == line_diff(before, app)
    assert _entries(ours) == _entries(app)


def test_editor_reopens_as_the_tasks_app_did() -> None:
    completed = _apply(REOPENED_STATE_A, _complete(_at("20261111T130000Z")))
    reopened = _apply(
        completed,
        {"STATUS": "NEEDS-ACTION", **_stamps(_at("20261111T130111Z"))},
        ("COMPLETED", "PERCENT-COMPLETE"),
    )
    app = _app("reopened.ics")
    assert line_diff(REOPENED_STATE_A, reopened) == line_diff(REOPENED_STATE_A, app)
    assert _entries(reopened) == _entries(app)


# --- Source rules ---------------------------------------------------------------------------


def test_editor_source_leaves_values_to_icalendar() -> None:
    source = EDITOR_SOURCE.read_text(encoding="utf-8")
    assert "sorted=False" in source
    assert "foldline" not in source
    assert "tools.tasks" not in source
    assert "from . import tasks" not in source

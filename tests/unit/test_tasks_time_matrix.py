"""The time matrix of the tasks bundle (TASK-04) and the VTODO reader around it.

Every row of the matrix is a named test, once per field (``DUE`` as ``due``, ``DTSTART`` as
``start``, ``COMPLETED`` as ``completed``):

* all day: ``VALUE=DATE`` stays a date, without midnight and without the next day
* zoned: ``TZID`` keeps its zone and its offset
* UTC: a ``Z`` time stays UTC
* floating: a time without zone stays floating and carries ``<field>_floating``, never
  ``+00:00``
* without a date: the field and its flag are absent

The Tasks app writes neither ``TZID`` nor floating times nor several ``CATEGORIES`` or
``RELATED-TO`` lines, so those objects are built by hand here (pitfall 11); the objects the
app does write are the fixtures under ``tests/fixtures/tasks_app``.
"""

from pathlib import Path

import pytest

from mcp_connector.tools import tasks as tasks_tools

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tasks_app"

VTIMEZONE_BERLIN = (
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Berlin",
    "BEGIN:STANDARD",
    "DTSTART:19701025T030000",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "BEGIN:DAYLIGHT",
    "DTSTART:19700329T020000",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "END:VTIMEZONE",
)


def todo_ics(*lines: str, timezone: bool = False, extra: tuple[str, ...] = ()) -> bytes:
    """One VCALENDAR with one VTODO, CRLF like the server."""
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//test//EN",
        *(VTIMEZONE_BERLIN if timezone else ()),
        "BEGIN:VTODO",
        "UID:matrix-1",
        "DTSTAMP:20261111T120000Z",
        "SUMMARY:matrix",
        *lines,
        "END:VTODO",
        *extra,
        "END:VCALENDAR",
    ]
    return ("\r\n".join(body) + "\r\n").encode("utf-8")


def read(*lines: str, timezone: bool = False) -> dict:
    todo = tasks_tools._read_todo(todo_ics(*lines, timezone=timezone))
    assert todo is not None
    return todo


# --- DUE --------------------------------------------------------------------------------


def test_matrix_due_all_day_stays_a_date() -> None:
    todo = read("DUE;VALUE=DATE:20261120")
    assert todo["due"] == "2026-11-20"
    assert "T" not in todo["due"]
    assert "due_floating" not in todo


def test_matrix_due_zoned_keeps_its_zone() -> None:
    todo = read("DUE;TZID=Europe/Berlin:20261120T090000", timezone=True)
    assert todo["due"] == "2026-11-20T09:00:00+01:00"
    assert "due_floating" not in todo


def test_matrix_due_utc_stays_utc() -> None:
    todo = read("DUE:20261120T090000Z")
    assert todo["due"] == "2026-11-20T09:00:00+00:00"
    assert "due_floating" not in todo


def test_matrix_floating_stays_floating_and_is_flagged() -> None:
    todo = read("DUE:20261120T090000")
    assert todo["due"] == "2026-11-20T09:00:00"
    assert todo["due_floating"] is True
    assert "+00:00" not in todo["due"]
    assert not todo["due"].endswith("Z")


def test_matrix_without_a_date_has_no_field() -> None:
    todo = read()
    assert "due" not in todo
    assert "due_floating" not in todo


# --- DTSTART ----------------------------------------------------------------------------


def test_matrix_start_all_day_stays_a_date() -> None:
    todo = read("DTSTART;VALUE=DATE:20261118")
    assert todo["start"] == "2026-11-18"
    assert "start_floating" not in todo


def test_matrix_start_zoned_keeps_its_zone() -> None:
    todo = read("DTSTART;TZID=Europe/Berlin:20260715T080000", timezone=True)
    assert todo["start"] == "2026-07-15T08:00:00+02:00"
    assert "start_floating" not in todo


def test_matrix_start_utc_stays_utc() -> None:
    todo = read("DTSTART:20261118T070000Z")
    assert todo["start"] == "2026-11-18T07:00:00+00:00"
    assert "start_floating" not in todo


def test_matrix_start_floating_stays_floating_and_is_flagged() -> None:
    todo = read("DTSTART:20261118T070000")
    assert todo["start"] == "2026-11-18T07:00:00"
    assert todo["start_floating"] is True


def test_matrix_start_without_a_date_has_no_field() -> None:
    todo = read("DUE:20261120T090000Z")
    assert "start" not in todo
    assert "start_floating" not in todo


# --- COMPLETED --------------------------------------------------------------------------


def test_matrix_completed_all_day_stays_a_date() -> None:
    todo = read("COMPLETED;VALUE=DATE:20261112")
    assert todo["completed"] == "2026-11-12"
    assert "completed_floating" not in todo


def test_matrix_completed_zoned_keeps_its_zone() -> None:
    todo = read("COMPLETED;TZID=Europe/Berlin:20261112T173000", timezone=True)
    assert todo["completed"] == "2026-11-12T17:30:00+01:00"
    assert "completed_floating" not in todo


def test_matrix_completed_utc_stays_utc() -> None:
    """The form the Tasks app writes (assumption A3)."""
    todo = read("COMPLETED:20261112T163000Z")
    assert todo["completed"] == "2026-11-12T16:30:00+00:00"
    assert "completed_floating" not in todo


def test_matrix_completed_floating_stays_floating_and_is_flagged() -> None:
    todo = read("COMPLETED:20261112T163000")
    assert todo["completed"] == "2026-11-12T16:30:00"
    assert todo["completed_floating"] is True


def test_matrix_completed_without_a_date_has_no_field() -> None:
    todo = read()
    assert "completed" not in todo
    assert "completed_floating" not in todo


# --- The reader around the matrix ---------------------------------------------------------


def test_time_field_never_moves_a_floating_time() -> None:
    from datetime import date, datetime

    assert tasks_tools._time_field(date(2026, 11, 20)) == ("2026-11-20", False)
    assert tasks_tools._time_field(datetime(2026, 11, 20, 9, 0)) == ("2026-11-20T09:00:00", True)


@pytest.mark.parametrize(
    ("lines", "status"),
    [
        ((), "open"),
        (("STATUS:NEEDS-ACTION",), "open"),
        (("STATUS:IN-PROCESS",), "in_progress"),
        (("STATUS:COMPLETED",), "completed"),
        (("COMPLETED:20261112T163000Z",), "completed"),
        (("STATUS:CANCELLED",), "cancelled"),
        (("STATUS:CANCELLED", "COMPLETED:20261112T163000Z"), "cancelled"),
        (("STATUS:IN-PROCESS", "COMPLETED:20261112T163000Z"), "completed"),
    ],
)
def test_status_rule_cancelled_wins_then_completed(lines: tuple[str, ...], status: str) -> None:
    assert read(*lines)["status"] == status


def test_several_categories_lines_and_a_comma_list_become_one_flat_list() -> None:
    todo = read("CATEGORIES:arbeit,privat", "CATEGORIES:privat", "CATEGORIES:dringend")
    assert todo["tags"] == ["arbeit", "privat", "dringend"]


def test_one_categories_line_is_a_list_as_well() -> None:
    assert read("CATEGORIES:solo")["tags"] == ["solo"]


def test_no_categories_means_no_tags_field() -> None:
    assert "tags" not in read()


def test_related_to_as_one_value_and_as_several_lines() -> None:
    single = read("RELATED-TO:parent-a")
    assert single["parents"] == ["parent-a"]
    several = read(
        "RELATED-TO;RELTYPE=SIBLING:sib", "RELATED-TO:parent-b", "RELATED-TO;RELTYPE=CHILD:c"
    )
    assert several["parents"] == ["parent-b"]
    explicit = read("RELATED-TO;RELTYPE=PARENT:parent-c")
    assert explicit["parents"] == ["parent-c"]


def test_rrule_or_rdate_marks_the_master_as_recurring() -> None:
    assert read("DUE:20261120T090000Z", "RRULE:FREQ=DAILY")["recurring"] is True
    assert read("DUE:20261120T090000Z", "RDATE:20261121T090000Z")["recurring"] is True
    assert "recurring" not in read("DUE:20261120T090000Z")


def test_an_override_with_recurrence_id_is_not_read_as_a_task_of_its_own() -> None:
    override = (
        "BEGIN:VTODO",
        "UID:matrix-1",
        "DTSTAMP:20261111T120000Z",
        "RECURRENCE-ID:20261121T090000Z",
        "SUMMARY:override",
        "END:VTODO",
    )
    ics = todo_ics("DUE:20261120T090000Z", "RRULE:FREQ=DAILY", extra=override)
    todo = tasks_tools._read_todo(ics)
    assert todo is not None
    assert todo["summary"] == "matrix"
    only_override = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:x\r\nBEGIN:VTODO\r\nUID:o\r\n"
        b"RECURRENCE-ID:20261121T090000Z\r\nSUMMARY:o\r\nEND:VTODO\r\nEND:VCALENDAR\r\n"
    )
    assert tasks_tools._read_todo(only_override) is None


def test_attach_appears_in_no_field() -> None:
    big = "A" * 200_000
    todo = read(
        "DESCRIPTION:plain",
        f"ATTACH;ENCODING=BASE64;VALUE=BINARY;FMTTYPE=image/png:{big}",
        "ATTACH:https://attacker.example/leak.png",
    )
    flat = repr(todo)
    assert big[:64] not in flat
    assert "attacker.example" not in flat
    assert "attach" not in {key.casefold() for key in todo}


def test_priority_one_to_nine_and_absent_otherwise() -> None:
    assert read("PRIORITY:1")["priority"] == 1
    assert read("PRIORITY:9")["priority"] == 9
    assert "priority" not in read("PRIORITY:0")
    assert "priority" not in read()


def test_uid_and_description_are_read_for_internal_use() -> None:
    todo = read("DESCRIPTION:line one\\nline two")
    assert todo["uid"] == "matrix-1"
    assert todo["description"] == "line one\nline two"


def test_forged_marker_is_removed_from_summary_and_tags() -> None:
    from mcp_connector.tools import marks

    todo = read(
        f"SUMMARY:before {marks.FINAL_TRUNCATION} after",
        f"CATEGORIES:{marks.EXCERPT_TRUNCATION}x",
    )
    assert marks.FINAL_TRUNCATION not in todo["summary"]
    assert all(marks.EXCERPT_TRUNCATION not in tag for tag in todo["tags"])


@pytest.mark.parametrize(
    "raw",
    [
        b"garbage",
        b"",
        (
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:x\r\nBEGIN:VEVENT\r\nUID:e\r\n"
            b"DTSTART:20261120T090000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        ),
        b"\xff\xfe not utf-8",
    ],
)
def test_invalid_icalendar_or_no_vtodo_is_none_and_never_raises(raw: bytes) -> None:
    assert tasks_tools._read_todo(raw) is None


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.ics")), ids=lambda path: path.name)
def test_every_fixture_of_the_tasks_app_is_read(path: Path) -> None:
    todo = tasks_tools._read_todo(path.read_bytes())
    assert todo is not None
    assert todo["summary"].startswith("s30 ")
    assert todo["status"] in {"open", "in_progress", "completed", "cancelled"}


def test_fixture_forms_of_the_tasks_app() -> None:
    def load(name: str) -> dict:
        todo = tasks_tools._read_todo((FIXTURES / name).read_bytes())
        assert todo is not None
        return todo

    assert load("all_day.ics")["due"].count("T") == 0
    assert load("with_time.ics")["due"].endswith("+00:00")
    assert load("recurring.ics")["recurring"] is True
    assert load("tags.ics")["tags"] == ["spike30", "wichtig"]
    assert load("tags.ics")["priority"] == 1
    assert load("completed.ics")["status"] == "completed"
    assert load("subtask.ics")["parents"] == [load("subtask_parent.ics")["uid"]]

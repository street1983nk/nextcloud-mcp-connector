"""Unit tests for ``update_task`` (``tasks_update``, plan 33-07), every path without a network.

Pinned here: every refusal before the first request (id, Deck key, ETag form, an empty
summary, a priority outside 0 to 9, a time without offset or Z, a malformed date, a start
after the due date within the new values, a parent in another list or the task itself, no
field named at all) and every refusal after the GET but before any PUT (unknown, read only,
stale ETag, recurring, several VTODO, a new due date against the stored start and the
other way round, a floating or zoned stored value next to a new UTC time, a DURATION, a
parent that is unknown in the list, the task itself or one of its descendants); no PUT
without a difference (D-33-15); one PUT with ``If-Match`` per change, and the round trip at
tool level over every fixture of the Tasks app and the hand objects of plan 33-04: the
stored text differs in exactly the named field plus LAST-MODIFIED and DTSTAMP (ENTSCHEID
pflegefelder_entfernen), every untouched line stays byte for byte; the cleared form equals
what the Tasks app wrote (ENTSCHEID entfernen_*); D-33-13 as the one named exception; times
in UTC with Z and dates as VALUE=DATE; and the answer, which never carries a URI or an owner.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
import respx
import task_store
from icalendar import Calendar as IcsCalendar
from test_ics_edit import (
    HTML_DESCRIPTION,
    LONG_TEXT,
    OBJECTS,
    byte_proof,
    line_diff,
    semantic_proof,
)
from test_tasks_complete import (
    LEAKS,
    OWN,
    SHARED_RO,
    SHARED_RW,
    mount,
    tid,
    vtodo,
)

from mcp_connector import ids
from mcp_connector.errors import (
    REASON_GUARD_TRIPPED,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import tasks as tasks_tools

ROOT = tid(OWN, "root.ics")
STAMPS = {"LAST-MODIFIED", "DTSTAMP"}


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(task_store.BASE, task_store.USER, "app-password-test"),
    )


def store_with(*objects: tuple[str, str | bytes], uri: str = OWN) -> task_store.TaskStore:
    store = task_store.TaskStore(uri)
    for name, text in objects:
        store.add(name, text)
    return store


async def call(
    clients: NcClients,
    store: task_store.TaskStore,
    *,
    task_id: str = ROOT,
    etag: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    name = ids.parse(task_id)[1][1]
    used = etag if etag is not None else store.etag(name)
    return await tasks_tools.update_task(clients, task_id=task_id, etag=used, **fields)


def puts(store: task_store.TaskStore) -> list[str]:
    return [name for method, name, _match in store.writes if method == "PUT"]


def todo_of(text: str | bytes) -> Any:
    (todo,) = IcsCalendar.from_ical(text).walk("VTODO")
    return todo


def crlf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


# --- refusals before any request -----------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"task_id": "note:12"},
        {"task_id": "garbage"},
        {"etag": ""},
        {"etag": "*"},
        {"etag": 'W/"abc"'},
        {"etag": '"a", "b"'},
        {"summary": ""},
        {"summary": "   "},
        {"priority": 10},
        {"priority": -1},
        {"priority": True},
        {"due": "2026-11-20T09:00:00"},
        {"start": "2026-11-20T09:00"},
        {"due": "2026-13-01"},
        {"due": "20.11.2026"},
        {"due": "2026-11-20T09:00:00.500+01:00"},
        {"due": "2026-11-20", "start": "2026-11-21"},
        {"due": "2026-11-20T09:00:00Z", "start": "2026-11-20T09:00:00Z"},
        {"due": "2026-11-20", "start": "2026-11-19T09:00:00Z"},
        {"parent": "note:1"},
        {"parent": tid(SHARED_RW, "p.ics")},
        {"parent": ROOT},
        {"tags": "eins"},
        {},
    ],
    ids=[
        "not-a-task",
        "no-id",
        "etag-empty",
        "etag-star",
        "etag-weak",
        "etag-list",
        "summary-empty",
        "summary-blank",
        "priority-10",
        "priority-negative",
        "priority-bool",
        "due-without-offset",
        "start-without-offset",
        "due-bad-date",
        "due-german-date",
        "due-fraction",
        "start-after-due-dates",
        "start-equal-due-times",
        "date-and-time",
        "parent-not-a-task",
        "parent-other-list",
        "parent-itself",
        "tags-not-a-list",
        "no-field",
    ],
)
@pytest.mark.anyio
async def test_bad_input_is_refused_before_any_request(
    clients: NcClients,
    kwargs: dict[str, Any],
) -> None:
    arguments: dict[str, Any] = {"task_id": ROOT, "etag": '"e-1"'}
    if kwargs and set(kwargs) <= {"task_id", "etag"}:
        # A field is named, so only the id or the ETag can be what is refused.
        arguments["summary"] = "Neu"
    arguments.update(kwargs)
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ToolError):
            await tasks_tools.update_task(clients, **arguments)
        assert mock.calls.call_count == 0


@pytest.mark.anyio
async def test_the_refusals_name_the_way_out(clients: NcClients) -> None:
    cases = {
        "summary": ({"summary": ""}, "summary"),
        "time": ({"due": "2026-11-20T09:00:00"}, "zone"),
        "nothing": ({}, "summary, description, due, start, priority, tags or parent"),
        "list": ({"parent": tid(SHARED_RW, "p.ics")}, "another list"),
    }
    with respx.mock(assert_all_called=False) as mock:
        for kwargs, needle in cases.values():
            with pytest.raises(ToolError) as caught:
                await tasks_tools.update_task(clients, task_id=ROOT, etag='"e"', **kwargs)
            assert needle in f"{caught.value.message} {caught.value.hint}"
        assert mock.calls.call_count == 0


@pytest.mark.anyio
async def test_a_deck_key_is_an_unknown_task_before_any_request(
    clients: NcClients,
) -> None:
    deck_id = ids.encode_task("app-generated--deck--board-1", "card-1.ics")
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ToolError) as caught:
            await tasks_tools.update_task(clients, task_id=deck_id, etag='"e"', summary="x")
        assert mock.calls.call_count == 0
    assert caught.value.reason == REASON_UNKNOWN_ID


# --- refusals after the GET, before any PUT --------------------------------------------------


@pytest.mark.anyio
async def test_everything_unknown_gets_one_answer_and_no_write(
    clients: NcClients,
) -> None:
    store = store_with(("root.ics", vtodo("root")), ("broken.ics", "not ical"))
    cases = [tid("no-such-list", "root.ics"), tid(OWN, "missing.ics"), tid(OWN, "broken.ics")]
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        for task_id in cases:
            with pytest.raises(ToolError) as caught:
                await tasks_tools.update_task(clients, task_id=task_id, etag='"e"', summary="x")
            assert caught.value.reason == REASON_UNKNOWN_ID
            assert caught.value.message == tasks_tools._unknown_task(task_id).message
    assert store.writes == []


@pytest.mark.anyio
async def test_a_read_only_list_is_refused_without_a_put(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root")), uri=SHARED_RO)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, task_id=tid(SHARED_RO, "root.ics"), summary="x")
    assert store.writes == []
    assert "read only" in caught.value.message
    for leak in LEAKS:
        assert leak not in str(caught.value)


@pytest.mark.anyio
async def test_a_stale_etag_is_a_conflict_without_a_put(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ConflictError) as caught:
            await call(clients, store, etag='"an-old-etag"', summary="x")
    assert store.writes == []
    assert "read the task again with tasks_read" in str(caught.value)


@pytest.mark.anyio
async def test_a_412_of_the_server_is_a_conflict_after_one_put(
    clients: NcClients,
) -> None:
    store = store_with(("root.ics", vtodo("root")))
    store.fail["root.ics"] = 412
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ConflictError):
            await call(clients, store, summary="x")
    assert puts(store) == ["root.ics"]


@pytest.mark.parametrize(
    "text",
    [
        vtodo("root", "DTSTART:20261111T120000Z", "RRULE:FREQ=DAILY"),
        vtodo("root", "RDATE:20261120T120000Z"),
        vtodo("root").replace(
            "END:VCALENDAR",
            "BEGIN:VTODO\r\nUID:second\r\nSUMMARY:two\r\nEND:VTODO\r\nEND:VCALENDAR",
        ),
        vtodo("root", "SUMMARY:twice"),
    ],
    ids=["rrule", "rdate", "two-vtodo", "summary-twice"],
)
@pytest.mark.anyio
async def test_a_task_that_cannot_be_changed_safely_is_refused_without_a_put(
    clients: NcClients,
    text: str,
) -> None:
    store = store_with(("root.ics", text))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, summary="Neu")
    assert store.writes == []
    assert caught.value.reason == REASON_GUARD_TRIPPED


@pytest.mark.anyio
async def test_a_text_that_is_not_utf8_is_refused_without_a_put(
    clients: NcClients,
) -> None:
    blob = vtodo("root", "DESCRIPTION:PLACEHOLDER").encode().replace(b"PLACEHOLDER", b"K\xe4se")
    store = store_with(("root.ics", blob))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, summary="Neu")
    assert store.writes == []
    assert "UTF-8" in caught.value.message


@pytest.mark.parametrize(
    ("stored", "kwargs", "needle"),
    [
        (("DTSTART;VALUE=DATE:20261118",), {"due": "2026-11-20T09:00:00Z"}, "both"),
        (("DUE;VALUE=DATE:20261120",), {"start": "2026-11-18T09:00:00Z"}, "both"),
        (("DTSTART:20261121T090000Z",), {"due": "2026-11-20T09:00:00Z"}, "before"),
        (("DTSTART;VALUE=DATE:20261121",), {"due": "2026-11-20"}, "before"),
        (("DUE:20261120T090000Z",), {"start": "2026-11-20T10:00:00+01:00"}, "before"),
        (("DTSTART:20261118T090000",), {"due": "2026-11-20T09:00:00Z"}, "together"),
        (("DUE:20261120T090000",), {"start": "2026-11-18T09:00:00Z"}, "together"),
        (
            ("DTSTART;TZID=Europe/Berlin:20261118T090000",),
            {"due": "2026-11-20T09:00:00Z"},
            "together",
        ),
        (
            ("DTSTART:20261118T090000Z", "DURATION:PT1H"),
            {"due": "2026-11-20T09:00:00Z"},
            "DURATION",
        ),
        (("DTSTART:20261118T090000Z", "DURATION:PT1H"), {"start": ""}, "DURATION"),
        (
            ("DTSTART:20261118T090000Z", "DURATION:PT1H"),
            {"start": "2026-11-18T10:00:00Z"},
            "DURATION",
        ),
    ],
    ids=[
        "due-time-against-start-date",
        "start-time-against-due-date",
        "due-before-stored-start",
        "due-date-before-stored-start-date",
        "start-after-stored-due",
        "floating-start",
        "floating-due",
        "zoned-start",
        "duration-due",
        "duration-clear-start",
        "duration-start",
    ],
)
@pytest.mark.anyio
async def test_times_are_checked_on_the_merged_state_without_a_put(
    clients: NcClients,
    stored: tuple[str, ...],
    kwargs: dict[str, Any],
    needle: str,
) -> None:
    store = store_with(("root.ics", vtodo("root", *stored)))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, **kwargs)
    assert store.writes == []
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert needle in f"{caught.value.message} {caught.value.hint}"


@pytest.mark.parametrize(
    ("stored", "kwargs"),
    [
        (
            ("DTSTART:20261118T090000",),
            {"due": "2026-11-20T09:00:00Z", "start": "2026-11-18T09:00:00Z"},
        ),
        (
            ("DTSTART;TZID=Europe/Berlin:20261118T090000",),
            {"due": "2026-11-20", "start": "2026-11-18"},
        ),
        (("DTSTART:20261118T090000Z",), {"due": "2026-11-20T09:00:00+01:00"}),
        (("DTSTART:20261118T090000Z", "DURATION:PT1H"), {"summary": "nur der Titel"}),
        (("DTSTART:20261121T090000Z",), {"due": ""}),
    ],
    ids=[
        "floating-set-both",
        "zoned-set-both-dates",
        "utc-start",
        "duration-untouched",
        "clear-due",
    ],
)
@pytest.mark.anyio
async def test_the_way_out_of_each_time_refusal_is_written(
    clients: NcClients,
    stored: tuple[str, ...],
    kwargs: dict[str, Any],
) -> None:
    """Positive control of the refusals above: the hinted call goes through."""
    store = store_with(("root.ics", vtodo("root", *stored)))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, **kwargs)
    assert puts(store) == ["root.ics"]
    assert answer["changed"]


@pytest.mark.parametrize(
    ("objects", "parent", "needle"),
    [
        ((), tid(OWN, "missing.ics"), "does not know"),
        ((("k.ics", vtodo("k", "RELATED-TO:root")),), tid(OWN, "k.ics"), "subtask"),
        (
            (
                ("k.ics", vtodo("k", "RELATED-TO:root")),
                ("e.ics", vtodo("e", "RELATED-TO:k")),
            ),
            tid(OWN, "e.ics"),
            "subtask",
        ),
        ((("twin.ics", vtodo("root")),), tid(OWN, "twin.ics"), "own parent"),
    ],
    ids=["unknown", "child", "grandchild", "same-uid"],
)
@pytest.mark.anyio
async def test_a_parent_that_does_not_fit_is_refused_without_a_put(
    clients: NcClients,
    objects: tuple[tuple[str, str], ...],
    parent: str,
    needle: str,
) -> None:
    store = store_with(("root.ics", vtodo("root")), *objects)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, parent=parent)
    assert store.writes == []
    assert needle in caught.value.message
    assert store.reports == 1


@pytest.mark.anyio
async def test_a_parent_in_the_same_list_is_set_and_cleared(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root")), ("p.ics", vtodo("parent-uid")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, parent=tid(OWN, "p.ics"))
        assert "RELATED-TO:parent-uid\r\n" in store.text("root.ics")
        assert answer["changed"] == ["parent"]
        again = await call(clients, store, parent="")
    assert "RELATED-TO" not in store.text("root.ics")
    assert again["changed"] == ["parent"]
    assert again["removed"] == ["parent"]


# --- no difference, no PUT -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stored", "kwargs"),
    [
        ((), {"summary": "root"}),
        (("DESCRIPTION:Text",), {"description": "Text"}),
        (("CATEGORIES:eins,zwei",), {"tags": ["eins", "zwei"]}),
        (("CATEGORIES:eins", "CATEGORIES:zwei"), {"tags": ["eins", "zwei"]}),
        (("DUE:20261120T080000Z",), {"due": "2026-11-20T09:00:00+01:00"}),
        (("DUE;VALUE=DATE:20261120",), {"due": "2026-11-20"}),
        (("PRIORITY:3",), {"priority": 3}),
        ((), {"priority": 0}),
        ((), {"due": "", "start": "", "description": "", "tags": [], "parent": ""}),
        (("DESCRIPTION:",), {"description": ""}),
    ],
    ids=[
        "same-summary",
        "same-description",
        "same-tags",
        "same-tags-two-lines",
        "same-instant",
        "same-date",
        "same-priority",
        "no-priority",
        "all-absent",
        "description-already-empty",
    ],
)
@pytest.mark.anyio
async def test_without_a_difference_nothing_is_written(
    clients: NcClients,
    stored: tuple[str, ...],
    kwargs: dict[str, Any],
) -> None:
    store = store_with(("root.ics", vtodo("root", *stored)))
    before = store.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, **kwargs)
    assert store.writes == []
    assert store.snapshot() == before
    assert answer["changed"] == []
    assert answer["id"] == ROOT
    assert "etag" not in answer


@pytest.mark.parametrize(
    ("stored", "kwargs"),
    [
        (("CATEGORIES:zwei,eins",), {"tags": ["eins", "zwei"]}),
        (("DUE:20261120T090000Z",), {"due": "2026-11-20"}),
        (("DUE;VALUE=DATE:20261120",), {"due": "2026-11-20T00:00:00Z"}),
        (("DUE:20261120T090000",), {"due": "2026-11-20T09:00:00Z"}),
    ],
    ids=["tags-other-order", "time-to-date", "date-to-time", "floating-to-utc"],
)
@pytest.mark.anyio
async def test_another_order_or_value_type_is_a_difference(
    clients: NcClients,
    stored: tuple[str, ...],
    kwargs: dict[str, Any],
) -> None:
    store = store_with(("root.ics", vtodo("root", *stored)))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, **kwargs)
    assert puts(store) == ["root.ics"]
    assert answer["changed"] == list(kwargs)


# --- times -----------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_times_are_written_in_utc_and_dates_as_dates(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(
            clients, store, due="2026-11-20T09:00:00+01:00", start="2026-11-19T23:30:00-02:00"
        )
        text = store.text("root.ics")
        assert "DUE:20261120T080000Z\r\n" in text
        assert "DTSTART:20261120T013000Z\r\n" in text
        await call(clients, store, due="2026-11-22", start="2026-11-21")
        text = store.text("root.ics")
    assert "DUE;VALUE=DATE:20261122\r\n" in text
    assert "DTSTART;VALUE=DATE:20261121\r\n" in text
    todo = todo_of(text)
    # A due date is the day named, never an exclusive end on the day after.
    assert todo["DUE"].dt == date(2026, 11, 22)
    assert "TZID" not in text


@pytest.mark.anyio
async def test_line_ends_of_the_input_are_normalised(clients: NcClients) -> None:
    """33-04: a carriage return cannot survive RFC 5545 text, so it becomes a line feed
    before the edit instead of a refusal of the check after it."""
    store = store_with(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, summary="eins\r\nzwei\rdrei", description="a\r\nb")
    todo = todo_of(store.text("root.ics"))
    assert str(todo["SUMMARY"]) == "eins\nzwei\ndrei"
    assert str(todo["DESCRIPTION"]) == "a\nb"
    assert len(IcsCalendar.from_ical(store.text("root.ics")).walk("VTODO")) == 1


@pytest.mark.anyio
async def test_a_smuggled_component_stays_a_value(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, summary="x\nEND:VTODO\nBEGIN:VTODO\nUID:evil")
    todos = IcsCalendar.from_ical(store.text("root.ics")).walk("VTODO")
    assert len(todos) == 1
    assert str(todos[0]["UID"]) == "root"


# --- the answer --------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_answer_names_fields_and_the_etag_of_the_put(clients: NcClients) -> None:
    store = store_with(
        ("root.ics", vtodo("root", "DUE:20261120T090000Z", "PRIORITY:3")), uri=SHARED_RW
    )
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(
            clients,
            store,
            task_id=tid(SHARED_RW, "root.ics"),
            summary="Neu",
            due="",
            priority=0,
            tags=["a"],
        )
    assert answer["id"] == tid(SHARED_RW, "root.ics")
    assert answer["changed"] == ["summary", "due", "priority", "tags"]
    assert answer["removed"] == ["due", "priority"]
    assert answer["etag"] == store.etag("root.ics")
    assert answer["list"] == {"name": "Team", "shared": True, "writable": True}
    assert "html_description_removed" not in answer
    for leak in LEAKS:
        assert leak not in str(answer)


@pytest.mark.anyio
async def test_without_an_etag_header_the_answer_says_read_again(
    clients: NcClients,
) -> None:
    store = store_with(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        mock.route(method="PUT", url__startswith=task_store.list_url(OWN)).mock(
            return_value=httpx.Response(204)
        )
        answer = await call(clients, store, summary="Neu")
    assert "etag" not in answer
    assert answer["note"] == tasks_tools.NEW_ETAG_NOTE


# --- D-33-13: the HTML version of the description ---------------------------------------------


@pytest.mark.parametrize("description", ["Neuer Text", ""], ids=["set", "clear"])
@pytest.mark.anyio
async def test_a_changed_description_drops_the_html_version_and_says_so(
    clients: NcClients,
    description: str,
) -> None:
    store = store_with(("root.ics", HTML_DESCRIPTION))
    task_id = tid(OWN, "root.ics")
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, task_id=task_id, description=description)
    after = store.objects["root.ics"][0]
    assert b"X-ALT-DESC" not in after
    assert b"ALTREP" not in after
    assert answer["html_description_removed"] is True
    touched = {"DESCRIPTION", *STAMPS}
    # X-ALT-DESC is the one named exception of the round trip (D-33-13): without it the
    # semantic proof reports exactly that line, with it the proof is quiet.
    assert [entry[1] for entry in semantic_proof(HTML_DESCRIPTION, after, touched)] == [
        "X-ALT-DESC"
    ]
    assert semantic_proof(HTML_DESCRIPTION, after, touched | {"X-ALT-DESC"}) == []
    assert byte_proof(HTML_DESCRIPTION, after, touched | {"X-ALT-DESC"}) == []


@pytest.mark.anyio
async def test_another_field_keeps_the_html_version(clients: NcClients) -> None:
    store = store_with(("root.ics", HTML_DESCRIPTION))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, summary="Neu")
    after = store.objects["root.ics"][0]
    assert b"X-ALT-DESC;FMTTYPE=text/html:<p>Text</p>" in after
    assert b"ALTREP" in after
    assert "html_description_removed" not in answer


# --- the round trip at tool level over every fixture ------------------------------------------

PARENT_UID = "new-parent-uid"
FAR_DUE_TIME = datetime(2031, 3, 4, 5, 6, 7, tzinfo=UTC)
FAR_START_TIME = datetime(2021, 3, 4, 5, 6, 7, tzinfo=UTC)

#: case name -> (keyword arguments, the field of the answer, the iCalendar name)
CASES: dict[str, tuple[dict[str, Any], str, str]] = {
    "set_summary": ({"summary": LONG_TEXT}, "summary", "SUMMARY"),
    "set_description": ({"description": LONG_TEXT}, "description", "DESCRIPTION"),
    "set_due_time": ({"due": "2031-03-04T06:06:07+01:00"}, "due", "DUE"),
    "set_due_date": ({"due": "2031-03-04"}, "due", "DUE"),
    "set_start_time": ({"start": "2021-03-04T05:06:07Z"}, "start", "DTSTART"),
    "set_start_date": ({"start": "2021-03-04"}, "start", "DTSTART"),
    "set_priority": ({"priority": 7}, "priority", "PRIORITY"),
    "set_tags": ({"tags": ["neu", "mit,komma", "äöü"]}, "tags", "CATEGORIES"),
    "set_parent": ({"parent": tid(OWN, "zz-parent.ics")}, "parent", "PARENT"),
    "clear_due": ({"due": ""}, "due", "DUE"),
    "clear_start": ({"start": ""}, "start", "DTSTART"),
    "clear_description": ({"description": ""}, "description", "DESCRIPTION"),
    "clear_priority": ({"priority": 0}, "priority", "PRIORITY"),
    "clear_tags": ({"tags": []}, "tags", "CATEGORIES"),
    "clear_parent": ({"parent": ""}, "parent", "PARENT"),
}

#: The new value of every time case, to tell from the stored object whether it is refused.
NEW_TIMES: dict[str, date | datetime] = {
    "set_due_time": FAR_DUE_TIME,
    "set_due_date": date(2031, 3, 4),
    "set_start_time": FAR_START_TIME,
    "set_start_date": date(2021, 3, 4),
}

MATRIX = [pytest.param(obj, case, id=f"{obj}-{case}") for obj in sorted(OBJECTS) for case in CASES]


def _is_utc(value: date | datetime) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.tzname() == "UTC"


def _expected_refusal(todo: Any, case: str) -> bool:
    """Whether the merged state check refuses the case, read with icalendar alone."""
    if case not in NEW_TIMES and case not in ("clear_due", "clear_start"):
        return False
    if todo.get("DURATION") is not None:
        return True
    if case not in NEW_TIMES:
        return False
    other = todo.get("DTSTART" if case.startswith("set_due") else "DUE")
    if other is None:
        return False
    new, old = NEW_TIMES[case], other.dt
    if isinstance(new, datetime) != isinstance(old, datetime):
        return True
    if isinstance(new, datetime) and not _is_utc(old):
        return True
    start, due = (old, new) if case.startswith("set_due") else (new, old)
    return not start < due


def _categories(todo: Any) -> list[str]:
    raw = todo.get("CATEGORIES")
    values = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    return [str(cat) for line in values for cat in line.cats]


def _parents(todo: Any) -> list[str]:
    raw = todo.get("RELATED-TO")
    values = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    return [
        str(v) for v in values if str((v.params or {}).get("RELTYPE", "PARENT")).upper() == "PARENT"
    ]


def _already(todo: Any, case: str) -> bool:
    """Whether the stored object already shows the wanted state (then nothing is written)."""
    kwargs, _field, name = CASES[case]
    if case.startswith("clear_"):
        if name == "PARENT":
            return not _parents(todo)
        if name == "DESCRIPTION":
            return not str(todo.get("DESCRIPTION") or "") and todo.get("X-ALT-DESC") is None
        return todo.get(name) is None
    value = next(iter(kwargs.values()))
    if name == "PARENT":
        return _parents(todo) == [PARENT_UID]
    if name == "CATEGORIES":
        return _categories(todo) == value
    if name == "PRIORITY":
        return str(todo.get(name) or "").strip() == str(value)
    if case in NEW_TIMES:
        old = todo.get(name)
        new = NEW_TIMES[case]
        return (
            old is not None
            and type(old.dt) is type(new)
            and (not isinstance(new, datetime) or _is_utc(old.dt))
            and old.dt == new
        )
    return str(todo.get(name) or "") == value


@pytest.mark.parametrize(("obj", "case"), MATRIX)
@pytest.mark.anyio
async def test_round_trip_changes_exactly_the_named_field(
    clients: NcClients,
    obj: str,
    case: str,
) -> None:
    before = OBJECTS[obj]
    kwargs, field, name = CASES[case]
    store = store_with(("root.ics", before), ("zz-parent.ics", vtodo(PARENT_UID)))
    todo = todo_of(before)
    start = datetime.now(UTC).replace(microsecond=0)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        if _expected_refusal(todo, case):
            with pytest.raises(ToolError) as caught:
                await call(clients, store, **kwargs)
            assert caught.value.reason == REASON_GUARD_TRIPPED
            assert store.writes == []
            return
        answer = await call(clients, store, **kwargs)
    if _already(todo, case):
        assert store.writes == []
        assert answer["changed"] == []
        return

    etag = store.writes[0][2]
    assert store.writes == [("PUT", "root.ics", etag)]
    assert answer["changed"] == [field]
    assert answer.get("removed", []) == ([field] if case.startswith("clear_") else [])
    after = store.objects["root.ics"][0]
    touched = {name, *STAMPS}
    if name == "DESCRIPTION" and todo.get("X-ALT-DESC") is not None:
        touched.add("X-ALT-DESC")
    assert byte_proof(crlf(before), after, touched) == []
    assert semantic_proof(before, after, touched) == []

    new = todo_of(after)
    stamps = {new[stamp].dt for stamp in STAMPS}
    assert len(stamps) == 1
    assert start <= stamps.pop() <= datetime.now(UTC)
    if case.startswith("clear_"):
        if name == "PARENT":
            assert _parents(new) == []
        elif name == "DESCRIPTION":
            assert str(new.get("DESCRIPTION") or "") == ""
            if todo.get("DESCRIPTION") is not None:
                # ENTSCHEID entfernen_description=leer: an empty line, as the app writes it.
                assert b"\r\nDESCRIPTION:\r\n" in after
        else:
            assert new.get(name) is None
    elif name == "PARENT":
        assert _parents(new) == [PARENT_UID]
    elif name == "CATEGORIES":
        assert _categories(new) == kwargs["tags"]
    elif name == "PRIORITY":
        assert int(new["PRIORITY"]) == 7
    elif case in NEW_TIMES:
        assert type(new[name].dt) is type(NEW_TIMES[case])
        assert new[name].dt == NEW_TIMES[case]
    else:
        assert str(new[name]) == next(iter(kwargs.values()))


def test_the_matrix_covers_every_fixture_of_the_tasks_app() -> None:
    from test_ics_edit import FIXTURE_FILES, RECURRING_FIXTURES

    assert set(FIXTURE_FILES) - RECURRING_FIXTURES <= set(OBJECTS)
    assert {"spike", "html_description", "relations"} <= set(OBJECTS)


# --- the cleared form equals what the Tasks app wrote ------------------------------------------


def _app(name: str) -> bytes:
    from test_ics_edit import FIXTURES as APP

    return (APP / name).read_bytes()


def _with_line(data: bytes, line: bytes) -> bytes:
    """A prior state the measurement did not keep as a file: the app object plus one line."""
    return data.replace(b"END:VTODO\r\n", line + b"\r\nEND:VTODO\r\n")


APP_PAIRS = [
    pytest.param(
        _with_line(_app("cleared_due.ics"), b"DUE:20261120T080000Z"),
        "cleared_due.ics",
        {"due": ""},
        id="clear-due",
    ),
    pytest.param(_app("cleared_due.ics"), "cleared_start.ics", {"start": ""}, id="clear-start"),
    pytest.param(
        _app("cleared_start.ics"), "cleared_description.ics", {"description": ""}, id="clear-desc"
    ),
    pytest.param(
        _app("cleared_description.ics"), "cleared_priority.ics", {"priority": 0}, id="clear-prio"
    ),
    pytest.param(_app("cleared_priority.ics"), "cleared_tags.ics", {"tags": []}, id="clear-tags"),
    pytest.param(
        _with_line(_app("cleared_parent.ics"), b"RELATED-TO:ab1f2041-6958-4201-9c93-722b1be7fd67"),
        "cleared_parent.ics",
        {"parent": ""},
        id="clear-parent",
    ),
]


@pytest.mark.parametrize(("before", "app_file", "kwargs"), APP_PAIRS)
@pytest.mark.anyio
async def test_update_task_clears_as_the_tasks_app_did(
    clients: NcClients,
    before: bytes,
    app_file: str,
    kwargs: dict[str, Any],
) -> None:
    store = store_with(("root.ics", before))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, **kwargs)
    ours = store.objects["root.ics"][0]
    app = _app(app_file)
    assert line_diff(before, ours) == line_diff(before, app)

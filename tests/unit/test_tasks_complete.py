"""Unit tests for ``complete_task`` (``tasks_complete``, plan 33-06), every path without a network.

Pinned here: every refusal before the first request (id, Deck key, ETag form, ``completed``
not a bool) and every refusal after the discovery and the GET but before any PUT (unknown
list or task with one answer, read only list, stale ETag, recurring task, several VTODO, a
text the check before the edit refuses); the target state without any PUT (D-33-08); the one
PUT of a task without subtasks with ``If-Match`` on the ETag of the assistant and a text that
differs from the stored one in exactly STATUS, PERCENT-COMPLETE, COMPLETED, LAST-MODIFIED and
DTSTAMP, all four times one UTC second with ``Z``; completing a parent with its descendants
first, the named task last, completed descendants without a PUT and cancelled ones left
alone and named (D-33-00b, D-33-09, D-33-14); a stop at the first failure; reopening only
the named task (D-33-05, ENTSCHEID wiederoeffnen_kinder=bleiben); a cancelled task completed
and reopened directly (ENTSCHEID cancelled_direkt); no SEQUENCE; line ends normalised to CRLF
also for an object that arrives with LF only; and the answer, which never carries a URI or
an owner.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape

import httpx
import pytest
import respx
import task_store
from icalendar import Calendar as IcsCalendar
from test_ics_edit import semantic_proof

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

SECRET = "app-password-test"
OWN = "spike30-aufgaben"
SHARED_RW = "spike30-b-rw_shared_by_bob"
SHARED_RO = "spike30-b-ro_shared_by_bob"
LEAKS = ("_shared_by_", "bob", "Bob", "remote.php", "http", "calendars/")
COMPLETE_FIELDS = {"STATUS", "PERCENT-COMPLETE", "COMPLETED", "LAST-MODIFIED", "DTSTAMP"}


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(task_store.BASE, task_store.USER, SECRET),
    )


# --- the server ----------------------------------------------------------------------------


def home_entry(uri: str, name: str, *, owner: str | None = None, writable: bool = True) -> str:
    """One task list of a discovery answer; ``owner`` makes it a share of that person."""
    privilege = "<d:privilege><d:write/></d:privilege>" if writable else ""
    shared = "<oc:invite/>"
    if owner is not None:
        shared = (
            f"<oc:read-only>{'0' if writable else '1'}</oc:read-only>"
            f"<x1:owner-displayname>{owner}</x1:owner-displayname>"
        )
        name = f"{name} ({owner})"
    return (
        f"<d:response><d:href>{task_store.HOME_PATH}{quote(uri, safe='')}/</d:href>"
        "<d:propstat><d:prop>"
        "<d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>"
        f"<d:displayname>{escape(name)}</d:displayname>"
        '<cal:supported-calendar-component-set><cal:comp name="VTODO"/>'
        "</cal:supported-calendar-component-set>"
        "<d:current-user-privilege-set><d:privilege><d:read/></d:privilege>"
        f"{privilege}</d:current-user-privilege-set>{shared}"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
    )


HOME = (
    '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
    'xmlns:cal="urn:ietf:params:xml:ns:caldav" xmlns:oc="http://owncloud.org/ns" '
    'xmlns:x1="http://nextcloud.com/ns">'
    + home_entry(OWN, "Einkauf")
    + home_entry(SHARED_RW, "Team", owner="bob")
    + home_entry(SHARED_RO, "Lesen", owner="bob", writable=False)
    + "</d:multistatus>"
)


def mount(mock: respx.MockRouter, *stores: task_store.TaskStore) -> respx.Route:
    discovery = mock.route(method="PROPFIND", url=task_store.CALENDAR_HOME).mock(
        return_value=httpx.Response(207, text=HOME, headers={"Content-Type": "application/xml"})
    )
    task_store.mount(mock, *stores)
    return discovery


def vtodo(uid: str, *lines: str, end: str = "\r\n") -> str:
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//test//EN",
        "BEGIN:VTODO",
        f"UID:{uid}",
        "DTSTAMP:20261111T120000Z",
        "LAST-MODIFIED:20261111T120000Z",
        f"SUMMARY:{uid}",
        "X-KEEP-ME:foreign value",
        *lines,
        "END:VTODO",
        "END:VCALENDAR",
    ]
    return end.join(body) + end


OPEN = "STATUS:NEEDS-ACTION"
DONE = ("STATUS:COMPLETED", "PERCENT-COMPLETE:100", "COMPLETED:20261112T080000Z")
CANCELLED = "STATUS:CANCELLED"


def tid(uri: str, name: str) -> str:
    return ids.encode_task(ids.task_list_key(uri), name)


ROOT = tid(OWN, "root.ics")


def store_with(*objects: tuple[str, str]) -> task_store.TaskStore:
    store = task_store.TaskStore(OWN)
    for name, text in objects:
        store.add(name, text)
    return store


def child(uid: str, parent: str, *lines: str) -> tuple[str, str]:
    return f"{uid}.ics", vtodo(uid, f"RELATED-TO:{parent}", *lines)


async def call(
    clients: NcClients,
    store: task_store.TaskStore,
    *,
    task_id: str = ROOT,
    etag: str | None = None,
    completed: Any = True,
) -> dict[str, Any]:
    used = etag if etag is not None else store.etag("root.ics")
    return await tasks_tools.complete_task(clients, task_id=task_id, etag=used, completed=completed)


def puts(store: task_store.TaskStore) -> list[str]:
    return [name for method, name, _match in store.writes if method == "PUT"]


def todo_of(text: str | bytes) -> Any:
    (todo,) = IcsCalendar.from_ical(text).walk("VTODO")
    return todo


def differing_names(before: str, after: str) -> set[str]:
    """Names of the VTODO properties whose lines differ, read with icalendar."""
    old, new = todo_of(before), todo_of(after)
    names = {str(name).upper() for name in (*old.keys(), *new.keys())}
    return {
        name
        for name in names
        if (old.get(name).to_ical() if old.get(name) is not None else None)
        != (new.get(name).to_ical() if new.get(name) is not None else None)
    }


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
        {"completed": "yes"},
        {"completed": 1},
        {"completed": None},
    ],
    ids=[
        "not-a-task",
        "no-id",
        "etag-empty",
        "etag-star",
        "etag-weak",
        "etag-list",
        "completed-text",
        "completed-int",
        "completed-none",
    ],
)
@pytest.mark.anyio
async def test_bad_input_is_refused_before_any_request(
    clients: NcClients, kwargs: dict[str, Any]
) -> None:
    arguments: dict[str, Any] = {"task_id": ROOT, "etag": '"e-1"', "completed": True, **kwargs}
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ToolError):
            await tasks_tools.complete_task(clients, **arguments)
        assert mock.calls.call_count == 0


@pytest.mark.anyio
async def test_a_deck_key_is_an_unknown_task_before_any_request(clients: NcClients) -> None:
    deck_id = ids.encode_task("app-generated--deck--board-1", "card-1.ics")
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ToolError) as caught:
            await tasks_tools.complete_task(clients, task_id=deck_id, etag='"e"', completed=True)
        assert mock.calls.call_count == 0
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert caught.value.message == tasks_tools._unknown_task(deck_id).message


# --- refusals after the discovery and the GET, before any PUT --------------------------------


@pytest.mark.anyio
async def test_everything_unknown_gets_one_answer_and_no_write(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root", OPEN)), ("broken.ics", "not ical"))
    cases = [
        tid("no-such-list", "root.ics"),
        tid(OWN, "missing.ics"),
        tid(OWN, "broken.ics"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        for task_id in cases:
            with pytest.raises(ToolError) as caught:
                await tasks_tools.complete_task(
                    clients, task_id=task_id, etag='"e"', completed=True
                )
            assert caught.value.reason == REASON_UNKNOWN_ID
            assert caught.value.message == tasks_tools._unknown_task(task_id).message
    assert store.writes == []


@pytest.mark.anyio
async def test_a_read_only_list_is_refused_without_a_put(clients: NcClients) -> None:
    store = task_store.TaskStore(SHARED_RO)
    store.add("root.ics", vtodo("root", OPEN))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, task_id=tid(SHARED_RO, "root.ics"))
    assert store.writes == []
    assert "read only" in caught.value.message
    for leak in LEAKS:
        assert leak not in str(caught.value)


@pytest.mark.anyio
async def test_a_stale_etag_is_a_conflict_without_a_put(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root", OPEN)))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ConflictError) as caught:
            await call(clients, store, etag='"an-old-etag"')
    assert store.writes == []
    assert store.reports == 0
    assert "read the task again with tasks_read" in str(caught.value)


@pytest.mark.parametrize(
    "text",
    [
        vtodo("root", OPEN, "DTSTART:20261111T120000Z", "RRULE:FREQ=DAILY"),
        vtodo("root", OPEN, "RDATE:20261120T120000Z"),
        vtodo("root", OPEN).replace(
            "END:VCALENDAR",
            "BEGIN:VTODO\r\nUID:second\r\nSUMMARY:two\r\nEND:VTODO\r\nEND:VCALENDAR",
        ),
        vtodo("root", OPEN, "SUMMARY:twice"),
    ],
    ids=["rrule", "rdate", "two-vtodo", "summary-twice"],
)
@pytest.mark.parametrize("completed", [True, False], ids=["complete", "reopen"])
@pytest.mark.anyio
async def test_a_task_that_cannot_be_changed_safely_is_refused_without_a_put(
    clients: NcClients, text: str, completed: bool
) -> None:
    store = store_with(("root.ics", text))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, completed=completed)
    assert store.writes == []
    assert caught.value.reason == REASON_GUARD_TRIPPED


# --- target state ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lines",
    [DONE, ("COMPLETED:20261112T080000Z",), ("STATUS:COMPLETED",)],
    ids=["all-three", "completed-time-only", "status-only"],
)
@pytest.mark.anyio
async def test_completing_a_completed_task_sends_nothing(
    clients: NcClients, lines: tuple[str, ...]
) -> None:
    store = store_with(("root.ics", vtodo("root", *lines)), child("a", "root", OPEN))
    before = store.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    assert store.writes == []
    assert store.reports == 0
    assert store.snapshot() == before
    assert answer["already"] is True
    assert answer["status"] == "completed"
    assert answer["id"] == ROOT


@pytest.mark.parametrize(
    ("lines", "status"),
    [
        ((OPEN,), "open"),
        ((), "open"),
        (("STATUS:IN-PROCESS", "PERCENT-COMPLETE:40"), "in_progress"),
    ],
    ids=["needs-action", "no-status", "in-process"],
)
@pytest.mark.anyio
async def test_reopening_an_open_task_sends_nothing(
    clients: NcClients, lines: tuple[str, ...], status: str
) -> None:
    store = store_with(("root.ics", vtodo("root", *lines)), child("a", "root", *DONE))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=False)
    assert store.writes == []
    assert store.reports == 0
    assert answer["already"] is True
    assert answer["status"] == status


# --- completing ------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_completing_without_children_is_one_put_with_the_etag_of_the_assistant(
    clients: NcClients,
) -> None:
    before = vtodo("root", OPEN, "PERCENT-COMPLETE:20")
    store = store_with(("root.ics", before), ("other.ics", vtodo("other", OPEN)))
    etag = store.etag("root.ics")
    start = datetime.now(UTC).replace(microsecond=0)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    end = datetime.now(UTC)
    assert store.writes == [("PUT", "root.ics", etag)]
    assert store.reports == 1
    after = store.text("root.ics")
    assert semantic_proof(before.encode(), after.encode(), COMPLETE_FIELDS) == []
    assert differing_names(before, after) == COMPLETE_FIELDS
    todo = todo_of(after)
    assert str(todo["STATUS"]) == "COMPLETED"
    assert str(todo["PERCENT-COMPLETE"]) == "100"
    moments = {todo[name].dt for name in ("COMPLETED", "LAST-MODIFIED", "DTSTAMP")}
    assert len(moments) == 1
    (moment,) = moments
    assert moment.utcoffset() == timedelta(0)
    assert start <= moment <= end
    for name in ("COMPLETED", "LAST-MODIFIED", "DTSTAMP"):
        assert re.search(rf"^{name}:\d{{8}}T\d{{6}}Z\r$", after, re.MULTILINE)
    assert answer["already"] is False
    assert answer["status"] == "completed"
    assert answer["changed"] == [ROOT]
    assert answer["etag"] == store.etag("root.ics")
    assert "failed" not in answer


@pytest.mark.anyio
async def test_a_task_without_a_status_line_gets_all_fields(clients: NcClients) -> None:
    before = vtodo("root")
    store = store_with(("root.ics", before))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, completed=True)
    after = store.text("root.ics")
    assert semantic_proof(before.encode(), after.encode(), COMPLETE_FIELDS) == []
    assert differing_names(before, after) == COMPLETE_FIELDS


@pytest.mark.anyio
async def test_completing_a_parent_writes_the_subtree_first_and_the_parent_last(
    clients: NcClients,
) -> None:
    store = store_with(
        ("root.ics", vtodo("root", OPEN)),
        child("k1", "root", OPEN),
        child("k2", "root", OPEN),
        child("e1", "k1", OPEN),
        child("u1", "e1", OPEN),
        child("e2", "k2", *DONE),
        child("e3", "k2", CANCELLED),
        ("other.ics", vtodo("other", OPEN)),
    )
    before = store.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    assert store.reports == 1
    assert puts(store) == ["u1.ics", "e1.ics", "k1.ics", "k2.ics", "root.ics"]
    for _method, name, match in store.writes:
        assert match == before[name][1]
    assert store.snapshot()["e2.ics"] == before["e2.ics"]
    assert store.snapshot()["e3.ics"] == before["e3.ics"]
    assert store.snapshot()["other.ics"] == before["other.ics"]
    for name in ("u1.ics", "e1.ics", "k1.ics", "k2.ics", "root.ics"):
        old, new = before[name][0], store.objects[name][0]
        assert semantic_proof(old, new, COMPLETE_FIELDS) == []
        assert str(todo_of(new)["STATUS"]) == "COMPLETED"
    assert answer["changed"] == [tid(OWN, n) for n in ("u1.ics", "e1.ics", "k1.ics", "k2.ics")] + [
        ROOT
    ]
    assert answer["unchanged"] == 1
    assert answer["left_alone"] == [tid(OWN, "e3.ics")]
    assert answer["status"] == "completed"


@pytest.mark.anyio
async def test_completing_with_depth_one_writes_each_child_once(clients: NcClients) -> None:
    store = store_with(
        ("root.ics", vtodo("root", OPEN)), child("b", "root", OPEN), child("a", "root", OPEN)
    )
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, completed=True)
    assert puts(store) == ["a.ics", "b.ics", "root.ics"]


@pytest.mark.anyio
async def test_an_unreadable_object_of_the_list_is_counted_as_skipped(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root", OPEN)), ("broken.ics", "not ical"))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    assert answer["skipped"] == 1
    assert puts(store) == ["root.ics"]


@pytest.mark.anyio
async def test_more_descendants_than_the_cap_are_refused_without_a_put(
    clients: NcClients,
) -> None:
    kids = [child(f"k{n:03d}", "root", OPEN) for n in range(tasks_tools.CHAIN_CAP + 1)]
    store = store_with(("root.ics", vtodo("root", OPEN)), *kids)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError) as caught:
            await call(clients, store, completed=True)
    assert store.writes == []
    assert str(tasks_tools.CHAIN_CAP) in caught.value.message


@pytest.mark.anyio
async def test_a_chain_of_exactly_the_cap_is_written(clients: NcClients) -> None:
    kids = [child(f"k{n:03d}", "root", OPEN) for n in range(tasks_tools.CHAIN_CAP)]
    store = store_with(("root.ics", vtodo("root", OPEN)), *kids)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    assert len(puts(store)) == tasks_tools.CHAIN_CAP + 1
    assert "failed" not in answer


@pytest.mark.parametrize(
    "lines",
    [
        (OPEN, "DTSTART:20261111T120000Z", "RRULE:FREQ=DAILY"),
        ("SUMMARY:twice",),
    ],
    ids=["recurring", "summary-twice"],
)
@pytest.mark.anyio
async def test_a_descendant_that_cannot_be_changed_refuses_the_chain_without_a_put(
    clients: NcClients, lines: tuple[str, ...]
) -> None:
    store = store_with(
        ("root.ics", vtodo("root", OPEN)),
        child("a", "root", OPEN),
        child("b", "a", *lines),
    )
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        with pytest.raises(ToolError):
            await call(clients, store, completed=True)
    assert store.writes == []


@pytest.mark.anyio
async def test_a_412_on_the_second_descendant_stops_and_keeps_the_named_task(
    clients: NcClients,
) -> None:
    store = store_with(
        ("root.ics", vtodo("root", OPEN)),
        child("a", "root", OPEN),
        child("b", "root", OPEN),
        child("c", "root", OPEN),
    )
    store.fail["b.ics"] = 412
    before = store.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    assert puts(store) == ["a.ics", "b.ics"]
    assert store.snapshot()["root.ics"] == before["root.ics"]
    assert store.snapshot()["c.ics"] == before["c.ics"]
    assert answer["changed"] == [tid(OWN, "a.ics")]
    assert answer["failed"] == tid(OWN, "b.ics")
    assert answer["reason"] == "conflict"
    assert "read the task again with tasks_read" in answer["message"]
    assert answer["status"] == "open"
    assert "etag" not in answer


@pytest.mark.anyio
async def test_a_412_on_the_named_task_is_reported_as_its_conflict(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root", OPEN)))
    store.fail["root.ics"] = 412
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    assert puts(store) == ["root.ics"]
    assert answer["failed"] == ROOT
    assert answer["reason"] == "conflict"
    assert answer["changed"] == []
    assert answer["status"] == "open"


# --- reopening -------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reopening_touches_only_the_named_task(clients: NcClients) -> None:
    before = vtodo("root", *DONE)
    store = store_with(("root.ics", before), child("a", "root", *DONE), child("b", "a", *DONE))
    snapshot = store.snapshot()
    etag = store.etag("root.ics")
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=False)
    assert store.reports == 0
    assert store.writes == [("PUT", "root.ics", etag)]
    assert store.snapshot()["a.ics"] == snapshot["a.ics"]
    assert store.snapshot()["b.ics"] == snapshot["b.ics"]
    after = store.text("root.ics")
    assert semantic_proof(before.encode(), after.encode(), COMPLETE_FIELDS) == []
    assert differing_names(before, after) == COMPLETE_FIELDS
    todo = todo_of(after)
    assert str(todo["STATUS"]) == "NEEDS-ACTION"
    assert todo.get("COMPLETED") is None
    assert todo.get("PERCENT-COMPLETE") is None
    assert todo["LAST-MODIFIED"].dt == todo["DTSTAMP"].dt
    assert answer["already"] is False
    assert answer["status"] == "open"
    assert answer["changed"] == [ROOT]


# --- cancelled -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lines",
    [(CANCELLED,), (CANCELLED, "PERCENT-COMPLETE:30")],
    ids=["plain", "with-percent"],
)
@pytest.mark.anyio
async def test_a_cancelled_task_is_completed_directly(
    clients: NcClients, lines: tuple[str, ...]
) -> None:
    before = vtodo("root", *lines)
    store = store_with(("root.ics", before))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    after = store.text("root.ics")
    assert semantic_proof(before.encode(), after.encode(), COMPLETE_FIELDS) == []
    todo = todo_of(after)
    assert str(todo["STATUS"]) == "COMPLETED"
    assert str(todo["PERCENT-COMPLETE"]) == "100"
    assert todo["COMPLETED"].dt == todo["DTSTAMP"].dt == todo["LAST-MODIFIED"].dt
    assert "CANCELLED" not in after
    assert answer["status"] == "completed"


@pytest.mark.parametrize(
    "lines",
    [(CANCELLED,), (CANCELLED, "PERCENT-COMPLETE:30", "COMPLETED:20261112T080000Z")],
    ids=["plain", "with-completed"],
)
@pytest.mark.anyio
async def test_a_cancelled_task_is_reopened_directly(
    clients: NcClients, lines: tuple[str, ...]
) -> None:
    before = vtodo("root", *lines)
    store = store_with(("root.ics", before))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=False)
    assert store.reports == 0
    after = store.text("root.ics")
    assert semantic_proof(before.encode(), after.encode(), COMPLETE_FIELDS) == []
    todo = todo_of(after)
    assert str(todo["STATUS"]) == "NEEDS-ACTION"
    assert todo.get("COMPLETED") is None
    assert todo.get("PERCENT-COMPLETE") is None
    assert answer["status"] == "open"


# --- SEQUENCE --------------------------------------------------------------------------------


@pytest.mark.parametrize("sequence", [None, "SEQUENCE:0", "SEQUENCE:7"], ids=["none", "0", "7"])
@pytest.mark.parametrize("completed", [True, False], ids=["complete", "reopen"])
@pytest.mark.anyio
async def test_the_sequence_is_never_touched(
    clients: NcClients, sequence: str | None, completed: bool
) -> None:
    state = (OPEN,) if completed else DONE
    before = vtodo("root", *state, *((sequence,) if sequence else ()))
    store = store_with(("root.ics", before))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, completed=completed)
    assert puts(store) == ["root.ics"]
    after = store.text("root.ics")
    old_lines = re.findall(r"^SEQUENCE[;:].*$", before, re.MULTILINE)
    new_lines = re.findall(r"^SEQUENCE[;:].*$", after, re.MULTILINE)
    assert new_lines == old_lines
    assert len(new_lines) == (1 if sequence else 0)


# --- line ends -------------------------------------------------------------------------------


@pytest.mark.parametrize("completed", [True, False], ids=["complete", "reopen"])
@pytest.mark.anyio
async def test_an_object_with_lf_line_ends_is_written_with_crlf(
    clients: NcClients, completed: bool
) -> None:
    state = (OPEN,) if completed else DONE
    before = vtodo(
        "root", *state, "DESCRIPTION:a long line that is folded here and", " continued", end="\n"
    )
    lf_child = vtodo("a", "RELATED-TO:root", OPEN, end="\n")
    assert "\r" not in before + lf_child
    store = store_with(("root.ics", before), ("a.ics", lf_child))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, completed=completed)
    for name in puts(store):
        sent = store.text(name)
        assert re.search(r"(?<!\r)\n", sent) is None
        old = before if name == "root.ics" else lf_child
        assert semantic_proof(old.encode(), sent.encode(), COMPLETE_FIELDS) == []
    assert puts(store) == (["a.ics", "root.ics"] if completed else ["root.ics"])
    assert "continued" in str(todo_of(store.text("root.ics"))["DESCRIPTION"])


@pytest.mark.anyio
async def test_a_crlf_object_keeps_every_untouched_line_byte_for_byte(clients: NcClients) -> None:
    before = vtodo("root", OPEN, "DESCRIPTION:a long line that is folded here and", "\tcontinued")
    store = store_with(("root.ics", before))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        await call(clients, store, completed=True)
    after = store.text("root.ics")
    for line in before.split("\r\n"):
        name = re.split(r"[;:]", line, maxsplit=1)[0]
        if name not in COMPLETE_FIELDS:
            assert line in after.split("\r\n")


# --- the answer ------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_put_without_an_etag_header_asks_for_a_new_read(clients: NcClients) -> None:
    store = store_with(("root.ics", vtodo("root", OPEN)))
    store.fail["root.ics"] = 204  # a 204 without ETag: the server altered the text
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, completed=True)
    assert "etag" not in answer
    assert "read the task again for its new etag" in json.dumps(answer)
    assert answer["changed"] == [ROOT]


@pytest.mark.anyio
async def test_the_answer_in_a_shared_list_names_neither_uri_nor_owner(
    clients: NcClients,
) -> None:
    store = task_store.TaskStore(SHARED_RW)
    store.add("root.ics", vtodo("root", OPEN))
    store.add("a.ics", vtodo("a", "RELATED-TO:root", OPEN))
    store.add("c.ics", vtodo("c", "RELATED-TO:root", CANCELLED))
    store.fail["root.ics"] = 412
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, store)
        answer = await call(clients, store, task_id=tid(SHARED_RW, "root.ics"))
    text = json.dumps(answer)
    for leak in LEAKS:
        assert leak not in text
    assert answer["list"]["name"] == "Team"
    assert answer["list"]["shared"] is True
    assert answer["id"] == tid(SHARED_RW, "root.ics")

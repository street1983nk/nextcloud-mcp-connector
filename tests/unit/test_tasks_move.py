"""Unit tests for ``move_task`` (``tasks_move``, plan 33-08), every path without a network.

Pinned here: every refusal before the first request (id, Deck key of the task, ETag form,
an empty target, a target with the Deck prefix); every refusal after the discovery and
before any relocation (unknown target, which names the writable task lists, an ambiguous
target, which names the keys, a read only target or source, a calendar that holds no tasks);
the same list as success without a relocation (``already``); the refusals after the GET
(stale ETag, recurring, several VTODO) and after the REPORT of the source (more than
``CHAIN_CAP`` descendants, a recurring descendant, one that is not UTF-8); the check of the
target list before the first relocation (object name or UID of any task to relocate already
there); one relocation with ``Destination`` on the same object name in the target list,
``Overwrite: F`` and ``If-Match``; a parent with its descendants in post-order, the named task
last (D-33-00c, D-33-09 to D-33-11); a stop at the first failure with the new ids of what was
relocated; 204 as a loud failure, 409 as a UID conflict; and the answer, which names old and
new ids and the target list, never a URI or an owner.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape

import httpx
import pytest
import respx
import task_store

from mcp_connector import ids
from mcp_connector.errors import (
    REASON_GUARD_TRIPPED,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import tasks as tasks_client
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import tasks as tasks_tools

SECRET = "app-password-test"
OWN = "spike30-aufgaben"
ZIEL = "ziel-liste"
SHARED_RW = "spike30-b-rw_shared_by_bob"
SHARED_RO = "spike30-b-ro_shared_by_bob"
EVENTS = "termine"
TWIN_OWN = "doppelt-eigen"
TWIN_SHARED = "doppelt-b_shared_by_bob"
LEAKS = ("_shared_by_", "bob", "Bob", "remote.php", "http", "calendars/")


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(task_store.BASE, task_store.USER, SECRET),
    )


# --- the server ----------------------------------------------------------------------------


def home_entry(
    uri: str,
    name: str,
    *,
    owner: str | None = None,
    writable: bool = True,
    component: str = "VTODO",
) -> str:
    """One calendar of a discovery answer; ``owner`` makes it a share of that person."""
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
        f'<cal:supported-calendar-component-set><cal:comp name="{component}"/>'
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
    + home_entry(ZIEL, "Ziel")
    + home_entry(SHARED_RW, "Team", owner="bob")
    + home_entry(SHARED_RO, "Lesen", owner="bob", writable=False)
    + home_entry(EVENTS, "Termine", component="VEVENT")
    + home_entry(TWIN_OWN, "Doppelt")
    + home_entry(TWIN_SHARED, "Doppelt", owner="bob")
    + "</d:multistatus>"
)


def mount(mock: respx.MockRouter, *stores: task_store.TaskStore) -> respx.Route:
    discovery = mock.route(method="PROPFIND", url=task_store.CALENDAR_HOME).mock(
        return_value=httpx.Response(207, text=HOME, headers={"Content-Type": "application/xml"})
    )
    task_store.mount(mock, *stores)
    return discovery


def vtodo(uid: str, *lines: str) -> str:
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//test//EN",
        "BEGIN:VTODO",
        f"UID:{uid}",
        "DTSTAMP:20261111T120000Z",
        f"SUMMARY:{uid}",
        "X-KEEP-ME:foreign value",
        *lines,
        "END:VTODO",
        "END:VCALENDAR",
    ]
    return "\r\n".join(body) + "\r\n"


def tid(uri: str, name: str) -> str:
    return ids.encode_task(ids.task_list_key(uri), name)


ROOT = tid(OWN, "root.ics")


def child(uid: str, parent: str, *lines: str) -> tuple[str, str]:
    return f"{uid}.ics", vtodo(uid, f"RELATED-TO:{parent}", *lines)


def stores(
    *objects: tuple[str, str], target: str = ZIEL, source: str = OWN
) -> tuple[task_store.TaskStore, task_store.TaskStore]:
    first = task_store.TaskStore(source)
    for name, text in objects:
        first.add(name, text)
    return first, task_store.TaskStore(target)


async def call(
    clients: NcClients,
    source: task_store.TaskStore,
    *,
    task_id: str = ROOT,
    etag: str | None = None,
    target: Any = "Ziel",
) -> dict[str, Any]:
    used = etag if etag is not None else source.etag("root.ics")
    return await tasks_tools.move_task(clients, task_id=task_id, etag=used, list_name=target)


def moves(store: task_store.TaskStore) -> list[str]:
    return [name for method, name, _match in store.writes if method == "MOVE"]


def no_leak(value: Any) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    for leak in LEAKS:
        assert leak not in text, leak


# --- refusals before any request -----------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"task_id": "note:12"},
        {"task_id": "garbage"},
        {"task_id": ids.encode_task("app-generated--deck--board-1", "card-1.ics")},
        {"etag": ""},
        {"etag": "*"},
        {"etag": 'W/"abc"'},
        {"etag": '"a", "b"'},
        {"list_name": ""},
        {"list_name": "   "},
        {"list_name": None},
        {"list_name": 3},
        {"list_name": "app-generated--deck--board-1"},
        {"list_name": "  app-generated--deck--board-1 "},
    ],
    ids=[
        "not-a-task",
        "no-id",
        "deck-task",
        "etag-empty",
        "etag-star",
        "etag-weak",
        "etag-list",
        "list-empty",
        "list-blank",
        "list-none",
        "list-int",
        "list-deck",
        "list-deck-padded",
    ],
)
@pytest.mark.anyio
async def test_bad_input_is_refused_before_any_request(
    clients: NcClients, kwargs: dict[str, Any]
) -> None:
    arguments: dict[str, Any] = {"task_id": ROOT, "etag": '"e-1"', "list_name": "Ziel", **kwargs}
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ToolError) as caught:
            await tasks_tools.move_task(clients, **arguments)
        assert mock.calls.call_count == 0
    no_leak(str(caught.value))


@pytest.mark.anyio
async def test_a_deck_task_gets_the_answer_of_an_unknown_task(clients: NcClients) -> None:
    deck_id = ids.encode_task("app-generated--deck--board-1", "card-1.ics")
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ToolError) as caught:
            await tasks_tools.move_task(clients, task_id=deck_id, etag='"e"', list_name="Ziel")
        assert mock.calls.call_count == 0
    assert caught.value.reason == REASON_UNKNOWN_ID


@pytest.mark.anyio
async def test_a_deck_target_is_refused_as_guard(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        with pytest.raises(ToolError) as caught:
            await tasks_tools.move_task(
                clients, task_id=ROOT, etag='"e"', list_name="app-generated--deck--board-1"
            )
        assert mock.calls.call_count == 0
    assert caught.value.reason == REASON_GUARD_TRIPPED


# --- refusals after the discovery, before any relocation -----------------------------------


@pytest.mark.parametrize("target", ["Nirgendwo", "Termine", EVENTS], ids=["name", "events", "key"])
@pytest.mark.anyio
async def test_an_unknown_target_names_the_writable_task_lists(
    clients: NcClients, target: str
) -> None:
    source, dest = stores(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source, target=target)
    assert source.writes == []
    hint = caught.value.hint or ""
    for name in ("Einkauf", "Ziel", "Team", "Doppelt"):
        assert name in hint
    # a read only list and a calendar without tasks are no way out
    assert "Lesen" not in hint
    assert "Termine" not in hint
    no_leak(str(caught.value) + hint)


@pytest.mark.anyio
async def test_an_ambiguous_target_names_the_keys_and_relocates_nothing(
    clients: NcClients,
) -> None:
    source, dest = stores(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source, target="doppelt")
    assert source.writes == []
    assert source.reports == 0
    hint = caught.value.hint or ""
    assert ids.task_list_key(TWIN_OWN) in hint
    assert ids.task_list_key(TWIN_SHARED) in hint
    no_leak(str(caught.value) + hint)


@pytest.mark.anyio
async def test_a_shared_target_resolves_only_when_named_uniquely(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), target=SHARED_RW)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source, target="Team")
    assert moves(source) == ["root.ics"]
    assert set(dest.objects) == {"root.ics"}
    assert answer["id"] == tid(SHARED_RW, "root.ics")
    assert answer["list"] == {"name": "Team", "shared": True, "writable": True}
    no_leak(answer)


@pytest.mark.anyio
async def test_the_key_of_a_twin_picks_exactly_that_list(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), target=TWIN_OWN)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source, target=ids.task_list_key(TWIN_OWN))
    assert set(dest.objects) == {"root.ics"}
    assert answer["id"] == tid(TWIN_OWN, "root.ics")


@pytest.mark.anyio
async def test_a_read_only_target_is_refused_without_a_relocation(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), target=SHARED_RO)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source, target="Lesen")
    assert source.writes == []
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert "read only" in caught.value.message
    assert "Ziel" in (caught.value.hint or "")
    no_leak(str(caught.value) + (caught.value.hint or ""))


@pytest.mark.anyio
async def test_a_read_only_source_is_refused_without_a_relocation(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), source=SHARED_RO)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source, task_id=tid(SHARED_RO, "root.ics"))
    assert source.writes == []
    assert "read only" in caught.value.message
    no_leak(str(caught.value))


@pytest.mark.anyio
async def test_an_unknown_source_gets_the_answer_of_an_unknown_task(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), ("broken.ics", "not ical"))
    cases = [tid("no-such-list", "root.ics"), tid(OWN, "missing.ics"), tid(OWN, "broken.ics")]
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        for task_id in cases:
            with pytest.raises(ToolError) as caught:
                await tasks_tools.move_task(clients, task_id=task_id, etag='"e"', list_name="Ziel")
            assert caught.value.reason == REASON_UNKNOWN_ID
            assert caught.value.message == tasks_tools._unknown_task(task_id).message
    assert source.writes == []


@pytest.mark.parametrize("target", ["Einkauf", "einkauf", OWN], ids=["name", "case", "key"])
@pytest.mark.anyio
async def test_the_same_list_is_a_success_without_a_relocation(
    clients: NcClients, target: str
) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    before = source.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source, target=target)
    assert source.writes == []
    assert source.reports == 0
    assert source.snapshot() == before
    assert answer["already"] is True
    assert answer["id"] == ROOT
    assert answer["list"]["name"] == "Einkauf"


# --- refusals after the GET and the REPORT of the source -----------------------------------


@pytest.mark.anyio
async def test_a_stale_etag_is_a_conflict_without_a_relocation(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ConflictError) as caught:
            await call(clients, source, etag='"an-old-etag"')
    assert source.writes == []
    assert dest.reports == 0
    assert "tasks_read" in str(caught.value)


@pytest.mark.parametrize(
    "text",
    [
        vtodo("root", "DTSTART:20261111T120000Z", "RRULE:FREQ=DAILY"),
        vtodo("root", "RDATE:20261120T120000Z"),
        vtodo("root").replace(
            "END:VCALENDAR",
            "BEGIN:VTODO\r\nUID:second\r\nSUMMARY:two\r\nEND:VTODO\r\nEND:VCALENDAR",
        ),
    ],
    ids=["rrule", "rdate", "two-vtodo"],
)
@pytest.mark.anyio
async def test_a_task_that_cannot_be_relocated_safely_is_refused(
    clients: NcClients, text: str
) -> None:
    source, dest = stores(("root.ics", text))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source)
    assert source.writes == []
    assert caught.value.reason == REASON_GUARD_TRIPPED


@pytest.mark.anyio
async def test_more_than_chain_cap_descendants_are_refused(clients: NcClients) -> None:
    kids = [child(f"k{i:03d}", "root") for i in range(tasks_tools.CHAIN_CAP + 1)]
    source, dest = stores(("root.ics", vtodo("root")), *kids)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source)
    assert source.writes == []
    assert str(tasks_tools.CHAIN_CAP) in caught.value.message


@pytest.mark.anyio
async def test_exactly_chain_cap_descendants_are_relocated(clients: NcClients) -> None:
    kids = [child(f"k{i:03d}", "root") for i in range(tasks_tools.CHAIN_CAP)]
    source, dest = stores(("root.ics", vtodo("root")), *kids)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert len(moves(source)) == tasks_tools.CHAIN_CAP + 1
    assert len(answer["moved"]) == tasks_tools.CHAIN_CAP
    assert source.objects == {}


@pytest.mark.anyio
async def test_a_recurring_grandchild_is_refused_before_the_first_relocation(
    clients: NcClients,
) -> None:
    source, dest = stores(
        ("root.ics", vtodo("root")),
        child("a", "root"),
        child("b", "a", "DTSTART:20261111T120000Z", "RRULE:FREQ=WEEKLY"),
    )
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source)
    assert source.writes == []
    assert tid(OWN, "b.ics") in caught.value.message
    assert "recurring" in caught.value.message


@pytest.mark.anyio
async def test_a_descendant_that_is_not_utf8_is_refused_before_the_first_relocation(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    latin = vtodo("b", "RELATED-TO:root").encode("utf-8").replace(b"SUMMARY:b", b"SUMMARY:K\xe4se")
    real = tasks_client.query_todos

    async def with_latin(*args: Any, **kwargs: Any) -> list[tasks_client.TodoObject]:
        found = await real(*args, **kwargs)
        if args[2].uri == OWN:
            found.append(tasks_client.TodoObject("b.ics", latin, '"etag-b"'))
        return found

    monkeypatch.setattr(tasks_client, "query_todos", with_latin)
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source)
    assert source.writes == []
    assert tid(OWN, "b.ics") in caught.value.message
    assert "UTF-8" in caught.value.message


# --- the check of the target list ----------------------------------------------------------


@pytest.mark.parametrize(
    ("occupant", "kind"),
    [
        (("root.ics", vtodo("someone-else")), "name"),
        (("a.ics", vtodo("other")), "name"),
        (("elsewhere.ics", vtodo("root")), "UID"),
        (("elsewhere.ics", vtodo("a")), "UID"),
        (("a.ics", "not ical"), "name"),
    ],
    ids=["root-name", "child-name", "root-uid", "child-uid", "unreadable-name"],
)
@pytest.mark.anyio
async def test_an_occupied_target_is_refused_without_a_relocation(
    clients: NcClients, occupant: tuple[str, str], kind: str
) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    dest.add(*occupant)
    before_source, before_dest = source.snapshot(), dest.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        with pytest.raises(ToolError) as caught:
            await call(clients, source)
    assert source.writes == []
    assert dest.writes == []
    assert dest.reports == 1
    assert source.snapshot() == before_source
    assert dest.snapshot() == before_dest
    message = caught.value.message
    assert "Ziel" in message
    assert kind in message
    no_leak(message + (caught.value.hint or ""))


@pytest.mark.anyio
async def test_the_target_check_counts_as_positive_control_on_a_free_target(
    clients: NcClients,
) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    dest.add("free.ics", vtodo("free"))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        await call(clients, source)
    assert set(dest.objects) == {"free.ics", "a.ics", "root.ics"}


# --- relocating ----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_task_without_children_is_one_relocation_under_the_same_name(
    clients: NcClients,
) -> None:
    text = vtodo("root", "DUE:20261120T090000Z")
    source, dest = stores(("root.ics", text), ("other.ics", vtodo("other")))
    etag = source.etag("root.ics")
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
        sent = [call.request for call in mock.calls if call.request.method == "MOVE"]
    assert source.writes == [("MOVE", "root.ics", etag)]
    (request,) = sent
    assert request.headers["Destination"] == f"{task_store.list_url(ZIEL)}root.ics"
    assert request.headers["Overwrite"] == "F"
    assert request.headers["If-Match"] == etag
    assert str(request.url) == f"{task_store.list_url(OWN)}root.ics"
    # UID, object name and text stay; so does the ETag (spike 4.1)
    assert dest.objects["root.ics"] == (text.encode("utf-8"), etag)
    assert set(source.objects) == {"other.ics"}
    assert answer["id"] == tid(ZIEL, "root.ics")
    assert answer["previous_id"] == ROOT
    assert answer["list"] == {"name": "Ziel", "shared": False, "writable": True}
    assert answer["moved"] == []
    assert answer["etag"] == etag
    assert "failed" not in answer
    assert "skipped" not in answer
    no_leak({k: v for k, v in answer.items() if k != "etag"})


@pytest.mark.anyio
async def test_a_bare_etag_is_quoted_and_still_matches(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")))
    etag = source.etag("root.ics")
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source, etag=etag.strip('"'))
    assert source.writes == [("MOVE", "root.ics", etag)]
    assert answer["etag"] == etag


@pytest.mark.anyio
async def test_depth_one_relocates_the_children_first_and_the_parent_last(
    clients: NcClients,
) -> None:
    source, dest = stores(
        ("root.ics", vtodo("root")),
        child("c", "root"),
        child("a", "root"),
        child("b", "root"),
        ("other.ics", vtodo("other")),
    )
    before = source.snapshot()
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert moves(source) == ["a.ics", "b.ics", "c.ics", "root.ics"]
    for _method, name, match in source.writes:
        assert match == before[name][1]
    assert answer["moved"] == [tid(ZIEL, n) for n in ("a.ics", "b.ics", "c.ics")]
    assert set(source.objects) == {"other.ics"}
    for name in ("a.ics", "b.ics", "c.ics", "root.ics"):
        assert dest.objects[name] == before[name]
    assert source.max_open == 1


@pytest.mark.anyio
async def test_depth_three_relocates_in_post_order(clients: NcClients) -> None:
    source, dest = stores(
        ("root.ics", vtodo("root")),
        child("k1", "root"),
        child("k2", "root"),
        child("e1", "k1"),
        child("e2", "k1"),
        child("u1", "e1"),
        child("e3", "k2"),
    )
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    order = ["u1.ics", "e1.ics", "e2.ics", "k1.ics", "e3.ics", "k2.ics"]
    assert moves(source) == [*order, "root.ics"]
    assert answer["moved"] == [tid(ZIEL, n) for n in order]
    assert source.objects == {}


@pytest.mark.anyio
async def test_a_412_on_a_descendant_stops_and_names_what_was_relocated(
    clients: NcClients,
) -> None:
    source, dest = stores(
        ("root.ics", vtodo("root")), child("a", "root"), child("b", "root"), child("c", "root")
    )
    source.fail["b.ics"] = 412
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert moves(source) == ["a.ics", "b.ics"]
    assert set(dest.objects) == {"a.ics"}
    assert {"root.ics", "b.ics", "c.ics"} <= set(source.objects)
    assert answer["id"] == ROOT
    assert answer["moved"] == [tid(ZIEL, "a.ics")]
    assert answer["failed"] == tid(OWN, "b.ics")
    assert answer["reason"] == "changed_or_name_taken"
    message = answer["message"]
    assert "changed since it was read or" in message
    assert "already taken" in message
    assert "tasks_read" in message
    assert f"{ROOT} was not relocated" in message
    assert "etag" not in answer
    no_leak(answer)


@pytest.mark.anyio
async def test_a_412_on_the_named_task_keeps_it_and_lists_the_relocated_subtasks(
    clients: NcClients,
) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    source.fail["root.ics"] = 412
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert moves(source) == ["a.ics", "root.ics"]
    assert answer["failed"] == ROOT
    assert answer["moved"] == [tid(ZIEL, "a.ics")]
    assert "etag" not in answer
    assert "root.ics" in source.objects


@pytest.mark.parametrize("where", ["a.ics", "root.ics"], ids=["descendant", "named"])
@pytest.mark.anyio
async def test_a_204_is_a_loud_failure_never_a_success(clients: NcClients, where: str) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    source.fail[where] = 204
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert answer["failed"] == tid(OWN, where)
    assert answer["reason"] == "replaced"
    assert "204" in answer["message"]
    assert "etag" not in answer
    assert "previous_id" not in answer


@pytest.mark.anyio
async def test_a_409_is_a_uid_conflict(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    source.fail["a.ics"] = 409
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert moves(source) == ["a.ics"]
    assert answer["reason"] == "uid_conflict"
    assert "UID" in answer["message"]
    assert answer["moved"] == []


@pytest.mark.anyio
async def test_an_unknown_outcome_on_the_named_task_names_both_ids(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")))
    source.fail["root.ics"] = httpx.ReadTimeout("slow")
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert answer["reason"] == "outcome_unknown"
    assert tid(ZIEL, "root.ics") in answer["message"]
    assert "etag" not in answer


@pytest.mark.anyio
async def test_skipped_objects_of_the_source_are_counted(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), ("broken.ics", "not ical"))
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source)
    assert answer["skipped"] == 1
    assert "broken.ics" in source.objects


@pytest.mark.anyio
async def test_relocating_out_of_a_shared_list_leaks_no_owner(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"), source=SHARED_RW)
    source.fail["root.ics"] = 412
    with respx.mock(assert_all_called=False) as mock:
        mount(mock, source, dest)
        answer = await call(clients, source, task_id=tid(SHARED_RW, "root.ics"))
    assert answer["moved"] == [tid(ZIEL, "a.ics")]
    no_leak(answer)


@pytest.mark.anyio
async def test_one_discovery_and_one_report_per_list(clients: NcClients) -> None:
    source, dest = stores(("root.ics", vtodo("root")), child("a", "root"))
    with respx.mock(assert_all_called=False) as mock:
        discovery = mount(mock, source, dest)
        await call(clients, source)
    assert discovery.call_count == 1
    assert source.reports == 1
    assert dest.reports == 1
    assert source.gets == ["root.ics"]

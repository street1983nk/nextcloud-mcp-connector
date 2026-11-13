"""Unit tests for ``create_task``, every path without a network.

Pinned here: every refusal before the first request (summary, priority, due, start,
timezone, parent), the object as it goes over the wire (a due date stays that very day, a
time with a zone is written in UTC, a named timezone is written with its VTIMEZONE, one
CATEGORIES line, one VTODO, RELATED-TO without RELTYPE), the choice of the target list after
E4 and D-32-16 (a shared list only when named, never through the parent alone, a read only
list refused before the request, Deck never), the create-only PUT with its wording, the read
back that never turns a write into a failure, the account without a task list (E6) and the
answer whose id ``read_task`` resolves again.
"""

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote
from xml.sax.saxutils import escape

import httpx
import pytest
import respx
from icalendar import Calendar as IcsCalendar
from lxml import etree

from mcp_connector import ids
from mcp_connector.errors import (
    REASON_GUARD_TRIPPED,
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import calendar as calendar_tools
from mcp_connector.tools import tasks as tasks_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
HOME_PATH = "/remote.php/dav/calendars/alice/"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

OWN = "spike30-aufgaben"
MIXED = "spike30-gemischt"
SHARED_RW = "spike30-b-rw_shared_by_bob"
SHARED_RO = "spike30-b-ro_shared_by_bob"
ALL_LISTS = (OWN, MIXED, SHARED_RW, SHARED_RO)
LEAKS = ("_shared_by_", "bob", "Bob")

PARENT_UID = "parent-uid-1"
PARENT_NAME = f"{PARENT_UID}.ics"


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def list_url(uri: str) -> str:
    return f"{CALENDAR_HOME}{quote(uri, safe='')}/"


def vtodo(uid: str, summary: str, *lines: str) -> str:
    body = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//test//EN",
        "BEGIN:VTODO",
        f"UID:{uid}",
        "DTSTAMP:20261111T120000Z",
        f"SUMMARY:{summary}",
        *lines,
        "END:VTODO",
        "END:VCALENDAR",
    ]
    return "\r\n".join(body) + "\r\n"


def home_entry(uri: str, name: str, *, owner: str | None = None, writable: bool = True) -> str:
    """One task list of a discovery answer; ``owner`` makes it a share of that person."""
    privilege = "<d:privilege><d:write/></d:privilege>" if writable else ""
    # An own list reports oc:invite in its 2xx propstat, empty when nobody else sees it
    # (measured in plan 32-09); a share into the account has its own marks below.
    shared = "<oc:invite/>"
    if owner is not None:
        shared = (
            f"<oc:read-only>{'0' if writable else '1'}</oc:read-only>"
            f"<x1:owner-displayname>{owner}</x1:owner-displayname>"
        )
        name = f"{name} ({owner})"
    return (
        f"<d:response><d:href>{HOME_PATH}{quote(uri, safe='')}/</d:href><d:propstat><d:prop>"
        "<d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>"
        f"<d:displayname>{escape(name)}</d:displayname>"
        '<cal:supported-calendar-component-set><cal:comp name="VTODO"/>'
        "</cal:supported-calendar-component-set>"
        "<d:current-user-privilege-set><d:privilege><d:read/></d:privilege>"
        f"{privilege}</d:current-user-privilege-set>{shared}"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
    )


def home(*entries: str) -> str:
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        'xmlns:cal="urn:ietf:params:xml:ns:caldav" xmlns:oc="http://owncloud.org/ns" '
        'xmlns:x1="http://nextcloud.com/ns">' + "".join(entries) + "</d:multistatus>"
    )


#: One own writable list and both shares of the fixture.
ONE_OWN = home(
    home_entry(OWN, OWN),
    home_entry(SHARED_RW, "spike30-b-rw", owner="bob"),
    home_entry(SHARED_RO, "spike30-b-ro", owner="bob", writable=False),
)

#: Only lists shared into the account.
ONLY_SHARED = home(
    home_entry(SHARED_RW, "spike30-b-rw", owner="bob"),
    home_entry(SHARED_RO, "spike30-b-ro", owner="bob", writable=False),
)


def recorded_home() -> str:
    """The recorded home of the spike, with the empty ``oc:invite`` the discovery of plan
    32-09 reads on each own list (the spike did not ask for it)."""
    text = fixture("caldav_home_task_lists.xml")
    for own in (OWN, MIXED):
        marker = f"<d:displayname>{own}</d:displayname>"
        assert text.count(marker) == 1
        text = text.replace(marker, f"{marker}<oc:invite/>")
    return text


def mock_discovery(mock: respx.MockRouter, body: str | None = None) -> respx.Route:
    return mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
        return_value=httpx.Response(
            207,
            text=body if body is not None else recorded_home(),
            headers={"Content-Type": "application/xml"},
        )
    )


class Store:
    """One task list on the server: PUT stores, GET answers what was stored."""

    def __init__(
        self,
        uri: str,
        *,
        put_status: int = 201,
        get_answer: httpx.Response | Exception | None = None,
        rewrite_uid: bool = False,
    ) -> None:
        self.uri = uri
        self.put_status = put_status
        self.get_answer = get_answer
        self.rewrite_uid = rewrite_uid
        self.objects: dict[str, bytes] = {}
        self.puts: list[httpx.Request] = []
        self.gets: list[str] = []

    @staticmethod
    def _name(request: httpx.Request) -> str:
        return unquote(request.url.path.rsplit("/", 1)[-1])

    def put(self, request: httpx.Request) -> httpx.Response:
        self.puts.append(request)
        if self.put_status != 201:
            return httpx.Response(self.put_status)
        self.objects[self._name(request)] = request.content
        return httpx.Response(201, headers={"ETag": '"e1"'})

    def get(self, request: httpx.Request) -> httpx.Response:
        name = self._name(request)
        self.gets.append(name)
        if name != PARENT_NAME and self.get_answer is not None:
            if isinstance(self.get_answer, Exception):
                raise self.get_answer
            return self.get_answer
        if name not in self.objects:
            return httpx.Response(404)
        content = self.objects[name]
        if self.rewrite_uid and name != PARENT_NAME:
            text = content.decode("utf-8")
            uid = name.removesuffix(".ics")
            content = text.replace(f"UID:{uid}", "UID:someone-else").encode("utf-8")
        return httpx.Response(200, content=content)

    @property
    def body(self) -> str:
        assert len(self.puts) == 1, "exactly one PUT"
        return self.puts[0].content.decode("utf-8")


def mock_stores(
    mock: respx.MockRouter, body: str | None = None, **options: Any
) -> dict[str, Store]:
    """Discovery plus one PUT and one GET route per list; ``options`` go to every store."""
    mock_discovery(mock, body)
    stores: dict[str, Store] = {}
    for uri in ALL_LISTS:
        store = Store(uri, **options)
        mock.route(method="PUT", url__startswith=list_url(uri)).mock(side_effect=store.put)
        mock.route(method="GET", url__startswith=list_url(uri)).mock(side_effect=store.get)
        stores[uri] = store
    return stores


def puts(stores: dict[str, Store]) -> int:
    return sum(len(store.puts) for store in stores.values())


def with_parent(store: Store, summary: str = "parent") -> str:
    store.objects[PARENT_NAME] = vtodo(PARENT_UID, summary).encode("utf-8")
    return ids.encode_task(ids.task_list_key(store.uri), PARENT_NAME)


async def create(clients: NcClients, body: str | None = ONE_OWN, **kwargs: Any) -> Any:
    """Create into a fresh mock; answer and stores come back together."""
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, body)
        result = await tasks_tools.create_task(clients, **kwargs)
    return result, stores


def due_lines(body: str) -> list[str]:
    return [line for line in body.split("\r\n") if line.startswith("DUE")]


# --- Refusals before any request ------------------------------------------------------------


REFUSED = [
    pytest.param({"summary": ""}, id="summary-empty"),
    pytest.param({"summary": "   "}, id="summary-blank"),
    pytest.param({"summary": "t", "priority": -1}, id="priority-minus-one"),
    pytest.param({"summary": "t", "priority": 10}, id="priority-ten"),
    pytest.param({"summary": "t", "due": "2026-11-20T09:00:00"}, id="due-without-zone"),
    pytest.param({"summary": "t", "due": "2026-13-01"}, id="due-not-a-date"),
    pytest.param({"summary": "t", "due": "tomorrow"}, id="due-garbage"),
    pytest.param(
        {"summary": "t", "due": "2026-11-20T09:00:00+01:00", "timezone": "Mars/Olympus"},
        id="timezone-unknown",
    ),
    pytest.param({"summary": "t", "timezone": "Europe/Berlin"}, id="timezone-without-time"),
    pytest.param(
        {"summary": "t", "due": "2026-11-20", "timezone": "Europe/Berlin"},
        id="timezone-with-a-date-only",
    ),
    pytest.param(
        {"summary": "t", "due": "2026-11-20T09:00:00+01:00", "start": "2026-11-19"},
        id="start-date-due-time",
    ),
    pytest.param(
        {"summary": "t", "due": "2026-11-20", "start": "2026-11-19T09:00:00+01:00"},
        id="start-time-due-date",
    ),
    pytest.param({"summary": "t", "due": "2026-11-20", "start": "2026-11-20"}, id="start-equal"),
    pytest.param({"summary": "t", "due": "2026-11-20", "start": "2026-11-21"}, id="start-after"),
    pytest.param(
        {
            "summary": "t",
            "due": "2026-11-20T09:00:00+01:00",
            "start": "2026-11-20T08:00:00Z",
        },
        id="start-equal-instant",
    ),
    pytest.param({"summary": "t", "parent": "event:personal:x.ics"}, id="parent-other-kind"),
    pytest.param({"summary": "t", "parent": "not an id"}, id="parent-garbage"),
]


@pytest.mark.anyio
@pytest.mark.parametrize("kwargs", REFUSED)
async def test_invalid_input_is_refused_before_any_request(
    clients: NcClients, kwargs: dict[str, Any]
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        discovery = mock_discovery(mock)
        stores = mock_stores(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, **kwargs)
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert discovery.call_count == 0
    assert puts(stores) == 0


@pytest.mark.anyio
async def test_timezone_without_time_names_the_rule(clients: NcClients) -> None:
    with pytest.raises(ToolError) as caught:
        await tasks_tools.create_task(clients, summary="t", timezone="Europe/Berlin")
    assert "timezone only applies to a due or start with a time" in caught.value.message


@pytest.mark.anyio
async def test_a_parent_in_a_deck_calendar_is_unknown_before_any_request(
    clients: NcClients,
) -> None:
    parent = ids.encode_task("app-generated--deck--board-1", "card.ics")
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", parent=parent)
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert mock.calls.call_count == 0
    assert puts(stores) == 0


@pytest.mark.anyio
@pytest.mark.parametrize("priority", [0, 9])
async def test_priority_zero_and_nine_are_accepted(clients: NcClients, priority: int) -> None:
    result, stores = await create(clients, summary="t", priority=priority)
    assert result["created"] is True
    assert f"PRIORITY:{priority}\r\n" in stores[OWN].body


@pytest.mark.anyio
async def test_start_alone_is_accepted(clients: NcClients) -> None:
    result, stores = await create(clients, summary="t", start="2026-11-19")
    assert "DTSTART;VALUE=DATE:20261119" in stores[OWN].body
    assert result["start"] == "2026-11-19"
    assert "due" not in result


# --- The object on the wire -----------------------------------------------------------------


@pytest.mark.anyio
async def test_a_due_date_is_that_very_day(clients: NcClients) -> None:
    result, stores = await create(clients, summary="t", due="2026-11-20")
    body = stores[OWN].body
    assert due_lines(body) == ["DUE;VALUE=DATE:20261120"]
    assert "20261121" not in body
    assert result["due"] == "2026-11-20"


@pytest.mark.anyio
async def test_a_due_with_zone_and_no_timezone_is_written_in_utc(clients: NcClients) -> None:
    result, stores = await create(clients, summary="t", due="2026-11-20T09:00:00+01:00")
    assert due_lines(stores[OWN].body) == ["DUE:20261120T080000Z"]
    assert "VTIMEZONE" not in stores[OWN].body
    assert result["due"] == "2026-11-20T08:00:00+00:00"
    assert "due_floating" not in result


@pytest.mark.anyio
async def test_a_named_timezone_is_written_with_its_vtimezone(clients: NcClients) -> None:
    result, stores = await create(
        clients,
        summary="t",
        due="2026-11-20T09:00:00+01:00",
        start="2026-11-19T08:00:00Z",
        timezone="Europe/Berlin",
    )
    body = stores[OWN].body
    assert due_lines(body) == ["DUE;TZID=Europe/Berlin:20261120T090000"]
    assert "DTSTART;TZID=Europe/Berlin:20261119T090000" in body
    assert body.count("BEGIN:VTIMEZONE") == 1
    assert "TZID:Europe/Berlin" in body
    assert result["due"] == "2026-11-20T09:00:00+01:00"


@pytest.mark.anyio
async def test_tags_are_one_line_without_empties_and_duplicates(clients: NcClients) -> None:
    result, stores = await create(clients, summary="t", tags=["a,b", "wichtig", "", "Wichtig"])
    lines = [line for line in stores[OWN].body.split("\r\n") if line.startswith("CATEGORIES")]
    assert lines == ["CATEGORIES:a\\,b,wichtig"]
    assert result["created"] is True


@pytest.mark.anyio
async def test_summary_with_line_break_comma_and_semicolon_is_escaped(
    clients: NcClients,
) -> None:
    summary = "x\r\nEND:VTODO\r\nBEGIN:VTODO\r\nSUMMARY:evil, a; b"
    result, stores = await create(clients, summary=summary, description="d\nEND:VCALENDAR")
    body = stores[OWN].body
    lines = body.split("\r\n")
    for marker in ("BEGIN:VTODO", "END:VTODO", "BEGIN:VCALENDAR", "END:VCALENDAR"):
        assert lines.count(marker) == 1, marker
    assert [component.name for component in IcsCalendar.from_ical(body).walk()] == [
        "VCALENDAR",
        "VTODO",
    ]
    assert "\\, a\\; b" in body
    assert result["summary"] == summary


@pytest.mark.anyio
async def test_the_object_carries_the_fields_of_a_new_task(clients: NcClients) -> None:
    result, stores = await create(clients, summary="Angebot", description="Text")
    store = stores[OWN]
    request = store.puts[0]
    body = store.body
    name = unquote(request.url.path.rsplit("/", 1)[-1])
    uid = name.removesuffix(".ics")
    assert name.endswith(".ics")
    assert len(uid) == 36
    assert f"UID:{uid}\r\n" in body
    for prop in ("DTSTAMP:", "CREATED:", "LAST-MODIFIED:", "SUMMARY:Angebot", "DESCRIPTION:Text"):
        assert prop in body, prop
    assert f"PRODID:{calendar_tools.PRODID}" in body
    assert "RELATED-TO" not in body
    assert "CATEGORIES" not in body
    assert result["id"] == ids.encode_task(OWN, name)


@pytest.mark.anyio
async def test_the_put_is_create_only(clients: NcClients) -> None:
    _result, stores = await create(clients, summary="t")
    request = stores[OWN].puts[0]
    assert request.headers["If-None-Match"] == "*"
    assert request.headers["Content-Type"].startswith("text/calendar")


# --- Target list (E4) -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_one_own_writable_list_is_the_target_without_list(clients: NcClients) -> None:
    result, stores = await create(clients, summary="t")
    assert len(stores[OWN].puts) == 1
    assert puts(stores) == 1
    assert result["list"] == {"name": OWN, "shared": False, "writable": True}


@pytest.mark.anyio
async def test_two_own_lists_without_list_is_an_error_with_both_names(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    text = caught.value.message + caught.value.hint
    assert OWN in text
    assert MIXED in text
    assert puts(stores) == 0
    for leak in LEAKS:
        assert leak not in text


@pytest.mark.anyio
async def test_only_shared_lists_without_list_is_an_error_and_writes_nothing(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, ONLY_SHARED)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    text = caught.value.message + caught.value.hint
    assert "spike30-b-rw" in text
    assert "list=" in caught.value.hint
    assert puts(stores) == 0
    for leak in LEAKS:
        assert leak not in text


@pytest.mark.anyio
@pytest.mark.parametrize("wanted", ["spike30-b-rw", ids.task_list_key(SHARED_RW)])
async def test_a_named_writable_shared_list_is_written(clients: NcClients, wanted: str) -> None:
    result, stores = await create(clients, summary="t", list_name=wanted)
    assert len(stores[SHARED_RW].puts) == 1
    assert puts(stores) == 1
    assert result["list"] == {"name": "spike30-b-rw", "shared": True, "writable": True}
    assert result["id"].startswith(f"task:{ids.task_list_key(SHARED_RW)}:")
    dumped = json.dumps(result)
    for leak in LEAKS:
        assert leak not in dumped


@pytest.mark.anyio
async def test_a_named_read_only_list_is_refused_before_the_request(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", list_name="spike30-b-ro")
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert "spike30-b-ro" in caught.value.message
    assert puts(stores) == 0
    for leak in LEAKS:
        assert leak not in caught.value.message + caught.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize(
    "wanted", ["nope", "app-generated--deck--board-1", SHARED_RW], ids=["unknown", "deck", "uri"]
)
async def test_an_unknown_list_names_the_available_ones(clients: NcClients, wanted: str) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", list_name=wanted)
    assert OWN in caught.value.hint
    assert puts(stores) == 0
    for leak in LEAKS:
        assert leak not in caught.value.message + caught.value.hint


@pytest.mark.anyio
async def test_two_shared_lists_with_one_name_need_their_keys(clients: NcClients) -> None:
    body = home(
        home_entry("team_shared_by_bob", "Team", owner="Bob Builder"),
        home_entry("team_shared_by_carol", "Team", owner="Carol Owner"),
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, body)
        put = mock.route(method="PUT").mock(return_value=httpx.Response(201))
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", list_name="team")
    text = caught.value.message + caught.value.hint
    assert ids.task_list_key("team_shared_by_bob") in text
    assert ids.task_list_key("team_shared_by_carol") in text
    assert put.call_count == 0
    for leak in ("bob", "Bob Builder", "carol", "Carol Owner", "_shared_by_"):
        assert leak not in text


# --- Parent (TASK-05, D-32-16) --------------------------------------------------------------


@pytest.mark.anyio
async def test_a_parent_in_a_shared_list_without_list_is_an_error(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        parent = with_parent(stores[SHARED_RW])
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", parent=parent)
    assert "list=" in caught.value.hint
    assert puts(stores) == 0
    for leak in LEAKS:
        assert leak not in caught.value.message + caught.value.hint


@pytest.mark.anyio
async def test_a_parent_in_a_shared_list_with_that_list_named_is_written(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        parent = with_parent(stores[SHARED_RW])
        result = await tasks_tools.create_task(
            clients, summary="t", parent=parent, list_name="spike30-b-rw"
        )
    assert len(stores[SHARED_RW].puts) == 1
    assert f"RELATED-TO:{PARENT_UID}\r\n" in stores[SHARED_RW].body
    assert result["list"]["shared"] is True


@pytest.mark.anyio
async def test_a_parent_in_an_own_list_picks_that_list_among_two(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        parent = with_parent(stores[MIXED])
        result = await tasks_tools.create_task(clients, summary="child", parent=parent)
    assert len(stores[MIXED].puts) == 1
    assert puts(stores) == 1
    body = stores[MIXED].body
    assert f"RELATED-TO:{PARENT_UID}\r\n" in body
    assert "RELTYPE" not in body
    assert result["list"]["name"] == MIXED


@pytest.mark.anyio
async def test_parent_and_list_in_different_lists_is_an_error(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        parent = with_parent(stores[MIXED])
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", parent=parent, list_name=OWN)
    assert "another list" in caught.value.message
    assert puts(stores) == 0


@pytest.mark.anyio
@pytest.mark.parametrize("key", [OWN, "unknown-list"])
async def test_an_unknown_parent_is_an_unknown_id_and_writes_nothing(
    clients: NcClients, key: str
) -> None:
    parent = ids.encode_task(key, "missing.ics")
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", parent=parent, list_name=OWN)
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert puts(stores) == 0


# --- Answers of the server to the PUT -------------------------------------------------------


@pytest.mark.anyio
async def test_412_is_a_conflict(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_stores(mock, ONE_OWN, put_status=412)
        with pytest.raises(ConflictError):
            await tasks_tools.create_task(clients, summary="t")


@pytest.mark.anyio
async def test_403_of_the_server_names_the_list_without_its_uri(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_stores(mock, ONE_OWN, put_status=403)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", list_name="spike30-b-rw")
    assert caught.value.reason == REASON_PERMISSION_DENIED
    assert "spike30-b-rw" in caught.value.message
    for leak in LEAKS:
        assert leak not in caught.value.message + caught.value.hint


@pytest.mark.anyio
async def test_404_of_the_server_does_not_claim_the_list_is_gone(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_stores(mock, ONE_OWN, put_status=404)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", list_name="spike30-b-rw")
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert "not found or does not allow writing" in caught.value.message
    for leak in LEAKS:
        assert leak not in caught.value.message + caught.value.hint


# --- Read back ------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_readable_object_with_the_same_uid_is_confirmed(clients: NcClients) -> None:
    result, stores = await create(clients, summary="t")
    assert result["created"] is True
    assert result["confirmed"] is True
    assert len(stores[OWN].gets) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "answer",
    [httpx.Response(500), httpx.ReadTimeout("slow"), httpx.ConnectError("gone")],
    ids=["500", "timeout", "unreachable"],
)
async def test_a_failing_read_back_never_fails_the_write(
    clients: NcClients, answer: httpx.Response | Exception
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, ONE_OWN, get_answer=answer)
        result = await tasks_tools.create_task(clients, summary="t")
    assert result["created"] is True
    assert result["confirmed"] is False
    assert len(stores[OWN].puts) == 1


@pytest.mark.anyio
async def test_another_uid_in_the_read_back_is_not_confirmed(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_stores(mock, ONE_OWN, rewrite_uid=True)
        result = await tasks_tools.create_task(clients, summary="t")
    assert result["created"] is True
    assert result["confirmed"] is False


# --- No task list (E6) ----------------------------------------------------------------------


@pytest.mark.anyio
async def test_an_account_without_a_task_list_gets_an_error_with_a_way_out(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, fixture("caldav_home_fresh_account.xml"))
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert caught.value.message == "This account has no task list."
    assert caught.value.hint == "Create a list in the Nextcloud Tasks app, then try again."
    assert puts(stores) == 0


# --- The answer -----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_answer_has_the_planned_shape_and_read_task_resolves_its_id(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_stores(mock, ONE_OWN)
        mock.route(method="REPORT", url__startswith=CALENDAR_HOME).mock(
            return_value=httpx.Response(
                207,
                text='<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>',
                headers={"Content-Type": "application/xml"},
            )
        )
        result = await tasks_tools.create_task(
            clients, summary="Angebot", due="2026-11-20", priority=2, tags=["kunde"]
        )
        read = await tasks_tools.read_task(clients, task_id=result["id"])
    assert list(result) == ["id", "summary", "list", "created", "confirmed", "due"]
    assert result["summary"] == "Angebot"
    assert read["id"] == result["id"]
    assert read["summary"] == "Angebot"
    assert read["due"] == "2026-11-20"
    assert read["priority"] == 2
    assert read["tags"] == ["kunde"]


# --- D-32-18 (plan 32-09): an own list shared with others is only written to when named ------

#: The measured mark of an own list the account shares itself: ``oc:invite`` with one user.
SHARED_OUT_INVITE = (
    "<oc:invite><oc:user><d:href>principal:principals/users/sharee</d:href>"
    "<oc:common-name>Sharee</oc:common-name><oc:invite-accepted/>"
    "<oc:access><oc:read/></oc:access></oc:user></oc:invite>"
)
OUT_LEAKS = ("sharee", "Sharee", "principal", "_shared_by_")


def shared_out_entry(uri: str, name: str) -> str:
    """An own list whose ``oc:invite`` names one sharee, as measured in plan 32-09."""
    return home_entry(uri, name).replace("<oc:invite/>", SHARED_OUT_INVITE)


#: The only own writable list is shared with others, plus the two shares of bob.
ONE_OWN_SHARED_OUT = home(
    shared_out_entry(OWN, OWN),
    home_entry(SHARED_RW, "spike30-b-rw", owner="bob"),
    home_entry(SHARED_RO, "spike30-b-ro", owner="bob", writable=False),
)


def assert_names_nobody(error: ToolError) -> None:
    text = error.message + error.hint
    for leak in (*LEAKS, *OUT_LEAKS):
        assert leak not in text, leak


@pytest.mark.anyio
async def test_the_only_own_list_shared_with_others_is_no_default_target(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, ONE_OWN_SHARED_OUT)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert "shared with others" in caught.value.message
    assert OWN in caught.value.message
    assert f"list={OWN}" in caught.value.hint or "list=<name>" in caught.value.hint
    assert OWN in caught.value.hint
    assert puts(stores) == 0
    assert_names_nobody(caught.value)


@pytest.mark.anyio
async def test_the_own_list_shared_with_others_is_written_when_named(clients: NcClients) -> None:
    result, stores = await create(clients, ONE_OWN_SHARED_OUT, summary="t", list_name=OWN)
    assert len(stores[OWN].puts) == 1
    assert result["list"] == {"name": OWN, "shared": False, "writable": True}


@pytest.mark.anyio
async def test_two_own_lists_one_shared_with_others_stay_more_than_one(
    clients: NcClients,
) -> None:
    body = home(shared_out_entry(OWN, OWN), home_entry(MIXED, MIXED))
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, body)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert "more than one task list" in caught.value.message
    assert puts(stores) == 0
    assert_names_nobody(caught.value)


@pytest.mark.anyio
async def test_an_unshared_own_list_beside_a_share_of_bob_is_still_the_target(
    clients: NcClients,
) -> None:
    result, stores = await create(clients, ONE_OWN, summary="t")
    assert len(stores[OWN].puts) == 1
    assert result["list"]["shared"] is False


@pytest.mark.anyio
async def test_an_own_list_without_a_readable_share_state_counts_as_shared(
    clients: NcClients,
) -> None:
    """Point 6: the measured property missing from the 2xx propstat means "maybe shared"."""
    body = home(home_entry(OWN, OWN).replace("<oc:invite/>", ""))
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, body)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert "shared with others" in caught.value.message
    assert puts(stores) == 0


@pytest.mark.anyio
async def test_a_published_own_list_counts_as_shared_with_others(clients: NcClients) -> None:
    published = home_entry(OWN, OWN).replace(
        "<oc:invite/>",
        "<oc:invite/><cs:publish-url><d:href>https://nc.test/public/TOKEN</d:href>"
        "</cs:publish-url>",
    )
    body = home(published).replace(
        'xmlns:x1="http://nextcloud.com/ns"',
        'xmlns:x1="http://nextcloud.com/ns" xmlns:cs="http://calendarserver.org/ns/"',
    )
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, body)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert "shared with others" in caught.value.message
    assert "TOKEN" not in caught.value.message + caught.value.hint
    assert puts(stores) == 0


@pytest.mark.anyio
async def test_a_parent_in_an_own_list_shared_with_others_does_not_name_it(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, ONE_OWN_SHARED_OUT)
        parent = with_parent(stores[OWN])
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", parent=parent)
    assert "shared with others" in caught.value.message
    assert f"list={OWN!r}" in caught.value.hint
    assert puts(stores) == 0
    assert stores[OWN].gets == []
    assert_names_nobody(caught.value)


@pytest.mark.anyio
async def test_a_parent_in_an_own_list_shared_with_others_is_written_when_named(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        stores = mock_stores(mock, ONE_OWN_SHARED_OUT)
        parent = with_parent(stores[OWN])
        await tasks_tools.create_task(clients, summary="t", parent=parent, list_name=OWN)
    assert len(stores[OWN].puts) == 1
    assert f"RELATED-TO:{PARENT_UID}\r\n" in stores[OWN].body


# --------------------------------------------------------------------------------------
# Plan 32-10: D-32-18, E4 and D-32-16 for group shares, on the measured discovery of
# Nextcloud 35 (tests/fixtures/caldav_home_group_share.xml). Regression tests.
# --------------------------------------------------------------------------------------

GROUP_OUT_RO, GROUP_OUT_RW, GROUP_PRIVATE = "p3210-aus-ro", "p3210-aus-rw", "p3210-privat"
GROUP_IN_RW = "p3210-rein-rw_shared_by_sharee"
GROUP_IN_RO = "p3210-rein-ro_shared_by_sharee"
GROUP_LEAKS = ("testgroup", "sharee", "Sharee", "_shared_by_", "principal")


def group_home(*keep: str) -> str:
    """The measured discovery with the home and only the lists named in ``keep``."""
    root = etree.fromstring(fixture("caldav_home_group_share.xml").encode("utf-8"))
    for response in list(root.findall("{DAV:}response")):
        href = (response.findtext("{DAV:}href") or "").rstrip("/")
        uri = unquote(href.rsplit("/", 1)[-1])
        if href != HOME_PATH.rstrip("/") and uri not in keep:
            root.remove(response)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8").decode("utf-8")


def group_stores(mock: respx.MockRouter, body: str, *uris: str) -> dict[str, Store]:
    mock_discovery(mock, body)
    stores: dict[str, Store] = {}
    for uri in uris:
        store = Store(uri)
        mock.route(method="PUT", url__startswith=list_url(uri)).mock(side_effect=store.put)
        mock.route(method="GET", url__startswith=list_url(uri)).mock(side_effect=store.get)
        stores[uri] = store
    return stores


def assert_names_no_group(error: ToolError) -> None:
    text = error.message + error.hint
    for leak in GROUP_LEAKS:
        assert leak not in text, leak


@pytest.mark.anyio
@pytest.mark.parametrize("own", [GROUP_OUT_RO, GROUP_OUT_RW])
async def test_the_only_own_list_shared_with_a_group_is_no_default_target(
    clients: NcClients, own: str
) -> None:
    uris = (own, GROUP_IN_RW, GROUP_IN_RO)
    with respx.mock(assert_all_called=False) as mock:
        stores = group_stores(mock, group_home(*uris), *uris)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert "shared with others" in caught.value.message
    assert "list=" in caught.value.hint
    assert puts(stores) == 0
    assert_names_no_group(caught.value)


@pytest.mark.anyio
async def test_an_own_list_after_the_group_share_is_taken_back_is_the_target_again(
    clients: NcClients,
) -> None:
    uris = (GROUP_PRIVATE, GROUP_IN_RW, GROUP_IN_RO)
    with respx.mock(assert_all_called=False) as mock:
        stores = group_stores(mock, group_home(*uris), *uris)
        result = await tasks_tools.create_task(clients, summary="t")
    assert len(stores[GROUP_PRIVATE].puts) == 1
    assert puts(stores) == 1
    assert result["list"] == {"name": GROUP_PRIVATE, "shared": False, "writable": True}


@pytest.mark.anyio
async def test_a_list_shared_in_through_a_group_is_written_when_named(
    clients: NcClients,
) -> None:
    uris = (GROUP_OUT_RO, GROUP_IN_RW, GROUP_IN_RO)
    with respx.mock(assert_all_called=False) as mock:
        stores = group_stores(mock, group_home(*uris), *uris)
        result = await tasks_tools.create_task(clients, summary="t", list_name="p3210-rein-rw")
    assert len(stores[GROUP_IN_RW].puts) == 1
    assert puts(stores) == 1
    assert result["list"] == {"name": "p3210-rein-rw", "shared": True, "writable": True}
    assert "sharee" not in json.dumps(result).casefold()


@pytest.mark.anyio
async def test_a_parent_in_a_list_shared_in_through_a_group_does_not_name_it(
    clients: NcClients,
) -> None:
    uris = (GROUP_PRIVATE, GROUP_IN_RW, GROUP_IN_RO)
    with respx.mock(assert_all_called=False) as mock:
        stores = group_stores(mock, group_home(*uris), *uris)
        parent = with_parent(stores[GROUP_IN_RW])
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", parent=parent)
    assert "list=" in caught.value.hint
    assert puts(stores) == 0
    assert_names_no_group(caught.value)


@pytest.mark.anyio
async def test_a_read_only_list_shared_in_through_a_group_is_refused_before_the_put(
    clients: NcClients,
) -> None:
    uris = (GROUP_PRIVATE, GROUP_IN_RW, GROUP_IN_RO)
    with respx.mock(assert_all_called=False) as mock:
        stores = group_stores(mock, group_home(*uris), *uris)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t", list_name="p3210-rein-ro")
    assert puts(stores) == 0
    assert_names_no_group(caught.value)


@pytest.mark.anyio
async def test_the_hint_names_the_group_share_by_name_and_key_only(clients: NcClients) -> None:
    """Without list and with the own list shared with a group, the writable lists are named:
    the share into the account as ``<name> (shared, key <key>)``, never with its owner."""
    uris = (GROUP_OUT_RW, GROUP_IN_RW, GROUP_IN_RO)
    with respx.mock(assert_all_called=False) as mock:
        stores = group_stores(mock, group_home(*uris), *uris)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert f"p3210-rein-rw (shared, key {ids.task_list_key(GROUP_IN_RW)})" in caught.value.hint
    assert "p3210-rein-ro" not in caught.value.hint
    assert puts(stores) == 0
    assert_names_no_group(caught.value)

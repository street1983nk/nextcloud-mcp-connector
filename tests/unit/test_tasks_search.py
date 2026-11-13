"""Unit tests for ``tasks_search``, every path without a network.

The discovery is the recorded home of the spike (``caldav_home_task_lists.xml``): two own
lists (``spike30-aufgaben``, ``spike30-gemischt``), two lists shared by ``bob`` (one writable,
one read only), two Deck calendars and every kind that must drop out. The objects of each
list are built by hand as Multi-Status answers.

Pinned here: the status filter (D-32-09), the server prefilter and the second REPORT for a
missing parent (D-32-04, variant V-B), the text and due filters, the order, the paging with
its scope and ceiling (D-32-08), the budget per list with ``degraded``, the skipped objects,
the list resolution (D-32-05, D-32-14), the empty account (E6), and that neither the account
id nor the name of the person who shared a list reaches any answer (D-32-06).
"""

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape

import httpx
import pytest
import respx

from mcp_connector import ids
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import tasks as tasks_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
HOME_PATH = "/remote.php/dav/calendars/alice/"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

OWNER = "bob"
OWN = "spike30-aufgaben"
MIXED = "spike30-gemischt"
SHARED_RW = "spike30-b-rw_shared_by_bob"
SHARED_RO = "spike30-b-ro_shared_by_bob"
ALL_LISTS = (OWN, MIXED, SHARED_RW, SHARED_RO)

PREFILTER = b"is-not-defined"


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


def multistatus(uri: str, objects: list[tuple[str, str]]) -> httpx.Response:
    entries = "".join(
        f"<d:response><d:href>{HOME_PATH}{quote(uri, safe='')}/{quote(name, safe=':')}</d:href>"
        '<d:propstat><d:prop><d:getetag>"1"</d:getetag>'
        f"<cal:calendar-data>{escape(ics)}</cal:calendar-data></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for name, ics in objects
    )
    body = (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        f'xmlns:cal="urn:ietf:params:xml:ns:caldav">{entries}</d:multistatus>'
    )
    return httpx.Response(207, text=body, headers={"Content-Type": "application/xml"})


def task(uid: str, summary: str, *lines: str) -> tuple[str, str]:
    """One object whose name is its UID plus ``.ics``, like the Tasks app writes it."""
    return f"{uid}.ics", vtodo(uid, summary, *lines)


def mock_discovery(mock: respx.MockRouter, body: str | None = None) -> respx.Route:
    return mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
        return_value=httpx.Response(
            207,
            text=body if body is not None else fixture("caldav_home_task_lists.xml"),
            headers={"Content-Type": "application/xml"},
        )
    )


class ListServer:
    """Answers the REPORT of one list like sabre: the prefilter drops objects with COMPLETED."""

    def __init__(self, uri: str, objects: list[tuple[str, str]]) -> None:
        self.uri = uri
        self.objects = objects
        self.bodies: list[bytes] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(request.content)
        objects = self.objects
        if PREFILTER in request.content:
            objects = [(name, ics) for name, ics in objects if "\r\nCOMPLETED" not in ics]
        return multistatus(self.uri, objects)


def mock_lists(
    mock: respx.MockRouter, **objects: list[tuple[str, str]]
) -> dict[str, tuple[ListServer, respx.Route]]:
    """One REPORT route per list of the fixture; keyword names use ``_`` for ``-``."""
    mock_discovery(mock)
    servers: dict[str, tuple[ListServer, respx.Route]] = {}
    for uri in ALL_LISTS:
        server = ListServer(uri, objects.get(uri.replace("-", "_"), []))
        route = mock.route(method="REPORT", url=list_url(uri)).mock(side_effect=server)
        servers[uri] = (server, route)
    return servers


def summaries(result: dict[str, Any]) -> list[str]:
    return [hit["summary"] for hit in result["tasks"]]


MIXED_STATUS = [
    task("t-open", "open one"),
    task("t-progress", "in progress", "STATUS:IN-PROCESS"),
    task("t-done", "done", "STATUS:COMPLETED", "COMPLETED:20261112T100000Z"),
    task("t-cancel", "cancelled", "STATUS:CANCELLED"),
]


# --- Status filter ------------------------------------------------------------------------


@pytest.mark.anyio
async def test_default_status_is_open_and_in_progress(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=MIXED_STATUS)
        result = await tasks_tools.search_tasks(clients)
    assert sorted(summaries(result)) == ["in progress", "open one"]
    statuses = {hit["summary"]: hit["status"] for hit in result["tasks"]}
    assert statuses == {"open one": "open", "in progress": "in_progress"}


@pytest.mark.anyio
async def test_status_completed_returns_only_completed(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=MIXED_STATUS)
        result = await tasks_tools.search_tasks(clients, status="completed")
    assert summaries(result) == ["done"]
    assert result["tasks"][0]["status"] == "completed"


@pytest.mark.anyio
async def test_status_all_includes_cancelled_and_names_each_status(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=MIXED_STATUS)
        result = await tasks_tools.search_tasks(clients, status="all")
    statuses = {hit["summary"]: hit["status"] for hit in result["tasks"]}
    assert statuses == {
        "open one": "open",
        "in progress": "in_progress",
        "done": "completed",
        "cancelled": "cancelled",
    }


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["foo", "OPEN ", "done", ""])
async def test_unknown_status_is_refused_before_any_request(
    clients: NcClients, status: str
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        discovery = mock_discovery(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.search_tasks(clients, status=status)
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert "open, completed, all" in caught.value.message
    assert discovery.call_count == 0


@pytest.mark.anyio
async def test_open_mode_sends_the_prefilter_and_sorts_out_cancelled(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_aufgaben=MIXED_STATUS)
        result = await tasks_tools.search_tasks(clients)
    server, _route = servers[OWN]
    assert len(server.bodies) == 1
    assert PREFILTER in server.bodies[0]
    assert b'name="COMPLETED"' in server.bodies[0]
    assert "cancelled" not in summaries(result)


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["completed", "all"])
async def test_completed_and_all_send_no_prefilter(clients: NcClients, status: str) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_aufgaben=MIXED_STATUS)
        await tasks_tools.search_tasks(clients, status=status)
    for server, _route in servers.values():
        assert len(server.bodies) == 1
        assert b"COMPLETED" not in server.bodies[0]


# --- Parent references (D-32-04, V-B) -----------------------------------------------------


@pytest.mark.anyio
async def test_open_child_of_a_completed_parent_costs_exactly_one_more_report(
    clients: NcClients,
) -> None:
    objects = [
        task("p-1", "parent done", "STATUS:COMPLETED", "COMPLETED:20261112T100000Z"),
        task("c-1", "child open", "RELATED-TO:p-1"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients)
    server, _route = servers[OWN]
    assert len(server.bodies) == 2
    assert PREFILTER in server.bodies[0]
    assert PREFILTER not in server.bodies[1]
    for other in (MIXED, SHARED_RW, SHARED_RO):
        assert len(servers[other][0].bodies) == 1
    assert summaries(result) == ["child open"]
    assert result["tasks"][0]["parent"] == {
        "id": ids.encode_task(OWN, "p-1.ics"),
        "summary": "parent done",
    }


@pytest.mark.anyio
async def test_parent_present_in_the_first_answer_needs_no_second_report(
    clients: NcClients,
) -> None:
    objects = [task("p-1", "parent open"), task("c-1", "child open", "RELATED-TO:p-1")]
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients)
    assert len(servers[OWN][0].bodies) == 1
    by_summary = {hit["summary"]: hit for hit in result["tasks"]}
    assert by_summary["child open"]["parent"]["summary"] == "parent open"
    assert "parent" not in by_summary["parent open"]


@pytest.mark.anyio
async def test_parent_in_no_answer_is_found_false(clients: NcClients) -> None:
    objects = [task("c-1", "orphan", "RELATED-TO:nowhere")]
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients)
    assert len(servers[OWN][0].bodies) == 2
    assert result["tasks"][0]["parent"] == {"found": False}


@pytest.mark.anyio
async def test_child_and_parent_are_hits_of_their_own_without_grouping(clients: NcClients) -> None:
    objects = [
        task("p-1", "parent", "STATUS:COMPLETED", "COMPLETED:20261112T100000Z"),
        task("c-1", "child", "RELATED-TO:p-1"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients, status="all")
    assert summaries(result) == ["child", "parent"]
    assert "subtasks" not in json.dumps(result)


# --- Text filter --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_query_is_casefolded_over_summary_description_and_tags(clients: NcClients) -> None:
    objects = [
        task("a", "Bericht schreiben"),
        task("b", "other", "DESCRIPTION:den BERICHT lesen"),
        task("c", "third", "CATEGORIES:x,berichte"),
        task("d", "unrelated", "DESCRIPTION:nothing"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients, query="BERICHT")
    assert sorted(summaries(result)) == ["Bericht schreiben", "other", "third"]
    dumped = json.dumps(result)
    assert "den BERICHT lesen" not in dumped
    assert "description" not in dumped


# --- Due filter ---------------------------------------------------------------------------

DUE_OBJECTS = [
    task("d-date", "date", "DUE;VALUE=DATE:20261120"),
    task("d-utc", "utc", "DUE:20261120T230000Z"),
    task("d-zoned", "zoned", "DUE;TZID=Europe/Berlin:20261121T003000"),
    task("d-float", "float", "DUE:20261120T090000"),
    task("d-float2", "float2", "DUE:20261121T000500"),
    task("d-late", "late", "DUE;VALUE=DATE:20261121"),
    task("d-none", "undated"),
]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("due_by", "expected"),
    [
        ("2026-11-20", {"date", "utc", "float"}),
        ("2026-11-20T23:15:00+00:00", {"date", "utc", "float"}),
        ("2026-11-20T23:45:00Z", {"date", "utc", "zoned", "float"}),
        ("2026-11-21T00:10:00+01:00", {"date", "utc", "float", "float2", "late"}),
    ],
)
async def test_due_by_follows_the_rules_and_never_returns_undated(
    clients: NcClients, due_by: str, expected: set[str]
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=DUE_OBJECTS)
        result = await tasks_tools.search_tasks(clients, due_by=due_by)
    assert set(summaries(result)) == expected


@pytest.mark.anyio
@pytest.mark.parametrize("due_by", ["tomorrow", "2026-11-20T09:00:00", "2026-13-40"])
async def test_invalid_due_by_is_refused_before_any_request(
    clients: NcClients, due_by: str
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        discovery = mock_discovery(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.search_tasks(clients, due_by=due_by)
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert discovery.call_count == 0


# --- Order --------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_order_status_then_due_then_summary_then_id(clients: NcClients) -> None:
    objects = [
        task("o-cancel", "cancel early", "STATUS:CANCELLED", "DUE;VALUE=DATE:20200101"),
        task("o-done", "done early", "COMPLETED:20261112T100000Z", "DUE;VALUE=DATE:20200101"),
        task("o-beta", "beta"),
        task("o-alpha", "Alpha"),
        task("o-time", "time on the 20th", "DUE:20261120T000000Z"),
        task("o-date", "date on the 20th", "DUE;VALUE=DATE:20261120"),
        task("o-19", "on the 19th", "STATUS:IN-PROCESS", "DUE;TZID=Europe/Berlin:20261119T100000"),
        task("o-twin-b", "twin", "DUE;VALUE=DATE:20261125"),
        task("o-twin-a", "twin", "DUE;VALUE=DATE:20261125"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients, status="all")
    assert summaries(result) == [
        "on the 19th",
        "date on the 20th",
        "time on the 20th",
        "twin",
        "twin",
        "Alpha",
        "beta",
        "done early",
        "cancel early",
    ]
    twins = [hit["id"] for hit in result["tasks"] if hit["summary"] == "twin"]
    assert twins == sorted(twins)


# --- Paging and the ceiling (D-32-08) -------------------------------------------------------

SIXTY = [task(f"p-{number:02d}", f"task {number:02d}") for number in range(60)]


@pytest.mark.anyio
async def test_sixty_hits_are_three_pages_of_25_25_and_10(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=SIXTY)
        first = await tasks_tools.search_tasks(clients)
        second = await tasks_tools.search_tasks(clients, cursor=first["next"])
        third = await tasks_tools.search_tasks(clients, cursor=second["next"])
    assert len(first["tasks"]) == 25
    assert first["truncated"] is True
    assert len(second["tasks"]) == 25
    assert len(third["tasks"]) == 10
    assert "next" not in third
    assert "truncated" not in third
    seen = summaries(first) + summaries(second) + summaries(third)
    assert seen == [f"task {number:02d}" for number in range(60)]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changed",
    [
        {"query": "task"},
        {"status": "all"},
        {"due_by": "2026-11-20"},
        {"list_name": OWN},
    ],
)
async def test_a_cursor_with_another_scope_is_refused(
    clients: NcClients, changed: dict[str, str]
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=SIXTY)
        first = await tasks_tools.search_tasks(clients)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.search_tasks(clients, cursor=first["next"], **changed)
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert "different" in caught.value.message


@pytest.mark.anyio
async def test_the_ceiling_stops_paging_with_an_honest_note(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tasks_tools, "MAX_RESULTS", 50)
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=SIXTY)
        first = await tasks_tools.search_tasks(clients)
        second = await tasks_tools.search_tasks(clients, cursor=first["next"])
    assert len(second["tasks"]) == 25
    assert second["truncated"] is True
    assert "next" not in second
    assert "capped at" in second["note"]
    assert "query, list or due_by" in second["note"]


def test_limit_policy_constants_are_the_measured_values() -> None:
    """Page 25 (D-32-08), ceiling and budget from plan 32-02, each with its measuring line."""
    assert tasks_tools.PAGE_SIZE == 25
    assert tasks_tools.MAX_RESULTS == 500
    assert tasks_tools.PER_LIST_TIMEOUT == 1
    assert tasks_tools.SUBTASK_TIMEOUT == 1
    source = inspect.getsource(tasks_tools)
    assert "MESSWERT per_list_timeout_s=1" in source
    assert "MESSWERT subtask_timeout_s=1" in source
    assert "MESSWERT max_results=500" in source
    assert tasks_tools.SEARCH_CAP_NOTE == (
        "result window capped at 500 tasks; narrow with query, list or due_by"
    )


def test_page_size_is_no_parameter() -> None:
    parameters = inspect.signature(tasks_tools.search_tasks).parameters
    assert "limit" not in parameters
    assert set(parameters) == {"clients", "query", "status", "due_by", "list_name", "cursor"}


# --- Budget, degraded, skipped ------------------------------------------------------------


@pytest.mark.anyio
async def test_a_list_over_its_budget_is_degraded_and_the_others_stay(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tasks_tools.tasks_client.query_todos

    async def slow(client: Any, creds: Any, task_list: Any, body: bytes) -> Any:
        if task_list.uri == SHARED_RW:
            await asyncio.sleep(5)
        return await original(client, creds, task_list, body)

    monkeypatch.setattr(tasks_tools.tasks_client, "query_todos", slow)
    monkeypatch.setattr(tasks_tools, "PER_LIST_TIMEOUT", 0.05)
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=[task("a", "own task")])
        result = await tasks_tools.search_tasks(clients)
    assert summaries(result) == ["own task"]
    assert result["degraded"] == [
        {"list": "spike30-b-rw", "reason": result["degraded"][0]["reason"]}
    ]
    assert "did not answer" in result["degraded"][0]["reason"]
    assert OWNER not in json.dumps(result)


@pytest.mark.anyio
async def test_a_transport_timeout_degrades_one_list(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_aufgaben=[task("a", "own task")])
        servers[MIXED][1].mock(side_effect=httpx.ReadTimeout("slow"))
        result = await tasks_tools.search_tasks(clients)
    assert summaries(result) == ["own task"]
    assert [entry["list"] for entry in result["degraded"]] == [MIXED]


@pytest.mark.anyio
async def test_a_server_error_degrades_with_the_name_without_owner(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock)
        servers[SHARED_RO][1].mock(side_effect=None, return_value=httpx.Response(503))
        result = await tasks_tools.search_tasks(clients)
    assert result["tasks"] == []
    assert result["degraded"][0]["list"] == "spike30-b-ro"
    assert OWNER not in json.dumps(result)


@pytest.mark.anyio
async def test_every_list_failing_is_an_error(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock)
        for uri in ALL_LISTS:
            mock.route(method="REPORT", url=list_url(uri)).mock(return_value=httpx.Response(500))
        with pytest.raises(ToolError) as caught:
            await tasks_tools.search_tasks(clients)
    assert caught.value.message == "None of the task lists could be read."
    assert OWNER not in caught.value.message + caught.value.hint


@pytest.mark.anyio
async def test_an_unexpected_failure_stays_loud(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_args: Any) -> Any:
        raise RuntimeError("bug")

    monkeypatch.setattr(tasks_tools.tasks_client, "query_todos", broken)
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock)
        with pytest.raises(RuntimeError):
            await tasks_tools.search_tasks(clients)


@pytest.mark.anyio
async def test_unaddressable_objects_are_skipped_and_counted(clients: NcClients) -> None:
    objects = [
        task("good-1", "good one"),
        ("broken.ics", "this is not icalendar"),
        (
            "event.ics",
            (
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:x\r\nBEGIN:VEVENT\r\nUID:e\r\n"
                "DTSTART:20261120T090000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
            ),
        ),
        ("a:b.ics", vtodo("colon", "colon in name")),
        task("good-2", "good two"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients)
    assert summaries(result) == ["good one", "good two"]
    assert result["skipped"] == 3


@pytest.mark.anyio
async def test_a_recurring_task_is_one_hit_without_expansion(clients: NcClients) -> None:
    objects = [task("r-1", "daily", "DUE:20261120T130000Z", "RRULE:FREQ=DAILY")]
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients)
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["recurring"] is True
    assert result["tasks"][0]["due"] == "2026-11-20T13:00:00+00:00"


# --- Hit shape and shared lists (D-32-05, D-32-06, D-32-07, D-32-14) ------------------------


@pytest.mark.anyio
async def test_a_hit_carries_the_fields_of_d_32_07_and_never_the_description(
    clients: NcClients,
) -> None:
    objects = [
        task(
            "full",
            "full task",
            "DESCRIPTION:secret body",
            "DUE:20261120T091500Z",
            "DTSTART:20261119T080000Z",
            "PRIORITY:3",
            "CATEGORIES:a,b",
        )
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock, spike30_aufgaben=objects)
        result = await tasks_tools.search_tasks(clients)
    assert result["tasks"] == [
        {
            "id": ids.encode_task(OWN, "full.ics"),
            "summary": "full task",
            "status": "open",
            "due": "2026-11-20T09:15:00+00:00",
            "start": "2026-11-19T08:00:00+00:00",
            "priority": 3,
            "tags": ["a", "b"],
            "list": {"name": OWN, "shared": False, "writable": True},
        }
    ]
    assert "secret body" not in json.dumps(result)


@pytest.mark.anyio
async def test_without_list_own_and_shared_lists_are_searched_without_the_owner(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(
            mock,
            spike30_aufgaben=[task("o", "own")],
            spike30_b_rw_shared_by_bob=[task("s", "shared rw")],
            spike30_b_ro_shared_by_bob=[task("r", "shared ro")],
        )
        result = await tasks_tools.search_tasks(clients)
    assert all(route.call_count == 1 for _server, route in servers.values())
    by_summary = {hit["summary"]: hit for hit in result["tasks"]}
    assert by_summary["own"]["list"] == {"name": OWN, "shared": False, "writable": True}
    assert by_summary["shared rw"]["list"] == {
        "name": "spike30-b-rw",
        "shared": True,
        "writable": True,
    }
    assert by_summary["shared ro"]["list"] == {
        "name": "spike30-b-ro",
        "shared": True,
        "writable": False,
    }
    key = ids.task_list_key(SHARED_RW)
    assert by_summary["shared rw"]["id"] == ids.encode_task(key, "s.ics")
    dumped = json.dumps(result)
    assert OWNER not in dumped.casefold()
    assert "_shared_by_" not in dumped


# --- Resolving the list parameter -------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "wanted",
    [OWN, OWN.upper(), " spike30-aufgaben "],
)
async def test_list_resolves_by_own_uri_or_name(clients: NcClients, wanted: str) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_aufgaben=[task("a", "own")])
        result = await tasks_tools.search_tasks(clients, list_name=wanted)
    assert summaries(result) == ["own"]
    assert servers[OWN][1].call_count == 1
    assert all(servers[uri][1].call_count == 0 for uri in (MIXED, SHARED_RW, SHARED_RO))


@pytest.mark.anyio
@pytest.mark.parametrize("wanted", [ids.task_list_key(SHARED_RW), "SPIKE30-B-RW"])
async def test_list_resolves_a_shared_list_by_key_or_name(clients: NcClients, wanted: str) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock, spike30_b_rw_shared_by_bob=[task("s", "shared")])
        result = await tasks_tools.search_tasks(clients, list_name=wanted)
    assert summaries(result) == ["shared"]
    assert servers[OWN][1].call_count == 0


@pytest.mark.anyio
async def test_unknown_list_names_the_available_lists_without_the_owner(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        servers = mock_lists(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.search_tasks(clients, list_name="nope")
    text = caught.value.message + caught.value.hint
    for name in (OWN, MIXED, "spike30-b-rw", "spike30-b-ro"):
        assert name in caught.value.hint
    assert "_shared_by_" not in text
    assert all(route.call_count == 0 for _server, route in servers.values())


@pytest.mark.anyio
async def test_the_uri_of_a_shared_list_does_not_resolve(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.search_tasks(clients, list_name=SHARED_RW)
    assert OWNER not in (caught.value.message + caught.value.hint)


@pytest.mark.anyio
async def test_a_deck_uri_is_unknown_and_deck_is_never_asked(clients: NcClients) -> None:
    deck = "app-generated--deck--board-1"
    with respx.mock(assert_all_called=False) as mock:
        mock_lists(mock)
        deck_route = mock.route(method="REPORT", url=list_url(deck)).mock(
            return_value=multistatus(deck, [])
        )
        with pytest.raises(ToolError):
            await tasks_tools.search_tasks(clients, list_name=deck)
    assert deck_route.call_count == 0


def two_shared_lists_named_team() -> str:
    def entry(uri: str, owner: str) -> str:
        return (
            f"<d:response><d:href>{HOME_PATH}{uri}/</d:href><d:propstat><d:prop>"
            "<d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>"
            f"<d:displayname>Team ({owner})</d:displayname>"
            '<cal:supported-calendar-component-set><cal:comp name="VTODO"/>'
            "</cal:supported-calendar-component-set>"
            "<d:current-user-privilege-set><d:privilege><d:read/></d:privilege>"
            "</d:current-user-privilege-set><oc:read-only>1</oc:read-only>"
            f"<x1:owner-displayname>{owner}</x1:owner-displayname>"
            "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        )

    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        'xmlns:cal="urn:ietf:params:xml:ns:caldav" xmlns:oc="http://owncloud.org/ns" '
        'xmlns:x1="http://nextcloud.com/ns">'
        + entry("team_shared_by_bob", "Bob Builder")
        + entry("team_shared_by_carol", "Carol Owner")
        + "</d:multistatus>"
    )


@pytest.mark.anyio
async def test_two_shared_lists_with_one_name_are_ambiguous_with_both_keys(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, two_shared_lists_named_team())
        with pytest.raises(ToolError) as caught:
            await tasks_tools.search_tasks(clients, list_name="team")
    text = caught.value.message + caught.value.hint
    assert ids.task_list_key("team_shared_by_bob") in text
    assert ids.task_list_key("team_shared_by_carol") in text
    for leak in ("bob", "Bob Builder", "carol", "Carol Owner", "_shared_by_"):
        assert leak not in text


@pytest.mark.anyio
async def test_shared_lists_named_by_owner_display_name_leak_nothing(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, two_shared_lists_named_team())
        for number, uri in enumerate(("team_shared_by_bob", "team_shared_by_carol")):
            mock.route(method="REPORT", url=list_url(uri)).mock(
                return_value=multistatus(uri, [task(f"t{number}", "team task")])
            )
        result = await tasks_tools.search_tasks(clients)
    assert [hit["list"]["name"] for hit in result["tasks"]] == ["Team", "Team"]
    dumped = json.dumps(result)
    for leak in ("bob", "Bob Builder", "carol", "Carol Owner", "_shared_by_"):
        assert leak not in dumped


# --- An account without a task list (E6) --------------------------------------------------


@pytest.mark.anyio
async def test_an_account_without_a_task_list_gets_an_empty_list_and_a_hint(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, fixture("caldav_home_fresh_account.xml"))
        result = await tasks_tools.search_tasks(clients)
    assert result["tasks"] == []
    assert "Tasks app" in result["hint"]
    assert set(result) == {"tasks", "hint"}


@pytest.mark.anyio
async def test_a_home_that_answers_404_is_the_same_empty_answer(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(return_value=httpx.Response(404))
        result = await tasks_tools.search_tasks(clients)
    assert result["tasks"] == []
    assert "hint" in result

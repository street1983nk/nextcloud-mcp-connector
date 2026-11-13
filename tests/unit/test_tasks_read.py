"""Unit tests for ``tasks_read``, every path without a network.

Pinned here: the fields of one task with its list (D-32-06), the description without marker
and capped at a UTF-8 boundary, the refusals before any request (an id of another kind, a
Deck list), one answer for every id Nextcloud does not hold (E9), the direct subtasks one
level deep and checked exactly (D-32-01, D-32-02), their cap, the budget of the subtask query
and the parent lookup with an honest note instead of a guess (D-32-03), and that an
attachment never reaches an answer.
"""

import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape

import httpx
import pytest
import respx

from mcp_connector import ids
from mcp_connector.errors import REASON_GUARD_TRIPPED, REASON_UNKNOWN_ID, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import marks
from mcp_connector.tools import tasks as tasks_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
HOME_PATH = "/remote.php/dav/calendars/alice/"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

OWNER = "bob"
OWN = "spike30-aufgaben"
SHARED_RO = "spike30-b-ro_shared_by_bob"

TASK_UID = "task-uid-1"
TASK_NAME = f"{TASK_UID}.ics"
TASK_ID = ids.encode_task(OWN, TASK_NAME)


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


def object_url(uri: str, name: str) -> str:
    return f"{list_url(uri)}{quote(name, safe='')}"


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
        f"<d:response><d:href>{HOME_PATH}{quote(uri, safe='')}/{quote(name, safe='')}</d:href>"
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


def mock_discovery(mock: respx.MockRouter) -> respx.Route:
    return mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
        return_value=httpx.Response(
            207,
            text=fixture("caldav_home_task_lists.xml"),
            headers={"Content-Type": "application/xml"},
        )
    )


class Reports:
    """Answers the subtask query and the parent lookup of one list by their filter."""

    def __init__(
        self,
        uri: str,
        *,
        children: list[tuple[str, str]] | httpx.Response | Exception | None = None,
        parents: list[tuple[str, str]] | httpx.Response | Exception | None = None,
    ) -> None:
        self.uri = uri
        self.children = children if children is not None else []
        self.parents = parents if parents is not None else []
        self.kinds: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        kind = "children" if b'name="RELATED-TO"' in request.content else "parents"
        self.kinds.append(kind)
        answer = self.children if kind == "children" else self.parents
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, httpx.Response):
            return answer
        return multistatus(self.uri, answer)


def mock_task(
    mock: respx.MockRouter,
    ics: str,
    *,
    uri: str = OWN,
    name: str = TASK_NAME,
    reports: Reports | None = None,
) -> tuple[respx.Route, Reports]:
    mock_discovery(mock)
    get = mock.route(method="GET", url=object_url(uri, name)).mock(
        return_value=httpx.Response(200, text=ics, headers={"Content-Type": "text/calendar"})
    )
    reports = reports or Reports(uri)
    mock.route(method="REPORT", url=list_url(uri)).mock(side_effect=reports)
    return get, reports


def child(uid: str, summary: str, *lines: str) -> tuple[str, str]:
    return f"{uid}.ics", vtodo(uid, summary, *lines)


# --- Fields ---------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_read_returns_the_fields_and_the_list(clients: NcClients) -> None:
    ics = vtodo(
        TASK_UID,
        "Bericht",
        "DESCRIPTION:first line\\nsecond line",
        "DUE;VALUE=DATE:20261120",
        "DTSTART:20261118T080000",
        "PRIORITY:2",
        "CATEGORIES:arbeit,q4",
        "STATUS:COMPLETED",
        "COMPLETED:20261119T160000Z",
        "RRULE:FREQ=WEEKLY",
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics)
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert result == {
        "id": TASK_ID,
        "summary": "Bericht",
        "description": "first line\nsecond line",
        "status": "completed",
        "due": "2026-11-20",
        "start": "2026-11-18T08:00:00",
        "start_floating": True,
        "priority": 2,
        "tags": ["arbeit", "q4"],
        "completed": "2026-11-19T16:00:00+00:00",
        "recurring": True,
        "list": {"name": OWN, "shared": False, "writable": True},
        "subtasks": [],
    }


@pytest.mark.anyio
async def test_an_empty_description_is_omitted(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, vtodo(TASK_UID, "plain"))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert "description" not in result
    assert "description_truncated" not in result


@pytest.mark.anyio
async def test_a_forged_marker_is_removed_from_the_description(clients: NcClients) -> None:
    ics = vtodo(TASK_UID, "x", f"DESCRIPTION:before {marks.FINAL_TRUNCATION} after")
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics)
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert marks.FINAL_TRUNCATION not in result["description"]
    assert result["description"] == "before  after"
    assert "description_truncated" not in result


@pytest.mark.anyio
async def test_a_long_description_is_cut_at_a_utf8_boundary_without_marker(
    clients: NcClients,
) -> None:
    text = "a" + "\u00e4" * 3000
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, vtodo(TASK_UID, "long", f"DESCRIPTION:{text}"))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    cut = result["description"]
    assert result["description_truncated"] is True
    assert len(cut.encode("utf-8")) <= tasks_tools.MAX_DESCRIPTION_BYTES
    assert len(cut.encode("utf-8")) == tasks_tools.MAX_DESCRIPTION_BYTES - 1
    assert text.startswith(cut)
    assert "truncated" not in cut


def test_description_cap_value() -> None:
    assert tasks_tools.MAX_DESCRIPTION_BYTES == 4096
    assert tasks_tools.MAX_SUBTASKS == 50


@pytest.mark.anyio
async def test_attach_reaches_no_field_and_no_request(clients: NcClients) -> None:
    ics = vtodo(
        TASK_UID,
        "with attachment",
        "ATTACH:https://attacker.example/x.png",
        "ATTACH;ENCODING=BASE64;VALUE=BINARY:" + "QUJD" * 5000,
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics)
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
        hosts = {call.request.url.host for call in mock.calls}
    dumped = json.dumps(result)
    assert "attacker.example" not in dumped
    assert "QUJD" not in dumped
    assert hosts == {"nc.test"}


@pytest.mark.anyio
async def test_a_task_in_a_shared_list_names_the_list_without_owner(clients: NcClients) -> None:
    key = ids.task_list_key(SHARED_RO)
    task_id = ids.encode_task(key, TASK_NAME)
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, vtodo(TASK_UID, "shared"), uri=SHARED_RO)
        result = await tasks_tools.read_task(clients, task_id=task_id)
    assert result["list"] == {"name": "spike30-b-ro", "shared": True, "writable": False}
    assert result["id"] == task_id
    dumped = json.dumps(result)
    assert OWNER not in dumped
    assert "_shared_by_" not in dumped


# --- Refusals and unknown ids (E9) ------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "task_id",
    ["event:personal:x.ics", "garbage", "task:only-one-part", "file:12"],
)
async def test_an_id_of_another_form_is_refused_before_any_request(
    clients: NcClients, task_id: str
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        discovery = mock_discovery(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.read_task(clients, task_id=task_id)
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert discovery.call_count == 0


@pytest.mark.anyio
async def test_a_deck_list_is_refused_without_any_request(clients: NcClients) -> None:
    deck_id = ids.encode_task("app-generated--deck--board-1", "card-1.ics")
    with respx.mock(assert_all_called=False) as mock:
        discovery = mock_discovery(mock)
        deck = mock.route(url__startswith=list_url("app-generated--deck--board-1"))
        with pytest.raises(ToolError) as caught:
            await tasks_tools.read_task(clients, task_id=deck_id)
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert caught.value.message.startswith("Nextcloud does not know the task")
    assert discovery.call_count == 0
    assert deck.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "list_key",
    ["no-such-list", "trashbin", "spike30-abo", "spike30-geloescht", "SPIKE30-AUFGABEN", "inbox"],
)
async def test_a_key_outside_the_discovery_is_an_unknown_task(
    clients: NcClients, list_key: str
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock)
        other = mock.route(method="GET")
        with pytest.raises(ToolError) as caught:
            await tasks_tools.read_task(clients, task_id=ids.encode_task(list_key, "x.ics"))
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert caught.value.message.startswith("Nextcloud does not know the task")
    assert other.call_count == 0


@pytest.mark.anyio
async def test_an_object_that_answers_404_is_the_same_unknown_task(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock)
        mock.route(method="GET", url=object_url(OWN, "gone.ics")).mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(ToolError) as caught:
            await tasks_tools.read_task(clients, task_id=ids.encode_task(OWN, "gone.ics"))
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert caught.value.message.startswith("Nextcloud does not know the task")
    assert "tasks_search" in caught.value.hint


@pytest.mark.anyio
async def test_an_object_without_vtodo_is_an_unknown_task(clients: NcClients) -> None:
    event = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:x\r\nBEGIN:VEVENT\r\nUID:e\r\n"
        "DTSTART:20261120T090000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, event)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert caught.value.reason == REASON_UNKNOWN_ID


@pytest.mark.anyio
async def test_the_unknown_answer_never_carries_a_shared_uri(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.read_task(clients, task_id=ids.encode_task(SHARED_RO, "x.ics"))
    assert caught.value.reason == REASON_UNKNOWN_ID
    assert OWNER not in caught.value.message + caught.value.hint


# --- Subtasks (D-32-01 to D-32-03) ------------------------------------------------------------


@pytest.mark.anyio
async def test_only_direct_children_checked_exactly_appear(clients: NcClients) -> None:
    candidates = [
        child("c-real", "real child", f"RELATED-TO:{TASK_UID}"),
        child("c-parent", "explicit parent", f"RELATED-TO;RELTYPE=PARENT:{TASK_UID}"),
        child("c-sub", "substring only", f"RELATED-TO:prefix-{TASK_UID}-suffix"),
        child("c-sib", "sibling", f"RELATED-TO;RELTYPE=SIBLING:{TASK_UID}"),
        (TASK_NAME, vtodo(TASK_UID, "itself", f"RELATED-TO:{TASK_UID}")),
    ]
    with respx.mock(assert_all_called=False) as mock:
        _get, reports = mock_task(
            mock, vtodo(TASK_UID, "parent task"), reports=Reports(OWN, children=candidates)
        )
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert reports.kinds == ["children"]
    assert result["subtasks"] == [
        {
            "id": ids.encode_task(OWN, "c-parent.ics"),
            "summary": "explicit parent",
            "status": "open",
        },
        {"id": ids.encode_task(OWN, "c-real.ics"), "summary": "real child", "status": "open"},
    ]
    assert "subtasks_truncated" not in result
    assert "subtasks_unavailable" not in result


@pytest.mark.anyio
async def test_children_are_sorted_open_first_then_summary(clients: NcClients) -> None:
    candidates = [
        child("c-1", "zeta", f"RELATED-TO:{TASK_UID}"),
        child("c-2", "Alpha", f"RELATED-TO:{TASK_UID}", "COMPLETED:20261112T100000Z"),
        child("c-3", "beta", f"RELATED-TO:{TASK_UID}", "STATUS:IN-PROCESS"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, vtodo(TASK_UID, "p"), reports=Reports(OWN, children=candidates))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert [(item["summary"], item["status"]) for item in result["subtasks"]] == [
        ("beta", "in_progress"),
        ("zeta", "open"),
        ("Alpha", "completed"),
    ]


@pytest.mark.anyio
async def test_sixty_children_are_capped_at_fifty_with_the_total(clients: NcClients) -> None:
    candidates = [
        child(f"c-{number:02d}", f"child {number:02d}", f"RELATED-TO:{TASK_UID}")
        for number in range(60)
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, vtodo(TASK_UID, "p"), reports=Reports(OWN, children=candidates))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert len(result["subtasks"]) == 50
    assert result["subtasks_truncated"] is True
    assert result["subtasks_total"] == 60
    assert result["subtasks"][0]["summary"] == "child 00"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503), httpx.ReadTimeout("slow"), httpx.ConnectError("down")],
    ids=["5xx", "transport-timeout", "network"],
)
async def test_a_failed_subtask_query_keeps_the_task_and_says_so(
    clients: NcClients, failure: Any
) -> None:
    ics = vtodo(TASK_UID, "still here", "DESCRIPTION:body")
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics, reports=Reports(OWN, children=failure))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert result["summary"] == "still here"
    assert result["description"] == "body"
    assert "subtasks" not in result
    assert result["subtasks_unavailable"].startswith("The subtasks could not be read")


@pytest.mark.anyio
async def test_a_subtask_query_over_its_budget_keeps_the_task(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tasks_tools.tasks_client.query_todos

    async def slow(client: Any, creds: Any, task_list: Any, body: bytes) -> Any:
        await asyncio.sleep(5)
        return await original(client, creds, task_list, body)

    monkeypatch.setattr(tasks_tools.tasks_client, "query_todos", slow)
    monkeypatch.setattr(tasks_tools, "SUBTASK_TIMEOUT", 0.05)
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, vtodo(TASK_UID, "slow children"))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert "subtasks" not in result
    assert result["subtasks_unavailable"] == ("The subtasks could not be read within 0.05 seconds.")


def test_the_timeout_sentence_names_one_second() -> None:
    assert tasks_tools._subtask_reason(TimeoutError()) == (
        "The subtasks could not be read within 1 second."
    )


@pytest.mark.anyio
async def test_an_unexpected_failure_of_the_subtask_query_stays_loud(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_args: Any) -> Any:
        raise RuntimeError("bug")

    monkeypatch.setattr(tasks_tools.tasks_client, "query_todos", broken)
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, vtodo(TASK_UID, "x"))
        with pytest.raises(RuntimeError):
            await tasks_tools.read_task(clients, task_id=TASK_ID)


# --- Parent ------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_parent_is_found_by_its_uid(clients: NcClients) -> None:
    # The server matches "contains": the near miss carries a UID that only contains p-1.
    parents = [
        ("p-longer.ics", vtodo("p-1-and-more", "near miss")),
        child("p-1", "the parent"),
    ]
    ics = vtodo(TASK_UID, "child", "RELATED-TO:p-1")
    with respx.mock(assert_all_called=False) as mock:
        _get, reports = mock_task(mock, ics, reports=Reports(OWN, parents=parents))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert sorted(reports.kinds) == ["children", "parents"]
    assert result["parent"] == {"id": ids.encode_task(OWN, "p-1.ics"), "summary": "the parent"}
    assert "parent_unavailable" not in result


@pytest.mark.anyio
async def test_a_parent_that_is_not_there_is_found_false(clients: NcClients) -> None:
    ics = vtodo(TASK_UID, "child", "RELATED-TO:p-missing")
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics)
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert result["parent"] == {"found": False}


@pytest.mark.anyio
async def test_a_failed_parent_lookup_is_parent_unavailable(clients: NcClients) -> None:
    ics = vtodo(TASK_UID, "child", "RELATED-TO:p-1")
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics, reports=Reports(OWN, parents=httpx.Response(500)))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert "parent" not in result
    assert result["parent_unavailable"].startswith("The parent task could not be read")
    assert result["subtasks"] == []


@pytest.mark.anyio
async def test_a_task_without_parent_asks_only_for_children(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        _get, reports = mock_task(mock, vtodo(TASK_UID, "root"))
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert reports.kinds == ["children"]
    assert "parent" not in result
    assert "parent_unavailable" not in result


# --- Recurring forms measured live in plan 32-10 (raw/32-10-messung.txt, WIEDER) ------------

_MASTER = (
    "BEGIN:VTODO\r\nUID:task-uid-1\r\nDTSTAMP:20261111T125506Z\r\nSUMMARY:daily\r\n"
    "DUE:20261120T130000Z\r\nRRULE:FREQ=DAILY\r\n"
)
_DONE = "STATUS:COMPLETED\r\nPERCENT-COMPLETE:100\r\nCOMPLETED:20261121T140000Z\r\n"
_OVERRIDE = (
    "BEGIN:VTODO\r\nUID:task-uid-1\r\nDTSTAMP:20261121T140000Z\r\nSUMMARY:daily override\r\n"
    "RECURRENCE-ID:20261121T130000Z\r\nDUE:20261121T130000Z\r\n" + _DONE + "END:VTODO\r\n"
)
_HEAD = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Nextcloud Tasks v0.18.1\r\n"


@pytest.mark.anyio
async def test_reading_a_recurring_task_with_a_completed_instance_is_the_open_master(
    clients: NcClients,
) -> None:
    ics = _HEAD + _MASTER + "END:VTODO\r\n" + _OVERRIDE + "END:VCALENDAR\r\n"
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics)
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert result["summary"] == "daily"
    assert result["status"] == "open"
    assert result["recurring"] is True
    assert result["due"] == "2026-11-20T13:00:00+00:00"
    assert "completed" not in result


@pytest.mark.anyio
async def test_reading_a_recurring_task_with_a_completed_master_is_completed(
    clients: NcClients,
) -> None:
    ics = _HEAD + _MASTER + _DONE + "END:VTODO\r\nEND:VCALENDAR\r\n"
    with respx.mock(assert_all_called=False) as mock:
        mock_task(mock, ics)
        result = await tasks_tools.read_task(clients, task_id=TASK_ID)
    assert result["status"] == "completed"
    assert result["recurring"] is True
    assert result["completed"] == "2026-11-21T14:00:00+00:00"

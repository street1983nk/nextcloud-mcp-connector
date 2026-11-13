"""The note about the Tasks app (D-32-10) under the measured decision ``erkennung=keine``.

D-32-10 asks for one sentence "tasks show up in the web interface only with the Tasks app"
in the answer of ``tasks_create`` and in the case without a task list (E6), but only when the
state of the app can be told reliably; otherwise the sentence is dropped and nothing is
guessed. Plan 32-02 measured both candidate ways (the navigation of the account and the list
of search providers): on Nextcloud 35 they follow every state at once, on Nextcloud 32 they
keep answering the old state after ``app:disable`` and ``app:enable`` without a restart, so
they are wrong and not merely unclear (ENTSCHEID erkennung=keine, docs/tasks-evidence.md).
The owner confirmed on 2026-11-13 that the note is dropped.

Pinned here: there is no detection to call (no field, no loader, no ``require_app``), no
answer of the bundle carries the sentence, and the bundle never asks Nextcloud for the state
of the app: no OCS request at all, counted per route.
"""

import inspect
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from mcp_connector import ids
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import tasks as tasks_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
HOME_PATH = "/remote.php/dav/calendars/alice/"
OCS_PREFIX = f"{BASE}/ocs/"
OWN = "spike30-aufgaben"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

#: Parts of the sentence D-32-10 would have added. None of them may appear anywhere.
OFF_SENTENCE_PARTS = (
    "not enabled",
    "only with the Tasks app",
    "show up in the Nextcloud web interface",
)


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    capabilities.clear_cache()


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def mock_discovery(mock: respx.MockRouter, name: str) -> respx.Route:
    return mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
        return_value=httpx.Response(
            207, text=fixture(name), headers={"Content-Type": "application/xml"}
        )
    )


def mock_ocs(mock: respx.MockRouter) -> respx.Route:
    """Every OCS URL, navigation and search providers included; it must stay uncalled."""
    return mock.route(url__startswith=OCS_PREFIX).mock(return_value=httpx.Response(500))


def assert_no_off_sentence(answer: Any) -> None:
    text = json.dumps(answer, ensure_ascii=False)
    for part in OFF_SENTENCE_PARTS:
        assert part not in text, part


def empty_report() -> httpx.Response:
    return httpx.Response(
        207,
        text='<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>',
        headers={"Content-Type": "application/xml"},
    )


# --- No detection is built ----------------------------------------------------------------


def test_capabilities_has_no_detection_of_the_tasks_app() -> None:
    assert not hasattr(capabilities, "load_tasks_app")
    assert "load_tasks_app" not in capabilities.__all__
    fields = {field.name for field in capabilities.Capabilities.__dataclass_fields__.values()}
    assert "tasks_available" not in fields


def test_the_tool_layer_never_asks_for_the_tasks_app() -> None:
    source = inspect.getsource(tasks_tools)
    assert "require_app" not in source
    assert "capabilities" not in source
    assert "_tasks_app_hint" not in source
    for part in OFF_SENTENCE_PARTS:
        assert part not in source, part


def test_has_does_not_know_tasks() -> None:
    """``has("tasks")`` stays unknown: no caller needs it under ``erkennung=keine``."""
    with pytest.raises(ValueError, match="not an optional app"):
        capabilities.Capabilities().has("tasks")


# --- No answer carries the sentence, no answer asks for the app -----------------------------


@pytest.mark.anyio
async def test_e6_of_tasks_search_has_no_sentence_and_asks_no_ocs(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, "caldav_home_fresh_account.xml")
        ocs = mock_ocs(mock)
        result = await tasks_tools.search_tasks(clients)
    assert result == {"tasks": [], "hint": tasks_tools.NO_LIST_HINT}
    assert_no_off_sentence(result)
    assert ocs.call_count == 0


@pytest.mark.anyio
async def test_a_normal_search_asks_no_ocs(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, "caldav_home_task_lists.xml")
        mock.route(method="REPORT", url__startswith=CALENDAR_HOME).mock(return_value=empty_report())
        ocs = mock_ocs(mock)
        result = await tasks_tools.search_tasks(clients)
    assert result == {"tasks": []}
    assert ocs.call_count == 0


@pytest.mark.anyio
async def test_read_task_has_no_sentence_and_asks_no_ocs(clients: NcClients) -> None:
    name = "task-uid-1.ics"
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\nBEGIN:VTODO\r\n"
        "UID:task-uid-1\r\nDTSTAMP:20261111T120000Z\r\nSUMMARY:one\r\n"
        "END:VTODO\r\nEND:VCALENDAR\r\n"
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, "caldav_home_task_lists.xml")
        mock.route(method="GET", url=f"{CALENDAR_HOME}{OWN}/{name}").mock(
            return_value=httpx.Response(200, text=ics)
        )
        mock.route(method="REPORT", url__startswith=CALENDAR_HOME).mock(return_value=empty_report())
        ocs = mock_ocs(mock)
        result = await tasks_tools.read_task(clients, task_id=ids.encode_task(OWN, name))
    assert result["summary"] == "one"
    assert_no_off_sentence(result)
    assert ocs.call_count == 0


@pytest.mark.anyio
async def test_e6_of_tasks_create_has_no_sentence_and_asks_no_ocs(clients: NcClients) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, "caldav_home_fresh_account.xml")
        ocs = mock_ocs(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, summary="t")
    assert_no_off_sentence({"message": caught.value.message, "hint": caught.value.hint})
    assert ocs.call_count == 0


@pytest.mark.anyio
async def test_a_created_task_has_no_hint_and_asks_no_ocs(clients: NcClients) -> None:
    stored: dict[str, bytes] = {}

    def put(request: httpx.Request) -> httpx.Response:
        stored[request.url.path] = request.content
        return httpx.Response(201)

    def get(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=stored[request.url.path])

    with respx.mock(assert_all_called=False) as mock:
        mock_discovery(mock, "caldav_home_task_lists.xml")
        mock.route(method="PUT", url__startswith=CALENDAR_HOME).mock(side_effect=put)
        mock.route(method="GET", url__startswith=CALENDAR_HOME).mock(side_effect=get)
        ocs = mock_ocs(mock)
        result = await tasks_tools.create_task(clients, summary="t", list_name=OWN)
    assert result["created"] is True
    assert "hint" not in result
    assert_no_off_sentence(result)
    assert ocs.call_count == 0

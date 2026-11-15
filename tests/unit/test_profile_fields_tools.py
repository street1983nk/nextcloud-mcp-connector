"""Read-only Profile Fields behavior and explicit opt-in tests."""

import json
import os
import subprocess
import sys

import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import profile_fields

ROOT = "http://nc.test/ocs/v2.php/apps/profile_fields/api/v1"


def payload(data: object, status: int = 200) -> dict:
    return {"ocs": {"meta": {"statuscode": status, "message": "test"}, "data": data}}


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials("http://nc.test", "admin", "test-password"),
    )


@pytest.mark.anyio
async def test_own_visible_fields_are_read_without_admin_catalog(clients: NcClients) -> None:
    own = [
        {"definition": {"id": 1, "field_key": "nickname"}, "value": None, "can_edit": True},
        {
            "definition": {"id": 2, "field_key": "employee_id"},
            "value": {"field_definition_id": 2, "value": {"value": "EMP-001"}},
            "can_edit": False,
        },
    ]
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(ROOT + "/me/values").respond(200, json=payload(own))
        result = await profile_fields.browse(clients)
    assert route.called
    assert result["level"] == "me"
    assert result["count"] == 2
    assert result["results"][1]["value"]["value"]["value"] == "EMP-001"
    assert all(call.request.method == "GET" for call in mock.calls)


@pytest.mark.anyio
async def test_admin_catalog_only_returns_selected_metadata(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(
            200,
            json=payload([{"id": 1, "field_key": "employee_id", "type": "text",
                           "label": "Sensitive label", "active": True}]),
        )
        result = await profile_fields.browse(clients, level="definitions")
    assert result["results"] == [
        {"id": 1, "field_key": "employee_id", "type": "text", "active": True}
    ]


@pytest.mark.anyio
async def test_admin_user_values_only_include_requested_keys(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(
            200, json=payload([
                {"id": 1, "field_key": "mailcow_mailbox"},
                {"id": 2, "field_key": "cpf"},
            ])
        )
        mock.get(ROOT + "/users/alice/values").respond(
            200, json=payload([
                {"field_definition_id": 1, "value": {"value": "alice@example.org"}},
                {"field_definition_id": 2, "value": {"value": "sensitive-id"}},
            ])
        )
        result = await profile_fields.browse(
            clients, "values", user_uid="alice", field_keys="mailcow_mailbox"
        )
    assert result["fields"] == {
        "mailcow_mailbox": {"value": "alice@example.org", "current_visibility": None}
    }
    assert "sensitive-id" not in repr(result)
    assert all(call.request.method == "GET" for call in mock.calls)


@pytest.mark.anyio
async def test_admin_search_returns_exact_match_and_pagination(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(ROOT + "/users/search").respond(
            200,
            json=payload({
                "items": [{
                    "user_uid": "alice",
                    "display_name": "Alice",
                    "fields": {
                        "region": {
                            "definition": {"field_key": "region"},
                            "value": {"value": {"value": "LATAM"}, "current_visibility": "private"},
                        }
                    },
                }],
                "pagination": {"limit": 1, "offset": 1, "total": 3},
            }),
        )
        result = await profile_fields.browse(
            clients, level="search", field_key="region", value="LATAM", limit=1, offset=1
        )
    assert route.called
    assert dict(route.calls[0].request.url.params) == {
        "fieldKey": "region", "operator": "eq", "value": "LATAM",
        "limit": "1", "offset": "1",
    }
    assert result["results"] == [{"user_uid": "alice", "value": "LATAM"}]
    assert result["total"] == 3
    assert all(call.request.method == "GET" for call in mock.calls)


@pytest.mark.anyio
async def test_admin_only_endpoint_rejects_regular_user(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(403, json=payload([], 403))
        with pytest.raises(ToolError):
            await profile_fields.browse(clients, level="definitions")
        assert len(mock.calls) == 1


@pytest.mark.anyio
async def test_invalid_inputs_cause_no_network_request(clients: NcClients) -> None:
    with respx.mock() as mock:
        for opts in (
            {"level": "values", "user_uid": "../admin", "field_keys": "region"},
            {"level": "values", "user_uid": "alice", "field_keys": "region,"},
            {"level": "search", "field_key": "region", "value": ""},
            {"level": "search", "field_key": "region", "value": "LATAM", "limit": 101},
            {"level": "unknown"},
        ):
            with pytest.raises(ToolError):
                await profile_fields.browse(clients, **opts)
        assert not mock.calls


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, False), ("", False), ("off", False), ("invalid", False),
        ("on", True), ("true", True), ("YES", True),
    ],
)
def test_opt_in_switch_fails_closed(raw: str | None, expected: bool) -> None:
    env = {} if raw is None else {config.ENV_PROFILE_FIELDS_READ: raw}
    assert config.profile_fields_read_enabled(env) is expected


@pytest.mark.parametrize(
    ("raw", "enabled"),
    [(None, False), ("off", False), ("typo", False), ("on", True)],
)
def test_opt_in_is_the_only_way_to_extend_the_27_tool_registry(
    raw: str | None, enabled: bool
) -> None:
    script = (
        "import json; from mcp_connector.server import mcp; "
        "print(json.dumps(sorted(t.name for t in mcp._tool_manager.list_tools())))"
    )
    env = os.environ.copy()
    env.pop(config.ENV_PROFILE_FIELDS_READ, None)
    env.pop("NC_MCP_DISABLED_TOOLS", None)
    env.pop("NC_MCP_FILES_UPDATE", None)
    env.pop("NC_MCP_TASKS_UPDATE", None)
    if raw is not None:
        env[config.ENV_PROFILE_FIELDS_READ] = raw
    proc = subprocess.run(  # noqa: S603 - fixed interpreter and constant snippet
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    names = json.loads(proc.stdout.strip().splitlines()[-1])
    assert len(names) == (28 if enabled else 27)
    assert ("profile_fields_browse" in names) is enabled
    assert not any(
        name.startswith("profile_fields_") and name != "profile_fields_browse" for name in names
    )

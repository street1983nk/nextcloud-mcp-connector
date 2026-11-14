"""Profile Fields admin-only read tests with synthetic data."""

import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import profile_fields

ROOT = "http://nc.test/ocs/v2.php/apps/profile_fields/api/v1"


def payload(data: object, status: int = 200) -> dict:
    return {"ocs": {"meta": {"statuscode": status, "message": "test"}, "data": data}}


@pytest.fixture
def clients() -> NcClients:
    return NcClients(client=httpx.AsyncClient(follow_redirects=False),
                     creds=Credentials("http://nc.test", "admin", "test-password"))


@pytest.mark.anyio
async def test_one_uid_only_explicit_fields(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").mock(return_value=httpx.Response(
            200, json=payload([{"id": 1, "field_key": "mailcow_mailbox"},
                               {"id": 2, "field_key": "cpf"}])))
        mock.get(ROOT + "/users/alice/values").mock(return_value=httpx.Response(
            200, json=payload([
                {"field_definition_id": 1, "value": {"value": "alice@example.org"}},
                {"field_definition_id": 2, "value": {"value": "sensitive-id"}},
            ])))
        result = await profile_fields.browse(
            clients, "values", user_uid="alice", field_keys="mailcow_mailbox"
        )
    assert result["fields"]["mailcow_mailbox"]["value"] == "alice@example.org"
    assert "sensitive-id" not in repr(result)


@pytest.mark.anyio
async def test_rejects_non_admin(clsients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").mock(
            return_value=httpx.Response(403, json=payload([], 403))
        )
        with pytest.raises(ToolError):
            await profile_fields.browse(clsients)
        assert len(mock.calls) == 1


@pytest.mark.anyio
async def test_bad_inputs_make_no_requests(clients: NcClients) -> None:
    with respx.mock() as mock:
        for opts in (
            {"level": "values", "user_uid": "../admin", "field_keys": "mailcow_mailbox"},
            {"level": "values", "user_uid": "alice", "field_keys": "mailcow_mailbox,"},
            {"level": "search", "field_key": "mailcow_mailbox", "value": ""},
        ):
            with pytest.raises(ToolError):
                await profile_fields.browse(clients, **opts)
        assert not mock.calls

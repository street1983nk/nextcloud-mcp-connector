"""Profile Fields writes are gated by the native Nextcloud OCS permission boundary."""

import json

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
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials("http://nc.test", "alice", "fake-app-password"),
    )


@pytest.mark.anyio
async def test_own_value_uses_own_endpoint_and_credentials(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/me/values").respond(200, json=payload([]))
        written = mock.put(ROOT + "/me/values/11").respond(
            200, json=payload({"field_definition_id": 11, "value": {"value": True}})
        )
        result = await profile_fields.set_value(clients, 11, "true")
    assert result["scope"] == "me"
    assert result["value"]["value"]["value"] is True
    request = written.calls[0].request
    assert request.headers["Authorization"].startswith("Basic ")
    assert json.loads(request.content) == {"value": {"value": True}}


@pytest.mark.anyio
async def test_identical_own_update_does_not_write_again(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/me/values").respond(
            200,
            json=payload(
                [
                    {
                        "definition": {"id": 11},
                        "value": {
                            "field_definition_id": 11,
                            "value": {"value": "already"},
                            "current_visibility": "private",
                        },
                    },
                ]
            ),
        )
        result = await profile_fields.set_value(clients, 11, '"already"')
        assert len(mock.calls) == 1
    assert result["changed"] is False


@pytest.mark.anyio
async def test_non_admin_cannot_get_other_user_for_write(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/users/bob/values").respond(403, json=payload({}, 403))
        with pytest.raises(ToolError):
            await profile_fields.set_value(clients, 11, '"value"', user_uid="bob")
        assert len(mock.calls) == 1


@pytest.mark.anyio
async def test_authorized_admin_uses_target_user_route(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/users/bob/values").respond(200, json=payload([]))
        changed = mock.put(ROOT + "/users/bob/values/11").respond(
            200, json=payload({"field_definition_id": 11, "user_uid": "bob"})
        )
        result = await profile_fields.set_value(clients, 11, '"bob@example.org"', user_uid="bob")
    assert result["scope"] == "admin"
    assert changed.called


@pytest.mark.anyio
async def test_create_definition_as_admin(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        create = mock.post(ROOT + "/definitions").respond(
            201, json=payload({"id": 7, "field_key": "mailcow_mailbox"}, 201)
        )
        result = await profile_fields.save_definition(
            clients,
            '{"fieldKey":"mailcow_mailbox","label":"Mailbox","type":"email"}',
        )
    assert result["operation"] == "create"
    assert create.called


@pytest.mark.anyio
async def test_complete_update_definition_and_noop(clients: NcClients) -> None:
    current = {
        "id": 7,
        "field_key": "mailcow_mailbox",
        "label": "Mailbox",
        "type": "email",
        "edit_policy": "admins",
        "exposure_policy": "hidden",
        "sort_order": 0,
        "active": True,
    }
    updated = {
        "label": "Mailbox",
        "type": "email",
        "editPolicy": "admins",
        "exposurePolicy": "hidden",
        "sortOrder": 0,
        "active": True,
    }
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(200, json=payload([current]))
        result = await profile_fields.save_definition(clients, json.dumps(updated), definition_id=7)
        assert len(mock.calls) == 1
    assert result["changed"] is False


@pytest.mark.anyio
async def test_admin_definition_update_forwards_to_native_ocs(clients: NcClients) -> None:
    fields = {
        "label": "Changed",
        "type": "email",
        "editPolicy": "admins",
        "exposurePolicy": "hidden",
        "sortOrder": 1,
        "active": True,
    }
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(200, json=payload([{"id": 7, "label": "Old"}]))
        changed = mock.put(ROOT + "/definitions/7").respond(
            200, json=payload({"id": 7, "label": "Changed"})
        )
        result = await profile_fields.save_definition(clients, json.dumps(fields), definition_id=7)
    assert result["operation"] == "update"
    assert changed.called


@pytest.mark.anyio
async def test_invalid_writes_do_not_hit_ocs(clients: NcClients) -> None:
    with respx.mock() as mock:
        for args in [
            (11, "not valid JSON", "", ""),
            (11, '"value"', "../bob", ""),
            (0, '"value"', "", ""),
            (11, '"value"', "", "all"),
        ]:
            with pytest.raises(ToolError):
                await profile_fields.set_value(
                    clients, args[0], args[1], user_uid=args[2], visibility=args[3]
                )
        with pytest.raises(ToolError):
            await profile_fields.save_definition(
                clients, '{"label":"Missing policies","type":"text"}', definition_id=7
            )
    assert len(mock.calls) == 0

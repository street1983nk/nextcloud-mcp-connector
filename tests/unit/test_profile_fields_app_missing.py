"""Profile Fields switched on, but the app itself missing or disabled (35-12, finding PF-FEHLT).

Every answer below is the shape measured on 2026-11-20 (raw/35-12-pf-fehlt.txt):

* app missing on Nextcloud 35.0.0 and app disabled on Nextcloud 34.0.3: HTTP 404 with
  ``ocs.meta.statuscode`` 998 and the core text "Invalid query, ..." for all four routes;
  the same answer as for any route no app knows (control route ``/apps/notesXYZ/...``).
* the app's own 404 (Profile Fields 4.0.0, unknown search field key): HTTP 404 with
  ``ocs.meta.statuscode`` 404, an empty ``meta.message`` and ``data.message``.
* an unknown UID at ``users/{uid}/values``: HTTP 200 with an empty list, no 404 at all.
"""

from typing import Any

import httpx
import pytest
import respx

from mcp_connector.errors import (
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    REASON_UNSPECIFIED,
    AppMissingError,
    ToolError,
)
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import ocs
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import profile_fields

ROOT = "http://nc.test/ocs/v2.php/apps/profile_fields/api/v1"

MISSING_MESSAGE = "Profile Fields is not installed or not enabled on this Nextcloud."
MISSING_HINT = (
    "Ask an administrator to install the app Profile Fields or to switch off profile_fields_read."
)

#: The core text exactly as Nextcloud 35.0.0 and 34.0.3 sent it, trailing newline included.
CORE_998_TEXT = (
    "Invalid query, please check the syntax. API specifications are here: "
    "http://www.freedesktop.org/wiki/Specifications/open-collaboration-services.\n"
)


def core_route_missing() -> dict[str, Any]:
    return {
        "ocs": {
            "meta": {"status": "failure", "statuscode": 998, "message": CORE_998_TEXT},
            "data": [],
        }
    }


def app_not_found(text: str) -> dict[str, Any]:
    return {
        "ocs": {
            "meta": {"status": "failure", "statuscode": 404, "message": ""},
            "data": {"message": text},
        }
    }


def ok(data: object) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials("http://nc.test", "admin", "test-password"),
    )


#: level, keyword arguments, the route the tool asks first.
LEVELS = [
    ("me", {}, "/me/values"),
    ("definitions", {}, "/definitions"),
    ("values", {"user_uid": "alice", "field_keys": "employee_id"}, "/definitions"),
    ("search", {"field_key": "employee_id", "value": "x"}, "/users/search"),
]


def assert_clean(error: ToolError) -> None:
    text = str(error)
    assert "://" not in text
    assert "\n" not in text
    assert "\\n" not in text
    assert "freedesktop" not in text
    assert "Invalid query" not in text


@pytest.mark.anyio
@pytest.mark.parametrize(("level", "kwargs", "route"), LEVELS)
async def test_missing_app_gets_the_owner_approved_sentence_on_every_level(
    clients: NcClients, level: str, kwargs: dict[str, Any], route: str
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + route).respond(404, json=core_route_missing())
        with pytest.raises(AppMissingError) as caught:
            await profile_fields.browse(clients, level=level, **kwargs)
        assert len(mock.calls) == 1
    error = caught.value
    assert error.message == MISSING_MESSAGE
    assert error.hint == MISSING_HINT
    assert str(error) == f"{MISSING_MESSAGE} Hint: {MISSING_HINT}"
    # The same reason the other missing apps carry (capabilities.app_missing): no thirteenth
    # identifier, and no "unknown_id", because nothing was looked up by an id.
    assert error.reason == REASON_UNSPECIFIED
    assert_clean(error)


@pytest.mark.anyio
async def test_app_disabled_between_catalog_and_values_gets_the_same_sentence(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(200, json=ok([{"id": 1, "field_key": "cpf"}]))
        mock.get(ROOT + "/users/alice/values").respond(404, json=core_route_missing())
        with pytest.raises(AppMissingError) as caught:
            await profile_fields.browse(clients, level="values", user_uid="alice", field_keys="cpf")
    assert caught.value.message == MISSING_MESSAGE
    assert_clean(caught.value)


@pytest.mark.anyio
async def test_the_apps_own_404_keeps_its_hint_positive_control(clients: NcClients) -> None:
    """Unknown search field key: the app answers 404/404, which is not a missing app."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/users/search").respond(
            404, json=app_not_found("Search field definition not found")
        )
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients, level="search", field_key="unknown_key", value="x")
    error = caught.value
    assert not isinstance(error, AppMissingError)
    assert error.message == "Nextcloud did not find the Profile Fields exact search."
    assert error.hint == "Search for it first; the id or the name is unknown to this instance."
    assert error.reason == REASON_UNKNOWN_ID


@pytest.mark.anyio
@pytest.mark.parametrize(("level", "kwargs", "route"), LEVELS)
async def test_an_ocs_404_without_998_is_never_called_a_missing_app(
    clients: NcClients, level: str, kwargs: dict[str, Any], route: str
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + route).respond(404, json=app_not_found("Field definition not found"))
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients, level=level, **kwargs)
    assert not isinstance(caught.value, AppMissingError)
    assert "not installed" not in str(caught.value)
    assert caught.value.reason == REASON_UNKNOWN_ID


@pytest.mark.anyio
async def test_998_without_http_404_is_not_called_a_missing_app(clients: NcClients) -> None:
    """Both halves of the measured answer are required, not one of them."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/me/values").respond(200, json=core_route_missing())
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients)
    assert not isinstance(caught.value, AppMissingError)


@pytest.mark.anyio
async def test_a_404_without_json_is_not_called_a_missing_app(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(
            404, content=b"", headers={"Content-Type": "text/html"}
        )
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients, level="definitions")
    assert not isinstance(caught.value, AppMissingError)


@pytest.mark.anyio
async def test_unknown_uid_is_an_empty_answer_not_an_error(clients: NcClients) -> None:
    """Measured: ``users/{uid}/values`` answers 200 with an empty list for an unknown UID."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(200, json=ok([{"id": 1, "field_key": "cpf"}]))
        mock.get(ROOT + "/users/unknown-zz9/values").respond(200, json=ok([]))
        result = await profile_fields.browse(
            clients, level="values", user_uid="unknown-zz9", field_keys="cpf"
        )
    assert result == {"level": "values", "user_uid": "unknown-zz9", "fields": {}}


@pytest.mark.anyio
async def test_unknown_field_key_for_values_is_refused_before_the_values_route(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(200, json=ok([{"id": 1, "field_key": "cpf"}]))
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients, level="values", user_uid="alice", field_keys="x")
        assert len(mock.calls) == 1
    assert caught.value.message == "Unknown field key."
    assert caught.value.hint == "List definitions first."


@pytest.mark.anyio
async def test_403_names_the_catalog_with_its_article(clients: NcClients) -> None:
    forbidden = {
        "ocs": {
            "meta": {
                "status": "failure",
                "statuscode": 403,
                "message": "Logged in account must be an admin",
            },
            "data": [],
        }
    }
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(403, json=forbidden)
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients, level="definitions")
    assert str(caught.value) == (
        "No permission for the Profile Fields admin catalog. Nextcloud says: "
        '"Logged in account must be an admin". Hint: Ask the owner of the item or an '
        "administrator in Nextcloud for the missing permission."
    )
    assert caught.value.reason == REASON_PERMISSION_DENIED


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("level", "kwargs", "failing", "what"),
    [
        ("me", {}, "/me/values", "the current user's Profile Fields values"),
        ("definitions", {}, "/definitions", "the Profile Fields admin catalog"),
        (
            "search",
            {"field_key": "cpf", "value": "x"},
            "/users/search",
            "the Profile Fields exact search",
        ),
        (
            "values",
            {"user_uid": "alice", "field_keys": "cpf"},
            "/users/alice/values",
            "the selected user's Profile Fields values",
        ),
    ],
)
async def test_every_profile_fields_object_carries_its_article(
    clients: NcClients, level: str, kwargs: dict[str, Any], failing: str, what: str
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        if failing != "/definitions" and level == "values":
            mock.get(ROOT + "/definitions").respond(200, json=ok([{"id": 1, "field_key": "cpf"}]))
        mock.get(ROOT + failing).respond(500, json={})
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients, level=level, **kwargs)
    assert caught.value.message == f"Nextcloud reported a server error (500) while reading {what}."


def test_other_apps_keep_the_shared_404_and_998_wording() -> None:
    """``_status_error`` is untouched: a 998 elsewhere still reads as an unknown id."""
    response = httpx.Response(
        404,
        json=core_route_missing(),
        request=httpx.Request("GET", "http://nc.test/ocs/v2.php/apps/notes/x"),
    )
    with pytest.raises(ToolError) as caught:
        ocs.parse_ocs(response, what="the note")
    error = caught.value
    assert not isinstance(error, AppMissingError)
    assert error.message == f'Nextcloud did not find the note. Nextcloud says: "{CORE_998_TEXT}".'
    assert error.hint == "Search for it first; the id or the name is unknown to this instance."
    assert error.reason == REASON_UNKNOWN_ID


# --- The app enabled for some groups only (35-12, owner decision pf-gruppen-412) -------------
#
# Measured on Nextcloud 34.0.3 with ``occ app:enable profile_fields --groups=<group>``: an
# account outside every listed group gets HTTP 412, ``Content-Type: application/json`` and
# the body ``{"message":"App is not enabled"}`` without an OCS envelope. The text is the fixed,
# untranslated literal of ``AppNotEnabledException`` (same in 34.0.3 and 35.0.0); the other
# 412 answers of the core security middleware carry other texts ("CSRF check failed",
# "ExApp required", the two cookie checks), and Profile Fields 4.0.0 never answers 412.

GROUP_MESSAGE = "Profile Fields is not enabled for this account."
GROUP_HINT = (
    "Ask an administrator to enable the app Profile Fields for one of your groups or to "
    "switch off profile_fields_read."
)


def not_enabled_for_account() -> dict[str, Any]:
    return {"message": "App is not enabled"}


@pytest.mark.anyio
@pytest.mark.parametrize(("level", "kwargs", "route"), LEVELS)
async def test_app_not_enabled_for_the_account_gets_its_own_sentence_on_every_level(
    clients: NcClients, level: str, kwargs: dict[str, Any], route: str
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + route).respond(412, json=not_enabled_for_account())
        with pytest.raises(AppMissingError) as caught:
            await profile_fields.browse(clients, level=level, **kwargs)
        assert len(mock.calls) == 1
    error = caught.value
    assert error.message == GROUP_MESSAGE
    assert error.hint == GROUP_HINT
    assert str(error) == f"{GROUP_MESSAGE} Hint: {GROUP_HINT}"
    assert error.reason == REASON_UNSPECIFIED
    assert_clean(error)
    assert "App is not enabled" not in str(error)


@pytest.mark.anyio
async def test_not_enabled_between_catalog_and_values_gets_the_same_sentence(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/definitions").respond(200, json=ok([{"id": 1, "field_key": "cpf"}]))
        mock.get(ROOT + "/users/alice/values").respond(412, json=not_enabled_for_account())
        with pytest.raises(AppMissingError) as caught:
            await profile_fields.browse(clients, level="values", user_uid="alice", field_keys="cpf")
    assert caught.value.message == GROUP_MESSAGE


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "body"),
    [
        (412, {"message": "CSRF check failed"}),
        (412, {"message": "ExApp required"}),
        (412, {"message": "Strict Cookie has not been found in request."}),
        (412, {"message": "App is not enabled", "ocs": {}}),
        (412, {"ocs": {"meta": {"statuscode": 412, "message": "App is not enabled"}, "data": []}}),
        (412, ["App is not enabled"]),
        (403, {"message": "App is not enabled"}),
        (404, {"message": "App is not enabled"}),
    ],
)
async def test_other_answers_never_read_as_not_enabled_positive_control(
    clients: NcClients, status: int, body: object
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/me/values").respond(status, json=body)
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients)
    assert caught.value.message not in (GROUP_MESSAGE, MISSING_MESSAGE)


@pytest.mark.anyio
async def test_a_412_without_json_keeps_the_old_way(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/me/values").respond(
            412, content=b"App is not enabled", headers={"Content-Type": "text/plain"}
        )
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients)
    assert not isinstance(caught.value, AppMissingError)


@pytest.mark.anyio
async def test_the_412_csrf_answer_keeps_its_previous_wording(clients: NcClients) -> None:
    """The way a non-matching 412 took before 35-12 is unchanged, word for word."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ROOT + "/me/values").respond(412, json={"message": "CSRF check failed"})
        with pytest.raises(ToolError) as caught:
            await profile_fields.browse(clients)
    assert caught.value.message == (
        "Nextcloud answered the current user's Profile Fields values without an OCS envelope."
    )


def test_other_apps_keep_the_envelope_wording_for_the_412_answer() -> None:
    response = httpx.Response(
        412,
        json=not_enabled_for_account(),
        request=httpx.Request("GET", "http://nc.test/ocs/v2.php/apps/notes/x"),
    )
    with pytest.raises(ToolError) as caught:
        ocs.parse_ocs(response, what="the note")
    assert not isinstance(caught.value, AppMissingError)
    assert caught.value.message == "Nextcloud answered the note without an OCS envelope."

"""The fifth credential mode: from a verified OAuth token to one Nextcloud identity.

This is the last piece of the durchstich of phase 3, and it is deliberately the smallest
one. No tool module is touched (D-26): a tool asks ``deps.resolve_clients`` for credentials
as it always has, and the only new thing is where those credentials come from when the
AppAPI header carries no user.

Two rules decide everything here and both are D-27: the branch is chosen by the user id of
the AppAPI header alone, and there is no fallback in either direction. A request with a
user is the impersonation path and its ``Authorization`` header is not read at all; a
request without one is the OAuth path and an app secret impersonation is not offered as a
consolation.

Threats covered here: T-03-54 (a credential in a log record or a repr), T-03-57 (a silent
fallback between the two channels) and the revocation half of SC 4.

The store is a SQLite file in ``tmp_path``, the identity comes through a real Starlette
request state, and nothing here opens a socket.
"""

import base64
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from starlette.requests import Request

from mcp_connector import config, deps
from mcp_connector.exapp.target import exapp_target
from mcp_connector.nextcloud.credentials import MODE_BASIC, MODES
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import registry
from mcp_connector.oauth.metadata import TOOL_SCOPE
from mcp_connector.oauth.store import OAuthStore
from mcp_connector.oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity, StoreTokenVerifier

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
AA_VERSION = "34.0.3"
BASE_URL = "http://nc.test"
PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
RESOURCE = f"{PUBLIC_URL}/mcp"

CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
AUTH_ID = "the-flow-this-authorization-was-born-in"
FAMILY_ID = "the-family-of-this-connection"
NC_USER = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
TOKEN = "the-access-token-of-this-connection"

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

ENV = {
    config.ENV_PUBLIC_URL: PUBLIC_URL,
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_NEXTCLOUD_URL: BASE_URL,
}

REGISTRATION = (
    '{"client_id": "'
    + CLIENT_ID
    + '", "client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"], '
    '"grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], '
    '"token_endpoint_auth_method": "none", "scope": "nextcloud"}'
)


@pytest.fixture
def exapp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deploy environment AppAPI injects into the ExApp container."""
    monkeypatch.setenv(config.ENV_APP_ID, APP_ID)
    monkeypatch.setenv(config.ENV_APP_SECRET, APP_SECRET)
    monkeypatch.setenv(config.ENV_APP_VERSION, APP_VERSION)
    monkeypatch.setenv(config.ENV_AA_VERSION, AA_VERSION)
    monkeypatch.setenv(config.ENV_NEXTCLOUD_URL, BASE_URL)
    monkeypatch.setenv(config.ENV_PUBLIC_URL, PUBLIC_URL)
    monkeypatch.delenv(config.ENV_STATIC_BEARER, raising=False)
    monkeypatch.delenv(config.ENV_APP_PASSWORD, raising=False)


def appapi_headers(user: str = NC_USER, secret: str = APP_SECRET) -> dict[str, str]:
    """The three headers HaRP puts in front of every request it forwards."""
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


class FakeRequestContext:
    """What the SDK hands a tool: the request of the message, and nothing else of ours."""

    def __init__(self, request: Request) -> None:
        self.request = request


class FakeContext:
    """The context object of a tool call, in the two shapes ``deps`` reads it in."""

    def __init__(
        self,
        headers: Mapping[str, str] | None = None,
        identity: OAuthIdentity | None = None,
    ) -> None:
        self.headers = headers
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [
                    (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
                ],
            }
        )
        if identity is not None:
            setattr(request.state, OAUTH_STATE_ATTR, identity)
        self.request_context = FakeRequestContext(request)


def identity(**fields: Any) -> OAuthIdentity:
    values: dict[str, Any] = {
        "nc_user": NC_USER,
        "app_password": APP_PASSWORD,
        "auth_id": AUTH_ID,
        "client_id": CLIENT_ID,
    }
    values.update(fields)
    return OAuthIdentity(**values)


# --- the OAuth branch ----------------------------------------------------------------------


def test_a_verified_token_becomes_the_basic_credentials_of_its_user(exapp_env: None) -> None:
    """Against Nextcloud an app password is Basic auth, so this is the fourth mode's twin."""
    creds = deps.resolve_credentials(
        FakeContext(headers=appapi_headers(user=""), identity=identity())
    )

    assert creds.mode == MODE_BASIC
    assert creds.user == NC_USER
    assert creds.secret == APP_PASSWORD
    assert creds.base_url == BASE_URL, "the base URL is a deployment decision, never a request"


def test_nextcloud_credentials_grew_no_third_mode(exapp_env: None) -> None:
    """D-26: an app password is Basic auth, and a fifth branch here is not a fifth mode."""
    assert set(MODES) == {"basic", "appapi"}


def test_a_revoked_connection_is_an_error_with_a_next_step(exapp_env: None) -> None:
    """SC 4: the answer a user can act on is "connect the app again", not a 500."""
    with pytest.raises(deps.MCPError) as raised:
        deps.resolve_credentials(
            FakeContext(headers=appapi_headers(user=""), identity=identity(revoked=True))
        )

    assert "connect" in raised.value.message.lower()
    assert APP_PASSWORD not in raised.value.message


def test_an_empty_user_without_an_identity_is_refused(exapp_env: None) -> None:
    """No fallback: a missing OAuth identity does not become an app secret impersonation."""
    with pytest.raises(deps.MCPError) as raised:
        deps.resolve_credentials(FakeContext(headers=appapi_headers(user="")))

    assert "user" in raised.value.message.lower()
    assert APP_SECRET not in raised.value.message


def test_a_context_without_a_request_is_refused(exapp_env: None) -> None:
    """A tool call outside an HTTP request has no OAuth identity and gets no credentials."""

    class Bare:
        headers = appapi_headers(user="")

    with pytest.raises(deps.MCPError):
        deps.resolve_credentials(Bare())


# --- the two channels next to each other ----------------------------------------------------


def test_an_appapi_user_wins_and_the_bearer_is_not_read(exapp_env: None) -> None:
    """T-03-57, D-27: the branch is decided by the user id, and never by a second header."""
    headers = {**appapi_headers(user="bob"), "Authorization": "Bearer a-token-of-somebody-else"}

    creds = deps.resolve_credentials(FakeContext(headers=headers, identity=identity()))

    assert creds.mode == "appapi"
    assert creds.user == "bob", "the impersonation path, although an identity was deposited"
    assert creds.secret == APP_SECRET


def test_the_docstring_describes_the_behaviour_the_code_has() -> None:
    """The paragraph that said the opposite is gone, and the condition is named."""
    source = deps.__doc__ or ""

    assert "is not read" not in source
    assert "empty" in source.lower(), "the docstring names when the bearer is read"


# --- the whole way, from a token in the store to the credentials of a tool call --------------


@pytest.mark.anyio
async def test_the_durchstich_from_a_stored_token_to_the_credentials(
    tmp_path: Path, exapp_env: None
) -> None:
    """One token, one verification, one identity, one set of credentials. No network."""
    store = OAuthStore(tmp_path / "oauth.sqlite3", KEY)

    async def opener() -> OAuthStore:
        return store

    provider = provider_module.NextcloudOAuthProvider(
        nextcloud=exapp_target(ENV),
        env=ENV,
        policy=registry.client_policy(ENV),
        store_provider=opener,
    )
    verifier = StoreTokenVerifier(store_provider=opener, get_client=provider.get_client, env=ENV)
    await store.save_client(CLIENT_ID, metadata_json=REGISTRATION)
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        nc_account_id=NC_USER,
        app_password=APP_PASSWORD,
        scopes=TOOL_SCOPE,
        resource=RESOURCE,
    )
    await store.create_access_token(
        TOKEN, auth_id=AUTH_ID, family_id=FAMILY_ID, scopes=TOOL_SCOPE, resource=RESOURCE
    )

    access = await verifier.verify_token(TOKEN)
    assert access is not None
    resolved = await verifier.resolve_identity(access)
    assert resolved is not None
    creds = deps.resolve_credentials(
        FakeContext(headers=appapi_headers(user=""), identity=resolved)
    )

    assert creds.user == NC_USER
    assert creds.secret == APP_PASSWORD
    assert creds.mode == MODE_BASIC


# --- what never leaves this process ----------------------------------------------------------


def test_nothing_of_the_connection_reaches_a_log_or_a_repr(
    exapp_env: None, caplog: pytest.LogCaptureFixture
) -> None:
    """T-03-54: not on DEBUG, not truncated, not in the successful case either."""
    with caplog.at_level(logging.DEBUG):
        creds = deps.resolve_credentials(
            FakeContext(headers=appapi_headers(user=""), identity=identity())
        )

    assert APP_PASSWORD not in caplog.text
    assert APP_PASSWORD not in repr(creds)
    assert APP_PASSWORD not in repr(identity())
    assert caplog.text.strip() == ""


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer a-token"},
        appapi_headers(secret="wrong-secret"),
        {**appapi_headers(user=""), "AUTHORIZATION-APP-API": "not base64 at all"},
    ],
)
def test_no_refusal_ever_repeats_a_header_value(exapp_env: None, headers: dict[str, str]) -> None:
    """T-02-03, unchanged by this plan: a header is credential material, not text."""
    try:
        deps.resolve_credentials(FakeContext(headers=headers, identity=identity()))
    except deps.MCPError as exc:
        text = f"{exc.message} {exc}"
        for value in headers.values():
            assert value not in text
        assert APP_SECRET not in text
        assert APP_PASSWORD not in text

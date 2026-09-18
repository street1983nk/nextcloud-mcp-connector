"""The way from an authorization request to the Nextcloud sign in and back to a decision.

This is the surface where a person, not a program, decides something: they see who is
asking, they sign in on Nextcloud's own pages, and they come back to a screen that names
the app, its return address and what it would be allowed to do.

Threats covered here: T-03-40 (a blocked client that keeps authorizing), T-03-41 (a return
address that does not belong to the registration), T-03-42 (a self registered client with a
name that imitates a trusted one), T-03-46 (a token without an audience) and T-03-47 (an
error page that tells the caller which check fired).

Every Nextcloud answer comes from respx and the store is a SQLite file in ``tmp_path``: no
container, no network, no Nextcloud.
"""

import ast
import asyncio
import base64
import html
import inspect
import json
import logging
import re
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from mcp.shared.auth import OAuthClientInformationFull
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.entry_exapp import build_exapp_app
from mcp_connector.exapp.browser_identity import AppApiBrowserIdentitySource
from mcp_connector.exapp.target import exapp_target
from mcp_connector.exapp.ui import consent as ui_consent
from mcp_connector.exapp.ui import strings
from mcp_connector.nextcloud.target import NextcloudTarget
from mcp_connector.oauth import consent, crypto, loginflow, registry
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth.browser_identity import BrowserIdentitySource
from mcp_connector.oauth.store import AUTH_CODE_TTL, FLOW_TTL, OAuthStore, token_hash

BASE_URL = "http://nc.test"
PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
HOST = "cloud.example.com"
PREFIX = "/exapps/mcp_connector"
RESOURCE = f"{PUBLIC_URL}/mcp"

CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
CLIENT_NAME = "Claude"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

#: What Claude Code publishes in its client id metadata document, and what it arrives with
#: at runtime: the document is portless, the client listens on 3118 (06-RESEARCH.md,
#: Pattern 4, fetched 2026-08-20).
LOOPBACK_REGISTERED = "http://localhost/callback"
LOOPBACK_REQUESTED = "http://localhost:3118/callback"
STATE = "state-of-the-client"

LOGIN_URL = "https://cloud.example.com/index.php/login/v2/flow/abc123"
POLL_TOKEN = "poll-token-of-this-flow"
LOGIN_NAME = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

ENV = {
    config.ENV_PUBLIC_URL: PUBLIC_URL,
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.1.0",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
}

INIT_URL = f"{BASE_URL}{loginflow.INIT_PATH}"
POLL_URL = f"{BASE_URL}{loginflow.POLL_PATH}"
REVOKE_URL = f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}"


def start_body() -> dict[str, object]:
    return {"poll": {"token": POLL_TOKEN, "endpoint": f"{BASE_URL}/x"}, "login": LOGIN_URL}


def poll_body() -> dict[str, str]:
    return {"server": BASE_URL, "loginName": LOGIN_NAME, "appPassword": APP_PASSWORD}


ACCOUNT_URL = f"{BASE_URL}{loginflow.ACCOUNT_PATH}"


def account_body(account: str = LOGIN_NAME, display_name: str | None = None) -> dict[str, object]:
    """The answer of OCS ``cloud/user`` for the fresh app password: the canonical id."""
    data: dict[str, object] = {"id": account}
    if display_name is not None:
        data["displayname"] = display_name
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": data}}


@pytest.fixture
def store(tmp_path: Path) -> OAuthStore:
    return OAuthStore(tmp_path / "oauth.sqlite3", KEY)


def make(store: OAuthStore, **env: str) -> provider_module.NextcloudOAuthProvider:
    async def provide() -> OAuthStore:
        return store

    return provider_module.NextcloudOAuthProvider(
        nextcloud=exapp_target(ENV | env),
        env=ENV | env,
        policy=registry.client_policy(ENV | env),
        store_provider=provide,
    )


def application(provider: provider_module.NextcloudOAuthProvider, **env: str) -> Starlette:
    deployed_env = ENV | env
    return application_with_identity(
        provider,
        AppApiBrowserIdentitySource(deployed_env),
        **env,
    )


def application_with_identity(
    provider: provider_module.NextcloudOAuthProvider,
    browser_identity: BrowserIdentitySource,
    **env: str,
) -> Starlette:
    deployed_env = ENV | env
    return Starlette(
        routes=[
            *provider_module.auth_routes(ENV | env, provider=provider),
            *consent.consent_routes(
                deployed_env,
                provider=provider,
                browser_identity=browser_identity,
                nextcloud=exapp_target(deployed_env),
            ),
        ]
    )


def register(provider: provider_module.NextcloudOAuthProvider, **fields: object) -> None:
    payload: dict[str, object] = {
        "client_id": CLIENT_ID,
        "client_name": CLIENT_NAME,
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "nextcloud",
    }
    payload.update(fields)
    asyncio.run(provider.register_client(OAuthClientInformationFull.model_validate(payload)))


def authorize_query(**overrides: str) -> dict[str, str]:
    query = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "redirect_uri": REDIRECT,
        "state": STATE,
        "scope": "nextcloud",
        "resource": RESOURCE,
    }
    query.update(overrides)
    return {key: value for key, value in query.items() if value}


def start(client: TestClient, **overrides: str) -> Any:
    """The authorization request itself, without following the redirect.

    The return type stays loose on purpose: the test client of Starlette answers with the
    response model of the httpx fork the SDK brings, which is a different class than the
    one this project imports (docs/dependency-audit.md).
    """
    return client.get("/authorize", params=authorize_query(**overrides), follow_redirects=False)


def flow_of(response: Any) -> str:
    location = response.headers["location"]
    match = re.search(r"flow=([A-Za-z0-9_-]+)", location)
    assert match is not None, location
    return match.group(1)


def consent_url(flow_id: str, *, step: str = "") -> str:
    query = f"{ui_consent.FLOW_PARAM}={flow_id}"
    if step:
        query += f"&{ui_consent.STEP_PARAM}={step}"
    return f"{ui_consent.CONSENT_PATH}?{query}"


# --- the authorization request -----------------------------------------------------------


def test_the_request_opens_a_flow_and_sends_the_browser_to_our_own_page(
    store: OAuthStore,
) -> None:
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))

    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client)

    assert response.status_code == 302
    assert init.call_count == 1
    location = response.headers["location"]
    assert location.startswith(f"{PUBLIC_URL}{ui_consent.CONSENT_PATH}?")
    assert response.headers["cache-control"] == "no-store"


def test_the_flow_carries_every_field_of_the_request_and_twenty_minutes(
    store: OAuthStore,
) -> None:
    """Everything plan 03-06 needs to build a code out of it, and nothing more."""
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))

    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client)

    row = asyncio.run(store.load_flow(flow_of(response)))
    assert row is not None
    assert row.client_id == CLIENT_ID
    assert row.redirect_uri == REDIRECT
    assert row.redirect_uri_explicit is True
    assert row.code_challenge == CHALLENGE
    assert row.state == STATE
    assert row.scopes == "nextcloud"
    assert row.resource == RESOURCE
    assert row.poll_token == POLL_TOKEN
    assert 0 < row.expires_at - int(time.time()) <= FLOW_TTL


def test_the_client_name_reaches_nextcloud_cleaned_and_prefixed(store: OAuthStore) -> None:
    """T-03-43: the name is attacker input and becomes a header at Nextcloud (pitfall 8)."""
    provider = make(store)
    register(provider, client_name="Evil\r\nX-Injected: 1")
    client = TestClient(application(provider))

    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        start(client)

    agent = init.calls[0].request.headers["user-agent"]
    assert agent.startswith(loginflow.AGENT_PREFIX)
    assert "\r" not in agent
    assert "\n" not in agent


def test_a_request_without_the_resource_parameter_is_refused(store: OAuthStore) -> None:
    """T-03-46: a token without an audience would be valid at every other MCP server."""
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))

    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client, resource="")

    assert init.call_count == 0, "no sign in is opened for a request that cannot be granted"
    assert response.status_code == 302
    assert "error=invalid_target" in response.headers["location"]


def test_a_request_for_another_resource_is_refused(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))

    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client, resource="https://other.example.com/mcp")

    assert "error=invalid_target" in response.headers["location"]


def test_a_return_address_that_is_not_registered_never_becomes_a_redirect(
    store: OAuthStore,
) -> None:
    """T-03-41: the answer is a page, and above all it is not a redirect anywhere."""
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))

    response = start(client, redirect_uri="https://attacker.example/callback")

    assert response.status_code == 400
    assert "location" not in response.headers
    assert strings.ERROR_REDIRECT_TITLE in response.text


# --- the loopback port rule (RFC 8252 7.3, CLIENT-05) ------------------------------------


def test_a_loopback_client_may_come_back_on_the_port_it_got(store: OAuthStore) -> None:
    """CLIENT-05: what Claude Code publishes, and what it arrives with.

    The metadata document names ``http://localhost/callback`` without a port and the client
    listens on 3118. RFC 8252 7.3 makes accepting that a MUST, and the address that travels
    on is the requested one, with its port, because that is what the token endpoint of the
    SDK compares the token request against later.
    """
    provider = make(store)
    register(provider, redirect_uris=[LOOPBACK_REGISTERED])
    client = TestClient(application(provider))

    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client, redirect_uri=LOOPBACK_REQUESTED)

    assert response.status_code == 302
    assert response.headers["location"].startswith(f"{PUBLIC_URL}{ui_consent.CONSENT_PATH}?")
    row = asyncio.run(store.load_flow(flow_of(response)))
    assert row is not None
    assert row.redirect_uri == LOOPBACK_REQUESTED
    assert row.redirect_uri_explicit is True


def test_the_relaxed_port_is_never_written_into_the_registration(store: OAuthStore) -> None:
    """T-06-19: a comparison that registered its input would grow the row every run."""
    provider = make(store)
    register(provider, redirect_uris=[LOOPBACK_REGISTERED])
    client = TestClient(application(provider))

    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        start(client, redirect_uri=LOOPBACK_REQUESTED)

    row = asyncio.run(store.load_client(CLIENT_ID))
    assert row is not None
    assert LOOPBACK_REGISTERED in row.metadata_json
    assert "3118" not in row.metadata_json


def test_a_host_change_is_not_a_port_change(store: OAuthStore) -> None:
    """RFC 8252 8.3: the name and the literal do not resolve through the same mechanism."""
    provider = make(store)
    register(provider, redirect_uris=[LOOPBACK_REGISTERED])
    client = TestClient(application(provider))

    response = start(client, redirect_uri="http://127.0.0.1:3118/callback")

    assert response.status_code == 400
    assert "location" not in response.headers
    assert strings.ERROR_REDIRECT_TITLE in response.text


def test_a_hosted_connector_gains_no_port_freedom(store: OAuthStore) -> None:
    """T-06-16: the relaxation is for loopback, so an https address is compared exactly."""
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))

    response = start(client, redirect_uri="https://claude.ai:8443/api/mcp/auth_callback")

    assert response.status_code == 400
    assert strings.ERROR_REDIRECT_TITLE in response.text


def test_the_registration_rule_still_runs_after_the_port_was_relaxed(
    store: OAuthStore,
) -> None:
    """T-03-41 with the port rule in front of it: a relaxation must not skip D-35.

    The registration is written straight into the store, because the registration endpoint
    would have dropped this address (that is D-35 at the other end). It is the shape of a
    row from a build before the rule, and the check where the address is *used* is the one
    that catches it.
    """
    provider = make(store)
    metadata = {
        "client_id": CLIENT_ID,
        "client_name": CLIENT_NAME,
        "redirect_uris": ["ws://localhost/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "nextcloud",
    }
    asyncio.run(store.save_client(CLIENT_ID, metadata_json=json.dumps(metadata)))
    client = TestClient(application(provider))

    response = start(client, redirect_uri="ws://localhost:3118/callback")

    assert response.status_code == 400
    assert strings.ERROR_REDIRECT_TITLE in response.text


def test_a_loopback_request_without_a_registration_is_still_refused(
    store: OAuthStore,
) -> None:
    """The rule matches against a registration; it does not replace having one."""
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))

    response = start(client, redirect_uri=LOOPBACK_REQUESTED)

    assert response.status_code == 400
    assert strings.ERROR_REDIRECT_TITLE in response.text


def test_a_client_that_is_not_on_the_allowlist_reaches_the_administrator_page(
    store: OAuthStore,
) -> None:
    provider = make(store, **{registry.ENV_ALLOWLIST_ONLY: "1"})
    register(provider)
    client = TestClient(application(provider, **{registry.ENV_ALLOWLIST_ONLY: "1"}))

    response = start(client)

    assert response.status_code == 403
    assert strings.ERROR_ALLOWLIST_TITLE in response.text


def test_an_unknown_client_with_registration_switched_off_reads_the_reason(
    store: OAuthStore,
) -> None:
    provider = make(store, **{registry.ENV_DCR: "off"})
    client = TestClient(application(provider, **{registry.ENV_DCR: "off"}))

    response = start(client)

    assert response.status_code == 400
    assert strings.ERROR_REGISTRATION_OFF_TITLE in response.text


def test_an_unknown_client_while_registration_is_open_is_sent_back_to_its_app(
    store: OAuthStore,
) -> None:
    """T-03-47: the same answer an expired registration gets, and no other information."""
    provider = make(store)
    client = TestClient(application(provider))

    response = start(client)

    assert response.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in response.text


def test_the_bare_address_is_the_empty_state_and_not_a_protocol_error(
    store: OAuthStore,
) -> None:
    """Where "Start over" of the timeout page leads, so it has to read as a sentence."""
    provider = make(store)
    client = TestClient(application(provider))

    response = client.get("/authorize")

    assert response.status_code == 400
    assert strings.EMPTY_TITLE in response.text
    assert strings.EMPTY_BODY in response.text


# --- the consent surface ------------------------------------------------------------------


def opened(
    provider: provider_module.NextcloudOAuthProvider,
) -> tuple[TestClient, str, str]:
    """Run one authorization request and return what the browser would follow.

    The third value is the address of the redirect with the public prefix removed, which
    is exactly the path this application sees behind HaRP.
    """
    client = TestClient(application(provider))
    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client)
    target = response.headers["location"].removeprefix(PUBLIC_URL)
    return client, flow_of(response), target


def test_the_first_page_hands_the_user_over_to_nextcloud(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client, _flow_id, target = opened(provider)

    with respx.mock:
        poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        response = client.get(target)

    assert response.status_code == 200
    assert poll.call_count == 0, "the handoff page polls nothing, it only hands over"
    assert f'href="{LOGIN_URL}"' in response.text
    assert 'rel="noopener noreferrer"' in response.text
    assert strings.SIGNIN_CTA in response.text
    assert CLIENT_NAME in response.text


def test_the_waiting_page_polls_exactly_once_per_load(store: OAuthStore) -> None:
    """T-03-34: the refresh is the throttle, so one load has to be one poll."""
    provider = make(store)
    register(provider)
    client, _flow_id, target = opened(provider)

    wait_target = f"{target}&{ui_consent.STEP_PARAM}={ui_consent.STEP_WAIT}"
    with respx.mock:
        poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        client.get(wait_target)
        client.get(wait_target)
        response = client.get(wait_target)

    assert poll.call_count == 3
    assert response.status_code == 200
    assert '<meta http-equiv="refresh"' in response.text
    assert strings.WAIT_STATUS.format(host=HOST) in response.text


def test_a_finished_sign_in_turns_into_the_consent_screen(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert response.status_code == 200
    assert strings.CONSENT_TITLE.format(client=CLIENT_NAME) in response.text
    assert strings.CONSENT_IDENTITY.format(user=LOGIN_NAME, host=HOST) in response.text
    assert REDIRECT in response.text
    assert CLIENT_ID in response.text
    assert strings.CONSENT_GRANT_READ in response.text


def test_the_credential_of_the_sign_in_is_stored_and_never_rendered(
    store: OAuthStore, tmp_path: Path
) -> None:
    """The app password belongs to the connection, not to the page (D-34, T-03-33)."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert APP_PASSWORD not in response.text
    row = asyncio.run(store.load_authorization(flow_id))
    assert row is not None
    assert row.nc_user == LOGIN_NAME
    assert row.resource == RESOURCE
    assert asyncio.run(store.app_password(flow_id)) == APP_PASSWORD
    assert APP_PASSWORD.encode() not in _store_bytes(tmp_path)


def _store_bytes(directory: Path) -> bytes:
    return b"".join(path.read_bytes() for path in sorted(directory.iterdir()) if path.is_file())


def test_a_second_load_after_the_sign_in_does_not_poll_again(store: OAuthStore) -> None:
    """The 200 of a poll arrives exactly once, so the screen has to survive a refresh."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        poll = respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))
        second = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert poll.call_count == 1
    assert second.status_code == 200
    assert strings.CONSENT_TITLE.format(client=CLIENT_NAME) in second.text


def test_the_unverified_callout_is_there_for_a_self_registered_client(
    store: OAuthStore,
) -> None:
    """T-03-42: a name from a registration is not a name Nextcloud vouched for."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert strings.CONSENT_WARNING_TITLE in response.text
    assert strings.CONSENT_WARNING_BODY in response.text


def test_the_unverified_callout_is_absent_for_a_listed_client(store: OAuthStore) -> None:
    listed = {registry.ENV_ALLOWED_CLIENTS: REDIRECT}
    provider = make(store, **listed)
    register(provider)
    client = TestClient(application(provider, **listed))
    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        flow_id = flow_of(start(client))
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert strings.CONSENT_WARNING_TITLE not in response.text


# --- the two display duties of a document identity (AUTH-08, plan 06-06) -----------------
#
# The screen renders them and this route computes them, which is the mechanism ``unverified``
# already uses. What is checked here is therefore the computation: a document identity has a
# host to show, a registration has none, and the loopback question hangs on the addresses and
# not on the path a client took to get registered.

#: The candidate client of AUTH-08 and the two portless loopback addresses of its document,
#: measured on 2026-08-20 (06-RESEARCH.md, pattern 4).
CIMD_CLIENT_ID = "https://claude.ai/oauth/claude-code-client-metadata"
CIMD_HOST = "claude.ai"
CIMD_URIS = [LOOPBACK_REGISTERED, "http://127.0.0.1/callback"]


#: The document such a client publishes, and the address its name resolves to in this file.
#: No name is ever looked up: the provider of the fetch checks below carries a resolver that
#: answers this literal, so ``respx`` sees the pinned request and no socket is opened.
CIMD_IP = "93.184.216.34"
CIMD_FETCH_URL = "https://93.184.216.34/oauth/claude-code-client-metadata"
CIMD_DOCUMENT: dict[str, object] = {
    "client_id": CIMD_CLIENT_ID,
    "client_name": "Claude Code",
    "client_uri": "https://claude.ai",
    "redirect_uris": CIMD_URIS,
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}


def save_document_client(
    store: OAuthStore,
    *,
    redirect_uris: list[str] | None = None,
    client_name: str = "Claude Code",
    expires_in: int = 3600,
) -> None:
    """A row as the document branch of ``get_client`` writes it, fresh unless asked otherwise.

    Fresh by default: a row inside its freshness window is handed straight back, so nothing
    here fetches a document and no check of this file opens a socket for one. A negative
    ``expires_in`` is what the fetch checks below want, a row whose deadline has passed.
    """
    metadata = {
        "client_id": CIMD_CLIENT_ID,
        "client_name": client_name,
        "redirect_uris": redirect_uris or CIMD_URIS,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "nextcloud",
    }
    moment = int(time.time())
    asyncio.run(
        store.save_client(
            CIMD_CLIENT_ID,
            metadata_json=json.dumps(metadata),
            cimd_fetched_at=moment,
            cimd_expires_at=moment + expires_in,
        )
    )


def resolving(*addresses: str) -> Callable[[str, int], Awaitable[list[str]]]:
    """A resolver that answers with these literals, so no name of a test is looked up."""

    async def resolve(host: str, port: int) -> list[str]:
        del host, port
        return list(addresses)

    return resolve


def fetching(store: OAuthStore, **env: str) -> provider_module.NextcloudOAuthProvider:
    """The provider of :func:`make`, with the resolver a pinned fetch needs."""

    async def provide() -> OAuthStore:
        return store

    return provider_module.NextcloudOAuthProvider(
        nextcloud=exapp_target(ENV | env),
        env=ENV | env,
        policy=registry.client_policy(ENV | env),
        store_provider=provide,
        resolver=resolving(CIMD_IP),
    )


def cimd_route() -> respx.Route:
    """The transport of one document fetch, answered at the pinned address."""
    return respx.get(CIMD_FETCH_URL).mock(return_value=httpx.Response(200, json=CIMD_DOCUMENT))


def signed_in_screen(provider: provider_module.NextcloudOAuthProvider, **overrides: str) -> str:
    """The consent screen of one finished sign in, as text."""
    client = TestClient(application(provider))
    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        flow_id = flow_of(start(client, **overrides))
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))
    assert response.status_code == 200, response.text
    return response.text


def test_a_document_identity_shows_its_host_and_both_warnings(store: OAuthStore) -> None:
    """The MUST and the SHOULD of the specification on one page, for the one client the
    phase is about: the identifier is a URL, and every address of it is loopback."""
    provider = make(store)
    save_document_client(store)

    page = signed_in_screen(provider, client_id=CIMD_CLIENT_ID, redirect_uri=LOOPBACK_REQUESTED)

    assert strings.CONSENT_DETAIL_CLIENT_HOST in page
    assert CIMD_HOST in page
    assert strings.CONSENT_WARNING_TITLE in page, "nobody listed it"
    assert strings.CONSENT_LOOPBACK_TITLE in page, "and every address of it is loopback"


def test_a_registered_client_with_a_hosted_address_shows_neither(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)

    page = signed_in_screen(provider)

    assert strings.CONSENT_DETAIL_CLIENT_HOST not in page
    assert strings.CONSENT_LOOPBACK_TITLE not in page


def test_a_registered_client_on_loopback_gets_the_warning_without_a_host(
    store: OAuthStore,
) -> None:
    """The flag hangs on the return address, the origin on the identifier (T-06-35).

    Cursor's own loopback address, as it registers it: any program on that machine can hold
    the port, and that risk does not become smaller because this client registered itself
    instead of publishing a document.
    """
    provider = make(store)
    register(provider, redirect_uris=["http://localhost:8787/callback"])

    page = signed_in_screen(provider, redirect_uri="http://localhost:8787/callback")

    assert strings.CONSENT_LOOPBACK_TITLE in page
    assert strings.CONSENT_DETAIL_CLIENT_HOST not in page


@pytest.mark.parametrize(
    ("addresses", "expected"),
    [
        ([], False),
        (CIMD_URIS, True),
        (["http://localhost:8787/callback", "http://[::1]:9000/cb"], True),
        (["http://localhost/callback", REDIRECT], False),
        ([REDIRECT], False),
        (["http://localhost:99999/callback"], False),
    ],
    ids=["none at all", "the document", "every spelling", "one hosted", "hosted", "unparsable"],
)
def test_the_loopback_flag_is_all_of_them_and_never_none_of_them(
    addresses: list[str], expected: bool
) -> None:
    """A client with no return address is not a loopback client, it is a client that ends
    on the redirect page before this screen; that is why the empty list is ``False`` and not
    a vacuous truth. Checked on the computation itself, because the route cannot deliver a
    client without an address to the consent screen at all.
    """
    assert consent._loopback_only(addresses) is expected


@pytest.mark.parametrize(
    ("client_id", "expected"),
    [
        (CIMD_CLIENT_ID, CIMD_HOST),
        (CLIENT_ID, None),
        ("https://claude.ai", None),
        ("http://claude.ai/oauth/document", None),
        ("https://user:pw@claude.ai/oauth/document", None),
        ("", None),
    ],
    ids=["a document url", "a registration", "no path", "not https", "user info", "empty"],
)
def test_the_host_is_read_from_the_identifier_and_from_nothing_else(
    client_id: str, expected: str | None
) -> None:
    """No store row is read for it: the string carries the fact, and this route costs
    exactly one Nextcloud round trip per request (SC 5 of phase 3)."""
    assert consent._identifier_host(client_id) == expected


# --- the default of may_fetch, pinned at the call sites of this route (W-06) --------------
#
# ``get_client(client_id)`` fetches a document; ``get_client(client_id, may_fetch=False)``
# does not, and since plan 06-10 every hot path passes the second form: the verifier of a
# tool call, the client authentication of /token and /revoke, and both exchanges. This route
# is the one place that must keep the default, because it is the one place where a person
# with a browser is waiting and a first connection has to be possible at all. That default is
# a keyword nobody sees when it is right, so it gets checks of its own: a may_fetch=False
# that slipped into consent.py would turn every first connection of such a client into an
# error page, and every check of the file above would stay green, because they all place a
# fresh row in the store by hand.


def test_the_authorize_chain_fetches_the_document_of_an_identity_it_has_no_row_for(
    store: OAuthStore,
) -> None:
    """The first connection of a document client, end to end through the real route.

    No row exists, so the identity can only come from the document, and the fetch is what
    makes the request survive. What is asserted is the outbound call plus its consequence:
    the browser goes to our own page instead of an error page, and the row is written.
    """
    provider = fetching(store)
    client = TestClient(application(provider))

    with respx.mock:
        route = cimd_route()
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client, client_id=CIMD_CLIENT_ID, redirect_uri=LOOPBACK_REQUESTED)

    assert route.called, "the consent route asked the document host"
    assert response.status_code == 302, response.text
    assert ui_consent.CONSENT_PATH in response.headers["location"]
    assert asyncio.run(store.load_client(CIMD_CLIENT_ID)) is not None


def test_the_authorize_chain_reads_a_document_again_once_its_window_has_passed(
    store: OAuthStore,
) -> None:
    """T-06-32 at this route: the refetch belongs to the path with a person on it.

    The row is past its freshness deadline, which is the state the hot paths deliberately
    keep answering from. Here it costs exactly one fetch, and the new reading is the identity
    that travels on: the name of the earlier reading is gone from the screen.
    """
    provider = fetching(store)
    save_document_client(store, client_name="The name of an earlier reading", expires_in=-1)
    client = TestClient(application(provider))

    with respx.mock:
        route = cimd_route()
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        flow_id = flow_of(start(client, client_id=CIMD_CLIENT_ID, redirect_uri=LOOPBACK_REQUESTED))
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        page = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert route.call_count >= 1
    assert page.status_code == 200, page.text
    assert "The name of an earlier reading" not in page.text


def test_no_call_of_this_module_switches_the_fetch_off() -> None:
    """The same rule as the two checks above, on the three call sites at once.

    The first of them is caught end to end, and the two behind it are reached only after it
    has already refreshed the row, so a transport check cannot tell them apart. The keyword
    can: this route keeps the default everywhere, and a ``may_fetch=False`` anywhere in it is
    a deliberate change that has to argue with this line.
    """
    tree = ast.parse(inspect.getsource(consent))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_client"
    ]

    assert calls, "this route asks the provider about the client, or the gate reads nothing"
    for call in calls:
        assert not [keyword for keyword in call.keywords if keyword.arg == "may_fetch"], (
            "the consent route is the one path that pays the refetch (WR-01, WR-03)"
        )


def test_a_fresh_row_still_costs_this_route_no_packet_at_all(store: OAuthStore) -> None:
    """The counter probe of both checks above, and the whole point of the freshness window.

    Without it the two checks above would also pass with a route that fetches on every
    single request, which is the shape plan 06-05 exists against.
    """
    provider = fetching(store)
    save_document_client(store)
    client = TestClient(application(provider))

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(CIMD_FETCH_URL)
        mock.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = start(client, client_id=CIMD_CLIENT_ID, redirect_uri=LOOPBACK_REQUESTED)

    assert route.called is False
    assert response.status_code == 302, response.text


def test_an_expired_flow_shows_the_timeout_page_and_stops_polling(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)
    _age_flow(store, flow_id)

    with respx.mock:
        poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))
        again = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert poll.call_count == 0
    assert response.status_code == 408
    assert strings.ERROR_TIMEOUT_TITLE in response.text
    assert again.status_code == 400, "the record is gone, so the next load is the expired page"


def _age_flow(store: OAuthStore, flow_id: str) -> None:
    """Move the deadline of one flow into the past, without touching the clock."""
    conn = sqlite3.connect(store.path)
    try:
        conn.execute(
            "UPDATE flows SET expires_at = ? WHERE flow_id = ?", (int(time.time()) - 1, flow_id)
        )
        conn.commit()
    finally:
        conn.close()


def test_an_unknown_flow_is_the_expired_page(store: OAuthStore) -> None:
    provider = make(store)
    client = TestClient(application(provider))

    response = client.get(consent_url("not-a-flow-id"))

    assert response.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in response.text


def test_a_client_blocked_after_the_sign_in_does_not_reach_the_decision(
    store: OAuthStore,
) -> None:
    """T-03-40: the enforcement point is asked again on the way to the decision."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)
    asyncio.run(store.save_client(CLIENT_ID, metadata_json='{"client_id": "x"}', allowed=False))

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert response.status_code in (400, 403)
    assert strings.CONSENT_APPROVE not in response.text


# --- the decision -----------------------------------------------------------------------


def signed_in(provider: provider_module.NextcloudOAuthProvider) -> tuple[TestClient, str, str]:
    """One flow that reached the consent screen, plus the screen it rendered."""
    client, flow_id, _target = opened(provider)
    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        page = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))
    return client, flow_id, page.text


def appapi_headers(user: str) -> dict[str, str]:
    """The three headers HaRP attaches to a request on a ``USER`` route.

    These tests speak to the application directly, so they stand in for the proxy. The
    value of ``AUTHORIZATION-APP-API`` is base64 of ``<user>:<APP_SECRET>``, which is what
    HaRP builds out of the Nextcloud account it resolved and the registration secret of
    this app, and which is why no caller can write it: the secret is not theirs.
    """
    raw = f"{user}:{ENV[config.ENV_APP_SECRET]}".encode()
    return {
        "EX-APP-ID": ENV[config.ENV_APP_ID],
        "EX-APP-VERSION": ENV[config.ENV_APP_VERSION],
        "AUTHORIZATION-APP-API": base64.b64encode(raw).decode("ascii"),
    }


def decide(
    client: TestClient,
    flow_id: str,
    decision: str,
    *,
    store: OAuthStore | None = None,
    confirm: str | None = None,
    user: str | None = LOGIN_NAME,
) -> Any:
    """One press of one of the two buttons, exactly as the rendered form sends it.

    ``user`` is the Nextcloud account HaRP resolved for the browser that presses it, and
    ``None`` is the anonymous request: no headers at all, which is what an attacker without
    a Nextcloud session can send (CR-01).
    """
    token = (
        confirm
        if confirm is not None
        else (store.form_token(flow_id, purpose=crypto.PURPOSE_CONSENT) if store else "")
    )
    return client.post(
        ui_consent.DECIDE_PATH,
        data={
            ui_consent.FLOW_PARAM: flow_id,
            ui_consent.DECISION_PARAM: decision,
            ui_consent.CONFIRM_PARAM: token,
        },
        headers=appapi_headers(user) if user is not None else {},
        follow_redirects=False,
    )


class StubBrowserIdentitySource:
    """A deployment-selected authority without AppAPI headers."""

    def __init__(self, answer: bool = True, *, fail: bool = False) -> None:
        self.answer = answer
        self.fail = fail
        self.expected: str | None = None
        self.path: str | None = None

    async def identifies(
        self, request: Request, expected_account_id: str, *, flow_id: str | None = None
    ) -> bool:
        self.expected = expected_account_id
        self.path = request.url.path
        if self.fail:
            raise RuntimeError("synthetic identity-source failure")
        return self.answer

    async def pending_step(
        self, request: Request, *, flow_id: str, expected_account_id: str
    ) -> None:
        return None


def rows(store: OAuthStore, table: str) -> list[tuple[Any, ...]]:
    """Every row of one table, read straight out of the file the store writes."""
    conn = sqlite3.connect(store.path)
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608
    finally:
        conn.close()


def _columns(store: OAuthStore, table: str) -> list[str]:
    """The column names of one table, so a test reads a row by name and not by position."""
    conn = sqlite3.connect(store.path)
    try:
        return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def snapshot(store: OAuthStore) -> dict[str, list[tuple[Any, ...]]]:
    """The three tables a decision may touch, so a test can prove none of them moved."""
    return {name: rows(store, name) for name in ("flows", "authorizations", "auth_codes")}


def returned_to(response: Any) -> str:
    """Where this answer sends the browser, out of a redirect or out of a return page.

    Since CR-03 the decision answers 200 with a page that navigates instead of a 302 to the
    client: Chromium and WebKit check ``form-action`` against the target of a redirect that
    follows a form submission, and every page of this phase carries ``form-action 'self'``.
    The authorization endpoint still answers a redirect, so both shapes are read here.
    """
    location = response.headers.get("location")
    if location:
        return str(location)
    match = re.search(r'content="0; url=([^"]+)"', response.text)
    assert match is not None, response.text
    target = html.unescape(match.group(1))
    assert f'href="{match.group(1)}"' in response.text, "the address is not readable as a link"
    return target


def query_of(response: Any) -> dict[str, list[str]]:
    return parse_qs(urlsplit(returned_to(response)).query)


def test_an_approval_returns_to_the_client_with_code_state_and_iss(store: OAuthStore) -> None:
    """The one moment of this phase that grants something, and the shape RFC 9207 wants.

    Answered with a page that navigates and not with a 302 since CR-03: the decision is a
    form submission, and Chromium and WebKit check ``form-action`` against the target of a
    redirect that follows one, so the redirect this used to answer never arrived in those
    browsers. The address is the same, and it is in the page as a link as well as in the
    refresh, so a reader sees where they are being sent.
    """
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 200
    assert "location" not in response.headers, "a 302 out of a form post is refused by CSP"
    assert returned_to(response).startswith(REDIRECT)
    assert "form-action 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    query = query_of(response)
    assert query["state"] == [STATE]
    assert query["iss"] == [PUBLIC_URL], "the issuer is the configured public URL (RFC 9207)"
    assert len(query["code"]) == 1
    assert len(rows(store, "authorizations")) == 1, "exactly one authorization, not a second"
    assert asyncio.run(store.load_flow(flow_id, now=0)) is None, "the flow is spent"


def test_the_code_lives_sixty_seconds_and_is_redeemable_exactly_once(
    store: OAuthStore,
) -> None:
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)
    code = query_of(response)["code"][0]

    stored = rows(store, "auth_codes")
    assert len(stored) == 1
    assert stored[0][0] == token_hash(code), "the code stands in the file as its digest only"
    assert code not in _store_bytes(store.path.parent).decode("utf-8", "ignore")
    first = asyncio.run(store.redeem_auth_code(code))
    second = asyncio.run(store.redeem_auth_code(code))
    assert first is not None
    assert second is None
    assert first.auth_id == flow_id
    assert first.code_challenge == CHALLENGE
    assert first.redirect_uri == REDIRECT
    assert first.resource == RESOURCE
    expires_at = dict(zip(_columns(store, "auth_codes"), stored[0], strict=True))["expires_at"]
    assert 0 < expires_at - int(time.time()) <= AUTH_CODE_TTL


def test_a_get_never_grants_anything_whatever_it_carries(store: OAuthStore) -> None:
    """T-03-50: a state change is a POST, so a GET with a decision in it changes nothing."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    before = snapshot(store)

    response = client.get(
        f"{consent_url(flow_id)}&{ui_consent.DECISION_PARAM}={ui_consent.DECISION_APPROVE}"
        f"&{ui_consent.CONFIRM_PARAM}={store.form_token(flow_id, purpose=crypto.PURPOSE_CONSENT)}",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "location" not in response.headers
    assert snapshot(store) == before, "not one row of the store moved"


def test_a_denial_answers_access_denied_and_hands_the_credential_back(
    store: OAuthStore,
) -> None:
    """A refused connection must not leave a usable Nextcloud credential behind (D-34)."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_DENY, store=store)

    assert response.status_code == 200
    assert returned_to(response).startswith(REDIRECT)
    assert revoke.call_count == 1, "one attempt, no retry"
    query = query_of(response)
    assert query["error"] == ["access_denied"]
    assert query["state"] == [STATE]
    assert query["iss"] == [PUBLIC_URL]
    assert "code" not in query
    assert rows(store, "authorizations") == [], "no authorization survives a denial"
    assert rows(store, "auth_codes") == []
    assert asyncio.run(store.load_flow(flow_id, now=0)) is None


@pytest.mark.parametrize("confirm", ["", "not-the-token", "0" * 64])
def test_a_decision_without_the_anti_forgery_token_changes_nothing(
    store: OAuthStore, confirm: str
) -> None:
    """T-03-50: the value is bound to this flow and to this deployment, and nothing else."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    before = snapshot(store)

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, confirm=confirm)

    assert response.status_code == 400
    assert "location" not in response.headers
    assert snapshot(store) == before


def test_a_consent_form_of_the_previous_window_still_decides(store: OAuthStore) -> None:
    """BL-08: a consent screen open across an hour boundary must still submit once."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    previous = store.form_token(
        flow_id,
        purpose=crypto.PURPOSE_CONSENT,
        now=time.time() - crypto.FORM_TOKEN_WINDOW,
    )
    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, confirm=previous)

    assert response.status_code == 200
    assert query_of(response)["code"], "the decision went through"


def test_a_consent_form_older_than_two_windows_decides_nothing(store: OAuthStore) -> None:
    """The value expires, and an expired one is refused exactly like a forged one."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    before = snapshot(store)

    expired = store.form_token(
        flow_id,
        purpose=crypto.PURPOSE_CONSENT,
        now=time.time() - 2 * crypto.FORM_TOKEN_WINDOW - 1,
    )
    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, confirm=expired)

    assert response.status_code == 400
    assert "location" not in response.headers
    assert snapshot(store) == before


def test_the_value_of_a_disconnect_form_does_not_approve_a_consent(store: OAuthStore) -> None:
    """ME-01: an authorization is written under the id of its own flow, so ``auth_id`` and
    ``flow_id`` are the same string. Without a purpose in the derivation the value that says
    "approve this request" is byte for byte the value that says "end this connection", and
    whoever sees one of them holds the other for good."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    before = snapshot(store)

    other_purpose = store.form_token(flow_id, purpose=crypto.PURPOSE_DISCONNECT)
    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, confirm=other_purpose)

    assert response.status_code == 400
    assert "location" not in response.headers
    assert snapshot(store) == before


def test_a_second_decision_on_the_same_flow_creates_nothing_more(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    first = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)
    second = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert first.status_code == 200
    assert second.status_code == 400
    assert len(rows(store, "auth_codes")) == 1
    assert len(rows(store, "authorizations")) == 1


# --- BL-19: two decisions on one flow that arrive at the same moment ----------------------
#
# The second press of the button was always refused, but only because the first one had
# already finished: the write was an insert of a code followed by a delete of the flow, after
# a read that had found the flow. Two decisions that pass that read before either of them
# writes are the same press twice as far as the store is concerned, and until this section
# existed, both of them wrote. One consent then carried two codes, which is the one promise
# an authorization code makes.


def _both_past_the_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold every decision at the last read before its write, until two of them are there.

    The window this opens is the real one, not an imitation of it: the gate sits on the last
    check :func:`consent._decide` runs, so both requests have read the flow, the client, the
    authorization and the account switch, and the next thing either of them does is the write.
    """
    barrier = threading.Barrier(2, timeout=10)
    original = consent._access_disabled

    async def gated(store: OAuthStore, nc_user: str) -> bool | None:
        answer = await original(store, nc_user)
        await asyncio.to_thread(barrier.wait)
        return answer

    monkeypatch.setattr(consent, "_access_disabled", gated)


def _at_once(first: Callable[[], Any], second: Callable[[], Any]) -> list[Any]:
    """Both requests in their own thread, and both answers once they are back."""
    answers: list[Any] = [None, None]
    failures: list[BaseException] = []

    def run(index: int, call: Callable[[], Any]) -> None:
        try:
            answers[index] = call()
        except BaseException as error:
            # Kept and raised again in the main thread, where a failure is readable.
            failures.append(error)

    threads = [
        threading.Thread(target=run, args=(0, first)),
        threading.Thread(target=run, args=(1, second)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if failures:
        raise failures[0]
    assert all(answer is not None for answer in answers), "a decision never came back"
    return answers


def test_two_approvals_that_arrive_at_once_produce_exactly_one_code(
    store: OAuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BL-19: one consent is one code, even when the two requests overlap completely."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    second_browser = TestClient(application(provider))
    _both_past_the_read(monkeypatch)

    answers = _at_once(
        lambda: decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store),
        lambda: decide(second_browser, flow_id, ui_consent.DECISION_APPROVE, store=store),
    )

    assert sorted(answer.status_code for answer in answers) == [200, 400]
    granted = next(answer for answer in answers if answer.status_code == 200)
    refused = next(answer for answer in answers if answer.status_code == 400)
    assert len(query_of(granted)["code"]) == 1
    assert strings.ERROR_EXPIRED_TITLE in refused.text, "the answer a spent flow always gets"
    assert len(rows(store, "auth_codes")) == 1, "one consent, one code"
    assert len(rows(store, "authorizations")) == 1
    assert asyncio.run(store.load_flow(flow_id, now=0)) is None


def test_an_approval_and_a_denial_that_arrive_at_once_leave_one_outcome(
    store: OAuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whichever of the two wins the flow, the other one changes nothing at all."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    second_browser = TestClient(application(provider))
    _both_past_the_read(monkeypatch)

    with respx.mock:
        respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        answers = _at_once(
            lambda: decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store),
            lambda: decide(second_browser, flow_id, ui_consent.DECISION_DENY, store=store),
        )

    approval, denial = answers
    assert sorted(answer.status_code for answer in answers) == [200, 400]
    if approval.status_code == 200:
        assert len(query_of(approval)["code"]) == 1
        assert len(rows(store, "auth_codes")) == 1, "the grant stands, whole"
        assert len(rows(store, "authorizations")) == 1
    else:
        assert query_of(denial)["error"] == ["access_denied"]
        assert rows(store, "auth_codes") == [], "a refused connection carries no code"
        assert rows(store, "authorizations") == []
    assert asyncio.run(store.load_flow(flow_id, now=0)) is None


def _spend_while_deciding(
    monkeypatch: pytest.MonkeyPatch, store: OAuthStore, spend: Callable[[], Awaitable[object]]
) -> None:
    """Let the other decision win the flow after this request has read it.

    The threaded tests above prove the race is closed, but which of the two wins is the
    business of SQLite. These two run the same window with the winner known, so the loser's
    answer and the rows it leaves are checked and not merely sampled.
    """
    original = consent._access_disabled

    async def overtaken(subject: OAuthStore, nc_user: str) -> bool | None:
        answer = await original(subject, nc_user)
        await spend()
        return answer

    monkeypatch.setattr(consent, "_access_disabled", overtaken)


def test_an_approval_that_loses_the_flow_writes_no_code(
    store: OAuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loser of the race writes nothing and answers the page a spent flow gets."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    _spend_while_deciding(monkeypatch, store, lambda: store.redeem_flow(flow_id))

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in response.text
    assert "location" not in response.headers
    assert rows(store, "auth_codes") == [], "the code of a decision that lost is never written"


def test_a_denial_that_loses_the_flow_takes_nothing_back(
    store: OAuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusing side of the same window: a late "no" may not undo a grant that happened."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    _spend_while_deciding(
        monkeypatch,
        store,
        lambda: store.redeem_flow_for_code(
            flow_id,
            "the-code-of-the-other-decision",
            redirect_uri=REDIRECT,
            code_challenge=CHALLENGE,
            resource=RESOURCE,
        ),
    )

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_DENY, store=store)

    assert response.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in response.text
    assert revoke.call_count == 0, "the credential of the granted connection stays valid"
    assert len(rows(store, "auth_codes")) == 1, "the code of the approval survives"
    assert len(rows(store, "authorizations")) == 1


def test_a_denial_after_an_approval_of_the_same_flow_takes_nothing_back(
    store: OAuthStore,
) -> None:
    """The same thing one press of a button later, without any window at all."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    first = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)
    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        second = decide(client, flow_id, ui_consent.DECISION_DENY, store=store)

    assert first.status_code == 200
    assert second.status_code == 400
    assert revoke.call_count == 0
    assert len(rows(store, "auth_codes")) == 1
    assert len(rows(store, "authorizations")) == 1


def test_an_approval_after_a_denial_of_the_same_flow_grants_nothing(store: OAuthStore) -> None:
    """And the other order: what a refusal took back stays taken back."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    with respx.mock:
        respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        first = decide(client, flow_id, ui_consent.DECISION_DENY, store=store)
    second = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert first.status_code == 200
    assert second.status_code == 400
    assert "location" not in second.headers
    assert rows(store, "auth_codes") == []
    assert rows(store, "authorizations") == []


# --- BL-20: the withdrawal of a paused account is a decision like the other two -----------
#
# The paused branch of ``_decide`` runs the denial path and answers a page of its own, and
# until this section existed it ran that path without the claim the two buttons took in
# BL-19. So a pause that arrived while an approval of the same flow was underway took back
# what the approval had just granted: the authorization was deleted, its app password was
# handed back, and the code of the approval stayed behind pointing at nothing. The token
# exchange refuses such a code, so nothing was ever granted twice, but the rows of one
# consent disagreed with each other, which is the state BL-19 exists against.


def _one_pauses_past_the_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold two decisions at the same last read, and let exactly one of them see the pause.

    The window of BL-20 is the window of BL-19 with the account switch flipped inside it: two
    tabs stand open, the person pauses their access, and the decision that read the switch
    before the pause approves while the one that read it after withdraws. A switch both of
    them read out of the store would send both down the same branch and prove nothing, so the
    answer is handed out per caller here, and neither moves before the other has one.
    """
    barrier = threading.Barrier(2, timeout=10)
    answers = iter([False, True])
    lock = threading.Lock()

    async def gated(_store: OAuthStore, _nc_user: str) -> bool | None:
        with lock:
            answer = next(answers)
        await asyncio.to_thread(barrier.wait)
        return answer

    monkeypatch.setattr(consent, "_access_disabled", gated)


def test_a_pause_and_an_approval_that_arrive_at_once_leave_one_outcome(
    store: OAuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BL-20: either a code and no withdrawal, or a withdrawal and no code. Never both."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    second_browser = TestClient(application(provider))
    _one_pauses_past_the_read(monkeypatch)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        answers = _at_once(
            lambda: decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store),
            lambda: decide(second_browser, flow_id, ui_consent.DECISION_APPROVE, store=store),
        )

    statuses = sorted(answer.status_code for answer in answers)
    if 200 in statuses:
        assert statuses == [200, 400], "the pause lost, and it lost as a spent flow does"
        granted = next(answer for answer in answers if answer.status_code == 200)
        refused = next(answer for answer in answers if answer.status_code == 400)
        assert len(query_of(granted)["code"]) == 1
        assert strings.ERROR_EXPIRED_TITLE in refused.text
        assert revoke.call_count == 0, "the credential of the granted connection stays valid"
        assert len(rows(store, "auth_codes")) == 1, "the grant stands, whole"
        assert len(rows(store, "authorizations")) == 1
    else:
        assert statuses == [400, 403], "the pause won, and the approval got the spent flow"
        withdrawn = next(answer for answer in answers if answer.status_code == 403)
        assert strings.CONNECTIONS_PAUSED_TITLE in withdrawn.text
        assert revoke.call_count == 1, "one attempt, and the app password goes back"
        assert rows(store, "auth_codes") == [], "a withdrawn connection carries no code"
        assert rows(store, "authorizations") == []
    assert asyncio.run(store.load_flow(flow_id, now=0)) is None


def test_a_pause_that_loses_the_flow_takes_nothing_back(
    store: OAuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same window with the winner known: a late pause may not undo a grant that happened."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    paused(store)
    _spend_while_deciding(
        monkeypatch,
        store,
        lambda: store.redeem_flow_for_code(
            flow_id,
            "the-code-of-the-approval-that-won",
            redirect_uri=REDIRECT,
            code_challenge=CHALLENGE,
            resource=RESOURCE,
        ),
    )

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in response.text
    assert revoke.call_count == 0, "the credential of the granted connection stays valid"
    assert len(rows(store, "auth_codes")) == 1, "the code of the approval survives"
    assert len(rows(store, "authorizations")) == 1, "and so does what it points at"


def test_an_approval_after_a_pause_of_the_same_flow_grants_nothing(store: OAuthStore) -> None:
    """The other order, and the control that the claim left the paused path itself alone."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    paused(store)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        first = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)
    second = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert first.status_code == 403
    assert strings.CONNECTIONS_PAUSED_TITLE in first.text
    assert second.status_code == 400
    assert "location" not in second.headers
    assert revoke.call_count == 1, "one attempt, and the app password goes back"
    assert rows(store, "auth_codes") == []
    assert rows(store, "authorizations") == []


# --- WR-06: a ciphertext that cannot be read is a page, never a 500 -----------------------


@pytest.mark.parametrize("step", ["", ui_consent.STEP_WAIT], ids=["screen", "waiting"])
def test_a_flow_written_with_another_data_key_is_a_page(
    store: OAuthStore, tmp_path: Path, step: str
) -> None:
    """WR-06: load_flow decrypts the poll token of the row, so a changed data key and a
    damaged blob both raise out of it. Both call sites of this module were unguarded, so
    such a row reached Starlette as a bare 500 while the docstring said the opposite."""
    provider = make(store)
    register(provider)
    _client, flow_id, _target = opened(provider)
    stranger = OAuthStore(tmp_path / "oauth.sqlite3", bytes(range(32, 64)))
    client = TestClient(application(make(stranger)))

    response = client.get(consent_url(flow_id, step=step))

    assert response.status_code == 500, "fail closed, and answered by us"
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert "Traceback" not in response.text
    assert POLL_TOKEN not in response.text


def test_a_decision_on_a_flow_that_cannot_be_read_is_a_page(
    store: OAuthStore, tmp_path: Path
) -> None:
    """The same guard on the request that would grant something (WR-06)."""
    provider = make(store)
    register(provider)
    _client, flow_id, _page = signed_in(provider)
    stranger = OAuthStore(tmp_path / "oauth.sqlite3", bytes(range(32, 64)))
    deciding = TestClient(application(make(stranger)))

    response = decide(deciding, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert rows(store, "auth_codes") == []


# --- CR-02: an authorization request costs a Nextcloud login flow, so it is counted -------


def test_a_flood_of_accepted_authorization_requests_ends_in_429(store: OAuthStore) -> None:
    """CR-02, SC 5: /authorize answers 302 when it works, and every one of those answers
    opened a Nextcloud login flow. While only refusals were counted, the throttle bounded
    nothing here, and the SDK answers its own error cases with 302 as well, so not even a
    PKCE downgrade was ever counted."""
    provider = make(store)
    register(provider)
    counters = throttle_module.Throttle(ceiling=10_000, window=60)
    client = TestClient(
        Starlette(
            routes=[
                *provider_module.auth_routes(ENV, provider=provider),
                *consent.consent_routes(
                    ENV,
                    provider=provider,
                    browser_identity=AppApiBrowserIdentitySource(ENV),
                    nextcloud=exapp_target(ENV),
                    throttle=counters,
                ),
            ]
        )
    )

    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        statuses = [start(client).status_code for _ in range(throttle_module.FLOW_LIMIT + 3)]

    assert statuses[: throttle_module.FLOW_LIMIT] == [302] * throttle_module.FLOW_LIMIT
    assert set(statuses[throttle_module.FLOW_LIMIT :]) == {429}
    assert init.call_count == throttle_module.FLOW_LIMIT, (
        "a throttled request must not reach Nextcloud at all"
    )


def test_the_flood_does_not_close_the_consent_screen_behind_it(store: OAuthStore) -> None:
    """The screen behind the endpoint refreshes itself every three seconds while a user is
    signing in, so it must not share the counter of the requests that open flows."""
    provider = make(store)
    register(provider)
    counters = throttle_module.Throttle(ceiling=10_000, window=60)
    client = TestClient(
        Starlette(
            routes=[
                *provider_module.auth_routes(ENV, provider=provider),
                *consent.consent_routes(
                    ENV,
                    provider=provider,
                    browser_identity=AppApiBrowserIdentitySource(ENV),
                    nextcloud=exapp_target(ENV),
                    throttle=counters,
                ),
            ]
        )
    )

    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        flow_id = flow_of(start(client))
        for _ in range(throttle_module.FLOW_LIMIT + 3):
            start(client)
        respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        screen = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert screen.status_code == 200


# --- CR-03: the decision answers a navigation, never a redirect a browser refuses ---------


@pytest.mark.parametrize(
    "decision", [ui_consent.DECISION_APPROVE, ui_consent.DECISION_DENY], ids=["approve", "deny"]
)
def test_no_decision_answers_a_redirect_to_a_foreign_origin(
    store: OAuthStore, decision: str
) -> None:
    """CR-03: Chromium and WebKit check ``form-action`` against the target of a redirect
    that follows a form submission, and every page of this phase carries ``form-action
    'self'``. A 302 to the client out of this POST is therefore a blank page in those
    browsers, which is the primary flow of success criteria 1 and 2. The answer is a page
    that navigates, and the policy is unchanged: no foreign origin is named in it."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    with respx.mock:
        respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, decision, store=store)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert returned_to(response).startswith(REDIRECT)
    policy = response.headers["content-security-policy"]
    assert "form-action 'self'" in policy
    assert "claude.ai" not in policy, "the policy never names the origin of a registration"
    assert "<script" not in response.text


def test_the_return_page_shows_the_address_it_continues_to(store: OAuthStore) -> None:
    """A page that navigates on its own has to say where, or it is the open redirect this
    surface exists against wearing a friendlier hat (T-03-41)."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    target = returned_to(response)
    assert f'href="{html.escape(target, quote=True)}"' in response.text
    assert strings.RESULT_RETURN_ACTION.format(client=CLIENT_NAME) in response.text
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


# --- CR-01: the decision belongs to the account that signed in ----------------------------


def test_the_decision_consults_the_injected_browser_identity_source(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    _client, flow_id, _page = signed_in(provider)
    source = StubBrowserIdentitySource()
    deciding = TestClient(application_with_identity(provider, source))

    response = decide(
        deciding,
        flow_id,
        ui_consent.DECISION_APPROVE,
        store=store,
        user=None,
    )

    assert response.status_code == 200
    assert source.expected == LOGIN_NAME
    assert source.path == ui_consent.DECIDE_PATH
    assert len(rows(store, "auth_codes")) == 1


def test_a_browser_identity_source_failure_fails_closed(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    _client, flow_id, _page = signed_in(provider)
    source = StubBrowserIdentitySource(fail=True)
    deciding = TestClient(application_with_identity(provider, source))
    before = snapshot(store)

    response = decide(
        deciding,
        flow_id,
        ui_consent.DECISION_APPROVE,
        store=store,
        user=None,
    )

    assert response.status_code == 400
    assert "location" not in response.headers
    assert snapshot(store) == before


@pytest.mark.parametrize(
    ("user", "case"),
    [(None, "no Nextcloud session at all"), ("mallory", "a different Nextcloud account")],
)
def test_the_relay_attack_never_reaches_a_code(
    store: OAuthStore, user: str | None, case: str
) -> None:
    """CR-01, the whole attack in one test.

    The attacker registers a client, starts the authorization and gets the flow id, which
    until this fix was the entire authorisation of the decision. They send the victim
    nothing but Nextcloud's own sign in link, the victim grants it, and the attacker
    presses "Allow access" with the flow id and the anti forgery value of that flow, both
    of which they hold. Every check before this one passes: the flow exists, it has not
    expired, the value fits the form, the client is allowed and the sign in is finished.
    Only the account behind the browser is somebody else's, and that is what has to end it.
    """
    provider = make(store)
    register(provider)
    client, flow_id, page = signed_in(provider)
    assert strings.CONSENT_APPROVE in page, "the sign in of the victim finished"
    before = snapshot(store)

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store, user=user)

    assert response.status_code == 400, case
    assert "location" not in response.headers
    assert "url=" not in response.text, "no code and no way back to the client"
    assert rows(store, "auth_codes") == []
    assert snapshot(store) == before, "not one row of the store moved"
    assert strings.CONSENT_APPROVE not in response.text


def test_a_forged_identity_header_is_not_an_identity(store: OAuthStore) -> None:
    """The header is signed with APP_SECRET, which the caller does not have (T-02-02)."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    forged = base64.b64encode(f"{LOGIN_NAME}:not-the-app-secret".encode()).decode("ascii")

    response = client.post(
        ui_consent.DECIDE_PATH,
        data={
            ui_consent.FLOW_PARAM: flow_id,
            ui_consent.DECISION_PARAM: ui_consent.DECISION_APPROVE,
            ui_consent.CONFIRM_PARAM: store.form_token(flow_id, purpose=crypto.PURPOSE_CONSENT),
        },
        headers={
            "EX-APP-ID": ENV[config.ENV_APP_ID],
            "EX-APP-VERSION": ENV[config.ENV_APP_VERSION],
            "AUTHORIZATION-APP-API": forged,
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert rows(store, "auth_codes") == []


def test_a_decision_body_that_cannot_be_parsed_is_a_page_and_grants_nothing(
    store: OAuthStore,
) -> None:
    """HI-02 on the decision route: ``Request.form()`` raises on a broken multipart body.

    The exception of ``python-multipart`` is not the one Starlette catches, so this used to
    leave the route as an unhandled 500. It carries no flow, so it is the same answer as a
    decision without one: the page that says the link is no longer valid.
    """
    provider = make(store)
    register(provider)
    client, _flow_id, _page = signed_in(provider)
    before = snapshot(store)

    response = client.post(
        ui_consent.DECIDE_PATH,
        headers=appapi_headers(LOGIN_NAME)
        | {"Content-Type": "multipart/form-data; boundary=the-boundary"},
        content=b"this is not a multipart body",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert "Traceback" not in response.text
    assert snapshot(store) == before, "not one row of the store moved"


def test_an_authorize_body_that_cannot_be_parsed_is_a_page_and_never_a_traceback(
    store: OAuthStore,
) -> None:
    """The same on the front door, which reads a form when it is asked with a POST."""
    provider = make(store)
    register(provider)
    client = TestClient(
        Starlette(
            routes=consent.consent_routes(
                ENV,
                provider=provider,
                browser_identity=AppApiBrowserIdentitySource(ENV),
                nextcloud=exapp_target(ENV),
            )
        )
    )

    response = client.post(
        consent.AUTHORIZATION_PATH,
        headers={"Content-Type": "multipart/form-data; boundary=the-boundary"},
        content=b"this is not a multipart body",
        follow_redirects=False,
    )

    assert response.status_code < 500
    assert response.headers["cache-control"] == "no-store"
    assert "Traceback" not in response.text


def test_a_denial_by_a_stranger_leaves_the_connection_alone(store: OAuthStore) -> None:
    """The refusal is the whole decision, not only the granting half of it: a stranger who
    could deny would end a connection somebody else is making and hand back their
    credential, which is the same authority in the other direction."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_DENY, store=store, user="mallory")

    assert response.status_code == 400
    assert revoke.call_count == 0, "no app password of another account is handed back"
    assert len(rows(store, "authorizations")) == 1, "the connection of the victim is untouched"


def test_the_decision_is_a_route_of_its_own_and_the_screen_stays_public() -> None:
    """CR-01: the split is what makes one access level possible per half of the surface."""
    paths = [getattr(route, "path", "") for route in build_exapp_app(ENV).router.routes]

    assert paths.count(ui_consent.CONSENT_PATH) == 1
    assert paths.count(ui_consent.DECIDE_PATH) == 1

    served = {
        getattr(route, "path", ""): sorted(getattr(route, "methods", set()) or set())
        for route in build_exapp_app(ENV).router.routes
    }
    assert served[ui_consent.CONSENT_PATH] == ["GET", "HEAD"]
    assert served[ui_consent.DECIDE_PATH] == ["POST"]


def test_the_form_of_the_consent_screen_posts_to_the_decision_route(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    _client, _flow_id, page = signed_in(provider)

    assert f'action="{PREFIX}{ui_consent.DECIDE_PATH}"' in page


def test_the_form_is_a_post_with_two_named_buttons_and_deny_first(store: OAuthStore) -> None:
    """03-UI-SPEC.md S3: no GET grants anything, and the safe action is reachable first."""
    provider = make(store)
    register(provider)
    _client, flow_id, page = signed_in(provider)

    assert 'method="post"' in page
    assert f'name="{ui_consent.DECISION_PARAM}" value="{ui_consent.DECISION_DENY}"' in page
    assert f'name="{ui_consent.DECISION_PARAM}" value="{ui_consent.DECISION_APPROVE}"' in page
    assert page.index(strings.CONSENT_DENY) < page.index(strings.CONSENT_APPROVE)
    expected = store.form_token(flow_id, purpose=crypto.PURPOSE_CONSENT)
    assert f'name="{ui_consent.CONFIRM_PARAM}" value="{expected}"' in page, (
        "the form carries the value that binds it to this authorization request"
    )
    assert "<script" not in page


def test_the_page_lands_on_its_heading_and_not_on_the_granting_button(
    store: OAuthStore,
) -> None:
    """A page that opens with the granting action focused turns a stray Enter into a grant."""
    provider = make(store)
    register(provider)
    _client, _flow_id, page = signed_in(provider)

    heading = re.search(r"<h1[^>]*>", page)
    assert heading is not None
    assert 'tabindex="-1"' in heading.group(0)
    assert "autofocus" in heading.group(0)
    assert "autofocus" not in page[page.index("<button") :]


def out_of_band(store: OAuthStore, flow_id: str, *, display_name: str | None = None) -> None:
    """A finished sign in of a client this server cannot redirect anywhere (S4)."""
    asyncio.run(
        store.create_flow(
            flow_id,
            client_id=CLIENT_ID,
            redirect_uri="",
            redirect_uri_explicit=False,
            code_challenge=CHALLENGE,
            state=None,
            scopes="nextcloud",
            resource=RESOURCE,
            poll_token=POLL_TOKEN,
        )
    )
    asyncio.run(
        store.create_authorization(
            flow_id,
            client_id=CLIENT_ID,
            nc_user=LOGIN_NAME,
            nc_account_id=LOGIN_NAME,
            nc_display_name=display_name,
            app_password=APP_PASSWORD,
            scopes="nextcloud",
            resource=RESOURCE,
        )
    )


def test_without_a_return_address_the_result_is_a_page(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))
    out_of_band(store, "flow-approved-out-of-band")

    response = decide(client, "flow-approved-out-of-band", ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert strings.RESULT_CONNECTED_TITLE in response.text
    assert (
        strings.RESULT_CONNECTED_BODY.format(client=CLIENT_NAME, user=LOGIN_NAME) in response.text
    )
    assert APP_PASSWORD not in response.text


def test_without_a_return_address_a_denial_is_a_page_too(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))
    out_of_band(store, "flow-denied-out-of-band")

    with respx.mock:
        respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, "flow-denied-out-of-band", ui_consent.DECISION_DENY, store=store)

    assert response.status_code == 200
    assert strings.RESULT_DENIED_TITLE in response.text
    assert strings.RESULT_DENIED_BODY.format(client=CLIENT_NAME) in response.text
    assert APP_PASSWORD not in response.text
    assert rows(store, "authorizations") == []


def test_a_decision_of_a_client_blocked_in_the_meantime_grants_nothing(
    store: OAuthStore,
) -> None:
    """T-03-40, pitfall 9: the enforcement point is asked again at the moment of the grant."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    asyncio.run(store.save_client(CLIENT_ID, metadata_json='{"client_id": "x"}', allowed=False))

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code in (400, 403)
    assert "location" not in response.headers
    assert rows(store, "auth_codes") == []


def test_no_decision_writes_a_credential_into_the_log(
    store: OAuthStore, caplog: pytest.LogCaptureFixture
) -> None:
    """T-03-54: not on DEBUG, not truncated, not in the successful case either."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    with caplog.at_level(logging.DEBUG):
        response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert APP_PASSWORD not in caplog.text
    assert POLL_TOKEN not in caplog.text
    assert query_of(response)["code"][0] not in caplog.text


# --- BL-10: the switch is enforced where an authorization is created ------------------------
#
# One comment per statement of BL-10, because each of them is a criterion of its own:
#
# * The gate used to hang on ``MCP_PATH`` alone, so a paused account ran the whole login flow
#   and only the later tool call met R1.
# * Nextcloud creates a real app password on the way, so every refusal here owes the
#   revocation: the set of valid app passwords may not grow while the brake is pulled.
# * The check may only happen where the account is known at all, which is after the poll, so
#   ``/authorize`` and ``connect._start`` stay unchecked on purpose.
# * A store that cannot answer is never a "no": fail closed, exactly like the transport
#   boundary of phase 4.


def paused(store: OAuthStore, user: str = LOGIN_NAME) -> None:
    """The switch of one account, pulled the way ``/connections`` pulls it."""
    asyncio.run(store.set_access(user, disabled=True))


def broken_switch(store: OAuthStore) -> None:
    """Make the one local read of the switch fail, and nothing else of the store."""

    async def refuse(_nc_user: str) -> bool:
        raise sqlite3.OperationalError("the switch could not be read")

    store.access_disabled = refuse  # type: ignore[method-assign]


def test_a_paused_account_never_reaches_the_consent_screen(store: OAuthStore) -> None:
    """Enforcement point 1: after the poll, before ``create_authorization``."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)
    paused(store)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert response.status_code == 403
    assert strings.CONNECTIONS_PAUSED_TITLE in response.text
    assert strings.SWITCH_OFF_STATE in response.text
    assert strings.SETTINGS_PLACE in response.text
    assert strings.CONSENT_APPROVE not in response.text, "nothing to approve while paused"
    assert revoke.call_count == 1, "one attempt, and the app password is handed back"
    assert rows(store, "authorizations") == [], "no authorization is created for a paused account"
    assert asyncio.run(store.load_flow(flow_id, now=0)) is None, "the spent flow is gone"
    assert APP_PASSWORD not in response.text


def test_an_account_that_is_not_paused_reaches_the_consent_screen(store: OAuthStore) -> None:
    """The positive control of point 1: the check refuses one case and not the surface."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert response.status_code == 200
    assert strings.CONSENT_TITLE.format(client=CLIENT_NAME) in response.text
    assert revoke.call_count == 0, "nothing is handed back on the way that works"
    assert len(rows(store, "authorizations")) == 1


def test_a_switch_that_cannot_be_read_creates_no_authorization(store: OAuthStore) -> None:
    """Fail closed (D-37): an unreadable switch is a page, never a pass through."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)
    broken_switch(store)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert rows(store, "authorizations") == []
    assert revoke.call_count == 1, "the credential nobody will use goes back either way"
    assert APP_PASSWORD not in response.text


def test_an_account_paused_while_the_screen_was_open_gets_no_code(store: OAuthStore) -> None:
    """Enforcement point 3: the decision itself, read before it can become a grant."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    paused(store)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 403
    assert strings.CONNECTIONS_PAUSED_TITLE in response.text
    assert rows(store, "auth_codes") == [], "no authorization code exists for a paused account"
    assert rows(store, "authorizations") == []
    assert revoke.call_count == 1
    assert asyncio.run(store.load_flow(flow_id, now=0)) is None


def test_a_screen_reloaded_after_the_pause_shows_no_buttons_to_press(
    store: OAuthStore,
) -> None:
    """IN-06 of 05-REVIEW.md, first pass: the screen used to be the one unread point.

    With an authorization row already written, ``_screen`` went straight to the consent
    page, so a reload after the account was paused in another tab still showed approve and
    deny. No grant was possible, enforcement point 3 answers the click, but a surface that
    offers a button it will refuse says the opposite of what the switch promises. Nothing is
    withdrawn here: this is a GET, and the decision point is where state changes.
    """
    provider = make(store)
    register(provider)
    client, flow_id, page = signed_in(provider)
    assert strings.CONSENT_APPROVE in page, "the screen offered the buttons before the pause"
    paused(store)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = client.get(consent_url(flow_id))

    assert response.status_code == 403
    assert strings.CONNECTIONS_PAUSED_TITLE in response.text
    assert strings.CONSENT_APPROVE not in response.text, "nothing to approve while paused"
    assert revoke.call_count == 0, "a reload is not a decision, so nothing is withdrawn"
    assert len(rows(store, "authorizations")) == 1, "and the row of the sign in stays"


def test_a_screen_of_an_account_that_is_not_paused_still_shows_the_buttons(
    store: OAuthStore,
) -> None:
    """The positive control of the check above: one case is refused, not the surface."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    response = client.get(consent_url(flow_id))

    assert response.status_code == 200
    assert strings.CONSENT_APPROVE in response.text


def test_a_screen_whose_switch_cannot_be_read_grants_no_view_of_the_buttons(
    store: OAuthStore,
) -> None:
    """Fail closed on the screen too (D-37), the same answer the decision point gives."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    broken_switch(store)

    response = client.get(consent_url(flow_id))

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert strings.CONSENT_APPROVE not in response.text


def test_the_refusal_of_a_paused_account_is_not_reported_as_a_user_decision(
    store: OAuthStore,
) -> None:
    """T-05-09: the reason is a setting of the account, so the client gets no
    ``access_denied`` and the browser is not sent back at all."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    paused(store)

    with respx.mock:
        respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert "location" not in response.headers
    assert "access_denied" not in response.text
    assert REDIRECT not in response.text


def test_a_decision_of_an_account_that_is_not_paused_still_returns_a_code(
    store: OAuthStore,
) -> None:
    """The positive control of point 3."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 200
    assert len(query_of(response)["code"]) == 1
    assert revoke.call_count == 0


def test_a_switch_that_cannot_be_read_at_the_decision_grants_nothing(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    broken_switch(store)

    response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert rows(store, "auth_codes") == []


def test_a_revocation_that_fails_does_not_hold_up_the_refusal(store: OAuthStore) -> None:
    """D-34, D-37: the connection goes even when the cleanup step at Nextcloud does not."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in(provider)
    paused(store)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(500, json={}))
        response = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store)

    assert response.status_code == 403
    assert strings.CONNECTIONS_PAUSED_TITLE in response.text
    assert revoke.call_count == 1, "one attempt, no retry"
    assert rows(store, "authorizations") == []
    assert rows(store, "auth_codes") == []


def test_no_refusal_of_a_paused_account_writes_a_value_into_the_log(
    store: OAuthStore, caplog: pytest.LogCaptureFixture
) -> None:
    """T-05-11: the new branches log the rule, never the account, the credential or the flow."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)
    paused(store)

    with respx.mock, caplog.at_level(logging.DEBUG, logger="mcp_connector"):
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert LOGIN_NAME not in caplog.text
    assert APP_PASSWORD not in caplog.text
    assert POLL_TOKEN not in caplog.text
    assert flow_id not in caplog.text


def test_the_unchecked_places_say_why_they_are_unchecked() -> None:
    """SC 4 of the plan: the reason stands in the code and not only in the backlog.

    ``/authorize`` and ``connect._start`` cannot check the switch, because at that moment no
    account is known: the sign in has not happened yet. A reader who finds no check there has
    to find the reason there too, or the gap looks like an oversight.
    """
    source = Path(consent.__file__).read_text(encoding="utf-8")
    marker = source.index("async def authorize(")
    assert "not known" in source[marker : marker + 900]


# --- the properties of every page of this route -------------------------------------------


def test_no_page_of_this_route_carries_a_script(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    client, flow_id, target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        pages = [
            client.get(target),
            client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT)),
            client.get("/authorize"),
        ]

    for page in pages:
        assert "<script" not in page.text
        assert "onclick" not in page.text
        assert page.headers["cache-control"] == "no-store"
        assert page.headers["x-frame-options"] == "DENY"
        assert page.headers["referrer-policy"] == "no-referrer"
        assert "default-src 'none'" in page.headers["content-security-policy"]


def test_every_link_of_a_page_carries_the_public_prefix(store: OAuthStore) -> None:
    """HaRP strips the prefix before this app sees a request, so a link without it would
    point at the root of the Nextcloud domain instead of at this application."""
    provider = make(store)
    register(provider)
    client, flow_id, target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    for target in re.findall(r'(?:href|action)="(/[^"]*)"', response.text):
        assert target.startswith(PREFIX), target


@pytest.mark.parametrize(
    ("link", "why"),
    [
        ("https://evil.example/login", "a foreign host"),
        (
            f"https://{HOST}/index.php/login?redirect_url=https://evil.example/",
            "the sign in page of the right host with a return address of the wrong one",
        ),
        (f"https://{HOST}/s/public-share-token", "a public share on the right host"),
        (f"https://{HOST}/", "the front page of the right host"),
        (f"https://{HOST}/index.php/login/v2", "the endpoint that starts a flow, not the page"),
    ],
    ids=["foreign host", "open redirect", "public share", "front page", "the start endpoint"],
)
def test_a_sign_in_link_that_is_not_the_login_flow_page_is_not_rendered(
    store: OAuthStore, link: str, why: str
) -> None:
    """The link is the one place this surface sends a user away from here (T-03-42).

    The host was the whole check until WR-07, so every page of the configured Nextcloud
    passed: the primary button of a page whose purpose is to be trustworthy could be
    pointed at a sign in with an attacker chosen redirect_url, at a public share, or at
    anything else that renders on that origin. The path of a Login Flow v2 grant page has
    one shape, and everything else is refused."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        response = client.get(f"{consent_url(flow_id)}&{ui_consent.LOGIN_PARAM}={link}")

    assert link not in response.text, why
    assert strings.SIGNIN_CTA not in response.text, "no button stands in front of it either"


def test_the_login_flow_page_of_this_instance_is_rendered(store: OAuthStore) -> None:
    """The counter probe: the check must not refuse the one address it exists to allow."""
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        response = client.get(f"{consent_url(flow_id)}&{ui_consent.LOGIN_PARAM}={LOGIN_URL}")

    assert f'href="{LOGIN_URL}"' in response.text


INJECTED_BASE = "https://nc.injected.example"


def test_the_consent_surface_uses_the_injected_target_and_not_the_environment(
    store: OAuthStore,
) -> None:
    """Standalone OAuth, slice 2: sign in link check and poll follow the injected target.

    The deploy environment still names ``BASE_URL``. A link on that host is refused once the
    application was assembled with another target, a link on the injected host is rendered,
    and the waiting screen polls the injected Nextcloud and nothing else.
    """
    provider = make(store)
    register(provider)
    client = TestClient(
        Starlette(
            routes=[
                *provider_module.auth_routes(ENV, provider=provider),
                *consent.consent_routes(
                    ENV,
                    provider=provider,
                    browser_identity=AppApiBrowserIdentitySource(ENV),
                    nextcloud=NextcloudTarget.from_url(INJECTED_BASE),
                ),
            ]
        )
    )
    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        flow_id = flow_of(start(client))

    injected_link = f"{INJECTED_BASE}/index.php/login/v2/flow/abc123"
    environment_link = f"{BASE_URL}/index.php/login/v2/flow/abc123"
    with respx.mock:
        environment_poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        injected_poll = respx.post(f"{INJECTED_BASE}{loginflow.POLL_PATH}").mock(
            return_value=httpx.Response(404)
        )
        accepted = client.get(f"{consent_url(flow_id)}&{ui_consent.LOGIN_PARAM}={injected_link}")
        refused = client.get(f"{consent_url(flow_id)}&{ui_consent.LOGIN_PARAM}={environment_link}")
        waiting = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert f'href="{injected_link}"' in accepted.text
    assert environment_link not in refused.text
    assert waiting.status_code == 200
    assert injected_poll.call_count == 1
    assert environment_poll.call_count == 0


def test_the_provider_opens_its_login_flow_at_its_injected_target(store: OAuthStore) -> None:
    """The authorization endpoint starts the flow through the provider, so the provider's
    target decides where, whatever the deploy environment names."""

    async def provide() -> OAuthStore:
        return store

    provider = provider_module.NextcloudOAuthProvider(
        nextcloud=NextcloudTarget.from_url(INJECTED_BASE),
        env=ENV,
        policy=registry.client_policy(ENV),
        store_provider=provide,
    )
    register(provider)
    client = TestClient(application(provider))
    with respx.mock:
        environment_init = respx.post(INIT_URL).mock(
            return_value=httpx.Response(200, json=start_body())
        )
        injected_init = respx.post(f"{INJECTED_BASE}{loginflow.INIT_PATH}").mock(
            return_value=httpx.Response(200, json=start_body())
        )
        response = start(client)

    assert response.status_code == 302
    assert (injected_init.call_count, environment_init.call_count) == (1, 0)


def test_the_consent_factory_requires_an_explicit_target() -> None:
    """No hidden fallback to ``exapp_settings``: the parameter has no default."""
    parameter = inspect.signature(consent.consent_routes).parameters["nextcloud"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
    assert "exapp_settings" not in inspect.getsource(consent)


def test_the_routes_are_declared_in_the_manifest_and_served_by_the_application() -> None:
    paths = [getattr(route, "path", "") for route in build_exapp_app(ENV).router.routes]

    assert paths.count("/authorize") == 1
    assert paths.count(ui_consent.CONSENT_PATH) == 1
    assert paths.count(ui_consent.DECIDE_PATH) == 1


# --- the canonical account id (principal rule) -------------------------------------------

ACCOUNT_ID = "a1b2c3d4"


def signed_in_as_account(
    provider: provider_module.NextcloudOAuthProvider, account: str
) -> tuple[TestClient, str]:
    """A sign in whose login name differs from its canonical account id (LDAP-like)."""
    client, flow_id, _target = opened(provider)
    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body(account)))
        page = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))
    assert page.status_code == 200, page.text
    return client, flow_id


def test_the_connection_stores_the_login_name_and_the_account_id(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    _client, flow_id = signed_in_as_account(provider, ACCOUNT_ID)

    row = asyncio.run(store.load_authorization(flow_id))

    assert row is not None
    assert row.nc_user == LOGIN_NAME
    assert row.nc_account_id == ACCOUNT_ID


def test_an_account_whose_login_name_differs_from_its_uid_can_decide(store: OAuthStore) -> None:
    """LDAP and alternative login names: the fix of #5, kept on purpose.

    AppAPI names the browser by its account id (the UID), while the sign in reports the
    login name. Comparing the two made consent a total fail-closed outage for every such
    account. The decision compares the account id, and the login name alone is refused.
    Do not "fix" this back to ``nc_user``.
    """
    provider = make(store)
    register(provider)
    client, flow_id = signed_in_as_account(provider, ACCOUNT_ID)

    refused = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store, user=LOGIN_NAME)
    assert asyncio.run(store.load_flow(flow_id)) is not None, "nothing was decided"
    granted = decide(client, flow_id, ui_consent.DECISION_APPROVE, store=store, user=ACCOUNT_ID)

    assert refused.headers.get("location") is None
    assert granted.status_code == 200, granted.text
    assert asyncio.run(store.load_flow(flow_id)) is None, "the approval spent the flow"


DISPLAY_NAME = "Alice Adams"


def signed_in_with_a_display_name(
    provider: provider_module.NextcloudOAuthProvider,
) -> tuple[TestClient, str, Any]:
    """A sign in on an instance that has a display name for the account."""
    client, flow_id, _target = opened(provider)
    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(
            return_value=httpx.Response(
                200, json=account_body(ACCOUNT_ID, display_name=DISPLAY_NAME)
            )
        )
        page = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))
    assert page.status_code == 200, page.text
    return client, flow_id, page


def test_the_sign_in_stores_the_display_name_beside_the_two_identities(
    store: OAuthStore,
) -> None:
    """Three names, three jobs: one to sign in with, one to own by, one to read."""
    provider = make(store)
    register(provider)
    _client, flow_id, _page = signed_in_with_a_display_name(provider)

    row = asyncio.run(store.load_authorization(flow_id))

    assert row is not None
    assert row.nc_user == LOGIN_NAME
    assert row.nc_account_id == ACCOUNT_ID
    assert row.nc_display_name == DISPLAY_NAME


def test_the_consent_screen_names_the_person_and_not_the_login(store: OAuthStore) -> None:
    """What the screen is for: the reader has to recognise the account they are granting."""
    provider = make(store)
    register(provider)
    client, flow_id, page = signed_in_with_a_display_name(provider)

    assert strings.CONSENT_IDENTITY.format(user=DISPLAY_NAME, host=HOST) in page.text

    reloaded = client.get(consent_url(flow_id))

    assert reloaded.status_code == 200, reloaded.text
    assert strings.CONSENT_IDENTITY.format(user=DISPLAY_NAME, host=HOST) in reloaded.text


def test_the_result_page_names_the_person_too(store: OAuthStore) -> None:
    """The page a client without a return address leaves the reader on (S4)."""
    provider = make(store)
    register(provider)
    client = TestClient(application(provider))
    out_of_band(store, "flow-named", display_name=DISPLAY_NAME)

    granted = decide(client, "flow-named", ui_consent.DECISION_APPROVE, store=store)

    assert granted.status_code == 200, granted.text
    assert strings.RESULT_CONNECTED_BODY.format(client=CLIENT_NAME, user=DISPLAY_NAME) in (
        granted.text
    )


def test_without_a_display_name_the_screen_still_names_the_login(store: OAuthStore) -> None:
    """An instance that sets none reads exactly as it did before the column existed."""
    provider = make(store)
    register(provider)
    _client, flow_id = signed_in_as_account(provider, ACCOUNT_ID)

    row = asyncio.run(store.load_authorization(flow_id))

    assert row is not None
    assert row.nc_display_name is None

    reloaded = _client.get(consent_url(flow_id))

    assert strings.CONSENT_IDENTITY.format(user=LOGIN_NAME, host=HOST) in reloaded.text


def test_a_denial_revokes_with_the_login_name_and_never_the_display_name(
    store: OAuthStore,
) -> None:
    """The one place the two names must not be swapped: Basic auth against Nextcloud."""
    provider = make(store)
    register(provider)
    client, flow_id, _page = signed_in_with_a_display_name(provider)

    with respx.mock:
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        denied = decide(client, flow_id, ui_consent.DECISION_DENY, store=store, user=ACCOUNT_ID)

    assert denied.status_code == 200, denied.text
    assert revoke.call_count == 1
    sent = revoke.calls.last.request
    expected = base64.b64encode(f"{LOGIN_NAME}:{APP_PASSWORD}".encode()).decode()
    assert sent.headers["Authorization"] == f"Basic {expected}"


def test_a_hostile_display_name_cannot_shape_the_consent_screen(store: OAuthStore) -> None:
    """The name comes from the Nextcloud side, so the page treats it like any foreign text."""
    provider = make(store)
    register(provider)
    hostile = "Alice\n\n" + "A" * 300
    client, flow_id, _target = opened(provider)
    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(
            return_value=httpx.Response(200, json=account_body(ACCOUNT_ID, display_name=hostile))
        )
        page = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert page.status_code == 200, page.text
    assert hostile not in page.text
    assert "A" * 200 not in page.text


def test_a_pause_of_the_account_id_refuses_the_sign_in(store: OAuthStore) -> None:
    provider = make(store)
    register(provider)
    asyncio.run(store.set_access(ACCOUNT_ID, disabled=True))
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body(ACCOUNT_ID)))
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert revoke.call_count == 1
    assert asyncio.run(store.load_authorization(flow_id)) is None


def test_an_unresolved_account_stores_nothing_and_hands_the_password_back(
    store: OAuthStore,
) -> None:
    provider = make(store)
    register(provider)
    client, flow_id, _target = opened(provider)

    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(500, json={}))
        revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
        response = client.get(consent_url(flow_id, step=ui_consent.STEP_WAIT))

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert revoke.call_count == 1
    assert asyncio.run(store.load_authorization(flow_id)) is None
    assert asyncio.run(store.load_flow(flow_id)) is None, "the spent poll leaves no waiting page"

"""The consent wiring of the standalone single sign-on proof (CR-01 without AppAPI).

A standalone deployment has no AppAPI header, so the consent decision asks the OIDC
browser identity source instead (``mcp_connector.oauth.oidc_identity``). This module
covers the part that is specific to that wiring, once the SDK plumbing already tested in
``test_oauth_consent.py`` and ``test_oauth_oidc_routes.py`` is assumed to work: the consent
screen offers the single sign-on step while no live proof exists, the decision consumes
that proof exactly once and only for the flow and the account it was issued for, and a
failure of the identity source never reaches the reader as a stack trace.
"""

import asyncio
import html
import json
import re
import sqlite3
import time
from collections.abc import Coroutine, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from mcp.shared.auth import OAuthClientInformationFull
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.exapp.ui import strings
from mcp_connector.exapp.ui.consent import (
    CONFIRM_PARAM,
    CONSENT_PATH,
    DECIDE_PATH,
    DECISION_APPROVE,
    DECISION_PARAM,
    FLOW_PARAM,
)
from mcp_connector.nextcloud.target import NextcloudTarget
from mcp_connector.oauth import consent, crypto, oidc, oidc_identity, oidc_routes, registry
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth.browser_identity import BrowserIdentitySource
from mcp_connector.oauth.store import OAuthStore

PUBLIC_URL = "https://mcp.example.com"
NEXTCLOUD_URL = "https://cloud.example.com"
ISSUER = "https://auth.example.com"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
AUTHORIZE_URL = f"{ISSUER}/oauth/v2/authorize"
TOKEN_URL = f"{ISSUER}/oauth/v2/token"
JWKS_URL = f"{ISSUER}/oauth/v2/keys"
OIDC_CLIENT_ID = "391054166463676676"
REDIRECT = f"{PUBLIC_URL}{oidc_routes.OIDC_CALLBACK_PATH}"
PROVIDER_ID = 2
SUB = "390763839257313538"
ACCOUNT = oidc.user_oidc_unique_uid_sub_v1(PROVIDER_ID, SUB)
KID = "key-1"

MCP_CLIENT_ID = "client-4711"
CLIENT_REDIRECT = "https://claude.ai/callback"
CLIENT_STATE = "state-of-the-client"
FLOW_ID = "flow-0001"
CODE = "authorization-code-from-the-provider"
KEY = bytes(range(32))

ENV = {config.ENV_PUBLIC_URL: PUBLIC_URL}
PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)

START = oidc_routes.OIDC_START_PATH
CALLBACK = oidc_routes.OIDC_CALLBACK_PATH
SIGN_IN = oidc_routes.SIGN_IN_COOKIE
PROOF = oidc_routes.PROOF_COOKIE


# --- fixtures and application wiring -----------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> OAuthStore:
    return OAuthStore(tmp_path / "oauth.sqlite3", KEY, oidc=True)


def run(awaitable: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(awaitable)


def make_provider(store: OAuthStore) -> provider_module.NextcloudOAuthProvider:
    async def provide() -> OAuthStore:
        return store

    return provider_module.NextcloudOAuthProvider(
        nextcloud=NextcloudTarget.from_url(NEXTCLOUD_URL),
        env=ENV,
        policy=registry.client_policy(ENV),
        store_provider=provide,
    )


def register(provider: provider_module.NextcloudOAuthProvider) -> None:
    payload: dict[str, object] = {
        "client_id": MCP_CLIENT_ID,
        "client_name": "Claude",
        "redirect_uris": [CLIENT_REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "nextcloud",
    }
    run(provider.register_client(OAuthClientInformationFull.model_validate(payload)))


def with_flow(
    store: OAuthStore,
    flow_id: str = FLOW_ID,
    *,
    account_id: str = ACCOUNT,
) -> None:
    async def work() -> None:
        await store.create_flow(
            flow_id,
            client_id=MCP_CLIENT_ID,
            redirect_uri=CLIENT_REDIRECT,
            redirect_uri_explicit=True,
            code_challenge="challenge",
            state=CLIENT_STATE,
            scopes="nextcloud",
            resource=f"{PUBLIC_URL}/mcp",
            poll_token="poll-token",
        )
        await store.create_authorization(
            flow_id,
            client_id=MCP_CLIENT_ID,
            nc_user="alice",
            nc_account_id=account_id,
            app_password="app-password",
            scopes="nextcloud",
            resource=f"{PUBLIC_URL}/mcp",
        )

    run(work())


def oidc_client(**overrides: Any) -> oidc.OidcClient:
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": REDIRECT,
        "provider_id": PROVIDER_ID,
    }
    values.update(overrides)
    return oidc.OidcClient(oidc.OidcSettings(**values))


def application_with_identity(store: OAuthStore, identity: BrowserIdentitySource) -> Starlette:
    provider = make_provider(store)
    routes = [
        *consent.consent_routes(
            ENV,
            provider=provider,
            browser_identity=identity,
            nextcloud=NextcloudTarget.from_url(NEXTCLOUD_URL),
            throttle=throttle_module.Throttle(),
        ),
        *oidc_routes.oidc_routes(
            ENV, provider=provider, client=oidc_client(), throttle=throttle_module.Throttle()
        ),
    ]
    return Starlette(routes=routes)


def application(store: OAuthStore) -> Starlette:
    async def provide() -> OAuthStore:
        return store

    identity = oidc_identity.OidcBrowserIdentitySource(store=provide)
    return application_with_identity(store, identity)


def browser(app: Starlette) -> TestClient:
    return TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)


class Idp:
    """The mocked provider plus what the last start sent to it."""

    def __init__(self, router: respx.MockRouter) -> None:
        self.router = router
        self.state: dict[str, str] = {}

    def post(self, url: str) -> respx.Route:
        return self.router.post(url)


@pytest.fixture
def idp() -> Iterator[Idp]:
    with respx.mock(assert_all_called=False) as router:
        router.get(DISCOVERY_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": AUTHORIZE_URL,
                    "token_endpoint": TOKEN_URL,
                    "jwks_uri": JWKS_URL,
                    "response_modes_supported": ["query"],
                    "code_challenge_methods_supported": ["S256"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        )
        public = json.loads(RSAAlgorithm.to_jwk(PRIVATE.public_key()))
        public.update({"kid": KID, "use": "sig", "alg": "RS256"})
        router.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [public]}))
        yield Idp(router)


def id_token(nonce: str, **overrides: Any) -> str:
    now = int(time.time())
    values: dict[str, Any] = {
        "iss": ISSUER,
        "sub": SUB,
        "aud": OIDC_CLIENT_ID,
        "exp": now + 300,
        "iat": now,
        "nonce": nonce,
    }
    values.update(overrides)
    return jwt.encode(values, PRIVATE, algorithm="RS256", headers={"kid": KID})


def answer_with(idp: Idp, **overrides: Any) -> respx.Route:
    """The token endpoint answers with an ID token for the nonce of the last start."""

    def reply(request: httpx.Request) -> httpx.Response:
        nonce = idp.state["nonce"]
        return httpx.Response(200, json={"id_token": id_token(nonce, **overrides)})

    return idp.post(TOKEN_URL).mock(side_effect=reply)


def oidc_start_confirm(store: OAuthStore, flow_id: str = FLOW_ID) -> str:
    return store.form_token(flow_id, purpose=crypto.PURPOSE_OIDC_START)


def set_cookies(response: Any) -> dict[str, str]:
    """``Any``: the test client answers with the ``httpx2`` response type
    (see test_exapp_audit_read.py)."""
    return {line.split("=", 1)[0]: line for line in response.headers.get_list("set-cookie")}


def cookie_value(response: Any, name: str) -> str:
    return set_cookies(response)[name].split(";", 1)[0].split("=", 1)[1]


def handoff_target(response: Any) -> str:
    """The provider address of the handoff page: its refresh target, equal to its link."""
    refresh = re.search(r'http-equiv="refresh" content="0; url=([^"]+)"', response.text)
    link = re.search(r'<a class="btn-link" href="([^"]+)" rel="noreferrer">', response.text)
    assert refresh is not None
    assert link is not None
    assert refresh.group(1) == link.group(1)
    return html.unescape(refresh.group(1))


def oidc_start(
    client: TestClient,
    store: OAuthStore,
    idp: Idp | None = None,
    *,
    cookie: str | None = None,
    flow_id: str = FLOW_ID,
) -> Any:
    client.cookies.clear()
    headers = {} if cookie is None else {"cookie": cookie}
    response = client.post(
        START,
        data={"flow": flow_id, "confirm": oidc_start_confirm(store, flow_id)},
        headers=headers,
    )
    client.cookies.clear()
    if idp is not None and response.status_code == 200:
        query = parse_qs(urlsplit(handoff_target(response)).query)
        idp.state = {
            "state": query["state"][0],
            "nonce": query["nonce"][0],
            "challenge": query["code_challenge"][0],
            "handle": cookie_value(response, SIGN_IN),
        }
    return response


def oidc_callback(
    client: TestClient, query: str, *, cookie: str | None = None, method: str = "GET"
) -> Any:
    client.cookies.clear()
    headers = {} if cookie is None else {"cookie": cookie}
    response = client.request(method, f"{CALLBACK}?{query}", headers=headers)
    client.cookies.clear()
    return response


def good_query(idp: Idp, **extra: str) -> str:
    return f"state={idp.state['state']}&code={CODE}" + "".join(
        f"&{key}={value}" for key, value in extra.items()
    )


def own_cookie(idp: Idp) -> str:
    return f"{SIGN_IN}={idp.state['handle']}"


def proofs(store: OAuthStore) -> list[tuple[str, str, str]]:
    conn = sqlite3.connect(store.path)
    try:
        return conn.execute("SELECT proof_hash, flow_id, principal FROM oidc_proofs").fetchall()
    finally:
        conn.close()


def rows(store: OAuthStore, table: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(store.path)
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()  # noqa: S608
    finally:
        conn.close()


def get_screen(client: TestClient, flow_id: str = FLOW_ID, *, cookie: str | None = None) -> Any:
    client.cookies.clear()
    headers = {} if cookie is None else {"cookie": cookie}
    response = client.get(CONSENT_PATH, params={FLOW_PARAM: flow_id}, headers=headers)
    client.cookies.clear()
    return response


def post_decide(
    client: TestClient,
    flow_id: str,
    confirm_token: str,
    decision: str,
    *,
    cookie: str | None = None,
) -> Any:
    client.cookies.clear()
    headers = {} if cookie is None else {"cookie": cookie}
    response = client.post(
        DECIDE_PATH,
        data={FLOW_PARAM: flow_id, CONFIRM_PARAM: confirm_token, DECISION_PARAM: decision},
        headers=headers,
        follow_redirects=False,
    )
    client.cookies.clear()
    return response


def returned_to(response: Any) -> str:
    """Where an approved decision sends the browser: a page that navigates, not a redirect."""
    location = response.headers.get("location")
    if location:
        return str(location)
    match = re.search(r'content="0; url=([^"]+)"', response.text)
    assert match is not None, response.text
    return html.unescape(match.group(1))


def hidden_fields(page: str) -> dict[str, str]:
    pattern = r'<input type="hidden" name="([^"]+)" value="([^"]*)">'
    return {key: html.unescape(value) for key, value in re.findall(pattern, page)}


def form_action(page: str) -> str:
    match = re.search(r'<form method="post" action="([^"]+)">', page)
    assert match is not None, page
    return html.unescape(match.group(1))


def build_request(*, cookie: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("latin-1")))
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


# --- the consent screen, before a proof exists --------------------------------------------


def test_the_screen_offers_the_single_sign_on_step_without_a_proof(store: OAuthStore) -> None:
    provider = make_provider(store)
    register(provider)
    with_flow(store)

    response = get_screen(browser(application(store)))

    assert response.status_code == 200
    page = response.text
    assert form_action(page).endswith(START)
    fields = hidden_fields(page)
    assert fields[FLOW_PARAM] == FLOW_ID
    assert fields[CONFIRM_PARAM] == oidc_start_confirm(store)
    assert strings.CONSENT_CONFIRM_ACTION in page
    assert strings.CONSENT_APPROVE not in page
    assert strings.CONSENT_DENY not in page


# --- the full path: start, callback, screen, decide ----------------------------------------


def test_start_then_callback_then_consent_then_approve(store: OAuthStore, idp: Idp) -> None:
    provider = make_provider(store)
    register(provider)
    with_flow(store)
    client = browser(application(store))

    oidc_start(client, store, idp)
    answer_with(idp)
    finished = oidc_callback(client, good_query(idp), cookie=own_cookie(idp))
    assert finished.status_code == 303
    proof_cookie = f"{PROOF}={cookie_value(finished, PROOF)}"

    screen = get_screen(client, cookie=proof_cookie)
    assert strings.CONSENT_APPROVE in screen.text
    assert strings.CONSENT_DENY in screen.text
    assert strings.CONSENT_CONFIRM_ACTION not in screen.text

    confirm_token = store.form_token(FLOW_ID, purpose=crypto.PURPOSE_CONSENT)
    response = post_decide(client, FLOW_ID, confirm_token, DECISION_APPROVE, cookie=proof_cookie)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert returned_to(response).startswith(CLIENT_REDIRECT)
    assert len(rows(store, "auth_codes")) == 1
    assert proofs(store) == []


# --- refusals of the decision ---------------------------------------------------------------


def test_a_decision_without_the_proof_cookie_is_refused(store: OAuthStore) -> None:
    provider = make_provider(store)
    register(provider)
    with_flow(store)
    client = browser(application(store))
    before = rows(store, "authorizations")

    confirm_token = store.form_token(FLOW_ID, purpose=crypto.PURPOSE_CONSENT)
    response = post_decide(client, FLOW_ID, confirm_token, DECISION_APPROVE)

    assert response.status_code == 400
    assert rows(store, "auth_codes") == []
    assert rows(store, "authorizations") == before


def test_a_proof_of_another_flow_does_not_authorize_this_one(store: OAuthStore) -> None:
    provider = make_provider(store)
    register(provider)
    with_flow(store, FLOW_ID)
    with_flow(store, "flow-0002")
    handle = "p" * 43
    created = run(
        store.create_browser_proof(proof_handle=handle, flow_id="flow-0002", principal=ACCOUNT)
    )
    assert created
    client = browser(application(store))
    cookie = f"{PROOF}={handle}"

    confirm_token = store.form_token(FLOW_ID, purpose=crypto.PURPOSE_CONSENT)
    response = post_decide(client, FLOW_ID, confirm_token, DECISION_APPROVE, cookie=cookie)

    assert response.status_code == 400
    assert rows(store, "auth_codes") == []
    other = run(store.browser_proof_principal(proof_handle=handle, flow_id="flow-0002"))
    assert other == ACCOUNT


def test_a_proof_of_another_account_keeps_the_sso_step(store: OAuthStore) -> None:
    provider = make_provider(store)
    register(provider)
    with_flow(store)
    handle = "q" * 43
    created = run(
        store.create_browser_proof(proof_handle=handle, flow_id=FLOW_ID, principal="someone-else")
    )
    assert created
    client = browser(application(store))
    cookie = f"{PROOF}={handle}"

    screen = get_screen(client, cookie=cookie)
    assert strings.CONSENT_CONFIRM_ACTION in screen.text
    assert strings.CONSENT_APPROVE not in screen.text

    confirm_token = store.form_token(FLOW_ID, purpose=crypto.PURPOSE_CONSENT)
    response = post_decide(client, FLOW_ID, confirm_token, DECISION_APPROVE, cookie=cookie)

    assert response.status_code == 400
    assert rows(store, "auth_codes") == []


def test_a_proof_is_single_use(store: OAuthStore) -> None:
    provider = make_provider(store)
    register(provider)
    with_flow(store)
    handle = "r" * 43
    created = run(
        store.create_browser_proof(proof_handle=handle, flow_id=FLOW_ID, principal=ACCOUNT)
    )
    assert created
    client = browser(application(store))
    cookie = f"{PROOF}={handle}"
    confirm_token = store.form_token(FLOW_ID, purpose=crypto.PURPOSE_CONSENT)

    first = post_decide(client, FLOW_ID, confirm_token, "", cookie=cookie)
    assert first.status_code == 400
    assert proofs(store) == []

    second = post_decide(client, FLOW_ID, confirm_token, DECISION_APPROVE, cookie=cookie)
    assert second.status_code == 400
    assert rows(store, "auth_codes") == []


# --- a failing identity source ---------------------------------------------------------------


class RaisingIdentitySource:
    """A browser identity source whose display step always fails."""

    async def identifies(
        self, request: Request, expected_account_id: str, *, flow_id: str | None = None
    ) -> bool:
        return False

    async def pending_step(
        self, request: Request, *, flow_id: str, expected_account_id: str
    ) -> None:
        raise RuntimeError("synthetic pending-step failure")


def test_a_pending_step_failure_is_a_page_without_buttons(store: OAuthStore) -> None:
    provider = make_provider(store)
    register(provider)
    with_flow(store)
    client = browser(application_with_identity(store, RaisingIdentitySource()))

    response = get_screen(client)

    assert response.status_code == 500
    assert strings.CONSENT_APPROVE not in response.text
    assert strings.CONSENT_DENY not in response.text
    assert strings.CONSENT_CONFIRM_ACTION not in response.text


# --- OidcBrowserIdentitySource, directly ------------------------------------------------


def test_identifies_without_a_flow_id_is_false(store: OAuthStore) -> None:
    async def provide() -> OAuthStore:
        return store

    source = oidc_identity.OidcBrowserIdentitySource(store=provide)
    request = build_request()

    assert run(source.identifies(request, ACCOUNT, flow_id=None)) is False


def test_identifies_with_an_ambiguous_cookie_consumes_nothing(store: OAuthStore) -> None:
    register(make_provider(store))
    with_flow(store)
    handle = "s" * 43
    other = "t" * 43
    created = run(
        store.create_browser_proof(proof_handle=handle, flow_id=FLOW_ID, principal=ACCOUNT)
    )
    assert created

    async def provide() -> OAuthStore:
        return store

    source = oidc_identity.OidcBrowserIdentitySource(store=provide)
    request = build_request(cookie=f"{PROOF}={handle}; {PROOF}={other}")

    assert run(source.identifies(request, ACCOUNT, flow_id=FLOW_ID)) is False
    principal = run(store.browser_proof_principal(proof_handle=handle, flow_id=FLOW_ID))
    assert principal == ACCOUNT

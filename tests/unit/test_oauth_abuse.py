"""The abuse matrix of D-40, as one file and over the HTTP layer.

**Why this file exists and why it is not spread over the others.** The owner directive of
this phase makes the misuse cases acceptance criteria rather than good intentions, and D-40
lists them. A criterion somebody has to search for is not a criterion, so they stand here,
in the order of D-40, each one as the thing an attacker actually reaches: a request against
a running deployment, not a call of a function. Several of them are checked on the function
level elsewhere as well; that is deliberate duplication, because the two answer different
questions. The other files ask whether a method refuses. This one asks what comes back over
the wire.

The cases of D-40, in its own order:

1. a refresh replay after the rotation kills the family and answers ``invalid_grant``
2. a revoked client gets 401 with the right ``WWW-Authenticate`` and can reconnect fully
3. a ``redirect_uri`` that differs from the registration is refused, with no redirect to it
4. PKCE downgrade: no ``code_challenge`` and ``code_challenge_method=plain`` are refused
5. a token request with a wrong or missing ``code_verifier`` is refused
6. an audience mismatch is refused, at the issue and at the verification
7. with dynamic registration off, a registration fails with a message that names the reason
8. in the allowlist mode an unlisted client is refused at ``/authorize`` **and** at ``/token``

and the two the research added to the list:

9. a client name with a line break, a control character or HTML reaches neither the
   Nextcloud dialog nor our own page (pitfall 8, T-03-31, T-03-43)
10. no refusal repeats the value it received, in an answer, in an exception or in a log

Plus three gates that no behaviour test can see: the echo test over every rejection path,
the log test on DEBUG over the same set of calls, and a source gate that keeps the two
comparisons in ``provider.py`` and ``verifier.py`` on ``compare_digest`` and keeps a retry
loop against Nextcloud out of both.

Every Nextcloud answer comes from respx, the store is a SQLite file in ``tmp_path``, and
the throttle of this deployment is built with limits high enough to stay out of the way:
it has its own checks in ``test_oauth_provider.py``, and an abuse matrix that throttles
itself would stop testing what it is here for.
"""

import ast
import asyncio
import base64
import hashlib
import html
import inspect
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from mcp.shared.auth import OAuthClientInformationFull
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.exapp.browser_identity import AppApiBrowserIdentitySource
from mcp_connector.exapp.middleware import RequireAppApi
from mcp_connector.exapp.target import exapp_target
from mcp_connector.exapp.ui import consent as ui_consent
from mcp_connector.exapp.ui import strings
from mcp_connector.oauth import consent, crypto, loginflow, registry
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth import verifier as verifier_module
from mcp_connector.oauth.metadata import REFRESH_SCOPE, TOOL_SCOPE
from mcp_connector.oauth.store import ROTATION_GRACE, OAuthStore

BASE_URL = "http://nc.test"
PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
RESOURCE = f"{PUBLIC_URL}/mcp"
FOREIGN_RESOURCE = "https://other.example.com/mcp"
MCP_PATH = "/mcp"

CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
CLIENT_NAME = "Claude"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
FOREIGN_REDIRECT = "https://evil.example.com/collect"
STATE = "state-of-the-client"

VERIFIER = "a-code-verifier-of-the-client-that-is-long-enough"
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)

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
PASSWORD_URL = f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}"


class Clock:
    """A clock a test moves by hand, so the grace window has two sides without a sleep."""

    def __init__(self) -> None:
        self.now = float(int(time.time()))

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class Deployment:
    """One process of this application, assembled the way ``entry_exapp`` assembles it.

    The pieces that matter for an attacker are all here and all share one store: the
    authorization server, the consent surface, the token verifier of the transport
    boundary, and a route behind that boundary that stands for a tool call.
    """

    def __init__(
        self,
        tmp_path: Path,
        *,
        clock: Clock | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.env = ENV | (env or {})
        self.clock = clock
        self.store = OAuthStore(tmp_path / "oauth.sqlite3", KEY)
        self.policy = registry.client_policy(self.env)
        self.provider = provider_module.NextcloudOAuthProvider(
            nextcloud=exapp_target(self.env),
            env=self.env,
            policy=self.policy,
            store_provider=self._open,
            clock=clock,
        )
        self.verifier = verifier_module.StoreTokenVerifier(
            store_provider=self._open, get_client=self.provider.get_client, env=self.env
        )
        self.provider.on_revocation(self.verifier.invalidate)
        # High on purpose: the throttle has its own checks, and a matrix that throttles
        # itself stops testing the refusals it is here for.
        counters = throttle_module.Throttle(limit=10_000, ceiling=100_000, window=60)
        tool = Route(MCP_PATH, self._tool, methods=["GET"])
        tool.app = RequireAppApi(tool.app, self.env, token_verifier=self.verifier)
        self.client = TestClient(
            Starlette(
                routes=[
                    *provider_module.auth_routes(
                        self.env, provider=self.provider, throttle=counters
                    ),
                    *consent.consent_routes(
                        self.env,
                        provider=self.provider,
                        browser_identity=AppApiBrowserIdentitySource(self.env),
                        nextcloud=exapp_target(self.env),
                        throttle=counters,
                    ),
                    tool,
                ]
            )
        )

    async def _open(self) -> OAuthStore:
        return self.store

    async def _tool(self, request: Request) -> Response:
        del request
        return Response("a tool answer", status_code=200)


@pytest.fixture
def live(tmp_path: Path) -> Deployment:
    """A deployment with one registered client, which is the starting point of most cases."""
    deployment = Deployment(tmp_path)
    register(deployment)
    return deployment


def register(deployment: Deployment, **fields: object) -> None:
    payload: dict[str, object] = {
        "client_id": CLIENT_ID,
        "client_name": CLIENT_NAME,
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": TOOL_SCOPE,
    }
    payload.update(fields)
    asyncio.run(
        deployment.provider.register_client(OAuthClientInformationFull.model_validate(payload))
    )


def authorize_query(**overrides: str) -> dict[str, str]:
    query = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "redirect_uri": REDIRECT,
        "state": STATE,
        "scope": TOOL_SCOPE,
        "resource": RESOURCE,
    }
    query.update(overrides)
    return {key: value for key, value in query.items() if value}


def start_body() -> dict[str, object]:
    return {"poll": {"token": POLL_TOKEN, "endpoint": f"{BASE_URL}/x"}, "login": LOGIN_URL}


def poll_body() -> dict[str, str]:
    return {"server": BASE_URL, "loginName": LOGIN_NAME, "appPassword": APP_PASSWORD}


ACCOUNT_URL = f"{BASE_URL}{loginflow.ACCOUNT_PATH}"


def account_body(account: str = LOGIN_NAME) -> dict[str, object]:
    """The answer of OCS ``cloud/user`` for the fresh app password: the canonical id."""
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": {"id": account}}}


def ask(deployment: Deployment, **overrides: str) -> Any:
    """One authorization request, with the Nextcloud login flow start mocked."""
    with respx.mock:
        respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        return deployment.client.get(
            "/authorize", params=authorize_query(**overrides), follow_redirects=False
        )


def flow_of(response: Any) -> str:
    match = re.search(r"flow=([A-Za-z0-9_-]+)", response.headers["location"])
    assert match is not None, response.headers["location"]
    return match.group(1)


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


def sign_in(deployment: Deployment, flow_id: str) -> Any:
    with respx.mock:
        respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
        respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=account_body()))
        return deployment.client.get(
            f"{ui_consent.CONSENT_PATH}?{ui_consent.FLOW_PARAM}={flow_id}"
            f"&{ui_consent.STEP_PARAM}={ui_consent.STEP_WAIT}"
        )


def as_user(user: str = LOGIN_NAME) -> dict[str, str]:
    """The headers HaRP attaches to a request on the USER route of the decision (CR-01).

    These tests speak to the application directly, so they stand in for the proxy: the
    value is base64 of ``<user>:<APP_SECRET>``, built out of the Nextcloud account HaRP
    resolved and the registration secret of this app.
    """
    raw = f"{user}:{ENV[config.ENV_APP_SECRET]}".encode()
    return {
        "EX-APP-ID": ENV[config.ENV_APP_ID],
        "EX-APP-VERSION": ENV[config.ENV_APP_VERSION],
        "AUTHORIZATION-APP-API": base64.b64encode(raw).decode("ascii"),
    }


def approve(deployment: Deployment, flow_id: str) -> Any:
    return deployment.client.post(
        ui_consent.DECIDE_PATH,
        data={
            ui_consent.FLOW_PARAM: flow_id,
            ui_consent.DECISION_PARAM: ui_consent.DECISION_APPROVE,
            ui_consent.CONFIRM_PARAM: deployment.store.form_token(
                flow_id, purpose=crypto.PURPOSE_CONSENT
            ),
        },
        headers=as_user(),
        follow_redirects=False,
    )


def token_request(**fields: str) -> dict[str, str]:
    payload = {
        "grant_type": "authorization_code",
        "code_verifier": VERIFIER,
        "redirect_uri": REDIRECT,
        "client_id": CLIENT_ID,
    }
    payload.update(fields)
    return payload


def connect(deployment: Deployment) -> dict[str, Any]:
    """The whole way a client walks: authorize, sign in, approve, exchange. Returns tokens."""
    opened = ask(deployment)
    assert opened.status_code == 302, opened.text
    flow_id = flow_of(opened)
    sign_in(deployment, flow_id)
    granted = approve(deployment, flow_id)
    # 200 and not 302 since CR-03: the decision answers a page that navigates, because a
    # redirect out of a form submission is refused under ``form-action 'self'``.
    assert granted.status_code == 200, granted.text
    code = query_of(granted)["code"][0]
    answer = deployment.client.post("/token", data=token_request(code=code))
    assert answer.status_code == 200, answer.text
    return answer.json()


def appapi_headers(user: str = "") -> dict[str, str]:
    """What HaRP signs every request with; an empty user id is the OAuth branch (03-01)."""
    return {
        "EX-APP-ID": "mcp_connector",
        "EX-APP-VERSION": "0.1.0",
        "AUTHORIZATION-APP-API": base64.b64encode(f"{user}:app-secret-test".encode()).decode(),
    }


def tool_call(deployment: Deployment, access_token: str = "") -> Any:
    headers = appapi_headers()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return deployment.client.get(MCP_PATH, headers=headers)


# --- D-40 case 1: the refresh replay -------------------------------------------------------


def test_a_refresh_replay_after_the_rotation_kills_the_family(tmp_path: Path) -> None:
    """The whole point of the rotation: a copy of a token costs the connection it copied."""
    clock = Clock()
    deployment = Deployment(tmp_path, clock=clock)
    register(deployment)
    tokens = connect(deployment)

    rotated = deployment.client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": CLIENT_ID,
        },
    )
    assert rotated.status_code == 200, rotated.text
    clock.advance(ROTATION_GRACE + 1)

    replayed = deployment.client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": CLIENT_ID,
        },
    )

    assert replayed.status_code == 400
    assert replayed.json()["error"] == "invalid_grant"
    assert tool_call(deployment, rotated.json()["access_token"]).status_code == 401
    assert tool_call(deployment, tokens["access_token"]).status_code == 401


def test_a_retry_inside_the_window_keeps_the_connection_alive(tmp_path: Path) -> None:
    """The counter probe of the case above: the detection must not fire on a retry (D-41)."""
    clock = Clock()
    deployment = Deployment(tmp_path, clock=clock)
    register(deployment)
    tokens = connect(deployment)
    body = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": CLIENT_ID,
    }

    first = deployment.client.post("/token", data=body)
    clock.advance(ROTATION_GRACE - 1)
    second = deployment.client.post("/token", data=body)

    assert second.status_code == 200
    assert second.json() == first.json()
    assert tool_call(deployment, first.json()["access_token"]).status_code == 200


# --- D-40 case 2: the revoked client -------------------------------------------------------


def test_a_revoked_client_gets_a_401_with_a_pointer_and_can_connect_again(
    live: Deployment,
) -> None:
    """SC 4 end to end: revoke, be refused with the discovery pointer, walk the flow again."""
    tokens = connect(live)
    assert tool_call(live, tokens["access_token"]).status_code == 200
    anonymous = tool_call(live)

    with respx.mock:
        respx.delete(PASSWORD_URL).mock(return_value=httpx.Response(200))
        revoked = live.client.post(
            "/revoke", data={"client_id": CLIENT_ID, "token": tokens["refresh_token"]}
        )

    assert revoked.status_code == 200
    refused = tool_call(live, tokens["access_token"])
    assert refused.status_code == 401
    assert refused.headers["www-authenticate"] == anonymous.headers["www-authenticate"]
    assert "resource_metadata=" in refused.headers["www-authenticate"]
    assert tokens["access_token"] not in refused.text

    fresh = connect(live)
    assert fresh["access_token"] != tokens["access_token"]
    assert tool_call(live, fresh["access_token"]).status_code == 200


# --- D-40 case 3: the return address -------------------------------------------------------


def test_a_foreign_redirect_uri_is_refused_and_nothing_is_sent_to_it(live: Deployment) -> None:
    """T-03-41: the refusal must not be a redirect to the address it is refusing."""
    response = ask(live, redirect_uri=FOREIGN_REDIRECT)

    assert response.status_code == 400
    assert "location" not in response.headers
    assert FOREIGN_REDIRECT not in response.text
    assert strings.ERROR_REDIRECT_TITLE in response.text


def test_a_token_request_that_changes_the_return_address_is_refused(live: Deployment) -> None:
    """RFC 6749 §10.6: the address of the token request has to be the one of the code."""
    opened = ask(live)
    flow_id = flow_of(opened)
    sign_in(live, flow_id)
    code = query_of(approve(live, flow_id))["code"][0]

    answer = live.client.post(
        "/token", data=token_request(code=code, redirect_uri="https://claude.ai/other")
    )

    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_request"


# --- D-40 case 4: the PKCE downgrade -------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"code_challenge": ""}, "no challenge at all is the downgrade to no PKCE"),
        ({"code_challenge_method": "plain"}, "plain is a challenge an eavesdropper can reuse"),
    ],
    ids=["no-challenge", "plain-method"],
)
def test_a_pkce_downgrade_never_produces_a_code(
    live: Deployment, overrides: dict[str, str], why: str
) -> None:
    response = ask(live, **overrides)

    assert "code" not in query_of(response), why
    assert query_of(response)["error"] == ["invalid_request"]


# --- D-40 case 5: the code verifier --------------------------------------------------------


@pytest.mark.parametrize(
    "verifier", ["", "a-verifier-that-belongs-to-another-request"], ids=["missing", "wrong"]
)
def test_a_token_request_without_the_matching_verifier_is_refused(
    live: Deployment, verifier: str
) -> None:
    opened = ask(live)
    flow_id = flow_of(opened)
    sign_in(live, flow_id)
    code = query_of(approve(live, flow_id))["code"][0]

    answer = live.client.post("/token", data=token_request(code=code, code_verifier=verifier))

    assert answer.status_code == 400
    assert answer.json()["error"] in ("invalid_grant", "invalid_request")
    assert verifier not in answer.text or not verifier


# --- D-40 case 6: the audience -------------------------------------------------------------


def test_an_authorization_for_another_resource_opens_no_sign_in(live: Deployment) -> None:
    """RFC 8707, T-03-46: refusing here means no Nextcloud call for a grant that cannot be."""
    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = live.client.get(
            "/authorize",
            params=authorize_query(resource=FOREIGN_RESOURCE),
            follow_redirects=False,
        )

    assert init.call_count == 0
    assert query_of(response)["error"] == ["invalid_target"]
    assert "code" not in query_of(response)


def test_a_token_for_another_resource_is_refused_at_the_boundary(live: Deployment) -> None:
    """T-03-51: a token of another MCP server is perfectly valid and still not ours."""
    tokens = connect(live)
    asyncio.run(
        live.store.create_access_token(
            "a-token-issued-for-another-server",
            auth_id=_auth_id_of(live),
            family_id="another-family",
            scopes=TOOL_SCOPE,
            resource=FOREIGN_RESOURCE,
        )
    )

    assert tool_call(live, "a-token-issued-for-another-server").status_code == 401
    assert tool_call(live, tokens["access_token"]).status_code == 200, "the counter probe"


# --- D-40 case 7: dynamic registration switched off ----------------------------------------


def test_with_registration_off_the_route_is_gone_and_the_page_names_the_reason(
    tmp_path: Path,
) -> None:
    deployment = Deployment(tmp_path, env={registry.ENV_DCR: "off"})

    refused = deployment.client.post(
        "/register", json={"redirect_uris": [REDIRECT], "client_name": CLIENT_NAME}
    )
    page = deployment.client.get("/authorize", params=authorize_query(), follow_redirects=False)

    assert refused.status_code == 404, "the endpoint is removed, not left refusing"
    assert page.status_code == 400
    assert strings.ERROR_REGISTRATION_OFF_TITLE in page.text
    assert strings.ERROR_REGISTRATION_OFF_BODY.format(client=CLIENT_ID)[:40] in page.text


# --- D-40 case 8: the allowlist, at both endpoints ------------------------------------------


def test_in_the_allowlist_mode_an_unlisted_client_is_refused_at_authorize(
    tmp_path: Path,
) -> None:
    deployment = Deployment(tmp_path, env={registry.ENV_ALLOWLIST_ONLY: "1"})
    register(deployment)

    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = deployment.client.get(
            "/authorize", params=authorize_query(), follow_redirects=False
        )

    assert init.call_count == 0
    assert response.status_code == 403
    assert strings.ERROR_ALLOWLIST_TITLE in response.text


def test_in_the_allowlist_mode_an_unlisted_client_is_refused_at_token(tmp_path: Path) -> None:
    """Pitfall 9: the D-40 case that is only half done when only ``/authorize`` is checked.

    The rows are written directly, because in this mode the client can never reach the
    consent screen to produce them. That is the state an administrator creates when they
    switch the mode on while connections exist.
    """
    deployment = Deployment(tmp_path, env={registry.ENV_ALLOWLIST_ONLY: "1"})
    asyncio.run(_seed_connection(deployment))

    answer = deployment.client.post("/token", data=token_request(code="the-code-of-that-consent"))
    refreshed = deployment.client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": "the-refresh-token-of-that-consent",
            "client_id": CLIENT_ID,
        },
    )

    assert answer.status_code == 401
    assert answer.json()["error"] == "invalid_client"
    assert refreshed.status_code == 401
    assert refreshed.json()["error"] == "invalid_client"


# --- the two cases the research added -------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "Evil\r\nX-Injected: 1",
        "Evil\x00\x07name",
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
    ],
    ids=["crlf", "control", "script", "img"],
)
def test_a_hostile_client_name_reaches_neither_nextcloud_nor_our_page(
    tmp_path: Path, name: str
) -> None:
    """Pitfall 8, T-03-31, T-03-43: the name is attacker input on two different surfaces."""
    deployment = Deployment(tmp_path)
    register(deployment, client_name=name)

    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        opened = deployment.client.get(
            "/authorize", params=authorize_query(), follow_redirects=False
        )
    agent = init.calls[0].request.headers["user-agent"]
    page = sign_in(deployment, flow_of(opened))

    assert agent.startswith(loginflow.AGENT_PREFIX)
    assert all(character not in agent for character in "\r\n\x00\x07")
    # The page may show the name, and it may not show it as markup. An escaped ``onerror``
    # is inert text, an unescaped ``<img`` is a tag, so the tags are what is asserted on.
    assert "<script" not in page.text
    assert "<img" not in page.text
    assert page.status_code == 200


# --- the interop case the live run of AUTH-04 found -----------------------------------------

#: The return address of a ChatGPT connector, measured against the staging instance. It is
#: minted per connector and not a fixed path, which is why nothing here matches on it.
CHATGPT_REDIRECT = "https://chatgpt.com/connector/oauth/GxdvJstdJeOS"

#: What ChatGPT sends to ``/register``, field for field as it was measured. The absence of
#: ``scope`` is the whole point of this section: the SDK fills it with the default scopes,
#: and everything the client asks for at ``/authorize`` is compared against that one value.
CHATGPT_REGISTRATION: dict[str, object] = {
    "client_name": "ChatGPT",
    "redirect_uris": [CHATGPT_REDIRECT],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}


def register_over_http(deployment: Deployment, **fields: object) -> dict[str, Any]:
    """Register the way a connector does, over the endpoint, not over the provider method.

    The helper above calls :meth:`register_client` directly, which skips everything the SDK
    handler does to a registration before it arrives, and the scope default is exactly that.
    A regression test that took the short way would not have seen this bug.
    """
    payload = dict(CHATGPT_REGISTRATION)
    payload.update(fields)
    answer = deployment.client.post("/register", json=payload)
    assert answer.status_code == 201, answer.text
    return dict(answer.json())


def test_a_self_registered_client_may_ask_for_the_scopes_we_advertise(tmp_path: Path) -> None:
    """The bug of the live run: our own metadata advertised a scope our own AS refused.

    ChatGPT reads ``scopes_supported``, asks for both entries and was answered with
    ``invalid_scope``, because the registration had been recorded with the tool scope alone.
    Claude never asked for ``offline_access`` and therefore never hit it.
    """
    deployment = Deployment(tmp_path)
    registered = register_over_http(deployment)

    response = ask(
        deployment,
        client_id=str(registered["client_id"]),
        redirect_uri=CHATGPT_REDIRECT,
        scope=f"{REFRESH_SCOPE} {TOOL_SCOPE}",
    )

    assert set(str(registered["scope"]).split()) == {TOOL_SCOPE, REFRESH_SCOPE}
    assert response.status_code == 302, response.text
    assert "error" not in query_of(response), returned_to(response)
    assert ui_consent.CONSENT_PATH in returned_to(response)


def test_a_scope_this_server_does_not_have_is_still_refused(tmp_path: Path) -> None:
    """The counter probe: the fix grants the advertised scopes and not a wildcard (D-42)."""
    deployment = Deployment(tmp_path)
    registered = register_over_http(deployment)

    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        response = deployment.client.get(
            "/authorize",
            params=authorize_query(
                client_id=str(registered["client_id"]),
                redirect_uri=CHATGPT_REDIRECT,
                scope=f"{TOOL_SCOPE} nextcloud:admin",
            ),
            follow_redirects=False,
        )

    assert init.call_count == 0, "no sign in is opened for a request that cannot be granted"
    assert query_of(response)["error"] == ["invalid_scope"]
    assert "code" not in query_of(response)


def test_a_registration_that_names_an_unknown_scope_is_refused(tmp_path: Path) -> None:
    """The other half of the counter probe, one endpoint earlier (RFC 7591 §3.2.2)."""
    deployment = Deployment(tmp_path)

    refused = deployment.client.post(
        "/register", json={**CHATGPT_REGISTRATION, "scope": "nextcloud:admin"}
    )

    assert refused.status_code == 400
    assert refused.json()["error"] == "invalid_client_metadata"


def test_a_registration_from_before_the_fix_may_ask_for_the_refresh_scope(
    tmp_path: Path,
) -> None:
    """The rows that already exist on a running instance, and the reason for the read side.

    An administrator whose server carries the fix must not have to delete a connector in
    ChatGPT to get past a bug that is fixed. The row is written the way the old code wrote
    it, with the tool scope alone.
    """
    deployment = Deployment(tmp_path)
    asyncio.run(_seed_connection(deployment))

    response = ask(deployment, scope=f"{REFRESH_SCOPE} {TOOL_SCOPE}")

    assert response.status_code == 302, response.text
    assert "error" not in query_of(response), returned_to(response)


def test_offline_access_changes_nothing_about_the_tokens_that_are_issued(
    tmp_path: Path,
) -> None:
    """What the refresh switch does here: it is accepted, echoed, and grants no data.

    This server rotates refresh tokens for every authorization it grants (D-41), so the
    scope is not the switch that decides whether one is issued. It is recorded and echoed
    because a client compares the granted scope against the one it asked for, and it is
    never a second data scope: what the access token reaches is the tool surface either way.
    """
    deployment = Deployment(tmp_path)
    registered = register_over_http(deployment)
    client_id = str(registered["client_id"])
    asked = f"{REFRESH_SCOPE} {TOOL_SCOPE}"

    opened = ask(deployment, client_id=client_id, redirect_uri=CHATGPT_REDIRECT, scope=asked)
    flow_id = flow_of(opened)
    sign_in(deployment, flow_id)
    granted = approve(deployment, flow_id)
    code = query_of(granted)["code"][0]
    answer = deployment.client.post(
        "/token",
        data=token_request(code=code, client_id=client_id, redirect_uri=CHATGPT_REDIRECT),
    )
    rotated = deployment.client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": answer.json()["refresh_token"],
            "client_id": client_id,
        },
    )

    assert answer.status_code == 200, answer.text
    assert set(answer.json()["scope"].split()) == {TOOL_SCOPE, REFRESH_SCOPE}
    assert answer.json()["refresh_token"]
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["refresh_token"] != answer.json()["refresh_token"]
    assert tool_call(deployment, rotated.json()["access_token"]).status_code == 200


# --- the three gates no behaviour test can see ----------------------------------------------


def rejections(deployment: Deployment) -> list[Any]:
    """Every rejection path of this server, driven with values that must never come back."""
    secrets_presented = _presented()
    return [
        deployment.client.post("/token", data=token_request(code=secrets_presented["code"])),
        deployment.client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": secrets_presented["refresh"],
                "client_id": CLIENT_ID,
            },
        ),
        deployment.client.post(
            "/token",
            data=token_request(
                code=secrets_presented["code"], code_verifier=secrets_presented["verifier"]
            ),
        ),
        deployment.client.post(
            "/token",
            data=token_request(
                code=secrets_presented["code"], client_secret=secrets_presented["secret"]
            ),
        ),
        deployment.client.post(
            "/revoke", data={"client_id": CLIENT_ID, "token": secrets_presented["refresh"]}
        ),
        deployment.client.post("/revoke", data={"client_id": CLIENT_ID}),
        deployment.client.get(
            MCP_PATH,
            headers=appapi_headers() | {"Authorization": f"Bearer {secrets_presented['bearer']}"},
        ),
        ask(deployment, redirect_uri=FOREIGN_REDIRECT),
        ask(deployment, code_challenge=""),
        ask(deployment, resource=FOREIGN_RESOURCE),
        deployment.client.get(
            f"{ui_consent.CONSENT_PATH}?{ui_consent.FLOW_PARAM}={secrets_presented['flow']}"
        ),
    ]


def test_no_rejection_ever_repeats_the_value_it_received(live: Deployment) -> None:
    """T-03-66: a refusal that quotes what it refused is a mirror for whoever is guessing."""
    answers = rejections(live)

    for answer in answers:
        body = answer.text + repr(dict(answer.headers))
        for label, value in _presented().items():
            assert value not in body, f"{label} came back on {answer.status_code}"


def test_no_rejection_writes_a_received_value_to_the_log(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """T-03-66 on the other channel, on DEBUG, over the same set of calls.

    The property is not that nothing is logged: this server logs named events, such as a
    refresh token that was presented outside the grace window, because an administrator has
    to be able to see that one happened. The property is that no record carries a value of
    the request that produced it.
    """
    with caplog.at_level(logging.DEBUG, logger="mcp_connector"):
        rejections(live)

    for label, value in _presented().items():
        assert value not in caplog.text, f"{label} reached the log"
    assert CHALLENGE not in caplog.text


@pytest.mark.parametrize("module", [provider_module, verifier_module], ids=["provider", "verifier"])
def test_the_comparisons_are_constant_time_and_no_loop_talks_to_nextcloud(module: Any) -> None:
    """T-01-24 and D-37 as one source gate over the two files that decide about a token.

    Read as code and not as text: both files explain themselves at length, and a prose
    sentence containing the word "while" is not a loop. The docstrings are therefore
    stripped and the rest is unparsed, which also drops every comment.
    """
    source = inspect.getsource(module)
    code = _executable(source)

    assert source.count("compare_digest") >= 1, "a value from a request is never compared with =="
    assert "while " not in code, "a retry loop against Nextcloud would need one of these"
    assert "range(" not in code, "and so would a bounded one"
    assert "sleep" not in code, "a backoff is a retry with a nicer name"


def _executable(source: str) -> str:
    """The source without its docstrings and comments, so a gate reads code and not prose."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


def _presented() -> dict[str, str]:
    """The values every rejection above receives, and none of them may ever come back."""
    return {
        "code": "presented-code-must-never-be-echoed",
        "refresh": "presented-refresh-must-never-be-echoed",
        "verifier": "presented-verifier-must-never-be-echoed",
        "secret": "presented-secret-must-never-be-echoed",
        "bearer": "presented-bearer-must-never-be-echoed",
        "flow": "presented-flow-must-never-be-echoed",
    }


def _auth_id_of(deployment: Deployment) -> str:
    """The id of the one connection this deployment made, read back out of the store."""
    conn = sqlite3.connect(deployment.store.path)
    try:
        row = conn.execute("SELECT auth_id FROM authorizations LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row is not None
    return str(row[0])


async def _seed_connection(deployment: Deployment) -> None:
    """A client, a consent and a token pair, written past the policy that would refuse them."""
    await deployment.store.save_client(
        CLIENT_ID,
        metadata_json=OAuthClientInformationFull.model_validate(
            {
                "client_id": CLIENT_ID,
                "client_name": CLIENT_NAME,
                "redirect_uris": [REDIRECT],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "scope": TOOL_SCOPE,
            }
        ).model_dump_json(exclude={"client_secret"}),
        allowed=True,
    )
    await deployment.store.create_authorization(
        "the-connection-of-that-consent",
        client_id=CLIENT_ID,
        nc_user=LOGIN_NAME,
        nc_account_id=LOGIN_NAME,
        app_password=APP_PASSWORD,
        scopes=TOOL_SCOPE,
        resource=RESOURCE,
    )
    await deployment.store.create_auth_code(
        "the-code-of-that-consent",
        auth_id="the-connection-of-that-consent",
        redirect_uri=REDIRECT,
        code_challenge=CHALLENGE,
        resource=RESOURCE,
    )
    await deployment.store.create_refresh_token(
        "the-refresh-token-of-that-consent",
        auth_id="the-connection-of-that-consent",
        family_id="the-family-of-that-consent",
    )


def test_no_module_under_src_automates_a_nextcloud_sign_in() -> None:
    """AR-03-03: the gate that scripts/oauth_flow_check.py says exists.

    The measurement script drives a Nextcloud sign in with a test account's password,
    because a browser is the only actor that can perform one, and its docstring promises
    that no product code does the same. The promise was written down and never enforced;
    this is the enforcement.

    Two properties, both read as code with docstrings and comments stripped:

    1. No file under ``src/`` mentions ``requesttoken``. That is the anti forgery field of
       Nextcloud's sign in form, and nothing but a form filler needs it.
    2. The only Login Flow v2 paths the product knows are the two this app calls itself,
       plus the marker ``consent.py`` compares a returned link against (WR-07). The page
       where a password is typed, ``/login/v2/grant``, is not among them, and neither is
       the sign in form at ``/login``.

    What this does not prove: that no future code posts a password to some other address.
    A gate over strings cannot; it can only keep the shortcut of the measurement script
    from quietly becoming a pattern.
    """
    allowed = {
        ("oauth/loginflow.py", "/index.php/login/v2"),
        ("oauth/loginflow.py", "/login/v2/poll"),
        ("oauth/consent.py", "/login/v2/flow"),
    }
    root = Path(__file__).resolve().parents[2] / "src" / "mcp_connector"
    found: set[tuple[str, str]] = set()

    for path in sorted(root.rglob("*.py")):
        where = path.relative_to(root).as_posix()
        code = _executable(path.read_text(encoding="utf-8"))

        assert "requesttoken" not in code, f"{where} carries the sign in form's anti forgery field"
        assert "/login/v2/grant" not in code, f"{where} names the page that grants a sign in"

        for literal in re.findall(r"[\"']([^\"']*login/v2[^\"']*)[\"']", code):
            found.add((where, literal))

    unexpected = found - allowed
    assert not unexpected, f"a module under src/ knows a sign in path it should not: {unexpected}"

"""The ExApp entry point and the boundary against the two phase 1 modes (D-23, D-27).

Nothing here starts a server: ``build_exapp_app`` is a pure function of its environment,
and every ``main`` case below exits before uvicorn is reached. Three regressions matter most
in this file. The standalone HTTP application of phase 1 must not grow a lifecycle route
or an AppAPI requirement just because the ExApp module exists, the MCP route of the
ExApp application must never answer a request that carries no valid handshake (CR-01):
before the wrapper existed, an ``initialize`` without a single AppAPI header was answered
with 200 and a fresh session id. And since plan 03-01 the route is declared PUBLIC, so HaRP
no longer decides who reaches it: an AppAPI context without a user id has to pass our own
bearer check or leave with a 401 that points at the metadata (pitfall 6, T-03-01).
"""

import asyncio
import base64
import json
import logging
import os
import re
import sqlite3
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
import respx
from mcp.server.auth.provider import AccessToken
from mcp.shared.auth import OAuthClientInformationFull
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config, entry_exapp, entry_http
from mcp_connector.audit import record as audit_record
from mcp_connector.audit import store as audit_store_module
from mcp_connector.errors import IssuerRefused, ToolError
from mcp_connector.exapp import config_values
from mcp_connector.exapp.middleware import RequireAppApi
from mcp_connector.exapp.ui import connections as ui_connections
from mcp_connector.exapp.ui import strings
from mcp_connector.nextcloud import http as nc_http
from mcp_connector.oauth import connections, crypto, registry, store
from mcp_connector.oauth.metadata import (
    AS_METADATA_SUFFIX,
    PRM_SUFFIX,
    RESOURCE_SUFFIX,
    TOOL_SCOPE,
)
from mcp_connector.oauth.provider import auth_routes
from mcp_connector.oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity, StoreTokenVerifier

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"

EXAPP_ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_NEXTCLOUD_URL: "http://nc.test",
}
#: Behind HaRP the Host header is the one of the proxy, which is what the container sets
#: this to as well. Without it every request below would be answered with 421 instead.
SERVED_ENV = {**EXAPP_ENV, config.ENV_DISABLE_DNS_REBINDING: "1"}
#: The same environment with a configured public URL, so the pointer in the 401 can be
#: asserted as a whole string instead of as a fragment.
OAUTH_ENV = {**SERVED_ENV, config.ENV_PUBLIC_URL: PUBLIC_URL}

LIFECYCLE_PATHS = {"/heartbeat", "/init", "/enabled"}

#: The capability field of AUTH-08 in the authorization server document. Absence and presence
#: are the two states that matter here, which is why the name is a constant and not a literal
#: repeated in three checks.
CIMD_FIELD = "client_id_metadata_document_supported"

#: The registration behind the connection the end to end guard of this phase acts on, and
#: the bearer that connection was issued. Both are values of this file and of nothing else.
CONNECTED_CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
CONNECTED_TOKEN = "an-access-token-of-alice"

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

#: The address an administrator typed into the Nextcloud form of plan 05-01. Deliberately not
#: :data:`PUBLIC_URL`, so a check can tell which of the two sources won.
ADMIN_URL = "https://admin.example.com/exapps/mcp_connector"

#: The one outgoing call this file allows: the start time read of the seven admin values, on
#: the route plan 03-08 measured. The constants come from ``crypto`` rather than being spelled
#: a second time here.
READ_URL = (
    f"{EXAPP_ENV[config.ENV_NEXTCLOUD_URL]}{crypto.EXAPP_CONFIG_PATH}{crypto.CONFIG_READ_SUFFIX}"
)


def ocs(values: Mapping[str, str]) -> dict[str, object]:
    """The OCS envelope AppAPI 34 answers a config read with, in its lower case spelling."""
    return {
        "ocs": {
            "meta": {"status": "ok", "statuscode": 200, "message": "OK"},
            "data": [{"configkey": key, "configvalue": value} for key, value in values.items()],
        }
    }


@dataclass(frozen=True, slots=True)
class AdminConfig:
    """What Nextcloud has stored for this app, plus the route that answers with it.

    ``values`` is mutated by a check before it starts the process, because the read happens
    inside :func:`entry_exapp.main` and there is no other way to hand values into it.
    """

    values: dict[str, str]
    route: respx.Route

    def breaks(self) -> None:
        """Make the read fail the way an unreachable Nextcloud fails (T-05-20)."""
        self.route.mock(side_effect=httpx.ConnectError("this Nextcloud is not reachable"))


@pytest.fixture(autouse=True)
def admin_config() -> Iterator[AdminConfig]:
    """Answer the start time read locally, for every check of this file.

    Autouse on purpose: since plan 05-04 ``main`` reads the seven admin values once before it
    serves, so every check that starts the process would otherwise open a socket against
    ``nc.test``. An empty dictionary is an installation whose administrator has configured
    nothing, which is the state every older check of this file was written under.
    """
    values: dict[str, str] = {}
    with respx.mock(assert_all_called=False) as router:
        route = router.post(READ_URL).mock(
            side_effect=lambda request: httpx.Response(200, json=ocs(values))
        )
        yield AdminConfig(values, route)


def paths(app: object) -> set[str]:
    return {getattr(route, "path", "") for route in app.router.routes}  # type: ignore[attr-defined]


def appapi_headers(user: str = "alice", secret: str = APP_SECRET) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


class StubVerifier:
    """The one method of the SDK ``TokenVerifier`` protocol, over one accepted token.

    A verifier that answers nothing about the identity behind a token, which is what the
    SDK protocol is: the boundary may let such a token through, and the credential layer
    then has nothing to act on. ``None`` instead of a verifier stays the fail-closed state.
    """

    def __init__(self, accepted: str | None = None) -> None:
        self._accepted = accepted
        self.seen: list[str] = []

    async def verify_token(self, token: str) -> AccessToken | None:
        self.seen.append(token)
        if self._accepted is not None and token == self._accepted:
            return AccessToken(token=token, client_id="test-client", scopes=[TOOL_SCOPE])
        return None


class StubSource(StubVerifier):
    """The verifier of this app: it also says whose connection a token is (plan 03-06)."""

    def __init__(self, accepted: str | None = None, identity: OAuthIdentity | None = None) -> None:
        super().__init__(accepted)
        self._identity = identity

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        del access
        return self._identity


class StubSwitch:
    """The per account switch of the boundary, over a set of paused accounts (EXAPP-02).

    The shape ``entry_exapp`` hands in: one async call that takes a Nextcloud account and
    answers whether that account paused its MCP access. ``asked`` is what the tests of the
    check order assert on, because "was never asked" is the property that keeps an invalid
    token from learning whether an account exists.
    """

    def __init__(self, paused: set[str] | None = None, *, breaks: bool = False) -> None:
        self.paused = set(paused or ())
        self.breaks = breaks
        self.asked: list[str] = []

    async def __call__(self, nc_user: str) -> bool:
        self.asked.append(nc_user)
        if self.breaks:
            raise RuntimeError("the store of this deployment cannot be read")
        return nc_user in self.paused


def with_a_local_store(
    base: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, str], list[str]]:
    """An environment with a store in ``tmp_path`` and a data key that costs no network.

    The one thing a unit test cannot have is the OCS round trip that fetches the data key of
    this installation, and since the transport boundary reads the per account switch, every
    served request needs the store that holds it. The returned list counts the key fetches,
    which is how the tests below assert that opening the store is a once per process cost and
    not a Nextcloud round trip per MCP request (SC 5 of phase 3, D-47).
    """
    fetched: list[str] = []

    async def fake_key(env: object = None) -> bytes:
        del env
        fetched.append("key")
        return bytes(range(32))

    monkeypatch.setattr(store.crypto, "data_key", fake_key)
    return {**base, config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}, fetched


def guarded_app(
    verifier: StubVerifier | None = None,
    switch: Callable[[str], Awaitable[bool]] | None = None,
) -> Starlette:
    """One route behind the real boundary, so a verifier and a switch can be handed in.

    The route answers with the identity the boundary deposited, when there is one: that is
    the hand over the credential layer of ``deps.py`` reads on every tool call.
    """

    async def served(request: Request) -> Response:
        identity = getattr(request.state, OAUTH_STATE_ATTR, None)
        return PlainTextResponse("served" if identity is None else f"served as {identity.nc_user}")

    app = Starlette(routes=[Route("/mcp", served, methods=["GET", "POST"])])
    for route in app.router.routes:
        if isinstance(route, Route):
            route.app = RequireAppApi(
                route.app, OAUTH_ENV, token_verifier=verifier, access_check=switch
            )
    return app


# --- the application -------------------------------------------------------------


def test_the_exapp_app_carries_the_three_lifecycle_routes() -> None:
    assert paths(entry_exapp.build_exapp_app(EXAPP_ENV)) >= LIFECYCLE_PATHS


def test_the_standalone_http_app_has_no_lifecycle_route() -> None:
    """D-23: phase 1 stays exactly as it was, whoever imported the ExApp package."""
    assert not LIFECYCLE_PATHS & paths(entry_http.build_app({}))


def test_the_exapp_app_still_serves_mcp() -> None:
    assert "/mcp" in paths(entry_exapp.build_exapp_app(EXAPP_ENV))


# --- the transport boundary (CR-01) ----------------------------------------------


@pytest.mark.parametrize(
    ("name", "headers"),
    [
        ("nothing at all", {}),
        ("only the app id", {"EX-APP-ID": APP_ID}),
        ("a wrong secret", appapi_headers(secret="not-the-secret")),
        ("a foreign app id", {**appapi_headers(), "EX-APP-ID": "other_app"}),
        ("a bearer instead", {"Authorization": "Bearer whatever"}),
    ],
)
def test_initialize_without_a_valid_handshake_is_rejected(
    name: str, headers: dict[str, str]
) -> None:
    """CR-01: the JSON-RPC preamble used to be served to anyone who reached the socket.

    Not a session, not a serverInfo, not a tool list: the request never reaches MCP code.
    """
    with TestClient(entry_exapp.build_exapp_app(SERVED_ENV)) as client:
        response = client.post("/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **headers})

    assert response.status_code == 401, name
    assert response.content == b"", name
    assert "mcp-session-id" not in {key.lower() for key in response.headers}, name
    assert response.headers["cache-control"] == "no-store", name
    # An invalid handshake says nothing at all, not even which scheme would work: the
    # caller behind those headers is a proxy, not an OAuth client (T-02-03).
    assert "www-authenticate" not in {key.lower() for key in response.headers}, name


def test_initialize_with_a_valid_handshake_is_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolved Nextcloud user is the AUTH-01 path and is not asked for a bearer.

    Since plan 04-01 this path reads the per account switch as well, so the application
    needs the store it reads it from: a local file and a data key that does not come over
    the network in a unit test. An account that never paused anything has no row there, and
    a request of that account is served exactly as it was before the switch existed.
    """
    env, _ = with_a_local_store(SERVED_ENV, tmp_path, monkeypatch)

    with TestClient(entry_exapp.build_exapp_app(env)) as client:
        response = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="alice")}
        )

    assert response.status_code == 200
    assert "protocolVersion" in response.text


# --- the 421 of issue #4: AIO forwards the public custom domain as the Host ---------

#: The deploy environment of a Nextcloud AIO installation, and every value of it was read
#: out of the source of the two components rather than assumed:
#:
#: * No ``HP_SHARED_KEY``. AIO registers its HaRP daemon with ``exapp_direct => true``
#:   (``AIODockerActions::registerAIOHarpDaemonConfig``), and ``DockerActions::
#:   buildDeployEnvs`` skips all three ``HP_*`` variables for a direct connect daemon. So
#:   the entrypoint of our container never exports the rebinding switch, and the Host check
#:   is armed in exactly the deployment that gets a foreign Host header.
#: * ``NEXTCLOUD_URL`` is the public custom domain, not an internal name: AIO passes
#:   ``'nextcloud_url' => 'https://' . getenv('NC_DOMAIN')``.
#: * That same domain arrives in the ``Host`` header, because nothing on the way rewrites
#:   it: the AIO Caddyfile reverse proxies ``/exapps/*`` without ``header_up Host``, and the
#:   HaRP ``ex_apps_backend`` sets EX-APP-ID, EX-APP-VERSION, AUTHORIZATION-APP-API and
#:   AA-VERSION, changes the destination with ``set-dst``, and touches no Host.
#:
#: Deliberately no ``NC_MCP_PUBLIC_URL``: this is the first minute of a one click
#: installation from the app store, which has no deploy variable and no filled in form yet.
AIO_ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_NEXTCLOUD_URL: "https://cloud.example.com",
}


def test_the_aio_custom_domain_is_served_instead_of_answering_421(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #4, reproduced against the real application object and then fixed.

    Measured before the fix, over a real socket and with a valid AppAPI handshake:
    ``HTTP/1.1 421 Misdirected Request`` with the body ``Invalid Host header`` and one
    WARNING per request in the container log, for every ``/mcp`` request of an AIO
    installation with a custom domain. The installation looks green, because the lifecycle
    routes sit before the transport check.

    Nothing about the environment below is unusual, and that is the whole point: it is what
    the deploy daemon sets and nothing else. An installation from the app store gets no
    deploy variable, so ``NC_MCP_ALLOWED_HOSTS`` was not a way out for the administrator
    who reported this.
    """
    env, _ = with_a_local_store(AIO_ENV, tmp_path, monkeypatch)

    with TestClient(
        entry_exapp.build_exapp_app(env), base_url="http://cloud.example.com"
    ) as client:
        response = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="alice")}
        )

    assert response.status_code == 200, response.text
    assert "protocolVersion" in response.text


def test_a_foreign_host_is_still_refused_in_the_same_deployment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative half: the allowlist was narrowed to this deployment, not opened.

    Same environment, same valid AppAPI handshake, a host name that is not this
    deployment's: the transport check answers 421 exactly as it did before.
    """
    env, _ = with_a_local_store(AIO_ENV, tmp_path, monkeypatch)

    with TestClient(entry_exapp.build_exapp_app(env), base_url="http://evil.example") as client:
        response = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="alice")}
        )

    assert response.status_code == 421
    assert response.text == "Invalid Host header"


# --- the second identity source of the same boundary (T-03-01, T-03-06) -----------


def test_an_empty_user_without_a_bearer_gets_the_discovery_401() -> None:
    """The 401 that starts the OAuth flow, out of /mcp itself and not out of HaRP.

    Until phase 2 the empty user id was the app context and passed on purpose (T-02-12);
    since /mcp is PUBLIC it is also what an anonymous caller produces, so the second check
    of this boundary decides here instead of at the credential layer.
    """
    with TestClient(entry_exapp.build_exapp_app(OAUTH_ENV)) as client:
        response = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="")}
        )

    assert response.status_code == 401
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith('Bearer error="invalid_token"')
    assert f'scope="{TOOL_SCOPE}"' in challenge
    assert f'resource_metadata="{PUBLIC_URL}{PRM_SUFFIX}"' in challenge
    assert "offline_access" not in challenge


@pytest.mark.parametrize(
    "authorization",
    ["Bearer whatever", "Bearer ", "bearer lower-case-scheme", "Basic YWxpY2U6cHc=", ""],
    ids=["a token", "an empty token", "a lower case scheme", "another scheme", "no header"],
)
def test_an_empty_user_is_refused_for_every_bearer_while_no_verifier_exists(
    authorization: str,
) -> None:
    """Fail-closed: without a verifier every bearer is invalid, never 200 and never 500."""
    headers = {**MCP_HEADERS, **appapi_headers(user="")}
    if authorization:
        headers["Authorization"] = authorization

    with TestClient(entry_exapp.build_exapp_app(OAUTH_ENV)) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=headers)

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_the_401_of_the_bearer_boundary_never_repeats_the_token() -> None:
    """T-03-06: not in the body, not in a header, not in the challenge."""
    secret_token = "5f4dcc3b5aa765d61d8327deb882cf99"
    headers = {
        **MCP_HEADERS,
        **appapi_headers(user=""),
        "Authorization": f"Bearer {secret_token}",
    }

    with TestClient(entry_exapp.build_exapp_app(OAUTH_ENV)) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=headers)

    assert response.status_code == 401
    assert secret_token not in response.text
    for key, value in response.headers.items():
        assert secret_token not in value, key


def test_a_verified_bearer_reaches_the_route_behind_the_boundary() -> None:
    """The other direction of the same branch, with the verifier plan 03-06 will hand in."""
    verifier = StubVerifier(accepted="a-good-token")

    with TestClient(guarded_app(verifier)) as client:
        response = client.get(
            "/mcp", headers={**appapi_headers(user=""), "Authorization": "Bearer a-good-token"}
        )

    assert response.status_code == 200
    assert response.text == "served"
    assert verifier.seen == ["a-good-token"]


def test_a_rejected_bearer_stops_at_the_boundary() -> None:
    verifier = StubVerifier(accepted="a-good-token")

    with TestClient(guarded_app(verifier)) as client:
        response = client.get(
            "/mcp", headers={**appapi_headers(user=""), "Authorization": "Bearer a-stolen-token"}
        )

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    assert verifier.seen == ["a-stolen-token"]


def test_a_verified_bearer_leaves_its_identity_for_the_credential_layer() -> None:
    """The hand over of plan 03-06: the boundary resolves, the tool call reads (D-26)."""
    identity = OAuthIdentity(
        nc_user="alice", app_password="app-password", auth_id="auth-1", client_id="client-1"
    )
    source = StubSource(accepted="a-good-token", identity=identity)

    with TestClient(guarded_app(source)) as client:
        response = client.get(
            "/mcp", headers={**appapi_headers(user=""), "Authorization": "Bearer a-good-token"}
        )

    assert response.status_code == 200
    assert response.text == "served as alice"


def test_a_token_whose_connection_is_gone_stops_at_the_boundary() -> None:
    """Fail closed: a token this server cannot turn into an identity is not a valid one."""
    source = StubSource(accepted="a-good-token", identity=None)

    with TestClient(guarded_app(source)) as client:
        response = client.get(
            "/mcp", headers={**appapi_headers(user=""), "Authorization": "Bearer a-good-token"}
        )

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_the_mcp_route_is_guarded_with_the_verifier_of_this_deployment() -> None:
    """Plan 03-06 wires the real verifier, at the one place the boundary is built."""
    app = entry_exapp.build_exapp_app(OAUTH_ENV)

    guards = [
        route.app
        for route in app.router.routes
        if isinstance(route, Route) and route.path == entry_exapp.MCP_PATH
    ]

    assert len(guards) == 1
    guard = guards[0]
    assert isinstance(guard, RequireAppApi)
    assert isinstance(guard._token_verifier, StoreTokenVerifier)


def test_a_resolved_user_is_never_asked_for_a_bearer() -> None:
    """Two identity sources, one branch each: no fallback from one to the other (D-27)."""
    verifier = StubVerifier(accepted="a-good-token")

    with TestClient(guarded_app(verifier)) as client:
        response = client.get(
            "/mcp",
            headers={**appapi_headers(user="alice"), "Authorization": "Bearer a-stolen-token"},
        )

    assert response.status_code == 200
    assert verifier.seen == [], "the AUTH-01 path read the Authorization header"


def test_a_duplicated_route_wrap_is_a_build_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The counter probe: a silently unwrapped MCP route is the whole finding CR-01."""
    original = entry_exapp.MCP_PATH
    monkeypatch.setattr(entry_exapp, "MCP_PATH", "/not-a-route")

    with pytest.raises(RuntimeError, match="without the AppAPI handshake"):
        entry_exapp.build_exapp_app(EXAPP_ENV)

    assert original == "/mcp"


# --- the per account switch of the same boundary (EXAPP-02, R1, D-49) --------------


def test_a_paused_account_is_refused_on_the_appapi_branch() -> None:
    """D-49: the switch blocks the app password way in, and the answer is R1, not a 401."""
    switch = StubSwitch(paused={"alice"})

    with TestClient(guarded_app(switch=switch)) as client:
        response = client.get("/mcp", headers=appapi_headers(user="alice"))

    assert response.status_code == 403
    assert json.loads(response.text)["error"] == "access_disabled"
    assert switch.asked == ["alice"]


def test_a_paused_account_is_refused_on_the_oauth_branch_as_well() -> None:
    """The other way in, same account, same answer: one decision for both (D-49)."""
    identity = OAuthIdentity(
        nc_user="alice", app_password="app-password", auth_id="auth-1", client_id="client-1"
    )
    source = StubSource(accepted="a-good-token", identity=identity)
    switch = StubSwitch(paused={"alice"})

    with TestClient(guarded_app(source, switch)) as client:
        response = client.get(
            "/mcp", headers={**appapi_headers(user=""), "Authorization": "Bearer a-good-token"}
        )

    assert response.status_code == 403
    assert json.loads(response.text)["error"] == "access_disabled"
    assert switch.asked == ["alice"], "the identity of the token is what the switch is asked about"


def test_the_refusal_of_a_paused_account_is_the_wire_contract_of_the_ui_spec() -> None:
    """R1 word for word: 403, the named code, the sentence, no challenge, no-store.

    The missing ``WWW-Authenticate`` is the deliberate deviation from RFC 6750: there is no
    other scope and no other credential to come back with, and the header is what would pull
    an OAuth client into the whole discovery loop again for a decision its user made.
    """
    switch = StubSwitch(paused={"alice"})

    with TestClient(guarded_app(switch=switch)) as client:
        response = client.get("/mcp", headers=appapi_headers(user="alice"))

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/json")
    assert "www-authenticate" not in {key.lower() for key in response.headers}
    body = json.loads(response.text)
    assert body == {
        "error": "access_disabled",
        "error_description": strings.ACCESS_DISABLED_DESCRIPTION,
    }
    assert strings.SETTINGS_PLACE in body["error_description"], "the sentence names the place"
    # T-03-66: the sentence states the rule, never a value out of the request.
    assert "alice" not in response.text
    assert APP_SECRET not in response.text


def test_an_invalid_bearer_of_a_paused_account_is_still_the_discovery_401() -> None:
    """The check order is the security here (pitfall 2): handshake, credential, switch.

    A 403 in front of the credential check would tell anyone who guesses an account name
    that the account exists and that it paused its access.
    """
    verifier = StubVerifier(accepted="a-good-token")
    switch = StubSwitch(paused={"alice"})

    with TestClient(guarded_app(verifier, switch)) as client:
        response = client.get(
            "/mcp", headers={**appapi_headers(user=""), "Authorization": "Bearer a-stolen-token"}
        )

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    assert switch.asked == [], "an unauthenticated caller must not reach the switch at all"


def test_a_broken_handshake_of_a_paused_account_is_still_the_bare_401() -> None:
    """R3 is unchanged, and it stays first: no detail, no challenge, no switch (T-02-03)."""
    switch = StubSwitch(paused={"alice"})

    with TestClient(guarded_app(switch=switch)) as client:
        response = client.get("/mcp", headers={"EX-APP-ID": APP_ID})

    assert response.status_code == 401
    assert response.content == b""
    assert "www-authenticate" not in {key.lower() for key in response.headers}
    assert switch.asked == []


def test_the_app_context_is_never_asked_for_a_switch() -> None:
    """Pitfall 10: an empty resolved identity has no switch, and the bearer already decided."""
    verifier = StubVerifier(accepted="a-good-token")
    switch = StubSwitch(paused={"alice"})

    with TestClient(guarded_app(verifier, switch)) as client:
        response = client.get(
            "/mcp", headers={**appapi_headers(user=""), "Authorization": "Bearer a-good-token"}
        )

    assert response.status_code == 200
    assert response.text == "served"
    assert switch.asked == []


def test_flipping_the_switch_takes_effect_on_the_very_next_request() -> None:
    """D-48 and D-46 in one run, on one application instance and one token.

    No cache may soften the pause, and switching back on restores the connection without a
    new sign in: the same credential is served again on the third request.
    """
    switch = StubSwitch()

    with TestClient(guarded_app(switch=switch)) as client:
        before = client.get("/mcp", headers=appapi_headers(user="alice"))
        switch.paused.add("alice")
        paused = client.get("/mcp", headers=appapi_headers(user="alice"))
        switch.paused.discard("alice")
        after = client.get("/mcp", headers=appapi_headers(user="alice"))

    assert before.status_code == 200
    assert paused.status_code == 403
    assert after.status_code == 200
    assert switch.asked == ["alice", "alice", "alice"], "every request reads the switch again"


def test_the_switch_of_the_real_store_reaches_the_boundary(tmp_path: Path) -> None:
    """The end to end guard of this plan, with the store instead of a stub.

    A test that only checked the store round trip would stay green with no gate in the
    boundary at all, which is the whole of pitfall 1: the write is flipped behind the
    running application, and the very next request has to be the refusal.
    """
    subject = store.OAuthStore(tmp_path / store.STORE_FILENAME, bytes(range(32)))

    with TestClient(guarded_app(switch=subject.access_disabled)) as client:
        before = client.get("/mcp", headers=appapi_headers(user="alice"))
        asyncio.run(subject.set_access("alice", disabled=True))
        paused = client.get("/mcp", headers=appapi_headers(user="alice"))
        asyncio.run(subject.set_access("alice", disabled=False))
        after = client.get("/mcp", headers=appapi_headers(user="alice"))

    assert before.status_code == 200
    assert paused.status_code == 403
    assert json.loads(paused.text)["error"] == "access_disabled"
    assert after.status_code == 200


def test_a_store_that_cannot_answer_the_switch_refuses_instead_of_letting_through(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fail closed (the D-37 analogy): a store outage is not a decision of the user.

    So it is neither a pass through nor a claim that the account paused its access. It is a
    503 that says nothing else, plus one log line for the administrator.
    """
    switch = StubSwitch(breaks=True)

    with (
        caplog.at_level("ERROR", logger="mcp_connector.exapp.middleware"),
        TestClient(guarded_app(switch=switch)) as client,
    ):
        response = client.get("/mcp", headers=appapi_headers(user="alice"))

    assert response.status_code == 503
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    assert "access_disabled" not in response.text
    assert caplog.records, "a store that cannot be read has to say so once"


def test_a_boundary_without_a_switch_serves_exactly_as_before() -> None:
    """The default of the new parameter is the behaviour of phase 3, unchanged."""
    with TestClient(guarded_app()) as client:
        response = client.get("/mcp", headers=appapi_headers(user="alice"))

    assert response.status_code == 200
    assert response.text == "served"


def test_the_mcp_route_is_guarded_with_the_switch_of_this_deployment() -> None:
    """The wiring: the store that holds the tokens is the store that holds the switch."""
    app = entry_exapp.build_exapp_app(OAUTH_ENV)

    guards = [
        route.app
        for route in app.router.routes
        if isinstance(route, Route) and route.path == entry_exapp.MCP_PATH
    ]

    assert len(guards) == 1
    guard = guards[0]
    assert isinstance(guard, RequireAppApi)
    assert guard._access_check is not None, "the boundary was built without the switch"


def test_the_switch_costs_no_nextcloud_round_trip_per_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC 5 of phase 3, which this phase may not worsen: one round trip per MCP call.

    The switch is a local read, and the one network call the store needs at all, the data key
    of this installation, is paid once per process by the opener both halves share. Three
    served requests therefore fetch it once, and nothing else of the switch leaves the
    container.
    """
    env, fetched = with_a_local_store(SERVED_ENV, tmp_path, monkeypatch)

    with TestClient(entry_exapp.build_exapp_app(env)) as client:
        for _ in range(3):
            response = client.post(
                "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="alice")}
            )
            assert response.status_code == 200

    assert fetched == ["key"], "the store was opened per request instead of per process"


def test_a_paused_account_is_refused_by_the_wired_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole chain of this plan in one test: store, wiring, boundary, R1.

    The switch is flipped in the file the running application reads, behind its back and
    between two requests, which is what "the flip takes effect on the next request" means
    (D-48). Nothing is disconnected by it, and turning it back on serves the same caller
    again without a new sign in (D-46).
    """
    env, _ = with_a_local_store(SERVED_ENV, tmp_path, monkeypatch)
    subject = store.OAuthStore(tmp_path / store.STORE_FILENAME, bytes(range(32)))

    with TestClient(entry_exapp.build_exapp_app(env)) as client:
        before = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="alice")}
        )
        asyncio.run(subject.set_access("alice", disabled=True))
        paused = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="alice")}
        )
        other = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="bob")}
        )
        asyncio.run(subject.set_access("alice", disabled=False))
        after = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="alice")}
        )

    assert before.status_code == 200
    assert paused.status_code == 403
    assert json.loads(paused.text) == {
        "error": "access_disabled",
        "error_description": strings.ACCESS_DISABLED_DESCRIPTION,
    }
    assert "www-authenticate" not in {key.lower() for key in paused.headers}
    assert paused.headers["cache-control"] == "no-store"
    assert other.status_code == 200, "the switch of one account is not the switch of another"
    assert after.status_code == 200


def test_the_switch_is_decided_at_the_boundary_and_nowhere_else() -> None:
    """One source for one sentence: no tool may carry a second copy of this decision."""
    tools = Path("src/mcp_connector/tools").glob("*.py")
    offenders = [path.name for path in tools if "access_disabled" in path.read_text("utf-8")]

    assert offenders == []


def test_the_standalone_http_app_serves_mcp_without_any_appapi_header() -> None:
    """D-23: phase 1 has no AppAPI identity, so it must not grow a handshake it cannot
    satisfy. This is the regression guard for the fix of CR-01."""
    with TestClient(entry_http.build_app({config.ENV_DISABLE_DNS_REBINDING: "1"})) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)

    assert response.status_code == 200
    assert "protocolVersion" in response.text


# --- the other direction of the mode switch (WR-03) -------------------------------


def test_ambient_appapi_variables_stop_the_standalone_http_app() -> None:
    """WR-03: APP_ID and APP_SECRET are the two mode switches without an NC_MCP_ prefix,
    and they are common names. A base image or a CI variable that sets them used to flip
    a phase 1 server into the ExApp credential mode without touching its configuration,
    which locks out every user of a passthrough deployment."""
    env = {config.ENV_APP_ID: "some-github-app", config.ENV_APP_SECRET: "some-other-thing"}
    assert config.select_mode(env, headers={}) == "exapp", "the counter probe stopped working"

    with pytest.raises(ToolError) as excinfo:
        entry_http.build_app(env)

    assert config.ENV_APP_SECRET in excinfo.value.message
    assert "nc-mcp-exapp" in excinfo.value.hint


@pytest.mark.parametrize(
    "env",
    [
        {},
        {config.ENV_APP_ID: "mcp_connector"},
        {config.ENV_APP_SECRET: "app-secret-test"},
        {config.ENV_APP_ID: "mcp_connector", config.ENV_APP_SECRET: "   "},
    ],
    ids=["nothing set", "only the id", "only the secret", "a blank secret"],
)
def test_the_guard_leaves_every_other_http_deployment_alone(env: dict[str, str]) -> None:
    """A blank value is a typo in a compose file, not a request to change the mode, and
    one of the two variables alone never selected the ExApp mode either."""
    assert "/mcp" in paths(entry_http.build_app(env))


# --- the startup validation ------------------------------------------------------


@pytest.mark.parametrize("conflicting", [config.ENV_STATIC_BEARER, config.ENV_APP_PASSWORD])
def test_a_second_credential_channel_stops_the_start(
    monkeypatch: pytest.MonkeyPatch, conflicting: str
) -> None:
    """T-02-08: an ExApp process with a second way to authenticate is a misconfiguration."""
    for name, value in EXAPP_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(config.ENV_STATIC_BEARER, raising=False)
    monkeypatch.delenv(config.ENV_APP_PASSWORD, raising=False)
    monkeypatch.setenv(conflicting, "something")

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()
    assert excinfo.value.code == 2


def test_a_missing_deploy_variable_stops_the_start(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (*EXAPP_ENV, config.ENV_STATIC_BEARER, config.ENV_APP_PASSWORD):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(config.ENV_APP_ID, "mcp_connector")

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()
    assert excinfo.value.code == 2


@pytest.mark.parametrize(
    ("env", "warned"),
    [
        ({}, True),
        ({config.ENV_HP_SHARED_KEY: "x" * 64}, False),
        ({config.ENV_ALLOWED_HOSTS: "harp.example"}, False),
        ({config.ENV_DISABLE_DNS_REBINDING: "1"}, False),
        ({config.ENV_HP_SHARED_KEY: "   ", config.ENV_ALLOWED_HOSTS: ""}, True),
        ({config.ENV_PUBLIC_URL: "https://cloud.example.com/exapps/mcp_connector"}, False),
        ({config.ENV_PUBLIC_URL: "not-an-address"}, True),
    ],
    ids=[
        "neither key nor allowlist",
        "harp path selected",
        "allowlist set",
        "host check disabled",
        "blank values do not count as a decision",
        "a public address answers the question",
        "an unreadable address answers nothing",
    ],
)
def test_the_421_trap_of_a_daemon_without_harp_is_named_at_startup(
    caplog: pytest.LogCaptureFixture, env: dict[str, str], warned: bool
) -> None:
    """IN-04: without HaRP the Host header is the container name, the check stays armed
    with the localhost default, and every /mcp request dies as a 421 while the
    installation looks green. The warning names it once; an operator who set the
    allowlist, the shared key or the rebinding switch already decided."""
    with caplog.at_level("WARNING", logger="mcp_connector.entry_exapp"):
        entry_exapp._warn_when_the_host_check_is_a_trap(env)

    messages = [record.getMessage() for record in caplog.records]
    assert any(config.ENV_ALLOWED_HOSTS in message for message in messages) is warned, messages


def test_a_missing_persistent_volume_stops_the_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-03-15: a store without a volume loses every authorization on the next restart,
    and it does so silently in production, weeks after the install looked green."""
    for name, value in EXAPP_ENV.items():
        monkeypatch.setenv(name, value)
    for name in (
        config.ENV_STATIC_BEARER,
        config.ENV_APP_PASSWORD,
        config.ENV_APP_PERSISTENT_STORAGE,
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()
    assert excinfo.value.code == 2


def test_the_missing_volume_names_itself_in_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for name, value in EXAPP_ENV.items():
        monkeypatch.setenv(name, value)
    for name in (
        config.ENV_STATIC_BEARER,
        config.ENV_APP_PASSWORD,
        config.ENV_APP_PERSISTENT_STORAGE,
    ):
        monkeypatch.delenv(name, raising=False)

    with caplog.at_level("ERROR", logger="mcp_connector.entry_exapp"), pytest.raises(SystemExit):
        entry_exapp.main()

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_APP_PERSISTENT_STORAGE in messages
    assert APP_SECRET not in messages


@pytest.mark.parametrize("port", [None, "", "not-a-number"])
def test_a_missing_or_broken_port_stops_the_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: str | None
) -> None:
    """A ValueError traceback out of int() would tell an administrator nothing."""
    for name, value in EXAPP_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(config.ENV_APP_PERSISTENT_STORAGE, str(tmp_path))
    for name in (config.ENV_STATIC_BEARER, config.ENV_APP_PASSWORD, config.ENV_HP_SHARED_KEY):
        monkeypatch.delenv(name, raising=False)
    if port is None:
        monkeypatch.delenv(config.ENV_APP_PORT, raising=False)
    else:
        monkeypatch.setenv(config.ENV_APP_PORT, port)

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()
    assert excinfo.value.code == 2


# --- the admin values of the start, and the setup state instead of exit 2 (05-04) --


def deployed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env: Mapping[str, str] | None = None,
) -> None:
    """Put a complete AppAPI deploy environment of the HaRP shape into ``os.environ``.

    The HaRP branch is selected because it needs no port, and the data key is answered
    locally, because a unit test has no Nextcloud to fetch it from.
    """
    deploy = {
        **EXAPP_ENV,
        config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path),
        config.ENV_HP_SHARED_KEY: "a" * 64,
        config.ENV_DISABLE_DNS_REBINDING: "1",
    }
    for name, value in deploy.items():
        monkeypatch.setenv(name, value)
    for name in (
        config.ENV_STATIC_BEARER,
        config.ENV_APP_PASSWORD,
        config.ENV_PUBLIC_URL,
        registry.ENV_DCR,
        registry.ENV_CIMD,
        registry.ENV_ALLOWLIST_ONLY,
        registry.ENV_ALLOWED_CLIENTS,
    ):
        monkeypatch.delenv(name, raising=False)

    # ``main`` writes this one key back into ``os.environ`` (plan 09-02), and monkeypatch
    # only undoes what it has touched itself. Recording the variable here before the start
    # is therefore what keeps a value written by one check from answering
    # ``config.talk_send_enabled`` in the next one: the setenv records that it was unset,
    # the delenv removes it again, and the teardown restores that unset state.
    monkeypatch.setenv(config.ENV_TALK_SEND, "")
    monkeypatch.delenv(config.ENV_TALK_SEND)

    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)

    async def fake_key(env: object = None) -> bytes:
        del env
        return bytes(range(32))

    monkeypatch.setattr(store.crypto, "data_key", fake_key)


def start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    env: Mapping[str, str] | None = None,
) -> Starlette:
    """Run ``main`` up to the point where it would serve, and return the built application.

    ``uvicorn.run`` is the last statement of every branch of ``main``, so replacing it is what
    turns the entry point into something a check can look at: whatever the resolution of the
    environment produced is now visible in the documents of this application.
    """
    deployed(monkeypatch, tmp_path, env)

    built: list[Starlette] = []

    def fake_run(app: Starlette, **kwargs: object) -> None:
        del kwargs
        built.append(app)

    monkeypatch.setattr(entry_exapp.uvicorn, "run", fake_run)
    entry_exapp.main()

    assert built, "main returned without ever reaching the server"
    return built[0]


def document_of(app: Starlette, path: str) -> dict[str, Any]:
    """One discovery document of a built application, read in process."""
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    return dict(response.json())


def test_an_admin_value_is_the_address_the_started_app_calls_itself(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The whole point of plans 05-01 and 05-04: a store installation sets no variable.

    With one Docker daemon, ``exApps.enableApp`` calls ``enableExApp`` without deploy options,
    so no ``NC_MCP_*`` variable ever reaches the container (05-RESEARCH, pitfall 2). The value
    the administrator typed into the Nextcloud form therefore has to become the ``resource`` of
    the protected resource document, and with it the issuer, the audience of every token and
    the prefix of every form action.
    """
    admin_config.values["public_url"] = ADMIN_URL

    app = start(monkeypatch, tmp_path)

    assert document_of(app, PRM_SUFFIX)["resource"] == f"{ADMIN_URL}{RESOURCE_SUFFIX}"


def test_a_deploy_variable_stays_in_force_when_nothing_is_stored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every installation that exists today: the variable is set and no form was saved."""
    app = start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: PUBLIC_URL})

    assert document_of(app, PRM_SUFFIX)["resource"] == f"{PUBLIC_URL}{RESOURCE_SUFFIX}"


def test_the_admin_value_wins_over_the_deploy_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The precedence rule of 05-01, applied: admin value, then variable, then default."""
    admin_config.values["public_url"] = ADMIN_URL

    app = start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: PUBLIC_URL})

    assert document_of(app, PRM_SUFFIX)["resource"] == f"{ADMIN_URL}{RESOURCE_SUFFIX}"


@pytest.mark.parametrize(
    "stored",
    [
        "not-an-address",
        "https://cloud.example.com/x#fragment",
        "https://a:b@cloud.example.com/x",
        # CR-01: this one used to pass the validation and then killed the next start.
        "http://cloud.example.com/exapps/mcp_connector",
        "http://localhost.example.com/x",
    ],
    ids=[
        "no scheme",
        "a fragment",
        "credentials in the address",
        "http on a host that is not loopback",
        "a host that merely contains a loopback word",
    ],
)
def test_an_unusable_admin_value_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig, stored: str
) -> None:
    """T-05-17: the validation sits in ``config_values`` and ``main`` never works around it.

    An address that would become a broken ``issuer`` is not a value, so the deploy environment
    of an existing installation keeps working exactly as it did before this plan.
    """
    admin_config.values["public_url"] = stored

    app = start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: PUBLIC_URL})

    assert document_of(app, PRM_SUFFIX)["resource"] == f"{PUBLIC_URL}{RESOURCE_SUFFIX}"


def test_an_installation_without_any_public_address_serves_and_says_where_to_set_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The deadlock this plan breaks (WR-09 revisited, 05-RESEARCH pitfall 2).

    Until now this was ``SystemExit(2)``. With it the app never became ``enabled``, so the
    ``enabled=1`` hook never registered the admin form, so there was no place an administrator
    could enter the missing address: a one click installation died on start and could not be
    finished. The promise "no silent misconfiguration" is now kept by this error line and by
    the setup state on the connections page, not by refusing to run.
    """
    with caplog.at_level("ERROR", logger="mcp_connector.entry_exapp"):
        app = start(monkeypatch, tmp_path)

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_PUBLIC_URL in messages
    assert strings.ADMIN_SETTINGS_PLACE in messages, "the line names where the value is set"
    assert "disable and enable" in messages.lower(), "and the step that makes it take effect"
    assert "no public address is stored in Nextcloud either" in messages, (
        "this is the empty case, and the line says exactly that"
    )
    default = f"{config.DEFAULT_PUBLIC_URL}{RESOURCE_SUFFIX}"
    assert document_of(app, PRM_SUFFIX)["resource"] == default, "and it serves the documents"


def test_a_stored_but_refused_address_is_not_reported_as_no_address_at_all(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    admin_config: AdminConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The deferred find of plan 05-14, measured there as line B of the run.

    Both cases end in the same setup state, and until now they ended in the same sentence:
    "no public address is stored in Nextcloud either". For an administrator who did store one
    and had it refused, that sentence is untrue, and it sends her looking for an empty field
    instead of at the value she typed. The two cases are told apart here, and the refused one
    still never carries the value into the log (T-05-03, T-05-21).
    """
    admin_config.values["public_url"] = UNUSABLE_URL

    with caplog.at_level("DEBUG"):
        app = start(monkeypatch, tmp_path)

    messages = " ".join(record.getMessage() for record in caplog.records)
    errors = " ".join(
        record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR
    )
    assert "no public address is stored in Nextcloud either" not in messages, (
        "an address was stored, it was only refused"
    )
    assert "refused" in errors, "the setup line says which of the two cases this is"
    assert config.ENV_PUBLIC_URL in errors
    assert strings.ADMIN_SETTINGS_PLACE in errors, "and where a usable one is entered"
    assert "disable and enable" in errors.lower()
    assert UNUSABLE_URL not in messages, "the value stays out of the log"
    assert "tls-is-missing.example.org" not in messages, "not even its host"
    default = f"{config.DEFAULT_PUBLIC_URL}{RESOURCE_SUFFIX}"
    assert document_of(app, PRM_SUFFIX)["resource"] == default, "and it serves the documents"


def test_a_refused_switch_does_not_make_the_missing_address_a_refused_one(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    admin_config: AdminConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The refusal is read per field: a typo in a checkbox says nothing about the address."""
    admin_config.values["oauth_dcr"] = "vielleicht"

    with caplog.at_level("DEBUG"):
        start(monkeypatch, tmp_path)

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "no public address is stored in Nextcloud either" in messages


def test_a_blank_public_url_is_the_same_setup_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A quoted empty value in a compose file is a typo, not a decision to use the default."""
    with caplog.at_level("ERROR", logger="mcp_connector.entry_exapp"):
        start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: "   "})

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_PUBLIC_URL in messages


def test_an_unreachable_nextcloud_does_not_stop_the_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """T-05-20: the read costs one attempt and can never be the reason a container dies."""
    admin_config.breaks()

    app = start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: PUBLIC_URL})

    assert document_of(app, PRM_SUFFIX)["resource"] == f"{PUBLIC_URL}{RESOURCE_SUFFIX}"


def test_an_admin_switch_reaches_the_client_policy_of_the_started_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The overlay is one environment for every reader, not only for the public address.

    ``client_policy`` reads the three AUTH-07 switches out of the same resolved environment,
    and the document is where that shows: with self registration off, the authorization server
    stops advertising a registration endpoint (D-35).
    """
    admin_config.values.update({"public_url": ADMIN_URL, "oauth_dcr": "0"})

    app = start(monkeypatch, tmp_path)

    assert "registration_endpoint" not in document_of(app, AS_METADATA_SUFFIX)


def test_the_shipped_state_still_advertises_the_registration_endpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The counter probe of the check above: without a stored switch nothing changes."""
    admin_config.values["public_url"] = ADMIN_URL

    app = start(monkeypatch, tmp_path)

    assert "registration_endpoint" in document_of(app, AS_METADATA_SUFFIX)


def test_the_cimd_admin_value_reaches_the_document_of_the_started_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """Finding B-1 of the v1.0 milestone audit, held where the switch becomes visible.

    ``NC_MCP_OAUTH_CIMD`` was a deploy variable, a manifest declaration and a documented
    sentence, and it was in no part of the admin value chain. An installation from the app
    store never receives a deploy variable (05-RESEARCH, pitfall 2), so on exactly the kind
    of installation this chain exists for, that switch could not be set at all. The document
    is where a client reads the answer, so it is where this check looks.
    """
    admin_config.values.update({"public_url": ADMIN_URL, "oauth_cimd": "0"})

    app = start(monkeypatch, tmp_path)

    document = document_of(app, AS_METADATA_SUFFIX)
    assert CIMD_FIELD not in document
    assert "registration_endpoint" in document, "and this switch closes nothing else"


def test_the_cimd_admin_value_wins_over_the_deploy_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The precedence rule of 05-01 for the fifth value: admin value, variable, default."""
    admin_config.values.update({"public_url": ADMIN_URL, "oauth_cimd": "0"})

    app = start(monkeypatch, tmp_path, env={registry.ENV_CIMD: "1"})

    assert CIMD_FIELD not in document_of(app, AS_METADATA_SUFFIX)


def test_an_unusable_cimd_admin_value_leaves_the_deploy_variable_in_force(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """A value that is neither on nor off is not a value, so it never becomes the default.

    The dangerous shape of a refusal is the one that falls back to the shipped state and
    quietly opens a way an administrator closed with a variable.
    """
    admin_config.values.update({"public_url": ADMIN_URL, "oauth_cimd": "vielleicht"})

    app = start(monkeypatch, tmp_path, env={registry.ENV_CIMD: "off"})

    assert CIMD_FIELD not in document_of(app, AS_METADATA_SUFFIX)


def test_a_stored_cimd_value_of_on_announces_the_way(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The happy half: a checkbox an administrator ticked reaches the document as well.

    Nextcloud stores a checkbox as a JSON boolean, which is the shape ``_as_text`` turns
    into a spelling the switch reader understands, so it is the shape this check stores.
    """
    admin_config.values.update({"public_url": ADMIN_URL})
    admin_config.values["oauth_cimd"] = "true"

    app = start(monkeypatch, tmp_path)

    assert document_of(app, AS_METADATA_SUFFIX)[CIMD_FIELD] is True


def test_a_stored_cimd_value_cannot_reopen_a_closed_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The locked decision of phase 6, now reachable from the form (W-9 is its copy).

    ``cimd_enabled`` is derived as "this switch AND the DCR switch", and the derivation is
    untouched by finding B-1: an administrator who ticks this box while self registration is
    off has closed both ways, and the document says so. This is the state the field
    description has to name in words, because a checkbox has no third position for it.
    """
    admin_config.values.update({"public_url": ADMIN_URL, "oauth_dcr": "0", "oauth_cimd": "1"})

    app = start(monkeypatch, tmp_path)

    document = document_of(app, AS_METADATA_SUFFIX)
    assert CIMD_FIELD not in document
    assert "registration_endpoint" not in document


def test_the_cimd_switch_reaches_the_document_of_the_built_application() -> None:
    """AUTH-08 through the wired application, not through a parameter (pitfall 5).

    The switch is read once, in ``build_exapp_app``, and the same policy object answers the
    document and ``provider.get_client``. So a deployment that switched the way off says
    nothing about it here, which is precisely the shape that lets a client fall back to
    dynamic registration: the specification offers that fallback only while the capability is
    absent, never when it is announced and then refused.
    """
    app = entry_exapp.build_exapp_app({**OAUTH_ENV, registry.ENV_CIMD: "off"})

    assert CIMD_FIELD not in document_of(app, AS_METADATA_SUFFIX)


def test_the_shipped_state_announces_the_metadata_document_way() -> None:
    """The counter probe: with nobody switching anything, the capability is announced."""
    document = document_of(entry_exapp.build_exapp_app(OAUTH_ENV), AS_METADATA_SUFFIX)

    assert document[CIMD_FIELD] is True


def test_a_closed_registration_closes_the_announcement_as_well() -> None:
    """The coupling of plan 06-03, measured where a client actually reads it.

    ``cimd_enabled`` is derived from both switches, so an administrator who closed self
    registration has closed both ways with one variable. If only the endpoint disappeared
    while the capability stayed, that administrator would have shut a door and left the other
    spelling of the same door open.
    """
    document = document_of(
        entry_exapp.build_exapp_app({**OAUTH_ENV, registry.ENV_DCR: "off"}), AS_METADATA_SUFFIX
    )

    assert CIMD_FIELD not in document
    assert "registration_endpoint" not in document


def test_the_two_switches_are_read_from_one_policy_per_application() -> None:
    """One policy per application, and the document is what proves the wire exists.

    A second ``client_policy`` call for the document would be a second answer to one
    question, and the two could then disagree after an administrator changed a value: the
    document is the half a client believes, and it is the half that cannot refuse.
    """
    both_off = document_of(
        entry_exapp.build_exapp_app(
            {**OAUTH_ENV, registry.ENV_CIMD: "off", registry.ENV_DCR: "off"}
        ),
        AS_METADATA_SUFFIX,
    )
    cimd_only = document_of(
        entry_exapp.build_exapp_app({**OAUTH_ENV, registry.ENV_DCR: "off"}), AS_METADATA_SUFFIX
    )

    assert CIMD_FIELD not in both_off
    assert "registration_endpoint" not in both_off
    assert both_off == cimd_only


def test_the_admin_values_are_read_once_per_start_and_never_per_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The decision of this plan, held by a check: resolved once, at the start (D-20).

    A per request read would be a second Nextcloud round trip on every request (SC 5 of phase
    3) or a mutable module cache, which D-20 forbids with two named exceptions. The price is
    the reactivation step, and it is named in three places instead of hidden.
    """
    admin_config.values["public_url"] = ADMIN_URL

    app = start(monkeypatch, tmp_path)
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get(PRM_SUFFIX).status_code == 200

    assert admin_config.route.call_count == 1


def test_nothing_is_read_outside_the_exapp_mode(
    monkeypatch: pytest.MonkeyPatch, admin_config: AdminConfig
) -> None:
    """Without the AppAPI variables there is no channel to read the values over."""
    for name in (*EXAPP_ENV, config.ENV_STATIC_BEARER, config.ENV_APP_PASSWORD):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()

    assert excinfo.value.code == 2
    assert admin_config.route.call_count == 0


def test_the_start_names_the_keys_it_took_from_nextcloud_and_never_their_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    admin_config: AdminConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-05-21: an administrator has to see which source won, and a log is not a place for
    an address, a client id or anything else that arrived over HTTP."""
    admin_config.values.update(
        {"public_url": ADMIN_URL, "oauth_allowed_clients": "https://claude.example/callback"}
    )

    with caplog.at_level("INFO", logger="mcp_connector.entry_exapp"):
        start(monkeypatch, tmp_path)

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_PUBLIC_URL in messages
    assert registry.ENV_ALLOWED_CLIENTS in messages
    assert ADMIN_URL not in messages
    assert "claude.example" not in messages


# --- the one key that leaves the resolved mapping again (TALK-04, way A of 09-RESEARCH) --
#
# Four cases, and they exist so the line in ``main`` does not disappear in the next refactor.
# A tool has no resolved mapping in its hand, so the switch of TALK-04 is only readable at
# all if the resolved value is part of the environment of this process. What that value is
# after the start is therefore the contract, not an implementation detail.


def test_a_stored_talk_switch_of_off_reaches_the_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """Layer 3 of success criterion 5, as far as this plan can prove it: the value an
    administrator unticked in Nextcloud is what ``config.talk_send_enabled`` answers on."""
    admin_config.values["talk_send"] = "0"

    start(monkeypatch, tmp_path)

    assert os.environ[config.ENV_TALK_SEND] == config_values.SWITCH_OFF
    assert config.talk_send_enabled() is False


def test_a_stored_talk_switch_of_on_reaches_the_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The other direction, so True is never just the absence of the write."""
    admin_config.values["talk_send"] = "1"

    start(monkeypatch, tmp_path)

    assert os.environ[config.ENV_TALK_SEND] == config_values.SWITCH_ON
    assert config.talk_send_enabled() is True


def test_a_start_without_a_stored_talk_switch_leaves_the_variable_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exactly one key travels, and only when it is in the overlay: an installation that
    configured nothing must not gain a variable it never set (TALK-04 ships on)."""
    start(monkeypatch, tmp_path)

    assert config.ENV_TALK_SEND not in os.environ
    assert config.talk_send_enabled() is True


def test_a_stored_talk_switch_wins_over_the_deploy_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The precedence rule of 05-01 for this key too: admin value, then variable, then code.

    ``_resolved_env`` builds that order, and the write below carries it into the environment,
    so the environment a tool reads is the resolved one and not the deployed one.
    """
    admin_config.values["talk_send"] = "0"

    start(monkeypatch, tmp_path, env={config.ENV_TALK_SEND: "1"})

    assert os.environ[config.ENV_TALK_SEND] == config_values.SWITCH_OFF
    assert config.talk_send_enabled() is False


def test_the_entry_point_writes_exactly_one_key_into_the_process_environment() -> None:
    """The exception of D-20 stays one exception, and it keeps its reasoning.

    Constructive rather than documented: a second write, or a write of the whole overlay,
    fails here, and so does a refactor that keeps the line but drops the comment block that
    explains why it contradicts the comment above it (A7).
    """
    source = Path(entry_exapp.__file__).read_text(encoding="utf-8")
    writes = re.findall(r"os\.environ\[[^\]]+\]\s*=", source)

    assert writes == ["os.environ[config.ENV_TALK_SEND] ="]

    lines = source.splitlines()
    index = next(
        number for number, line in enumerate(lines) if re.search(r"os\.environ\[[^\]]+\]\s*=", line)
    )
    reasoning = [line for line in lines[max(0, index - 14) : index] if line.strip().startswith("#")]
    assert len(reasoning) >= 4


def test_the_write_happens_before_the_application_is_built() -> None:
    """A switch that is exported after the first socket has not switched anything off."""
    source = Path(entry_exapp.__file__).read_text(encoding="utf-8")

    export = source.index("os.environ[config.ENV_TALK_SEND]")
    resolved = source.index("resolved, refused = _resolved_env()")
    served = source.index("uvicorn.run(")

    assert resolved < export < served


@pytest.mark.anyio
async def test_the_client_of_the_start_time_read_is_hardened_like_the_shared_one() -> None:
    """Why a client of its own: the loop of this read is closed again right afterwards.

    ``shared_client`` binds a connection pool to the event loop it was first used in, and the
    loop ``asyncio.run`` opens for the start time read is gone before uvicorn opens its own.
    A pool left behind there is unusable and its sockets are never closed. The four properties
    stay the ones of the shared client, and this is what holds them equal.
    """
    startup = entry_exapp._startup_client()
    shared = nc_http.shared_client()

    assert startup is not shared
    assert startup.follow_redirects is False
    assert startup.timeout == shared.timeout
    assert isinstance(startup.cookies.jar, nc_http.NoCookieJar)
    assert startup.headers["user-agent"] == shared.headers["user-agent"]
    await startup.aclose()


# --- an unusable public address is survived, not died of (CR-01, gap 1 of 05-VERIFICATION) --

#: The address of the finding: it passes ``config.public_url`` unchanged, and the SDK refuses
#: it as an issuer. Before this plan that refusal was ``SystemExit(2)`` on every start, which
#: is a container restart loop, an app that never becomes ``enabled`` again, and with it an
#: admin form that AppAPI no longer serves. The wrong value was then correctable by hand in
#: ``oc_appconfig_ex`` and nowhere else.
#: Deliberately not the host of the example address in the hint of ``provider._HINT_ISSUER``:
#: this one appears in a log record only if the value itself was logged.
UNUSABLE_URL = "http://tls-is-missing.example.org/exapps/mcp_connector"


class RefusingBuild:
    """A ``build_exapp_app`` that refuses the issuer as often as it is told to.

    The refusal is the one ``oauth/provider.auth_routes`` raises when the SDK rejects the
    issuer, so no second wording of the same failure is invented here. ``seen`` is what makes
    "exactly one rescue" and "the second build ran without the address" assertable.
    """

    def __init__(self, failures: int) -> None:
        self._left = failures
        self.seen: list[dict[str, str]] = []

    def __call__(self, env: Mapping[str, str] | None = None) -> Starlette:
        self.seen.append(dict(env or {}))
        if self._left > 0:
            self._left -= 1
            raise IssuerRefused(
                message=f"{config.ENV_PUBLIC_URL} is not a usable issuer: Issuer URL must be HTTPS",
                hint="RFC 8414 requires https for an issuer, with the loopback exception.",
            )
        return Starlette()


class FailingBuild:
    """A ``build_exapp_app`` whose failure is not the issuer, and never becomes one."""

    def __init__(self) -> None:
        self.seen: list[dict[str, str]] = []

    def __call__(self, env: Mapping[str, str] | None = None) -> Starlette:
        self.seen.append(dict(env or {}))
        raise ToolError(
            message="the persistent volume of this app is not writable",
            hint="Check the volume of the deploy daemon.",
        )


def test_a_build_failure_that_is_not_the_issuer_is_not_rescued(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    admin_config: AdminConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """IN-06: the rescue is for the issuer refusal and for nothing that merely resembles it.

    ``except ToolError`` was true about today and an assumption about tomorrow: the issuer
    refusal of ``provider.auth_routes`` is the only ``ToolError`` raised while this
    application is built, so any second source would have been logged as an address
    problem, would have had the (possibly perfectly good) address dropped, and would have
    ended in a second build with a confusing double message. The refusal carries its own
    type now, and this test is the second source arriving.
    """
    admin_config.values["public_url"] = ADMIN_URL
    build = FailingBuild()
    monkeypatch.setattr(entry_exapp, "build_exapp_app", build)
    deployed(monkeypatch, tmp_path)

    with (
        caplog.at_level("ERROR", logger="mcp_connector.entry_exapp"),
        pytest.raises(SystemExit) as excinfo,
    ):
        entry_exapp.main()

    assert excinfo.value.code == 2
    assert len(build.seen) == 1, "no second build, because dropping the address fixes nothing"
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "not writable" in messages, "the failure is reported as what it is"
    assert strings.ADMIN_SETTINGS_PLACE not in messages, "and never as an address problem"


def test_the_issuer_refusal_of_the_provider_is_the_type_the_rescue_catches() -> None:
    """The other half of IN-06: the marker is on the raise site, not only in the test.

    A rescue narrowed to a type that nothing raises would be a rescue that never runs, and
    CR-01 would be open again with nothing to show for it.
    """
    stub = SimpleNamespace(policy=SimpleNamespace(dcr_enabled=True))

    with pytest.raises(IssuerRefused):
        auth_routes(
            {**EXAPP_ENV, config.ENV_PUBLIC_URL: "http://tls-is-missing.example.org"},
            provider=cast(Any, stub),
        )


def test_one_issuer_refusal_drops_the_address_instead_of_the_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """The rescue half of CR-01: the process keeps running and the form stays reachable."""
    admin_config.values["public_url"] = ADMIN_URL
    build = RefusingBuild(failures=1)
    monkeypatch.setattr(entry_exapp, "build_exapp_app", build)

    app = start(monkeypatch, tmp_path)

    assert isinstance(app, Starlette), "main reached uvicorn instead of ending the process"
    assert len(build.seen) == 2, "exactly one rescue attempt, never a loop"
    assert build.seen[0][config.ENV_PUBLIC_URL] == ADMIN_URL
    assert config.ENV_PUBLIC_URL not in build.seen[1], "the address that broke was not dropped"


def test_a_second_refusal_ends_the_start_with_exit_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, admin_config: AdminConfig
) -> None:
    """One rescue and no more: a build that fails without the address is a real defect."""
    admin_config.values["public_url"] = ADMIN_URL
    build = RefusingBuild(failures=2)
    monkeypatch.setattr(entry_exapp, "build_exapp_app", build)
    deployed(monkeypatch, tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()

    assert excinfo.value.code == 2
    assert len(build.seen) == 2


def test_an_unusable_address_from_the_deploy_environment_takes_the_same_way(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The prevention half cannot reach this one: nothing validates a deploy variable.

    Nothing is stubbed here either: the real ``build_exapp_app`` runs, the real SDK refuses
    the issuer, and what the started application answers is the proof that the rescue is
    wired rather than described.
    """
    app = start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: UNUSABLE_URL})

    default = f"{config.DEFAULT_PUBLIC_URL}{RESOURCE_SUFFIX}"
    assert document_of(app, PRM_SUFFIX)["resource"] == default


def test_the_rescued_start_shows_the_setup_state_on_the_connections_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The link to plan 05-04: with the default in force the page says what is missing.

    That is what keeps the promise "no silent misconfiguration" after the rescue: the process
    lives, and it says so where the administrator and the user both look.
    """
    app = start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: UNUSABLE_URL})

    with TestClient(app) as client:
        page = client.get(ui_connections.CONNECTIONS_PATH, headers=appapi_headers(user="alice"))

    assert page.status_code == 200
    assert strings.SETUP_PUBLIC_URL_TITLE in page.text


def test_the_rescue_line_names_the_rule_and_the_place_but_never_the_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T-05-21 and T-05-43: the value may have come out of the form and travelled over HTTP."""
    with caplog.at_level("ERROR", logger="mcp_connector.entry_exapp"):
        start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: UNUSABLE_URL})

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_PUBLIC_URL in messages
    assert "https" in messages, "the line names the rule the value broke"
    assert strings.ADMIN_SETTINGS_PLACE in messages, "and where the value is corrected"
    assert f"app_api:app:disable {APP_ID}" in messages
    assert f"app_api:app:enable {APP_ID}" in messages
    assert UNUSABLE_URL not in messages
    assert "tls-is-missing.example.org" not in messages, "not even the host of the value"


def test_the_rescue_line_names_the_deploy_variable_as_a_source_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """IN-02: the address that broke did not have to come out of the admin form.

    After the prevention half of CR-01 an unusable form value never reaches the build at
    all, so the case this branch really sees is the one this test builds: a deploy variable.
    A line that sends the administrator to the form to correct "the stored value" sends her
    to an empty field, and she looks for a value that is not there. Both sources are named,
    with the rule between them, so the sentence is true whichever one it was.
    """
    with caplog.at_level("ERROR", logger="mcp_connector.entry_exapp"):
        start(monkeypatch, tmp_path, env={config.ENV_PUBLIC_URL: UNUSABLE_URL})

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_PUBLIC_URL in messages, "the deploy variable is a place to correct it"
    assert strings.ADMIN_SETTINGS_PLACE in messages, "and so is the form"
    assert "wins over" in messages, "and which of the two wins is said, not guessed"
    assert "the stored value is kept" not in messages.lower(), (
        "no claim that a value is waiting in the form, because there may be none"
    )


def test_the_rescue_line_says_the_same_two_places_for_a_stored_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    admin_config: AdminConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The counter probe of IN-02: one line for both sources, never a wrong one for either.

    Here the address really did come out of the form (the build is stubbed, because the
    prevention half refuses such a value before it can reach the real one). Nothing is
    deleted in Nextcloud either way (T-05-44), so what the administrator finds in the form
    is still what she typed.
    """
    admin_config.values["public_url"] = ADMIN_URL
    monkeypatch.setattr(entry_exapp, "build_exapp_app", RefusingBuild(failures=1))

    with caplog.at_level("ERROR", logger="mcp_connector.entry_exapp"):
        start(monkeypatch, tmp_path)

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert config.ENV_PUBLIC_URL in messages
    assert strings.ADMIN_SETTINGS_PLACE in messages
    assert "wins over" in messages
    assert ADMIN_URL not in messages, "the value itself stays out of the log (T-05-21)"


def test_a_missing_volume_stops_the_start_before_anything_is_built(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The counter probe: the rescue is for the issuer and for nothing else (T-03-15)."""
    build = RefusingBuild(failures=0)
    monkeypatch.setattr(entry_exapp, "build_exapp_app", build)
    deployed(monkeypatch, tmp_path)
    monkeypatch.delenv(config.ENV_APP_PERSISTENT_STORAGE, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()

    assert excinfo.value.code == 2
    assert build.seen == [], "a broken volume must never reach the build"


@pytest.mark.parametrize("conflicting", [config.ENV_STATIC_BEARER, config.ENV_APP_PASSWORD])
def test_a_second_credential_channel_is_still_exit_two_and_builds_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, conflicting: str
) -> None:
    """D-27 is untouched by the rescue: two ways to authenticate stay a refusal to start."""
    build = RefusingBuild(failures=0)
    monkeypatch.setattr(entry_exapp, "build_exapp_app", build)
    deployed(monkeypatch, tmp_path)
    monkeypatch.setenv(conflicting, "something")

    with pytest.raises(SystemExit) as excinfo:
        entry_exapp.main()

    assert excinfo.value.code == 2
    assert build.seen == []


# --- the end to end guard of phase 4: the hand on the switch, and the refusal ------


def a_connected_account(
    tmp_path: Path, *, nc_user: str = "alice", token: str = CONNECTED_TOKEN
) -> store.OAuthStore:
    """One registered client and one live OAuth connection of that account, in the store.

    Written straight into the file the application opens, because what this guard is about
    happens after the connection exists: everything from the sign in to the consent has its
    own tests, and repeating the whole dance here would test those again instead of this.
    """
    subject = store.OAuthStore(tmp_path / store.STORE_FILENAME, bytes(range(32)))
    registration = OAuthClientInformationFull.model_validate(
        {
            "client_id": CONNECTED_CLIENT_ID,
            "client_name": "Claude",
            "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": TOOL_SCOPE,
        }
    ).model_dump_json(exclude={"client_secret"})
    asyncio.run(subject.save_client(CONNECTED_CLIENT_ID, metadata_json=registration, allowed=True))
    asyncio.run(subject.touch_client(CONNECTED_CLIENT_ID))
    asyncio.run(
        subject.create_authorization(
            f"authorization-of-{nc_user}",
            client_id=CONNECTED_CLIENT_ID,
            nc_user=nc_user,
            app_password="aaaaa-bbbbb-ccccc-ddddd-eeeee",
            scopes=TOOL_SCOPE,
            resource=f"{PUBLIC_URL}{RESOURCE_SUFFIX}",
        )
    )
    asyncio.run(
        subject.create_access_token(
            token,
            auth_id=f"authorization-of-{nc_user}",
            family_id=f"family-of-{nc_user}",
            scopes=TOOL_SCOPE,
            resource=f"{PUBLIC_URL}{RESOURCE_SUFFIX}",
        )
    )
    return subject


def switch_form(subject: store.OAuthStore, action: str, nc_user: str = "alice") -> dict[str, str]:
    """The form the page renders for that account, with the anti forgery value it carries."""
    return {
        ui_connections.ACTION_FIELD: action,
        ui_connections.CONFIRM_PARAM: subject.form_token(
            f"{connections.SWITCH_HANDLE}{nc_user}", purpose=crypto.PURPOSE_SWITCH
        ),
    }


def bearer_call(client: TestClient, token: str) -> Any:
    """One MCP request of a connected client: the OAuth branch of the boundary."""
    return client.post(
        "/mcp",
        json=INITIALIZE,
        headers={**MCP_HEADERS, **appapi_headers(user=""), "Authorization": f"Bearer {token}"},
    )


def test_the_switch_on_the_page_refuses_the_very_next_call_of_that_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The end to end guard of this phase (SC 1): a hand on the switch, and the refusal.

    Everything is the wired application: the user posts the pause form of ``/connections``
    under their own AppAPI identity, and the very next MCP call of their assistant, with a
    token that has not changed, is R1. A test that only checked the store round trip would
    stay green with no gate in the boundary at all, which is exactly pitfall 1.
    """
    env, _ = with_a_local_store(OAUTH_ENV, tmp_path, monkeypatch)
    subject = a_connected_account(tmp_path)

    with TestClient(entry_exapp.build_exapp_app(env)) as client:
        before = bearer_call(client, CONNECTED_TOKEN)
        paused = client.post(
            ui_connections.CONNECTIONS_PATH,
            data=switch_form(subject, ui_connections.ACTION_PAUSE),
            headers=appapi_headers(user="alice"),
        )
        refused = bearer_call(client, CONNECTED_TOKEN)
        resumed = client.post(
            ui_connections.CONNECTIONS_PATH,
            data=switch_form(subject, ui_connections.ACTION_RESUME),
            headers=appapi_headers(user="alice"),
        )
        after = bearer_call(client, CONNECTED_TOKEN)

    assert before.status_code == 200, "the connection works before anything is switched"
    assert paused.status_code == 200
    assert strings.CONNECTIONS_PAUSED_TITLE in paused.text, "the page shows what it just did"
    assert refused.status_code == 403
    assert json.loads(refused.text) == {
        "error": "access_disabled",
        "error_description": strings.ACCESS_DISABLED_DESCRIPTION,
    }
    assert "www-authenticate" not in {key.lower() for key in refused.headers}
    assert refused.headers["cache-control"] == "no-store"
    assert resumed.status_code == 200
    assert strings.CONNECTIONS_PAUSED_TITLE not in resumed.text
    assert after.status_code == 200, "turning it back on needs no new sign in (D-46)"


def test_the_switch_of_one_account_leaves_the_other_accounts_serving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative probe of the same chain: a pause is one account's decision, not a mode."""
    env, _ = with_a_local_store(OAUTH_ENV, tmp_path, monkeypatch)
    subject = a_connected_account(tmp_path)

    with TestClient(entry_exapp.build_exapp_app(env)) as client:
        client.post(
            ui_connections.CONNECTIONS_PATH,
            data=switch_form(subject, ui_connections.ACTION_PAUSE),
            headers=appapi_headers(user="alice"),
        )
        other = client.post(
            "/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **appapi_headers(user="bob")}
        )

    assert other.status_code == 200


def test_the_page_of_this_deployment_is_wired_to_the_store_of_this_deployment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One store, one truth: the page lists the connection the token verifier knows about."""
    env, _ = with_a_local_store(OAUTH_ENV, tmp_path, monkeypatch)
    a_connected_account(tmp_path)

    with TestClient(entry_exapp.build_exapp_app(env)) as client:
        listed = client.get(ui_connections.CONNECTIONS_PATH, headers=appapi_headers(user="alice"))

    assert listed.status_code == 200
    assert "Claude" in listed.text
    assert ui_connections.CONNECTIONS_PATH in paths(entry_exapp.build_exapp_app(env))


# --- the switch of D-14 and the switch row of D-15 --------------------------------


def audit_rows(tmp_path: Path) -> list[dict[str, Any]]:
    """Every row of the audit store of a deployment, read with a connection of our own.

    Past the store API on purpose, the same way ``test_audit_record.py`` reads its rows: what
    is asserted here is what really landed in the file, not what an object says about it.
    """
    path = tmp_path / audit_store_module.AUDIT_FILENAME
    if not path.exists():
        return []
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM entries ORDER BY seq")]
    finally:
        connection.close()


def recorder_of(app: Starlette) -> object | None:
    """The recorder the built application handed to its transport boundary, or ``None``.

    Reaches into the wrapper because that is exactly the wire under test: "is a recorder
    attached" is not visible from outside, and a check that only grepped the source for
    ``audit_recorder=`` would pass on an application that never built one.
    """
    for route in app.router.routes:
        if isinstance(route, Route) and route.path == "/mcp":
            return getattr(route.app, "_audit_recorder", None)
    raise AssertionError("the built application has no /mcp route")


def test_without_the_switch_no_recorder_reaches_the_boundary(tmp_path: Path) -> None:
    """D-14, and the state every installation ships in: nothing is recorded, nothing exists.

    Two halves and both matter. No recorder means the boundary deposits nothing and the
    recording path in ``graceful`` returns before it writes. And no file: an installation that
    never switched the log on has no ``audit.sqlite3``, not even an empty one with a schema
    in it, because a file that exists says something happened.
    """
    env = {**EXAPP_ENV, config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}

    app = entry_exapp.build_exapp_app(env)

    assert recorder_of(app) is None
    assert not (tmp_path / audit_store_module.AUDIT_FILENAME).exists()
    assert audit_rows(tmp_path) == []


def test_with_the_switch_on_the_boundary_gets_a_recorder(tmp_path: Path) -> None:
    """The other direction of the same line, and the whole of what D-14 asks for."""
    env = {
        **EXAPP_ENV,
        config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path),
        config.ENV_AUDIT_LOG: "on",
    }

    recorder = recorder_of(entry_exapp.build_exapp_app(env))

    assert isinstance(recorder, audit_record.Recorder)
    assert recorder.retention_days == 180
    assert recorder.size_limit == 100_000_000


def test_the_recorder_carries_the_mapping_the_application_was_built_with(
    tmp_path: Path,
) -> None:
    """The one check that holds the account check of D-12 (plan 18-09) wired to reality.

    ``Recorder.env`` is what that check will call Nextcloud with. Built from ``os.environ``
    instead of from the resolved mapping it would carry different values at exactly the moment
    it matters: an installation from the app store gets no deploy variable at all, so
    everything an administrator set lives only in the mapping ``_resolved_env`` produced.

    Asserted against the mapping that was handed in, and explicitly not against ``None`` and
    not against ``os.environ``: a grep for ``env=env`` in the source would pass on all three.
    """
    env = {
        **EXAPP_ENV,
        config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path),
        config.ENV_AUDIT_LOG: "on",
        config.ENV_PUBLIC_URL: PUBLIC_URL,
    }

    recorder = recorder_of(entry_exapp.build_exapp_app(env))

    assert isinstance(recorder, audit_record.Recorder)
    assert recorder.env == env
    assert recorder.env is not None
    assert recorder.env != dict(os.environ)


def test_the_first_start_with_the_log_on_writes_one_switch_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-15 and D-16: the change of state leaves a trace, and it names no administrator.

    The start is the moment because it is the only one this app can observe: an admin value
    takes effect after a disable and enable cycle, which stops and starts this container, and
    AppAPI's ``SetValueListener`` tells the app nothing when a value is stored.
    """
    start(monkeypatch, tmp_path, env={config.ENV_AUDIT_LOG: "on"})

    rows = audit_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["kind"] == "switch"
    assert rows[0]["chain"] == audit_store_module.CHAIN_INSTANCE
    assert rows[0]["outcome"] == "on"
    assert rows[0]["actor"] == audit_store_module.ACTOR_UNKNOWN
    assert rows[0]["actor"] == "unknown"
    assert rows[0]["nc_user"] is None, "a switch belongs to the instance and to no account"


def test_a_second_start_in_the_same_state_writes_no_second_switch_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A restart is not a switching. Only a state that differs from the recorded one is one.

    Without this the instance chain would grow one row per container restart, and the rows
    that really mean something, the two directions of D-15, would be lost among them.
    """
    start(monkeypatch, tmp_path, env={config.ENV_AUDIT_LOG: "on"})
    first = audit_rows(tmp_path)

    start(monkeypatch, tmp_path, env={config.ENV_AUDIT_LOG: "on"})

    assert len(first) == 1
    assert audit_rows(tmp_path) == first


def test_switching_the_log_off_again_is_recorded_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The other direction of D-15, and the reason the record is worth having at all.

    Without it the log could be switched off, something could happen and it could be switched
    on again, and the gap would have no name.
    """
    start(monkeypatch, tmp_path, env={config.ENV_AUDIT_LOG: "on"})

    start(monkeypatch, tmp_path, env={config.ENV_AUDIT_LOG: "off"})

    rows = audit_rows(tmp_path)
    assert [row["outcome"] for row in rows] == ["on", "off"]
    assert [row["kind"] for row in rows] == ["switch", "switch"]


def test_a_store_that_cannot_be_written_does_not_cost_the_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """D-13 at the start as well: a broken store must never keep this container from serving.

    The line names the type of the failure and nothing else, because the message of a store
    error carries the path of the file (T-18-10).
    """

    async def explode(env: Mapping[str, str]) -> None:
        del env
        raise OSError("no space left on device: /var/lib/mcp_connector/audit.sqlite3")

    monkeypatch.setattr(entry_exapp, "_audit_startup", explode)

    with caplog.at_level(logging.ERROR, logger="mcp_connector.entry_exapp"):
        app = start(monkeypatch, tmp_path, env={config.ENV_AUDIT_LOG: "on"})

    assert isinstance(app, Starlette), "the application is built whatever the audit log does"
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "OSError" in logged
    assert "no space left" not in logged
    assert "audit.sqlite3" not in logged


def test_a_switched_off_store_still_loses_its_expired_rows_on_a_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T-18-05: the one moment left to clean up a log that has no write path any more.

    The expiry of D-11 rides on the write path, every nth row. Switch the log off and that
    path is gone, so without this call the rows of an installation that stopped recording
    would sit out their retention window and stay forever. The row below is older than the
    window, the log is off, and the start takes it all the same and leaves the marker of D-10
    behind, so the gap is an explained one and not a break.
    """
    path = tmp_path / audit_store_module.AUDIT_FILENAME
    old = audit_store_module.AuditStore(path)
    long_ago = int(time.time()) - 400 * 24 * 60 * 60
    asyncio.run(
        old.append(
            audit_store_module.Entry(
                chain=audit_store_module.user_chain("alice"),
                at=long_ago,
                nc_user="alice",
                tool="files_list",
                outcome=audit_store_module.OUTCOME_OK,
            )
        )
    )
    assert [row["nc_user"] for row in audit_rows(tmp_path)] == ["alice"]

    start(monkeypatch, tmp_path, env={config.ENV_AUDIT_LOG: "off"})

    rows = audit_rows(tmp_path)
    assert [row["nc_user"] for row in rows] == [None], "the expired call is gone"
    assert rows[0]["kind"] == audit_store_module.KIND_TOMBSTONE
    assert rows[0]["chain"] == audit_store_module.CHAIN_INSTANCE

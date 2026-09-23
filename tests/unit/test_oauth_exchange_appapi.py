"""The account source of the ExApp operation (MAP-02, CRED-01): existence fail closed.

``oauth/exchange_appapi.py`` is the implementation of the ``ExchangeAccounts`` protocol the
ExApp deployment hands into the chain. Two properties carry this file. First the reversed
asymmetry: ``audit/accounts.existing_users`` answers ``None`` for "unknown, so keep every
chain", and this source reads the very same answer as "unknown, so refuse the identity".
Second the cost brake: the account list of an instance is ten thousand identifiers on a
large deployment, so it is fetched once per TTL and never once per tool call, with a single
flight for concurrent callers and a grace period after a failure.

No network anywhere in the unit half: the list source is a counting stand-in and the clock
is a hand clock, so every freshness rule is measured against numbers rather than sleeps.
"""

import asyncio
import base64
import inspect
import json
import logging
import time
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from mcp.server.auth.provider import AccessToken
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config, deps, entry_exapp
from mcp_connector.audit import accounts
from mcp_connector.exapp.middleware import RequireAppApi
from mcp_connector.nextcloud.http import shared_client
from mcp_connector.oauth import chain, exchange_accounts, exchange_appapi
from mcp_connector.oauth import store as oauth_store_module
from mcp_connector.oauth.metadata import RESOURCE_SUFFIX
from mcp_connector.oauth.verifier import CREDENTIAL_IMPERSONATE, OAuthIdentity

AZP = "f13-orchestrator"
MAPPED = "f13-account-7"

CLAIMS: dict[str, Any] = {"azp": AZP, "sub": MAPPED}


class HandClock:
    """A monotonic clock the test advances by hand: freshness is arithmetic, not sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CountingUsers:
    """The account list as far as the source may see it: what it was asked, how often."""

    def __init__(self, answer: frozenset[str] | None) -> None:
        self.answer = answer
        self.calls = 0
        self.environments: list[Mapping[str, str] | None] = []

    async def __call__(self, env: Mapping[str, str] | None = None) -> frozenset[str] | None:
        self.calls += 1
        self.environments.append(env)
        # One yield to the loop, so two concurrent callers really overlap on the fetch.
        await asyncio.sleep(0)
        return self.answer


def source(
    answer: frozenset[str] | None = frozenset({MAPPED}),
    *,
    clock: HandClock | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[exchange_appapi.AppApiAccounts, CountingUsers, HandClock]:
    users = CountingUsers(answer)
    hand = clock if clock is not None else HandClock()
    return exchange_appapi.AppApiAccounts(env=env, users=users, clock=hand), users, hand


# --- the identity of a mapped account --------------------------------------------------------


@pytest.mark.anyio
async def test_a_known_principal_becomes_the_impersonation_identity() -> None:
    """The one positive answer of this source, field by field.

    ``nc_user`` is the principal itself and never a second, guessed name: the AppAPI header
    takes the user id, and the user id is the principal of this project. The password and the
    stored authorization are empty because neither exists on this way.
    """
    subject, users, _ = source()

    identity = await subject.identity_for(MAPPED, CLAIMS)

    assert identity is not None
    assert identity.principal == MAPPED
    assert identity.nc_user == MAPPED
    assert identity.app_password == ""
    assert identity.auth_id == ""
    assert identity.client_id == exchange_accounts.EXCHANGE_CLIENT_ID
    assert identity.client_name == exchange_accounts.acting_party(CLAIMS)
    assert identity.credential == CREDENTIAL_IMPERSONATE
    assert identity.revoked is False
    assert users.calls == 1


@pytest.mark.anyio
async def test_a_principal_the_list_does_not_name_is_refused() -> None:
    """MAP-02: a claim cannot invent an account; not in the list means not acting here."""
    subject, _, _ = source(frozenset({"somebody-else"}))

    assert await subject.identity_for(MAPPED, CLAIMS) is None


@pytest.mark.anyio
async def test_an_unknown_account_list_is_a_refusal() -> None:
    """The reversed asymmetry: the ``None`` that keeps every audit chain refuses here."""
    subject, _, _ = source(None)

    assert await subject.identity_for(MAPPED, CLAIMS) is None


@pytest.mark.anyio
async def test_an_empty_set_from_the_source_is_a_refusal() -> None:
    """``existing_users`` never answers an empty set, but a refusal must not depend on that."""
    subject, _, _ = source(frozenset())

    assert await subject.identity_for(MAPPED, CLAIMS) is None


@pytest.mark.anyio
async def test_an_empty_principal_is_refused_without_a_fetch() -> None:
    """An empty user id is the app context without a user; it never even costs a call."""
    subject, users, _ = source()

    assert await subject.identity_for("", CLAIMS) is None
    assert users.calls == 0


# --- the cost brake: one cache, one flight, one grace period ---------------------------------


@pytest.mark.anyio
async def test_two_concurrent_calls_with_an_empty_cache_cost_one_fetch() -> None:
    """Single flight: whoever waited takes the outcome of the fetch that just happened."""
    subject, users, _ = source()

    first, second = await asyncio.gather(
        subject.identity_for(MAPPED, CLAIMS), subject.identity_for(MAPPED, CLAIMS)
    )

    assert first is not None
    assert second is not None
    assert users.calls == 1


@pytest.mark.anyio
async def test_a_second_call_within_the_ttl_costs_no_fetch_and_after_it_one() -> None:
    """The cache with expiry: fresh answers are free, a stale cache pays one fetch."""
    subject, users, clock = source()

    assert await subject.identity_for(MAPPED, CLAIMS) is not None
    clock.advance(exchange_appapi.ACCOUNT_CACHE_TTL - 1)
    assert await subject.identity_for(MAPPED, CLAIMS) is not None
    assert users.calls == 1

    clock.advance(2)
    assert await subject.identity_for(MAPPED, CLAIMS) is not None
    assert users.calls == 2


@pytest.mark.anyio
async def test_after_a_failure_the_grace_period_answers_none_without_a_fetch() -> None:
    """A provider outage must not turn every incoming call into an outgoing fetch."""
    subject, users, clock = source(None)

    assert await subject.identity_for(MAPPED, CLAIMS) is None
    clock.advance(exchange_appapi.ACCOUNT_FAILURE_RETRY_SECONDS - 1)
    assert await subject.identity_for(MAPPED, CLAIMS) is None
    assert users.calls == 1, "inside the grace period the refusal is free"

    clock.advance(2)
    users.answer = frozenset({MAPPED})
    assert await subject.identity_for(MAPPED, CLAIMS) is not None
    assert users.calls == 2, "after the grace period the next call pays for a fetch"


@pytest.mark.anyio
async def test_the_failure_stamp_is_set_before_the_outgoing_fetch() -> None:
    """A slow server must not stretch the grace window it caused.

    The list source advances the clock past the whole retry window while it is in flight
    and then fails. If the stamp were set after the answer, the very next call would sit
    inside a grace period the slow answer itself extended; set before the fetch, the window
    has already run out and the next call fetches again.
    """
    clock = HandClock()

    class SlowFailingUsers(CountingUsers):
        async def __call__(self, env: Mapping[str, str] | None = None) -> frozenset[str] | None:
            clock.advance(exchange_appapi.ACCOUNT_FAILURE_RETRY_SECONDS + 1)
            return await super().__call__(env)

    users = SlowFailingUsers(None)
    subject = exchange_appapi.AppApiAccounts(users=users, clock=clock)

    assert await subject.identity_for(MAPPED, CLAIMS) is None
    assert await subject.identity_for(MAPPED, CLAIMS) is None
    assert users.calls == 2


@pytest.mark.anyio
async def test_a_failure_is_never_cached_as_an_empty_account_list() -> None:
    """A refusal is a moment, not a truth: after the grace period the account acts again."""
    subject, users, clock = source(None)

    assert await subject.identity_for(MAPPED, CLAIMS) is None
    users.answer = frozenset({MAPPED})
    clock.advance(exchange_appapi.ACCOUNT_FAILURE_RETRY_SECONDS + 1)

    identity = await subject.identity_for(MAPPED, CLAIMS)

    assert identity is not None, "the failure did not stand in the cache as an empty list"


# --- what never happens ----------------------------------------------------------------------


@pytest.mark.anyio
async def test_identity_for_never_raises_and_writes_no_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No principal, no claim and no header in a log line, and no exception for any input."""
    subject, _, _ = source(None)
    hostile_claims: list[Any] = [{}, {"azp": "\x00\ud800"}, {"azp": 3.14}, CLAIMS]

    with caplog.at_level(logging.DEBUG):
        for claims in hostile_claims:
            assert await subject.identity_for(MAPPED, claims) is None
        assert await subject.identity_for("", CLAIMS) is None

    assert caplog.text.strip() == ""
    assert MAPPED not in caplog.text


# --- the wiring and the two documented numbers -----------------------------------------------


def test_the_two_time_constants_are_the_documented_ones() -> None:
    assert exchange_appapi.ACCOUNT_CACHE_TTL == 60.0
    assert exchange_appapi.ACCOUNT_FAILURE_RETRY_SECONDS == 30.0


def test_the_default_list_source_is_the_account_list_of_the_audit_module() -> None:
    """The route exists exactly once, in ``audit/accounts.py``; this module only reads it."""
    parameter = inspect.signature(exchange_appapi.AppApiAccounts.__init__).parameters["users"]
    assert parameter.default is accounts.existing_users


def test_the_environment_of_the_deployment_reaches_the_list_source() -> None:
    """The constructor environment is the one the list is read with, never a second one."""
    env = {"APP_ID": "mcp_connector"}
    subject, users, _ = source(env=env)

    asyncio.run(subject.identity_for(MAPPED, CLAIMS))

    assert users.environments == [env]


def test_the_source_fits_the_protocol_of_the_chain() -> None:
    subject, _, _ = source()
    assert isinstance(subject, exchange_accounts.ExchangeAccounts)


# --- the durchstich: from the exchanged token to the outgoing AppAPI header ------------------

ISSUER = "https://idp.example.org/realms/f13"
PUBLIC_URL = "https://mcp.example.org"
AUDIENCE = f"{PUBLIC_URL}{RESOURCE_SUFFIX}"
JWKS_URL = f"{ISSUER}{chain.DEFAULT_JWKS_PATH}"
KID = "key-1"

#: The second mapped account of the two-account measurement (T-23-15).
OTHER = "f13-account-9"

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
AA_VERSION = "34.0.3"
BASE_URL = "http://nc.test"
USERS_URL = f"{BASE_URL}{accounts.USERS_PATH}"

#: The one outgoing data call of the tool-shaped handler below.
DATA_URL = f"{BASE_URL}/remote.php/dav/"

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)

#: The deploy environment of an armed ExApp: AppAPI identity plus the exchange namespace.
DEPLOYMENT = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_AA_VERSION: AA_VERSION,
    config.ENV_NEXTCLOUD_URL: BASE_URL,
    config.ENV_PUBLIC_URL: PUBLIC_URL,
    config.ENV_DISABLE_DNS_REBINDING: "1",
    config.ENV_EXCHANGE_ENABLED: "1",
    config.ENV_EXCHANGE_ISSUER: ISSUER,
    config.ENV_EXCHANGE_AZP: AZP,
}

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


def serve_jwks() -> respx.Route:
    entry = json.loads(RSAAlgorithm.to_jwk(PRIVATE.public_key()))
    entry.update({"kid": KID, "use": "sig", "alg": "RS256"})
    return respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [entry]}))


def serve_accounts(names: list[str]) -> respx.Route:
    """The AppAPI account list of the instance, in the OCS envelope it really answers in."""
    payload = {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": names}}
    return respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=payload))


def exchange_token(sub: str = MAPPED, **overrides: Any) -> str:
    """A token that passes every rule of phase 21: issuer, audience, azp, age and shape."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "sub": sub,
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now,
        "typ": "Bearer",
        "azp": AZP,
    }
    claims.update(overrides)
    return jwt.encode(claims, PRIVATE, algorithm="RS256", headers={"kid": KID})


def appapi_headers(user: str = "") -> dict[str, str]:
    """The headers HaRP puts in front of every request it forwards."""
    token = base64.b64encode(f"{user}:{APP_SECRET}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


def built_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The application of ``entry_exapp``, with a local store and no key fetch."""

    async def fake_key(env: object = None) -> bytes:
        del env
        return bytes(range(32))

    monkeypatch.setattr(oauth_store_module.crypto, "data_key", fake_key)
    return entry_exapp.build_exapp_app(
        {**DEPLOYMENT, config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}
    )


def mcp_call(client: TestClient, token: str) -> Any:
    return client.post(
        "/mcp",
        json=INITIALIZE,
        headers={**MCP_HEADERS, **appapi_headers(), "Authorization": f"Bearer {token}"},
    )


@respx.mock
def test_a_mapped_account_passes_the_built_application_and_one_call_costs_one_list_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wiring of the entry point, measured end to end against the built application.

    A token that passes every rule of phase 21 reaches the MCP transport because the
    account exists, and two calls cost the account list exactly one fetch: the source is
    built once per application and holds the one cache of this process.
    """
    serve_jwks()
    listed = serve_accounts([MAPPED, "somebody-else"])
    app = built_app(tmp_path, monkeypatch)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        first = mcp_call(client, exchange_token())
        second = mcp_call(client, exchange_token())

    assert first.status_code == 200
    assert "protocolVersion" in first.text
    assert second.status_code == 200
    assert listed.call_count == 1, "the account list is cached, never fetched per call"


@respx.mock
def test_an_account_the_instance_does_not_name_is_401_without_a_data_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MAP-02 at the boundary: no account, no identity, no call in anybody's name."""
    serve_jwks()
    serve_accounts(["somebody-else"])
    app = built_app(tmp_path, monkeypatch)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = mcp_call(client, exchange_token())

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    called = {str(call.request.url) for call in respx.calls}
    assert called <= {JWKS_URL, USERS_URL}, "nothing was asked in the name of the account"


@respx.mock
def test_an_unreadable_account_list_is_401_without_a_data_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reversed asymmetry end to end: cannot know is refused, exactly like not found."""
    serve_jwks()
    respx.get(USERS_URL).mock(return_value=httpx.Response(500))
    app = built_app(tmp_path, monkeypatch)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = mcp_call(client, exchange_token())

    assert response.status_code == 401
    called = {str(call.request.url) for call in respx.calls}
    assert called <= {JWKS_URL, USERS_URL}


@respx.mock
def test_the_401_does_not_distinguish_the_three_refusal_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-23-13: unknown account, unreadable list and unmappable claim are one answer."""
    serve_jwks()
    listed = serve_accounts(["somebody-else"])
    app = built_app(tmp_path, monkeypatch)

    with TestClient(app, base_url=PUBLIC_URL) as client:
        unknown_account = mcp_call(client, exchange_token())
        # An untrimmed claim value is refused by the mapping, before the list is asked.
        unmappable_claim = mcp_call(client, exchange_token(sub=f" {MAPPED}"))
        listed.mock(return_value=httpx.Response(500))
        # A fresh source would still hold the cached list; a new application starts empty.
    app = built_app(tmp_path, monkeypatch)
    with TestClient(app, base_url=PUBLIC_URL) as client:
        unreadable_list = mcp_call(client, exchange_token())

    answers = (unknown_account, unmappable_claim, unreadable_list)
    assert {response.status_code for response in answers} == {401}
    assert len({response.content for response in answers}) == 1
    assert len({response.headers["www-authenticate"] for response in answers}) == 1


class ExplodingStoreBranch:
    """The store branch of the chain, never asked: every token below is a compact JWS."""

    async def verify_token(self, token: str) -> AccessToken | None:
        raise AssertionError("the store branch was asked about an exchange token")

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        raise AssertionError("the store branch was asked to resolve an exchange token")

    def invalidate(self) -> None:
        raise AssertionError("the store branch was emptied by a test that does not revoke")


@respx.mock
def test_the_outgoing_appapi_header_carries_the_mapped_principal_and_never_the_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The durchstich of CRED-01, measured at the outgoing header and not at a return value.

    Everything on the way is real: the transport boundary, the chain with the checker of
    phase 21 (its key set served over the network stand-in), the mapping, the account
    source with the real list reader against the AppAPI route, and the credential layer of
    ``deps``. The handler behind the boundary is shaped like every tool: it resolves the
    credentials of its call and makes one outgoing Nextcloud request with them.

    Two different tokens for two different accounts produce two different impersonation
    headers, and neither carries the name of the other (T-23-15). The header decodes to
    ``<principal>:<app secret>``, and the three other AppAPI headers are the installation's.
    """
    del tmp_path
    for name, value in DEPLOYMENT.items():
        monkeypatch.setenv(name, value)
    serve_jwks()
    serve_accounts([MAPPED, OTHER])
    outgoing = respx.get(DATA_URL).mock(return_value=httpx.Response(200))

    verifier = chain.build_chain(
        ExplodingStoreBranch(),
        env=DEPLOYMENT,
        accounts=exchange_appapi.AppApiAccounts(env=DEPLOYMENT),
    )

    async def tool_shaped(request: Request) -> Response:
        ctx = SimpleNamespace(
            headers=request.headers, request_context=SimpleNamespace(request=request)
        )
        creds = deps.resolve_credentials(ctx)
        answer = await shared_client().get(DATA_URL, auth=creds.auth())
        return PlainTextResponse(str(answer.status_code))

    async def never_paused(principal: str) -> bool:
        del principal
        return False

    app = Starlette(routes=[Route("/mcp", tool_shaped, methods=["POST"])])
    for route in app.router.routes:
        if isinstance(route, Route):
            route.app = RequireAppApi(
                route.app, DEPLOYMENT, token_verifier=verifier, access_check=never_paused
            )

    with TestClient(app) as client:

        def call(token: str) -> Any:
            headers = {**appapi_headers(), "Authorization": f"Bearer {token}"}
            return client.post("/mcp", headers=headers)

        assert call(exchange_token(sub=MAPPED)).status_code == 200
        assert call(exchange_token(sub=OTHER)).status_code == 200

    assert outgoing.call_count == 2
    first, second = (call.request.headers for call in outgoing.calls)
    decoded_first = base64.b64decode(first["AUTHORIZATION-APP-API"]).decode()
    decoded_second = base64.b64decode(second["AUTHORIZATION-APP-API"]).decode()
    assert decoded_first == f"{MAPPED}:{APP_SECRET}"
    assert decoded_second == f"{OTHER}:{APP_SECRET}"
    assert MAPPED not in decoded_second
    assert OTHER not in decoded_first
    for headers in (first, second):
        assert headers["EX-APP-ID"] == APP_ID
        assert headers["EX-APP-VERSION"] == APP_VERSION
        assert headers["AA-VERSION"] == AA_VERSION

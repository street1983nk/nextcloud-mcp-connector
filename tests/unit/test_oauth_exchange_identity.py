"""The identity of the exchange path (MAP-01, plan 23-02): one seam, one branch, one proof.

Two things are pinned here. First the seam itself, ``oauth/exchange_accounts.py``: the one
interface at which the two operating modes of the exchange path differ, its reserved client
identifier and the reading of the acting party out of a checked foreign claim set. Second,
the ``EXCHANGE_CLAIM`` branch of ``ChainedVerifier.resolve_identity``: the one place a
checked exchange token becomes an identity, and the measured proof that the pause switch,
the audit chain and the sweep treat a mapped account exactly like a signed in one.

No Nextcloud and no socket: the account source is a stand-in of this file, the stores are
SQLite files in ``tmp_path``, and both directions of "never asked" are stand-ins that raise
:class:`AssertionError` the moment they are touched (the shape of 22-02).
"""

import asyncio
import base64
import logging
import time
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.auth.provider import AccessToken
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.audit import record
from mcp_connector.audit.store import OUTCOME_OK, AuditStore, user_chain
from mcp_connector.exapp.middleware import RequireAppApi
from mcp_connector.oauth import chain, connect, exchange_accounts
from mcp_connector.oauth.metadata import RESOURCE_SUFFIX, TOOL_SCOPE
from mcp_connector.oauth.store import OAuthStore
from mcp_connector.oauth.verifier import AUTH_ID_CLAIM, CREDENTIAL_APP_PASSWORD, OAuthIdentity

AZP = "f13-orchestrator"
ISSUER = "https://idp.example.org/realms/f13"
PUBLIC_URL = "https://mcp.example.org"
AUDIENCE = f"{PUBLIC_URL}{RESOURCE_SUFFIX}"

#: The two accounts of the proof: one acts through the exchange path, one is signed in.
MAPPED = "f13-account-7"
SIGNED_IN = "alice"

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
BASE_URL = "http://nc.test"

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

STUB_APP_PASSWORD = "a-stub-app-password-of-this-file"

#: The two token shapes of the switch, the same values the chain tests use.
SHAPED_LIKE_A_JWS = "a-header.a-payload.a-signature"
SHAPED_LIKE_A_STORE_TOKEN = "Rl9TBaUr2vMbqLKGh3dwXcE1nQ6y0ZsA"


# --- the reserved client identifier of the exchange path -----------------------------------


def test_the_exchange_client_id_is_the_reserved_urn_of_this_path() -> None:
    """The value every audit line of an exchange call carries as its client."""
    assert exchange_accounts.EXCHANGE_CLIENT_ID == "urn:mcp-connector:token-exchange"


def test_the_exchange_client_id_differs_from_the_onboarding_client() -> None:
    """Two reserved identifiers, two different paths: a reader must be able to tell them."""
    assert exchange_accounts.EXCHANGE_CLIENT_ID != connect.CONNECT_CLIENT_ID


# --- the acting party out of a checked foreign claim set -----------------------------------


def test_the_acting_party_is_the_azp_of_the_checked_claim_set() -> None:
    assert exchange_accounts.acting_party({"azp": AZP}) == AZP


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"azp": ""},
        {"azp": None},
        {"azp": 1},
        {"azp": True},
        {"azp": ["f13"]},
        {"azp": {"name": "f13"}},
        {"azp": b"f13"},
    ],
    ids=["missing", "empty", "none", "number", "bool", "list", "dict", "bytes"],
)
def test_a_missing_empty_or_untextual_azp_is_the_empty_string(claims: dict) -> None:
    """The value is freight of a foreign realm: anything that is not text names nobody."""
    assert exchange_accounts.acting_party(claims) == ""


def test_the_acting_party_is_capped_at_its_named_bound() -> None:
    assert exchange_accounts.MAX_ACTING_PARTY_LENGTH == 64
    capped = exchange_accounts.acting_party({"azp": "x" * 200})
    assert len(capped) == exchange_accounts.MAX_ACTING_PARTY_LENGTH


def test_the_acting_party_carries_no_control_or_format_character() -> None:
    """A line break could fake a log line, an RTL override could turn one around."""
    assert exchange_accounts.acting_party({"azp": "f13\x00\x07"}) == "f13"
    assert exchange_accounts.acting_party({"azp": "f\r\n13"}) == "f13"
    assert exchange_accounts.acting_party({"azp": "a‮b"}) == "ab"
    assert exchange_accounts.acting_party({"azp": "\x1b[31m"}) == "[31m"


def test_the_acting_party_never_raises_under_a_hostile_corpus() -> None:
    """The function stands next to the hot path and refusal is its only failure mode."""
    corpus = [
        {"azp": "\ud800"},
        {"azp": "\x00" * 300},
        {"azp": 3.14},
        {"azp": object()},
        {"azp": "x" * 100_000},
        {"other": AZP},
    ]
    for claims in corpus:
        result = exchange_accounts.acting_party(claims)
        assert isinstance(result, str)
        assert len(result) <= exchange_accounts.MAX_ACTING_PARTY_LENGTH


# --- the protocol of the account source -----------------------------------------------------


def test_an_object_with_the_one_method_satisfies_the_protocol() -> None:
    """The runtime checkable shape both operating modes have to fit."""

    class Fitting:
        async def identity_for(self, principal, claims):
            return None

    class NotFitting:
        pass

    assert isinstance(Fitting(), exchange_accounts.ExchangeAccounts)
    assert not isinstance(NotFitting(), exchange_accounts.ExchangeAccounts)


# --- the branch in the chain: helpers -------------------------------------------------------


def configuration() -> chain.ExchangeConfig:
    loaded = chain.load_exchange_config(
        {
            config.ENV_EXCHANGE_ENABLED: "1",
            config.ENV_EXCHANGE_ISSUER: ISSUER,
            config.ENV_EXCHANGE_AZP: AZP,
            config.ENV_PUBLIC_URL: PUBLIC_URL,
        }
    )
    assert loaded is not None
    return loaded


def checked_claims(**overrides: Any) -> dict[str, Any]:
    """What the checker of phase 21 hands over: the claim set of a checked exchange token."""
    now = int(time.time())
    values: dict[str, Any] = {
        "iss": ISSUER,
        "sub": MAPPED,
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now,
        "typ": "Bearer",
        "azp": AZP,
    }
    values.update(overrides)
    return values


def mapped_identity(principal: str, claims: Mapping[str, Any]) -> OAuthIdentity:
    """What a real account source of plan 23-03 will answer, in the shape of this plan."""
    return OAuthIdentity(
        nc_user=principal,
        app_password=STUB_APP_PASSWORD,
        auth_id="an-exchange-identity",
        client_id=exchange_accounts.EXCHANGE_CLIENT_ID,
        principal=principal,
        client_name=exchange_accounts.acting_party(claims),
        credential=CREDENTIAL_APP_PASSWORD,
    )


class StubChecker:
    """The exchange branch as far as the chain sees it: one checked claim set."""

    def __init__(self, claims: dict[str, Any] | None = None) -> None:
        self._claims = claims

    async def claims_of(self, token: str) -> dict[str, Any]:
        del token
        return dict(self._claims if self._claims is not None else checked_claims())

    def forget_keys(self) -> None:
        return None


class ExplodingStoreBranch:
    """A store branch that flies apart the moment it is touched: "never asked" is measured."""

    async def verify_token(self, token: str) -> AccessToken | None:
        raise AssertionError("the store branch was asked about an exchange token")

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        raise AssertionError("the store branch was asked to resolve an exchange token")

    def invalidate(self) -> None:
        raise AssertionError("the store branch was emptied by a test that does not revoke")


class ExplodingAccounts:
    """The same stand-in for the other direction: an account source that is never asked."""

    async def identity_for(self, principal: str, claims: Mapping[str, Any]) -> OAuthIdentity | None:
        raise AssertionError("the account source was asked although nothing was mapped")


class RecordingStoreBranch:
    """The store branch as far as the chain sees it: what it was asked, what it answered."""

    def __init__(
        self, *, access: AccessToken | None = None, resolved: OAuthIdentity | None = None
    ) -> None:
        self.asked_to_resolve: list[AccessToken] = []
        self._access = access
        self._resolved = resolved

    async def verify_token(self, token: str) -> AccessToken | None:
        del token
        return self._access

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        self.asked_to_resolve.append(access)
        return self._resolved

    def invalidate(self) -> None:
        return None


class PrincipalAccounts:
    """An account source that knows exactly one account, recording every question."""

    def __init__(self, known: str, *, error: Exception | None = None) -> None:
        self.known = known
        self.seen: list[tuple[str, dict[str, Any]]] = []
        self._error = error

    async def identity_for(self, principal: str, claims: Mapping[str, Any]) -> OAuthIdentity | None:
        self.seen.append((principal, dict(claims)))
        if self._error is not None:
            raise self._error
        if principal != self.known:
            return None
        return mapped_identity(principal, claims)


def own_access() -> AccessToken:
    """What the store branch answers for a token of this server."""
    return AccessToken(
        token=SHAPED_LIKE_A_STORE_TOKEN,
        client_id="a-client",
        scopes=[TOOL_SCOPE],
        expires_at=int(time.time()) + 300,
        resource=AUDIENCE,
        subject=SIGNED_IN,
        claims={AUTH_ID_CLAIM: "an-authorization"},
    )


def chained(
    store: chain.StoreBranch,
    accounts: exchange_accounts.ExchangeAccounts | None,
    claims: dict[str, Any] | None = None,
) -> chain.ChainedVerifier:
    return chain.ChainedVerifier(
        store=store, checker=StubChecker(claims), config=configuration(), accounts=accounts
    )


# --- which branch answers, and which one is never asked -------------------------------------


@pytest.mark.anyio
async def test_a_store_token_never_asks_the_account_source() -> None:
    """The existing path is untouched: its identity comes from the store branch alone."""
    expected = OAuthIdentity(
        nc_user=SIGNED_IN,
        app_password=STUB_APP_PASSWORD,
        auth_id="an-authorization",
        client_id="a-client",
        principal=SIGNED_IN,
    )
    store = RecordingStoreBranch(access=own_access(), resolved=expected)
    verifier = chained(store, ExplodingAccounts())

    access = await verifier.verify_token(SHAPED_LIKE_A_STORE_TOKEN)
    assert access is not None

    assert await verifier.resolve_identity(access) is expected
    assert store.asked_to_resolve == [access]


@pytest.mark.anyio
async def test_an_exchange_token_never_asks_the_store_branch() -> None:
    """The other direction of the same switch, with the same kind of proof."""
    verifier = chained(ExplodingStoreBranch(), PrincipalAccounts(MAPPED))

    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)
    assert access is not None

    assert await verifier.resolve_identity(access) is not None


@pytest.mark.anyio
async def test_the_identity_carries_exactly_the_mapped_principal_and_no_login_name() -> None:
    """T-23-06: the principal comes out of the mapping and never out of a claim directly."""
    claims = checked_claims(preferred_username="a-login-name-of-a-foreign-realm")
    accounts = PrincipalAccounts(MAPPED)
    verifier = chained(ExplodingStoreBranch(), accounts, claims)
    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)
    assert access is not None

    identity = await verifier.resolve_identity(access)

    assert identity is not None
    assert identity.principal == MAPPED
    assert identity.nc_user != "a-login-name-of-a-foreign-realm"
    assert identity.client_id == exchange_accounts.EXCHANGE_CLIENT_ID
    assert identity.credential == CREDENTIAL_APP_PASSWORD
    assert accounts.seen == [(MAPPED, claims)], "asked once, with the checked claim set"


# --- every unclarity is a refusal ------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "claims",
    [
        checked_claims(sub=None),
        {key: value for key, value in checked_claims().items() if key != "sub"},
        checked_claims(sub=7),
        checked_claims(sub=" alice"),
        checked_claims(sub="a/b"),
        checked_claims(sub="x" * 65),
    ],
    ids=["none", "missing", "number", "untrimmed", "forbidden-character", "too-long"],
)
async def test_a_claim_set_the_mapping_refuses_never_reaches_the_source(
    claims: dict[str, Any],
) -> None:
    """No mapping, no question: the account source is behind the mapping, never before it."""
    verifier = chained(ExplodingStoreBranch(), ExplodingAccounts(), claims)
    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)
    assert access is not None

    assert await verifier.resolve_identity(access) is None


@pytest.mark.anyio
async def test_a_source_without_an_answer_is_a_refusal() -> None:
    """``None`` of the source always means "this account does not act here" (MAP-02)."""
    verifier = chained(ExplodingStoreBranch(), PrincipalAccounts("somebody-else"))
    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)
    assert access is not None

    assert await verifier.resolve_identity(access) is None


@pytest.mark.anyio
async def test_a_source_that_raises_is_a_refusal_and_one_line_naming_the_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-23-08 and T-23-09: fail closed for this one call, and the line carries no value."""
    error = RuntimeError("a principal nobody may read in a log")
    verifier = chained(ExplodingStoreBranch(), PrincipalAccounts(MAPPED, error=error))
    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)
    assert access is not None

    with caplog.at_level(logging.ERROR, logger="mcp_connector.oauth.chain"):
        assert await verifier.resolve_identity(access) is None

    lines = [entry.getMessage() for entry in caplog.records]
    assert len(lines) == 1
    assert "RuntimeError" in lines[0]
    assert "a principal nobody may read in a log" not in lines[0]
    assert MAPPED not in lines[0]


@pytest.mark.anyio
async def test_a_memory_error_of_the_source_is_a_refusal_too() -> None:
    """The catch has the exact shape of the one in ``verify_token``, MemoryError included."""
    verifier = chained(ExplodingStoreBranch(), PrincipalAccounts(MAPPED, error=MemoryError()))
    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)
    assert access is not None

    assert await verifier.resolve_identity(access) is None


@pytest.mark.anyio
async def test_without_an_account_source_an_exchange_token_stays_refused() -> None:
    """T-23-07: ``accounts=None`` is the state after phase 22, and it green in RED already,
    because it pins what must not change: an armed chain without a source refuses."""
    verifier = chain.ChainedVerifier(
        store=ExplodingStoreBranch(), checker=StubChecker(), config=configuration()
    )
    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)
    assert access is not None

    assert await verifier.resolve_identity(access) is None


@pytest.mark.anyio
async def test_build_chain_hands_the_account_source_through() -> None:
    """The one place a deployment hangs the chain in takes the source the same way."""
    built = chain.build_chain(
        RecordingStoreBranch(),
        env={
            config.ENV_EXCHANGE_ENABLED: "1",
            config.ENV_EXCHANGE_ISSUER: ISSUER,
            config.ENV_EXCHANGE_AZP: AZP,
            config.ENV_PUBLIC_URL: PUBLIC_URL,
        },
        accounts=PrincipalAccounts(MAPPED),
    )
    assert isinstance(built, chain.ChainedVerifier)

    access = AccessToken(
        token=SHAPED_LIKE_A_JWS,
        client_id=AZP,
        scopes=[TOOL_SCOPE],
        expires_at=int(time.time()) + 300,
        resource=AUDIENCE,
        subject=None,
        claims={chain.EXCHANGE_CLAIM: checked_claims()},
    )
    identity = await built.resolve_identity(access)

    assert identity is not None
    assert identity.principal == MAPPED


# --- the proof: pause switch, audit chain and sweep, for both kinds of account ---------------


def appapi_headers(user: str) -> dict[str, str]:
    """The headers HaRP puts in front of every request it forwards."""
    token = base64.b64encode(f"{user}:{APP_SECRET}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


MIDDLEWARE_ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_NEXTCLOUD_URL: BASE_URL,
    config.ENV_PUBLIC_URL: PUBLIC_URL,
}


def test_the_pause_switch_the_audit_chain_and_the_sweep_treat_both_kinds_alike(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Success criterion 1 of the phase, measured and not asserted in prose.

    One boundary, one audit store, one pause switch, and two accounts side by side: one
    acts through a checked exchange token and the mapping, one is signed in through the
    AppAPI handshake. Every measurement runs for both, and the claim of each is the same:
    the mapped account is treated exactly like the signed in one. The comparison **is** the
    test, which is why the two runs stand next to each other in one function.
    """
    # The AppAPI half of the recording path reads the process environment.
    for name, value in MIDDLEWARE_ENV.items():
        monkeypatch.setenv(name, value)

    run = asyncio.run
    oauth_store = OAuthStore(tmp_path / "oauth.sqlite3", KEY)
    audit = AuditStore(tmp_path / "audit.sqlite3")

    async def audit_opener() -> AuditStore:
        return audit

    async def switch(principal: str) -> bool:
        return await oauth_store.access_disabled(principal)

    verifier = chained(ExplodingStoreBranch(), PrincipalAccounts(MAPPED))
    recorder = record.Recorder(store_provider=audit_opener)

    async def served(request: Request) -> Response:
        ctx = SimpleNamespace(request_context=SimpleNamespace(request=request, params=None))
        await record.note(ctx, "a_tool", OUTCOME_OK, None, 0.001)
        return PlainTextResponse("served")

    app = Starlette(routes=[Route("/mcp", served, methods=["POST"])])
    for route in app.router.routes:
        if isinstance(route, Route):
            route.app = RequireAppApi(
                route.app,
                MIDDLEWARE_ENV,
                token_verifier=verifier,
                access_check=switch,
                audit_recorder=recorder,
            )

    with TestClient(app) as client:

        def exchange_call() -> Any:
            headers = {**appapi_headers(user=""), "Authorization": f"Bearer {SHAPED_LIKE_A_JWS}"}
            return client.post("/mcp", headers=headers)

        def appapi_call() -> Any:
            return client.post("/mcp", headers=appapi_headers(user=SIGNED_IN))

        # A valid exchange token reaches a tool call, exactly like a signed in account.
        assert exchange_call().status_code == 200
        assert appapi_call().status_code == 200

        # Measurement 1, the audit chain: the mapped call writes into ``u:<principal>``,
        # the very same kind of chain an AppAPI call of an account writes into.
        mapped_chain = user_chain(MAPPED)
        signed_chain = user_chain(SIGNED_IN)
        assert mapped_chain == f"u:{MAPPED}"
        mapped_row = run(audit.last_entry(mapped_chain))
        signed_row = run(audit.last_entry(signed_chain))
        assert mapped_row is not None, "the exchange call was recorded under its principal"
        assert signed_row is not None, "the signed in call was recorded under its account"
        assert mapped_row.nc_user == MAPPED
        assert signed_row.nc_user == SIGNED_IN
        # T-23-10: the row itself says this was the exchange path and who acted.
        assert mapped_row.client_id == exchange_accounts.EXCHANGE_CLIENT_ID
        assert mapped_row.client_name == AZP

        # Measurement 2, the pause switch: 403 with ``access_disabled`` after
        # ``set_access``, read off ``identity.principal`` for both kinds alike.
        run(oauth_store.set_access(MAPPED, disabled=True))
        run(oauth_store.set_access(SIGNED_IN, disabled=True))
        refused_mapped = exchange_call()
        refused_signed = appapi_call()
        assert (refused_mapped.status_code, refused_signed.status_code) == (403, 403)
        assert refused_mapped.json()["error"] == "access_disabled"
        assert refused_signed.json()["error"] == "access_disabled"

    # Measurement 3, the sweep of D-12: a silent chain stays while its principal stands in
    # the account list, and off the list both kinds fall the same way, marker included.
    moment = int(time.time()) + 40 * 86400
    silent = run(audit.silent_users(moment=moment))
    assert {MAPPED, SIGNED_IN} <= set(silent)
    known = {MAPPED, SIGNED_IN}
    for account in silent:
        if account not in known:
            run(audit.drop_user_chain(account, moment=moment))
    assert run(audit.last_entry(mapped_chain)) is not None, "in the list, the chain stays"
    assert run(audit.last_entry(signed_chain)) is not None
    assert run(audit.drop_user_chain(MAPPED, moment=moment)) == 1
    assert run(audit.drop_user_chain(SIGNED_IN, moment=moment)) == 1
    assert run(audit.last_entry(mapped_chain)) is None, "off the list, the chain goes"
    assert run(audit.last_entry(signed_chain)) is None

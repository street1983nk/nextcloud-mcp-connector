"""The token exchange path in one file: its configuration (CONF-01), then its chain.

Nothing here opens a socket. Every environment is a dict that is handed in, which is what
makes each configuration case a pure function of its input; only one test touches
``os.environ``, and it is the one that has to prove the process environment is read like
everywhere else. Every provider answer of the chain cases is served by respx, and the keys
are generated per test run.

No test asserts a whole message text. What is asserted is the one property every refusal
of the reader owes an operator: the message names the variable that has to change, and no
message carries the value that was read, because that value can have travelled here over
HTTP (T-22-04).

The switch of the chain is measured and not described: both branches are proved with a
stand-in that raises :class:`AssertionError` the moment it is called, so "never reaches the
other branch" is a failing test and not a sentence (T-22-06, pitfall 1 of the research).
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from mcp.server.auth.provider import AccessToken
from starlette.requests import Request
from starlette.testclient import TestClient

from mcp_connector import config, entry_oauth
from mcp_connector.errors import ToolError
from mcp_connector.exapp.middleware import RequireOAuthBearer
from mcp_connector.oauth import chain, exchange, mapping, oidc, throttle
from mcp_connector.oauth.metadata import RESOURCE_SUFFIX, TOOL_SCOPE
from mcp_connector.oauth.verifier import AUTH_ID_CLAIM, IdentitySource, OAuthIdentity

ISSUER = "https://idp.example.org/realms/f13"
AZP = "f13-orchestrator"
PUBLIC_URL = "https://mcp.example.org"

ARMED = {
    config.ENV_EXCHANGE_ENABLED: "1",
    config.ENV_EXCHANGE_ISSUER: ISSUER,
    config.ENV_EXCHANGE_AZP: AZP,
}


def armed(**overrides: str) -> dict[str, str]:
    return {**ARMED, config.ENV_PUBLIC_URL: PUBLIC_URL, **overrides}


# --- the off state -----------------------------------------------------------------------


def test_an_untouched_environment_configures_nothing() -> None:
    """The factory state of CONF-01, and the measurement behind "unchanged behaviour"."""
    assert chain.load_exchange_config({}) is None


def test_an_environment_of_other_variables_configures_nothing() -> None:
    assert chain.load_exchange_config({config.ENV_URL: "http://nc.test"}) is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_switch_alone_configures_nothing(blank: str) -> None:
    assert chain.load_exchange_config({config.ENV_EXCHANGE_ENABLED: blank}) is None


@pytest.mark.parametrize(
    "name",
    [name for name in config.EXCHANGE_VARIABLES if name != config.ENV_EXCHANGE_ENABLED],
)
def test_a_configured_but_disarmed_path_refuses_the_start(name: str) -> None:
    """T-22-02: a configured path that nothing armed is the silent half state itself.

    Any of the seven values is enough; an operator who set one and forgot the switch has to
    read which variable was seen and which one is missing, instead of running a server that
    ignores both.
    """
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config({name: "a-value-nobody-should-read"})

    assert name in excinfo.value.message
    assert config.ENV_EXCHANGE_ENABLED in excinfo.value.message
    assert "a-value-nobody-should-read" not in f"{excinfo.value.message} {excinfo.value.hint}"


def test_an_explicit_off_with_a_configured_value_refuses_as_well() -> None:
    """Off is off, and a value next to it is still the half state of T-22-02."""
    with pytest.raises(ToolError):
        chain.load_exchange_config(
            {config.ENV_EXCHANGE_ENABLED: "0", config.ENV_EXCHANGE_ISSUER: ISSUER}
        )


def test_a_blank_value_next_to_a_disarmed_switch_is_no_configuration() -> None:
    assert chain.load_exchange_config({config.ENV_EXCHANGE_ISSUER: "   "}) is None


# --- the required values -----------------------------------------------------------------


def test_an_armed_path_without_the_issuer_refuses() -> None:
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config({config.ENV_EXCHANGE_ENABLED: "1", config.ENV_EXCHANGE_AZP: AZP})

    assert config.ENV_EXCHANGE_ISSUER in excinfo.value.message


def test_an_armed_path_without_the_azp_allowlist_refuses() -> None:
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(
            {config.ENV_EXCHANGE_ENABLED: "1", config.ENV_EXCHANGE_ISSUER: ISSUER}
        )

    assert config.ENV_EXCHANGE_AZP in excinfo.value.message


@pytest.mark.parametrize("raw", ["", "   ", ",", " , ,"])
def test_an_azp_allowlist_of_separators_alone_is_never_an_empty_allowlist(raw: str) -> None:
    """An empty allowlist would be a rule nobody wrote: it refuses every token, which looks
    like a broken deployment, and the next hand that fixes the symptom widens it."""
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config({**ARMED, config.ENV_EXCHANGE_AZP: raw})

    assert config.ENV_EXCHANGE_AZP in excinfo.value.message


# --- the documented defaults -------------------------------------------------------------


def test_the_defaults_of_an_armed_path_are_the_documented_ones() -> None:
    loaded = chain.load_exchange_config(armed())

    assert loaded is not None
    assert loaded.settings.issuer == ISSUER
    assert loaded.settings.jwks_uri == f"{ISSUER}{chain.DEFAULT_JWKS_PATH}"
    assert loaded.settings.audience == f"{PUBLIC_URL}{RESOURCE_SUFFIX}"
    assert loaded.settings.azp_allowed == (AZP,)
    assert loaded.settings.algorithms == exchange.DEFAULT_EXCHANGE_ALGORITHMS
    assert loaded.settings.jwks_origin is None
    assert loaded.account_claim == config.DEFAULT_EXCHANGE_ACCOUNT_CLAIM


def test_the_audience_default_is_the_resource_url_of_this_instance() -> None:
    """T-22-03: never a generic name that a token of another instance would hold against.

    The value is the one this server already writes into its own tokens, so an operator who
    takes the default takes the audience that is documented for this deployment.
    """
    loaded = chain.load_exchange_config(armed(**{config.ENV_PUBLIC_URL: "https://a.example.org"}))

    assert loaded is not None
    assert loaded.settings.audience == f"https://a.example.org{RESOURCE_SUFFIX}"


@pytest.mark.parametrize("public", [None, "", "   ", "/"])
def test_an_armed_path_without_a_public_url_refuses_instead_of_defaulting(
    public: str | None,
) -> None:
    """CR-01: the loopback default is the same value everywhere and is no instance boundary.

    ``config.public_url`` answers ``DEFAULT_PUBLIC_URL`` for all four of these, so all four
    would have armed the path with an audience every equally misconfigured installation
    accepts, and a token minted for one agency behind a shared provider would hold at the
    next. The refusal names both variables an operator can act on and neither value.
    """
    source = dict(ARMED)
    if public is not None:
        source[config.ENV_PUBLIC_URL] = public

    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(source)

    assert config.ENV_PUBLIC_URL in excinfo.value.message
    assert config.ENV_EXCHANGE_AUDIENCE in excinfo.value.message
    assert config.DEFAULT_PUBLIC_URL not in f"{excinfo.value.message} {excinfo.value.hint}"


def test_a_named_audience_needs_no_public_url() -> None:
    """The refusal above is about the derivation, never about the variable as such."""
    loaded = chain.load_exchange_config(
        {**ARMED, config.ENV_EXCHANGE_AUDIENCE: "https://cloud.example.org/exapps/mcp/mcp"}
    )

    assert loaded is not None
    assert loaded.settings.audience == "https://cloud.example.org/exapps/mcp/mcp"


def test_an_address_that_is_deliberately_the_loopback_default_is_served() -> None:
    """A development run is a typed answer, and the refusal is about the absence of one."""
    loaded = chain.load_exchange_config({**ARMED, config.ENV_PUBLIC_URL: config.DEFAULT_PUBLIC_URL})

    assert loaded is not None
    assert loaded.settings.audience == f"{config.DEFAULT_PUBLIC_URL}{RESOURCE_SUFFIX}"


def test_every_value_can_be_configured_explicitly() -> None:
    loaded = chain.load_exchange_config(
        armed(
            **{
                config.ENV_EXCHANGE_JWKS_URI: "https://certs.internal.example.org/keys",
                config.ENV_EXCHANGE_JWKS_ORIGIN: "https://certs.internal.example.org",
                config.ENV_EXCHANGE_AUDIENCE: "https://cloud.example.org/exapps/mcp/mcp",
                config.ENV_EXCHANGE_ACCOUNT_CLAIM: "preferred_username",
                config.ENV_EXCHANGE_ALGORITHMS: "RS256, ES256",
            }
        )
    )

    assert loaded is not None
    assert loaded.settings.jwks_uri == "https://certs.internal.example.org/keys"
    assert loaded.settings.jwks_origin == "https://certs.internal.example.org"
    assert loaded.settings.audience == "https://cloud.example.org/exapps/mcp/mcp"
    assert loaded.settings.algorithms == ("RS256", "ES256")
    assert loaded.account_claim == "preferred_username"


def test_the_azp_allowlist_is_split_on_commas() -> None:
    loaded = chain.load_exchange_config(armed(**{config.ENV_EXCHANGE_AZP: "a, b ,c"}))

    assert loaded is not None
    assert loaded.settings.azp_allowed == ("a", "b", "c")


def test_a_single_azp_never_becomes_an_allowlist_of_its_characters() -> None:
    """The shape phase 21 refuses in the constructor, refused here where it is built."""
    loaded = chain.load_exchange_config(armed())

    assert loaded is not None
    assert loaded.settings.azp_allowed == (AZP,)


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_account_claim_refuses(blank: str) -> None:
    """A variable that stands there and says nothing is a typo, never a request for the
    default: the account claim decides which account an exchanged token acts as."""
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(armed(**{config.ENV_EXCHANGE_ACCOUNT_CLAIM: blank}))

    assert config.ENV_EXCHANGE_ACCOUNT_CLAIM in excinfo.value.message


# --- the mapping profile is configuration with a documented default (MAP-01) ---------------


def test_an_armed_path_without_a_mapping_takes_the_documented_default() -> None:
    """The account id profile: the assumption an installation without an F13 answer is
    least wrong with, because the provider carries the canonical id itself."""
    loaded = chain.load_exchange_config(armed())

    assert loaded is not None
    assert loaded.mapping.strategy == config.DEFAULT_EXCHANGE_MAPPING
    assert loaded.mapping.account_claim == config.DEFAULT_EXCHANGE_ACCOUNT_CLAIM
    assert loaded.mapping.oidc_provider_id is None


def test_the_sub_profile_is_configurable_with_its_provider_id() -> None:
    loaded = chain.load_exchange_config(
        armed(
            **{
                config.ENV_EXCHANGE_MAPPING: mapping.MAPPING_USER_OIDC_SUB_V1,
                config.ENV_EXCHANGE_OIDC_PROVIDER_ID: "7",
            }
        )
    )

    assert loaded is not None
    assert loaded.mapping.strategy == mapping.MAPPING_USER_OIDC_SUB_V1
    assert loaded.mapping.oidc_provider_id == 7
    assert loaded.mapping.account_claim == config.DEFAULT_EXCHANGE_ACCOUNT_CLAIM


def test_the_mapping_carries_the_configured_account_claim() -> None:
    """One value, read once: the claim of the namespace is the claim the mapping reads."""
    loaded = chain.load_exchange_config(
        armed(**{config.ENV_EXCHANGE_ACCOUNT_CLAIM: "nextcloud_uid"})
    )

    assert loaded is not None
    assert loaded.mapping.account_claim == "nextcloud_uid"
    assert loaded.account_claim == "nextcloud_uid"


def test_an_unknown_mapping_name_is_a_refusal_that_names_the_variable() -> None:
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(armed(**{config.ENV_EXCHANGE_MAPPING: "a-secret-profile"}))

    assert config.ENV_EXCHANGE_MAPPING in excinfo.value.message
    assert "a-secret-profile" not in f"{excinfo.value.message} {excinfo.value.hint}"


def test_the_sub_profile_without_a_provider_id_names_the_missing_variable() -> None:
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(
            armed(**{config.ENV_EXCHANGE_MAPPING: mapping.MAPPING_USER_OIDC_SUB_V1})
        )

    assert config.ENV_EXCHANGE_OIDC_PROVIDER_ID in excinfo.value.message


@pytest.mark.parametrize("raw", ["abc", "0", "-1", " "])
def test_an_unusable_provider_id_is_a_refusal_that_names_the_variable(raw: str) -> None:
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(
            armed(
                **{
                    config.ENV_EXCHANGE_MAPPING: mapping.MAPPING_USER_OIDC_SUB_V1,
                    config.ENV_EXCHANGE_OIDC_PROVIDER_ID: raw,
                }
            )
        )

    assert config.ENV_EXCHANGE_OIDC_PROVIDER_ID in excinfo.value.message


def test_a_refused_provider_id_is_never_repeated_in_the_refusal() -> None:
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(
            armed(
                **{
                    config.ENV_EXCHANGE_MAPPING: mapping.MAPPING_USER_OIDC_SUB_V1,
                    config.ENV_EXCHANGE_OIDC_PROVIDER_ID: "a-secret-provider-value",
                }
            )
        )

    assert "a-secret-provider-value" not in f"{excinfo.value.message} {excinfo.value.hint}"


def test_a_provider_id_next_to_the_account_id_profile_is_a_half_state() -> None:
    """A value nobody reads is a half state, refused for the reason ``_optional`` refuses
    an empty variable: the operator believes it does something until somebody measures."""
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(armed(**{config.ENV_EXCHANGE_OIDC_PROVIDER_ID: "7"}))

    assert config.ENV_EXCHANGE_OIDC_PROVIDER_ID in excinfo.value.message


def test_a_mapping_alone_without_the_switch_refuses_the_start() -> None:
    """The new variables stand in ``EXCHANGE_VARIABLES``, so T-22-02 covers them too."""
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config({config.ENV_EXCHANGE_MAPPING: config.DEFAULT_EXCHANGE_MAPPING})

    assert config.ENV_EXCHANGE_ENABLED in excinfo.value.message


# --- every rule of phase 21 arrives as a named refusal -------------------------------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (config.ENV_EXCHANGE_ISSUER, "http://idp.example.org/realms/f13"),
        (config.ENV_EXCHANGE_ISSUER, f"{ISSUER}/"),
        (config.ENV_EXCHANGE_ISSUER, "not-a-url"),
        (config.ENV_EXCHANGE_JWKS_URI, "https://elsewhere.example.org/certs"),
        (config.ENV_EXCHANGE_JWKS_ORIGIN, "http://certs.example.org"),
        (config.ENV_EXCHANGE_ALGORITHMS, "HS256"),
    ],
)
def test_a_rule_of_phase_21_arrives_as_a_tool_error_and_never_as_a_value_error(
    name: str, value: str
) -> None:
    """The rules live in ``exchange.ExchangeSettings`` and are not written a second time
    here. What this module owes is the translation: an operator reads a named refusal in
    the container log, not a bare ``ValueError`` out of a constructor.
    """
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(armed(**{name: value}))

    assert excinfo.value.hint
    assert "NC_MCP_EXCHANGE_" in f"{excinfo.value.message} {excinfo.value.hint}"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (config.ENV_EXCHANGE_ISSUER, "http://idp.secret-tenant.example.org/realms/f13"),
        (config.ENV_EXCHANGE_JWKS_URI, "https://elsewhere.secret-tenant.example.org/certs"),
        (config.ENV_EXCHANGE_ALGORITHMS, "HS256-secret-tenant"),
    ],
)
def test_no_refusal_of_this_module_repeats_the_value_it_read(name: str, value: str) -> None:
    with pytest.raises(ToolError) as excinfo:
        chain.load_exchange_config(armed(**{name: value}))

    assert "secret-tenant" not in f"{excinfo.value.message} {excinfo.value.hint}"


def test_the_reader_reads_the_process_environment_when_no_mapping_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shape every reader of ``config`` has, so that no caller is a special case."""
    for name in config.EXCHANGE_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    assert chain.load_exchange_config() is None

    monkeypatch.setenv(config.ENV_EXCHANGE_ENABLED, "1")
    monkeypatch.setenv(config.ENV_EXCHANGE_ISSUER, ISSUER)
    monkeypatch.setenv(config.ENV_EXCHANGE_AZP, AZP)
    # The address the audience is derived from, set here for the same reason every other
    # armed case of this file sets it: without it the reader refuses (CR-01), and this test
    # is about which mapping is read and not about that refusal.
    monkeypatch.setenv(config.ENV_PUBLIC_URL, PUBLIC_URL)
    loaded = chain.load_exchange_config()

    assert loaded is not None
    assert loaded.settings.issuer == ISSUER


def test_the_configuration_is_frozen() -> None:
    """Nothing downstream may widen an allowlist after the start has accepted it."""
    loaded = chain.load_exchange_config(armed())

    assert loaded is not None
    with pytest.raises(AttributeError):
        loaded.account_claim = "sub"  # type: ignore[misc]


# --- the chain: helpers ------------------------------------------------------------------

JWKS_URL = f"{ISSUER}{chain.DEFAULT_JWKS_PATH}"
AUDIENCE = f"{PUBLIC_URL}{RESOURCE_SUFFIX}"
KID = "key-1"
SUB = "service-account-f13"

#: A value with the shape of a compact JWS and nothing else in it. Every switch case that
#: never gets as far as a signature uses this one, so no case can pass for the wrong reason.
SHAPED_LIKE_A_JWS = "a-header.a-payload.a-signature"

#: What this server issues itself: ``secrets.token_urlsafe`` has no dot in its alphabet.
SHAPED_LIKE_A_STORE_TOKEN = "Rl9TBaUr2vMbqLKGh3dwXcE1nQ6y0ZsA"

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwk_of(private: rsa.RSAPrivateKey, kid: str = KID) -> dict[str, Any]:
    entry = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    entry.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return entry


def serve() -> respx.Route:
    payload = {"keys": [jwk_of(PRIVATE)]}
    return respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=payload))


def exchange_claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    values: dict[str, Any] = {
        "iss": ISSUER,
        "sub": SUB,
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now,
        "typ": "Bearer",
        "azp": AZP,
    }
    values.update(overrides)
    return values


def exchange_token(**overrides: Any) -> str:
    return jwt.encode(
        exchange_claims(**overrides), PRIVATE, algorithm="RS256", headers={"kid": KID}
    )


def configuration(**overrides: str) -> chain.ExchangeConfig:
    loaded = chain.load_exchange_config(armed(**overrides))
    assert loaded is not None
    return loaded


def chained(store: chain.StoreBranch, checker: chain.ExchangeBranch) -> chain.ChainedVerifier:
    return chain.ChainedVerifier(store=store, checker=checker, config=configuration())


def identity(auth_id: str = "an-authorization") -> OAuthIdentity:
    return OAuthIdentity(
        nc_user="alice",
        app_password="an-app-password",
        auth_id=auth_id,
        client_id="a-client",
        principal="alice",
    )


def store_access(token: str) -> AccessToken:
    """What the store branch answers with: an own token, carrying its own claim."""
    return AccessToken(
        token=token,
        client_id="a-client",
        scopes=[TOOL_SCOPE],
        expires_at=int(time.time()) + 300,
        resource=AUDIENCE,
        subject="alice",
        claims={AUTH_ID_CLAIM: "an-authorization"},
    )


class ExplodingStore:
    """A store branch that flies apart the moment it is touched.

    This is what turns "the exchange token never reaches the store" into a measurement: a
    branch that was not supposed to run does not stay silent, it fails the test.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        raise AssertionError("the store branch was asked about a compact JWS")

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        raise AssertionError("the store branch was asked to resolve an exchange token")

    def invalidate(self) -> None:
        raise AssertionError("the store branch was emptied by a test that does not revoke")


class ExplodingChecker:
    """The same stand-in for the other direction: the foreign checker, never called."""

    async def claims_of(self, token: str) -> dict[str, Any]:
        raise AssertionError("the exchange branch was asked about a token of this server")

    def forget_keys(self) -> None:
        raise AssertionError("the exchange branch was emptied by a test that does not revoke")


class RecordingStore:
    """The store branch as far as the chain can see it: what it was asked, what it answered."""

    def __init__(
        self, *, access: AccessToken | None = None, resolved: OAuthIdentity | None = None
    ) -> None:
        self.seen: list[str] = []
        self.asked_to_resolve: list[AccessToken] = []
        self.invalidated = 0
        self._access = access
        self._resolved = resolved

    async def verify_token(self, token: str) -> AccessToken | None:
        self.seen.append(token)
        return self._access

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        self.asked_to_resolve.append(access)
        return self._resolved

    def invalidate(self) -> None:
        self.invalidated += 1


class RecordingChecker:
    """The exchange branch as far as the chain can see it, including its way of refusing."""

    def __init__(
        self, *, claims: dict[str, Any] | None = None, error: Exception | None = None
    ) -> None:
        self.seen: list[str] = []
        self.forgotten = 0
        self._claims = claims
        self._error = error

    async def claims_of(self, token: str) -> dict[str, Any]:
        self.seen.append(token)
        if self._error is not None:
            raise self._error
        return dict(self._claims or exchange_claims())

    def forget_keys(self) -> None:
        self.forgotten += 1


# --- the switch falls on the shape, before any check --------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("abc", False),
        ("a.b.c", True),
        ("a.b", False),
        ("a.b.c.d.e", False),
        ("", False),
        ("a..c", False),
        (".b.c", False),
        ("a.b.", False),
        (SHAPED_LIKE_A_STORE_TOKEN, False),
    ],
)
def test_the_shape_alone_decides_which_branch_sees_a_token(value: str, expected: bool) -> None:
    """Two dots and three non-empty segments, and nothing else is a compact JWS.

    A JWE has four dots and an empty segment is no segment; both go to the store branch,
    where they are refused as unknown tokens and never reach the foreign checker.
    """
    assert chain.looks_like_jws(value) is expected


@pytest.mark.anyio
async def test_a_token_of_this_server_never_reaches_the_exchange_checker() -> None:
    """T-22-06 in the direction that matters most: today's tokens meet no new code."""
    store = RecordingStore(access=store_access(SHAPED_LIKE_A_STORE_TOKEN))
    verifier = chained(store, ExplodingChecker())

    access = await verifier.verify_token(SHAPED_LIKE_A_STORE_TOKEN)

    assert access is not None
    assert store.seen == [SHAPED_LIKE_A_STORE_TOKEN]


@pytest.mark.anyio
async def test_a_compact_jws_never_reaches_the_store() -> None:
    """The other direction of the same switch, with the same kind of proof."""
    checker = RecordingChecker()
    verifier = chained(ExplodingStore(), checker)

    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)

    assert access is not None
    assert checker.seen == [SHAPED_LIKE_A_JWS]


@pytest.mark.anyio
async def test_an_empty_token_is_refused_without_asking_either_branch() -> None:
    verifier = chained(ExplodingStore(), ExplodingChecker())

    assert await verifier.verify_token("") is None


# --- a failure in one branch is never a second try in the other ---------------------------


@pytest.mark.anyio
async def test_a_refused_exchange_token_is_not_offered_to_the_store() -> None:
    """Pitfall 1: the moment one branch becomes the fallback of the other, every unknown
    token is an attempt in foreign code."""
    store = RecordingStore(access=store_access(SHAPED_LIKE_A_JWS))
    checker = RecordingChecker(error=exchange.ExchangeRefused())
    verifier = chain.ChainedVerifier(store=store, checker=checker, config=configuration())

    assert await verifier.verify_token(SHAPED_LIKE_A_JWS) is None
    assert store.seen == [], "the store was asked after the exchange branch refused"


@pytest.mark.anyio
async def test_an_unknown_store_token_is_not_offered_to_the_checker() -> None:
    store = RecordingStore(access=None)
    checker = RecordingChecker()
    verifier = chain.ChainedVerifier(store=store, checker=checker, config=configuration())

    assert await verifier.verify_token(SHAPED_LIKE_A_STORE_TOKEN) is None
    assert checker.seen == [], "the foreign checker was asked after the store refused"


# --- what a checked exchange token becomes ------------------------------------------------


@pytest.mark.anyio
async def test_a_checked_exchange_token_becomes_an_access_token_of_the_acting_party() -> None:
    claims = exchange_claims()
    verifier = chained(RecordingStore(), RecordingChecker(claims=claims))

    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)

    assert access is not None
    assert access.token == SHAPED_LIKE_A_JWS
    assert access.client_id == AZP
    assert access.scopes == [TOOL_SCOPE]
    assert access.expires_at == int(claims["exp"])
    assert access.resource == AUDIENCE


@pytest.mark.anyio
async def test_the_subject_of_an_exchange_token_stays_empty() -> None:
    """Pitfall 5: a raw ``sub`` in this field would be a login name posing as a principal.

    Empty for good since plan 23-02: the identity of a mapped account travels in the request
    state of the transport boundary, never back into the SDK token model.
    """
    verifier = chained(RecordingStore(), RecordingChecker())

    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)

    assert access is not None
    assert access.subject is None


@pytest.mark.anyio
async def test_the_whole_claim_set_travels_under_exactly_one_key() -> None:
    claims = exchange_claims(preferred_username="alex", groups=["a", "b"])
    verifier = chained(RecordingStore(), RecordingChecker(claims=claims))

    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)

    assert access is not None
    assert access.claims == {chain.EXCHANGE_CLAIM: claims}


@pytest.mark.anyio
async def test_a_foreign_auth_id_claim_cannot_reach_the_store_branch() -> None:
    """T-22-07: nested and not spread out, so no foreign claim can pose as one of ours."""
    store = RecordingStore(resolved=identity())
    claims = exchange_claims(**{AUTH_ID_CLAIM: "an-authorization-of-somebody-else"})
    verifier = chained(store, RecordingChecker(claims=claims))

    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)

    assert access is not None
    assert access.claims is not None
    assert AUTH_ID_CLAIM not in access.claims
    assert await verifier.resolve_identity(access) is None
    assert store.asked_to_resolve == []


# --- the identity contract of the transport boundary --------------------------------------


@pytest.mark.anyio
async def test_an_exchange_token_gets_no_identity_without_an_account_source() -> None:
    """Fail closed: the boundary ends a request whose identity source answers ``None``.

    Since plan 23-02 the reason is ``accounts=None`` (T-23-07): a chain without a handed in
    account source is the state after phase 22 and refuses every exchange token, whatever
    the mapping would have said. ``tests/unit/test_oauth_exchange_identity.py`` holds the
    armed half of the same branch.
    """
    store = RecordingStore(resolved=identity())
    verifier = chained(store, RecordingChecker())
    access = await verifier.verify_token(SHAPED_LIKE_A_JWS)

    assert access is not None
    assert await verifier.resolve_identity(access) is None


@pytest.mark.anyio
async def test_a_store_token_resolves_to_whatever_the_store_branch_says() -> None:
    expected = identity()
    store = RecordingStore(access=store_access(SHAPED_LIKE_A_STORE_TOKEN), resolved=expected)
    verifier = chained(store, ExplodingChecker())
    access = await verifier.verify_token(SHAPED_LIKE_A_STORE_TOKEN)

    assert access is not None
    assert await verifier.resolve_identity(access) is expected
    assert store.asked_to_resolve == [access]


def test_the_chain_is_an_identity_source() -> None:
    """Without this the boundary would let an exchange token through without an identity."""
    verifier = chained(RecordingStore(), RecordingChecker())

    assert isinstance(verifier, IdentitySource)


# --- a defect in the new branch is not a defect of the old one ----------------------------


@pytest.mark.anyio
async def test_an_unexpected_exception_of_the_checker_becomes_one_refusal_and_one_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-22-09: fail closed means this one call, and the line names the type and nothing else."""
    store = RecordingStore()
    checker = RecordingChecker(error=RuntimeError("a value nobody may read in a log"))
    verifier = chain.ChainedVerifier(store=store, checker=checker, config=configuration())

    with caplog.at_level(logging.ERROR, logger="mcp_connector.oauth.chain"):
        assert await verifier.verify_token(SHAPED_LIKE_A_JWS) is None

    lines = [record.getMessage() for record in caplog.records]
    assert len(lines) == 1
    assert "RuntimeError" in lines[0]
    assert "a value nobody may read in a log" not in lines[0]
    assert SHAPED_LIKE_A_JWS not in lines[0]
    assert store.seen == []


@pytest.mark.parametrize("missing", ["azp", "exp"])
@pytest.mark.anyio
async def test_a_claim_set_without_the_claims_the_token_is_built_from_is_a_refusal(
    missing: str, caplog: pytest.LogCaptureFixture
) -> None:
    """IN-01: the fail closed catch covers the construction of the token, not only the call.

    The real checker of phase 21 guarantees both claims, but the branch is a protocol and
    the object is whatever a deployment handed in. Built outside the catch, a missing claim
    was a ``KeyError`` travelling out of a verifier, which the transport boundary answers
    with a 500 where a 401 belongs.
    """
    claims = exchange_claims()
    del claims[missing]
    store = RecordingStore()
    checker = RecordingChecker(claims=claims)
    verifier = chain.ChainedVerifier(store=store, checker=checker, config=configuration())

    with caplog.at_level(logging.ERROR, logger="mcp_connector.oauth.chain"):
        assert await verifier.verify_token(SHAPED_LIKE_A_JWS) is None

    lines = [record.getMessage() for record in caplog.records]
    assert len(lines) == 1
    assert "KeyError" in lines[0]
    assert missing not in lines[0], "the line names the type of the failure and nothing else"
    assert store.seen == [], "and the refusal is never offered to the store branch"


@pytest.mark.anyio
async def test_a_broken_exchange_branch_does_not_end_a_call_of_the_existing_path() -> None:
    """The whole point of T-22-09: fail closed, not fail everything."""
    store = RecordingStore(access=store_access(SHAPED_LIKE_A_STORE_TOKEN))
    checker = RecordingChecker(error=MemoryError())
    verifier = chain.ChainedVerifier(store=store, checker=checker, config=configuration())

    assert await verifier.verify_token(SHAPED_LIKE_A_JWS) is None
    assert await verifier.verify_token(SHAPED_LIKE_A_STORE_TOKEN) is not None


# --- one revocation, both layers ----------------------------------------------------------


def test_one_invalidate_reaches_both_layers() -> None:
    store = RecordingStore()
    checker = RecordingChecker()
    verifier = chain.ChainedVerifier(store=store, checker=checker, config=configuration())

    verifier.invalidate()

    assert (store.invalidated, checker.forgotten) == (1, 1)


def test_a_store_branch_that_throws_does_not_keep_the_revocation_from_the_key_set() -> None:
    """WR-04: the keyset half runs even when the store half fails, and the failure travels.

    ``StoreTokenVerifier.invalidate`` is a ``dict.clear`` and cannot throw, but the branch
    is a protocol and the object is whatever a deployment handed in. Without the
    ``finally`` a failure of the first half left a rotated signature key usable for the five
    minutes of the cache, in the very moment somebody revoked.
    """
    checker = RecordingChecker()
    verifier = chain.ChainedVerifier(
        store=ExplodingStore(), checker=checker, config=configuration()
    )

    with pytest.raises(AssertionError):
        verifier.invalidate()

    assert checker.forgotten == 1, "the key set was forgotten although the store half failed"


def test_the_repr_says_that_the_exchange_branch_is_armed_and_no_value() -> None:
    verifier = chained(RecordingStore(), RecordingChecker())

    shown = repr(verifier)

    assert "armed" in shown
    assert ISSUER not in shown
    assert AUDIENCE not in shown


# --- build_chain: the one place the chain is hung in --------------------------------------


def test_the_off_state_hands_back_the_very_same_verifier() -> None:
    """Not an equal object, the same one: byte-identical behaviour is the promise."""
    store = RecordingStore()

    assert chain.build_chain(store, env={}) is store


def test_a_configured_environment_hands_back_a_chain() -> None:
    store = RecordingStore()

    built = chain.build_chain(store, env=armed())

    assert isinstance(built, chain.ChainedVerifier)


def test_a_configuration_that_was_already_read_is_not_read_again() -> None:
    """The reader ran at startup; ``build_chain`` takes its answer instead of the environment."""
    store = RecordingStore()

    built = chain.build_chain(store, env={}, config=configuration())

    assert isinstance(built, chain.ChainedVerifier)


def test_a_half_configured_environment_refuses_at_the_chain_as_well() -> None:
    with pytest.raises(ToolError):
        chain.build_chain(RecordingStore(), env={config.ENV_EXCHANGE_ENABLED: "1"})


def test_an_armed_path_without_a_public_url_refuses_at_the_chain_as_well() -> None:
    """CR-01 travels the way every other half configuration of this module does."""
    with pytest.raises(ToolError) as excinfo:
        chain.build_chain(RecordingStore(), env=dict(ARMED))

    assert config.ENV_PUBLIC_URL in excinfo.value.message


# --- the chain against the real checker ---------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_real_exchange_token_passes_the_chain_and_gets_no_identity() -> None:
    """End to end through the real checker: every rule of phase 21 runs, and the answer is
    still a token without an identity, which the boundary turns into a refusal."""
    serve()
    store = RecordingStore(resolved=identity())
    built = chain.build_chain(store, env=armed())
    assert isinstance(built, chain.ChainedVerifier)

    access = await built.verify_token(exchange_token())

    assert access is not None
    assert access.client_id == AZP
    assert await built.resolve_identity(access) is None
    assert store.seen == []


@respx.mock
@pytest.mark.anyio
async def test_a_real_token_of_another_issuer_is_refused_by_the_chain() -> None:
    serve()
    built = chain.build_chain(RecordingStore(), env=armed())
    assert isinstance(built, chain.ChainedVerifier)

    assert (
        await built.verify_token(exchange_token(iss="https://idp.example.org/realms/other")) is None
    )


@respx.mock
@pytest.mark.anyio
async def test_one_invalidate_costs_the_real_chain_one_new_key_set_fetch() -> None:
    """The two halves of the revocation measured together, at the outgoing requests."""
    route = serve()
    store = RecordingStore()
    built = chain.build_chain(store, env=armed())
    assert isinstance(built, chain.ChainedVerifier)
    assert await built.verify_token(exchange_token()) is not None
    assert route.call_count == 1

    built.invalidate()

    assert await built.verify_token(exchange_token()) is not None
    assert route.call_count == 2
    assert store.invalidated == 1


# --- the built application, from the bearer to the refusal --------------------------------


def standalone_env(tmp_path: Path) -> dict[str, str]:
    """The standalone deployment of ``entry_oauth`` with the exchange path armed.

    The public URL is the one of this file, so the default audience of the namespace is the
    resource URL a token has to name and nothing has to be configured twice.
    """
    storage = tmp_path / "storage"
    storage.mkdir()
    storage.chmod(0o700)
    key_file = tmp_path / "key"
    key_file.write_text("ab" * 32)
    key_file.chmod(0o600)
    return {
        config.ENV_URL: "http://nc.test",
        config.ENV_AUTH_MODE: config.AUTH_MODE_OAUTH,
        config.ENV_PUBLIC_URL: PUBLIC_URL,
        config.ENV_OAUTH_STORAGE_DIR: str(storage),
        config.ENV_OAUTH_DATA_KEY_FILE: str(key_file),
        config.ENV_OIDC_ISSUER: "https://idp.example.com",
        config.ENV_OIDC_CLIENT_ID: "the-client-id",
        config.ENV_OIDC_PROVIDER_ID: "7",
        config.ENV_OIDC_MAPPING: oidc.STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1,
        **ARMED,
    }


@respx.mock
def test_a_token_that_passes_every_rule_still_ends_at_the_boundary_with_401(
    tmp_path: Path,
) -> None:
    """EXCH-04 end to end: checked is not served, because no account source is wired in.

    The key set is fetched, which is the proof that the token was not turned away by a
    cheap rule before the signature: it went through the whole checker and was refused at
    the boundary because the entry points hand no account source into ``build_chain`` yet.
    Whoever makes this test go green by wiring one in has done plan 23-03 or 23-04 early:
    the wiring belongs to those plans, not to the entry points of today.
    """
    route = serve()
    app = entry_oauth.build_oauth_app(standalone_env(tmp_path))

    with TestClient(app, base_url=PUBLIC_URL) as client:
        response = client.post(
            "/mcp",
            json={},
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {exchange_token()}",
            },
        )

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    assert route.call_count == 1, "the token was refused before the signature was checked"


# --- the shape rule, read out of the header of a request (EXCH-05) ------------------------


def asking(header: str | None) -> Request:
    """One request, with an ``Authorization`` header or without one.

    A hand built scope and not a client: the condition of the throttle wrapper is asked
    before anything else about a request is read, and building it here is what keeps this
    test on the one thing it measures, the reading of that header.
    """
    headers = [(b"authorization", header.encode())] if header is not None else []
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/mcp",
            "query_string": b"",
            "headers": headers,
            "client": ("10.0.0.1", 55555),
        }
    )


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer a.b.c", True),
        ("bearer a.b.c", True),
        ("BEARER a.b.c", True),
        ("Bearer abc", False),
        ("Basic a.b.c", False),
        ("Bearer ", False),
        ("", False),
        (None, False),
    ],
)
def test_only_a_jws_shaped_bearer_is_a_request_of_the_exchange_path(
    header: str | None, expected: bool
) -> None:
    """The scheme is read case insensitively, like the transport boundary reads it."""
    assert chain.exchange_shaped_request(asking(header)) is expected


def test_the_condition_of_the_throttle_is_the_switch_of_the_verifier_itself() -> None:
    """One form rule, read in two places and written in one (T-22-06 and EXCH-05).

    A second spelling of "this looks like a foreign token" next to the counter would drift
    from this one the first time either is corrected, and a throttle that counts a different
    set of requests than the one it bounds is worse than no throttle at all.
    """
    for token in ("a.b.c", "abc", "", "a.b.c.d.e", "a..c", "a.b"):
        assert chain.exchange_shaped_request(asking(f"Bearer {token}")) is chain.looks_like_jws(
            token
        )


# --- the other half of that rule: how the header is read (WR-03) --------------------------


class CapturingVerifier:
    """A verifier that records the token the boundary handed it and accepts nothing.

    ``None`` from :meth:`verify_token` is what a refused bearer looks like, so the boundary
    behaves exactly as it does against an unknown token. What this exists for is the one
    value nothing else exposes: what the boundary extracted out of the header, if anything.
    """

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def verify_token(self, token: str) -> AccessToken | None:
        self.seen.append(token)
        return None

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        del access
        return None


#: Header forms the end to end cases never reach: the separator is something other than one
#: plain space, or there is nothing behind the scheme at all. They are where two hand written
#: readings of the same rule drift apart first.
BEARER_FORMS = (
    "Bearer a.b.c",
    "bearer a.b.c",
    "BEARER a.b.c",
    "Bearer\ta.b.c",
    "Bearer  a.b.c",
    "Bearer \t a.b.c",
    "Bearera.b.c",
    "Bearer",
    "Bearer ",
    "Bearer   ",
    " Bearer a.b.c",
    "\tBearer a.b.c",
    "Bearer a.b.c ",
    "Bearer ä.b.c",
    "Bearer .",
    "Bearer a.b.c.d",
    "Basic a.b.c",
    "Bearer abc",
)


@pytest.mark.parametrize("header", BEARER_FORMS)
@pytest.mark.anyio
async def test_the_throttle_and_the_transport_boundary_read_the_same_bearer(header: str) -> None:
    """WR-03: the two hand written readings of one header rule, held against each other.

    ``looks_like_jws`` exists exactly once and the test above holds the throttle to it. The
    other half of the same condition, getting the credential out of the header, is written
    twice: privately in ``exapp/middleware.py`` and as an acknowledged copy in
    ``chain._BEARER_PREFIX``. They are character for character the same today, and nothing
    but this test keeps them that way. If the boundary ever grew a more tolerant separator,
    the throttle would count a different set of requests than the one the boundary sends
    into the exchange branch, which is the case the docstring of ``exchange_shaped_request``
    calls worse than no throttle at all.

    What is compared is measured on both sides: the boundary is the real
    :class:`RequireOAuthBearer` and the token it extracted is the one it handed its
    verifier. The rule is nowhere written a third time here.
    """
    verifier = CapturingVerifier()
    guard = RequireOAuthBearer(_unreachable_app, {}, token_verifier=verifier)

    await guard._bearer_is_valid(asking(header))

    extracted = verifier.seen[0] if verifier.seen else None
    boundary_says = extracted is not None and chain.looks_like_jws(extracted)
    assert chain.exchange_shaped_request(asking(header)) is boundary_says


async def _unreachable_app(scope: Any, receive: Any, send: Any) -> None:
    """The application behind the boundary, which this test never gets as far as."""
    del scope, receive, send
    raise AssertionError("the bearer check passed a request through")


# --- the throttle of the exchange path, measured on the built application (EXCH-05) --------


def mcp_call(client: TestClient, header: str | None) -> Any:
    """One MCP request, with the ``Authorization`` a case needs or with none at all."""
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if header is not None:
        headers["Authorization"] = header
    return client.post("/mcp", json={}, headers=headers)


@respx.mock
def test_repeated_exchange_refusals_end_in_429_while_the_existing_path_is_untouched(
    tmp_path: Path,
) -> None:
    """The bound of EXCH-05, and the promise around it, in one measurement.

    ``Bearer a.b.c`` has the shape of the exchange path and fails at its unreadable header,
    so the counting is provable without a single outgoing fetch: the key set route is
    registered and stays at zero calls. After the limit the same caller is answered with a
    429 and a ``Retry-After``, while two requests that are not of this path are served
    exactly as they are today, in the very state an attacker produced.
    """
    keys = serve()
    app = entry_oauth.build_oauth_app(standalone_env(tmp_path))

    with TestClient(app, base_url=PUBLIC_URL) as client:
        refused = [
            mcp_call(client, "Bearer a.b.c").status_code
            for _attempt in range(throttle.EXCHANGE_LIMIT)
        ]
        throttled = mcp_call(client, "Bearer a.b.c")
        dotless = mcp_call(client, "Bearer a-token-this-server-issued-itself")
        without_a_header = mcp_call(client, None)

    assert refused == [401] * throttle.EXCHANGE_LIMIT
    assert throttled.status_code == 429
    assert int(throttled.headers["Retry-After"]) > 0
    assert keys.call_count == 0, "an unreadable header never costs an outgoing fetch"

    assert dotless.status_code == 401, "the exception of the MCP route holds for our own tokens"
    assert without_a_header.status_code == 401


@respx.mock
def test_the_429_of_the_exchange_path_names_no_check_that_failed(tmp_path: Path) -> None:
    """T-22-15: the same body as on every other machine route, and no hint in it."""
    serve()
    app = entry_oauth.build_oauth_app(standalone_env(tmp_path))

    with TestClient(app, base_url=PUBLIC_URL) as client:
        for _attempt in range(throttle.EXCHANGE_LIMIT):
            mcp_call(client, "Bearer a.b.c")
        throttled = mcp_call(client, "Bearer a.b.c")

    assert throttled.status_code == 429
    assert throttled.json()["error"] == "temporarily_unavailable"
    spoken = throttled.text.lower()
    for word in ("exchange", "signature", "issuer", "audience", "claim", "key"):
        assert word not in spoken

"""The token verifier of the transport boundary: one store lookup, two checks, one cache.

This is the half of the phase that runs on every single tool call, so the checks here are
the ones that decide whether a token that exists is a token that may act. Three of them are
ours and not the SDK's: the audience of RFC 8707, the client policy of AUTH-07, and the
refusal of anything the store cannot answer for.

Threats covered here: T-03-51 (a token issued for another MCP server), T-03-54 (a token in
a log record), T-03-55 (a client blocked after its token was issued) and T-03-56 (a store
that is not reachable).

No Nextcloud, no container and no network: the store is a SQLite file in ``tmp_path`` and
the clock of the cache is a parameter.
"""

import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path

import pytest
from mcp.server.auth.provider import AccessToken
from mcp.shared.auth import OAuthClientInformationFull

from mcp_connector import config
from mcp_connector.exapp.target import exapp_target
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import registry
from mcp_connector.oauth import verifier as verifier_module
from mcp_connector.oauth.metadata import TOOL_SCOPE
from mcp_connector.oauth.store import ACCESS_TOKEN_TTL, VALIDATION_CACHE_TTL, OAuthStore

PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
BASE_URL = "http://nc.test"
RESOURCE = f"{PUBLIC_URL}/mcp"
FOREIGN_RESOURCE = "https://other.example.com/mcp"

CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
AUTH_ID = "the-flow-this-authorization-was-born-in"
FAMILY_ID = "the-family-of-this-connection"
NC_USER = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
TOKEN = "the-access-token-of-this-connection"
CLIENT_NAME = "Claude"

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

ENV = {
    config.ENV_PUBLIC_URL: PUBLIC_URL,
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.1.0",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
}

REGISTRATION = OAuthClientInformationFull.model_validate(
    {
        "client_id": CLIENT_ID,
        "client_name": CLIENT_NAME,
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": TOOL_SCOPE,
    }
).model_dump_json(exclude={"client_secret"})

#: The same registration without the optional name: dynamic client registration does not
#: require one, so the nameless client is a case and not an anomaly.
REGISTRATION_WITHOUT_NAME = OAuthClientInformationFull.model_validate(
    {
        "client_id": CLIENT_ID,
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": TOOL_SCOPE,
    }
).model_dump_json(exclude={"client_secret"})


class CountingStore(OAuthStore):
    """The same store, counting what the verifier asks it for."""

    def __init__(self, path: Path, key: bytes) -> None:
        super().__init__(path, key)
        self.lookups = 0

    async def load_access_token(self, token: str, *, now: int | None = None):  # type: ignore[override]
        self.lookups += 1
        return await super().load_access_token(token, now=now)


class BrokenStore(CountingStore):
    """A store that cannot answer. Fail closed means this is a refusal, not a pass."""

    async def load_access_token(self, token: str, *, now: int | None = None):  # type: ignore[override]
        self.lookups += 1
        raise RuntimeError("the volume is gone")


class Clock:
    """A clock a test can move, so the cache window needs no sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def build(
    tmp_path: Path,
    *,
    store: CountingStore | None = None,
    clock: Callable[[], float] | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[verifier_module.StoreTokenVerifier, CountingStore]:
    """A verifier and the store behind it, sharing the policy of one environment."""
    subject = store if store is not None else CountingStore(tmp_path / "oauth.sqlite3", KEY)
    environment = ENV | dict(env or {})

    async def opener() -> OAuthStore:
        return subject

    provider = provider_module.NextcloudOAuthProvider(
        nextcloud=exapp_target(environment),
        env=environment,
        policy=registry.client_policy(environment),
        store_provider=opener,
    )
    built = verifier_module.StoreTokenVerifier(
        env=environment,
        store_provider=opener,
        get_client=provider.get_client,
        clock=clock,
    )
    return built, subject


async def seed(
    store: OAuthStore,
    *,
    resource: str = RESOURCE,
    allowed: bool = True,
    issued_at: int | None = None,
    registration: str = REGISTRATION,
) -> None:
    """One registered client, one authorization and one access token of that connection."""
    await store.save_client(CLIENT_ID, metadata_json=registration, allowed=allowed)
    await store.touch_client(CLIENT_ID)
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        app_password=APP_PASSWORD,
        scopes=TOOL_SCOPE,
        resource=resource,
    )
    await store.create_access_token(
        TOKEN,
        auth_id=AUTH_ID,
        family_id=FAMILY_ID,
        scopes=TOOL_SCOPE,
        resource=resource,
        now=issued_at,
    )


# --- what a token has to be for this server to act on it -----------------------------------


@pytest.mark.anyio
async def test_a_valid_token_carries_the_nextcloud_user_and_its_audience(
    tmp_path: Path,
) -> None:
    subject, store = build(tmp_path)
    await seed(store)

    access = await subject.verify_token(TOKEN)

    assert access is not None
    assert access.subject == NC_USER, "the identity of the tool call, and nothing else"
    assert access.client_id == CLIENT_ID
    assert access.resource == RESOURCE
    assert access.scopes == [TOOL_SCOPE]
    assert access.expires_at is not None


@pytest.mark.anyio
@pytest.mark.parametrize("token", ["", "never-issued", TOKEN + "x"])
async def test_a_token_this_server_never_issued_is_refused(tmp_path: Path, token: str) -> None:
    subject, store = build(tmp_path)
    await seed(store)

    assert await subject.verify_token(token) is None


@pytest.mark.anyio
async def test_an_expired_token_is_refused(tmp_path: Path) -> None:
    subject, store = build(tmp_path)
    await seed(store, issued_at=int(time.time()) - ACCESS_TOKEN_TTL - 60)

    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_a_revoked_family_is_refused(tmp_path: Path) -> None:
    subject, store = build(tmp_path)
    await seed(store)
    await store.revoke_family(FAMILY_ID)

    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_a_revoked_authorization_is_refused(tmp_path: Path) -> None:
    """SC 4: a connection the user ended stops working, without waiting for the token."""
    subject, store = build(tmp_path)
    await seed(store)
    await store.revoke_authorization(AUTH_ID)

    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_a_token_of_another_resource_is_refused_although_it_exists(
    tmp_path: Path,
) -> None:
    """T-03-51: the confused deputy this check exists against (RFC 8707, pitfall 3)."""
    subject, store = build(tmp_path)
    await seed(store, resource=FOREIGN_RESOURCE)

    row = await store.load_access_token(TOKEN)
    assert row is not None, "the token is in the store and has not expired"
    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_a_token_without_a_resource_is_refused(tmp_path: Path) -> None:
    subject, store = build(tmp_path)
    await seed(store, resource="")

    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_a_client_blocked_after_the_token_was_issued_is_refused(tmp_path: Path) -> None:
    """T-03-55, pitfall 9: the fourth enforcement point of AUTH-07 is this one."""
    subject, store = build(tmp_path)
    await seed(store)
    await store.save_client(CLIENT_ID, metadata_json=REGISTRATION, allowed=False)

    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_a_client_that_is_not_on_the_allowlist_is_refused(tmp_path: Path) -> None:
    subject, store = build(tmp_path, env={registry.ENV_ALLOWLIST_ONLY: "1"})
    await seed(store)

    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_a_store_that_cannot_answer_refuses_and_never_passes(tmp_path: Path) -> None:
    """T-03-56, D-37: an unreachable store is a refusal, not an open door."""
    broken = BrokenStore(tmp_path / "oauth.sqlite3", KEY)
    subject, store = build(tmp_path, store=broken)
    await seed(store)

    assert await subject.verify_token(TOKEN) is None
    assert broken.lookups == 1, "it was asked, and the failure did not become a pass"


# --- the cache -----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_two_checks_inside_the_cache_window_are_one_store_lookup(tmp_path: Path) -> None:
    """SC 5: the store must not sit in the hot path of every tool call."""
    clock = Clock()
    subject, store = build(tmp_path, clock=clock)
    await seed(store)

    first = await subject.verify_token(TOKEN)
    store.lookups = 0
    second = await subject.verify_token(TOKEN)

    assert first is not None
    assert second is not None
    assert second.subject == NC_USER
    assert store.lookups == 0


@pytest.mark.anyio
async def test_after_the_cache_window_the_store_is_asked_again(tmp_path: Path) -> None:
    """D-34: a revocation has to take effect, so the window is short and it ends."""
    clock = Clock()
    subject, store = build(tmp_path, clock=clock)
    await seed(store)

    await subject.verify_token(TOKEN)
    store.lookups = 0
    clock.now += VALIDATION_CACHE_TTL + 1
    await subject.verify_token(TOKEN)

    assert store.lookups == 1


@pytest.mark.anyio
async def test_a_revocation_inside_the_process_takes_effect_at_once(tmp_path: Path) -> None:
    """The hook plan 03-07 uses: a revoked connection must not live out the cache window."""
    clock = Clock()
    subject, store = build(tmp_path, clock=clock)
    await seed(store)

    await subject.verify_token(TOKEN)
    await store.revoke_authorization(AUTH_ID)
    subject.invalidate()

    assert await subject.verify_token(TOKEN) is None


@pytest.mark.anyio
async def test_only_a_valid_token_is_ever_cached(tmp_path: Path) -> None:
    """A negative answer that is cached is a token that stays refused after it was fixed."""
    clock = Clock()
    subject, store = build(tmp_path, clock=clock)
    await store.save_client(CLIENT_ID, metadata_json=REGISTRATION)

    assert await subject.verify_token(TOKEN) is None
    await seed(store)

    assert await subject.verify_token(TOKEN) is not None


@pytest.mark.anyio
async def test_the_cache_cannot_grow_without_a_bound(tmp_path: Path) -> None:
    """A dictionary that grows with every presented token is a denial of service."""
    clock = Clock()
    subject, store = build(tmp_path, clock=clock)
    await seed(store)

    for _ in range(verifier_module.CACHE_LIMIT + 10):
        await subject.verify_token(TOKEN)
        clock.now += 0.001

    assert len(subject._cache) <= verifier_module.CACHE_LIMIT


# --- from the token to the Nextcloud identity ----------------------------------------------


@pytest.mark.anyio
async def test_the_identity_of_a_token_is_the_user_and_the_app_password(tmp_path: Path) -> None:
    subject, store = build(tmp_path)
    await seed(store)
    access = await subject.verify_token(TOKEN)
    assert access is not None

    identity = await subject.resolve_identity(access)

    assert identity is not None
    assert identity.nc_user == NC_USER
    assert identity.app_password == APP_PASSWORD
    assert identity.client_id == CLIENT_ID
    assert identity.auth_id == AUTH_ID
    assert identity.revoked is False
    assert APP_PASSWORD not in repr(identity), "the credential is masked like every other"


@pytest.mark.anyio
async def test_the_identity_carries_the_registered_name_of_its_client(tmp_path: Path) -> None:
    """The name rides in the claim of the token, so no lookup is added to the hot path."""
    subject, store = build(tmp_path)
    await seed(store)
    access = await subject.verify_token(TOKEN)
    assert access is not None
    assert access.claims is not None
    assert access.claims[verifier_module.CLIENT_NAME_CLAIM] == CLIENT_NAME

    identity = await subject.resolve_identity(access)

    assert identity is not None
    assert identity.client_name == CLIENT_NAME
    assert CLIENT_NAME in repr(identity), "the name is not a secret and stays readable"
    assert APP_PASSWORD not in repr(identity)
    assert "app_password='***'" in repr(identity), "the credential is masked as before"


@pytest.mark.anyio
async def test_a_client_without_a_name_becomes_an_empty_string_and_never_none(
    tmp_path: Path,
) -> None:
    """A reader of the log never has to tell "no name" from "no field" apart."""
    subject, store = build(tmp_path)
    await seed(store, registration=REGISTRATION_WITHOUT_NAME)
    access = await subject.verify_token(TOKEN)
    assert access is not None

    identity = await subject.resolve_identity(access)

    assert identity is not None
    assert identity.client_name == ""


@pytest.mark.anyio
async def test_a_revoked_connection_is_reported_as_revoked_and_not_as_a_credential(
    tmp_path: Path,
) -> None:
    """The one case the credential layer turns into "connect the app again"."""
    subject, store = build(tmp_path)
    await seed(store)
    access = await subject.verify_token(TOKEN)
    assert access is not None
    await store.revoke_authorization(AUTH_ID)

    identity = await subject.resolve_identity(access)

    assert identity is not None
    assert identity.revoked is True


@pytest.mark.anyio
async def test_an_identity_of_an_authorization_that_is_gone_is_none(tmp_path: Path) -> None:
    subject, store = build(tmp_path)
    await seed(store)
    access = await subject.verify_token(TOKEN)
    assert access is not None
    await store.delete_authorization(AUTH_ID)

    assert await subject.resolve_identity(access) is None


@pytest.mark.anyio
async def test_an_access_token_without_our_own_claim_has_no_identity(tmp_path: Path) -> None:
    """A token of another verifier is not one this credential layer may act on."""
    subject, _store = build(tmp_path)

    foreign = AccessToken(token="x", client_id=CLIENT_ID, scopes=[TOOL_SCOPE], subject=NC_USER)

    assert await subject.resolve_identity(foreign) is None


# --- the properties every check of this module has ------------------------------------------


@pytest.mark.anyio
async def test_no_verification_writes_a_token_or_a_credential_into_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T-03-54: not on DEBUG, not truncated, not in the successful case either."""
    subject, store = build(tmp_path)
    await seed(store)

    with caplog.at_level(logging.DEBUG):
        access = await subject.verify_token(TOKEN)
        assert access is not None
        await subject.resolve_identity(access)
        await subject.verify_token("a-stolen-token")

    assert TOKEN not in caplog.text
    assert "a-stolen-token" not in caplog.text
    assert APP_PASSWORD not in caplog.text


def test_the_verifier_compares_in_constant_time() -> None:
    """T-01-24, inherited: a plain == on attacker input leaks its prefix over enough tries."""
    source = inspect.getsource(verifier_module)

    assert source.count("compare_digest") >= 1


@pytest.mark.anyio
async def test_no_token_ever_appears_in_the_repr_of_the_verifier(tmp_path: Path) -> None:
    """A repr ends up in a log record the moment somebody adds a debug line (T-03-54)."""
    subject, store = build(tmp_path)
    await seed(store)

    await subject.verify_token(TOKEN)

    assert TOKEN not in repr(subject)
    assert TOKEN not in repr(subject._cache), "the cache is keyed by the digest, never by the token"


@pytest.mark.anyio
async def test_the_verifier_answers_the_sdk_protocol(tmp_path: Path) -> None:
    """It is handed to the transport boundary as a ``TokenVerifier`` and nothing else."""
    subject, store = build(tmp_path)
    await seed(store)

    check: Callable[[str], Awaitable[AccessToken | None]] = subject.verify_token

    assert await check(TOKEN) is not None
    assert isinstance(subject, verifier_module.IdentitySource)

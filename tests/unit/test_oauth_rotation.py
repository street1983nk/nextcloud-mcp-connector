"""The refresh rotation: one use, one successor, and the two sides of the grace window.

This is the half of the authorization server that decides what a stolen refresh token is
worth and what a flaky network costs. Both answers live in the same method, and they pull
in opposite directions: reuse detection wants every second use to be an attack, while a
connector that refreshes reactively on a 401 *and* proactively five minutes before the
expiry produces a second use of the same token as a matter of course (03-RESEARCH.md,
pitfall 10). D-41 resolves it with ten seconds: inside the window the same token is
answered with the same successor and no second branch of the family is created, outside it
every reuse revokes the whole family.

Threats covered here: T-03-60 (a stolen refresh token that never stops working), T-03-61
(a network retry that kills a healthy session), T-03-62 (a revoked token that survives in
the process cache), T-03-67 (an unbounded set of held answers) and T-03-58 (a Nextcloud
round trip in the token path).

The clock is a parameter and no test ever sleeps: the provider reads it and hands the same
moment to the store, so both sides of the window are exact instead of timing dependent.
Nothing here opens a socket; the store is a SQLite file in ``tmp_path``.
"""

import asyncio
import base64
import hashlib
import inspect
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
import respx
from mcp.server.auth.provider import RefreshToken, TokenError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from mcp_connector import config
from mcp_connector.exapp.target import exapp_target
from mcp_connector.oauth import provider as provider_module
from mcp_connector.oauth import registry
from mcp_connector.oauth import verifier as verifier_module
from mcp_connector.oauth.metadata import TOOL_SCOPE
from mcp_connector.oauth.store import (
    REFRESH_TOKEN_TTL,
    ROTATION_GRACE,
    STATE_ACTIVE,
    STATE_REVOKED,
    OAuthStore,
    token_hash,
)

PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
BASE_URL = "http://nc.test"
RESOURCE = f"{PUBLIC_URL}/mcp"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"
AUTH_ID = "the-flow-this-authorization-was-born-in"
NC_USER = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
CODE = "the-authorization-code-of-this-consent"
VERIFIER = "a-code-verifier-of-the-client-that-is-long-enough"
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

ENV = {
    config.ENV_PUBLIC_URL: PUBLIC_URL,
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.1.0",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
}


class Clock:
    """A clock a test moves by hand, in the shape ``test_oauth_verifier.py`` uses."""

    def __init__(self, start: float | None = None) -> None:
        self.now = float(int(time.time())) if start is None else start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def opener(subject: OAuthStore) -> Callable[[], Awaitable[OAuthStore]]:
    async def open_it() -> OAuthStore:
        return subject

    return open_it


def registration(secret: str | None = None) -> OAuthClientInformationFull:
    return OAuthClientInformationFull.model_validate(
        {
            "client_id": CLIENT_ID,
            "client_secret": secret,
            "client_name": "Claude",
            "redirect_uris": [REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none" if secret is None else "client_secret_post",
            "scope": TOOL_SCOPE,
        }
    )


def build(
    tmp_path: Path, *, clock: Clock | None = None, **env: str
) -> tuple[provider_module.NextcloudOAuthProvider, OAuthStore]:
    store = OAuthStore(tmp_path / "oauth.sqlite3", KEY)
    policy = registry.client_policy(ENV | env)
    subject = provider_module.NextcloudOAuthProvider(
        nextcloud=exapp_target(ENV | env),
        env=ENV | env,
        policy=policy,
        store_provider=opener(store),
        clock=clock,
    )
    return subject, store


async def connected(
    tmp_path: Path, *, clock: Clock | None = None, resource: str = RESOURCE, **env: str
) -> tuple[provider_module.NextcloudOAuthProvider, OAuthStore, OAuthToken]:
    """A client that walked the whole flow once, so a real refresh token exists."""
    subject, store = build(tmp_path, clock=clock, **env)
    await subject.register_client(registration())
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        app_password=APP_PASSWORD,
        scopes=TOOL_SCOPE,
        resource=resource,
    )
    await store.create_auth_code(
        CODE, auth_id=AUTH_ID, redirect_uri=REDIRECT, code_challenge=CHALLENGE, resource=resource
    )
    code = await subject.load_authorization_code(registration(), CODE)
    assert code is not None
    issued = await subject.exchange_authorization_code(registration(), code)
    return subject, store, issued


async def refresh(subject: provider_module.NextcloudOAuthProvider, token: str | None) -> OAuthToken:
    """One refresh, in the shape the SDK token handler builds it."""
    assert token is not None
    grant = RefreshToken(token=token, client_id=CLIENT_ID, scopes=[TOOL_SCOPE])
    return await subject.exchange_refresh_token(registration(), grant, [TOOL_SCOPE])


def refresh_rows(store: OAuthStore) -> list[tuple[str, str, str | None]]:
    """Every refresh row of the file, so a second branch of a family cannot hide."""
    conn = sqlite3.connect(store.path)
    try:
        return list(conn.execute("SELECT token_hash, state, successor FROM refresh_tokens"))
    finally:
        conn.close()


def access_states(store: OAuthStore) -> list[int | None]:
    conn = sqlite3.connect(store.path)
    try:
        return [row[0] for row in conn.execute("SELECT revoked_at FROM access_tokens")]
    finally:
        conn.close()


# --- the ordinary rotation ---------------------------------------------------------------


@pytest.mark.anyio
async def test_a_first_redemption_issues_a_successor_of_the_same_family(tmp_path: Path) -> None:
    subject, store, issued = await connected(tmp_path)

    rotated = await refresh(subject, issued.refresh_token)

    assert rotated.access_token != issued.access_token
    assert rotated.refresh_token != issued.refresh_token
    assert rotated.token_type == "Bearer"
    assert rotated.scope == TOOL_SCOPE

    rows = {digest: (state, successor) for digest, state, successor in refresh_rows(store)}
    old = rows[token_hash(issued.refresh_token or "")]
    assert old[0] == "used", "the presented token is spent by the rotation"
    assert old[1] == token_hash(rotated.refresh_token or ""), "and points at its successor"
    assert rows[token_hash(rotated.refresh_token or "")][0] == STATE_ACTIVE


@pytest.mark.anyio
async def test_the_new_pair_stays_inside_the_family_of_the_connection(tmp_path: Path) -> None:
    """One connection is one family, whatever the number of rotations."""
    subject, store, issued = await connected(tmp_path)

    await refresh(subject, issued.refresh_token)

    conn = sqlite3.connect(store.path)
    try:
        families = {
            row[0]
            for row in conn.execute(
                "SELECT family_id FROM refresh_tokens UNION SELECT family_id FROM access_tokens"
            )
        }
    finally:
        conn.close()
    assert len(families) == 1


@pytest.mark.anyio
async def test_a_rotated_token_still_acts_as_the_user_who_consented(tmp_path: Path) -> None:
    subject, store, issued = await connected(tmp_path)

    rotated = await refresh(subject, issued.refresh_token)

    row = await store.load_access_token(rotated.access_token)
    assert row is not None
    assert row.nc_user == NC_USER
    assert row.resource == RESOURCE


@pytest.mark.anyio
async def test_the_rotation_marks_the_registration_as_used(tmp_path: Path) -> None:
    """A refresh is a sign of life, so the registration must not expire under a client."""
    clock = Clock()
    subject, store, issued = await connected(tmp_path, clock=clock)
    first = await store.load_client(CLIENT_ID)
    clock.advance(60)

    await refresh(subject, issued.refresh_token)

    second = await store.load_client(CLIENT_ID)
    assert first is not None
    assert second is not None
    assert first.last_used_at is not None
    assert second.last_used_at is not None
    assert second.last_used_at > first.last_used_at


# --- the grace window of D-41 ------------------------------------------------------------


@pytest.mark.anyio
async def test_a_retry_inside_the_window_repeats_the_same_answer(tmp_path: Path) -> None:
    """T-03-61: a network retry of a connector must not cost the user their session."""
    clock = Clock()
    subject, store, issued = await connected(tmp_path, clock=clock)

    first = await refresh(subject, issued.refresh_token)
    clock.advance(ROTATION_GRACE - 1)
    second = await refresh(subject, issued.refresh_token)

    assert second == first, "the same answer, not a new one"
    assert len(refresh_rows(store)) == 2, "no second successor was created"
    assert all(state != STATE_REVOKED for _digest, state, _successor in refresh_rows(store))


@pytest.mark.anyio
async def test_a_retry_inside_the_window_creates_no_second_branch_of_the_family(
    tmp_path: Path,
) -> None:
    clock = Clock()
    subject, store, issued = await connected(tmp_path, clock=clock)

    first = await refresh(subject, issued.refresh_token)
    clock.advance(1)
    await refresh(subject, issued.refresh_token)
    clock.advance(1)
    await refresh(subject, issued.refresh_token)

    successors = {
        successor for _digest, _state, successor in refresh_rows(store) if successor is not None
    }
    assert successors == {token_hash(first.refresh_token or "")}
    assert len(access_states(store)) == 2, "no second access token was issued either"


@pytest.mark.anyio
async def test_a_replay_after_the_window_kills_the_whole_family(tmp_path: Path) -> None:
    """T-03-60: outside the window a second use is a theft, and it costs the family."""
    clock = Clock()
    subject, store, issued = await connected(tmp_path, clock=clock)

    await refresh(subject, issued.refresh_token)
    clock.advance(ROTATION_GRACE + 1)

    with pytest.raises(TokenError) as raised:
        await refresh(subject, issued.refresh_token)

    assert raised.value.error == "invalid_grant"
    assert all(state == STATE_REVOKED for _digest, state, _successor in refresh_rows(store))
    assert all(revoked is not None for revoked in access_states(store))


@pytest.mark.anyio
async def test_after_the_family_died_every_token_of_it_is_refused(tmp_path: Path) -> None:
    """The kill has to reach the tool call, not only the token endpoint."""
    clock = Clock()
    subject, store, issued = await connected(tmp_path, clock=clock)
    rotated = await refresh(subject, issued.refresh_token)
    clock.advance(ROTATION_GRACE + 1)

    with pytest.raises(TokenError):
        await refresh(subject, issued.refresh_token)

    checker = verifier_module.StoreTokenVerifier(
        store_provider=opener(store), get_client=subject.get_client, env=ENV
    )
    assert await checker.verify_token(issued.access_token) is None
    assert await checker.verify_token(rotated.access_token) is None
    with pytest.raises(TokenError):
        await refresh(subject, rotated.refresh_token)


@pytest.mark.anyio
async def test_the_grace_window_is_a_named_constant_that_names_its_decision() -> None:
    """A ten that only exists as a literal is a ten nobody finds when it has to change."""
    assert ROTATION_GRACE == 10
    source = inspect.getsource(provider_module)
    assert "ROTATION_GRACE" in source
    assert "D-41" in source, "the deliberate softening is named where it is implemented"


@pytest.mark.anyio
async def test_a_held_answer_that_is_gone_is_a_refusal_and_not_a_family_kill(
    tmp_path: Path,
) -> None:
    """The held answers are a cache with a lifetime of seconds, not session state (SRV-05).

    Losing them (a restart, the hard ceiling) may cost a retry its answer; it must never
    turn that retry into the reuse detection.
    """
    clock = Clock()
    subject, store, issued = await connected(tmp_path, clock=clock)
    await refresh(subject, issued.refresh_token)
    subject._held.clear()  # what a restart and what the hard ceiling both look like

    with pytest.raises(TokenError) as raised:
        await refresh(subject, issued.refresh_token)

    assert raised.value.error == "invalid_grant"
    assert all(state != STATE_REVOKED for _digest, state, _successor in refresh_rows(store))


@pytest.mark.anyio
async def test_the_held_answers_have_a_hard_ceiling(tmp_path: Path) -> None:
    """T-03-67: a dictionary that grows with every rotation is a denial of service."""
    clock = Clock()
    subject, _store, issued = await connected(tmp_path, clock=clock)

    for index in range(provider_module.HELD_ANSWER_LIMIT + 5):
        subject._hold(f"digest-{index}", issued, clock())

    assert len(subject._held) <= provider_module.HELD_ANSWER_LIMIT


@pytest.mark.anyio
async def test_a_held_answer_does_not_outlive_the_window(tmp_path: Path) -> None:
    clock = Clock()
    subject, _store, issued = await connected(tmp_path, clock=clock)
    await refresh(subject, issued.refresh_token)

    clock.advance(ROTATION_GRACE + 1)

    assert subject._held_answer(token_hash(issued.refresh_token or ""), clock()) is None


# --- the concurrency case ----------------------------------------------------------------


@pytest.mark.anyio
async def test_two_simultaneous_redemptions_produce_exactly_one_successor(
    tmp_path: Path,
) -> None:
    """Pitfall 10: Claude refreshes reactively and proactively, so this is the normal case."""
    subject, store, issued = await connected(tmp_path)

    results = await asyncio.gather(
        refresh(subject, issued.refresh_token),
        refresh(subject, issued.refresh_token),
        return_exceptions=True,
    )

    granted = [item for item in results if isinstance(item, OAuthToken)]
    assert len(granted) >= 1, "one of the two has to win"
    successors = {
        successor for _digest, _state, successor in refresh_rows(store) if successor is not None
    }
    assert len(successors) == 1, "never two branches of one family"
    assert all(state != STATE_REVOKED for _digest, state, _successor in refresh_rows(store))
    for item in results:
        if isinstance(item, TokenError):
            assert item.error == "invalid_grant"


# --- the refusals ------------------------------------------------------------------------


@pytest.mark.anyio
async def test_an_unknown_refresh_token_is_refused_without_killing_anything(
    tmp_path: Path,
) -> None:
    subject, store, _issued = await connected(tmp_path)

    with pytest.raises(TokenError) as raised:
        await refresh(subject, "a-token-this-server-never-issued")

    assert raised.value.error == "invalid_grant"
    assert all(state == STATE_ACTIVE for _digest, state, _successor in refresh_rows(store))


@pytest.mark.anyio
async def test_an_expired_refresh_token_is_refused_without_killing_anything(
    tmp_path: Path,
) -> None:
    clock = Clock()
    subject, store, issued = await connected(tmp_path, clock=clock)
    clock.advance(REFRESH_TOKEN_TTL + 1)

    with pytest.raises(TokenError) as raised:
        await refresh(subject, issued.refresh_token)

    assert raised.value.error == "invalid_grant"
    assert all(state == STATE_ACTIVE for _digest, state, _successor in refresh_rows(store))


@pytest.mark.anyio
async def test_a_client_blocked_after_its_token_was_issued_gets_nothing(tmp_path: Path) -> None:
    """Pitfall 9, T-03-55: the enforcement point has to reach the refresh grant as well."""
    subject, store, issued = await connected(tmp_path)
    await store.save_client(
        CLIENT_ID,
        metadata_json=registration().model_dump_json(exclude={"client_secret"}),
        allowed=False,
    )

    with pytest.raises(TokenError) as raised:
        await refresh(subject, issued.refresh_token)

    assert raised.value.error == "invalid_client"
    assert all(state == STATE_ACTIVE for _digest, state, _successor in refresh_rows(store))


@pytest.mark.anyio
async def test_a_refresh_token_of_a_revoked_connection_is_refused(tmp_path: Path) -> None:
    subject, store, issued = await connected(tmp_path)
    await store.revoke_authorization(AUTH_ID)

    assert await subject.load_refresh_token(registration(), issued.refresh_token or "") is None
    with pytest.raises(TokenError) as raised:
        await refresh(subject, issued.refresh_token)

    assert raised.value.error == "invalid_grant"


@pytest.mark.anyio
@pytest.mark.parametrize("resource", ["", "https://other.example.com/mcp"])
async def test_a_connection_for_another_audience_never_rotates(
    tmp_path: Path, resource: str
) -> None:
    """RFC 8707, T-03-51: the audience is checked again at every issue, not only the first.

    The connection is written directly here, because a code for a foreign audience never
    becomes a token in the first place (plan 03-06); this is the row a deployment whose
    public URL changed would leave behind.
    """
    subject, store = build(tmp_path)
    await subject.register_client(registration())
    await store.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user=NC_USER,
        app_password=APP_PASSWORD,
        scopes=TOOL_SCOPE,
        resource=resource,
    )
    await store.create_refresh_token(
        "the-refresh-token-of-a-foreign-audience", auth_id=AUTH_ID, family_id="one-family"
    )

    with pytest.raises(TokenError) as raised:
        await refresh(subject, "the-refresh-token-of-a-foreign-audience")

    assert raised.value.error == "invalid_target"


@pytest.mark.anyio
async def test_a_revoked_refresh_token_is_not_even_loaded(tmp_path: Path) -> None:
    """The state machine of the store is the answer, so a killed family cannot come back."""
    subject, store, issued = await connected(tmp_path)
    row = await store.load_refresh_token(issued.refresh_token or "")
    assert row is not None
    await store.revoke_family(row.family_id)

    assert await subject.load_refresh_token(registration(), issued.refresh_token or "") is None


@pytest.mark.anyio
async def test_a_used_refresh_token_is_still_loaded_so_the_window_can_decide(
    tmp_path: Path,
) -> None:
    """The load must not swallow the reuse: the decision belongs to the exchange."""
    clock = Clock()
    subject, _store, issued = await connected(tmp_path, clock=clock)
    await refresh(subject, issued.refresh_token)

    loaded = await subject.load_refresh_token(registration(), issued.refresh_token or "")

    assert loaded is not None
    assert loaded.client_id == CLIENT_ID
    assert loaded.scopes == [TOOL_SCOPE]


# --- what the rotation must never do -----------------------------------------------------


@pytest.mark.anyio
async def test_the_rotation_asks_nextcloud_nothing_at_all(tmp_path: Path) -> None:
    """T-03-58, pitfall 13: a connector gives its token endpoint about ten seconds."""
    clock = Clock()
    subject, _store, issued = await connected(tmp_path, clock=clock)

    with respx.mock:
        rotated = await refresh(subject, issued.refresh_token)
        clock.advance(ROTATION_GRACE + 1)
        with pytest.raises(TokenError):
            await refresh(subject, issued.refresh_token)
        assert len(respx.calls) == 0, "not on the happy path and not on the family kill"
    assert rotated.access_token


@pytest.mark.anyio
async def test_no_refusal_of_the_rotation_repeats_the_token_it_received(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T-03-66: the value came from a request and is echoed nowhere, not even on DEBUG."""
    clock = Clock()
    subject, _store, issued = await connected(tmp_path, clock=clock)
    presented = issued.refresh_token or ""

    with caplog.at_level(logging.DEBUG):
        await refresh(subject, presented)
        clock.advance(ROTATION_GRACE + 1)
        with pytest.raises(TokenError) as raised:
            await refresh(subject, presented)

    text = f"{raised.value.error} {raised.value.error_description}"
    assert presented not in text
    assert presented not in caplog.text

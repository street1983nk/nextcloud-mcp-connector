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
import inspect
import logging
from collections.abc import Mapping
from typing import Any

import pytest

from mcp_connector.audit import accounts
from mcp_connector.oauth import exchange_accounts, exchange_appapi
from mcp_connector.oauth.verifier import CREDENTIAL_IMPERSONATE

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

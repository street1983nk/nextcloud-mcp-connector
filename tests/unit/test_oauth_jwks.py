"""The key set layer, spoken to directly: cooldown, single-flight, fail-closed.

Keys are generated per test run, every provider answer is served by respx, and nothing
opens a socket. The layer is exercised without the browser identity flow on purpose: the
decoupling is part of the proof. The refusal is a tiny local exception handed in the way
every caller hands in its own, and it carries no detail, like the real ones.
"""

import asyncio
import base64
import json
from typing import Any

import httpx
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from mcp_connector.oauth import jwks, throttle

ORIGIN = "https://auth.example.com"
JWKS_URL = f"{ORIGIN}/oauth/v2/keys"
KID = "key-1"

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Refused(Exception):
    """The stand-in for a caller's refusal. Carries no detail, like the real ones."""


def refuse(_reason: str) -> Exception:
    return Refused()


def jwk_of(private: rsa.RSAPrivateKey, kid: str = KID, **extra: Any) -> dict[str, Any]:
    entry = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    entry.update({"kid": kid, "use": "sig", "alg": "RS256"}, **extra)
    return entry


class Clock:
    """A hand-turned clock, so cooldown and expiry are decided by the test."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def key_set(clock: Clock | None = None, *, url: str = JWKS_URL, **overrides: Any) -> jwks.KeySet:
    async def jwks_uri() -> str:
        return url

    values: dict[str, Any] = {
        "origin": ORIGIN,
        "jwks_uri": jwks_uri,
        "algorithms": ("RS256",),
        "refuse": refuse,
    }
    if clock is not None:
        values["clock"] = clock
    values.update(overrides)
    return jwks.KeySet(**values)


def serve(keys: list[dict[str, Any]] | None = None) -> respx.Route:
    payload = {"keys": keys if keys is not None else [jwk_of(PRIVATE)]}
    return respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=payload))


# --- cooldown ----------------------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_hundred_invented_kids_against_a_fresh_cache_cost_one_fetch() -> None:
    route = serve()
    keys = key_set(Clock())
    await keys.key(KID, "RS256")
    route.reset()

    for index in range(100):
        with pytest.raises(Refused):
            await keys.key(f"invented-{index}", "RS256")

    assert route.call_count == 1, "the first miss refetches once; the cooldown absorbs the rest"


@respx.mock
@pytest.mark.anyio
async def test_inside_the_cooldown_an_unknown_kid_is_refused_without_a_fetch() -> None:
    route = serve()
    keys = key_set(Clock())
    await keys.key(KID, "RS256")
    with pytest.raises(Refused) as after_fetch:
        await keys.key("unknown-1", "RS256")
    fetched = route.call_count

    with pytest.raises(Refused) as inside_cooldown:
        await keys.key("unknown-2", "RS256")

    assert route.call_count == fetched, "inside the cooldown no fetch goes out"
    assert type(inside_cooldown.value) is type(after_fetch.value)
    assert str(inside_cooldown.value) == str(after_fetch.value)


@respx.mock
@pytest.mark.anyio
async def test_after_the_cooldown_an_unknown_kid_costs_one_fetch_again() -> None:
    route = serve()
    clock = Clock()
    keys = key_set(clock)
    await keys.key(KID, "RS256")
    with pytest.raises(Refused):
        await keys.key("unknown", "RS256")
    fetched = route.call_count

    clock.advance(jwks.JWKS_KID_COOLDOWN_SECONDS + 1)
    with pytest.raises(Refused):
        await keys.key("still-unknown", "RS256")

    assert route.call_count == fetched + 1


@respx.mock
@pytest.mark.anyio
async def test_an_expired_cache_refreshes_regardless_of_the_cooldown() -> None:
    route = serve()
    clock = Clock()
    keys = key_set(clock, cooldown_seconds=10_000.0)
    await keys.key(KID, "RS256")
    with pytest.raises(Refused):
        await keys.key("unknown", "RS256")
    fetched = route.call_count

    clock.advance(jwks.JWKS_CACHE_SECONDS + 1)
    assert await keys.key(KID, "RS256") is not None

    assert route.call_count == fetched + 1, "expiry refreshes; the cooldown only brakes misses"


@respx.mock
@pytest.mark.anyio
async def test_a_failed_miss_reload_still_spends_the_cooldown() -> None:
    route = respx.get(JWKS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]}),
            httpx.Response(500),
        ]
    )
    keys = key_set(Clock())
    await keys.key(KID, "RS256")

    with pytest.raises(Refused):
        await keys.key("unknown-1", "RS256")
    with pytest.raises(Refused):
        await keys.key("unknown-2", "RS256")

    assert route.call_count == 2, "the failing fetch spent the cooldown; no second one follows"


@respx.mock
@pytest.mark.anyio
async def test_an_unknown_kid_inside_the_cooldown_does_not_queue_behind_a_fetch() -> None:
    """The cooldown is decided before the lock, so a flood of invented kids never queues.

    While a reload is in flight it holds the lock, and a flight can take two timeouts
    (discovery, then the JWKS). A call whose answer is already settled must not wait for
    it: otherwise a flood of invented kids serializes on one lock whose queue grows
    without a bound, exactly while the provider is slow.
    """
    gate = asyncio.Event()
    reached_the_gate = asyncio.Event()
    calls = 0

    async def answer(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 2:
            # The reload for the first unknown kid: in flight, holding the lock.
            reached_the_gate.set()
            await gate.wait()
        return httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]})

    respx.get(JWKS_URL).mock(side_effect=answer)
    keys = key_set(Clock())
    await keys.key(KID, "RS256")
    in_flight = asyncio.create_task(keys.key("unknown-1", "RS256"))
    await reached_the_gate.wait()

    with pytest.raises(Refused):
        await asyncio.wait_for(keys.key("unknown-2", "RS256"), timeout=1.0)

    gate.set()
    with pytest.raises(Refused):
        await in_flight


# --- the failure path is braked ----------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_failing_cold_fetch_is_not_repeated_for_every_caller() -> None:
    """A provider that just failed must not be asked again by every arriving call.

    This is the cold cache, the case an attacker creates most easily: without the brake
    every incoming request becomes an outgoing fetch, so the layer amplifies the load on
    an identity provider that is already struggling. The brake only makes refusals
    cheaper; none of the twenty-five calls is answered with a key.
    """
    route = respx.get(JWKS_URL).mock(return_value=httpx.Response(500))
    keys = key_set(Clock())

    for _ in range(25):
        with pytest.raises(Refused):
            await keys.key(KID, "RS256")

    assert route.call_count == 1, "the failed fetch brakes the ones that would follow it"


@respx.mock
@pytest.mark.anyio
async def test_after_the_retry_pause_a_cold_fetch_is_attempted_again() -> None:
    route = respx.get(JWKS_URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]}),
        ]
    )
    clock = Clock()
    keys = key_set(clock)
    with pytest.raises(Refused):
        await keys.key(KID, "RS256")

    clock.advance(jwks.JWKS_FAILURE_RETRY_SECONDS + 1)

    assert await keys.key(KID, "RS256") is not None, "the brake is a pause, not a shutdown"
    assert route.call_count == 2


# --- single-flight -----------------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_twenty_concurrent_calls_cost_one_fetch_and_share_the_key() -> None:
    async def slow_answer(_request: httpx.Request) -> httpx.Response:
        for _ in range(5):
            await asyncio.sleep(0)
        return httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]})

    route = respx.get(JWKS_URL).mock(side_effect=slow_answer)
    keys = key_set(Clock())

    found = await asyncio.gather(*(keys.key(KID, "RS256") for _ in range(20)))

    assert route.call_count == 1
    assert all(key is found[0] for key in found)
    # The counter a waiter behind the lock compares against. It is nailed down here
    # because the decision "share the refusal, do not start a second flight" rests on it:
    # one finished attempt must move it by exactly one, whatever the outcome was.
    assert keys._fetches == 1


@respx.mock
@pytest.mark.anyio
async def test_twenty_concurrent_calls_whose_fetch_fails_are_all_refused_by_one_fetch() -> None:
    async def slow_failure(_request: httpx.Request) -> httpx.Response:
        for _ in range(5):
            await asyncio.sleep(0)
        return httpx.Response(500)

    route = respx.get(JWKS_URL).mock(side_effect=slow_failure)
    keys = key_set(Clock())

    found = await asyncio.gather(
        *(keys.key(KID, "RS256") for _ in range(20)), return_exceptions=True
    )

    assert route.call_count == 1
    assert all(isinstance(outcome, Refused) for outcome in found)


# --- the failure path keeps the cache ----------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_failed_reload_leaves_the_cache_standing() -> None:
    route = respx.get(JWKS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]}),
            httpx.Response(500),
        ]
    )
    keys = key_set(Clock())
    first = await keys.key(KID, "RS256")

    with pytest.raises(Refused):
        await keys.key("unknown", "RS256")

    assert await keys.key(KID, "RS256") is first, "the known kid is still served, no new fetch"
    assert route.call_count == 2, "nothing was written over the usable entry"


@respx.mock
@pytest.mark.anyio
async def test_a_200_without_a_usable_key_leaves_the_cache_standing() -> None:
    """An answer with no usable key counts as a failed fetch, exactly like a 500.

    A provider that briefly serves an empty JWKS during a rolling restart would otherwise
    replace a working cache with nothing and lock every sign in out, healing in steps of
    the miss cooldown rather than at once.
    """
    route = respx.get(JWKS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]}),
            httpx.Response(200, json={"keys": []}),
        ]
    )
    keys = key_set(Clock())
    first = await keys.key(KID, "RS256")

    with pytest.raises(Refused):
        await keys.key("unknown", "RS256")

    assert await keys.key(KID, "RS256") is first, "the empty answer did not wipe the cache"
    assert route.call_count == 2


# --- inherited hardening, proven at the layer itself --------------------------------------


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "entry",
    [
        {"kty": "oct", "k": base64.urlsafe_b64encode(b"0" * 32).decode(), "kid": KID},
        jwk_of(PRIVATE, use="enc"),
        jwk_of(PRIVATE, key_ops=["encrypt"]),
        jwk_of(PRIVATE, alg="RS512"),
        {"kty": "RSA", "n": None, "e": "AQAB", "kid": KID},
        {"kty": "RSA", "n": [1, 2], "e": "AQAB", "kid": KID, "alg": "RS256"},
        {"kty": "OKP", "crv": "Ed25519", "x": 7, "kid": KID},
    ],
    ids=[
        "symmetric key",
        "encryption use",
        "encrypt-only key_ops",
        "unconfigured algorithm",
        "null modulus",
        "modulus as a list",
        "OKP coordinate as a number",
    ],
)
async def test_an_entry_that_may_not_verify_never_enters_the_cache(entry: dict[str, Any]) -> None:
    serve([entry])
    with pytest.raises(Refused):
        await key_set(Clock()).key(KID, "RS256")


@respx.mock
@pytest.mark.anyio
async def test_a_key_declared_for_another_algorithm_than_asked_is_refused() -> None:
    serve([jwk_of(PRIVATE, alg="RS384")])
    keys = key_set(Clock(), algorithms=("RS256", "RS384"))
    with pytest.raises(Refused):
        await keys.key(KID, "RS256")


@respx.mock
@pytest.mark.anyio
async def test_two_entries_with_the_same_kid_make_that_kid_unusable() -> None:
    serve([jwk_of(PRIVATE), jwk_of(OTHER_PRIVATE)])
    with pytest.raises(Refused):
        await key_set(Clock()).key(KID, "RS256")


@respx.mock
@pytest.mark.anyio
async def test_more_than_max_keys_entries_are_refused_as_a_whole() -> None:
    serve([jwk_of(PRIVATE, kid=f"key-{index}") for index in range(jwks.MAX_KEYS + 1)])
    with pytest.raises(Refused):
        await key_set(Clock()).key("key-0", "RS256")


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/oauth/v2/keys",
        f"{JWKS_URL}#",
        "https://user:secret@auth.example.com/oauth/v2/keys",
    ],
    ids=["foreign origin", "fragment", "credentials"],
)
async def test_a_jwks_uri_off_the_issuer_origin_is_refused_without_a_fetch(url: str) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={"keys": []}))

    with pytest.raises(Refused):
        await key_set(Clock(), url=url).key(KID, "RS256")

    assert route.call_count == 0, "the refusal happens before anything goes out"


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "https://evil.example.com/"}),
        httpx.Response(500),
        httpx.Response(200, text="not json"),
        httpx.Response(200, content=b"{" + b" " * (jwks.MAX_RESPONSE_BYTES + 1) + b"}"),
    ],
    ids=["redirect", "server error", "not json", "too large"],
)
async def test_an_unusable_answer_is_refused(response: httpx.Response) -> None:
    respx.get(JWKS_URL).mock(return_value=response)
    with pytest.raises(Refused):
        await key_set(Clock()).key(KID, "RS256")


@respx.mock
@pytest.mark.anyio
async def test_an_expired_cache_never_serves_a_kid_when_the_reload_fails() -> None:
    route = respx.get(JWKS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]}),
            httpx.Response(500),
            httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]}),
        ]
    )
    clock = Clock()
    keys = key_set(clock)
    await keys.key(KID, "RS256")

    clock.advance(jwks.JWKS_CACHE_SECONDS + 1)
    with pytest.raises(Refused):
        # The kid sat in the old cache, but an expired cache is never served: no key
        # means refusal, and the convenient mistake (take the expired entry in an
        # emergency) would turn fail-closed into a barn door.
        await keys.key(KID, "RS256")

    # Past the pause the failed fetch put on the expiry branch, so the third answer is
    # reached at all; inside it the call would be refused without a fetch.
    clock.advance(jwks.JWKS_FAILURE_RETRY_SECONDS + 1)
    assert await keys.key(KID, "RS256") is not None, "the failure did not wipe the layer"
    assert route.call_count == 3


# --- a revocation may empty the cache, never the brakes ----------------------------------


@respx.mock
@pytest.mark.anyio
async def test_after_forget_a_known_kid_costs_one_new_fetch() -> None:
    """The half of a revocation that reaches this layer: the cached keys are gone.

    Measured at the outgoing requests and never at a private attribute. The cache was
    fresh right up to the call, so the second fetch is the whole statement.
    """
    route = serve()
    keys = key_set(Clock())
    await keys.key(KID, "RS256")
    assert route.call_count == 1

    keys.forget()

    assert await keys.key(KID, "RS256") is not None
    assert route.call_count == 2, "a fresh cache that was forgotten is fetched again"


@respx.mock
@pytest.mark.anyio
async def test_forget_does_not_lift_the_cooldown_of_an_unknown_kid() -> None:
    """The reason the method touches two fields and not four.

    The cooldown is the pre-authentication brake of phase 20 against a flood of invented
    kids. If it fell together with the cache, whoever can trigger a revocation in this
    process could order one outgoing fetch per invented kid again.
    """
    route = serve()
    keys = key_set(Clock())
    await keys.key(KID, "RS256")
    with pytest.raises(Refused):
        await keys.key("unknown-1", "RS256")
    keys.forget()
    await keys.key(KID, "RS256")
    refilled = route.call_count

    with pytest.raises(Refused):
        await keys.key("unknown-2", "RS256")

    assert route.call_count == refilled, "the cooldown outlived the forgetting"


@respx.mock
@pytest.mark.anyio
async def test_forget_does_not_lift_the_pause_after_a_failed_fetch() -> None:
    """The second brake, for the same reason: a failing provider stays braked."""
    route = respx.get(JWKS_URL).mock(return_value=httpx.Response(500))
    keys = key_set(Clock())
    with pytest.raises(Refused):
        await keys.key(KID, "RS256")
    assert route.call_count == 1

    keys.forget()
    with pytest.raises(Refused):
        await keys.key(KID, "RS256")

    assert route.call_count == 1, "the retry pause outlived the forgetting"


@respx.mock
@pytest.mark.anyio
async def test_forget_on_a_never_filled_key_set_does_nothing_and_raises_nothing() -> None:
    """A revocation before the first sign in is an ordinary event, not an error."""
    route = serve()
    keys = key_set(Clock())

    keys.forget()

    assert await keys.key(KID, "RS256") is not None
    assert route.call_count == 1


# --- how many outgoing fetches a peer can order per window, measured after phase 23 (IN-05) -
#
# The question BL-21/IN-05 asks, and the reason it waited for this phase: how many fetches
# at the identity provider can a holder of a valid exchange token order per window of
# ``throttle.WINDOW`` seconds? Before phase 23 no exchange token had an identity, so every
# call of that branch ended as a refusal, was counted in ``CLASS_EXCHANGE`` and ran into
# ``EXCHANGE_LIMIT``. Since phase 23 a valid token is answered with 200, is not counted, and
# pays one earlier refusal back, so the old ceiling is gone and the number had to be measured
# again rather than reasoned about.

#: How many revocation cycles one window is driven with. One past ``EXCHANGE_LIMIT`` on
#: purpose: that is the ceiling which used to cap this lever, so a run that gets a fetch out
#: of the thirty-first cycle is the measurement that the cap is no longer there.
REVOCATION_CYCLES = throttle.EXCHANGE_LIMIT + 1

#: How often the miss cooldown opens inside one window. Derived here and held against the
#: measured counter below, never asserted on its own.
COOLDOWN_STEPS = int(throttle.WINDOW // jwks.JWKS_KID_COOLDOWN_SECONDS)

#: The spacing of the cycles, chosen so that the whole run fits inside a single window.
SECONDS_PER_CYCLE = throttle.WINDOW / (REVOCATION_CYCLES + 1)

#: The total this file measured on 2026-09-23 for both levers pulled alternately inside one
#: window. Written down as a number rather than computed in the assertion, so that a run
#: which produces a different one is red and readable instead of quietly self-consistent.
MEASURED_FETCHES_PER_WINDOW = 36

#: The account a signed revocation would come from. ``CLASS_CONNECTIONS`` is keyed by it.
ACCOUNT = "alice"


@respx.mock
@pytest.mark.anyio
async def test_each_revocation_cycle_orders_exactly_one_fetch_and_thirty_one_fit_in_a_window() -> (
    None
):
    """Lever a of IN-05: a revocation plus one valid call costs exactly one outgoing fetch.

    ``forget`` clears the cache and puts the stamp at minus infinity, so the call that
    follows takes the expiry branch, and that branch never consults the miss cooldown. One
    cycle, one fetch, and nothing in this layer slows the next one down.

    ``forget`` is called directly because it is what a revocation reaches here:
    ``chain.ChainedVerifier.invalidate`` calls ``forget_keys`` on the exchange branch, and
    that link is measured in ``test_oauth_exchange_chain.py``, not a second time in this
    file. What a revocation costs a peer in reality is a proved browser identity: the
    revocation routes sit behind the consent surface and the account page, so this lever is
    bounded by how often somebody can sign in and revoke, and by nothing in this process.

    What this does not measure: the number is per process and per issuer. Two workers hold
    two ``KeySet`` instances and therefore two of these numbers, exactly as the throttle
    holds two of its counters.
    """
    route = serve()
    clock = Clock()
    keys = key_set(clock)

    for _cycle in range(REVOCATION_CYCLES):
        keys.forget()
        assert await keys.key(KID, "RS256") is not None
        clock.advance(SECONDS_PER_CYCLE)

    assert clock.now - 1_000.0 < throttle.WINDOW, "the whole run has to sit inside one window"
    assert route.call_count == REVOCATION_CYCLES, (
        f"{REVOCATION_CYCLES} revocation cycles ordered {route.call_count} outgoing fetches, "
        f"expected {REVOCATION_CYCLES}, one per cycle and none of them braked"
    )


@respx.mock
@pytest.mark.anyio
async def test_unknown_key_ids_alone_order_five_fetches_per_window_and_no_more() -> None:
    """Lever b of IN-05: the miss cooldown is the only ceiling this layer puts up itself.

    Measured with a hand-turned clock that jumps in cooldown-sized steps rather than
    computed from the two constants: what is asserted is the counter of the route, and the
    derived ``COOLDOWN_STEPS`` is only held against it.

    The flood inside each step is part of the measurement and not decoration: ten further
    invented key ids between two steps have to cost nothing at all, which is the property
    the cooldown exists for.
    """
    route = serve()
    clock = Clock()
    keys = key_set(clock)
    await keys.key(KID, "RS256")
    route.reset()

    for step in range(COOLDOWN_STEPS):
        with pytest.raises(Refused):
            await keys.key(f"invented-{step}", "RS256")
        for inside in range(10):
            with pytest.raises(Refused):
                await keys.key(f"invented-{step}-{inside}", "RS256")
        clock.advance(jwks.JWKS_KID_COOLDOWN_SECONDS)

    assert COOLDOWN_STEPS == 5, "five cooldowns of sixty seconds fit into a window of three hundred"
    assert route.call_count == COOLDOWN_STEPS, (
        f"unknown key ids ordered {route.call_count} outgoing fetches in one window, "
        f"expected {COOLDOWN_STEPS}: one per cooldown, whatever arrives between them"
    )


@respx.mock
@pytest.mark.anyio
async def test_both_levers_in_one_window_measure_thirty_six_outgoing_fetches() -> None:
    """IN-05, the whole number: both levers pulled alternately inside one window.

    This is the case the two measurements above cannot be added up into, and the reason the
    number in the docstring of ``jwks.forget`` had to come from a run. The two levers touch
    the same two fields: a revocation makes the cache stale, and an unknown key id against a
    *stale* cache takes the expiry branch, which never looks at the miss cooldown and never
    spends it. So the cooldown does not brake the first invented key id after a revocation
    at all, and the one that follows it, against the refilled cache, is the only one the
    cooldown ever sees.

    Measured on 2026-09-23: thirty-one revocation cycles plus two invented key ids each,
    spaced so the run sits inside one window of ``throttle.WINDOW`` seconds, order
    thirty-six outgoing fetches. The two part numbers happen to add up to the same total
    here, and that agreement is asserted below as a second reading rather than used as the
    expectation: what fixes the number is the counter of the route.

    What this does not measure: one process, one issuer, and no HTTP layer. The revocations
    a real peer needs are browser round trips against a proved identity, and two workers
    would hold two key sets and therefore two of this number.
    """
    route = serve()
    clock = Clock()
    keys = key_set(clock)

    for cycle in range(REVOCATION_CYCLES):
        keys.forget()
        with pytest.raises(Refused):
            # Against the stale cache: the expiry branch fetches and leaves the cooldown
            # untouched, which is the interaction this case exists for.
            await keys.key(f"invented-{cycle}", "RS256")
        with pytest.raises(Refused):
            # Against the cache the line above refilled: this one is the miss branch, and
            # it is the only one of the two the cooldown can refuse.
            await keys.key(f"invented-{cycle}-again", "RS256")
        clock.advance(SECONDS_PER_CYCLE)

    assert clock.now - 1_000.0 < throttle.WINDOW, "the whole run has to sit inside one window"
    assert route.call_count == MEASURED_FETCHES_PER_WINDOW, (
        f"both levers in one window ordered {route.call_count} outgoing fetches, "
        f"expected the measured {MEASURED_FETCHES_PER_WINDOW}"
    )
    assert MEASURED_FETCHES_PER_WINDOW == REVOCATION_CYCLES + COOLDOWN_STEPS, (
        f"the measured {MEASURED_FETCHES_PER_WINDOW} reads as {REVOCATION_CYCLES} expiry "
        f"fetches plus {COOLDOWN_STEPS} miss fetches; if this ever disagrees with the "
        "counter above, the counter is the truth and this reading is the stale one"
    )


async def _revocation_succeeded(scope: Scope, receive: Receive, send: Send) -> None:
    """The answer a successful revocation writes: 200, and nothing for the counter."""
    await Response(status_code=200)(scope, receive, send)


def _the_signed_account(_request: Request) -> str:
    """What HaRP signs onto the account page, in the shape ``Throttled`` asks for."""
    return ACCOUNT


def test_a_successful_revocation_is_not_braked_by_its_own_path_class() -> None:
    """The side finding of IN-05, measured through the real wrapper and not read off a module.

    ``CLASS_CONNECTIONS`` is what stands in front of the account page a revocation is
    ordered from. It counts refusals and pays one back on every success, and it is keyed by
    the signed account without the ceiling of the path class (HI-01). So a peer that keeps
    revoking successfully never brakes itself, which is why lever a above has no ceiling
    from the throttle either and why the number in ``jwks.forget`` has to be a measured one.

    This is not a defect: a successful revocation is a wanted action, and a page that
    refused the emergency brake of an account after ten uses would be the worse design. It
    is written down because it is the reason the old calculation of IN-05 no longer holds.
    """
    counters = throttle.Throttle()
    guarded = throttle.Throttled(
        _revocation_succeeded,
        counters,
        throttle.CLASS_CONNECTIONS,
        machine=False,
        identity=_the_signed_account,
    )
    client = TestClient(guarded)

    answered = [client.post("/connections").status_code for _cycle in range(REVOCATION_CYCLES)]

    assert answered == [200] * REVOCATION_CYCLES, (
        f"{REVOCATION_CYCLES} successful revocations were answered {sorted(set(answered))}, "
        "expected [200]: this class counts refusals, so a success never fills it"
    )
    assert counters.retry_after(throttle.CLASS_CONNECTIONS, ACCOUNT, shared=False) == 0, (
        "and the counter behind them is still open, which is what lets lever a run on"
    )

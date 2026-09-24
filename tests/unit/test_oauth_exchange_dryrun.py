"""The rule half of the dry run (EXCH-06), spoken to directly: one measured case per step.

Keys are generated per test run, every key set answer is served by respx and nothing leaves
the process. The dry run is exercised without a route and without an environment, which is
the whole point of its shape: the console half arrives with plan 24-06 and has nothing to
decide.

Three things this corpus measures that no other file can:

* every local rule of ``ExchangeTokenChecker.claims_of`` has a named step here, and a step
  that fell leaves every later step ``skipped`` rather than absent (pitfall 8);
* no field of an answer ever carries a value out of the presented token (T-24-09);
* the drift gate of task 3 holds the two sides together structurally: a refusal phrase of
  the operating path without a step here is a finding, not a silence.
"""

import base64
import inspect
import json
import sqlite3
import time
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from mcp_connector import errors
from mcp_connector.audit import store as audit_store
from mcp_connector.oauth import chain, exchange, exchange_dryrun, mapping
from mcp_connector.oauth import store as oauth_store

ISSUER = "https://idp.example.org/realms/f13"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"
AUDIENCE = "https://cloud.example.org/exapps/mcp_connector/mcp"
AZP = "f13-orchestrator"
KID = "key-1"
SUB = "service-account-f13"
SHARED_SECRET = "client-secret-long-enough-for-hmac-sha256-0123456789"

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Clock:
    """A hand-turned clock, so cache expiry and cooldown are decided by the test."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def jwk_of(private: rsa.RSAPrivateKey, kid: str = KID, **extra: Any) -> dict[str, Any]:
    entry = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    entry.update({"kid": kid, "use": "sig", "alg": "RS256"}, **extra)
    return entry


def serve(url: str = JWKS_URL, keys: list[dict[str, Any]] | None = None) -> respx.Route:
    payload = {"keys": keys if keys is not None else [jwk_of(PRIVATE)]}
    return respx.get(url).mock(return_value=httpx.Response(200, json=payload))


def settings_for(**overrides: Any) -> exchange.ExchangeSettings:
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "jwks_uri": JWKS_URL,
        "audience": AUDIENCE,
        "azp_allowed": (AZP,),
    }
    values.update(overrides)
    return exchange.ExchangeSettings(**values)


def config_for(account_claim: str = "sub", **overrides: Any) -> chain.ExchangeConfig:
    """The validated configuration, handed in exactly as the chain would hand it in."""
    return chain.ExchangeConfig(
        settings=settings_for(**overrides),
        account_claim=account_claim,
        mapping=mapping.MappingSettings(
            strategy=mapping.MAPPING_ACCOUNT_ID_V1, account_claim=account_claim
        ),
    )


def claims(**overrides: Any) -> dict[str, Any]:
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
    return {key: value for key, value in values.items() if value is not None}


def token(
    private: Any = PRIVATE,
    *,
    algorithm: str = "RS256",
    kid: str | None = KID,
    headers: dict[str, Any] | None = None,
    **overrides: Any,
) -> str:
    header: dict[str, Any] = {} if kid is None else {"kid": kid}
    if headers:
        header.update(headers)
    return jwt.encode(claims(**overrides), private, algorithm=algorithm, headers=header)


def encoded(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def segment(value: dict[str, Any]) -> str:
    return encoded(json.dumps(value).encode())


def handmade(header: dict[str, Any], payload: bytes) -> str:
    """A token whose payload bytes are whatever the test wants, header still readable.

    The payload segment stays valid base64url on purpose. PyJWT decodes both segments while
    it reads the header, so a payload that is not even base64 falls one step earlier, in
    ``header_readable``, and would measure the wrong rule.
    """
    return f"{segment(header)}.{encoded(payload)}.c2lnbmF0dXJl"


# --- reading an answer --------------------------------------------------------------------


def outcomes(result: exchange_dryrun.DryRunResult) -> dict[str, str]:
    return {step.step: step.outcome for step in result.steps}


def step_named(result: exchange_dryrun.DryRunResult, name: str) -> exchange_dryrun.DryRunStep:
    return next(step for step in result.steps if step.step == name)


def assert_fell_at(result: exchange_dryrun.DryRunResult, name: str, reason: str) -> None:
    """Exactly this step failed, everything before it passed, everything after is skipped."""
    index = exchange_dryrun.STEPS.index(name)
    seen = outcomes(result)
    assert list(seen) == list(exchange_dryrun.STEPS), "every step stands in the answer, in order"
    for earlier in exchange_dryrun.STEPS[:index]:
        assert seen[earlier] == exchange_dryrun.OUTCOME_PASSED, earlier
    assert seen[name] == exchange_dryrun.OUTCOME_FAILED
    for later in exchange_dryrun.STEPS[index + 1 :]:
        assert seen[later] == exchange_dryrun.OUTCOME_SKIPPED, later
    assert result.passed is False
    assert step_named(result, name).reason == reason
    # The step that is never executed keeps its note whatever else happened (pitfall 8).
    assert step_named(result, exchange_dryrun.STEP_ACCOUNT_EXISTS).note == (
        exchange_dryrun.NOTE_WOULD_CALL_NEXTCLOUD
    )


def serialized(result: exchange_dryrun.DryRunResult) -> str:
    """The answer as a machine would carry it: every field of every step, as text."""
    return json.dumps(
        {
            "passed": result.passed,
            "limit_sentence": result.limit_sentence,
            "cost_sentence": result.cost_sentence,
            "steps": [
                {
                    "step": step.step,
                    "outcome": step.outcome,
                    "reason": step.reason,
                    "note": step.note,
                }
                for step in result.steps
            ],
        }
    )


# --- the closed set of steps ---------------------------------------------------------------


def test_the_steps_are_the_closed_ordered_set_of_the_checker() -> None:
    """Twenty-two names in checking order; the list follows the checker, never the other way."""
    assert exchange_dryrun.STEPS == (
        "token_present",
        "token_size",
        "token_is_text",
        "token_shape",
        "header_readable",
        "algorithm_allowed",
        "key_named",
        "header_type",
        "payload_readable",
        "issuer_matches",
        "key_available",
        "signature_and_standard_claims",
        "audience_exact",
        "acting_party_named",
        "acting_party_allowed",
        "token_type_bearer",
        "times_numeric",
        "lifetime_within_bound",
        "age_within_bound",
        "subject_usable",
        "mapping_yields_principal",
        "account_exists",
    )
    assert len(exchange_dryrun.STEPS) == 22
    assert len(set(exchange_dryrun.STEPS)) == 22


def test_the_four_outcomes_are_named_and_distinct() -> None:
    four = {
        exchange_dryrun.OUTCOME_PASSED,
        exchange_dryrun.OUTCOME_FAILED,
        exchange_dryrun.OUTCOME_SKIPPED,
        exchange_dryrun.OUTCOME_NOT_CHECKED,
    }
    assert four == {"passed", "failed", "skipped", "not_checked"}


def test_the_bound_of_the_checker_is_imported_and_never_retyped() -> None:
    """One number for both sides: a second copy is a bound that can drift (T-24-25)."""
    assert exchange_dryrun.MAX_TOKEN_BYTES is exchange.MAX_TOKEN_BYTES


# --- the local steps, one measured case each -------------------------------------------------


@pytest.mark.anyio
async def test_an_empty_token_falls_in_the_first_step() -> None:
    result = await exchange_dryrun.dry_run("", config_for())
    assert_fell_at(result, "token_present", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
async def test_a_token_one_character_over_the_bound_falls_in_the_size_step() -> None:
    """One character over, and before the first base64 step: the order of ``claims_of``."""
    result = await exchange_dryrun.dry_run("x" * (exchange.MAX_TOKEN_BYTES + 1), config_for())
    assert_fell_at(result, "token_size", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
async def test_a_token_over_the_bound_in_bytes_but_not_in_characters_falls_in_the_size_step() -> (
    None
):
    """The exact measurement is the UTF-8 byte count, as in the checker."""
    wide = "ä" * (exchange.MAX_TOKEN_BYTES // 2 + 10)
    assert len(wide) <= exchange.MAX_TOKEN_BYTES
    result = await exchange_dryrun.dry_run(wide, config_for())
    assert_fell_at(result, "token_size", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
async def test_a_token_that_is_not_text_falls_in_its_own_step() -> None:
    """A lone surrogate cannot be encoded; the checker refuses it rather than repairing it."""
    result = await exchange_dryrun.dry_run("a.b.\ud800", config_for())
    assert_fell_at(result, "token_is_text", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "shapeless",
    ["not-a-jws", "one.dot", "a.b.c.d.e", "a..c", ".b.c", "a.b."],
)
async def test_a_token_of_the_wrong_shape_falls_in_the_shape_step(shapeless: str) -> None:
    """The shape step asks ``chain.looks_like_jws`` and never counts dots of its own."""
    result = await exchange_dryrun.dry_run(shapeless, config_for())
    assert_fell_at(result, "token_shape", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
async def test_an_unreadable_header_falls_in_the_header_step() -> None:
    result = await exchange_dryrun.dry_run("aaa.bbb.ccc", config_for())
    assert_fell_at(result, "header_readable", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
async def test_an_algorithm_outside_the_allowlist_falls_before_any_key_is_looked_at() -> None:
    hmac_signed = jwt.encode(claims(), SHARED_SECRET, algorithm="HS256", headers={"kid": KID})
    result = await exchange_dryrun.dry_run(hmac_signed, config_for())
    assert_fell_at(result, "algorithm_allowed", errors.REASON_EXCHANGE_KEY)


@pytest.mark.anyio
async def test_a_token_naming_no_key_falls_in_the_key_named_step() -> None:
    result = await exchange_dryrun.dry_run(token(kid=None), config_for())
    assert_fell_at(result, "key_named", errors.REASON_EXCHANGE_KEY)


@pytest.mark.anyio
async def test_a_foreign_header_type_falls_in_the_header_type_step() -> None:
    result = await exchange_dryrun.dry_run(token(headers={"typ": "dpop+jwt"}), config_for())
    assert_fell_at(result, "header_type", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
async def test_a_missing_header_type_is_no_reason_to_fall() -> None:
    """Tolerated, never required: the rule of ``ACCEPTED_TYP_HEADERS``, not a stricter one."""
    result = await exchange_dryrun.dry_run(
        token(iss="https://evil.example.org/realms/f13"), config_for()
    )
    assert outcomes(result)["header_type"] == exchange_dryrun.OUTCOME_PASSED


@pytest.mark.anyio
async def test_an_unreadable_payload_falls_in_the_payload_step() -> None:
    result = await exchange_dryrun.dry_run(
        handmade({"alg": "RS256", "kid": KID, "typ": "JWT"}, b"[[[not json"), config_for()
    )
    assert_fell_at(result, "payload_readable", errors.REASON_EXCHANGE_MALFORMED)


@pytest.mark.anyio
async def test_a_foreign_issuer_falls_in_the_issuer_step_and_costs_no_outgoing_call() -> None:
    """No respx route is armed: an outgoing fetch here would end the test, not pass it."""
    result = await exchange_dryrun.dry_run(
        token(iss="https://evil.example.org/realms/f13"), config_for()
    )
    assert_fell_at(result, "issuer_matches", errors.REASON_EXCHANGE_ISSUER)


# --- no value of the token ever leaves the rule (T-24-09) ------------------------------------

MARKER = "zzmarkerzz"


@pytest.mark.anyio
async def test_no_field_of_an_answer_carries_a_value_out_of_the_token() -> None:
    """The step says which rule fell, never which value it saw.

    Every claim an attacker controls carries the marker, and so does the key id: if any of
    them were echoed into a field, the console of plan 24-06 would print a foreign realm's
    text on an administrator's terminal, and a refusal would become an oracle.
    """
    marked = token(
        kid=f"{MARKER}-kid",
        azp=f"{MARKER}-azp",
        aud=f"{MARKER}-aud",
        sub=f"{MARKER}-sub",
        iss=f"https://{MARKER}.example.org/realms/f13",
    )
    result = await exchange_dryrun.dry_run(marked, config_for())
    assert_fell_at(result, "issuer_matches", errors.REASON_EXCHANGE_ISSUER)
    assert MARKER not in serialized(result)
    assert marked[:32] not in serialized(result)


# --- the shape of a result ---------------------------------------------------------------


@pytest.mark.anyio
async def test_every_reason_of_a_fallen_step_is_one_of_the_frozen_identifiers() -> None:
    result = await exchange_dryrun.dry_run("", config_for())
    for step in result.steps:
        if step.outcome == exchange_dryrun.OUTCOME_FAILED:
            assert step.reason in errors.REASONS
        else:
            assert step.reason is None


@pytest.mark.anyio
async def test_a_result_is_data_and_not_a_finished_sentence() -> None:
    result = await exchange_dryrun.dry_run("", config_for())
    assert isinstance(result.steps, tuple)
    assert all(isinstance(step, exchange_dryrun.DryRunStep) for step in result.steps)
    with pytest.raises(AttributeError):
        result.passed = True  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.steps[0].outcome = "passed"  # type: ignore[misc]


# --- the key set of the run is its own (pitfall 7, T-24-07) ----------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_run_that_falls_at_the_issuer_filter_costs_no_outgoing_call() -> None:
    """The pre-authentication cost guard of the checker, kept in the dry run."""
    keys = serve()
    result = await exchange_dryrun.dry_run(
        token(iss="https://evil.example.org/realms/f13"), config_for()
    )
    assert_fell_at(result, "issuer_matches", errors.REASON_EXCHANGE_ISSUER)
    assert keys.call_count == 0


@respx.mock
@pytest.mark.anyio
async def test_a_run_past_the_issuer_filter_costs_exactly_one_outgoing_call() -> None:
    keys = serve()
    result = await exchange_dryrun.dry_run(token(), config_for())
    assert result.passed is True
    assert keys.call_count == 1


@respx.mock
@pytest.mark.anyio
async def test_the_dry_run_does_not_spend_the_brakes_of_the_running_checker() -> None:
    """Two objects, two counters: an administrator's test may not brake the hot path.

    The measurement is built so that a shared key set would be visible. Two dry runs against
    an unknown key id would arm the miss cooldown of a shared instance, and the running
    checker behind them would then be refused without a fetch, so the count would stop at
    two. It reaches three, which is the proof that the running checker still ordered its own
    fetch and that the sixty second cooldown of the hot path was never spent here.
    """
    keys = serve()
    clock = Clock()
    checker = exchange.ExchangeTokenChecker(settings_for(), clock=clock)
    unknown = token(kid="rotated-away")

    for _ in range(2):
        result = await exchange_dryrun.dry_run(unknown, config_for(), clock=clock)
        assert_fell_at(result, "key_available", errors.REASON_EXCHANGE_KEY)
    assert keys.call_count == 2, "one fetch per run, and every run brings its own key set"

    with pytest.raises(exchange.ExchangeRefused):
        await checker.claims_of(unknown)
    assert keys.call_count == 3, "the running checker still ordered a fetch of its own"


@respx.mock
@pytest.mark.anyio
async def test_a_key_set_that_cannot_be_reached_falls_in_the_key_step() -> None:
    respx.get(JWKS_URL).mock(side_effect=httpx.ConnectError("down"))
    result = await exchange_dryrun.dry_run(token(), config_for())
    assert_fell_at(result, "key_available", errors.REASON_EXCHANGE_KEY)


@respx.mock
@pytest.mark.anyio
async def test_a_jwks_carrying_only_a_symmetric_key_falls_in_the_key_step() -> None:
    serve(keys=[{"kty": "oct", "kid": KID, "k": "c2VjcmV0"}])
    result = await exchange_dryrun.dry_run(token(), config_for())
    assert_fell_at(result, "key_available", errors.REASON_EXCHANGE_KEY)


# --- the signature-covered steps ------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_signature_by_a_key_outside_the_key_set_falls_in_the_signature_step() -> None:
    serve()
    result = await exchange_dryrun.dry_run(token(OTHER_PRIVATE), config_for())
    assert_fell_at(result, "signature_and_standard_claims", errors.REASON_EXCHANGE_KEY)


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("missing", ["azp", "sub", "exp", "iat", "aud"])
async def test_a_missing_required_claim_falls_in_the_signature_step(missing: str) -> None:
    """The require list of the decoder, and its refusal is a statement about the claims."""
    serve()
    # ``None`` is what the claim builder drops, so the claim is absent rather than empty.
    dropped: dict[str, Any] = {missing: None}
    result = await exchange_dryrun.dry_run(token(**dropped), config_for())
    assert_fell_at(result, "signature_and_standard_claims", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_an_expired_token_falls_in_the_signature_step() -> None:
    serve()
    now = int(time.time())
    result = await exchange_dryrun.dry_run(token(iat=now - 400, exp=now - 100), config_for())
    assert_fell_at(result, "signature_and_standard_claims", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_an_audience_missing_the_last_path_segment_falls_in_the_audience_step() -> None:
    """``audience_holds`` is called, never re-implemented: a prefix is not the audience."""
    serve()
    result = await exchange_dryrun.dry_run(token(aud=f"{AUDIENCE}/tenant-b"), config_for())
    assert_fell_at(result, "audience_exact", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_an_audience_list_holding_the_value_exactly_passes_that_step() -> None:
    serve()
    result = await exchange_dryrun.dry_run(token(aud=["account", AUDIENCE]), config_for())
    assert result.passed is True


@respx.mock
@pytest.mark.anyio
async def test_an_acting_party_that_is_not_text_falls_in_the_named_step() -> None:
    serve()
    result = await exchange_dryrun.dry_run(token(azp=17), config_for())
    assert_fell_at(result, "acting_party_named", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_an_unlisted_acting_party_falls_in_the_allowed_step() -> None:
    serve()
    result = await exchange_dryrun.dry_run(token(azp="another-client"), config_for())
    assert_fell_at(result, "acting_party_allowed", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_an_id_token_of_the_same_realm_falls_in_the_token_type_step() -> None:
    """Same keys, same issuer, same audience: the payload ``typ`` is what tells them apart."""
    serve()
    result = await exchange_dryrun.dry_run(token(typ=exchange.ID_TOKEN_TYP), config_for())
    assert_fell_at(result, "token_type_bearer", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_a_numeric_string_time_falls_in_the_times_step() -> None:
    """What actually reaches this rule: the decoder lets a numeric string through its int()."""
    serve()
    result = await exchange_dryrun.dry_run(token(iat=str(int(time.time()))), config_for())
    assert_fell_at(result, "times_numeric", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_a_token_living_longer_than_allowed_falls_in_the_lifetime_step() -> None:
    serve()
    now = int(time.time())
    bound = exchange.MAX_TOKEN_LIFETIME_SECONDS
    result = await exchange_dryrun.dry_run(token(iat=now, exp=now + bound + 60), config_for())
    assert_fell_at(result, "lifetime_within_bound", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_a_token_older_than_allowed_falls_in_the_age_step() -> None:
    """Measured against the injected wall clock, the one the age rule is ours alone on."""
    serve()
    real = time.time()
    bound = exchange.MAX_TOKEN_LIFETIME_SECONDS
    result = await exchange_dryrun.dry_run(token(), config_for(), now=lambda: real + bound + 60)
    assert_fell_at(result, "age_within_bound", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("unusable", [" padded", "padded ", "   ", ""])
async def test_a_subject_the_checker_refuses_falls_in_the_subject_step(unusable: str) -> None:
    """A string, not empty, no edge whitespace, and handed on exactly as it arrived.

    The empty string belongs in this list and not one step earlier: the require list of the
    decoder asks whether the claim is present, and ``""`` is present. The checker measures
    the same thing in ``test_an_empty_sub_is_refused``, which is the claim group as well.
    """
    serve()
    result = await exchange_dryrun.dry_run(token(sub=unusable), config_for())
    assert_fell_at(result, "subject_usable", errors.REASON_EXCHANGE_CLAIMS)


@respx.mock
@pytest.mark.anyio
async def test_a_subject_the_mapping_refuses_falls_in_the_mapping_step() -> None:
    """The step calls ``principal_from_claims`` itself, so it cannot drift from operation.

    A forward slash is one of the characters Nextcloud refuses in a user id. The checker has
    no rule against it (it is a non-empty string without edge whitespace), the mapping has,
    and the operating path answers such a token with no principal at all.
    """
    serve()
    result = await exchange_dryrun.dry_run(token(sub="alice/bob"), config_for())
    assert_fell_at(result, "mapping_yields_principal", errors.REASON_EXCHANGE_ACCOUNT)
    assert (
        mapping.principal_from_claims(
            {"sub": "alice/bob"},
            mapping.MappingSettings(strategy=mapping.MAPPING_ACCOUNT_ID_V1, account_claim="sub"),
        )
        is None
    )


# --- the step that is never executed (pitfall 8, T-24-23) ------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_green_run_passes_and_still_says_the_account_was_not_checked() -> None:
    serve()
    result = await exchange_dryrun.dry_run(token(), config_for())
    assert result.passed is True
    for step in result.steps:
        if step.step == exchange_dryrun.STEP_ACCOUNT_EXISTS:
            assert step.outcome == exchange_dryrun.OUTCOME_NOT_CHECKED
            assert step.note == exchange_dryrun.NOTE_WOULD_CALL_NEXTCLOUD
        else:
            assert step.outcome == exchange_dryrun.OUTCOME_PASSED


@respx.mock
@pytest.mark.anyio
async def test_the_account_step_stands_in_the_answer_in_all_three_shapes() -> None:
    """Early failure, late failure, green run: never absent, because absence reads green."""
    serve()
    runs = [
        await exchange_dryrun.dry_run("", config_for()),
        await exchange_dryrun.dry_run(token(azp="another-client"), config_for()),
        await exchange_dryrun.dry_run(token(), config_for()),
    ]
    for result in runs:
        step = step_named(result, exchange_dryrun.STEP_ACCOUNT_EXISTS)
        assert step.note == exchange_dryrun.NOTE_WOULD_CALL_NEXTCLOUD
        assert step.outcome in (
            exchange_dryrun.OUTCOME_SKIPPED,
            exchange_dryrun.OUTCOME_NOT_CHECKED,
        )


@respx.mock
@pytest.mark.anyio
async def test_a_green_answer_carries_both_qualifying_sentences() -> None:
    """Honesty belongs in the answer, not only in a docstring (the rule of LIMIT_SENTENCE)."""
    serve()
    result = await exchange_dryrun.dry_run(token(), config_for())
    assert result.limit_sentence == exchange_dryrun.LIMIT_SENTENCE
    assert result.cost_sentence == exchange_dryrun.COST_SENTENCE
    assert "account" in result.limit_sentence
    assert "clock" in result.limit_sentence
    assert "one outgoing key set request" in result.cost_sentence


@respx.mock
@pytest.mark.anyio
async def test_no_field_of_a_green_answer_carries_a_value_out_of_the_token() -> None:
    """The same marker test as on a refusal, now on the path where every rule held."""
    issuer = f"https://{MARKER}.example.org/realms/f13"
    jwks_url = f"{issuer}/protocol/openid-connect/certs"
    marked_kid = f"{MARKER}-kid"
    marked_audience = f"https://cloud.example.org/{MARKER}"
    serve(jwks_url, [jwk_of(PRIVATE, kid=marked_kid)])
    config = config_for(
        issuer=issuer,
        jwks_uri=jwks_url,
        audience=marked_audience,
        azp_allowed=(f"{MARKER}-azp",),
    )
    marked = token(
        kid=marked_kid,
        iss=issuer,
        aud=marked_audience,
        azp=f"{MARKER}-azp",
        sub=f"{MARKER}-sub",
    )
    result = await exchange_dryrun.dry_run(marked, config)
    assert result.passed is True
    assert MARKER not in serialized(result)
    assert marked[:32] not in serialized(result)


# --- no session, no store, no audit line (T-24-22) -------------------------------------------


class Exploding:
    """Anything a dry run must not touch. Every contact ends the test."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("the dry run opened something it must never open")

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the dry run reached for {name}")


@respx.mock
@pytest.mark.anyio
async def test_a_full_run_opens_no_store_and_writes_no_audit_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both stores and the database driver below them are poisoned; the run still completes."""

    def never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the dry run opened a database")

    monkeypatch.setattr(oauth_store, "OAuthStore", Exploding)
    monkeypatch.setattr(audit_store, "AuditStore", Exploding)
    monkeypatch.setattr(sqlite3, "connect", never)
    serve()
    result = await exchange_dryrun.dry_run(token(), config_for())
    assert result.passed is True


def test_the_rule_reaches_for_no_identity_and_for_no_store() -> None:
    """Measured on the source, so the absence cannot be undone by a helpful later hand."""
    source = inspect.getsource(exchange_dryrun)
    for forbidden in (
        "resolve_identity",
        "identity_for",
        "ExchangeAccounts",
        "OAuthStore",
        "AuditStore",
        "note_refusal",
    ):
        assert forbidden not in source, forbidden

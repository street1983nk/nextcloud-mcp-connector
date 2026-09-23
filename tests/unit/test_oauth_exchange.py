"""The exchange token checker, spoken to directly: every rule of EXCH-02, one test each.

Keys are generated per test run, every key set answer is served by respx, and nothing
leaves the process: no server is started and no real provider is asked. The checker is
exercised without the transport boundary on purpose; the chain that wires it in is
phase 22, and the decoupling is part of the proof.

Claim times are built against the real wall clock, because PyJWT checks ``exp``, ``nbf``
and ``iat`` against its own wall clock and that one is not injectable. The injected wall
clock stand-in of the checker is used only where a rule is purely ours.

No test asserts a refusal text: the wordings are internal log phrases, not an interface.
Every refusal is the same :class:`exchange.ExchangeRefused` from the outside.
"""

import ast
import base64
import inspect
import json
import json.scanner
import logging
import sys
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from mcp_connector import errors
from mcp_connector.oauth import exchange, jwks

ISSUER = "https://idp.example.org/realms/f13"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"
AUDIENCE = "https://cloud.example.org/exapps/mcp_connector/mcp"
AZP = "f13-orchestrator"
KID = "key-1"
SUB = "service-account-f13"
SHARED_SECRET = "client-secret-long-enough-for-hmac-sha256-0123456789"

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwk_of(private: rsa.RSAPrivateKey, kid: str = KID, **extra: Any) -> dict[str, Any]:
    entry = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    entry.update({"kid": kid, "use": "sig", "alg": "RS256"}, **extra)
    return entry


class Clock:
    """A hand-turned clock, so cache expiry and cooldown are decided by the test."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def serve(keys: list[dict[str, Any]] | None = None) -> respx.Route:
    payload = {"keys": keys if keys is not None else [jwk_of(PRIVATE)]}
    return respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=payload))


def settings_for(**overrides: Any) -> exchange.ExchangeSettings:
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "jwks_uri": JWKS_URL,
        "audience": AUDIENCE,
        "azp_allowed": (AZP,),
    }
    values.update(overrides)
    return exchange.ExchangeSettings(**values)


def checker_for(
    clock: Clock | None = None,
    now: Any = None,
    max_token_bytes: int | None = None,
    **overrides: Any,
) -> exchange.ExchangeTokenChecker:
    bound: dict[str, Any] = {} if max_token_bytes is None else {"max_token_bytes": max_token_bytes}
    return exchange.ExchangeTokenChecker(
        settings_for(**overrides), clock=clock or Clock(), now=now, **bound
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


def unsigned_token(**overrides: Any) -> str:
    """A token with ``alg: none`` and an empty signature."""

    def part(value: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT', 'kid': KID})}.{part(claims(**overrides))}."


# --- settings ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"issuer": "http://idp.example.org/realms/f13"},
        {"issuer": f"{ISSUER}/"},
        {"jwks_uri": "https://elsewhere.example.org/certs"},
        {"jwks_uri": "http://idp.example.org/realms/f13/certs"},
        {"audience": ""},
        {"audience": ["one", "two"]},
        {"azp_allowed": ()},
        {"azp_allowed": ("",)},
        {"algorithms": ("HS256",)},
        {"algorithms": ("none",)},
        {"algorithms": ()},
        {"leeway_seconds": 0},
        {"max_lifetime_seconds": -1},
        {"leeway_seconds": float("nan")},
        {"leeway_seconds": float("inf")},
        {"max_lifetime_seconds": float("nan")},
        {"max_lifetime_seconds": float("inf")},
        {"leeway_seconds": "30"},
        {"max_lifetime_seconds": None},
        {"leeway_seconds": True},
        {"typ_expected": 5},
        {"typ_expected": "   "},
        {"jwks_uri": None},
        {"jwks_origin": 7},
        {"audience": 1234},
    ],
    ids=[
        "plain http issuer",
        "trailing slash issuer",
        "jwks off the issuer origin",
        "plain http jwks",
        "empty audience",
        "audience as a list",
        "empty azp allowlist",
        "empty azp entry",
        "symmetric algorithm",
        "no signature at all",
        "no algorithms",
        "zero leeway",
        "negative lifetime",
        "a leeway of nan",
        "a leeway of inf",
        "a lifetime of nan",
        "a lifetime of inf",
        "a leeway as a string",
        "a lifetime of None",
        "a leeway as a bool",
        "typ_expected as a number",
        "typ_expected as whitespace",
        "jwks_uri as None",
        "jwks_origin as a number",
        "audience as a number",
    ],
)
def test_a_bad_configuration_is_refused_on_construction(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"."):
        settings_for(**overrides)


def test_an_allowlist_is_a_sequence_of_strings_never_a_bare_string() -> None:
    """A string is iterable, so a bare one becomes an allowlist of single characters.

    Practically that refuses every real token, so it is not fail open; it is the silent
    configuration error that only surfaces in phase 22 as "nothing works any more", and a
    client id of a single character would in fact have matched.
    """
    with pytest.raises(ValueError, match=r"sequence"):
        settings_for(azp_allowed=AZP)
    with pytest.raises(ValueError, match=r"sequence"):
        settings_for(algorithms="RS256")
    with pytest.raises(ValueError, match=r"."):
        settings_for(azp_allowed={"one": AZP})

    assert settings_for(azp_allowed=[AZP]).azp_allowed == [AZP]


def test_a_time_that_is_not_a_finite_number_never_reaches_the_hot_path() -> None:
    """The anchor of CR-02: nan passes every comparison, so it must fall at construction.

    With ``leeway_seconds = nan`` every comparison of PyJWT and of the two own lifetime
    rules is false, which switches the expiry check off without a word anywhere. The
    counter-proof is not a refusal of the token: it is that no checker with such a
    configuration can be built at all.
    """
    for value in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match=r"."):
            settings_for(leeway_seconds=value)
        with pytest.raises(ValueError, match=r"."):
            settings_for(max_lifetime_seconds=value)


def test_a_named_second_origin_keeps_the_https_same_origin_rule() -> None:
    internal = "https://keys.internal.example.org"
    settings_for(jwks_origin=internal, jwks_uri=f"{internal}/certs")

    with pytest.raises(ValueError, match=r"."):
        settings_for(
            jwks_origin="http://keys.internal.example.org",
            jwks_uri="http://keys.internal.example.org/certs",
        )


# --- acceptance -------------------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_complete_token_is_accepted_and_returns_its_claims() -> None:
    serve()

    found = await checker_for().claims_of(token())

    assert found["sub"] == SUB
    assert found["iss"] == ISSUER
    assert found["typ"] == "Bearer"


# --- refusals, one rule each ------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_foreign_issuer_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(iss="https://evil.example.org/realms/f13"))


@respx.mock
@pytest.mark.anyio
async def test_a_signature_by_a_key_outside_the_jwks_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(OTHER_PRIVATE))


@respx.mock
@pytest.mark.anyio
async def test_hs256_with_a_shared_secret_is_refused() -> None:
    serve()
    bearer = jwt.encode(claims(), SHARED_SECRET, algorithm="HS256", headers={"kid": KID})
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(bearer)


@respx.mock
@pytest.mark.anyio
async def test_an_unsigned_token_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(unsigned_token())


@respx.mock
@pytest.mark.anyio
async def test_a_jwks_carrying_only_a_symmetric_key_is_refused() -> None:
    serve([{"kty": "oct", "k": base64.urlsafe_b64encode(b"0" * 32).decode(), "kid": KID}])
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token())


@respx.mock
@pytest.mark.anyio
async def test_an_unknown_kid_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(kid="unknown-key"))


@respx.mock
@pytest.mark.anyio
async def test_a_token_without_a_kid_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(kid=None))


@respx.mock
@pytest.mark.anyio
async def test_an_expired_token_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(exp=int(time.time()) - 3600))


@respx.mock
@pytest.mark.anyio
async def test_a_token_not_yet_valid_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(nbf=int(time.time()) + 3600))


@respx.mock
@pytest.mark.anyio
async def test_a_token_without_an_audience_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(aud=None))


@respx.mock
@pytest.mark.anyio
async def test_a_token_without_iat_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(iat=None))


@respx.mock
@pytest.mark.anyio
async def test_a_token_without_exp_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(exp=None))


@respx.mock
@pytest.mark.anyio
async def test_an_empty_sub_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(sub=""))


@respx.mock
@pytest.mark.anyio
async def test_a_missing_sub_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(sub=None))


@respx.mock
@pytest.mark.anyio
async def test_a_padded_sub_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(sub=" padded"))


@respx.mock
@pytest.mark.anyio
async def test_an_empty_token_string_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of("")


# --- an unusable key set is a refusal, never an acceptance -------------------------------


@respx.mock
@pytest.mark.anyio
async def test_an_unreachable_key_set_is_a_refusal_never_an_acceptance() -> None:
    respx.get(JWKS_URL).mock(side_effect=httpx.ConnectError("no route to the provider"))
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token())


@respx.mock
@pytest.mark.anyio
async def test_a_key_set_answering_500_is_a_refusal() -> None:
    respx.get(JWKS_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token())


# --- typ: the payload claim decides, the header is tolerated ------------------------------


@respx.mock
@pytest.mark.anyio
async def test_an_id_token_of_the_same_realm_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(typ=exchange.ID_TOKEN_TYP))


@respx.mock
@pytest.mark.anyio
async def test_a_token_without_a_typ_claim_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(typ=None))


@respx.mock
@pytest.mark.anyio
async def test_a_header_typ_of_at_jwt_is_accepted() -> None:
    serve()

    found = await checker_for().claims_of(token(headers={"typ": "at+jwt"}))

    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
async def test_the_header_typ_is_compared_without_case() -> None:
    serve()

    found = await checker_for().claims_of(token(headers={"typ": "AT+JWT"}))

    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
async def test_a_missing_header_typ_is_no_refusal() -> None:
    # PyJWT drops a falsy header typ from the header instead of writing it.
    serve()

    found = await checker_for().claims_of(token(headers={"typ": None}))

    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
async def test_a_foreign_header_typ_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(headers={"typ": "dpop+jwt"}))


# --- clock skew: inside the tolerance holds, beyond it falls, in both directions ----------


@respx.mock
@pytest.mark.anyio
async def test_an_exp_twenty_seconds_past_holds_inside_the_leeway() -> None:
    serve()

    found = await checker_for().claims_of(token(exp=int(time.time()) - 20))

    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
async def test_an_exp_forty_five_seconds_past_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(exp=int(time.time()) - 45))


@respx.mock
@pytest.mark.anyio
async def test_an_nbf_twenty_seconds_ahead_holds_inside_the_leeway() -> None:
    serve()

    found = await checker_for().claims_of(token(nbf=int(time.time()) + 20))

    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
async def test_an_nbf_forty_five_seconds_ahead_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(nbf=int(time.time()) + 45))


@respx.mock
@pytest.mark.anyio
async def test_a_missing_nbf_is_no_refusal() -> None:
    # nbf is checked when it is there and never required; the base token carries none.
    serve()

    found = await checker_for().claims_of(token())

    assert "nbf" not in found


# --- lifetime and age: rules PyJWT does not bring -----------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_a_lifetime_beyond_the_maximum_is_refused_even_while_valid() -> None:
    serve()
    now = int(time.time())
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(iat=now - 100, exp=now + 900))


@respx.mock
@pytest.mark.anyio
async def test_an_iat_older_than_the_maximum_age_is_refused() -> None:
    # Measured against the injected wall clock of the checker, not against PyJWT's own:
    # the token is still valid by exp, only its age breaks the rule.
    serve()
    ahead = time.time() + exchange.MAX_TOKEN_LIFETIME_SECONDS + 100
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for(now=lambda: ahead).claims_of(token())


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iat": {"value": 1}},
        {"iat": [1]},
        {"nbf": {"value": 1}},
        {"exp": {"value": 1}},
        {"exp": [1]},
        {"exp": float("inf")},
        {"iat": float("inf")},
        {"nbf": float("inf")},
        {"exp": float("nan")},
    ],
    ids=[
        "iat as an object",
        "iat as a list",
        "nbf as an object",
        "exp as an object",
        "exp as a list",
        "exp as Infinity",
        "iat as Infinity",
        "nbf as Infinity",
        "exp as NaN",
    ],
)
async def test_a_hostile_time_claim_is_a_refusal_never_an_arithmetic_error(
    overrides: dict[str, Any],
) -> None:
    """PyJWT computes int(claim) and catches ValueError alone.

    An object or a list makes that a TypeError, Infinity an OverflowError, and neither is
    a PyJWTError. json.loads accepts the non-standard literal Infinity, so the token needs
    nothing but a valid signature of the configured issuer to reach the arithmetic.
    """
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(**overrides))


@respx.mock
@pytest.mark.anyio
async def test_a_non_numeric_iat_is_a_refusal_not_a_type_error() -> None:
    # PyJWT itself lets a numeric string through int(); the lifetime rules do not.
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(iat=str(int(time.time()))))


# --- the pre-filter: a foreign issuer never triggers an outgoing fetch --------------------


@respx.mock
@pytest.mark.anyio
async def test_a_foreign_issuer_causes_no_outgoing_fetch() -> None:
    route = serve()

    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(iss="https://evil.example.org/realms/f13"))

    assert route.call_count == 0, "the pre-filter refuses before any key is looked at"


# --- the size guard and the unverified parse: fail closed before any decoding -------------
#
# Everything in this section is pre-authentication: a stranger reaches it with an HTTP
# request, no key and no signature. The rule of the module docstring (every input ends in
# exactly one detail-free exception) is proven here against the two parsing steps that run
# on unverified bytes.

#: Measured against the installed parser, not guessed: at this depth ``json.loads`` runs
#: out of stack and raises RecursionError, which is neither a ValueError nor a PyJWTError,
#: so PyJWT does not catch it on the payload (it does on the header). The token built from
#: it stays under MAX_TOKEN_BYTES, which is why a byte limit alone would not close CR-01.
#: The test below fails loudly if a future parser stops overflowing at this depth.
NESTING_DEPTH = 2998


def segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def payload_bytes_of(bearer: str) -> bytes:
    raw = bearer.split(".")[1]
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def deeply_nested_token(depth: int = NESTING_DEPTH) -> str:
    """Header, payload and signature segment of the CR-01 case, without a key."""
    header = segment(json.dumps({"alg": "RS256", "kid": KID, "typ": "JWT"}).encode())
    payload = segment(b'{"iss":' + b"[" * depth + b"]" * depth + b"}")
    return f"{header}.{payload}.AAAA"


def test_the_nesting_depth_of_the_corpus_case_still_overflows_the_json_parser() -> None:
    """The overflow depth of json.loads is platform dependent (CI runs 35429889426
    and 35430504542: the C scanner guards against the C stack, which differs per
    platform, and since CPython 3.12 sys.setrecursionlimit does not reach it).
    The pure-Python scanner recurses on the interpreter's own limit, so under an
    explicit limit of 1000 the corpus token overflows it on every platform, which
    proves the corpus case exercises the very error class the guard has to contain."""
    bearer = deeply_nested_token()
    assert len(bearer.encode("utf-8")) < exchange.MAX_TOKEN_BYTES
    decoder = json.decoder.JSONDecoder()
    # typeshed declares neither the pure-Python scanner nor scan_once as
    # assignable; CPython has both, and the RecursionError below asserts it.
    decoder.scan_once = json.scanner.py_make_scanner(decoder)  # type: ignore[attr-defined]
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(1000)
    try:
        with pytest.raises(RecursionError):
            decoder.decode(payload_bytes_of(bearer).decode("utf-8"))
    finally:
        sys.setrecursionlimit(limit)


@respx.mock
@pytest.mark.anyio
async def test_a_deeply_nested_payload_is_a_refusal_never_a_recursion_error() -> None:
    route = serve()

    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(deeply_nested_token())

    assert route.call_count == 0, "a stranger must not be able to order a key fetch here"


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("failure", [RecursionError, ValueError, TypeError, MemoryError])
async def test_anything_out_of_the_unverified_parse_is_a_refusal(
    monkeypatch: pytest.MonkeyPatch, failure: type[BaseException]
) -> None:
    """Fail closed by class, not by the list of errors one library version happens to raise."""
    serve()

    def boom(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise failure("out of the unverified parse")

    monkeypatch.setattr(jwt, "decode", boom)
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token())


@respx.mock
@pytest.mark.anyio
async def test_a_token_beyond_the_byte_limit_falls_before_the_first_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The limit stands in front of base64 and JSON, not behind them."""
    serve()

    def never(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("the token was decoded although it is longer than allowed")

    monkeypatch.setattr(jwt, "get_unverified_header", never)
    monkeypatch.setattr(jwt, "decode", never)
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for(max_token_bytes=512).claims_of(token())


@respx.mock
@pytest.mark.anyio
async def test_an_oversized_token_is_refused_although_every_claim_would_hold() -> None:
    route = serve()
    padded = token(sub=SUB + "x" * exchange.MAX_TOKEN_BYTES)
    assert len(padded.encode("utf-8")) > exchange.MAX_TOKEN_BYTES

    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(padded)

    assert route.call_count == 0


@respx.mock
@pytest.mark.anyio
async def test_the_payload_is_decoded_and_parsed_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cost filter parses the payload to read iss; the decoder must not repeat it.

    Measured before the fix: the second pass is the whole difference between 1202 ms and
    1542 ms on an eight megabyte payload, and it is a second surface of the same class as
    CR-01. The signature still decides before a single claim is read; only the parsing of
    the very same bytes of the very same token happens once.
    """
    serve()
    checker = checker_for()
    bearer = token()
    await checker.claims_of(bearer)  # warms the key cache, so nothing below goes out

    wanted = payload_bytes_of(bearer)
    parsed: list[int] = []
    genuine = json.loads

    def counting(value: Any, *args: Any, **kwargs: Any) -> Any:
        raw = value.encode("utf-8") if isinstance(value, str) else value
        if isinstance(raw, bytes | bytearray) and bytes(raw) == wanted:
            parsed.append(1)
        return genuine(value, *args, **kwargs)

    monkeypatch.setattr(json, "loads", counting)
    found = await checker.claims_of(bearer)

    assert found["sub"] == SUB
    assert parsed == [1], "the payload of one token is parsed once, not twice"


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "8192", None, float("inf")])
def test_a_bad_byte_limit_is_refused_on_construction(value: Any) -> None:
    with pytest.raises(ValueError, match=r"."):
        exchange.ExchangeTokenChecker(settings_for(), max_token_bytes=value)


def test_the_byte_limit_is_a_module_constant_phase_22_can_read() -> None:
    assert "MAX_TOKEN_BYTES" in exchange.__all__
    assert isinstance(exchange.MAX_TOKEN_BYTES, int)
    assert exchange.MAX_TOKEN_BYTES > 0


# --- the audience holds exactly, never as a prefix and never as an OR ----------------------


TRUNCATED_AUDIENCE = AUDIENCE.rsplit("/", 1)[0]


def test_required_claims_name_azp_after_the_standard_claims() -> None:
    assert exchange.REQUIRED_CLAIMS == ("iss", "sub", "aud", "exp", "iat", "typ", "azp")


def test_the_required_claims_cannot_be_weakened_at_runtime() -> None:
    """The rule the decoder executes, exported: a list would be removable from anywhere.

    Every other rule constant of the module is a frozenset or a tuple. This one was a
    list, so a single ``exchange.REQUIRED_CLAIMS.remove("azp")`` anywhere in the process
    would have weakened every checker that exists and every one built afterwards, without
    touching a construction or a configuration.
    """
    assert isinstance(exchange.REQUIRED_CLAIMS, tuple)
    assert not hasattr(exchange.REQUIRED_CLAIMS, "remove")


def test_the_exchange_module_imports_no_resource_matcher_and_nothing_of_the_sdk() -> None:
    """The gate of the must-haves: check_resource_allowed stays out of the exchange path.

    The function compares the path as a prefix, which is right for our own tokens in
    oauth/verifier.py and wrong for a foreign audience. The gate reads the imports of the
    module, so the prefix matcher cannot come back quietly with a refactor.
    """
    tree = ast.parse(inspect.getsource(exchange))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported.extend(alias.name for alias in node.names)
    assert "check_resource_allowed" not in imported
    assert not any(name == "mcp" or name.startswith("mcp.") for name in imported)
    # One name for the constant time comparison across the repository, so a search for
    # every comparison site finds them all: oauth/principal.py and the other sites use
    # secrets, and hmac.compare_digest is the same function under a second name.
    assert "secrets" in imported
    assert "hmac" not in imported


@pytest.mark.parametrize(
    ("claim", "holds"),
    [
        (AUDIENCE, True),
        (AUDIENCE + "/tenant-b", False),
        (TRUNCATED_AUDIENCE, False),
        (["account", AUDIENCE], True),
        (["account"], False),
        ([], False),
        ([1234, AUDIENCE], False),
        ([None, AUDIENCE], False),
        (None, False),
        ({"value": AUDIENCE}, False),
        ((AUDIENCE,), False),
    ],
    ids=[
        "the exact string holds",
        "a tenant suffix never holds",
        "a truncated path never holds",
        "exact membership in a list holds",
        "a list without the value never holds",
        "an empty list never holds",
        "a numeric entry poisons the list",
        "a null entry poisons the list",
        "a missing claim never holds",
        "an object is no audience",
        "a tuple is no audience",
    ],
)
def test_audience_holds_is_exact_equality_or_exact_membership(claim: object, holds: bool) -> None:
    assert exchange.audience_holds(claim, AUDIENCE) is holds


def test_an_empty_expectation_and_an_empty_claim_never_hold() -> None:
    """The rule of principal.same_principal (D-37), and a rule of this function.

    ``same_principal`` refuses an empty value before the comparison, so a request without
    an identity never passes as the owner of a row that has none either. audience_holds
    quoted the form of that comparison and not its rule: ``audience_holds("", "")`` held.
    Today the guard on the settings keeps the expectation non-empty, but the function is
    exported, stands forty lines from that guard and is what a later caller reaches for.
    """
    assert exchange.audience_holds("", "") is False
    assert exchange.audience_holds([""], "") is False
    assert exchange.audience_holds(AUDIENCE, "") is False
    assert exchange.audience_holds([AUDIENCE], "") is False
    assert exchange.audience_holds("", AUDIENCE) is False
    assert exchange.audience_holds([""], AUDIENCE) is False


@respx.mock
@pytest.mark.anyio
async def test_an_audience_with_a_tenant_suffix_is_refused() -> None:
    # The counter-proof to the prefix semantics: a token for .../mcp/tenant-b must never
    # pass the check against the configured .../mcp.
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(aud=f"{AUDIENCE}/tenant-b"))


@respx.mock
@pytest.mark.anyio
async def test_an_audience_missing_the_last_path_segment_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(aud=TRUNCATED_AUDIENCE))


@respx.mock
@pytest.mark.anyio
async def test_a_multi_audience_carrying_the_configured_value_holds() -> None:
    # Keycloak regularly writes several audiences, classically ``account`` beside the
    # target; exact membership of the one configured value is what holds.
    serve()

    found = await checker_for().claims_of(token(aud=["account", AUDIENCE]))

    assert found["sub"] == SUB


@respx.mock
@pytest.mark.anyio
async def test_a_multi_audience_without_the_configured_value_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(aud=["account"]))


@respx.mock
@pytest.mark.anyio
async def test_an_empty_audience_list_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(aud=[]))


@respx.mock
@pytest.mark.anyio
async def test_a_non_string_entry_beside_the_right_value_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(aud=[1234, AUDIENCE]))


# --- the acting party: an azp allowlist replaces the act claim Keycloak does not write ----


@respx.mock
@pytest.mark.anyio
async def test_an_unknown_azp_is_refused_despite_a_valid_signature() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(azp="someone-else"))


@respx.mock
@pytest.mark.anyio
async def test_a_missing_azp_is_refused_despite_a_valid_signature() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(azp=None))


@respx.mock
@pytest.mark.anyio
async def test_a_non_string_azp_is_refused() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(azp=1234))


@respx.mock
@pytest.mark.anyio
async def test_a_two_entry_allowlist_accepts_both_and_refuses_a_third() -> None:
    serve()
    checker = checker_for(azp_allowed=("first-party", "second-party"))

    assert (await checker.claims_of(token(azp="first-party")))["azp"] == "first-party"
    assert (await checker.claims_of(token(azp="second-party")))["azp"] == "second-party"
    with pytest.raises(exchange.ExchangeRefused):
        await checker.claims_of(token(azp="third-party"))


# --- the negative corpus: deliberately-off tokens, because no F13 sample exists yet --------
#
# The cases build wrong on purpose (the counter-measure the research names for exactly
# this state): a self-made token that matches the checker's own expectation proves only
# the expectation. Conspicuous canary values make the leak gate below searchable; none of
# them appears anywhere else in this repository.

EXCHANGE_LOGGER = "mcp_connector.oauth.exchange"


@pytest.fixture
def spoken() -> Iterator[list[logging.LogRecord]]:
    """Every record of the exchange logger, collected at that logger itself.

    Not caplog alone: ``nextcloud.http.configure_logging`` sets ``propagate = False`` on
    the package logger and pins its level, so whether a record of this module ever reaches
    a root handler depends on the order the suite is shuffled into. A handler on the
    logger under test is independent of both, which is what a gate about log content has
    to be.
    """
    logger = logging.getLogger(EXCHANGE_LOGGER)
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collect(level=logging.DEBUG)
    was = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(was)


CANARY_SUB = "sub-canary-7f3ad9-nowhere-else"
CANARY_EMAIL = "canary-mailbox-9c2b@leak-canary.example"
CANARY_USERNAME = "canary-username-5b1d"
CANARY_AZP = "azp-canary-2e8f"

#: Its own issuer, its own key and its own JWKS route, so this case is a realm boundary
#: and never accidentally the same case as "a signature by the wrong key".
SECOND_REALM_ISSUER = "https://second-idp.example.org/realms/elsewhere"
SECOND_REALM_JWKS_URL = f"{SECOND_REALM_ISSUER}/protocol/openid-connect/certs"
SECOND_REALM_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
SECOND_REALM_KID = "second-realm-key"


def canary_token(
    private: Any = PRIVATE,
    *,
    algorithm: str = "RS256",
    kid: str | None = KID,
    **overrides: Any,
) -> str:
    values: dict[str, Any] = {
        "sub": CANARY_SUB,
        "email": CANARY_EMAIL,
        "preferred_username": CANARY_USERNAME,
        "azp": CANARY_AZP,
    }
    values.update(overrides)
    return token(private, algorithm=algorithm, kid=kid, **values)


def canary_checker() -> exchange.ExchangeTokenChecker:
    return checker_for(azp_allowed=(CANARY_AZP,))


def serve_both_realms() -> None:
    serve()
    respx.get(SECOND_REALM_JWKS_URL).mock(
        return_value=httpx.Response(
            200, json={"keys": [jwk_of(SECOND_REALM_PRIVATE, kid=SECOND_REALM_KID)]}
        )
    )


NEGATIVE_CORPUS: list[tuple[str, Callable[[], str]]] = [
    ("a missing azp", lambda: canary_token(azp=None)),
    (
        "a multi-audience without the expected value",
        lambda: canary_token(aud=["account", "some-other-client"]),
    ),
    (
        "an audience that only prefixes the configured one",
        lambda: canary_token(aud=f"{AUDIENCE}/tenant-b"),
    ),
    ("an id token of the same realm", lambda: canary_token(typ=exchange.ID_TOKEN_TYP)),
    (
        "a token of a second realm",
        lambda: canary_token(SECOND_REALM_PRIVATE, kid=SECOND_REALM_KID, iss=SECOND_REALM_ISSUER),
    ),
    ("an unknown kid", lambda: canary_token(kid="kid-nobody-serves")),
    ("a signature by the wrong key", lambda: canary_token(OTHER_PRIVATE)),
    (
        "hs256 with the shared secret",
        lambda: jwt.encode(
            claims(
                sub=CANARY_SUB,
                email=CANARY_EMAIL,
                preferred_username=CANARY_USERNAME,
                azp=CANARY_AZP,
            ),
            SHARED_SECRET,
            algorithm="HS256",
            headers={"kid": KID},
        ),
    ),
    (
        "alg none with an empty signature",
        lambda: unsigned_token(
            sub=CANARY_SUB,
            email=CANARY_EMAIL,
            preferred_username=CANARY_USERNAME,
            azp=CANARY_AZP,
        ),
    ),
    ("an expired token", lambda: canary_token(exp=int(time.time()) - 3600)),
    ("an nbf in the future", lambda: canary_token(nbf=int(time.time()) + 3600)),
    (
        "a lifetime beyond the maximum",
        lambda: canary_token(iat=int(time.time()) - 100, exp=int(time.time()) + 900),
    ),
    # The four structurally broken cases. Until they were added every case of this corpus
    # was a well-formed token with a wrong rule, which is exactly why all of it stayed
    # green while CR-01 and WR-01 stood open. They are the regression anchor for both: the
    # oracle proof and the leak gate below run over the same list and cover them with it.
    ("a payload nested past the parser", deeply_nested_token),
    (
        "a token beyond the byte limit",
        lambda: canary_token(sub=CANARY_SUB + "x" * exchange.MAX_TOKEN_BYTES),
    ),
    ("an iat that is an object", lambda: canary_token(iat={"value": 1})),
    ("an exp of Infinity", lambda: canary_token(exp=float("inf"))),
]

CORPUS_IDS = [case for case, _ in NEGATIVE_CORPUS]
CORPUS_BUILDERS = [build for _, build in NEGATIVE_CORPUS]


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("build", CORPUS_BUILDERS, ids=CORPUS_IDS)
async def test_every_corpus_case_raises_exactly_the_one_refusal(
    build: Callable[[], str],
) -> None:
    serve_both_realms()
    with pytest.raises(exchange.ExchangeRefused):
        await canary_checker().claims_of(build())


@respx.mock
@pytest.mark.anyio
async def test_the_refusal_is_indistinguishable_across_the_whole_corpus() -> None:
    """The oracle proof, measured and not asserted in prose (T-03-47 discipline).

    All refusals share one type, carry no text and no arguments; a caller who collects
    them all learns nothing about which rule fired in which case.
    """
    serve_both_realms()
    caught: list[exchange.ExchangeRefused] = []
    for _case, build in NEGATIVE_CORPUS:
        try:
            await canary_checker().claims_of(build())
        except exchange.ExchangeRefused as exc:
            caught.append(exc)

    assert len(caught) == len(NEGATIVE_CORPUS)
    assert all(type(exc) is exchange.ExchangeRefused for exc in caught)
    assert all(str(exc) == "" for exc in caught)
    assert all(exc.args == () for exc in caught)


@respx.mock
@pytest.mark.anyio
async def test_a_refusal_is_a_debug_line_and_never_a_warning(
    spoken: list[logging.LogRecord],
) -> None:
    """A stranger sets the pace of this log: one HTTP request, one line.

    The path phase 22 builds is reachable before any authentication, so the number of
    WARNING lines and the disk they cost would be an attacker's decision. The refusals
    are routine and belong on DEBUG; what an operator needs to see about rejected
    exchange attempts is AUDIT-07 in phase 24, and a log level is no substitute for it.
    """
    serve()

    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(azp="someone-else"))

    assert spoken, "a silent refusal proves nothing"
    assert all(record.levelno == logging.DEBUG for record in spoken)


@respx.mock
@pytest.mark.anyio
async def test_an_unusable_key_set_is_no_warning_either(
    spoken: list[logging.LogRecord],
) -> None:
    """The key set layer refuses through the same factory, so it is the same line.

    Deliberate and named here rather than left to be discovered: a provider that cannot
    be reached is invisible to an operator until AUDIT-07 lands.
    """
    respx.get(JWKS_URL).mock(side_effect=httpx.ConnectError("no route to the provider"))

    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token())

    assert spoken, "a key set problem is refused through the same factory"
    assert all(record.levelno == logging.DEBUG for record in spoken)


@respx.mock
@pytest.mark.anyio
async def test_no_corpus_run_writes_token_or_claim_material_into_a_log_line(
    caplog: pytest.LogCaptureFixture,
    spoken: list[logging.LogRecord],
) -> None:
    """The gate against claim leaks: DEBUG over all loggers, then a sweep per case.

    Each case must log at least one line of the exchange logger (a silent logger checks
    nothing), and no collected message or formatted line may carry the token string, one
    of its three dot segments, the sub, a set email or preferred_username, or the azp
    value.
    """
    serve_both_realms()
    caplog.set_level(logging.DEBUG)
    for case, build in NEGATIVE_CORPUS:
        bearer = build()
        caplog.clear()
        spoken.clear()
        with pytest.raises(exchange.ExchangeRefused):
            await canary_checker().claims_of(bearer)

        assert spoken, f"a silent refusal proves nothing: {case}"

        shown = logging.Formatter("%(name)s %(levelname)s %(message)s")
        written = "\n".join(
            [record.getMessage() for record in spoken]
            + [shown.format(record) for record in spoken]
            + [record.getMessage() for record in caplog.records]
            + [caplog.text]
        )
        forbidden = [
            bearer,
            *bearer.split("."),
            CANARY_SUB,
            CANARY_EMAIL,
            CANARY_USERNAME,
            CANARY_AZP,
        ]
        for value in forbidden:
            if value:
                assert value not in written, f"leaked material in a log line: {case}"


# --- the rejection group of AUDIT-07: carried by the exception, never by an answer --------
#
# The identifier is the value plan 24-04 writes into an audit line. Everything here is about
# the two halves of that: no call site may forget it, and no call site may invent one.

EXCHANGE_REASON_NAMES = frozenset(
    {
        "REASON_EXCHANGE_MALFORMED",
        "REASON_EXCHANGE_KEY",
        "REASON_EXCHANGE_ISSUER",
        "REASON_EXCHANGE_CLAIMS",
        "REASON_EXCHANGE_ACCOUNT",
        "REASON_EXCHANGE_FAILED",
    }
)

#: Read from the module, never typed here, so a renamed value cannot leave this file green.
EXCHANGE_REASONS = frozenset(getattr(errors, name) for name in EXCHANGE_REASON_NAMES)


def refused_call_sites() -> list[ast.Call]:
    """Every ``_refused(...)`` call site of the checker, counted by the AST and not by grep.

    ``grep -c "_refused("`` answers 20 on this module because the definition line counts
    itself. What the gate is about is call sites, so it parses instead of searching.
    """
    tree = ast.parse(inspect.getsource(exchange))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_refused"
    ]


def groups_named_by(node: ast.expr) -> set[str] | None:
    """The constant names an argument expression can evaluate to, or ``None`` for anything.

    ``None`` is the honest answer for every shape this gate cannot follow, and it is a
    finding rather than a pass: a value the gate cannot read is a value nobody reviews.
    """
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.IfExp):
        # The condition is not read on purpose: what is handed on is one of the two arms.
        taken = groups_named_by(node.body)
        otherwise = groups_named_by(node.orelse)
        return None if taken is None or otherwise is None else taken | otherwise
    return None


def test_no_refusal_of_the_checker_can_forget_its_group() -> None:
    """T-24-16: a call site without an identifier would silently fall back to the default.

    The default exists for ``jwks.KeySet``, which calls the factory through a
    ``Callable[[str], Exception]`` and can hand only one argument. Inside this module the
    default is never the right answer, and a new rule added without a second argument would
    be written into the audit trail as a key problem it has nothing to do with. The gate
    names file and line of every such site.
    """
    calls = refused_call_sites()
    assert len(calls) == 19, "the count of call sites changed; the grouping below has to follow"

    forgotten = [
        f"oauth/exchange.py:{call.lineno}: _refused() without its rejection group"
        for call in calls
        if len(call.args) < 2
    ]
    assert forgotten == [], "\n".join(forgotten)


def test_every_group_handed_to_a_refusal_is_one_of_the_frozen_six() -> None:
    """The identifier travels as a positional argument, where the gate of ``errors`` is blind.

    ``tests/unit/test_errors_reason.py`` watches ``reason=`` at an error construction. Here
    the value is the second argument of a factory, so nothing but this case keeps a made-up
    string out of the one path a stranger reaches without a key.

    Two shapes are allowed and no third: a bare name, and a choice between two names, which
    one site needs because the decoder carries the signature check and the standard claim
    rules in the same call. Everything else, a literal, a local variable, a function call,
    a foreign constant, is a finding with its line.
    """
    findings: list[str] = []
    for call in refused_call_sites():
        handed = call.args[1]
        named = groups_named_by(handed)
        if named is None or not named <= EXCHANGE_REASON_NAMES:
            findings.append(f"oauth/exchange.py:{handed.lineno}: {sorted(named or [])}")

    assert findings == [], (
        "a rejection group is a name of mcp_connector.errors and never anything else:\n"
        + "\n".join(findings)
    )
    assert all(getattr(errors, name) in errors.REASONS for name in EXCHANGE_REASON_NAMES)


def test_a_refusal_without_a_group_reads_as_the_unknown_case() -> None:
    """The default of the class, which is the honest answer and never a guessed one."""
    assert exchange.ExchangeRefused().reason == errors.REASON_EXCHANGE_FAILED


@respx.mock
@pytest.mark.anyio
async def test_a_token_beyond_the_byte_limit_is_a_malformed_token() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused) as refused:
        await checker_for().claims_of(token(sub=SUB + "x" * exchange.MAX_TOKEN_BYTES))
    assert refused.value.reason == errors.REASON_EXCHANGE_MALFORMED


@respx.mock
@pytest.mark.anyio
async def test_a_foreign_issuer_is_the_issuer_group() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused) as refused:
        await checker_for().claims_of(token(iss="https://evil.example.org/realms/f13"))
    assert refused.value.reason == errors.REASON_EXCHANGE_ISSUER


@respx.mock
@pytest.mark.anyio
async def test_a_wrong_audience_is_the_claims_group() -> None:
    serve()
    with pytest.raises(exchange.ExchangeRefused) as refused:
        await checker_for().claims_of(token(aud=f"{AUDIENCE}/tenant-b"))
    assert refused.value.reason == errors.REASON_EXCHANGE_CLAIMS


@respx.mock
@pytest.mark.anyio
async def test_an_unknown_kid_is_the_key_group() -> None:
    """And with it the one-argument path: the key set layer refuses through the default."""
    serve()
    with pytest.raises(exchange.ExchangeRefused) as refused:
        await checker_for().claims_of(token(kid="kid-nobody-serves"))
    assert refused.value.reason == errors.REASON_EXCHANGE_KEY


@respx.mock
@pytest.mark.anyio
async def test_an_unreachable_provider_is_the_key_group_as_well() -> None:
    """The second proof of the default: ``KeySet`` hands one argument and nothing else."""
    respx.get(JWKS_URL).mock(side_effect=httpx.ConnectError("no route to the provider"))
    with pytest.raises(exchange.ExchangeRefused) as refused:
        await checker_for().claims_of(token())
    assert refused.value.reason == errors.REASON_EXCHANGE_KEY


def test_the_key_set_layer_still_takes_a_one_argument_factory() -> None:
    """The signature the default exists for, read at the layer and not described here.

    A second parameter without a default would have made the factory unusable there, and
    the key set layer would have had to grow a rejection vocabulary of its own.

    Two sites, not one: ``KeySet.__init__`` takes the factory and ``fetch_json`` takes it a
    second time, because the hardened round trip refuses on its own (a foreign origin, an
    unreachable provider, an answer that is too large). Both are the same one-argument
    contract, and both are the reason the second parameter of ``_refused`` has a default.
    """
    assert inspect.getsource(jwks).count("refuse: Callable[[str], Exception]") == 2


@respx.mock
@pytest.mark.anyio
async def test_the_debug_line_carries_the_phrase_and_never_the_group(
    spoken: list[logging.LogRecord],
) -> None:
    """T-24-14: the log keeps the sharper wording, the audit line keeps the coarser one.

    Two readers, two needs. Whoever switches this module to DEBUG holds the instance anyway
    and is served best by the exact rule; the audit trail is read by an operator and is one
    copy away from a stranger, so it carries the group. Swapping the phrase for the
    identifier here would lose the first without gaining anything for the second.
    """
    serve()
    with pytest.raises(exchange.ExchangeRefused):
        await checker_for().claims_of(token(iss="https://evil.example.org/realms/f13"))

    written = [record.getMessage() for record in spoken]
    assert written == ["exchange refused: the token comes from another issuer"]
    for name in EXCHANGE_REASONS:
        assert name not in written[0]


# --- the revocation of phase 22 reaches the key set --------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_forget_keys_makes_the_next_check_fetch_the_key_set_again() -> None:
    """``forget_keys`` reaches into the key set layer and stops there.

    Measured at the outgoing requests, like every other cache statement of this file: two
    checks in a row cost one fetch, and one call in between costs the second. The chain of
    plan 22-02 is the only caller; nothing here binds the checker to a server.
    """
    route = serve()
    checker = checker_for()
    assert await checker.claims_of(token())
    assert await checker.claims_of(token())
    assert route.call_count == 1

    checker.forget_keys()

    assert await checker.claims_of(token())
    assert route.call_count == 2

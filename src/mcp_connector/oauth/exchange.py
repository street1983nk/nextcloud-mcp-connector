"""The freestanding checker of a foreign Keycloak JWS: issuer, signature, claims, typ.

This module answers one question and wires nothing: is this token a currently valid
access token of the one configured foreign issuer, and what are its checked claims. The
chain that places it next to the store verifier is phase 22, the mapping of a claim set
onto a Nextcloud account is phase 23; this module reads nothing from the environment and
knows no account, which is what makes every one of its rules provable against self-made
keys, without a single answer from the real orchestrator.

**Where the keys come from.** Signature keys are fetched, cached and rotated by the one
key set layer in ``oauth/jwks.py``; this module holds a ``KeySet`` and asks it for the
key behind a ``kid``. A hardening that lands in only one of two copies is how a gap
survives a fix, so no second copy of that machinery exists here, and this module never
talks to the network itself.

**Why the tolerance is smaller than in the ID token flow.** The browser identity accepts
sixty seconds of clock skew on a token that lives for minutes. An exchanged Keycloak
token is short-lived by design, and a minute of tolerance on a one-minute token doubles
its validity; thirty seconds is enough for real clock drift and no more.

**Every refusal is the same object from the outside.** One detail-free exception type,
no text and no arguments, a fixed phrase in the log, never a claim value, a token
fragment or a principal in any line: a caller who can tell a wrong signature from a
wrong audience has been handed an oracle.

The promise is about the object, and it stops there on purpose. The checker is staged
from cheap to expensive, so its duration falls into coarse classes that can be told
apart: before the payload is parsed, before the signature is checked, after it, and, with
a cold key cache, an unknown ``kid`` that costs an outgoing request. Measured over forty
runs the classes lie between 0.04 and 0.29 milliseconds. That is accepted knowingly and
not repaired here: the order is what keeps the cheap refusals cheap for a path a stranger
reaches without a key, the issuer filter is the deliberate marker in it, and what an
attacker learns from it, our issuer and a public ``kid``, is not secret. The rate at
which the classes can be sampled is the throttle of phase 22, not a reordering of rules.

**What this module cannot tell apart.** Keycloak Standard Token Exchange V2 writes no
``act`` claim, so ``azp`` is the only trace of the acting party and an ordinary
client_credentials token of the same allowed client carries the same ``iss``, ``azp``,
``typ`` and, with a matching mapper, the same ``aud``. Nothing in these rules separates
it from an exchange result. Its ``sub`` is the service account id of that client, so
whoever owns the credentials of an allowed party can assert any ``sub`` the account
mapping accepts. Phase 23 maps ``sub`` onto a Nextcloud account and is where that
decision belongs (a rule only the exchange path can meet, a scope, or an accepted
assumption written down); the limit is named here so it is not discovered there.

**The audience is instance-specific, never generic.** A generic value like ``nextcloud``
makes a token minted for instance A valid at instance B, which is exactly the tenant
boundary the audience convention exists to hold. The proposal documented towards F13 is
one Keycloak client id per connector instance, in doubt the resource URL of that
instance: the same value this server already uses for its own tokens.
"""

import logging
import math
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import urlsplit

import jwt

from ..errors import (
    REASON_EXCHANGE_CLAIMS,
    REASON_EXCHANGE_FAILED,
    REASON_EXCHANGE_ISSUER,
    REASON_EXCHANGE_KEY,
    REASON_EXCHANGE_MALFORMED,
)
from .jwks import ALLOWED_ALGORITHMS, KeySet, same_origin

__all__ = [
    "ACCEPTED_TYP_HEADERS",
    "ACCESS_TOKEN_TYP",
    "DEFAULT_EXCHANGE_ALGORITHMS",
    "EXCHANGE_LEEWAY_SECONDS",
    "ID_TOKEN_TYP",
    "MAX_TOKEN_BYTES",
    "MAX_TOKEN_LIFETIME_SECONDS",
    "REQUIRED_CLAIMS",
    "ExchangeRefused",
    "ExchangeSettings",
    "ExchangeTokenChecker",
    "audience_holds",
]

#: RS256 alone unless the operator says otherwise: it is what Keycloak signs access
#: tokens with by default, and every additional algorithm is additional attack surface.
DEFAULT_EXCHANGE_ALGORITHMS = ("RS256",)

#: Deliberately half the sixty seconds of the ID token flow: an exchanged token is
#: short-lived on purpose, and a minute of tolerance on a one-minute token would double
#: its validity. Thirty seconds covers real clock drift and no more.
EXCHANGE_LEEWAY_SECONDS = 30

#: A token older or longer-lived than this is refused, never shortened. There is no
#: introspection and no revocation list in the hot path, so the lifetime is the only
#: bound on how long a leaked or revoked-at-the-provider token keeps working here.
MAX_TOKEN_LIFETIME_SECONDS = 900

#: The hard bound on the raw token, checked before the first base64 step and therefore
#: before any attacker-shaped bytes are decoded or parsed. A Keycloak access token lives
#: between one and three kilobytes, so this leaves room for a fat realm-role mapper and
#: still refuses the payloads whose only purpose is work: a megabyte of JSON cost 175 ms
#: of measured event loop time per request, and a payload nested three thousand levels
#: deep overflows the parser at 8074 bytes. The same line ``jwks.py`` draws for a foreign
#: answer with ``MAX_RESPONSE_BYTES``, drawn here for the foreign input of every request.
#: The value is a constructor parameter of the checker, never read from the environment;
#: phase 22 owns configuration and can hand a different bound in.
MAX_TOKEN_BYTES: Final[int] = 8192

#: Keycloak writes the token type as the payload claim ``typ``; this is its value on an
#: access token. The header ``typ`` is no substitute, see the comment in ``claims_of``.
ACCESS_TOKEN_TYP = "Bearer"  # noqa: S105 - the token type of RFC 6750, not a secret

#: The payload ``typ`` of an ID token of the same realm, signed by the same keys with
#: the same issuer. The claim is what tells the two apart, which is why the tests build
#: their ID token against exactly this value.
ID_TOKEN_TYP = "ID"  # noqa: S105 - a token type name, not a secret

#: Header ``typ`` values tolerated when present, compared without case, never required.
#: Keycloak sets JWT or at+jwt depending on the age of the client (Keycloak discussion
#: 19419), so requiring at+jwt in the header, as RFC 9068 suggests, would refuse every
#: real token; do not "correct" the payload check below into a header check. A header
#: type outside this set is a different artifact altogether (a DPoP proof, a logout
#: token) and falls.
ACCEPTED_TYP_HEADERS = frozenset({"JWT", "at+jwt"})

#: The case-folded form the comparison runs against.
_TYP_HEADERS_FOLDED = frozenset(value.lower() for value in ACCEPTED_TYP_HEADERS)

#: Handed to the decoder as its require list. ``aud`` stays in it although the decoder's
#: own value comparison is switched off: a token without an audience falls already in the
#: decoder, and the value comparison in ``claims_of`` is ours. ``azp`` is required because
#: Keycloak enforces the claim on every exchanged token; a token without it is not from
#: the path this phase serves, however clean its signature.
#: Immutable on purpose, like every other rule constant here: this one is exported and
#: handed to the decoder, so a list would have been a rule any line in the process could
#: remove an entry from, weakening every existing and every future checker at once.
REQUIRED_CLAIMS: Final[tuple[str, ...]] = ("iss", "sub", "aud", "exp", "iat", "typ", "azp")

logger = logging.getLogger("mcp_connector.oauth.exchange")


class ExchangeRefused(Exception):
    """The token, a claim or the key set did not meet the rules. Carries exactly one value.

    That value is :attr:`reason`, a fixed identifier out of :data:`errors.REASONS` and one
    of the six ``exchange_`` groups. It is not a message: the exception carries no argument,
    prints as the empty string and is the same object for every refusal, which is what the
    corpus of ``tests/unit/test_oauth_exchange.py`` measures.

    **Where the identifier may go, and this is the whole of it:** into the audit line of
    AUDIT-07, written by plan 24-04. Nowhere else.

    **Where it may never go:** into an HTTP answer, in a body or in a header, and into any
    log line above DEBUG. The exchange path is reachable before any authentication, so a
    401 that says which rule fell is an oracle a stranger orders with one request, and a
    handful of them tells him whether it was the signature, the audience or the acting
    party (threat T-24-03). This paragraph is here because without it the next reader takes
    the field for an oversight and "helpfully" passes it on at the next boundary.

    A group and never the single rule: the eighteen fixed phrases of this module stay in the
    DEBUG line of :func:`_refused`, where the reader already holds the instance.
    """

    def __init__(self, reason: str = REASON_EXCHANGE_FAILED) -> None:
        # No argument to ``Exception``: ``str(exc)`` stays empty and ``exc.args`` stays
        # empty, so a caller who catches every refusal of the corpus still cannot tell two
        # of them apart. The value lives on the instance, which only the audit writer reads.
        super().__init__()
        self.reason = reason


def _refused(reason: str, identifier: str = REASON_EXCHANGE_KEY) -> ExchangeRefused:
    """One line per refusal, on DEBUG, with a fixed phrase and never a value.

    DEBUG and not WARNING, because in the path phase 22 builds this runs before any
    authentication: a stranger would otherwise decide how many WARNING lines are written
    and how much disk they cost, one HTTP request at a time, and the logging is
    synchronous. The key set layer refuses through this same factory, so a provider that
    cannot be reached is quiet here as well.

    ``reason`` is the phrase for that line and stays the sharper of the two wordings.
    ``identifier`` is the coarser one and is the value AUDIT-07 writes; the line never
    carries it, because whoever switches this module to DEBUG is served better by the exact
    rule and the audit trail is read by someone who must not learn it.

    The default of ``identifier`` is :data:`errors.REASON_EXCHANGE_KEY`, and it is bound to
    a fact rather than to convenience: the only caller that reaches this factory with one
    argument is ``jwks.py``, which takes it as a ``Callable[[str], Exception]`` in
    ``KeySet`` and in ``fetch_json``. Every refusal that comes out of there is about the key
    set of the provider or about reaching him at all. A second parameter without a default
    would have broken that signature; inside this module the default is never the answer,
    which is what the AST gate of ``tests/unit/test_oauth_exchange.py`` holds.

    What an operator needs to see about rejected exchange attempts is AUDIT-07, in the
    hash-chained audit trail and under its content bans. The identifier is the half of it
    this module owes; the writing of the line is plan 24-04 and belongs to the chain, which
    is the only place that knows whether a refusal is worth a row.
    """
    logger.debug("exchange refused: %s", reason)
    return ExchangeRefused(identifier)


@dataclass(frozen=True, slots=True)
class ExchangeSettings:
    """What phase 22 will read from configuration. Validated on construction.

    Until that phase exists, configuration is exactly these parameters: nothing here
    reads the environment, and every violation is a :class:`ValueError` while building,
    never a silent default.
    """

    issuer: str
    jwks_uri: str
    audience: str
    azp_allowed: tuple[str, ...]
    # In split networks (openDesk, agency deployments) the issuer is public and the
    # certs URL internal. The same-origin rule is the default and is never switched
    # off: it is bound to an explicitly named second origin, which must still be
    # HTTPS. Do not "clean up" this field into a switch that disables the rule.
    jwks_origin: str | None = None
    algorithms: tuple[str, ...] = DEFAULT_EXCHANGE_ALGORITHMS
    leeway_seconds: float = EXCHANGE_LEEWAY_SECONDS
    max_lifetime_seconds: float = MAX_TOKEN_LIFETIME_SECONDS
    typ_expected: str = ACCESS_TOKEN_TYP

    def __post_init__(self) -> None:
        # Every field is typed first and read second: a configuration error must arrive
        # as the ValueError this docstring promises, not as an AttributeError out of
        # ``.strip()`` or a TypeError out of a comparison three calls deeper.
        _require_text(self.issuer, "issuer")
        _require_https_url(self.issuer, "issuer")
        if self.issuer.endswith("/"):
            raise ValueError("the issuer is used exactly as configured; drop the trailing slash")
        _require_text(self.jwks_uri, "jwks_uri")
        if self.jwks_origin is not None:
            _require_text(self.jwks_origin, "jwks_origin")
            _require_https_url(self.jwks_origin, "jwks_origin")
        if not same_origin(self.jwks_uri, self.jwks_origin or self.issuer):
            raise ValueError("jwks_uri must live on the HTTPS origin of the issuer or jwks_origin")
        # Exactly one string, never a list: an expected audience that can be several
        # values turns the comparison of plan 21-02 into an OR, which is pitfall 2.
        _require_text(self.audience, "audience")
        if not self.audience.strip():
            raise ValueError("the audience is exactly one non-empty string")
        _require_string_sequence(self.azp_allowed, "azp_allowed")
        _require_string_sequence(self.algorithms, "algorithms")
        if not set(self.algorithms) <= ALLOWED_ALGORITHMS:
            raise ValueError("only asymmetric algorithms of the key set layer are allowed")
        _require_text(self.typ_expected, "typ_expected")
        if not self.typ_expected.strip():
            raise ValueError("typ_expected must not be empty")
        _require_positive_seconds(self.leeway_seconds, "leeway_seconds")
        _require_positive_seconds(self.max_lifetime_seconds, "max_lifetime_seconds")


def audience_holds(claim: object, expected: str) -> bool:
    """Whether the ``aud`` claim carries exactly ``expected``, alone or as a list member.

    A string holds on exact equality. A list holds when ``expected`` stands exactly among
    its entries; any non-string entry makes the whole list unusable and the token
    refusable, and an empty list never holds. Everything else (a missing claim, an object,
    a number) never holds.

    An empty expectation and an empty claim never hold either. That is the rule of
    ``principal.same_principal`` (D-37), where an empty value fails before the comparison
    so that a request without an identity never passes as the owner of a row that has none
    either, and it belongs to this function rather than to the guard on the settings forty
    lines above: the function is exported and a later caller reaches it, not the guard.

    The comparison of two strings runs in constant time on UTF-8 bytes. Inside a list of
    strings the walk has no early exit, so neither a hit nor its position teaches anything;
    the shape of the list does, because a non-string entry costs no comparison at all. The
    list is read after the signature check, so its shape is the issuer's, not a caller's.
    """
    # The measured reasons this function exists instead of two ready-made checks:
    #
    # 1. ``check_resource_allowed`` (mcp.shared.auth_utils, at home in oauth/verifier.py)
    #    compares scheme and host exactly but the *path as a prefix* ("hierarchical
    #    matching", measured at .venv/Lib/site-packages/mcp/shared/auth_utils.py): a
    #    token with ``aud = <configured>/tenant-b`` passes against ``<configured>``.
    #    Right for our own tokens, where a parent resource covers its children; fatal
    #    for a foreign audience, where the path suffix is exactly the tenant boundary.
    #    That is why it has no business in the exchange path (pitfall 2).
    # 2. PyJWT's strict mode, measured at ``jwt/api_jwt.py::_validate_aud`` (2.14.0 in
    #    this venv): ``strict_aud`` demands a single string on *both* sides and refuses
    #    every list outright, so it cannot express "exactly contained in a list", which
    #    Keycloak tokens regularly are (classically ``account`` beside the target). Its
    #    non-strict mode is an OR over lists on both sides, which is pitfall 2 again.
    #
    # ``expected`` is ``settings.audience`` and by construction a single string (its
    # ``__post_init__`` enforces that), so the expected side can never become an OR.
    if not isinstance(expected, str) or not expected:
        return False
    if isinstance(claim, str):
        return bool(claim) and secrets.compare_digest(
            claim.encode("utf-8"), expected.encode("utf-8")
        )
    if not isinstance(claim, list) or not claim:
        return False
    held = False
    usable = True
    for entry in claim:
        # No early exit in either direction: every entry is looked at, so neither a hit
        # nor a poisoned entry changes how long the walk takes.
        if not isinstance(entry, str):
            usable = False
        elif secrets.compare_digest(entry.encode("utf-8"), expected.encode("utf-8")):
            held = True
    return usable and held


class _PreparsedJWT(jwt.PyJWT):
    """The decoder, told to reuse the payload the cost filter has already parsed.

    The filter in ``claims_of`` parses the whole payload to read ``iss`` before a key is
    fetched, and the decoder would base64-decode and parse the very same bytes of the very
    same token a second time: permanent double work in the path that carries every
    request, and on a hostile payload the doubling of its cost (measured: 1542 ms against
    1202 ms on eight megabytes). ``_decode_payload`` is the hook PyJWT documents for
    exactly this override.

    What does **not** change is the order. ``decode`` verifies the signature before it
    asks for the payload, and every claim rule still runs on the signature-covered token;
    handed back here is the object parsed from the same segment of the same string, not a
    second, differently read token.
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__()
        self._payload = payload

    def _decode_payload(self, decoded: dict[str, Any]) -> dict[str, Any]:
        return self._payload


class ExchangeTokenChecker:
    """One configured foreign issuer. Holds only the key set cache of that issuer."""

    def __init__(
        self,
        settings: ExchangeSettings,
        *,
        clock: Callable[[], float] | None = None,
        now: Callable[[], float] | None = None,
        max_token_bytes: int = MAX_TOKEN_BYTES,
    ) -> None:
        if isinstance(max_token_bytes, bool) or not isinstance(max_token_bytes, int):
            raise ValueError("max_token_bytes must be a whole number of bytes")
        if max_token_bytes <= 0:
            raise ValueError("max_token_bytes must be a positive number of bytes")
        self._settings = settings
        self._max_token_bytes = max_token_bytes
        # Two clocks, deliberately separate and separately injectable. ``clock`` is the
        # monotonic one and only measures elapsed time inside the key set layer (cache
        # expiry, cooldown, failure pause); ``now`` is the wall clock for the claim
        # rules that are ours alone. Whoever checks ``exp`` against a monotonic clock
        # checks it against the uptime of the process (pitfall 6, third part).
        self._clock = clock or time.monotonic
        self._now = now or time.time

        async def jwks_uri() -> str:
            return settings.jwks_uri

        # Cooldown, single-flight and the failure pause come from the layer and are not
        # rebuilt here. The refusal factory is handed in, so a key set problem surfaces
        # as the same exception as every other refusal.
        self._keys = KeySet(
            origin=settings.jwks_origin or settings.issuer,
            jwks_uri=jwks_uri,
            algorithms=settings.algorithms,
            refuse=_refused,
            clock=self._clock,
        )

    async def claims_of(self, token: str) -> dict[str, Any]:
        """The claim set of a checked ``token``, or :class:`ExchangeRefused`.

        Checked are exactly these: ``iss``, ``aud``, ``azp``, ``typ``, ``iat``, ``exp``,
        ``sub`` and, when it is there, ``nbf``. Every other claim of the payload,
        ``email``, ``preferred_username``, ``groups``, ``realm_access`` and whatever else
        the realm writes, is transport: covered by the signature, read by nothing here
        and checked against nothing. The return value is the whole set rather than the
        checked part, because phase 23 needs the claim it maps onto an account and that
        one need not be among the seven; what it may trust of the rest is a decision of
        that phase, and this sentence is what it has to read first.

        The order is deliberate: the cheap, local rules fall first, the outgoing key
        fetch happens only for a token that already looks like one of our issuer, and
        the signature-covered checks are the last word on everything the earlier steps
        read unverified.
        """
        if not token:
            raise _refused("the token is empty", REASON_EXCHANGE_MALFORMED)
        # Bytes before base64, base64 before JSON. Everything behind this line is work a
        # stranger can order with nothing but an HTTP request, so the bound stands in
        # front of the first decoding step and not behind it. A character count never
        # falls below the UTF-8 byte count, which is what keeps the exact measurement
        # itself bounded; a token is base64url and therefore ASCII, and an input that
        # cannot even be encoded is refused rather than repaired.
        if len(token) > self._max_token_bytes:
            raise _refused("the token is longer than allowed", REASON_EXCHANGE_MALFORMED)
        try:
            measured = len(token.encode("utf-8"))
        except UnicodeEncodeError:
            raise _refused("the token is not text", REASON_EXCHANGE_MALFORMED) from None
        if measured > self._max_token_bytes:
            raise _refused("the token is longer than allowed", REASON_EXCHANGE_MALFORMED)
        try:
            header = jwt.get_unverified_header(token)
        except Exception:
            # Deliberately by class, not by the list of exceptions one library version
            # happens to raise on unverified bytes: PyJWT catches ValueError and
            # RecursionError around the header and only ValueError around the payload
            # (measured in 2.14.0), and a promise that every input ends in one
            # detail-free exception cannot rest on that asymmetry. Everything this
            # parse raises is a refusal.
            raise _refused("the token header is unreadable", REASON_EXCHANGE_MALFORMED) from None
        algorithm = header.get("alg")
        if algorithm not in self._settings.algorithms:
            # Decided before any other work, so ``none`` and every ``HS*`` fall here,
            # long before a key or a shared secret could be looked at.
            raise _refused(
                "the token uses an algorithm that is not configured", REASON_EXCHANGE_KEY
            )
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise _refused("the token names no key", REASON_EXCHANGE_KEY)
        header_typ = header.get("typ")
        if header_typ is not None and (
            not isinstance(header_typ, str) or header_typ.lower() not in _TYP_HEADERS_FOLDED
        ):
            # Tolerated, not required: see the comment on ACCEPTED_TYP_HEADERS. A missing
            # header type is no reason to refuse; a foreign one is.
            raise _refused("the token header names another type", REASON_EXCHANGE_MALFORMED)
        # The pre-authentication cost guard: this checker sits in a path a stranger can
        # reach with nothing but an HTTP request, and without this filter an invented
        # kid in a self-made JWT makes this process fetch the provider's keys. The
        # issuer claim is read from the unverified payload, so this filter can only
        # refuse and never accept; the decoder below checks the issuer a second time,
        # signature-covered, through its issuer argument. From the outside the refusal
        # is the same as every other.
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except Exception:
            # The same fail-closed catch as on the header above, and here it is load
            # bearing: ``json.loads`` raises RecursionError on a deeply nested payload,
            # PyJWT does not catch it on this side, and RecursionError is no PyJWTError.
            # An unsigned token of about eight kilobytes would otherwise leave this
            # method as a RecursionError, before any authentication (the corpus carries
            # exactly that case).
            raise _refused("the token payload is unreadable", REASON_EXCHANGE_MALFORMED) from None
        if unverified.get("iss") != self._settings.issuer:
            raise _refused("the token comes from another issuer", REASON_EXCHANGE_ISSUER)
        key = await self._keys.key(kid, algorithm)
        try:
            claims = _PreparsedJWT(unverified).decode(
                token,
                key,
                algorithms=list(self._settings.algorithms),
                issuer=self._settings.issuer,
                leeway=self._settings.leeway_seconds,
                # verify_aud is off on purpose while ``aud`` stays in the require list:
                # the absence of the claim is still PyJWT's refusal, but the value
                # comparison is ours alone, because neither of PyJWT's two modes says
                # "exactly the one configured value, alone or as an exact list member"
                # (measured, see the note at ``audience_holds``).
                options={"require": list(REQUIRED_CLAIMS), "verify_aud": False},
            )
        except (jwt.PyJWTError, TypeError, OverflowError) as failure:
            # The decoder computes int() on iat, nbf and exp and catches ValueError
            # alone (measured in 2.14.0): an object or a list makes that a TypeError,
            # Infinity an OverflowError, and json.loads accepts that non-standard
            # literal. Neither is a PyJWTError, so both classes are caught here; the
            # own guard below never sees these forms, it sees the numeric string.
            #
            # One call site, two groups, and the branch is read off the failure rather
            # than off a second rule of ours: this one decoder call carries the signature
            # check and the standard claim rules together, and a broken signature is a
            # statement about the key that signed, not about what the payload said. The
            # log line stays one phrase either way, because the phrase is written for a
            # reader who has the instance and sees the token in front of him.
            raise _refused(
                "the token did not meet the standard claims",
                REASON_EXCHANGE_KEY
                if isinstance(failure, jwt.InvalidSignatureError)
                else REASON_EXCHANGE_CLAIMS,
            ) from None
        if not audience_holds(claims.get("aud"), self._settings.audience):
            raise _refused("the token is meant for another audience", REASON_EXCHANGE_CLAIMS)
        # Keycloak's Standard Token Exchange V2 writes no ``act`` claim and no delegation
        # semantics, so ``azp``, the client id of the exchanging client, is the only
        # reliable trace of the acting party. The check therefore reads as "allowed
        # acting party", not "allowed azp": ``act`` takes this role over the moment
        # Keycloak writes it. Membership runs over every entry without an early break,
        # in constant time per entry, so the position of a hit teaches nothing.
        azp = claims.get("azp")
        if not isinstance(azp, str):
            raise _refused("the token names no acting party", REASON_EXCHANGE_CLAIMS)
        acting_party_allowed = False
        for party in self._settings.azp_allowed:
            if secrets.compare_digest(azp.encode("utf-8"), party.encode("utf-8")):
                acting_party_allowed = True
        if not acting_party_allowed:
            raise _refused(
                "the token was obtained by an unlisted acting party", REASON_EXCHANGE_CLAIMS
            )
        if claims.get("typ") != self._settings.typ_expected:
            # The type lives in the payload: Keycloak marks an access token Bearer and
            # an ID token ID there, while the header varies by client. An ID token of
            # the same realm, same keys and same issuer falls exactly here (pitfall 9).
            raise _refused("the token is not an access token", REASON_EXCHANGE_CLAIMS)
        iat = _number(claims.get("iat"))
        exp = _number(claims.get("exp"))
        if iat is None or exp is None:
            # What actually arrives here is the numeric string and the bool: the decoder
            # above lets "1758230000" through its own int() and refuses an object, a list
            # or Infinity before this line is reached. The guard keeps both out of the
            # two lifetime rules below, which are arithmetic.
            raise _refused("the token carries no numeric times", REASON_EXCHANGE_CLAIMS)
        # Two rules the decoder does not bring, both refusals and never a shortening:
        # a bounded lifetime and a bounded age. They run on the injected wall clock;
        # the monotonic clock stays with the key set layer (pitfall 6, third part).
        if exp - iat > self._settings.max_lifetime_seconds:
            raise _refused("the token lives longer than allowed", REASON_EXCHANGE_CLAIMS)
        if self._now() - iat > self._settings.max_lifetime_seconds:
            raise _refused("the token is older than allowed", REASON_EXCHANGE_CLAIMS)
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub.strip() or sub != sub.strip():
            raise _refused("the token names no usable subject", REASON_EXCHANGE_CLAIMS)
        # A string, not empty, no edge whitespace, and handed on exactly as it arrived.
        # No Unicode normal form is chosen here and none is enforced: "alex" in NFD and
        # in NFC are two different values with the same appearance, and which of them
        # names the same account is a question of the account mapping, phase 23, not of
        # the token check. The length is bounded only through MAX_TOKEN_BYTES, which is
        # the same bound the audience list and the number of claims run under.
        return claims

    def forget_keys(self) -> None:
        """Drop the cached key set of this issuer, and nothing else.

        The chain of plan 22-02 is the only caller: one revocation in this process empties
        the cache of the store verifier and this key set with the same call. The checker
        stays free of any binding to a server through this method too; it forwards to the
        one key set layer and learns nothing about what caused the call.
        """
        self._keys.forget()


def _require_text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")


def _require_string_sequence(value: object, name: str) -> None:
    """An allowlist is a sequence of non-empty strings, and a bare string is none.

    A string is iterable and every one of its characters is a non-empty string, so a bare
    ``azp_allowed = "f13-orchestrator"`` passed the membership rule below as an allowlist
    of the characters f, 1, 3, minus, o and so on. That refuses every real token instead
    of accepting a wrong one, so it is not fail open; it is the silent configuration error
    that surfaces only as "nothing works any more", and a client id of a single character
    would have matched. The same shape is refused for every allowlist of this module.
    """
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise ValueError(f"{name} is a sequence of strings, never a single string")
    if not value or not all(isinstance(entry, str) and entry.strip() for entry in value):
        raise ValueError(f"{name} must name at least one non-empty value")


def _require_positive_seconds(value: object, name: str) -> None:
    """A duration is a finite positive number, and nan is neither.

    Every comparison against ``nan`` is false, so ``nan <= 0`` lets the value through and
    from then on switches the rule it belongs to off without a word: PyJWT computes
    ``exp <= now - leeway`` and the two own lifetime rules compare against it as well.
    The strings "nan", "NaN", "inf" and "Infinity" all become such a value through
    ``float()`` without an error, which is exactly the path phase 22 will take.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a number of seconds")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number of seconds")


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _require_https_url(url: str, name: str) -> None:
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError:
        raise ValueError(f"{name} is not a valid URL") from None
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"{name} must be an https URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError(f"{name} must not carry credentials, a query or a fragment")

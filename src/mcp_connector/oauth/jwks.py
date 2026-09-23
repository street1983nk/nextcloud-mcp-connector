"""The one key set layer: hardened fetch, cache with expiry, rotation.

This module exists so that a key set is fetched, cached and rotated in exactly one place.
Phase 21 adds a second verification path (token exchange) next to the OIDC browser flow,
and a hardening that lands in only one of two copies is how a gap survives a fix; the
machinery therefore moved out of ``oauth/oidc.py`` instead of being written a second time.

**Why a dedicated HTTP client and not ``shared_client``.** The identity provider is a
foreign trust domain. Its connections share no pool with the path that carries Nextcloud
credentials (T-06-14). The posture is the same: TLS with hostname validation, no redirects,
no cookies, fixed timeouts, and every body read through a size limit.

**Why the targets are not attacker-chosen.** The issuer is administrator configuration.
Discovery must name exactly that issuer, and every endpoint it returns must live on the
same HTTPS origin. Nothing a client, a browser or a response supplies can widen that set;
:class:`KeySet` receives its ``jwks_uri`` from that discovery and checks the origin again
before every fetch, and nothing here ever follows a ``jku`` or ``x5u`` from a token header.

**Why not ``jwt.PyJWKClient``.** Even with its 2.14 corrections it is synchronous on
``urllib`` and would block the event loop, and it brings no same-origin check, no size
limit, no key type allowlist and no handling of a ``kid`` claimed by more than one key.
Those properties are the point of this module, so the client stays our own.

**Why ``refuse`` is handed in.** The layer defines no exception of its own: every caller
brings the refusal it already answers with. ``OidcClient`` passes its ``_refused`` factory
through, which keeps the exception type and the log line of the OIDC flow exactly what
they were before the machinery moved here.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt

from ..exapp.responses import BodyTooLarge, BodyUnreadable, bounded_response
from ..nextcloud.http import USER_AGENT, NoCookieJar

__all__ = [
    "ALLOWED_ALGORITHMS",
    "ALLOWED_KEY_TYPES",
    "JWKS_CACHE_SECONDS",
    "JWKS_FAILURE_RETRY_SECONDS",
    "JWKS_KID_COOLDOWN_SECONDS",
    "MAX_KEYS",
    "MAX_RESPONSE_BYTES",
    "KeySet",
    "fetch_json",
    "same_origin",
]

#: Asymmetric algorithms only. A symmetric ``HS*`` algorithm would let anybody who knows
#: the client secret mint tokens, and ``none`` is no signature at all.
ALLOWED_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"}
)

#: Key types a JWKS entry may have. ``oct`` (a symmetric key) is never accepted.
ALLOWED_KEY_TYPES = frozenset({"RSA", "EC", "OKP"})

#: Discovery, JWKS and token answers are small; anything larger is refused unread.
MAX_RESPONSE_BYTES = 256 * 1024

#: How long a fetched JWKS is reused. Against a fresh cache an unknown ``kid`` costs at
#: most one refetch; when the cache expires in the same moment, the expiry fetch can come
#: first and a second one follows for the miss, so two is the ceiling, not one.
JWKS_CACHE_SECONDS = 300

#: After a reload for an unknown ``kid``, no further miss-driven reload for this long.
#: PyJWT 2.14 picked thirty seconds for its own client; sixty is the value recommended in
#: practice for a pre-authentication reachable path, and it is settable per instance as
#: ``cooldown_seconds`` so that phase 22 can hang it onto the configuration without
#: touching this layer. Expiry-driven reloads are never braked by it.
JWKS_KID_COOLDOWN_SECONDS = 60

#: After a failed fetch, no further fetch is started for this long; every call that arrives
#: meanwhile is refused straight away. Without it a provider outage turns every incoming
#: request into an outgoing fetch, which amplifies the load exactly when the provider is
#: already struggling and invites its rate limit. It is deliberately much shorter than the
#: miss cooldown: a brief hiccup must not cost a full minute of sign ins.
JWKS_FAILURE_RETRY_SECONDS = 10

#: A key list longer than this is refused as unusable rather than truncated.
MAX_KEYS = 20

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


#: A usable JWKS entry: its key material and its declared ``alg`` (``None`` if it named
#: none). ``None`` in the cache marks a ``kid`` that named more than one usable key, which
#: makes that ``kid`` unusable rather than picking one of them.
_KeyEntry = tuple[Any, str | None]


@dataclass(slots=True)
class _KeyCache:
    keys: dict[str, _KeyEntry | None] = field(default_factory=dict)
    #: Minus infinity, not zero: a cache nobody filled has to be stale under every clock,
    #: and under a monotonic one zero would count as fresh for the first five minutes of
    #: the process. The default sits next to the measure that exists against exactly that.
    fetched_at: float = float("-inf")


class KeySet:
    """The keys of one issuer: fetched through the hardened client, cached, rotated.

    One instance per issuer. ``jwks_uri`` is awaited before every fetch because the
    address comes from the discovery of the configured issuer and must not be resolved
    before first need: a provider outage is a refusal of one token, never a startup
    failure. ``origin`` pins where a fetch may go, whatever that discovery answered.
    """

    def __init__(
        self,
        *,
        origin: str,
        jwks_uri: Callable[[], Awaitable[str]],
        algorithms: tuple[str, ...],
        refuse: Callable[[str], Exception],
        clock: Callable[[], float] = time.monotonic,
        cache_seconds: float = JWKS_CACHE_SECONDS,
        cooldown_seconds: float = JWKS_KID_COOLDOWN_SECONDS,
        retry_seconds: float = JWKS_FAILURE_RETRY_SECONDS,
    ) -> None:
        self._origin = origin
        self._jwks_uri = jwks_uri
        self._algorithms = algorithms
        self._refuse = refuse
        self._clock = clock
        self._cache_seconds = cache_seconds
        self._cooldown_seconds = cooldown_seconds
        self._retry_seconds = retry_seconds
        # ``fetched_at`` starts at minus infinity so a never-filled cache is stale under
        # any clock, including a monotonic one that starts near zero.
        self._keys = _KeyCache(fetched_at=float("-inf"))
        self._miss_refresh_at = float("-inf")
        self._failed_refresh_at = float("-inf")
        self._fetches = 0
        # One lock per KeySet, and a KeySet is one issuer: the lock per issuer the
        # single-flight requirement asks for. Created here, not on first use.
        self._lock = asyncio.Lock()

    async def key(self, kid: str, algorithm: str) -> Any:
        """The key material behind ``kid`` if it may verify ``algorithm``, else a refusal."""
        now = self._clock()
        if not self._stale(now):
            if kid in self._keys.keys:
                # The fast path takes no lock: a fresh cache with a known kid answers at
                # once. Nothing is awaited between the check and the read, so the cache
                # cannot be exchanged underneath it.
                return self._entry(kid, algorithm)
            if now - self._miss_refresh_at < self._cooldown_seconds:
                # Also decided without the lock, and re-checked behind it below. A call
                # whose answer already stands must not queue behind a flight in progress,
                # or a flood of invented kids serializes on one lock whose queue has no
                # bound, precisely while the provider is slow.
                raise self._refuse("the token names an unknown or unusable key")
        elif now - self._failed_refresh_at < self._retry_seconds:
            raise self._refuse("the key set could not be refreshed")
        fetches_seen = self._fetches
        async with self._lock:
            # Re-read the clock and re-check every condition under the lock: whoever
            # waited here takes the outcome of the fetch that just happened instead of
            # starting a second one (single-flight).
            now = self._clock()
            if self._stale(now):
                if self._fetches != fetches_seen:
                    # A concurrent caller fetched while this one waited and the cache is
                    # still stale, so that fetch failed; share the refusal, not the cost.
                    raise self._refuse("the key set could not be refreshed")
                if now - self._failed_refresh_at < self._retry_seconds:
                    # A fetch failed just now. Refusing again is fail-closed either way;
                    # this only makes the refusal cheap instead of spending one outgoing
                    # fetch per incoming call while the provider is down. The wording is
                    # the one a failed refresh gets, so nothing is given away.
                    raise self._refuse("the key set could not be refreshed")
                # Never filled or expired: the miss cooldown plays no part here and its
                # stamp is not set, because it only brakes reloads for unknown kids.
                await self._attempt(now)
            elif kid not in self._keys.keys:
                if now - self._miss_refresh_at < self._cooldown_seconds:
                    # Refused exactly like an unknown kid after a fetch (no oracle).
                    raise self._refuse("the token names an unknown or unusable key")
                # The stamp is set before the outgoing fetch, not after: a slow or
                # failing provider must not stretch the window an attacker can reload in.
                self._miss_refresh_at = now
                await self._attempt(now)
        return self._entry(kid, algorithm)

    def forget(self) -> None:
        """Drop the cached key set; the two pre-authentication brakes stay standing.

        Why the method exists: a revocation inside this process has to reach the whole
        chain. A key set that keeps a rotated key ready for five more minutes is the second
        half of the very five second window ``StoreTokenVerifier.invalidate`` closes, and
        closing one half alone is a promise that does not hold.

        Why the two timestamps of this layer survive it: they are the brake this layer puts
        in front of the authentication, and a revocation that took them along would be a
        way to reset the cooldown from the outside, which is precisely the amplifier they
        were written against. What this leaves behind is the state of a cache nobody ever
        filled, and nothing besides.

        What it costs, measured and not estimated (2026-09-23, one process and one issuer,
        ``tests/unit/test_oauth_jwks.py``): 36 outgoing fetches per window of 300 seconds,
        which reads as 31 plus 5. A revocation makes the cache stale, so the call behind it
        takes the expiry branch and orders one fetch, and nothing here brakes the cycle that
        follows; 31 cycles were driven inside one window and every one of them cost its
        fetch. The other 5 are the miss branch, the one ceiling this layer raises itself:
        300 seconds over the 60 of :data:`JWKS_KID_COOLDOWN_SECONDS`. The two were measured
        together rather than added up, because they share the fields above: an unknown key
        id against a *stale* cache takes the expiry branch as well and never spends the
        cooldown, so only the second invented key id of a cycle is ever braked by it. Phase
        23 is why this number is not the older one. Before it no exchange token had an
        identity, so every call of that branch ended as a refusal, was counted in
        ``CLASS_EXCHANGE`` and ran into ``EXCHANGE_LIMIT``, which capped the cycles at 30
        per source; since then a valid token is answered with 200, is not counted and pays
        one earlier refusal back, and a successful revocation is not counted by
        ``CLASS_CONNECTIONS`` either. What bounds this lever today is that every cycle needs
        a proved browser identity to revoke with, and two workers hold two key sets and
        therefore two of this number.
        """
        self._keys.keys.clear()
        self._keys.fetched_at = float("-inf")

    def _stale(self, now: float) -> bool:
        return now - self._keys.fetched_at >= self._cache_seconds

    async def _attempt(self, now: float) -> None:
        """One counted refresh attempt; the count moves on success and failure alike.

        The count is what a waiter behind the lock compares against, so it may only move
        once an attempt has *finished*: a waiter that queued up during the flight then
        sees a moved count and shares the outcome instead of starting a second fetch.

        A failure is stamped here, in the one place every attempt passes through, so the
        pause before the next outgoing fetch covers the expiry branch and the miss branch
        alike.
        """
        try:
            await self._refresh(now)
        except Exception:
            self._failed_refresh_at = now
            self._fetches += 1
            raise
        self._fetches += 1

    def _entry(self, kid: str, algorithm: str) -> Any:
        entry = self._keys.keys.get(kid)
        if entry is None:
            # Either no key at all, or a kid claimed by more than one usable key: both are
            # refused the same way, so a caller cannot tell a collision from an unknown kid.
            raise self._refuse("the token names an unknown or unusable key")
        key, alg = entry
        if alg is not None and alg != algorithm:
            raise self._refuse("the key is declared for another algorithm")
        return key

    async def _refresh(self, now: float) -> None:
        url = await self._jwks_uri()
        document = await fetch_json("GET", url, origin=self._origin, refuse=self._refuse)
        entries = document.get("keys") if isinstance(document, dict) else None
        if not isinstance(entries, list) or len(entries) > MAX_KEYS:
            raise self._refuse("the JWKS is not a usable key list")
        keys: dict[str, _KeyEntry | None] = {}
        for entry in entries:
            usable = _usable_key(entry, self._algorithms)
            if usable is None:
                continue
            kid, parsed = usable
            # A kid already seen becomes unusable rather than resolving to either key.
            keys[kid] = None if kid in keys else parsed
        if not keys:
            # A 200 carrying no usable key is treated as a failed fetch, so the old cache
            # stays: the refusal happens before the assignment below. Otherwise a provider
            # that briefly serves an empty JWKS during a rolling restart would replace a
            # working key set with nothing and lock every sign in out, and because the
            # empty cache counts as fresh, every call would then take the lock as well.
            raise self._refuse("the JWKS carries no usable key")
        # The cache is replaced only after a fully parsed, valid answer; a failed fetch
        # propagates above and leaves both ``keys`` and ``fetched_at`` untouched.
        self._keys = _KeyCache(keys=keys, fetched_at=now)


async def fetch_json(
    method: str,
    url: str,
    *,
    origin: str,
    refuse: Callable[[str], Exception],
    data: dict[str, str] | None = None,
    auth: httpx.Auth | None = None,
) -> Any:
    """One hardened round trip: pinned origin, no redirects, no cookies, bounded body."""
    if not same_origin(url, origin):
        raise refuse("a request would leave the issuer origin")
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        cookies=NoCookieJar(),
    ) as client:
        try:
            response = await client.send(
                client.build_request(method, url, data=data), stream=True, auth=auth
            )
        except httpx.HTTPError:
            raise refuse("the provider could not be reached") from None
        # The response is streamed, so it is owed a close on every path, including the
        # refusals below (GHSA-fhv5-28vv-h8m8 is what an unclosed one costs). ``aclosing``
        # is a ``try/finally`` around ``aclose()`` and nothing more; it is here because a
        # context manager states the obligation where it arises.
        async with aclosing(response):
            try:
                if response.status_code != 200:
                    raise refuse(f"the provider answered {response.status_code}")
                raw = await bounded_response(response, MAX_RESPONSE_BYTES)
            except (BodyTooLarge, BodyUnreadable):
                raise refuse("the provider answer is too large or unreadable") from None
    try:
        return json.loads(raw)
    except ValueError:
        raise refuse("the provider answer is not JSON") from None


def _usable_key(entry: object, algorithms: tuple[str, ...]) -> tuple[str, _KeyEntry] | None:
    """The ``(kid, (key, alg))`` of ``entry`` if it may verify a signature, else ``None``.

    ``use`` and ``key_ops``, when present, must each allow verification, and when both are
    present they must agree: ``use`` must be ``"sig"`` and ``key_ops`` must contain
    ``"verify"``. A declared ``alg`` outside the configured algorithms is unusable too, so
    the cache never carries a key for an algorithm the operator did not allow.
    """
    if not isinstance(entry, dict):
        return None
    if entry.get("kty") not in ALLOWED_KEY_TYPES:
        return None
    if entry.get("use") not in (None, "sig"):
        return None
    key_ops = entry.get("key_ops")
    if key_ops is not None:
        if not isinstance(key_ops, list) or not all(isinstance(op, str) for op in key_ops):
            return None
        if "verify" not in key_ops:
            return None
    kid = entry.get("kid")
    alg = entry.get("alg")
    if not isinstance(kid, str) or (alg is not None and alg not in algorithms):
        return None
    try:
        key = jwt.PyJWK(entry).key
    except (jwt.PyJWTError, TypeError, ValueError, AttributeError):
        # Measured against PyJWT 2.14.0, not assumed: an entry whose ``n`` is ``null``, a
        # number or a list still raises ``TypeError: Expected a string value``, and an
        # ``OKP`` entry with a numeric ``x`` does the same. The 2.14 corrections hardened
        # ``PyJWKClient``, not ``PyJWK`` against every input shape. Catching only
        # ``PyJWTError`` would let that escape ``KeySet.key`` raw and break the promise of
        # the module header: the layer defines no exception of its own, every caller gets
        # the refusal it handed in.
        return None
    return kid, (key, alg)


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc.lower()


def same_origin(url: str, origin: str) -> bool:
    """Whether ``url`` lives on exactly the HTTPS origin of ``origin``."""
    # ``urlsplit`` alone cannot tell "no fragment" from "an empty fragment" (both report
    # ``fragment == ""``), so the raw text is checked directly; an endpoint the operator
    # never intended to carry one is refused either way.
    if "#" in url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.username is not None or parts.password is not None:
        return False
    try:
        return _origin(url) == _origin(origin) and _origin(url)[0] == "https"
    except ValueError:
        return False

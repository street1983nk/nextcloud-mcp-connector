"""The OIDC client of the standalone browser identity: discovery, token exchange, ID token.

This module talks to exactly one identity provider, the one the operator configured. It is
the relying-party half of the standalone consent (design note, "OIDC consent flow"); the
browser routes and the store rows live elsewhere, so everything here is testable without a
browser.

**Why a dedicated HTTP client and not ``shared_client``.** The IdP is a foreign trust
domain. Its connections share no pool with the path that carries Nextcloud credentials
(T-06-14). The posture is the same: TLS with hostname validation, no redirects, no cookies,
fixed timeouts, and every body read through a size limit.

**Why the targets are not attacker-chosen.** The issuer is administrator configuration.
Discovery must name exactly that issuer, and every endpoint it returns must live on the
same HTTPS origin. Nothing a client, a browser or a response supplies can widen that set.

**What an ID token has to be.** Signed with one of the configured algorithms by a key of the
issuer's JWKS (never a symmetric key), issued by the issuer, for this client, not expired,
carrying the nonce of this sign in, and, where it names an authorized party or several
audiences, authorized for this client. ``sub`` must be a non-empty string.

**The identity mapping** is a named strategy. ``user_oidc_unique_uid_sub_v1`` reproduces
how the Nextcloud ``user_oidc`` app derives a first-created account id with ``uniqueUid``
enabled and ``sub`` as the effective mapping claim. The operator asserts that profile; a
wrong assertion is caught when the derived id does not match the account id of the
authorization, which fails closed.
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import jwt

from ..exapp.responses import BodyTooLarge, BodyUnreadable, bounded_response
from ..nextcloud.http import USER_AGENT, NoCookieJar

__all__ = [
    "DEFAULT_ALGORITHMS",
    "JWKS_CACHE_SECONDS",
    "MAX_RESPONSE_BYTES",
    "STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1",
    "OidcClient",
    "OidcRefused",
    "OidcSettings",
    "ProviderMetadata",
    "code_challenge",
    "new_code_verifier",
    "user_oidc_unique_uid_sub_v1",
]

#: The algorithms an ID token may be signed with unless the operator says otherwise.
DEFAULT_ALGORITHMS = ("RS256",)

#: Asymmetric algorithms only. A symmetric ``HS*`` algorithm would let anybody who knows
#: the client secret mint ID tokens, and ``none`` is no signature at all.
_ALLOWED_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"}
)

#: Key types a JWKS entry may have. ``oct`` (a symmetric key) is never accepted.
_ALLOWED_KEY_TYPES = frozenset({"RSA", "EC", "OKP"})

#: The one supported identity mapping profile.
STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1 = "user_oidc_unique_uid_sub_v1"

#: Discovery, JWKS and token answers are small; anything larger is refused unread.
MAX_RESPONSE_BYTES = 256 * 1024

#: How long a fetched JWKS is reused. An unknown ``kid`` triggers at most one refetch.
JWKS_CACHE_SECONDS = 300

#: Clock skew tolerated on ``exp``, ``iat`` and ``nbf``.
_LEEWAY_SECONDS = 60

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_KEYS = 20

logger = logging.getLogger("mcp_connector.oauth.oidc")


class OidcRefused(Exception):
    """The provider, a response or a token did not meet the rules. Carries no detail.

    Callers answer every refusal the same way (oracle-free); the reason goes to the log as
    a fixed phrase, never with a value from the exchange.
    """


@dataclass(frozen=True, slots=True, repr=False)
class OidcSettings:
    """What the operator configures. Validated on construction; nothing is guessed."""

    issuer: str
    client_id: str
    redirect_uri: str
    provider_id: int
    strategy: str = STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1
    subject_type: str = "public"
    client_secret: str | None = None
    algorithms: tuple[str, ...] = DEFAULT_ALGORITHMS

    def __post_init__(self) -> None:
        _require_https_origin(self.issuer, "issuer", allow_path=True)
        if self.issuer.endswith("/"):
            raise ValueError("the issuer is used exactly as configured; drop the trailing slash")
        _require_https_origin(self.redirect_uri, "redirect_uri", allow_path=True)
        if not self.client_id.strip():
            raise ValueError("the client id is required")
        if isinstance(self.provider_id, bool) or self.provider_id <= 0:
            raise ValueError("provider_id is the positive numeric id of the user_oidc provider")
        if self.strategy != STRATEGY_USER_OIDC_UNIQUE_UID_SUB_V1:
            raise ValueError("unknown identity mapping strategy")
        if self.subject_type != "public":
            raise ValueError("only public subject identifiers are supported")
        if self.client_secret is not None and not self.client_secret:
            raise ValueError("an empty client secret is a configuration error")
        if not self.algorithms or not set(self.algorithms) <= _ALLOWED_ALGORITHMS:
            raise ValueError("only asymmetric ID token algorithms are allowed")

    def __repr__(self) -> str:
        secret = "None" if self.client_secret is None else "'***'"
        return (
            f"OidcSettings(issuer={self.issuer!r}, client_id={self.client_id!r}, "
            f"redirect_uri={self.redirect_uri!r}, provider_id={self.provider_id!r}, "
            f"strategy={self.strategy!r}, algorithms={self.algorithms!r}, "
            f"client_secret={secret})"
        )


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """The validated part of the discovery document."""

    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


def new_code_verifier() -> str:
    """A PKCE verifier: 64 URL-safe characters (RFC 7636 allows 43 to 128)."""
    return secrets.token_urlsafe(48)


def code_challenge(verifier: str) -> str:
    """The S256 challenge of a verifier (RFC 7636, 4.2)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def user_oidc_unique_uid_sub_v1(provider_id: int, sub: str) -> str:
    """The account id user_oidc creates for ``sub`` with ``uniqueUid`` on and claim ``sub``.

    Lowercase hex SHA-256 of ``"<provider_id>_0_<sub>"``. This describes first creation;
    existing accounts are matched by provider and ``sub`` in user_oidc, which is why the
    result is always compared with the account id Nextcloud reports and never trusted alone.
    """
    return hashlib.sha256(f"{provider_id}_0_{sub}".encode()).hexdigest()


#: A usable JWKS entry: its key material and its declared ``alg`` (``None`` if it named
#: none). ``None`` in the cache marks a ``kid`` that named more than one usable key, which
#: makes that ``kid`` unusable rather than picking one of them.
_KeyEntry = tuple[Any, str | None]


@dataclass(slots=True)
class _KeyCache:
    keys: dict[str, _KeyEntry | None] = field(default_factory=dict)
    fetched_at: float = 0.0


class OidcClient:
    """One configured provider. Built once per application; holds only a JWKS cache."""

    def __init__(
        self,
        settings: OidcSettings,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock or time.time
        self._metadata: ProviderMetadata | None = None
        self._keys = _KeyCache()

    @property
    def settings(self) -> OidcSettings:
        return self._settings

    async def metadata(self) -> ProviderMetadata:
        """Discovery, validated once and then reused for the life of the process."""
        if self._metadata is not None:
            return self._metadata
        document = await self._get_json(f"{self._settings.issuer}/.well-known/openid-configuration")
        if not isinstance(document, dict):
            raise _refused("discovery is not a JSON object")
        if document.get("issuer") != self._settings.issuer:
            raise _refused("discovery names another issuer")
        endpoints = {}
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            value = document.get(name)
            if not isinstance(value, str) or not _same_origin(value, self._settings.issuer):
                raise _refused("a discovery endpoint leaves the issuer origin")
            endpoints[name] = value
        if "S256" not in _strings(document.get("code_challenge_methods_supported")):
            raise _refused("the provider does not offer S256")
        modes = document.get("response_modes_supported")
        if modes is not None and "query" not in _strings(modes):
            raise _refused("the provider does not offer response_mode=query")
        if "public" not in _strings(document.get("subject_types_supported")):
            raise _refused("the provider does not offer public subject identifiers")
        algorithms = document.get("id_token_signing_alg_values_supported")
        if algorithms is not None and not set(self._settings.algorithms) & set(
            _strings(algorithms)
        ):
            raise _refused("the provider signs with none of the configured algorithms")
        self._metadata = ProviderMetadata(**endpoints)
        return self._metadata

    async def authorization_url(self, *, state: str, nonce: str, code_verifier: str) -> str:
        """Where the browser goes: code flow, PKCE S256, response_mode=query, scope openid."""
        metadata = await self.metadata()
        parts = urlsplit(metadata.authorization_endpoint)
        params = parse_qsl(parts.query, keep_blank_values=True)
        params.extend(
            [
                ("response_type", "code"),
                ("response_mode", "query"),
                ("client_id", self._settings.client_id),
                ("redirect_uri", self._settings.redirect_uri),
                ("scope", "openid"),
                ("state", state),
                ("nonce", nonce),
                ("code_challenge", code_challenge(code_verifier)),
                ("code_challenge_method", "S256"),
            ]
        )
        return urlunsplit(parts._replace(query=urlencode(params)))

    async def exchange(self, *, code: str, code_verifier: str, nonce: str) -> dict[str, Any]:
        """Redeem the code and return the claims of a fully validated ID token."""
        metadata = await self.metadata()
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._settings.redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self._settings.client_id,
        }
        auth = None
        if self._settings.client_secret is not None:
            auth = httpx.BasicAuth(self._settings.client_id, self._settings.client_secret)
        answer = await self._request("POST", metadata.token_endpoint, data=form, auth=auth)
        if not isinstance(answer, dict):
            raise _refused("the token answer is not a JSON object")
        id_token = answer.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise _refused("the token answer carries no ID token")
        return await self.validate_id_token(id_token, nonce=nonce)

    async def validate_id_token(self, token: str, *, nonce: str) -> dict[str, Any]:
        """Every rule of the module docstring, or :class:`OidcRefused`."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise _refused("the ID token header is unreadable") from None
        algorithm = header.get("alg")
        if algorithm not in self._settings.algorithms:
            raise _refused("the ID token uses an algorithm that is not configured")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise _refused("the ID token names no key")
        key = await self._key(kid, algorithm)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self._settings.algorithms),
                audience=self._settings.client_id,
                issuer=self._settings.issuer,
                leeway=_LEEWAY_SECONDS,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
        except jwt.PyJWTError:
            raise _refused("the ID token did not validate") from None
        token_nonce = claims.get("nonce")
        if not isinstance(token_nonce, str) or not hmac.compare_digest(token_nonce, nonce):
            raise _refused("the ID token carries another nonce")
        audience = claims.get("aud")
        azp = claims.get("azp")
        if isinstance(audience, list) and len(audience) > 1 and azp is None:
            raise _refused("a token for several audiences names no authorized party")
        if azp is not None and azp != self._settings.client_id:
            raise _refused("the ID token was issued to another party")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub.strip() or sub != sub.strip():
            raise _refused("the ID token names no usable subject")
        return claims

    def account_id_for(self, claims: dict[str, Any]) -> str:
        """The Nextcloud account id the configured strategy derives from validated claims."""
        return user_oidc_unique_uid_sub_v1(self._settings.provider_id, str(claims["sub"]))

    # --- transport -------------------------------------------------------------------

    async def _key(self, kid: str, algorithm: str) -> Any:
        now = self._clock()
        fresh = now - self._keys.fetched_at < JWKS_CACHE_SECONDS
        if not fresh or kid not in self._keys.keys:
            # At most one fetch per call: a fresh cache without the kid refetches once, a
            # stale cache refetches anyway, and either way the answer below is final.
            await self._refresh_keys(now)
        entry = self._keys.keys.get(kid)
        if entry is None:
            # Either no key at all, or a kid claimed by more than one usable key: both are
            # refused the same way, so a caller cannot tell a collision from an unknown kid.
            raise _refused("the ID token names an unknown or unusable key")
        key, alg = entry
        if alg is not None and alg != algorithm:
            raise _refused("the key is declared for another algorithm")
        return key

    async def _refresh_keys(self, now: float) -> None:
        metadata = await self.metadata()
        document = await self._get_json(metadata.jwks_uri)
        entries = document.get("keys") if isinstance(document, dict) else None
        if not isinstance(entries, list) or len(entries) > _MAX_KEYS:
            raise _refused("the JWKS is not a usable key list")
        keys: dict[str, _KeyEntry | None] = {}
        for entry in entries:
            usable = _usable_key(entry, self._settings.algorithms)
            if usable is None:
                continue
            kid, parsed = usable
            # A kid already seen becomes unusable rather than resolving to either key.
            keys[kid] = None if kid in keys else parsed
        self._keys = _KeyCache(keys=keys, fetched_at=now)

    async def _get_json(self, url: str) -> Any:
        return await self._request("GET", url)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        auth: httpx.Auth | None = None,
    ) -> Any:
        if not _same_origin(url, self._settings.issuer):
            raise _refused("a request would leave the issuer origin")
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
                raise _refused("the provider could not be reached") from None
            try:
                if response.status_code != 200:
                    raise _refused(f"the provider answered {response.status_code}")
                raw = await bounded_response(response, MAX_RESPONSE_BYTES)
            except (BodyTooLarge, BodyUnreadable):
                raise _refused("the provider answer is too large or unreadable") from None
            finally:
                await response.aclose()
        try:
            return json.loads(raw)
        except ValueError:
            raise _refused("the provider answer is not JSON") from None


def _usable_key(entry: object, algorithms: tuple[str, ...]) -> tuple[str, _KeyEntry] | None:
    """The ``(kid, (key, alg))`` of ``entry`` if it may verify a signature, else ``None``.

    ``use`` and ``key_ops``, when present, must each allow verification, and when both are
    present they must agree: ``use`` must be ``"sig"`` and ``key_ops`` must contain
    ``"verify"``. A declared ``alg`` outside the configured algorithms is unusable too, so
    the cache never carries a key for an algorithm the operator did not allow.
    """
    if not isinstance(entry, dict):
        return None
    if entry.get("kty") not in _ALLOWED_KEY_TYPES:
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
    except jwt.PyJWTError:
        return None
    return kid, (key, alg)


def _refused(reason: str) -> OidcRefused:
    logger.warning("OIDC refused: %s", reason)
    return OidcRefused()


def _strings(value: object) -> Sequence[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc.lower()


def _same_origin(url: str, issuer: str) -> bool:
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
        return _origin(url) == _origin(issuer) and _origin(url)[0] == "https"
    except ValueError:
        return False


def _require_https_origin(url: str, name: str, *, allow_path: bool) -> None:
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError:
        raise ValueError(f"{name} is not a valid URL") from None
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError(f"{name} must be an https URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError(f"{name} must not carry credentials, a query or a fragment")
    if not allow_path and parts.path not in ("", "/"):
        raise ValueError(f"{name} must not carry a path")

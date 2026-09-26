"""The token verifier of the transport boundary: the store, a short cache, two extra checks.

This module answers one question on every single tool call: is this bearer a token this
server issued, is it still valid, and whose Nextcloud account does it act as. It is the
production form of ``deps.StaticBearerVerifier``, which implements the same SDK protocol
for the single user deployment of phase 1, and it keeps the three properties that one was
written for: ``None`` instead of an exception on every failure, a comparison in constant
time on bytes, and a token that appears in no log record and in no answer.

**Why the store and not a Nextcloud round trip (D-34, D-37).** Validating a token against
Nextcloud would put a network call in the hot path of every tool call, and it would make
this server unavailable whenever Nextcloud is slow. The token is ours, so the answer is
ours: one indexed lookup by digest in a local SQLite file.

**Why a cache of five seconds and not of one hour.** Success criterion 5 says the store must
not sit in the hot path, and D-34 says a revocation takes effect at once. Five seconds is
the compromise between the two, spelled out as
:data:`mcp_connector.oauth.store.VALIDATION_CACHE_TTL`: long enough that a burst of tool
calls of one conversation costs one lookup, short enough that a user who ends a connection
does not wait. Only positive results are cached, because a cached refusal would outlive the
repair of whatever caused it, and :meth:`StoreTokenVerifier.invalidate` empties it in the
same process the moment something is revoked (plan 03-07 calls it).

**The two checks the SDK does not make.** The SDK verifies that a token exists; it does not
ask what the token was issued for and it does not ask whether the client behind it may
still act. Both are refusals here: a token whose audience is another MCP server is refused
even though it is perfectly valid (RFC 8707, pitfall 3, T-03-51), and a client that an
administrator blocked after its token was issued is refused although the token has not
expired (pitfall 9, T-03-55).

**Why the identity is resolved here and not in the credential layer.** ``deps.py`` runs
inside a tool call and is synchronous, while reading the authorization and decrypting its
app password is asynchronous work against the store. So the boundary resolves it once per
request and leaves it in the request state, and the credential layer reads a value instead
of doing I/O in the middle of a tool. The app password never enters the cache: it is read
per request, lives for that request and is masked in every repr (T-03-54).
"""

import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from mcp.server.auth.provider import AccessToken
from mcp.shared.auth import OAuthClientInformationFull
from mcp.shared.auth_utils import check_resource_allowed

from .. import config
from .metadata import RESOURCE_SUFFIX
from .principal import login_name_of, principal_of
from .store import VALIDATION_CACHE_TTL, OAuthStore, token_hash

__all__ = [
    "AUTH_ID_CLAIM",
    "CACHE_LIMIT",
    "CLIENT_NAME_CLAIM",
    "CREDENTIAL_APP_PASSWORD",
    "CREDENTIAL_IMPERSONATE",
    "OAUTH_STATE_ATTR",
    "IdentitySource",
    "OAuthIdentity",
    "StoreTokenVerifier",
]

#: How a caller hands in the store of this application, the same shape ``provider.py`` uses.
type StoreProvider = Callable[[], Awaitable[OAuthStore]]


class ClientLookup(Protocol):
    """The enforcement point of AUTH-07, handed in rather than imported.

    The verifier asks the very same ``get_client`` the authorization endpoints ask, so one
    block covers all of them. ``may_fetch`` is part of the shape because this caller must
    be able to say no to it: a document identity whose freshness ran out would otherwise
    be refetched from a host the client named, in the hot path of every tool call (WR-01),
    which is exactly the network call the module docstring promises away.
    """

    def __call__(
        self, client_id: str, *, may_fetch: bool = True
    ) -> Awaitable[OAuthClientInformationFull | None]: ...


#: Where the id of the authorization travels inside the SDK token model. The model has no
#: field for it, and ``claims`` is what it offers for exactly this (RFC 7662 style claims).
#: The value is an internal id, never a secret: it is the flow id of a consent that already
#: happened, and by itself it grants nothing.
AUTH_ID_CLAIM = "auth_id"

#: Where the registered name of the client travels, next to the id of the authorization and
#: for the same reason: the token model has no field for it, and ``claims`` is what it offers.
#: The value is public information a client chose for itself at registration time, never a
#: secret, and it is carried rather than looked up later: the audit log has to survive ``occ
#: mcp_connector:purge``, which empties the client table, so a name resolved at reading time
#: would be gone by then.
CLIENT_NAME_CLAIM = "client_name"

#: The name the transport boundary deposits the resolved identity under, and the name
#: ``deps.py`` reads. One constant, so the two sides cannot drift apart.
OAUTH_STATE_ATTR = "oauth_identity"

#: The credential way of every connection that exists today: an app password of its own,
#: created for one connection, which is Basic authentication towards Nextcloud
#: (``nextcloud/credentials.py``, ``MODE_BASIC``).
CREDENTIAL_APP_PASSWORD = "app-password"  # noqa: S105 - the name of a credential way, not a password

#: The credential way plan 23-03 builds: the container speaks with ``APP_SECRET`` on behalf
#: of an account, without anything ever having been provisioned for that account. Nothing
#: hands this value out yet; it exists so both ways are named in one place from the start.
CREDENTIAL_IMPERSONATE = "appapi-impersonation"

#: The hard ceiling of the process cache. A dictionary that grows with every token somebody
#: presents is a denial of service with a delay, so it is emptied when it is full rather
#: than trimmed cleverly: the entries live five seconds anyway, and a simpler rule is one
#: that cannot leak (T-03-56).
CACHE_LIMIT = 1024

logger = logging.getLogger("mcp_connector.oauth.verifier")


@dataclass(frozen=True, slots=True, repr=False)
class OAuthIdentity:
    """Who a verified token acts as, and with which Nextcloud credential.

    The app password is a live Nextcloud credential, so this object masks its repr like
    every other credential carrier of this project (``nextcloud/credentials.py``). It is
    built per request and never cached.

    ``nc_user`` is the login name, the value Nextcloud Basic authentication needs.
    ``principal`` is the value every identity decision uses: the pause switch on ``/mcp``
    and the audit subject (oauth/principal.py). Both come from the connection row.

    ``revoked`` is carried rather than turned into a refusal here, because the two sides
    answer differently: the transport boundary refuses a token whose connection is gone,
    while the credential layer turns a connection that was ended into a sentence the user
    can act on ("connect the app again").

    ``client_name`` is the name the client gave itself at registration, carried unquoted:
    it is attacker chosen input, and the one place that quotes it is the one that writes it
    into a line or onto a page. It defaults to the empty string and never to ``None``, so a
    reader never has to distinguish "no name" from "no field".

    ``actor`` is the acting party of a delegation: the ``azp`` of a token this server did
    not issue, which names a client of a foreign realm (AUDIT-07). It is a different fact
    from ``client_name``, which is why it is a field of its own and not the same column used
    twice: a registered client named itself **here**, an acting party registered somewhere
    else, and a reader who has only one name column cannot tell the two apart without
    reading ``client_id`` alongside. Both are foreign text and both are carried unquoted,
    under the same rule and for the same reason. That sameness holds for carrying them and
    not for the debugging output: ``actor`` is deliberately left out of the repr, because it
    names a client of a foreign realm and a repr ends up in logs that nobody reads as an audit
    path. Whoever wants to see the acting party reads the ``actor`` column of the audit trail.
    ``client_name`` stands in the repr because that name was registered here. The omission
    is the direction the owner accepted for R-24-04 (24-SECURITY.md), and a test holds it. It
    defaults to the empty string, which is every path that has no delegation, so no existing
    construction site changes meaning.

    ``credential`` says **where** the Nextcloud credential of this request comes from, and
    never who the caller is. ``app_password`` is empty under
    :data:`CREDENTIAL_IMPERSONATE`, because there is none; the credential layer reads this
    field and never the emptiness of the password, because "empty" could also be a broken
    read. It defaults to :data:`CREDENTIAL_APP_PASSWORD`, which is everything that exists
    today, so no existing construction site changes meaning.
    """

    nc_user: str
    app_password: str
    auth_id: str
    client_id: str
    principal: str
    revoked: bool = False
    client_name: str = ""
    actor: str = ""
    credential: str = CREDENTIAL_APP_PASSWORD

    def __repr__(self) -> str:
        return (
            f"OAuthIdentity(nc_user={self.nc_user!r}, principal={self.principal!r}, "
            f"auth_id={self.auth_id!r}, "
            f"client_id={self.client_id!r}, client_name={self.client_name!r}, "
            f"revoked={self.revoked!r}, credential={self.credential!r}, "
            f"app_password='***')"
        )


@runtime_checkable
class IdentitySource(Protocol):
    """A token verifier that can also say whose connection a token is.

    The SDK protocol ends at :meth:`verify_token`; this one adds the half this application
    needs to run a tool call as the right Nextcloud user. It is a protocol and not a base
    class so the transport boundary keeps taking any ``TokenVerifier``: a verifier without
    an identity half simply deposits nothing, which is the fail-closed reading.
    """

    async def verify_token(self, token: str) -> AccessToken | None: ...

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None: ...


@dataclass(frozen=True, slots=True, repr=False)
class _Cached:
    """One positive answer, its deadline and the digest it was given for."""

    digest: str
    access: AccessToken
    expires_at: float

    def __repr__(self) -> str:
        return f"_Cached(expires_at={self.expires_at!r}, digest='***')"


class StoreTokenVerifier:
    """Verify a bearer against the store of this deployment, and say who it is.

    Built once per application, next to the provider and sharing its store and its client
    lookup, so a revocation on one side is visible on the other without a second source of
    truth.
    """

    def __init__(
        self,
        *,
        store_provider: StoreProvider,
        get_client: ClientLookup,
        env: Mapping[str, str] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._store = store_provider
        self._get_client = get_client
        #: The audience every token of this server carries, built from the configured
        #: public URL and never from a request (T-03-02), exactly like the provider's.
        self._resource = f"{config.public_url(env)}{RESOURCE_SUFFIX}"
        #: Monotonic by default: a cache window must not grow or shrink because somebody
        #: corrected the system clock.
        self._clock = clock if clock is not None else time.monotonic
        self._cache: dict[str, _Cached] = {}

    def __repr__(self) -> str:
        return f"StoreTokenVerifier(resource={self._resource!r}, cached={len(self._cache)})"

    def invalidate(self) -> None:
        """Forget every cached answer at once.

        Called when something is revoked in this process (plan 03-07): the window is five
        seconds, and five seconds of a connection the user just ended is five seconds too
        many. Emptying everything instead of one entry keeps the caller from having to know
        which tokens belonged to the family it just killed.
        """
        self._cache.clear()

    async def verify_token(self, token: str) -> AccessToken | None:
        """The SDK protocol: a valid token becomes an ``AccessToken``, everything else None.

        Unknown, expired, revoked, issued for another resource and issued to a client that
        is blocked by now are one answer from outside, and that is deliberate: an answer
        that separated them would say which of the checks fired (T-03-47).
        """
        if not token:
            return None

        digest = token_hash(token)
        cached = self._cached(digest)
        if cached is not None:
            return cached

        try:
            store = await self._store()
            row = await store.load_access_token(token)
            if row is None:
                return None
            authorization = await store.load_authorization(row.auth_id)
        except Exception as exc:
            # A store that cannot be opened or read is never a reason to let a caller in
            # (D-37, T-03-56). The kind of the failure is logged, no value of the request.
            logger.error("a token could not be verified against the store: %s", type(exc).__name__)
            return None

        if authorization is None or authorization.revoked_at is not None:
            return None
        if not row.resource or not check_resource_allowed(row.resource, self._resource):
            # RFC 8707: a token for another MCP server, or one without an audience at all,
            # which would be valid at every server a user connects (pitfall 3, T-03-51).
            return None
        client = await self._get_client(authorization.client_id, may_fetch=False)
        if client is None:
            # The fourth enforcement point of AUTH-07: a block has to reach tokens that
            # were issued before it (pitfall 9, T-03-55). ``may_fetch=False`` keeps the
            # promise of the module docstring against every host, not only Nextcloud
            # (WR-01): a document identity is read from its stored row here, stale or not,
            # and never refetched in the hot path of a tool call. A stranger's outage
            # minute must not end a running session whose token is valid.
            return None

        access = AccessToken(
            token=token,
            client_id=authorization.client_id,
            scopes=row.scopes.split(),
            expires_at=row.expires_at,
            resource=row.resource,
            subject=principal_of(row),
            # The name comes from the client this check has just loaded anyway: zero
            # additional reads, no second lookup and no new ``await``. The price is that a
            # rename is visible up to the cache window of five seconds later, which is
            # without consequence for a record of what happened.
            claims={AUTH_ID_CLAIM: row.auth_id, CLIENT_NAME_CLAIM: client.client_name or ""},
        )
        self._remember(digest, access)
        return access

    async def resolve_identity(self, access: AccessToken) -> OAuthIdentity | None:
        """The Nextcloud identity behind a verified token, for exactly one request.

        Read fresh every time and never cached, for two reasons at once: the value is a
        live Nextcloud credential, and it is the one lookup that still sees a revocation
        that happened inside the cache window of :meth:`verify_token`.
        """
        claims = access.claims or {}
        auth_id = str(claims.get(AUTH_ID_CLAIM) or "")
        if not auth_id:
            # A token from another verifier. Nothing here may act on it.
            return None

        try:
            store = await self._store()
            row = await store.load_authorization(auth_id)
            if row is None:
                return None
            password = await store.app_password(auth_id)
        except Exception as exc:
            logger.error("an authorization could not be read back: %s", type(exc).__name__)
            return None

        if not password:
            return None
        return OAuthIdentity(
            nc_user=login_name_of(row),
            app_password=password,
            auth_id=auth_id,
            client_id=row.client_id,
            principal=principal_of(row),
            revoked=row.revoked_at is not None,
            # Copied from the claim rather than read from the store: the name rode along
            # with the token, so a missing claim is an empty name and never a lookup.
            client_name=str(claims.get(CLIENT_NAME_CLAIM) or ""),
        )

    def _cached(self, digest: str) -> AccessToken | None:
        """The cached answer for this digest, or ``None``. Never a stale one.

        ``compare_digest`` and not ``==`` on the way out: the entry repeats the digest it
        was stored for and it is compared in constant time, so nothing about a lookup can
        be learned from how long it took. The dictionary is keyed by the digest and never
        by the token, so the token itself is not a key anywhere in this process.
        """
        entry = self._cache.get(digest)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            del self._cache[digest]
            return None
        if not secrets.compare_digest(entry.digest, digest):  # pragma: no cover - key equality
            return None
        return entry.access

    def _remember(self, digest: str, access: AccessToken) -> None:
        """Keep one positive answer for the window, inside the ceiling."""
        if len(self._cache) >= CACHE_LIMIT:
            self._cache.clear()
        self._cache[digest] = _Cached(
            digest=digest, access=access, expires_at=self._clock() + VALIDATION_CACHE_TTL
        )

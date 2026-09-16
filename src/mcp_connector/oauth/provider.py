"""The authorization server of this app: the SDK protocol, plus the four controls it lacks.

**Why a provider and not four endpoints of our own.** The stack research of phase 0 said
the SDK brings no authorization server; for mcp 2.0.0 that is wrong, and the difference is
the size of this plan. ``create_auth_routes`` serves ``/authorize``, ``/token``,
``/register`` and ``/revoke`` with PKCE as a required field, ``S256`` as the only method
the request model accepts, exact redirect matching, an expiring code, client
authentication with ``compare_digest`` and the RFC error shapes for all of them. Rebuilding
that would mean rewriting tested security code to arrive at the same behaviour. What the
SDK deliberately leaves to us is the policy, and that is what lives here: the audience
binding of RFC 8707, the https rule for redirect addresses, the refresh rotation with reuse
detection, and the client allowlist of AUTH-07.

**Why not ``auth_server_provider=`` on the MCPServer constructor.** It works, and it
attaches the same routes to the MCP application instead of to this deployment mode, which
would put them into the standalone HTTP server of phase 1 as well (D-23). It also installs
``ProviderTokenVerifier``, which verifies a bearer through ``load_access_token`` and
therefore bypasses both the process cache and the audience check that plan 03-06 builds.
The routes are handed out by :func:`auth_routes` and attached by ``entry_exapp`` alone,
exactly like every other route factory of this project.

**What is built here and what refuses.** ``register_client``, ``get_client``, ``authorize``,
``load_authorization_code``, ``exchange_authorization_code``, ``load_refresh_token``,
``exchange_refresh_token`` and ``revoke_token`` are complete: a client can register, ask, be
sent through the sign in, trade its code for a token, rotate that token for weeks and end
the whole connection in one request. Only ``exchange_identity_assertion`` refuses, and it
refuses permanently rather than until a later plan (D-33).

**The two sentences the rotation is built on.** A refresh token is redeemed exactly once,
and the redemption is one ``UPDATE`` under ``BEGIN IMMEDIATE`` in the store, so of two
simultaneous requests exactly one changes a row (pitfall 10). A second use of an already
redeemed token is a network retry inside :data:`~mcp_connector.oauth.store.ROTATION_GRACE`
seconds and an attack after them (D-41).

**Why ``load_access_token`` stays a refusal although the tokens exist.** It is the hook of
the SDK's ``ProviderTokenVerifier``, which this deployment does not install: the bearer of
every request is checked by ``oauth/verifier.py``, which adds the process cache, the
audience check of RFC 8707 and the client policy. A second, weaker path to the same
decision is not a convenience, it is the one that gets forgotten in a review.

**Why ``get_client`` is the enforcement point.** ``/authorize``, ``/token`` and ``/revoke``
all load their client through it, so one refusal here covers all three (pitfall 9). It
answers ``None`` for a client that is unknown, blocked by an administrator, missing from
the allowlist or expired, and those four are indistinguishable from outside on purpose: an
answer that separates them is an information service for whoever is guessing (T-03-47).
"""

import base64
import binascii
import copy
import json
import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import unquote

from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import AuthenticationError, ClientAuthenticator
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    IdentityAssertionParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.server.auth.routes import (
    AUTHORIZATION_PATH,
    REGISTRATION_PATH,
    REVOCATION_PATH,
    TOKEN_PATH,
    cors_middleware,
    create_auth_routes,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from mcp.shared.auth_utils import check_resource_allowed
from pydantic import AnyHttpUrl, AnyUrl, BaseModel, ValidationError
from starlette.datastructures import FormData, MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .. import config
from ..errors import IssuerRefused
from ..exapp.auth import is_user
from ..exapp.responses import NO_STORE, form_or_none, json_response
from ..exapp.ui.consent import consent_url
from ..nextcloud.target import NextcloudTarget
from . import cimd, loginflow
from .metadata import (
    AS_METADATA_SUFFIX,
    PUBLIC_CLIENT_AUTH_METHOD,
    REFRESH_SCOPE,
    REGISTERED_SCOPE,
    RESOURCE_SUFFIX,
    TOOL_SCOPE,
)
from .registry import (
    IDLE_REGISTRATION_TTL,
    UNUSED_REGISTRATION_TTL,
    ClientPolicy,
    client_policy,
    redirect_uri_allowed,
)
from .store import (
    ACCESS_TOKEN_TTL,
    REDEEM_OK,
    REDEEM_REUSED,
    ROTATION_GRACE,
    STATE_REVOKED,
    ClientRow,
    OAuthStore,
    store_opener,
    token_hash,
)
from .throttle import CLASS_REGISTER, CLASS_REVOKE, CLASS_TOKEN, Throttle, Throttled

__all__ = [
    "FAMILY_BYTES",
    "HELD_ANSWER_LIMIT",
    "SWEEP_LIMIT",
    "TOKEN_BYTES",
    "FamilyRevocation",
    "HashedClientAuthenticator",
    "NextcloudOAuthProvider",
    "NoStore",
    "StoreProvider",
    "auth_routes",
]

#: The two client authentication methods of RFC 6749 §2.3.1. Named here so the literal
#: appears once and so the third method of the registry, ``none``, is the absence of both.
_AUTH_BASIC = "client_secret_basic"
_AUTH_POST = "client_secret_post"

#: The two verbs the machine endpoints of the authorization server answer. ``OPTIONS`` is
#: the CORS preflight the SDK wrapper handles; the manifest declares ``POST`` alone,
#: because no browser calls these endpoints cross origin in this topology (D-38).
_MACHINE_VERBS = ["POST", "OPTIONS"]

#: How a caller hands in its own store, which is what the tests of this module do and what
#: ``entry_exapp`` uses to give the browser onboarding and the authorization server the same
#: one. Without it the provider opens its own on first use.
type StoreProvider = Callable[[], Awaitable[OAuthStore]]

#: What a refused registration says. It names the reason, because an administrator turned
#: the switch off and the developer on the other end has to learn that from the answer
#: rather than from a support ticket (D-40).
_DCR_OFF = "dynamic client registration is disabled on this instance"

#: What a refused redirect address says. It names the rule and not the address: the value
#: came from the request and is echoed nowhere.
_REDIRECT_RULE = "redirect_uris must use https, except loopback addresses of native clients"

#: The description of the one grant type this server refuses on purpose. One sentence, no
#: internal detail: a client cannot act on a design decision, and an attacker should not
#: read one either.
_NOT_YET = "this authorization server cannot complete the request"

#: What a refused exchange says. Each names the rule and never a value of the request: the
#: developer on the other end has to be able to fix the call, and nothing more is owed.
_NO_AUDIENCE = "the grant carries no resource, which this server requires (RFC 8707)"
_WRONG_AUDIENCE = "the grant was issued for another resource"
_CLIENT_GONE = "this client may not use this authorization server"
_CODE_SPENT = "the authorization code is not valid"

#: The one sentence every refused refresh grant gets, and deliberately the only one.
#: Unknown, expired, already redeemed outside the window, redeemed inside the window with
#: no held answer left and belonging to a connection that was ended are five different
#: events; an answer that told them apart would say which check fired, which is exactly the
#: information a replay is looking for (RFC 6749 §5.2, T-03-47, T-03-66).
_GRANT_GONE = "the refresh token is not valid"

#: 32 bytes of entropy behind every token this server issues, which ``token_urlsafe``
#: renders as 43 characters. The token is the whole authorisation of a connection, and it
#: exists on disk only as its SHA-256 digest.
TOKEN_BYTES = 32

#: The id that ties an access token to the refresh token it was issued with. Not a secret,
#: never handed out, and the unit a reuse detection kills in plan 03-07.
FAMILY_BYTES = 16

_HINT_ISSUER = (
    f"{config.ENV_PUBLIC_URL} is the address clients reach this app under, for example "
    "https://cloud.example.com/exapps/mcp_connector. RFC 8414 requires https for an issuer, "
    "with the loopback exception for a local test."
)

#: 32 bytes of entropy behind a flow id, which ``token_urlsafe`` renders as 43 characters.
#: The value is the whole authorisation of the consent screen for the length of one sign
#: in, so it is drawn from the same generator as every other secret of this phase.
FLOW_ID_BYTES = 32

#: How many answers of a rotation may be held for the grace window at once. The ceiling is
#: hard and the reaction to it is to empty the whole dictionary, exactly like the process
#: cache of the verifier: the entries live ten seconds anyway, and a rule that cannot leak
#: beats a clever one that can (T-03-67).
HELD_ANSWER_LIMIT = 256

#: How many abandoned sign ins one authorization request cleans up after. Every one of them
#: costs a Nextcloud round trip on a path where a person is waiting, so the number is small
#: and the sweep is a background chore that finishes over several connections rather than a
#: batch job that delays one of them.
SWEEP_LIMIT = 3

logger = logging.getLogger("mcp_connector.oauth.provider")


def _nothing() -> None:
    """The cache eraser of a provider that was never given one (the tests, phase 1 modes)."""


@dataclass(frozen=True, slots=True, repr=False)
class _Held:
    """One answer of a rotation, kept for the length of the grace window and no longer.

    **Why this is a cache and not session state (SRV-05).** It holds an answer that was
    already sent, for ten seconds, in one process. Losing it, through a restart, a second
    worker or the hard ceiling, costs a network retry its repeat answer and nothing else:
    the retry gets ``invalid_grant`` and the client reconnects, which is the same path it
    walks when a refresh token finally expires. Nothing in this server reads it to decide
    who somebody is.
    """

    digest: str
    answer: OAuthToken
    expires_at: float

    def __repr__(self) -> str:
        return f"_Held(expires_at={self.expires_at!r}, digest='***')"


class NextcloudOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """The one provider of this deployment. Built once per application, never per request."""

    def __init__(
        self,
        *,
        nextcloud: NextcloudTarget,
        env: Mapping[str, str] | None = None,
        policy: ClientPolicy | None = None,
        store_provider: StoreProvider | None = None,
        clock: Callable[[], float] | None = None,
        resolver: cimd.AddressLookup | None = None,
    ) -> None:
        self._env = env
        #: The Nextcloud every login flow of this provider starts at and every app password
        #: it hands back belongs to. Injected, never read from the environment here.
        self._nextcloud = nextcloud
        self._policy = policy if policy is not None else client_policy(env)
        self._store = store_provider if store_provider is not None else store_opener(env)
        #: The canonical audience of every token this server issues (RFC 8707). Built from
        #: the configured public URL and never from a request, like every other identity
        #: statement of this app (T-03-02).
        self._resource = f"{config.public_url(env)}{RESOURCE_SUFFIX}"
        #: Wall clock and not ``monotonic``: the grace window compares against ``used_at``
        #: of a row, which is written in seconds since the epoch and has to survive the
        #: second worker on the same file. A parameter, so a test can stand on both sides
        #: of a ten second window without sleeping.
        self._clock = clock if clock is not None else time.time
        #: How a name is resolved for the one outbound request this server makes on a
        #: stranger's behalf (AUTH-08). A parameter for the same reason ``clock`` is one: a
        #: test hands in a resolver instead of patching a library, and nothing in the unit
        #: suite touches a socket. ``None`` means the resolver of ``cimd`` itself, which is
        #: this host's own.
        self._resolver = resolver
        self._held: dict[str, _Held] = {}
        #: The process cache of the verifier, handed in by ``entry_exapp`` through
        #: :meth:`on_revocation`. Without it a revocation would take effect at the next
        #: store lookup instead of at once, which is up to five seconds of a connection the
        #: user just ended (T-03-62).
        self._invalidate: Callable[[], None] = _nothing
        #: The one return address a per request view of this provider lets a client use on
        #: top of its registration, set by :meth:`also_accepting` and never here. ``None``
        #: on the provider the application builds, which is the only one that is long lived.
        self._also: AnyUrl | None = None

    def __repr__(self) -> str:
        return f"NextcloudOAuthProvider(resource={self._resource!r}, policy={self._policy!r})"

    @property
    def policy(self) -> ClientPolicy:
        """What an administrator decided. Read by the consent screen and by the routes."""
        return self._policy

    async def store(self) -> OAuthStore:
        """The store of this application, opened at its first use."""
        return await self._store()

    def on_revocation(self, invalidate: Callable[[], None]) -> None:
        """Take the cache eraser of the verifier that shares this store.

        Handed in rather than imported, for the reason the verifier takes ``get_client``
        the same way: the two objects are built next to each other in ``entry_exapp`` and
        neither may reach into the other's internals to find the same answer twice.
        """
        self._invalidate = invalidate

    def _now(self) -> int:
        """Whole seconds, from the one clock this provider reads."""
        return int(self._clock())

    # --- the two halves this plan builds ------------------------------------------------

    async def get_client(
        self, client_id: str, *, may_fetch: bool = True
    ) -> OAuthClientInformationFull | None:
        """The enforcement point of AUTH-07, on the way into three endpoints.

        Four refusals with one answer, and a fifth that is not a refusal but a sweep: a
        registration that never produced a token is deleted when somebody asks for it, and
        so is one that has not been used for a season. That is the whole cleanup of the
        registry (T-03-44), because this project has no cron and a table that only grows
        is a denial of service with a delay.

        **``may_fetch`` separates the policy question from the freshness question** (WR-01,
        WR-03). Every caller of this method asks "may this client still act", and for a
        document identity that question used to carry a hidden second one: "and is the
        document still fresh", whose answer could be an outbound request against a host the
        client named. The verifier of every tool call, the client authentication of
        ``/token`` and ``/revoke`` and the two exchanges all promise in writing that no
        foreign network sits in their path, so they ask with ``may_fetch=False`` and read
        only the stored row: an identity that was bound byte for byte once changes rarely,
        and a stale one is strictly better on those paths than an unavailable server or a
        session killed by a stranger's outage minute. The refetch belongs to the one path
        where a person with a browser is waiting, ``/authorize``, whose callers keep the
        default. The policy questions themselves, the allowed flag, the allowlist and the
        switch, are answered either way, so a block still reaches every endpoint at once.

        **Why the registration TTL does not apply to a document identity** (pitfall 4,
        T-06-31). The two windows above say "a registration nobody ever used" and "a
        connection nobody has used for a season", and both sentences describe something
        nobody can bring back. An identity that came from a metadata document is the
        opposite of that: it can be read again at any moment, so it is never orphaned, and
        the row is not a registration a client made but this server's own note of what it
        read. Deleting it would take every ``authorizations`` row under it along through
        the cascade, which is a user's connection ended by a deadline that user never met.
        What does run out for such a row is its freshness, and running out of freshness
        costs one fetch. The sweep of :meth:`sweep_expired_clients` skips these rows in the
        store for the same reason, and ``purge_expired`` still removes them once no
        connection hangs on them at all, which is what keeps the table finite.
        """
        try:
            store = await self.store()
            row = await store.load_client(client_id)
        except Exception as exc:
            # A store that cannot be opened or read is not a reason to let a client in
            # (D-37). The kind of the failure is logged, no value of the request is.
            logger.error("the client lookup has no store: %s", type(exc).__name__)
            return None

        if row is None or row.cimd_fetched_at is not None:
            # The one branch of AUTH-08, and it is here so that everything below it applies
            # to a client that identifies itself with a metadata document exactly as it
            # applies to one that registered: the allowed flag, the allowlist and the
            # expiry are the shared rest of this function and not a copy of it. Three cases
            # arrive here and :meth:`_resolve_cimd` tells them apart: no row at all, a row
            # whose freshness ran out, and a row that is still fresh.
            row = await self._resolve_cimd(client_id, store, row=row, may_fetch=may_fetch)
            if row is None:
                return None

        client = _client_information(row.metadata_json, client_id)
        if client is None:
            return None

        if not row.allowed:
            return None

        addresses = [str(uri) for uri in client.redirect_uris or []]
        if not self._policy.allows(client_id, addresses):
            return None

        if row.cimd_fetched_at is None and _has_expired(row.registered_at, row.last_used_at):
            # The credentials first, then the row (WR-04): ``authorizations`` points at
            # ``clients`` with ON DELETE CASCADE, so the delete would take the ciphertext of
            # every app password under this client along and leave the credentials working
            # at Nextcloud with no record that they exist.
            await self._hand_back_client(store, client_id)
            await store.delete_client(client_id)
            return None

        if self._also is not None and self._also not in (client.redirect_uris or []):
            # The one address :meth:`also_accepting` was asked to let through, added to the
            # object and to nothing else. It is added last, after every check above, so the
            # allowlist and the expiry still see the registration as it is on disk.
            client = client.model_copy(
                update={"redirect_uris": [*(client.redirect_uris or []), self._also]}
            )

        return client

    async def _resolve_cimd(
        self,
        client_id: str,
        store: OAuthStore,
        *,
        row: ClientRow | None = None,
        may_fetch: bool = True,
    ) -> ClientRow | None:
        """The store row of a client that identifies itself with a metadata document.

        ``None`` for every refusal, never an exception (D-37): the callers of
        :meth:`get_client` are request handlers in four endpoints, and a client whose
        document could not be read gets the same answer as one nobody ever heard of
        (T-06-33).

        **The switch is the first question, before any packet** (T-06-26, T-06-28). A
        disabled CIMD must not be a switched off feature that still makes outbound requests
        for whoever asks, so the refusal happens before the form of the identifier is even
        looked at. ``cimd_enabled`` is derived fail closed from the DCR switch in
        ``registry`` (plan 06-03), which is how the locked decision "a disabled DCR must not
        be bypassable through CIMD" holds without a second reading of a second switch here.
        It also holds for a row that already exists: an administrator who turns the switch
        off means the clients of this path, not only the next one of them.

        **Then freshness, and only then a request.** A row whose ``cimd_expires_at`` is
        still in the future is handed straight back, which is the whole cache: no request,
        no second identity, and the deadline is the one the answer's own cache header asked
        for inside our bounds (:func:`cimd.cache_lifetime`). A row whose deadline passed is
        read again, and a read that fails is a refusal rather than a walk on with an
        identity that may have changed (T-06-32). This is the one place the freshness
        question is asked, so :meth:`get_client` cannot forget it for one of its three
        cases.

        **``may_fetch=False`` is the hot path answer to a deadline that passed** (WR-01,
        WR-03). The verifier of every tool call and the token endpoints may not wait on a
        host the client named, so for them a stale row keeps answering: the identity was
        bound byte for byte once, the shared rest of :meth:`get_client` still applies every
        policy question to it, and the next ``/authorize`` pays the refetch. A client this
        server has no row for is a plain refusal on those paths, because an identity that
        was never read cannot be reused, only fetched, and fetching is exactly what is
        forbidden there. Fail closed both ways, and no packet either way.

        **The allowlist is asked before any packet as well** (WR-02). In the allowlist
        mode an unlisted identifier used to be fetched first and refused after, which
        handed an unauthenticated caller of ``/authorize`` an outbound GET to any public
        https target of their choosing, in the hardest configuration this server has. The
        identifier of this path is the URL of the document, so the id form of the listing
        is known before any request and is required here: an administrator who runs the
        allowlist mode lists a document client by that URL. A listing by return address
        cannot admit the fetch, because the addresses exist only inside the document
        nobody has read yet; that residual asymmetry is deliberate and the price of "no
        packet on a stranger's word", and the registration path is untouched by it.

        **Why a row and not only a cache entry** (pitfall 3). ``flows.client_id`` and
        ``authorizations.client_id`` reference ``clients(client_id)`` with a foreign key, so
        a client that exists only in memory would fail the first ``/authorize`` with an
        integrity error. The row is therefore written before this returns, and it is written
        with ``secret_hash=None`` in every case: a client of this path is public by
        definition, ``validate_document`` already refuses every shared secret method
        (T-06-30), and ``client_secret_hash`` reads ``None`` as "this client has no secret".

        The return addresses go through the very same check as a registration
        (``redirect_uri_allowed``, D-35), including the partial acceptance of plan 03-09: a
        forbidden entry is dropped and the admissible ones are kept, and a document with no
        admissible entry left writes no row at all (T-06-29). There is no
        ``RegistrationError`` anywhere on this path, because an exception out of
        :meth:`get_client` would be a new failure shape in four endpoints.
        """
        if not self._policy.cimd_enabled:
            return None
        if row is not None and _cimd_is_fresh(row, self._now()):
            return row
        if not may_fetch:
            # The hot paths (WR-01, WR-03): a stale row keeps answering and a missing one
            # is a refusal, and neither costs a packet. The shared rest of ``get_client``
            # still asks every policy question about the row this returns.
            return row
        if self._policy.allowlist_only and not self._policy.listed(client_id):
            # Before any packet (WR-02): in the allowlist mode the listed id decides
            # whether this server makes an outbound request at all. The identifier of this
            # path is the URL of the document, so an administrator can list it in advance,
            # and an unlisted one is refused without a resolution and without a fetch.
            return None
        if client_id != client_id.strip():
            # An identifier this server would fetch under one spelling and store under
            # another is a refusal, not a normalisation: the difference between the two
            # spellings is what an attacker would get (the rule of the ``issuer`` check).
            return None
        if not cimd.is_cimd_client_id(client_id):
            return None

        if self._resolver is None:
            found = await cimd.fetch_document_and_lifetime(client_id)
        else:
            found = await cimd.fetch_document_and_lifetime(client_id, resolver=self._resolver)
        if found is None:
            return None
        document, lifetime = found

        client = _cimd_client_information(document, client_id)
        if client is None:
            return None
        registrable = [uri for uri in client.redirect_uris or [] if redirect_uri_allowed(str(uri))]
        if not registrable:
            # The same refusal a registration of nothing but forbidden addresses gets: a
            # client with no return target is one this server could never send anywhere.
            logger.warning("a document was refused: it names no admissible return address")
            return None
        client.redirect_uris = registrable
        addresses = [str(uri) for uri in registrable]
        # The advertised set and the granted set have to be the same set, for the reason the
        # docstring of :meth:`register_client` gives at length: a client that reads
        # ``scopes_supported`` and asks for both entries would otherwise be refused by this
        # very server with ``invalid_scope``.
        client.scope = REGISTERED_SCOPE

        moment = self._now()
        try:
            await store.save_client(
                client_id,
                metadata_json=client.model_dump_json(exclude={"client_secret"}),
                secret_hash=None,
                # The same question a registration answers at this point, although in the
                # allowlist mode an unlisted identifier no longer reaches this write at all
                # (WR-02: it is refused before any packet). The call stays, so a policy
                # whose listing changes between the gate above and this write is recorded
                # as the policy answered it, and the refusal for a stored block still lives
                # in the shared rest of :meth:`get_client` (T-06-27).
                allowed=self._policy.allows(client_id, addresses),
                now=moment,
                cimd_fetched_at=moment,
                cimd_expires_at=moment + lifetime,
            )
            return await store.load_client(client_id)
        except Exception as exc:
            logger.error("a document identity could not be written: %s", type(exc).__name__)
            return None

    def also_accepting(self, address: AnyUrl) -> "NextcloudOAuthProvider":
        """This provider for one request, whose client also accepts ``address``.

        **Why this exists.** The SDK's authorization handler loads the client itself and
        compares the return address of the request against the registration a second time
        (``mcp/server/auth/handlers/authorize.py:180``). So the RFC 8252 7.3 port rule that
        ``consent.py`` applies to a loopback request has to reach that comparison, or it
        would have decided nothing: the request would pass our readable check and then be
        refused by the SDK with ``invalid_request``. This view is how it reaches it.

        **Why a view and not a write.** Nothing is stored. The copy lives for one request,
        the row on disk is untouched, and the next request sees the registration as it was:
        the anti pattern of putting a requested address into a registration would grow the
        row on every run and hand whoever holds a loopback port a permanent entry (T-06-19).
        The address is the one the port rule of ``registry`` already matched against that
        same registration, so this view cannot widen anything the rule did not widen, and
        the rule itself lives in exactly one place on the request path.
        """
        view = copy.copy(self)
        view._also = address
        return view

    async def client_secret_hash(self, client_id: str) -> str | None:
        """The stored digest of this client's secret, or ``None`` for a public client.

        Deliberately not part of what :meth:`get_client` returns: the SDK model carries a
        plaintext secret field, and a digest in it would be compared against a presented
        secret as if it were one. Whoever needs the digest asks for it, which is exactly
        one caller, :class:`HashedClientAuthenticator`.

        A store that cannot answer raises out of here instead of answering ``None``: the
        caller turns that into a refused authentication, and ``None`` would mean "this
        client has no secret", which is the one reading that would let a caller in.
        """
        store = await self.store()
        row = await store.load_client(client_id)
        return None if row is None else row.client_secret_hash

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Store a self registered client, once the two checks of D-35 pass.

        The SDK only attaches ``/register`` when registration is enabled, so the first
        check looks redundant. It is not: it is the half that names the reason, and it is
        the one that holds if the route is ever reachable another way. The second check is
        the one the SDK does not do at all: it accepts any address a registration sends,
        including ``http://`` on a host somebody else controls (T-03-41).

        **Why one forbidden address no longer refuses the whole registration (BL-04).**
        The rule of D-35 is unchanged and so is the reasoning behind it; what changed is
        what happens to the entries around a refused one. Cursor sends three addresses in
        one body, ``cursor://anysphere.cursor-mcp/oauth/callback`` next to an https one and
        a loopback one, and an all or nothing field check turned that into a 400 with our
        rule quoted in the client's own log: a whole class of clients stayed out over an
        entry it would not have had to use. A forbidden entry is therefore dropped and the
        allowed ones are registered, which RFC 7591 section 3.2.1 covers, because the
        answer carries the metadata that was registered and not the metadata that was sent.
        Dropping is not acceptance: the address is not in the record, so the exact matching
        of the SDK refuses it at ``/authorize`` exactly as before, and it cannot carry a
        listing in the allowlist mode either. A registration whose every address is
        forbidden is still a refusal, because a client with no return target is one the SDK
        would hand its "single registered address" to and there is none.

        **Why the scope is overwritten here.** The registration handler of the SDK writes
        the default scopes into a registration that names none, and ``validate_scope``
        later compares everything a client asks for at ``/authorize`` against that one
        recorded value. A client that reads ``scopes_supported`` out of our own metadata
        and asks for both entries was then refused by our own authorization server with
        ``invalid_scope``, which is what the live run of AUTH-04 measured against ChatGPT:
        it asks for ``offline_access nextcloud``, Claude asks for the tool scope alone and
        never saw it. The advertised set and the granted set have to be the same set, so
        every registration is recorded with both entries whatever it sent.

        This is not a widening: the two scopes are the two this server has, an unknown one
        is still refused one endpoint earlier by the SDK handler and at ``/authorize`` by
        ``validate_scope``, and D-42 still holds because ``offline_access`` names no data.
        It is the refresh switch of RFC 6749 §1.5, and what an access token of this server
        may reach is the curated tool surface either way.

        The value is written into the object rather than only into the record, because the
        handler echoes this very object back as the registration response (RFC 7591 §3.2.1
        asks a server to answer with the metadata it registered, not with the metadata it
        was sent), and a client that compares the two must see what it actually got.
        """
        if not self._policy.dcr_enabled:
            raise RegistrationError("invalid_client_metadata", _DCR_OFF)

        registrable = [
            uri for uri in client_info.redirect_uris or [] if redirect_uri_allowed(str(uri))
        ]
        if not registrable:
            raise RegistrationError("invalid_redirect_uri", _REDIRECT_RULE)
        # Written into the object, not only into the record: the handler echoes this very
        # object back, so a client that reads the answer sees what it may come back to.
        client_info.redirect_uris = registrable
        addresses = [str(uri) for uri in registrable]

        client_info.scope = REGISTERED_SCOPE
        secret = client_info.client_secret
        store = await self.store()
        await store.save_client(
            client_info.client_id,
            # The secret is dropped from the record and kept as a digest, like every other
            # credential of this phase (T-03-11). The client authenticator of plan 03-06
            # compares against that digest, which is what ``client_secret_hash`` exists for.
            metadata_json=client_info.model_dump_json(exclude={"client_secret"}),
            secret_hash=token_hash(secret) if secret else None,
            # In the allowlist mode a client that nobody listed is stored as not allowed,
            # so the block survives a restart and shows up in the admin view of phase 4.
            # A client whose return address is on the list is stored as allowed, because
            # that address is the only property an administrator can name in advance.
            allowed=self._policy.allows(client_info.client_id, addresses),
        )

    # --- what plan 03-06 and plan 03-07 fill in -----------------------------------------

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Open a Nextcloud sign in and send the browser to our own consent screen.

        The audience is decided here and not at the token endpoint, and it is required
        rather than defaulted: a token without an audience would be accepted by every other
        MCP server a user connects, which is the confused deputy this parameter exists
        against (RFC 8707, T-03-46). The second half of that check, at the moment the token
        is issued, is plan 03-06; refusing here means no sign in is even opened for a
        request that could never be granted.

        The Nextcloud round trip happens on this path and never on the token path. The
        browser has a generous timeout, the token endpoint of a connector has ten seconds
        (pitfall 13), and a Nextcloud call under load is exactly the sporadic timeout
        nobody can reproduce afterwards.
        """
        resource = (params.resource or "").strip()
        if not resource:
            raise AuthorizeError("invalid_target", "the resource parameter is required")
        if not check_resource_allowed(resource, self._resource):
            raise AuthorizeError("invalid_target", "the resource does not match this server")

        started = await loginflow.start_flow(client.client_name or "", target=self._nextcloud)
        if started is None:
            # loginflow logged what happened; nothing of the request is repeated here.
            raise AuthorizeError("temporarily_unavailable", "the sign in could not be started")

        flow_id = secrets.token_urlsafe(FLOW_ID_BYTES)
        try:
            store = await self.store()
            await store.create_flow(
                flow_id,
                client_id=client.client_id,
                redirect_uri=str(params.redirect_uri),
                redirect_uri_explicit=params.redirect_uri_provided_explicitly,
                code_challenge=params.code_challenge,
                state=params.state,
                scopes=" ".join(params.scopes or []),
                resource=resource,
                poll_token=started.poll_token,
            )
        except Exception:
            logger.exception("the authorization request could not be written to the store")
            raise AuthorizeError("server_error", "the request could not be remembered") from None

        try:
            # The chore of this project, on the one path that has a reason to pay for it:
            # a new connection hands back the credentials of the sign ins nobody finished
            # and of the registrations that ran out. Neither can break an authorization, so
            # neither raises out of here.
            await self.sweep_abandoned()
            await self.sweep_expired_clients()
        except Exception as exc:  # pragma: no cover - the sweeps guard themselves already
            logger.error("the sweep of abandoned sign ins failed: %s", type(exc).__name__)

        return consent_url(config.public_url(self._env), flow_id, started.login_url)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        """Read a code back, with everything the token endpoint compares against it.

        Reads and does not consume: the SDK loads a code, checks four things about it (it
        belongs to this client, it has not expired, the return address is the one of the
        authorization request, the PKCE verifier matches the challenge) and only then asks
        for the exchange. Spending the code inside this method would burn it on every
        failed check.

        Two of the fields come from the authorization rather than from the code: the client
        and the user. The code points at its authorization, and the authorization is the
        row that knows whose connection this is, which is also why a revoked one answers
        ``None`` here already.
        """
        del client
        try:
            store = await self.store()
            row = await store.load_auth_code(authorization_code)
            if row is None:
                return None
            authorization = await store.load_authorization(row.auth_id)
        except Exception as exc:
            # Fail closed (D-37): a store that cannot answer is not a code that exists.
            logger.error("an authorization code could not be read: %s", type(exc).__name__)
            return None

        if authorization is None or authorization.revoked_at is not None:
            return None

        return AuthorizationCode(
            code=authorization_code,
            scopes=authorization.scopes.split(),
            expires_at=float(row.expires_at),
            client_id=authorization.client_id,
            code_challenge=row.code_challenge,
            redirect_uri=AnyUrl(row.redirect_uri),
            redirect_uri_provided_explicitly=row.redirect_uri_explicit,
            resource=row.resource,
            subject=authorization.nc_user,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        """Turn one consent into one opaque access token and one refresh token.

        The order of this method is the order of its risks. The audience is checked first
        and fails closed on a missing value, because a token without one would be accepted
        by every other MCP server the user connects (RFC 8707, pitfall 3, T-03-51). The
        client policy is asked second, because a block that arrived while the user was on
        the consent screen must not be outrun by a code that was already issued (pitfall 9,
        T-03-55). Only then is the code spent, in the one atomic statement that makes a
        second exchange impossible, and only after that do the tokens exist.

        **What ``offline_access`` does here, and what it does not.** A refresh token is
        issued for every code this method spends, whether or not the authorization named
        the refresh scope. That is deliberate and it is the reliable reading: Claude does
        not ask for the scope and refreshes anyway, ChatGPT asks for it, and a connector
        that silently lost its refresh token would look like a connection that expires
        after an hour for no reason. The scope is recorded and echoed back because a client
        compares the granted scope against the one it asked for; it is never a second data
        scope, and what this access token reaches is the curated tool surface either way
        (D-42).

        Nothing here talks to Nextcloud. The whole Nextcloud round trip of this phase
        happens in the browser path, where a person is waiting and a second costs nothing;
        a connector gives its token endpoint about ten seconds (pitfall 13, T-03-58). And
        nothing here talks to a document host either (WR-03): the policy check below reads
        the stored row and never refetches, or the sentence above would hold against
        Nextcloud and break against whichever host a client id names.
        """
        resource = (authorization_code.resource or "").strip()
        if not resource:
            raise TokenError("invalid_target", _NO_AUDIENCE)
        if not check_resource_allowed(resource, self._resource):
            raise TokenError("invalid_target", _WRONG_AUDIENCE)

        if await self.get_client(client.client_id, may_fetch=False) is None:
            raise TokenError("invalid_client", _CLIENT_GONE)

        store = await self.store()
        moment = self._now()
        spent = await store.redeem_auth_code(authorization_code.code, now=moment)
        if spent is None:
            # Used, expired or never issued. One answer for all three, which is also the
            # answer a client expects for a grant it may not use again (RFC 6749 §5.2).
            raise TokenError("invalid_grant", _CODE_SPENT)

        refresh = secrets.token_urlsafe(TOKEN_BYTES)
        family = secrets.token_urlsafe(FAMILY_BYTES)
        scopes = " ".join(authorization_code.scopes)
        await store.create_refresh_token(
            refresh, auth_id=spent.auth_id, family_id=family, now=moment
        )
        # A registration that produced a token is a connection somebody made, and it lives
        # on the long expiry window from here on (AUTH-07, T-03-44).
        await store.touch_client(client.client_id, now=moment)

        return await self._issue(
            store,
            auth_id=spent.auth_id,
            family_id=family,
            refresh=refresh,
            scopes=scopes,
            resource=resource,
            now=moment,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        """Read a refresh token back, including one that has already been redeemed.

        That inclusion is the whole reason this method is not a one line lookup. The SDK
        answers ``invalid_grant`` and never calls the exchange when this returns ``None``,
        so a redeemed token that were refused here would never reach the two decisions that
        belong to it: the repeat answer inside the grace window and the family kill outside
        it (D-41). What is refused here is what has no decision left: a token this server
        never issued, one whose family was killed, and one whose connection was ended.

        ``client`` is not compared: the SDK does that itself against ``client_id`` of the
        returned model, and the value here comes from the authorization rather than from the
        request, so a stolen token cannot name a different owner than the one it was issued
        to.
        """
        del client
        try:
            store = await self.store()
            row = await store.load_refresh_token(refresh_token)
            if row is None:
                return None
            authorization = await store.load_authorization(row.auth_id)
        except Exception as exc:
            # Fail closed (D-37): a store that cannot answer is not a token that exists.
            logger.error("a refresh token could not be read: %s", type(exc).__name__)
            return None

        if row.state == STATE_REVOKED:
            return None
        if authorization is None or authorization.revoked_at is not None:
            return None

        return RefreshToken(
            token=refresh_token,
            client_id=authorization.client_id,
            scopes=authorization.scopes.split(),
            expires_at=row.expires_at,
            subject=authorization.nc_user,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Rotate one refresh token, and decide what a second use of it was.

        The order is the order of the risks, the same as in the code exchange. The client
        policy first, because a block that arrived while a connection was running must not
        be outrun by a token that was issued before it (pitfall 9, T-03-55). The audience
        second, because a token without one would be accepted by every other MCP server the
        user connects (RFC 8707). Only then the redemption, which is one ``UPDATE`` under
        ``BEGIN IMMEDIATE`` in the store and therefore the only place two simultaneous
        requests can be told apart (pitfall 10).

        The three outcomes of that statement are the three cases of this method:

        * redeemed: a new pair of the same family, and the answer is held for the window,
        * already used: the retry window of D-41 decides, see below,
        * unknown or expired: ``invalid_grant``, and no family is touched, because neither
          of those is evidence of anything.

        **Why the grace window is not a weakening of the reuse detection (D-41).** Claude
        refreshes reactively on a 401 *and* proactively up to five minutes before an expiry,
        so a second request with the same token is the normal case and not the exception
        (03-RESEARCH.md, pitfall 10). Without the window a single retransmitted request
        would end a healthy connection, which is the reliability half of the owner
        directive. Inside the window an attacker gains nothing: they receive the very
        answer the legitimate client already has, no second branch of the family is created,
        and the window is ten seconds long and belongs to one token. **Outside the window
        the detection is not negotiable**: a token that was redeemed and is presented again
        is either a copy or a replay, and both cost the whole family, because the one thing
        worse than a lost session is a stolen one that keeps working.

        Nothing here talks to Nextcloud, on any of the three paths. A connector gives its
        token endpoint about ten seconds and its refresh about thirty (pitfall 13, T-03-58),
        and a family kill under load must not depend on a PHP round trip. The same sentence
        holds against a document host (WR-03): the policy check below reads the stored row
        and never refetches, so a rotation at the freshness deadline cannot fail over a
        stranger's outage minute.
        """
        if await self.get_client(client.client_id, may_fetch=False) is None:
            raise TokenError("invalid_client", _CLIENT_GONE)

        store = await self.store()
        moment = self._now()
        presented = refresh_token.token
        digest = token_hash(presented)

        row = await store.load_refresh_token(presented)
        if row is None:
            raise TokenError("invalid_grant", _GRANT_GONE)
        authorization = await store.load_authorization(row.auth_id)
        if authorization is None or authorization.revoked_at is not None:
            raise TokenError("invalid_grant", _GRANT_GONE)

        resource = (authorization.resource or "").strip()
        if not resource:
            raise TokenError("invalid_target", _NO_AUDIENCE)
        if not check_resource_allowed(resource, self._resource):
            raise TokenError("invalid_target", _WRONG_AUDIENCE)

        successor = secrets.token_urlsafe(TOKEN_BYTES)
        redeemed = await store.redeem_refresh_token(presented, successor=successor, now=moment)

        if redeemed.outcome == REDEEM_OK:
            granted = " ".join(scopes) if scopes else authorization.scopes
            await store.touch_client(client.client_id, now=moment)
            answer = await self._issue(
                store,
                auth_id=redeemed.auth_id,
                family_id=redeemed.family_id,
                refresh=successor,
                scopes=granted,
                resource=resource,
                now=moment,
            )
            self._hold(digest, answer, moment)
            return answer

        if redeemed.outcome == REDEEM_REUSED and _inside_grace(redeemed.used_at, moment):
            held = self._held_answer(digest, moment)
            if held is not None:
                return held
            # The window is open but this process has no answer for it any more. That is a
            # lost repeat, not a replay, so the family lives and the client reconnects.
            raise TokenError("invalid_grant", _GRANT_GONE)

        if redeemed.outcome == REDEEM_REUSED:
            logger.warning(
                "a refresh token was presented again outside the grace window; "
                "the token family of that connection is revoked"
            )
            await self._end_connection(
                store, auth_id=redeemed.auth_id, family_ids=[redeemed.family_id], now=moment
            )

        raise TokenError("invalid_grant", _GRANT_GONE)

    async def _issue(
        self,
        store: OAuthStore,
        *,
        auth_id: str,
        family_id: str,
        refresh: str,
        scopes: str,
        resource: str,
        now: int,
    ) -> OAuthToken:
        """One opaque access token, in the one shape both grants answer with."""
        access = secrets.token_urlsafe(TOKEN_BYTES)
        await store.create_access_token(
            access, auth_id=auth_id, family_id=family_id, scopes=scopes, resource=resource, now=now
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",  # noqa: S106 - the token type of RFC 6750, not a secret
            expires_in=ACCESS_TOKEN_TTL,
            scope=scopes,
            refresh_token=refresh,
        )

    async def end_connection(self, nc_user: str, auth_id: str) -> bool:
        """End one connection of one account, the way the user's own page asks for it.

        The public form of :meth:`_end_connection`, and the only one the connections page
        of EXAPP-02 uses: a second revocation path would be a second place to forget the
        verifier cache in, and a revoked token would then keep working for the five seconds
        of that window (T-03-62, T-04-35). What the page adds to the protocol paths is the
        handle instead of a token, so the families of the connection are looked up here.

        The account is a parameter and not an assumption (LO-01). The page compares it too,
        before it ever gets here, and that is exactly the point: a method that ends somebody
        else's access may not rely on its one caller for the only ownership check in the
        chain. The next caller, an administrative view or a command of a later phase, would
        hand in a handle it read somewhere. ``is_user`` refuses the empty identity, so the
        app context owns nothing here.

        ``False`` for a handle that does not exist, for one that was already revoked and for
        one of another account, and nothing is written in any of the three: the page answers
        all of them with the same sentence as a resubmitted form, which is what keeps it
        from being an existence oracle.

        The Nextcloud app password of the connection goes back, exactly as on ``/revoke``
        (BL-01). It cannot be left to a sweep: ``abandoned_authorizations`` filters
        ``revoked_at IS NULL``, so a row this method just revoked is invisible to
        :meth:`sweep_abandoned` by construction, and the only other path is
        :meth:`sweep_expired_clients`, which waits for a registration to be unused for
        ``IDLE_CLIENT_TTL`` and therefore never runs for a client somebody keeps using. The
        credential behind a connection is a full Nextcloud credential and not an MCP token,
        so a "Disconnect" that left it valid would be strictly weaker than the machine path
        (WR-04, D-34).

        The attempt is best effort and the last thing that happens, the order of
        :meth:`_revoke`: the connection is revoked in the store before Nextcloud is asked,
        so a deployment whose Nextcloud is unreachable ends the connection anyway and keeps
        the note that its credential is still out there (pitfall 13, D-37).
        """
        store = await self.store()
        row = await store.load_authorization(auth_id)
        if row is None or row.revoked_at is not None or not is_user(nc_user, row.nc_user):
            return False
        families = await store.families_of_authorization(auth_id)
        await self._end_connection(store, auth_id=auth_id, family_ids=families, now=self._now())
        await self._hand_back(store, auth_id)
        return True

    async def _end_connection(
        self, store: OAuthStore, *, auth_id: str, family_ids: Sequence[str], now: int
    ) -> None:
        """End one connection in the store, and make it visible in this process at once.

        Three writes and one call, in this order and never another: the families first,
        because that is what a presented token is checked against; the authorization
        second, so every token ever issued under it dies with it and the app password
        behind it is marked as something somebody still has to hand back; the held answers
        and the verifier cache last, because both are the five to ten seconds in which a
        revoked token would still work (T-03-62).

        A token path knows the one family it just refused and hands in exactly that one; a
        disconnect on the connections page hands in every family of the connection, because
        a connection that a user ended must not keep a second family alive.

        No Nextcloud call. This runs on the token path as well, where a round trip is the
        sporadic timeout nobody can reproduce afterwards (pitfall 13).
        """
        for family_id in family_ids:
            await store.revoke_family(family_id, now=now)
        await store.revoke_authorization(auth_id, now=now)
        await store.note_cleanup(auth_id, now=now)
        self._held.clear()
        self._invalidate()

    def _hold(self, digest: str, answer: OAuthToken, now: float) -> None:
        """Keep one answer for the grace window, inside the ceiling."""
        if len(self._held) >= HELD_ANSWER_LIMIT:
            self._held.clear()
        self._held[digest] = _Held(digest=digest, answer=answer, expires_at=now + ROTATION_GRACE)

    def _held_answer(self, digest: str, now: float) -> OAuthToken | None:
        """The answer this token already received, or ``None``. Never a stale one.

        ``compare_digest`` and not ``==`` on the way out, the rule of the verifier cache:
        the dictionary is keyed by the digest of a token and the entry repeats the digest
        it was stored for, so nothing about a lookup can be learned from its duration.
        """
        entry = self._held.get(digest)
        if entry is None:
            return None
        if entry.expires_at <= now:
            del self._held[digest]
            return None
        if not secrets.compare_digest(entry.digest, digest):  # pragma: no cover - key equality
            return None
        return entry.answer

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Refused on purpose: the bearer of a request is checked by ``oauth/verifier.py``.

        This method exists because the protocol has it, and it answers ``None`` because the
        only caller it would ever have is the SDK's ``ProviderTokenVerifier``, which this
        application does not install. That verifier knows neither the process cache nor the
        audience check nor the client policy, so a token accepted through here would be one
        accepted by a weaker path than the one at the transport boundary (T-03-51).
        """
        del token
        return None

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """End the whole connection behind this value, and take the credential back (SC 4).

        The protocol asks for a token to be revoked; a user asks for a connection to end,
        and this method answers the user. One access token, one refresh token and the
        family they belong to are one connection here, so whichever of them arrives, all of
        them stop working and the Nextcloud app password behind them goes back.

        Doing nothing for a value this server does not know is the correct answer, not a
        missing branch: RFC 7009 §2.2 requires 200 for an unknown token, and an answer that
        distinguished the two would turn this endpoint into an oracle.
        """
        await self._revoke(presented=token.token, client_id=None)

    async def revoke_presented_token(self, client_id: str, presented: str) -> None:
        """The same revocation, for a value that arrived at ``/revoke`` from a client.

        The difference to :meth:`revoke_token` is the ownership check, which the SDK
        handler does on its own model and which this application has to do on the store:
        a client may only end connections that were issued to it, or ``/revoke`` would be a
        way to disconnect somebody else's assistant with a guessed value.
        """
        await self._revoke(presented=presented, client_id=client_id)

    async def _revoke(self, *, presented: str, client_id: str | None) -> None:
        """The three steps of a revocation, in the order the user expects them in.

        1. the store: the family and the authorization are marked as gone,
        2. this process: the held answers and the verifier cache are emptied,
        3. Nextcloud: the app password of the connection is handed back.

        Step three is last and may fail. "Revoked" has to mean "revoked" the moment the
        request returns, and Nextcloud is the slowest participant of this whole phase and
        the only one that can be unreachable; a revocation that waited for it, or that gave
        up because of it, would keep a connection alive that its owner just ended (pitfall
        13, D-37). A failed deletion therefore leaves the connection revoked and a note in
        the store that the credential is still out there (T-03-63).
        """
        try:
            store = await self.store()
            found = await self._connection_of(store, presented)
        except Exception as exc:
            # Nothing to answer with and nothing to leak: the endpoint answers 200 either
            # way, and the kind of the failure is the only thing that reaches the log.
            logger.error("a revocation could not read its store: %s", type(exc).__name__)
            return

        if found is None:
            return
        auth_id, family_id, owner = found
        if client_id is not None and not secrets.compare_digest(owner, client_id):
            logger.warning("a client presented a token of another client for revocation")
            return

        await self._end_connection(store, auth_id=auth_id, family_ids=[family_id], now=self._now())
        await self._hand_back(store, auth_id)

    async def _connection_of(
        self, store: OAuthStore, presented: str
    ) -> tuple[str, str, str] | None:
        """The connection behind a presented value: its id, its family and its client.

        Both kinds are looked up, because RFC 7009 lets a client hand in either and several
        of them hand in the access token. The refresh token is asked first, since that is
        the value the specification recommends and therefore the common case.
        """
        if not presented:
            return None

        refresh = await store.load_refresh_token(presented)
        if refresh is not None:
            authorization = await store.load_authorization(refresh.auth_id)
            if authorization is not None:
                return refresh.auth_id, refresh.family_id, authorization.client_id

        access = await store.load_access_token(presented)
        if access is not None:
            authorization = await store.load_authorization(access.auth_id)
            if authorization is not None:
                return access.auth_id, access.family_id, authorization.client_id

        return None

    async def _hand_back(self, store: OAuthStore, auth_id: str) -> bool:
        """Delete the Nextcloud app password of this connection. One attempt, no retry.

        The note that the credential is an orphan was already written by
        :meth:`_end_connection`, so the order here is "note first, attempt second, clear on
        success". A process that dies in the middle of the attempt therefore leaves the
        note behind, which is the state the sweep of :meth:`sweep_abandoned` and the admin
        view of phase 4 can act on. Anything else, including a store that cannot be read,
        is a failure that the revocation itself does not notice.
        """
        try:
            row = await store.load_authorization(auth_id)
            password = await store.app_password(auth_id)
        except Exception:
            logger.error("the app password of a revoked connection could not be read back")
            return False

        if row is None or not password:
            return False
        if not await loginflow.revoke_app_password(row.nc_user, password, target=self._nextcloud):
            # loginflow logged what happened, without any value of the exchange.
            return False

        await store.clear_cleanup(auth_id)
        return True

    async def sweep_abandoned(self) -> int:
        """Hand back the credentials of the sign ins nobody ever came back to.

        The consent bridge has to write an authorization the moment the Login Flow v2 poll
        answers, because that answer arrives exactly once and a Nextcloud app password
        exists from then on (plan 03-05, pitfall 7). A user who closes the browser at that
        moment leaves a working credential behind, and this project has no cron to find it
        (T-03-17). So the sweep hangs where a new connection begins: whoever connects pays
        for at most :data:`SWEEP_LIMIT` of the ones that were never finished, which bounds
        the cost of one request by construction and needs no scheduler.

        The row goes even when the deletion fails, for the same reason a denied consent
        deletes it (plan 03-06): the connection never existed as far as its user is
        concerned, and keeping a ciphertext of a credential nobody may use is worse than
        losing the record of it. A failure is logged and counted as not swept.
        """
        try:
            store = await self.store()
            rows = await store.abandoned_authorizations(SWEEP_LIMIT, now=self._now())
        except Exception as exc:
            logger.error("the sweep of abandoned sign ins found no store: %s", type(exc).__name__)
            return 0

        swept = 0
        for row in rows:
            try:
                password = await store.app_password(row.auth_id)
            except Exception:
                logger.error("the app password of an abandoned sign in could not be read back")
                password = None
            if password and await loginflow.revoke_app_password(
                row.nc_user, password, target=self._nextcloud
            ):
                swept += 1
            else:
                logger.warning("an abandoned sign in was dropped without handing its password back")
            await store.delete_authorization(row.auth_id)
        return swept

    async def sweep_expired_clients(self) -> int:
        """Hand back the credentials of the registrations that ran out, then remove them.

        The counterpart of :meth:`sweep_abandoned`, and it exists for the same rule stated
        the other way round (WR-04, D-34): a connection that ends gives its Nextcloud app
        password back. ``purge_expired`` used to remove client rows on its own, and
        ``authorizations`` cascades on that delete, so the credential of a user who signed
        in and approved while their client never exchanged the code was deleted out of the
        store after a day and kept working at Nextcloud forever, unfindable for any later
        sweep because the ciphertext was gone with the row.

        The store leaves such a client alone now and this hands its credentials back first.
        Bounded like the other sweep: whoever connects pays for at most
        :data:`SWEEP_LIMIT` of them, which is what keeps this off the critical path of one
        request.
        """
        try:
            store = await self.store()
            expired = await store.expired_clients(SWEEP_LIMIT, now=self._now())
        except Exception as exc:
            logger.error("the sweep of expired clients found no store: %s", type(exc).__name__)
            return 0

        swept = 0
        for client_id in expired:
            await self._hand_back_client(store, client_id)
            await store.delete_client(client_id)
            swept += 1
        return swept

    async def _hand_back_client(self, store: OAuthStore, client_id: str) -> None:
        """Revoke and remove the connections of one client, before its row is deleted.

        The row goes even when the revocation fails, which is the rule of every other
        cleanup path of this phase: keeping the ciphertext of a credential nobody may use
        is worse than losing the record of it, and the failure is logged and counted
        nowhere else (D-34, plan 03-06). What must not happen is the silent case, and that
        is exactly what the cascade used to do.

        **Every connection of the client, and not a page of them (BL-01).** The read used to
        stop at :data:`SWEEP_LIMIT` although the ``delete_client`` of the caller cascades over
        all of them, so from the fourth connection of one registration on the ciphertext was
        deleted without ever being handed back, and no later sweep could find it either. The
        cap belongs on how many *clients* one request pays for, which is where
        :meth:`sweep_expired_clients` applies it, and not on how many credentials of one
        registration may survive its deletion. So this reads without a limit, and the price
        is named rather than hidden: a registration with many connections costs one Nextcloud
        request per connection, once, in the request that expires it. Paying that is the
        cheaper of the two, because the alternative is a credential that stays valid at
        Nextcloud with no record left that it exists.
        """
        try:
            rows = await store.authorizations_of_client(client_id)
        except Exception as exc:
            logger.error(
                "the connections of an expired client could not be read: %s", type(exc).__name__
            )
            return

        for row in rows:
            try:
                password = await store.app_password(row.auth_id)
            except Exception:
                logger.error("the app password of an expired client could not be read back")
                password = None
            if not password or not await loginflow.revoke_app_password(
                row.nc_user, password, target=self._nextcloud
            ):
                logger.warning("an expired client was removed without handing its password back")
            await store.delete_authorization(row.auth_id)

    async def exchange_identity_assertion(
        self, client: OAuthClientInformationFull, params: IdentityAssertionParams
    ) -> OAuthToken:
        """Refused permanently, not until a later plan.

        The SEP-990 profile hands an enterprise identity provider the right to assert who
        a user is. This connector has exactly one identity source, Nextcloud itself, and
        adding a second one is a decision for a later version and not a side effect of a
        grant type (D-33).
        """
        del client, params
        raise TokenError("unsupported_grant_type", _NOT_YET)


def auth_routes(
    env: Mapping[str, str] | None = None,
    *,
    provider: NextcloudOAuthProvider,
    throttle: Throttle | None = None,
) -> list[Route]:
    """The routes of the authorization server, with ``no-store`` over all of them.

    Two of the routes the SDK builds are dropped here, and both because this app already
    serves the same path with more than the SDK can know. ``oauth/metadata.py`` publishes
    the authorization server document with the fields the SDK does not set and the issuer
    spelled exactly as it was configured (03-01), and ``oauth/consent.py`` serves
    ``/authorize`` in front of the SDK handler, so that a refused request ends on a page a
    person can read instead of in JSON a browser displays raw. Two routes on one path would
    answer whichever was registered first, which is not a property to leave to registration
    order.

    The issuer is the configured public URL. The SDK requires https for it, with the
    loopback exception that makes the local test topology work; a value that fails that
    rule is a deployment error and is named as one instead of surfacing as a traceback.
    """
    try:
        issuer = AnyHttpUrl(config.public_url(env))
        routes = create_auth_routes(
            provider=provider,
            issuer_url=issuer,
            client_registration_options=ClientRegistrationOptions(
                enabled=provider.policy.dcr_enabled,
                valid_scopes=[TOOL_SCOPE, REFRESH_SCOPE],
                default_scopes=[TOOL_SCOPE],
            ),
            revocation_options=RevocationOptions(enabled=True),
        )
    except ValueError as exc:
        # A type of its own, not a bare ToolError: ``entry_exapp.main`` rescues exactly this
        # failure by dropping the address and building once more, and a second build time
        # failure caught by the same clause would be reported as an address problem it is
        # not (IN-06). The wording stays what it was.
        raise IssuerRefused(
            message=f"{config.ENV_PUBLIC_URL} is not a usable issuer: {exc}", hint=_HINT_ISSUER
        ) from None

    dropped = (AS_METADATA_SUFFIX, AUTHORIZATION_PATH, TOKEN_PATH, REVOCATION_PATH)
    kept = [route for route in routes if route.path not in dropped]
    # The two endpoints that authenticate a client are rebuilt with our own authenticator.
    # For ``/token`` everything else about it stays the SDK's: the same handler, the same
    # CORS wrapper and the same methods, because only the comparison of the secret is ours.
    # ``/revoke`` needs more than that, see :class:`FamilyRevocation`.
    authenticator = HashedClientAuthenticator(provider)
    kept.append(
        Route(
            TOKEN_PATH,
            endpoint=cors_middleware(TokenHandler(provider, authenticator).handle, _MACHINE_VERBS),
            methods=_MACHINE_VERBS,
        )
    )
    kept.append(
        Route(
            REVOCATION_PATH,
            endpoint=cors_middleware(
                FamilyRevocation(provider, authenticator).handle, _MACHINE_VERBS
            ),
            methods=_MACHINE_VERBS,
        )
    )
    classes = {
        TOKEN_PATH: CLASS_TOKEN,
        REGISTRATION_PATH: CLASS_REGISTER,
        REVOCATION_PATH: CLASS_REVOKE,
    }
    counters = throttle if throttle is not None else Throttle()
    for route in kept:
        # The order of the two wrappers is the order of what they answer: a throttled
        # request never reaches the handler, and every answer of this server, the 429
        # included, carries ``no-store``.
        route.app = Throttled(
            route.app, counters, classes.get(route.path, CLASS_TOKEN), machine=True, env=env
        )
        route.app = NoStore(route.app)
    return kept


class _RevocationRequest(BaseModel):
    """The body of RFC 7009 §2.1, with the one field the SDK model gets wrong.

    ``client_secret`` is declared as ``str | None`` without a default in the SDK, which
    makes it a *required* field that may be null: a public client, which Claude.ai and
    ChatGPT both are, sends no such field at all and would get a 400 from its own
    revocation. Optional is what the RFC says and what this model does.

    ``token_type_hint`` is absent on purpose rather than ignored: this server looks both
    kinds up either way, so the hint would be a field nothing reads. Unknown fields are
    dropped by pydantic, so a client that sends it is not refused for it.
    """

    token: str
    client_id: str
    client_secret: str | None = None


class FamilyRevocation:
    """``/revoke``, rebuilt because the SDK handler cannot see the tokens of this server.

    The SDK resolves the presented value through ``load_access_token`` and then through
    ``load_refresh_token``. The first of those refuses by design here (see the module
    docstring: the bearer of a request is checked by ``oauth/verifier.py`` and by nothing
    else), so a client that hands in its access token, which RFC 7009 explicitly allows,
    would receive a 200 and keep a working connection. That is the one shape of silent
    failure this endpoint may not have (SC 4).

    Everything else is the SDK's shape, deliberately: the same request model, the same
    client authentication, 401 for a client that cannot authenticate, 400 for a body that
    is not a revocation request, and 200 for everything else, including a value this server
    never issued and one that belongs to another client.
    """

    def __init__(
        self, provider: "NextcloudOAuthProvider", authenticator: ClientAuthenticator
    ) -> None:
        self._provider = provider
        self._authenticator = authenticator

    async def handle(self, request: Request) -> Response:
        try:
            client = await self._authenticator.authenticate_request(request)
        except AuthenticationError as exc:
            return json_response(
                {"error": "unauthorized_client", "error_description": exc.message}, status_code=401
            )

        form = await form_or_none(request)
        if form is None:
            # A body no parser can read is not a revocation request either, so it gets the
            # answer of one, and not the traceback the framework used to write (HI-02).
            return json_response(
                {"error": "invalid_request", "error_description": "this is not a revocation"},
                status_code=400,
            )

        try:
            revocation = _RevocationRequest.model_validate(dict(form))
        except ValidationError:
            # The offending body carries a credential, so the shape of the error is named
            # and its content is not (T-03-66).
            return json_response(
                {"error": "invalid_request", "error_description": "this is not a revocation"},
                status_code=400,
            )

        await self._provider.revoke_presented_token(client.client_id, revocation.token)
        return Response(status_code=200, headers=dict(NO_STORE))


class HashedClientAuthenticator(ClientAuthenticator):
    """Authenticate a client at ``/token`` and ``/revoke`` against the stored digest.

    The SDK compares ``client.client_secret`` with the presented secret in plaintext, which
    means the store would have to keep one. It does not: plan 03-02 stores a SHA-256 digest
    for the same reason every other credential of this phase is stored as one, so that a
    stolen store file cannot be replayed against this server (T-03-11). This class is the
    other half of that decision, and without it the token endpoint would refuse every
    confidential client.

    What it does not change: which clients exist and which of them may act. Both come from
    ``get_client``, which is the one enforcement point of AUTH-07 (pitfall 9). A public
    client, which is what Claude.ai and ChatGPT are, has no secret at all and is
    authenticated by PKCE alone, exactly as the SDK does it.
    """

    def __init__(self, provider: "NextcloudOAuthProvider") -> None:
        super().__init__(provider)
        self._provider = provider

    async def authenticate_request(self, request: Request) -> OAuthClientInformationFull:
        form = await form_or_none(request)
        if form is None:
            # A body that cannot be parsed authenticates nobody, and it may carry a client
            # secret, so it becomes a refused authentication and never a traceback (HI-02,
            # T-03-66).
            raise AuthenticationError("The client could not be authenticated")
        client_id = str(form.get("client_id") or "")
        if not client_id:
            raise AuthenticationError("Missing client_id")

        # ``may_fetch=False`` (WR-01): this runs on ``/token`` and ``/revoke``, where an
        # outbound request against a host the client named would put a stranger's outage
        # into the ten seconds a connector gives its token endpoint. The stored row is the
        # identity here; the refetch belongs to ``/authorize``.
        client = await self._provider.get_client(client_id, may_fetch=False)
        if client is None:
            raise AuthenticationError("Invalid client_id")

        try:
            stored = await self._provider.client_secret_hash(client_id)
        except Exception as exc:
            # A store that cannot be read is a refused authentication, never an accepted
            # one (D-37). The kind of the failure is logged, no value of the request is.
            logger.error("a client could not be authenticated: %s", type(exc).__name__)
            raise AuthenticationError("The client could not be authenticated") from None
        if stored is None:
            if client.token_endpoint_auth_method != PUBLIC_CLIENT_AUTH_METHOD:
                # A registration that asked for a secret and has none stored is not a
                # public client, it is a row nothing can be verified against, and the SDK
                # authenticator refuses exactly this case. Reading it as "no secret, so no
                # check" would authenticate such a client with no credential at all
                # (WR-01, fail closed D-37).
                logger.error("a client registered for a secret has none stored and is refused")
                raise AuthenticationError("The client could not be authenticated")
            # A public client. The SDK treats a registration without a secret the same way,
            # and PKCE is what authenticates the exchange (OAuth 2.1, S256 enforced).
            return client

        presented = _presented_secret(request, form, client_id, client)
        if not presented:
            raise AuthenticationError("Client secret is required")
        # The comparison runs on the digests and in constant time, for the same reason the
        # AppAPI handshake compares that way: the value comes from a request, and a
        # comparison that stops early leaks its prefix over enough attempts (T-01-24).
        if not secrets.compare_digest(token_hash(presented), stored):
            raise AuthenticationError("Invalid client_secret")
        expires_at = client.client_secret_expires_at
        if expires_at and expires_at < self._provider._now():
            # The second guard of the SDK authenticator this override used to drop: a
            # secret that ran out keeps working while nobody compares it against a clock.
            # The default of this deployment is "never", so this is the guard for the
            # installation that sets client_secret_expiry_seconds (WR-01).
            raise AuthenticationError("The client could not be authenticated")
        return client


def _presented_secret(
    request: Request,
    form: FormData,
    client_id: str,
    client: OAuthClientInformationFull,
) -> str:
    """The secret this request carries, in the form the registration asked for.

    The two methods of RFC 6749 §2.3.1 and nothing else. A client that registered for
    ``none`` and then sends a secret is not authenticated by it: the method decides, not
    the request, because anything else would let a caller pick the weaker of two paths.
    """
    if client.token_endpoint_auth_method == _AUTH_BASIC:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            raise AuthenticationError("Missing or invalid Basic authentication")
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
        except (ValueError, binascii.Error, UnicodeDecodeError):
            # The offending value is credential material and stays out of the message.
            raise AuthenticationError("Invalid Basic authentication header") from None
        name, separator, secret = decoded.partition(":")
        if not separator or unquote(name) != client_id:
            raise AuthenticationError("Client ID mismatch in Basic auth")
        return unquote(secret)
    if client.token_endpoint_auth_method == _AUTH_POST:
        value = form.get("client_secret")
        return value if isinstance(value, str) else ""
    return ""


class NoStore:
    """Put ``Cache-Control: no-store`` on every answer of the authorization server.

    Two answers make this necessary and one rule makes it simple. The registration answer
    of the SDK carries no cache header at all, and the AppAPI PHP proxy caches a JSON
    answer without one for 3600 seconds, which would hand a second client the credentials
    of the first (pitfall 4, T-03-45). The metadata handler of the SDK sets ``public,
    max-age=3600``, which would pin a document with a stale public URL for an hour.

    The rule: every answer of an authorization server is either a credential or a decision
    about one, so there is no branch on which a cache header may survive. Overwriting
    unconditionally is therefore both simpler and stricter than merging, and it is what the
    HTML pages of this phase do through their own shell as well.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pragma: no cover - these routes are HTTP only
            await self._app(scope, receive, send)
            return

        async def send_with_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["cache-control"] = "no-store"
            await send(message)

        await self._app(scope, receive, send_with_no_store)


def _client_information(metadata_json: str, client_id: str) -> OAuthClientInformationFull | None:
    """Read a stored registration back, or refuse it. Never raise into a handler.

    A row this code cannot parse is a row from a future or a broken write. Both are
    reasons to refuse the client, never to answer a 500 that tells the caller a client id
    exists (fail closed, D-37, T-03-47).

    The scope of the row is replaced by the scope this server grants today, for the rows
    that were written before it granted both: without that line the fix of the
    ``invalid_scope`` refusal would only reach clients that register again, and an
    administrator would have to delete a connector in ChatGPT to get past a bug that is
    already fixed on their server. It is a normalisation and not a widening: the value is
    the set every registration is recorded with, an unknown scope is still refused, and
    the scope is the only field of a registration this server assigns rather than accepts.
    """
    try:
        client = OAuthClientInformationFull.model_validate_json(metadata_json)
    except (ValidationError, ValueError, json.JSONDecodeError):
        logger.error("the stored registration of a client cannot be read and is refused")
        return None
    client.scope = REGISTERED_SCOPE
    return client


#: What of a foreign metadata document becomes this server's record of a client. Everything
#: else is dropped rather than stored, and ``logo_uri`` above all: reading it would put a URL
#: of a domain nobody checked into the record, from where a later consent page would have to
#: decide again not to fetch it (draft section 6.7, T-06-13). The four here are the ones this
#: server uses: the name the consent screen shows, the addresses it compares a request
#: against, and the two lists the SDK's own handlers check a grant against.
_CIMD_TAKEN = ("client_name", "redirect_uris", "grant_types", "response_types")


def _cimd_client_information(
    document: Mapping[str, object], client_id: str
) -> OAuthClientInformationFull | None:
    """The SDK model of a document, or ``None``. The same model a registration produces.

    A projection and not a parse of the whole document: only the properties of
    :data:`_CIMD_TAKEN` travel into the record, the identifier is the one this server fetched
    rather than the one the document repeats (they are equal, because ``validate_document``
    compared them byte for byte, and taking ours means a later change of that comparison
    cannot make the two drift apart), and the authentication method is written as the truth
    of this path: a client of it is public and holds no secret.

    Never raises. A document that the model refuses is a client this server does not know,
    which is the same answer every other refusal of this path gives.
    """
    metadata = {key: document[key] for key in _CIMD_TAKEN if key in document}
    try:
        return OAuthClientInformationFull.model_validate(
            metadata
            | {
                "client_id": client_id,
                "token_endpoint_auth_method": PUBLIC_CLIENT_AUTH_METHOD,
            }
        )
    except (ValidationError, ValueError) as exc:
        logger.warning("a document could not be read as a client: %s", type(exc).__name__)
        return None


def _cimd_is_fresh(row: ClientRow, now: int) -> bool:
    """Whether the document behind this row may still be reused without reading it again.

    A row without a deadline is never fresh: that is a row of the registration path, which
    has no document, and a row of this path whose deadline is missing is one this code cannot
    judge. Both readings end in a read of the document, which is the safe end.
    """
    return row.cimd_expires_at is not None and row.cimd_expires_at > now


def _inside_grace(used_at: int | None, now: int) -> bool:
    """Whether a second use of an already redeemed token is still a retry (D-41).

    A row without a redemption time is not one, and neither is a redemption that lies in
    the future: a clock that jumped backwards must not open a window instead of closing
    one, because the open state is the one that answers with a token.
    """
    if used_at is None:
        return False
    return 0 <= now - used_at <= ROTATION_GRACE


def _has_expired(registered_at: int, last_used_at: int | None, *, now: int | None = None) -> bool:
    """Whether this registration ran out, by the window that applies to it.

    Two windows, because the two states mean different things: a registration that never
    produced a token is a fingerprint somebody left behind and goes after a day, while one
    that was used is a connection somebody made and goes after a season without a sign of
    life (AUTH-07).
    """
    moment = int(time.time()) if now is None else now
    if last_used_at is None:
        return registered_at < moment - UNUSED_REGISTRATION_TTL
    return last_used_at < moment - IDLE_REGISTRATION_TTL

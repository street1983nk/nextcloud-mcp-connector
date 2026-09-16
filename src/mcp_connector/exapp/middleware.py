"""The transport boundary in front of the MCP route: two identity sources (CR-01, T-03-01).

``deps.resolve_credentials`` verifies the same handshake, and it stays where it is. The
difference is what each of the two protects. The check in the credential layer is a
handler control point: it runs when a tool asks for credentials, so everything the MCP
protocol does before that (``initialize``, ``tools/list``, session allocation) was served
to an unauthenticated caller. Measured, not assumed: without this module the ExApp
application answers 200 to an ``initialize`` that carries no AppAPI header at all.

So this is a second control, not a replacement. The handler check keeps a future tool that
forgets ``resolve_clients`` from reading data, this one keeps an unauthenticated caller
from reaching MCP code in the first place.

Since plan 03-01 the ``/mcp`` route is declared PUBLIC in ``appinfo/info.xml``, because the
401 that starts the OAuth discovery flow has to come from this application and not from
HaRP. HaRP still signs every request with ``AUTHORIZATION-APP-API``, but the user id in it
is empty whenever the caller sent no Nextcloud credential. That gives this boundary two
branches instead of one (03-RESEARCH.md, pattern 4):

* valid handshake with a user id: the AUTH-01 path, unchanged. The ``Authorization`` header
  is not read at all, so an OAuth token can never be mistaken for that user's credential
  and a Nextcloud credential can never stand in for a missing token (D-27, no fallback in
  either direction).
* valid handshake without a user id: our own OAuth path. The bearer goes to the token
  verifier, and anything but a verified token ends the request with a 401 that carries the
  ``WWW-Authenticate`` challenge with the ``resource_metadata`` pointer.
* invalid handshake: 401 with an empty body and no hint, exactly as before (T-02-03).

The verifier is a parameter, and ``entry_exapp`` hands in the one of this deployment
(``oauth/verifier.py``), which checks the token against the store of this app, its audience
and the client policy. ``None`` stays the strictest state this boundary has and is what the
phase 1 modes and the tests of this wrapper use: while no verifier exists, no bearer is
valid, and every anonymous caller gets the discovery 401 (T-03-01).

A verified token is turned into the Nextcloud identity behind it right here, and that
identity is left in the state of this request. It is the one place that can do it: the
credential layer of a tool call is synchronous, and reading an authorization and decrypting
its app password is not (D-26).

Since plan 04-01 a third check follows the two above, and only ever after them: the per
account switch of EXAPP-02. Whoever owns a Nextcloud account can pause the MCP access of
that account, and this is the one place both connection types pass, so it is the one place
that enforces it (D-49). The order is deliberate and is the security of the feature: a
caller who has not proved an identity leaves with the 401 above and never learns whether an
account exists or has paused. The state is read from our own SQLite file per request, not
from Nextcloud and not from a cache, which keeps the measured cost of a tool call at one
Nextcloud roundtrip (D-47) while a flip still takes effect on the very next request (D-48).
The refusal is R1 of ``04-UI-SPEC.md``: 403, a named code, no ``WWW-Authenticate``.

Every rejection carries ``Cache-Control: no-store``, like every other answer of this
package, and none of them repeats the received token in body or header (T-03-06).
"""

import json
import logging
from collections.abc import Awaitable, Callable, Mapping

from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .. import config
from ..audit import AUDIT_STATE_ATTR
from ..errors import ToolError
from ..oauth.metadata import PRM_SUFFIX, TOOL_SCOPE
from ..oauth.verifier import OAUTH_STATE_ATTR, IdentitySource
from .auth import AppApiRejected, require_appapi
from .responses import NO_STORE
from .ui import strings

__all__ = ["RequireAppApi"]

#: How the switch of one Nextcloud account reaches this boundary: one call, one account, one
#: answer. It is handed in like the verifier and for the same reason, so the standalone HTTP
#: mode of phase 1 cannot grow a store it has no volume for (D-23).
type AccessCheck = Callable[[str], Awaitable[bool]]

#: The scheme prefix of a bearer credential, compared case insensitively (RFC 9110 §11.1).
_BEARER_PREFIX = "bearer "

#: The whole body of R1, built once from two constants (04-UI-SPEC.md "Refusal Contract").
#: A machine readable code plus the one sentence a person reads, and nothing from the
#: request: the credential was fine, the decision was the account owner's (T-03-66).
_ACCESS_DISABLED_BODY = json.dumps(
    {"error": "access_disabled", "error_description": strings.ACCESS_DISABLED_DESCRIPTION}
)

logger = logging.getLogger("mcp_connector.exapp.middleware")

#: The challenge of the 401, minus the pointer, which is the only part that depends on the
#: deployment. Built from constants alone so no part of a request can reach a client
#: through it (T-03-06). ``scope`` names the one tool scope and never ``offline_access``,
#: which the MCP specification keeps out of both the challenge and the resource metadata.
_CHALLENGE = (
    'Bearer error="invalid_token", '
    'error_description="Authentication required", '
    f'scope="{TOOL_SCOPE}", '
    'resource_metadata="{metadata_url}"'
)


class RequireAppApi:
    """Verify the AppAPI handshake, then the bearer, then the switch, before any MCP code."""

    def __init__(
        self,
        app: ASGIApp,
        env: Mapping[str, str] | None = None,
        *,
        token_verifier: TokenVerifier | None = None,
        access_check: AccessCheck | None = None,
        audit_recorder: object | None = None,
    ) -> None:
        self._app = app
        self._env = env
        self._token_verifier = token_verifier
        self._access_check = access_check
        #: ``object`` and not the type of the recorder, on purpose: this boundary has no
        #: business knowing what a recorder is, and importing the recording path here would
        #: reach from the transport shell into a layer below it. The reader checks the type
        #: itself, exactly as ``deps._oauth_identity`` does with ``OAuthIdentity``.
        self._audit_recorder = audit_recorder

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Nothing else reaches this route in this deployment, and a lifespan or
            # websocket scope has no headers to verify. Passing it through keeps the
            # wrapper transparent for the startup of the session manager.
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        try:
            user = require_appapi(request, env=self._env)
        except (AppApiRejected, ToolError):
            # No detail and no WWW-Authenticate: the caller behind these headers is a
            # proxy, and every hint would only say which of the checks rejected the
            # request (T-02-03).
            response = Response(status_code=401, headers=NO_STORE)
            await response(scope, receive, send)
            return

        if not user and not await self._bearer_is_valid(request):
            response = Response(status_code=401, headers=self._unauthorized_headers())
            await response(scope, receive, send)
            return

        refusal = await self._switch_refusal(request, user)
        if refusal is not None:
            await refusal(scope, receive, send)
            return

        self._deposit_recorder(request)
        await self._app(scope, receive, send)

    def _deposit_recorder(self, request: Request) -> None:
        """Leave the recorder of this deployment where the recording path reads it.

        The same seam and the same shape as :meth:`_deposit`: one constant for both sides
        (``AUDIT_STATE_ATTR``), one value in the state of one request. Here rather than
        inside :meth:`_deposit`, because that one runs on the OAuth branch alone, while the
        AppAPI path has a Nextcloud user id and belongs in the record just as much.

        It happens for every request that passed all three checks and for no other: a
        rejected request has left long before this line, so nothing about a caller that was
        turned away can reach the log through this path.

        Without a recorder nothing is deposited and nothing is recorded. That is the state
        this ships in (D-14, off by default), and it is also the permanent state of stdio
        and of the standalone HTTP mode, neither of which passes through this boundary.
        """
        if self._audit_recorder is None:
            return
        setattr(request.state, AUDIT_STATE_ATTR, self._audit_recorder)

    async def _switch_refusal(self, request: Request, user: str) -> Response | None:
        """The per account switch (EXAPP-02), third and last check of this boundary.

        Third and not first, and that order is the security of it: an anonymous or wrongly
        authenticated caller has already left with R2 or R3 above and never learns whether
        an account exists, let alone whether it paused its access (04-RESEARCH.md pitfall 2).
        Only a request that proved an identity is asked about that identity.

        The identity is the user id of the handshake on the AUTH-01 path, or the one the
        bearer resolved to on the OAuth path, which :meth:`_deposit` has just left in the
        state of this request. An empty identity is the app context, which has no switch and
        is never asked (pitfall 10).

        The read is local SQLite in this container and is not cached anywhere, which is what
        makes the two promises of the phase hold at once: no second Nextcloud roundtrip per
        MCP request (D-47), and a flip that takes effect on the very next request (D-48).

        A read that raises is answered with 503 and nothing else. Passing the request through
        would make a store outage a way past the switch, and answering R1 would tell the user
        their own decision was something it was not; both are worse than saying "not now"
        (the fail closed rule of D-37).
        """
        if self._access_check is None:
            return None
        identity = getattr(request.state, OAUTH_STATE_ATTR, None)
        nc_user = user or (identity.principal if identity is not None else "")
        if not nc_user:
            return None
        try:
            disabled = await self._access_check(nc_user)
        except Exception:
            # No account name in the log line either: the boundary logs that the switch
            # could not be read, and the store logs what it could not read.
            logger.exception("the access switch of this request could not be read")
            return Response(status_code=503, headers=NO_STORE)
        if not disabled:
            return None
        return Response(
            content=_ACCESS_DISABLED_BODY,
            status_code=403,
            media_type="application/json",
            headers=NO_STORE,
        )

    async def _bearer_is_valid(self, request: Request) -> bool:
        """Whether this request carries a token the configured verifier accepts.

        False whenever anything is missing: no verifier, no header, a different scheme, an
        empty token, a verifier that answered ``None``, or a verified token whose
        connection cannot be resolved any more. The verifier never sees a value that is not
        a bearer credential, and the token is never written anywhere.
        """
        if self._token_verifier is None:
            return False
        header = request.headers.get("authorization") or ""
        if header[: len(_BEARER_PREFIX)].lower() != _BEARER_PREFIX:
            return False
        token = header[len(_BEARER_PREFIX) :].strip()
        if not token:
            return False
        access = await self._token_verifier.verify_token(token)
        if access is None:
            return False
        return await self._deposit(request, access)

    async def _deposit(self, request: Request, access: AccessToken) -> bool:
        """Leave the identity of this token where the credential layer reads it.

        This is the hand over of D-26: ``deps.resolve_credentials`` runs inside a tool call
        and is synchronous, while turning a token into a Nextcloud user and its app
        password is asynchronous work against the store. So it happens once here, and the
        result travels in the state of this one request, which the MCP transport hands to
        the tool as the request of its context.

        A verifier that has no identity half (the SDK protocol is only ``verify_token``)
        deposits nothing and the request continues: it has no connection to hand over, and
        the credential layer refuses on its own. A verifier that has one and cannot resolve
        the identity ends the request, because a token whose authorization is gone is not a
        token this server may act on (fail closed, D-37).
        """
        if not isinstance(self._token_verifier, IdentitySource):
            return True
        identity = await self._token_verifier.resolve_identity(access)
        if identity is None:
            return False
        setattr(request.state, OAUTH_STATE_ATTR, identity)
        return True

    def _unauthorized_headers(self) -> dict[str, str]:
        """The 401 headers of the OAuth branch: no-store plus the discovery pointer.

        The pointer is built from the configured public URL and the one path constant of
        ``oauth.metadata``, so the address in the challenge and the route that answers it
        cannot drift apart, and a forged host cannot aim a client somewhere else (T-03-02).
        """
        metadata_url = f"{config.public_url(self._env)}{PRM_SUFFIX}"
        return {**NO_STORE, "WWW-Authenticate": _CHALLENGE.format(metadata_url=metadata_url)}

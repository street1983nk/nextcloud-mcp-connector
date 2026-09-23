"""Credential resolution per tool call: the one channel the identity may come from.

Why a request header is allowed to carry credentials here, although the SDK docstring
warns "never treat one as an identity assertion": we do not. This server never decides
who the caller is, and it never grants anything based on the header. It forwards the
Basic credentials unchanged to the configured Nextcloud, and Nextcloud authenticates
them. That is the whole difference between a passthrough and a confused deputy
(threat T-01-23), and it is why no tool has a user parameter (threat T-01-12).

Three rules that follow from D-12 and pitfall 8, all of them load bearing:

* no caching of credentials anywhere, they live for the duration of one call
* no auth retry, because Nextcloud counts failures per source IP and a remote MCP
  server is one IP for many users
* no logging of the header, not even on DEBUG, not even truncated (threat T-01-21)

The static bearer mode is the only mode that configures the SDK auth layer, and it
configures ``auth=`` and ``token_verifier=`` together, because the SDK raises
``ValueError`` in the constructor when only one of them is set (pitfall 2).

In the ExApp mode the user id of ``AUTHORIZATION-APP-API`` decides which of two channels
this call belongs to, and it decides alone:

* a user id in the header is the AppAPI impersonation of AUTH-01. An ``Authorization``
  header that arrives with the same request is not looked at in this branch at all: HaRP
  forwards whatever the client sent, so reading it as well would be a second usable auth
  channel next to the one the proxy vouches for.
* an empty user id is the OAuth branch of AUTH-03. The bearer of the request was verified
  by the transport boundary before any MCP code ran, and what this module reads is the
  identity that boundary resolved from it: the Nextcloud user who consented and the app
  password of that one connection.

There is no fallback in either direction (D-27). A missing OAuth identity does not become
an app secret impersonation, and a missing AppAPI user does not make a bearer optional;
each branch either has its own ground or it fails.

The sixth way (CRED-01): in the ExApp mode the identity of a request can come out of an
exchanged token, and then this container speaks in the name of the mapped account with the
same mechanism as on the AUTH-01 path, the AppAPI impersonation header. The difference is
where the name comes from, never what happens afterwards: Nextcloud judges the header and
the permissions on every request, exactly as it does for a signed in user. D-27 continues
to hold in both directions around it: a missing ExApp environment does not turn an
impersonation wish into a Basic sign in, and a missing app password does not turn a
connection into an impersonation.
"""

import base64
import binascii
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_REQUEST

from . import config
from .config import ExAppSettings, load_stdio_credentials
from .exapp.auth import AppApiRejected, appapi_user, verify_appapi_headers
from .nextcloud import NcClients
from .nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials
from .nextcloud.http import shared_client
from .oauth.verifier import CREDENTIAL_IMPERSONATE, OAUTH_STATE_ATTR, OAuthIdentity

__all__ = [
    "Caller",
    "MCPError",
    "StaticBearerVerifier",
    "build_auth",
    "resolve_caller",
    "resolve_clients",
    "resolve_credentials",
]

#: Client id reported for the single deployment identity of the static bearer mode.
STATIC_BEARER_CLIENT_ID = "nc-mcp-static-bearer"

_BASIC_HINT = (
    "Send an Authorization header with Basic credentials: base64 of "
    "'<nextcloud-user>:<app-password>'. Create the app password in Nextcloud under "
    "Settings, Security, Devices and sessions."
)


def resolve_credentials(ctx: Any) -> Credentials:
    """Return the credentials for this call, from the one source this mode allows.

    Raises ``MCPError`` in the HTTP passthrough mode when the request carries no usable
    Basic credentials. That is deliberate and matches the SDK guidance: a smarter model
    could not have avoided a missing Authorization header, so the failure belongs to the
    host, not into the model's context as a correctable tool error.
    """
    headers = getattr(ctx, "headers", None) if ctx is not None else None
    mode = config.select_mode(headers=headers)

    if mode == "exapp":
        # headers is not None in this mode either, for the same reason.
        return _credentials_from_appapi(ctx, headers or {})

    if mode == "oauth":
        # The standalone OAuth deployment: only a verified bearer reaches a tool, and the
        # Nextcloud is the configured one, never a value from the request.
        return _credentials_from_oauth(ctx, config.load_base_url())

    if mode == "http_passthrough":
        # headers is not None in this mode, select_mode guarantees it.
        return _credentials_from_basic(headers or {})

    # stdio and static bearer both take the Nextcloud account from the environment: the
    # bearer authenticates the caller of this server, it does not select a Nextcloud user.
    return load_stdio_credentials()


def resolve_clients(ctx: Any) -> NcClients:
    """Bundle the event loop client with the credentials of this call."""
    return NcClients(client=shared_client(), creds=resolve_credentials(ctx))


@dataclass(frozen=True, slots=True)
class Caller:
    """Who made one tool call, in the five values a record of it may name (D-08, AUDIT-07).

    Five fields and no sixth. There is no Nextcloud password here, and that absence is the
    point: the recording path must not use :func:`resolve_credentials`, whose result carries
    the live app password of the connection (``nextcloud/credentials.py``) and which raises
    ``MCPError`` when a request has no user context. A recorder may do neither. It may not
    hold a credential it could write into a line, and it may not raise, because a log that
    fails must not end the call it was recording (D-13).

    No address and no user agent either, and that is a decision and not an omission (D-08):
    the two together would turn a record of what happened into a record of where somebody
    was.

    The three client values are ``None`` on every path that has no OAuth client, which are
    the AppAPI impersonation, stdio, the static bearer and the passthrough mode. ``None``
    and not the empty string: there is nothing to name, which is a different fact from a
    client that registered without a name.

    ``actor`` is the fifth field, and it is a field of its own because the acting party of a
    delegation is not the client the delegation runs under (AUDIT-07). Over the token
    exchange path the caller is a client of a foreign realm, booked here under one reserved
    client id; without a column for it a reader would have to read ``client_id`` alongside
    to work out which of the two kinds of name ``client_name`` is carrying this time, and a
    record that has to be decoded that way is one nobody checks. ``None`` on every path
    without a delegation, which is every path that exists apart from the exchange one.
    """

    nc_user: str
    client_id: str | None
    auth_id: str | None
    client_name: str | None
    actor: str | None = None


def resolve_caller(ctx: Any) -> Caller | None:
    """Name the caller of this tool call, or answer ``None``. Never raise, never call out.

    Two sources and no third, in this order. The identity the transport boundary resolved
    from a verified bearer once per request, which fills all five fields; otherwise the
    Nextcloud user id of the AppAPI handshake, which is signed with ``APP_SECRET`` and
    parsed locally, and which fills the user alone. Reading is defensive at every step, in
    the shape of :func:`_oauth_identity`: a context without a request, a request without
    state, a state without our value and a handshake that does not verify are one answer,
    and that answer is ``None``. The gap that leaves in the log is what the check command
    of this phase makes visible.

    Deliberately not read: ``ctx.request_context.params["_meta"]``. The client named there
    is declared by the client itself and would be a second, unverified identity next to the
    one D-08 asks for. It stays unread on purpose, so this does not come back one day as an
    improvement.

    No ``await``, no network call and no read of the OAuth store: everything this needs was
    resolved before any MCP code ran, and this function only reads the result.
    """
    identity = _oauth_identity(ctx)
    if identity is not None:
        return Caller(
            # The principal and not the login name: the audit chain of an account is keyed by
            # the value AppAPI callers use as well (oauth/principal.py).
            nc_user=identity.principal,
            client_id=identity.client_id,
            auth_id=identity.auth_id,
            client_name=identity.client_name,
            # The empty string of the identity and "nobody named" are the same fact in a
            # row, so the two are not carried as two.
            actor=identity.actor or None,
        )

    request = _request_of(ctx)
    if request is None:
        return None
    try:
        user = appapi_user(request)
    except Exception:
        # ``appapi_user`` swallows its own two rejections, so anything reaching here is a
        # request object that is not the one this branch expects. It is still not a reason
        # to raise inside a recorder.
        return None
    if not user:
        return None
    return Caller(nc_user=user, client_id=None, auth_id=None, client_name=None, actor=None)


class StaticBearerVerifier:
    """Verify the single configured bearer token of a single-user deployment.

    ``secrets.compare_digest`` instead of ``==``: the comparison runs on attacker
    supplied input, and a short-circuiting comparison leaks the shared prefix over
    enough requests (threat T-01-24). The token is never logged and never echoed.

    The comparison runs on UTF-8 bytes, never on the strings themselves:
    ``compare_digest`` raises ``TypeError`` as soon as either side contains a
    non-ASCII character, and the caller-supplied side is hostile header input. A
    crash here would turn a malformed bearer into a 500 instead of a 401.
    """

    def __init__(self, token: str) -> None:
        self._token = token.encode("utf-8")

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not secrets.compare_digest(token.encode("utf-8"), self._token):
            return None
        return AccessToken(
            token=token,
            client_id=STATIC_BEARER_CLIENT_ID,
            scopes=[],
            subject=STATIC_BEARER_CLIENT_ID,
        )


def build_auth(
    env: Mapping[str, str] | None = None,
) -> tuple[StaticBearerVerifier | None, AuthSettings | None]:
    """Return the SDK auth wiring for the configured mode.

    ``(None, None)`` in the passthrough mode: the SDK bearer layer only understands
    ``Bearer`` and would answer 401 to every Basic request before a tool ever runs
    (pitfall 2). Both values set in the static bearer mode, never one of them.
    """
    token = config.static_bearer(env)
    if token is None:
        return None, None

    base = config.public_url(env)
    settings = AuthSettings(
        issuer_url=base,  # type: ignore[arg-type] - pydantic coerces the string
        resource_server_url=base,  # type: ignore[arg-type]
        required_scopes=[],
    )
    return StaticBearerVerifier(token), settings


def _credentials_from_appapi(ctx: Any, headers: Mapping[str, str]) -> Credentials:
    """Turn the AppAPI headers of this request into the credentials of one Nextcloud user.

    One refusal and two branches. A request that AppAPI did not sign is not ours to serve;
    a signed one with a user id is that user; a signed one without is the OAuth branch,
    where the identity comes from the token the transport boundary already verified.
    Impersonating nobody with ``APP_SECRET`` is not among the outcomes, because it would
    read data no logged in user could reach (T-02-12).

    No message repeats a header value, and none of them offers a hint about which check
    failed: the caller behind these headers is a proxy, not a model.
    """
    settings = config.exapp_settings()
    try:
        user = verify_appapi_headers(headers, settings.app_id, settings.app_secret)
    except AppApiRejected:
        raise MCPError(
            code=INVALID_REQUEST,
            message="This request carries no valid AppAPI authentication.",
        ) from None

    if not user:
        # The settings this branch already read travel along: they are what makes the
        # impersonation way of an exchange identity reachable here and nowhere else.
        return _credentials_from_oauth(ctx, settings.base_url, exapp=settings)

    # The base URL is the one AppAPI deployed us against, never a value from the request.
    return Credentials(
        base_url=settings.base_url,
        user=user,
        secret=settings.app_secret,
        mode="appapi",
        app_id=settings.app_id,
        app_version=settings.app_version,
        aa_version=settings.aa_version,
    )


def _credentials_from_oauth(
    ctx: Any, base_url: str, *, exapp: ExAppSettings | None = None
) -> Credentials:
    """The fifth credential mode: one OAuth token, one authorization, one app password.

    The identity is read and not resolved here. ``exapp/middleware.py`` verified the bearer
    against the token store, loaded the authorization behind it and decrypted its app
    password before any MCP code ran, and left the result in the state of this request.
    This function is synchronous, as every credential resolution of this project is, so
    doing that work here would mean blocking inside a tool call (D-26).

    No third ``MODE_`` value is added for this: towards Nextcloud an app password is Basic
    authentication, exactly like the one a user pastes into a client in the passthrough
    mode. The difference is where it came from, not what it is, and a mode of its own would
    suggest a fifth authentication scheme that does not exist.

    ``exapp`` is only ever handed in by the AppAPI branch above. That is the security half
    of the impersonation way: the standalone OAuth caller passes nothing, so there is no
    app secret an exchange identity could be turned into there, and the branch below is
    unreachable outside the ExApp mode by construction rather than by check.
    """
    identity = _oauth_identity(ctx)
    if identity is None:
        raise _no_user_context()
    if identity.revoked:
        raise MCPError(
            code=INVALID_REQUEST,
            message=(
                "This connection was ended in Nextcloud. Connect the app again to create a new one."
            ),
        )

    if identity.credential == CREDENTIAL_IMPERSONATE:
        # An empty user id in the AppAPI header would be the app context, a read no signed
        # in user could reach, so an impersonation identity without a user is a refusal and
        # never an outgoing call (T-02-12). The refusal is word for word the one a missing
        # identity gets, so the outside cannot tell the two apart (T-23-12, T-23-13).
        if exapp is None or not identity.nc_user:
            raise _no_user_context()
        return Credentials(
            base_url=exapp.base_url,
            user=identity.nc_user,
            secret=exapp.app_secret,
            mode=MODE_APPAPI,
            app_id=exapp.app_id,
            app_version=exapp.app_version,
            aa_version=exapp.aa_version,
        )

    # The base URL is the one this app was deployed against, never a value from the request.
    return Credentials(
        base_url=base_url,
        user=identity.nc_user,
        secret=identity.app_password,
        mode=MODE_BASIC,
    )


def _no_user_context() -> MCPError:
    """The one sentence every request without a usable user context is refused with.

    One sentence in one place, because three refusals share it on purpose: no identity at
    all, an impersonation identity outside the ExApp mode, and an impersonation identity
    without a user. Distinguishable refusals would tell a caller which half of the
    configuration exists (T-23-13).
    """
    return MCPError(
        code=INVALID_REQUEST,
        message=(
            "This request has no user context: it carries neither a signed in Nextcloud "
            "user nor an authorized connection, and without one there is nothing this "
            "server is allowed to read."
        ),
    )


def _oauth_identity(ctx: Any) -> OAuthIdentity | None:
    """The identity the transport boundary left for this request, or ``None``.

    Defensive on the way in and never on the way out: a context without a request, a
    request without state and a state without our value are one answer, and that answer is
    a refusal in the caller. The alternative, guessing an identity from anything else in
    the request, is the confused deputy this whole layer exists against (T-01-12).
    """
    request = _request_of(ctx)
    state = getattr(request, "state", None)
    if state is None:
        return None
    identity = getattr(state, OAUTH_STATE_ATTR, None)
    return identity if isinstance(identity, OAuthIdentity) else None


def _request_of(ctx: Any) -> Any:
    """The HTTP request behind a tool context, or ``None``. The one defensive read.

    Both readers of the request state go through here, so "a context this server cannot
    read" means the same thing to the credential layer and to the recording path.
    """
    try:
        return getattr(ctx.request_context, "request", None)
    except (AttributeError, ValueError):
        return None


def _credentials_from_basic(headers: Mapping[str, str]) -> Credentials:
    """Decode Basic credentials from the request, or fail with an actionable message."""
    raw = headers.get("authorization") or headers.get("Authorization")
    if not raw:
        raise MCPError(
            code=INVALID_REQUEST,
            message=f"This server needs Basic credentials per request. {_BASIC_HINT}",
        )

    scheme, _, payload = raw.partition(" ")
    if scheme.lower() != "basic":
        raise MCPError(
            code=INVALID_REQUEST,
            message=(
                "This server expects Basic credentials, not another authorization scheme. "
                f"{_BASIC_HINT}"
            ),
        )

    try:
        decoded = base64.b64decode(payload.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        # The offending value is never part of the message: it is credential material.
        raise MCPError(
            code=INVALID_REQUEST,
            message=f"The Basic credentials could not be decoded. {_BASIC_HINT}",
        ) from None

    user, separator, secret = decoded.partition(":")
    if not separator or not user or not secret:
        raise MCPError(
            code=INVALID_REQUEST,
            message=f"The Basic credentials are not in the form user:app-password. {_BASIC_HINT}",
        )

    # The base URL stays a deployment decision. A client that could pick the target
    # instance could aim this server, and the credentials, at a host of its choosing.
    return Credentials(base_url=config.load_base_url(), user=user, secret=secret)

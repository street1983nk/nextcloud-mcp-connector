"""The two browser routes of the standalone OIDC identity: start a sign in, finish it.

A standalone deployment has no AppAPI header that names the account behind a browser, so
the consent decision needs another independent source (CR-01). These routes produce it:
the consent screen offers a sign in at the identity provider the operator configured, and a
successful callback leaves a short-lived, server-side proof that this browser signed in as
the account the Nextcloud sign in of this flow produced. The consent decision consumes that
proof through the standalone browser identity source.

The rules this module keeps (design note, "OIDC consent flow"):

* The start is a POST with an anti forgery value of its own purpose. No GET starts anything.
* The start needs a live flow whose authorization already carries a canonical account id,
  so a proof is bound to that authorization and never becomes a generic login.
* The browser only ever holds opaque random handles in ``__Host-`` cookies. The store keeps
  their digests; state, nonce and PKCE verifier never leave the server.
* The callback is a GET with ``response_mode=query`` and at most one of each protocol
  parameter. A known state with a wrong or missing browser binding ends that sign in for
  good (``OAuthStore.redeem_oidc_transaction``).
* Every refusal of the callback is the same page, so a caller cannot learn which check fired.
* Only after the mapped account id equals the authorization's account id is a proof issued,
  under a fresh handle, and the sign in handle is dropped from the browser.
* No state, code, token or handle is logged or rendered.

Both routes are throttled as browser paths. They are attached by the standalone entry point
only; the ExApp keeps its AppAPI identity and never serves them.
"""

import logging
import re
import secrets
from collections.abc import Callable, Mapping
from urllib.parse import urlencode

from starlette.datastructures import QueryParams
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .. import config
from ..exapp.responses import (
    NO_STORE,
    BodyTooLarge,
    BodyUnreadable,
    bounded_body,
    form_or_none,
    with_body,
)
from ..exapp.ui import errors, layout, strings
from ..exapp.ui.consent import CONFIRM_PARAM, CONSENT_PATH, FLOW_PARAM
from . import crypto, oidc
from .principal import same_principal
from .provider import NextcloudOAuthProvider
from .store import OIDC_TTL, OAuthStore
from .throttle import (
    CLASS_OIDC_CALLBACK,
    CLASS_OIDC_START,
    FLOW_LIMIT,
    Throttle,
    Throttled,
    source_of,
)

__all__ = [
    "OIDC_CALLBACK_PATH",
    "OIDC_START_PATH",
    "PROOF_COOKIE",
    "SIGN_IN_COOKIE",
    "browser_cookie",
    "oidc_routes",
]

#: Where the consent screen sends a browser to sign in, and where the provider sends it back.
#: The configured redirect URI of the OIDC client must end in :data:`OIDC_CALLBACK_PATH`.
OIDC_START_PATH = "/oidc/start"
OIDC_CALLBACK_PATH = "/oidc/callback"

#: The two browser cookies. ``__Host-`` forces ``Secure``, ``Path=/`` and no ``Domain``, so
#: no other host and no plain HTTP page can set or read them.
SIGN_IN_COOKIE = "__Host-mcp-oidc-sign-in"
PROOF_COOKIE = "__Host-mcp-oidc-proof"

#: Entropy of every handle and of state and nonce: 32 bytes, 43 URL-safe characters.
HANDLE_BYTES = 32
_HANDLE = re.compile(r"[A-Za-z0-9_-]{43}")

#: The start form carries two short values. Anything larger is refused before it is parsed,
#: because a standalone deployment has no proxy in front that would limit it.
MAX_START_BODY_BYTES = 4096

#: An authorization code longer than this is not one the provider issued.
MAX_CODE_LENGTH = 2048

#: A redirect carries no cache and hands no referrer to the next page: the consent address
#: names the flow, the callback address carries the code.
_REDIRECT_HEADERS = {**NO_STORE, "Referrer-Policy": "no-referrer"}

logger = logging.getLogger("mcp_connector.oauth.oidc_routes")


def oidc_routes(
    env: Mapping[str, str] | None = None,
    *,
    provider: NextcloudOAuthProvider,
    client: oidc.OidcClient,
    throttle: Throttle | None = None,
) -> list[Route]:
    """The start and the callback of the standalone browser identity."""

    async def start(request: Request) -> Response:
        return await _start(request, provider, client, env)

    async def callback(request: Request) -> Response:
        return await _callback(request, provider, client, env)

    counters = throttle if throttle is not None else Throttle()
    start_route = Route(OIDC_START_PATH, start, methods=["POST"])
    callback_route = Route(OIDC_CALLBACK_PATH, callback, methods=["GET"])
    # Every start writes a sign in row and costs a provider round trip later, so every one is
    # counted, with the limit of the other requests that open a sign in.
    start_route.app = Throttled(
        start_route.app,
        counters,
        CLASS_OIDC_START,
        machine=False,
        env=env,
        count_all=True,
        limit=FLOW_LIMIT,
    )
    # Refusals of the callback are counted per source only. The class wide ceiling would let
    # anybody who varies a forwarded address close every sign in for everybody, and a sign in
    # lives no longer than that lock. Requests that cannot do any work (not a GET, no usable
    # state) are answered before the counter, so they cannot fill it either.
    callback_route.app = _cheap_refusals(
        Throttled(
            callback_route.app,
            counters,
            CLASS_OIDC_CALLBACK,
            machine=False,
            env=env,
            identity=_source_key(env),
        ),
        env,
    )
    return [start_route, callback_route]


async def _start(
    request: Request,
    provider: NextcloudOAuthProvider,
    client: oidc.OidcClient,
    env: Mapping[str, str] | None,
) -> Response:
    """Remember one sign in for this flow and hand the browser to the provider."""
    try:
        raw = await bounded_body(request, MAX_START_BODY_BYTES)
    except (BodyTooLarge, BodyUnreadable):
        return _refused(env)
    form = await form_or_none(with_body(request, raw))
    if form is None:
        return _refused(env)
    flow_id = str(form.get(FLOW_PARAM) or "")
    confirm = str(form.get(CONFIRM_PARAM) or "")
    if not flow_id or not confirm:
        return _refused(env)

    store = await _store_or_none(provider)
    if store is None:
        return _generic("the OIDC start has no store", env)
    if not store.form_token_valid(flow_id, confirm, purpose=crypto.PURPOSE_OIDC_START):
        logger.warning("an OIDC start arrived without the anti forgery value of its flow")
        return _refused(env)

    try:
        # Before anything is written: a provider that cannot be reached leaves no row.
        await client.metadata()
    except Exception:
        return _generic("the identity provider could not be prepared", env)

    # A browser that already holds a sign in handle keeps it, so the per browser cap of the
    # store counts its open sign ins. A missing or malformed one is replaced.
    handle = browser_cookie(request, SIGN_IN_COOKIE) or _new_handle()
    state = _new_handle()
    nonce = _new_handle()
    verifier = oidc.new_code_verifier()
    try:
        created = await store.create_oidc_transaction(
            state=state,
            flow_id=flow_id,
            browser_handle=handle,
            nonce=nonce,
            code_verifier=verifier,
        )
    except Exception:
        logger.error("an OIDC sign in could not be written to the store")
        return _generic("an OIDC sign in could not be written", env)
    if not created:
        # The flow is gone or expired, its sign in at Nextcloud has not produced an account
        # yet, or this browser already has too many open sign ins. One answer for all three.
        return _refused(env)

    try:
        target = await client.authorization_url(state=state, nonce=nonce, code_verifier=verifier)
    except Exception:
        return _generic("the identity provider address could not be built", env)
    # A page that navigates, not a redirect: the start is a form submission, and browsers
    # check ``form-action 'self'`` against the target of a redirect that follows one (CR-03).
    response = layout.page(
        strings.IDENTITY_HANDOFF_TITLE,
        [
            layout.paragraph(strings.IDENTITY_HANDOFF_BODY),
            layout.return_action(strings.IDENTITY_HANDOFF_ACTION, target),
        ],
        env=env,
        refresh_to=target,
    )
    _set_cookie(response, SIGN_IN_COOKIE, handle)
    return response


async def _callback(
    request: Request,
    provider: NextcloudOAuthProvider,
    client: oidc.OidcClient,
    env: Mapping[str, str] | None,
) -> Response:
    """Finish one sign in, compare the account, and leave a proof for the consent decision."""
    if request.method != "GET":
        # Starlette answers HEAD on a GET route. A HEAD (a link preview, a prefetch) must not
        # consume a sign in.
        return Response(status_code=405, headers={"Allow": "GET", **NO_STORE})
    params = request.query_params
    state = _usable_state(params)
    if state is None:
        return _refused(env)

    store = await _store_or_none(provider)
    if store is None:
        return _generic("the OIDC callback has no store", env)
    try:
        # Consumed first, whatever follows: from here on this state is spent.
        transaction = await store.redeem_oidc_transaction(
            state=state, browser_handle=browser_cookie(request, SIGN_IN_COOKIE) or ""
        )
    except Exception:
        logger.error("an OIDC sign in could not be read back")
        return _refused(env)
    if transaction is None:
        return _refused(env)

    code = _single(params, "code")
    if "error" in params or code is None or len(code) > MAX_CODE_LENGTH:
        # A cancelled sign in and a malformed answer end the same way.
        return _refused(env)
    if not _issuer_matches(params, client.settings.issuer):
        return _refused(env)

    try:
        claims = await client.exchange(
            code=code, code_verifier=transaction.code_verifier, nonce=transaction.nonce
        )
        account = client.account_id_for(claims)
    except oidc.OidcRefused:
        # The client logged its fixed reason already.
        return _refused(env)
    except Exception:
        logger.error("the OIDC code exchange failed")
        return _refused(env)

    try:
        authorization = await store.load_authorization(transaction.flow_id)
    except Exception:
        logger.error("the authorization of an OIDC sign in could not be read")
        return _refused(env)
    expected = ""
    if authorization is not None and authorization.revoked_at is None:
        # The canonical account id and nothing else: a legacy row without one has no
        # standalone identity (no fallback to the login name).
        expected = authorization.nc_account_id or ""
    if not same_principal(account, expected):
        logger.warning("an OIDC sign in named another account than the Nextcloud sign in")
        return _refused(env)

    proof = _new_handle()
    try:
        issued = await store.create_browser_proof(
            proof_handle=proof, flow_id=transaction.flow_id, principal=account
        )
    except Exception:
        logger.error("a browser proof could not be written to the store")
        return _refused(env)
    if not issued:
        return _refused(env)

    query = urlencode({FLOW_PARAM: transaction.flow_id})
    target = f"{layout.app_path(CONSENT_PATH, env)}?{query}"
    response = RedirectResponse(target, status_code=303, headers=_REDIRECT_HEADERS)
    _set_cookie(response, PROOF_COOKIE, proof)
    response.delete_cookie(SIGN_IN_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response


def _cheap_refusals(app: ASGIApp, env: Mapping[str, str] | None) -> ASGIApp:
    """Answer callbacks that cannot consume anything before they reach the counter."""

    async def guard(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            if request.method != "GET":
                response: Response = Response(status_code=405, headers={"Allow": "GET", **NO_STORE})
                await response(scope, receive, send)
                return
            if _usable_state(request.query_params) is None:
                await _refused(env)(scope, receive, send)
                return
        await app(scope, receive, send)

    return guard


def _source_key(env: Mapping[str, str] | None) -> Callable[[Request], str]:
    """The per source key of the callback counter; never empty, so nothing is unthrottled.

    Whether a forwarded address may be that key is configuration of the deployment
    (:func:`mcp_connector.config.trust_forwarded_for`), read once when the routes are built.
    """
    trusted = config.trust_forwarded_for(env)

    def key(request: Request) -> str:
        return source_of(request, trust_forwarded=trusted) or "unknown"

    return key


def _usable_state(params: QueryParams) -> str | None:
    """The one state value of a callback, if it has the shape this app issues."""
    state = _single(params, "state")
    if state is None or not _HANDLE.fullmatch(state):
        return None
    return state


def _issuer_matches(params: QueryParams, issuer: str) -> bool:
    """RFC 9207: an ``iss`` in the answer, if present, is exactly the configured issuer."""
    values = params.getlist("iss")
    if not values:
        return True
    return len(values) == 1 and secrets.compare_digest(
        values[0].encode("utf-8"), issuer.encode("utf-8")
    )


def _single(params: QueryParams, name: str) -> str | None:
    """The one non-empty value of a parameter, or ``None`` when it is missing or repeated."""
    values = params.getlist(name)
    if len(values) != 1 or not values[0]:
        return None
    return values[0]


def browser_cookie(request: Request, name: str) -> str | None:
    """The one well-formed value of a cookie, or ``None``.

    Read from the raw headers, because the parsed mapping silently keeps one of several
    values of the same name, and an ambiguous cookie must not bind anything.
    """
    values: list[str] = []
    for header, raw in request.scope.get("headers", []):
        if header != b"cookie":
            continue
        for part in raw.decode("latin-1").split(";"):
            key, separator, value = part.strip().partition("=")
            if separator and key == name:
                values.append(value.strip())
    if len(values) != 1 or not _HANDLE.fullmatch(values[0]):
        return None
    return values[0]


def _set_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=OIDC_TTL,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _new_handle() -> str:
    return secrets.token_urlsafe(HANDLE_BYTES)


async def _store_or_none(provider: NextcloudOAuthProvider) -> OAuthStore | None:
    try:
        return await provider.store()
    except Exception:
        logger.error("the OIDC routes could not open the store")
        return None


def _refused(env: Mapping[str, str] | None) -> Response:
    """The one answer to every refusal: the page an expired link gets."""
    response, _ = errors.error_page("E3", env=env)
    return response


def _generic(what: str, env: Mapping[str, str] | None) -> Response:
    """The generic page plus the one log line that carries its reference."""
    response, reference = errors.error_page("E7", env=env)
    logger.error("%s (reference %s)", what, reference)
    return response

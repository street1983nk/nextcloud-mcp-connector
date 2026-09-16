"""``/authorize`` and the consent screen behind it: the bridge into the Nextcloud sign in.

**Why this route exists at all.** The SDK serves ``/authorize`` on its own and answers a
refused request with JSON, which is the right answer for a machine and the wrong one for
the person standing in front of the browser this endpoint redirects. A blocked client, a
return address that does not match the registration and a registration that expired all
end here as a page that names what happened and what to do next (03-UI-SPEC.md, E1 to E5),
and everything the SDK does check stays where it is: this handler decides who gets in and
then hands the request to :class:`AuthorizationHandler` unchanged, so PKCE, the response
type, the exact redirect matching and the RFC error shapes are still the SDK's.

**Why a page and never a redirect for a bad return address.** A redirect to an address the
client did not register is the open redirect this whole check exists against (T-03-41). The
SDK refuses it too; the difference here is that the refusal is readable.

**Why the sign in link travels in the query.** The Login Flow v2 gives us the address of
its sign in page exactly once, in the answer to the authorization request, and the flow
record of the store has no column for it (the schema of plan 03-02 is shipped and a
migration is a bigger decision than this plan). So the redirect carries it, and the page
checks before it renders it that it points at the configured Nextcloud: a link on a page
that asks for trust is exactly the phishing step this surface exists against, and an
unchecked one would let anybody who can build a URL put their own page behind our button
(T-03-42). A link that fails the check is not shown; the sign in still finishes, because
the waiting state polls the flow either way.

**Why the sign in produces an authorization before anybody consented.** The poll answers
200 exactly once, and what it hands over is a Nextcloud app password that exists from that
moment on. It has to be stored right there or it is lost, so the row is written under the
id of its own flow, which is what connects the two without a column for it. Nothing can be
done with that row yet: no token exists without an authorization code, and plan 03-06
creates the code only when the user approves. The denial path of that plan revokes the app
password again, and that is the one piece of housekeeping this state owes.

**Why the decision has a route of its own.** The screen and the decision are two different
security problems (CR-01). The screen shows what a client is asking for and grants nothing,
so a browser that has not signed in yet may see it. The decision turns a sign in into a
grant, and the only fact that says the person deciding is the person who signed in is the
Nextcloud account behind the browser. So the decision lives at ``/authorize/decide`` and
:func:`_decide` compares the account HaRP resolved with the one the sign in produced.
Without that comparison the flow id alone decided, and the flow id belongs to whoever
started the flow.

**Why that route is PUBLIC and not ``USER``.** HaRP resolves the Nextcloud account of a
request on a PUBLIC route as well and writes it into ``AUTHORIZATION-APP-API``, empty when
the caller sent no credential (``exapp/auth.appapi_user``), so the access level buys nothing
the comparison below does not already do. It costs something, though: HaRP records every
refusal of a ``USER`` route in a blacklist of its own, and ten of them from one address in
five minutes answer that address with 502 on *every* route of this app, discovery documents
and ``/mcp`` included. Refusals are this route's normal traffic, not an anomaly, so the
level meant to harden it took the connector down for the caller instead. Measured, both
halves, in ``docs/oauth-setup.md``. The comparison is also the only check that can tell the
two apart: the relay attacker of CR-01 holds a valid Nextcloud account too, so the question
is never "signed in" but "signed in as whom", and HaRP cannot answer that one.

The route is a factory like every other one of this project and is attached by
``entry_exapp`` alone (D-23). The guards return a response instead of raising, so no
refusal can escape as a 500 (the shape of ``exapp/lifecycle.py``).
"""

import logging
import secrets
import time
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.provider import construct_redirect_uri
from mcp.server.auth.routes import AUTHORIZATION_PATH
from mcp.shared.auth import InvalidRedirectUriError, OAuthClientInformationFull
from pydantic import AnyUrl, ValidationError
from starlette.datastructures import FormData, QueryParams
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from .. import config
from ..errors import ToolError
from ..exapp.responses import form_or_none
from ..exapp.ui import errors
from ..exapp.ui.consent import (
    CONFIRM_PARAM,
    CONSENT_PATH,
    DECIDE_PATH,
    DECISION_APPROVE,
    DECISION_DENY,
    DECISION_PARAM,
    FLOW_PARAM,
    LOGIN_PARAM,
    STEP_PARAM,
    STEP_WAIT,
    connected_page,
    consent_page,
    denied_page,
    empty_page,
    handoff_page,
    waiting_page,
)
from ..nextcloud.target import NextcloudTarget
from . import cimd, crypto, loginflow, registry
from .browser_identity import BrowserIdentitySource
from .provider import NextcloudOAuthProvider
from .registry import redirect_uri_allowed
from .store import FlowRow, OAuthStore
from .throttle import CLASS_AUTHORIZE, CLASS_AUTHORIZE_START, FLOW_LIMIT, Throttle, Throttled

__all__ = [
    "AUTHORIZATION_PATH",
    "CODE_BYTES",
    "CONSENT_PATH",
    "DECIDE_PATH",
    "consent_routes",
]

#: 32 bytes of entropy behind an authorization code, which ``token_urlsafe`` renders as 43
#: characters. The same size as every other secret of this phase: the code is a bearer
#: value for sixty seconds, and sixty seconds of a guessable code is still a granted
#: connection.
CODE_BYTES = 32

#: The one path shape a Login Flow v2 grant page has: Nextcloud builds it as
#: ``<base>/index.php/login/v2/flow/<token>`` and answers it as ``/login/v2/flow/<token>``
#: behind a prefix rewrite, so the marker is the part both spellings share. Checked as a
#: substring and not as a prefix on purpose: the base of an instance may carry a path of
#: its own, and what has to be excluded is every *other* page of that host (WR-07).
_LOGIN_PATH_MARKER = "/login/v2/flow"

logger = logging.getLogger("mcp_connector.oauth.consent")


def consent_routes(
    env: Mapping[str, str] | None = None,
    *,
    provider: NextcloudOAuthProvider,
    browser_identity: BrowserIdentitySource,
    nextcloud: NextcloudTarget,
    throttle: Throttle | None = None,
) -> list[Route]:
    """The authorization endpoint of this app and the consent surface behind it.

    Every route is throttled, and every one of them as a browser path: a refused request
    here ends on a page, so the throttled one has to as well (E6 with the same seconds in
    its header and in its text). The screen and the decision share one path class, because
    they are one surface to a caller: the two halves of one attempt (D-37). The
    authorization endpoint has one of its own since CR-02, because what has to be bounded
    there is not its refusals but its successes: each of them opens a Nextcloud login flow.
    """
    handler = AuthorizationHandler(provider)

    async def authorize(request: Request) -> Response:
        """The front door: refuse readably, or let the SDK do its work.

        The per account switch of EXAPP-02 is deliberately *not* checked here, and the
        absence is not an oversight (BL-10): at this point the account is not known. The
        request carries a client id and a return address, the sign in has not happened yet,
        and the browser may belong to anybody. The earliest place the switch can be enforced
        is therefore the one where the sign in produced an account, which is :func:`_screen`
        after the poll, and the price of that placement is the app password that already
        exists by then. That is why every refusal there hands it back.
        """
        if request.method == "GET":
            params: Mapping[str, str] | FormData = request.query_params
        else:
            form = await form_or_none(request)
            if form is None:
                # A body no parser can read carries no authorization request, so it is
                # refused as one that names nothing, on a page and never as a traceback
                # (HI-02).
                return _page(errors.error_page("E3", env=env))
            params = form
        refusal, relaxed = await _refuse(params, provider, env)
        if refusal is not None:
            return refusal
        if relaxed is not None:
            # The SDK handler loads the client itself and compares the return address
            # against the registration a second time (authorize.py:180), so the port rule
            # of RFC 8252 7.3 that :func:`_refuse` just applied has to reach that
            # comparison or it applied to nothing. It reaches it as a view of this provider
            # that lives for this one request and hands out a client with this one address
            # added: nothing is written, and the next request sees the registration as it
            # is (T-06-19).
            return await AuthorizationHandler(provider.also_accepting(relaxed)).handle(request)
        return await handler.handle(request)

    async def consent(request: Request) -> Response:
        """The consent surface: hand over, wait, show the decision screen.

        A GET only, and it grants nothing whatever it carries (T-03-50). It is the one
        half of this surface a browser may reach without being signed in to Nextcloud,
        because that is where the sign in is offered in the first place, which is why the
        route stays PUBLIC in ``appinfo/info.xml``.
        """
        return await _screen(request.query_params, provider, nextcloud, env)

    async def decide(request: Request) -> Response:
        """The other half: the decision, on a path of its own because it grants something.

        Split off the consent screen for CR-01. The screen may be anonymous, the decision
        may not: HaRP resolves the Nextcloud account behind the request and writes it into
        the AppAPI header, and :func:`_decide` refuses every decision that does not come
        from the account whose sign in produced the authorization. The route is PUBLIC and
        the refusal is this application's own, for the reason the module docstring gives.
        """
        return await _decide(request, provider, browser_identity, nextcloud, env)

    counters = throttle if throttle is not None else Throttle()
    authorize_route = Route(AUTHORIZATION_PATH, authorize, methods=["GET", "POST"])
    screen_routes = [
        Route(CONSENT_PATH, consent, methods=["GET"]),
        Route(DECIDE_PATH, decide, methods=["POST"]),
    ]
    # The authorization endpoint opens a Nextcloud login flow on every request it does not
    # refuse, and it answers 302 when it does, so its cost was invisible to a counter that
    # only saw refusals (CR-02, SC 5). Every request of it is counted now, with a class and
    # a limit of its own, so the consent screen behind it keeps the ten refusals it needs.
    authorize_route.app = Throttled(
        authorize_route.app,
        counters,
        CLASS_AUTHORIZE_START,
        machine=False,
        env=env,
        count_all=True,
        limit=FLOW_LIMIT,
    )
    for route in screen_routes:
        route.app = Throttled(route.app, counters, CLASS_AUTHORIZE, machine=False, env=env)
    return [authorize_route, *screen_routes]


async def _refuse(
    params: QueryParams | FormData,
    provider: NextcloudOAuthProvider,
    env: Mapping[str, str] | None,
) -> tuple[Response | None, AnyUrl | None]:
    """The page this request ends on, and the address the SDK still has to be told about.

    Two values, because the redirect check has two outcomes that both matter. The first is
    the page: ``None`` means the request may go to the SDK handler. The second is the one
    address the loopback port rule of RFC 8252 7.3 let through, which the handler's own
    exact comparison would refuse a second time, and ``None`` for every other request.

    The order of the two halves of that check is fixed: the SDK compares exactly, and only
    where that fails is the port rule asked. Whatever comes out of it goes through the D-35
    check below, because a relaxed port must not skip the rule about which addresses may be
    returned to at all (T-03-41). Every refusal is the same page, ``E5``: an answer that
    said which half fell would be an information service for whoever is guessing (T-03-47).
    """
    client_id = str(params.get("client_id") or "")
    if not client_id:
        # Not an authorization request at all: a link somebody kept, a stale tab, or the
        # "Start over" of the timeout page. The empty state says so in a sentence.
        return empty_page(env=env), None

    client = await provider.get_client(client_id)
    if client is None:
        return _no_client_page(client_id, provider, env), None

    raw = params.get("redirect_uri")
    try:
        requested = AnyUrl(str(raw)) if raw else None
    except (ValidationError, ValueError):
        return _page(errors.error_page("E5", env=env, client=_name(client))), None
    relaxed: AnyUrl | None = None
    try:
        address = client.validate_redirect_uri(requested)
    except InvalidRedirectUriError:
        # The one relaxation RFC 8252 7.3 demands, and it is a MUST: a native client takes
        # whatever port the operating system gives it, so the exact comparison of the SDK
        # refuses it over a property it cannot control. Claude Code publishes
        # ``http://localhost/callback`` in its client id metadata document and arrives with
        # ``http://localhost:3118/callback`` (CLIENT-05). Everything except the port is
        # still compared exactly, by the port rule of the registry, and nothing is written
        # back into the registration on a match (T-06-19).
        registered = [str(uri) for uri in client.redirect_uris or []]
        if requested is None or registry.loopback_match(str(requested), registered) is None:
            return _page(errors.error_page("E5", env=env, client=_name(client))), None
        # The REQUESTED address, with its port, is what travels on into the flow and into
        # the authorization code. That is what makes the token endpoint correct without a
        # change: ``mcp/server/auth/handlers/token.py:164-183`` compares the redirect URI of
        # the token request against the stored value of the code, not against the
        # registration, so both sides carry the same port of their own accord. A second
        # relaxation in the token path would be one place too many (T-06-20).
        address = requested
        relaxed = requested
    except (ValidationError, ValueError):
        return _page(errors.error_page("E5", env=env, client=_name(client))), None
    if not redirect_uri_allowed(str(address)):
        # A registration from before this rule, or one written another way. The address is
        # checked where it is used and not only where it was accepted (T-03-41).
        return _page(errors.error_page("E5", env=env, client=_name(client))), None
    return None, relaxed


def _no_client_page(
    client_id: str, provider: NextcloudOAuthProvider, env: Mapping[str, str] | None
) -> Response:
    """Which of the three pages a refused client gets, decided without asking the store.

    ``get_client`` answers ``None`` for unknown, blocked, unlisted and expired alike, and
    that is deliberate: an answer that separates them is an information service for whoever
    is guessing client ids (T-03-47). The page is therefore chosen from the policy, which
    is the administrator's own configuration and tells the caller nothing about any client:

    * with the allowlist mode on, the next step is an administrator (E1),
    * with registration switched off, the next step is an administrator too, and the page
      names the reason a registration would fail (E2),
    * otherwise the honest reading is that the registration is gone or was never made, and
      the next step is the app that asked (E3).
    """
    policy = provider.policy
    if policy.allowlist_only and not policy.listed(client_id):
        return _page(errors.error_page("E1", env=env, client=client_id))
    if not policy.dcr_enabled:
        return _page(errors.error_page("E2", env=env, client=client_id))
    return _page(errors.error_page("E3", env=env, client=client_id))


async def _screen(
    params: QueryParams,
    provider: NextcloudOAuthProvider,
    nextcloud: NextcloudTarget,
    env: Mapping[str, str] | None,
) -> Response:
    """One of the four states of the consent surface, in the order they can happen."""
    flow_id = params.get(FLOW_PARAM) or ""
    if not flow_id:
        return _page(errors.error_page("E3", env=env))

    store = await _store_or_page(provider, env)
    if isinstance(store, Response):
        return store

    # Loaded without the deadline, so that "ran out of time" and "never existed" can be
    # told apart here. Nextcloud cannot tell them apart: it answers 404 for both.
    row = await _flow_or_page(store, flow_id, env)
    if isinstance(row, Response):
        return row
    if row is None:
        return _page(errors.error_page("E3", env=env))
    if row.expires_at <= _now():
        await store.delete_flow(flow_id)
        return _page(errors.error_page("E4", env=env))

    client = await provider.get_client(row.client_id)
    if client is None:
        # The enforcement point again, on the way to the decision: a client that was
        # blocked while its user was signing in must not reach the screen that grants
        # anything (T-03-40, pitfall 9).
        return _no_client_page(row.client_id, provider, env)

    signed_in = await store.load_authorization(flow_id)
    if signed_in is not None:
        # The switch again, between point 1 (after the poll, below) and point 3 (the
        # decision), and IN-06 of 05-REVIEW.md is why it is read here at all. This branch
        # runs when an authorization row already exists, which is every reload of the
        # screen: after the account was paused in another tab it still showed approve and
        # deny. No grant was possible, point 3 answers the click with the paused page, but a
        # surface that offers a button it is going to refuse says the opposite of what the
        # switch promises. This is a display check and not a fourth enforcement point:
        # nothing is granted here, and nothing would be granted without it.
        #
        # Nothing is withdrawn on this path, unlike after the poll and unlike at the
        # decision: this is a GET, a reload is not a decision, and a request that changes
        # state because a browser repeated it is its own defect. The row and the app
        # password behind it end where they always did, at the decision or with the flow.
        disabled = await _access_disabled(store, signed_in.nc_user)
        if disabled is None:
            return _generic("the access switch could not be read", env)
        if disabled:
            logger.info("a consent screen was refused because the account has paused access")
            return _page(errors.error_page(errors.PAUSED, env=env))
        return _decision(client, signed_in.nc_user, row, store, provider, env)

    if params.get(STEP_PARAM) != STEP_WAIT:
        link = _sign_in_link(params.get(LOGIN_PARAM) or "", nextcloud, env)
        if link:
            return handoff_page(_name(client), link, flow_id, env=env)
        # No usable link, so the honest page is the one that keeps asking: the sign in may
        # already be running in another window.
        return waiting_page(flow_id, env=env)

    result = await loginflow.poll_once(row.poll_token, target=nextcloud)
    if result.outcome == loginflow.POLL_PENDING:
        return waiting_page(flow_id, env=env)
    if result.outcome != loginflow.POLL_DONE or result.credentials is None:
        return _generic("the login flow poll failed", env)

    credentials = result.credentials

    # Enforcement point 1 of BL-10, and the earliest one there is: the account is known from
    # this line on and not one line earlier, because it is the poll that names it. The switch
    # is read locally, from the file this container already owns (D-47), and never from a
    # process cache, so pulling the brake takes effect on the very next request (D-48).
    #
    # The price of the placement is the app password: it exists at Nextcloud from the 200 of
    # the poll, and this refusal is the reason nobody will ever use it. So it goes back, word
    # for word like the write failure branch below and the ``is_user`` branch of
    # ``connect._wait`` (pitfall 13, D-34).
    disabled = await _access_disabled(store, credentials.login_name)
    if disabled is not False:
        # ``None`` is the store that could not answer, and that is never a "no" (fail closed,
        # D-37, the same choice the transport boundary of phase 4 makes).
        return await _refuse_paused(
            store, flow_id, credentials, nextcloud, env, readable=disabled is True
        )

    try:
        # Written under the id of its own flow, which is what connects the two without a
        # column for it. It has to happen now: the 200 of a poll arrives exactly once.
        await store.create_authorization(
            flow_id,
            client_id=row.client_id,
            nc_user=credentials.login_name,
            app_password=credentials.app_password,
            scopes=row.scopes,
            resource=row.resource,
        )
    except Exception:
        logger.exception("the finished sign in could not be written to the store")
        # The app password exists at Nextcloud from now on and nobody will ever use it, so
        # it is handed back instead of left behind (pitfall 13, D-34).
        await loginflow.revoke_app_password(
            credentials.login_name, credentials.app_password, target=nextcloud
        )
        return _generic("the finished sign in could not be written to the store", env)

    return _decision(client, credentials.login_name, row, store, provider, env)


def _decision(
    client: OAuthClientInformationFull,
    user: str,
    row: FlowRow,
    store: OAuthStore,
    provider: NextcloudOAuthProvider,
    env: Mapping[str, str] | None,
) -> Response:
    """The consent screen, with the three things about this client the reader has to know.

    The first is the answer to "who says this app is what it says it is". In v1 every
    client in the registry got there by registering itself or by publishing a document, so
    the honest condition is membership of the administrator's list, and the shipped state
    (an empty list) shows the warning for every one of them (03-UI-SPEC.md, S3, T-03-42).

    The other two are the display duties the MCP specification puts on a client that
    identifies itself with a metadata document, and they are computed here for the same
    reason ``unverified`` is: the caller decides, the page renders (plan 06-06).

    * The host comes from the identifier itself, because such an identifier *is* an https
      URL while a registered one is a random identifier. No store row and no column is read
      for it, deliberately: this route costs exactly one Nextcloud round trip per request
      (success criterion 5 of phase 3), and a second lookup for a fact the string already
      carries would be a round trip bought for nothing.
    * The loopback question is asked of the registered addresses and never of the
      registration path, because the danger lives in the address: on a desktop any program
      can hold a loopback port and name a foreign identifier, so a client that registered
      itself with nothing but loopback addresses is in the same position as one that
      published a document (T-06-35).
    """
    addresses = [str(uri) for uri in client.redirect_uris or []]
    return consent_page(
        _name(client),
        client.client_id,
        row.redirect_uri,
        user,
        row.flow_id,
        store.form_token(row.flow_id, purpose=crypto.PURPOSE_CONSENT),
        unverified=not provider.policy.listed(client.client_id, addresses),
        client_host=_identifier_host(client.client_id),
        loopback_only=_loopback_only(addresses),
        env=env,
    )


def _identifier_host(client_id: str) -> str | None:
    """The host of an identifier that is a document URL, and ``None`` for anything else.

    The form of the identifier is the whole test (``cimd.is_cimd_client_id``): a document
    identity is an https URL with a path by definition of the draft, and a registration
    carries a random identifier the SDK minted. An unparsable value is ``None`` and never an
    exception, like every other reading of an address in this module.
    """
    if not cimd.is_cimd_client_id(client_id):
        return None
    try:
        return urlsplit(client_id).hostname
    except ValueError:
        return None


def _loopback_only(addresses: Sequence[str]) -> bool:
    """Whether every registered return address of this client is on the user's own machine.

    An empty list is not "only loopback": a client with no return address at all is a
    different situation, and it already ends in a page of its own before this screen.
    """
    if not addresses:
        return False
    return all(_is_loopback(address) for address in addresses)


def _is_loopback(address: str) -> bool:
    """One address against :data:`registry.LOOPBACK_HOSTS`, the set D-35 already admits.

    Both the host and the port are read, the reading of ``registry._comparable_host``: an
    address this library cannot take apart is not one this page would claim anything about.
    """
    parts = urlsplit(address)
    try:
        host, _port = parts.hostname, parts.port
    except ValueError:
        return False
    return bool(host) and host.lower() in registry.LOOPBACK_HOSTS


async def _decide(
    request: Request,
    provider: NextcloudOAuthProvider,
    browser_identity: BrowserIdentitySource,
    nextcloud: NextcloudTarget,
    env: Mapping[str, str] | None,
) -> Response:
    """The one request of this whole surface that grants or refuses something.

    The order of the checks is the order of the things that can be wrong, and every one of
    them ends the request without touching a row: no flow, no time left, no anti forgery
    value, a client that was blocked while the user was reading, a sign in that never
    finished, and finally a browser that is not the account that signed in. Only after all
    six does the decision itself get read.

    The seventh check is the one exception to "without touching a row" and it is the last one
    before the decision: an account that paused its own MCP access while this screen stood
    open (BL-10). It cannot end the request untouched, because by then a sign in has happened
    and an app password exists, so it runs the denial path and answers a page of its own.

    **Why the last check is the one that matters (CR-01).** Until it existed, the flow id
    was the whole authorisation of this request, and the flow id belongs to whoever started
    the flow, which in the OAuth path is the client and not the user. That made the classic
    Login Flow v2 relay work: an attacker starts an authorization, sends the victim nothing
    but Nextcloud's own sign in link, and then finishes the flow themselves, so the consent
    screen the victim was supposed to read is never shown to anybody. The anti forgery
    value could not answer that, because it is derived from the same flow id. The account
    that signed in can: it is the one fact of this request the party that started the flow
    cannot produce, and HaRP puts it into the AppAPI header of every request it forwards.
    A source must fail closed for a missing or ambiguous identity, so an anonymous request
    is refused here as well.  The deployment chooses the trust anchor when it assembles the
    application; no request parameter can select or replace it.
    """
    form = await form_or_none(request)
    if form is None:
        # The same answer as a decision without a flow, for the same reason: this request
        # names none, and a body the parser refused may not leave as a 500 (HI-02).
        return _page(errors.error_page("E3", env=env))
    flow_id = str(form.get(FLOW_PARAM) or "")
    if not flow_id:
        return _page(errors.error_page("E3", env=env))

    store = await _store_or_page(provider, env)
    if isinstance(store, Response):
        return store

    row = await _flow_or_page(store, flow_id, env)
    if isinstance(row, Response):
        return row
    if row is None:
        # Also the second press of the same button: an approved flow is gone, so the page
        # that says "this link has expired" is exactly right for it.
        return _page(errors.error_page("E3", env=env))
    if row.expires_at <= _now():
        await store.delete_flow(flow_id)
        return _page(errors.error_page("E4", env=env))

    if not _confirmed(store, flow_id, str(form.get(CONFIRM_PARAM) or "")):
        # A decision that did not come from the form this server rendered (T-03-50). The
        # answer is the page an expired link gets, because a refusal that names the reason
        # would tell whoever tried which of the two values they got wrong.
        logger.warning("a decision arrived without the anti forgery value of its flow")
        return _page(errors.error_page("E3", env=env))

    client = await provider.get_client(row.client_id)
    if client is None:
        # The enforcement point one last time, at the moment the grant would happen
        # (T-03-40, pitfall 9).
        return _no_client_page(row.client_id, provider, env)

    authorization = await store.load_authorization(flow_id)
    if authorization is None:
        # The form was submitted before the sign in finished. Nothing exists to approve,
        # and the honest next step is to start the connection again.
        return _page(errors.error_page("E4", env=env))

    try:
        identified = await browser_identity.identifies(request, authorization.nc_user)
    except Exception:
        # A source is a security boundary.  Its outage or malformed state is one refusal,
        # never a 500 that might tempt a caller to add a weaker fallback.
        logger.error("the browser identity source could not decide the consent identity")
        identified = False

    if not identified:
        # The browser that decides is not the account whose sign in this is (CR-01).
        # Answered with the page an expired link gets, for the reason the anti forgery
        # refusal above is: a refusal that named the reason would tell whoever tried which
        # of the two halves they were missing (T-03-47).
        logger.warning("a decision arrived from a browser that is not the account that signed in")
        return _page(errors.error_page("E3", env=env))

    # Enforcement point 3 of BL-10, and the last one: an account can pause its access while
    # this screen stands open, and the press of a button on a page that was rendered before
    # that must not become a grant. Read here rather than only in :func:`_screen`, because
    # between the two lies however long the person took to read.
    disabled = await _access_disabled(store, authorization.nc_user)
    if disabled is None:
        return _generic("the access switch could not be read", env)
    if disabled:
        # The existing denial path runs: the app password goes back, the authorization and the
        # flow go, and nothing is granted. What differs is the answer. The client gets no
        # ``access_denied`` redirect, because that error means "the user said no", and this
        # user said nothing: the reason is a setting of their account (T-05-09). So the answer
        # is the page that names the setting and the way back to it, and the client learns
        # only that no code arrived.
        logger.info("a decision was refused because the account has paused its MCP access")
        if not await store.redeem_flow(row.flow_id):
            # The claim of BL-19 on this path too (BL-20): a withdrawal that arrives while an
            # approval of the same flow is underway must not take back what the other one just
            # granted, so it is the second press of the button like any other late decision.
            logger.info("a paused refusal arrived for a flow another decision had already spent")
            return _page(errors.error_page("E3", env=env))
        await _withdraw(store, row, authorization.nc_user, nextcloud)
        return _page(errors.error_page(errors.PAUSED, env=env))

    decision = str(form.get(DECISION_PARAM) or "")
    if decision == DECISION_APPROVE:
        return await _approve(store, row, client, authorization.nc_user, env)
    if decision == DECISION_DENY:
        return await _deny(store, row, client, authorization.nc_user, nextcloud, env)
    # Neither button. Nothing is granted and nothing is refused, so nothing changes.
    return _page(errors.error_page("E3", env=env))


async def _approve(
    store: OAuthStore,
    row: FlowRow,
    client: OAuthClientInformationFull,
    user: str,
    env: Mapping[str, str] | None,
) -> Response:
    """Turn the consent of a person into one short lived, single use authorization code.

    The code is the only thing this step creates: the authorization itself was written when
    the sign in finished, under the id of its own flow, which is why the code points at the
    flow id (plan 03-05). The flow is spent in the same breath, so a second press of the
    same button finds nothing to approve twice.

    "In the same breath" is one transaction since BL-19, and it has to be. The write used to
    be an insert followed by a delete, after a read that had found the flow: two approvals of
    the same flow that arrived at once both passed the read and both wrote a code, so one
    consent handed out two of them. :meth:`OAuthStore.redeem_flow_for_code` makes the
    deletion the claim and the code its consequence, and the caller that does not get the row
    gets the answer the second press of the button gets, because that is what it is.
    """
    code = secrets.token_urlsafe(CODE_BYTES)
    try:
        granted = await store.redeem_flow_for_code(
            row.flow_id,
            code,
            redirect_uri=row.redirect_uri,
            redirect_uri_explicit=row.redirect_uri_explicit,
            code_challenge=row.code_challenge,
            resource=row.resource,
        )
    except Exception:
        logger.exception("the approved authorization could not be written to the store")
        return _generic("the authorization code could not be written", env)
    if not granted:
        logger.info("an approval arrived for a flow another decision had already spent")
        return _page(errors.error_page("E3", env=env))

    if not row.redirect_uri:
        return connected_page(_name(client), user, env=env)

    # ``iss`` is the mix-up protection of RFC 9207: a client that talks to more than one
    # authorization server can tell from it which one answered, and refuse a response that
    # came back from a server it did not send this request to. The same fact is announced
    # in the metadata document as ``authorization_response_iss_parameter_supported``
    # (oauth/metadata.py), and the value is the configured public URL, never a request.
    target = construct_redirect_uri(
        row.redirect_uri, code=code, state=row.state, iss=config.public_url(env)
    )
    # A page and not a 302 (CR-03). This answer is the answer of a form submission, and
    # Chromium and WebKit check ``form-action`` against the target of a redirect that
    # follows one; the policy of every page of this phase is ``form-action 'self'``, so
    # those browsers refuse to follow a redirect to the client and the user is left on a
    # blank page. The page navigates instead, which no browser checks against that
    # directive, and it does so without naming a foreign origin in the policy.
    return connected_page(_name(client), user, target=target, env=env)


async def _deny(
    store: OAuthStore,
    row: FlowRow,
    client: OAuthClientInformationFull,
    user: str,
    nextcloud: NextcloudTarget,
    env: Mapping[str, str] | None,
) -> Response:
    """Refuse the connection, and take back what the sign in already handed out.

    The app password behind this flow exists at Nextcloud from the moment the sign in
    finished, which is before anybody consented (plan 03-05). A refused connection must not
    leave a working credential behind, so it is handed back here: one attempt, no retry,
    and the row goes even when that attempt fails, because a connection the user refused
    must not survive a cleanup step that did not work (D-34, D-37).

    The flow is claimed first, the same compare and set the approval runs (BL-19): a refusal
    that arrives while an approval of the same flow is underway must not take back what the
    other one just granted, and the second of the two decisions is the second press of the
    button, whichever button it was.
    """
    if not await store.redeem_flow(row.flow_id):
        logger.info("a denial arrived for a flow another decision had already spent")
        return _page(errors.error_page("E3", env=env))

    await _withdraw(store, row, user, nextcloud)

    if not row.redirect_uri:
        return denied_page(_name(client), env=env)

    # The same page shape as the approval, for the same reason (CR-03): the refusal has to
    # reach the client that asked, and a 302 out of a form submission is refused by
    # Chromium and WebKit under ``form-action 'self'``.
    target = construct_redirect_uri(
        row.redirect_uri, error="access_denied", state=row.state, iss=config.public_url(env)
    )
    return denied_page(_name(client), target=target, env=env)


async def _withdraw(
    store: OAuthStore,
    row: FlowRow,
    user: str,
    nextcloud: NextcloudTarget,
) -> None:
    """Take back what the sign in already handed out, and forget the flow that produced it.

    Split out of :func:`_deny` so the refusal of a paused account can run the very same three
    steps and answer a different page (BL-10). One attempt at the revocation and no retry,
    and the rows go even when that attempt fails: a connection that must not exist may not
    survive because a cleanup step at Nextcloud did not work (D-34, D-37).
    """
    password = await _app_password(store, row.flow_id)
    if password:
        await loginflow.revoke_app_password(user, password, target=nextcloud)
    await store.delete_authorization(row.flow_id)
    await store.delete_flow(row.flow_id)


async def _refuse_paused(
    store: OAuthStore,
    flow_id: str,
    credentials: loginflow.AppCredentials,
    nextcloud: NextcloudTarget,
    env: Mapping[str, str] | None,
    *,
    readable: bool,
) -> Response:
    """End a finished sign in that may not become an authorization (BL-10).

    No authorization row exists yet at this point, so there is nothing to delete: what has to
    happen is that the app password of the poll goes back and the flow record goes with it,
    because the 200 of a poll arrives exactly once and a record that survived would leave a
    page to try the same sign in on again.

    ``readable`` tells the two cases apart that end here. A switch that says "paused" is the
    page that names the setting and the way to it. A switch that could not be read at all is
    the generic page: the reader can do nothing about it, and an administrator needs the
    reference in the log. Both refuse, which is the point (fail closed, D-37).
    """
    if readable:
        logger.info("a finished sign in was refused because the account has paused MCP access")
    await loginflow.revoke_app_password(
        credentials.login_name, credentials.app_password, target=nextcloud
    )
    try:
        await store.delete_flow(flow_id)
    except Exception:
        # The store is the reason this branch runs in the unreadable case, so its second
        # failure is expected and may not turn the refusal into a traceback.
        logger.exception("the flow record of a refused sign in could not be removed")
    if readable:
        return _page(errors.error_page(errors.PAUSED, env=env))
    return _generic("the access switch could not be read", env)


async def _access_disabled(store: OAuthStore, nc_user: str) -> bool | None:
    """Whether this account paused its MCP access, or ``None`` when the store cannot say.

    Three states and not two on purpose: the caller has to be able to tell "not paused" from
    "no answer", because only the first one may continue. A single ``bool`` would have to pick
    a default for the failure, and both defaults are wrong: ``True`` refuses every connection
    of a healthy deployment whose file is momentarily locked, ``False`` is the pass through
    this whole plan exists against.
    """
    try:
        return await store.access_disabled(nc_user)
    except Exception:
        logger.exception("the per account access switch could not be read")
        return None


async def _app_password(store: OAuthStore, auth_id: str) -> str:
    """The credential of this connection, or an empty string. Never an exception.

    A ciphertext that cannot be read is a store written with another key, and it must not
    stop a denial: the user refused, and the refusal has to complete either way.
    """
    try:
        return await store.app_password(auth_id) or ""
    except Exception:
        logger.error("the app password of a denied connection could not be read back")
        return ""


def _confirmed(store: OAuthStore, flow_id: str, presented: str) -> bool:
    """Whether this decision came from the form this server rendered for this flow, recently.

    The comparison lives in the store and is the constant time one: the value arrives from a
    request, and a comparison that stops at the first different character leaks its prefix
    over enough attempts (the rule of ``exapp/auth.py``). It accepts the current window and
    the one before it, so a consent screen that was opened just before a full hour can still
    be decided; an older one is refused like a forged one, which is the answer below
    (BL-08, ME-02).
    """
    return store.form_token_valid(flow_id, presented, purpose=crypto.PURPOSE_CONSENT)


def _sign_in_link(candidate: str, nextcloud: NextcloudTarget, env: Mapping[str, str] | None) -> str:
    """The Nextcloud sign in address, or an empty string when it is not one.

    Three checks, and all of them are about the same question: is this the address of the
    Login Flow v2 page of the Nextcloud this app is deployed against. The scheme is checked
    because a link is clicked, the host because the value travelled through the browser and
    anybody can write a URL, and the path because the host alone is not an answer (WR-07):
    every page of that host passed, and a sign in page with an attacker chosen
    ``redirect_url``, a public share or anything else that renders on that origin would
    have stood behind the primary button of a page whose whole purpose is to be
    trustworthy.

    The two accepted hosts are the injected Nextcloud target and the configured public address
    of this app, which in every supported topology are the same domain: the ExApp lives
    under it, and Nextcloud builds its sign in address from ``overwrite.cli.url``. The path
    of a Login Flow v2 grant page has one shape, and :data:`_LOGIN_PATH_MARKER` is it.
    """
    if not candidate:
        return ""
    parts = urlsplit(candidate)
    if parts.scheme not in ("https", "http") or not parts.netloc:
        return ""
    known = {
        urlsplit(config.public_url(env)).netloc,
        nextcloud.netloc,
    }
    if parts.netloc not in known - {""}:
        logger.warning("a sign in link of a foreign host was not rendered")
        return ""
    if _LOGIN_PATH_MARKER not in parts.path:
        logger.warning("a sign in link with a foreign path was not rendered")
        return ""
    return candidate


async def _flow_or_page(
    store: OAuthStore, flow_id: str, env: Mapping[str, str] | None
) -> FlowRow | Response | None:
    """The flow record, ``None`` when there is none, or the page that ends the request.

    ``load_flow`` decrypts the poll token of the row, and a data key that changed or a
    damaged blob make that a :class:`~mcp_connector.oauth.crypto.DecryptionRejected`. This
    call site was unguarded, so such a row reached Starlette as a bare 500 while the module
    docstring said no refusal escapes as one (WR-06). Every other read of a secret in this
    phase is guarded the same way, and the answer is the generic page: the reader can do
    nothing about it, and the reference in the log is what an administrator needs.
    """
    try:
        return await store.load_flow(flow_id, now=0)
    except Exception:
        logger.exception("a flow record could not be read back")
        return _generic("the flow record could not be read", env)


async def _store_or_page(
    provider: NextcloudOAuthProvider, env: Mapping[str, str] | None
) -> OAuthStore | Response:
    """The store, or the page that ends the request. Never an exception into the framework.

    Fail closed (D-37): an incomplete deploy environment, a volume that is not writable and
    a data key that cannot be fetched are one answer to the user, and all three are an
    administrator's problem rather than theirs.
    """
    try:
        return await provider.store()
    except ToolError as exc:
        logger.error("the consent screen has no store: %s %s", exc.message, exc.hint)
        return _generic("the store could not be opened", env)
    except Exception:
        logger.exception("the consent screen could not open its store")
        return _generic("the store could not be opened", env)


def _name(client: OAuthClientInformationFull) -> str:
    """The name a registration gave itself, cleaned and cut where it is rendered."""
    return client.client_name or ""


def _generic(what: str, env: Mapping[str, str] | None) -> Response:
    """The generic page plus the one log line that carries its reference (T-03-24)."""
    response, reference = errors.error_page("E7", env=env)
    logger.error("%s (reference %s)", what, reference)
    return response


def _page(built: tuple[Response, str]) -> Response:
    """Take the response of an error page whose reference nobody has to log."""
    response, _ = built
    return response


def _now() -> int:
    """Whole seconds, in one place, so a deadline is compared against one clock."""
    return int(time.time())

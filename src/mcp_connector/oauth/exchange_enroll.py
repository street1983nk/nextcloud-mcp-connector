"""How a binding of the standalone mode comes to exist: three steps, two reserved clients.

A binding is a permanent pass for an account (CRED-02), so it must not come to exist in the
moment the Login Flow v2 answers. That moment can be triggered by whoever started the flow,
and that is not necessarily the person who signed in: an attacker who starts an enrollment
and sends the victim nothing but Nextcloud's own sign in link would otherwise own the
victim's binding. That is the very situation the independent browser identity of CR-01 was
written against, so the sign in only writes a holding row under
:data:`EXCHANGE_PENDING_CLIENT_ID`, a client the account source of plan 23-04 never reads,
and only the confirmed independent sign in of the same browser turns it into the binding
under :data:`~mcp_connector.oauth.exchange_accounts.EXCHANGE_CLIENT_ID`. With one client
instead of two, the binding would be usable between the login flow answer and the
confirmation, for the length of a browser excursion, and that window is the CR-01 attack.

The holding row is not bookkeeping that could be skipped: ``create_oidc_transaction``
demands a live flow whose authorization carries a canonical account id before the
independent sign in can even start, so the row has to exist first, and it can do nothing,
because ``binding_of`` filters on the other client.

The three steps are functions whose every outcome is a named value, so a test can measure
each of them; none of them raises outward, for the reason the pages of ``connect.py`` give:
whoever calls them renders an answer for a person. Since plan 23-06 the routes around them
live here as well: :func:`exchange_routes` hands out one address with two verbs, built like
``connections_routes``, and it is attached by ``entry_oauth`` alone and only while the
exchange path is armed.
"""

import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from .. import config
from ..errors import ToolError
from ..exapp.responses import BodyTooLarge, BodyUnreadable, bounded_body, form_or_none, with_body
from ..exapp.ui import errors
from ..exapp.ui.exchange import (
    ACTION_FIELD,
    ACTION_START,
    ENROLL_PATH,
    FLOW_PARAM,
    Binding,
    bound_page,
    handoff_page,
    identity_page,
    invitation_page,
    waiting_page,
)
from ..nextcloud.target import NextcloudTarget
from . import crypto, loginflow
from .browser_identity import BrowserIdentitySource
from .connect import FLOW_ID_BYTES
from .connections import MAX_FORM_BYTES
from .exchange_accounts import EXCHANGE_CLIENT_ID
from .metadata import RESOURCE_SUFFIX, TOOL_SCOPE
from .principal import login_name_of, principal_of
from .store import AuthorizationRow, OAuthStore
from .throttle import (
    CLASS_EXCHANGE_ENROLL,
    CLASS_EXCHANGE_ENROLL_START,
    FLOW_LIMIT,
    Throttle,
    Throttled,
)

__all__ = [
    "ENROLLMENT_CLIENT_NAME",
    "ENROLL_ALREADY_BOUND",
    "ENROLL_BOUND",
    "ENROLL_EXPIRED",
    "ENROLL_FAILED",
    "ENROLL_PATH",
    "ENROLL_PAUSED",
    "ENROLL_PENDING",
    "ENROLL_SIGNED_IN",
    "ENROLL_STARTED",
    "EXCHANGE_PENDING_CLIENT_ID",
    "EnrollmentSettled",
    "EnrollmentSignIn",
    "EnrollmentStart",
    "abort_enrollment",
    "begin_enrollment",
    "complete_enrollment",
    "exchange_routes",
    "settle_enrollment",
]

#: How a caller hands in its own store, the same shape ``oauth/connect.py`` uses.
type StoreProvider = Callable[[], Awaitable[OAuthStore]]

#: The one revocation of this deployment, handed in rather than imported: the withdrawal
#: goes through ``provider.end_connection`` and never through the store, because only that
#: path also empties the caches of the verifier chain (T-03-62, T-04-35).
type EndConnection = Callable[[str, str], Awaitable[bool]]

#: The reserved client id of the holding row: an enrollment that signed in and is not yet
#: confirmed. Same form as ``connect.CONNECT_CLIENT_ID`` and marked as not allowed for the
#: same reason (a bookkeeping row, never a client that may ask for a token). Deliberately
#: not :data:`EXCHANGE_CLIENT_ID`: the account source filters on that one, so a row under
#: this one can act as nothing, and the existing sweep of the abandoned sign ins takes it
#: when nobody ever confirms (plan 23-05, T-23-21).
EXCHANGE_PENDING_CLIENT_ID = "urn:mcp-connector:token-exchange-pending"

#: What the two reserved rows say about themselves when an administrator looks at the store.
_PENDING_CLIENT_METADATA = (
    '{"client_name":"Token exchange enrollment (CRED-02), not a registration"}'
)
_BINDING_CLIENT_METADATA = '{"client_name":"Token exchange bindings (CRED-02), not a registration"}'

#: The name Nextcloud shows in the grant dialog and under "Devices and sessions" for the
#: app password of a binding. ``loginflow`` puts its fixed prefix in front.
ENROLLMENT_CLIENT_NAME = "token exchange binding"

# The path of the enrollment page is re-exported above from ``exapp.ui.exchange``, where it
# stands next to the forms that write it into the document, so the page, these mechanics and
# the OIDC callback share one truth about one address and the dependency runs in one
# direction only (the rule of every page module of this project).

#: The named outcomes of the three steps. Strings and not an enum, for the reason
#: ``loginflow.py`` gives: the unknown case has to stay reachable in a test.
ENROLL_STARTED = "started"
ENROLL_PENDING = "pending"
ENROLL_EXPIRED = "expired"
ENROLL_PAUSED = "paused"
ENROLL_SIGNED_IN = "signed-in"
ENROLL_BOUND = "bound"
ENROLL_ALREADY_BOUND = "already-bound"
ENROLL_FAILED = "failed"

logger = logging.getLogger("mcp_connector.oauth.exchange_enroll")


@dataclass(frozen=True, slots=True)
class EnrollmentStart:
    """One opened enrollment: where the person signs in, and how this flow is asked about."""

    outcome: str
    flow_id: str = ""
    login_url: str = ""


@dataclass(frozen=True, slots=True)
class EnrollmentSignIn:
    """One answered poll: the holding row exists, or the named reason why nothing does."""

    outcome: str
    account_id: str = ""
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class EnrollmentSettled:
    """One confirmation: the binding it wrote, or the one it found already living."""

    outcome: str
    auth_id: str = ""


async def begin_enrollment(
    store: OAuthStore, *, nextcloud: NextcloudTarget, now: int | None = None
) -> EnrollmentStart:
    """Open a sign in at Nextcloud and remember it, under the holding client.

    The shape of ``connect._start``: the reserved row first (``flows`` points at ``clients``
    with a foreign key), then the flow at Nextcloud, then our own record of it. A store that
    cannot be written costs no Nextcloud round trip, and a flow record that cannot be
    written leaves only a sign in that expires at Nextcloud on its own, with no credential
    behind it.
    """
    try:
        await store.save_client(
            EXCHANGE_PENDING_CLIENT_ID, metadata_json=_PENDING_CLIENT_METADATA, allowed=False
        )
        await store.touch_client(EXCHANGE_PENDING_CLIENT_ID)
    except Exception:
        logger.exception("the enrollment could not write its reserved client")
        return EnrollmentStart(outcome=ENROLL_FAILED)

    started = await loginflow.start_flow(ENROLLMENT_CLIENT_NAME, target=nextcloud)
    if started is None:
        # loginflow logged what happened; nothing of the request is repeated here.
        return EnrollmentStart(outcome=ENROLL_FAILED)

    flow_id = secrets.token_urlsafe(FLOW_ID_BYTES)
    try:
        await store.create_flow(
            flow_id,
            client_id=EXCHANGE_PENDING_CLIENT_ID,
            # No redirect target, no code challenge, no scope and no resource: this flow
            # issues no token and sends nobody anywhere. Same honest emptiness as the
            # onboarding of ``connect.py``.
            redirect_uri="",
            redirect_uri_explicit=False,
            code_challenge="",
            state=None,
            scopes="",
            resource="",
            poll_token=started.poll_token,
            now=now,
        )
    except Exception:
        logger.exception("the enrollment flow could not be written to the store")
        return EnrollmentStart(outcome=ENROLL_FAILED)

    return EnrollmentStart(outcome=ENROLL_STARTED, flow_id=flow_id, login_url=started.login_url)


async def complete_enrollment(
    store: OAuthStore,
    flow_id: str,
    *,
    nextcloud: NextcloudTarget,
    env: Mapping[str, str] | None = None,
    now: int | None = None,
) -> EnrollmentSignIn:
    """Ask about the sign in once and, when it finished, write the holding row.

    The poll branch of ``consent.py``, step for step and with the same ways out: the 200 of
    a Login Flow v2 poll arrives exactly once and a Nextcloud app password exists from then
    on, so **every** refusal after the poll hands it back with ``revoke_app_password``,
    because nobody else will ever use it (pitfall 13, D-34). The one difference to the
    consent bridge: the flow record survives a success, because the OIDC transaction of the
    confirmation demands a live flow, and it is the settlement or the sweep that ends it.
    """
    try:
        # Loaded without the deadline, so "ran out" and "never existed" read the same here
        # and an expired record is still removed (the shape of ``connect._wait``).
        row = await store.load_flow(flow_id, now=0)
    except Exception:
        logger.exception("an enrollment flow record could not be read back")
        return EnrollmentSignIn(outcome=ENROLL_FAILED)
    if row is None:
        return EnrollmentSignIn(outcome=ENROLL_EXPIRED)
    if row.expires_at <= _moment(now):
        await _forget_flow(store, flow_id)
        return EnrollmentSignIn(outcome=ENROLL_EXPIRED)

    result = await loginflow.poll_once(row.poll_token, target=nextcloud)
    if result.outcome == loginflow.POLL_PENDING:
        return EnrollmentSignIn(outcome=ENROLL_PENDING)
    if result.outcome != loginflow.POLL_DONE or result.credentials is None:
        return EnrollmentSignIn(outcome=ENROLL_FAILED)
    credentials = result.credentials

    # The principal of this sign in: the canonical account id behind the fresh credential.
    # Without it nothing is held, and the credential goes back (pitfall 13).
    account = await loginflow.account(
        credentials.login_name, credentials.app_password, target=nextcloud
    )
    if account is None:
        await loginflow.revoke_app_password(
            credentials.login_name, credentials.app_password, target=nextcloud
        )
        await _forget_flow(store, flow_id)
        return EnrollmentSignIn(outcome=ENROLL_FAILED)

    disabled = await _access_disabled(store, account.account_id)
    if disabled is not False:
        # ``None`` is the store that could not answer, and that is never a "no" (fail
        # closed, D-37, the same choice every enforcement point of BL-10 makes).
        if disabled is True:
            logger.info("an enrollment was refused because the account has paused MCP access")
        await loginflow.revoke_app_password(
            credentials.login_name, credentials.app_password, target=nextcloud
        )
        await _forget_flow(store, flow_id)
        return EnrollmentSignIn(outcome=ENROLL_PAUSED if disabled is True else ENROLL_FAILED)

    try:
        # Written under the id of its own flow, which is what lets the OIDC transaction of
        # the confirmation find it. It has to happen now: the 200 of a poll arrives once.
        await store.create_authorization(
            flow_id,
            client_id=EXCHANGE_PENDING_CLIENT_ID,
            nc_user=credentials.login_name,
            nc_account_id=account.account_id,
            nc_display_name=account.display_name,
            app_password=credentials.app_password,
            scopes=TOOL_SCOPE,
            resource=f"{config.public_url(env)}{RESOURCE_SUFFIX}",
            now=now,
        )
    except Exception:
        logger.exception("the enrollment sign in could not be written to the store")
        await loginflow.revoke_app_password(
            credentials.login_name, credentials.app_password, target=nextcloud
        )
        await _forget_flow(store, flow_id)
        return EnrollmentSignIn(outcome=ENROLL_FAILED)

    return EnrollmentSignIn(
        outcome=ENROLL_SIGNED_IN,
        account_id=account.account_id,
        display_name=account.display_name,
    )


async def settle_enrollment(
    store: OAuthStore, flow_id: str, *, nextcloud: NextcloudTarget, now: int | None = None
) -> EnrollmentSettled:
    """Turn the holding row into the binding the account source reads.

    Only the confirmed browser identity of this flow may trigger this step; that check is
    the route's (plan 23-06), not this function's, exactly as the consent decision asks its
    identity source and ``redeem_flow`` claims the flow before anything is granted here.

    What this function does hold on to: only a row under the holding client settles. A
    caller that names the auth id of an ordinary connection gets a refusal that touches
    nothing, because turning a foreign row into a binding would mint a permanent pass out
    of a connection that never asked for one.
    """
    try:
        row = await store.load_authorization(flow_id)
        password = None if row is None else await store.app_password(flow_id)
    except Exception as exc:
        logger.error("the holding row of an enrollment could not be read: %s", type(exc).__name__)
        return EnrollmentSettled(outcome=ENROLL_FAILED)
    if (
        row is None
        or row.client_id != EXCHANGE_PENDING_CLIENT_ID
        or row.revoked_at is not None
        or not password
        or not row.nc_account_id
    ):
        return EnrollmentSettled(outcome=ENROLL_FAILED)

    try:
        existing = await store.binding_of(principal_of(row), EXCHANGE_CLIENT_ID)
    except Exception as exc:
        logger.error("the living binding of an account could not be read: %s", type(exc).__name__)
        return EnrollmentSettled(outcome=ENROLL_FAILED)
    if existing is not None:
        # One living binding per account (T-23-25). The second credential exists at
        # Nextcloud since its own poll and nobody will ever use it, so it goes back.
        await loginflow.revoke_app_password(login_name_of(row), password, target=nextcloud)
        await _drop_enrollment(store, flow_id)
        return EnrollmentSettled(outcome=ENROLL_ALREADY_BOUND, auth_id=existing.auth_id)

    auth_id = secrets.token_urlsafe(FLOW_ID_BYTES)
    try:
        await store.save_client(
            EXCHANGE_CLIENT_ID, metadata_json=_BINDING_CLIENT_METADATA, allowed=False
        )
        await store.touch_client(EXCHANGE_CLIENT_ID)
        await store.create_authorization(
            auth_id,
            client_id=EXCHANGE_CLIENT_ID,
            nc_user=row.nc_user,
            nc_account_id=row.nc_account_id,
            nc_display_name=row.nc_display_name,
            app_password=password,
            scopes=row.scopes,
            resource=row.resource,
            now=now,
        )
    except Exception:
        logger.exception("the binding of a confirmed enrollment could not be written")
        return EnrollmentSettled(outcome=ENROLL_FAILED)

    # Deleted and never revoked: the holding row and the binding share one app password,
    # and a revocation of the holding row would hand it back to Nextcloud and bring the
    # freshly written binding into the world dead. This is not cleanup to tidy up later.
    await _drop_enrollment(store, flow_id)
    return EnrollmentSettled(outcome=ENROLL_BOUND, auth_id=auth_id)


async def abort_enrollment(store: OAuthStore, flow_id: str, *, nextcloud: NextcloudTarget) -> None:
    """The shared way out: hand the credential back, drop both records, never raise.

    Best effort in every step, because one of its callers runs precisely because something
    just failed, and the worst end state is the one the sweep of the abandoned sign ins
    already knows how to clean up.
    """
    row = None
    password = None
    try:
        row = await store.load_authorization(flow_id)
        if row is not None:
            password = await store.app_password(flow_id)
    except Exception as exc:
        logger.error("an aborted enrollment could not be read back: %s", type(exc).__name__)
    if row is not None and password:
        await loginflow.revoke_app_password(login_name_of(row), password, target=nextcloud)
    await _drop_enrollment(store, flow_id)


async def _drop_enrollment(store: OAuthStore, flow_id: str) -> None:
    """Remove the holding row and the flow record, and never raise doing it."""
    try:
        await store.delete_authorization(flow_id)
    except Exception as exc:
        logger.error(
            "the holding row of an enrollment could not be removed: %s", type(exc).__name__
        )
    await _forget_flow(store, flow_id)


async def _forget_flow(store: OAuthStore, flow_id: str) -> None:
    """Drop the flow record of an enrollment that ends here, and never raise doing it."""
    try:
        await store.delete_flow(flow_id)
    except Exception as exc:
        logger.error(
            "the flow record of an enrollment could not be removed: %s", type(exc).__name__
        )


async def _access_disabled(store: OAuthStore, nc_user: str) -> bool | None:
    """Whether this account paused its MCP access, or ``None`` when the store cannot say.

    Three states and not two, for the reason ``connect._access_disabled`` gives: only "not
    paused" may continue, and both defaults of a bare bool would be wrong.
    """
    try:
        return await store.access_disabled(nc_user)
    except Exception:
        logger.exception("the per account access switch could not be read")
        return None


def _moment(now: int | None) -> int:
    """Whole seconds, in one place, so a deadline is compared against one clock."""
    return int(time.time()) if now is None else now


# --- the routes of the enrollment page (plan 23-06) -----------------------------------------


def exchange_routes(
    env: Mapping[str, str] | None = None,
    *,
    nextcloud: NextcloudTarget,
    store_provider: StoreProvider,
    browser_identity: BrowserIdentitySource,
    end_connection: EndConnection,
    acting_party: str = "",
    throttle: Throttle | None = None,
) -> list[Route]:
    """One address for the whole enrollment, in the shape of ``connections_routes``.

    One named action field and every state change a POST; the ``GET`` branch is the
    invitation, the waiting screen, the step to the independent sign in or the page of the
    binding, whatever the procedure says. Attached by ``entry_oauth`` alone and only while
    the exchange path is armed: in the off state this address does not exist at all.

    **The ownership check is the one strict line of this surface** (T-23-26): the binding
    is written only after ``browser_identity.identifies(request, account_id,
    flow_id=...)`` answered ``True``, immediately before the write and in the same request
    run. A failure of the source itself is a refusal and never a fallback, word for word as
    ``connect._wait`` has it: a source is a security boundary.

    ``end_connection`` is ``provider.end_connection``, handed in like the connections page
    takes it, so the withdrawal runs over the one revocation path of this deployment and
    the caches of the verifier chain are emptied with it (T-04-35).

    ``acting_party`` is what the page of a binding names as the service that acts: the
    configured allowed parties of the exchange path, handed in by the deployment because
    only it holds the validated configuration. Foreign realm text, treated by the page
    like a client name.

    Throttled as a browser surface and in two classes (T-23-27): the starting POST opens a
    Nextcloud login flow and answers 200 when it succeeds, so it counts every request
    against :data:`~mcp_connector.oauth.throttle.FLOW_LIMIT` (CR-02); the reads count
    refusals. A throttled request here is a person in a browser, so the answer is the
    error page E6 and never JSON.
    """

    async def enrollment(request: Request) -> Response:
        """The GET branch: whatever the procedure behind the flow id looks like right now."""
        flow_id = request.query_params.get(FLOW_PARAM) or ""
        if not flow_id:
            return invitation_page(env=env)
        store = await _store_or_page(store_provider, env)
        if isinstance(store, Response):
            return store
        return await _resume(request, store, flow_id)

    async def act(request: Request) -> Response:
        """The POST branch: two named actions, and everything else is the invitation, 400."""
        store = await _store_or_page(store_provider, env)
        if isinstance(store, Response):
            return store
        if _oversized(request):
            logger.warning("a form larger than this page has fields for was refused unread")
            return invitation_page(status_code=400, env=env)
        try:
            raw = await bounded_body(request, MAX_FORM_BYTES)
        except BodyTooLarge:
            logger.warning("a form larger than this page has fields for was refused unread")
            return invitation_page(status_code=400, env=env)
        except BodyUnreadable:
            return _generic("a submitted form could not be read", env)
        form = await form_or_none(with_body(request, raw))
        if form is None:
            return _generic("a submitted form could not be parsed", env)
        return await _act(request, form, store)

    async def _act(request: Request, form: FormData, store: OAuthStore) -> Response:
        action = str(form.get(ACTION_FIELD) or "")
        if action == ACTION_START:
            return await _start(store)
        # ACTION_REVOKE arrives with task 3 of this plan; until then it is an action this
        # route does not know, exactly like every other one.
        return invitation_page(status_code=400, env=env)

    async def _start(store: OAuthStore) -> Response:
        started = await begin_enrollment(store, nextcloud=nextcloud)
        if started.outcome != ENROLL_STARTED:
            return _generic("the enrollment could not be started", env)
        return handoff_page(started.login_url, started.flow_id, env=env)

    async def _resume(request: Request, store: OAuthStore, flow_id: str) -> Response:
        """One flow id, read back: the holding row decides whether the sign in is done.

        The 200 of a Login Flow v2 poll arrives exactly once, so a browser that returns
        from the independent sign in must not poll again: when the holding row of this
        flow already exists, the only step left is the confirmation.
        """
        try:
            holding = await store.load_authorization(flow_id)
        except Exception:
            logger.exception("an enrollment could not be read back")
            return _generic("the enrollment could not be read back", env)
        if holding is not None and _is_holding(holding):
            # ``or ""`` only narrows the type: ``_is_holding`` already required the id.
            return await _confirm(request, store, flow_id, holding.nc_account_id or "")

        result = await complete_enrollment(store, flow_id, nextcloud=nextcloud, env=env)
        if result.outcome == ENROLL_PENDING:
            return waiting_page(flow_id, env=env)
        if result.outcome == ENROLL_SIGNED_IN:
            return await _confirm(request, store, flow_id, result.account_id)
        if result.outcome == ENROLL_PAUSED:
            return _page(errors.error_page(errors.PAUSED, env=env))
        if result.outcome == ENROLL_EXPIRED:
            # A procedure that ran out, never existed or names a row that is no holding
            # row reads exactly like no procedure at all: the invitation, 200 (T-23-28).
            return invitation_page(env=env)
        return _generic("the enrollment could not be finished", env)

    async def _confirm(
        request: Request, store: OAuthStore, flow_id: str, account_id: str
    ) -> Response:
        """The ownership check, immediately before the only write of this surface.

        ``identifies`` consumes the browser proof exactly once and compares its account
        with the one the sign in produced. Only ``True`` settles; ``False`` shows the step
        to the independent sign in while the procedure lives and writes nothing; and an
        exception of the source is a refusal, never a pass (T-23-26).
        """
        if not account_id:
            return invitation_page(env=env)
        try:
            identified = await browser_identity.identifies(request, account_id, flow_id=flow_id)
        except Exception:
            # A source is a security boundary: its failure is a refusal, never a fallback.
            logger.error("the browser identity source could not decide the enrollment identity")
            return _generic("the browser identity could not be decided", env)
        if not identified:
            try:
                step = await browser_identity.pending_step(
                    request, flow_id=flow_id, expected_account_id=account_id
                )
            except Exception:
                logger.error("the browser identity source could not offer its step")
                return _generic("the browser identity could not be decided", env)
            if step is None:
                # A proof this source reads but did not redeem is not a confirmation.
                return invitation_page(env=env)
            return identity_page(step.action_path, dict(step.fields), env=env)

        settled = await settle_enrollment(store, flow_id, nextcloud=nextcloud)
        if settled.outcome not in (ENROLL_BOUND, ENROLL_ALREADY_BOUND):
            return _generic("the confirmed enrollment could not be settled", env)
        return await _bound(store, settled.auth_id)

    async def _bound(store: OAuthStore, auth_id: str) -> Response:
        """The page of one binding, with the anti forgery value of exactly this binding."""
        try:
            row = await store.load_authorization(auth_id)
        except Exception:
            logger.exception("a settled binding could not be read back")
            return _generic("the binding could not be read back", env)
        if row is None:
            return _generic("the binding could not be read back", env)
        return bound_page(
            Binding(
                auth_id=auth_id,
                created_at=row.created_at,
                acting_party=acting_party,
                token=store.form_token(auth_id, purpose=crypto.PURPOSE_DISCONNECT),
            ),
            user=row.nc_display_name or login_name_of(row),
            env=env,
        )

    counters = throttle if throttle is not None else Throttle()
    reads = Route(ENROLL_PATH, enrollment, methods=["GET"])
    starts = Route(ENROLL_PATH, act, methods=["POST"])
    reads.app = Throttled(reads.app, counters, CLASS_EXCHANGE_ENROLL, machine=False, env=env)
    # The POST is the one request of this address that makes Nextcloud open a login flow,
    # so every one of them is counted and not only the refused ones (CR-02, T-23-27). Its
    # own class, for the reason spelled at the two constants: the reads pay attempts back.
    starts.app = Throttled(
        starts.app,
        counters,
        CLASS_EXCHANGE_ENROLL_START,
        machine=False,
        env=env,
        count_all=True,
        limit=FLOW_LIMIT,
    )
    return [reads, starts]


def _is_holding(row: AuthorizationRow) -> bool:
    """Whether this row is the holding row of a signed in enrollment, and nothing else.

    The client filter is what keeps an ordinary connection out of this procedure: a caller
    that names the auth id of one gets the same answer as an unknown flow, and the row is
    never touched (the guard ``settle_enrollment`` holds a second time).
    """
    return (
        row.client_id == EXCHANGE_PENDING_CLIENT_ID
        and row.revoked_at is None
        and bool(row.nc_account_id)
    )


def _oversized(request: Request) -> bool:
    """Whether this request announces more body than this page could possibly need (LO-08).

    The announcement and not the body: a request that announces nothing passes here and
    meets ``responses.bounded_body`` in the handler, which counts what really arrives
    (IN-01). A header that is not a number is refused as well.
    """
    announced = request.headers.get("content-length") or "0"
    try:
        return int(announced) > MAX_FORM_BYTES
    except ValueError:
        return True


async def _store_or_page(
    store: StoreProvider, env: Mapping[str, str] | None
) -> OAuthStore | Response:
    """The store, or the page that ends the request. Never an exception into the framework.

    Fail closed (D-37): an incomplete environment, an unwritable volume and an unreadable
    data key are one answer to the user, and all three are an administrator's problem.
    """
    try:
        return await store()
    except ToolError as exc:
        logger.error("the enrollment page has no store: %s %s", exc.message, exc.hint)
        return _generic("the store could not be opened", env)
    except Exception:
        logger.exception("the enrollment page could not open its store")
        return _generic("the store could not be opened", env)


def _generic(what: str, env: Mapping[str, str] | None) -> Response:
    """The generic page plus the one log line that carries its reference (T-03-24)."""
    response, reference = errors.error_page("E7", env=env)
    logger.error("%s (reference %s)", what, reference)
    return response


def _page(built: tuple[Response, str]) -> Response:
    """Take the response of an error page whose reference nobody has to log."""
    response, _ = built
    return response

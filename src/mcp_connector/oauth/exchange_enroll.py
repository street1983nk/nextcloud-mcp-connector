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

No route, no request and no page lives here. The three steps are functions whose every
outcome is a named value, so a test can measure each of them; the routes and the pages
arrive with plan 23-06. None of these functions raises outward, for the reason the pages of
``connect.py`` give: whoever calls them renders an answer for a person.
"""

import logging
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass

from .. import config
from ..nextcloud.target import NextcloudTarget
from . import loginflow
from .connect import FLOW_ID_BYTES
from .exchange_accounts import EXCHANGE_CLIENT_ID
from .metadata import RESOURCE_SUFFIX, TOOL_SCOPE
from .principal import login_name_of, principal_of
from .store import OAuthStore

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
    "settle_enrollment",
]

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

#: The path of the enrollment page. The page itself is plan 23-06, but the OIDC callback
#: sends a confirmed enrollment browser back here today, so the constant lives with the
#: mechanics and 23-06 reuses it: two pages must not hold two truths about one path.
ENROLL_PATH = "/exchange"

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

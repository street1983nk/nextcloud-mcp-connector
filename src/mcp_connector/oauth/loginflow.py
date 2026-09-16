"""The Nextcloud Login Flow v2: start a sign in, poll it once, revoke what it produced.

This is the building block behind D-36. Nextcloud runs the whole sign in, including the
second factor, on its own pages; this server never sees the password and never shows a
password prompt of its own. What comes back is one dedicated app password per connection,
which the user can see and revoke in Nextcloud under "Devices and sessions".

The module is built like :mod:`mcp_connector.exapp.status`, the one outgoing call of the
ExApp package, and follows the same four rules (03-PATTERNS.md):

1. The target is the :class:`~mcp_connector.nextcloud.target.NextcloudTarget` the
   deployment injected when it built the application, never a value from an answer and
   never a second read of the environment.
2. The client comes from :func:`mcp_connector.nextcloud.http.shared_client`, which already
   refuses redirects and carries the timeouts of this project.
3. One attempt per call and no retry (D-37). A failure is a return value, so a caller can
   answer the user instead of dying.
4. No value of a request is repeated in a log record, because the request carries secrets.

Three properties of the flow are worth naming here, because each of them is easy to get
wrong exactly once (pitfall 7 of 03-RESEARCH.md):

* The poll answers 200 exactly once. Afterwards the record is gone in Nextcloud, and a
  second poll is a 404 again, so the caller has to process a success immediately.
* A 404 means "not finished yet" and "unknown or expired" at the same time. The difference
  is not visible from outside, which is why the deadline of a sign in is ours
  (:data:`mcp_connector.oauth.store.FLOW_TTL`) and never read out of an answer.
* The start answer carries an absolute poll address built from ``overwrite.cli.url``. It is
  a public URL that this container may not be able to resolve at all, so it is deliberately
  ignored: the poll below goes to the configured base URL with a fixed path.
"""

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..nextcloud.clients.ocs import OCS_HEADERS
from ..nextcloud.http import shared_client
from ..nextcloud.target import NextcloudTarget

__all__ = [
    "ACCOUNT_PATH",
    "AGENT_FALLBACK",
    "AGENT_NAME_LIMIT",
    "AGENT_PREFIX",
    "APP_PASSWORD_PATH",
    "INIT_PATH",
    "POLL_DONE",
    "POLL_FAILED",
    "POLL_PATH",
    "POLL_PENDING",
    "REVOKE_TIMEOUT",
    "AppCredentials",
    "FlowStart",
    "PollResult",
    "account_id",
    "poll_once",
    "revoke_app_password",
    "safe_user_agent",
    "start_flow",
]

#: Where a login flow is started. The ``index.php`` spelling is the one that works on an
#: instance without pretty URLs as well.
INIT_PATH = "/index.php/login/v2"

#: The one poll address this project uses. Fixed on purpose, see the module docstring.
POLL_PATH = "/login/v2/poll"

#: The OCS route that names the account a request authenticates as. Its ``id`` is the
#: canonical Nextcloud account id, which can differ from the login name (LDAP, alternative
#: login names).
ACCOUNT_PATH = "/ocs/v2.php/cloud/user"

#: The OCS route that deletes the app password a request authenticates with.
APP_PASSWORD_PATH = "/ocs/v2.php/core/apppassword"  # noqa: S105 - a route, not a password

#: Nextcloud turns the user agent of the start request into the client name it shows in the
#: grant dialog and later in "Devices and sessions" (``ClientFlowLoginV2Controller::init``).
#: The prefix is fixed so that entry is always recognisable as one of ours, and so an
#: administrator can write an allow list rule with ``core.login_flow_v2.allowed_user_agents``.
AGENT_PREFIX = "MCP Connector: "

#: How much of the name survives. Long enough to stay recognisable, short enough that a
#: registration cannot fill the Nextcloud dialog with copy of its own (pitfall 8).
AGENT_NAME_LIMIT = 64

#: What an app without a usable name is called. Never an empty user agent: an empty value
#: would leave the user with an unnamed entry in a dialog that asks for trust.
AGENT_FALLBACK = "unnamed app"

#: How long the deletion of an app password may take. Deliberately far below the read
#: timeout of the shared client: this call runs inside a revocation, a client gives that
#: request about ten seconds, and the deletion is the one step of a revocation that is
#: allowed to fail (pitfall 13, T-03-63).
REVOKE_TIMEOUT = 5.0

#: The three outcomes of one poll. Strings and not an enum, for the reason
#: ``nextcloud/credentials.py`` states: the unknown case has to stay reachable in a test.
POLL_DONE = "done"
POLL_PENDING = "pending"
POLL_FAILED = "failed"

#: The two schemes a login link may carry. The value is rendered as a link a human clicks,
#: so anything else is refused rather than shown (T-03-30).
_LOGIN_SCHEMES = frozenset({"https", "http"})

logger = logging.getLogger("mcp_connector.oauth.loginflow")


@dataclass(frozen=True, slots=True, repr=False)
class FlowStart:
    """A sign in that Nextcloud has opened: where the user goes, and how we ask about it."""

    poll_token: str
    login_url: str

    def __repr__(self) -> str:
        return f"FlowStart(login_url={self.login_url!r}, poll_token='***')"


@dataclass(frozen=True, slots=True, repr=False)
class AppCredentials:
    """The result of a completed sign in: one user, one dedicated app password."""

    login_name: str
    app_password: str

    def __repr__(self) -> str:
        return f"AppCredentials(login_name={self.login_name!r}, app_password='***')"


@dataclass(frozen=True, slots=True)
class PollResult:
    """One poll, told apart: finished with credentials, not yet, or finally failed."""

    outcome: str
    credentials: AppCredentials | None = None


def safe_user_agent(raw: str) -> str:
    """Turn a client name into a header value that can only be a name.

    The value reaches Nextcloud as the ``User-Agent`` of the start request and is displayed
    to a human who decides whether to trust the app behind it. In plan 03-05 the name comes
    from a dynamic client registration, which is open in the shipped state (D-35), so this
    is attacker input in the strict sense (pitfall 8, T-03-31).

    Three cuts, in this order: everything outside printable ASCII goes, which removes CR and
    LF and with them every header injection; runs of whitespace collapse into one blank, so
    a name cannot draw a layout; the rest is cut to :data:`AGENT_NAME_LIMIT` characters. A
    name that is empty afterwards becomes :data:`AGENT_FALLBACK`, because an empty user
    agent would leave the Nextcloud dialog without any name at all.
    """
    printable = "".join(character for character in (raw or "") if " " <= character <= "~")
    collapsed = " ".join(printable.split())
    if not collapsed:
        collapsed = AGENT_FALLBACK
    return f"{AGENT_PREFIX}{collapsed[:AGENT_NAME_LIMIT]}"


async def start_flow(client_name: str, *, target: NextcloudTarget) -> FlowStart | None:
    """Open a sign in at Nextcloud, or say that it could not be opened.

    ``None`` instead of an exception, for the reason ``status.py`` gives: the caller of this
    function renders a page for a person, and a page that names the next step is a better
    answer than a stack trace turned into a 500 (D-37).
    """
    url = f"{target.base_url}{INIT_PATH}"
    client = shared_client()

    try:
        response = await client.post(url, headers={"User-Agent": safe_user_agent(client_name)})
    except httpx.HTTPError:
        logger.error("the login flow start at %s did not reach Nextcloud", url)
        return None

    if response.status_code != 200:
        logger.error("the login flow start at %s answered %s", url, response.status_code)
        return None

    payload = _payload(response, url)
    poll = payload.get("poll") if isinstance(payload, dict) else None
    token = _text(poll.get("token") if isinstance(poll, dict) else None)
    login = _text(payload.get("login") if isinstance(payload, dict) else None)
    if token is None or login is None:
        logger.error("the login flow start at %s answered a body without a usable flow", url)
        return None

    if urlsplit(login).scheme not in _LOGIN_SCHEMES:
        # The link is shown to a person and clicked by them. A value with another scheme is
        # either a broken instance or an attempt to put something else behind our button.
        logger.error("the login flow start at %s answered a login link with a foreign scheme", url)
        return None

    return FlowStart(poll_token=token, login_url=login)


async def poll_once(poll_token: str, *, target: NextcloudTarget) -> PollResult:
    """Ask Nextcloud once whether the sign in is finished. Exactly one request, ever.

    One request per call is the whole throttling of the waiting page: it refreshes every few
    seconds and every refresh produces one poll and nothing else (T-03-34).

    A 404 is :data:`POLL_PENDING`, and that is deliberately not the same as "expired".
    Nextcloud answers 404 for "not finished yet", for "unknown" and for "expired" alike, so
    the difference cannot come from this answer. It comes from the deadline the caller keeps
    in its own flow record.
    """
    url = f"{target.base_url}{POLL_PATH}"
    client = shared_client()

    try:
        response = await client.post(url, data={"token": poll_token})
    except httpx.HTTPError:
        logger.error("the login flow poll at %s did not reach Nextcloud", url)
        return PollResult(outcome=POLL_FAILED)

    if response.status_code == 404:
        return PollResult(outcome=POLL_PENDING)

    if response.status_code != 200:
        logger.error("the login flow poll at %s answered %s", url, response.status_code)
        return PollResult(outcome=POLL_FAILED)

    payload = _payload(response, url)
    login_name = _text(payload.get("loginName") if isinstance(payload, dict) else None)
    app_password = _text(payload.get("appPassword") if isinstance(payload, dict) else None)
    if login_name is None or app_password is None:
        # A 200 arrives exactly once, so an answer this code cannot read means the sign in is
        # lost: there is no second chance to ask for the same result.
        logger.error("the login flow poll at %s answered a body without credentials", url)
        return PollResult(outcome=POLL_FAILED)

    return PollResult(
        outcome=POLL_DONE,
        credentials=AppCredentials(login_name=login_name, app_password=app_password),
    )


async def revoke_app_password(
    login_name: str, app_password: str, *, target: NextcloudTarget
) -> bool:
    """Remove one app password again, authenticated with exactly that app password.

    The route deletes the token the request authenticated with, which is why the credential
    is both the authentication and the subject here.

    200 and 401 are both success, and that is a deliberate deviation from
    ``nextcloud/clients/ocs.py``, where 401 raises: there the status means "your credential
    is wrong", here it means "this credential no longer exists", which is precisely the end
    state this call wants. Anything else is a failure the caller may report but must not
    depend on: a revocation that hangs on a failed deletion would keep a user connected
    because a cleanup step did not work (pitfall 13, D-37).
    """
    url = f"{target.base_url}{APP_PASSWORD_PATH}"
    client = shared_client()

    try:
        response = await client.request(
            "DELETE",
            url,
            headers=dict(OCS_HEADERS),
            auth=httpx.BasicAuth(login_name, app_password),
            timeout=REVOKE_TIMEOUT,
        )
    except httpx.HTTPError:
        logger.error("the app password deletion at %s did not reach Nextcloud", url)
        return False

    if response.status_code in (200, 401):
        return True

    logger.error("the app password deletion at %s answered %s", url, response.status_code)
    return False


async def account_id(login_name: str, app_password: str, *, target: NextcloudTarget) -> str | None:
    """The canonical account id behind a fresh app password, or ``None``.

    One authenticated OCS request right after the poll. The answer decides who the
    connection belongs to (the principal rule), so anything but a clean 200 with a
    non-empty, printable ``id`` is ``None`` and the caller refuses the sign in. One attempt,
    no retry, and nothing of the exchange is logged (the rules of this module).
    """
    url = f"{target.base_url}{ACCOUNT_PATH}"
    client = shared_client()

    try:
        response = await client.get(
            url,
            headers=dict(OCS_HEADERS),
            auth=httpx.BasicAuth(login_name, app_password),
        )
    except httpx.HTTPError:
        logger.error("the account lookup at %s did not reach Nextcloud", url)
        return None

    if response.status_code != 200:
        logger.error("the account lookup at %s answered %s", url, response.status_code)
        return None

    payload = _payload(response, url)
    ocs = payload.get("ocs") if isinstance(payload, dict) else None
    data = ocs.get("data") if isinstance(ocs, dict) else None
    found = _text(data.get("id") if isinstance(data, dict) else None)
    if found is None or not found.isprintable() or found != found.strip():
        logger.error("the account lookup at %s answered without a usable account id", url)
        return None
    return found


def _payload(response: httpx.Response, url: str) -> Any:
    """The JSON body, or ``None`` when the answer is not JSON at all.

    A Nextcloud that answers HTML here is usually a login page or a proxy error page, and
    the same shape of check exists in ``nextcloud/clients/ocs.py`` for the same reason.
    """
    try:
        return response.json()
    except ValueError:
        logger.error("the answer of %s is not JSON", url)
        return None


def _text(value: object) -> str | None:
    """The value when it is a non empty string, ``None`` otherwise.

    A number, a missing field and an empty string are the same case here: this code refuses
    to build a flow or a credential out of it, instead of carrying the surprise further.
    """
    return value if isinstance(value, str) and value else None

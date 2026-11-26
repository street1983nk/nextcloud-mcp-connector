"""The credential object that every Nextcloud call receives as a parameter.

Immutable and masked: the secret must never show up in a traceback, a log record or a
``repr`` of some container that happens to hold it (threat T-01-07). It is a parameter
object, not module state, because the HTTP passthrough mode changes credentials per
request and a module-global client would be a cross-user leak.
"""

import base64
from collections.abc import Generator
from dataclasses import dataclass

import httpx

#: The two ways a credential object can authenticate. Plain strings and not a ``Literal``
#: on the field: the refusal of a third value below has to stay reachable, and a type that
#: makes the bad case unwritable also makes it untestable.
MODE_BASIC = "basic"
MODE_APPAPI = "appapi"
MODES = (MODE_BASIC, MODE_APPAPI)


@dataclass(frozen=True, slots=True, repr=False)
class Credentials:
    """Base URL without trailing slash, Nextcloud user id and app password.

    The three leading fields carry no default, so every construction site of phase 1 keeps
    working unchanged. The four trailing ones describe the ExApp deployment this object
    belongs to; in the Basic modes they stay empty and nothing reads them.

    In the ``appapi`` mode ``secret`` is ``APP_SECRET``, not a user password: the user id
    travels in the same base64 token, and Nextcloud picks the account from it (AUTH-05).

    Two names, one account (issue 60). ``user`` is what authenticates: the login name in
    the Basic modes, the user id in the ``appapi`` mode. ``account_id`` is the canonical
    Nextcloud user id, and :attr:`account` is what every DAV path and every comparison with
    a user id reads. On LDAP/AD and with a login by email address the two differ, and a DAV
    home below the login name answers 404. ``account_id`` is filled only from the value this
    server stored for the connection (``nc_account_id``, ``oauth/principal.py``), never from
    a request. Empty means "no stored id", and :attr:`account` then falls back to ``user``,
    which is every legacy row, the passthrough mode and stdio, exactly as before. A wrong
    value could never widen access: Nextcloud refuses a DAV home that is not the one of the
    authenticated account.
    """

    base_url: str
    user: str
    secret: str
    mode: str = MODE_BASIC
    app_id: str = ""
    app_version: str = ""
    aa_version: str = ""
    account_id: str = ""

    @property
    def account(self) -> str:
        """The Nextcloud user id of this account: the stored id, else ``user``."""
        return self.account_id or self.user

    @property
    def identity_key(self) -> tuple[str, str, str]:
        """The key of every per account cache: never coarser than ``(base_url, user)``.

        The account id is added to the old key and does not replace it, so an entry can only
        be split further than before and never shared between two accounts that one of the
        two values alone would have kept apart.
        """
        return (self.base_url, self.user, self.account)

    def auth(self) -> httpx.Auth:
        """Return the ``httpx.Auth`` of this mode, one fresh object per call.

        No default branch and no fallback: an unknown mode raises instead of quietly
        authenticating with Basic (D-27). In the ExApp mode a Basic fallback would send
        ``APP_SECRET`` as a user password, which is both an authentication failure and a
        secret sent to the wrong place.
        """
        if self.mode == MODE_APPAPI:
            return AppApiAuth(self)
        if self.mode == MODE_BASIC:
            return httpx.BasicAuth(self.user, self.secret)
        raise ValueError(f"unknown credential mode {self.mode!r}, expected one of {MODES}")

    def __repr__(self) -> str:
        return (
            f"Credentials(base_url={self.base_url!r}, user={self.user!r}, "
            f"account={self.account!r}, mode={self.mode!r}, secret='***')"
        )


class AppApiAuth(httpx.Auth):
    """Sign every outgoing request with the four AppAPI headers of this deployment.

    Stateless by construction: the headers are built once in the constructor and the flow
    yields exactly once. There is no retry branch, because a retry would replay an
    impersonation blindly against an instance that already refused it, and Nextcloud
    counts authentication failures per source IP for every user of this server.

    ``_headers`` stays private and this class carries its own ``__repr__``: the value of
    ``AUTHORIZATION-APP-API`` is base64 of ``"<user>:<APP_SECRET>"``, and base64 is an
    encoding, not a protection, so it is exactly as sensitive as the secret (T-02-13).
    """

    def __init__(self, creds: Credentials) -> None:
        self._app_id = creds.app_id
        self._headers = appapi_auth_headers(
            creds.user,
            app_id=creds.app_id,
            app_version=creds.app_version,
            aa_version=creds.aa_version,
            app_secret=creds.secret,
        )

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        """Add the four headers and hand the request on; nothing else is touched."""
        request.headers.update(self._headers)
        yield request

    def __repr__(self) -> str:
        return f"AppApiAuth(app_id={self._app_id!r})"


def appapi_auth_headers(
    user: str,
    *,
    app_id: str,
    app_version: str,
    aa_version: str,
    app_secret: str,
) -> dict[str, str]:
    """Build the four headers an ExApp sends to Nextcloud, one fresh dict per call.

    ``AUTHORIZATION-APP-API`` is base64 of ``"<user>:<app_secret>"``. base64 is an
    encoding and not a protection, so the result is exactly as sensitive as the secret
    itself: it is never written to a log record and never put into an error message
    (T-02-03). An empty ``user`` is the app context without a user, which is what the
    init progress push uses.

    This lives next to :class:`Credentials` and not in the ``exapp`` package because the
    ``nextcloud`` package must not import from ``exapp``: the fourth credential mode of
    plan 02-02 grows right here, one layer below the ExApp shell.
    """
    token = base64.b64encode(f"{user}:{app_secret}".encode()).decode()
    return {
        "AA-VERSION": aa_version,
        "EX-APP-ID": app_id,
        "EX-APP-VERSION": app_version,
        "AUTHORIZATION-APP-API": token,
    }

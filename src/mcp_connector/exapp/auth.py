"""The incoming AppAPI handshake: three headers become one Nextcloud user id.

This mirrors ``nc_py_api._session.NcSessionApp.sign_check`` with two deliberate
tightenings, both of them inherited from ``deps.StaticBearerVerifier``:

* ``secrets.compare_digest`` on UTF-8 bytes instead of ``!=`` on strings. The comparison
  runs on attacker supplied input, a short circuiting comparison leaks the shared prefix
  over enough requests (T-02-02), and ``compare_digest`` raises ``TypeError`` on non-ASCII
  ``str`` input, which would turn a malformed header into a 500 instead of a 401.
* The received value never leaves this module. It is not part of any exception, it is not
  written anywhere, and no f-string embeds it (T-02-03). ``base64`` is an encoding, not a
  protection: the decoded value contains ``APP_SECRET`` in the clear.

An empty user id is a valid result and means "app context, no user". Refusing data access
for that case belongs to the credential layer, not to this parser.
"""

import base64
import binascii
import secrets
from collections.abc import Mapping, Sequence
from typing import cast

from starlette.requests import Request

from .. import config
from ..errors import ToolError

__all__ = [
    "AppApiRejected",
    "appapi_user",
    "require_appapi",
    "verify_appapi_headers",
]

HEADER_APP_ID = "ex-app-id"
HEADER_APP_VERSION = "ex-app-version"
HEADER_AUTHORIZATION = "authorization-app-api"


class AppApiRejected(Exception):
    """This request is not a valid AppAPI request.

    Carries no message on purpose. Every rejection answers 401 with an empty body: the
    caller is AppAPI, a proxy, not a human and not a model, so the "message plus hint"
    format of the rest of this project would only tell an attacker which of the checks
    failed.
    """


def verify_appapi_headers(headers: Mapping[str, str], app_id: str, app_secret: str) -> str:
    """Return the Nextcloud user id this request runs as, or raise :class:`AppApiRejected`.

    Each of the three is read with :func:`_single`, which refuses a request that carries
    the same header twice.
    """
    received_app_id = _single(headers, HEADER_APP_ID)
    app_version = _single(headers, HEADER_APP_VERSION)
    raw_auth = _single(headers, HEADER_AUTHORIZATION)
    if not received_app_id or not app_version or not raw_auth:
        raise AppApiRejected

    if not _same(received_app_id, app_id):
        raise AppApiRejected

    try:
        decoded = base64.b64decode(raw_auth, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        # The offending value is credential material and stays out of the exception.
        raise AppApiRejected from None

    user, separator, secret = decoded.partition(":")
    if not separator:
        raise AppApiRejected
    if not _same(secret, app_secret):
        raise AppApiRejected
    return user


def require_appapi(request: Request, *, env: Mapping[str, str] | None = None) -> str:
    """Verify one Starlette request against the deploy environment of this process.

    The settings are read per call and never cached in module state: the statelessness
    rule of phase 1 applies here too, and a cached secret would survive a re-registration
    that already invalidated it (pitfall 11).
    """
    settings = config.exapp_settings(env)
    return verify_appapi_headers(request.headers, settings.app_id, settings.app_secret)


def appapi_user(request: Request, *, env: Mapping[str, str] | None = None) -> str:
    """The Nextcloud account this request runs as, or an empty string when there is none.

    The browser surfaces of phase 3 need the same fact the MCP route needs, and they need
    it without an exception: who is sitting in front of this browser (CR-01). HaRP answers
    that question for every request it forwards, on a PUBLIC route as well, by resolving
    the Nextcloud credential of the request and writing the user id into
    ``AUTHORIZATION-APP-API``; the id is empty when the caller sent no credential
    (03-RESEARCH.md, pattern 4). The value is trustworthy because it is signed with
    ``APP_SECRET``, which no caller has, and because the manifest has the proxy strip a
    client set copy of the header before it ever reaches this process.

    Every rejection collapses into the empty string on purpose: a caller that is not signed
    in, one whose headers were tampered with and a process that is not registered as an
    ExApp are one answer here, "this request has no Nextcloud identity", and the caller
    that asks turns that into a refusal. Nothing about which of the three it was reaches a
    response (T-02-03).
    """
    try:
        return require_appapi(request, env=env)
    except (AppApiRejected, ToolError):
        return ""


def _single(headers: Mapping[str, str], name: str) -> str:
    """Return the one value of this header, or reject a request that carries it twice.

    HTTP allows a header to appear more than once, and every reader of such a message
    picks one. Which one differs: a dict comprehension over ``items()`` keeps the last
    value, ``starlette.datastructures.Headers.get`` returns the first (both measured).
    While this module resolved duplicates implicitly, the answer to "which value did we
    verify" depended on whether the proxy in front of us prepends or appends its own copy,
    which is a component outside this repository (WR-01).

    So duplicates are refused instead of resolved. A legitimate AppAPI request never
    carries one, the manifest additionally has the proxy strip the client set copies, and
    a request that still arrives with two is answered like any other rejection: 401,
    empty, no hint about which check fired.

    ``getlist`` is used where the mapping has it, because two values of the same header
    are invisible in ``items()`` of a real Starlette ``Headers`` object; the fallback scan
    covers the plain dict a unit test hands in.
    """
    getlist = getattr(headers, "getlist", None)
    if callable(getlist):
        values = list(cast("Sequence[str]", getlist(name)))
    else:
        values = [value for key, value in headers.items() if key.lower() == name]
    if len(values) > 1:
        raise AppApiRejected
    return values[0] if values else ""


def _same(received: str, expected: str) -> bool:
    """Constant time comparison on UTF-8 bytes, never on the strings themselves."""
    return secrets.compare_digest(received.encode("utf-8"), expected.encode("utf-8"))

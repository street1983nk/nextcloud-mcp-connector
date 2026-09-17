"""The nine error pages of the browser surface, from one table (E1 to E7, plus E8 and E9).

The rule that gives this file its value: the user learns what went wrong and what to do
next, and the attacker learns nothing about which check fired (T-03-24). Those two are in
tension on every error page, and the resolution is that the pages differ in what the user
can do about them, never in what they reveal about the protocol. E1 sends the user to an
administrator, E3 sends them back into their assistant app, E5 warns them that the return
address did not match, and none of the three names an OAuth error code, a parameter, an
internal host or a fragment of a code or token.

Structurally this is ``nextcloud/clients/ocs.py:_status_error``: one table, one function,
one return type, and every branch names the problem plus the next step. The copy lives in
:mod:`.strings` and the status codes live here, so a wording fix never touches a status
code and a status code fix never touches the wording.

Two pages carry more than text. E6 answers 429 and repeats the wait in a ``Retry-After``
header, so an assistant app that reads headers backs off on its own instead of hammering
the throttle (D-37, SC 5). E7 answers 500 and carries a reference that this function
generates and hands back to the caller, which writes it into its one log line. The
reference is random and decodes to nothing: it correlates a user report with a log entry
and is useless to anyone who does not already have the log.

E8 joined the table in phase 4 and is the same shape as the rest: the connections page
without a Nextcloud account behind the browser. 403 and not 401, because a 401 from a page
a browser opened invites the browser's own credential prompt, and this surface never puts a
password prompt in front of a user (04-UI-SPEC.md, E8).

E9 joined in phase 5 (BL-10) and is the neighbour of E8 in more than the table: it is a
refusal of an account and not of a request. It answers the three points at which the per
account switch is enforced while a connection is being made, and it is the only page of the
table whose next step is a page of this app rather than an administrator or the assistant
app: the switch belongs to the reader, so the way out is a link they can follow themselves.
Also 403 without a challenge, the same choice R1 makes at the transport boundary for the
same reason (D-51).
"""

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from starlette.responses import Response

from ... import config
from . import connections, icons, layout, strings

__all__ = [
    "CODES",
    "PAUSED",
    "REFERENCE_ALPHABET",
    "REFERENCE_LENGTH",
    "error_page",
    "new_reference",
]

#: Where "Start over" leads on the timeout page. The authorization route answers a request
#: without a running flow with the empty state, which is the honest landing point after a
#: sign in that timed out.
START_OVER_PATH: Final = "/authorize"

#: Upper case without the characters that are read wrong over a phone: no O, no I, no 0,
#: no 1. An administrator gets this reference from a user and searches the log with it.
REFERENCE_ALPHABET: Final = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

REFERENCE_LENGTH: Final = 8

#: The smallest wait the throttled page may promise. A page that says zero seconds invites
#: exactly the immediate retry the throttle exists against.
MINIMUM_RETRY_SECONDS: Final = 1

#: The generic page, used for anything the caller did not name and for every unknown code.
GENERIC = "E7"

#: The page of an account that paused its own MCP access, named rather than spelled at the
#: three call sites that answer with it (``oauth/consent.py``, ``oauth/connect.py``): a code
#: that travels between modules as a bare string is a code a rename cannot follow.
PAUSED: Final = "E9"


@dataclass(frozen=True, slots=True)
class _ErrorPage:
    """One row of the contract table: status, heading, body and an optional way out."""

    status: int
    title: str
    body: str
    action_label: str = ""
    action_href: str = ""


_PAGES: dict[str, _ErrorPage] = {
    "E1": _ErrorPage(403, strings.ERROR_ALLOWLIST_TITLE, strings.ERROR_ALLOWLIST_BODY),
    "E2": _ErrorPage(
        400, strings.ERROR_REGISTRATION_OFF_TITLE, strings.ERROR_REGISTRATION_OFF_BODY
    ),
    "E3": _ErrorPage(400, strings.ERROR_EXPIRED_TITLE, strings.ERROR_EXPIRED_BODY),
    "E4": _ErrorPage(
        408,
        strings.ERROR_TIMEOUT_TITLE,
        strings.ERROR_TIMEOUT_BODY,
        action_label=strings.ACTION_START_OVER,
        action_href=START_OVER_PATH,
    ),
    "E5": _ErrorPage(400, strings.ERROR_REDIRECT_TITLE, strings.ERROR_REDIRECT_BODY),
    "E6": _ErrorPage(429, strings.ERROR_THROTTLED_TITLE, strings.ERROR_THROTTLED_BODY),
    "E8": _ErrorPage(403, strings.ERROR_SIGN_IN_TITLE, strings.ERROR_SIGN_IN_BODY),
    PAUSED: _ErrorPage(
        403,
        strings.CONNECTIONS_PAUSED_TITLE,
        strings.ERROR_PAUSED_BODY,
        action_label=strings.ACTION_OPEN_CONNECTIONS,
        action_href=connections.CONNECTIONS_PATH,
    ),
    GENERIC: _ErrorPage(500, strings.ERROR_GENERIC_TITLE, strings.ERROR_GENERIC_BODY),
}

#: The nine identifiers of the contract, in the order of the table above, which is not the
#: order of their names (LO-05 of the phase 4 review): ``GENERIC`` is the
#: last row because it is also the fallback of an unknown code, and E8 and E9 joined in front
#: of it rather than behind it. Nothing depends on the order; the comment used to promise one
#: it did not deliver, and a documentation or test that iterates over this would have
#: believed it.
CODES: Final = tuple(_PAGES)


def error_page(
    code: str,
    *,
    env: Mapping[str, str] | None = None,
    client: str = "",
    seconds: int = 0,
) -> tuple[Response, str]:
    """Build one error page, and return it together with its reference.

    The reference is empty for every page except E7, where it is a fresh random value that
    also appears in the rendered text. The caller writes exactly that value into its one
    log line, so the sentence "an administrator can find the details under reference ..."
    is true instead of decorative.

    An unknown code is not a programming error that may escape as a 500 with no body: it
    lands on the generic page, so a caller with a typo still answers something the user can
    act on (fail closed, D-37).
    """
    spec = _PAGES.get(code, _PAGES[GENERIC])
    reference = new_reference() if spec is _PAGES[GENERIC] else ""
    wait = max(MINIMUM_RETRY_SECONDS, int(seconds))

    text = spec.body.format(
        client=layout.client_name(client),
        seconds=wait,
        ref=reference,
        host=_host(env),
    )
    blocks = [layout.paragraph(text)]
    if spec.action_label:
        blocks.append(layout.action(spec.action_label, spec.action_href, env=env))

    headers = {"Retry-After": str(wait)} if spec.status == 429 else None
    response = layout.page(
        spec.title,
        blocks,
        env=env,
        status_code=spec.status,
        headers=headers,
        heading_icon=icons.CROSS,
        heading_tone="error",
    )
    return response, reference


def _host(env: Mapping[str, str] | None) -> str:
    """Where the user signs in, from configuration, never the Host header (T-03-02).

    Filled for every page instead of only for the one that names it, so a body that starts
    naming the host later cannot ship with an unfilled placeholder in it.
    """
    return config.sign_in_host(env)


def new_reference() -> str:
    """A random reference for one answer, drawn from a readable alphabet.

    Random and nothing else on purpose: an identifier that encoded the failing check, the
    client or a timestamp would tell the caller which check fired, which is the one thing
    these pages must not do (T-03-24).
    """
    return "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_LENGTH))

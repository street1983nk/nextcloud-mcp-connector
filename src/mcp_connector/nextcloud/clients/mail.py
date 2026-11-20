"""Mail client: four declared read paths of one app, and no path that writes.

The Mail app answers accounts, mailboxes, message envelopes and one full message below
``/ocs/v2.php/apps/mail/``. This module reads exactly those four and nothing else. Mail is
the most sensitive family this server ever carries, so it is strictly read only, and the
shape of that promise is that the code which could break it was never written.

Both mandatory headers of D-18 are already set by :func:`ocs.ocs_get`, which is why this
module deliberately has no header constant of its own. Tables needs one because its row route
belongs to a generation 1 path that is built directly; every route here goes through the OCS
helper.

Replaceability, and the reason this is the longest paragraph in the file. All four routes in
use stand in the ``openapi.json`` that Mail 5.11.1 ships, and none of them carries
``#[OpenAPI(scope: SCOPE_IGNORE)]``: they are a promised API. Beside them the app has a
second, internal route set below ``/apps/mail/api/`` which the phase 8 spike measured, and
those three listing routes **are** ``SCOPE_IGNORE``, so a Mail release may change or drop
them without any deprecation. They are deliberately not used here. Falling back to them would
be worse in two directions at once. It would trade a declared API for the internals of Mail's
own frontend, and it would make the write prohibition unsayable: ``/api/messages`` is a
resource route, so POST creates, PUT changes and DELETE removes on exactly the path a read
would use, and a path based prohibition cannot tell the four apart. On the declared routes
the send path is a path of its own, which is what makes a prohibition writable and counter
checkable at all. The word ``SCOPE_IGNORE`` is spelled out here because it is the search term
somebody will find this decision under.

The trap of this family is ``limit``. It looks optional, and the app's own OpenAPI
description claims an empty value returns all messages. The controller computes
``min(100, max(1, $limit))``, and ``max(1, null)`` is 1 in PHP 8, so an omitted limit answers
exactly **one** message. :func:`get_messages` therefore takes ``limit`` as a keyword without a
default and caps it here, so a URL without a window cannot be built by construction.

Two statuses mean something on these routes that they mean nowhere else in this project.
**206** on the full message is a success: the message was found and everything but ``body`` is
there, because it could not be decrypted. **500** on the three IMAP backed routes (mailboxes,
envelopes and the full message, which opens an IMAP session on every read) is the everyday
case of a mail server of the user that cannot be reached, or of a mailbox that was never
synchronised, so the sentence points at that account and not at the Nextcloud log. Both
are handled in this module and not in the shared parser, exactly as phase 9 kept Talk's 304
local: they carry this meaning on these routes only, and a global change would loosen the
rules for every other family in silence.

There is deliberately no send, no draft, no move, no flag, no delete, no attachment download,
no tag write and no trusted-sender path in this module. The server promise is that it can
neither send nor change nor remove anything through Mail, and the cheapest way to keep a
promise is to never write the code that could break it (threat T-10-07). A unit test greps the
**code part** of this file for every one of those paths, with docstrings and comments blanked
out after the pattern of ``tests/contract/test_no_destructive_calls.py``, which is exactly
what lets this explanation name them out loud.

In place of a retry rule, which a module without a write path needs no room for: every full
message read opens an IMAP session inside the app (``clientFactory->getClient``, ``logout`` in
the ``finally``), so a loop over the single message route is expensive. The brute force
counter is not the reason. ``#[BruteForceProtection]`` sits on that controller, but
``throttle()`` is never called anywhere in the ``lib/`` tree of Mail 5.11.1, so the counter
does not count.
"""

import re
from typing import Any

import httpx

from ...errors import ToolError
from ..credentials import Credentials
from . import ocs

#: The accounts of the signed in user. No parameters, and the answer carries no IMAP host
#: and no account name, only id, address, delegation flag and aliases, which is exactly as
#: much as a model context should ever see of somebody's mail infrastructure.
ACCOUNTS_PATH = "/apps/mail/account/list"

#: The mailboxes of one account. ``accountId`` is mandatory here, and there is deliberately no
#: default for it anywhere in this family: a guessed account is the kind of answer that looks
#: right.
MAILBOXES_PATH = "/apps/mail/ocs/mailboxes"

#: One window of envelopes. The path carries the ``databaseId`` of the mailbox and not its
#: ``id``, which is base64 of the IMAP name and a frontend detail; confusing the two is the
#: most expensive mistake in this family.
MESSAGES_PATH = "/apps/mail/ocs/mailboxes/{mailbox}/messages"

#: One full message, addressed by the ``databaseId`` of the envelope. It sits directly below
#: ``/apps/mail/`` and has no ``api`` segment: the ``api`` spelling answers a 404 out of the
#: routing layer and makes Mail look unreachable when it is not.
MESSAGE_PATH = "/apps/mail/message/{message}"

#: Not a parameter, a constant. Without ``singleton`` the controller answers the threaded
#: view, a thread root is not a message, and the two are indistinguishable in the payload, so
#: a caller who got this wrong would read a list of threads believing it to be mail. Same
#: principle as ``READ_ONLY_PARAMS`` in the Talk client: what a caller can get wrong is not an
#: argument.
VIEW = "singleton"

#: Upper bound of one window. The app caps at 100 and answers exactly ONE message when
#: ``limit`` is absent, so the value is enforced here rather than offered: a URL without a
#: window cannot be built by construction.
MAX_MESSAGES = 50

#: The full message was found and is complete except for its body, because the body could not
#: be decrypted. That is a success, and it is handled here instead of by widening
#: ``ocs._OK_STATUS``, which would quietly accept a half answer for every other family too.
PARTIAL = 206

_SHAPE_HINT = "Check that the Mail app is enabled and up to date on that instance."

#: The digits an id of this family may consist of, and only those. ``str.isdigit`` would
#: accept a superscript two and an Arabic-Indic digit as well, and both would build a URL
#: the app answers with a cast-to-zero 404 instead of being stopped here (review finding
#: WR-04); ``tools/mail.py`` checks its timestamps with the same pattern for the same reason.
_DIGITS = re.compile(r"[0-9]+")


async def get_accounts(client: httpx.AsyncClient, creds: Credentials) -> list[dict[str, Any]]:
    """List the mail accounts of the signed in user.

    An account holder without a single mail account is answered with 200 and an empty list,
    and that is a success with zero accounts rather than a failure. The difference to "the
    Mail app is not there" has to stay visible in the answer, because the next step differs:
    one is "set up an account in the Mail app", the other is "ask an administrator".
    """
    response = await ocs.ocs_get(client, creds, ACCOUNTS_PATH)
    return _as_list(ocs.parse_ocs(response, what="the mail accounts"), what="mail accounts")


async def get_mailboxes(
    client: httpx.AsyncClient, creds: Credentials, account_id: str | int
) -> list[dict[str, Any]]:
    """List the mailboxes of one account, with their unread counts and special roles.

    The interesting field is ``databaseId``: it is the number every other route of this family
    expects, while ``id`` is base64 of the IMAP name and belongs to the frontend.

    A server error is caught before the shared parser sees it. Measured, an unreachable IMAP
    server answers HTTP 500 with ``ocs.meta.statuscode`` 996, and a mailbox that was never
    synchronised does the same, because ``MailSearch`` raises and ``listMessages`` carries no
    ``#[TrapError]``. The shared ``_check_transport`` turns every status from 500 upwards into
    "this is a problem on the Nextcloud side", which is the wrong next step for the most common
    failure of this family by a wide margin.
    """
    account = _path_id(account_id, "mail account id")
    what = f"the mailboxes of account {account}"
    response = await ocs.ocs_get(client, creds, MAILBOXES_PATH, params={"accountId": account})
    _check_mail_server(response, what)
    return _as_list(ocs.parse_ocs(response, what=what), what="mailboxes")


async def get_messages(
    client: httpx.AsyncClient,
    creds: Credentials,
    mailbox_id: str | int,
    *,
    limit: int,
    filter_string: str | None = None,
    cursor: int | None = None,
) -> list[dict[str, Any]]:
    """Read one window of message envelopes, newest first.

    ``limit`` is a keyword without a default, capped at :data:`MAX_MESSAGES` and lifted to at
    least one, and :data:`VIEW` is always sent, because the URL is built here and nowhere else.

    The order is fixed to newest first inside the app and there is no sort parameter at all.
    The cursor filters ``sent_at <`` strictly, so it is the ``dateInt`` of the oldest envelope
    of the current page; a negative one becomes zero. Two filters the app applies by itself,
    whatever is asked for: inside a flagged mailbox only flagged messages, and outside the
    trash no deleted ones.

    An empty filter is left out entirely rather than sent: the app turns an empty string into
    ``null``, so leaving it out has the same effect with a shorter URL. Same 500 branch as
    :func:`get_mailboxes`, and for the same measured reason.
    """
    mailbox = _path_id(mailbox_id, "mailbox id")
    params: dict[str, Any] = {
        "limit": min(max(int(limit), 1), MAX_MESSAGES),
        "view": VIEW,
    }
    wanted = (filter_string or "").strip()
    if wanted:
        params["filter"] = wanted
    if cursor is not None:
        params["cursor"] = max(int(cursor), 0)

    what = f"the messages of mailbox {mailbox}"
    path = MESSAGES_PATH.format(mailbox=mailbox)
    response = await ocs.ocs_get(client, creds, path, params=params)
    _check_mail_server(response, what)
    return _as_list(ocs.parse_ocs(response, what=what), what="messages")


async def get_message(
    client: httpx.AsyncClient, creds: Credentials, message_id: str | int
) -> tuple[dict[str, Any], bool]:
    """Read one full message, and say whether its body is missing.

    The second element of the answer is ``True`` exactly when the app answered
    :data:`PARTIAL`: the message was found and everything but ``body`` is present, because it
    could not be decrypted. That is a success, so it is recognised before the shared parser
    sees it, which would read the 206 in ``ocs.meta.statuscode`` as an unexpected status.

    An unknown or foreign message id is answered with 404, and the app puts its own wording
    into ``ocs.data`` as the plain string "Account not found." while ``meta.message`` stays
    empty. The shared status mapping reads ``meta.message``, so that sentence is dropped, and
    here that is a gain rather than a loss: a sentence about somebody else's account would say
    that a message exists that this user may not see.

    The 500 branch of the two list routes stands here as well, and here most of all: this is
    the route that opens an IMAP session inside the app on every read, so a dead mail server
    hits it first (measured against GreenMail in the phase 8 spike: HTTP 500 "Could not
    connect to IMAP server."). Without the check the shared transport turn would send the
    user to the Nextcloud log about a machine that is not at fault.
    """
    message = _path_id(message_id, "message id")
    response = await ocs.ocs_get(client, creds, MESSAGE_PATH.format(message=message))
    _check_mail_server(response, f"the message {message}")
    if response.status_code == PARTIAL:
        return _partial_message(response), True
    payload = ocs.parse_ocs(response, what=f"the message {message}")
    return _as_dict(payload, what="a message"), False


def _path_id(value: str | int, what: str) -> str:
    """Ids are numeric in Mail; anything else is a bug or an attempt (threat T-10-06).

    The app offers no protection to lean on: a non numeric id is cast to 0 by PHP and answered
    with 404, so there is no routing error that would stop it. The guard costs nothing and it
    keeps the most expensive call of this family away from a value that is certainly wrong.
    """
    text = str(value).strip()
    if not _DIGITS.fullmatch(text):
        raise ToolError(
            message=f"{value!r} is not a numeric {what}.",
            hint="Use an id exactly as mail_browse reports it; Mail addresses by number.",
        )
    return text


def _check_mail_server(response: httpx.Response, what: str) -> None:
    """Name the failure the IMAP backed routes actually have, before the shared parser generalises.

    ``ocs._check_transport`` catches every status from 500 upwards before the envelope is even
    read, so this check has to run first and cannot wait for a raised error to inspect.
    """
    if response.status_code < 500:
        return
    raise ToolError(
        message=f"The Mail app could not read {what} from the mail server of this account.",
        hint=(
            "Open Mail in Nextcloud and check that account: the usual causes are a mail "
            "server that cannot be reached, a password the mail server rejects, or a mailbox "
            "that has not been synchronised yet."
        ),
    )


def _partial_message(response: httpx.Response) -> dict[str, Any]:
    """Read the payload of a :data:`PARTIAL` answer, which the shared parser refuses by design.

    Exactly one status on exactly one route reaches this function, which is why the envelope
    is read here rather than by widening the shared success set for every family at once.
    """
    try:
        payload = response.json()
    except ValueError:
        payload = None
    envelope = payload.get("ocs") if isinstance(payload, dict) else None
    data = envelope.get("data") if isinstance(envelope, dict) else None
    return _as_dict(data, what="a message")


def _as_list(payload: Any, what: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ToolError(
            message=f"Nextcloud answered with something that is not a list of {what}.",
            hint=_SHAPE_HINT,
        )
    return [item for item in payload if isinstance(item, dict)]


def _as_dict(payload: Any, what: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ToolError(
            message=f"Nextcloud answered with something that is not {what}.",
            hint=_SHAPE_HINT,
        )
    return payload

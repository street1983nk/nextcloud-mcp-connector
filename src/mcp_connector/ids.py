"""Prefixed resource IDs, encoded and parsed in exactly one place.

``fetch`` is the only caller that has to route an ID back to a resource type, and a
malformed prefix there resolves a card as a note without any error. One codec plus a
roundtrip test makes that class of bug testable.

Formats::

    file:<fileid>
    note:<id>
    card:<boardId>:<stackId>:<cardId>      (short form card:<cardId> is accepted)
    event:<calendarUri>:<objectName>
    mail:<databaseId>                      (the databaseId of the message, and no other
                                            number: one message carries uid, remoteId,
                                            messageId and, in the full answer, id as well,
                                            and all four of them address nothing here)
    message:<token>:<messageId>            (the conversation token plus the message id of
                                            that same conversation: a Talk search entry
                                            carries threadId and the client knows
                                            referenceId, and neither of them addresses a
                                            single message on the context route)
    table:<tableId>                        (a table, never a view: the tables search
                                            provider builds #/view/<id> for views, and a
                                            view id used as a table id reads a foreign
                                            table or answers 404)
    task:<list>:<object>                   (the key of a task list plus the object name; for
                                            a shared list the key is neutral, see
                                            task_list_key, and never the URI)
    url:<absolute-url>                     (honest rest category, see pitfall 10)
"""

import hashlib
import re

from .errors import REASON_GUARD_TRIPPED, ToolError

SEPARATOR = ":"

# Every refusal of this module is a guard of this server and never an answer of Nextcloud, so
# every raise site below carries ``reason=REASON_GUARD_TRIPPED``. It is set at the raise site
# and not at a status mapping because there is no status here: nothing has left this process
# yet (D-17).
_HINT = (
    "Use an id exactly as returned by a search tool: file:<fileid>, note:<id>, "
    "card:<board>:<stack>:<card>, event:<calendar>:<object>, mail:<databaseId>, "
    "message:<token>:<messageId>, table:<tableId>, task:<list>:<object> "
    "or url:<absolute-url>."
)

#: The marker Nextcloud puts between the URI of a shared calendar or task list and the
#: account id of the person who shared it: ``<uri>_shared_by_<account id>``.
SHARED_BY_MARKER = "_shared_by_"

#: Hex characters of the sha256 that make up the key of a shared task list.
_SHARED_KEY_HEX = 16

#: The digits a mail id may consist of, and only those. ``str.isdigit`` would accept a
#: superscript two and an Arabic-Indic digit as well (the same reason ``tools/mail.py``
#: checks its timestamps with this pattern), and both would build a URL the app answers
#: with a cast-to-zero 404 instead of stopping here (review finding WR-04).
_DIGITS = re.compile(r"[0-9]+")

#: The token alphabet of a Talk conversation, four to thirty lowercase letters and digits.
#: This is the same expression as ``nextcloud/clients/talk.py::_TOKEN``, written out a second
#: time on purpose: this module is the codec every tool imports, and it must not depend on the
#: client layer (a codec that imports a client turns one wrong id into an import cycle).
_TOKEN = re.compile(r"[a-z0-9]{4,30}")


def encode_file(fileid: str | int) -> str:
    return _join("file", str(fileid))


def encode_note(note_id: str | int) -> str:
    return _join("note", str(note_id))


def encode_mail(message_id: str | int) -> str:
    """The ``databaseId`` of one message, and deliberately nothing else.

    A message carries ``uid``, ``remoteId``, ``messageId`` and, in the full answer, ``id``
    beside it. Every one of those is a number that looks usable and addresses nothing on the
    full text route, which is why only one function of this module builds a mail id at all.
    """
    return _join("mail", str(message_id))


def encode_message(token: str, message_id: str | int) -> str:
    """One message of one conversation: the token names the room, the number the message.

    A Talk search entry ships ``threadId`` beside ``messageId``, and the chat client knows a
    ``referenceId`` as well. Neither of them addresses a single message on the context route,
    which is why only this function builds a message id.
    """
    return _join("message", token, str(message_id))


def encode_table(table_id: str | int) -> str:
    """The id of a table, and deliberately never the id of a view.

    The tables search provider builds ``#/table/<id>`` and ``#/view/<id>`` from the same
    template, and the client of this project reads tables only. A view id handed in here would
    address a different table or answer 404 (threat T-11-01).
    """
    return _join("table", str(table_id))


def encode_card(board_id: str | int, stack_id: str | int, card_id: str | int) -> str:
    return _join("card", str(board_id), str(stack_id), str(card_id))


def encode_card_short(card_id: str | int) -> str:
    """The one segment card form, and the only place that is allowed to build it.

    :func:`parse` accepts ``card:<cardId>`` beside the full triple, because the Deck search
    provider knows neither board nor stack, and an invented one would address a card that
    does not exist. This function is the encode side of that acceptance: without it the one
    caller who needs the short form has to build the prefix itself, and then this module is
    no longer the only place a card id comes from.
    """
    return _join("card", str(card_id))


def encode_event(calendar_uri: str, object_name: str) -> str:
    return _join("event", calendar_uri, object_name)


def task_list_key(uri: str) -> str:
    """The key that stands for a task list in an id and in every answer (D-32-14).

    An own list keeps its URI, readable like the calendar of an ``event:`` id. The URI of a
    shared list reads ``<uri>_shared_by_<account id>`` and so names the person who shared
    it, which no answer of the tasks bundle may do; its key is ``s`` plus the first sixteen
    hex characters of the sha256 of the URI instead. That key is pseudonymous, not
    anonymous: whoever guesses the URI and the account id can compute it. It stays stable
    as long as the share exists. An own list whose URI happens to have the form ``s`` plus
    sixteen hex characters could collide with it; the caller resolves a key against the
    discovery, where two lists with one key are an ambiguity and an error, never a guess.

    A pure function in this module and not in the client, because the codec must not import
    the client layer and both the client and the provider map need the same key.
    """
    if SHARED_BY_MARKER not in uri:
        return uri
    digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()
    return "s" + digest[:_SHARED_KEY_HEX]


def encode_task(list_key: str, object_name: str) -> str:
    """One task: the key of its list (see :func:`task_list_key`) and its object name."""
    return _join("task", list_key, object_name)


def encode_url(url: str) -> str:
    """The rest category: everything we cannot address by a stable Nextcloud id."""
    value = (url or "").strip()
    if not value:
        raise ToolError(
            message="Cannot build an id from an empty url.", hint=_HINT, reason=REASON_GUARD_TRIPPED
        )
    return f"url{SEPARATOR}{value}"


def parse(raw: str) -> tuple[str, tuple[str, ...]]:
    """Return ``(kind, parts)`` or raise :class:`ToolError` with a hint."""
    value = (raw or "").strip()
    kind, separator, rest = value.partition(SEPARATOR)
    if not separator or not kind or not rest:
        raise ToolError(
            message=f"{raw!r} is not a valid resource id.", hint=_HINT, reason=REASON_GUARD_TRIPPED
        )

    if kind == "url":
        # Both halves of this guard stand here and not in the caller, and the yardstick is the
        # mirror side: ``encode_url`` builds ``url:`` plus ``url.strip()`` and refuses an empty
        # value, so exactly that set and no larger one may be read back (review finding IN-04).
        # The whitespace only rest is refused today already, but only by way of the outer
        # ``strip`` above, which stands there for a different reason; it is written out here so
        # the promise does not hang on a foreign line. Leading whitespace is the half that is
        # really reachable: ``url:  https://x`` used to parse into a value ``encode_url`` can
        # never have built. Inner whitespace stays allowed on purpose, because
        # ``encode_url("https://a b")`` builds exactly that, and a refusal would be stricter
        # than the encode side and would only turn the asymmetry around.
        if not rest.strip() or rest != rest.strip():
            raise ToolError(
                message=f"{raw!r} is not a valid resource id.",
                hint=_HINT,
                reason=REASON_GUARD_TRIPPED,
            )
        return "url", (rest,)
    if kind in ("file", "note"):
        # One segment, and the separator may not hide inside it: ``_join`` refuses the
        # separator in every part, so ``note:4:2`` and ``file:a:b`` are ids this module can
        # never have built, and exactly the set the encode side builds may be read back
        # (the same yardstick the ``url`` branch above wrote down, review finding WR-03).
        if SEPARATOR in rest:
            raise ToolError(
                message=f"{raw!r} is not a valid resource id.",
                hint=_HINT,
                reason=REASON_GUARD_TRIPPED,
            )
        parts = (rest,)
    elif kind == "mail":
        parts = (rest,)
        # The digit guard stands here and not only in the mail client, and that is the whole
        # difference to ``file`` and ``note``: ``mail:abc`` has to fail without a single
        # request. The full text route is the most expensive call of that family, because
        # every read of it opens an IMAP session inside the Mail app, and the app offers
        # nothing to lean on: PHP casts a non numeric id to 0 and answers 404, so there is no
        # routing error that would stop a wrong value on the way out (pitfall 11).
        if not _DIGITS.fullmatch(rest):
            raise ToolError(
                message=f"{raw!r} is not a valid mail id.", hint=_HINT, reason=REASON_GUARD_TRIPPED
            )
    elif kind == "message":
        parts = tuple(rest.split(SEPARATOR, 1))
        if len(parts) != 2:
            raise ToolError(
                message=f"{raw!r} is not a valid Talk message id.",
                hint=_HINT,
                reason=REASON_GUARD_TRIPPED,
            )
        # Both guards stand here and not only in the Talk client, for the same reason the mail
        # guard does: an id out of a model answer becomes part of the URL path of the context
        # route, so ``message:ABC:1`` has to be refused without a single request. The token
        # alphabet is the cheap half of that (a wrong token is a request against a room that
        # never existed), the digit check is the other one (the app casts a non numeric message
        # id to 0 and answers with the oldest messages instead of refusing it).
        if not _TOKEN.fullmatch(parts[0]) or not _DIGITS.fullmatch(parts[1]):
            raise ToolError(
                message=f"{raw!r} is not a valid Talk message id.",
                hint=_HINT,
                reason=REASON_GUARD_TRIPPED,
            )
    elif kind == "table":
        parts = (rest,)
        # Same reason as ``mail``: a non numeric table id would reach the URL path, and the app
        # casts it to 0 and answers 404 instead of refusing it.
        if not _DIGITS.fullmatch(rest):
            raise ToolError(
                message=f"{raw!r} is not a valid table id.", hint=_HINT, reason=REASON_GUARD_TRIPPED
            )
    elif kind == "card":
        parts = tuple(rest.split(SEPARATOR))
        if len(parts) not in (1, 3):
            raise ToolError(
                message=f"{raw!r} is not a valid card id.",
                hint=_HINT,
                reason=REASON_GUARD_TRIPPED,
            )
    elif kind == "event":
        # A full split instead of ``maxsplit=1``: ``_join`` refuses the separator in the
        # calendar uri and in the object name alike, so ``event:a:b:c`` is an id the encode
        # side can never have built, and a third segment must be refused rather than folded
        # into the object name (review finding WR-03).
        parts = tuple(rest.split(SEPARATOR))
        if len(parts) != 2:
            raise ToolError(
                message=f"{raw!r} is not a valid event id.", hint=_HINT, reason=REASON_GUARD_TRIPPED
            )
    elif kind == "task":
        # The same full split as ``event``, for the same reason: ``_join`` refuses the
        # separator in the list key and in the object name, so a third segment is an id the
        # encode side can never have built.
        parts = tuple(rest.split(SEPARATOR))
        if len(parts) != 2:
            raise ToolError(
                message=f"{raw!r} is not a valid task id.", hint=_HINT, reason=REASON_GUARD_TRIPPED
            )
    else:
        raise ToolError(
            message=f"Unknown id type {kind!r}.", hint=_HINT, reason=REASON_GUARD_TRIPPED
        )

    if any(not part.strip() for part in parts):
        raise ToolError(
            message=f"{raw!r} has an empty segment.", hint=_HINT, reason=REASON_GUARD_TRIPPED
        )
    return kind, parts


def _join(kind: str, *parts: str) -> str:
    for part in parts:
        if not part or not part.strip():
            raise ToolError(
                message=f"Cannot build a {kind} id from an empty value.",
                hint=_HINT,
                reason=REASON_GUARD_TRIPPED,
            )
        if SEPARATOR in part:
            raise ToolError(
                message=f"A {kind} id segment must not contain {SEPARATOR!r} (got {part!r}).",
                hint="Report this as a bug: ids are built from Nextcloud values, not user input.",
                reason=REASON_GUARD_TRIPPED,
            )
    return SEPARATOR.join((kind, *parts))

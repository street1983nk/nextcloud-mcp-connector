"""The handler behind ``occ mcp_connector:audit:read``: the rows of the log, on a console.

AUDIT-04 asks for a way to read the audit log and to hand it over, and it asks for it on the
command line and not in a browser. The query itself lives in ``audit/store.py``
(:meth:`~mcp_connector.audit.store.AuditStore.read_entries`, plan 19-04) and answers in raw
rows; this module is the half that turns those rows into lines an administrator reads and into
a document a script reads. It is the twin of ``exapp/audit_verify.py`` and shares four of its
decisions, each one written out here because each one is one somebody will want to undo.

**Why there is no route in the manifest, and why the absence is the control.** The occ command
reaches this handler over AppAPI's ``PublicFunctions``, the same internal path ``/heartbeat``,
``/init``, ``/enabled``, ``/purge`` and ``/audit-verify`` arrive on, so it needs no declaration
to work. Declaring one would publish the content of the audit log of this instance to the
internet, because the PHP proxy attaches valid AppAPI headers itself and protects none of these
paths (T-02-20, T-18-07). This answer names chains, and a chain of a person is named after her
account, so a declared route would hand the list of everybody who ever used this app to anyone
who can reach that proxy, and one option further the tools they called. HaRP blocks a path that
is declared nowhere; the proxy does not. So the absence in ``appinfo/info.xml`` is not an
omission to be tidied up later, it is the access control, and it is held by a test that asserts
this path appears in none of the thirteen declared routes. On top of it
:func:`audit_read_routes` runs the same double check ``exapp/purge.py`` and
``exapp/audit_verify.py`` run: ``x-origin-ip`` means the PHP proxy and is answered with 404,
then ``require_appapi``, and neither rejection says which of the two spoke.

**Why every answer carries status 200, and what it costs.** Measured against app_api v34.0.3,
``ExAppOccService::buildCommand`` (``lib/Service/ExAppOccService.php:159-213``) writes the body
of the answer to the console verbatim, but only after a status check: on any status other than
200 it prints ``[<app>] command executeHandler failed`` and returns 1, and the body is dropped
unread. A store that could not be opened would therefore lose the one sentence that says so. So
the verdict travels in the body and the status is 200 even then. The price is named rather than
hidden: the exit code of the command is always 0, so a monitoring script cannot watch the
return value. The machine readable shape cushions that with its first key, ``read``, which is
what a script watches instead (the same trade ``audit_verify`` makes with ``checked``, T-18-20).

**Why a ceiling and no streaming.** 100 MB of this store are roughly 440.000 rows, and AppAPI
calls the handler of an occ command with ``timeout => 0``, so nothing outside this process cuts
a long read short. A ``StreamingResponse`` through HaRP and the AppAPI PHP layer is nowhere
measured in this project, and an unmeasured answer shape is not what a ceiling gets replaced
with: the read is bounded instead, by :data:`~mcp_connector.audit.store.READ_LIMIT_DEFAULT`
when nobody said a number and by :data:`~mcp_connector.audit.store.READ_LIMIT_MAX` whatever
anybody says. Every answer names the ceiling it applied, so a cut section of the log cannot be
mistaken for the whole one.

**Why the text shows the newest first and the document the order of the chain.** The store
hands rows over youngest first, which is what somebody looking at a console wants and the only
direction a limit can be combined with (plan 19-04). A file that is kept, however, is read in
the order the chain has, because the chain is what makes it checkable: so the machine readable
shape reverses the list and the text does not. The reversal happens here and not in the store,
for the reason the docstring of ``read_entries`` gives.
"""

import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from ..audit.store import (
    ACTOR_LIMIT,
    CHAIN_INSTANCE,
    CLIENT_NAME_LIMIT,
    READ_LIMIT_DEFAULT,
    READ_LIMIT_MAX,
    AuditStore,
    _entry_of_row,
    user_chain,
)
from ..audit.text import printable
from ..errors import ToolError
from .auth import AppApiRejected, require_appapi
from .responses import NO_STORE, BodyTooLarge, BodyUnreadable, bounded_body, json_response

__all__ = [
    "AUDIT_READ_PATH",
    "JSON_OPTION",
    "LIMIT_OPTION",
    "SINCE_OPTION",
    "USER_OPTION",
    "audit_read_routes",
]

#: The path of the one route of this module, and the name the occ command registration hands
#: to AppAPI as its ``execute_handler`` (``exapp/occ.py`` derives that from this constant, so
#: the two cannot drift apart). It appears in no ``<url>`` of the manifest, on purpose and as
#: the access control itself; see the module docstring.
AUDIT_READ_PATH = "/audit-read"

#: Which chain to read. An account name, or :data:`INSTANCE_KEYWORD` for the chain of the
#: instance. Without it every chain is read.
USER_OPTION = "user"

#: How many whole days back to read, counted from the moment of the call.
SINCE_OPTION = "since"

#: How many entries at most. The default and the ceiling are the two numbers of the store.
LIMIT_OPTION = "limit"

#: The one option that is a shape and not a filter: with it the same answer arrives as JSON.
#: Spelled here rather than imported from ``exapp/audit_verify.py``, with the reason that
#: module gives for the same duplication: ``lifecycle`` imports ``occ``, ``occ`` imports the
#: handler modules, and an import back would close a cycle. A test in
#: ``tests/unit/test_exapp_audit_read.py`` holds the two spellings equal, so they cannot drift
#: apart without somebody deciding it.
JSON_OPTION = "json"

#: The envelope AppAPI wraps an occ invocation in. Measured against a running AppAPI 34.0.0 in
#: plan 05-08 and unchanged since: ``ExAppOccService::buildCommand`` calls
#: ``PublicFunctions::exAppRequest`` with ``params: ['occ' => ['arguments' => ...,
#: 'options' => ...]]``, and ``AppAPIService::prepareRequestToExApp`` turns ``params`` into the
#: JSON body of a POST. So the body of a real invocation is ``{"occ": {"arguments": null,
#: "options": {"user": "alice"}}}`` and the options sit one level below the top.
OCC_ENVELOPE = "occ"

#: Set on the proxy path, never by HaRP and never on the internal AppAPI path. The same header
#: ``exapp/lifecycle.py``, ``exapp/purge.py`` and ``exapp/audit_verify.py`` refuse, spelled a
#: fourth time rather than imported, for the reason at :data:`JSON_OPTION`. A test holds all
#: four spellings equal.
HEADER_ORIGIN_IP = "x-origin-ip"

#: The largest body this handler reads before deciding it is not an occ invocation. The real
#: one is three option names and their values; anything above this is not AppAPI and is not
#: parsed (the rule of ``exapp/purge.py`` and of ``oauth/connections.py``).
MAX_BODY_BYTES = 4096

#: How many digits an announced length may carry before it is refused unread. Ten digits are
#: ten gigabytes, so a longer run is above :data:`MAX_BODY_BYTES` whatever it says, and it is
#: never converted: since Python 3.11 :func:`int` refuses a run of more than 4300 digits and
#: raises, which would answer a header with a 500 (R-18-08, closed in plan 19-01).
MAX_ANNOUNCED_DIGITS = 10

#: How many digits the value of a numeric option may carry, and a second number rather than a
#: use of the one above, because the two bound different things: that one bounds a claim about
#: a body, this one bounds a claim about a count. Ten digits are above every ceiling of this
#: module whatever they say, so the length of the run is decided before its value and
#: :func:`int` never sees a run it refuses to convert.
MAX_OPTION_DIGITS = 10

#: The words that mean "yes" when :data:`JSON_OPTION` arrives with a value. The list of
#: ``exapp/purge.py`` and ``exapp/audit_verify.py``, spelled here for the reason that module
#: gives: a value that arms a switch of this app reads the same everywhere, and a change made
#: for one command must not silently change how another one is invoked. A test holds them equal.
TRUE_WORDS = frozenset({"1", "true", "yes", "on"})

#: What a chain identifier and an account name are cut to before they are printed. Eighty
#: characters are what one line of this answer can carry. The same number as
#: ``exapp/audit_verify.CHAIN_LIMIT``, spelled here for the reason at :data:`TRUE_WORDS` and
#: held equal by a test: a width changed for the verdict of the check must not silently change
#: the width of a column of the read.
CHAIN_LIMIT = 80

#: The name of the instance chain as an administrator types it. The chain of the instance has
#: no account behind it (its ``nc_user`` column is ``NULL``, D-03), so ``--user`` could not
#: address it at all otherwise, and it is the chain that carries the switch of the log and the
#: markers for the chains that are gone. The price is named rather than hidden: an account that
#: is really called ``instance`` is not addressable through this option, and its chain is read
#: by a call without ``--user``.
INSTANCE_KEYWORD = "instance"

#: How far back ``--since`` may reach, in days. Ten years is longer than this app has existed
#: and longer than any retention window it has, so a larger number is the whole log and is read
#: as such instead of being refused.
MAX_SINCE_DAYS = 3650

#: Seconds in a day, so a window is written in days at the one place it is computed.
_DAY_SECONDS = 86400

#: How a moment is printed: UTC, to the second. The rows carry Unix seconds, and a console line
#: with a timezone of its own reader in it cannot be compared with the line above it.
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

#: What a column that holds no value looks like. A single dash and never ``None``: ``None`` is
#: the word of a language and this is a line for a person.
NULL_FIELD = "-"

#: Between two columns of a line. Spaces around the dash, because a value may carry a dash and
#: none of them carries a space next to one after
#: :func:`mcp_connector.audit.text.printable` has run.
FIELD_SEPARATOR = " - "

#: The line for a section of the log with nothing in it. It says nothing about the account
#: behind the filter: "no such account" and "this account called nothing in this window" are
#: the same answer here on purpose, because the difference is what a stranger would want.
NO_ENTRY = "no entry in this part of the log, which says nothing about whether an account exists"

#: The last line of every answer, in both shapes. Two things, and both of them belong in the
#: answer rather than only in this file, because whoever has to judge a read is the person at
#: the console: this answer is bounded, and the first line says by which number, and it is not
#: a statement about the chain. A read that shows an entry does not say the entry is unchanged;
#: the command that walks the chain is the other one.
READ_NOTE = (
    "This read stops at the number of entries the first line names, and asking for more costs "
    "one option. It says nothing about whether the chain behind these entries is unbroken, "
    "which is what occ mcp_connector:audit:verify answers."
)

logger = logging.getLogger("mcp_connector.exapp.audit_read")

#: How a caller hands in its own store, the shape ``exapp/purge.py`` uses for the OAuth one.
type StoreProvider = Callable[[], Awaitable[AuditStore]]


def audit_read_routes(
    env: Mapping[str, str] | None = None, *, store_provider: StoreProvider
) -> list[Route]:
    """The one route of the read, handed out rather than registered on the server object.

    A factory for the reason D-23 gives and ``exapp/lifecycle.py`` states: a registration on
    the shared MCP server object would make this path appear in the standalone HTTP mode of
    phase 1 as soon as anything imports this module, and that mode has no AppAPI identity to
    check it against.
    """

    async def audit_read(request: Request) -> Response:
        """Read the rows this invocation asked for, then print them or hand them over."""
        guarded = _guard(request, env)
        if isinstance(guarded, Response):
            return guarded

        payload = await _payload(request)
        as_json = _set_in(payload)
        chain = _chain_of(payload)
        since = _since_of(payload)
        limit = _bounded_number(
            _value(payload, LIMIT_OPTION), LIMIT_OPTION, READ_LIMIT_DEFAULT, READ_LIMIT_MAX
        )

        try:
            store = await store_provider()
            rows = await store.read_entries(chain=chain, since=since, limit=limit)
            # The rendering is inside the same try on purpose: a row of a file somebody wrote
            # past this app can carry a moment no calendar has or a ``params`` column that is
            # not JSON, and a 500 is the one answer this handler must never give (T-18-20).
            body = _machine_readable(rows, limit) if as_json else _report(rows, limit)
        except Exception as exc:
            # The type only, never the message: a store error can carry a path.
            logger.error("the audit log could not be read: %s", type(exc).__name__)
            if as_json:
                return json_response({"read": False, "error": type(exc).__name__})
            return _text(f"the audit log could not be read: {type(exc).__name__}")

        logger.info("the audit log was read: %s entries, at most %s", len(rows), limit)
        if isinstance(body, str):
            return _text(body)
        return json_response(body)

    return [Route(AUDIT_READ_PATH, audit_read, methods=["POST"])]


def _report(rows: Sequence[tuple[Any, ...]], limit: int) -> str:
    """The answer an administrator reads: a head, one line per entry, and the note.

    Newest first, the order the store hands rows over in, so the head says so: a list whose
    direction is not written down is one that gets read in the other one. Exactly one line per
    entry, which is what makes :func:`mcp_connector.audit.text.printable` necessary two columns
    further down: a name with a line break in it could otherwise add a line of its own to this
    answer and say whatever it likes in it (T-18-08, T-19-22).
    """
    lines = [f"{_count(len(rows), 'entry', 'entries')}, newest first, at most {limit} per read"]
    lines.extend([NO_ENTRY] if not rows else [_line(row) for row in rows])
    lines.append(READ_NOTE)
    return "\n".join(lines) + "\n"


def _count(number: int, one: str, many: str) -> str:
    """A number with the word behind it in the right number, the helper of ``audit_verify``."""
    return f"{number} {one}" if number == 1 else f"{number} {many}"


def _line(row: tuple[Any, ...]) -> str:
    """One entry on one line, in the order the plan of 19-06 fixed.

    Four of these columns are written by somebody who is not this app: the chain identifier
    carries an account name, the client name comes out of a dynamic registration, and the
    acting party is the ``azp`` of a token issued in a foreign realm (AUDIT-07). All of them
    go through :func:`mcp_connector.audit.text.printable`, the one rule of this application
    for such a value. The rest are identifiers this app writes itself, and ``params`` is a
    list of parameter *names*: no parameter value is stored (D-06, AUDIT-01), so none can be
    printed.

    The acting party stands directly behind the client name because the two are the two
    names a call can carry, and a reader compares them: an empty client name next to a
    filled acting party is what a call over the token exchange path looks like.
    """
    entry = _entry_of_row(row)
    return FIELD_SEPARATOR.join(
        (
            _field(row[0]),
            _moment(entry.at),
            printable(entry.chain, limit=CHAIN_LIMIT),
            _field(entry.tool),
            _cleaned(entry.client_name, CLIENT_NAME_LIMIT),
            _cleaned(entry.actor, ACTOR_LIMIT),
            _field(entry.outcome),
            _field(entry.reason),
            _field(entry.duration_ms),
            _names(entry.params),
        )
    )


def _field(value: object) -> str:
    """One column of a line, and :data:`NULL_FIELD` for a column that holds nothing."""
    return NULL_FIELD if value is None else str(value)


def _cleaned(value: str | None, limit: int) -> str:
    """A value from a stranger, made safe to print, and :data:`NULL_FIELD` when there is none.

    A name that is nothing but characters that cannot be printed leaves an empty string
    behind, and an empty column between two separators reads like a fault of this handler, so
    it becomes the same dash a missing value gets.
    """
    if value is None:
        return NULL_FIELD
    return printable(value, limit=limit) or NULL_FIELD


def _names(params: Sequence[str]) -> str:
    """The parameter names of one call, or :data:`NULL_FIELD` for a call that had none."""
    return ",".join(params) if params else NULL_FIELD


def _moment(at: object) -> str:
    """A Unix second as UTC, to the second, or :data:`NULL_FIELD` when it is not a moment.

    Total on purpose. Every row this app writes carries ``int(time.time())``, but a row of a
    file that somebody wrote past this app can carry any number at all, and one such row must
    cost its own column and never the whole answer.
    """
    if not isinstance(at, int) or isinstance(at, bool):
        return NULL_FIELD
    try:
        return datetime.fromtimestamp(at, UTC).strftime(TIME_FORMAT)
    except (OSError, OverflowError, ValueError):
        return NULL_FIELD


def _machine_readable(rows: Sequence[tuple[Any, ...]], limit: int) -> dict[str, Any]:
    """The same answer for a script, with the same 200 under it.

    ``read`` exists because the exit code cannot carry it: the command answers 0 whatever it
    found, for the reason the module docstring measures, so this key is what a script watches
    instead. ``truncated`` is the second thing a script needs and a person reads off the head
    line: as many entries as the ceiling allows means there may be more behind them.

    ``entries`` carries the entries in the order of the **chain**, so the list is the reverse
    of what the store hands over. The store answers youngest first, because that is the only
    direction a limit can be combined with (plan 19-04); a document that is kept is read in
    the order the chain has, because that order is what makes it checkable.
    """
    return {
        "read": True,
        "count": len(rows),
        "limit_applied": limit,
        "truncated": len(rows) == limit,
        "entries": [_document(row) for row in reversed(rows)],
        "note": READ_NOTE,
    }


def _document(row: tuple[Any, ...]) -> dict[str, Any]:
    """One entry as data: every field of the row, the number, and the two hashes as hex.

    The fields are read with :func:`mcp_connector.audit.store._entry_of_row`, and the number
    and the hashes off the ends of the row, exactly as the docstring of ``read_entries`` says:
    the column order stays written down once, in the module that owns the schema.

    The four values from a stranger are bracketed here as well and not only in the text: a
    document is printed to a console too, and a reader that hands one on has the same problem
    with a control character that a line has (T-19-22, T-24-01).
    """
    entry = _entry_of_row(row)
    return {
        "seq": row[0],
        "chain": printable(entry.chain, limit=CHAIN_LIMIT),
        "kind": entry.kind,
        "at": entry.at,
        "nc_user": None if entry.nc_user is None else printable(entry.nc_user, limit=CHAIN_LIMIT),
        "tool": entry.tool,
        "client_id": entry.client_id,
        "auth_id": entry.auth_id,
        "client_name": (
            None
            if entry.client_name is None
            else printable(entry.client_name, limit=CLIENT_NAME_LIMIT)
        ),
        "actor": None if entry.actor is None else printable(entry.actor, limit=ACTOR_LIMIT),
        "outcome": entry.outcome,
        "reason": entry.reason,
        "duration_ms": entry.duration_ms,
        "params": list(entry.params),
        "prev_hash": _hex(row[-2]),
        "hash": _hex(row[-1]),
    }


def _hex(value: object) -> str | None:
    """A raw digest as hex, because a BLOB is not JSON, and ``None`` when it is not one."""
    return value.hex() if isinstance(value, bytes) else None


def _chain_of(payload: Any) -> str | None:
    """Which chain this invocation asked for, or ``None`` for all of them.

    An account name becomes the identifier of its chain through
    :func:`mcp_connector.audit.store.user_chain`, so the prefix of a chain is built in the one
    place that knows it. :data:`INSTANCE_KEYWORD` is the one word that is not an account, for
    the reason that constant gives.
    """
    given = _value(payload, USER_OPTION)
    if given is None:
        return None
    if given == INSTANCE_KEYWORD:
        return CHAIN_INSTANCE
    return user_chain(given)


def _since_of(payload: Any) -> int | None:
    """The oldest moment this invocation asked for, or ``None`` for no lower end.

    Whole days back and never a date. A number can be tested with :meth:`str.isascii` and
    :meth:`str.isdigit` before anything converts it; a date cannot, and a date parser on a
    value from a console is a second place a 500 can come from for a value nobody checked. A
    number above :data:`MAX_SINCE_DAYS` is the whole log and is read as one rather than
    refused, and a value that is not a number falls back to the same window with a warning
    that names the option and the bound and never the value (T-05-03).
    """
    given = _value(payload, SINCE_OPTION)
    if given is None:
        return None
    days = _bounded_number(given, SINCE_OPTION, MAX_SINCE_DAYS, MAX_SINCE_DAYS)
    return int(time.time()) - days * _DAY_SECONDS


def _bounded_number(given: str | None, name: str, default: int, maximum: int) -> int:
    """One numeric option, in the form of ``config.py:433-465`` and for the same reasons.

    Only a plain run of ASCII digits is taken, and its length is decided before its value:
    ``"²".isdigit()`` is True while ``int("²")`` raises, and a run of more than 4300 digits
    makes :func:`int` raise as well since the integer conversion limit of Python 3.11 (R-18-08).
    A run longer than :data:`MAX_OPTION_DIGITS` is above ``maximum`` whatever it says, so it
    never reaches a conversion at all.

    Both ends are clamped. The upper end catches the option that says a billion; the lower end
    catches the zero and, if a shape ever carried one, the negative number, because a limit of
    zero is an answer nobody asked for. ``read_entries`` clamps a second time against the same
    :data:`~mcp_connector.audit.store.READ_LIMIT_MAX`, so a value that got past this function
    is still not an unbounded read.

    The warning names the option and the bound and never the value, the rule every reader of a
    value from outside in this project follows (T-05-03).
    """
    if given is None:
        return default
    plain_number = given.isascii() and given.isdigit()
    if not plain_number or len(given) > MAX_OPTION_DIGITS:
        logger.warning(
            "--%s is not a plain number up to %s, so the default of %s stays in force.",
            name,
            maximum,
            default,
        )
        return default
    return max(1, min(int(given), maximum))


def _value(payload: Any, name: str, *, inside_envelope: bool = False) -> str | None:
    """The value of one option: in the occ envelope, at the top level, or under ``options``.

    The reading shape of :func:`_set_in`, for an option that carries a value instead of only
    its presence, and it is a second function rather than a parameter of the first one because
    the two answer different questions about the same body.

    Measured against app_api v34.0.3: an option declared with ``mode: optional`` arrives as its
    declared ``default`` or as ``null`` when nobody set it, and an option in ``mode: none``
    arrives as ``false``. So ``None`` and ``False`` both mean "not set", and only a string with
    something in it after :meth:`str.strip` is an input. Everything else is a shape this
    handler does not understand, and a shape nobody understands decides nothing.

    ``inside_envelope`` keeps the descent one level deep. The envelope AppAPI builds carries no
    second one, and a body that nests them is not an occ invocation.
    """
    if not isinstance(payload, dict):
        return None

    for source in (payload, payload.get("options")):
        if isinstance(source, dict) and name in source:
            given = _given(source[name])
            if given is not None:
                return given

    if not inside_envelope:
        return _value(payload.get(OCC_ENVELOPE), name, inside_envelope=True)
    return None


def _given(value: object) -> str | None:
    """The input in this value, or ``None`` when there is none. See :func:`_value`."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _guard(request: Request, env: Mapping[str, str] | None) -> str | Response:
    """Return the Nextcloud user id of this request, or the response that ends it.

    Verbatim the guard of ``exapp/audit_verify.py``, ``exapp/purge.py`` and
    ``exapp/lifecycle.py``, including the reason for both halves: a response instead of an
    exception so no rejection escapes as a 500, and no detail in the rejection so nothing tells
    a caller which of the checks refused it (T-02-03, T-18-07, T-19-20).
    """
    if HEADER_ORIGIN_IP in request.headers:
        return _text("Not Found", status_code=404)
    try:
        return require_appapi(request, env=env)
    except (AppApiRejected, ToolError):
        return json_response({}, status_code=401)


def _set_in(payload: Any, *, inside_envelope: bool = False) -> bool:
    """Whether this invocation carries ``--json``, in any shape AppAPI may send it.

    The flag reader of ``exapp/audit_verify.py``, unchanged: an option in ``mode: none`` is
    presence and nothing more, so it can arrive as ``true``, as no value at all, or as its own
    name inside a list.
    """
    if not isinstance(payload, dict):
        return False
    if JSON_OPTION in payload and _is_set(payload[JSON_OPTION]):
        return True

    options = payload.get("options")
    if isinstance(options, dict) and JSON_OPTION in options and _is_set(options[JSON_OPTION]):
        return True
    if isinstance(options, list | tuple) and any(
        isinstance(item, str) and item.strip().lstrip("-") == JSON_OPTION for item in options
    ):
        return True

    if not inside_envelope:
        return _set_in(payload.get(OCC_ENVELOPE), inside_envelope=True)
    return False


def _is_set(value: object) -> bool:
    """Whether this value means the flag is set. A positive list, and nothing beside it.

    The rule of ``registry._switch``, ``config_values._switch``, ``purge._is_set`` and
    ``audit_verify._is_set``: a value nobody understands is a typo, and a typo does not decide
    anything. Nothing is logged for an unknown value, because the worst outcome of a misread
    here is an answer in the other shape.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    if isinstance(value, int | float):
        return value == 1
    if not isinstance(value, str):
        return False
    return value.strip().lower() in TRUE_WORDS


async def _payload(request: Request) -> Any:
    """The JSON body, or ``None`` when there is none this handler is willing to read.

    Bounded and never logged, the form of ``exapp/audit_verify.py`` as plan 19-01 corrected it:
    the announced length is read first because refusing before a byte is on the wire
    is cheaper than counting, ``responses.bounded_body`` is what actually holds because a
    chunked request announces nothing at all (IN-01), and the announced length is tested with
    :meth:`str.isascii` before :meth:`str.isdigit` and by the length of its run before its
    value, so :func:`int` never raises on it (R-18-08).

    A body this handler will not read is not a rejection. It is the default, which is the text
    shape with no filter, because a read changes nothing and an unreadable body is no reason to
    tell an administrator nothing at all.
    """
    announced = request.headers.get("content-length", "")
    plain_number = announced.isascii() and announced.isdigit()
    if plain_number and _above_the_body_bound(announced):
        logger.warning("a read call announced a body this handler does not read")
        return None
    try:
        raw = await bounded_body(request, MAX_BODY_BYTES)
    except BodyTooLarge:
        logger.warning("a read call sent a body this handler does not read")
        return None
    except BodyUnreadable:
        logger.warning("the body of a read call could not be read")
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning("the body of a read call is not JSON")
        return None


def _above_the_body_bound(announced: str) -> bool:
    """Whether a run of ASCII digits stands for a number above :data:`MAX_BODY_BYTES`.

    Called with a run this module has already tested for ``isascii`` and ``isdigit``, and the
    length is asked before the value, so :func:`int` never sees a run it refuses to convert.
    """
    return len(announced) > MAX_ANNOUNCED_DIGITS or int(announced) > MAX_BODY_BYTES


def _text(body: str, status_code: int = 200) -> Response:
    """Every answer of this module that is not JSON, and 200 unless a guard says otherwise.

    The default is the measurement of the module docstring rather than a habit: a status other
    than 200 makes AppAPI drop this body, and the body is the whole answer.
    """
    return Response(body, status_code=status_code, media_type="text/plain", headers=NO_STORE)

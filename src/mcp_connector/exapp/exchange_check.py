"""The handler behind ``occ mcp_connector:exchange:check``: would this token be accepted?

Success criterion 3 of this phase asks for a command an administrator can run against a
token somebody handed them, and EXCH-06 is the requirement. The rule itself lives in
``oauth/exchange_dryrun.py`` and answers in data; this module is the half that turns that
data into sentences and hands it to an occ command. Exactly the split
``audit/store.verify_chains`` and ``exapp/audit_verify.py`` have, and for the same reason:
the rule may not know what a console looks like, and the console may not own a rule.

Two decisions of ``exapp/audit_verify.py`` are inherited whole rather than copied, and both
are measured there rather than here:

**Why there is no route in the manifest** (``exapp/audit_verify.py:13-23``). AppAPI reaches
this handler over ``PublicFunctions``, the same internal path ``/heartbeat``, ``/init``,
``/enabled``, ``/purge``, ``/audit-verify`` and ``/audit-read`` arrive on, so it needs no
declaration to work. A declaration would make it callable by anyone who can reach the PHP
proxy, because that proxy attaches valid AppAPI headers itself (T-02-20, T-24-27). What
would leak here is not a list of accounts but an oracle: a caller could hold any token
against the configured provider of this instance and read back which single rule refused it.
The comment in ``appinfo/info.xml`` names this path as the seventh deliberately absent one,
and :func:`exchange_check_routes` therefore runs the same double check its six siblings run.

**Why the answer is always 200** (``exapp/audit_verify.py:25-33``). Measured there against
app_api v34.0.3: ``ExAppOccService::buildCommand`` writes the body to the console verbatim,
but only after a status check, and on any status but 200 it prints ``command executeHandler
failed`` and drops the body unread. A token that fails at step four reported with an error
status would therefore lose exactly the answer that names the step. The price is the same
one and is named rather than hidden: the exit code is always 0, so a script reads the
``passed`` key of ``--json`` and never the return value.

**What this module never writes down.** Not the presented token, not a fragment of it, not a
claim out of it, not to confirm what was checked. The rule half refuses to put a token value
into a step for the reason its own docstring gives (T-24-09); a console that printed the
value back would undo that in one line, and the value stands in the process list of the
Nextcloud host already (pitfall 6), which is a reason to repeat it less, not more.
"""

import json
import logging
from collections.abc import Mapping
from typing import Any, Final

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from ..errors import ToolError
from ..oauth.chain import load_exchange_config
from ..oauth.exchange_dryrun import (
    MAX_TOKEN_BYTES,
    OUTCOME_FAILED,
    STEP_ACCOUNT_EXISTS,
    STEP_ACTING_PARTY_ALLOWED,
    STEP_ACTING_PARTY_NAMED,
    STEP_AGE_WITHIN_BOUND,
    STEP_ALGORITHM_ALLOWED,
    STEP_AUDIENCE_EXACT,
    STEP_HEADER_READABLE,
    STEP_HEADER_TYPE,
    STEP_ISSUER_MATCHES,
    STEP_KEY_AVAILABLE,
    STEP_KEY_NAMED,
    STEP_LIFETIME_WITHIN_BOUND,
    STEP_MAPPING_YIELDS_PRINCIPAL,
    STEP_PAYLOAD_READABLE,
    STEP_SIGNATURE_AND_STANDARD_CLAIMS,
    STEP_SUBJECT_USABLE,
    STEP_TIMES_NUMERIC,
    STEP_TOKEN_IS_TEXT,
    STEP_TOKEN_PRESENT,
    STEP_TOKEN_SHAPE,
    STEP_TOKEN_SIZE,
    STEP_TOKEN_TYPE_BEARER,
    DryRunResult,
    DryRunStep,
    dry_run,
)
from .auth import AppApiRejected, require_appapi
from .responses import NO_STORE, BodyTooLarge, BodyUnreadable, bounded_body, json_response

__all__ = [
    "EXCHANGE_CHECK_PATH",
    "JSON_OPTION",
    "MAX_BODY_BYTES",
    "NOT_CONFIGURED_SENTENCE",
    "OUTCOME_NOT_CONFIGURED",
    "STEP_NAMES",
    "TOKEN_OPTION",
    "exchange_check_routes",
]

#: The path of the one route of this module, and the name the occ command registration hands
#: to AppAPI as its ``execute_handler`` (``exapp/occ.py`` derives that from this constant, so
#: the two cannot drift apart). It appears in no ``<url>`` of the manifest, on purpose; see
#: the module docstring.
EXCHANGE_CHECK_PATH = "/exchange-check"

#: The option that carries the token to check. Declared on the AppAPI side in ``exapp/occ.py``
#: and read here as well, because what AppAPI hands over is input. Its description there says
#: the thing this constant cannot: the value stands in the process list of the Nextcloud host
#: (pitfall 6), so what belongs in it is a short lived test token.
TOKEN_OPTION = "token"  # noqa: S105 - an option name, not a secret

#: The second option, and the same shape switch ``exapp/audit_verify.py`` and
#: ``exapp/audit_read.py`` carry: with it the same answer arrives as JSON.
JSON_OPTION = "json"

#: The envelope AppAPI wraps an occ invocation in, measured in ``exapp/audit_verify.py:79-86``
#: against a running AppAPI: ``params: ['occ' => ['arguments' => ..., 'options' => ...]]``
#: becomes the JSON body of a POST, so every option sits one level below the top.
OCC_ENVELOPE = "occ"

#: Set on the proxy path, never by HaRP and never on the internal AppAPI path. The same header
#: ``exapp/lifecycle.py``, ``exapp/purge.py``, ``exapp/audit_verify.py`` and
#: ``exapp/audit_read.py`` refuse, spelled a fifth time rather than imported, for the import
#: cycle those modules describe: ``lifecycle`` imports ``occ``, and ``occ`` imports this
#: module. ``tests/unit/test_exapp_exchange_check.py`` holds this spelling against the one of
#: ``exapp/audit_verify.py``.
HEADER_ORIGIN_IP = "x-origin-ip"

#: The largest body this handler reads before deciding it is not an occ invocation, and the
#: one constant of this module that is not the four kilobytes of ``exapp/audit_verify.py:97``.
#:
#: The rule there is "the real body is one option name", and this body carries a token. The
#: hard bound of this application is :data:`~mcp_connector.oauth.exchange.MAX_TOKEN_BYTES`, so
#: a body bound below it would answer a token that is merely large with a form error instead
#: of with the rule that refused it, which is the one answer a dry run exists to avoid. The
#: number is therefore written as the multiple of the token bound that it is: twice, which
#: leaves the JSON envelope, the second option and the quoting of the value the same room
#: again that the token itself takes.
#:
#: **The way in front of this bound is measured and not assumed** (assumption A5 of
#: ``24-RESEARCH.md``). 2026-09-24, against the running NC 35 HaRP topology: Nextcloud
#: 35.0.0 (``nc35-nc``), AppAPI 35.0.0, ``ghcr.io/nextcloud/nextcloud-appapi-harp:release``
#: (``nc35-harp``), ``caddy:2`` (``nc35-caddy``), this app as ``nc_app_mcp_connector`` at
#: version 0.2.1. ``occ mcp_connector:exchange:check --token=<n bytes> --json`` was run at
#: 1 000, 4 000, 8 000, 8 192 and 8 193 bytes. The first four answered with ``token_size``
#: held and fell at ``token_shape``; the run at 8 193 bytes fell at ``token_size``. The
#: second reading is the one that proves it: a value that reaches the rule with more than
#: :data:`~mcp_connector.oauth.exchange.MAX_TOKEN_BYTES` bytes can only do so if nothing on
#: the way shortened it, so ``ExAppOccService::buildCommand`` hands an option value of these
#: sizes through unchanged. Every one of the five answered ``checked: true``, so this bound
#: judged none of them a form error. A5 holds.
MAX_BODY_BYTES: Final[int] = 2 * MAX_TOKEN_BYTES

#: How many digits an announced length may carry before it is refused unread. Ten digits are
#: ten gigabytes, so a longer run is above :data:`MAX_BODY_BYTES` whatever it says, and it is
#: never converted: since Python 3.11 :func:`int` refuses a run of more than 4300 digits and
#: raises, which would answer a header with a 500 (R-18-08).
MAX_ANNOUNCED_DIGITS = 10

#: The words that mean "yes" when the shape option arrives with a value. Written here rather
#: than imported from ``exapp/audit_verify.py``, the rule that module states for its own copy:
#: a change made for one command must not silently change how another one reads its input.
#: ``tests/unit/test_exapp_exchange_check.py`` holds this list against the one of
#: ``exapp/audit_verify.py``.
TRUE_WORDS = frozenset({"1", "true", "yes", "on"})

#: The named result of an instance that has no exchange path at all, and the reason it is a
#: result of its own rather than a token that fails every rule: a list of fallen steps would
#: send an administrator to the token they were handed, while what is missing is the
#: configuration of this deployment. Named, because an answer that only reads differently is
#: an answer a script cannot tell apart.
OUTCOME_NOT_CONFIGURED = "exchange_path_not_configured"

NOT_CONFIGURED_SENTENCE = (
    "the token exchange path is not configured on this instance, so there is nothing to hold "
    "a token against. Nothing was checked and nothing about the token follows from that."
)

#: The named result of an invocation whose body never reached this handler, after the shape of
#: :data:`OUTCOME_NOT_CONFIGURED` and for the same reason (WR-24-03 of the phase 24 review).
#:
#: Without it the four refusals of :func:`_payload` fell together into "no body", the rule was
#: run against the empty string, and the answer said ``a token was presented`` had failed. That
#: is worse than a form error: it is a sentence about the token, it is false, and it is the one
#: answer a dry run exists to avoid. It bites exactly where :data:`MAX_BODY_BYTES` was chosen
#: to not bite, at a token between the hard bound of this app and twice that bound, or at one
#: that arrives with a second option beside it.
OUTCOME_BODY_NOT_READ = "request_body_not_read"

BODY_NOT_READ_SENTENCE = (
    "the body of this invocation was not read, so no token reached the rule. Nothing was "
    "checked and nothing about the token follows from that. The body was either larger than "
    "this handler reads, unreadable, or not JSON; the container log of this app names which "
    "of the three, without naming the body."
)

#: The first line of every answer that ran the rule. Deliberately not a step line: the count
#: of step lines is what a test holds against ``len(STEPS)``.
HEAD_LINE = "checked one presented token against the configured token exchange path"

#: How wide the outcome column of a step line is. Every outcome of the rule fits, and the
#: padding is what lets a reader and a test tell a step line from a sentence by its first word.
OUTCOME_WIDTH = 12

#: The names an administrator reads, one per identifier of
#: :data:`~mcp_connector.oauth.exchange_dryrun.STEPS`. They are built here and nowhere else,
#: which is the split this module exists for: the rule answers in data, the console makes
#: sentences of it (the shape of ``audit/store.ChainFinding`` against
#: ``exapp/audit_verify._report``). A test holds the keys of this table against ``STEPS``
#: rather than against a typed number, so a step that arrives in the rule cannot stay nameless
#: here: an unnamed step is a step an administrator cannot act on.
STEP_NAMES: Final[dict[str, str]] = {
    STEP_TOKEN_PRESENT: "a token was presented",
    STEP_TOKEN_SIZE: "the token stays within the size bound of this app",
    STEP_TOKEN_IS_TEXT: "the token is text this process can encode",
    STEP_TOKEN_SHAPE: "the token has the shape of a signed JWT",
    STEP_HEADER_READABLE: "the header of the token can be read",
    STEP_ALGORITHM_ALLOWED: "the signing algorithm is one of the configured ones",
    STEP_KEY_NAMED: "the header names the key that signed",
    STEP_HEADER_TYPE: "the header type is one this app tolerates",
    STEP_PAYLOAD_READABLE: "the payload of the token can be read",
    STEP_ISSUER_MATCHES: "the issuer is the configured one",
    STEP_KEY_AVAILABLE: "the named key is available from the provider",
    STEP_SIGNATURE_AND_STANDARD_CLAIMS: (
        "the signature holds and the required standard claims are there"
    ),
    STEP_AUDIENCE_EXACT: "the audience is exactly the configured one",
    STEP_ACTING_PARTY_NAMED: "the token names the party that acted",
    STEP_ACTING_PARTY_ALLOWED: "the acting party stands on the configured allowlist",
    STEP_TOKEN_TYPE_BEARER: "the token type is the configured one and not an ID token",
    STEP_TIMES_NUMERIC: "the issued and expiry times are numbers",
    STEP_LIFETIME_WITHIN_BOUND: "the lifetime stays within the configured bound",
    STEP_AGE_WITHIN_BOUND: "the token is no older than that same bound",
    STEP_SUBJECT_USABLE: "the subject is a value this app can map",
    STEP_MAPPING_YIELDS_PRINCIPAL: "the configured mapping profile yields a principal",
    STEP_ACCOUNT_EXISTS: "the account exists in this Nextcloud",
}

logger = logging.getLogger("mcp_connector.exapp.exchange_check")


def exchange_check_routes(env: Mapping[str, str] | None = None) -> list[Route]:
    """The one route of the dry run, handed out rather than registered on the server object.

    A factory for the reason D-23 gives and ``exapp/lifecycle.py`` states: a registration on
    the shared MCP server object would make this path appear in the standalone HTTP mode of
    phase 1 as soon as anything imports this module, and that mode has no AppAPI identity to
    check it against.

    The configuration is read once, here, and not per request. Reading it in the handler would
    turn the one state :func:`~mcp_connector.oauth.chain.load_exchange_config` refuses loudly,
    the half configured one, into a 500 on a path whose whole contract is 200. Here it cannot:
    ``entry_exapp.build_exapp_app`` already calls the same function over the same environment
    before it appends these routes, so a half configured deployment is refused at startup and
    this call can never be the first one to raise.
    """
    config = load_exchange_config(env)

    async def exchange_check(request: Request) -> Response:
        """Walk every rule against the presented token, then name each one with its outcome."""
        guarded = _guard(request, env)
        if isinstance(guarded, Response):
            return guarded

        payload, unread = await _payload(request)
        as_json = _set_in(payload)
        if unread is not None:
            # Always the reading shape, and that is not an oversight: the shape option travels
            # in the very body that was not read, so there is no answer here about what was
            # asked for. The named outcome is in the sentence, so a script that parses this
            # can still tell this case from a checked one.
            return _text(f"{unread}: {BODY_NOT_READ_SENTENCE}\n")
        if config is None:
            logger.info("a dry run was asked for on an instance without a configured exchange path")
            if as_json:
                return json_response(
                    {
                        "checked": False,
                        "passed": False,
                        "outcome": OUTCOME_NOT_CONFIGURED,
                        "message": NOT_CONFIGURED_SENTENCE,
                    }
                )
            return _text(NOT_CONFIGURED_SENTENCE + "\n")

        try:
            # The option value, never logged and never echoed. An invocation without it is not
            # an error of this handler: the rule has a first step for exactly that case, and a
            # named outcome is a better answer than an exception (pitfall 8).
            result = await dry_run(_value(payload, TOKEN_OPTION) or "", config)
            # The verdict and the first step that fell, and nothing else: both are constants
            # of this application, while everything the token said is not.
            logger.info(
                "a presented token was checked: passed=%s, first fallen step=%s",
                result.passed,
                _first_fallen(result),
            )
            # Inside the bracket and not after it (WR-24-05). Building the answer is the
            # second half of this handler's work and it can fail for the same kind of reason
            # the run can: a step that arrives in the rule without a name here used to be a
            # ``KeyError``, and AppAPI drops the body of anything that is not a 200, so the
            # administrator saw ``command executeHandler failed`` and nothing else. A gate in
            # the test run is not a fail-open bracket at run time, and this module argues that
            # way about everything else it does.
            answer = json_response(_machine_readable(result)) if as_json else _text(_report(result))
        except Exception as exc:
            # The type only, never the message: a failure of the run can carry a URL of the
            # provider or a value it was handed.
            logger.error("the presented token could not be checked: %s", type(exc).__name__)
            if as_json:
                return json_response(
                    {"checked": False, "passed": False, "error": type(exc).__name__}
                )
            return _text(f"the presented token could not be checked: {type(exc).__name__}\n")

        return answer

    return [Route(EXCHANGE_CHECK_PATH, exchange_check, methods=["POST"])]


def _report(result: DryRunResult) -> str:
    """The answer an administrator reads: a head, one line per rule, and the two qualifiers.

    Every step of the rule appears, in the order of the rule, whatever happened before it. A
    step that is simply missing from an answer reads like a step that passed (pitfall 8), and
    the order is the order the operating path checks in, so a reader can see which rules were
    never reached rather than having to assume it.

    The two closing sentences are the rule's own and are not written a second time here.
    :data:`~mcp_connector.oauth.exchange_dryrun.COST_SENTENCE` says what the run spent,
    :data:`~mcp_connector.oauth.exchange_dryrun.LIMIT_SENTENCE` says what a green run does not
    mean, and the second one stands last for the reason ``exapp/audit_verify.py`` gives for
    its own: whoever has to judge a green result is reading the console, not this file.
    """
    lines = [HEAD_LINE]
    lines.extend(_line(step) for step in result.steps)
    lines.append(result.cost_sentence)
    lines.append(result.limit_sentence)
    return "\n".join(lines) + "\n"


def _line(step: DryRunStep) -> str:
    """One step: its outcome, its name, and the group or the note that qualifies it.

    The outcome stands first and in a column of its own, so a console reader scans one column
    instead of the ends of twenty-two sentences. ``reason`` is named as what it is, the group
    the operating path would have booked this refusal under, because an administrator who
    reads a container log of that path has to be able to find the same word there.
    """
    line = f"{step.outcome:<{OUTCOME_WIDTH}} {_name(step.step)}"
    if step.reason is not None:
        line += f" (refused in operation as: {step.reason})"
    if step.note is not None:
        line += f" ({step.note})"
    return line


def _machine_readable(result: DryRunResult) -> dict[str, Any]:
    """The same answer for a script, with the same 200 under it.

    ``passed`` exists because the exit code cannot carry it: the command answers 0 whatever it
    found, for the reason the module docstring measures, so this key is what a script watches
    instead. It is the same trade ``exapp/audit_verify._machine_readable`` makes with its
    ``broken`` key, in the direction this answer reads in.

    Every step keeps its identifier next to its name, so a script matches on the identifier
    and a reader of the document still sees what was checked. ``reason`` and ``note`` stay in
    the document even when they are empty, because a key that appears only sometimes is a key
    a script has to guess about.
    """
    return {
        "checked": True,
        "passed": result.passed,
        "steps": [
            {
                "step": step.step,
                "name": _name(step.step),
                "outcome": step.outcome,
                "reason": step.reason,
                "note": step.note,
            }
            for step in result.steps
        ],
        "cost": result.cost_sentence,
        "limit": result.limit_sentence,
    }


def _name(step: str) -> str:
    """The name an administrator reads for one step, and the identifier when there is none.

    Total on purpose (WR-24-05). A step of the rule without an entry in :data:`STEP_NAMES` is
    a fault of this module, and the answer is the wrong thing to spend it on: the gate in
    ``tests/unit/test_exapp_exchange_check.py`` holds the two sets together, so the drift is
    caught where it is cheap, and here the identifier is a worse name than a sentence and a
    far better one than no answer at all.
    """
    return STEP_NAMES.get(step, step)


def _first_fallen(result: DryRunResult) -> str | None:
    """The identifier of the first rule that did not hold, for the one log line of a run."""
    return next((step.step for step in result.steps if step.outcome == OUTCOME_FAILED), None)


def _guard(request: Request, env: Mapping[str, str] | None) -> str | Response:
    """Return the Nextcloud user id of this request, or the response that ends it.

    Verbatim the guard of ``exapp/audit_verify.py``, ``exapp/audit_read.py``,
    ``exapp/purge.py`` and ``exapp/lifecycle.py``, including the reason for both halves: a
    response instead of an exception so no rejection escapes as a 500, and no detail in the
    rejection so nothing tells a caller which of the checks refused it (T-02-03, T-24-08).
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
    name inside a list. ``inside_envelope`` keeps the descent one level deep, because the
    envelope AppAPI builds carries no second one.
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
    """Whether this value means the shape option is set. A positive list, and nothing beside it.

    The rule of ``exapp/audit_verify._is_set``: a value nobody understands is a typo, and a
    typo does not decide anything. Nothing is logged for an unknown value, because the worst
    outcome of a misread here is an answer in the other shape.
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


def _value(payload: Any, name: str, *, inside_envelope: bool = False) -> str | None:
    """The value of one option: in the occ envelope, at the top level, or under ``options``.

    The reader of ``exapp/audit_read._value``, and it is the first one of this module that
    takes a value rather than a presence. Measured there against app_api v34.0.3: an option
    declared with ``mode: optional`` arrives as its declared ``default`` or as ``null`` when
    nobody set it, and an option in ``mode: none`` arrives as ``false``. So ``None`` and
    ``False`` both mean "not set", and only a string with something in it after
    :meth:`str.strip` is an input.
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


async def _payload(request: Request) -> tuple[Any, str | None]:
    """The JSON body, and the named outcome when there is none this handler could read.

    The second half of the pair is :data:`OUTCOME_BODY_NOT_READ` for every refusal below and
    ``None`` for an invocation that carried no body at all. The two are not the same thing and
    must not answer the same way: an empty body is an administrator who set no option, which
    the rule has a first step for, while a refused body is an administrator who set one this
    handler never saw. Letting both fall into ``None`` made the second answer "a token was
    presented" had failed, which is a statement about a token nobody here ever read
    (WR-24-04).

    Bounded and never logged, the shape of ``exapp/audit_verify._payload``: the announced
    length is read first because refusing before a byte is on the wire is cheaper than
    counting, and ``responses.bounded_body`` is what actually holds, because a chunked request
    announces nothing at all (IN-01 of the re-review of phase 5).

    The announced length is read in the form of ``config.py:433-465``, and for the reason that
    function gives: ``"²".isdigit()`` is True while ``int("²")`` raises, so the digit test
    alone turned one header of an authenticated caller into a 500 (R-18-08). A run of more
    than 4300 digits makes :func:`int` raise as well since the integer conversion limit of
    Python 3.11, which ``isascii`` does not catch, so a run longer than
    :data:`MAX_ANNOUNCED_DIGITS` is decided by its length before its value. A 500 would be the
    worst answer this handler has, because AppAPI drops the body of anything that is not a 200
    (T-18-20). Every warning names the circumstance and never the value, the rule every reader
    of a value from outside in this project follows (T-05-03), and here that rule is sharper
    than usual: the value is a bearer token of a foreign realm.
    """
    announced = request.headers.get("content-length", "")
    plain_number = announced.isascii() and announced.isdigit()
    if plain_number and _above_the_body_bound(announced):
        logger.warning("a dry run call announced a body this handler does not read")
        return None, OUTCOME_BODY_NOT_READ
    try:
        raw = await bounded_body(request, MAX_BODY_BYTES)
    except BodyTooLarge:
        logger.warning("a dry run call sent a body this handler does not read")
        return None, OUTCOME_BODY_NOT_READ
    except BodyUnreadable:
        logger.warning("the body of a dry run call could not be read")
        return None, OUTCOME_BODY_NOT_READ
    if not raw:
        return None, None
    try:
        return json.loads(raw), None
    except ValueError:
        logger.warning("the body of a dry run call is not JSON")
        return None, OUTCOME_BODY_NOT_READ


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

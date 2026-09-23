"""The recording path: one row after one tool call, and never at the cost of that call.

This is the other half of the seam ``@graceful`` opens. The decorator knows what happened,
this module knows what may be written down about it, and the two are kept apart on purpose:
the decorator has no business knowing about SQLite, and this module has no business knowing
how a tool answers.

**What a row may never carry, in one paragraph.** A parameter *value*, a piece of a result,
``exc.message``, ``exc.hint``, an IP address and a user agent (D-06, D-08, T-18-01). The
first two are result content, the messages of this server are written for a model and name
real paths and real calendars, and the last two would turn a record of what happened into a
record of where somebody was. Of the parameters only the names that were *set*, intersected
with the allowlist of that tool, and of a refusal only the fixed identifier of D-07.

**Why nothing here raises.** A full volume must not cost a tool call (D-13). Every step
after the recorder was found runs inside one ``except Exception``, which logs the type of
the failure and nothing else: the message of a store error can carry a path, the same rule
``exapp/purge.py`` follows one layer up. The gap this leaves is not hidden, it is what the
check command of this phase makes visible.

**What this module must not import.** ``..server``, because the server calls the recorder
and the import would close a ring, and anything under ``..exapp``, because the ExApp shell
sits above this package. The one thing borrowed from up there, the cleaning of a client
name, sits in the leaf module ``audit/text.py`` instead, where all three callers of this
application reach it without anybody importing upwards.
"""

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .. import deps
from ..errors import REASON_UNSPECIFIED, REASONS
from . import AUDIT_STATE_ATTR, accounts, store
from .allowlist import PARAM_ALLOWLIST
from .store import (
    ACTOR_UNKNOWN,
    CHAIN_INSTANCE,
    KIND_CALL,
    KIND_SWITCH,
    AuditStore,
    Entry,
    user_chain,
)
from .text import printable

__all__ = ["SWITCH_OFF", "SWITCH_ON", "Recorder", "note", "note_switch", "set_parameter_names"]

logger = logging.getLogger("mcp_connector.audit.record")

#: How a caller hands in its own store, the same shape ``exapp/purge.py`` uses for the OAuth
#: one: the file cannot be opened when the routes are built, so the recorder gets a function
#: and the first row that needs the file pays for opening it.
type StoreProvider = Callable[[], Awaitable[AuditStore]]

#: The two directions a switch row of D-15 can have, written into ``outcome`` because that
#: column already means "how did this end" and a switch ends in exactly one of two states.
SWITCH_ON = "on"
SWITCH_OFF = "off"

#: Milliseconds per second, so the one conversion of this module is a name and not a literal.
_MILLISECONDS = 1000


@dataclass(frozen=True, slots=True)
class Recorder:
    """Everything the recording path needs, deposited once per request by the boundary.

    Four fields and no fifth, and above all no counter and no dictionary: the interval of the
    sweep hangs on the sequence number the store just handed back (D-11, D-20), so there is
    nothing here that would have to survive between two requests.
    """

    store_provider: StoreProvider
    # Read by nobody in this plan, and it stands here all the same: the account check of D-12
    # (plan 18-09) needs the same resolved environment mapping the application was built
    # with, and a recorder that received it only later would be a second way to construct
    # one.
    env: Mapping[str, str] | None = None
    retention_days: int = store.RETENTION_DAYS
    size_limit: int = store.SIZE_LIMIT_BYTES


def set_parameter_names(ctx: Any, tool: str) -> list[str]:
    """Only the names the caller really set, and only allowed ones.

    ``params["arguments"]`` carries exactly the keys that were set; ``kwargs`` cannot, because
    the SDK materialises the default values of a tool signature before it calls it
    (``func_metadata.py:50-61``), so a parameter nobody sent would be recorded as sent. The
    values live in the same mapping, which is why this walks ``keys()`` and never
    ``values()``.

    The intersection with the allowlist is the second half: the arguments are input from the
    outside, and an invented key name stands in ``params["arguments"]`` even when pydantic
    throws it away afterwards (T-18-02).
    """
    params = getattr(getattr(ctx, "request_context", None), "params", None)
    if not isinstance(params, dict):
        return []
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        return []
    return sorted(set(arguments.keys()) & PARAM_ALLOWLIST.get(tool, frozenset()))


def _clamped_client_name(raw: str | None) -> str | None:
    """The registered name of a client, made safe to write down and bounded in length.

    The rule itself lives in :mod:`mcp_connector.audit.text` and lives there exactly once. It
    used to stand here in five lines of its own, in ``audit/store.py`` in five more and in
    ``exapp/audit_verify.py`` in five more, and two of those three replaced only the C0 range
    and DEL: three versions with two different sets of characters were R-18-06 of phase 18, and
    a name carrying a right-to-left override could turn the reading direction of an output line
    round. ``exapp/ui/layout.py`` keeps a version of its own on purpose, because ``exapp`` sits
    above this package and an import upwards would be a layering break.

    What is left here is the part that belongs to this caller: the name comes from a dynamic
    registration, so it is written by whoever registers (T-18-08), it is cut at
    :data:`~mcp_connector.audit.store.CLIENT_NAME_LIMIT`, and a name that is empty afterwards is
    ``None``, because "nothing to print" is not a name.
    """
    if raw is None:
        return None
    return printable(raw, limit=store.CLIENT_NAME_LIMIT) or None


def _clamped_actor(raw: str | None) -> str | None:
    """The acting party of a delegation, made safe to write down and bounded in length.

    The neighbour of :func:`_clamped_client_name`, under the same rule and cut at
    :data:`~mcp_connector.audit.store.ACTOR_LIMIT`. The difference worth naming is against
    ``oauth.exchange_accounts.acting_party``, which cleaned the very same value once already
    on its way into the identity: that one filters with ``str.isprintable`` and drops what it
    refuses, while the rule of :mod:`mcp_connector.audit.text` replaces it with a space and
    collapses runs of whitespace afterwards. Two rules that agree about most characters and
    not about all of them were R-18-06, so the value is cleaned again here rather than
    trusted, and the one rule of this application is the one that decides what a row carries.

    A value that is empty afterwards is ``None``, for the reason the client name gives:
    "nothing left to print" names nobody, and an empty column would claim a delegation that
    nobody can read back.
    """
    if raw is None:
        return None
    return printable(raw, limit=store.ACTOR_LIMIT) or None


def _recorder_of(ctx: Any) -> Recorder | None:
    """The recorder the transport boundary left for this request, or ``None``.

    Defensive on the way in and never on the way out, the shape of ``deps._oauth_identity``.
    That function is not called here and its private neighbour is not imported: a name with a
    leading underscore is a promise its owner may take back, and three lines are cheaper than
    a dependency on one.

    ``None`` is the ordinary answer, not a fault, and therefore silent: stdio and the
    standalone HTTP mode never pass a boundary that deposits anything, and the log is off by
    default (D-14). A line here would be noise on every call of those two modes.
    """
    try:
        request = getattr(ctx.request_context, "request", None)
    except (AttributeError, ValueError):
        return None
    state = getattr(request, "state", None)
    if state is None:
        return None
    recorder = getattr(state, AUDIT_STATE_ATTR, None)
    return recorder if isinstance(recorder, Recorder) else None


def _tool_name(ctx: Any, fallback: str) -> str:
    """The name the tool was called under, with the name of the function as the fallback.

    ``params["name"]`` is the name the ``ToolManager`` resolved the call with, so it can never
    be an unknown one; the fallback covers a context that carries no parameters at all, which
    is what every direct call of a wrapped function looks like.
    """
    params = getattr(getattr(ctx, "request_context", None), "params", None)
    if isinstance(params, dict):
        name = params.get("name")
        if isinstance(name, str) and name:
            return name
    return fallback


def _known_reason(reason: str | None) -> str | None:
    """A rejection identifier out of the frozen set of D-07, or the honest "not determined".

    The reason travels from an exception into a row, and an exception is not a place this
    module controls: anything that is not one of :data:`~mcp_connector.errors.REASONS` would
    be free text in a column that exists to have none.
    """
    if reason is None:
        return None
    return reason if reason in REASONS else REASON_UNSPECIFIED


async def _drop_chains_without_an_account(
    audit_store: AuditStore, recorder: Recorder, *, moment: int
) -> None:
    """The account check of D-12, and it deletes only where all three conditions hold.

    One call to Nextcloud per run and never one per account: every silent chain is held
    against one list that was fetched once (18-RESEARCH.md §7, the cost paragraph).

    ``None`` means the list could not be read, and then nothing happens at all, not even for a
    chain that has been silent for a year. That is the fail-safe of this plan written out: the
    assumption behind the list is unmeasured (A1), and a chain that is kept costs storage
    while a chain that falls costs the record of everything that account ever did.

    No line here names an account. The store holds that name in a column, and a log line
    outside it would carry it into the Nextcloud log, which has neither the retention window
    of D-09 nor the switch of D-14 over it.
    """
    known = await accounts.existing_users(recorder.env)
    if known is None:
        logger.info(
            "the account check of this sweep was skipped: the account list could not be read, "
            "and a list that was not read never removes a chain"
        )
        return
    for nc_user in await audit_store.silent_users(moment=moment):
        if nc_user not in known:
            await audit_store.drop_user_chain(nc_user, moment=moment)


async def note(
    ctx: Any,
    tool_fallback: str,
    outcome: str,
    reason: str | None,
    duration_s: float,
) -> None:
    """Write one row about one finished tool call. Never raises, never writes a value.

    The order is the whole function. The recorder of this request first, because its absence
    is the ordinary case and costs nothing; then the tool name, then who called; then the row;
    then the sweep, if the number the store handed back says it is this row's turn (D-11).

    A call without a caller writes nothing: an entry without a user belongs in no user chain
    (D-02), and inventing one would be worse than the gap.

    Everything from the second step on is wrapped once, and the handler logs
    ``type(exc).__name__`` and nothing else. That is D-13 word for word: a full volume must
    not cost a tool call, and the message of a store error can carry a path.
    """
    recorder = _recorder_of(ctx)
    if recorder is None:
        return
    try:
        tool = _tool_name(ctx, tool_fallback)
        caller = deps.resolve_caller(ctx)
        if caller is None:
            return
        audit_store = await recorder.store_provider()
        seq = await audit_store.append(
            Entry(
                chain=user_chain(caller.nc_user),
                kind=KIND_CALL,
                at=int(time.time()),
                actor=_clamped_actor(caller.actor),
                nc_user=caller.nc_user,
                tool=tool,
                client_id=caller.client_id,
                auth_id=caller.auth_id,
                client_name=_clamped_client_name(caller.client_name),
                outcome=outcome,
                reason=_known_reason(reason),
                duration_ms=round(duration_s * _MILLISECONDS),
                params=set_parameter_names(ctx, tool),
            )
        )
        if store.should_sweep(seq):
            # One moment for both halves of this run, so the retention window, every marker
            # and the threshold of the account check agree about the time.
            moment = int(time.time())
            await audit_store.sweep(
                moment=moment,
                retention_days=recorder.retention_days,
                size_limit=recorder.size_limit,
            )
            if store.should_check_accounts(seq):
                # A magnitude rarer than the sweep around it, because this is its only step
                # that costs a call to Nextcloud (D-11, D-12, T-18-16).
                await _drop_chains_without_an_account(audit_store, recorder, moment=moment)
    except Exception as exc:
        # The type only, never the message: a store error can carry a path (D-13).
        logger.error("the audit log did not record a call: %s", type(exc).__name__)


async def note_switch(audit_store: AuditStore, *, enabled: bool, moment: int) -> None:
    """Write the switching of the log itself into the chain of instance events (D-15).

    ``actor`` is :data:`~mcp_connector.audit.store.ACTOR_UNKNOWN`, and that is a measured fact
    rather than a shortcut (D-16): AppAPI's ``SetValueListener`` drops the user of an admin
    form before the app is asked (app_api v34.0.3), so the administrator behind a switch
    cannot be determined on this path. The column stands in the schema from the first version
    all the same, so a later way to learn the name needs no migration.

    Unlike :func:`note` this one lets a failure through. A switch is an administrative action
    with an answer of its own, not a tool call that must survive its own bookkeeping, and the
    caller of plan 18-07 decides what an unwritten switch means for that answer.
    """
    await audit_store.append(
        Entry(
            chain=CHAIN_INSTANCE,
            kind=KIND_SWITCH,
            at=moment,
            actor=ACTOR_UNKNOWN,
            outcome=SWITCH_ON if enabled else SWITCH_OFF,
        )
    )

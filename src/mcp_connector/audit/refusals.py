"""The refused attempts of the token exchange path, written down without letting a stranger
decide how much is written (AUDIT-07, T-24-02).

**Why this module exists at all.** Until now a refusal of ``oauth/exchange.py`` left one DEBUG
line and nothing else, and the docstring of ``_refused`` names this phase as the place where
that gets fixed: an operator cannot see repeated rejected exchange attempts in a log level
that is off in production. The hash chained trail is where they belong, under its content
bans and its retention window.

**Why this is the one module of the application that keeps a counter.**
``record.Recorder`` says "no counter and no dictionary" in so many words, because the interval
of the sweep hangs on the sequence number the store hands back (D-11, D-20), so nothing there
has to survive between two requests. Here the state **is** the brake: it is the thing being
built, not an optimisation of something else. Reading it out of the chain instead would mean
one database query per pre-authentication request, which is precisely the load the brake is
written against.

**What the counter is worth, and what it is not.** It lives in one process. With several
workers the guarantee is at most one row per reason, per window and per worker, and an
operator has to know that number rather than read the rows as a count of attempts against the
instance. The count a row carries (``removed``) is exact for the worker that wrote it.

**Why nothing here raises.** The path runs before any authentication. An exception escaping
this module would turn a refusal into a 500 where a 401 belongs, and it would hand a stranger
a way to produce one. So every step is wrapped once, and the handler writes the type of the
failure and nothing else: the message of a store error can carry a path (D-13).

**What this module must not import.** Anything under ``..oauth``. The window below is the
same five minutes ``oauth/throttle.WINDOW`` counts in and is named here a second time rather
than imported, for that reason. The direction is held by
``test_the_refusal_writer_imports_nothing_out_of_oauth`` in
``tests/contract/test_no_claim_leak.py``, which reads this file's imports off its syntax tree
and whose counter proof shows it sees every spelling of such an import. It is not the
invariant of ``tests/contract/test_module_boundaries.py`` (no module reaches into the private
names of a foreign ``tools/*.py``), nor the one the module docstring of ``record.py`` states
(no ``..server`` and nothing under ``..exapp``).
"""

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from ..errors import REASON_UNSPECIFIED, known_reason
from . import store
from .store import CHAIN_EXCHANGE, KIND_REFUSAL, OUTCOME_REJECTED, AuditStore, Entry

__all__ = ["REFUSAL_WINDOW_SECONDS", "RefusalWriter"]

logger = logging.getLogger("mcp_connector.audit.refusals")

#: How a caller hands in its own store: the shape of ``audit/record.StoreProvider``, spelled
#: here a second time rather than imported, the way ``exapp/audit_read.py`` and
#: ``exapp/audit_verify.py`` already spell it. Importing ``record`` for one alias would pull
#: the whole recording path, ``deps`` and the account check behind it into a module that opens
#: nothing and asks nobody.
type StoreProvider = Callable[[], Awaitable[AuditStore]]

#: How long one written refusal speaks for every further refusal of the same reason. Five
#: minutes, the same length ``oauth/throttle.WINDOW`` counts its limits in, named here instead
#: of imported because ``audit/`` must not import ``oauth/`` (see the module docstring; the
#: direction is held by ``test_the_refusal_writer_imports_nothing_out_of_oauth``).
#:
#: The number matters for what an operator sees rather than for what the file costs: with a
#: shorter window the trail fills with lines that all say the same thing, with a longer one an
#: attack that started and stopped inside it is one line without a shape. Five minutes is the
#: window the refusals themselves are counted in one layer down, so the two agree about what
#: "a burst" is.
REFUSAL_WINDOW_SECONDS = 300


@dataclass(frozen=True, slots=True)
class RefusalWriter:
    """One braked writer per process, for the refusals of the pre-authentication path.

    ``store_provider`` is the seam of ``record.Recorder``: the file cannot be opened when the
    verifier chain is built, so the writer receives a function and the first row that needs
    the file pays for opening it.

    The state is a dictionary from a rejection identifier to the pair "when the current window
    opened" and "how many attempts it has swallowed since". It is bounded by the number of
    identifiers in :data:`~mcp_connector.errors.REASONS`, six of which name this path today,
    because every value goes through :func:`~mcp_connector.errors.known_reason` first. A
    stranger therefore cannot make this dictionary hold a key of their choosing, which is what
    keeps a brake against a flood from becoming the flood.
    """

    store_provider: StoreProvider
    #: The two bounds of the sweep, handed in the way ``record.Recorder`` receives them, and
    #: here for the same reason: this writer is a second caller of :meth:`AuditStore.sweep`
    #: (see :meth:`note_refusal`), and a caller that swept against the defaults would run a
    #: retention window an administrator did not configure.
    retention_days: int = store.RETENTION_DAYS
    size_limit: int = store.SIZE_LIMIT_BYTES
    #: Not an argument of the constructor: two writers sharing one window would be two brakes
    #: that are one, and a caller handing in a prepared state would be a caller deciding when
    #: the next row is written. Nor does it take part in the comparison or the hash: a writer
    #: whose dictionary did would be unhashable, and two writers would be compared by what
    #: their brakes have counted rather than by the store they write to.
    _windows: dict[str, tuple[int, int]] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    async def note_refusal(self, reason: str, *, moment: int | None = None) -> None:
        """Note one refused exchange attempt. Never raises, never writes a value.

        The first refusal of a reason in a fresh window is written at once, so a single probe
        is visible without a delay. Every further one of the same reason inside the window is
        counted and writes nothing. The first one after the window carries the swallowed
        attempts plus itself in ``removed``, so no counted attempt is lost.

        A moment older than the start of the current window opens a new one. A clock stepped
        backwards (an NTP correction, a resumed VM) would otherwise leave the difference
        negative and below the window for as long as the step lasts, which on a large step is
        hours in which nothing is written down at all.

        The window is set **before** the write and not after it. A writer that only armed its
        brake on a successful write would go to a failing store on every single request of a
        path a stranger drives, which is the load this class exists to prevent, and a failing
        store is exactly when that matters. The price is named rather than hidden: a write
        that fails loses the attempts its row would have stood for, and the log line is what
        says so.

        The sweep of D-11 runs from here as well, on the number this store hands back, and
        that is not an extra: the schedule **is** that number. A writer that dropped it would
        take two things out of the retention window at once. Its own rows, because on an
        instance whose traffic is somebody else's attempts and not tool calls nothing else
        ever writes, so nothing would ever sweep and the promise of ``docs/privacy.md`` about
        the ``x:exchange`` chain would hold in SQL and not in operation. And every other
        chain, because the numbers come out of one ``AUTOINCREMENT``: a refusal landing on a
        multiple of :data:`~mcp_connector.audit.store.SWEEP_EVERY` would make that sweep of
        the whole trail happen never instead of late, and how often that happens is ordered
        from the outside.

        No new lever for a stranger comes with it. The brake above decides how many rows this
        path writes at all, so it decides how many numbers it can consume, and only every five
        hundredth row sweeps.

        The one step of the sweep that stays behind is the account check of D-12: it costs a
        call to Nextcloud, and this path runs before any authentication. A check that falls on
        a refusal row therefore waits for the next one, a magnitude rarer schedule where being
        late is what it already is by design.
        """
        at = int(time.time()) if moment is None else moment
        identifier = known_reason(reason) or REASON_UNSPECIFIED
        window = self._windows.get(identifier)
        if window is not None:
            opened, swallowed = window
            if 0 <= at - opened < REFUSAL_WINDOW_SECONDS:
                self._windows[identifier] = (opened, swallowed + 1)
                return
        stands_for = 1 if window is None else window[1] + 1
        self._windows[identifier] = (at, 0)
        try:
            audit_store = await self.store_provider()
            seq = await audit_store.append(
                # Six values and no seventh. Never an ``azp``, never an issuer, never an
                # audience, never a ``sub``, never a piece of the token and never a key id:
                # the token behind a refusal did not pass its signature check, so every value
                # in it is text a stranger chose, and a row carrying one would be the claim
                # leak this chain was created to keep out (T-24-04). ``actor`` stays empty for
                # that reason and not because nobody thought of it.
                Entry(
                    chain=CHAIN_EXCHANGE,
                    kind=KIND_REFUSAL,
                    at=at,
                    outcome=OUTCOME_REJECTED,
                    reason=identifier,
                    removed=stands_for,
                )
            )
            if store.should_sweep(seq):
                # The same fail-open bracket as the write itself, and on purpose inside it:
                # a sweep that throws must not turn a refusal into a 500 either.
                await audit_store.sweep(
                    moment=at,
                    retention_days=self.retention_days,
                    size_limit=self.size_limit,
                )
        except Exception as exc:
            # The type only, never the message: a store error can carry a path (D-13). One
            # line for both halves, because from the outside they are one step: the row is
            # missing, or the sweep that its number was the turn of did not run.
            logger.error(
                "a refused exchange attempt was not recorded or not swept: %s",
                type(exc).__name__,
            )

"""The braked write of the pre-authentication path: AUDIT-07 and threat T-24-02.

Every case here is written against one number. ``oauth/throttle.py`` lets a whole path class
produce up to ``PATH_CEILING`` refusals per window and per worker, which is in the order of
fifty to a hundred thousand rows a day, ordered by somebody who holds no key of this
deployment. An unbraked writer would turn that into a write load on the audit database and,
worse, into a way to push the history of real accounts out of the upper bound, because the
bound may only evict rows outside the instance chain. So the property under test is not "a
refusal is written down" but "a thousand refusals are one row, and the count of them is not
lost".

The store is a real SQLite file in ``tmp_path``, the way every other audit suite of this
repository works: what a row carries is a property of the file, and a double of the store
would assert the double. The one exception is the failing store, which is a double whose
``append`` raises, because a file that produces one is a corrupted file no test may write.

The clock is handed in and never read. ``note_refusal`` takes the moment as an argument for
the reason the sweep does: a brake whose window is measured against the wall clock of the
machine running the suite is a flaky test, and the edge of the window is exactly what several
cases here stand on.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

from mcp_connector.audit import refusals
from mcp_connector.audit.store import (
    CHAIN_EXCHANGE,
    KIND_CALL,
    KIND_REFUSAL,
    KIND_TOMBSTONE,
    OUTCOME_REJECTED,
    SWEEP_EVERY,
    AuditStore,
    Entry,
    _entry_of_row,
    user_chain,
)
from mcp_connector.errors import (
    REASON_EXCHANGE_CLAIMS,
    REASON_EXCHANGE_ISSUER,
    REASON_UNSPECIFIED,
    REASONS,
)

pytestmark = pytest.mark.anyio

#: The moment every case starts at, and a plain number so a window edge can be read off it.
NOW = 1_700_000_000

#: A path in the message of a store failure, the value the fail-open case must not find in a
#: log line: the type of the failure may be written down, its sentence may not (D-13).
BROKEN_PATH = "/var/lib/mcp_connector/audit.sqlite3"

#: Seconds in a day, so a retention window is written as days at every call site.
DAY = 86400

#: The window the sweep cases configure. Short and not the shipped one hundred and eighty,
#: so a case can put a row on either side of it without inventing a year.
RETENTION = 30

#: An account with a row of its own, so the cases about the shared counter can watch what
#: happens to a chain that has nothing to do with the exchange path.
ALICE = "alice"

#: A real tool of the allowlist, so a seeded call row is the row the recording path writes.
TOOL = "files_list"


def writer(tmp_path: Path) -> tuple[refusals.RefusalWriter, Path]:
    """A writer over a real store, and the file beside it so a case can read it back."""
    path = tmp_path / "audit.sqlite3"
    store = AuditStore(path)

    async def provider() -> AuditStore:
        return store

    return refusals.RefusalWriter(store_provider=provider), path


class ExplodingStore:
    """A store whose append raises, with a path in the message the way a real one would."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls = 0

    async def append(self, *_: Any, **__: Any) -> int:
        self.calls += 1
        raise sqlite3.OperationalError(f"database or disk is full: {self.path}")


class SweepingStore:
    """A store that appends the five hundredth row and then fails to sweep it.

    The shape of a full volume: the row still fits, the vacuum behind it does not. It is a
    double and not a file because a store that raises on a sweep is a broken store.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.sweeps = 0

    async def append(self, *_: Any, **__: Any) -> int:
        return SWEEP_EVERY

    async def sweep(self, *_: Any, **__: Any) -> None:
        self.sweeps += 1
        raise sqlite3.OperationalError(f"database or disk is full: {self.path}")


def writer_over(store: AuditStore, *, retention_days: int = RETENTION) -> refusals.RefusalWriter:
    """A writer over a store a case opened itself, so the case can seed rows beside it."""

    async def provider() -> AuditStore:
        return store

    return refusals.RefusalWriter(store_provider=provider, retention_days=retention_days)


def arm_the_next_row(path: Path, number: int) -> None:
    """Make the next appended row carry ``number``, through the counter AUTOINCREMENT keeps.

    The same helper ``tests/unit/test_audit_accounts.py`` uses, and for the same reason: the
    schedule of D-11 hangs on that number, and this is how a case reaches the five hundredth
    row without writing five hundred of them.
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = 'entries'", (number - 1,)
        )
        connection.commit()
    finally:
        connection.close()


def broken_writer() -> tuple[refusals.RefusalWriter, ExplodingStore]:
    exploding = ExplodingStore(Path(BROKEN_PATH))

    async def provider() -> AuditStore:
        return cast(AuditStore, exploding)

    return refusals.RefusalWriter(store_provider=provider), exploding


def written(path: Path) -> list[Any]:
    """Every row of the file, read past the store, youngest last."""
    if not path.exists():
        return []
    connection = sqlite3.connect(path)
    try:
        return [
            _entry_of_row(row)
            for row in connection.execute(
                "SELECT seq, chain, kind, at, actor, nc_user, tool, client_id, auth_id, "
                "client_name, outcome, reason, duration_ms, params, removed, gap_chain, "
                "gap_hash FROM entries ORDER BY seq"
            )
        ]
    finally:
        connection.close()


# --- the brake ---------------------------------------------------------------------------


async def test_a_thousand_refusals_of_one_reason_in_one_window_are_one_row(
    tmp_path: Path,
) -> None:
    """T-24-02, and the case the research names as the whole point of this module.

    The warning sign it was written against is a case that expects ``EXCHANGE_LIMIT`` rows:
    that number is what one source may produce before the throttle answers 429, and a writer
    braked to it would still be a stranger deciding how much this file grows.
    """
    subject, path = writer(tmp_path)

    for attempt in range(1000):
        await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + attempt % 60)

    rows = written(path)
    assert len(rows) == 1
    assert rows[0].removed == 1, "the first attempt is written at once and stands for itself"


async def test_the_first_refusal_of_a_window_is_written_without_a_delay(tmp_path: Path) -> None:
    """An operator sees a single attempt immediately: the brake holds back the repetition,
    never the first line, or a lone probe would be invisible until a second one arrived."""
    subject, path = writer(tmp_path)

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)

    (row,) = written(path)
    assert row.at == NOW
    assert row.removed == 1


async def test_the_next_window_carries_the_attempts_the_brake_swallowed(tmp_path: Path) -> None:
    """No counted attempt is lost: the second row stands for the 999 that wrote nothing plus
    the one that opened the new window."""
    subject, path = writer(tmp_path)

    for attempt in range(1000):
        await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + attempt % 60)
    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + refusals.REFUSAL_WINDOW_SECONDS)

    first, second = written(path)
    assert (first.removed, second.removed) == (1, 1000)
    assert first.removed + second.removed == 1001, "every attempt is accounted for exactly once"


async def test_the_window_edge_is_the_second_the_window_is_long(tmp_path: Path) -> None:
    """One second short of the window suppresses, exactly on it writes. The edge is asserted
    from both sides, because a brake that is one second wrong is a brake nobody notices."""
    subject, path = writer(tmp_path)
    edge = NOW + refusals.REFUSAL_WINDOW_SECONDS

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)
    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=edge - 1)
    assert len(written(path)) == 1

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=edge)
    assert [row.removed for row in written(path)] == [1, 2]


async def test_two_reasons_in_one_window_are_two_rows(tmp_path: Path) -> None:
    """The brake counts per reason, so the second group is not swallowed by the first."""
    subject, path = writer(tmp_path)

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)
    await subject.note_refusal(REASON_EXCHANGE_ISSUER, moment=NOW)
    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + 1)
    await subject.note_refusal(REASON_EXCHANGE_ISSUER, moment=NOW + 1)

    rows = written(path)
    assert [row.reason for row in rows] == [REASON_EXCHANGE_CLAIMS, REASON_EXCHANGE_ISSUER]
    assert [row.removed for row in rows] == [1, 1]


async def test_a_clock_that_stepped_back_opens_a_new_window_instead_of_closing_forever(
    tmp_path: Path,
) -> None:
    """An NTP correction or a resumed VM can hand a moment older than the one before it. A
    brake that only asks whether the difference is below the window would then suppress every
    further refusal until the clock caught up, which on a large step is hours of silence."""
    subject, path = writer(tmp_path)

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)
    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW - 86400)

    rows = written(path)
    assert [row.at for row in rows] == [NOW, NOW - 86400], "the second one is written, not eaten"
    assert [row.removed for row in rows] == [1, 1], "the first window had swallowed nothing"


async def test_the_state_of_the_brake_is_bounded_by_the_number_of_reasons(
    tmp_path: Path,
) -> None:
    """The one counter of this application, and it cannot grow: its keys are identifiers of a
    frozen set, so a stranger cannot make it hold a key of their choosing.

    Read off the file rather than off the object: five hundred invented reasons produce one
    row inside one window, which is only possible if all five hundred collapsed onto one key.
    A test that looked into the dictionary would assert the dictionary.
    """
    subject, path = writer(tmp_path)

    for attempt in range(500):
        await subject.note_refusal(f"invented-reason-{attempt}", moment=NOW + attempt % 60)

    rows = written(path)
    assert [row.reason for row in rows] == [REASON_UNSPECIFIED]
    assert rows[0].removed == 1
    assert REASON_UNSPECIFIED in REASONS, "and the one key is a known identifier, not free text"


async def test_a_writer_hashes_and_compares_by_where_it_writes_not_by_its_brake(
    tmp_path: Path,
) -> None:
    """IN-01: the brake is state, not identity. A frozen dataclass that let the dictionary
    into ``__eq__`` and ``__hash__`` would raise on ``hash()`` and would call two writers over
    the same store different the moment one of them had counted a refusal."""
    store = AuditStore(tmp_path / "audit.sqlite3")

    async def provider() -> AuditStore:
        return store

    first = refusals.RefusalWriter(store_provider=provider)
    second = refusals.RefusalWriter(store_provider=provider)
    assert hash(first) == hash(second)

    await first.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)

    assert first == second, "one of the two has braked, and they still write to the same place"
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


# --- what the row carries, and what it may never carry ------------------------------------


async def test_the_row_names_the_chain_the_kind_the_reason_and_the_count_and_nothing_else(
    tmp_path: Path,
) -> None:
    """T-24-04: the token behind a refusal was not checked, so no value out of it may reach a
    row. The columns that could carry one are named one by one rather than counted."""
    subject, path = writer(tmp_path)

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)

    (row,) = written(path)
    assert row.chain == CHAIN_EXCHANGE
    assert row.kind == KIND_REFUSAL
    assert row.at == NOW
    assert row.outcome == OUTCOME_REJECTED
    assert row.reason == REASON_EXCHANGE_CLAIMS
    assert row.removed == 1
    assert row.actor is None, "an unchecked token has no acting party that may be written down"
    assert (row.nc_user, row.tool, row.client_id, row.auth_id) == (None, None, None, None)
    assert (row.client_name, row.duration_ms) == (None, None)
    assert (row.gap_chain, row.gap_hash) == (None, None)
    assert tuple(row.params) == ()


async def test_an_unknown_reason_becomes_the_unspecified_identifier(tmp_path: Path) -> None:
    """The rule of ``errors.known_reason`` and not a second version of it: free text in the
    one column that exists in order to have none is the whole failure mode here."""
    subject, path = writer(tmp_path)

    await subject.note_refusal("the token is meant for another audience", moment=NOW)

    (row,) = written(path)
    assert row.reason == REASON_UNSPECIFIED


# --- the path is pre-authentication, so nothing here may end a request --------------------


async def test_a_store_that_throws_ends_no_call_and_the_line_names_only_the_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-24-19 and D-13. An exception out of here would be a 500 where a 401 belongs, and the
    message of a store failure can carry a path, so only its type is written down."""
    subject, exploding = broken_writer()

    with caplog.at_level(logging.DEBUG):
        await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)

    assert exploding.calls == 1
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "OperationalError" in logged
    assert BROKEN_PATH not in logged
    assert "database or disk is full" not in logged


async def test_a_sweep_that_throws_ends_no_call_either(caplog: pytest.LogCaptureFixture) -> None:
    """The sweep runs inside the same bracket as the write, not after it.

    A store that appends and then fails to sweep is the ordinary shape of a full volume, and
    on a path that runs before any authentication that must be a line in the log and never a
    500 a stranger can order.
    """
    sweeping = SweepingStore(Path(BROKEN_PATH))

    async def provider() -> AuditStore:
        return cast(AuditStore, sweeping)

    subject = refusals.RefusalWriter(store_provider=provider)

    with caplog.at_level(logging.DEBUG):
        await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)

    assert sweeping.sweeps == 1
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "OperationalError" in logged
    assert BROKEN_PATH not in logged


# --- the schedule of the sweep hangs on the number this path consumes (CR-24-01) ----------


async def test_the_refusals_of_this_chain_expire_when_nothing_else_ever_writes(
    tmp_path: Path,
) -> None:
    """Consequence one of the dropped sequence number.

    An instance with the log on and the exchange path armed, whose traffic is somebody
    else's attempts and not tool calls, has exactly one writer: this one. If it drops the
    number the store hands back, nothing in the process ever sweeps, and what
    ``docs/privacy.md`` promises about the ``x:exchange`` chain holds in SQL and not in
    operation: the rows lie there until the next container start.
    """
    path = tmp_path / "audit.sqlite3"
    store = AuditStore(path)
    subject = writer_over(store)

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW)
    arm_the_next_row(path, SWEEP_EVERY)
    await subject.note_refusal(REASON_EXCHANGE_ISSUER, moment=NOW + RETENTION * DAY + 1)

    rows = written(path)
    assert [row.reason for row in rows if row.kind == KIND_REFUSAL] == [REASON_EXCHANGE_ISSUER], (
        "the refusal older than the window is gone, the one that swept stands"
    )
    assert [row.kind for row in rows].count(KIND_TOMBSTONE) == 1, "and the gap is explained"


async def test_a_refusal_on_the_sweep_number_sweeps_the_whole_trail_and_not_only_its_own_chain(
    tmp_path: Path,
) -> None:
    """Consequence two, and the worse one.

    The numbers come out of one ``AUTOINCREMENT``. A refusal that consumes a multiple of
    :data:`SWEEP_EVERY` without asking would make that sweep happen never rather than late,
    and the rows it would have taken are in the user chains, whose window
    ``docs/privacy.md`` promises to a person. How often it happens is ordered from outside.
    """
    path = tmp_path / "audit.sqlite3"
    store = AuditStore(path)
    await store.append(
        Entry(
            chain=user_chain(ALICE),
            kind=KIND_CALL,
            at=NOW,
            nc_user=ALICE,
            tool=TOOL,
            outcome="ok",
        )
    )
    subject = writer_over(store)

    arm_the_next_row(path, SWEEP_EVERY)
    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + RETENTION * DAY + 1)

    kinds = [row.kind for row in written(path)]
    assert KIND_CALL not in kinds, "the expired row of a person went with this sweep"
    assert kinds.count(KIND_TOMBSTONE) == 1
    assert kinds.count(KIND_REFUSAL) == 1


async def test_a_refusal_that_is_not_the_five_hundredth_row_sweeps_nothing(
    tmp_path: Path,
) -> None:
    """The other side of the schedule: every row would be a sweep per refused attempt, which
    is a load a stranger orders. Only the number decides, exactly as on the recording path."""
    path = tmp_path / "audit.sqlite3"
    store = AuditStore(path)
    await store.append(
        Entry(
            chain=user_chain(ALICE),
            kind=KIND_CALL,
            at=NOW,
            nc_user=ALICE,
            tool=TOOL,
            outcome="ok",
        )
    )
    subject = writer_over(store)

    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + RETENTION * DAY + 1)

    kinds = [row.kind for row in written(path)]
    assert kinds == [KIND_CALL, KIND_REFUSAL], "row two of the file is not row five hundred"


async def test_the_sweep_of_this_writer_runs_the_window_it_was_configured_with(
    tmp_path: Path,
) -> None:
    """The other half of the configured window, the one the case above cannot see.

    That case proves the window is the short one an administrator set, because the row it
    removes would have survived the shipped one hundred and eighty days. This one proves the
    sweep is a window and not a broom: a row inside it stays, so a refusal landing on the
    five hundredth number cannot cost an instance the history it is still entitled to.
    """
    path = tmp_path / "audit.sqlite3"
    store = AuditStore(path)
    await store.append(
        Entry(
            chain=user_chain(ALICE),
            kind=KIND_CALL,
            at=NOW,
            nc_user=ALICE,
            tool=TOOL,
            outcome="ok",
        )
    )
    subject = writer_over(store, retention_days=RETENTION)

    arm_the_next_row(path, SWEEP_EVERY)
    # One day short of the configured window, and far inside the shipped one hundred and
    # eighty days, so only a sweep that used the configured number leaves this row standing.
    await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + (RETENTION - 1) * DAY)

    kinds = [row.kind for row in written(path)]
    assert kinds == [KIND_CALL, KIND_REFUSAL], "nothing was expired, and no marker was needed"


async def test_a_store_that_keeps_throwing_is_asked_once_per_window_and_no_more() -> None:
    """The brake is set before the write and not after it. A writer that only remembered a
    successful write would retry on every single request of a path a stranger drives, which
    is the very load T-24-02 is about, and a failing store is exactly when that matters."""
    subject, exploding = broken_writer()

    for attempt in range(1000):
        await subject.note_refusal(REASON_EXCHANGE_CLAIMS, moment=NOW + attempt % 60)

    assert exploding.calls == 1

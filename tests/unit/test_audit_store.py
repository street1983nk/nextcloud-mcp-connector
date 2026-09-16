"""The store of the audit log: the file, the chain, and what one row may carry.

Threats covered here: T-18-03 (a row changed after the fact), T-18-05 (a store that grows
without a bound) and T-18-01 (a value in the log).

Every check runs against a real SQLite file in ``tmp_path``, because the properties under
test are properties of the file: two writers that meet on the same chain, pages that move to
the free list when rows go, and a digest that has to be reproducible from the row alone. A
mock of the connection would assert the mock.
"""

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from mcp_connector.audit import store
from mcp_connector.oauth import store as oauth

pytestmark = pytest.mark.anyio

ALICE = store.user_chain("alice")
BOB = store.user_chain("bob")

#: The neighbour in the same volume, for the second half of success criterion 4. A key that
#: is not secret, because it never leaves this file, and the handful of values one connection
#: and one rotation need.
OAUTH_KEY = bytes(range(32))
CLIENT_ID = "client-4711"
AUTH_ID = "auth-0001"
FAMILY = "family-0001"
APP_PASSWORD = "app-password-of-alice"
RESOURCE = "https://cloud.example.com/exapps/mcp_connector/mcp"
FIRST_TOKEN = "refresh-token-before-the-rotation"
SECOND_TOKEN = "refresh-token-after-the-rotation"

#: A file name of a user, the kind of value a parameter of ``files_read`` carries. It is
#: never handed to the store: no method here takes a parameter value, and the check below
#: looks for it in every column to say so out loud (D-06, AUDIT-01).
A_VALUE = "kuendigung-2026.md"


def open_store(tmp_path: Path) -> store.AuditStore:
    return store.AuditStore(tmp_path / store.AUDIT_FILENAME)


def rows(tmp_path: Path) -> list[tuple[Any, ...]]:
    """Every row of the table, read out of the file behind the store's back."""
    conn = sqlite3.connect(tmp_path / store.AUDIT_FILENAME)
    try:
        return list(conn.execute("SELECT * FROM entries ORDER BY seq"))
    finally:
        conn.close()


def pragma(tmp_path: Path, name: str) -> Any:
    conn = sqlite3.connect(tmp_path / store.AUDIT_FILENAME)
    try:
        return conn.execute(f"PRAGMA {name}").fetchone()[0]
    finally:
        conn.close()


def pages_times_size(tmp_path: Path) -> int:
    """The number that looks like the size of the store and is not (18-RESEARCH.md §8)."""
    return pragma(tmp_path, "page_count") * pragma(tmp_path, "page_size")


def fill(tmp_path: Path, count: int) -> None:
    """Write ``count`` rows with an own connection, in one transaction.

    The rows carry no chain worth checking: this helper exists for the size case only, and
    going through :meth:`AuditStore.append` for two thousand rows would open two thousand
    connections for a measurement that is about pages, not about hashes.
    """
    conn = sqlite3.connect(tmp_path / store.AUDIT_FILENAME, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "INSERT INTO entries (chain, kind, at, nc_user, tool, client_id, auth_id, "
            "client_name, outcome, params, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f"u:user-{number % 7}",
                    store.KIND_CALL,
                    1_700_000_000 + number,
                    f"user-{number % 7}",
                    "files_search",
                    "client-4711",
                    f"auth-{number:06d}",
                    "A Client With A Name",
                    store.OUTCOME_OK,
                    '["query"]',
                    hashlib.sha256(f"prev-{number}".encode()).digest(),
                    hashlib.sha256(f"row-{number}".encode()).digest(),
                )
                for number in range(count)
            ],
        )
        conn.execute("COMMIT")
    finally:
        conn.close()


def drop_oldest(tmp_path: Path, count: int) -> None:
    """Remove rows with an own connection, the way a sweep of plan 18-04 will."""
    conn = sqlite3.connect(tmp_path / store.AUDIT_FILENAME, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM entries WHERE seq <= ?", (count,))
        conn.execute("COMMIT")
    finally:
        conn.close()


def file_names(tmp_path: Path) -> set[str]:
    """What the store laid down in its directory. Sync, like every other helper that touches
    the filesystem here: a path call inside an async test blocks the loop."""
    return {path.name for path in tmp_path.iterdir()}


def past_the_store(tmp_path: Path, statement: str, parameters: tuple[Any, ...]) -> None:
    """Change the file with a connection of its own, the way an attacker would.

    Never through a method of the module: a manipulation that went through the store would
    recompute the chain and prove nothing about the check.
    """
    conn = sqlite3.connect(tmp_path / store.AUDIT_FILENAME, isolation_level=None)
    try:
        conn.execute(statement, parameters)
    finally:
        conn.close()


async def write_calls(subject: store.AuditStore, chain: str, moments: list[int]) -> None:
    """One ordinary row per moment, through the public interface, so the chain is real."""
    for at in moments:
        await subject.append(
            store.Entry(
                chain=chain,
                tool="files_search",
                nc_user=chain.removeprefix("u:"),
                outcome=store.OUTCOME_OK,
                params=["query"],
                at=at,
            )
        )


def digest_of(row: tuple[Any, ...]) -> bytes:
    """Recompute the hash of a row from the row itself, as a check will have to."""
    canonical = row[: len(store.CANONICAL_FIELDS)]
    return hashlib.sha256(store._canonical(canonical) + row[-2]).digest()


# --- the file itself ------------------------------------------------------------------


async def test_a_fresh_file_carries_wal_incremental_vacuum_and_the_nineteen_columns(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await subject.size()

    assert pragma(tmp_path, "journal_mode") == "wal"
    assert pragma(tmp_path, "auto_vacuum") == 2
    conn = sqlite3.connect(tmp_path / store.AUDIT_FILENAME)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(entries)")]
    finally:
        conn.close()
    assert columns == [
        "seq",
        "chain",
        "kind",
        "at",
        "actor",
        "nc_user",
        "tool",
        "client_id",
        "auth_id",
        "client_name",
        "outcome",
        "reason",
        "duration_ms",
        "params",
        "removed",
        "gap_chain",
        "gap_hash",
        "prev_hash",
        "hash",
    ]
    # The seventeen that are hashed are these nineteen without the two hashes themselves.
    assert list(store.CANONICAL_FIELDS) == columns[:-2]


# --- the chain ------------------------------------------------------------------------


async def test_the_first_row_of_a_chain_points_at_genesis_and_the_second_at_the_first(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await subject.append(store.Entry(chain=ALICE, tool="files_search", nc_user="alice", at=1000))
    await subject.append(store.Entry(chain=ALICE, tool="notes_read", nc_user="alice", at=1001))

    first, second = rows(tmp_path)
    assert first[-2] == store.GENESIS
    assert len(store.GENESIS) == 32
    assert second[-2] == first[-1]


async def test_the_hash_of_a_row_can_be_recomputed_from_the_row(tmp_path: Path) -> None:
    subject = open_store(tmp_path)
    await subject.append(
        store.Entry(
            chain=ALICE,
            tool="files_read",
            nc_user="alice",
            client_id="client-4711",
            outcome=store.OUTCOME_REJECTED,
            reason="no_permission",
            duration_ms=42,
            params=["path"],
            at=1000,
        )
    )
    await subject.append(store.Entry(chain=ALICE, tool="notes_read", nc_user="alice", at=1001))

    for row in rows(tmp_path):
        assert digest_of(row) == row[-1]


async def test_twenty_simultaneous_writers_of_one_chain_leave_no_fork(tmp_path: Path) -> None:
    subject = open_store(tmp_path)
    await subject.size()  # the schema, so twenty threads do not race to lay it down

    await asyncio.gather(
        *(
            subject.append(store.Entry(chain=ALICE, tool="files_search", nc_user="alice", at=at))
            for at in range(1000, 1020)
        )
    )

    written = rows(tmp_path)
    assert len(written) == 20
    assert len({row[-2] for row in written}) == 20, "two rows with the same predecessor is a fork"
    expected = store.GENESIS
    for row in written:
        assert row[-2] == expected
        assert digest_of(row) == row[-1]
        expected = row[-1]


async def test_the_instance_chain_and_a_user_chain_do_not_extend_each_other(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await subject.append(store.Entry(chain=ALICE, tool="files_search", nc_user="alice", at=1000))
    await subject.append(
        store.Entry(
            chain=store.CHAIN_INSTANCE,
            kind=store.KIND_SWITCH,
            actor=store.ACTOR_UNKNOWN,
            reason="on",
            at=1001,
        )
    )
    await subject.append(store.Entry(chain=BOB, tool="notes_read", nc_user="bob", at=1002))

    alice, instance, bob = rows(tmp_path)
    assert instance[-2] == store.GENESIS
    assert bob[-2] == store.GENESIS
    assert alice[-2] == store.GENESIS
    assert instance[1] == store.CHAIN_INSTANCE
    assert instance[5] is None, "the instance chain has no account behind it"


async def test_last_entry_of_a_kind_skips_the_calls_between_two_switches(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await subject.append(
        store.Entry(chain=store.CHAIN_INSTANCE, kind=store.KIND_SWITCH, reason="on", at=1000)
    )
    await subject.append(
        store.Entry(chain=store.CHAIN_INSTANCE, kind=store.KIND_SWITCH, reason="off", at=1001)
    )
    await subject.append(store.Entry(chain=store.CHAIN_INSTANCE, tool="files_search", at=1002))

    switch = await subject.last_entry(store.CHAIN_INSTANCE, kind=store.KIND_SWITCH)
    assert switch is not None
    assert switch.reason == "off"
    assert switch.at == 1001

    youngest = await subject.last_entry(store.CHAIN_INSTANCE)
    assert youngest is not None
    assert youngest.kind == store.KIND_CALL

    assert await subject.last_entry(ALICE) is None


# --- the size -------------------------------------------------------------------------


async def test_size_falls_after_rows_go_and_page_count_times_page_size_does_not(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await subject.size()
    fill(tmp_path, 2000)

    before = await subject.size()
    pages_before = pages_times_size(tmp_path)
    assert before > 1  # more than one page in use, or the case measures nothing

    drop_oldest(tmp_path, 1000)

    after = await subject.size()
    pages_after = pages_times_size(tmp_path)
    assert after < before, "used_bytes has to fall, or the upper bound sweeps to an empty table"
    assert pages_after >= pages_before, "the pages stay: they moved to the free list"


# --- what a row may carry -------------------------------------------------------------


async def test_params_are_a_sorted_list_of_names_and_no_column_holds_a_value(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await subject.append(
        store.Entry(
            chain=ALICE,
            tool="files_read",
            nc_user="alice",
            outcome=store.OUTCOME_OK,
            params=["path", "format", "max_bytes"],
            at=1000,
        )
    )

    (row,) = rows(tmp_path)
    assert row[13] == '["format","max_bytes","path"]'
    assert json.loads(row[13]) == ["format", "max_bytes", "path"]
    assert A_VALUE not in " ".join(str(column) for column in row)


# --- what the check finds, and what it does not ---------------------------------------
# Three answers, not one: changed, missing, and explained. A check that only shouts "broken"
# fails success criterion 3 of the roadmap even when it is technically right.


async def test_a_row_changed_after_the_fact_is_named_with_its_own_number(tmp_path: Path) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001, 1002, 1003])

    past_the_store(tmp_path, "UPDATE entries SET tool = ? WHERE seq = ?", ("files_read", 3))

    (finding,) = await subject.verify_chains()
    assert finding.chain == ALICE
    assert finding.kind == store.FINDING_MODIFIED
    assert finding.seq == 3, "the changed row itself, not the one after it"
    assert finding.next_seq is None


async def test_a_removed_row_is_named_as_the_pair_of_numbers_it_was_between(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001, 1002, 1003])

    past_the_store(tmp_path, "DELETE FROM entries WHERE seq = ?", (3,))

    (finding,) = await subject.verify_chains()
    assert finding.chain == ALICE
    assert finding.kind == store.FINDING_MISSING
    assert (finding.seq, finding.next_seq) == (2, 4)


async def test_a_real_tombstone_explains_the_gap_and_leaves_no_finding(tmp_path: Path) -> None:
    """The difference between an explained and an unexplained hole, in one case.

    Both halves together are the proof: no finding **and** a marker that says which chain lost
    how many rows. Without the second half the case would also pass if the check were blind.
    """
    subject = open_store(tmp_path)
    old = 1_000_000_000
    young = old + 400 * 86400
    await write_calls(subject, ALICE, [old, old + 1, old + 2, old + 3])
    await write_calls(subject, ALICE, [young, young + 1])

    report = await subject.sweep(moment=young + 2)

    assert report.expired == 4
    assert report.tombstones == 1
    assert await subject.verify_chains() == []

    marker = [row for row in rows(tmp_path) if row[2] == store.KIND_TOMBSTONE]
    assert len(marker) == 1
    assert marker[0][1] == store.CHAIN_INSTANCE, "a marker hangs where the gap is not"
    assert marker[0][14] == 4
    assert marker[0][15] == ALICE
    assert marker[0][16] is not None
    assert marker[0][5] is None, "a marker carries no account and no value"


async def test_two_chains_and_the_finding_names_only_the_broken_one(tmp_path: Path) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001, 1002])
    await write_calls(subject, BOB, [1003, 1004, 1005])

    past_the_store(tmp_path, "UPDATE entries SET tool = ? WHERE seq = ?", ("notes_read", 5))

    findings = await subject.verify_chains()
    assert [(finding.chain, finding.kind, finding.seq) for finding in findings] == [
        (BOB, store.FINDING_MODIFIED, 5)
    ]


# --- the sweep ------------------------------------------------------------------------


async def test_the_retention_window_takes_the_old_rows_and_leaves_the_young_ones(
    tmp_path: Path,
) -> None:
    """180 days is the default of D-09 and is reachable without an argument."""
    assert store.RETENTION_DAYS == 180

    subject = open_store(tmp_path)
    moment = 1_000_000_000 + 400 * 86400
    just_over = moment - store.RETENTION_DAYS * 86400 - 1
    just_under = moment - store.RETENTION_DAYS * 86400 + 1
    await write_calls(subject, ALICE, [just_over - 10, just_over])
    await write_calls(subject, ALICE, [just_under, moment])

    report = await subject.sweep(moment=moment)

    assert report.expired == 2
    left = [row[3] for row in rows(tmp_path) if row[2] == store.KIND_CALL]
    assert left == [just_under, moment], "nothing younger than the window may go"

    shorter = await subject.sweep(moment=moment, retention_days=0)
    assert shorter.expired == 2, "the window is a parameter, not a law of nature"


async def test_a_backwards_clock_step_never_tears_a_hole_into_the_middle_of_a_chain(
    tmp_path: Path,
) -> None:
    """WR-02 of the phase 18 review, reproduced there against this store.

    ``at`` comes from the wall clock at write time, so an NTP correction or a VM resume can
    put a younger moment onto a higher sequence number. The window may then only take the
    expired **prefix** of a chain: an expired row behind a survivor has to stay, or the
    surviving head points at a hash no marker names and the check reports tampering where a
    clock corrected itself.
    """
    subject = open_store(tmp_path)
    base = 1_000_000_000
    jump = base + 400 * 86400  # the clock jumped forward and stepped back again
    await write_calls(subject, ALICE, [base, jump, base + 1, jump + 1])
    await write_calls(subject, BOB, [base, base + 1])

    report = await subject.sweep(moment=base + store.RETENTION_DAYS * 86400 + 10)

    # alice: only seq 1 is prefix-expired; seq 3 is old enough for the window but stands
    # behind the younger seq 2 and must stay. bob has no survivor and goes whole.
    assert report.expired == 3
    assert await subject.verify_chains() == [], "a clock step is not a tamper finding"
    left = [(row[0], row[1]) for row in rows(tmp_path) if row[2] == store.KIND_CALL]
    assert left == [(2, ALICE), (3, ALICE), (4, ALICE)]

    # once the survivor in front has expired too, the rest follows, whole at every step
    later = await subject.sweep(moment=jump + store.RETENTION_DAYS * 86400 + 10)
    assert later.expired == 3
    assert await subject.verify_chains() == []
    assert [row for row in rows(tmp_path) if row[2] == store.KIND_CALL] == []


async def test_the_upper_bound_stops_before_the_table_is_empty(tmp_path: Path) -> None:
    """The case falle 2 of the research asks for: a bound that sweeps to zero is broken."""
    subject = open_store(tmp_path)
    await subject.size()
    fill(tmp_path, 15000)

    before = await subject.size()
    limit = before // 2
    moment = 1_700_000_000  # older than every row, so the window takes nothing here

    report = await subject.sweep(moment=moment, size_limit=limit)

    assert report.expired == 0
    assert report.trimmed > 0
    calls = [row for row in rows(tmp_path) if row[2] == store.KIND_CALL]
    assert calls, "the bound may not sweep until the table is empty"
    assert report.used_bytes_after <= limit
    assert await subject.size() <= limit

    again = await subject.sweep(moment=moment, size_limit=limit)
    assert again.trimmed == 0
    assert again.tombstones == 0


async def test_the_sweep_leaves_the_instance_chain_standing(tmp_path: Path) -> None:
    """The register that explains every gap is the one chain that is never trimmed."""
    subject = open_store(tmp_path)
    old = 1_000_000_000
    await subject.append(
        store.Entry(
            chain=store.CHAIN_INSTANCE,
            kind=store.KIND_SWITCH,
            actor=store.ACTOR_UNKNOWN,
            reason="on",
            at=old,
        )
    )
    await write_calls(subject, ALICE, [old + 1, old + 2])

    report = await subject.sweep(moment=old + 400 * 86400, size_limit=0)

    assert report.expired == 2
    kinds = [row[2] for row in rows(tmp_path)]
    assert store.KIND_SWITCH in kinds, "the switch is older than the window and stays"
    assert store.KIND_CALL not in kinds
    assert kinds.count(store.KIND_TOMBSTONE) == 1


async def test_a_batch_whose_marker_cannot_be_written_removes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-01 of the phase 18 review: the marker is atomic with the deletion it explains.

    The fault is injected into the marker write of the one batch this sweep has. If deletion
    and marker were two commits, the rows would already be gone here and the next check would
    report tampering after a perfectly ordinary crash. In one transaction the batch rolls
    back whole: no row gone, no marker written, no finding.
    """
    subject = open_store(tmp_path)
    old = 1_000_000_000
    await write_calls(subject, ALICE, [old, old + 1, old + 2])

    def refuse(
        conn: sqlite3.Connection, moment: int, ends: dict[str, str], counts: dict[str, int]
    ) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(store, "_write_markers", refuse)

    with pytest.raises(sqlite3.OperationalError):
        await subject.sweep(moment=old + 400 * 86400)

    assert len([row for row in rows(tmp_path) if row[2] == store.KIND_CALL]) == 3
    assert [row for row in rows(tmp_path) if row[2] == store.KIND_TOMBSTONE] == []
    assert await subject.verify_chains() == []


async def test_a_crash_between_two_batches_leaves_every_committed_batch_explained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-01, the multi-batch half: every committed batch carries its own marker.

    The first batch goes through, the second dies mid-transaction. Whatever the crash left
    behind has to be a store the check calls whole: the surviving head points at the end the
    marker of the committed batch names, and the rolled back batch left no trace.
    """
    subject = open_store(tmp_path)
    old = 1_000_000_000
    await write_calls(subject, ALICE, [old, old + 1, old + 2, old + 3, old + 4])
    monkeypatch.setattr(store, "SWEEP_BATCH_ROWS", 2)

    real = store._write_markers
    batches = {"count": 0}

    def flaky(
        conn: sqlite3.Connection, moment: int, ends: dict[str, str], counts: dict[str, int]
    ) -> None:
        batches["count"] += 1
        if batches["count"] == 2:
            raise sqlite3.OperationalError("disk I/O error")
        real(conn, moment, ends, counts)

    monkeypatch.setattr(store, "_write_markers", flaky)

    with pytest.raises(sqlite3.OperationalError):
        await subject.sweep(moment=old + 400 * 86400)

    assert await subject.verify_chains() == [], "a crashed sweep is not a tamper finding"
    left = [row[0] for row in rows(tmp_path) if row[2] == store.KIND_CALL]
    assert left == [3, 4, 5], "batch one is gone, batch two rolled back whole"
    (marker,) = [row for row in rows(tmp_path) if row[2] == store.KIND_TOMBSTONE]
    assert marker[14] == 2, "the marker explains exactly the batch it was committed with"
    assert marker[15] == ALICE


# --- the register of markers: bounded, not append-only --------------------------------
# WR-03 of the phase 18 review: the instance chain is never swept, so an append-only
# register would crowd the actual audit rows out of the fixed budget over the years. Only
# the newest marker of a chain explains its surviving head (the sweep takes prefixes), so
# the trailing run of markers is consolidated instead of extended.


async def test_repeated_sweeps_consolidate_to_one_marker_per_chain(tmp_path: Path) -> None:
    """Four sweeps, one chain: the register holds one marker, not four.

    The counts of the superseded markers are summed into the survivor, so the overview
    still answers with the true number of rows that ever went, and the surviving head still
    points at the end the one marker names.
    """
    subject = open_store(tmp_path)
    base = 1_000_000_000
    ats = [base + day * 86400 for day in range(6)]
    await write_calls(subject, ALICE, ats)

    for day in range(1, 5):
        await subject.sweep(moment=ats[day] + store.RETENTION_DAYS * 86400)

    (marker,) = [row for row in rows(tmp_path) if row[2] == store.KIND_TOMBSTONE]
    assert marker[14] == 5, "the counts of the superseded markers are summed"
    assert marker[15] == ALICE
    assert await subject.verify_chains() == []
    assert [row[0] for row in rows(tmp_path) if row[2] == store.KIND_CALL] == [6]

    overview = await subject.overview()
    assert overview.tombstones == 1
    assert overview.explained_entries == 5, "the true total survives the consolidation"


async def test_two_chains_keep_one_consolidated_marker_each(tmp_path: Path) -> None:
    subject = open_store(tmp_path)
    base = 1_000_000_000
    far = base + 400 * 86400

    for round_number in range(3):
        await write_calls(subject, ALICE, [base + round_number])
        await write_calls(subject, BOB, [base + round_number])
        await subject.sweep(moment=far + round_number)

    markers = [row for row in rows(tmp_path) if row[2] == store.KIND_TOMBSTONE]
    assert sorted((row[15], row[14]) for row in markers) == [(ALICE, 3), (BOB, 3)]
    assert await subject.verify_chains() == []


async def test_a_switch_row_is_a_barrier_the_consolidation_never_crosses(
    tmp_path: Path,
) -> None:
    """The consolidation absorbs only the trailing run of markers. A switch row belongs to
    the record of D-15 and stays where it stands, and so do the markers older than it: the
    register grows with switches and chains, never with sweeps."""
    subject = open_store(tmp_path)
    base = 1_000_000_000
    far = base + 400 * 86400
    await write_calls(subject, ALICE, [base, base + 1])
    await subject.sweep(moment=far)
    await subject.append(
        store.Entry(
            chain=store.CHAIN_INSTANCE,
            kind=store.KIND_SWITCH,
            actor=store.ACTOR_UNKNOWN,
            outcome="off",
            at=far,
        )
    )
    await write_calls(subject, ALICE, [base + 2, base + 3])
    await subject.sweep(moment=far + 10)
    await write_calls(subject, ALICE, [base + 4, base + 5])
    await subject.sweep(moment=far + 20)

    kinds = [row[2] for row in rows(tmp_path)]
    assert kinds.count(store.KIND_SWITCH) == 1, "the switch is never absorbed"
    assert kinds.count(store.KIND_TOMBSTONE) == 2, "one marker before the barrier, one after"
    markers = [row for row in rows(tmp_path) if row[2] == store.KIND_TOMBSTONE]
    assert [row[14] for row in markers] == [2, 4], "only the run behind the barrier is summed"
    assert await subject.verify_chains() == []

    overview = await subject.overview()
    assert overview.explained_entries == 6, "the true total survives the barrier as well"


async def test_overview_measures_the_size_and_the_rows_the_sweep_may_take(
    tmp_path: Path,
) -> None:
    """The two numbers of the over-bound state (WR-03): how much the store occupies and how
    many rows a sweep may still take. Zero sweepable rows over the bound is the one state no
    sweep resolves, and the check command needs both numbers to say so."""
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001])
    await subject.append(
        store.Entry(
            chain=store.CHAIN_INSTANCE,
            kind=store.KIND_SWITCH,
            actor=store.ACTOR_UNKNOWN,
            outcome="on",
            at=1002,
        )
    )

    overview = await subject.overview()

    assert overview.entries == 3
    assert overview.sweepable_entries == 2, "the instance chain is never the sweep's to take"
    assert overview.used_bytes == await subject.size()
    assert overview.used_bytes > 0


# --- the neighbour in the same volume: AUDIT-03, T-18-05 ------------------------------
# The second half of success criterion 4 of the roadmap. The first half is the bound and
# the window above; this is the sentence "at a full volume token rotation and new
# connections keep working". Both files live in the one volume of D-01, so the question is
# about space and not about locks, and the answer is the bound plus the incremental vacuum
# that hands the pages back to the filesystem instead of to the free list.
#
# No case here depends on a measured time. A time threshold in a test is a random number on
# somebody else's hardware; the cost of one entry is a line in the summary of plan 18-10
# (measured 2026-08-29, Windows/NTFS) and stays a piece of evidence, not a promise.


async def test_the_oauth_store_still_rotates_and_connects_after_the_bound_bit(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await subject.size()
    fill(tmp_path, 15000)
    limit = await subject.size() // 2
    moment = 1_700_000_000  # older than every row, so the window takes nothing here

    report = await subject.sweep(moment=moment, size_limit=limit)

    assert report.trimmed > 0, "the bound has to bite, or this case measures nothing"
    assert await subject.size() <= limit

    neighbour = oauth.OAuthStore(tmp_path / oauth.STORE_FILENAME, OAUTH_KEY)
    await neighbour.save_client(CLIENT_ID, metadata_json='{"client_id": "client-4711"}')
    await neighbour.create_authorization(
        AUTH_ID,
        client_id=CLIENT_ID,
        nc_user="alice",
        nc_account_id="alice",
        app_password=APP_PASSWORD,
        scopes="nextcloud",
        resource=RESOURCE,
    )
    await neighbour.create_refresh_token(FIRST_TOKEN, auth_id=AUTH_ID, family_id=FAMILY)

    rotated = await neighbour.redeem_refresh_token(FIRST_TOKEN, successor=SECOND_TOKEN)

    assert rotated.outcome == oauth.REDEEM_OK, "the rotation is the write that may not fail"
    assert await neighbour.load_authorization(AUTH_ID) is not None, "and the new connection"
    assert await neighbour.load_refresh_token(SECOND_TOKEN) is not None
    assert await subject.size() <= limit, "the audit store is still under its own bound"


# --- reading rows out: read_entries ---------------------------------------------------
# The one method of this module that hands the content of a row over, and therefore the one
# with two bounds instead of none: T-19-11 (nothing of a caller in the statement) and
# T-19-12 (nothing unbounded in the answer, because 100 MB of this store are roughly
# 440.000 rows). Every case below runs against the real file for the same reason the rest of
# this file does.


async def test_read_entries_of_an_empty_store_is_an_empty_list(tmp_path: Path) -> None:
    subject = open_store(tmp_path)

    assert await subject.read_entries() == []
    assert file_names(tmp_path) <= {
        store.AUDIT_FILENAME,
        f"{store.AUDIT_FILENAME}-wal",
        f"{store.AUDIT_FILENAME}-shm",
    }, "a read lays down the schema of this store and nothing beside it"


async def test_read_entries_hands_the_youngest_row_over_first(tmp_path: Path) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001, 1002])

    read = await subject.read_entries()

    assert [row[0] for row in read] == [3, 2, 1], "newest first, which is what an admin looks for"
    assert [row[3] for row in read] == [1002, 1001, 1000]


async def test_read_entries_with_a_limit_below_the_number_of_rows_cuts_the_answer(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001, 1002, 1003, 1004])

    read = await subject.read_entries(limit=2)

    assert [row[0] for row in read] == [5, 4], "the two youngest, not the two oldest"


async def test_read_entries_with_a_limit_of_zero_or_below_answers_with_exactly_one_row(
    tmp_path: Path,
) -> None:
    """The lower bound of the clamp. Zero would be an answer nobody asked for and a negative
    number is ``LIMIT -5``, which SQLite reads as no limit at all: both ends of the clamp are
    there to keep an option nobody validated from meaning "everything"."""
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001, 1002])

    assert [row[0] for row in await subject.read_entries(limit=0)] == [3]
    assert [row[0] for row in await subject.read_entries(limit=-5)] == [3]


async def test_read_entries_with_a_chain_filter_leaves_every_other_chain_out(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1002])
    await write_calls(subject, BOB, [1001])
    await subject.append(
        store.Entry(
            chain=store.CHAIN_INSTANCE,
            kind=store.KIND_SWITCH,
            actor=store.ACTOR_UNKNOWN,
            outcome="on",
            at=1003,
        )
    )

    read = await subject.read_entries(chain=ALICE)

    assert {row[1] for row in read} == {ALICE}, "neither bob nor the instance chain"
    assert [row[0] for row in read] == [2, 1], "the numbers bob and the switch left over"
    assert [row[3] for row in read] == [1002, 1000]


async def test_read_entries_of_a_chain_nobody_wrote_to_is_an_empty_list_and_not_an_error(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001])

    assert await subject.read_entries(chain=store.user_chain("nobody")) == []


async def test_read_entries_cuts_a_limit_above_the_maximum_down_to_the_maximum(
    tmp_path: Path,
) -> None:
    """The upper end of the clamp, measured against more rows than the maximum, because a
    store with three rows in it would pass this assertion with no clamp at all."""
    subject = open_store(tmp_path)
    await subject.size()  # the schema, so the bulk insert below has a table
    fill(tmp_path, store.READ_LIMIT_MAX + 3)

    read = await subject.read_entries(limit=10**9)

    assert len(read) == store.READ_LIMIT_MAX
    assert read[0][0] == store.READ_LIMIT_MAX + 3, "cut at the old end, not at the young one"


async def test_read_entries_without_a_limit_stops_at_the_default(tmp_path: Path) -> None:
    subject = open_store(tmp_path)
    await subject.size()
    fill(tmp_path, store.READ_LIMIT_DEFAULT + 5)

    read = await subject.read_entries()

    assert len(read) == store.READ_LIMIT_DEFAULT
    assert store.READ_LIMIT_DEFAULT < store.READ_LIMIT_MAX, "or the default were no default"


async def test_read_entries_since_takes_the_moment_itself_and_not_the_one_before_it(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [999, 1000, 1001])

    read = await subject.read_entries(since=1000)

    assert [row[3] for row in read] == [1001, 1000], "the border belongs to the window"


async def test_read_entries_until_takes_the_moment_itself_and_not_the_one_after_it(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [999, 1000, 1001])

    read = await subject.read_entries(until=1000)

    assert [row[3] for row in read] == [1000, 999]


async def test_read_entries_puts_a_row_with_a_smaller_moment_than_its_predecessor_first(
    tmp_path: Path,
) -> None:
    """WR-02 against the read: ``at`` is the wall clock at write time, and a clock stepped
    backwards puts a smaller moment onto a higher sequence number. The youngest row of the
    chain is the one with the highest ``seq``, whatever its moment says.

    The moment is changed behind the store's back, which breaks the hash of that row. That is
    beside the point here: what is under test is the order of the answer, not the chain.
    """
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001, 1002])
    past_the_store(tmp_path, "UPDATE entries SET at = ? WHERE seq = ?", (500, 3))

    read = await subject.read_entries()

    assert [row[0] for row in read] == [3, 2, 1], "seq decides, or a clock step reorders history"
    assert [row[3] for row in read] == [500, 1001, 1000], "and the moments are not sorted at all"


async def test_read_entries_hands_an_account_with_a_control_character_over_untouched(
    tmp_path: Path,
) -> None:
    """The store cleans the one value it writes itself, the registered client name, and hands
    the account through as it is. Bracketing an account for an output line belongs immediately
    before that line (plan 19-06); a store that cleaned it here would hand a name over that
    does not match the chain it is in, and no reader could look the chain up again.
    """
    hostile = "al\nice"
    subject = open_store(tmp_path)
    await subject.append(
        store.Entry(
            chain=store.user_chain(hostile),
            tool="files_search",
            nc_user=hostile,
            client_name="Claude\nAssistant",
            outcome=store.OUTCOME_OK,
            at=1000,
        )
    )

    (row,) = await subject.read_entries()

    assert row[5] == hostile, "the account is handed over unchanged"
    assert row[1] == store.user_chain(hostile)
    assert row[9] == "Claude Assistant", "the client name is the one the store itself cleans"


async def test_read_entries_carries_the_number_the_canonical_fields_and_both_hashes(
    tmp_path: Path,
) -> None:
    subject = open_store(tmp_path)
    await write_calls(subject, ALICE, [1000, 1001])

    read = await subject.read_entries()

    for row in read:
        assert len(row) == len(store.CANONICAL_FIELDS) + 2
        assert isinstance(row[0], int), "row[0] is the number an output line needs"
        assert isinstance(row[-2], bytes), "the hashes stay raw bytes, they are not hex here"
        assert isinstance(row[-1], bytes)
        assert len(row[-2]) == 32
        assert len(row[-1]) == 32
        assert digest_of(row) == row[-1], "the answer is enough to recompute the chain"
        assert store._entry_of_row(row).tool == "files_search", "and the fields read as an Entry"
    assert read[0][-2] == read[1][-1], "the younger row points at the older one"

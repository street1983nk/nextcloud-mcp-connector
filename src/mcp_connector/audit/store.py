"""The audit log of this app, in a SQLite file of its own, next to the OAuth store.

**Why a second file and not a second table.** The log is swept, capped and read by an admin
command, which is SQL either way, but it must never take the write lock of the store that
answers OAuth requests. Two files, two connections, one volume (D-01): the volume is shared
on purpose, and what protects the neighbour there is the upper bound of this file, not its
name.

**Why the standard library and nothing else.** Every call runs in :func:`asyncio.to_thread`
with its own connection, which is the whole of what an async wrapper would add
(``oauth/store.py`` says the same about the same choice). There is no encryption here and no
data key either: a row of this log carries no secret, and a log that were encrypted with the
key of :mod:`mcp_connector.oauth.crypto` would become unreadable the moment an uninstall
removes that key.

**What a row carries and what it must not.** A user, a tool name, a moment, the calling
client, an outcome class, a duration, and of the parameters only the names that were set,
sorted (D-06). Never a parameter value, never a piece of a result, never an address of the
caller. Nothing in this module takes a value, so nothing here can write one.

**The chain, and the limit that belongs to it.** Every row carries the hash of its
predecessor in its own chain and its own SHA-256 over the canonical field list plus that
predecessor hash. This makes the unnoticed change of a single row visible: whoever edits a
row breaks its own hash, whoever removes one breaks the link of the next.

It does **not** protect against somebody who can write the file and recompute the chain.
Every part of the proof lives in the same file: there is no external anchor, no signature
with a key outside this volume, and no second place to check against. A forged marker for a
gap is indistinguishable from a real one. That is the honest boundary of this construction,
and it belongs in every text that describes it.
"""

import asyncio
import contextlib
import hashlib
import json
import sqlite3
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .text import printable

#: What every method below hands to the worker thread: one function, one connection, one
#: result. Naming it keeps the wrappers at the bottom readable and typed.
type Work[T] = Callable[[sqlite3.Connection], T]

__all__ = [
    "ACTOR_LIMIT",
    "ACTOR_UNKNOWN",
    "AUDIT_FILENAME",
    "CANONICAL_FIELDS",
    "CHAIN_EXCHANGE",
    "CHAIN_INSTANCE",
    "CLIENT_NAME_LIMIT",
    "EXCHANGE_CHAIN_PREFIX",
    "FINDING_MISSING",
    "FINDING_MODIFIED",
    "GENESIS",
    "KIND_CALL",
    "KIND_REFUSAL",
    "KIND_SWITCH",
    "KIND_TOMBSTONE",
    "OUTCOME_FAILED",
    "OUTCOME_OK",
    "OUTCOME_REJECTED",
    "READ_LIMIT_DEFAULT",
    "READ_LIMIT_MAX",
    "RETENTION_DAYS",
    "SIZE_LIMIT_BYTES",
    "SWEEP_BATCH_ROWS",
    "SWEEP_EVERY",
    "SWEEP_MAX_ROUNDS",
    "SWEEP_USER_CHECK_EVERY",
    "SWEEP_VACUUM_PAGES",
    "USER_CHAIN_PREFIX",
    "USER_SILENCE_DAYS",
    "AuditStore",
    "ChainFinding",
    "Entry",
    "StoreOverview",
    "SweepReport",
    "should_check_accounts",
    "should_sweep",
    "used_bytes",
    "user_chain",
]

#: The second file in the persistent volume of this app. The first one is called
#: ``oauth.sqlite3`` (``oauth/store.py``), so this one is named after what it holds too.
AUDIT_FILENAME = "audit.sqlite3"

# --- limits ---------------------------------------------------------------------------
# Every number this module lives by is one of the names below. A literal at a call site is
# a value nobody finds again when an instance turns out to need a different one.

#: Six months, the lower bound the phase was asked for (D-09). The retention window is the
#: limit that is meant to bite in practice; the size below is the one that catches an
#: instance nobody looked at for a year.
RETENTION_DAYS = 180

#: 100 MB of used pages (D-09). Measured at roughly 163 byte per row with raw hashes, this
#: is in the order of half a million entries, and it needs about 6 MB of air in the volume
#: for the write ahead log beside it.
SIZE_LIMIT_BYTES = 100_000_000

#: How many rows :meth:`AuditStore.read_entries` hands over when nobody said a number. The
#: bound above is what makes this one necessary: 100 MB are roughly 440.000 rows (measured in
#: 18-RESEARCH.md §8), and a read without a ceiling pulls every one of them into the memory of
#: a container that has other work to do. Two hundred is what an administrator reads in one
#: go, and asking again with a larger number costs one line.
READ_LIMIT_DEFAULT = 200

#: The number no option can go above, whatever it says. AppAPI calls the handler of an occ
#: command with ``timeout => 0`` and waits as long as it takes, so nothing outside this module
#: cuts a read short: the ceiling has to be here. Five thousand rows are far more than a
#: console shows and far less than the 440.000 that are the alternative.
READ_LIMIT_MAX = 5000

#: Every five hundredth entry pays for the sweep (D-11), which is roughly every 110 KB of
#: rows. No cron, no background task, no counter that would have to live between two
#: requests; the sequence number of the row that was just written is the whole schedule.
SWEEP_EVERY = 500

#: Only every twentieth sweep asks Nextcloud whether an account still exists (D-12). It is
#: the one step of the sweep that costs an HTTP call, so it runs a magnitude less often.
SWEEP_USER_CHECK_EVERY = 20

#: How long a chain has to be silent before the sweep asks whether its account is still
#: there (D-12). Thirty days is longer than a holiday and shorter than a quarter.
USER_SILENCE_DAYS = 30

#: How many rows one transaction of the sweep may take. The write ahead log cannot be
#: checkpointed while a transaction is open, so a single sweep of ten thousand rows grew it
#: to 5.5 MB in the measurement of 18-RESEARCH.md; a bounded batch keeps that flat.
SWEEP_BATCH_ROWS = 5000

#: How many batches the upper bound may take in one run. Twenty times five thousand rows is
#: far more than one run can ever have to give up, and the number exists for the case it does
#: not cover: a store that is over the bound with no user row left in it is a different fault
#: (a swollen instance chain, a page size nobody expected) and must not end in an endless
#: loop. That state is not silent either: :meth:`AuditStore.overview` measures it and the
#: check command of AUDIT-02 names it (WR-03).
SWEEP_MAX_ROUNDS = 20

#: How many free pages one incremental vacuum hands back to the filesystem. Ten thousand pages
#: is about 40 MB at the usual page size, so one run gives everything back that one sweep can
#: possibly have freed, and the pragma stops by itself when the free list is empty.
SWEEP_VACUUM_PAGES = 10000

#: Seconds in a day, so the retention window is written as days at every call site.
_DAY_SECONDS = 86400

#: The registered client name arrives from the outside and is written by whoever registers.
#: Eighty characters is what the admin output can print on one line; the rest is cut, and
#: control characters never enter a row at all.
CLIENT_NAME_LIMIT = 80

#: The bound of the acting party of a delegation, the ``azp`` of an exchanged token
#: (AUDIT-07). The same number as ``oauth.exchange_accounts.MAX_ACTING_PARTY_LENGTH`` and
#: named a second time here rather than imported: ``audit`` may not import from ``oauth``
#: (the layering rule of ``audit/record.py``), and a bound this module applies has to stand
#: in this module. Below :data:`CLIENT_NAME_LIMIT` on purpose, for the reason the other
#: constant gives as well: the value is never looked up, only printed, and it shares an
#: output line with a client name that may want the eighty.
ACTOR_LIMIT = 64

#: How long the loser of a lock waits for the winner. Long enough for a transaction that
#: writes one row, short enough that a wedged process answers instead of hanging.
_BUSY_TIMEOUT_MS = 5000
_BUSY_TIMEOUT_SECONDS = _BUSY_TIMEOUT_MS / 1000

#: What the first row of a chain points at. Thirty-two zero bytes, the length of a SHA-256
#: digest, so the first link has the same shape as every other one.
GENESIS = b"\x00" * 32

#: D-16: the administrator behind a switch cannot be determined today, because AppAPI drops
#: the user of an admin form before the app sees it. The column exists from the first
#: version so that a later way to learn the name needs no schema change, and until then it
#: says so in one word. The code writes its strings in English.
ACTOR_UNKNOWN = "unknown"

# --- chains ------------------------------------------------------------------------------
# One table, three kinds of chain, told apart by the identifier in the ``chain`` column. A
# chain per user (D-02) so that removing one account removes one whole chain instead of
# breaking everybody else's, one chain for what happens to the instance (D-03), and one for
# the attempts that were turned down before anybody was authenticated (AUDIT-07).

#: The chain of instance events: the switch of D-15, and the markers for user chains that
#: are gone (a marker for a removed chain has nobody left to attach to in that chain).
CHAIN_INSTANCE = "i:instance"

#: The prefix of a user chain, named because two functions below have to agree on it: one
#: builds an identifier out of an account and the other reads the account back out of it.
USER_CHAIN_PREFIX = "u:"

#: The prefix of the third kind, so the identifier below can never collide with an account
#: however that account is named, exactly like :data:`USER_CHAIN_PREFIX` promises for its own.
EXCHANGE_CHAIN_PREFIX = "x:"

#: The refused attempts of the token exchange path (AUDIT-07), and deliberately **not** a
#: part of :data:`CHAIN_INSTANCE`. The instance chain is spared by every statement of the
#: sweep below, so a row put there never expires, and these rows are ordered from outside: the
#: exchange path runs before any authentication, so a stranger who holds no key of this
#: deployment decides how many of them are written. They have to fall under the retention
#: window and under the upper bound like the row of an account, and a chain outside the
#: instance chain is what makes them do so without a single statement changing.
#:
#: One chain and not one per issuer or per acting party: the identifier of a chain would then
#: be a value out of a token nobody checked, which is the claim leak this phase exists to keep
#: out of the file (T-24-04).
CHAIN_EXCHANGE = f"{EXCHANGE_CHAIN_PREFIX}exchange"


def user_chain(nc_user: str) -> str:
    """The chain identifier of one account. Prefixed, so it can never collide with
    :data:`CHAIN_INSTANCE` however an account is named."""
    return f"{USER_CHAIN_PREFIX}{nc_user}"


def _account_of(chain: str) -> str:
    """The account behind a chain identifier, the exact inverse of :func:`user_chain`.

    Read off the identifier and not out of the ``nc_user`` column, because the column is
    ``NULL`` for a row of the instance chain and the identifier is what a chain is grouped by
    anyway. The round trip is exact: a name that goes through :func:`user_chain` comes back
    out of here unchanged, whatever characters are in it.
    """
    return chain.removeprefix(USER_CHAIN_PREFIX)


# --- kinds of a row ----------------------------------------------------------------------

#: One tool call, the ordinary row (D-05: one row after the call, not a pair around it).
KIND_CALL = "call"

#: A row that explains a gap: rows that gave way to the upper bound, or a whole chain that
#: went with its account (D-10, D-12). It carries the count and the end of what it replaces.
KIND_TOMBSTONE = "tombstone"

#: The log being switched on or off, which is itself logged (D-15).
KIND_SWITCH = "switch"

#: An attempt over the token exchange path that was turned down, standing for as many of them
#: as ``removed`` says (AUDIT-07). A fourth value in this column and not an eighteenth column:
#: ``kind`` is already a text column of the schema, so a new value in it changes no hash, needs
#: no migration and leaves :data:`CANONICAL_FIELDS` exactly as it was. A column would have
#: done all three.
KIND_REFUSAL = "refusal"

# --- outcome classes (D-07) ---------------------------------------------------------------
# A class, never the sentence of an error: an error message of this server is written for
# the model and therefore carries paths and names, which would be result content.

OUTCOME_OK = "ok"
OUTCOME_REJECTED = "rejected"
OUTCOME_FAILED = "failed"

# --- what a check can find ----------------------------------------------------------------
# Two kinds, deliberately told apart: "somebody edited this row" and "something is gone or was
# pushed in between these two rows" are different events with different answers, and a check
# that only shouts "broken" leaves the administrator with the whole file to look at.

#: The row does not match its own hash: it was changed after it was written.
FINDING_MODIFIED = "modified"

#: The row does not point at its predecessor: a row between the two is gone or was inserted.
FINDING_MISSING = "missing"

#: The schema of 18-RESEARCH.md §4, plus the three columns that are here from the first
#: version rather than through a later migration: ``actor`` (D-16) and the two a marker for
#: a gap needs (``gap_chain``, ``gap_hash``). ``CREATE TABLE IF NOT EXISTS`` is the whole
#: migration for a second process opening the same file.
SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
  -- AUTOINCREMENT and not a plain rowid: SQLite would otherwise hand out max(rowid)+1, and
  -- a sweep that removed the newest rows would make one number appear twice. A number that
  -- is reused is a chain that cannot be checked, because the number is hashed with the row.
  seq         INTEGER PRIMARY KEY AUTOINCREMENT,
  -- 'u:<nc_user>', 'i:instance' or 'x:exchange' (D-02, D-03, AUDIT-07). Three kinds of chain
  -- in one table, told apart here and nowhere else.
  chain       TEXT NOT NULL,
  -- 'call' | 'tombstone' | 'switch' | 'refusal'
  kind        TEXT NOT NULL,
  -- Unix seconds. The moment the row was written, never a moment from a request.
  at          INTEGER NOT NULL,
  -- Who acted, and it says two things because two kinds of row need it. In a 'switch' or a
  -- 'tombstone' row it is 'unknown' (D-16), until there is a way to learn the administrator
  -- behind it. In a 'call' row of the token exchange path it is the acting party of a
  -- foreign realm, cleaned and cut like a client name because it comes from outside just as
  -- much (AUDIT-07). In every other 'call' row it is NULL: nobody delegated anything.
  actor       TEXT,
  -- NULL in the instance chain, which has no account behind it.
  nc_user     TEXT,
  tool        TEXT,
  client_id   TEXT,
  auth_id     TEXT,
  -- The name from the dynamic registration, cleaned and cut: it comes from outside.
  client_name TEXT,
  outcome     TEXT,
  -- D-07: a fixed identifier of a refusal, never a message of an error.
  reason      TEXT,
  duration_ms INTEGER,
  -- A sorted JSON list of parameter names, never a value (D-06, AUDIT-01).
  params      TEXT NOT NULL,
  -- For how many events this one row stands, which is the same meaning twice and is written
  -- out because the second reading arrived later: in a 'tombstone' row it is how many rows
  -- gave way to this marker, in a 'refusal' row how many turned down attempts this line
  -- stands for, because the writer of those is braked and only writes one per reason and
  -- window (AUDIT-07). Without this sentence the second reading would be a silent
  -- reinterpretation of a column.
  removed     INTEGER,
  -- Which chain the gap belongs to, for a marker that stands in the instance chain because
  -- the chain it explains is gone (D-12).
  gap_chain   TEXT,
  -- The last hash of the block that gave way, as hex so the canonical form stays JSON.
  gap_hash    TEXT,
  -- 32 raw bytes each. Hex would cost 64 byte more per row and buy nothing: unlike the
  -- token digests of the OAuth store, these two are never looked up by value.
  prev_hash   BLOB NOT NULL,
  hash        BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS entries_chain_seq ON entries(chain, seq);
CREATE INDEX IF NOT EXISTS entries_at ON entries(at);
"""

#: The field order of the canonical form, decided once and unchangeable afterwards: every
#: column except the two hashes, ``seq`` first. ``seq`` is part of it because a row could
#: otherwise be renumbered inside its own chain without breaking a hash.
CANONICAL_FIELDS: tuple[str, ...] = (
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
)

# The four statements of this module, assembled once from the field list above rather than
# written out a second time: two hand written column lists are how an insert and a digest
# end up meaning different things. Nothing of a caller enters any of them, every part is a
# name from :data:`CANONICAL_FIELDS`, and every value travels as a placeholder.
_COLUMNS = ", ".join(CANONICAL_FIELDS)
_PLACEHOLDERS = ", ".join("?" * (len(CANONICAL_FIELDS) + 2))
_INSERT = f"INSERT INTO entries ({_COLUMNS}, prev_hash, hash) VALUES ({_PLACEHOLDERS})"  # noqa: S608 - column names of this module, values are placeholders
_LAST_OF_CHAIN = "SELECT hash FROM entries WHERE chain = ? ORDER BY seq DESC LIMIT 1"
_LAST_ROW_OF_CHAIN = f"SELECT {_COLUMNS} FROM entries WHERE chain = ? ORDER BY seq DESC LIMIT 1"  # noqa: S608 - same column names, same placeholders
_LAST_ROW_OF_KIND = (
    f"SELECT {_COLUMNS} FROM entries WHERE chain = ? AND kind = ? ORDER BY seq DESC LIMIT 1"  # noqa: S608 - same column names, same placeholders
)
_CHAINS = "SELECT DISTINCT chain FROM entries ORDER BY chain"
_ROWS_OF_CHAIN = f"SELECT {_COLUMNS}, prev_hash, hash FROM entries WHERE chain = ? ORDER BY seq"  # noqa: S608 - same column names, no value in the statement
# The read of AUDIT-04. Three filters, each of them a pair of placeholders so that a filter
# nobody set is the statement saying so and not a second statement: ``? IS NULL OR column =
# ?`` is one text for eight combinations. The limit is a placeholder as well, clamped by
# :meth:`AuditStore.read_entries` before it gets here.
_READ_ROWS = (
    f"SELECT {_COLUMNS}, prev_hash, hash FROM entries "  # noqa: S608 - column names of this module, values are placeholders
    "WHERE (? IS NULL OR chain = ?) AND (? IS NULL OR at >= ?) AND (? IS NULL OR at <= ?) "
    "ORDER BY seq DESC LIMIT ?"
)
_EXPLAINED_GAPS = (
    "SELECT gap_chain, gap_hash FROM entries "
    "WHERE chain = ? AND kind = ? AND gap_chain IS NOT NULL AND gap_hash IS NOT NULL"
)

# The three counting statements of :meth:`AuditStore.overview`. They are aggregates and touch
# no row of a caller: what they answer is how much there is, never what is in it. The third
# one counts what the sweep is allowed to take, which is every row outside the instance
# chain: zero of those while the store is over its bound is the one state no sweep resolves,
# and the check command needs the number to say so (WR-03).
_TOTALS = "SELECT COUNT(DISTINCT chain), COUNT(*) FROM entries"
_MARKER_TOTALS = "SELECT COUNT(*), COALESCE(SUM(removed), 0) FROM entries WHERE kind = ?"
_SWEEPABLE_TOTAL = "SELECT COUNT(*) FROM entries WHERE chain <> ?"

# The four statements of the sweep. ``chain <> ?`` is the instance chain being spared, and it
# is written into the statement instead of into a comment, because a sweep that trimmed the
# instance chain would remove the very rows that explain the gaps of every other one.
#
# The retention pair does not take every expired row: it takes the expired **prefix** of each
# chain, so a row only goes when every row before it in its own chain goes too. ``at`` comes
# from the wall clock at write time, and a clock stepped backwards (an NTP correction, a VM
# resume) puts a younger moment onto a higher sequence number; a bare ``at``-predicate would
# then tear rows out of the middle of a chain, and the surviving row behind the hole would
# point at a hash no marker names, which the check reports as tampering that never happened
# (WR-02 of the phase 18 review, reproduced against this store). An expired row behind a
# survivor therefore stays until the survivor expires as well. The subquery names the first
# surviving row of the chain, and ``COALESCE(..., seq + 1)`` is the chain that has none, in
# which case the whole chain is expired.
#
# The two reads pick a bounded batch, the two removals take exactly what the read returned:
# the batch is ordered by ``seq``, so every row of the same predicate up to the last number of
# the batch is in it, and ``seq <= ?`` therefore removes that batch and nothing else.
#
# The two removals are named ``_DROP_*`` and not ``_DELETE_*`` on purpose. The gate of
# tests/contract/test_no_destructive_calls.py exempts two exact SQL forms in this file, not
# the file itself, so a call site that carried the word would be a finding, and widening the
# exemption to cover it would also hide an HTTP DELETE written in this module one day.
_EXPIRED_PREFIX = (
    "seq < COALESCE((SELECT MIN(survivor.seq) FROM entries AS survivor "
    "WHERE survivor.chain = entries.chain AND survivor.at > ?), entries.seq + 1)"
)
_EXPIRED_ROWS = (
    f"SELECT seq, chain, hash FROM entries WHERE chain <> ? AND {_EXPIRED_PREFIX} "  # noqa: S608 - the fragment is a constant of this module, every value is a placeholder
    "ORDER BY seq LIMIT ?"
)
_OLDEST_ROWS = "SELECT seq, chain, hash FROM entries WHERE chain <> ? ORDER BY seq LIMIT ?"
_DROP_EXPIRED = f"DELETE FROM entries WHERE chain <> ? AND {_EXPIRED_PREFIX} AND seq <= ?"  # noqa: S608 - same fragment, same placeholders
_DROP_OLDEST = "DELETE FROM entries WHERE chain <> ? AND seq <= ?"

# The two statements of the marker consolidation (:func:`_write_markers`, WR-03). The read
# walks the instance chain newest first and is stopped in Python at the first row that is not
# a marker for a gap, so a switch row is a barrier the consolidation never crosses. The
# removal takes exactly the rows of that trailing run, one sequence number at a time, and only
# ever the tail of the chain: a new marker appended in the same transaction attaches to the
# row before the absorbed run, so no hole opens and the instance chain stays verifiable link
# by link.
_INSTANCE_TAIL = (
    "SELECT seq, kind, at, removed, gap_chain, gap_hash FROM entries "
    "WHERE chain = ? ORDER BY seq DESC"
)
_DROP_SUPERSEDED = "DELETE FROM entries WHERE chain = ? AND seq = ?"

# The three statements of the account check (D-12). The filter is positive and names the
# prefix of a user chain, where it used to be negative and only spared the instance chain.
# That was the same set while there were two kinds of chain and stopped being it with the
# third: the refused attempts of the token exchange path stand in ``x:exchange`` (AUDIT-07),
# that chain is silent by nature, and it has no account behind it any more than the instance
# chain has. Offered as one it would be held against a list of Nextcloud accounts it can never
# be in and deleted by ``drop_user_chain``, which is a marker over a record that was never a
# person's. So the rule of this statement is what the check really asks about: the chains of
# accounts, and no other kind, whatever kinds arrive after this one.
#
# ``substr`` and not ``LIKE``: SQLite folds ASCII case in ``LIKE``, so a chain spelled with a
# capital letter in front of the colon would pass a pattern built from the lower case prefix.
# And the prefix travels as a placeholder out of :data:`USER_CHAIN_PREFIX` rather than being
# spelled into this text a second time, so the two cannot drift apart.
#
# The grouping is by chain and not by ``nc_user``, because the chain is what is dropped and
# what a marker for a gap names, and a row of a chain whose ``nc_user`` column were ever
# ``NULL`` would otherwise fall out of the question entirely.
_SILENT_CHAINS = (
    "SELECT chain FROM entries WHERE substr(chain, 1, ?) = ? "
    "GROUP BY chain HAVING MAX(at) <= ? ORDER BY chain"
)
_COUNT_OF_CHAIN = "SELECT COUNT(*) FROM entries WHERE chain = ?"
_DROP_CHAIN = "DELETE FROM entries WHERE chain = ?"


def _now() -> int:
    """Unix seconds. One function, so a row never carries a moment of a request."""
    return int(time.time())


@dataclass(frozen=True, slots=True)
class Entry:
    """One row on its way in, without the three fields the store itself decides.

    ``seq``, ``prev_hash`` and ``hash`` are missing on purpose: they are the parts of the
    chain, and a caller that could set them could fork it. Everything else is a plain value
    of the row, and ``params`` is a list of names, never of values (D-06).
    """

    chain: str
    kind: str = KIND_CALL
    at: int = field(default_factory=_now)
    actor: str | None = None
    nc_user: str | None = None
    tool: str | None = None
    client_id: str | None = None
    auth_id: str | None = None
    client_name: str | None = None
    outcome: str | None = None
    reason: str | None = None
    duration_ms: int | None = None
    params: Sequence[str] = ()
    removed: int | None = None
    gap_chain: str | None = None
    gap_hash: str | None = None


@dataclass(frozen=True, slots=True)
class ChainFinding:
    """One broken place in one chain, as data and never as a finished sentence.

    The wording an administrator reads is built by the check command (plan 18-08), so the
    same finding can also be handed out machine readable. What stands here is only what was
    measured: which chain, which of the two kinds, and the number or the pair of numbers the
    place is between.

    ``kind`` is :data:`FINDING_MODIFIED` for a row whose content no longer matches its own
    hash; ``seq`` is that row. It is :data:`FINDING_MISSING` for a row that does not point at
    its predecessor; ``seq`` is the row before the gap and ``next_seq`` the row after it.
    ``next_seq`` stays ``None`` when the gap is at the head of the chain, because there is no
    row before it to name.
    """

    chain: str
    kind: str
    seq: int
    next_seq: int | None = None


@dataclass(frozen=True, slots=True)
class SweepReport:
    """What one sweep did, so a test and later the admin command can read the effect off it.

    ``expired`` is the number of rows the retention window took, ``trimmed`` the number the
    upper bound took, ``tombstones`` how many chains got a marker for their gap, and
    ``used_bytes_after`` the measurement of :func:`used_bytes` when the run was over.
    """

    expired: int
    trimmed: int
    tombstones: int
    used_bytes_after: int


@dataclass(frozen=True, slots=True)
class StoreOverview:
    """How much there is, so a check can say what it looked at and what a gap is worth.

    ``chains`` and ``entries`` are what the check walked. ``tombstones`` is how many markers
    for a gap the instance chain carries and ``explained_entries`` how many rows they stand
    for together, which is the difference between an explained hole and an unexplained one:
    without those two numbers the sentence "no break found" would read the same over a store
    that gave half its rows to the upper bound as over one that never lost a row.

    ``used_bytes`` and ``sweepable_entries`` exist for the one state no sweep resolves: over
    the bound of :data:`SIZE_LIMIT_BYTES` with nothing outside the instance chain left to
    take. The bound may only evict user rows, so without these two numbers that state would
    stay silent forever, and the check command is where it has to become visible (WR-03).

    Counts and one measurement, and that is the rule of this class: nothing here names a
    chain, an account or a row, so the answer of the check command stays as free of content
    as the log itself.
    """

    chains: int
    entries: int
    tombstones: int
    explained_entries: int
    used_bytes: int
    sweepable_entries: int


def should_sweep(seq: int) -> bool:
    """True for every :data:`SWEEP_EVERY`-th row: the whole schedule of D-11.

    The sequence number of the row that was just written **is** the interval. A counter on
    module level is forbidden (D-20), a cron would not run on an instance that never sees an
    occ command, and a background task would have to survive a restart it cannot promise to
    survive. This function is pure, so the schedule is a case in a test and not a stopwatch.
    """
    return seq % SWEEP_EVERY == 0


def should_check_accounts(seq: int) -> bool:
    """True for every :data:`SWEEP_USER_CHECK_EVERY`-th sweep, on the same number.

    The question whether an account still exists (D-12) is the one step of the sweep that
    costs an HTTP call to Nextcloud, so it runs a magnitude less often than the rest.
    """
    return seq % (SWEEP_EVERY * SWEEP_USER_CHECK_EVERY) == 0


def _canonical(fields: tuple[Any, ...]) -> bytes:
    """The one byte form a row is hashed in, in the order of :data:`CANONICAL_FIELDS`.

    JSON and not a separator of our own: a separator inside a value would otherwise be able
    to fake a field boundary, and JSON escapes it instead. ``ensure_ascii=False`` keeps a
    name with an umlaut one character rather than six, which changes nothing about the
    digest as long as both sides agree, and they do, because this is the only writer.
    """
    return json.dumps(list(fields), separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _clean_client_name(value: str | None) -> str | None:
    """The registered name of a client, made safe to print and bounded in length.

    The name arrives from a dynamic registration, so it is written by whoever registers: two
    hundred characters with line breaks in them would make the output of the admin command
    unreadable and could fake a row of its own.

    The rule is :func:`mcp_connector.audit.text.printable` and stands there once for the whole
    application. It used to stand here as well, and in ``audit/record.py`` and
    ``exapp/audit_verify.py`` in versions of their own: this one replaced the C0 range and DEL
    and the one in ``record.py`` filtered by ``str.isprintable``, so three versions with two
    different sets of characters were R-18-06 of phase 18, and the narrow set let a
    right-to-left override reach an output line. What is left here is the bound,
    :data:`CLIENT_NAME_LIMIT`, and the ``None`` of a client that registered without a name.
    """
    if value is None:
        return None
    return printable(value, limit=CLIENT_NAME_LIMIT) or None


def _clean_actor(value: str | None) -> str | None:
    """Who acted, made safe to print and bounded at :data:`ACTOR_LIMIT`.

    The same rule as :func:`_clean_client_name` and deliberately not a second idea of what is
    printable: over the token exchange path this column carries the ``azp`` of a foreign
    realm, so it is written by somebody who is not this application, exactly like a name from
    a dynamic registration. ``oauth.exchange_accounts.acting_party`` already filtered the
    value on its way into the identity, with ``str.isprintable`` and nothing else; that is a
    narrower rule than :func:`mcp_connector.audit.text.printable`, which also collapses runs
    of whitespace, and a column that trusted the earlier filter would be the fourth version
    of one rule (R-18-06).

    :data:`ACTOR_UNKNOWN` passes through unchanged, which is what a ``switch`` or
    ``tombstone`` row needs, and a value that is empty afterwards is ``None``, because
    "nothing left to print" names nobody.
    """
    if value is None:
        return None
    return printable(value, limit=ACTOR_LIMIT) or None


def _row_values(seq: int, entry: Entry) -> tuple[Any, ...]:
    """The row in the order of :data:`CANONICAL_FIELDS`, which is the order it is hashed in.

    One function for the insert and for the digest, because two hand written field lists are
    how a chain ends up unverifiable against the rows it is made of.
    """
    return (
        seq,
        entry.chain,
        entry.kind,
        entry.at,
        _clean_actor(entry.actor),
        entry.nc_user,
        entry.tool,
        entry.client_id,
        entry.auth_id,
        _clean_client_name(entry.client_name),
        entry.outcome,
        entry.reason,
        entry.duration_ms,
        json.dumps(sorted(entry.params), separators=(",", ":"), ensure_ascii=False),
        entry.removed,
        entry.gap_chain,
        entry.gap_hash,
    )


def _entry_of_row(row: tuple[Any, ...]) -> Entry:
    """One shape for every reader of a row, in the column order of the canonical form."""
    return Entry(
        chain=row[1],
        kind=row[2],
        at=row[3],
        actor=row[4],
        nc_user=row[5],
        tool=row[6],
        client_id=row[7],
        auth_id=row[8],
        client_name=row[9],
        outcome=row[10],
        reason=row[11],
        duration_ms=row[12],
        params=tuple(json.loads(row[13])),
        removed=row[14],
        gap_chain=row[15],
        gap_hash=row[16],
    )


def used_bytes(conn: sqlite3.Connection) -> int:
    """How many bytes this store really occupies.

    Not the file size and not ``page_count * page_size``: neither of them falls after rows
    are dropped, because the pages move to the free list (measured 2026-08-29: 20.000 rows,
    half of them dropped, file unchanged at 4.579.328 byte, 532 free pages). An upper bound
    driven by either of those two numbers keeps sweeping until the table is empty. This one
    falls immediately, needs no filesystem call, and the free pages are reused by the next
    rows, so the file does not grow past them either.
    """
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    free = conn.execute("PRAGMA freelist_count").fetchone()[0]
    return (page_count - free) * page_size


def _next_seq(conn: sqlite3.Connection) -> int:
    """The number the next row will carry, read inside the transaction that writes it.

    The number has to be known before the insert, because it is part of what is hashed.
    ``sqlite_sequence`` is where AUTOINCREMENT keeps the highest number ever handed out, and
    it is not lowered by a sweep, which is the whole reason that keyword is in the schema.
    Writing the number explicitly keeps that counter moving: SQLite raises it whenever an
    explicit key is larger than what it holds.
    """
    row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'entries'").fetchone()
    return (row[0] if row is not None else 0) + 1


def _append_row(conn: sqlite3.Connection, entry: Entry) -> int:
    """Read the predecessor and write the row, inside a transaction the caller opened.

    One function for both writers of this module: the ordinary call of :meth:`AuditStore.
    append` and the marker the sweep hangs into the instance chain. Two places that read a
    previous hash and compute a digest are two places that can disagree about the chain.
    """
    row = conn.execute(_LAST_OF_CHAIN, (entry.chain,)).fetchone()
    previous = row[0] if row is not None else GENESIS
    seq = _next_seq(conn)
    values = _row_values(seq, entry)
    digest = hashlib.sha256(_canonical(values) + previous).digest()
    conn.execute(_INSERT, (*values, previous, digest))
    return seq


def _note_removed(
    ends: dict[str, str], counts: dict[str, int], batch: list[tuple[Any, ...]]
) -> int:
    """Remember, per chain, the end of the block that gave way and how long it was.

    The batch is ordered by ``seq``, so the last row of a chain in it is the youngest one that
    goes, and its hash is what the row after the gap points at. That hash is the whole reason
    a marker can explain a gap instead of leaving a break behind.
    """
    for _seq, chain, row_hash in batch:
        ends[chain] = row_hash.hex()
        counts[chain] = counts.get(chain, 0) + 1
    return len(batch)


def _sweep_expired(conn: sqlite3.Connection, moment: int, cutoff: int, affected: set[str]) -> int:
    """Step one, the retention window: the expired prefix of every user chain goes.

    A prefix and never a hole: a row not younger than ``cutoff`` only goes when everything
    before it in its own chain goes too, so the block a chain gives up is always contiguous
    and its end is always the predecessor of the surviving head. The reason stands at
    :data:`_EXPIRED_PREFIX`: a clock stepped backwards writes a younger moment onto a higher
    sequence number, and a hole torn into the middle of a chain would read as tampering.

    Every batch commits its deletion **together with the markers that explain it** (WR-01 of
    the phase 18 review): a marker committed separately leaves a window in which a process
    kill, an OOM or a power loss has removed rows whose gap nothing names, and the next check
    would report tampering after a perfectly ordinary crash.

    In batches of :data:`SWEEP_BATCH_ROWS` and not in one go: no checkpoint can run while a
    transaction is open, and ten thousand rows in one transaction grew the write ahead log to
    5.5 MB in the measurement of 18-RESEARCH.md §8. Every round removes at least one row, so
    the loop ends by itself.
    """
    expired = 0
    while True:
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute(_EXPIRED_ROWS, (CHAIN_INSTANCE, cutoff, SWEEP_BATCH_ROWS)).fetchall()
        if not batch:
            conn.execute("COMMIT")
            return expired
        ends: dict[str, str] = {}
        counts: dict[str, int] = {}
        expired += _note_removed(ends, counts, batch)
        conn.execute(_DROP_EXPIRED, (CHAIN_INSTANCE, cutoff, batch[-1][0]))
        _write_markers(conn, moment, ends, counts)
        conn.execute("COMMIT")
        affected.update(ends)


def _sweep_over_limit(
    conn: sqlite3.Connection, moment: int, size_limit: int, affected: set[str]
) -> int:
    """Step two, the upper bound: the oldest user rows go until the store is under it again.

    The loop is driven by :func:`used_bytes` and by nothing else. ``os.stat`` and
    ``page_count * page_size`` do not fall after a delete, because the pages move to the free
    list (measured, 18-RESEARCH.md §8), so a loop against either of them keeps deleting until
    the table is empty. This one falls with the first commit, which is what makes the
    condition an end and not a wish.

    Every batch commits its deletion together with the markers that explain it, for the
    reason :func:`_sweep_expired` gives (WR-01).

    Two guards beside it: at most :data:`SWEEP_MAX_ROUNDS` batches per run, and a stop as soon
    as no user row is left. A store that is over the bound while empty is a different fault
    and may not turn into an endless loop here.
    """
    trimmed = 0
    for _round in range(SWEEP_MAX_ROUNDS):
        if used_bytes(conn) <= size_limit:
            break
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute(_OLDEST_ROWS, (CHAIN_INSTANCE, SWEEP_BATCH_ROWS)).fetchall()
        if not batch:
            conn.execute("COMMIT")
            break
        ends: dict[str, str] = {}
        counts: dict[str, int] = {}
        trimmed += _note_removed(ends, counts, batch)
        conn.execute(_DROP_OLDEST, (CHAIN_INSTANCE, batch[-1][0]))
        _write_markers(conn, moment, ends, counts)
        conn.execute("COMMIT")
        affected.update(ends)
    return trimmed


def _write_markers(
    conn: sqlite3.Connection, moment: int, ends: dict[str, str], counts: dict[str, int]
) -> None:
    """One consolidated marker per chain, inside the transaction of the batch.

    Inside it and never in one of its own: the caller holds the transaction that removes the
    rows, and the marker and the deletion it explains stand or fall together (WR-01). This
    function therefore opens nothing and commits nothing.

    **Consolidated, so the register stays bounded (WR-03).** Every sweep used to append one
    more marker per affected chain, and no statement ever removes an instance row, so on a
    busy instance the permanent markers would slowly crowd the actual audit rows out of the
    fixed budget of :data:`SIZE_LIMIT_BYTES`, which may only evict user rows. Since a chain
    only ever loses a contiguous prefix, only the **newest** marker of a chain explains its
    surviving head; the older ones name hashes no row points at any more. So the trailing run
    of markers of the instance chain is absorbed: its counts are summed into the new markers,
    its ends give way to the newer ones, and an untouched chain among them is re-appended
    with its own moment and its own end. Removing only the tail of a chain and appending in
    the same transaction opens no hole: the new rows attach to the row before the absorbed
    run, and the chain stays verifiable link by link.

    A switch row is never absorbed. The walk stops at the first row that is not a marker for
    a gap, so a switch stays where it stands and so do the markers older than it; the
    register therefore grows with switches and with chains, never with sweeps.

    The marker stands in the instance chain and not in the chain it explains. A marker there
    would have to attach to the head of a chain whose head is exactly what just went, so the
    instance chain is the only place it can hang on to (D-02 plus D-03, 18-RESEARCH.md lines
    581 to 585). A sweep never trims the instance chain: it is the register that explains
    every gap, and what happens here is a replacement inside one transaction, never a loss.

    A marker carries a count and the end of the block that gave way, never a parameter name
    and never a value.
    """
    # Copies, because the consolidation extends them with absorbed chains the batch never
    # touched, and the caller counts its own dictionary as "chains this run affected".
    ends = dict(ends)
    counts = dict(counts)
    ats = dict.fromkeys(ends, moment)
    superseded: list[int] = []
    tail = conn.execute(_INSTANCE_TAIL, (CHAIN_INSTANCE,))
    for seq, kind, at, removed, gap_chain, gap_hash in tail:
        if kind != KIND_TOMBSTONE or gap_chain is None or gap_hash is None:
            break
        superseded.append(seq)
        counts[gap_chain] = counts.get(gap_chain, 0) + (removed or 0)
        if gap_chain not in ends:
            # Newest first, so the first absorbed marker of a chain carries its youngest
            # end and its own moment; an older one of the same chain only adds its count.
            ends[gap_chain] = gap_hash
            ats[gap_chain] = at
    tail.close()
    conn.executemany(_DROP_SUPERSEDED, [(CHAIN_INSTANCE, seq) for seq in superseded])
    for chain in sorted(ends):
        _append_row(
            conn,
            Entry(
                chain=CHAIN_INSTANCE,
                kind=KIND_TOMBSTONE,
                at=ats[chain],
                actor=ACTOR_UNKNOWN,
                removed=counts[chain],
                gap_chain=chain,
                gap_hash=ends[chain],
            ),
        )


def _give_the_space_back(conn: sqlite3.Connection) -> None:
    """Step four: hand the free pages to the filesystem and shorten the write ahead log.

    ``.fetchall()`` is not decoration. The pragma answers in rows, and without walking them
    the ``sqlite3`` module runs it to the first step only: measured, one page came back
    instead of 478. The file itself shrinks with the checkpoint after it, because
    ``page_count`` falls immediately while the size on disk waits for the next one.
    """
    conn.execute(f"PRAGMA incremental_vacuum({SWEEP_VACUUM_PAGES})").fetchall()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()


def _explained_gaps(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Every gap the instance chain explains, from chain identifier to the ends it names.

    Read **once** per check and not once per chain: a marker for a gap stands in the instance
    chain (D-10, D-12), so every chain would otherwise ask the same question again, and at the
    upper bound of this store there are chains enough for that to be the whole cost.
    """
    gaps: dict[str, set[str]] = {}
    for gap_chain, gap_hash in conn.execute(_EXPLAINED_GAPS, (CHAIN_INSTANCE, KIND_TOMBSTONE)):
        gaps.setdefault(gap_chain, set()).add(gap_hash)
    return gaps


def _first_finding(
    conn: sqlite3.Connection, chain: str, explained: set[str]
) -> ChainFinding | None:
    """The first broken place of one chain, or ``None`` when the chain is whole.

    The rows are walked in batches of :data:`SWEEP_BATCH_ROWS` and not read in one go: at the
    upper bound this table holds in the order of half a million rows, and the memory of the
    container is not a number to guess at. The walk stops at the first finding of this chain,
    because everything after a break is a consequence of it and not a second event.
    """
    cursor = conn.execute(_ROWS_OF_CHAIN, (chain,))
    expected: bytes | None = None
    previous_seq = 0
    while True:
        batch = cursor.fetchmany(SWEEP_BATCH_ROWS)
        if not batch:
            return None
        for row in batch:
            seq: int = row[0]
            previous_hash: bytes = row[-2]
            stored: bytes = row[-1]
            # First the content of the row: it carries its own hash over its own fields, so
            # this half needs no neighbour and says "this row was changed after the fact".
            recomputed = hashlib.sha256(_canonical(row[: len(CANONICAL_FIELDS)]) + previous_hash)
            if recomputed.digest() != stored:
                return ChainFinding(chain, FINDING_MODIFIED, seq=seq)
            if expected is None:
                # The head of the chain, and the one place where a marker for a gap is the
                # difference between an explained and an unexplained hole: the first row may
                # point at the genesis value, or at the end of a block that gave way and that
                # the instance chain names.
                if previous_hash != GENESIS and previous_hash.hex() not in explained:
                    return ChainFinding(chain, FINDING_MISSING, seq=seq)
            elif previous_hash != expected:
                # Then the link: between these two numbers something was removed or pushed in.
                return ChainFinding(chain, FINDING_MISSING, seq=previous_seq, next_seq=seq)
            expected = stored
            previous_seq = seq


class AuditStore:
    """The audit log, bound to one file.

    Every method opens its own connection inside a worker thread and closes it again, the
    same rule the OAuth store follows and for the same reason: no connection, no cursor and
    no transaction is shared between two requests, so two workers on one volume behave like
    two threads in one worker. There is no key here and nothing to mask.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        # False until this object has opened the file once. See :meth:`_call` for what the
        # flag is worth and what it deliberately does not promise.
        self._schema_ready = False

    def __repr__(self) -> str:
        return f"AuditStore(path={self._path!r})"

    async def append(self, entry: Entry) -> int:
        """Add one row to the end of its chain and return the number it was given.

        Reading the previous hash and writing the new row happen in **one** transaction that
        takes the write lock at its start. Two calls of the same account want to extend the
        same chain; in two transactions both would read the same last hash and write two
        rows with the same predecessor, which is a fork, and a check would report it as a
        break where nobody manipulated anything.

        The number is returned because the sweep of D-11 hangs its interval on it.
        """

        def work(conn: sqlite3.Connection) -> int:
            conn.execute("BEGIN IMMEDIATE")
            seq = _append_row(conn, entry)
            conn.execute("COMMIT")
            return seq

        return await self._transaction(work)

    async def sweep(
        self,
        *,
        moment: int,
        retention_days: int = RETENTION_DAYS,
        size_limit: int = SIZE_LIMIT_BYTES,
    ) -> SweepReport:
        """The retention window, the upper bound, the markers, and the space given back.

        Three steps in this order (D-10, D-11): the expired prefix of every chain goes, then
        the oldest rows go until :func:`used_bytes` is under ``size_limit``, and finally the
        free pages go back to the filesystem. Every chain that lost rows gets its marker in
        the instance chain **inside the same transaction as the batch that took its rows**
        (WR-01): a crash between a committed deletion and a separately committed marker would
        otherwise leave a gap the check reads as tampering. Each batch is bounded and commits
        for itself, so the write ahead log can be checkpointed in between.

        ``moment`` is handed in rather than read from the clock, because it is both the end of
        the retention window and the moment written into every marker of this run, and a run
        whose two halves disagree about the time is a run nobody can reproduce in a test.
        """

        def work(conn: sqlite3.Connection) -> SweepReport:
            affected: set[str] = set()
            expired = _sweep_expired(conn, moment, moment - retention_days * _DAY_SECONDS, affected)
            trimmed = _sweep_over_limit(conn, moment, size_limit, affected)
            if expired or trimmed:
                _give_the_space_back(conn)
            return SweepReport(
                expired=expired,
                trimmed=trimmed,
                tombstones=len(affected),
                used_bytes_after=used_bytes(conn),
            )

        return await self._transaction(work)

    async def silent_users(
        self, *, moment: int, silence_days: int = USER_SILENCE_DAYS
    ) -> list[str]:
        """The accounts whose youngest entry is at or past the threshold of D-12.

        This is the whole reason the account check stays rare and cheap: an account whose last
        entry is younger than :data:`USER_SILENCE_DAYS` is not even asked about, so the
        question is put to a handful of chains and never to all of them. Thirty days is longer
        than a holiday and far short of the retention window, which is what makes the check
        bite long before the entries would have expired anyway.

        Only the chains of accounts are named, because only they have an account to ask about.
        The instance chain is left out because it explains the gaps of every other one, and the
        chain of refused exchange attempts because it belongs to nobody: it is written on a
        path that runs before any authentication, so the name it would be asked about is not an
        account name at all (AUDIT-07, T-24-18). The statement says so with a positive filter
        on :data:`USER_CHAIN_PREFIX`, so a fourth kind of chain is left out by default rather
        than by somebody remembering to.

        The edge is inclusive, the same way the retention window of :meth:`sweep` is: an entry
        exactly ``silence_days`` old is past the threshold, one second younger is not.
        """

        def work(conn: sqlite3.Connection) -> list[str]:
            cutoff = moment - silence_days * _DAY_SECONDS
            return [
                _account_of(chain)
                for (chain,) in conn.execute(
                    _SILENT_CHAINS, (len(USER_CHAIN_PREFIX), USER_CHAIN_PREFIX, cutoff)
                )
            ]

        return await self._read(work)

    async def drop_user_chain(self, nc_user: str, *, moment: int) -> int:
        """Remove every row of one account and leave one marker for the gap. D-12.

        Called only after :func:`~mcp_connector.audit.accounts.existing_users` answered with a
        list that was read, that is not empty, and that does not contain this account. What
        this method itself guarantees is the other half: whatever it removes leaves a trace.

        The marker stands in the instance chain and not in the chain it explains, for the
        reason :func:`_write_markers` gives at length: the chain it would attach to is
        exactly what just went. It carries the count and the end of what it replaces, never a
        tool, never a parameter name.

        The instance chain cannot be dropped here however an account is named, because
        :func:`user_chain` prefixes every identifier this method builds and
        :data:`CHAIN_INSTANCE` carries a different prefix.

        Returns how many rows went. Zero means there was nothing of this account, and then
        there is no gap either, so no marker is written: a marker for a chain that never
        existed would be a hole in the record where there is none.
        """
        chain = user_chain(nc_user)

        def work(conn: sqlite3.Connection) -> int:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(_LAST_OF_CHAIN, (chain,)).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return 0
            removed = conn.execute(_COUNT_OF_CHAIN, (chain,)).fetchone()[0]
            end: bytes = row[0]
            conn.execute(_DROP_CHAIN, (chain,))
            _append_row(
                conn,
                Entry(
                    chain=CHAIN_INSTANCE,
                    kind=KIND_TOMBSTONE,
                    at=moment,
                    actor=ACTOR_UNKNOWN,
                    removed=removed,
                    gap_chain=chain,
                    gap_hash=end.hex(),
                ),
            )
            conn.execute("COMMIT")
            # After the commit and never inside it: no incremental vacuum runs while a
            # transaction is open. A whole chain is the largest thing this store ever gives
            # up at once, and the step is the same one the sweep ends with.
            _give_the_space_back(conn)
            return removed

        return await self._transaction(work)

    async def last_entry(self, chain: str, *, kind: str | None = None) -> Entry | None:
        """The youngest row of a chain, optionally of one kind only.

        The switch of D-15 asks for the last row of its own kind to know which direction it
        is in; a caller that wants the end of the chain itself leaves ``kind`` out.
        """

        def work(conn: sqlite3.Connection) -> Entry | None:
            statement = _LAST_ROW_OF_CHAIN if kind is None else _LAST_ROW_OF_KIND
            parameters: tuple[Any, ...] = (chain,) if kind is None else (chain, kind)
            row = conn.execute(statement, parameters).fetchone()
            return None if row is None else _entry_of_row(row)

        return await self._read(work)

    async def read_entries(
        self,
        *,
        chain: str | None = None,
        since: int | None = None,
        until: int | None = None,
        limit: int = READ_LIMIT_DEFAULT,
    ) -> list[tuple[Any, ...]]:
        """Rows out, youngest first, at most ``limit`` of them and never more than
        :data:`READ_LIMIT_MAX`.

        The one method here that hands the content of a row over, for the read command of
        AUDIT-04. It changes nothing and runs without a transaction of its own, like every
        other read of this class. A filter that is ``None`` is a filter nobody set: the
        statement says so itself, so there is one text for every combination and no value of a
        caller ever enters it.

        **Why the limit is clamped.** ``limit`` arrives from an option of a console command,
        so it is a number from the outside, and the answer of this method sits in the memory of
        a container while it is built. 100 MB of this store are roughly 440.000 rows, and
        AppAPI calls the handler of an occ command with ``timeout => 0``, so nothing outside
        cuts a long read short either. The clamp is ``max(1, min(limit, READ_LIMIT_MAX))``:
        the upper end catches the option that says a billion, the lower end catches the zero
        and the negative number, because SQLite reads a negative ``LIMIT`` as no limit at all,
        which is the one answer this method must not be able to give.

        **Why the order is ``seq`` and not ``at``.** ``at`` is the wall clock at the moment a
        row was written, and a clock stepped backwards (an NTP correction, a resumed VM) puts a
        smaller moment onto a higher sequence number; ordering by it would hand rows over in an
        order the chain never had (WR-02 of the phase 18 review). ``seq`` is the order of the
        chain itself, so it is the order of the answer.

        **The direction is always youngest first.** That is what somebody looking at a console
        wants, and it is also the only direction a limit can be combined with: ``ORDER BY seq
        ASC LIMIT ?`` would hand over the *oldest* rows and therefore, for an export, the wrong
        ones. Whoever needs the order of the chain reverses the list where it is printed.

        **What comes back and why it is not an** :class:`Entry`. The raw rows, in the column
        order of :data:`CANONICAL_FIELDS` plus ``prev_hash`` and ``hash``. :class:`Entry`
        carries neither the number nor the two hashes on purpose (it is a row on its way *in*),
        and an output line without a number cannot be followed up. A caller reads the fields
        with :func:`_entry_of_row` and takes ``row[0]`` for the number, ``row[-2]`` and
        ``row[-1]`` for the two hashes, so the column order stays written down once.
        """
        bounded = max(1, min(limit, READ_LIMIT_MAX))

        def work(conn: sqlite3.Connection) -> list[tuple[Any, ...]]:
            return conn.execute(
                _READ_ROWS, (chain, chain, since, since, until, until, bounded)
            ).fetchall()

        return await self._read(work)

    async def verify_chains(self) -> list[ChainFinding]:
        """Walk every chain and name the first broken place of each one.

        An untouched store answers with an empty list. Every chain is walked for itself, in
        batches, and every chain contributes at most one finding: the first, because the rows
        behind a break are its consequence.

        **What this does not do.** A whole user chain that vanished does not catch its eye:
        every chain stands for itself (D-02), so a table without ``u:alice`` looks exactly
        like a table in which ``alice`` never called a tool. The only trace of such a chain is
        a marker in the instance chain, and that trace is worth what the file it lives in is
        worth: whoever can write this file can write a marker too, and a forged one is
        indistinguishable from a real one (D-v1.5-02). This check finds the unnoticed change,
        not the attacker who recomputes the chain.
        """

        def work(conn: sqlite3.Connection) -> list[ChainFinding]:
            explained = _explained_gaps(conn)
            findings: list[ChainFinding] = []
            for (chain,) in conn.execute(_CHAINS).fetchall():
                finding = _first_finding(conn, chain, explained.get(chain, set()))
                if finding is not None:
                    findings.append(finding)
            return findings

        return await self._read(work)

    async def overview(self) -> StoreOverview:
        """The counts :class:`StoreOverview` describes, in one read.

        Read next to :meth:`verify_chains` rather than inside it, because the two answer
        different questions and only one of them may be expensive: this one is five
        aggregates and one size measurement, and it stays cheap even when the walk of every
        chain is not.
        """

        def work(conn: sqlite3.Connection) -> StoreOverview:
            chains, entries = conn.execute(_TOTALS).fetchone()
            tombstones, explained = conn.execute(_MARKER_TOTALS, (KIND_TOMBSTONE,)).fetchone()
            (sweepable,) = conn.execute(_SWEEPABLE_TOTAL, (CHAIN_INSTANCE,)).fetchone()
            return StoreOverview(
                chains=chains,
                entries=entries,
                tombstones=tombstones,
                explained_entries=explained,
                used_bytes=used_bytes(conn),
                sweepable_entries=sweepable,
            )

        return await self._read(work)

    async def size(self) -> int:
        """The number :data:`SIZE_LIMIT_BYTES` is compared against, see :func:`used_bytes`."""
        return await self._read(used_bytes)

    # --- the plumbing ---------------------------------------------------------------

    async def _read[T](self, work: Work[T]) -> T:
        """A statement without a transaction of its own, in a worker thread."""
        return await asyncio.to_thread(self._call, work, False)

    async def _write[T](self, work: Work[T]) -> T:
        """Statements that are committed together when ``work`` returns, or not at all."""
        return await asyncio.to_thread(self._call, work, True)

    async def _transaction[T](self, work: Work[T]) -> T:
        """``work`` runs its own ``BEGIN IMMEDIATE`` and its own ``COMMIT``."""
        return await asyncio.to_thread(self._call, work, False)

    def _call[T](self, work: Work[T], commit: bool) -> T:
        """Run ``work`` on one connection, inside a transaction when it is a write.

        The schema runs on the first open of this object and when the file is gone. The flag
        is what makes the ordinary call cheap, and the ``exists`` is what keeps the cheap
        call honest, because SQLite creates an empty file for a connection to a path that has
        none: without the second half, a volume removed while the process runs would turn
        every later call into "no such table" until a restart.

        The rollback is best effort, because there is one case in which no transaction is
        open any more, and it is the interesting one: a body that hit the busy timeout on its
        own ``BEGIN``. Failing there would replace the real error with a second one.
        """
        conn = _connect(self._path, schema=not self._schema_ready or not self._path.exists())
        self._schema_ready = True
        try:
            if commit:
                conn.execute("BEGIN IMMEDIATE")
            result = work(conn)
            if commit:
                conn.execute("COMMIT")
            return result
        except BaseException:
            if commit:
                # Suppressed and not handled: the error of ``work`` is the one that
                # matters, and it is on its way up.
                with contextlib.suppress(sqlite3.Error):
                    conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()


def _connect(path: Path, *, schema: bool = True) -> sqlite3.Connection:
    """One connection with its pragmas, and the schema when the caller asks for it.

    ``isolation_level=None`` turns off the implicit transaction handling of the standard
    library, which is what makes an explicit ``BEGIN IMMEDIATE`` mean what it says.

    There is no ``foreign_keys`` pragma here, because this schema has no foreign key: one
    table, and a row of it refers to nothing but a hash it carries itself.

    The order below is load bearing, and it is one step stricter than the research of this
    phase wrote down. ``auto_vacuum`` is decided while the file is still empty and can
    afterwards only be changed by a full ``VACUUM`` that rewrites everything. Running it
    before ``executescript`` is not enough: switching a fresh file to WAL already writes its
    header, and the pragma after that is silently ignored. Measured on this machine,
    Python 3.13 with SQLite 3.50.4, both orders against a new file:
    ``journal_mode`` first leaves ``PRAGMA auto_vacuum`` at 0, ``auto_vacuum`` first leaves
    it at 2 with ``journal_mode`` still ``wal``. So this pragma is the very first statement
    on the connection, and on a file that already has its mode it costs one no-op.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=_BUSY_TIMEOUT_SECONDS)
    conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    if schema:
        conn.executescript(SCHEMA)
    return conn

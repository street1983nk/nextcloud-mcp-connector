"""Everything of this phase that has to survive a restart, in one SQLite file.

**Why SQLite and not a JSON file.** The refresh rotation is a compare and set: exactly one
of two simultaneous redemptions may win, and the loser has to learn that it lost rather
than to overwrite the winner. A file that is read, changed and written back cannot do
that; a transaction with ``BEGIN IMMEDIATE`` can, in one line of SQL, across threads and
across worker processes on the same volume (pitfall 10, T-03-13).

**Why the standard library module and not aiosqlite.** Every call here runs in
:func:`asyncio.to_thread` with its own connection, which is the whole of what an async
wrapper would add. The dependency surface of this project is a deliberate decision
(``docs/dependency-audit.md``), and a new direct dependency for a thirty line wrapper is
not one worth making.

**Pragmas, set on every connection because two of the three are per connection.**
``journal_mode = WAL`` so a reader does not block the writer of a parallel request,
``foreign_keys = ON`` so revoking a client actually takes its authorizations with it, and
``busy_timeout`` so the loser of a lock waits for the winner instead of failing with
"database is locked" while a user watches a spinner.

**What is stored and what is not.** Tokens exist here only as their SHA-256 hex digest, so
a stolen file cannot be replayed against the server (T-03-11). The two secrets that must
come back out, the Nextcloud app password of an authorization and the poll token of a
running login flow, are encrypted with :mod:`mcp_connector.oauth.crypto` and bound to the
id of their own row, so moving a ciphertext to another row makes it unreadable rather than
useful (T-03-12). Every row object that carries such a value masks its repr.

No module global mutable state: the store is an object that is given its path and its key,
which is the same rule the credential objects of phase 1 follow. Two processes on the same
file are a supported case, not an accident (SRV-05).
"""

import asyncio
import contextlib
import hashlib
import hmac
import os
import sqlite3
import stat
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config
from ..errors import ToolError
from . import crypto
from .crypto import DecryptionRejected, decrypt, encrypt

#: What every method below hands to the worker thread: one function, one connection, one
#: result. Naming it keeps the three wrappers at the bottom readable and typed.
type Work[T] = Callable[[sqlite3.Connection], T]

__all__ = [
    "ACCESS_TOKEN_TTL",
    "AUTH_CODE_TTL",
    "FLOW_TTL",
    "IDLE_CLIENT_TTL",
    "KEY_CHECK_NAME",
    "KEY_CHECK_SAMPLES",
    "OIDC_SCHEMA",
    "OIDC_TRANSACTIONS_PER_BROWSER",
    "OIDC_TTL",
    "REDEEM_EXPIRED",
    "REDEEM_OK",
    "REDEEM_REUSED",
    "REDEEM_UNKNOWN",
    "REFRESH_TOKEN_TTL",
    "ROTATION_GRACE",
    "STALE_ACCESS_TTL",
    "STATES",
    "STATE_ACTIVE",
    "STATE_REVOKED",
    "STATE_USED",
    "STORE_FILENAME",
    "UNUSED_CLIENT_TTL",
    "VALIDATION_CACHE_TTL",
    "AccessTokenRow",
    "AuthCodeRow",
    "AuthorizationRow",
    "ClientRow",
    "DirectoryProvider",
    "FlowRow",
    "KeyProvider",
    "OAuthStore",
    "OidcTransaction",
    "RefreshRedemption",
    "RefreshTokenRow",
    "StoreFileRefused",
    "StoreKeyMismatch",
    "StoreProvider",
    "explicit_store_opener",
    "store_opener",
    "token_hash",
]

#: The one file in the persistent volume of this app.
STORE_FILENAME = "oauth.sqlite3"

#: Where a deployment keeps the store file. Called when the store is opened, not when the
#: application is assembled, so an ExApp whose volume is mounted late still starts.
type DirectoryProvider = Callable[[], Path]

#: The data key of a deployment. Asynchronous because the ExApp reads it from Nextcloud.
#: A provider never invents a key: a fresh key silently invalidates every stored row.
type KeyProvider = Callable[[], Awaitable[bytes]]

#: The one row of ``store_meta`` today: the :func:`crypto.key_check` of the data key.
KEY_CHECK_NAME = "data_key_check_v1"

#: How many encrypted rows a store without a check value tries before it adopts the key.
#: One readable row proves the key; a single damaged row must not refuse a whole store.
KEY_CHECK_SAMPLES = 20

#: The table of the key check. Not part of :data:`SCHEMA` on purpose: only a deployment that
#: asks for the check creates it, so an ExApp store keeps exactly its documented tables.
_META_SCHEMA = "CREATE TABLE IF NOT EXISTS store_meta (name TEXT PRIMARY KEY, value TEXT NOT NULL)"

_KEY_MISMATCH_HINT = (
    "The OAuth store was written with a different data key. Restore the original key; the "
    "connector never replaces it on its own. If the key is lost, the stored connections "
    "cannot be read by anyone: remove the store file and let every user connect again."
)


_STORE_FILE_HINT = (
    "The OAuth store file has to be a regular file that only the connector's own user can "
    "read or write (mode 0600). Fix the mode with 'chmod 600', or remove a link that stands "
    "in its place."
)


class StoreFileRefused(ToolError):
    """The store path is a link, not a regular file, or readable beyond its owner."""

    def __init__(self) -> None:
        super().__init__(message="The OAuth store file is not private.", hint=_STORE_FILE_HINT)


class StoreKeyMismatch(ToolError):
    """The data key of this process cannot read the store it was pointed at."""

    def __init__(self) -> None:
        super().__init__(
            message="The data key does not match the OAuth store.", hint=_KEY_MISMATCH_HINT
        )


#: What every consumer of the store receives: one opener per application.
type StoreProvider = Callable[[], Awaitable["OAuthStore"]]

# --- lifetimes ---------------------------------------------------------------------
# Every number of seconds this phase uses is one of the names below. A literal at a call
# site is a value nobody finds again when a client turns out to need a different one.

#: An authorization code is a hand over between two requests of the same browser, so it is
#: short by an order of magnitude compared to everything else here.
AUTH_CODE_TTL = 60

#: One hour, which is what the connectors expect and what keeps a revocation cheap.
ACCESS_TOKEN_TTL = 3600

#: Thirty days. Longer than any session, short enough that an abandoned connection dies.
REFRESH_TOKEN_TTL = 30 * 24 * 3600

#: Twenty minutes, the pace Nextcloud sets for its own login flow.
FLOW_TTL = 1200

#: Five minutes for an OIDC sign in and for the browser proof it leaves behind, and never
#: longer than the flow they belong to. Short on purpose: both are bearer-like values in a
#: browser, and a person who needs longer starts the confirmation again.
OIDC_TTL = 300

#: Open OIDC sign ins per browser handle. The start is an anonymous browser surface that
#: writes a row and makes the IdP busy, so one browser gets a small, fixed number of them.
OIDC_TRANSACTIONS_PER_BROWSER = 3

#: How long a validated access token may be answered from a process cache (03-06 uses it).
VALIDATION_CACHE_TTL = 5

#: The idempotent retry window of the rotation (D-41). Inside it the same refresh token is
#: answered with the same successor; outside it a second use is an attack on the family.
ROTATION_GRACE = 10

#: A registration that never produced a token is a fingerprint, not a client.
UNUSED_CLIENT_TTL = 24 * 3600

#: A client that has not been seen for a season goes, and takes its authorizations along.
IDLE_CLIENT_TTL = 90 * 24 * 3600

#: How long a pause with nothing behind it is kept (LO-03). ``user_access`` has no foreign
#: key and nothing ever removed a row from it, so the table grew monotonically and held
#: rows for accounts that no longer exist. A row goes when it has nothing left to switch:
#: no authorization of that account at all, and the pause older than this window. The same
#: season as :data:`IDLE_CLIENT_TTL`, and for the same reason: long enough that a holiday,
#: a sabbatical or a device swap does not resume anybody's access, short enough that the
#: table does not carry a deleted account forever. The price is named in ``docs/faq.md``:
#: an account that pauses without ever connecting is switched on again after 90 days.
STALE_ACCESS_TTL = 90 * 24 * 3600

#: The two tables of the standalone OIDC browser identity. Created only for a store that
#: asks for them (``OAuthStore(..., oidc=True)``), so an ExApp store keeps exactly its seven
#: documented tables. Both hang on the flow they belong to: every path that ends a flow
#: (completion, denial, expiry, binding failure, paused withdrawal, sweeps, client removal,
#: purge) takes them along through the cascade.
#:
#: No handle, state, nonce or verifier is stored in the clear. State, browser handle and
#: proof handle are SHA-256 digests (lookup keys); nonce and PKCE verifier come back out and
#: are AES-GCM encrypted with an AAD of table, field and row key, so a ciphertext moved to
#: another row, field or table is refused.
OIDC_SCHEMA = """
CREATE TABLE IF NOT EXISTS oidc_transactions (
  state_hash TEXT PRIMARY KEY,
  flow_id TEXT NOT NULL REFERENCES flows(flow_id) ON DELETE CASCADE,
  browser_hash TEXT NOT NULL,
  nonce_enc BLOB NOT NULL,
  verifier_enc BLOB NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS oidc_transactions_browser ON oidc_transactions(browser_hash);

CREATE TABLE IF NOT EXISTS oidc_proofs (
  proof_hash TEXT PRIMARY KEY,
  flow_id TEXT NOT NULL UNIQUE REFERENCES flows(flow_id) ON DELETE CASCADE,
  principal TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
"""

#: SQLite's own spelling of "no upper bound": a negative ``LIMIT`` expression returns every
#: row. It lets a read that must not be capped keep one constant statement with one
#: placeholder, instead of assembling SQL around a value (BL-01).
_NO_LIMIT = -1

# --- refresh token states ------------------------------------------------------------

STATE_ACTIVE = "active"
STATE_USED = "used"
STATE_REVOKED = "revoked"

#: Plain strings and an explicit check instead of an enum on the column: the refusal of an
#: unknown value has to stay reachable, and a type that makes the bad case unwritable also
#: makes it untestable (the rule of ``nextcloud/credentials.py``).
STATES = (STATE_ACTIVE, STATE_USED, STATE_REVOKED)

# --- outcomes of a refresh redemption --------------------------------------------------
# Three failures, not one: plan 03-07 kills the family for a reuse and answers a plain
# invalid_grant for the other two, so the store has to tell them apart.

REDEEM_OK = "ok"
REDEEM_UNKNOWN = "unknown"
REDEEM_EXPIRED = "expired"
REDEEM_REUSED = "reused"

#: The schema of 03-RESEARCH.md, verbatim except for the ``IF NOT EXISTS`` that makes it
#: idempotent for a second process opening the same file, plus the one table phase 4 adds
#: (``user_access``, the per account switch of EXAPP-02). ``CREATE TABLE IF NOT EXISTS``
#: here is the whole migration for a new table: every process runs this script on its first
#: open, so a store file written by an earlier build grows the table when the next build
#: starts. It runs once per store object and no longer on every open (LO-02, see
#: :meth:`OAuthStore._call`), which is why a new table arrives with a restart and not in
#: the middle of a request.
SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
  client_id TEXT PRIMARY KEY,
  client_secret_hash TEXT,
  metadata_json TEXT NOT NULL,
  allowed INTEGER NOT NULL DEFAULT 1,
  registered_at INTEGER NOT NULL,
  last_used_at INTEGER,
  -- The two moments of a client that identifies itself with a metadata document instead of
  -- registering (AUTH-08). NULL in both is what every other row carries and means "not one
  -- of those": a registration that arrived through RFC 7591 has no document to be fresh
  -- about, and no row is ever rewritten to say so.
  -- Two columns and not one, because the two windows are two different statements
  -- (pitfall 4): the registration TTL above is about a registration that never produced a
  -- token, while the freshness below is about a document that may have changed since it was
  -- read. Running out of freshness costs one fetch; running out of registration TTL costs
  -- the row and, through the cascade, every connection under it.
  -- The freshness window comes from the HTTP cache headers of the answer, floored at 300
  -- seconds and capped at 3600, which the draft explicitly leaves to the authorization
  -- server ("SHOULD respect HTTP cache headers", "MAY define its own upper and/or lower
  -- bounds", section 6.6).
  cimd_fetched_at INTEGER,
  cimd_expires_at INTEGER
);

CREATE TABLE IF NOT EXISTS flows (
  flow_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
  redirect_uri TEXT NOT NULL,
  redirect_uri_explicit INTEGER NOT NULL,
  code_challenge TEXT NOT NULL,
  state TEXT,
  scopes TEXT NOT NULL,
  resource TEXT NOT NULL,
  poll_token_enc BLOB NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS authorizations (
  auth_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
  nc_user TEXT NOT NULL,
  -- The canonical Nextcloud account id (OCS cloud/user) and with it the principal of the
  -- connection. NULL only in rows an ExApp wrote before the column existed; for those the
  -- principal stays nc_user (oauth/principal.py).
  nc_account_id TEXT,
  app_password_enc BLOB NOT NULL,
  scopes TEXT NOT NULL,
  resource TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  revoked_at INTEGER,
  cleanup_at INTEGER
);

CREATE INDEX IF NOT EXISTS authorizations_nc_user ON authorizations(nc_user);

CREATE TABLE IF NOT EXISTS user_access (
  nc_user TEXT PRIMARY KEY,
  disabled_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_codes (
  code_hash TEXT PRIMARY KEY,
  auth_id TEXT NOT NULL REFERENCES authorizations(auth_id) ON DELETE CASCADE,
  redirect_uri TEXT NOT NULL,
  redirect_uri_explicit INTEGER NOT NULL DEFAULT 1,
  code_challenge TEXT NOT NULL,
  resource TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  used_at INTEGER
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  token_hash TEXT PRIMARY KEY,
  auth_id TEXT NOT NULL REFERENCES authorizations(auth_id) ON DELETE CASCADE,
  family_id TEXT NOT NULL,
  state TEXT NOT NULL,
  successor TEXT,
  issued_at INTEGER NOT NULL,
  used_at INTEGER,
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS refresh_family ON refresh_tokens(family_id);

CREATE TABLE IF NOT EXISTS access_tokens (
  token_hash TEXT PRIMARY KEY,
  auth_id TEXT NOT NULL REFERENCES authorizations(auth_id) ON DELETE CASCADE,
  family_id TEXT NOT NULL,
  scopes TEXT NOT NULL,
  resource TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE INDEX IF NOT EXISTS access_family ON access_tokens(family_id);
"""


def token_hash(token: str) -> str:
    """The one form a token takes on disk. SHA-256 hex, never the token itself.

    No salt and no key stretching on purpose: these are 256 bit random values, not
    passwords, so there is nothing to brute force and a per row salt would only make the
    lookup by token impossible.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class ClientRow:
    """A registered client. The secret hash is masked like every other credential.

    The two ``cimd_`` fields are ``None`` for every row that came from a registration, and
    that is how the rest of the code tells the two kinds apart: a set ``cimd_fetched_at``
    means this identity was read from a metadata document and can be read again, which is
    what takes such a row out of the registration TTL (pitfall 4).
    """

    client_id: str
    client_secret_hash: str | None
    metadata_json: str
    allowed: bool
    registered_at: int
    last_used_at: int | None
    cimd_fetched_at: int | None = None
    cimd_expires_at: int | None = None

    def __repr__(self) -> str:
        return (
            f"ClientRow(client_id={self.client_id!r}, allowed={self.allowed!r}, "
            f"registered_at={self.registered_at!r}, last_used_at={self.last_used_at!r}, "
            "client_secret_hash='***')"
        )


@dataclass(frozen=True, slots=True, repr=False)
class FlowRow:
    """A login flow that is still running. ``poll_token`` is the decrypted value."""

    flow_id: str
    client_id: str
    redirect_uri: str
    redirect_uri_explicit: bool
    code_challenge: str
    state: str | None
    scopes: str
    resource: str
    poll_token: str
    expires_at: int

    def __repr__(self) -> str:
        return (
            f"FlowRow(flow_id={self.flow_id!r}, client_id={self.client_id!r}, "
            f"redirect_uri={self.redirect_uri!r}, expires_at={self.expires_at!r}, "
            "poll_token='***')"
        )


@dataclass(frozen=True, slots=True)
class AuthorizationRow:
    """One connection of one user. The app password is deliberately not a field here.

    Reading it is an explicit act with its own method, so a caller cannot end up with a
    plaintext Nextcloud credential just because it wanted the user id.

    ``cleanup_at`` is the one field that is neither identity nor deadline: it is the moment
    at which somebody noticed that the Nextcloud app password of this connection still has
    to be handed back. It exists because the revocation must not hang on that deletion
    (pitfall 13, D-37), and something has to remember the attempt that failed.
    """

    auth_id: str
    client_id: str
    nc_user: str
    scopes: str
    resource: str
    created_at: int
    revoked_at: int | None
    cleanup_at: int | None = None
    nc_account_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuthCodeRow:
    """What an authorization code is bound to: everything the token endpoint compares.

    ``redirect_uri_explicit`` is the one field that is neither a secret nor a deadline: the
    SDK compares the return address of the token request against the one of the
    authorization request, and a request that named none has to name none again. Carrying
    the flag is the only way that comparison can still be made after the flow record that
    knew it is gone.
    """

    auth_id: str
    redirect_uri: str
    redirect_uri_explicit: bool
    code_challenge: str
    resource: str
    expires_at: int


@dataclass(frozen=True, slots=True)
class AccessTokenRow:
    """A valid access token, with the user the request will act as."""

    auth_id: str
    family_id: str
    nc_user: str
    scopes: str
    resource: str
    expires_at: int
    nc_account_id: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshTokenRow:
    """A refresh token as it stands in the file, with a state that was checked."""

    auth_id: str
    family_id: str
    state: str
    successor: str | None
    issued_at: int
    used_at: int | None
    expires_at: int


@dataclass(frozen=True, slots=True)
class RefreshRedemption:
    """The outcome of one redemption, plus what the caller needs to act on it.

    ``used_at`` and ``successor`` are filled for :data:`REDEEM_REUSED` only: they are what
    plan 03-07 needs to tell a network retry inside the grace window from a replay that
    has to kill the family (D-41).
    """

    outcome: str
    auth_id: str = ""
    family_id: str = ""
    used_at: int | None = None
    successor: str | None = None


@dataclass(frozen=True, slots=True, repr=False)
class OidcTransaction:
    """One consumed OIDC sign in: what the callback needs to finish it."""

    flow_id: str
    nonce: str
    code_verifier: str
    expires_at: int

    def __repr__(self) -> str:
        return (
            f"OidcTransaction(flow_id={self.flow_id!r}, expires_at={self.expires_at!r}, "
            "nonce='***', code_verifier='***')"
        )


class OAuthStore:
    """The persistence of the phase, bound to one file and one data key.

    Every method opens its own connection inside a worker thread and closes it again. That
    costs a fraction of a millisecond per call and buys the property this server needs
    most: no connection, no cursor and no transaction is shared between two requests, so
    two workers on the same volume behave exactly like two threads in one worker.
    """

    def __init__(self, path: Path, key: bytes, *, oidc: bool = False) -> None:
        self._path = path
        self._key = key
        # Whether this store carries the two OIDC tables (standalone only).
        self._oidc = oidc
        # False until this object has opened the file once (LO-02). See :meth:`_call` for
        # what it is worth and what it deliberately does not promise.
        self._schema_ready = False

    def __repr__(self) -> str:
        return f"OAuthStore(path={self._path!r}, key='***')"

    @property
    def path(self) -> Path:
        return self._path

    def form_token(self, handle: str, *, purpose: str, now: float | None = None) -> str:
        """The anti forgery value of one form: this handle, this purpose, this hour.

        T-03-50, ME-01 and ME-02. It lives on this object because the data key does, and
        nowhere else in the process holds that key. Nothing is read or written: the value is
        derived, which is why it is the same for every render of the same form inside one
        window and different for every deployment.

        ``purpose`` is one of the constants of :mod:`.crypto` and is required, because the
        handles of two different actions can be the same string: an authorization carries
        the id of the flow it was born in, so the consent form and the disconnect form of
        one connection would otherwise be authorised by one value.

        ``now`` is for tests, which is why the callers never pass it: it is what lets a
        check name an expired form without waiting an hour for one.
        """
        return crypto.form_token(self._key, handle, purpose=purpose, now=now)

    def form_token_valid(
        self, handle: str, presented: str, *, purpose: str, now: float | None = None
    ) -> bool:
        """Whether this value belongs to this form and is still inside its window (BL-08).

        The counterpart of :meth:`form_token` and the only way a caller should compare one:
        the current window and the previous one are accepted, and both comparisons are the
        constant time one. A caller that recomputed a value and compared it itself would
        accept exactly one window and would refuse every form that was open across an hour
        boundary.
        """
        return crypto.form_token_valid(self._key, handle, presented, purpose=purpose, now=now)

    # --- clients --------------------------------------------------------------------

    async def save_client(
        self,
        client_id: str,
        *,
        metadata_json: str,
        secret_hash: str | None = None,
        allowed: bool = True,
        now: int | None = None,
        cimd_fetched_at: int | None = None,
        cimd_expires_at: int | None = None,
    ) -> None:
        """Write a registration, keeping the original registration time on an update.

        The two ``cimd_`` values default to ``None``, which is what every caller that
        writes a registration passes: a row without them is a row of the registration path
        and stays one. The client identifier metadata document path (AUTH-08) hands both in
        and hands them in again on every re-read, so an update refreshes them while
        ``registered_at`` keeps saying when this identity was first seen here.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO clients (
                  client_id, client_secret_hash, metadata_json, allowed, registered_at,
                  cimd_fetched_at, cimd_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                  client_secret_hash = excluded.client_secret_hash,
                  metadata_json = excluded.metadata_json,
                  allowed = excluded.allowed,
                  cimd_fetched_at = excluded.cimd_fetched_at,
                  cimd_expires_at = excluded.cimd_expires_at
                """,
                (
                    client_id,
                    secret_hash,
                    metadata_json,
                    int(allowed),
                    moment,
                    cimd_fetched_at,
                    cimd_expires_at,
                ),
            )

        await self._write(work)

    async def load_client(self, client_id: str) -> ClientRow | None:
        def work(conn: sqlite3.Connection) -> ClientRow | None:
            row = conn.execute(
                "SELECT client_id, client_secret_hash, metadata_json, allowed, registered_at, "
                "last_used_at, cimd_fetched_at, cimd_expires_at FROM clients WHERE client_id = ?",
                (client_id,),
            ).fetchone()
            if row is None:
                return None
            return ClientRow(
                client_id=row[0],
                client_secret_hash=row[1],
                metadata_json=row[2],
                allowed=bool(row[3]),
                registered_at=row[4],
                last_used_at=row[5],
                cimd_fetched_at=row[6],
                cimd_expires_at=row[7],
            )

        return await self._read(work)

    async def touch_client(self, client_id: str, *, now: int | None = None) -> None:
        """Record that this client was actually used, which is what stops it expiring."""
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE clients SET last_used_at = ? WHERE client_id = ?", (moment, client_id)
            )

        await self._write(work)

    async def delete_client(self, client_id: str) -> None:
        """Remove a registration and, through the cascade, everything issued under it."""

        def work(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))

        await self._write(work)

    # --- flows ----------------------------------------------------------------------

    async def create_flow(
        self,
        flow_id: str,
        *,
        client_id: str,
        redirect_uri: str,
        redirect_uri_explicit: bool,
        code_challenge: str,
        state: str | None,
        scopes: str,
        resource: str,
        poll_token: str,
        now: int | None = None,
    ) -> None:
        """Remember a pending authorization while Nextcloud runs the login."""
        moment = _moment(now)
        blob = encrypt(self._key, poll_token.encode("utf-8"), aad=flow_id)

        def work(conn: sqlite3.Connection) -> None:
            _purge_expired_rows(conn, moment)
            conn.execute(
                "INSERT INTO flows (flow_id, client_id, redirect_uri, redirect_uri_explicit, "
                "code_challenge, state, scopes, resource, poll_token_enc, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    flow_id,
                    client_id,
                    redirect_uri,
                    int(redirect_uri_explicit),
                    code_challenge,
                    state,
                    scopes,
                    resource,
                    blob,
                    moment + FLOW_TTL,
                ),
            )

        await self._write(work)

    async def load_flow(self, flow_id: str, *, now: int | None = None) -> FlowRow | None:
        """The flow, or ``None`` when it does not exist or ran out of time."""
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> FlowRow | None:
            row = conn.execute(
                "SELECT flow_id, client_id, redirect_uri, redirect_uri_explicit, code_challenge, "
                "state, scopes, resource, poll_token_enc, expires_at FROM flows "
                "WHERE flow_id = ? AND expires_at > ?",
                (flow_id, moment),
            ).fetchone()
            if row is None:
                return None
            return FlowRow(
                flow_id=row[0],
                client_id=row[1],
                redirect_uri=row[2],
                redirect_uri_explicit=bool(row[3]),
                code_challenge=row[4],
                state=row[5],
                scopes=row[6],
                resource=row[7],
                poll_token=decrypt(self._key, row[8], aad=row[0]).decode("utf-8"),
                expires_at=row[9],
            )

        return await self._read(work)

    async def delete_flow(self, flow_id: str) -> None:
        def work(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM flows WHERE flow_id = ?", (flow_id,))

        await self._write(work)

    async def redeem_flow(self, flow_id: str, *, now: int | None = None) -> bool:
        """Spend the flow, or return ``False``. The second caller always gets ``False``.

        The compare and set of :meth:`redeem_auth_code`, applied to the record a decision
        hangs on: two requests that read the same running flow must not both act on it
        (BL-19). The refusal belongs to the caller, which answers it as the page a flow
        that was already decided gets.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> bool:
            conn.execute("BEGIN IMMEDIATE")
            spent = _spend_flow(conn, flow_id, moment)
            conn.execute("COMMIT")
            return spent

        return await self._transaction(work)

    # --- authorizations -------------------------------------------------------------

    async def create_authorization(
        self,
        auth_id: str,
        *,
        client_id: str,
        nc_user: str,
        nc_account_id: str,
        app_password: str,
        scopes: str,
        resource: str,
        now: int | None = None,
    ) -> None:
        """Store one connection: one user, one dedicated Nextcloud app password.

        ``nc_account_id`` is required and may not be blank: no new connection exists without
        its canonical account id (the principal rule). Only rows written before the column
        existed lack it.
        """
        if not nc_account_id.strip():
            raise ValueError("a new connection needs its canonical account id")
        moment = _moment(now)
        blob = encrypt(self._key, app_password.encode("utf-8"), aad=auth_id)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO authorizations (auth_id, client_id, nc_user, nc_account_id, "
                "app_password_enc, scopes, resource, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (auth_id, client_id, nc_user, nc_account_id, blob, scopes, resource, moment),
            )

        await self._write(work)

    async def load_authorization(self, auth_id: str) -> AuthorizationRow | None:
        def work(conn: sqlite3.Connection) -> AuthorizationRow | None:
            row = conn.execute(
                "SELECT auth_id, client_id, nc_user, scopes, resource, created_at, revoked_at, "
                "cleanup_at, nc_account_id FROM authorizations WHERE auth_id = ?",
                (auth_id,),
            ).fetchone()
            return None if row is None else _authorization_row(row)

        return await self._read(work)

    async def app_password(self, auth_id: str) -> str | None:
        """Decrypt the Nextcloud app password of this authorization. An explicit act.

        Raises :class:`~mcp_connector.oauth.crypto.DecryptionRejected` when the ciphertext
        does not belong to this row or to this key, which is the case a moved ciphertext
        and a changed data key both produce.
        """

        def work(conn: sqlite3.Connection) -> bytes | None:
            row = conn.execute(
                "SELECT app_password_enc FROM authorizations WHERE auth_id = ?", (auth_id,)
            ).fetchone()
            return None if row is None else row[0]

        blob = await self._read(work)
        if blob is None:
            return None
        return decrypt(self._key, blob, aad=auth_id).decode("utf-8")

    async def delete_authorization(self, auth_id: str) -> None:
        """Remove a connection and, through the cascade, every code and token under it.

        The deliberate difference to :meth:`revoke_authorization`: a revoked authorization
        is a connection that existed and ended, and it is kept so a later revocation is
        idempotent and visible. A denied one never existed as far as the user is concerned,
        so the row goes and takes the ciphertext of an app password with it that nobody may
        ever use again.
        """

        def work(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM authorizations WHERE auth_id = ?", (auth_id,))

        await self._write(work)

    async def revoke_authorization(self, auth_id: str, *, now: int | None = None) -> None:
        """Mark the connection as gone. Idempotent: the first revocation time stands."""
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE authorizations SET revoked_at = ? WHERE auth_id = ? AND revoked_at IS NULL",
                (moment, auth_id),
            )

        await self._write(work)

    async def note_cleanup(self, auth_id: str, *, now: int | None = None) -> None:
        """Record that the Nextcloud app password of this connection is still out there.

        Written whenever a revocation could not hand the credential back, and whenever a
        revocation happened on a path that may not talk to Nextcloud at all, which is every
        path of the token endpoint (pitfall 13). Idempotent: the first note stands, because
        the interesting moment is the one at which the credential became an orphan.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE authorizations SET cleanup_at = ? WHERE auth_id = ? AND cleanup_at IS NULL",
                (moment, auth_id),
            )

        await self._write(work)

    async def clear_cleanup(self, auth_id: str) -> None:
        """The credential of this connection is gone from Nextcloud; the note can go too."""

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE authorizations SET cleanup_at = NULL WHERE auth_id = ?", (auth_id,)
            )

        await self._write(work)

    async def authorizations_of_client(
        self, client_id: str, limit: int | None = None
    ) -> list[AuthorizationRow]:
        """The connections booked under one client, oldest first (WR-04).

        Read before a client row is deleted, because ``authorizations`` points at
        ``clients`` with ``ON DELETE CASCADE`` and the delete takes the encrypted app
        password of every one of them with it. A caller that does not hand the credentials
        back first leaves them at Nextcloud with no record left that they exist, so no
        later sweep can find them either.

        ``limit`` is optional since BL-01, and the default is deliberately "all of them".
        A capped read in front of a cascading delete is not a bound on the work, it is a
        bound on how many credentials are handed back before the rest is destroyed: the
        rows beyond the cap went with the client row, ciphertext included, and nothing
        could find them afterwards. A caller that wants to bound its own cost bounds the
        number of *clients* it sweeps, which is what ``sweep_expired_clients`` does.

        ``None`` travels as ``LIMIT -1``, which is SQLite's own spelling of "no upper bound"
        (a negative limit expression). The statement therefore stays one constant string with
        one placeholder, and no branch of this method builds SQL out of a value.
        """
        capped = _NO_LIMIT if limit is None else limit

        def work(conn: sqlite3.Connection) -> list[AuthorizationRow]:
            rows = conn.execute(
                "SELECT auth_id, client_id, nc_user, scopes, resource, created_at, "
                "revoked_at, cleanup_at, nc_account_id FROM authorizations WHERE client_id = ? "
                "ORDER BY created_at LIMIT ?",
                (client_id, capped),
            ).fetchall()
            return [_authorization_row(row) for row in rows]

        return await self._read(work)

    async def authorizations_of_user(self, nc_user: str) -> list[AuthorizationRow]:
        """The live connections of one account, newest first (S5 of the connections page).

        ``nc_user`` here is the principal (oauth/principal.py): the canonical account id, or
        the login name of a legacy row without one. The same value keys ``user_access``.

        Only what still exists: a revoked connection ended, and the page that lists it is
        the page a user opens to see who can reach their Nextcloud right now. No ``limit``
        here, unlike :meth:`authorizations_of_client`: this list costs one local read and
        never one Nextcloud request per row, and a page that silently dropped the oldest
        connection would leave a user unable to disconnect it.

        An empty account id returns an empty list rather than every row of every account:
        the app context has no connections of its own (pitfall 10 of 04-RESEARCH.md).
        """
        if not nc_user.strip():
            return []

        def work(conn: sqlite3.Connection) -> list[AuthorizationRow]:
            rows = conn.execute(
                "SELECT auth_id, client_id, nc_user, scopes, resource, created_at, "
                "revoked_at, cleanup_at, nc_account_id FROM authorizations "
                "WHERE COALESCE(nc_account_id, nc_user) = ? "
                "AND revoked_at IS NULL ORDER BY created_at DESC",
                (nc_user,),
            ).fetchall()
            return [_authorization_row(row) for row in rows]

        return await self._read(work)

    async def all_authorizations(self) -> list[AuthorizationRow]:
        """Every connection this deployment ever wrote, oldest first, unfiltered (05-06).

        The read the instance wide purge starts from, and the only read of this store
        without a ``WHERE`` clause. It has to be that, and the two obvious models are both
        the wrong one: :meth:`authorizations_of_user` and :meth:`abandoned_authorizations`
        filter ``revoked_at IS NULL``, because they answer questions about connections that
        are still live.

        The purge asks a different question. Not "which connection exists" but "which
        Nextcloud app password of this instance may still be valid", and a revoked row
        answers yes to that. Revoking marks our own record; the credential in Nextcloud
        only goes when Nextcloud is asked to delete it, and every path that could not ask
        leaves a note in ``cleanup_at`` instead (pitfall 13, D-37). A purge built on a
        filtered read would therefore leave exactly those credentials behind: valid, and
        with no record left that they exist.

        No upper bound, spelled as SQLite's own ``LIMIT -1`` like
        :meth:`authorizations_of_client`, so the statement stays one constant string with
        one placeholder. A cap here would not bound the work, it would bound how many
        credentials are handed back before the rest is destroyed.
        """

        def work(conn: sqlite3.Connection) -> list[AuthorizationRow]:
            rows = conn.execute(
                "SELECT auth_id, client_id, nc_user, scopes, resource, created_at, "
                "revoked_at, cleanup_at, nc_account_id FROM authorizations "
                "ORDER BY created_at LIMIT ?",
                (_NO_LIMIT,),
            ).fetchall()
            return [_authorization_row(row) for row in rows]

        return await self._read(work)

    # --- the per account access switch (EXAPP-02) -----------------------------------

    async def set_access(self, nc_user: str, *, disabled: bool, now: int | None = None) -> None:
        """Pause or resume the MCP access of one Nextcloud account (D-47).

        Idempotent in both directions, and asymmetric on purpose. Pausing writes at most one
        row and keeps the first ``disabled_at``, so the moment the user pulled the brake
        stands even if the form is submitted twice. Resuming *deletes* the row instead of
        writing a zero into it: an account that was never paused and an account that was
        resumed are then the same truth in the file, and no reader can tell them apart
        wrongly. Being switched on therefore costs no row at all (D-50).

        A blank account id is a programming error and not a state: the app context has no
        switch, and a row under the empty string would be a switch nobody can reach and
        every empty identity would hit.
        """
        if not nc_user.strip():
            raise ValueError("nc_user must name an account; the app context has no switch")
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            if disabled:
                conn.execute(
                    "INSERT INTO user_access (nc_user, disabled_at) VALUES (?, ?) "
                    "ON CONFLICT(nc_user) DO NOTHING",
                    (nc_user, moment),
                )
                return
            conn.execute("DELETE FROM user_access WHERE nc_user = ?", (nc_user,))

        await self._write(work)

    async def access_disabled(self, nc_user: str) -> bool:
        """Whether this account has paused its MCP access. One local read, never a cache.

        This runs at the transport boundary on every MCP request, which is why it is a
        ``SELECT 1`` against a primary key in the file this container already owns: the
        switch may not cost a second Nextcloud roundtrip (D-47), and it may not be answered
        from a process cache either, because flipping it has to take effect on the very next
        request (D-48).

        **What it costs, measured instead of assumed (LO-02).** "One local read" was the
        whole sentence here, and the read is the cheapest part of it. The call opens its own
        connection in a worker thread, sets three pragmas, reads one row and closes again.
        Measured on 2026-08-20 on the development machine, 300 warm runs each: **1.77 ms**
        per call while the schema script ran on every open, **1.56 ms** with the script on
        the first open only, and 1.51 ms for a bare connection with the three pragmas and
        this one read. So the schema was the part worth removing, and what remains is the
        connection itself: the thread hop is 0.06 ms of it and the ``SELECT`` is not
        measurable beside them. That is the price of the property above, an answer that is
        never older than the request, and it sits on a route that deliberately carries no
        throttling (AR-03-04). Anything cheaper means a cache, and a cache means a paused
        account that is answered for a few seconds more.

        A blank account id is never paused and is answered without opening the file: the app
        context has no switch, and the OAuth branch of the boundary decides on the bearer
        (pitfall 10 of 04-RESEARCH.md).
        """
        if not nc_user.strip():
            return False

        def work(conn: sqlite3.Connection) -> bool:
            row = conn.execute("SELECT 1 FROM user_access WHERE nc_user = ?", (nc_user,)).fetchone()
            return row is not None

        return await self._read(work)

    async def expired_clients(self, limit: int, *, now: int | None = None) -> list[str]:
        """The client ids :meth:`purge_expired` would remove, read before anything is (WR-04).

        The same two windows as the purge below, and deliberately the same SQL shape: a
        caller reads this list, hands the credentials of those clients back to Nextcloud and
        deletes them, and the purge is then the backstop that removes what is left over.

        **A row read from a metadata document is not in this list** (pitfall 4, T-06-31).
        The registration TTL says "a registration that nobody ever used", and that sentence
        does not hold for an identity this server can read again at any time: such a row is
        never orphaned, and deleting it would take the connections under it along through the
        cascade, which is a user's connection ended by a deadline nobody set. The freshness
        of those rows is the other column and it costs a fetch, never a row. The purge below
        still removes them once they carry no connection at all, which is what keeps the
        table from growing, and re-reading the document writes the row again.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                "SELECT client_id FROM clients WHERE cimd_fetched_at IS NULL AND "
                "((last_used_at IS NULL AND registered_at < ?) OR "
                "(last_used_at IS NOT NULL AND last_used_at < ?)) "
                "ORDER BY registered_at LIMIT ?",
                (moment - UNUSED_CLIENT_TTL, moment - IDLE_CLIENT_TTL, limit),
            ).fetchall()
            return [str(row[0]) for row in rows]

        return await self._read(work)

    async def abandoned_authorizations(
        self, limit: int, *, now: int | None = None
    ) -> list[AuthorizationRow]:
        """Connections that were written by a sign in and then never used for anything.

        The consent bridge writes the authorization the moment the Login Flow v2 poll
        answers, because that answer arrives exactly once and carries a Nextcloud app
        password that exists from then on (plan 03-05). A browser that is closed at that
        moment leaves the row behind, and with it a working credential nobody will ever
        use. This query finds exactly those rows: no flow record any more, no code, no
        token of either kind, not revoked, and older than the deadline of a sign in, so a
        flow that is still running cannot be caught by it.

        A connection whose tokens all expired matches as well, and deliberately so: the
        short lived rows are removed by every write, so a row without any of them is either
        a sign in nobody finished or a connection that ended by running out. Both own an
        app password that has to go back.

        ``limit`` is not optional. The caller pays for every row with one Nextcloud request,
        and an unbounded sweep on a browser path is a timeout waiting to happen.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> list[AuthorizationRow]:
            rows = conn.execute(
                "SELECT a.auth_id, a.client_id, a.nc_user, a.scopes, a.resource, a.created_at, "
                "a.revoked_at, a.cleanup_at, a.nc_account_id FROM authorizations AS a "
                "LEFT JOIN flows AS f ON f.flow_id = a.auth_id "
                "WHERE a.revoked_at IS NULL AND f.flow_id IS NULL AND a.created_at < ? "
                "AND NOT EXISTS (SELECT 1 FROM auth_codes AS c WHERE c.auth_id = a.auth_id) "
                "AND NOT EXISTS (SELECT 1 FROM refresh_tokens AS r WHERE r.auth_id = a.auth_id) "
                "AND NOT EXISTS (SELECT 1 FROM access_tokens AS t WHERE t.auth_id = a.auth_id) "
                "ORDER BY a.created_at LIMIT ?",
                (moment - FLOW_TTL, limit),
            ).fetchall()
            return [_authorization_row(row) for row in rows]

        return await self._read(work)

    # --- authorization codes --------------------------------------------------------

    async def create_auth_code(
        self,
        code: str,
        *,
        auth_id: str,
        redirect_uri: str,
        code_challenge: str,
        resource: str,
        redirect_uri_explicit: bool = True,
        now: int | None = None,
    ) -> None:
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            _purge_expired_rows(conn, moment)
            conn.execute(
                "INSERT INTO auth_codes (code_hash, auth_id, redirect_uri, "
                "redirect_uri_explicit, code_challenge, resource, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    token_hash(code),
                    auth_id,
                    redirect_uri,
                    int(redirect_uri_explicit),
                    code_challenge,
                    resource,
                    moment + AUTH_CODE_TTL,
                ),
            )

        await self._write(work)

    async def redeem_flow_for_code(
        self,
        flow_id: str,
        code: str,
        *,
        redirect_uri: str,
        code_challenge: str,
        resource: str,
        redirect_uri_explicit: bool = True,
        now: int | None = None,
    ) -> bool:
        """Turn one running flow into exactly one code, or write nothing and return ``False``.

        :meth:`create_auth_code` followed by :meth:`delete_flow` was a check then act, and
        the consent screen is a place where two requests really do arrive at once: both
        approvals read a flow that was still there and both wrote a code, so one consent
        handed out two codes (BL-19). Here the deletion of the flow *is* the claim, the
        insert runs only for the caller whose deletion found the row, and the two are one
        ``BEGIN IMMEDIATE`` transaction, so the loser leaves nothing behind at all.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> bool:
            conn.execute("BEGIN IMMEDIATE")
            if not _spend_flow(conn, flow_id, moment):
                conn.execute("COMMIT")
                return False
            _purge_expired_rows(conn, moment)
            conn.execute(
                "INSERT INTO auth_codes (code_hash, auth_id, redirect_uri, "
                "redirect_uri_explicit, code_challenge, resource, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    token_hash(code),
                    flow_id,
                    redirect_uri,
                    int(redirect_uri_explicit),
                    code_challenge,
                    resource,
                    moment + AUTH_CODE_TTL,
                ),
            )
            conn.execute("COMMIT")
            return True

        return await self._transaction(work)

    async def load_auth_code(self, code: str, *, now: int | None = None) -> AuthCodeRow | None:
        """A code that is still redeemable, or ``None``. Reads, never consumes.

        The token endpoint of the SDK loads a code, checks four things about it and only
        then asks the provider to exchange it, so the load has to leave the code alone.
        The single use is enforced where the tokens are issued, by
        :meth:`redeem_auth_code`, which is one atomic statement rather than this read
        followed by a write.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> AuthCodeRow | None:
            row = conn.execute(
                "SELECT auth_id, redirect_uri, redirect_uri_explicit, code_challenge, resource, "
                "expires_at FROM auth_codes "
                "WHERE code_hash = ? AND used_at IS NULL AND expires_at > ?",
                (token_hash(code), moment),
            ).fetchone()
            return None if row is None else _auth_code_row(row)

        return await self._read(work)

    async def redeem_auth_code(self, code: str, *, now: int | None = None) -> AuthCodeRow | None:
        """Consume the code, or return ``None``. The second caller always gets ``None``.

        The same compare and set the refresh rotation uses, for the same reason: two
        requests with one code must not both receive a token.
        """
        moment = _moment(now)
        digest = token_hash(code)

        def work(conn: sqlite3.Connection) -> AuthCodeRow | None:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "UPDATE auth_codes SET used_at = ? "
                "WHERE code_hash = ? AND used_at IS NULL AND expires_at > ?",
                (moment, digest, moment),
            )
            if cursor.rowcount != 1:
                conn.execute("COMMIT")
                return None
            row = conn.execute(
                "SELECT auth_id, redirect_uri, redirect_uri_explicit, code_challenge, resource, "
                "expires_at FROM auth_codes WHERE code_hash = ?",
                (digest,),
            ).fetchone()
            conn.execute("COMMIT")
            return _auth_code_row(row)

        return await self._transaction(work)

    # --- access tokens --------------------------------------------------------------

    async def create_access_token(
        self,
        token: str,
        *,
        auth_id: str,
        family_id: str,
        scopes: str,
        resource: str,
        now: int | None = None,
    ) -> None:
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            _purge_expired_rows(conn, moment)
            conn.execute(
                "INSERT INTO access_tokens (token_hash, auth_id, family_id, scopes, resource, "
                "expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    token_hash(token),
                    auth_id,
                    family_id,
                    scopes,
                    resource,
                    moment + ACCESS_TOKEN_TTL,
                ),
            )

        await self._write(work)

    async def load_access_token(
        self, token: str, *, now: int | None = None
    ) -> AccessTokenRow | None:
        """A token that is valid right now, or ``None``. There is no third answer.

        Expired, revoked and issued under a revoked authorization are one case for the
        verifier, and the join is what makes a revoked connection take effect immediately
        instead of at the next sweep (SC 4, D-37).
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> AccessTokenRow | None:
            row = conn.execute(
                "SELECT t.auth_id, t.family_id, a.nc_user, t.scopes, t.resource, t.expires_at, "
                "a.nc_account_id "
                "FROM access_tokens AS t JOIN authorizations AS a ON a.auth_id = t.auth_id "
                "WHERE t.token_hash = ? AND t.revoked_at IS NULL AND t.expires_at > ? "
                "AND a.revoked_at IS NULL",
                (token_hash(token), moment),
            ).fetchone()
            if row is None:
                return None
            return AccessTokenRow(
                auth_id=row[0],
                family_id=row[1],
                nc_user=row[2],
                scopes=row[3],
                resource=row[4],
                expires_at=row[5],
                nc_account_id=row[6],
            )

        return await self._read(work)

    # --- refresh tokens -------------------------------------------------------------

    async def create_refresh_token(
        self, token: str, *, auth_id: str, family_id: str, now: int | None = None
    ) -> None:
        """Open a new family. Every later token of it comes out of a redemption."""
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            _purge_expired_rows(conn, moment)
            _insert_refresh_token(conn, token_hash(token), auth_id, family_id, moment)

        await self._write(work)

    async def load_refresh_token(self, token: str) -> RefreshTokenRow | None:
        def work(conn: sqlite3.Connection) -> RefreshTokenRow | None:
            row = conn.execute(
                "SELECT auth_id, family_id, state, successor, issued_at, used_at, expires_at "
                "FROM refresh_tokens WHERE token_hash = ?",
                (token_hash(token),),
            ).fetchone()
            if row is None:
                return None
            return RefreshTokenRow(
                auth_id=row[0],
                family_id=row[1],
                state=_checked_state(row[2]),
                successor=row[3],
                issued_at=row[4],
                used_at=row[5],
                expires_at=row[6],
            )

        return await self._read(work)

    async def redeem_refresh_token(
        self, token: str, *, successor: str, now: int | None = None
    ) -> RefreshRedemption:
        """Rotate this token, atomically, and say precisely what happened.

        One ``UPDATE`` inside ``BEGIN IMMEDIATE`` is the whole race protection: the write
        lock is taken before the row is read, so of two simultaneous callers exactly one
        changes a row. Zero changed rows is never a success; the row is then read to tell
        unknown, expired and already used apart, because plan 03-07 kills the family for
        the third case and answers a plain ``invalid_grant`` for the first two.

        The successor is inserted in the same transaction. A rotation that changed the old
        row but died before writing the new one would leave a user with no valid token at
        all, which is the reliability half of the owner directive.
        """
        moment = _moment(now)
        digest = token_hash(token)
        successor_digest = token_hash(successor)

        def work(conn: sqlite3.Connection) -> RefreshRedemption:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "UPDATE refresh_tokens SET state = ?, used_at = ?, successor = ? "
                "WHERE token_hash = ? AND state = ? AND expires_at > ?",
                (STATE_USED, moment, successor_digest, digest, STATE_ACTIVE, moment),
            )
            if cursor.rowcount == 1:
                row = conn.execute(
                    "SELECT auth_id, family_id FROM refresh_tokens WHERE token_hash = ?",
                    (digest,),
                ).fetchone()
                _insert_refresh_token(conn, successor_digest, row[0], row[1], moment)
                conn.execute("COMMIT")
                return RefreshRedemption(outcome=REDEEM_OK, auth_id=row[0], family_id=row[1])

            row = conn.execute(
                "SELECT auth_id, family_id, state, successor, used_at, expires_at "
                "FROM refresh_tokens WHERE token_hash = ?",
                (digest,),
            ).fetchone()
            conn.execute("COMMIT")
            if row is None:
                return RefreshRedemption(outcome=REDEEM_UNKNOWN)
            state = _checked_state(row[2])
            if state == STATE_ACTIVE:
                # The only way an active row does not match the update above.
                return RefreshRedemption(outcome=REDEEM_EXPIRED, auth_id=row[0], family_id=row[1])
            return RefreshRedemption(
                outcome=REDEEM_REUSED,
                auth_id=row[0],
                family_id=row[1],
                used_at=row[4],
                successor=row[3],
            )

        return await self._transaction(work)

    async def revoke_family(self, family_id: str, *, now: int | None = None) -> None:
        """End a whole token family in one transaction (reuse detection, SC 4).

        The refresh tokens carry a state and the access tokens carry a revocation time;
        that asymmetry is the schema of 03-RESEARCH.md and not an oversight, because only
        the refresh tokens have a state machine to be in.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE refresh_tokens SET state = ? WHERE family_id = ? AND state != ?",
                (STATE_REVOKED, family_id, STATE_REVOKED),
            )
            conn.execute(
                "UPDATE access_tokens SET revoked_at = ? WHERE family_id = ? "
                "AND revoked_at IS NULL",
                (moment, family_id),
            )
            conn.execute("COMMIT")

        await self._transaction(work)

    async def families_of_authorization(self, auth_id: str) -> list[str]:
        """Every token family that was ever opened under one connection.

        The token paths know the family they are dealing with, because a presented token
        names it. The connections page of EXAPP-02 does not: it holds a handle, and a
        connection that a user ended must not keep a second family alive, so the families
        are read here rather than guessed. Both tables are asked, because a family whose
        refresh token has already been purged can still have a live access token in it.
        """

        def work(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                "SELECT family_id FROM refresh_tokens WHERE auth_id = ? "
                "UNION SELECT family_id FROM access_tokens WHERE auth_id = ?",
                (auth_id, auth_id),
            ).fetchall()
            return [row[0] for row in rows]

        return await self._read(work)

    # --- housekeeping ---------------------------------------------------------------

    async def purge_expired(self, *, now: int | None = None) -> None:
        """Remove what has run out, including registrations nobody ever used.

        Called at startup and opportunistically from the client lookup of plan 03-06. The
        expired rows of the four short lived tables are already removed by every write, so
        what this adds is the client policy, which is kept out of the write path because
        deleting a client deletes its authorizations through the cascade.

        And that cascade is why a client with authorizations left is not removed here
        (WR-04). The delete takes the encrypted app password of every connection under it
        along, and this method cannot hand a credential back: it runs in a worker thread on
        one SQLite connection and talks to nobody. So the row survives one more round and
        :meth:`OAuthStore.expired_clients` hands it to the caller that can, which revokes
        the app passwords, deletes the authorizations and then deletes the client. What is
        left for this method is the ordinary case, a registration nobody ever signed in
        under.

        The third statement is the one table that had no cleanup at all (LO-03). A pause is
        one row under an account id, written by the connections page and removed when the
        user resumes, and nothing ever removed it otherwise: a deleted account kept its
        pause, and on a directory setup that reuses account ids the next account of that
        name started silently paused. A row goes only when both halves hold, no
        authorization of that account and a pause older than :data:`STALE_ACCESS_TTL`, so
        the switch of anybody who has a connection stays untouched however old it is. A
        revoked authorization counts as a connection here: its Nextcloud app password may
        still exist, so the account is not a stranger.
        """
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> None:
            _purge_expired_rows(conn, moment)
            if self._oidc:
                conn.execute("DELETE FROM oidc_transactions WHERE expires_at <= ?", (moment,))
                conn.execute("DELETE FROM oidc_proofs WHERE expires_at <= ?", (moment,))
            conn.execute(
                "DELETE FROM user_access WHERE disabled_at < ? "
                "AND NOT EXISTS (SELECT 1 FROM authorizations AS a "
                "WHERE COALESCE(a.nc_account_id, a.nc_user) = user_access.nc_user)",
                (moment - STALE_ACCESS_TTL,),
            )
            conn.execute(
                "DELETE FROM clients WHERE last_used_at IS NULL AND registered_at < ? "
                "AND NOT EXISTS (SELECT 1 FROM authorizations AS a "
                "WHERE a.client_id = clients.client_id)",
                (moment - UNUSED_CLIENT_TTL,),
            )
            conn.execute(
                "DELETE FROM clients WHERE last_used_at IS NOT NULL AND last_used_at < ? "
                "AND NOT EXISTS (SELECT 1 FROM authorizations AS a "
                "WHERE a.client_id = clients.client_id)",
                (moment - IDLE_CLIENT_TTL,),
            )

        await self._write(work)

    async def verify_data_key(self) -> None:
        """Refuse a data key that is not the key this store was written with.

        One immediate transaction, so two workers that start together cannot both record a
        check value. A store with a recorded value compares against it. A store without one
        (an older file, or a new one) tries up to :data:`KEY_CHECK_SAMPLES` encrypted rows:
        if there are rows and none of them decrypts, the key is wrong; otherwise the key is
        adopted and its check value recorded. Nothing is ever overwritten, so a wrong key
        cannot replace the right one. Raises :class:`StoreKeyMismatch`.
        """
        expected = crypto.key_check(self._key)

        def work(conn: sqlite3.Connection) -> bool:
            conn.execute(_META_SCHEMA)
            row = conn.execute(
                "SELECT value FROM store_meta WHERE name = ?", (KEY_CHECK_NAME,)
            ).fetchone()
            if row is None:
                samples = conn.execute(
                    "SELECT auth_id, app_password_enc FROM authorizations "
                    "UNION ALL SELECT flow_id, poll_token_enc FROM flows LIMIT ?",
                    (KEY_CHECK_SAMPLES,),
                ).fetchall()
                if samples and not any(self._decrypts(blob, aad) for aad, blob in samples):
                    return False
                conn.execute(
                    "INSERT INTO store_meta (name, value) VALUES (?, ?)",
                    (KEY_CHECK_NAME, expected),
                )
                return True
            return hmac.compare_digest(str(row[0]), expected)

        if not await self._write(work):
            raise StoreKeyMismatch

    def _decrypts(self, blob: bytes, aad: str) -> bool:
        try:
            decrypt(self._key, blob, aad=aad)
        except DecryptionRejected:
            return False
        return True

    async def wipe_all(self) -> None:
        """Empty every table of the schema in one transaction. The file stays (05-06).

        What this is: the local half of ``occ mcp_connector:purge``, run after every
        Nextcloud app password of this instance has been handed back and before the data
        key is deleted. What it is not: a replacement for
        ``occ app_api:app:unregister mcp_connector --rm-data``. It is the precondition of
        that command, because ``--rm-data`` removes the volume and takes with it the only
        record of which credential belonged to which connection. Whoever runs it first can
        never revoke those app passwords again (pattern 4 of 05-RESEARCH.md).

        The file and the schema stay usable on purpose: the purge runs inside a live
        process that has to answer the request it arrived in, and every request after it,
        without creating its store again.

        One statement per table rather than a loop over a tuple of names, and children
        before parents even though the cascades would do it anyway. The explicit order
        keeps working if a foreign key is ever dropped, and the literal ``DELETE FROM``
        keeps these statements inside the narrow, counter proved exemption the destructive
        gate grants this one file (``tests/contract/test_no_destructive_calls.py``).
        """

        def work(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM access_tokens")
            conn.execute("DELETE FROM refresh_tokens")
            conn.execute("DELETE FROM auth_codes")
            conn.execute("DELETE FROM flows")
            conn.execute("DELETE FROM authorizations")
            conn.execute("DELETE FROM clients")
            # Its own statement because it hangs on no cascade: the per account switch of
            # EXAPP-02 has no foreign key, so emptying every authorization leaves every
            # paused account paused (D-50).
            conn.execute("DELETE FROM user_access")
            # The key check goes with the data it vouched for: the purge deletes the key
            # next, and a check value that outlived it would refuse the fresh key of the
            # next start. The table exists only where a deployment asked for the check.
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'store_meta'"
            ).fetchone():
                conn.execute("DELETE FROM store_meta")
            # The two OIDC tables hang on flows and are already empty through the cascade;
            # the statements make that independent of the foreign keys, like above.
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'oidc_proofs'"
            ).fetchone():
                conn.execute("DELETE FROM oidc_proofs")
                conn.execute("DELETE FROM oidc_transactions")

        await self._write(work)

    # --- standalone OIDC browser identity -------------------------------------------

    async def create_oidc_transaction(
        self,
        *,
        state: str,
        flow_id: str,
        browser_handle: str,
        nonce: str,
        code_verifier: str,
        now: int | None = None,
    ) -> bool:
        """Remember one OIDC sign in for a flow whose authorization already exists.

        ``False`` when the flow is gone or expired, when its authorization is missing,
        revoked or has no canonical account id, or when this browser already has
        :data:`OIDC_TRANSACTIONS_PER_BROWSER` open sign ins. The row lives
        :data:`OIDC_TTL` seconds and never longer than its flow.
        """
        self._require_oidc()
        moment = _moment(now)
        state_hash = token_hash(state)
        nonce_enc = encrypt(
            self._key, nonce.encode("utf-8"), aad=_oidc_aad("transactions", "nonce", state_hash)
        )
        verifier_enc = encrypt(
            self._key,
            code_verifier.encode("utf-8"),
            aad=_oidc_aad("transactions", "verifier", state_hash),
        )
        browser_hash = token_hash(browser_handle)

        def work(conn: sqlite3.Connection) -> bool:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM oidc_transactions WHERE expires_at <= ?", (moment,))
            (open_count,) = conn.execute(
                "SELECT COUNT(*) FROM oidc_transactions WHERE browser_hash = ?",
                (browser_hash,),
            ).fetchone()
            if open_count >= OIDC_TRANSACTIONS_PER_BROWSER:
                conn.execute("COMMIT")
                return False
            cursor = conn.execute(
                "INSERT INTO oidc_transactions (state_hash, flow_id, browser_hash, nonce_enc, "
                "verifier_enc, created_at, expires_at) "
                "SELECT ?, f.flow_id, ?, ?, ?, ?, MIN(f.expires_at, ?) "
                "FROM flows AS f JOIN authorizations AS a ON a.auth_id = f.flow_id "
                "WHERE f.flow_id = ? AND f.expires_at > ? AND a.revoked_at IS NULL "
                "AND a.nc_account_id IS NOT NULL AND a.nc_account_id != ''",
                (
                    state_hash,
                    browser_hash,
                    nonce_enc,
                    verifier_enc,
                    moment,
                    moment + OIDC_TTL,
                    flow_id,
                    moment,
                ),
            )
            conn.execute("COMMIT")
            return cursor.rowcount == 1

        return await self._transaction(work)

    async def redeem_oidc_transaction(
        self, *, state: str, browser_handle: str, now: int | None = None
    ) -> OidcTransaction | None:
        """Consume the sign in behind ``state``, or return ``None``. Exactly once.

        The row is deleted as soon as its state is known, whatever follows: a known state
        with a wrong or missing browser binding ends that sign in for good (H2), and so do
        an expired row and a ciphertext that does not belong to it. Every refusal is the
        same ``None``, so a caller cannot answer differently for them (oracle-free).
        """
        self._require_oidc()
        moment = _moment(now)
        state_hash = token_hash(state)

        def work(conn: sqlite3.Connection) -> tuple[Any, ...] | None:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT flow_id, browser_hash, nonce_enc, verifier_enc, expires_at "
                "FROM oidc_transactions WHERE state_hash = ?",
                (state_hash,),
            ).fetchone()
            if row is not None:
                conn.execute("DELETE FROM oidc_transactions WHERE state_hash = ?", (state_hash,))
            conn.execute("COMMIT")
            return row

        row = await self._transaction(work)
        if row is None or row[4] <= moment:
            return None
        if not hmac.compare_digest(str(row[1]), token_hash(browser_handle)):
            return None
        try:
            nonce = decrypt(
                self._key, row[2], aad=_oidc_aad("transactions", "nonce", state_hash)
            ).decode("utf-8")
            verifier = decrypt(
                self._key, row[3], aad=_oidc_aad("transactions", "verifier", state_hash)
            ).decode("utf-8")
        except (DecryptionRejected, TypeError, UnicodeDecodeError):
            # TypeError: a value that is not a ciphertext at all, e.g. rewritten as text.
            # UnicodeDecodeError: a genuine ciphertext whose plaintext is not valid UTF-8.
            return None
        return OidcTransaction(
            flow_id=row[0],
            nonce=nonce,
            code_verifier=verifier,
            expires_at=row[4],
        )

    async def create_browser_proof(
        self, *, proof_handle: str, flow_id: str, principal: str, now: int | None = None
    ) -> bool:
        """Record that this browser proved ``principal`` for this flow; one proof per flow.

        An earlier proof of the same flow is replaced, so an older handle stops working the
        moment a new one is issued (rotation after the callback, H1). ``False`` when the
        flow is gone or expired. The proof lives :data:`OIDC_TTL` seconds and never longer
        than its flow.
        """
        self._require_oidc()
        if not principal.strip():
            raise ValueError("a browser proof needs a principal")
        moment = _moment(now)
        proof_hash = token_hash(proof_handle)

        def work(conn: sqlite3.Connection) -> bool:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM oidc_proofs WHERE flow_id = ?", (flow_id,))
            cursor = conn.execute(
                "INSERT INTO oidc_proofs (proof_hash, flow_id, principal, created_at, expires_at) "
                "SELECT ?, f.flow_id, ?, ?, MIN(f.expires_at, ?) FROM flows AS f "
                "WHERE f.flow_id = ? AND f.expires_at > ?",
                (proof_hash, principal, moment, moment + OIDC_TTL, flow_id, moment),
            )
            conn.execute("COMMIT")
            return cursor.rowcount == 1

        return await self._transaction(work)

    async def browser_proof_principal(
        self, *, proof_handle: str, flow_id: str, now: int | None = None
    ) -> str | None:
        """The principal a live proof of this browser names for this flow. Consumes nothing."""
        self._require_oidc()
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                "SELECT principal FROM oidc_proofs "
                "WHERE proof_hash = ? AND flow_id = ? AND expires_at > ?",
                (token_hash(proof_handle), flow_id, moment),
            ).fetchone()
            return None if row is None else str(row[0])

        return await self._read(work)

    async def redeem_browser_proof(
        self, *, proof_handle: str, flow_id: str, now: int | None = None
    ) -> str | None:
        """Consume the proof of this browser for this flow and return its principal, once."""
        self._require_oidc()
        moment = _moment(now)
        proof_hash = token_hash(proof_handle)

        def work(conn: sqlite3.Connection) -> str | None:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT principal FROM oidc_proofs "
                "WHERE proof_hash = ? AND flow_id = ? AND expires_at > ?",
                (proof_hash, flow_id, moment),
            ).fetchone()
            if row is not None:
                conn.execute("DELETE FROM oidc_proofs WHERE proof_hash = ?", (proof_hash,))
            conn.execute("COMMIT")
            return None if row is None else str(row[0])

        return await self._transaction(work)

    def _require_oidc(self) -> None:
        if not self._oidc:
            raise RuntimeError("this store was opened without the OIDC tables")

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

        The transaction is explicit, and it has to be (WR-05). The connection is opened
        with ``isolation_level=None``, which is autocommit: every ``execute`` of ``work``
        used to commit on its own and the ``conn.commit()`` here was a statement about
        nothing. :meth:`_write` promised the opposite in one line of documentation, so the
        next caller that groups two statements there would have got none of it, and a body
        that failed halfway would have left the half it had already written.

        ``BEGIN IMMEDIATE`` and not ``BEGIN``: the write lock is taken at the start, so two
        writers meet at the beginning of their work rather than at its end, which is the
        same rule the bodies that open their own transaction follow (pitfall 10). The
        rollback is best effort, because there is one case in which no transaction is open
        any more, and it is the interesting one: a body that hit the busy timeout on its
        own ``BEGIN``. Failing there would replace the real error with a second one.

        **The schema runs on the first open of this object and when the file is gone**
        (LO-02). It used to run on every open, thirteen statements that create what is
        already there, and that sat on every MCP request of an authenticated identity
        through :meth:`access_disabled`. What replaces it is a flag plus one ``exists``:
        the flag is what makes the ordinary call cheap, and the ``exists`` is what keeps
        the cheap call honest, because SQLite creates an empty file for a connection to a
        path that has none. Without the second half, a volume that is removed while the
        process runs would turn every later call into "no such table" until a restart.

        The flag belongs to this object and not to the module. Two processes on the same
        volume are a supported case (SRV-05), and a process that trusted the flag of
        another one would be trusting a file it never looked at. Two threads of this object
        that open at the same moment can both see it unset and both run the script, which
        costs one extra script and nothing else: every statement of it is
        ``IF NOT EXISTS``.
        """
        needs_schema = not self._schema_ready or not self._path.exists()
        conn = _connect(self._path, schema=needs_schema)
        if needs_schema and self._oidc:
            conn.executescript(OIDC_SCHEMA)
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


def store_opener(env: Mapping[str, str] | None = None) -> StoreProvider:
    """The store of an ExApp deployment: AppAPI volume and the key kept in Nextcloud.

    The composition of :func:`explicit_store_opener` for this one deployment mode. The key
    comes from :func:`crypto.data_key`, the directory from :func:`config.persistent_storage`.
    Any other deployment passes its own two inputs to :func:`explicit_store_opener` and never
    reaches the development fallback of :func:`config.persistent_storage`.
    """

    async def exapp_key() -> bytes:
        return await crypto.data_key(env)

    def exapp_directory() -> Path:
        return config.persistent_storage(env)

    # No key check for the ExApp, deliberately: its key lives in Nextcloud and is replaced by
    # a reinstallation that keeps the volume. Today that makes the old rows unreadable one by
    # one while new connections work; a check would refuse the whole store instead. Changing
    # that is a decision for the ExApp, not a side effect of the standalone preparation.
    return explicit_store_opener(directory=exapp_directory, key=exapp_key, strict=False)


def explicit_store_opener(
    *, directory: DirectoryProvider, key: KeyProvider, strict: bool = True
) -> StoreProvider:
    """One store per application, opened at its first use and swept when it opens.

    The store cannot be built when the routes are: the data key comes from Nextcloud over
    HTTP, which needs a running event loop, and a deployment that is not complete has to
    end in a page rather than in a failed import. So the callers get a function, and the
    first request that needs the store pays for opening it.

    The first open is also where :meth:`OAuthStore.purge_expired` runs. This project has no
    cron and no scheduler, so the sweep that removes what ran out hangs on the first use of
    the store and on every write after that (T-03-17).

    The cache lives in this closure and not in a module global, for the reason D-20 gives:
    a dictionary that outlives a request is one refactor away from being a session store.
    Two applications in one process, which is what every test builds, get one store each
    unless the caller passes the same opener to both.

    ``strict`` is the default for every deployment except the ExApp. It opens the store with
    the two OIDC tables (:data:`OIDC_SCHEMA`) and adds two rules before anything else
    touches the file. The store file is created with mode 0600 and
    must be a regular, owner-only file (:class:`StoreFileRefused`); SQLite gives its
    ``-wal`` and ``-shm`` files the mode of the database. And the data key is checked
    (:meth:`OAuthStore.verify_data_key`, :class:`StoreKeyMismatch`). Both rules assume a
    directory nobody else can write into, which :func:`config.storage_directory` enforces.
    """
    opened: dict[str, OAuthStore] = {}
    lock = asyncio.Lock()

    async def open_once() -> OAuthStore:
        ready = opened.get("store")
        if ready is not None:
            return ready
        async with lock:
            ready = opened.get("store")
            if ready is None:
                # The key first: it is the one step that can fail with a named error, and
                # it fails before anything creates a directory.
                data_key = await key()
                path = directory() / STORE_FILENAME
                if strict:
                    _prepare_private_file(path)
                candidate = OAuthStore(path, data_key, oidc=strict)
                if strict:
                    # Before the sweep and before anything is cached, so the next request
                    # asks again. A recorded check value is compared before any protected
                    # row is read; an older store without one is tested against a bounded
                    # sample of its encrypted rows (see verify_data_key).
                    await candidate.verify_data_key()
                await candidate.purge_expired()
                ready = candidate
                opened["store"] = ready
            return ready

    return open_once


def _prepare_private_file(path: Path) -> None:
    """Create the store file owner-only if it is missing, then refuse anything else.

    ``O_EXCL`` never opens an existing entry, a link included, so a file this call creates
    is new and has mode 0600 (or stricter under the umask). An existing entry is checked
    with ``lstat``: a link, a directory or a file with any group or other bits is refused.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(descriptor)
    try:
        status = path.lstat()
    except OSError:
        raise StoreFileRefused from None
    if not stat.S_ISREG(status.st_mode):
        raise StoreFileRefused
    # POSIX only, for the reason config.storage_directory gives.
    if os.name != "nt" and status.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise StoreFileRefused


def _connect(path: Path, *, schema: bool = True) -> sqlite3.Connection:
    """One connection with the three pragmas, and the schema when the caller asks for it.

    ``isolation_level=None`` turns off the implicit transaction handling of the standard
    library, which is what makes an explicit ``BEGIN IMMEDIATE`` mean what it says.

    The three pragmas run every time, because two of them are properties of a connection
    and not of a file: ``foreign_keys`` off for one connection means no cascade for the
    statements of that connection. The schema and the column migration are properties of
    the file, so :meth:`OAuthStore._call` decides when they are needed (LO-02).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=_BUSY_TIMEOUT_SECONDS)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    if schema:
        conn.executescript(SCHEMA)
        _add_missing_columns(conn)
    return conn


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Bring a file written by an earlier build up to the schema above.

    ``CREATE TABLE IF NOT EXISTS`` does nothing to a table that already exists, so a store
    file from a development build before plan 03-06 would keep an ``auth_codes`` table
    without ``redirect_uri_explicit`` and fail on the first insert. One ``ALTER TABLE`` with
    the same default as the schema is the whole migration, and it is idempotent because it
    asks first. Nothing here rewrites a row: a column that is added with a default is what
    every existing code carried anyway, an authorization request that named its return
    address.

    The two columns of plan 06-05 are the same migration in its cheapest form: they are
    nullable and have no default, so a ``clients`` table written by an earlier build grows
    two empty columns and every row in it keeps meaning exactly what it meant, a client that
    registered and has no metadata document to be fresh about (``cleanup_at`` above is the
    same shape and the same reasoning). There is no data migration here either, and there is
    nothing that could be migrated: no existing row was ever read from a document.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(auth_codes)")}
    if "redirect_uri_explicit" not in columns:
        conn.execute(
            "ALTER TABLE auth_codes ADD COLUMN redirect_uri_explicit INTEGER NOT NULL DEFAULT 1"
        )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(authorizations)")}
    if "cleanup_at" not in columns:
        conn.execute("ALTER TABLE authorizations ADD COLUMN cleanup_at INTEGER")
    if "nc_account_id" not in columns:
        # Nullable, no default and no backfill: an older row keeps meaning what it meant, a
        # connection whose principal is its login name (oauth/principal.py).
        conn.execute("ALTER TABLE authorizations ADD COLUMN nc_account_id TEXT")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(clients)")}
    if "cimd_fetched_at" not in columns:
        conn.execute("ALTER TABLE clients ADD COLUMN cimd_fetched_at INTEGER")
    if "cimd_expires_at" not in columns:
        conn.execute("ALTER TABLE clients ADD COLUMN cimd_expires_at INTEGER")


def _authorization_row(row: tuple[Any, ...]) -> AuthorizationRow:
    """One shape for the three places that read a connection, in the column order they
    all select. The third reader arrived with the connections page of phase 4, and a third
    hand written copy of eight fields is how two of them end up meaning different things."""
    return AuthorizationRow(
        auth_id=row[0],
        client_id=row[1],
        nc_user=row[2],
        scopes=row[3],
        resource=row[4],
        created_at=row[5],
        revoked_at=row[6],
        cleanup_at=row[7],
        nc_account_id=row[8],
    )


def _auth_code_row(row: tuple[Any, ...]) -> AuthCodeRow:
    """One shape for the two places that read a code, so they cannot drift apart."""
    return AuthCodeRow(
        auth_id=row[0],
        redirect_uri=row[1],
        redirect_uri_explicit=bool(row[2]),
        code_challenge=row[3],
        resource=row[4],
        expires_at=row[5],
    )


#: How long the loser of a lock waits for the winner. Long enough for a transaction that
#: writes two rows, short enough that a wedged process answers instead of hanging.
_BUSY_TIMEOUT_MS = 5000
_BUSY_TIMEOUT_SECONDS = _BUSY_TIMEOUT_MS / 1000


def _insert_refresh_token(
    conn: sqlite3.Connection, digest: str, auth_id: str, family_id: str, moment: int
) -> None:
    conn.execute(
        "INSERT INTO refresh_tokens (token_hash, auth_id, family_id, state, issued_at, "
        "expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (digest, auth_id, family_id, STATE_ACTIVE, moment, moment + REFRESH_TOKEN_TTL),
    )


def _spend_flow(conn: sqlite3.Connection, flow_id: str, moment: int) -> bool:
    """Delete one running flow, and say whether this caller is the one that deleted it.

    ``expires_at`` is part of the condition for the reason :meth:`OAuthStore.load_flow`
    carries it: a row that ran out of time is not a running flow any more, so a claim on it
    may not succeed either. Called inside a transaction the caller opened, never on its own.
    """
    cursor = conn.execute(
        "DELETE FROM flows WHERE flow_id = ? AND expires_at > ?", (flow_id, moment)
    )
    return cursor.rowcount == 1


def _purge_expired_rows(conn: sqlite3.Connection, moment: int) -> None:
    """Drop what has run out. Opportunistic, so this project needs no cron (T-03-17)."""
    conn.execute("DELETE FROM flows WHERE expires_at <= ?", (moment,))
    conn.execute("DELETE FROM auth_codes WHERE expires_at <= ?", (moment,))
    conn.execute("DELETE FROM refresh_tokens WHERE expires_at <= ?", (moment,))
    conn.execute("DELETE FROM access_tokens WHERE expires_at <= ?", (moment,))


def _checked_state(value: str) -> str:
    """Return the state, or refuse to guess what an unknown one was supposed to mean.

    No default branch, the rule of ``nextcloud/credentials.py``: a value this code does not
    know must not quietly count as ``active``, because that is the one reading that hands
    out a token.
    """
    if value not in STATES:
        raise ValueError(f"unknown refresh token state {value!r}, expected one of {STATES}")
    return value


def _oidc_aad(table: str, field: str, row_key: str) -> str:
    """The AAD of an encrypted OIDC value: purpose (table and field) plus row key."""
    return f"oidc_{table}:{field}:{row_key}"


def _moment(now: int | None) -> int:
    """Whole seconds, and a parameter so a test can place a row in the past."""
    return int(time.time()) if now is None else int(now)

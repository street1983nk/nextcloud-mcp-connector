"""A wrong data key is refused when the store opens (standalone OAuth, slice 4).

The check lives in ``store_meta``, a table only a deployment that asks for the check creates.
The ExApp opener does not ask, so an ExApp store keeps its documented tables and behaviour.
"""

import asyncio
import os
import sqlite3
from pathlib import Path

import pytest

from mcp_connector.oauth import crypto, store

KEY = bytes(range(32))
OTHER_KEY = bytes(range(32, 64))
CLIENT_ID = "client-4711"
UNUSED_CLIENT = "client-never-used"

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions and links")


def file_of(tmp_path: Path) -> Path:
    return tmp_path / store.STORE_FILENAME


def tables(tmp_path: Path) -> set[str]:
    conn = sqlite3.connect(file_of(tmp_path))
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def recorded_check(tmp_path: Path) -> str | None:
    conn = sqlite3.connect(file_of(tmp_path))
    try:
        row = conn.execute(
            "SELECT value FROM store_meta WHERE name = ?", (store.KEY_CHECK_NAME,)
        ).fetchone()
    finally:
        conn.close()
    return None if row is None else row[0]


async def legacy_store(tmp_path: Path, key: bytes, *, connections: int = 1) -> None:
    """A store file written without any key check, like every file before this slice."""
    subject = store.OAuthStore(file_of(tmp_path), key)
    await subject.save_client(CLIENT_ID, metadata_json='{"client_id": "client-4711"}')
    await subject.save_client(UNUSED_CLIENT, metadata_json="{}", now=1)
    for index in range(connections):
        await subject.create_authorization(
            f"auth-{index}",
            client_id=CLIENT_ID,
            nc_user="alice",
            nc_account_id="alice",
            app_password=f"app-password-{index}",
            scopes="nextcloud",
            resource="https://mcp.example.com/mcp",
        )
    file_of(tmp_path).chmod(0o600)


def opener(tmp_path: Path, key: bytes) -> store.StoreProvider:
    async def provide() -> bytes:
        return key

    return store.explicit_store_opener(directory=lambda: tmp_path, key=provide)


def test_the_check_value_identifies_a_key_without_revealing_it() -> None:
    assert crypto.key_check(KEY) == crypto.key_check(KEY)
    assert crypto.key_check(KEY) != crypto.key_check(OTHER_KEY)
    assert KEY.hex() not in crypto.key_check(KEY)
    assert crypto.key_check(KEY) != crypto.form_token(KEY, "", purpose="x", now=0)


@pytest.mark.anyio
async def test_a_new_store_records_the_check_and_accepts_its_key_again(tmp_path: Path) -> None:
    await opener(tmp_path, KEY)()
    assert recorded_check(tmp_path) == crypto.key_check(KEY)

    reopened = await opener(tmp_path, KEY)()
    assert reopened.path == file_of(tmp_path)


@pytest.mark.anyio
async def test_a_recorded_store_refuses_another_key_before_anything_else(tmp_path: Path) -> None:
    await opener(tmp_path, KEY)()
    writer = store.OAuthStore(file_of(tmp_path), KEY)
    await writer.save_client(UNUSED_CLIENT, metadata_json="{}", now=1)

    wrong = opener(tmp_path, OTHER_KEY)
    with pytest.raises(store.StoreKeyMismatch) as raised:
        await wrong()

    assert KEY.hex() not in str(raised.value)
    assert OTHER_KEY.hex() not in str(raised.value)
    assert recorded_check(tmp_path) == crypto.key_check(KEY), "the check is never replaced"
    assert await writer.load_client(UNUSED_CLIENT) is not None, "no sweep ran with the wrong key"
    with pytest.raises(store.StoreKeyMismatch):
        await wrong()


@pytest.mark.anyio
async def test_an_older_store_adopts_the_key_that_reads_it(tmp_path: Path) -> None:
    await legacy_store(tmp_path, KEY)
    assert "store_meta" not in tables(tmp_path)

    opened = await opener(tmp_path, KEY)()

    assert recorded_check(tmp_path) == crypto.key_check(KEY)
    assert await opened.app_password("auth-0") == "app-password-0"


@pytest.mark.anyio
async def test_an_older_store_refuses_a_key_that_reads_none_of_its_rows(tmp_path: Path) -> None:
    await legacy_store(tmp_path, KEY, connections=3)

    with pytest.raises(store.StoreKeyMismatch):
        await opener(tmp_path, OTHER_KEY)()

    assert recorded_check(tmp_path) is None, "a wrong key is never recorded"
    assert (await opener(tmp_path, KEY)()).path == file_of(tmp_path)


@pytest.mark.anyio
async def test_one_damaged_row_does_not_refuse_the_right_key(tmp_path: Path) -> None:
    await legacy_store(tmp_path, KEY, connections=2)
    conn = sqlite3.connect(file_of(tmp_path))
    try:
        conn.execute(
            "UPDATE authorizations SET app_password_enc = ? WHERE auth_id = 'auth-0'",
            (b"\x00" * 40,),
        )
        conn.commit()
    finally:
        conn.close()

    await opener(tmp_path, KEY)()

    assert recorded_check(tmp_path) == crypto.key_check(KEY)


@pytest.mark.anyio
async def test_an_empty_older_store_adopts_the_first_key(tmp_path: Path) -> None:
    """Nothing to protect yet, so nothing to compare against: the documented first use."""
    subject = store.OAuthStore(file_of(tmp_path), KEY)
    await subject.save_client(CLIENT_ID, metadata_json="{}")
    file_of(tmp_path).chmod(0o600)

    await opener(tmp_path, OTHER_KEY)()

    assert recorded_check(tmp_path) == crypto.key_check(OTHER_KEY)


@pytest.mark.anyio
async def test_two_workers_with_different_keys_cannot_both_open_a_new_store(
    tmp_path: Path,
) -> None:
    results = await asyncio.gather(
        opener(tmp_path, KEY)(), opener(tmp_path, OTHER_KEY)(), return_exceptions=True
    )

    refused = [result for result in results if isinstance(result, store.StoreKeyMismatch)]
    opened = [result for result in results if isinstance(result, store.OAuthStore)]
    assert len(refused) == 1, results
    assert len(opened) == 1, results


@pytest.mark.anyio
async def test_two_workers_opening_a_new_store_never_see_a_lock_error(tmp_path: Path) -> None:
    """Both switch the new file to WAL at once; SQLite does not wait there on its own.

    Before the retry this failed in roughly a third of the rounds with "database is locked".
    """
    for index in range(30):
        directory = tmp_path / f"round-{index}"
        directory.mkdir(mode=0o700)
        results = await asyncio.gather(
            opener(directory, KEY)(), opener(directory, KEY)(), return_exceptions=True
        )
        assert all(isinstance(result, store.OAuthStore) for result in results), results


def test_the_wal_switch_waits_for_a_lock_and_then_gives_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Busy:
        def __init__(self, failures: int) -> None:
            self.failures = failures
            self.calls = 0

        def execute(self, sql: str) -> None:
            self.calls += 1
            if self.calls <= self.failures:
                raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "_WAL_RETRY_SECONDS", 0)
    patient = Busy(failures=3)
    store._enable_wal(patient)  # type: ignore[arg-type]
    assert patient.calls == 4

    monkeypatch.setattr(store, "_BUSY_TIMEOUT_SECONDS", 0)
    with pytest.raises(sqlite3.OperationalError):
        store._enable_wal(Busy(failures=10**6))  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_the_exapp_opener_does_not_check_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unchanged ExApp behaviour: no check table, and a replaced key still opens."""
    await legacy_store(tmp_path, KEY)

    async def data_key(env: object = None) -> bytes:
        return OTHER_KEY

    monkeypatch.setattr(store.crypto, "data_key", data_key)
    monkeypatch.setattr(store.config, "persistent_storage", lambda env=None: tmp_path)

    await store.store_opener({})()

    assert "store_meta" not in tables(tmp_path)


@pytest.mark.anyio
async def test_the_wipe_takes_the_check_with_it(tmp_path: Path) -> None:
    """The purge deletes the key next; a surviving check would refuse the next start."""
    opened = await opener(tmp_path, KEY)()
    await opened.wipe_all()

    assert recorded_check(tmp_path) is None
    await opener(tmp_path, OTHER_KEY)()
    assert recorded_check(tmp_path) == crypto.key_check(OTHER_KEY)


@pytest.mark.anyio
async def test_two_workers_on_an_older_store_only_admit_the_key_that_reads_it(
    tmp_path: Path,
) -> None:
    await legacy_store(tmp_path, KEY, connections=2)

    results = await asyncio.gather(
        opener(tmp_path, OTHER_KEY)(), opener(tmp_path, KEY)(), return_exceptions=True
    )

    assert isinstance(results[0], store.StoreKeyMismatch)
    assert isinstance(results[1], store.OAuthStore)
    assert recorded_check(tmp_path) == crypto.key_check(KEY)


# --- the store file itself -----------------------------------------------------------------


@posix_only
@pytest.mark.anyio
async def test_a_new_store_file_is_private(tmp_path: Path) -> None:
    await opener(tmp_path, KEY)()

    mode = file_of(tmp_path).stat().st_mode
    assert mode & 0o077 == 0, oct(mode)


@posix_only
@pytest.mark.anyio
async def test_an_existing_store_file_readable_by_others_is_refused(tmp_path: Path) -> None:
    await legacy_store(tmp_path, KEY)
    file_of(tmp_path).chmod(0o644)

    with pytest.raises(store.StoreFileRefused):
        await opener(tmp_path, KEY)()

    assert "store_meta" not in tables(tmp_path), "nothing was written before the refusal"


@posix_only
@pytest.mark.anyio
async def test_a_link_in_place_of_the_store_file_is_refused(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = elsewhere / "victim.sqlite3"
    target.write_bytes(b"")
    target.chmod(0o600)
    file_of(tmp_path).symlink_to(target)

    with pytest.raises(store.StoreFileRefused):
        await opener(tmp_path, KEY)()

    assert target.read_bytes() == b"", "the link target was not turned into a store"


@posix_only
@pytest.mark.anyio
async def test_the_exapp_opener_keeps_its_file_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unchanged ExApp behaviour: an existing store readable by others still opens."""
    await legacy_store(tmp_path, KEY)
    file_of(tmp_path).chmod(0o644)

    async def data_key(env: object = None) -> bytes:
        return KEY

    monkeypatch.setattr(store.crypto, "data_key", data_key)
    monkeypatch.setattr(store.config, "persistent_storage", lambda env=None: tmp_path)

    await store.store_opener({})()

    assert file_of(tmp_path).stat().st_mode & 0o777 == 0o644

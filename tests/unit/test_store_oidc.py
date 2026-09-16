"""The two standalone OIDC tables: sign ins in progress and the browser proofs they leave.

Real SQLite files, no network. The rules under test are the ones the maintainer set for the
data model: a named five-minute lifetime capped by the flow, hard expiry on every read,
single use under ``BEGIN IMMEDIATE``, digests for every handle, AES-GCM with an AAD of
purpose and row for recoverable values, a per-browser cap, cleanup through the flow, and no
new tables in an ExApp store.
"""

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_connector.oauth import store

KEY = bytes(range(32))
CLIENT_ID = "client-4711"
FLOW_ID = "flow-0001"
OTHER_FLOW = "flow-0002"
NOW = 1_000_000

STATE = "state-value-of-the-sign-in"
BROWSER = "browser-handle-of-the-sign-in"
NONCE = "nonce-value-of-the-sign-in"
VERIFIER = "pkce-verifier-of-the-sign-in-0123456789abcdef"
PROOF = "proof-handle-after-the-callback"
PRINCIPAL = "a1b2c3"


def file_of(tmp_path: Path) -> Path:
    return tmp_path / store.STORE_FILENAME


def oidc_store(tmp_path: Path) -> store.OAuthStore:
    return store.OAuthStore(file_of(tmp_path), KEY, oidc=True)


async def with_flow(
    subject: store.OAuthStore,
    flow_id: str = FLOW_ID,
    *,
    account_id: str | None = PRINCIPAL,
    flow_expires_in: int = store.FLOW_TTL,
) -> None:
    """A running flow whose sign in finished: flow row plus authorization row."""
    await subject.save_client(CLIENT_ID, metadata_json="{}", now=NOW)
    await subject.create_flow(
        flow_id,
        client_id=CLIENT_ID,
        redirect_uri="https://client.example/callback",
        redirect_uri_explicit=True,
        code_challenge="challenge",
        state=None,
        scopes="nextcloud",
        resource="https://mcp.example/mcp",
        poll_token="poll-token",
        now=NOW - store.FLOW_TTL + flow_expires_in,
    )
    if account_id is not None:
        await subject.create_authorization(
            flow_id,
            client_id=CLIENT_ID,
            nc_user="alice",
            nc_account_id=account_id,
            app_password="app-password",
            scopes="nextcloud",
            resource="https://mcp.example/mcp",
            now=NOW,
        )


async def begin(subject: store.OAuthStore, **overrides: object) -> bool:
    values: dict[str, object] = {
        "state": STATE,
        "flow_id": FLOW_ID,
        "browser_handle": BROWSER,
        "nonce": NONCE,
        "code_verifier": VERIFIER,
        "now": NOW,
    }
    values.update(overrides)
    return await subject.create_oidc_transaction(**values)  # type: ignore[arg-type]


def query(tmp_path: Path, sql: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(file_of(tmp_path))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def execute(tmp_path: Path, sql: str, params: tuple = ()) -> None:
    conn = sqlite3.connect(file_of(tmp_path))
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def stored_bytes(directory: Path) -> bytes:
    """Every byte the store wrote, the write ahead log included."""
    return b"".join(path.read_bytes() for path in directory.iterdir() if path.is_file())


def make_private(directory: Path) -> None:
    directory.chmod(0o700)


def tables(tmp_path: Path) -> set[str]:
    return {row[0] for row in query(tmp_path, "SELECT name FROM sqlite_master WHERE type='table'")}


# --- transactions -----------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_sign_in_is_redeemed_once_by_its_browser(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)

    found = await subject.redeem_oidc_transaction(state=STATE, browser_handle=BROWSER, now=NOW)

    assert found is not None
    assert (found.flow_id, found.nonce, found.code_verifier) == (FLOW_ID, NONCE, VERIFIER)
    assert NONCE not in repr(found)
    assert VERIFIER not in repr(found)
    again = await subject.redeem_oidc_transaction(state=STATE, browser_handle=BROWSER, now=NOW)
    assert again is None


@pytest.mark.anyio
async def test_a_wrong_browser_ends_the_sign_in_for_everybody(tmp_path: Path) -> None:
    """H2: a known state with a wrong binding terminates; the right browser cannot follow."""
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)

    wrong = await subject.redeem_oidc_transaction(state=STATE, browser_handle="other", now=NOW)
    right = await subject.redeem_oidc_transaction(state=STATE, browser_handle=BROWSER, now=NOW)

    assert wrong is None
    assert right is None


@pytest.mark.anyio
async def test_an_unknown_state_and_a_wrong_browser_look_the_same(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)

    unknown = await subject.redeem_oidc_transaction(state="nope", browser_handle=BROWSER, now=NOW)
    wrong = await subject.redeem_oidc_transaction(state=STATE, browser_handle="other", now=NOW)

    assert unknown is None
    assert wrong is None


@pytest.mark.anyio
async def test_the_lifetime_is_five_minutes_and_checked_on_every_read(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    (expires_at,) = query(tmp_path, "SELECT expires_at FROM oidc_transactions")[0]
    assert expires_at == NOW + store.OIDC_TTL

    late = await subject.redeem_oidc_transaction(
        state=STATE, browser_handle=BROWSER, now=NOW + store.OIDC_TTL
    )

    assert late is None, "a row that was never purged is still expired"


@pytest.mark.anyio
async def test_the_lifetime_never_outlives_the_flow(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject, flow_expires_in=60)
    assert await begin(subject)

    (expires_at,) = query(tmp_path, "SELECT expires_at FROM oidc_transactions")[0]
    assert expires_at == NOW + 60


@pytest.mark.anyio
@pytest.mark.parametrize("case", ["no flow", "no authorization", "revoked", "expired flow"])
async def test_a_sign_in_needs_a_live_flow_with_a_resolved_account(
    tmp_path: Path, case: str
) -> None:
    subject = oidc_store(tmp_path)
    if case == "no authorization":
        await with_flow(subject, account_id=None)
    elif case != "no flow":
        await with_flow(subject)
    if case == "revoked":
        await subject.revoke_authorization(FLOW_ID, now=NOW)
    if case == "expired flow":
        execute(tmp_path, "UPDATE flows SET expires_at = ?", (NOW,))

    assert await begin(subject) is False
    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_transactions")[0][0] == 0


@pytest.mark.anyio
async def test_a_legacy_authorization_without_account_id_cannot_start(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    execute(tmp_path, "UPDATE authorizations SET nc_account_id = NULL")

    assert await begin(subject) is False


@pytest.mark.anyio
async def test_one_browser_gets_a_small_number_of_open_sign_ins(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    for index in range(store.OIDC_TRANSACTIONS_PER_BROWSER):
        assert await begin(subject, state=f"state-{index}")

    assert await begin(subject, state="one-too-many") is False
    assert await begin(subject, state="another-browser", browser_handle="other")
    # Expired rows no longer count.
    assert await begin(subject, state="later", now=NOW + store.OIDC_TTL)


@pytest.mark.anyio
async def test_parallel_starts_respect_the_browser_cap(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)

    results = await asyncio.gather(
        *(
            oidc_store(tmp_path).create_oidc_transaction(
                state=f"{STATE}-{index}",
                flow_id=FLOW_ID,
                browser_handle=BROWSER,
                nonce=NONCE,
                code_verifier=VERIFIER,
                now=NOW,
            )
            for index in range(store.OIDC_TRANSACTIONS_PER_BROWSER + 3)
        )
    )

    assert results.count(True) == store.OIDC_TRANSACTIONS_PER_BROWSER


@pytest.mark.anyio
async def test_parallel_redemptions_have_exactly_one_winner(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)

    results = await asyncio.gather(
        *(
            oidc_store(tmp_path).redeem_oidc_transaction(
                state=STATE, browser_handle=BROWSER, now=NOW
            )
            for _ in range(6)
        )
    )

    assert sum(result is not None for result in results) == 1


@pytest.mark.anyio
async def test_a_restart_keeps_the_sign_in(tmp_path: Path) -> None:
    await with_flow(oidc_store(tmp_path))
    assert await begin(oidc_store(tmp_path))

    found = await oidc_store(tmp_path).redeem_oidc_transaction(
        state=STATE, browser_handle=BROWSER, now=NOW
    )

    assert found is not None
    assert found.nonce == NONCE


def flip_one_byte(tmp_path: Path) -> None:
    (blob,) = query(tmp_path, "SELECT nonce_enc FROM oidc_transactions")[0]
    changed = bytearray(blob)
    changed[20] ^= 0x01
    execute(tmp_path, "UPDATE oidc_transactions SET nonce_enc = ?", (bytes(changed),))


def swap_fields(tmp_path: Path) -> None:
    execute(
        tmp_path,
        "UPDATE oidc_transactions SET nonce_enc = verifier_enc, verifier_enc = nonce_enc",
    )


def text_instead_of_bytes(tmp_path: Path) -> None:
    execute(tmp_path, "UPDATE oidc_transactions SET nonce_enc = 'not a ciphertext'")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tamper",
    [flip_one_byte, swap_fields, text_instead_of_bytes],
    ids=["flipped byte", "field swap", "text value"],
)
async def test_a_manipulated_ciphertext_is_refused(
    tmp_path: Path, tamper: Callable[[Path], None]
) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    tamper(tmp_path)

    found = await subject.redeem_oidc_transaction(state=STATE, browser_handle=BROWSER, now=NOW)
    assert found is None


@pytest.mark.anyio
async def test_a_ciphertext_whose_plaintext_is_not_utf8_is_refused(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    state_hash = store.token_hash(STATE)
    bad = store.encrypt(KEY, b"\xff\xfe", aad=store._oidc_aad("transactions", "nonce", state_hash))
    execute(tmp_path, "UPDATE oidc_transactions SET nonce_enc = ?", (bad,))

    found = await subject.redeem_oidc_transaction(state=STATE, browser_handle=BROWSER, now=NOW)

    assert found is None
    assert query(tmp_path, "SELECT 1 FROM oidc_transactions") == []


@pytest.mark.anyio
async def test_a_ciphertext_moved_to_another_row_is_refused(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject, state="first")
    assert await begin(subject, state="second")
    execute(
        tmp_path,
        "UPDATE oidc_transactions SET nonce_enc = "
        "(SELECT nonce_enc FROM oidc_transactions WHERE state_hash = ?), "
        "verifier_enc = (SELECT verifier_enc FROM oidc_transactions WHERE state_hash = ?) "
        "WHERE state_hash = ?",
        (store.token_hash("first"), store.token_hash("first"), store.token_hash("second")),
    )

    moved = await subject.redeem_oidc_transaction(state="second", browser_handle=BROWSER, now=NOW)
    assert moved is None


@pytest.mark.anyio
async def test_no_handle_or_secret_is_stored_in_the_clear(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    assert await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    raw = stored_bytes(tmp_path)
    for secret in (STATE, BROWSER, NONCE, VERIFIER, PROOF):
        assert secret.encode() not in raw, secret


# --- browser proofs ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_proof_names_its_principal_and_is_consumed_once(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    peeked = await subject.browser_proof_principal(proof_handle=PROOF, flow_id=FLOW_ID, now=NOW)
    first = await subject.redeem_browser_proof(proof_handle=PROOF, flow_id=FLOW_ID, now=NOW)
    second = await subject.redeem_browser_proof(proof_handle=PROOF, flow_id=FLOW_ID, now=NOW)

    assert (peeked, first, second) == (PRINCIPAL, PRINCIPAL, None)


@pytest.mark.anyio
async def test_a_new_proof_invalidates_the_old_handle(tmp_path: Path) -> None:
    """H1: the handle is rotated after the callback; the old one is worth nothing."""
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    await subject.create_browser_proof(
        proof_handle="old", flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )
    await subject.create_browser_proof(
        proof_handle="new", flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    assert await subject.redeem_browser_proof(proof_handle="old", flow_id=FLOW_ID, now=NOW) is None
    assert (
        await subject.redeem_browser_proof(proof_handle="new", flow_id=FLOW_ID, now=NOW)
        == PRINCIPAL
    )


@pytest.mark.anyio
async def test_a_proof_is_bound_to_its_flow_and_expires(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    await with_flow(subject, OTHER_FLOW)
    await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    assert (
        await subject.browser_proof_principal(proof_handle=PROOF, flow_id=OTHER_FLOW, now=NOW)
        is None
    )
    assert (
        await subject.browser_proof_principal(
            proof_handle=PROOF, flow_id=FLOW_ID, now=NOW + store.OIDC_TTL
        )
        is None
    )


@pytest.mark.anyio
async def test_a_proof_needs_a_live_flow_and_a_principal(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    assert not await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )
    await with_flow(subject)
    with pytest.raises(ValueError, match="principal"):
        await subject.create_browser_proof(
            proof_handle=PROOF, flow_id=FLOW_ID, principal=" ", now=NOW
        )


@pytest.mark.anyio
async def test_callback_and_decision_racing_for_one_proof_have_one_winner(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    results = await asyncio.gather(
        *(
            oidc_store(tmp_path).redeem_browser_proof(proof_handle=PROOF, flow_id=FLOW_ID, now=NOW)
            for _ in range(6)
        )
    )

    assert results.count(PRINCIPAL) == 1


# --- cleanup ----------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ending_the_flow_takes_both_rows_along(tmp_path: Path) -> None:
    """Completion, denial, withdrawal and sweeps all end in a deleted flow."""
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    await subject.delete_flow(FLOW_ID)

    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_transactions")[0][0] == 0
    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_proofs")[0][0] == 0


@pytest.mark.anyio
async def test_removing_the_client_takes_both_rows_along(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    await subject.delete_client(CLIENT_ID)

    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_transactions")[0][0] == 0
    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_proofs")[0][0] == 0


@pytest.mark.anyio
async def test_the_sweep_removes_what_ran_out(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    await subject.purge_expired(now=NOW + store.OIDC_TTL)

    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_transactions")[0][0] == 0
    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_proofs")[0][0] == 0


@pytest.mark.anyio
async def test_the_wipe_empties_both_tables(tmp_path: Path) -> None:
    subject = oidc_store(tmp_path)
    await with_flow(subject)
    assert await begin(subject)
    await subject.create_browser_proof(
        proof_handle=PROOF, flow_id=FLOW_ID, principal=PRINCIPAL, now=NOW
    )

    await subject.wipe_all()

    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_transactions")[0][0] == 0
    assert query(tmp_path, "SELECT COUNT(*) FROM oidc_proofs")[0][0] == 0


# --- the ExApp store stays as it is ------------------------------------------------------


@pytest.mark.anyio
async def test_an_exapp_store_has_no_oidc_tables_and_no_oidc_methods(tmp_path: Path) -> None:
    subject = store.OAuthStore(file_of(tmp_path), KEY)
    await with_flow(subject)
    await subject.purge_expired(now=NOW)
    await subject.wipe_all()

    assert not {"oidc_transactions", "oidc_proofs"} & tables(tmp_path)
    with pytest.raises(RuntimeError):
        await begin(subject)
    with pytest.raises(RuntimeError):
        await subject.redeem_browser_proof(proof_handle=PROOF, flow_id=FLOW_ID, now=NOW)


@pytest.mark.anyio
async def test_the_strict_opener_creates_the_tables(tmp_path: Path) -> None:
    make_private(tmp_path)

    async def key() -> bytes:
        return KEY

    opened = await store.explicit_store_opener(directory=lambda: tmp_path, key=key)()
    await opened.purge_expired(now=NOW)

    assert {"oidc_transactions", "oidc_proofs"} <= tables(tmp_path)

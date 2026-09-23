"""The account source of the standalone mode (CRED-02, plan 23-04): a binding, read only.

``BoundAccounts`` answers the one question the two operating modes differ in, and it does
so against a real SQLite store in ``tmp_path``, so the decryption of the app password runs
for real in every test. The contract under test is the contract of the seam
(``oauth/exchange_accounts.py``): ``None`` always means "this account does not act here"
without saying why, nothing here ever writes, and the read happens per request so a
revocation is seen by the very next call. The row counter before and after every refusal is
part of the tests, because "writes nothing" has to be a measurement and not a sentence
(T-23-18).
"""

import logging
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from mcp_connector.oauth import exchange_binding
from mcp_connector.oauth.exchange_accounts import EXCHANGE_CLIENT_ID, ExchangeAccounts
from mcp_connector.oauth.store import AuthorizationRow, OAuthStore
from mcp_connector.oauth.verifier import CREDENTIAL_APP_PASSWORD

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

#: The mapped principal an exchange token acts as, and the login name of its binding. Two
#: different values on purpose: a test that used one for both could pass for the wrong
#: reason (an LDAP account is exactly the case where they differ).
MAPPED = "f13-account-7"
LOGIN = "alice-login"

BOUND_PASSWORD = "the-bound-app-password-xyz"
AZP = "f13-orchestrator"

STORE_FILE = "oauth.sqlite3"


def open_store(tmp_path: Path) -> OAuthStore:
    return OAuthStore(tmp_path / STORE_FILE, KEY)


def opener_of(subject: OAuthStore):
    async def opener() -> OAuthStore:
        return subject

    return opener


def exploding_opener():
    async def opener() -> OAuthStore:
        raise AssertionError("the store was opened although nothing may be read")

    return opener


async def with_binding(
    subject: OAuthStore,
    *,
    auth_id: str = "binding-1",
    client_id: str = EXCHANGE_CLIENT_ID,
    login: str = LOGIN,
    account: str = MAPPED,
    password: str = BOUND_PASSWORD,
    moment: int = 1_000,
) -> None:
    """One living authorization under the reserved client: the row plan 23-05 will write."""
    await subject.save_client(client_id, metadata_json='{"client_id": "reserved"}', allowed=False)
    await subject.create_authorization(
        auth_id,
        client_id=client_id,
        nc_user=login,
        nc_account_id=account,
        app_password=password,
        scopes="nextcloud",
        resource="https://mcp.example.org/mcp",
        now=moment,
    )


def checked_claims(**overrides: Any) -> dict[str, Any]:
    """The checked claim set of an exchanged token, as the chain hands it over."""
    values: dict[str, Any] = {
        "iss": "https://idp.example.org/realms/f13",
        "sub": MAPPED,
        "azp": AZP,
    }
    values.update(overrides)
    return values


def authorization_rows(tmp_path: Path) -> int:
    """The row count of ``authorizations``, read out of the file behind the store's back."""
    conn = sqlite3.connect(tmp_path / STORE_FILE)
    try:
        return conn.execute("SELECT COUNT(*) FROM authorizations").fetchone()[0]
    finally:
        conn.close()


def corrupt_password_blob(tmp_path: Path, auth_id: str) -> None:
    """Damage the ciphertext of one row, which is what a changed data key looks like."""
    conn = sqlite3.connect(tmp_path / STORE_FILE)
    try:
        conn.execute(
            "UPDATE authorizations SET app_password_enc = ? WHERE auth_id = ?",
            (b"not-a-ciphertext", auth_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- the protocol and the happy path -------------------------------------------------------


def test_bound_accounts_satisfies_the_account_source_protocol(tmp_path: Path) -> None:
    """The one interface the chain asks; both operating modes have to fit it."""
    source = exchange_binding.BoundAccounts(opener_of(open_store(tmp_path)))
    assert isinstance(source, ExchangeAccounts)


@pytest.mark.anyio
async def test_a_bound_account_becomes_the_identity_of_its_authorization(tmp_path: Path) -> None:
    """The binding is an authorization like any other, and the identity is built from it."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    source = exchange_binding.BoundAccounts(opener_of(subject))
    claims = checked_claims()

    identity = await source.identity_for(MAPPED, claims)

    assert identity is not None
    assert identity.principal == MAPPED
    assert identity.nc_user == LOGIN
    assert identity.app_password == BOUND_PASSWORD
    assert identity.auth_id == "binding-1"
    assert identity.client_id == EXCHANGE_CLIENT_ID
    assert identity.client_name == AZP
    assert identity.credential == CREDENTIAL_APP_PASSWORD
    assert identity.revoked is False


@pytest.mark.anyio
async def test_the_acting_party_is_read_from_the_claims_and_may_be_empty(tmp_path: Path) -> None:
    """No ``azp`` names nobody; the identity still stands, the audit line stays honest."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    source = exchange_binding.BoundAccounts(opener_of(subject))

    identity = await source.identity_for(MAPPED, {"sub": MAPPED})

    assert identity is not None
    assert identity.client_name == ""


# --- every other state is one silent refusal, and none of them writes ----------------------


@pytest.mark.anyio
async def test_without_a_binding_the_answer_is_none_and_nothing_is_written(
    tmp_path: Path,
) -> None:
    """No silent provisioning: a refusal leaves exactly the rows that were there before."""
    subject = open_store(tmp_path)
    await with_binding(subject, account="somebody-else", login="somebody-else")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    assert await source.identity_for(MAPPED, checked_claims()) is None
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_a_revoked_binding_is_a_refusal_that_writes_nothing(tmp_path: Path) -> None:
    """The read already skips a revoked row, and the refusal leaves the store untouched."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    await subject.revoke_authorization("binding-1")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    assert await source.identity_for(MAPPED, checked_claims()) is None
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_a_revocation_is_seen_by_the_very_next_call(tmp_path: Path) -> None:
    """Per request and without a cache: the widerruf of plan 23-06 acts at once."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    source = exchange_binding.BoundAccounts(opener_of(subject))
    assert await source.identity_for(MAPPED, checked_claims()) is not None

    await subject.revoke_authorization("binding-1")

    assert await source.identity_for(MAPPED, checked_claims()) is None


@pytest.mark.anyio
async def test_a_binding_of_another_client_is_a_refusal(tmp_path: Path) -> None:
    """A connection of a registered client is never the binding of the exchange path."""
    subject = open_store(tmp_path)
    await with_binding(subject, client_id="client-4711")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    assert await source.identity_for(MAPPED, checked_claims()) is None
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_an_unreadable_app_password_is_a_refusal_and_one_line_naming_the_type(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T-23-19: the line carries the exception type and never a principal, id or password."""
    subject = open_store(tmp_path)
    await with_binding(subject)
    corrupt_password_blob(tmp_path, "binding-1")
    source = exchange_binding.BoundAccounts(opener_of(subject))
    before = authorization_rows(tmp_path)

    with caplog.at_level(logging.ERROR, logger="mcp_connector.oauth.exchange_binding"):
        assert await source.identity_for(MAPPED, checked_claims()) is None

    lines = [entry.getMessage() for entry in caplog.records]
    assert len(lines) == 1
    assert "DecryptionRejected" in lines[0]
    assert MAPPED not in lines[0]
    assert "binding-1" not in lines[0]
    assert BOUND_PASSWORD not in lines[0]
    assert authorization_rows(tmp_path) == before


@pytest.mark.anyio
async def test_an_empty_stored_password_is_a_refusal(tmp_path: Path) -> None:
    """Empty is refused by its own check: it could also be a broken read, so it never acts."""
    subject = open_store(tmp_path)
    await with_binding(subject, password="")
    source = exchange_binding.BoundAccounts(opener_of(subject))

    assert await source.identity_for(MAPPED, checked_claims()) is None


@pytest.mark.anyio
async def test_a_store_that_cannot_be_opened_is_a_refusal_not_an_exception() -> None:
    """Fail closed without a 500: an unreadable store refuses this one call and nothing more."""

    async def broken_opener() -> OAuthStore:
        raise OSError("the volume is gone")

    source = exchange_binding.BoundAccounts(broken_opener)

    assert await source.identity_for(MAPPED, checked_claims()) is None


@pytest.mark.anyio
async def test_an_empty_principal_never_touches_the_store() -> None:
    """The app context owns nothing here, and the refusal costs no store call at all."""
    source = exchange_binding.BoundAccounts(exploding_opener())

    assert await source.identity_for("", checked_claims()) is None


@pytest.mark.anyio
async def test_a_row_of_another_principal_is_refused_by_the_ownership_check() -> None:
    """Belt and braces (T-23-16): the decision holds its own comparison, not only the query."""

    class WrongRowStore:
        """A store whose read answers with somebody else's row: the query filter is bypassed."""

        async def binding_of(self, principal: str, client_id: str) -> AuthorizationRow | None:
            del principal, client_id
            return AuthorizationRow(
                auth_id="binding-of-somebody-else",
                client_id=EXCHANGE_CLIENT_ID,
                nc_user="somebody-else",
                scopes="nextcloud",
                resource="https://mcp.example.org/mcp",
                created_at=1_000,
                revoked_at=None,
                nc_account_id="somebody-else",
            )

        async def app_password(self, auth_id: str) -> str | None:
            del auth_id
            return "a-password-that-may-never-act"

    async def opener() -> Any:
        return WrongRowStore()

    source = exchange_binding.BoundAccounts(opener)

    assert await source.identity_for(MAPPED, checked_claims()) is None


# --- what this module is forbidden to do, held as structure --------------------------------


def test_the_module_never_writes_and_never_logs_a_value() -> None:
    """The source is a read and a refusal, nothing else; the greps of the plan, held here."""
    import inspect

    src = inspect.getsource(exchange_binding)
    meaningful = [line for line in src.splitlines() if not line.lstrip().startswith("#")]
    body = "\n".join(meaningful)
    assert "create_authorization" not in body
    assert "INSERT" not in body
    assert "_write" not in body
    assert body.count("return None") >= 4
    assert "same_principal" in body
    assert "type(exc).__name__" in body


def test_the_claims_parameter_takes_any_mapping(tmp_path: Path) -> None:
    """The contract of the seam: the claim set rides along as a mapping, never a dict only."""
    import inspect

    signature = inspect.signature(exchange_binding.BoundAccounts.identity_for)
    annotation = signature.parameters["claims"].annotation
    assert annotation in (Mapping[str, Any], "Mapping[str, Any]")

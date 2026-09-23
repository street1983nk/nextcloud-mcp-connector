"""How a binding comes to exist (CRED-02, plan 23-05): three steps, two reserved clients.

The mechanics are functions without a route, so every outcome is measured directly: a real
SQLite store in ``tmp_path`` (the encryption of the app password runs for real), and stand
ins for ``loginflow`` that record every credential this module hands back to Nextcloud. The
two properties everything here exists for: a holding row can do nothing, because
``binding_of`` filters on the other reserved client, and no way out of an enrollment leaves
a Nextcloud credential behind (pitfall 13, D-34).
"""

import sqlite3
from pathlib import Path

import pytest

from mcp_connector import config
from mcp_connector.nextcloud.target import NextcloudTarget
from mcp_connector.oauth import exchange_enroll, loginflow
from mcp_connector.oauth.exchange_accounts import EXCHANGE_CLIENT_ID
from mcp_connector.oauth.metadata import RESOURCE_SUFFIX, TOOL_SCOPE
from mcp_connector.oauth.store import OAuthStore

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

PUBLIC_URL = "https://mcp.example.com"
ENV = {config.ENV_PUBLIC_URL: PUBLIC_URL}
TARGET = NextcloudTarget.from_url("http://nc.test")

#: Login name and canonical account id differ on purpose (the LDAP case): a test that used
#: one value for both could go green for the wrong reason.
LOGIN = "alice-login"
ACCOUNT_ID = "acc-alice-7"
DISPLAY = "Alice Example"
PASSWORD = "fresh-app-password-xyz"
LOGIN_URL = "https://nc.test/login/v2/flow/abc"

STORE_FILE = "oauth.sqlite3"


def open_store(tmp_path: Path) -> OAuthStore:
    return OAuthStore(tmp_path / STORE_FILE, KEY)


def authorization_rows(tmp_path: Path) -> int:
    """The row count of ``authorizations``, read out of the file behind the store's back."""
    if not (tmp_path / STORE_FILE).exists():
        return 0
    conn = sqlite3.connect(tmp_path / STORE_FILE)
    try:
        return conn.execute("SELECT COUNT(*) FROM authorizations").fetchone()[0]
    finally:
        conn.close()


def flow_rows(tmp_path: Path) -> int:
    if not (tmp_path / STORE_FILE).exists():
        return 0
    conn = sqlite3.connect(tmp_path / STORE_FILE)
    try:
        return conn.execute("SELECT COUNT(*) FROM flows").fetchone()[0]
    finally:
        conn.close()


class LoginFlowStub:
    """The four loginflow answers of one test, plus what was handed back to Nextcloud."""

    def __init__(self) -> None:
        self.started: loginflow.FlowStart | None = loginflow.FlowStart(
            poll_token="poll-token-of-this-enrollment", login_url=LOGIN_URL
        )
        self.poll = loginflow.PollResult(
            outcome=loginflow.POLL_DONE,
            credentials=loginflow.AppCredentials(login_name=LOGIN, app_password=PASSWORD),
        )
        self.resolved: loginflow.Account | None = loginflow.Account(
            account_id=ACCOUNT_ID, display_name=DISPLAY
        )
        self.revoked: list[tuple[str, str]] = []


@pytest.fixture
def flows(monkeypatch: pytest.MonkeyPatch) -> LoginFlowStub:
    stub = LoginFlowStub()

    async def start_flow(client_name: str, *, target: NextcloudTarget):
        return stub.started

    async def poll_once(poll_token: str, *, target: NextcloudTarget):
        return stub.poll

    async def account(login_name: str, app_password: str, *, target: NextcloudTarget):
        return stub.resolved

    async def revoke_app_password(login_name: str, app_password: str, *, target: NextcloudTarget):
        stub.revoked.append((login_name, app_password))
        return True

    monkeypatch.setattr(loginflow, "start_flow", start_flow)
    monkeypatch.setattr(loginflow, "poll_once", poll_once)
    monkeypatch.setattr(loginflow, "account", account)
    monkeypatch.setattr(loginflow, "revoke_app_password", revoke_app_password)
    return stub


async def begun(store: OAuthStore, flows: LoginFlowStub) -> str:
    started = await exchange_enroll.begin_enrollment(store, nextcloud=TARGET)
    assert started.outcome == exchange_enroll.ENROLL_STARTED
    return started.flow_id


async def signed_in(store: OAuthStore, flows: LoginFlowStub) -> str:
    flow_id = await begun(store, flows)
    result = await exchange_enroll.complete_enrollment(store, flow_id, nextcloud=TARGET, env=ENV)
    assert result.outcome == exchange_enroll.ENROLL_SIGNED_IN
    return flow_id


# --- the two reserved clients ---------------------------------------------------------


def test_the_holding_client_is_reserved_and_not_the_binding_client() -> None:
    """The whole plan in one comparison: two identifiers, so 'signed in' is not 'confirmed'."""
    assert exchange_enroll.EXCHANGE_PENDING_CLIENT_ID != EXCHANGE_CLIENT_ID
    assert exchange_enroll.EXCHANGE_PENDING_CLIENT_ID.startswith("urn:mcp-connector:")


# --- begin_enrollment -----------------------------------------------------------------


@pytest.mark.anyio
async def test_begin_opens_a_flow_under_the_holding_client(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)

    started = await exchange_enroll.begin_enrollment(subject, nextcloud=TARGET)

    assert started.outcome == exchange_enroll.ENROLL_STARTED
    assert started.login_url == LOGIN_URL
    row = await subject.load_flow(started.flow_id)
    assert row is not None
    assert row.client_id == exchange_enroll.EXCHANGE_PENDING_CLIENT_ID
    client = await subject.load_client(exchange_enroll.EXCHANGE_PENDING_CLIENT_ID)
    assert client is not None
    assert client.allowed is False


@pytest.mark.anyio
async def test_begin_with_a_login_flow_that_does_not_open_writes_nothing(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flows.started = None

    started = await exchange_enroll.begin_enrollment(subject, nextcloud=TARGET)

    assert started.outcome == exchange_enroll.ENROLL_FAILED
    assert started.flow_id == ""
    assert flow_rows(tmp_path) == 0


# --- complete_enrollment --------------------------------------------------------------


@pytest.mark.anyio
async def test_a_running_sign_in_is_not_finished_and_writes_nothing(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)
    flows.poll = loginflow.PollResult(outcome=loginflow.POLL_PENDING)

    result = await exchange_enroll.complete_enrollment(subject, flow_id, nextcloud=TARGET, env=ENV)

    assert result.outcome == exchange_enroll.ENROLL_PENDING
    assert authorization_rows(tmp_path) == 0
    assert flows.revoked == []
    # The flow stays: a waiting page asks again.
    assert await subject.load_flow(flow_id) is not None


@pytest.mark.anyio
async def test_an_unknown_and_an_expired_flow_are_their_own_outcome(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)

    unknown = await exchange_enroll.complete_enrollment(
        subject, "never-existed", nextcloud=TARGET, env=ENV
    )
    expired = await exchange_enroll.complete_enrollment(
        subject, flow_id, nextcloud=TARGET, env=ENV, now=10_000_000_000
    )

    assert unknown.outcome == exchange_enroll.ENROLL_EXPIRED
    assert expired.outcome == exchange_enroll.ENROLL_EXPIRED
    assert authorization_rows(tmp_path) == 0
    assert flows.revoked == []


@pytest.mark.anyio
async def test_a_failed_poll_is_a_failure_without_a_credential_to_return(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)
    flows.poll = loginflow.PollResult(outcome=loginflow.POLL_FAILED)

    result = await exchange_enroll.complete_enrollment(subject, flow_id, nextcloud=TARGET, env=ENV)

    assert result.outcome == exchange_enroll.ENROLL_FAILED
    assert authorization_rows(tmp_path) == 0
    # No 200 arrived, so no app password exists that could be handed back.
    assert flows.revoked == []


@pytest.mark.anyio
async def test_a_finished_sign_in_writes_the_holding_row(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)

    result = await exchange_enroll.complete_enrollment(subject, flow_id, nextcloud=TARGET, env=ENV)

    assert result.outcome == exchange_enroll.ENROLL_SIGNED_IN
    assert result.account_id == ACCOUNT_ID
    row = await subject.load_authorization(flow_id)
    assert row is not None
    assert row.client_id == exchange_enroll.EXCHANGE_PENDING_CLIENT_ID
    assert row.nc_user == LOGIN
    assert row.nc_account_id == ACCOUNT_ID
    assert row.nc_display_name == DISPLAY
    assert row.scopes == TOOL_SCOPE
    assert row.resource == f"{PUBLIC_URL}{RESOURCE_SUFFIX}"
    assert await subject.app_password(flow_id) == PASSWORD
    # The flow record stays: the OIDC transaction of the confirmation needs it.
    assert await subject.load_flow(flow_id) is not None
    assert flows.revoked == []


@pytest.mark.anyio
async def test_a_holding_row_is_not_a_binding(tmp_path: Path, flows: LoginFlowStub) -> None:
    """The heart of the plan: after the sign in the account source still finds nothing,
    and only the settled enrollment answers (T-23-21)."""
    subject = open_store(tmp_path)
    flow_id = await signed_in(subject, flows)

    assert await subject.binding_of(ACCOUNT_ID, EXCHANGE_CLIENT_ID) is None

    settled = await exchange_enroll.settle_enrollment(subject, flow_id, nextcloud=TARGET)

    assert settled.outcome == exchange_enroll.ENROLL_BOUND
    binding = await subject.binding_of(ACCOUNT_ID, EXCHANGE_CLIENT_ID)
    assert binding is not None
    assert binding.auth_id == settled.auth_id


@pytest.mark.anyio
async def test_an_unresolvable_account_hands_the_credential_back(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)
    flows.resolved = None

    result = await exchange_enroll.complete_enrollment(subject, flow_id, nextcloud=TARGET, env=ENV)

    assert result.outcome == exchange_enroll.ENROLL_FAILED
    assert flows.revoked == [(LOGIN, PASSWORD)]
    assert authorization_rows(tmp_path) == 0
    assert await subject.load_flow(flow_id) is None


@pytest.mark.anyio
async def test_a_paused_account_hands_the_credential_back(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)
    await subject.set_access(ACCOUNT_ID, disabled=True)

    result = await exchange_enroll.complete_enrollment(subject, flow_id, nextcloud=TARGET, env=ENV)

    assert result.outcome == exchange_enroll.ENROLL_PAUSED
    assert flows.revoked == [(LOGIN, PASSWORD)]
    assert authorization_rows(tmp_path) == 0
    assert await subject.load_flow(flow_id) is None


@pytest.mark.anyio
async def test_an_unreadable_pause_switch_is_never_a_no(
    tmp_path: Path, flows: LoginFlowStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)

    async def broken(nc_user: str) -> bool:
        raise RuntimeError("the file is locked")

    monkeypatch.setattr(subject, "access_disabled", broken)
    result = await exchange_enroll.complete_enrollment(subject, flow_id, nextcloud=TARGET, env=ENV)

    assert result.outcome == exchange_enroll.ENROLL_FAILED
    assert flows.revoked == [(LOGIN, PASSWORD)]
    assert authorization_rows(tmp_path) == 0


@pytest.mark.anyio
async def test_a_failed_write_hands_the_credential_back(
    tmp_path: Path, flows: LoginFlowStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)

    async def refused(*args: object, **kwargs: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(subject, "create_authorization", refused)
    result = await exchange_enroll.complete_enrollment(subject, flow_id, nextcloud=TARGET, env=ENV)

    assert result.outcome == exchange_enroll.ENROLL_FAILED
    assert flows.revoked == [(LOGIN, PASSWORD)]
    assert authorization_rows(tmp_path) == 0
    assert await subject.load_flow(flow_id) is None


# --- settle_enrollment ----------------------------------------------------------------


@pytest.mark.anyio
async def test_settling_writes_the_binding_and_removes_the_holding_row(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await signed_in(subject, flows)

    settled = await exchange_enroll.settle_enrollment(subject, flow_id, nextcloud=TARGET)

    assert settled.outcome == exchange_enroll.ENROLL_BOUND
    assert settled.auth_id != flow_id
    binding = await subject.load_authorization(settled.auth_id)
    assert binding is not None
    assert binding.client_id == EXCHANGE_CLIENT_ID
    assert binding.nc_user == LOGIN
    assert binding.nc_account_id == ACCOUNT_ID
    assert await subject.app_password(settled.auth_id) == PASSWORD
    assert await subject.load_authorization(flow_id) is None
    assert await subject.load_flow(flow_id) is None
    # Deleted and never revoked: the shared app password stays alive with the binding.
    assert flows.revoked == []


@pytest.mark.anyio
async def test_a_second_enrollment_of_the_same_account_writes_no_second_binding(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    """T-23-25: one living binding per account, and the second credential goes back."""
    subject = open_store(tmp_path)
    first_flow = await signed_in(subject, flows)
    first = await exchange_enroll.settle_enrollment(subject, first_flow, nextcloud=TARGET)
    assert first.outcome == exchange_enroll.ENROLL_BOUND

    second_flow = await signed_in(subject, flows)
    second = await exchange_enroll.settle_enrollment(subject, second_flow, nextcloud=TARGET)

    assert second.outcome == exchange_enroll.ENROLL_ALREADY_BOUND
    assert flows.revoked == [(LOGIN, PASSWORD)]
    assert await subject.load_authorization(second_flow) is None
    assert await subject.load_flow(second_flow) is None
    binding = await subject.binding_of(ACCOUNT_ID, EXCHANGE_CLIENT_ID)
    assert binding is not None
    assert binding.auth_id == first.auth_id
    # The first binding keeps its credential although the second holding row shared it not.
    assert await subject.app_password(first.auth_id) == PASSWORD


@pytest.mark.anyio
async def test_settling_a_row_that_is_no_holding_row_touches_nothing(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    """A foreign auth_id must never be turned into a binding: only rows under the holding
    client settle, and a refusal leaves the row exactly as it was."""
    subject = open_store(tmp_path)
    await subject.save_client("client-4711", metadata_json="{}")
    await subject.create_authorization(
        "an-ordinary-connection",
        client_id="client-4711",
        nc_user=LOGIN,
        nc_account_id=ACCOUNT_ID,
        app_password=PASSWORD,
        scopes=TOOL_SCOPE,
        resource=f"{PUBLIC_URL}{RESOURCE_SUFFIX}",
    )

    settled = await exchange_enroll.settle_enrollment(
        subject, "an-ordinary-connection", nextcloud=TARGET
    )

    assert settled.outcome == exchange_enroll.ENROLL_FAILED
    assert await subject.load_authorization("an-ordinary-connection") is not None
    assert await subject.binding_of(ACCOUNT_ID, EXCHANGE_CLIENT_ID) is None
    assert flows.revoked == []


@pytest.mark.anyio
async def test_settling_an_unknown_enrollment_is_a_failure_and_no_exception(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)

    settled = await exchange_enroll.settle_enrollment(subject, "never-existed", nextcloud=TARGET)

    assert settled.outcome == exchange_enroll.ENROLL_FAILED
    assert flows.revoked == []


@pytest.mark.anyio
async def test_a_store_that_fails_while_settling_is_a_failure_and_no_exception(
    tmp_path: Path, flows: LoginFlowStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = open_store(tmp_path)
    flow_id = await signed_in(subject, flows)

    async def broken(principal: str, client_id: str):
        raise RuntimeError("the file is locked")

    monkeypatch.setattr(subject, "binding_of", broken)
    settled = await exchange_enroll.settle_enrollment(subject, flow_id, nextcloud=TARGET)

    assert settled.outcome == exchange_enroll.ENROLL_FAILED
    # Nothing was decided, so nothing was dropped and nothing handed back.
    assert await subject.load_authorization(flow_id) is not None
    assert flows.revoked == []


# --- abort_enrollment -----------------------------------------------------------------


@pytest.mark.anyio
async def test_aborting_hands_the_credential_back_and_removes_both_records(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await signed_in(subject, flows)

    await exchange_enroll.abort_enrollment(subject, flow_id, nextcloud=TARGET)

    assert flows.revoked == [(LOGIN, PASSWORD)]
    assert await subject.load_authorization(flow_id) is None
    assert await subject.load_flow(flow_id) is None


@pytest.mark.anyio
async def test_aborting_before_the_sign_in_finished_only_drops_the_flow(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    flow_id = await begun(subject, flows)

    await exchange_enroll.abort_enrollment(subject, flow_id, nextcloud=TARGET)

    assert flows.revoked == []
    assert await subject.load_flow(flow_id) is None


@pytest.mark.anyio
async def test_aborting_never_raises_even_when_the_store_does(
    tmp_path: Path, flows: LoginFlowStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = open_store(tmp_path)
    flow_id = await signed_in(subject, flows)

    async def broken(auth_id: str):
        raise RuntimeError("the file is locked")

    monkeypatch.setattr(subject, "app_password", broken)
    await exchange_enroll.abort_enrollment(subject, flow_id, nextcloud=TARGET)

    # Best effort: the credential could not be read, the records still went.
    assert await subject.load_authorization(flow_id) is None
    assert await subject.load_flow(flow_id) is None

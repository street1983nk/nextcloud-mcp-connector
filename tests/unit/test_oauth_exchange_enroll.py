"""How a binding comes to exist (CRED-02, plan 23-05): three steps, two reserved clients.

The mechanics are functions without a route, so every outcome is measured directly: a real
SQLite store in ``tmp_path`` (the encryption of the app password runs for real), and stand
ins for ``loginflow`` that record every credential this module hands back to Nextcloud. The
two properties everything here exists for: a holding row can do nothing, because
``binding_of`` filters on the other reserved client, and no way out of an enrollment leaves
a Nextcloud credential behind (pitfall 13, D-34).
"""

import asyncio
import re
import sqlite3
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.exapp.ui import exchange as ui_exchange
from mcp_connector.exapp.ui import strings as ui_strings
from mcp_connector.nextcloud.target import NextcloudTarget
from mcp_connector.oauth import exchange_enroll, loginflow
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth.browser_identity import IdentityStep
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


# --- the routes of the enrollment page (plan 23-06) -------------------------------------

ACTING_PARTY = "f13-orchestrator"
OIDC_STEP_PATH = "/oidc/start"


class IdentityStub:
    """A browser identity source of one test: programmable answer, recorded questions."""

    def __init__(self) -> None:
        self.answer = False
        self.raises = False
        self.asked: list[tuple[str, str | None]] = []

    async def identifies(
        self, request: Request, expected_account_id: str, *, flow_id: str | None = None
    ) -> bool:
        if self.raises:
            raise RuntimeError("the identity source broke")
        self.asked.append((expected_account_id, flow_id))
        return self.answer

    async def pending_step(
        self, request: Request, *, flow_id: str, expected_account_id: str
    ) -> IdentityStep | None:
        if self.raises:
            raise RuntimeError("the identity source broke")
        return IdentityStep(
            action_path=OIDC_STEP_PATH,
            fields={"flow": flow_id, "confirm": "a-rendered-form-value"},
        )


class EndConnectionStub:
    """The one revocation path, as the routes receive it: recorded, never the store."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.answer = True

    async def __call__(self, principal: str, auth_id: str) -> bool:
        self.calls.append((principal, auth_id))
        return self.answer


def routed_client(
    subject: OAuthStore,
    identity: IdentityStub,
    *,
    end_connection: EndConnectionStub | None = None,
    throttle: throttle_module.Throttle | None = None,
) -> TestClient:
    async def opener() -> OAuthStore:
        return subject

    routes = exchange_enroll.exchange_routes(
        ENV,
        nextcloud=TARGET,
        store_provider=opener,
        browser_identity=identity,
        end_connection=end_connection if end_connection is not None else EndConnectionStub(),
        acting_party=ACTING_PARTY,
        throttle=throttle,
    )
    return TestClient(Starlette(routes=routes))


def binding_missing(subject: OAuthStore, account_id: str) -> bool:
    """Whether the account source of 23-04 still finds nothing for this account."""
    return asyncio.run(subject.binding_of(account_id, EXCHANGE_CLIENT_ID)) is None


def flow_id_of(handoff_body: str) -> str:
    """The flow id out of the hidden field of the rendered handoff page."""
    match = re.search(rf'name="{ui_exchange.FLOW_PARAM}" value="([^"]+)"', handoff_body)
    assert match is not None, "the handoff page carries the flow id as a hidden value"
    return match.group(1)


def normalized(body: str) -> str:
    """One page body with the per response nonce taken out, so two renders compare."""
    return re.sub(r"nonce-[A-Za-z0-9_-]+", "nonce-X", re.sub(r'nonce="[^"]+"', 'nonce="X"', body))


def started_flow(client: TestClient) -> str:
    response = client.post(
        ui_exchange.ENROLL_PATH, data={ui_exchange.ACTION_FIELD: ui_exchange.ACTION_START}
    )
    assert response.status_code == 200
    assert LOGIN_URL in response.text
    return flow_id_of(response.text)


def test_the_read_and_the_start_have_their_two_throttle_classes() -> None:
    """One address, two counters: the POST that opens a login flow counts every request
    against FLOW_LIMIT, and it may not share a class with the reads, because a successful
    read pays one attempt back (WR-03) and a shared counter would let a reload of the
    invitation erase the count of the flows an attacker opened."""
    assert "CLASS_EXCHANGE_ENROLL" in throttle_module.__all__
    assert "CLASS_EXCHANGE_ENROLL_START" in throttle_module.__all__
    assert throttle_module.CLASS_EXCHANGE_ENROLL != throttle_module.CLASS_EXCHANGE_ENROLL_START


def test_the_bare_page_is_the_invitation(tmp_path: Path, flows: LoginFlowStub) -> None:
    client = routed_client(open_store(tmp_path), IdentityStub())

    response = client.get(ui_exchange.ENROLL_PATH)

    assert response.status_code == 200
    assert ui_strings.EXCHANGE_REACH in response.text
    assert f'value="{ui_exchange.ACTION_START}"' in response.text
    assert response.headers["cache-control"] == "no-store"


def test_starting_opens_a_login_flow_and_answers_the_handoff(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    client = routed_client(subject, IdentityStub())

    flow_id = started_flow(client)

    assert flow_rows(tmp_path) == 1
    assert flow_id


def test_a_running_sign_in_answers_the_waiting_screen(tmp_path: Path, flows: LoginFlowStub) -> None:
    subject = open_store(tmp_path)
    client = routed_client(subject, IdentityStub())
    flow_id = started_flow(client)
    flows.poll = loginflow.PollResult(outcome=loginflow.POLL_PENDING)

    response = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: flow_id})

    assert response.status_code == 200
    assert '<meta http-equiv="refresh" content="3">' in response.text


def test_a_finished_sign_in_without_a_proof_shows_the_step_and_writes_no_binding(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    """The acceptance criterion of T-23-26: no proof, no row under EXCHANGE_CLIENT_ID."""
    subject = open_store(tmp_path)
    identity = IdentityStub()
    client = routed_client(subject, identity)
    flow_id = started_flow(client)

    response = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: flow_id})

    assert response.status_code == 200
    assert OIDC_STEP_PATH in response.text
    assert ui_strings.CONSENT_CONFIRM_ACTION in response.text
    assert binding_missing(subject, ACCOUNT_ID)
    assert identity.asked == [(ACCOUNT_ID, flow_id)]


def test_the_same_call_with_a_proof_writes_the_binding_and_shows_it(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    """T-23-26 mitigated: the binding is written only after ``identifies`` said yes, in the
    same request run, and the page shows account, date and acting party."""
    subject = open_store(tmp_path)
    identity = IdentityStub()
    client = routed_client(subject, identity)
    flow_id = started_flow(client)
    client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: flow_id})
    assert binding_missing(subject, ACCOUNT_ID)
    identity.answer = True

    response = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: flow_id})

    assert response.status_code == 200
    assert ui_strings.EXCHANGE_BOUND_TITLE in response.text
    assert DISPLAY in response.text
    assert ACTING_PARTY in response.text
    assert f'value="{ui_exchange.ACTION_REVOKE}"' in response.text
    assert not binding_missing(subject, ACCOUNT_ID)


def test_an_already_bound_account_gets_the_page_of_the_existing_binding(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    subject = open_store(tmp_path)
    identity = IdentityStub()
    identity.answer = True
    client = routed_client(subject, identity)
    first_flow = started_flow(client)
    first = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: first_flow})
    assert ui_strings.EXCHANGE_BOUND_TITLE in first.text

    second_flow = started_flow(client)
    second = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: second_flow})

    assert second.status_code == 200
    assert ui_strings.EXCHANGE_BOUND_TITLE in second.text
    # No second row was written, and the second credential went back to Nextcloud.
    assert flows.revoked == [(LOGIN, PASSWORD)]


def test_an_unknown_an_expired_and_a_foreign_procedure_read_like_no_procedure(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    """One answer (T-23-28): a dead procedure is indistinguishable from none at all."""
    subject = open_store(tmp_path)
    client = routed_client(subject, IdentityStub())
    plain = client.get(ui_exchange.ENROLL_PATH)

    expired = asyncio.run(exchange_enroll.begin_enrollment(subject, nextcloud=TARGET, now=1_000))
    assert expired.outcome == exchange_enroll.ENROLL_STARTED
    asyncio.run(subject.save_client("client-4711", metadata_json="{}"))
    asyncio.run(
        subject.create_authorization(
            "an-ordinary-connection",
            client_id="client-4711",
            nc_user=LOGIN,
            nc_account_id=ACCOUNT_ID,
            app_password=PASSWORD,
            scopes=TOOL_SCOPE,
            resource="",
        )
    )

    for flow_value in ("never-existed", expired.flow_id, "an-ordinary-connection"):
        response = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: flow_value})
        assert response.status_code == plain.status_code
        assert normalized(response.text) == normalized(plain.text)


def test_a_failing_identity_source_is_a_refusal_and_never_a_binding(
    tmp_path: Path, flows: LoginFlowStub
) -> None:
    """A source is a security boundary: its failure is a refusal, never a fallback."""
    subject = open_store(tmp_path)
    identity = IdentityStub()
    identity.raises = True
    client = routed_client(subject, identity)
    flow_id = started_flow(client)

    response = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: flow_id})

    assert response.status_code == 500
    assert ui_strings.ERROR_GENERIC_TITLE in response.text
    assert binding_missing(subject, ACCOUNT_ID)


def test_a_paused_account_meets_the_paused_page(tmp_path: Path, flows: LoginFlowStub) -> None:
    subject = open_store(tmp_path)
    client = routed_client(subject, IdentityStub())
    flow_id = started_flow(client)

    asyncio.run(subject.set_access(ACCOUNT_ID, disabled=True))
    response = client.get(ui_exchange.ENROLL_PATH, params={ui_exchange.FLOW_PARAM: flow_id})

    assert response.status_code == 403
    assert flows.revoked == [(LOGIN, PASSWORD)]


def test_an_oversized_and_an_unknown_form_are_a_400(tmp_path: Path, flows: LoginFlowStub) -> None:
    subject = open_store(tmp_path)
    client = routed_client(subject, IdentityStub())

    oversized = client.post(
        ui_exchange.ENROLL_PATH,
        data={
            ui_exchange.ACTION_FIELD: ui_exchange.ACTION_START,
            "padding": "p" * 8192,
        },
    )
    unknown = client.post(ui_exchange.ENROLL_PATH, data={ui_exchange.ACTION_FIELD: "surprise"})

    assert oversized.status_code == 400
    assert unknown.status_code == 400
    assert flow_rows(tmp_path) == 0, "neither body was ever acted on"


def test_repeated_starts_run_into_the_flow_throttle(tmp_path: Path, flows: LoginFlowStub) -> None:
    """T-23-27: the POST that opens a login flow counts every request, and a throttled
    caller gets the error page E6, not JSON, because a browser stands here."""
    subject = open_store(tmp_path)
    client = routed_client(subject, IdentityStub(), throttle=throttle_module.Throttle())

    start = {ui_exchange.ACTION_FIELD: ui_exchange.ACTION_START}
    for _ in range(throttle_module.FLOW_LIMIT):
        allowed = client.post(ui_exchange.ENROLL_PATH, data=start)
        assert allowed.status_code == 200

    refused = client.post(ui_exchange.ENROLL_PATH, data=start)

    assert refused.status_code == 429
    assert refused.headers["content-type"].startswith("text/html")
    assert refused.headers["retry-after"]
    assert ui_strings.ERROR_THROTTLED_TITLE in refused.text


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

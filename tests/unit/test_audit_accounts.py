"""D-12: a deleted account takes its chain, and a doubt about an account takes nothing.

Every case in this file is written against the one asymmetry of plan 18-09. The list of
accounts is input, it comes over the network, and the assumption behind it is unmeasured
(A1, 18-RESEARCH.md §7): it is not known whether ``searchDisplayName('')`` answers
completely on every user backend. So the two directions cost different things and are tested
differently:

*   **Deleting** needs a list that was read, that is not empty, and that does not contain the
    account. Three conditions, and the case that matters most is the one that has two of them
    and deletes nothing.
*   **Keeping** is what every other answer means. A network error, any status but 200, a body
    that is not a list, and an empty list are one case each, and all four keep.

Nothing here goes to the network: Nextcloud answers through ``respx``, and the store is a
real SQLite file in ``tmp_path``, because what a dropped chain leaves behind is a state of
that file and no double could show it.

The schedule is not mocked either. ``should_check_accounts`` is a pure function of the
sequence number the store hands back, so a case that wants the tenthousandth row asks SQLite
for it: ``sqlite_sequence`` is set to 9999 and the next written row is number 10000. That way
the case rides on the real predicate of D-11 and D-12 rather than on a patched one.
"""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from starlette.requests import Request

from mcp_connector import config
from mcp_connector.audit import AUDIT_STATE_ATTR, accounts
from mcp_connector.audit.record import Recorder
from mcp_connector.audit.store import (
    CHAIN_INSTANCE,
    KIND_CALL,
    KIND_SWITCH,
    KIND_TOMBSTONE,
    SWEEP_EVERY,
    SWEEP_USER_CHECK_EVERY,
    USER_SILENCE_DAYS,
    AuditStore,
    Entry,
    user_chain,
)
from mcp_connector.oauth.verifier import OAUTH_STATE_ATTR, OAuthIdentity
from mcp_connector.server import graceful

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
BASE_URL = "http://nc.test"

ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_AA_VERSION: "34.0.3",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
}

USERS_URL = f"{BASE_URL}{accounts.USERS_PATH}"

#: Seconds in a day, spelled here rather than imported from the private name of the store.
DAY = 86400

#: The account that stopped calling, and the account that is calling right now.
SILENT = "alice"
CALLER = "bob"

#: A real tool of the allowlist, so the recording path takes its ordinary way.
TOOL = "files_list"

#: The number of the row that is both a sweep and an account check (D-11 plus D-12).
CHECKING_ROW = SWEEP_EVERY * SWEEP_USER_CHECK_EVERY

#: A path in the message of a store failure. It is what the fail-open case searches for and
#: must not find: D-13 is the type of the failure and never its sentence.
BROKEN_PATH = "/var/lib/mcp_connector/audit.sqlite3"


def envelope(data: Any) -> dict[str, Any]:
    """The OCS envelope AppAPI answers in, with whatever a case wants inside it."""
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": data}}


class FakeRequestContext:
    """What the SDK hands a tool: the request of the message, and the call parameters."""

    def __init__(self, request: Request, params: Any) -> None:
        self.request = request
        self.params = params


class FakeContext:
    """A tool context carrying the recorder and the identity of the caller."""

    def __init__(self, *, recorder: object, who: OAuthIdentity) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [],
            }
        )
        setattr(request.state, OAUTH_STATE_ATTR, who)
        setattr(request.state, AUDIT_STATE_ATTR, recorder)
        self.headers: dict[str, str] = {}
        self.request_context = FakeRequestContext(request, {"name": TOOL, "arguments": {}})


def identity(nc_user: str = CALLER) -> OAuthIdentity:
    """The identity the transport boundary resolves once per request."""
    return OAuthIdentity(
        nc_user=nc_user,
        principal=nc_user,
        app_password="aaaaa-bbbbb-ccccc-ddddd-eeeee",
        auth_id="the-flow-this-authorization-was-born-in",
        client_id="9d0f8f1a-0b3c-4a0e-9f4c-000000000001",
        client_name="Claude",
    )


@graceful
async def probe(ctx: Any = None) -> str:
    """A tool shaped function, so the recording path runs exactly as it does in production."""
    return "answered"


@pytest.fixture
def audit_file(tmp_path: Path) -> Path:
    """The path of the store every case writes to, so a case can read it back by hand."""
    return tmp_path / "audit.sqlite3"


@pytest.fixture
def store(audit_file: Path) -> AuditStore:
    return AuditStore(audit_file)


@pytest.fixture
def recorder(store: AuditStore) -> Recorder:
    """A recorder over a real store, carrying the deploy environment of this instance.

    ``env`` is the field plan 18-07 wired in ``entry_exapp.py``; without it the account check
    would stand in the code and have nobody to call.
    """

    async def provider() -> AuditStore:
        return store

    return Recorder(store_provider=provider, env=ENV)


def rows(path: Path) -> list[dict[str, Any]]:
    """Every row of the store, read with a connection of our own and past the store API."""
    if not path.exists():
        return []
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM entries ORDER BY seq")]
    finally:
        connection.close()


def arm_the_next_row(path: Path, number: int) -> None:
    """Make the next appended row carry ``number``, through the counter AUTOINCREMENT keeps.

    The schedule of D-11 and D-12 hangs on that number, and this is how a case reaches the
    tenthousandth row without writing ten thousand of them. ``sqlite_sequence`` is exactly
    where SQLite keeps the highest number it ever handed out.
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = 'entries'", (number - 1,)
        )
        connection.commit()
    finally:
        connection.close()


async def a_silent_chain(store: AuditStore, *, moment: int, nc_user: str = SILENT) -> None:
    """Two rows of one account, both older than the threshold of D-12."""
    for age in (90, 60):
        await store.append(
            Entry(
                chain=user_chain(nc_user),
                kind=KIND_CALL,
                at=moment - age * DAY,
                nc_user=nc_user,
                tool=TOOL,
                outcome="ok",
            )
        )


# --- the account list: one answer becomes a set, four keep everything -------------------


@pytest.mark.anyio
@respx.mock
async def test_a_list_of_names_is_the_only_answer_that_becomes_a_set() -> None:
    """The one shape that may be used to say an account is gone."""
    route = respx.get(USERS_URL).mock(
        return_value=httpx.Response(200, json=envelope([SILENT, CALLER]))
    )

    assert await accounts.existing_users(ENV) == frozenset({SILENT, CALLER})

    sent = route.calls[0].request
    assert sent.headers["OCS-APIRequest"] == "true"
    assert sent.headers["EX-APP-ID"] == APP_ID
    # The empty user id is the app context: this is the ExApp asking about the instance and
    # not a request on behalf of a person.
    assert sent.headers["AUTHORIZATION-APP-API"]


@pytest.mark.anyio
@respx.mock
async def test_a_network_error_means_every_account_exists() -> None:
    respx.get(USERS_URL).mock(side_effect=httpx.ConnectError("no route to nextcloud"))

    assert await accounts.existing_users(ENV) is None


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("status", [401, 403, 404, 500, 502])
async def test_a_status_other_than_200_means_every_account_exists(status: int) -> None:
    respx.get(USERS_URL).mock(return_value=httpx.Response(status, json=envelope([SILENT])))

    assert await accounts.existing_users(ENV) is None


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize(
    "body",
    [
        {"ocs": {"data": {"0": SILENT}}},
        {"ocs": {"meta": {"status": "ok"}}},
        {"data": [SILENT]},
        [SILENT],
    ],
    ids=["data-is-an-object", "no-data-at-all", "no-envelope", "a-bare-list"],
)
async def test_an_answer_that_is_not_a_list_means_every_account_exists(body: Any) -> None:
    """An unreadable shape is never an empty one, the rule ``config_values.py`` already has."""
    respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=body))

    assert await accounts.existing_users(ENV) is None


@pytest.mark.anyio
@respx.mock
async def test_an_answer_that_is_not_json_means_every_account_exists() -> None:
    respx.get(USERS_URL).mock(return_value=httpx.Response(200, text="<html>login</html>"))

    assert await accounts.existing_users(ENV) is None


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("data", [[], [None, 17, ""]], ids=["empty", "nothing-usable"])
async def test_an_empty_list_is_a_fault_and_never_an_instance_without_users(data: Any) -> None:
    """A store with a chain in it belongs to an instance that has users (18-RESEARCH.md §7)."""
    respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=envelope(data)))

    assert await accounts.existing_users(ENV) is None


@pytest.mark.anyio
async def test_an_incomplete_deploy_environment_never_raises() -> None:
    assert await accounts.existing_users({}) is None


@pytest.mark.anyio
@respx.mock
async def test_no_line_about_a_failure_carries_a_value_or_a_header(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-18-10: the status or the type of the failure, never a value and never the secret."""
    respx.get(USERS_URL).mock(return_value=httpx.Response(500, json=envelope([SILENT])))

    with caplog.at_level(logging.DEBUG):
        assert await accounts.existing_users(ENV) is None
        respx.get(USERS_URL).mock(side_effect=httpx.ConnectError("no route to nextcloud"))
        assert await accounts.existing_users(ENV) is None

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "500" in logged
    assert "ConnectError" in logged
    assert APP_SECRET not in logged
    assert SILENT not in logged
    assert "no route to nextcloud" not in logged


# --- the silent chains, and what dropping one leaves behind -----------------------------


@pytest.mark.anyio
async def test_only_the_chains_past_the_threshold_are_named(store: AuditStore) -> None:
    """The question is asked about a silent account and about nobody else."""
    moment = int(time.time())
    await a_silent_chain(store, moment=moment)
    await store.append(
        Entry(
            chain=user_chain(CALLER),
            kind=KIND_CALL,
            at=moment - DAY,
            nc_user=CALLER,
            tool=TOOL,
            outcome="ok",
        )
    )
    await store.append(Entry(chain=CHAIN_INSTANCE, kind=KIND_SWITCH, at=moment - 400 * DAY))

    assert await store.silent_users(moment=moment) == [SILENT]


@pytest.mark.anyio
async def test_the_threshold_is_the_edge_of_the_window(store: AuditStore) -> None:
    """One second younger than the window is not silent, exactly on it is."""
    moment = int(time.time())
    edge = moment - USER_SILENCE_DAYS * DAY
    await store.append(
        Entry(chain=user_chain(SILENT), kind=KIND_CALL, at=edge, nc_user=SILENT, outcome="ok")
    )
    await store.append(
        Entry(chain=user_chain(CALLER), kind=KIND_CALL, at=edge + 1, nc_user=CALLER, outcome="ok")
    )

    assert await store.silent_users(moment=moment) == [SILENT]


@pytest.mark.anyio
async def test_dropping_a_chain_removes_every_row_and_leaves_one_tombstone(
    store: AuditStore, audit_file: Path
) -> None:
    """D-12 and T-18-21: the chain goes, and the instance chain says that it went."""
    moment = int(time.time())
    await a_silent_chain(store, moment=moment)
    end = rows(audit_file)[-1]["hash"]

    assert await store.drop_user_chain(SILENT, moment=moment) == 2

    left = rows(audit_file)
    assert [row["chain"] for row in left] == [CHAIN_INSTANCE]
    marker = left[0]
    assert marker["kind"] == KIND_TOMBSTONE
    assert marker["gap_chain"] == user_chain(SILENT)
    assert marker["gap_hash"] == end.hex()
    assert marker["removed"] == 2
    assert marker["actor"] == "unknown"


@pytest.mark.anyio
async def test_a_dropped_chain_leaves_a_store_without_a_finding(store: AuditStore) -> None:
    """The check has to stay quiet afterwards, or every deletion would look like a break."""
    moment = int(time.time())
    await a_silent_chain(store, moment=moment)
    await store.append(Entry(chain=CHAIN_INSTANCE, kind=KIND_SWITCH, at=moment, outcome="on"))

    await store.drop_user_chain(SILENT, moment=moment)

    assert await store.verify_chains() == []


@pytest.mark.anyio
async def test_dropping_a_chain_that_is_not_there_writes_nothing(
    store: AuditStore, audit_file: Path
) -> None:
    """No rows, no gap, and therefore no marker explaining one."""
    moment = int(time.time())
    await store.append(Entry(chain=CHAIN_INSTANCE, kind=KIND_SWITCH, at=moment, outcome="on"))

    assert await store.drop_user_chain(SILENT, moment=moment) == 0

    assert [row["kind"] for row in rows(audit_file)] == [KIND_SWITCH]


# --- the account check inside the bundled sweep -----------------------------------------


@pytest.mark.anyio
@respx.mock
async def test_an_unknown_account_list_drops_no_chain(
    store: AuditStore, recorder: Recorder, audit_file: Path
) -> None:
    """The case of this plan: two of three conditions are met, and nothing is deleted."""
    respx.get(USERS_URL).mock(side_effect=httpx.ConnectError("no route to nextcloud"))
    moment = int(time.time())
    await a_silent_chain(store, moment=moment)
    arm_the_next_row(audit_file, CHECKING_ROW)

    assert await probe(ctx=FakeContext(recorder=recorder, who=identity())) == "answered"

    chains = {row["chain"] for row in rows(audit_file)}
    assert user_chain(SILENT) in chains
    assert not [row for row in rows(audit_file) if row["kind"] == KIND_TOMBSTONE]


@pytest.mark.anyio
@respx.mock
async def test_a_silent_account_that_still_exists_keeps_its_chain(
    store: AuditStore, recorder: Recorder, audit_file: Path
) -> None:
    respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=envelope([SILENT, CALLER])))
    moment = int(time.time())
    await a_silent_chain(store, moment=moment)
    arm_the_next_row(audit_file, CHECKING_ROW)

    await probe(ctx=FakeContext(recorder=recorder, who=identity()))

    assert len([row for row in rows(audit_file) if row["chain"] == user_chain(SILENT)]) == 2
    assert not [row for row in rows(audit_file) if row["kind"] == KIND_TOMBSTONE]


@pytest.mark.anyio
@respx.mock
async def test_a_silent_account_missing_from_a_read_list_loses_its_chain(
    store: AuditStore, recorder: Recorder, audit_file: Path
) -> None:
    """The whole point of D-12, and the only shape of an answer that reaches it."""
    respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=envelope([CALLER])))
    moment = int(time.time())
    await a_silent_chain(store, moment=moment)
    arm_the_next_row(audit_file, CHECKING_ROW)

    await probe(ctx=FakeContext(recorder=recorder, who=identity()))

    left = rows(audit_file)
    assert not [row for row in left if row["chain"] == user_chain(SILENT)]
    markers = [row for row in left if row["kind"] == KIND_TOMBSTONE]
    assert [marker["gap_chain"] for marker in markers] == [user_chain(SILENT)]
    assert markers[0]["removed"] == 2
    assert await store.verify_chains() == []


@pytest.mark.anyio
@respx.mock
async def test_an_ordinary_sweep_never_asks_for_the_account_list(
    store: AuditStore, recorder: Recorder, audit_file: Path
) -> None:
    """T-18-16: the one step that costs an HTTP call runs a magnitude less often."""
    route = respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=envelope([CALLER])))
    moment = int(time.time())
    await a_silent_chain(store, moment=moment)
    arm_the_next_row(audit_file, SWEEP_EVERY)

    await probe(ctx=FakeContext(recorder=recorder, who=identity()))

    assert route.call_count == 0
    assert len([row for row in rows(audit_file) if row["chain"] == user_chain(SILENT)]) == 2


@pytest.mark.anyio
@respx.mock
async def test_a_failed_account_check_costs_the_call_nothing(
    recorder: Recorder, audit_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """D-13 over the new branch: the answer arrives, and the line names the type only."""
    respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=envelope([CALLER])))

    class BrokenStore(AuditStore):
        async def silent_users(self, *, moment: int, silence_days: int = USER_SILENCE_DAYS):
            raise OSError(f"no space left on device: {BROKEN_PATH}")

    store = BrokenStore(audit_file)

    async def provider() -> AuditStore:
        return store

    broken = Recorder(store_provider=provider, env=ENV)
    await store.append(Entry(chain=CHAIN_INSTANCE, kind=KIND_SWITCH, at=int(time.time())))
    arm_the_next_row(audit_file, CHECKING_ROW)

    with caplog.at_level(logging.DEBUG):
        assert await probe(ctx=FakeContext(recorder=broken, who=identity())) == "answered"

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "OSError" in logged
    assert BROKEN_PATH not in logged

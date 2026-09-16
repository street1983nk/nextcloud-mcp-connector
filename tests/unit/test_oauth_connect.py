"""The browser onboarding for clients that cannot speak OAuth (AUTH-02, D-36).

The promise of this route is small and hard: a user opens a page, signs in at Nextcloud
itself, and reads one credential exactly once. This server never sees the password, never
asks for one, and keeps nothing of what it hands over.

Threats covered here: T-03-30 (a password prompt of our own, or a page that imitates
Nextcloud), T-03-32 (taking over a running sign in through its flow id), T-03-33 (the
credential surviving in a file or a cache), T-03-34 (a poll storm out of the waiting page)
and T-03-35 (flows without an end).

Nothing here starts a container, opens a socket or needs a Nextcloud: every call to
Nextcloud is answered by respx, and the store is a SQLite file in ``tmp_path``.
"""

import asyncio
import base64
import logging
import re
import sqlite3
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config, entry_http
from mcp_connector.entry_exapp import build_exapp_app
from mcp_connector.exapp.target import exapp_target
from mcp_connector.exapp.ui import strings
from mcp_connector.nextcloud.target import NextcloudTarget
from mcp_connector.oauth import connect, loginflow
from mcp_connector.oauth import store as store_module
from mcp_connector.oauth import throttle as throttle_module
from mcp_connector.oauth.store import FLOW_TTL, FlowRow, OAuthStore

BASE_URL = "http://nc.test"
PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"
HOST = "cloud.example.com"

ENV = {
    config.ENV_PUBLIC_URL: PUBLIC_URL,
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.1.0",
    config.ENV_AA_VERSION: "34.0.3",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
}

#: The Nextcloud the onboarding routes are built against, resolved like the ExApp does.
TARGET = exapp_target(ENV)

INIT_URL = f"{BASE_URL}{loginflow.INIT_PATH}"
POLL_URL = f"{BASE_URL}{loginflow.POLL_PATH}"

LOGIN_URL = "https://cloud.example.com/index.php/login/v2/flow/abc123"
POLL_TOKEN = "poll-token-of-this-flow"
LOGIN_NAME = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

UI_DIR = Path(connect.__file__).resolve().parents[1] / "exapp" / "ui"


def start_body() -> dict[str, object]:
    endpoint = "https://public.example.org/login/v2/poll"
    return {"poll": {"token": POLL_TOKEN, "endpoint": endpoint}, "login": LOGIN_URL}


def poll_body() -> dict[str, str]:
    return {"server": BASE_URL, "loginName": LOGIN_NAME, "appPassword": APP_PASSWORD}


class Inputs(HTMLParser):
    """Collect every form control of a page, which is what a phishing page would need."""

    def __init__(self) -> None:
        super().__init__()
        self.controls: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"input", "textarea", "select"}:
            self.controls.append({key: value or "" for key, value in attrs} | {"tag": tag})


def controls(markup: str) -> list[dict[str, str]]:
    parser = Inputs()
    parser.feed(markup)
    return parser.controls


@pytest.fixture
def store(tmp_path: Path) -> OAuthStore:
    return OAuthStore(tmp_path / "oauth.sqlite3", KEY)


@pytest.fixture
def client(store: OAuthStore) -> TestClient:
    return TestClient(app_with(store))


def app_with(store: OAuthStore) -> Starlette:
    async def provider() -> OAuthStore:
        return store

    return Starlette(routes=connect.connect_routes(ENV, nextcloud=TARGET, store_provider=provider))


def start_a_flow(client: TestClient) -> str:
    """Run the POST that opens a sign in and return the flow id it created."""
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
    response = client.post(connect.CONNECT_PATH, data={connect.ACTION_FIELD: connect.ACTION_START})
    assert response.status_code == 200, response.text
    match = re.search(rf'name="{connect.FLOW_PARAM}" value="([A-Za-z0-9_-]+)"', response.text)
    assert match is not None, response.text
    return match.group(1)


def wait_url(flow_id: str) -> str:
    return f"{connect.WAIT_PATH}?{connect.FLOW_PARAM}={flow_id}"


def as_user(user: str = LOGIN_NAME) -> dict[str, str]:
    """The three headers HaRP attaches once it has resolved a Nextcloud account.

    These tests speak to the application directly, so they stand in for the proxy. The
    value of ``AUTHORIZATION-APP-API`` is base64 of ``<user>:<APP_SECRET>``, which is what
    HaRP builds out of the account it resolved and the registration secret of this app, and
    which is why no caller can write it themselves: the secret is not theirs.
    """
    raw = f"{user}:{ENV[config.ENV_APP_SECRET]}".encode()
    return {
        "EX-APP-ID": ENV[config.ENV_APP_ID],
        "EX-APP-VERSION": ENV[config.ENV_APP_VERSION],
        "AUTHORIZATION-APP-API": base64.b64encode(raw).decode("ascii"),
    }


def result_of(client: TestClient, flow_id: str, user: str = LOGIN_NAME) -> Any:
    """Load the waiting page as the browser of one signed in Nextcloud account (CR-01)."""
    return client.get(wait_url(flow_id), headers=as_user(user))


def flow_ids(store: OAuthStore) -> list[str]:
    """Every flow id in the file, read beside the store on purpose."""
    if not store.path.is_file():
        return []
    conn = sqlite3.connect(store.path)
    try:
        return [row[0] for row in conn.execute("SELECT flow_id FROM flows").fetchall()]
    finally:
        conn.close()


def load_flow(store: OAuthStore, flow_id: str) -> FlowRow | None:
    return asyncio.run(store.load_flow(flow_id))


def store_bytes(directory: Path) -> bytes:
    """Everything the store wrote, including the write ahead log."""
    return b"".join(path.read_bytes() for path in sorted(directory.iterdir()) if path.is_file())


# --- the handoff page --------------------------------------------------------------------


def test_the_handoff_page_names_who_is_asking_and_offers_the_sign_in(client: TestClient) -> None:
    response = client.get(connect.CONNECT_PATH)

    assert response.status_code == 200
    assert strings.WORDMARK in response.text
    assert HOST in response.text
    assert strings.SIGNIN_CTA in response.text
    assert '<form method="post"' in response.text


def test_the_handoff_page_starts_nothing(client: TestClient) -> None:
    """T-03-35: a GET may not open a login flow, or a crawler opens thousands."""
    with respx.mock:
        init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
        client.get(connect.CONNECT_PATH)

        assert init.call_count == 0


# --- starting a sign in ------------------------------------------------------------------


@respx.mock
def test_the_start_opens_one_flow_and_links_to_nextcloud_in_a_new_window(
    client: TestClient,
) -> None:
    init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))

    response = client.post(connect.CONNECT_PATH, data={connect.ACTION_FIELD: connect.ACTION_START})

    assert init.call_count == 1
    assert response.status_code == 200
    assert LOGIN_URL in response.text
    assert 'target="_blank"' in response.text
    assert 'rel="noopener noreferrer"' in response.text
    assert strings.SIGNIN_CTA in response.text


@respx.mock
def test_the_start_sends_the_prefixed_onboarding_name_as_the_user_agent(
    client: TestClient,
) -> None:
    """T-03-37: the entry in "Devices and sessions" has to say where it came from."""
    init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))

    client.post(connect.CONNECT_PATH, data={connect.ACTION_FIELD: connect.ACTION_START})

    assert init.calls[0].request.headers["user-agent"].startswith(loginflow.AGENT_PREFIX)


@respx.mock
def test_the_flow_record_is_unguessable_and_runs_out_after_twenty_minutes(
    client: TestClient, store: OAuthStore
) -> None:
    flow_id = start_a_flow(client)

    assert flow_ids(store) == [flow_id]
    assert len(flow_id) >= 32, "the flow id is the only authorisation to fetch the result"
    row = load_flow(store, flow_id)
    assert row is not None
    assert row.poll_token == POLL_TOKEN
    assert abs(row.expires_at - (int(time.time()) + FLOW_TTL)) <= 5


@respx.mock
def test_the_poll_token_never_lies_in_the_file_in_clear_text(
    client: TestClient, tmp_path: Path
) -> None:
    start_a_flow(client)

    assert POLL_TOKEN.encode() not in store_bytes(tmp_path)


@respx.mock
def test_a_start_nextcloud_refuses_leaves_no_flow_behind(
    client: TestClient, store: OAuthStore
) -> None:
    respx.post(INIT_URL).mock(return_value=httpx.Response(500, json={}))

    response = client.post(connect.CONNECT_PATH, data={connect.ACTION_FIELD: connect.ACTION_START})

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert flow_ids(store) == []


def test_an_unknown_action_changes_nothing(client: TestClient, store: OAuthStore) -> None:
    response = client.post(connect.CONNECT_PATH, data={connect.ACTION_FIELD: "something else"})

    assert response.status_code == 400
    assert flow_ids(store) == []


def test_a_body_that_cannot_be_parsed_changes_nothing_and_stays_a_page(
    client: TestClient, store: OAuthStore
) -> None:
    """HI-02 on the older half of the family: ``Request.form()`` can raise.

    The parser of ``python-multipart`` raises an exception Starlette does not catch, so this
    body used to leave the route as a bare 500 with a traceback in the log. It is the same
    case as an action this route does not understand, and it gets the same answer.
    """
    response = client.post(
        connect.CONNECT_PATH,
        headers={"Content-Type": "multipart/form-data; boundary=the-boundary"},
        content=b"this is not a multipart body",
    )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert "Traceback" not in response.text
    assert flow_ids(store) == []


# --- waiting (T-03-34) --------------------------------------------------------------------


@respx.mock
def test_the_waiting_page_refreshes_itself_and_polls_exactly_once(client: TestClient) -> None:
    flow_id = start_a_flow(client)
    poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))

    response = client.get(wait_url(flow_id))

    assert response.status_code == 200
    assert poll.call_count == 1
    assert 'http-equiv="refresh"' in response.text
    assert 'role="status"' in response.text
    assert 'aria-live="polite"' in response.text
    assert strings.ACTION_CHECK_NOW in response.text
    assert "<script" not in response.text


@respx.mock
def test_three_loads_of_the_waiting_page_are_three_polls_and_nothing_more(
    client: TestClient,
) -> None:
    flow_id = start_a_flow(client)
    poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))

    for _ in range(3):
        client.get(wait_url(flow_id))

    assert poll.call_count == 3


@respx.mock
def test_the_poll_carries_the_token_of_that_flow(client: TestClient) -> None:
    flow_id = start_a_flow(client)
    poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))

    client.get(wait_url(flow_id))

    assert poll.calls[0].request.content == f"token={POLL_TOKEN}".encode()


# --- the one time result ------------------------------------------------------------------


@respx.mock
def test_the_credential_is_shown_once_and_never_again(client: TestClient) -> None:
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))

    first = result_of(client, flow_id)
    second = result_of(client, flow_id)

    assert first.status_code == 200
    assert APP_PASSWORD in first.text
    assert LOGIN_NAME in first.text
    assert second.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in second.text
    assert APP_PASSWORD not in second.text


@respx.mock
def test_the_flow_record_is_gone_after_the_result(client: TestClient, store: OAuthStore) -> None:
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))

    result_of(client, flow_id)

    assert flow_ids(store) == []


@respx.mock
def test_the_credential_reaches_no_file_of_this_server(client: TestClient, tmp_path: Path) -> None:
    """T-03-33: the app password belongs to the user, not to this server."""
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))

    assert APP_PASSWORD in result_of(client, flow_id).text
    assert APP_PASSWORD.encode() not in store_bytes(tmp_path)


@respx.mock
def test_the_result_page_says_how_to_use_it_and_how_to_revoke_it(client: TestClient) -> None:
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))

    text = result_of(client, flow_id).text

    assert strings.RESULT_CONNECTED_TITLE in text
    assert "Devices and sessions" in text
    assert strings.CONNECT_RESULT_ONCE in text


# --- BL-10: a paused account never reads a credential out of this page ---------------------
#
# One comment per statement of BL-10:
#
# * Until this plan the switch hung on ``MCP_PATH`` alone, so this whole route ran for a
#   paused account and handed it a working app password.
# * The credential exists at Nextcloud from the 200 of the poll, so the refusal owes the
#   revocation: the set of valid app passwords may not grow while the brake is pulled.
# * The check sits after the poll on purpose. Before it, ``_start`` knows no account at all.
# * A store that cannot answer is never a "no" (fail closed, like the boundary of phase 4).

REVOKE_URL = f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}"


def pause(store: OAuthStore, user: str = LOGIN_NAME) -> None:
    """The switch of one account, pulled the way ``/connections`` pulls it."""
    asyncio.run(store.set_access(user, disabled=True))


def break_switch(store: OAuthStore) -> None:
    """Make the one local read of the switch fail, and nothing else of the store."""

    async def refuse(_nc_user: str) -> bool:
        raise sqlite3.OperationalError("the switch could not be read")

    store.access_disabled = refuse  # type: ignore[method-assign]


@respx.mock
def test_a_paused_account_is_never_shown_its_app_password(
    client: TestClient, store: OAuthStore
) -> None:
    """Enforcement point 2: after the poll and after the identity check, before the result."""
    flow_id = start_a_flow(client)
    pause(store)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))

    response = result_of(client, flow_id)

    assert response.status_code == 403
    assert APP_PASSWORD not in response.text, "the credential is never rendered while paused"
    assert strings.CONNECTIONS_PAUSED_TITLE in response.text
    assert strings.SWITCH_OFF_STATE in response.text
    assert strings.SETTINGS_PLACE in response.text
    assert revoke.call_count == 1, "one attempt, and the app password is handed back"
    assert flow_ids(store) == [], "the spent flow is gone, so the poll is not repeated"


@respx.mock
def test_an_account_that_is_not_paused_still_reads_its_credential(
    client: TestClient, store: OAuthStore
) -> None:
    """The positive control of point 2: the check refuses one case and not the route."""
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))

    response = result_of(client, flow_id)

    assert response.status_code == 200
    assert APP_PASSWORD in response.text
    assert revoke.call_count == 0
    assert flow_ids(store) == []


@respx.mock
def test_a_switch_that_cannot_be_read_shows_no_credential(
    client: TestClient, store: OAuthStore
) -> None:
    """Fail closed (D-37): an unreadable switch is a page, never a rendered credential."""
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    revoke = respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))
    break_switch(store)

    response = result_of(client, flow_id)

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert APP_PASSWORD not in response.text
    assert revoke.call_count == 1, "the credential nobody will use goes back either way"


@respx.mock
def test_no_refusal_of_a_paused_account_writes_a_value_into_the_log(
    client: TestClient, store: OAuthStore, caplog: pytest.LogCaptureFixture
) -> None:
    """T-05-11: the new branch logs the rule, never the account, the credential or the flow."""
    flow_id = start_a_flow(client)
    pause(store)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    respx.delete(REVOKE_URL).mock(return_value=httpx.Response(200, json={}))

    with caplog.at_level(logging.DEBUG, logger="mcp_connector"):
        result_of(client, flow_id)

    assert LOGIN_NAME not in caplog.text
    assert APP_PASSWORD not in caplog.text
    assert POLL_TOKEN not in caplog.text
    assert flow_id not in caplog.text


def test_the_start_says_why_it_does_not_check_the_switch() -> None:
    """SC 4 of the plan: the reason stands in the code and not only in the backlog.

    ``_start`` opens a sign in for whoever asks, and at that moment there is no account to
    look up. A reader who finds no check there has to find the reason there too, or the gap
    looks like an oversight.
    """
    source = Path(connect.__file__).read_text(encoding="utf-8")
    marker = source.index("async def _start(")
    assert "not known" in source[marker : marker + 900]


@respx.mock
def test_a_deployment_without_a_provider_opens_one_store_and_sweeps_it_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """IN-02 of 05-REVIEW.md, first pass: the branch every deployment takes, measured.

    In the ExApp process nobody hands a store to this factory, so the opener is what runs:
    one store for the whole application, opened at the first request that needs it, swept
    exactly once. This branch carried a word for word copy of ``store.store_opener``, and
    the one check that walked it looked at the key read alone, so the sweep and the file it
    opens were nobody's assertion. It is the shared opener now, and this test says the
    shared one behaves the way this factory promised.
    """
    swept: list[str] = []
    original = OAuthStore.purge_expired

    async def counted(self: OAuthStore) -> None:
        swept.append(str(self.path))
        await original(self)

    async def key(env: object = None) -> bytes:
        del env
        return KEY

    monkeypatch.setattr(OAuthStore, "purge_expired", counted)
    monkeypatch.setattr(store_module.crypto, "data_key", key)
    env = {**ENV, config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}
    client = TestClient(Starlette(routes=connect.connect_routes(env, nextcloud=TARGET)))

    first = start_a_flow(client)
    second = start_a_flow(client)

    assert first != second, "two flows, so the store answered both requests"
    assert len(swept) == 1, "one open, one sweep, and no second store behind it"
    assert swept[0] == str(tmp_path / store_module.STORE_FILENAME)


def test_the_store_of_this_route_is_the_shared_opener() -> None:
    """The other half of IN-02: one implementation, not two that look alike.

    A second copy of the double checked locking, the key first rule and the sweep on first
    open is not a small duplication: it is a second place to fix whenever the first one
    changes, in a branch no test of this file walks.
    """
    source = Path(connect.__file__).read_text(encoding="utf-8")
    assert "store_opener(" in source, "the opener is called here"
    # The calls, not the prose: the docstring names all three, which is the point of it.
    assert "purge_expired()" not in source, "the sweep is the opener's business"
    assert "crypto.data_key(" not in source, "and so is the key"
    assert "asyncio.Lock()" not in source, "and so is the locking"


# --- WR-06: a ciphertext that cannot be read is a page, never a 500 -----------------------


@respx.mock
def test_a_flow_written_with_another_data_key_is_a_page(store: OAuthStore, tmp_path: Path) -> None:
    """WR-06: load_flow decrypts the poll token of the row, so a changed data key and a
    damaged blob both raise out of it. Unguarded that reached Starlette as a bare 500,
    while the docstring of the module says no rejection escapes as one."""
    flow_id = start_a_flow(TestClient(app_with(store)))
    stranger = OAuthStore(tmp_path / "oauth.sqlite3", bytes(range(32, 64)))
    client = TestClient(app_with(stranger))

    response = client.get(wait_url(flow_id))

    assert response.status_code == 500, "fail closed, and answered by us"
    assert strings.ERROR_GENERIC_TITLE in response.text
    assert "Traceback" not in response.text
    assert POLL_TOKEN not in response.text


# --- CR-02: the requests that cost a Nextcloud round trip are the ones that are counted ---


@respx.mock
def test_a_flood_of_successful_starts_ends_in_429(store: OAuthStore) -> None:
    """CR-02, SC 5: this is the path the throttle was built for, and it answers 200.

    Every one of these requests makes Nextcloud open a login flow: one PHP round trip and
    one record that lives for twenty minutes there. While only refusals were counted, none
    of them was ever counted at all, so the ceiling this module exists for was unreachable
    on the one route that named it in its own docstring.
    """
    counters = throttle_module.Throttle(ceiling=10_000, window=60)

    async def provide() -> OAuthStore:
        return store

    client = TestClient(
        Starlette(
            routes=connect.connect_routes(
                ENV, nextcloud=TARGET, store_provider=provide, throttle=counters
            )
        )
    )
    init = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))

    statuses = [
        client.post(
            connect.CONNECT_PATH, data={connect.ACTION_FIELD: connect.ACTION_START}
        ).status_code
        for _ in range(throttle_module.FLOW_LIMIT + 3)
    ]

    assert statuses[: throttle_module.FLOW_LIMIT] == [200] * throttle_module.FLOW_LIMIT
    assert set(statuses[throttle_module.FLOW_LIMIT :]) == {429}
    assert init.call_count == throttle_module.FLOW_LIMIT, (
        "a throttled request must not reach Nextcloud at all"
    )


@respx.mock
def test_the_throttled_start_does_not_close_the_waiting_screen(store: OAuthStore) -> None:
    """The waiting screen loads itself every three seconds by design, so it must not share
    the counter of the requests that open flows (CR-02, T-03-34)."""
    counters = throttle_module.Throttle(ceiling=10_000, window=60)

    async def provide() -> OAuthStore:
        return store

    client = TestClient(
        Starlette(
            routes=connect.connect_routes(
                ENV, nextcloud=TARGET, store_provider=provide, throttle=counters
            )
        )
    )
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
    respx.post(POLL_URL).mock(return_value=httpx.Response(404))
    flow_id = start_a_flow(client)

    for _ in range(throttle_module.FLOW_LIMIT + 3):
        client.post(connect.CONNECT_PATH, data={connect.ACTION_FIELD: connect.ACTION_START})

    assert client.get(wait_url(flow_id)).status_code == 200
    assert client.get(connect.CONNECT_PATH).status_code == 200


# --- CR-01: the credential goes to the account that signed in, or back to Nextcloud -------


@pytest.mark.parametrize(
    ("user", "case"),
    [(None, "no Nextcloud session at all"), ("mallory", "a different Nextcloud account")],
)
@respx.mock
def test_the_relay_attack_reads_no_app_password(
    client: TestClient, user: str | None, case: str
) -> None:
    """CR-01, the whole attack in one test.

    The attacker starts the sign in here, so they hold the flow id, which until this fix
    was the entire authorisation of this page. They send the victim nothing but Nextcloud's
    own sign in link; the victim signs in and grants access, and the attacker loads the
    waiting page. Every check before this one passes: the flow exists, it has not expired
    and the poll answers 200 with a credential. Only the browser is somebody else's, and
    the credential must not appear on it.
    """
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    revoke = respx.delete(f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )

    response = client.get(wait_url(flow_id)) if user is None else result_of(client, flow_id, user)

    assert response.status_code == 400, case
    assert APP_PASSWORD not in response.text
    assert LOGIN_NAME not in response.text, "not even who signed in"
    assert revoke.call_count == 1, "the credential nobody may read is handed back (D-34)"


@respx.mock
def test_a_forged_identity_header_reads_no_app_password(client: TestClient) -> None:
    """The header is signed with APP_SECRET, which the caller does not have (T-02-02)."""
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    respx.delete(f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )
    forged = base64.b64encode(f"{LOGIN_NAME}:not-the-app-secret".encode()).decode("ascii")

    response = client.get(
        wait_url(flow_id),
        headers={
            "EX-APP-ID": ENV[config.ENV_APP_ID],
            "EX-APP-VERSION": ENV[config.ENV_APP_VERSION],
            "AUTHORIZATION-APP-API": forged,
        },
    )

    assert response.status_code == 400
    assert APP_PASSWORD not in response.text


@respx.mock
def test_a_refused_result_ends_the_flow_so_the_poll_is_not_repeated(
    client: TestClient, store: OAuthStore
) -> None:
    """The 200 of a poll arrives exactly once, so a record that survived the refusal would
    leave a flow behind that can never finish, and one more page to try it on."""
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    respx.delete(f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )

    result_of(client, flow_id, "mallory")

    assert flow_ids(store) == []


@respx.mock
def test_no_secret_of_the_result_reaches_the_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """T-03-36: the one page that carries a credential must not repeat it in a record."""
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))

    with caplog.at_level(logging.DEBUG, logger="mcp_connector"):
        result_of(client, flow_id)

    assert APP_PASSWORD not in caplog.text
    assert POLL_TOKEN not in caplog.text
    assert flow_id not in caplog.text


# --- the failure paths --------------------------------------------------------------------


def test_an_unknown_flow_is_the_expired_page(client: TestClient) -> None:
    response = client.get(wait_url("not-a-flow-that-exists"))

    assert response.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in response.text


def test_a_request_without_a_flow_is_the_expired_page(client: TestClient) -> None:
    response = client.get(connect.WAIT_PATH)

    assert response.status_code == 400
    assert strings.ERROR_EXPIRED_TITLE in response.text


def test_a_sign_in_that_ran_out_of_time_is_the_timeout_page(
    client: TestClient, store: OAuthStore
) -> None:
    """Never an endless refresh: the deadline is ours, because Nextcloud answers 404 for
    "not yet" and for "expired" alike (pitfall 7)."""
    long_ago = int(time.time()) - FLOW_TTL - 10
    asyncio.run(store.save_client(connect.CONNECT_CLIENT_ID, metadata_json="{}", allowed=False))
    asyncio.run(
        store.create_flow(
            "an-old-flow",
            client_id=connect.CONNECT_CLIENT_ID,
            redirect_uri="",
            redirect_uri_explicit=False,
            code_challenge="",
            state=None,
            scopes="",
            resource="",
            poll_token=POLL_TOKEN,
            now=long_ago,
        )
    )

    with respx.mock:
        poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))
        response = client.get(wait_url("an-old-flow"))

        assert poll.call_count == 0, "an expired flow must not produce another poll"

    assert response.status_code == 408
    assert strings.ERROR_TIMEOUT_TITLE in response.text


@respx.mock
def test_a_nextcloud_that_cannot_be_reached_is_the_generic_page(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(side_effect=httpx.ConnectError("no route"))

    with caplog.at_level(logging.ERROR, logger="mcp_connector"):
        response = client.get(wait_url(flow_id))

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text
    reference = re.search(r"reference ([A-Z2-9]{8})", response.text)
    assert reference is not None, response.text
    assert reference.group(1) in caplog.text


@respx.mock
def test_the_cancellation_removes_the_running_flow(client: TestClient, store: OAuthStore) -> None:
    flow_id = start_a_flow(client)

    response = client.post(
        connect.CONNECT_PATH,
        data={connect.ACTION_FIELD: connect.ACTION_CANCEL, connect.FLOW_PARAM: flow_id},
    )

    assert response.status_code == 200
    assert flow_ids(store) == []
    assert client.get(wait_url(flow_id)).status_code == 400


# --- what none of these pages does (T-03-30) -----------------------------------------------


@respx.mock
def test_no_page_of_this_route_asks_for_anything(client: TestClient) -> None:
    """Not one visible input on the whole path, so a page that asks is not ours."""
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(404))
    pages = [
        client.get(connect.CONNECT_PATH).text,
        client.get(wait_url(flow_id)).text,
        client.get(wait_url("unknown")).text,
    ]

    for markup in pages:
        for control in controls(markup):
            assert control["tag"] == "input", control
            assert control.get("type") == "hidden", control


def test_the_ui_package_carries_no_credential_input_at_all() -> None:
    """A source gate, so a later page cannot grow one without this test going red."""
    for path in sorted(UI_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for forbidden in ('type="password"', 'type="email"', 'type="text"'):
            assert forbidden not in text, f"{path.name} carries {forbidden}"


@respx.mock
def test_every_answer_of_this_route_carries_the_security_headers(client: TestClient) -> None:
    flow_id = start_a_flow(client)
    respx.post(POLL_URL).mock(return_value=httpx.Response(404))
    answers = [
        client.get(connect.CONNECT_PATH),
        client.get(wait_url(flow_id)),
        client.get(wait_url("unknown")),
    ]

    for response in answers:
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-frame-options"] == "DENY"
        assert "default-src 'none'" in response.headers["content-security-policy"]


def test_the_pages_do_not_imitate_nextcloud(client: TestClient) -> None:
    """A page that looks like Nextcloud teaches the wrong lesson (03-UI-SPEC, Color)."""
    text = client.get(connect.CONNECT_PATH).text

    assert "0082C9" not in text.upper()
    assert strings.FOOTER_PASSWORD_PROMPT in text


# --- wiring ---------------------------------------------------------------------------------


def test_the_exapp_application_serves_the_onboarding_and_the_http_mode_does_not() -> None:
    """D-23: the standalone HTTP server of phase 1 stays exactly as it was."""
    exapp = {getattr(route, "path", "") for route in build_exapp_app(ENV).router.routes}
    standalone = {getattr(route, "path", "") for route in entry_http.build_app({}).router.routes}

    assert {connect.CONNECT_PATH, connect.WAIT_PATH} <= exapp
    assert not {connect.CONNECT_PATH, connect.WAIT_PATH} & standalone


def test_the_default_store_is_opened_once_and_purged_at_the_first_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The process wide store and the purge at the first use are wired here (T-03-17).

    The key read is patched in ``oauth.store``, which is where the opener this route calls
    reads it (IN-02). It used to be patched through ``connect.crypto``, the same module
    object under a second name, and that name is gone with the copy.
    """
    opened: list[str] = []

    async def fake_key(env: object = None) -> bytes:
        opened.append("key")
        return KEY

    monkeypatch.setattr(store_module.crypto, "data_key", fake_key)
    env = ENV | {config.ENV_APP_PERSISTENT_STORAGE: str(tmp_path)}
    client = TestClient(Starlette(routes=connect.connect_routes(env, nextcloud=TARGET)))

    first = client.get(wait_url("unknown"))
    second = client.get(wait_url("unknown"))

    assert first.status_code == 400
    assert second.status_code == 400
    assert opened == ["key"], "the store is opened once per application, not per request"
    assert (tmp_path / "oauth.sqlite3").is_file()


def test_a_store_that_cannot_be_opened_is_the_generic_page() -> None:
    """Fail closed (D-37): no deploy environment, no store, and a named page, not a 500."""
    client = TestClient(
        Starlette(
            routes=connect.connect_routes({config.ENV_PUBLIC_URL: PUBLIC_URL}, nextcloud=TARGET)
        )
    )

    response = client.get(wait_url("anything"))

    assert response.status_code == 500
    assert strings.ERROR_GENERIC_TITLE in response.text


def test_the_flow_id_is_drawn_from_the_secure_generator() -> None:
    source = Path(connect.__file__).read_text(encoding="utf-8")

    assert "secrets.token_urlsafe" in source
    assert "import random" not in source


def test_the_onboarding_stores_no_credential_anywhere_in_its_source() -> None:
    """The result is rendered and dropped: no authorization row on this path."""
    source = Path(connect.__file__).read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if "#" not in line)

    assert "create_authorization" not in code


def test_the_factory_returns_the_three_declared_routes() -> None:
    routes = connect.connect_routes(ENV, nextcloud=TARGET)

    assert [getattr(route, "path", "") for route in routes] == [
        connect.CONNECT_PATH,
        connect.CONNECT_PATH,
        connect.WAIT_PATH,
    ]


@respx.mock
def test_the_onboarding_opens_its_flow_at_the_injected_target(store: OAuthStore) -> None:
    """Standalone OAuth, slice 2: the environment still names BASE_URL, the routes do not."""
    injected = "https://nc.injected.example"

    async def provider() -> OAuthStore:
        return store

    client = TestClient(
        Starlette(
            routes=connect.connect_routes(
                ENV, nextcloud=NextcloudTarget.from_url(injected), store_provider=provider
            )
        )
    )
    environment_init = respx.post(INIT_URL).mock(
        return_value=httpx.Response(200, json=start_body())
    )
    injected_init = respx.post(f"{injected}{loginflow.INIT_PATH}").mock(
        return_value=httpx.Response(200, json=start_body())
    )

    response = client.post(connect.CONNECT_PATH, data={connect.ACTION_FIELD: connect.ACTION_START})

    assert response.status_code == 200, response.text
    assert (injected_init.call_count, environment_init.call_count) == (1, 0)

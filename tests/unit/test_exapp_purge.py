"""``occ mcp_connector:purge``: the action that makes success criterion 2 reachable.

The Remove button of Nextcloud 34 does not uninstall an ExApp. It calls ``disableExApp()``,
so the container stops, the volume stays, and every Nextcloud app password this connector
created for a connection keeps working in ``oc_authtoken``. This module is the answer to
that measurement, and this file is its criteria catalogue.

Threats covered here, in the order of the plan:

* **T-05-26** the handler reached through the PHP proxy: ``x-origin-ip`` is 404, a request
  without the AppAPI headers is 401, ``force`` is checked in the handler itself, and the
  path appears in no ``<route>`` of ``appinfo/info.xml``.
* **T-05-27** app passwords left behind: every authorization is handed back, the revoked
  ones included, before anything is deleted.
* **T-05-28** cleaning up on the wrong hook: ``enabled=0`` purges nothing, because an
  update fires that hook too.
* **T-05-29** an answer or a log line that names an account or a credential.
* **T-05-30** the order: the data key is deleted last, after every revocation.
* **T-05-31** one hanging revocation stopping the whole purge.
* **T-05-57** the destructive local half running although not a single app password could
  be handed back (WR-01 of 05-REVIEW.md).
* **T-05-58** a flag shape nobody sends arming the instance wide deletion (WR-02).
* **T-18-22** the audit log next to the store: the purge leaves it standing, and these
  cases hold that claim. It is not a change of the clean up logic, it is a property the
  existing handler already has and that nobody checked, and a claim nobody checks falls
  silently at the next rebuild (D-v1.5-01, 18-RESEARCH.md section 11).

Every Nextcloud answer comes from respx and the store is a real SQLite file in
``tmp_path``: what is under test is the order of two outgoing calls and the state of that
file afterwards, which no mock of the store could show.
"""

import asyncio
import base64
import json
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from lxml import etree
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.audit import store as audit
from mcp_connector.exapp import admin_settings, audit_verify, lifecycle, occ, purge, settings_form
from mcp_connector.exapp.target import exapp_target
from mcp_connector.nextcloud.clients.xml import hardened_parser
from mcp_connector.oauth import crypto, loginflow
from mcp_connector.oauth.store import OAuthStore

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
BASE_URL = "http://nc.test"
PUBLIC_URL = "https://cloud.example.com/exapps/mcp_connector"

#: A key that is not secret, because it never leaves this file.
KEY = bytes(range(32))

ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_AA_VERSION: "34.0.3",
    config.ENV_NEXTCLOUD_URL: BASE_URL,
    config.ENV_PUBLIC_URL: PUBLIC_URL,
}

PASSWORD_URL = f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}"
CONFIG_URL = f"{BASE_URL}{crypto.EXAPP_CONFIG_PATH}"
OCC_URL = f"{BASE_URL}{occ.OCC_COMMAND_PATH}"
SETTINGS_URL = f"{BASE_URL}{settings_form.SETTINGS_PATH}"

CLIENT_ID = "client-4711"
CLIENT_NAME = "Claude"

#: Two connections of two accounts, with app passwords a leak test can search for.
CONNECTIONS = (
    ("auth-of-alice", "alice", "app-password-of-alice"),
    ("auth-of-bob", "bob", "app-password-of-bob"),
)

TABLES = (
    "access_tokens",
    "refresh_tokens",
    "auth_codes",
    "flows",
    "authorizations",
    "clients",
    "user_access",
)

MANIFEST = Path(__file__).resolve().parents[2] / "appinfo" / "info.xml"


def appapi_headers(user: str = "", secret: str = APP_SECRET) -> dict[str, str]:
    """What AppAPI puts on an internal call. The user is empty: this is the app context."""
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


class Deployment:
    """One process of this application with its own store file and the purge route on it.

    Since plan 18-10 there is a second file in the same directory: the audit log of D-01
    lives next to the OAuth store, and the cases at the end of this file read it the way
    :meth:`counts` reads the tables, with a connection of their own.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / "oauth.sqlite3"
        self.store = OAuthStore(self.path, KEY)
        self.audit_path = tmp_path / audit.AUDIT_FILENAME
        self.audit = audit.AuditStore(self.audit_path)
        self.client = TestClient(
            Starlette(
                routes=purge.purge_routes(
                    ENV, nextcloud=exapp_target(ENV), store_provider=self._open
                )
            )
        )

    async def _open(self) -> OAuthStore:
        return self.store

    def seed(self, *, revoked: tuple[str, ...] = ()) -> None:
        asyncio.run(self._seed(revoked))

    async def _seed(self, revoked: tuple[str, ...]) -> None:
        await self.store.save_client(
            CLIENT_ID, metadata_json=json.dumps({"client_name": CLIENT_NAME})
        )
        for auth_id, nc_user, password in CONNECTIONS:
            await self.store.create_authorization(
                auth_id,
                client_id=CLIENT_ID,
                nc_user=nc_user,
                nc_account_id=nc_user,
                app_password=password,
                scopes="nextcloud",
                resource=f"{PUBLIC_URL}/mcp",
            )
            await self.store.create_refresh_token(
                f"refresh-{auth_id}", auth_id=auth_id, family_id=f"family-{auth_id}"
            )
        await self.store.set_access("alice", disabled=True)
        for auth_id in revoked:
            await self.store.revoke_authorization(auth_id)

    #: How many audit rows :meth:`note` writes: one per moment and connection.
    AUDIT_ROWS = 6

    def note(self, moments: tuple[int, ...] = (1000, 1001, 1002)) -> None:
        """Write a few audit rows next to the OAuth store, before a purge runs.

        Through :meth:`AuditStore.append` and never with an own ``INSERT``: what the cases
        below claim is that real chains stand afterwards, and a row written past the store
        would carry no chain at all.
        """
        asyncio.run(self._note(moments))

    async def _note(self, moments: tuple[int, ...]) -> None:
        for at in moments:
            for auth_id, nc_user, _password in CONNECTIONS:
                await self.audit.append(
                    audit.Entry(
                        chain=audit.user_chain(nc_user),
                        at=at,
                        nc_user=nc_user,
                        tool="files_search",
                        client_id=CLIENT_ID,
                        auth_id=auth_id,
                        client_name=CLIENT_NAME,
                        outcome=audit.OUTCOME_OK,
                        params=["query"],
                    )
                )

    def audit_rows(self) -> list[tuple[Any, ...]]:
        """Every row of the audit file, read behind the store's back.

        The same way :meth:`counts` reads the tables: what is under test is the state of a
        file after a handler ran, and a store method could open the file, find it missing and
        create it again, which would hide exactly the loss this asks about.
        """
        conn = sqlite3.connect(self.audit_path)
        try:
            return list(conn.execute("SELECT * FROM entries ORDER BY seq"))
        finally:
            conn.close()

    def counts(self) -> dict[str, int]:
        """The row count of every table, read out of the file behind the store's back."""
        conn = sqlite3.connect(self.path)
        try:
            found: dict[str, int] = {}
            for table in TABLES:
                statement = "SELECT COUNT(*) FROM " + table  # noqa: S608 - a literal name
                found[table] = conn.execute(statement).fetchone()[0]
            return found
        finally:
            conn.close()


@pytest.fixture
def live(tmp_path: Path) -> Deployment:
    """A deployment with two connections, one paused account and two refresh tokens."""
    deployment = Deployment(tmp_path)
    deployment.seed()
    return deployment


@pytest.fixture
def destructive(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A spy on the two destructive steps, so "it did not run" is an assertion.

    The row counts below show the same thing from the outside, but only for the tables. The
    data key lives in Nextcloud, so an untouched key is otherwise a missing respx call, and
    a missing call is also what a wrong URL looks like (WR-01, T-05-57).
    """
    seen: list[str] = []

    async def empty(store: OAuthStore) -> bool:
        seen.append("empty")
        return True

    async def delete(env: object = None) -> bool:
        seen.append("key")
        return True

    monkeypatch.setattr(purge, "_empty", empty)
    monkeypatch.setattr(crypto, "delete_key", delete)
    return seen


def call(
    deployment: Deployment,
    *,
    force: bool = True,
    body: object | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """One occ invocation, as AppAPI delivers it: a POST with the options in the body.

    ``Any`` for the reason ``tests/unit/test_oauth_abuse.py`` gives: the test client of
    Starlette answers with the response type of ``httpx2``, the fork the MCP SDK brings, and
    the outgoing calls of this app use ``httpx``. Naming either type here is a false claim.
    """
    payload = body if body is not None else {"options": {purge.FORCE_OPTION: True} if force else {}}
    sent = appapi_headers() if headers is None else headers
    return deployment.client.post(purge.PURGE_PATH, json=payload, headers=sent)


class Wire:
    """Both outgoing calls of the purge, with the order they happened in."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def install(self, *, password: int = 200, config_status: int = 200) -> None:
        def revoked(request: httpx.Request) -> httpx.Response:
            self.seen.append("password")
            return httpx.Response(password)

        def deleted(request: httpx.Request) -> httpx.Response:
            self.seen.append("key")
            return httpx.Response(config_status, json={})

        respx.delete(PASSWORD_URL).mock(side_effect=revoked)
        respx.delete(CONFIG_URL).mock(side_effect=deleted)


# --- the boundary: T-05-26 ----------------------------------------------------------


def test_a_request_through_the_php_proxy_is_not_served(live: Deployment) -> None:
    """Pitfall 13: the PHP proxy attaches valid AppAPI headers itself, so its own marker
    is the only thing that tells this handler the request came through it."""
    headers = appapi_headers() | {"x-origin-ip": "203.0.113.7"}
    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(live, headers=headers)

    assert response.status_code == 404
    assert wire.seen == [], "a proxied request reaches no Nextcloud call"
    assert live.counts()["authorizations"] == len(CONNECTIONS)


def test_a_request_without_appapi_headers_is_401_without_detail(live: Deployment) -> None:
    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(live, headers={})

    assert response.status_code == 401
    assert response.json() == {}
    assert APP_SECRET not in response.text
    assert wire.seen == []
    assert live.counts()["authorizations"] == len(CONNECTIONS)


def test_a_request_with_a_wrong_app_secret_is_401(live: Deployment) -> None:
    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(live, headers=appapi_headers(secret="wrong"))

    assert response.status_code == 401
    assert wire.seen == []
    assert live.counts()["authorizations"] == len(CONNECTIONS)


def test_the_proxy_marker_is_the_same_header_the_lifecycle_routes_refuse() -> None:
    """The header is spelled in three modules, so this is where all three are held equal.

    ``exapp/lifecycle.py`` imports ``exapp/occ.py``, which imports ``exapp/purge.py`` and
    ``exapp/audit_verify.py``, so an import back would close a cycle. The duplicate string is
    the price and this assertion is the guard: a rename in one module without the others
    would leave the purge or the audit check open to the PHP proxy path (T-05-26, T-18-07).
    """
    assert purge.HEADER_ORIGIN_IP == lifecycle.HEADER_ORIGIN_IP
    assert purge.HEADER_ORIGIN_IP == audit_verify.HEADER_ORIGIN_IP


def test_the_handler_path_is_declared_in_no_route_of_the_manifest() -> None:
    """T-02-20 and pitfall 13: a declared route would publish an instance wide deletion.

    The manifest still carries exactly the thirteen routes of this phase, and none of them
    matches the purge path in any spelling.
    """
    root = etree.parse(str(MANIFEST), hardened_parser()).getroot()
    urls = [(element.text or "").strip() for element in root.iter("url")]

    assert len(urls) == 13, urls
    bare = purge.PURGE_PATH.strip("/")
    for url in urls:
        assert bare not in url, f"{url} would make the purge reachable from the internet"


def test_every_answer_carries_no_store(live: Deployment) -> None:
    """T-02-07: the PHP proxy caches a JSON answer for 3600 seconds without this header."""
    with respx.mock:
        Wire().install()
        answers = [
            call(live, headers={}),
            call(live, headers=appapi_headers() | {"x-origin-ip": "203.0.113.7"}),
            call(live, force=False),
        ]

    for answer in answers:
        assert answer.headers["cache-control"] == "no-store"


# --- the force option, checked in the handler itself --------------------------------


def test_without_force_the_purge_does_nothing(live: Deployment) -> None:
    """What AppAPI hands over is input. The option is declared there and checked here."""
    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(live, force=False)

    assert response.status_code == 200
    assert response.json()["purged"] is False
    assert response.json()["hint"], "the answer says how to really run it"
    assert wire.seen == []
    assert live.counts() == before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"options": {}},
        {"options": {"force": False}},
        {"options": {"force": "no"}},
        {"force": "off"},
        {"options": ["dry-run"]},
        "not an object at all",
        [1, 2, 3],
        {"occ": {"arguments": None, "options": {"force": False}}},
        {"occ": {"arguments": None, "options": None}},
        {"occ": "not an object either"},
        {"occ": {"options": {"force": "maybe"}}},
        {"occ": {"options": {"force": ""}}},
        {"options": {"force": "vielleicht"}},
        {"options": {"force": 0}},
        {"options": {"force": 2}},
        {"options": {"force": -1}},
        {"options": {"force": 0.5}},
    ],
    ids=[
        "an empty body",
        "no option",
        "the flag as false",
        "the word no",
        "the word off",
        "another option",
        "a string",
        "a list",
        "the measured envelope with the flag unset",
        "the measured envelope of a call without options",
        "an envelope that is not an object",
        "a word nobody understands",
        "an empty value",
        "a word in another language",
        "a zero",
        "the number two",
        "a negative number",
        "a fraction",
    ],
)
def test_a_body_without_the_force_flag_changes_nothing(live: Deployment, body: object) -> None:
    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(live, body=body)

    assert response.json()["purged"] is False
    assert wire.seen == []
    assert live.counts() == before


@pytest.mark.parametrize(
    "body",
    [
        {"options": {"force": True}},
        {"options": {"force": "1"}},
        {"options": {"force": 1}},
        {"options": {"force": None}},
        {"options": ["force"]},
        {"options": ["--force"]},
        {"force": True},
        {"occ": {"arguments": None, "options": {"force": True}}},
        {"occ": {"options": {"force": True}}},
    ],
    ids=[
        "the flag as true",
        "the flag as a one",
        "the flag as the number one",
        "the flag without a value",
        "a list of option names",
        "a list with the dashes",
        "at the top level",
        "the measured shape of AppAPI 34.0.0",
        "the same envelope without arguments",
    ],
)
def test_every_shape_of_the_flag_appapi_may_send_is_accepted(
    live: Deployment, body: object
) -> None:
    """The wire shape of the option was Assumption A5 until plan 05-08 measured it.

    The first two ids of the envelope cases are that measurement: ``{"occ": {"arguments":
    null, "options": {"force": true}}}`` is what AppAPI 34.0.0 really sent, and a live
    ``occ mcp_connector:purge --force`` answered ``purged: false`` before this shape was
    accepted. Every entry in this list stays accepted after WR-02 narrowed the value side
    to a positive list, so this test is the regression guard against exactly that finding.
    """
    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(live, body=body)

    assert response.json()["purged"] is True
    assert wire.seen.count("password") == len(CONNECTIONS)


def test_a_value_nobody_understands_is_not_a_yes_and_says_so_once(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """WR-02: the fail closed rule of ``registry._switch``, on the destructive action.

    ``Only a spelled out no is a no`` inverted that rule for the one command that cannot be
    undone. A word this handler does not know is a typo, and a typo is not a security
    switch, so it changes nothing and leaves one line behind that explains why.
    """
    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install()
        with caplog.at_level(logging.DEBUG):
            response = call(live, body={"occ": {"options": {purge.FORCE_OPTION: "maybe"}}})

    assert response.json()["purged"] is False
    assert wire.seen == []
    assert live.counts() == before
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "maybe" not in logged, "the value itself stays out of the log"
    assert [record for record in caplog.records if record.levelno >= logging.WARNING]


@pytest.mark.parametrize(
    "number", [2, -1, 0.5], ids=["the number two", "a negative number", "a fraction"]
)
def test_a_number_other_than_one_is_not_a_yes_and_says_so_once(
    live: Deployment, caplog: pytest.LogCaptureFixture, number: object
) -> None:
    """WR-01 of the re-review: the positive list of WR-02 holds for JSON numbers as well.

    Before this test the string ``"2"`` was a no with a warning while the number ``2`` armed
    the one action of this app that cannot be undone. A number this handler does not know is
    the same typo an unknown word is: it changes nothing and leaves exactly one line behind.
    """
    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install()
        with caplog.at_level(logging.DEBUG):
            response = call(live, body={"occ": {"options": {purge.FORCE_OPTION: number}}})

    assert response.json()["purged"] is False
    assert wire.seen == []
    assert live.counts() == before
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1, "exactly one line, the same one an unknown word leaves"


def test_a_spelled_out_no_needs_no_log_line(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """The counter check of the test above: ``false`` is a decision, not a typo."""
    with respx.mock:
        Wire().install()
        with caplog.at_level(logging.DEBUG):
            response = call(live, body={"occ": {"options": {purge.FORCE_OPTION: "false"}}})

    assert response.json()["purged"] is False
    assert [record for record in caplog.records if record.levelno >= logging.WARNING] == []


@pytest.mark.parametrize("query", ["?force=1", "?force=true", "?force="])
def test_the_flag_in_the_query_string_runs_nothing(live: Deployment, query: str) -> None:
    """WR-02: the measured invocation carries the flag in the JSON body and nowhere else.

    ``AppAPIService::prepareRequestToExApp`` puts the parameters of a POST into the body,
    and this route is POST only, so a query parameter is a shape AppAPI never produces.
    Every additional accepted shape is attack surface for the day one of the three barriers
    in front of this handler falls.
    """
    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install()
        response = live.client.post(f"{purge.PURGE_PATH}{query}", json={}, headers=appapi_headers())

    assert response.json()["purged"] is False
    assert wire.seen == []
    assert live.counts() == before


# --- the body this handler is willing to read (IN-01) ------------------------------

#: One POST at this route, as ASGI hands it over: the scope of the two tests that measure
#: the reader itself instead of going through the test client.
_SCOPE: dict[str, Any] = {
    "type": "http",
    "http_version": "1.1",
    "method": "POST",
    "path": purge.PURGE_PATH,
    "raw_path": purge.PURGE_PATH.encode(),
    "query_string": b"",
    "root_path": "",
    "scheme": "http",
    "headers": [(b"content-type", b"application/json")],
    "client": ("127.0.0.1", 1234),
    "server": ("testserver", 80),
}


def test_an_announced_body_above_the_limit_is_not_parsed(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """The header half of the schranke: a length nobody needs is not an occ invocation."""
    before = live.counts()
    padded = {"options": {purge.FORCE_OPTION: True}, "pad": "a" * (purge.MAX_BODY_BYTES + 1)}
    with respx.mock:
        wire = Wire()
        wire.install()
        with caplog.at_level(logging.DEBUG):
            response = call(live, body=padded)

    assert response.json()["purged"] is False
    assert wire.seen == []
    assert live.counts() == before
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "aaaa" not in logged, "the body itself stays out of the log"


def test_a_chunked_body_above_the_limit_does_not_arm_the_purge(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """IN-01: the schranke holds without a ``Content-Length`` to trust.

    A request with ``Transfer-Encoding: chunked`` announces no length at all, so the header
    check never fires for it. Until this test the handler then read whatever arrived into
    memory, and a valid ``force`` flag hidden in half a megabyte armed the one action of
    this app that cannot be undone. What the reader takes off the wire is measured one test
    below; this one is the outcome an administrator would have seen.
    """

    def in_chunks() -> Iterator[bytes]:
        yield b'{"options": {"' + purge.FORCE_OPTION.encode() + b'": true}, "pad": "'
        for _ in range(512):
            yield b"a" * 1024
        yield b'"}'

    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install()
        with caplog.at_level(logging.DEBUG):
            response = live.client.post(
                purge.PURGE_PATH,
                content=in_chunks(),
                headers=appapi_headers() | {"content-type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json()["purged"] is False, "a body this handler does not read is no flag"
    assert wire.seen == []
    assert live.counts() == before
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1, "exactly one line, the same shape the announced case leaves"
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "aaaa" not in logged, "the body itself stays out of the log"


def test_the_body_reader_stops_at_the_limit_instead_of_draining_the_stream() -> None:
    """The other half of IN-01, and the reason it is measured below the test client.

    The test client of Starlette reads a generator body into memory itself before the app
    ever runs (``httpx.Request.read`` in ``testclient.receive``), so nothing counted up
    there says anything about this application. This test hands the reader an ASGI
    ``receive`` of its own and counts what the reader asks for: no more than one chunk
    beyond the limit, and never the rest of a stream that has half a megabyte left in it.
    """
    handed_over: list[int] = []
    chunk = b"a" * 1024

    async def receive() -> dict[str, Any]:
        if len(handed_over) >= 512:  # pragma: no cover - reached only by a draining reader
            return {"type": "http.request", "body": b"", "more_body": False}
        handed_over.append(len(chunk))
        return {"type": "http.request", "body": chunk, "more_body": True}

    payload = asyncio.run(purge._payload(Request(_SCOPE, receive)))

    assert payload is None, "a body above the limit is not parsed at all"
    assert sum(handed_over) <= purge.MAX_BODY_BYTES + len(chunk), (
        "the reader stops at the limit instead of taking the whole stream into memory"
    )


def test_a_chunked_body_below_the_limit_still_arms_the_purge(live: Deployment) -> None:
    """The counter check: the schranke bounds the read, it does not refuse chunked bodies.

    Nothing measured says AppAPI sends the invocation in one piece, so a small body that
    arrives in several chunks has to keep working exactly as the announced one does.
    """

    def in_chunks() -> Iterator[bytes]:
        yield b'{"occ": {"arguments": null, "options": {"'
        yield purge.FORCE_OPTION.encode() + b'": true'
        yield b"}}}"

    with respx.mock:
        wire = Wire()
        wire.install()
        response = live.client.post(
            purge.PURGE_PATH,
            content=in_chunks(),
            headers=appapi_headers() | {"content-type": "application/json"},
        )

    assert response.json()["purged"] is True
    assert wire.seen.count("password") == len(CONNECTIONS)


def test_a_chunked_body_at_the_limit_is_still_read(live: Deployment) -> None:
    """The edge of the schranke: exactly ``MAX_BODY_BYTES`` is inside, not outside."""
    body = json.dumps({"options": {purge.FORCE_OPTION: True}, "pad": ""}).encode()
    padding = purge.MAX_BODY_BYTES - len(body)
    assert padding > 0
    exact = json.dumps({"options": {purge.FORCE_OPTION: True}, "pad": "a" * padding}).encode()
    assert len(exact) == purge.MAX_BODY_BYTES

    def in_chunks() -> Iterator[bytes]:
        for start in range(0, len(exact), 1024):
            yield exact[start : start + 1024]

    with respx.mock:
        wire = Wire()
        wire.install()
        response = live.client.post(
            purge.PURGE_PATH,
            content=in_chunks(),
            headers=appapi_headers() | {"content-type": "application/json"},
        )

    assert response.json()["purged"] is True
    assert wire.seen.count("password") == len(CONNECTIONS)


def test_a_body_that_cannot_be_read_is_no_flag(caplog: pytest.LogCaptureFixture) -> None:
    """A stream that breaks mid body is not an occ invocation either.

    Measured at the reader for the same reason as the test above: the test client reads the
    body itself, so a sender that breaks never reaches this application through it.
    """

    async def breaks() -> dict[str, Any]:
        raise RuntimeError("the connection went away")

    with caplog.at_level(logging.DEBUG):
        payload = asyncio.run(purge._payload(Request(_SCOPE, breaks)))

    assert payload is None
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert "the connection went away" not in warnings[0].getMessage()


# --- the purge itself, and its order (T-05-27, T-05-30) ----------------------------


def test_the_purge_revokes_every_app_password_then_empties_the_store(live: Deployment) -> None:
    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(live)

    body = response.json()
    assert response.status_code == 200
    assert body["purged"] is True
    assert body["connections"] == len(CONNECTIONS)
    assert body["revoked"] == len(CONNECTIONS)
    assert body["revoke_failures"] == 0
    assert body["tables_cleared"] is True
    assert body["key_deleted"] is True
    assert live.counts() == dict.fromkeys(TABLES, 0)


def test_every_revocation_happens_before_the_data_key_is_deleted(live: Deployment) -> None:
    """T-05-30: the key is in Nextcloud, the ciphertexts are in the volume.

    Whoever deletes the key first can decrypt nothing afterwards, so no app password can be
    handed back any more. The order is therefore an assertion and not a convention.
    """
    with respx.mock:
        wire = Wire()
        wire.install()
        call(live)

    assert wire.seen == ["password", "password", "key"]


def test_a_revoked_connection_is_purged_too(tmp_path: Path) -> None:
    """T-05-27: revoking marks our own row, the credential in Nextcloud lives on."""
    deployment = Deployment(tmp_path)
    deployment.seed(revoked=("auth-of-alice",))

    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(deployment)

    assert response.json()["connections"] == len(CONNECTIONS)
    assert wire.seen.count("password") == len(CONNECTIONS)


def test_the_paused_account_row_goes_with_it(live: Deployment) -> None:
    """``user_access`` hangs on no cascade, so a purge that forgets it leaves a row."""
    assert live.counts()["user_access"] == 1

    with respx.mock:
        Wire().install()
        call(live)

    assert live.counts()["user_access"] == 0


# --- the audit log next to the store: D-v1.5-01 and T-18-22 ------------------------
# ``exapp/purge.py`` does not change for any of these four cases, and that is the point:
# the purge hands app passwords back, empties seven tables and deletes the data key, and
# none of the three touches a second file in the same directory. Survival is a property of
# the existing handler and not a special case built for the audit log. The measured
# grounds are in 18-RESEARCH.md section 11.


def test_the_purge_leaves_every_row_of_the_audit_log_where_it_is(live: Deployment) -> None:
    live.note()
    before = live.audit_rows()
    assert len(before) == Deployment.AUDIT_ROWS, "or this case measures an empty file"

    with respx.mock:
        Wire().install()
        response = call(live)

    assert response.json()["purged"] is True
    assert live.audit_path.exists()
    assert live.audit_rows() == before, "same count, same rows, byte for byte"


def test_the_chains_of_the_audit_log_are_unbroken_after_the_purge(live: Deployment) -> None:
    """A file that is still there says little; an unbroken chain says the rows are untouched.

    The row count is asserted first and on purpose: :meth:`AuditStore.verify_chains` opens the
    file, creates the schema if it is gone and finds nothing to complain about, so an empty
    list alone is also what a deleted log looks like. Reading the rows behind the store's back
    is the half of this case that can fail.
    """
    live.note()

    with respx.mock:
        Wire().install()
        call(live)

    assert len(live.audit_rows()) == Deployment.AUDIT_ROWS
    assert asyncio.run(live.audit.verify_chains()) == []


def test_the_purge_empties_every_oauth_table_and_keeps_the_audit_rows(live: Deployment) -> None:
    """Both halves in one case: everything else goes, and the log stays."""
    live.note()

    with respx.mock:
        wire = Wire()
        wire.install()
        body = call(live).json()

    assert body["tables_cleared"] is True
    assert body["key_deleted"] is True
    assert wire.seen == ["password", "password", "key"]
    assert live.counts() == dict.fromkeys(TABLES, 0)
    assert len(live.audit_rows()) == Deployment.AUDIT_ROWS


def test_the_audit_log_is_still_readable_after_the_data_key_was_deleted(
    live: Deployment,
) -> None:
    """The log carries no secret (D-06), so it is not encrypted with the key the purge deletes.

    Were it encrypted with that key, every row would still be in the file after the purge and
    not one of them could be read again, which would satisfy a case that only counts rows.
    """
    live.note()

    with respx.mock:
        Wire().install()
        assert call(live).json()["key_deleted"] is True

    tools = [row[6] for row in live.audit_rows()]
    assert tools == ["files_search"] * Deployment.AUDIT_ROWS, "plain text, no key needed"

    entry = asyncio.run(live.audit.last_entry(audit.user_chain("alice")))
    assert entry is not None
    assert entry.tool == "files_search"
    assert entry.nc_user == "alice"


def test_a_failed_revocation_does_not_stop_the_loop_and_is_a_number(
    live: Deployment, destructive: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    """T-05-31 and T-05-57: every row is attempted, and a total failure ends it there.

    Until WR-01 of 05-REVIEW.md this test pinned the opposite: the tables were emptied and
    the data key deleted although not one app password had been handed back. That state is
    the catastrophe of pattern 4 in 05-RESEARCH.md, because the tables are the only record
    of which app password belongs to which connection, while every one of those credentials
    stays valid in Nextcloud. A run that reaches nothing is a fault of the connection and
    not of a single row, so it changes nothing and stays repeatable.
    """
    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install(password=500)
        with caplog.at_level(logging.DEBUG):
            response = call(live)

    body = response.json()
    assert wire.seen.count("password") == len(CONNECTIONS), "every row was still attempted"
    assert body["purged"] is False
    assert body["connections"] == len(CONNECTIONS)
    assert body["revoked"] == 0
    assert body["revoke_failures"] == len(CONNECTIONS)
    assert body["hint"] == purge.REVOKE_HINT
    assert destructive == [], "neither the tables nor the data key were touched"
    assert live.counts() == before, "the second run after the fault is a complete one"
    assert [record for record in caplog.records if record.levelno >= logging.ERROR]


def test_a_revocation_that_never_reaches_nextcloud_stops_the_purge_too(
    live: Deployment,
) -> None:
    """The transport half of the case above: no answer at all is no revocation at all."""
    before = live.counts()
    with respx.mock:
        respx.delete(PASSWORD_URL).mock(side_effect=httpx.ConnectError("no route"))
        deleted = respx.delete(CONFIG_URL).mock(return_value=httpx.Response(200, json={}))
        response = call(live)

    body = response.json()
    assert body["purged"] is False
    assert body["revoke_failures"] == len(CONNECTIONS)
    assert not deleted.called, "the key still opens the rows that are still there"
    assert live.counts() == before


def test_a_partly_failed_revocation_purges_and_counts_the_failure(live: Deployment) -> None:
    """WR-01 draws the line at zero, not at one: one broken connection blocks nothing.

    An uninstall that stops because a single app password could not be handed back would
    leave an administrator with no way forward at all, and the number in the answer plus
    the runbook are the documented handling of that case.
    """
    answers = iter([200, 500])
    with respx.mock:
        seen: list[str] = []

        def revoked(request: httpx.Request) -> httpx.Response:
            seen.append("password")
            return httpx.Response(next(answers, 500))

        respx.delete(PASSWORD_URL).mock(side_effect=revoked)
        deleted = respx.delete(CONFIG_URL).mock(return_value=httpx.Response(200, json={}))
        response = call(live)

    body = response.json()
    assert len(seen) == len(CONNECTIONS)
    assert body["purged"] is True
    assert body["revoked"] == 1
    assert body["revoke_failures"] == len(CONNECTIONS) - 1
    assert body["tables_cleared"] is True
    assert deleted.called
    assert live.counts() == dict.fromkeys(TABLES, 0)


def test_a_failed_key_deletion_is_its_own_number(live: Deployment) -> None:
    """The runbook has to be able to tell the administrator that one value is left."""
    with respx.mock:
        wire = Wire()
        wire.install(config_status=500)
        response = call(live)

    body = response.json()
    assert body["purged"] is True
    assert body["revoked"] == len(CONNECTIONS)
    assert body["tables_cleared"] is True
    assert body["key_deleted"] is False


def test_a_purge_of_an_empty_deployment_is_a_clean_zero(tmp_path: Path) -> None:
    """No connection, nothing to revoke, and the key still goes.

    The other side of the WR-01 line: ``revoked == 0`` alone is not a fault. Without a row
    there is nothing to hand back, so emptying the tables and deleting the key is exactly
    right here, and an abort would make an uninstall impossible on a deployment nobody ever
    connected to.
    """
    deployment = Deployment(tmp_path)

    with respx.mock:
        wire = Wire()
        wire.install()
        response = call(deployment)

    body = response.json()
    assert body["connections"] == 0
    assert body["revoked"] == 0
    assert body["revoke_failures"] == 0
    assert body["key_deleted"] is True
    assert wire.seen == ["key"]


def test_a_deployment_without_a_readable_store_says_so_and_never_pretends(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A purge that could not read its store must not answer as if it had emptied one."""

    async def broken() -> OAuthStore:
        raise RuntimeError("this volume is not readable")

    client = TestClient(
        Starlette(
            routes=purge.purge_routes(ENV, nextcloud=exapp_target(ENV), store_provider=broken)
        )
    )

    with respx.mock:
        wire = Wire()
        wire.install()
        with caplog.at_level(logging.DEBUG):
            response = client.post(
                purge.PURGE_PATH,
                json={"options": {purge.FORCE_OPTION: True}},
                headers=appapi_headers(),
            )

    assert response.json()["purged"] is False
    assert response.json()["hint"]
    assert wire.seen == [], "nothing outgoing happened"
    assert [record for record in caplog.records if record.levelno >= logging.ERROR]


# --- what the answer and the log may say (T-05-29) --------------------------------


@pytest.mark.parametrize("outcome", ["ok", "revocation refused", "key refused"])
def test_no_answer_names_an_account_a_client_or_a_credential(
    live: Deployment, outcome: str
) -> None:
    with respx.mock:
        wire = Wire()
        wire.install(
            password=500 if outcome == "revocation refused" else 200,
            config_status=500 if outcome == "key refused" else 200,
        )
        response = call(live)

    text = response.text
    for _auth_id, nc_user, password in CONNECTIONS:
        assert nc_user not in text
        assert password not in text
        assert password[:8] not in text
    assert CLIENT_NAME not in text
    assert APP_SECRET not in text
    assert KEY.hex() not in text


@pytest.mark.parametrize("outcome", ["ok", "revocation refused", "key refused"])
def test_no_log_record_names_an_account_a_client_or_a_credential(
    live: Deployment, caplog: pytest.LogCaptureFixture, outcome: str
) -> None:
    """The counter check of the answer above, on DEBUG: counts, never values (V7)."""
    with respx.mock:
        wire = Wire()
        wire.install(
            password=500 if outcome == "revocation refused" else 200,
            config_status=500 if outcome == "key refused" else 200,
        )
        with caplog.at_level(logging.DEBUG):
            call(live)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    for _auth_id, nc_user, password in CONNECTIONS:
        assert nc_user not in logged
        assert password not in logged
        assert password[:8] not in logged
    assert CLIENT_NAME not in logged
    assert APP_SECRET not in logged
    assert KEY.hex() not in logged


# --- the occ command registration -------------------------------------------------


def test_the_command_and_the_route_cannot_drift_apart() -> None:
    """One derivation, so a rename of the path renames the handler of the command."""
    assert purge.PURGE_PATH.removeprefix("/") == occ.OCC_HANDLER
    assert f"/{occ.OCC_HANDLER}" == purge.PURGE_PATH
    assert occ.command_schemes()[0]["execute_handler"] == occ.OCC_HANDLER
    assert occ.OCC_HANDLER, "an empty handler would register a command AppAPI cannot call"


def test_the_command_is_the_one_the_runbook_calls() -> None:
    scheme = occ.command_schemes()[0]

    assert occ.OCC_COMMAND_NAME == "mcp_connector:purge"
    assert scheme["name"] == occ.OCC_COMMAND_NAME
    assert scheme["hidden"] == 0
    assert scheme["arguments"] == []
    assert scheme["options"] == [
        {"name": purge.FORCE_OPTION, "mode": "none", "description": occ.OCC_FORCE_DESCRIPTION}
    ]
    assert scheme["usages"] == [f"{occ.OCC_COMMAND_NAME} --{purge.FORCE_OPTION}"]
    assert scheme["description"]


@pytest.mark.anyio
@respx.mock
async def test_the_registration_is_one_post_in_the_app_context() -> None:
    """One POST per command since plan 18-08: AppAPI registers exactly one at a time."""
    route = respx.post(OCC_URL).mock(return_value=httpx.Response(200, json={}))

    await occ.register_occ_commands(env=ENV)

    assert route.call_count == len(occ.command_schemes())
    bodies = [json.loads(call.request.content) for call in route.calls]
    assert bodies == occ.command_schemes()
    sent = route.calls[0].request
    assert json.loads(sent.content) == occ.command_schemes()[0]
    assert sent.headers["OCS-APIRequest"] == "true"
    assert sent.headers["EX-APP-ID"] == APP_ID
    assert (
        sent.headers["AUTHORIZATION-APP-API"]
        == base64.b64encode(f":{APP_SECRET}".encode()).decode()
    )


@pytest.mark.anyio
@respx.mock
@pytest.mark.parametrize("outcome", ["refused", "unreachable"])
async def test_a_failed_registration_is_one_log_line_and_never_raises(
    caplog: pytest.LogCaptureFixture, outcome: str
) -> None:
    """Pitfall 11: a non empty error field out of /enabled disables the app again at once."""
    route = respx.post(OCC_URL)
    if outcome == "unreachable":
        route.mock(side_effect=httpx.ConnectError("no route to nextcloud"))
    else:
        route.mock(return_value=httpx.Response(500, json={}))

    with caplog.at_level(logging.DEBUG):
        await occ.register_occ_commands(env=ENV)

    assert [record for record in caplog.records if record.levelno >= logging.ERROR]
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert APP_SECRET not in logged


@pytest.mark.anyio
async def test_a_registration_without_a_deploy_environment_never_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        await occ.register_occ_commands(env={})

    assert [record for record in caplog.records if record.levelno >= logging.ERROR]


# --- the hook it hangs on, and the hook it must not hang on (T-05-28) -------------


@pytest.fixture
def hooks(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[object]]:
    """Record all three registrations of the enable branch instead of sending them."""
    seen: dict[str, list[object]] = {"settings": [], "admin": [], "occ": []}

    async def note(name: str, env: object) -> None:
        seen[name].append(env)

    async def settings(*, env: object = None) -> None:
        await note("settings", env)

    async def admin(*, env: object = None) -> None:
        await note("admin", env)

    async def command(*, env: object = None) -> None:
        await note("occ", env)

    monkeypatch.setattr(settings_form, "register_settings_form", settings)
    monkeypatch.setattr(admin_settings, "register_admin_form", admin)
    monkeypatch.setattr(occ, "register_occ_commands", command)
    return seen


def lifecycle_client() -> TestClient:
    return TestClient(Starlette(routes=lifecycle.lifecycle_routes(ENV)))


def test_enabling_the_app_registers_the_command_next_to_both_forms(
    hooks: dict[str, list[object]],
) -> None:
    with lifecycle_client() as http:
        response = http.put("/enabled?enabled=1", headers=appapi_headers(user="admin"))

    assert response.status_code == 200
    assert response.json() == {"error": ""}
    assert hooks == {"settings": [ENV], "admin": [ENV], "occ": [ENV]}


def test_a_failing_command_registration_costs_neither_the_forms_nor_the_enable(
    monkeypatch: pytest.MonkeyPatch, hooks: dict[str, list[object]]
) -> None:
    """Its own try block: the three registrations are independent of each other."""

    async def boom(*, env: object = None) -> None:
        raise httpx.ConnectError("nextcloud is not reachable")

    monkeypatch.setattr(occ, "register_occ_commands", boom)
    with lifecycle_client() as http:
        response = http.put("/enabled?enabled=1", headers=appapi_headers(user="admin"))

    assert response.status_code == 200
    assert response.json() == {"error": ""}
    assert response.headers["cache-control"] == "no-store"
    assert hooks["settings"] == [ENV]
    assert hooks["admin"] == [ENV]


def test_disabling_the_app_registers_nothing_and_purges_nothing(
    hooks: dict[str, list[object]], live: Deployment
) -> None:
    """T-05-28: ``disableExApp()`` also runs on every update (``Command/ExApp/Update.php``).

    Cleaning up here would delete every connection of every user on every update, which is
    why the disable branch stays empty and this check exists to keep it that way.
    """
    before = live.counts()
    with respx.mock:
        wire = Wire()
        wire.install()
        with lifecycle_client() as http:
            response = http.put("/enabled?enabled=0", headers=appapi_headers(user="admin"))

    assert response.status_code == 200
    assert hooks == {"settings": [], "admin": [], "occ": []}
    assert wire.seen == []
    assert live.counts() == before


def test_the_lifecycle_module_reaches_no_purge_action() -> None:
    """The source side of the check above: the hooks can register, never destroy.

    The only thing ``lifecycle.py`` may know about this feature is the registration of the
    command. Neither the route factory nor any of the three destructive steps may be
    reachable from a hook that an update fires.
    """
    source = Path(lifecycle.__file__).read_text(encoding="utf-8")
    assert "purge_routes" not in source
    assert "wipe_all" not in source
    assert "revoke_app_password" not in source
    assert "delete_key" not in source

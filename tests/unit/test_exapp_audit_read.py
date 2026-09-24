"""``occ mcp_connector:audit:read``: AUDIT-04 as a command, and what it may never hand out.

The query itself is tested in ``tests/unit/test_audit_store.py``. What is under test here is
everything between that query and the console of an administrator: who may reach it, which
status it answers with, which option shapes it understands, and what its lines carry.

Threats covered here, in the order of the plan:

* **T-19-20** the handler reached from outside: ``x-origin-ip`` is 404, a request without the
  AppAPI headers is 401, neither says which of the two refused it, and the path appears in no
  route of ``appinfo/info.xml``, of which there are still thirteen.
* **T-19-21** the answer saying more than it may: no parameter value, no address, no path and
  no message of an error, in either shape.
* **T-19-22** a name from a stranger faking a line: an account with a line break in it does not
  change the number of lines of the answer, and one with a right to left override loses it.
* **T-19-23** a read without a ceiling: every number is tested before it is converted, and the
  default and the maximum of the store both hold.

The store is a real SQLite file in ``tmp_path`` for the reason the store tests give: what is
read out is a property of the file, and a mock of the store would assert the mock. The one
exception is the case of a store that cannot be read at all, which is a double whose read
raises, because a broken file is not a state this suite may create by hand.
"""

import asyncio
import base64
import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, cast

import pytest
from lxml import etree
from starlette.applications import Starlette
from starlette.testclient import TestClient
from starlette.types import Message

from mcp_connector import config
from mcp_connector.audit import store
from mcp_connector.errors import REASON_EXCHANGE_CLAIMS
from mcp_connector.exapp import audit_read, audit_verify
from mcp_connector.nextcloud.clients.xml import hardened_parser

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

ALICE = store.user_chain("alice")
BOB = store.user_chain("bob")

MANIFEST = Path(__file__).resolve().parents[2] / "appinfo" / "info.xml"

#: The parameter value of ``tests/unit/test_audit_store.py``, the kind of thing a parameter of
#: ``files_read`` carries. No method of the store takes one, so no answer of this handler can
#: carry one either, and two cases say so out loud (D-06, AUDIT-01, T-19-21).
A_VALUE = "kuendigung-2026.md"

DAY = 86400


def appapi_headers(user: str = "", secret: str = APP_SECRET) -> dict[str, str]:
    """What AppAPI puts on an internal call. The user is empty: this is the app context."""
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


def appapi_header_pairs(*extra: tuple[bytes, bytes]) -> list[tuple[bytes, bytes]]:
    """The same headers as raw byte pairs, plus whatever a case wants to add to them."""
    pairs = [(name.lower().encode(), text.encode()) for name, text in appapi_headers().items()]
    return [*pairs, *extra]


class Deployment:
    """One process of this application with its own audit file and the read route on it."""

    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / store.AUDIT_FILENAME
        self.store = store.AuditStore(self.path)
        #: The application itself, kept next to the client because one case has to drive it
        #: without the client in between; see :func:`raw_call`.
        self.app = Starlette(routes=audit_read.audit_read_routes(ENV, store_provider=self._open))
        self.client = TestClient(self.app)

    async def _open(self) -> store.AuditStore:
        return self.store

    def write_calls(
        self,
        chain: str,
        moments: list[int],
        *,
        client_name: str | None = None,
        actor: str | None = None,
    ) -> None:
        """Ordinary rows through the public interface, so the chain of the file is real."""
        asyncio.run(self._write_calls(chain, moments, client_name, actor))

    async def _write_calls(
        self, chain: str, moments: list[int], client_name: str | None, actor: str | None
    ) -> None:
        for at in moments:
            await self.store.append(
                store.Entry(
                    chain=chain,
                    tool="files_search",
                    nc_user=chain.removeprefix("u:"),
                    client_name=client_name,
                    actor=actor,
                    outcome=store.OUTCOME_OK,
                    params=["query", "dir"],
                    at=at,
                )
            )

    def write_switch(self, *, at: int) -> None:
        """The row of D-15, so the second meaning of the ``actor`` column is covered too."""
        asyncio.run(self._write_switch(at))

    async def _write_switch(self, at: int) -> None:
        await self.store.append(
            store.Entry(
                chain=store.CHAIN_INSTANCE,
                kind=store.KIND_SWITCH,
                at=at,
                actor=store.ACTOR_UNKNOWN,
                outcome="on",
            )
        )

    def write_refusal(self, *, at: int, removed: int = 1) -> None:
        """A row of the third chain (AUDIT-07): an attempt that never reached an account."""
        asyncio.run(self._write_refusal(at, removed))

    async def _write_refusal(self, at: int, removed: int) -> None:
        await self.store.append(
            store.Entry(
                chain=store.CHAIN_EXCHANGE,
                kind=store.KIND_REFUSAL,
                at=at,
                outcome=store.OUTCOME_REJECTED,
                reason=REASON_EXCHANGE_CLAIMS,
                removed=removed,
            )
        )

    def fill(self, count: int) -> None:
        """``count`` rows with an own connection, in one transaction.

        The rows carry no chain worth checking, the way ``tests/unit/test_audit_store.py``
        fills for its size cases: this helper exists for the ceiling only, and going through
        :meth:`AuditStore.append` for five thousand rows would open five thousand connections
        for a measurement that is about a number, not about hashes.
        """
        asyncio.run(self.store.read_entries(limit=1))  # so the schema is there to insert into
        conn = sqlite3.connect(self.path, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                "INSERT INTO entries (chain, kind, at, nc_user, tool, client_id, auth_id, "
                "client_name, outcome, params, prev_hash, hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        f"u:user-{number % 7}",
                        store.KIND_CALL,
                        1_700_000_000 + number,
                        f"user-{number % 7}",
                        "files_search",
                        "client-4711",
                        f"auth-{number:06d}",
                        "A Client With A Name",
                        store.OUTCOME_OK,
                        '["query"]',
                        hashlib.sha256(f"prev-{number}".encode()).digest(),
                        hashlib.sha256(f"row-{number}".encode()).digest(),
                    )
                    for number in range(count)
                ],
            )
            conn.execute("COMMIT")
        finally:
            conn.close()


class ExplodingStore:
    """A store whose read raises, with a path in the message the way a real one would.

    A double and not a monkeypatched method of the real store: what is under test is what the
    handler does with an exception, and the file that would produce one is a corrupted file
    nobody here may write. The message carries a path on purpose, because the assertion is that
    the answer does not.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    async def read_entries(self, **_: Any) -> list[tuple[Any, ...]]:
        raise sqlite3.DatabaseError(f"database disk image is malformed: {self.path}")


def broken(tmp_path: Path) -> Deployment:
    """A deployment whose store cannot be read, otherwise the same as any other."""
    deployment = Deployment(tmp_path)
    exploding = ExplodingStore(deployment.path)

    async def open_broken() -> store.AuditStore:
        return cast(store.AuditStore, exploding)

    deployment.app = Starlette(routes=audit_read.audit_read_routes(ENV, store_provider=open_broken))
    deployment.client = TestClient(deployment.app)
    return deployment


@pytest.fixture
def live(tmp_path: Path) -> Deployment:
    """A deployment with two chains of two and one entries, all of them whole."""
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000, 1001], client_name="A Client With A Name")
    deployment.write_calls(BOB, [1002])
    return deployment


def call(
    deployment: Deployment,
    *,
    options: dict[str, Any] | None = None,
    body: object | None = None,
    headers: dict[str, str] | list[tuple[bytes, bytes]] | None = None,
) -> Any:
    """One occ invocation, as AppAPI delivers it: a POST with the options in the body.

    ``Any`` for the reason ``tests/unit/test_oauth_abuse.py`` gives: the test client of
    Starlette answers with the response type of ``httpx2``, the fork the MCP SDK brings, and
    the outgoing calls of this app use ``httpx``. Naming either type here is a false claim.
    """
    payload = body if body is not None else {"occ": {"arguments": None, "options": options or {}}}
    sent = appapi_headers() if headers is None else headers
    return deployment.client.post(audit_read.AUDIT_READ_PATH, json=payload, headers=sent)


def raw_call(
    deployment: Deployment, headers: list[tuple[bytes, bytes]], body: bytes = b"{}"
) -> tuple[int, str]:
    """One POST straight into the application, with the header bytes handed over untouched.

    The helper of ``tests/unit/test_exapp_audit_verify.py``, and the reason is a property of
    the test client and not of this handler: httpx reads a field value it cannot decode as
    ASCII with latin-1 and the test client encodes it again as UTF-8, so a single byte such as
    ``b"\\xb2"`` arrives as two characters and a case built on it would assert the mangling
    instead of the handler.
    """
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": audit_read.AUDIT_READ_PATH,
        "raw_path": audit_read.AUDIT_READ_PATH.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 45678),
        "server": ("testserver", 80),
    }
    answered: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: Message) -> None:
        answered.append(message)

    asyncio.run(deployment.app(scope, receive, send))

    status = next(part["status"] for part in answered if part["type"] == "http.response.start")
    text = b"".join(
        part.get("body", b"") for part in answered if part["type"] == "http.response.body"
    )
    return status, text.decode("utf-8")


def parts(text: str) -> tuple[str, list[str], str]:
    """The head, the entry lines and the note of a text answer, taken by position.

    By position and not by a pattern on purpose: the claim of this shape is that an entry is
    exactly one line, so the count of the middle is what the cases assert, and a helper that
    filtered lines by what they look like would repair the very thing that must not break
    (T-19-22).
    """
    lines = text.splitlines()
    return lines[0], lines[1:-1], lines[-1]


# --- the boundary: T-19-20 ------------------------------------------------------------


def test_a_read_through_the_php_proxy_is_not_served(live: Deployment) -> None:
    """The PHP proxy attaches valid AppAPI headers itself, so its own marker is the only thing
    that tells this handler the request came through it (pitfall 13, T-19-20)."""
    headers = appapi_headers() | {"x-origin-ip": "203.0.113.7"}

    response = call(live, headers=headers)

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert "alice" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_a_read_without_appapi_headers_is_401_without_detail(live: Deployment) -> None:
    """A caller who learns "alice called files_search" has learned that alice uses this app,
    so the rejection says nothing at all."""
    response = call(live, headers={})

    assert response.status_code == 401
    assert response.json() == {}
    assert "alice" not in response.text
    assert APP_SECRET not in response.text


def test_neither_rejection_tells_the_caller_which_check_refused(live: Deployment) -> None:
    """The two answers have to be distinguishable by status alone and by nothing else."""
    proxied = call(live, headers=appapi_headers() | {"x-origin-ip": "203.0.113.7"})
    anonymous = call(live, headers={})

    for answer in (proxied, anonymous):
        assert audit_read.HEADER_ORIGIN_IP not in answer.text.lower()
        assert "appapi" not in answer.text.lower()
        assert "header" not in answer.text.lower()
        assert "alice" not in answer.text.lower()
        assert answer.headers["cache-control"] == "no-store"


def test_a_read_with_a_wrong_app_secret_is_401(live: Deployment) -> None:
    response = call(live, headers=appapi_headers(secret="wrong"))

    assert response.status_code == 401
    assert response.json() == {}


def test_the_handler_path_is_declared_in_no_route_of_the_manifest() -> None:
    """T-19-20: a declared route would publish the content of the log to the internet.

    The manifest still carries exactly the thirteen routes of phase 5, none of them matches
    this path in any spelling, and the absence is the access control itself: HaRP blocks a path
    that is declared nowhere, the PHP proxy does not.
    """
    root = etree.parse(str(MANIFEST), hardened_parser()).getroot()
    urls = [(element.text or "").strip() for element in root.iter("url")]

    assert len(urls) == 13, urls
    bare = audit_read.AUDIT_READ_PATH.strip("/")
    for url in urls:
        assert bare not in url, f"{url} would make the read reachable from the internet"


def test_the_constants_of_the_two_commands_are_spelled_the_same() -> None:
    """The duplicates of this module, and every one of them is a decision, not an accident.

    ``lifecycle`` imports ``occ`` and ``occ`` imports both handler modules, so this one may not
    import the other: a header, an option name, a positive list and a column width are spelled
    twice on purpose, and this assertion is what makes a change to either of them a decision
    somebody made rather than a drift nobody saw.
    """
    assert audit_read.HEADER_ORIGIN_IP == audit_verify.HEADER_ORIGIN_IP
    assert audit_read.JSON_OPTION == audit_verify.JSON_OPTION
    assert audit_read.OCC_ENVELOPE == audit_verify.OCC_ENVELOPE
    assert audit_read.TRUE_WORDS == audit_verify.TRUE_WORDS
    assert audit_read.CHAIN_LIMIT == audit_verify.CHAIN_LIMIT
    assert audit_read.MAX_BODY_BYTES == audit_verify.MAX_BODY_BYTES
    assert audit_read.MAX_ANNOUNCED_DIGITS == audit_verify.MAX_ANNOUNCED_DIGITS


# --- the answer, and the status it may never carry: T-18-20 ---------------------------


def test_an_empty_store_says_so_without_saying_whether_an_account_exists(tmp_path: Path) -> None:
    """The store of an installation that never switched the log on has nothing to hand over,
    and it says that in a way that tells a reader nothing about any account."""
    response = call(Deployment(tmp_path))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-store"
    assert audit_read.NO_ENTRY in response.text
    assert audit_read.READ_NOTE in response.text
    assert "0 entries" in response.text


def test_a_filter_without_a_hit_answers_like_an_empty_store(live: Deployment) -> None:
    """ "no such account" and "this account called nothing" are the same answer on purpose."""
    response = call(live, options={audit_read.USER_OPTION: "carol"})

    assert response.status_code == 200
    assert audit_read.NO_ENTRY in response.text
    assert "alice" not in response.text


# --- the options, in every shape AppAPI may send them ---------------------------------


def test_the_options_are_read_under_the_envelope_and_at_the_top(live: Deployment) -> None:
    """AppAPI wraps an invocation in ``occ``; a body that hands the options in without the
    wrapper is the same invocation and is read as one."""
    wrapped = call(live, options={audit_read.USER_OPTION: "bob"})
    plain = call(live, body={audit_read.USER_OPTION: "bob"})

    assert wrapped.status_code == plain.status_code == 200
    assert wrapped.text == plain.text
    assert BOB in wrapped.text
    assert ALICE not in wrapped.text


def test_an_option_nobody_set_arrives_as_null_and_changes_nothing(live: Deployment) -> None:
    """Measured against app_api v34.0.3: an option in mode ``optional`` that nobody set arrives
    as its declared default, which is ``null``, and a flag in mode ``none`` arrives as
    ``false``. Neither may act like an input."""
    empty = call(live)
    unset = call(
        live,
        options={
            audit_read.USER_OPTION: None,
            audit_read.SINCE_OPTION: None,
            audit_read.LIMIT_OPTION: None,
            audit_read.JSON_OPTION: False,
        },
    )

    assert unset.status_code == 200
    assert unset.headers["content-type"].startswith("text/plain")
    assert unset.text == empty.text
    assert f"at most {store.READ_LIMIT_DEFAULT} per read" in unset.text


def test_an_option_that_is_only_whitespace_is_not_an_input(live: Deployment) -> None:
    """A value that is nothing after ``strip`` is a shape this handler does not act on."""
    response = call(live, options={audit_read.USER_OPTION: "   "})

    assert response.status_code == 200
    assert ALICE in response.text
    assert BOB in response.text


def test_the_json_flag_switches_the_shape_and_nothing_else(live: Deployment) -> None:
    response = call(live, options={audit_read.JSON_OPTION: True})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["read"] is True


def test_the_instance_keyword_reads_the_chain_that_has_no_account(tmp_path: Path) -> None:
    """The instance chain carries the switch of the log and the markers for chains that are
    gone, and it has no account, so this one word is the only way to address it."""
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000])
    asyncio.run(deployment.store.append(store.Entry(chain=store.CHAIN_INSTANCE, kind="switch")))

    response = call(deployment, options={audit_read.USER_OPTION: audit_read.INSTANCE_KEYWORD})

    assert response.status_code == 200
    assert store.CHAIN_INSTANCE in response.text
    assert ALICE not in response.text


# --- every number, before it is converted: T-19-23 ------------------------------------


def test_a_limit_that_is_not_a_plain_number_falls_back_to_the_default(
    live: Deployment, caplog: pytest.LogCaptureFixture
) -> None:
    """``"²".isdigit()`` is True and ``int("²")`` raises, so the digit test alone would turn an
    option of an authenticated administrator into a 500, which AppAPI answers with an empty
    console (T-18-20, R-18-08)."""
    with caplog.at_level(logging.DEBUG):
        response = call(live, options={audit_read.LIMIT_OPTION: "²"})

    assert response.status_code == 200
    assert f"at most {store.READ_LIMIT_DEFAULT} per read" in response.text
    assert "²" not in response.text, "the answer repeats no option value"
    assert "Traceback" not in response.text
    logged = "\n".join(entry.getMessage() for entry in caplog.records)
    assert "²" not in logged, "and neither does the log (T-05-03)"


def test_a_limit_of_a_run_no_integer_can_hold_falls_back_as_well(live: Deployment) -> None:
    """The second half of the same trap, ASCII throughout: since Python 3.11 a run of more than
    4300 digits makes :func:`int` raise, which ``isascii`` does not catch, so the length of the
    run is decided before its value."""
    response = call(live, options={audit_read.LIMIT_OPTION: "9" * 5000})

    assert response.status_code == 200
    assert f"at most {store.READ_LIMIT_DEFAULT} per read" in response.text


def test_a_limit_above_the_maximum_hands_over_the_maximum_and_no_more(tmp_path: Path) -> None:
    """The ceiling is measured against more rows than it allows: a case with three rows and a
    limit of a million passes without any ceiling at all."""
    deployment = Deployment(tmp_path)
    deployment.fill(store.READ_LIMIT_MAX + 3)

    response = call(
        deployment, options={audit_read.LIMIT_OPTION: "999999", audit_read.JSON_OPTION: True}
    )

    answer = response.json()
    assert response.status_code == 200
    assert answer["limit_applied"] == store.READ_LIMIT_MAX
    assert answer["count"] == store.READ_LIMIT_MAX
    assert len(answer["entries"]) == store.READ_LIMIT_MAX


def test_a_limit_of_zero_is_not_a_read_of_everything(live: Deployment) -> None:
    """SQLite reads a negative ``LIMIT`` as no limit at all, so both ends are clamped and the
    lower one is not cosmetics."""
    response = call(live, options={audit_read.LIMIT_OPTION: "0", audit_read.JSON_OPTION: True})

    assert response.status_code == 200
    assert response.json()["limit_applied"] == 1
    assert response.json()["count"] == 1


def test_since_one_day_leaves_the_older_entries_out(tmp_path: Path) -> None:
    deployment = Deployment(tmp_path)
    now = int(time.time())
    deployment.write_calls(ALICE, [now - 400 * DAY])
    deployment.write_calls(BOB, [now - 3600])

    response = call(deployment, options={audit_read.SINCE_OPTION: "1"})

    assert response.status_code == 200
    assert BOB in response.text
    assert ALICE not in response.text
    assert "1 entry" in response.text


def test_since_above_the_bound_is_capped_and_hands_over_everything(tmp_path: Path) -> None:
    """A window longer than :data:`MAX_SINCE_DAYS` is the whole log and is read as one rather
    than refused, and the cap keeps the arithmetic on a Unix second in range."""
    deployment = Deployment(tmp_path)
    now = int(time.time())
    deployment.write_calls(ALICE, [now - 400 * DAY])
    deployment.write_calls(BOB, [now - 3600])

    response = call(deployment, options={audit_read.SINCE_OPTION: "99999"})

    assert response.status_code == 200
    assert ALICE in response.text
    assert BOB in response.text
    assert "2 entries" in response.text


def test_a_since_that_is_not_a_number_falls_back_to_the_widest_window(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A date is deliberately not parsed: a run of digits can be tested before anything
    converts it and a date cannot, so ``--since yesterday`` is not an input.

    What it falls back to is the widest window this option has and not "no window at all",
    which is the one thing this case pins down: a row older than :data:`MAX_SINCE_DAYS` stays
    out. The warning names the option and the bound and never the value (T-05-03).
    """
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000])
    deployment.write_calls(BOB, [int(time.time()) - 3600])

    with caplog.at_level(logging.DEBUG):
        response = call(deployment, options={audit_read.SINCE_OPTION: "yesterday"})

    assert response.status_code == 200
    assert BOB in response.text
    assert ALICE not in response.text, "the fallback is the widest window, not every moment"
    logged = "\n".join(entry.getMessage() for entry in caplog.records)
    assert str(audit_read.MAX_SINCE_DAYS) in logged
    assert "yesterday" not in logged


# --- bodies this handler will not read ------------------------------------------------


def test_a_body_above_the_limit_is_not_parsed_and_costs_no_answer(live: Deployment) -> None:
    """The rule of ``exapp/purge.py``: a body this handler will not read is the default, which
    is the text shape without a filter, and never a rejection."""
    payload = {
        "occ": {
            "options": {audit_read.JSON_OPTION: True},
            "padding": "x" * audit_read.MAX_BODY_BYTES,
        }
    }

    response = call(live, body=payload)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "3 entries" in response.text


def test_a_unicode_digit_in_the_announced_length_answers_like_any_other_call(
    live: Deployment,
) -> None:
    """The same trap in the header the option carries in its value, and the same answer: a 500
    is the worst answer this handler has, because AppAPI drops the body of anything else."""
    status, text = raw_call(live, appapi_header_pairs((b"content-length", b"\xb2")))

    assert status == 200
    assert audit_read.READ_NOTE in text
    assert "Traceback" not in text
    assert str(live.path) not in text


def test_a_body_that_is_not_json_leaves_the_answer_as_it_was(live: Deployment) -> None:
    status, text = raw_call(live, appapi_header_pairs(), body=b"not json at all")

    assert status == 200
    assert audit_read.READ_NOTE in text


# --- the shape of the answer, line by line --------------------------------------------


def test_three_entries_are_three_lines_between_the_head_and_the_note(live: Deployment) -> None:
    """The head first, one line per entry, the note last, and the newest entry on top.

    The order is asserted with the numbers of the rows and not with a moment, because ``seq``
    is what the store sorts by and a moment can move backwards (WR-02).
    """
    head, lines, note = parts(call(live).text)

    assert head == f"3 entries, newest first, at most {store.READ_LIMIT_DEFAULT} per read"
    assert len(lines) == 3
    assert note == audit_read.READ_NOTE
    assert [line.split(audit_read.FIELD_SEPARATOR)[0] for line in lines] == ["3", "2", "1"]
    assert lines[0].startswith(f"3{audit_read.FIELD_SEPARATOR}")
    assert BOB in lines[0], "the newest entry is the one of the chain written last"


def test_an_account_with_a_line_break_adds_no_line_to_the_answer(tmp_path: Path) -> None:
    """The case that justifies the bracketing (T-18-08, T-19-22).

    Without :func:`mcp_connector.audit.text.printable` in front of the column, the account
    name below ends its line and starts another one, and whoever registered that account
    decides what the extra line says.
    """
    deployment = Deployment(tmp_path)
    deployment.write_calls(store.user_chain("ali\nce - 99 - files_read"), [1000])
    deployment.write_calls(BOB, [1001])

    head, lines, note = parts(call(deployment).text)

    assert head.startswith("2 entries")
    assert len(lines) == 2, "an account name may not add a line of its own"
    assert note == audit_read.READ_NOTE
    assert "\n" not in lines[0]


def test_an_account_with_a_right_to_left_override_loses_it(tmp_path: Path) -> None:
    """A character of the category Cf turns the reading direction of the rest of the line
    round, so a name can look like a different name without one different letter (R-18-06)."""
    override = "‮"
    deployment = Deployment(tmp_path)
    deployment.write_calls(store.user_chain(f"al{override}ice"), [1000])

    response = call(deployment)
    document = call(deployment, options={audit_read.JSON_OPTION: True}).json()

    assert response.status_code == 200
    assert override not in response.text
    assert override not in json.dumps(document)
    assert "al ice" in response.text, "the character became a space and melted no two words"


def test_no_shape_of_the_answer_carries_a_parameter_value(tmp_path: Path) -> None:
    """D-06 and AUDIT-01 at the far end: no method of the store takes a parameter value, so no
    line and no document can carry one, and this is the case that says it out loud."""
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000], client_name="A Client With A Name")

    text = call(deployment).text
    document = call(deployment, options={audit_read.JSON_OPTION: True}).json()

    assert A_VALUE not in text
    assert A_VALUE not in json.dumps(document)
    assert "kuendigung" not in text.lower()


def test_the_names_of_the_parameters_are_there_and_the_values_are_not(live: Deployment) -> None:
    """The names are the point of the log: which parameters a call carried is what makes a
    refusal readable afterwards, and the schema says "never a value" next to them."""
    text = call(live).text
    document = call(live, options={audit_read.JSON_OPTION: True}).json()

    assert "dir,query" in text, "sorted, the way the store writes them"
    assert document["entries"][0]["params"] == ["dir", "query"]


def test_a_column_that_holds_nothing_is_a_dash_and_never_the_word_none(live: Deployment) -> None:
    """``None`` is a word of a language, and this is a line for a person."""
    _, lines, _ = parts(call(live).text)

    assert audit_read.NULL_FIELD in lines[0].split(audit_read.FIELD_SEPARATOR)
    assert "None" not in call(live).text


# --- the acting party of an exchanged token (AUDIT-07) --------------------------------


#: Where the acting party stands in a line: directly behind the client name, so the two
#: names of a call are read next to each other and never mistaken for one another.
ACTOR_COLUMN = 5

#: Where the count of a row stands: last, behind the parameter names, so the ten columns that
#: were there before AUDIT-07 kept their places and no case had to be renumbered.
REMOVED_COLUMN = 10

#: How many columns a line of this answer has. Written down here because the whole point of
#: the case below is that the number moved, and a case that counts what it found proves
#: nothing about what it should have found. It moved twice for AUDIT-07: once for the acting
#: party of a delegated call and once for the number of attempts a refusal row stands for.
LINE_COLUMNS = 11


def test_a_line_carries_the_acting_party_behind_the_client_name(tmp_path: Path) -> None:
    """AUDIT-07 in the shape an administrator reads: the ``azp`` has a column of its own."""
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000], client_name=None, actor="kc-client-of-another-realm")

    _, lines, _ = parts(call(deployment).text)
    columns = lines[0].split(audit_read.FIELD_SEPARATOR)

    assert len(columns) == LINE_COLUMNS
    assert columns[ACTOR_COLUMN] == "kc-client-of-another-realm"
    assert columns[ACTOR_COLUMN - 1] == audit_read.NULL_FIELD, "the client name, and it is empty"


def test_a_call_without_an_acting_party_shows_a_dash_in_that_column(live: Deployment) -> None:
    """The honest placeholder of this module, and never an empty column between two separators."""
    _, lines, _ = parts(call(live).text)
    columns = lines[0].split(audit_read.FIELD_SEPARATOR)

    assert len(columns) == LINE_COLUMNS
    assert columns[ACTOR_COLUMN] == audit_read.NULL_FIELD


def test_a_switch_row_keeps_its_word_in_the_same_column(tmp_path: Path) -> None:
    """The column says two things (D-16 and AUDIT-07) and loses neither of them."""
    deployment = Deployment(tmp_path)
    deployment.write_switch(at=1000)

    _, lines, _ = parts(call(deployment).text)
    columns = lines[0].split(audit_read.FIELD_SEPARATOR)

    assert columns[ACTOR_COLUMN] == store.ACTOR_UNKNOWN


def test_an_acting_party_with_an_override_loses_it_in_both_shapes(tmp_path: Path) -> None:
    """T-24-01: the value comes from a foreign realm, so it goes through the cleaning rule.

    A right-to-left override would turn the reading direction of everything behind it round,
    so a line could show one acting party and mean another one. The column goes through
    ``_cleaned`` and not through ``_field`` for exactly this.
    """
    override = "‮"
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000], actor=f"kc{override}client")

    text = call(deployment).text
    document = call(deployment, options={audit_read.JSON_OPTION: True}).json()

    assert override not in text
    assert override not in json.dumps(document)
    assert "kc client" in text, "the character became a space and melted no two words"


def test_the_document_carries_the_acting_party_next_to_the_client_name(
    tmp_path: Path,
) -> None:
    """The machine readable shape gets the same field, in the same form as the other name."""
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000], actor="kc-client-of-another-realm")

    first = call(deployment, options={audit_read.JSON_OPTION: True}).json()["entries"][0]

    assert first["actor"] == "kc-client-of-another-realm"


def test_a_line_carries_the_moment_as_utc_to_the_second(live: Deployment) -> None:
    """A console line with the timezone of its reader in it cannot be compared with the line
    above it, so every moment is UTC and says so."""
    _, lines, _ = parts(call(live).text)

    assert lines[0].split(audit_read.FIELD_SEPARATOR)[1] == "1970-01-01T00:16:42Z"


# --- the machine readable shape -------------------------------------------------------


def test_the_document_carries_the_state_key_the_counts_and_the_note(live: Deployment) -> None:
    """``read`` is the key a script watches, because the exit code of the command is always 0
    for the reason T-18-20 measures."""
    answer = call(live, options={audit_read.JSON_OPTION: True}).json()

    assert list(answer) == ["read", "count", "limit_applied", "truncated", "entries", "note"]
    assert answer["read"] is True
    assert answer["count"] == 3
    assert answer["limit_applied"] == store.READ_LIMIT_DEFAULT
    assert answer["truncated"] is False
    assert answer["note"] == audit_read.READ_NOTE


def test_the_document_hands_the_entries_over_in_the_order_of_the_chain(live: Deployment) -> None:
    """The text shows the newest first because that is what a console wants; a document that is
    kept is read in the order the chain has, because that order is what makes it checkable."""
    answer = call(live, options={audit_read.JSON_OPTION: True}).json()

    assert [entry["seq"] for entry in answer["entries"]] == [1, 2, 3]


def test_the_hashes_of_the_document_are_hex_and_not_bytes(live: Deployment) -> None:
    """A BLOB is not JSON, and the chain cannot be recomputed from a truncated one."""
    first = call(live, options={audit_read.JSON_OPTION: True}).json()["entries"][0]

    assert isinstance(first["hash"], str)
    assert isinstance(first["prev_hash"], str)
    assert len(first["hash"]) == 64
    assert first["prev_hash"] == store.GENESIS.hex()
    assert bytes.fromhex(first["hash"])


def test_an_entry_of_the_document_carries_every_field_of_the_row(live: Deployment) -> None:
    """The fields come out of the store through ``_entry_of_row``, so the column order stays
    written down once, in the module that owns the schema."""
    first = call(live, options={audit_read.JSON_OPTION: True}).json()["entries"][0]

    assert first == {
        "seq": 1,
        "chain": ALICE,
        "kind": store.KIND_CALL,
        "at": 1000,
        "nc_user": "alice",
        "tool": "files_search",
        "client_id": None,
        "auth_id": None,
        "client_name": "A Client With A Name",
        "actor": None,
        "outcome": store.OUTCOME_OK,
        "reason": None,
        "duration_ms": None,
        "params": ["dir", "query"],
        "removed": None,
        "prev_hash": store.GENESIS.hex(),
        "hash": first["hash"],
    }


@pytest.mark.parametrize(("limit", "expected"), [("4", True), ("5", False)])
def test_truncated_says_whether_there_may_be_more_behind_the_last_entry(
    tmp_path: Path, limit: str, expected: bool
) -> None:
    """As many entries as the ceiling allows means there may be more, and one less means there
    are not. Both ends are asserted, because the first one alone is true of every ceiling."""
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000, 1001, 1002, 1003])

    answer = call(
        deployment, options={audit_read.LIMIT_OPTION: limit, audit_read.JSON_OPTION: True}
    ).json()

    assert answer["truncated"] is expected
    assert answer["count"] == 4


# --- a store that cannot be read: T-19-21 ---------------------------------------------


def test_a_store_that_cannot_be_read_answers_200_with_the_type_and_nothing_else(
    tmp_path: Path,
) -> None:
    """The type of the exception, never its message: a store error carries a path, and a path
    of a container is not something a console line of an occ command has to hand out.

    The status is 200 for the reason T-18-20 measures: with anything else AppAPI drops this
    body, and an administrator would be left with an empty console instead of the sentence.
    """
    deployment = broken(tmp_path)

    response = call(deployment)

    assert response.status_code == 200
    assert "DatabaseError" in response.text
    assert "malformed" not in response.text, "the message of the error stays out of the answer"
    assert store.AUDIT_FILENAME not in response.text
    assert str(tmp_path) not in response.text
    assert "Traceback" not in response.text


def test_a_store_that_cannot_be_read_puts_the_state_key_on_false(tmp_path: Path) -> None:
    """The half of the same answer a script reads, because the exit code is always 0."""
    answer = call(broken(tmp_path), options={audit_read.JSON_OPTION: True}).json()

    assert answer == {"read": False, "error": "DatabaseError"}
    assert store.AUDIT_FILENAME not in json.dumps(answer)


def test_the_failure_is_logged_with_the_type_and_without_the_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The same rule in the log of the instance: the type says what happened, the message would
    say where, and the where is what T-19-21 keeps out."""
    with caplog.at_level(logging.DEBUG):
        call(broken(tmp_path))

    logged = "\n".join(entry.getMessage() for entry in caplog.records)
    assert "DatabaseError" in logged
    assert str(tmp_path) not in logged
    assert "malformed" not in logged


# --- the chain of the refused exchange attempts (AUDIT-07) ----------------------------
# The rows an operator was promised in success criterion 2 of this phase. They stand in a
# chain of their own, that chain has no account behind it, and ``--user`` addresses a chain
# by an account name: so this needs a word of its own for exactly the reason the instance
# chain needed one.


def test_the_refusals_keyword_reads_the_chain_of_the_turned_down_attempts(
    tmp_path: Path,
) -> None:
    """The whole of success criterion 2 in one case: the operator can read them, in both
    shapes, and the chain of an account is not mixed into the answer."""
    deployment = Deployment(tmp_path)
    deployment.write_calls(ALICE, [1000])
    deployment.write_refusal(at=1001, removed=23)

    text = call(deployment, options={audit_read.USER_OPTION: audit_read.REFUSALS_KEYWORD}).text
    document = call(
        deployment,
        options={
            audit_read.USER_OPTION: audit_read.REFUSALS_KEYWORD,
            audit_read.JSON_OPTION: True,
        },
    ).json()

    assert store.CHAIN_EXCHANGE in text
    assert ALICE not in text
    assert [entry["chain"] for entry in document["entries"]] == [store.CHAIN_EXCHANGE]
    assert document["entries"][0]["kind"] == store.KIND_REFUSAL
    assert document["entries"][0]["reason"] == REASON_EXCHANGE_CLAIMS
    assert document["entries"][0]["removed"] == 23


def test_an_account_named_like_the_keyword_is_read_as_the_keyword(tmp_path: Path) -> None:
    """The price of the second reserved word, measured rather than assumed.

    The same resolution :data:`~mcp_connector.exapp.audit_read.INSTANCE_KEYWORD` has had
    since plan 19-06 and the same trade behind it: the word wins, an account that is really
    called ``refusals`` is not addressable through this option, and its chain is read by a
    call without ``--user``. One rule for both reserved words, because two rules would be the
    kind of difference nobody remembers at the console.
    """
    deployment = Deployment(tmp_path)
    deployment.write_calls(store.user_chain(audit_read.REFUSALS_KEYWORD), [1000])
    deployment.write_refusal(at=1001)

    named = call(deployment, options={audit_read.USER_OPTION: audit_read.REFUSALS_KEYWORD}).text
    everything = call(deployment).text

    assert store.CHAIN_EXCHANGE in named
    assert store.user_chain(audit_read.REFUSALS_KEYWORD) not in named
    assert store.user_chain(audit_read.REFUSALS_KEYWORD) in everything, (
        "the account is not lost, it is read by the call that filters nothing"
    )


def test_a_refusal_line_shows_the_count_and_a_dash_where_it_has_no_value(
    tmp_path: Path,
) -> None:
    """What such a row is worth reading for is the identifier and the number of attempts it
    stands for, and the number is the reason the line grew a column: without it the one value
    a refusal row carries would be readable in no shape of this answer at all.
    """
    deployment = Deployment(tmp_path)
    deployment.write_refusal(at=1000, removed=17)

    _, lines, _ = parts(call(deployment).text)
    columns = lines[0].split(audit_read.FIELD_SEPARATOR)

    assert len(columns) == LINE_COLUMNS
    assert columns[2] == store.CHAIN_EXCHANGE
    assert columns[3] == audit_read.NULL_FIELD, "a refusal calls no tool"
    assert columns[4] == audit_read.NULL_FIELD, "and registers no client"
    assert columns[ACTOR_COLUMN] == audit_read.NULL_FIELD, "and has no acting party (T-24-04)"
    assert columns[6] == store.OUTCOME_REJECTED
    assert columns[7] == REASON_EXCHANGE_CLAIMS
    assert columns[8] == audit_read.NULL_FIELD, "nothing was carried out, so nothing took time"
    assert columns[9] == audit_read.NULL_FIELD, "and no parameter was ever read"
    assert columns[REMOVED_COLUMN] == "17"


def test_an_ordinary_call_shows_a_dash_in_the_count_column(live: Deployment) -> None:
    """The new column is a column of every line, and a call stands for itself alone."""
    _, lines, _ = parts(call(live).text)
    columns = lines[0].split(audit_read.FIELD_SEPARATOR)

    assert len(columns) == LINE_COLUMNS
    assert columns[REMOVED_COLUMN] == audit_read.NULL_FIELD

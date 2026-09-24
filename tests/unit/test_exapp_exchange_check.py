"""``occ mcp_connector:exchange:check``: the console half of the dry run (EXCH-06).

The rule itself is measured in ``tests/unit/test_oauth_exchange_dryrun.py``, one case per
step. What is under test here is everything between that rule and the console of an
administrator: who may reach the handler, which status it answers with, whether every step
of the rule really reaches the answer, and whether the presented token stays out of it.

Threats covered here, in the order of the plan:

* **T-24-08** the handler reached from outside: ``x-origin-ip`` is 404, a request without the
  AppAPI headers is 401, neither says which of the two refused it, and the path appears in no
  ``<url>`` of ``appinfo/info.xml``.
* **T-24-09** the answer as an oracle: no shape of it ever repeats the presented token or a
  fragment of it, not even to confirm what was checked.
* **T-24-25** the request body: the bound is a calculation over ``MAX_TOKEN_BYTES`` rather
  than a literal, and a token at the hard bound is measured through it instead of assumed
  through it.
* **pitfall 8** a step that is merely absent reads as a passed one: the number of step lines
  and the number of JSON entries are both held against ``len(STEPS)``, derived and never
  typed, so a step added to the rule cannot stay nameless here.

Nothing in this file reaches the network. Every token below falls at a local step, which is
what keeps the corpus free of a key set fixture it would not measure anything with.
"""

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from lxml import etree
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.exapp import audit_verify, exchange_check
from mcp_connector.nextcloud.clients.xml import hardened_parser
from mcp_connector.oauth import exchange_dryrun

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

#: The same deployment with the exchange path armed. The audience is written out rather than
#: derived, so no check of this file depends on the derivation rule of another module.
ARMED = {
    **ENV,
    config.ENV_EXCHANGE_ENABLED: "1",
    config.ENV_EXCHANGE_ISSUER: "https://idp.example.org/realms/f13",
    config.ENV_EXCHANGE_AZP: "f13-orchestrator",
    config.ENV_EXCHANGE_AUDIENCE: "https://cloud.example.org/exapps/mcp_connector/mcp",
}

MANIFEST = Path(__file__).resolve().parents[2] / "appinfo" / "info.xml"

#: The four outcomes a step line of the text answer may begin with. Read off the rule module
#: rather than spelled here, because a fifth outcome there has to reach this file as a failure
#: and not as a silently smaller count.
OUTCOMES = frozenset(
    {
        exchange_dryrun.OUTCOME_PASSED,
        exchange_dryrun.OUTCOME_FAILED,
        exchange_dryrun.OUTCOME_SKIPPED,
        exchange_dryrun.OUTCOME_NOT_CHECKED,
    }
)

#: A token that is not a JWS, so every case built on it falls at ``token_shape`` without a
#: single outgoing request. The marker is what the leak check searches the answers for.
MARKER = "MARKER-7f3a9c"


def appapi_headers(user: str = "", secret: str = APP_SECRET) -> dict[str, str]:
    """What AppAPI puts on an internal call. The user is empty: this is the app context."""
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


def client_for(env: dict[str, str] = ARMED) -> TestClient:
    """One process of this application with nothing on it but the check route."""
    return TestClient(Starlette(routes=exchange_check.exchange_check_routes(env)))


def call(
    client: TestClient,
    *,
    token: str | None = None,
    as_json: bool = False,
    body: object | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """One occ invocation, as AppAPI delivers it: a POST with the options in the body.

    ``Any`` for the reason ``tests/unit/test_exapp_audit_verify.py`` gives: the test client of
    Starlette answers with the response type of ``httpx2``, the fork the MCP SDK brings, and
    the outgoing calls of this app use ``httpx``. Naming either type here is a false claim.
    """
    options: dict[str, Any] = {}
    if token is not None:
        options[exchange_check.TOKEN_OPTION] = token
    if as_json:
        options[exchange_check.JSON_OPTION] = True
    payload = body if body is not None else {"occ": {"arguments": None, "options": options}}
    return client.post(
        exchange_check.EXCHANGE_CHECK_PATH,
        json=payload,
        headers=appapi_headers() if headers is None else headers,
    )


def opaque(size: int) -> str:
    """A token of exactly ``size`` bytes that carries the marker and is not a JWS."""
    return MARKER + "a" * (size - len(MARKER))


def step_lines(text: str) -> list[str]:
    """The lines of the text answer that report a step, told apart by their first word."""
    return [line for line in text.splitlines() if line.split(" ", 1)[0] in OUTCOMES]


def fallen(payload: dict[str, Any]) -> list[str]:
    """The identifiers of the steps that fell in this machine readable answer."""
    return [
        entry["step"]
        for entry in payload["steps"]
        if entry["outcome"] == exchange_dryrun.OUTCOME_FAILED
    ]


# --- who may reach the handler at all: T-24-08 ----------------------------------------


def test_a_call_over_the_php_proxy_is_not_found() -> None:
    """The proxy header means the request came the way this path is not meant to be reached."""
    response = call(client_for(), token="x", headers={**appapi_headers(), "x-origin-ip": "1.2.3.4"})

    assert response.status_code == 404


def test_a_call_without_the_appapi_headers_is_unauthorized() -> None:
    response = call(client_for(), token="x", headers={})

    assert response.status_code == 401


def test_neither_rejection_says_which_of_the_two_checks_refused_it() -> None:
    """A body that named the reason would tell a caller which door it stood in front of."""
    proxied = call(
        client_for(), token="x", headers={**appapi_headers(), "x-origin-ip": "1.2.3.4"}
    ).text
    anonymous = call(client_for(), token="x", headers={}).text

    for body in (proxied, anonymous):
        lowered = body.lower()
        for word in ("appapi", "origin", "proxy", "secret", "header", "exchange"):
            assert word not in lowered, f"{body!r} names why it refused"


def test_the_path_is_declared_in_no_route_of_the_manifest() -> None:
    """T-24-27: a declared route would put this answer on the internet."""
    root = etree.parse(str(MANIFEST), hardened_parser()).getroot()
    urls = [(element.text or "").strip() for element in root.iter("url")]

    assert urls, "with no url at all this test would prove nothing"
    bare = exchange_check.EXCHANGE_CHECK_PATH.strip("/")
    for url in urls:
        assert bare not in url, f"{url} would make the dry run reachable from the internet"


# --- the status the answer may never carry, and the shape of it -----------------------


def test_a_token_that_falls_still_answers_200() -> None:
    """AppAPI drops the body on any status but 200, and the body is the whole answer."""
    response = call(client_for(), token=opaque(64))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "no-store"
    assert exchange_dryrun.LIMIT_SENTENCE in response.text
    assert exchange_dryrun.COST_SENTENCE in response.text


def test_the_machine_readable_answer_carries_the_verdict_a_script_watches() -> None:
    """The exit code is always 0, so ``passed`` is what a monitoring script reads instead."""
    response = call(client_for(), token=opaque(64), as_json=True)
    payload = response.json()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert payload["checked"] is True
    assert payload["passed"] is False
    assert payload["limit"] == exchange_dryrun.LIMIT_SENTENCE
    assert payload["cost"] == exchange_dryrun.COST_SENTENCE


# --- every step reaches the answer: pitfall 8 -----------------------------------------


def test_the_text_answer_carries_one_line_per_step_of_the_rule() -> None:
    """Derived from ``STEPS`` and never typed, so a step added in 24-05 cannot go missing."""
    response = call(client_for(), token=opaque(64))

    assert len(step_lines(response.text)) == len(exchange_dryrun.STEPS)


def test_the_machine_readable_answer_carries_one_entry_per_step_of_the_rule() -> None:
    payload = call(client_for(), token=opaque(64), as_json=True).json()

    assert [entry["step"] for entry in payload["steps"]] == list(exchange_dryrun.STEPS)


def test_the_spellings_this_module_copies_stay_equal_to_the_ones_it_copied() -> None:
    """WR-24-03: two constants of this module said a test held them, and none did.

    ``lifecycle`` imports ``occ`` and ``occ`` imports this module, so the header name and the
    positive list are written out a fifth and a fourth time rather than imported, which is a
    decision the comments beside them state. The decision is only safe with this assertion
    under it: without one, a change made for the audit commands drifts away from the command
    that reads its input the same way, and the comment sends the next reader past the gap
    instead of into it.
    """
    assert exchange_check.HEADER_ORIGIN_IP == audit_verify.HEADER_ORIGIN_IP
    assert exchange_check.TRUE_WORDS == audit_verify.TRUE_WORDS
    assert exchange_check.JSON_OPTION == audit_verify.JSON_OPTION
    assert exchange_check.OCC_ENVELOPE == audit_verify.OCC_ENVELOPE
    assert exchange_check.MAX_ANNOUNCED_DIGITS == audit_verify.MAX_ANNOUNCED_DIGITS


def test_every_step_identifier_of_the_rule_has_a_name_an_administrator_reads() -> None:
    """The table of names is built here and nowhere else, so here is where it is held whole."""
    assert set(exchange_check.STEP_NAMES) == set(exchange_dryrun.STEPS)
    for name in exchange_check.STEP_NAMES.values():
        assert name.strip(), "a step without a name reads as a step without a rule"


def test_the_step_that_is_never_executed_says_so_in_both_shapes() -> None:
    """Pitfall 8: an absent step reads as a passed one, so it is named and carries its note."""
    text = call(client_for(), token=opaque(64)).text
    payload = call(client_for(), token=opaque(64), as_json=True).json()

    entry = next(
        item for item in payload["steps"] if item["step"] == exchange_dryrun.STEP_ACCOUNT_EXISTS
    )
    assert entry["note"] == exchange_dryrun.NOTE_WOULD_CALL_NEXTCLOUD
    assert exchange_check.STEP_NAMES[exchange_dryrun.STEP_ACCOUNT_EXISTS] in text


# --- the body bound against the token bound: T-24-25 and assumption A5 ----------------


def test_a_token_at_the_hard_bound_gets_through_the_body_bound() -> None:
    """The measurement A5 asks for on our own side: 8192 bytes may not fall at ``token_size``."""
    response = call(client_for(), token=opaque(exchange_dryrun.MAX_TOKEN_BYTES), as_json=True)
    payload = response.json()

    assert response.status_code == 200
    assert payload["checked"] is True
    assert exchange_dryrun.STEP_TOKEN_SIZE not in fallen(payload)
    assert fallen(payload) == [exchange_dryrun.STEP_TOKEN_SHAPE]


def test_a_token_above_the_hard_bound_falls_at_the_size_step_and_still_answers_200() -> None:
    payload = call(
        client_for(), token=opaque(exchange_dryrun.MAX_TOKEN_BYTES + 1), as_json=True
    ).json()

    assert payload["checked"] is True
    assert fallen(payload) == [exchange_dryrun.STEP_TOKEN_SIZE]


def test_the_body_bound_is_a_calculation_over_the_token_bound() -> None:
    """The relation has to stay visible: a literal would drift when the token bound moves."""
    source = Path(exchange_check.__file__).read_text(encoding="utf-8")

    assert exchange_check.MAX_BODY_BYTES > exchange_dryrun.MAX_TOKEN_BYTES
    assert str(exchange_check.MAX_BODY_BYTES) not in source


def test_a_body_above_the_bound_names_the_body_and_never_the_token() -> None:
    """WR-24-04: over the bound the handler read nothing, and it has to say that.

    The wrong answer this replaces was ``failed  a token was presented``, which reads as
    "you did not hand one over" to the one administrator who did, and it lands exactly where
    ``MAX_BODY_BYTES`` was chosen so it would not: on a token that is merely large. A
    sentence about a token nobody read is worse than a form error.
    """
    response = call(
        client_for(),
        body={"occ": {"options": {"token": "a" * (exchange_check.MAX_BODY_BYTES + 1)}}},
        headers={**appapi_headers(), "content-type": "application/json"},
    )

    assert response.status_code == 200
    assert exchange_check.OUTCOME_BODY_NOT_READ in response.text
    assert exchange_check.BODY_NOT_READ_SENTENCE in response.text
    assert exchange_check.STEP_NAMES[exchange_dryrun.STEP_TOKEN_PRESENT] not in response.text


def test_an_announced_body_above_the_bound_is_refused_the_same_way() -> None:
    """The half that is decided before a byte is on the wire takes the same named outcome."""
    response = call(
        client_for(),
        body={"occ": {"options": {"token": "a"}}},
        headers={
            **appapi_headers(),
            "content-type": "application/json",
            "content-length": str(exchange_check.MAX_BODY_BYTES + 1),
        },
    )

    assert response.status_code == 200
    assert exchange_check.OUTCOME_BODY_NOT_READ in response.text


def test_a_body_that_is_not_json_is_refused_the_same_way() -> None:
    """The third of the four, and the same reasoning: the option was set and never seen."""
    response = client_for().post(
        exchange_check.EXCHANGE_CHECK_PATH,
        content=b"{not json at all",
        headers={**appapi_headers(), "content-type": "application/json"},
    )

    assert response.status_code == 200
    assert exchange_check.OUTCOME_BODY_NOT_READ in response.text


def test_an_invocation_without_a_body_still_runs_the_rule() -> None:
    """The other side of the same distinction, and the reason it had to be made.

    An empty body is an administrator who set no option, which the rule has a first step
    for. It must keep answering with that step and never with the named refusal, or the fix
    above would have traded one wrong sentence for another.
    """
    response = client_for().post(
        exchange_check.EXCHANGE_CHECK_PATH,
        headers={**appapi_headers(), "content-type": "application/json"},
    )

    assert response.status_code == 200
    assert exchange_check.OUTCOME_BODY_NOT_READ not in response.text
    assert exchange_check.STEP_NAMES[exchange_dryrun.STEP_TOKEN_PRESENT] in response.text


# --- the token never comes back out: T-24-09 -------------------------------------------


def test_no_shape_of_the_answer_repeats_the_presented_token() -> None:
    token = opaque(256)
    text = call(client_for(), token=token).text
    machine = call(client_for(), token=token, as_json=True).text

    for body in (text, machine):
        assert MARKER not in body
        assert token not in body


def test_nothing_of_the_token_reaches_the_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("DEBUG"):
        call(client_for(), token=opaque(256))

    assert MARKER not in caplog.text


# --- the two states that are not a fallen rule -----------------------------------------


def test_a_call_without_a_token_falls_at_the_first_step_instead_of_raising() -> None:
    payload = call(client_for(), as_json=True).json()

    assert payload["checked"] is True
    assert fallen(payload) == [exchange_dryrun.STEP_TOKEN_PRESENT]


def test_an_instance_without_a_configured_exchange_path_says_exactly_that() -> None:
    """A list of fallen steps would send an administrator to the token, not to the config."""
    response = call(client_for(ENV), token=opaque(64))
    payload = call(client_for(ENV), token=opaque(64), as_json=True).json()

    assert response.status_code == 200
    assert exchange_check.NOT_CONFIGURED_SENTENCE in response.text
    assert step_lines(response.text) == []
    assert payload["checked"] is False
    assert payload["passed"] is False
    assert payload["outcome"] == exchange_check.OUTCOME_NOT_CONFIGURED
    assert "steps" not in payload


def test_a_failure_of_the_run_is_reported_by_type_and_never_by_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rule of this repository for an exception from outside: the class, never the text."""

    async def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("a message that may carry a path or a value")

    monkeypatch.setattr(exchange_check, "dry_run", explode)

    response = call(client_for(), token=opaque(64))
    payload = call(client_for(), token=opaque(64), as_json=True).json()

    assert response.status_code == 200
    assert "RuntimeError" in response.text
    assert "a message that may carry" not in response.text
    assert payload["checked"] is False
    assert payload["error"] == "RuntimeError"


def test_a_body_that_is_not_json_is_the_default_shape_and_not_a_rejection() -> None:
    response = call(
        client_for(),
        body=None,
        headers={**appapi_headers(), "content-type": "application/json"},
    )
    raw = TestClient(Starlette(routes=exchange_check.exchange_check_routes(ARMED))).post(
        exchange_check.EXCHANGE_CHECK_PATH,
        content=b"not json at all",
        headers={**appapi_headers(), "content-type": "application/json"},
    )

    assert response.status_code == 200
    assert raw.status_code == 200
    assert raw.headers["content-type"].startswith("text/plain")


def test_the_json_option_is_read_in_every_shape_appapi_may_send_it() -> None:
    """The flag reader of ``audit_verify``, held against the three shapes it has to survive."""
    bare = call(client_for(), token=opaque(64), body={"json": True})
    listed = call(client_for(), token=opaque(64), body={"occ": {"options": ["--json"]}})

    assert json.loads(bare.text)["checked"] is True
    assert json.loads(listed.text)["checked"] is True

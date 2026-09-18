"""The Nextcloud Login Flow v2 as this project drives it: three calls, one attempt each.

Threats covered here: T-03-31 (header injection through the client name, which arrives from
a dynamic client registration in plan 03-05), T-03-34 (a poll storm against Nextcloud),
T-03-36 (an app password or a poll token in a log record) and pitfall 7c (the absolute poll
address of the start answer, which the container may not be able to resolve at all).

Nothing here opens a socket. Every Nextcloud call is answered by respx, and every check that
counts requests reads the call counter of the route it registered, so "exactly one attempt"
is measured and not assumed.
"""

import base64
import logging
import re
from pathlib import Path

import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.nextcloud.target import NextcloudTarget
from mcp_connector.oauth import loginflow

BASE_URL = "http://nc.test"

#: The injected Nextcloud. No login flow call reads the deploy environment any more.
TARGET = NextcloudTarget.from_url(BASE_URL)

INIT_URL = f"{BASE_URL}{loginflow.INIT_PATH}"
POLL_URL = f"{BASE_URL}{loginflow.POLL_PATH}"
APP_PASSWORD_URL = f"{BASE_URL}{loginflow.APP_PASSWORD_PATH}"

#: What Nextcloud returns as ``poll.endpoint``: a public absolute URL built from
#: ``overwrite.cli.url``. It may point anywhere, and this project never calls it.
FOREIGN_POLL_ENDPOINT = "https://public.example.org/login/v2/poll"

LOGIN_URL = "https://cloud.example.com/index.php/login/v2/flow/abc123"
POLL_TOKEN = "poll-token-of-this-flow"
LOGIN_NAME = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"

SOURCE = Path(loginflow.__file__)


def start_body() -> dict[str, object]:
    """The answer of ``POST /index.php/login/v2``, in the shape Nextcloud sends it."""
    return {
        "poll": {"token": POLL_TOKEN, "endpoint": FOREIGN_POLL_ENDPOINT},
        "login": LOGIN_URL,
    }


def poll_body() -> dict[str, str]:
    return {"server": BASE_URL, "loginName": LOGIN_NAME, "appPassword": APP_PASSWORD}


def code_lines() -> list[str]:
    """The source of the module without comment lines, for the source gates below."""
    return [line for line in SOURCE.read_text(encoding="utf-8").splitlines() if "#" not in line]


# --- the client name that becomes the user agent (T-03-31) ---------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Claude", "Claude"),
        ("Claude\r\nX-Evil: yes", "ClaudeX-Evil: yes"),
        ("Claude\x00Code", "ClaudeCode"),
        ("Grüße", "Gre"),
        ("Claude \U0001f600 Code", "Claude Code"),
        ("a" * 300, "a" * loginflow.AGENT_NAME_LIMIT),
        ("   ", loginflow.AGENT_FALLBACK),
        ("", loginflow.AGENT_FALLBACK),
        ("\r\n\r\n", loginflow.AGENT_FALLBACK),
        ("‮‮", loginflow.AGENT_FALLBACK),
    ],
    ids=[
        "a plain name",
        "a header injection",
        "a null byte",
        "umlauts",
        "an emoji",
        "three hundred characters",
        "whitespace only",
        "an empty name",
        "line breaks only",
        "a right to left override",
    ],
)
def test_the_user_agent_is_cleaned_and_prefixed(raw: str, expected: str) -> None:
    """Printable ASCII, no CR, no LF, length capped, and always the fixed prefix."""
    agent = loginflow.safe_user_agent(raw)

    assert agent == f"{loginflow.AGENT_PREFIX}{expected}"
    assert "\r" not in agent
    assert "\n" not in agent
    assert agent.isascii()
    assert agent.isprintable()
    assert len(agent) <= len(loginflow.AGENT_PREFIX) + loginflow.AGENT_NAME_LIMIT


def test_the_user_agent_is_never_empty_and_always_a_valid_header_value() -> None:
    """httpx refuses a header value with a control character; so does this function."""
    for raw in ("", "\r\n", "\x00\x01\x02", "\U0001f600"):
        agent = loginflow.safe_user_agent(raw)
        assert agent.strip()
        headers = httpx.Headers({"User-Agent": agent})
        assert headers["User-Agent"] == agent


# --- starting the flow ---------------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_the_start_sends_one_request_and_returns_the_token_and_the_login_url() -> None:
    route = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))

    started = await loginflow.start_flow("Claude", target=TARGET)

    assert route.call_count == 1
    assert started is not None
    assert started.poll_token == POLL_TOKEN
    assert started.login_url == LOGIN_URL


@respx.mock
@pytest.mark.anyio
async def test_the_start_sends_the_cleaned_client_name_as_the_user_agent() -> None:
    route = respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))

    await loginflow.start_flow("Claude\r\nX-Evil: yes", target=TARGET)

    sent = route.calls[0].request.headers["user-agent"]
    assert sent == f"{loginflow.AGENT_PREFIX}ClaudeX-Evil: yes"
    assert "evil" not in {name.lower() for name in route.calls[0].request.headers}


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 302])
async def test_a_start_that_is_not_a_200_is_a_named_failure(status: int) -> None:
    route = respx.post(INIT_URL).mock(return_value=httpx.Response(status, json={}))

    assert await loginflow.start_flow("Claude", target=TARGET) is None
    assert route.call_count == 1, "a failed start must not be retried"


@respx.mock
@pytest.mark.anyio
async def test_a_start_that_does_not_reach_nextcloud_is_a_named_failure() -> None:
    route = respx.post(INIT_URL).mock(side_effect=httpx.ConnectError("no route to host"))

    assert await loginflow.start_flow("Claude", target=TARGET) is None
    assert route.call_count == 1


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"poll": {}, "login": LOGIN_URL},
        {"poll": {"token": POLL_TOKEN}},
        {"poll": {"token": ""}, "login": LOGIN_URL},
        {"poll": {"token": POLL_TOKEN}, "login": ""},
        {"poll": "not a mapping", "login": LOGIN_URL},
        {"poll": {"token": 17}, "login": LOGIN_URL},
    ],
    ids=[
        "an empty object",
        "no token",
        "no login url",
        "an empty token",
        "an empty login url",
        "a poll field that is not an object",
        "a token that is not a string",
    ],
)
async def test_a_start_answer_this_code_cannot_read_is_a_named_failure(body: object) -> None:
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=body))

    assert await loginflow.start_flow("Claude", target=TARGET) is None


@respx.mock
@pytest.mark.anyio
async def test_a_start_answer_that_is_not_json_is_a_named_failure() -> None:
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, html="<html>login</html>"))

    assert await loginflow.start_flow("Claude", target=TARGET) is None


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "login",
    ["javascript:alert(1)", "data:text/html,<script>x</script>", "/login/v2/flow/abc", "ftp://x/y"],
    ids=["javascript", "a data url", "a bare path", "another scheme"],
)
async def test_a_login_url_that_is_not_http_is_refused(login: str) -> None:
    """The value is rendered as a link a human clicks, so a scheme check is not cosmetics."""
    body = start_body()
    body["login"] = login
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=body))

    assert await loginflow.start_flow("Claude", target=TARGET) is None


# --- polling (T-03-34, pitfall 7) ------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_one_poll_is_exactly_one_request_against_the_configured_base_url() -> None:
    poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))
    foreign = respx.post(FOREIGN_POLL_ENDPOINT).mock(return_value=httpx.Response(200))

    result = await loginflow.poll_once(POLL_TOKEN, target=TARGET)

    assert poll.call_count == 1
    assert foreign.call_count == 0, "the absolute endpoint of the answer must never be called"
    assert result.outcome == loginflow.POLL_PENDING
    assert result.credentials is None


@respx.mock
@pytest.mark.anyio
async def test_three_polls_are_three_requests_and_nothing_else() -> None:
    poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))

    for _ in range(3):
        await loginflow.poll_once(POLL_TOKEN, target=TARGET)

    assert poll.call_count == 3


@respx.mock
@pytest.mark.anyio
async def test_the_poll_sends_the_token_as_a_form_field() -> None:
    poll = respx.post(POLL_URL).mock(return_value=httpx.Response(404))

    await loginflow.poll_once(POLL_TOKEN, target=TARGET)

    request = poll.calls[0].request
    assert request.content == f"token={POLL_TOKEN}".encode()
    assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")


@respx.mock
@pytest.mark.anyio
async def test_a_poll_that_answers_200_carries_the_credentials() -> None:
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))

    result = await loginflow.poll_once(POLL_TOKEN, target=TARGET)

    assert result.outcome == loginflow.POLL_DONE
    assert result.credentials is not None
    assert result.credentials.login_name == LOGIN_NAME
    assert result.credentials.app_password == APP_PASSWORD


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 302])
async def test_any_other_poll_status_is_a_named_failure_without_a_second_attempt(
    status: int,
) -> None:
    poll = respx.post(POLL_URL).mock(return_value=httpx.Response(status, json={}))

    result = await loginflow.poll_once(POLL_TOKEN, target=TARGET)

    assert result.outcome == loginflow.POLL_FAILED
    assert result.credentials is None
    assert poll.call_count == 1


@respx.mock
@pytest.mark.anyio
async def test_a_poll_that_does_not_reach_nextcloud_is_a_named_failure() -> None:
    poll = respx.post(POLL_URL).mock(side_effect=httpx.ReadTimeout("too slow"))

    result = await loginflow.poll_once(POLL_TOKEN, target=TARGET)

    assert result.outcome == loginflow.POLL_FAILED
    assert poll.call_count == 1


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"loginName": LOGIN_NAME},
        {"appPassword": APP_PASSWORD},
        {"loginName": "", "appPassword": ""},
    ],
    ids=["empty", "no app password", "no login name", "both empty"],
)
async def test_a_poll_answer_without_credentials_is_a_named_failure(body: object) -> None:
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=body))

    result = await loginflow.poll_once(POLL_TOKEN, target=TARGET)

    assert result.outcome == loginflow.POLL_FAILED
    assert result.credentials is None


# --- revoking the app password ---------------------------------------------------------


@respx.mock
@pytest.mark.anyio
async def test_the_revocation_sends_one_delete_with_the_credentials_of_that_password() -> None:
    route = respx.delete(APP_PASSWORD_URL).mock(return_value=httpx.Response(200, json={}))

    assert await loginflow.revoke_app_password(LOGIN_NAME, APP_PASSWORD, target=TARGET) is True

    request = route.calls[0].request
    expected = base64.b64encode(f"{LOGIN_NAME}:{APP_PASSWORD}".encode()).decode()
    assert route.call_count == 1
    assert request.headers["authorization"] == f"Basic {expected}"
    assert request.headers["ocs-apirequest"] == "true"
    assert request.headers["accept"] == "application/json"


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("status", [200, 401])
async def test_the_revocation_counts_deleted_and_already_gone_as_success(status: int) -> None:
    """401 means the user was faster than we were, and that is the wanted end state."""
    respx.delete(APP_PASSWORD_URL).mock(return_value=httpx.Response(status, json={}))

    assert await loginflow.revoke_app_password(LOGIN_NAME, APP_PASSWORD, target=TARGET) is True


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize("status", [403, 404, 429, 500])
async def test_any_other_revocation_status_is_a_failure_without_a_second_attempt(
    status: int,
) -> None:
    route = respx.delete(APP_PASSWORD_URL).mock(return_value=httpx.Response(status, json={}))

    assert await loginflow.revoke_app_password(LOGIN_NAME, APP_PASSWORD, target=TARGET) is False
    assert route.call_count == 1


@respx.mock
@pytest.mark.anyio
async def test_a_revocation_that_does_not_reach_nextcloud_is_a_failure_not_an_exception() -> None:
    """Pitfall 13: a failed deletion may never block the revocation path that called it."""
    route = respx.delete(APP_PASSWORD_URL).mock(side_effect=httpx.ConnectError("gone"))

    assert await loginflow.revoke_app_password(LOGIN_NAME, APP_PASSWORD, target=TARGET) is False
    assert route.call_count == 1


# --- secrets stay out of reprs and out of the log (T-03-36) ------------------------------


def test_the_containers_mask_their_secrets() -> None:
    started = loginflow.FlowStart(poll_token=POLL_TOKEN, login_url=LOGIN_URL)
    credentials = loginflow.AppCredentials(login_name=LOGIN_NAME, app_password=APP_PASSWORD)

    assert POLL_TOKEN not in repr(started)
    assert POLL_TOKEN not in f"{started}"
    assert LOGIN_URL in repr(started)
    assert APP_PASSWORD not in repr(credentials)
    assert APP_PASSWORD not in f"{credentials}"
    assert LOGIN_NAME in repr(credentials)


@respx.mock
@pytest.mark.anyio
async def test_no_secret_reaches_the_log_at_debug_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    respx.post(INIT_URL).mock(return_value=httpx.Response(500, json={}))
    respx.post(POLL_URL).mock(return_value=httpx.Response(500, json={}))
    respx.delete(APP_PASSWORD_URL).mock(return_value=httpx.Response(500, json={}))

    with caplog.at_level(logging.DEBUG, logger="mcp_connector"):
        await loginflow.start_flow("Claude", target=TARGET)
        await loginflow.poll_once(POLL_TOKEN, target=TARGET)
        await loginflow.revoke_app_password(LOGIN_NAME, APP_PASSWORD, target=TARGET)

    text = caplog.text
    assert text, "the failures were not logged at all"
    for secret in (POLL_TOKEN, APP_PASSWORD):
        assert secret not in text


@respx.mock
@pytest.mark.anyio
async def test_a_successful_flow_logs_no_secret_either(caplog: pytest.LogCaptureFixture) -> None:
    respx.post(INIT_URL).mock(return_value=httpx.Response(200, json=start_body()))
    respx.post(POLL_URL).mock(return_value=httpx.Response(200, json=poll_body()))
    respx.delete(APP_PASSWORD_URL).mock(return_value=httpx.Response(200, json={}))

    with caplog.at_level(logging.DEBUG, logger="mcp_connector"):
        await loginflow.start_flow("Claude", target=TARGET)
        await loginflow.poll_once(POLL_TOKEN, target=TARGET)
        await loginflow.revoke_app_password(LOGIN_NAME, APP_PASSWORD, target=TARGET)

    for secret in (POLL_TOKEN, APP_PASSWORD):
        assert secret not in caplog.text


# --- source gates ------------------------------------------------------------------------


@pytest.mark.parametrize("needle", ["for attempt", "while True", "retries", "retry("])
def test_the_module_carries_no_retry_loop(needle: str) -> None:
    """D-37 and pitfall 13: one attempt per call, and a failure is a return value."""
    assert not any(needle in line for line in code_lines()), f"{needle!r} is a retry"


def test_the_absolute_poll_endpoint_of_the_answer_is_never_read() -> None:
    """Pitfall 7c: it is a public URL from overwrite.cli.url and may not resolve here."""
    for line in code_lines():
        assert '"endpoint"' not in line, line
        assert ".endpoint" not in line, line


def test_every_url_of_this_module_is_built_from_the_configured_base_url() -> None:
    """Shared pattern 2 of 03-PATTERNS.md: configuration decides the target, never a body."""
    urls = [line for line in code_lines() if "http://" in line or "https://" in line]
    assert urls == [], urls


def test_the_module_opens_no_client_of_its_own() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "AsyncClient(" not in source
    assert "shared_client()" in source


def test_the_three_paths_are_the_ones_of_the_research() -> None:
    assert loginflow.INIT_PATH == "/index.php/login/v2"
    assert loginflow.POLL_PATH == "/login/v2/poll"
    assert loginflow.APP_PASSWORD_PATH == "/ocs/v2.php/core/apppassword"
    assert re.fullmatch(r"MCP Connector: ", loginflow.AGENT_PREFIX)


# --- the injected target (standalone OAuth, slice 2) ---------------------------------------

INJECTED_BASE = "https://cloud.injected.example/nextcloud"
INJECTED = NextcloudTarget.from_url(INJECTED_BASE)


@respx.mock
@pytest.mark.anyio
async def test_all_three_calls_go_to_the_injected_target_and_ignore_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deploy environment names another Nextcloud; none of the three calls follows it."""
    monkeypatch.setenv(config.ENV_NEXTCLOUD_URL, "http://environment.example")
    monkeypatch.setenv(config.ENV_URL, "http://environment.example")
    init = respx.post(f"{INJECTED_BASE}{loginflow.INIT_PATH}").mock(
        return_value=httpx.Response(200, json=start_body())
    )
    poll = respx.post(f"{INJECTED_BASE}{loginflow.POLL_PATH}").mock(
        return_value=httpx.Response(404)
    )
    revoke = respx.delete(f"{INJECTED_BASE}{loginflow.APP_PASSWORD_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )

    assert await loginflow.start_flow("Claude", target=INJECTED) is not None
    assert (await loginflow.poll_once(POLL_TOKEN, target=INJECTED)).outcome == (
        loginflow.POLL_PENDING
    )
    assert await loginflow.revoke_app_password(LOGIN_NAME, APP_PASSWORD, target=INJECTED)

    assert (init.call_count, poll.call_count, revoke.call_count) == (1, 1, 1)


@pytest.mark.parametrize("function", ["start_flow", "poll_once", "revoke_app_password"])
def test_the_target_is_a_required_keyword_without_a_default(function: str) -> None:
    """No hidden fallback to the ExApp environment: a caller has to name the target."""
    import inspect

    parameter = inspect.signature(getattr(loginflow, function)).parameters["target"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
    assert "env" not in inspect.signature(getattr(loginflow, function)).parameters


def test_the_module_no_longer_reads_the_deploy_environment() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "exapp_settings" not in source
    assert "os.environ" not in source


# --- the canonical account id -------------------------------------------------------------

ACCOUNT_URL = f"{BASE_URL}{loginflow.ACCOUNT_PATH}"


def ocs_user(value: object, **extra: object) -> dict[str, object]:
    data: dict[str, object] = {"id": value, **extra}
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": data}}


@respx.mock
@pytest.mark.anyio
async def test_the_account_id_is_read_with_the_fresh_app_password() -> None:
    route = respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=ocs_user("a1b2c3")))

    found = await loginflow.account(LOGIN_NAME, APP_PASSWORD, target=TARGET)
    assert found == loginflow.Account(account_id="a1b2c3", display_name=None)

    assert route.call_count == 1
    sent = route.calls.last.request
    expected = base64.b64encode(f"{LOGIN_NAME}:{APP_PASSWORD}".encode()).decode()
    assert sent.headers["Authorization"] == f"Basic {expected}"
    assert sent.headers["OCS-APIRequest"] == "true"


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={}),
        httpx.Response(500, json={}),
        httpx.Response(200, text="<html>login</html>"),
        httpx.Response(200, json={"ocs": {"data": {}}}),
        httpx.Response(200, json=ocs_user("")),
        httpx.Response(200, json=ocs_user(42)),
        httpx.Response(200, json=ocs_user(" alice")),
        httpx.Response(200, json=ocs_user("ali\nce")),
        httpx.Response(200, json=[]),
    ],
    ids=[
        "401",
        "500",
        "html",
        "no id",
        "empty id",
        "number",
        "padded",
        "control character",
        "list",
    ],
)
async def test_an_unusable_answer_is_no_account(response: httpx.Response) -> None:
    respx.get(ACCOUNT_URL).mock(return_value=response)
    assert await loginflow.account(LOGIN_NAME, APP_PASSWORD, target=TARGET) is None


@respx.mock
@pytest.mark.anyio
async def test_an_unreachable_nextcloud_is_no_account_and_logs_no_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    respx.get(ACCOUNT_URL).mock(side_effect=httpx.ConnectError("down"))
    with caplog.at_level(logging.DEBUG, logger="mcp_connector"):
        assert await loginflow.account(LOGIN_NAME, APP_PASSWORD, target=TARGET) is None
    assert APP_PASSWORD not in caplog.text


@respx.mock
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"displayname": "Alice Adams"}, "Alice Adams"),
        ({"display-name": "Alice Adams"}, "Alice Adams"),
        ({"displayname": "Alice Adams", "display-name": "Stale"}, "Alice Adams"),
        ({"displayname": "", "display-name": "Alice Adams"}, "Alice Adams"),
        ({"displayname": "   "}, None),
        ({"displayname": 42}, None),
        ({}, None),
    ],
    ids=[
        "displayname",
        "hyphenated",
        "both",
        "empty first",
        "whitespace",
        "number",
        "absent",
    ],
)
async def test_the_display_name_is_taken_along_or_left_out(
    data: dict[str, object], expected: str | None
) -> None:
    """The display name rides on the answer that resolves the account, and never fails it."""
    respx.get(ACCOUNT_URL).mock(return_value=httpx.Response(200, json=ocs_user("a1b2c3", **data)))

    found = await loginflow.account(LOGIN_NAME, APP_PASSWORD, target=TARGET)

    assert found is not None
    assert found.account_id == "a1b2c3"
    assert found.display_name == expected


@respx.mock
@pytest.mark.anyio
async def test_a_display_name_does_not_rescue_an_unusable_account_id() -> None:
    """Identity is the id. A name is never a substitute for one."""
    respx.get(ACCOUNT_URL).mock(
        return_value=httpx.Response(200, json=ocs_user("", displayname="Alice Adams"))
    )

    assert await loginflow.account(LOGIN_NAME, APP_PASSWORD, target=TARGET) is None

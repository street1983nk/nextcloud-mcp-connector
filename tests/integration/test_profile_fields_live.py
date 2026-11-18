"""Live proof of the opt-in ``profile_fields_browse`` tool against a real Profile Fields app.

The unit tests of the tool answer mocked OCS envelopes, so they prove the shape the tool
expects and nothing about the shape the app sends, and nothing at all about who is allowed
to read what. This file measures both against the store release of ``profile_fields`` on a
running Nextcloud, through a real MCP client over Streamable HTTP:

*   without the switch ``NC_MCP_PROFILE_FIELDS_READ`` the server lists exactly the 27 tools
    of the default registry and the tool is neither listed nor callable; with the switch it
    is the one additional tool (the positive control of the absence),
*   an administrator gets the field definitions back,
*   an account reads its own value and never the value of the other account,
*   an account without administrator rights gets no foreign value over any level of the
    tool, while an administrator gets exactly that value with exactly those arguments (the
    positive control, without which the refusal could be an empty pass).

The world is built and checked a second time **without** the code under test: the field,
the two values and the counter check of the app's own guard go through plain ``httpx``
requests against the OCS routes of the app (``lib/Controller`` of profile_fields 4.0.0:
``POST /definitions``, ``PUT /users/{uid}/values/{id}``, ``GET /users/{uid}/values``).
The module creates its own administrator with a random password, passed through the
environment of ``docker exec`` and never through an argument, and deletes it again, so it
depends on no administrator password of the instance. The two markers are random and
carry no secret.

Both servers run in passthrough mode, as in ``test_http_tool_call.py``: the account of a
call is the Basic header of that call and nothing else.

The CI step sets every switch; the job-wide ``pytest -m integration`` sets none of them and
skips this file. ``NC_MCP_EXPECT_PROFILE_FIELDS=1`` is the demand: with it, every missing
prerequisite fails instead of skipping. The job ``integration`` must not carry the switch
``NC_MCP_REQUIRE_LIVE`` (``tests/unit/test_live_requirement.py``), so this file brings a
demand of its own::

    docker compose -f compose.test.yml exec -T --user www-data nextcloud \\
        php occ app:install profile_fields
    set -a && . ./.env.test && set +a
    NC_MCP_E2E_NEXTCLOUD=nc-mcp-test NC_MCP_EXPECT_PROFILE_FIELDS=1 \\
        NC_MCP_PROFILE_FIELDS_READ=on PYTHONUTF8=1 \\
        uv run pytest tests/integration/test_profile_fields_live.py -m integration -s
"""

import base64
import dataclasses
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NoReturn

import canary_world as cw
import httpx
import httpx2
import pytest
import topology
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from mcp_connector import config
from mcp_connector.config import normalize_base_url

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = "profile_fields_browse"
#: Counted at the code, not copied from the unit test: the ``@mcp.tool`` decorators at module
#: level of the twelve ``server/reg_*.py`` files. The four indented ones (``files_update`` and
#: the three modifying task tools) hang on switches of their own, which the servers of this
#: file never see.
DEFAULT_TOOL_COUNT = 27
ENV_EXPECT = "NC_MCP_EXPECT_PROFILE_FIELDS"
REQUIRED = {
    "base_url": "NC_MCP_URL",
    "alice": "NC_MCP_USER",
    "alice_secret": "NC_MCP_APP_PASSWORD",
    "bob": "NC_MCP_TEST_USER2",
    "bob_secret": "NC_MCP_TEST_APP_PASSWORD2",
}
#: Switches that change the tool list. No server of this file inherits them from the caller.
LIST_SWITCHES = (
    config.ENV_PROFILE_FIELDS_READ,
    config.ENV_DISABLED_TOOLS,
    config.ENV_FILES_UPDATE,
    config.ENV_TASKS_UPDATE,
)
API = "/ocs/v2.php/apps/profile_fields/api/v1"
OCS_HEADERS = {"OCS-APIRequest": "true", "Accept": "application/json"}
STAMP = uuid.uuid4().hex[:8]


@dataclasses.dataclass(frozen=True)
class World:
    """One private text field with one value per account, and who may read all of it."""

    base_url: str
    field_key: str
    field_id: int
    admin: tuple[str, str]
    alice: tuple[str, str]
    bob: tuple[str, str]
    alice_value: str
    bob_value: str


def demand(reason: str) -> NoReturn:
    """Fail on a missing prerequisite. Only reached once :data:`ENV_EXPECT` asked for the run."""
    pytest.fail(f"{ENV_EXPECT}=1 but {reason}", pytrace=False)


def basic(account: tuple[str, str]) -> str:
    return "Basic " + base64.b64encode(f"{account[0]}:{account[1]}".encode()).decode()


def _json_of(output: str) -> Any:
    start = output.find("{")
    assert start >= 0, f"no JSON in: {output[:300]}"
    return json.loads(output[start:])


def _ocs_data(response: httpx.Response, what: str, expected: int) -> Any:
    assert response.status_code == expected, f"{what}: HTTP {response.status_code}"
    return response.json()["ocs"]["data"]


# --- the instance ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def env() -> dict[str, str]:
    """The two accounts of ``.env.test`` and a Nextcloud that really carries the app."""
    if (os.environ.get(ENV_EXPECT) or "").strip() != "1":
        pytest.skip(f"no Profile Fields run configured ({ENV_EXPECT} is not 1)")
    values = {key: (os.environ.get(name) or "").strip() for key, name in REQUIRED.items()}
    missing = sorted(REQUIRED[key] for key, value in values.items() if not value)
    if missing:
        demand(f"no test Nextcloud configured (missing: {', '.join(missing)})")
    if not config.profile_fields_read_enabled():
        demand(f"{config.ENV_PROFILE_FIELDS_READ} is not switched on for this run")
    if shutil.which("docker") is None:
        demand("docker is not on PATH, occ cannot build the world")
    # The app state is read a second time with occ, so a run against an instance without
    # the app fails here with its name instead of as a 404 inside a tool answer.
    enabled = _json_of(cw.occ("app:list", "--output=json")).get("enabled") or {}
    if "profile_fields" not in enabled:
        demand(f"profile_fields is not enabled in {topology.NC_CONTAINER}")
    status = _json_of(cw.occ("status", "--output=json"))
    print(
        f"\nPROFILE-FIELDS nextcloud={status.get('versionstring')} "
        f"app={enabled['profile_fields']} container={topology.NC_CONTAINER}"
    )
    assert "admin" not in (values["alice"], values["bob"]), "both accounts are normal users"
    assert values["alice"] != values["bob"], "the refusal needs two different accounts"
    values["base_url"] = normalize_base_url(values["base_url"])
    return values


@pytest.fixture(scope="module")
def admin(env: dict[str, str]) -> Iterator[tuple[str, str]]:
    """An administrator of this run only; the password never reaches an argv or the log."""
    del env
    uid = f"pfadm{STAMP}"
    password = f"Pf-{secrets.token_urlsafe(24)}-9a"
    try:
        finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
            [  # noqa: S607
                "docker",
                "exec",
                "-e",
                "OC_PASS",
                "-u",
                "www-data",
                topology.NC_CONTAINER,
                "php",
                "occ",
                "user:add",
                "--password-from-env",
                uid,
            ],
            env={**os.environ, "OC_PASS": password},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert finished.returncode == 0, f"user:add failed: {(finished.stdout or '')[:200]}"
        cw.occ("group:adduser", "admin", uid)
        yield uid, password
    finally:
        cw.occ("user:delete", uid, check_status=False)


@pytest.fixture(scope="module")
def world(env: dict[str, str], admin: tuple[str, str]) -> Iterator[World]:
    """The field and both values, written over the app's own OCS routes as the administrator.

    ``editPolicy=admins`` and ``exposurePolicy=private`` are the strictest pair the app
    offers for a value its owner can still see: nobody but the owner and an administrator
    may read it (``FieldAccessService::canViewValue``). The visibility each value really
    got is read back from the answer, because the refusals below are only worth something
    for a value that is private.
    """
    key = f"mcp_live_{STAMP}"
    marks = {name: f"pf-{name}-{uuid.uuid4().hex[:12]}" for name in ("alice", "bob")}
    with httpx.Client(
        base_url=env["base_url"] + API, auth=admin, headers=OCS_HEADERS, timeout=30.0
    ) as http:
        created = _ocs_data(
            http.post(
                "/definitions",
                json={
                    "fieldKey": key,
                    "label": f"MCP live {STAMP}",
                    "type": "text",
                    "editPolicy": "admins",
                    "exposurePolicy": "private",
                },
            ),
            "create the field definition",
            201,
        )
        field_id = created["id"]
        assert isinstance(field_id, int), created
        try:
            for name in ("alice", "bob"):
                stored = _ocs_data(
                    http.put(f"/users/{env[name]}/values/{field_id}", json={"value": marks[name]}),
                    f"store the value of {name}",
                    200,
                )
                assert stored["user_uid"] == env[name], stored
                assert stored["current_visibility"] == "private", stored
            yield World(
                base_url=env["base_url"],
                field_key=key,
                field_id=field_id,
                admin=admin,
                alice=(env["alice"], env["alice_secret"]),
                bob=(env["bob"], env["bob_secret"]),
                alice_value=marks["alice"],
                bob_value=marks["bob"],
            )
        finally:
            http.delete(f"/definitions/{field_id}")


# --- the two servers ------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def running_server(base_url: str, switch: str | None) -> Iterator[str]:
    """A uvicorn subprocess in passthrough mode; ``switch`` is the only list switch it sees."""
    port = free_port()
    env = dict(os.environ.items())
    for name in ("NC_MCP_USER", "NC_MCP_APP_PASSWORD", "NC_MCP_STATIC_BEARER", *LIST_SWITCHES):
        env.pop(name, None)
    if switch is not None:
        env[config.ENV_PROFILE_FIELDS_READ] = switch
    env["NC_MCP_URL"] = base_url
    env["NC_MCP_ALLOWED_HOSTS"] = "127.0.0.1"
    process = subprocess.Popen(  # noqa: S603 - fixed command from our own package
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mcp_connector.entry_http:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    deadline = time.monotonic() + 60.0
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                pytest.fail(f"uvicorn exited early: {output[:2000]}")
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=2.0).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        else:  # pragma: no cover - only on a hung server
            pytest.fail("the MCP server did not become healthy")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
            process.wait(timeout=30)


@pytest.fixture(scope="module")
def server_on(env: dict[str, str]) -> Iterator[str]:
    """The server with the switch exactly as the run set it (checked in ``env``)."""
    with running_server(env["base_url"], os.environ[config.ENV_PROFILE_FIELDS_READ]) as url:
        yield url


@pytest.fixture(scope="module")
def server_off(env: dict[str, str]) -> Iterator[str]:
    """The same server without the switch: the state every installation starts in."""
    with running_server(env["base_url"], None) as url:
        yield url


# --- the client -----------------------------------------------------------------------


async def tool_names(url: str, account: tuple[str, str]) -> list[str]:
    """Every tool name ``tools/list`` hands a real client, across all pages."""
    names: list[str] = []
    cursor: str | None = None
    async with (
        httpx2.AsyncClient(
            headers={"Authorization": basic(account)}, timeout=httpx2.Timeout(30.0, read=120.0)
        ) as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        for _ in range(20):
            page = await client.list_tools(cursor=cursor)
            names.extend(tool.name for tool in page.tools)
            cursor = page.next_cursor
            if cursor is None:
                break
    return names


async def call(url: str, account: tuple[str, str], name: str, arguments: dict[str, Any]) -> Any:
    """Call one tool as ``account`` and return the decoded JSON answer."""
    async with (
        httpx2.AsyncClient(
            headers={"Authorization": basic(account)}, timeout=httpx2.Timeout(30.0, read=120.0)
        ) as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        result = await client.call_tool(name, arguments)
    text = "\n".join(b.text for b in result.content if isinstance(b, TextContent) and b.text)
    if result.is_error:
        raise AssertionError(f"tool error: {text}")
    return json.loads(text)


def describe(exc: BaseException) -> str:
    """Flatten an ExceptionGroup: anyio wraps a JSON-RPC error into a TaskGroup failure."""
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(describe(sub) for sub in exc.exceptions)
    return f"{type(exc).__name__}: {exc}"


async def refusal(url: str, account: tuple[str, str], name: str, arguments: dict[str, Any]) -> str:
    """Call a tool that has to fail and return everything the caller got to see of it."""
    try:
        answer = await call(url, account, name, arguments)
    except AssertionError as exc:
        return str(exc)
    except Exception as exc:
        return describe(exc)
    raise AssertionError(f"expected a refusal, got an answer: {json.dumps(answer)[:300]}")


def own_value(answer: dict[str, Any], field_key: str) -> Any:
    """The value of ``field_key`` in a ``level=me`` answer, or ``None`` when it is absent."""
    for entry in answer["results"]:
        if entry["definition"]["field_key"] == field_key:
            return entry["value"]["value"]["value"]
    return None


# --- the switch -----------------------------------------------------------------------


async def test_without_the_switch_the_registry_is_the_27_default_tools(
    server_off: str, server_on: str, world: World
) -> None:
    off = await tool_names(server_off, world.alice)
    on = await tool_names(server_on, world.alice)
    print(f"PROFILE-FIELDS tools without switch={len(off)} with switch={len(on)}")

    assert len(off) == len(set(off)) == DEFAULT_TOOL_COUNT, sorted(off)
    assert not [name for name in off if name.startswith("profile_fields")], sorted(off)
    # The positive control: the same listing does show the tool once the switch is on, and
    # the switch adds this one tool and nothing else.
    assert sorted(on) == sorted([*off, TOOL])


async def test_without_the_switch_the_tool_cannot_be_called_either(
    server_off: str, world: World
) -> None:
    """A tool that is only hidden from the list would still be an open door."""
    message = await refusal(server_off, world.admin, TOOL, {"level": "definitions"})

    assert world.field_key not in message, message


# --- what comes back ------------------------------------------------------------------


async def test_an_administrator_gets_the_field_definitions(server_on: str, world: World) -> None:
    answer = await call(server_on, world.admin, TOOL, {"level": "definitions"})

    found = [entry for entry in answer["results"] if entry.get("field_key") == world.field_key]
    assert len(found) == 1, answer
    assert found[0]["id"] == world.field_id
    assert found[0]["type"] == "text"
    assert answer["count"] == len(answer["results"])


async def test_each_account_reads_its_own_value_and_not_the_other_one(
    server_on: str, world: World
) -> None:
    for account, own, foreign in (
        (world.alice, world.alice_value, world.bob_value),
        (world.bob, world.bob_value, world.alice_value),
    ):
        answer = await call(server_on, account, TOOL, {"level": "me"})

        assert own_value(answer, world.field_key) == own, f"{account[0]}: {answer}"
        assert foreign not in json.dumps(answer), f"{account[0]} reads a foreign value"


# --- what does not come back ----------------------------------------------------------


def foreign_reads(world: World) -> dict[str, dict[str, Any]]:
    """Every level of the tool that could hand out the value of alice to somebody else."""
    return {
        "values": {
            "level": "values",
            "user_uid": world.alice[0],
            "field_keys": world.field_key,
        },
        "search": {
            "level": "search",
            "field_key": world.field_key,
            "value": world.alice_value,
        },
    }


async def test_an_administrator_reads_the_value_of_alice(server_on: str, world: World) -> None:
    """The positive control. Without it, a refusal for bob below proves nothing."""
    reads = foreign_reads(world)

    values = await call(server_on, world.admin, TOOL, reads["values"])
    assert values["fields"] == {
        world.field_key: {"value": world.alice_value, "current_visibility": "private"}
    }

    search = await call(server_on, world.admin, TOOL, reads["search"])
    assert search["results"] == [{"user_uid": world.alice[0], "value": world.alice_value}]
    assert search["total"] == 1


async def test_bob_gets_no_value_of_alice_over_any_level(server_on: str, world: World) -> None:
    """The same server and the same arguments as above; only the account differs."""
    reads = {**foreign_reads(world), "definitions": {"level": "definitions"}}
    for case, arguments in reads.items():
        message = await refusal(server_on, world.bob, TOOL, arguments)

        assert world.alice_value not in message, f"{case}: the refusal carries the value"


def test_the_app_itself_refuses_bob_the_values_of_alice(world: World) -> None:
    """The counter check without the tool: the route behind ``level=values``, asked directly.

    The tool reads the definitions first and is refused there, so the test above never
    reaches ``/users/{uid}/values`` as bob. This one does, with nothing of this project in
    between, and the administrator on the very same route is its positive control.
    """
    url = f"{world.base_url}{API}/users/{world.alice[0]}/values"

    as_admin = httpx.get(url, auth=world.admin, headers=OCS_HEADERS, timeout=30.0)
    assert as_admin.status_code == 200
    assert world.alice_value in as_admin.text

    as_bob = httpx.get(url, auth=world.bob, headers=OCS_HEADERS, timeout=30.0)
    assert as_bob.status_code >= 400, f"bob is answered with HTTP {as_bob.status_code}"
    assert world.alice_value not in as_bob.text

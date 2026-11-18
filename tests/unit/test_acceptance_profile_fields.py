"""The acceptance run and the optional tool ``profile_fields_browse``.

``scripts/acceptance_all_tools.py`` runs against a real Nextcloud and is no test of this
suite. One of its decisions can be held without one: what it makes of a tool whose app the
test instance does not carry. (Which switches it hands on to the server it starts is held by
``tests/contract/test_tool_surface.py``, beside the other lists of switches.) The instance
is replaced by a client that answers what this file tells it to; the question to the app
itself is replaced the same way.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from mcp.types import TextContent

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "acceptance_all_tools.py"
TOOL = "profile_fields_browse"


@pytest.fixture(scope="module")
def acceptance() -> ModuleType:
    """The script, loaded by path so ``scripts/`` stays off ``sys.path``."""
    spec = importlib.util.spec_from_file_location("acceptance_all_tools", SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - a missing script is a red test
        raise RuntimeError(f"{SCRIPT} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeClient:
    """Answers one call the way the stdio client would, and keeps what it was asked."""

    def __init__(self, text: str, *, is_error: bool) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._result = SimpleNamespace(
            content=[TextContent(type="text", text=text)], is_error=is_error
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return self._result


def app_answers(
    monkeypatch: pytest.MonkeyPatch, acceptance: ModuleType, status: int | None
) -> list[int]:
    """Replace the question to the app itself; the list counts how often it was asked."""
    asked: list[int] = []

    async def answer() -> int | None:
        asked.append(1)
        return status

    monkeypatch.setattr(acceptance, "_profile_fields_app_status", answer)
    return asked


@pytest.mark.anyio
async def test_with_the_switch_off_the_tool_is_named_and_not_called(
    acceptance: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient("{}", is_error=False)
    report = acceptance.Report()

    await acceptance._profile_fields(client, report, registered={"files_read"})

    assert client.calls == []
    assert report.rows == []
    assert f"{TOOL}" in capsys.readouterr().out


@pytest.mark.anyio
async def test_the_own_values_are_one_call_and_an_ok(
    acceptance: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = app_answers(monkeypatch, acceptance, 200)
    client = FakeClient(json.dumps({"level": "me", "count": 0, "results": []}), is_error=False)
    report = acceptance.Report()

    await acceptance._profile_fields(client, report, registered={TOOL})

    assert client.calls == [(TOOL, {"level": "me"})]
    assert [(tool, verdict) for tool, verdict, _ in report.rows] == [(TOOL, "OK")]
    assert asked == [], "an answer needs no second opinion"


@pytest.mark.anyio
async def test_an_answer_that_is_no_list_of_values_is_a_failure(
    acceptance: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_answers(monkeypatch, acceptance, 200)
    client = FakeClient("no json at all", is_error=False)
    report = acceptance.Report()

    await acceptance._profile_fields(client, report, registered={TOOL})

    assert report.failures() == [TOOL]


@pytest.mark.anyio
async def test_a_missing_app_is_a_prerequisite_and_neither_a_pass_nor_a_skip(
    acceptance: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = app_answers(monkeypatch, acceptance, 404)
    client = FakeClient("Nextcloud answered with HTTP 404.", is_error=True)
    report = acceptance.Report()

    await acceptance._profile_fields(client, report, registered={TOOL})

    assert asked == [1]
    assert [(tool, verdict) for tool, verdict, _ in report.rows] == [(TOOL, acceptance.PREREQ)]
    assert TOOL not in report.called(), "a missing prerequisite never counts as answered"
    assert report.failures() == []
    assert report.held_up() == {TOOL}
    (line,) = report.prerequisites()
    assert "profile_fields is not installed or not enabled" in line
    assert "occ app:install profile_fields" in line


@pytest.mark.parametrize("status", [200, 401, 403, 500, None])
@pytest.mark.anyio
async def test_a_failed_call_with_the_app_in_place_stays_a_failure(
    acceptance: ModuleType, monkeypatch: pytest.MonkeyPatch, status: int | None
) -> None:
    """Only "no such route" is the instance; every other answer leaves the tool to explain."""
    app_answers(monkeypatch, acceptance, status)
    client = FakeClient("the tool refused", is_error=True)
    report = acceptance.Report()

    await acceptance._profile_fields(client, report, registered={TOOL})

    assert report.failures() == [TOOL]
    assert report.prerequisites() == []
    assert report.held_up() == set()

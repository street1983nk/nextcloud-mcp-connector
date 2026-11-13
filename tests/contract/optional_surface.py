"""The tool surface with every switch on; a helper module of the contract gates, not a test.

Until phase 33 every gate that reads a registry read the default one, so an optional tool
(``files_update`` behind ``NC_MCP_FILES_UPDATE``) escaped the annotation, audit and class
gates and the budget (33-RESEARCH.md, core findings 1 and 2). This module names the optional
tools once and measures the surface the way an administrator who ticked every box gets it.

The switches are read when ``mcp_connector.server`` is imported, and inside a test process
that import happened long ago, so the measurement runs in a fresh interpreter, the pattern of
``test_tool_bundles._run``: copy the environment, set the switches, read JSON from stdout.

Plans 33-06 to 33-08 add ``tasks_complete``, ``tasks_update`` and ``tasks_move`` to
``OPTIONAL_TOOLS``, each with ``NC_MCP_TASKS_UPDATE``; that switch is set on already, so a
tool behind it that registers without an entry here is found as "neither standard nor
optional" the day it appears.
"""

import functools
import json
import os
import subprocess
import sys
from collections.abc import Iterable
from typing import Any

from mcp.types import ToolAnnotations

#: Every tool that registers only behind a switch, with the variable of that switch.
OPTIONAL_TOOLS: dict[str, str] = {
    "files_update": "NC_MCP_FILES_UPDATE",
    "tasks_complete": "NC_MCP_TASKS_UPDATE",
    "tasks_update": "NC_MCP_TASKS_UPDATE",
}

#: The variable of the modifying task tools (D-33-01). Named here as well as through
#: ``OPTIONAL_TOOLS``, because in plan 33-02 no tool hangs on it yet and the measurement must
#: still switch it on.
TASKS_UPDATE_SWITCH = "NC_MCP_TASKS_UPDATE"

#: Every switch the measurement turns on.
SWITCHES: frozenset[str] = frozenset(OPTIONAL_TOOLS.values()) | {TASKS_UPDATE_SWITCH}

_MEASURE = """
import asyncio, json
from mcp import Client
from mcp_connector.server import mcp

async def main():
    async with Client(mcp, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
    registered = {tool.name: tool for tool in mcp._tool_manager.list_tools()}
    return {
        tool.name: {
            "annotations": (
                None
                if tool.annotations is None
                else tool.annotations.model_dump(mode="json", exclude_none=True)
            ),
            "input_schema": tool.input_schema,
            "audited": getattr(registered[tool.name].fn, "__mcp_audited__", False) is True,
        }
        for tool in tools
    }

print(json.dumps(asyncio.run(main())))
"""


def tools_of_switch(switch: str) -> frozenset[str]:
    """The optional tools that hang on one switch."""
    return frozenset(name for name, variable in OPTIONAL_TOOLS.items() if variable == switch)


def measure(env_overrides: dict[str, str]) -> dict[str, dict[str, Any]]:
    """One registry in a fresh interpreter: per tool annotations, schema and audit marker.

    ``NC_MCP_DISABLED_TOOLS`` and every switch are taken out of the inherited environment
    first, so the answer depends on ``env_overrides`` alone.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key != "NC_MCP_DISABLED_TOOLS" and key not in SWITCHES
    }
    env["PYTHONUTF8"] = "1"
    env.update(env_overrides)
    done = subprocess.run(  # noqa: S603 - the interpreter of this test run, a fixed snippet
        [sys.executable, "-c", _MEASURE],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


@functools.cache
def _switched_on() -> str:
    return json.dumps(measure(dict.fromkeys(sorted(SWITCHES), "on")))


def switched_on_surface() -> dict[str, dict[str, Any]]:
    """The surface with every switch of ``SWITCHES`` on, measured once per test session.

    A fresh copy on every call, so a gate that edits its answer cannot change the next one.
    """
    return json.loads(_switched_on())


def annotations_of(entry: dict[str, Any]) -> ToolAnnotations | None:
    """The annotations of one measured tool, back as the type the gates check."""
    raw = entry["annotations"]
    return None if raw is None else ToolAnnotations.model_validate(raw)


def surface_findings(registered: Iterable[str], standard: Iterable[str]) -> list[str]:
    """What is wrong with a switched-on surface, in the form the failure message prints.

    An optional tool that is missing with its switch on is a tool no gate has seen; a tool
    that is neither standard nor optional is one nobody decided about. Shared by the gates
    and by their counter proofs, so the proof bites with the lines that run.
    """
    names = set(registered)
    known = set(standard) | OPTIONAL_TOOLS.keys()
    findings = [
        f"optional tool missing with its switch on: {name}"
        for name in sorted(OPTIONAL_TOOLS.keys() - names)
    ]
    findings += [
        f"registered but neither standard nor optional: {name}" for name in sorted(names - known)
    ]
    return findings

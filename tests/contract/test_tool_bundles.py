"""Contract test for the tool bundles that ``NC_MCP_DISABLED_TOOLS`` switches off (issue #15).

The bundle names are public API: an administrator writes them into a deploy environment,
and a renamed ``server/reg_*.py`` file would turn a working configuration into a start
failure. So the names and the tools behind each of them are frozen here as literals. Who
renames a registration file or moves a tool from one bundle to another gets a red test and
has to decide that in a review, with a changelog entry.

The switch is read when ``mcp_connector.server`` is imported, so every case runs in a fresh
interpreter. That is slower than an in-process test and the only honest one.
"""

import json
import os
import subprocess
import sys

import pytest
from test_tool_surface import EXPECTED_TOOLS

from mcp_connector.server import bundle_names

BUNDLE_TOOLS: dict[str, frozenset[str]] = {
    "calendar": frozenset({"calendar_list_events", "calendar_create_event"}),
    "chatgpt": frozenset({"search", "fetch"}),
    "contacts": frozenset({"contacts_search"}),
    "context": frozenset({"prepare_context"}),
    "deck": frozenset({"deck_browse", "deck_create_card"}),
    "files": frozenset(
        {
            "files_search",
            "files_list",
            "files_read",
            "files_download",
            "files_read_as_markdown",
            "files_upload",
            "files_create_folder",
        }
    ),
    "mail": frozenset({"mail_browse"}),
    "notes": frozenset({"notes_search", "notes_read", "notes_create"}),
    "search": frozenset({"unified_search"}),
    "tables": frozenset({"tables_browse", "tables_create_row"}),
    "talk": frozenset({"talk_browse", "talk_send"}),
}

_LIST_TOOLS = """
import asyncio, json, sys
from mcp import Client
from mcp_connector.server import mcp
{extra}

async def main():
    async with Client(mcp, raise_exceptions=True) as client:
        return sorted(tool.name for tool in (await client.list_tools()).tools)

print(json.dumps(asyncio.run(main())))
"""


def _run(value: str | None, *, extra: str = "", **more: str) -> subprocess.CompletedProcess[str]:
    env = {key: val for key, val in os.environ.items() if key != "NC_MCP_DISABLED_TOOLS"}
    env["PYTHONUTF8"] = "1"
    if value is not None:
        env["NC_MCP_DISABLED_TOOLS"] = value
    env.update(more)
    return subprocess.run(  # noqa: S603 - the interpreter of this test run, a fixed snippet
        [sys.executable, "-c", _LIST_TOOLS.format(extra=extra)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def _tools(value: str | None, *, extra: str = "", **more: str) -> set[str]:
    done = _run(value, extra=extra, **more)
    assert done.returncode == 0, done.stderr
    return set(json.loads(done.stdout.strip().splitlines()[-1]))


def test_the_bundle_names_are_frozen() -> None:
    assert bundle_names() == [
        "calendar",
        "chatgpt",
        "contacts",
        "context",
        "deck",
        "files",
        "mail",
        "notes",
        "search",
        "tables",
        "talk",
    ]


def test_the_bundles_cover_the_tool_surface_exactly_once() -> None:
    assert set(BUNDLE_TOOLS) == set(bundle_names())
    union: set[str] = set()
    for tools in BUNDLE_TOOLS.values():
        assert union.isdisjoint(tools), f"{tools} overlaps another bundle"
        union |= tools
    assert union == EXPECTED_TOOLS


def test_without_the_variable_every_tool_is_registered() -> None:
    assert _tools(None) == EXPECTED_TOOLS


def test_mail_and_calendar_switched_off() -> None:
    expected = EXPECTED_TOOLS - BUNDLE_TOOLS["mail"] - BUNDLE_TOOLS["calendar"]
    assert _tools("mail,calendar") == expected


def test_chatgpt_can_be_switched_off_in_the_oauth_mode() -> None:
    tools = _tools("chatgpt", NC_MCP_AUTH_MODE="oauth")
    assert "search" not in tools
    assert "fetch" not in tools
    assert {"prepare_context", "unified_search"} <= tools
    assert tools == EXPECTED_TOOLS - BUNDLE_TOOLS["chatgpt"]


def test_switching_bundles_off_keeps_their_logic_importable() -> None:
    tools = _tools("talk,tables,notes,mail", extra="import mcp_connector.tools.chatgpt")
    assert {"prepare_context", "search", "fetch"} <= tools
    assert tools.isdisjoint(
        BUNDLE_TOOLS["talk"] | BUNDLE_TOOLS["tables"] | BUNDLE_TOOLS["notes"] | BUNDLE_TOOLS["mail"]
    )


def test_an_unknown_name_stops_the_start() -> None:
    done = _run("nope")
    assert done.returncode != 0
    assert "NC_MCP_DISABLED_TOOLS" in done.stderr
    assert "nope" in done.stderr
    assert "calendar" in done.stderr


@pytest.mark.parametrize("bundle", sorted(BUNDLE_TOOLS))
def test_each_bundle_switches_off_exactly_its_tools(bundle: str) -> None:
    assert _tools(bundle) == EXPECTED_TOOLS - BUNDLE_TOOLS[bundle]

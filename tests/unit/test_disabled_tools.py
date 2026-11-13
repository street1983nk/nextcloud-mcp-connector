"""Unit tests for the tool bundle switch ``NC_MCP_DISABLED_TOOLS`` (issue #15).

The switch is read once, when the server module registers its tools, so the parsing is a
pure function that is tested here with an explicit environment. A wrong name has to stop
the start and name the variable, the wrong value and every valid bundle: the administrator
reads that message in a container log where nothing else explains it.
"""

import pytest

from mcp_connector import config
from mcp_connector.errors import ToolError

KNOWN = (
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
    "tasks",
)


def test_an_unset_variable_switches_nothing_off() -> None:
    assert config.disabled_bundles(KNOWN, {}) == frozenset()


@pytest.mark.parametrize("raw", ["", "  ", ",, ,"])
def test_an_empty_value_switches_nothing_off(raw: str) -> None:
    assert config.disabled_bundles(KNOWN, {config.ENV_DISABLED_TOOLS: raw}) == frozenset()


def test_the_variable_name_is_the_documented_one() -> None:
    assert config.ENV_DISABLED_TOOLS == "NC_MCP_DISABLED_TOOLS"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mail,calendar", {"mail", "calendar"}),
        (" Mail , CALENDAR, ", {"mail", "calendar"}),
        ("talk,talk", {"talk"}),
    ],
)
def test_named_bundles_are_switched_off(raw: str, expected: set[str]) -> None:
    assert config.disabled_bundles(KNOWN, {config.ENV_DISABLED_TOOLS: raw}) == expected


def test_a_tool_name_is_not_a_bundle_name() -> None:
    with pytest.raises(ToolError) as caught:
        config.disabled_bundles(KNOWN, {config.ENV_DISABLED_TOOLS: "talk_send"})
    text = str(caught.value)
    assert "NC_MCP_DISABLED_TOOLS" in text
    assert "talk_send" in text
    for name in KNOWN:
        assert name in text


def test_a_valid_entry_does_not_rescue_an_unknown_one() -> None:
    with pytest.raises(ToolError) as caught:
        config.disabled_bundles(KNOWN, {config.ENV_DISABLED_TOOLS: "mail,bogus"})
    assert "bogus" in str(caught.value)


def test_switching_every_bundle_off_is_a_misconfiguration() -> None:
    with pytest.raises(ToolError) as caught:
        config.disabled_bundles(KNOWN, {config.ENV_DISABLED_TOOLS: ",".join(KNOWN)})
    assert "NC_MCP_DISABLED_TOOLS" in str(caught.value)

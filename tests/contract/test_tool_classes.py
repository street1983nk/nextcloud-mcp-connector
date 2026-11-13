"""GATE-01: every tool of the live registry stands in exactly one class, with a reason.

The table lives in ``tool_classes.py`` (D-28-02) and is compared with the tools the running
server object lists, not with a literal of this file: a new tool such as ``files_update``
(issue #9) fails here the day it is registered, before the canary and the pair tests could
silently miss it. The counter proofs go through the same ``freeze_findings`` as the gate,
because a counter proof that reimplements the check proves something about the counter proof.
"""

import pytest
import tool_classes
from mcp import Client
from mcp.types import Tool
from optional_surface import OPTIONAL_TOOLS, switched_on_surface

from mcp_connector.server import mcp

# D-28-14: tables_browse became a reader, which gives 12 / 3 / 7. files_read_as_markdown
# made it 13 / 3 / 7, and files_create_folder of FOLD-01 is the fourth writer: 13 / 4 / 7.
# The tasks bundle of TASK-07 adds three tools that name no file: 13 / 4 / 10.
TOTAL = 27

# The same registry with every switch on: the default plus every optional tool. 28 in plan
# 33-02 (files_update), 29 since plan 33-06 (tasks_complete); plans 33-07 and 33-08 raise it
# with each tool behind NC_MCP_TASKS_UPDATE.
TOTAL_SWITCHED_ON = 29

# The optional tools that carry a class entry: tasks_complete since plan 33-06 (UNAFFECTED).
# files_update stays unclassified as before phase 33. Named as a literal, so a new entry has
# to pass this door on purpose like a standard tool.
CLASSIFIED_OPTIONAL = frozenset({"tasks_complete"})


async def _tools() -> dict[str, Tool]:
    async with Client(mcp, raise_exceptions=True) as client:
        return {tool.name: tool for tool in (await client.list_tools()).tools}


@pytest.mark.anyio
async def test_every_registered_tool_has_exactly_one_class_and_a_reason() -> None:
    names = sorted(await _tools())

    findings = tool_classes.freeze_findings(names, switched_on=sorted(switched_on_surface()))
    assert findings == [], "\n".join(findings)
    assert len(names) == TOTAL, (
        f"{len(names)} tools; the split 13/4/10 is D-28-14 plus files_read_as_markdown "
        "plus files_create_folder plus the three tools of the tasks bundle"
    )


@pytest.mark.anyio
async def test_the_freeze_knows_the_switched_on_surface() -> None:
    """An entry for an optional tool is not stale: it is registered once its switch is on."""
    names = sorted(await _tools())
    switched_on = sorted(switched_on_surface())

    assert tool_classes.freeze_findings(names, switched_on=switched_on) == []
    assert len(switched_on) == TOTAL_SWITCHED_ON
    assert len(switched_on) == TOTAL + len(OPTIONAL_TOOLS)


@pytest.mark.anyio
async def test_an_entry_registered_nowhere_stays_stale_with_every_switch_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counter proof: an entry for a tool that no switch registers is still reported, and an
    entry for an optional tool is reported only when the switched-on names are left out."""
    names = sorted(await _tools())
    switched_on = sorted(switched_on_surface())
    optional = sorted(OPTIONAL_TOOLS)[0]

    monkeypatch.setitem(tool_classes.UNAFFECTED, "tasks_probe", "Answers nothing at all here.")
    monkeypatch.setitem(tool_classes.UNAFFECTED, optional, "Answers its own path and an etag.")

    assert tool_classes.freeze_findings(names, switched_on=switched_on) == ["stale: tasks_probe"]
    # Without the switched-on names every classified optional tool reads as stale as well.
    assert tool_classes.freeze_findings(names) == [
        f"stale: {name}" for name in sorted({"tasks_probe", optional, *CLASSIFIED_OPTIONAL})
    ]


@pytest.mark.anyio
async def test_a_probe_tool_without_entry_turns_the_freeze_red() -> None:
    with tool_classes.probe_tool() as name:
        names = set(await _tools())
        assert name in names, "the probe must really be registered"
        findings = tool_classes.freeze_findings(names)
        assert f"unclassified: {name}" in findings, findings
        assert tool_classes.unclassified(names) == [name]

    names = set(await _tools())
    assert name not in names, "the probe leaked into the registry"
    assert tool_classes.freeze_findings(names, switched_on=sorted(switched_on_surface())) == []


@pytest.mark.anyio
async def test_an_empty_reason_turns_the_freeze_red(monkeypatch: pytest.MonkeyPatch) -> None:
    names = set(await _tools())
    monkeypatch.setitem(tool_classes.UNAFFECTED, "deck_browse", "")
    assert "empty reason: UNAFFECTED[deck_browse]" in tool_classes.freeze_findings(names)

    monkeypatch.setitem(tool_classes.UNAFFECTED, "deck_browse", "Safe.")
    findings = tool_classes.freeze_findings(names)
    assert any("shorter than" in finding for finding in findings), findings

    monkeypatch.setitem(tool_classes.UNAFFECTED, "deck_browse", "Answers only ids and titles")
    findings = tool_classes.freeze_findings(names)
    assert any("full stop" in finding for finding in findings), findings


@pytest.mark.anyio
async def test_a_tool_in_two_classes_turns_the_freeze_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = set(await _tools())
    monkeypatch.setitem(
        tool_classes.FILE_READERS, "deck_browse", "Pretends that a card answers a file name."
    )
    findings = tool_classes.freeze_findings(names)
    assert any(finding.startswith("in more than one class: deck_browse") for finding in findings)


@pytest.mark.anyio
async def test_a_pair_case_of_an_unaffected_tool_turns_the_freeze_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = set(await _tools())
    monkeypatch.setitem(tool_classes.PAIR_CASES, ("deck_browse", "card"), "apps")
    findings = tool_classes.freeze_findings(names)
    assert "pair case of a tool that is not a reader or writer: deck_browse/card" in findings


@pytest.mark.anyio
async def test_readers_are_read_only_and_writers_are_not() -> None:
    tools = await _tools()
    for name in tool_classes.FILE_READERS:
        annotations = tools[name].annotations
        assert annotations is not None, name
        assert annotations.read_only_hint is True, f"{name} is a reader"
    for name in tool_classes.FILE_WRITERS:
        annotations = tools[name].annotations
        assert annotations is not None, name
        assert annotations.read_only_hint is False, f"{name} is a writer"


def test_the_three_classes_add_up_to_the_frozen_surface() -> None:
    """The frozen number is named once; a twenty-eighth tool must pass this door on purpose."""
    total = (
        len(tool_classes.FILE_READERS)
        + len(tool_classes.FILE_WRITERS)
        + len(tool_classes.UNAFFECTED)
    )
    assert total == TOTAL + len(CLASSIFIED_OPTIONAL)
    assert (
        len(tool_classes.FILE_READERS),
        len(tool_classes.FILE_WRITERS),
        len(tool_classes.UNAFFECTED),
    ) == (13, 4, 10 + len(CLASSIFIED_OPTIONAL))

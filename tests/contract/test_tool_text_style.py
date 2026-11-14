"""Compound modifiers in the tool texts carry their hyphen (owner decision 2026-11-14).

"Comma-separated provider ids", "space-separated type:value", "Percent-encode a value":
a compound in front of a noun, or a compound verb, is written with a hyphen. The check reads
every text a client sees in tools/list: the descriptions of the standard registry and the
parameter descriptions of the registry with every switch on.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from mcp import Client
from optional_surface import switched_on_surface

from mcp_connector.server import mcp

#: Open compounds that need a hyphen in these texts, case-insensitive.
UNHYPHENATED = re.compile(
    r"\b(?:comma|space|semicolon|tab|newline) separated\b|\bpercent encod\w*|\bread only (?=[a-z])",
    re.IGNORECASE,
)


def _schema_texts(schema: dict[str, Any]) -> list[str]:
    properties = schema.get("properties") or {}
    return [str(entry.get("description") or "") for entry in properties.values()]


def style_findings(texts: dict[str, str]) -> list[str]:
    """``<where>: <match>`` for every open compound in ``texts``."""
    return [
        f"{where}: {match.group(0)!r}"
        for where, text in texts.items()
        for match in UNHYPHENATED.finditer(text)
    ]


def test_the_check_names_a_planted_open_compound() -> None:
    planted = {"x param": "Tab separated values", "y": "Percent encode it", "z": "a read only list"}
    assert len(style_findings(planted)) == 3
    assert style_findings({"ok": "Comma-separated ids; the list is read only."}) == []


@pytest.mark.anyio
async def test_tool_texts_hyphenate_compound_modifiers() -> None:
    texts: dict[str, str] = {}
    async with Client(mcp, raise_exceptions=True) as client:
        for tool in (await client.list_tools()).tools:
            texts[f"{tool.name} description"] = tool.description or ""
            for index, text in enumerate(_schema_texts(tool.input_schema)):
                texts[f"{tool.name} param {index}"] = text
    for name, entry in switched_on_surface().items():
        for index, text in enumerate(_schema_texts(entry["input_schema"])):
            texts[f"{name} switched param {index}"] = text
    assert style_findings(texts) == []

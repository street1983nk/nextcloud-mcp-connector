"""The admin switch that lets files_update replace a file with a ChatGPT attachment (0.10.0).

``NC_MCP_FILES_UPDATE_ATTACHMENT`` is off by default and has an effect only together with
``NC_MCP_FILES_UPDATE``: an administrator can allow text edits without allowing binary
replacements. The tool registers one form or the other when ``mcp_connector.server`` is
imported, so every check here runs in a fresh interpreter, as in
``test_exapp_files_update_switch.py``.

The text-only form is the one of 0.9.0, byte for byte: :data:`MAIN_FILES_UPDATE` is the entry
``tools/list`` had then, copied from that release, and the default surface of the two states
that do not arm the attachment path is compared with the surface of a server that never heard
of the switch.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ENV_FILES_UPDATE = "NC_MCP_FILES_UPDATE"
ENV_ATTACHMENT = "NC_MCP_FILES_UPDATE_ATTACHMENT"

#: ``files_update`` in ``tools/list`` of 0.9.0, with the switch of 0.9.0 on.
MAIN_FILES_UPDATE = {
    "name": "files_update",
    "description": (
        "Replace an existing UTF-8 text file only when its ETag still matches.\n\n"
        "This is a whole-file replacement: read the complete file first and send the\n"
        "complete new content, not a partial read. The file must already exist and keeps\n"
        "its path. If the file changed or was deleted, the update is rejected and\n"
        "the client must read it again and decide what to do. Whether an older version is\n"
        "kept depends on the Nextcloud storage backend.\n"
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "path": {
                "description": "Existing text file path; must already exist",
                "type": "string",
            },
            "content": {
                "description": "Complete replacement content as UTF-8 text",
                "type": "string",
            },
            "etag": {"description": "ETag returned when the file was read", "type": "string"},
        },
        "required": ["path", "content", "etag"],
    },
    "annotations": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
}

_LIST = """
import asyncio, json
from mcp import Client
from mcp_connector.server import mcp

async def main():
    async with Client(mcp, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        instructions = mcp.instructions
    return {
        "tools": [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools],
        "instructions": instructions,
    }

print(json.dumps(asyncio.run(main())))
"""

_CALL = """
import asyncio, json
from mcp import Client
from mcp_connector.server import mcp

FILE = {"download_url": "https://files.oaiusercontent.com/x", "file_id": "file_1"}

async def main():
    out = {}
    async with Client(mcp) as client:
        for name, args in (("file_only", {"path": "/a.docx", "etag": '"x"', "file": FILE}),):
            result = await client.call_tool("files_update", args)
            out[name] = [result.is_error, result.content[0].text]
    return out

print(json.dumps(asyncio.run(main())))
"""


def _env(**switches: str | None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("NC_MCP_")}
    env["PYTHONUTF8"] = "1"
    env.update({key: value for key, value in switches.items() if value is not None})
    return env


def _run(code: str, env: dict[str, str]) -> dict:
    done = subprocess.run(  # noqa: S603 - this interpreter, a fixed snippet
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def _surface(files: str | None, attachment: str | None) -> dict:
    return _run(_LIST, _env(NC_MCP_FILES_UPDATE=files, NC_MCP_FILES_UPDATE_ATTACHMENT=attachment))


def _files_update(surface: dict) -> dict | None:
    return next((t for t in surface["tools"] if t["name"] == "files_update"), None)


@pytest.mark.parametrize(
    ("files", "attachment", "registered", "with_file"),
    [
        (None, None, False, False),
        ("on", None, True, False),
        ("on", "off", True, False),
        ("on", "", True, False),
        ("on", "maybe", True, False),
        ("on", "on", True, True),
        ("on", "1", True, True),
        # The switch hangs on files_update: alone it registers nothing.
        (None, "on", False, False),
        ("off", "on", False, False),
    ],
)
def test_the_two_switches_decide_which_form_of_files_update_is_served(
    files: str | None, attachment: str | None, registered: bool, with_file: bool
) -> None:
    tool = _files_update(_surface(files, attachment))

    assert (tool is not None) is registered
    if tool is not None:
        assert ("file" in tool["inputSchema"]["properties"]) is with_file
        assert ("_meta" in tool) is with_file
        assert ("attachment" in tool["description"].lower()) is with_file


def test_with_the_attachment_switch_off_files_update_is_the_one_of_0_9_0_byte_for_byte() -> None:
    tool = _files_update(_surface("on", None))

    assert tool == MAIN_FILES_UPDATE
    assert json.dumps(tool) == json.dumps(MAIN_FILES_UPDATE)


@pytest.mark.parametrize("attachment", [None, "off", "on"])
def test_without_files_update_the_attachment_switch_leaves_the_whole_surface_as_it_is(
    attachment: str | None,
) -> None:
    default = _surface(None, None)

    assert _surface(None, attachment) == default
    assert _files_update(default) is None


def test_with_the_attachment_switch_off_the_whole_surface_is_the_text_only_one() -> None:
    """Nothing but ``files_update`` differs between the two states, and the instruction names
    the text edit only."""
    off, on = _surface("on", None), _surface("on", "on")

    others_off = [t for t in off["tools"] if t["name"] != "files_update"]
    others_on = [t for t in on["tools"] if t["name"] != "files_update"]
    assert others_off == others_on
    assert "attachment" not in off["instructions"].lower()
    assert "ChatGPT attachment" in on["instructions"]


def test_with_both_switches_on_the_tool_offers_the_file_parameter_for_chatgpt() -> None:
    tool = _files_update(_surface("on", "on"))

    assert tool is not None
    assert tool["_meta"] == {"openai/fileParams": ["file"]}
    assert set(tool["inputSchema"]["properties"]) == {"path", "etag", "content", "file"}
    assert tool["inputSchema"]["required"] == ["path", "etag"]


def test_a_file_that_reaches_the_tool_with_the_switch_off_is_refused_before_the_network() -> None:
    """The tool is the one of 0.9.0: a client that still holds the schema with ``file`` and
    sends no ``content`` gets the validation error of that schema. The answer is not the
    "NC_MCP_URL is not set" of the first step that needs a server, so no connection to
    Nextcloud was prepared, and the attachment path is not there at all."""
    answers = _run(_CALL, _env(NC_MCP_FILES_UPDATE="on"))

    is_error, text = answers["file_only"]
    assert is_error
    assert "validation error" in text
    assert "NC_MCP_URL" not in text
    assert "download_url" not in text.split("input_value=")[0]


# --- the entry point: the stored admin value reaches the registry -------------------------

DRIVER = """
import asyncio, json, os, sys

from mcp_connector import entry_exapp
from mcp_connector.exapp import config_values
from mcp_connector.oauth import store

overlay = json.loads(os.environ.pop("TEST_ADMIN_OVERLAY"))

async def fake_admin_values(env):
    return config_values.AdminValues(overlay=dict(overlay), refused=frozenset())

async def fake_key(env=None):
    return bytes(range(32))

entry_exapp._admin_values = fake_admin_values
store.crypto.data_key = fake_key
entry_exapp.uvicorn.run = lambda app, **kwargs: None

entry_exapp.main()

from mcp_connector.server import mcp

tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
tool = tools.get("files_update")
print(json.dumps({"registered": tool is not None,
                  "with_file": tool is not None and "file" in tool.input_schema["properties"]}))
"""


def _started(tmp_path: Path, *, deploy: dict[str, str], admin: dict[str, str]) -> dict:
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("NC_MCP_", "APP_", "NEXTCLOUD_", "AA_", "HP_"))
    }
    env.update(
        {
            "APP_ID": "mcp_connector",
            "APP_SECRET": "s3cret-of-the-test",
            "APP_VERSION": "0.6.0",
            "NEXTCLOUD_URL": "http://nc.test",
            "APP_PERSISTENT_STORAGE": str(tmp_path),
            "HP_SHARED_KEY": "a" * 64,
            "NC_MCP_DISABLE_DNS_REBINDING_PROTECTION": "1",
            "PYTHONUTF8": "1",
            "TEST_ADMIN_OVERLAY": json.dumps(admin),
        }
    )
    env.update(deploy)
    return _run(DRIVER, env)


@pytest.mark.parametrize(
    ("deploy", "admin", "with_file"),
    [
        # A store installation sets no variable: the stored values alone decide.
        ({}, {ENV_FILES_UPDATE: "on", ENV_ATTACHMENT: "on"}, True),
        ({}, {ENV_FILES_UPDATE: "on"}, False),
        # An unticked box disarms the binary replacement even when the deploy armed it.
        (
            {ENV_FILES_UPDATE: "on", ENV_ATTACHMENT: "on"},
            {ENV_FILES_UPDATE: "on", ENV_ATTACHMENT: "off"},
            False,
        ),
        # A ticked box arms it over a deploy variable that said off.
        (
            {ENV_FILES_UPDATE: "on", ENV_ATTACHMENT: "off"},
            {ENV_ATTACHMENT: "on"},
            True,
        ),
        # With files_update unticked there is no tool, whatever the attachment box says.
        ({ENV_ATTACHMENT: "on"}, {ENV_FILES_UPDATE: "off", ENV_ATTACHMENT: "on"}, None),
    ],
)
def test_the_resolved_attachment_switch_decides_which_form_a_started_app_serves(
    tmp_path: Path, deploy: dict[str, str], admin: dict[str, str], with_file: bool | None
) -> None:
    started = _started(tmp_path, deploy=deploy, admin=admin)

    assert started["registered"] is (with_file is not None)
    if with_file is not None:
        assert started["with_file"] is with_file

"""The admin switch of ``profile_fields_browse`` reaches a started ExApp.

Built after ``test_exapp_tasks_update_switch.py``: the optional registration behind
``NC_MCP_PROFILE_FIELDS_READ`` is imported only when ``config.profile_fields_read_enabled``
answers True at the moment ``mcp_connector.server`` is imported, so a stored admin value has
to reach the process environment before that import. Each check runs in a fresh interpreter,
because inside this test process the registry was fixed long ago.

A store installation gets no deploy variable at all, so the row with nothing deployed and
the box ticked is the one this file exists for: without the manifest declaration, the form
field and the write in ``entry_exapp.main`` the tool could not be switched on there.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

#: The one tool that registers only with the switch on.
SWITCHED_TOOLS: frozenset[str] = frozenset({"profile_fields_browse"})

#: Counted at the code like in the live proof: the module level ``@mcp.tool`` decorators of
#: the twelve ``server/reg_*.py`` files.
DEFAULT_TOOL_COUNT = 27

#: One start of ``main`` in a fresh interpreter, the admin read and the data key answered
#: locally and ``uvicorn.run`` replaced. It prints what the started process believes about
#: the switch and the tool names of the registry the built application serves.
DRIVER = """
import asyncio, json, os, sys

from mcp_connector import config, entry_exapp
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

names = sorted(tool.name for tool in asyncio.run(mcp.list_tools()))
print(json.dumps({"enabled": config.profile_fields_read_enabled(), "tools": names}))
"""

ENV_PROFILE_FIELDS_READ = "NC_MCP_PROFILE_FIELDS_READ"


def started(tmp_path: Path, *, deploy: str | None, admin: str | None) -> dict[str, object]:
    """Start the ExApp once with this deploy variable and this stored admin value."""
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
            "TEST_ADMIN_OVERLAY": json.dumps(
                {} if admin is None else {ENV_PROFILE_FIELDS_READ: admin}
            ),
        }
    )
    if deploy is not None:
        env[ENV_PROFILE_FIELDS_READ] = deploy
    result = subprocess.run(  # noqa: S603 - a literal driver from this test, no user input
        [sys.executable, "-c", DRIVER],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def standard_tools(tmp_path_factory: pytest.TempPathFactory) -> frozenset[str]:
    """The registry with the switch off and nothing stored: the shipped state."""
    answer = started(tmp_path_factory.mktemp("standard"), deploy=None, admin=None)
    tools = answer["tools"]
    assert isinstance(tools, list)
    return frozenset(str(name) for name in tools)


def test_the_shipped_state_serves_the_27_default_tools(standard_tools: frozenset[str]) -> None:
    """Opt-in means the registry of an installation that set nothing is the default one."""
    assert len(standard_tools) == DEFAULT_TOOL_COUNT
    assert not SWITCHED_TOOLS & standard_tools


@pytest.mark.parametrize(
    ("deploy", "admin", "expected"),
    [
        # Deploy off, the box ticked in Nextcloud: the stored value decides.
        ("off", "on", True),
        # The direction that matters for safety: an unticked box keeps the tool away even
        # when the deploy environment armed it.
        ("on", "off", False),
        # A store installation sets no variable at all; the stored value alone decides.
        (None, "on", True),
        # Nothing stored: the deploy variable keeps deciding.
        ("on", None, True),
        (None, None, False),
    ],
)
def test_the_resolved_switch_decides_whether_profile_fields_browse_is_served(
    tmp_path: Path,
    standard_tools: frozenset[str],
    deploy: str | None,
    admin: str | None,
    expected: bool,
) -> None:
    answer = started(tmp_path, deploy=deploy, admin=admin)
    tools = answer["tools"]
    assert isinstance(tools, list)

    assert answer["enabled"] is expected
    assert frozenset(tools) == (standard_tools | SWITCHED_TOOLS if expected else standard_tools)
    assert len(tools) == DEFAULT_TOOL_COUNT + (1 if expected else 0)

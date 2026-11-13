"""Shared test fixtures.

This module deliberately imports nothing from ``mcp_connector``: the contract tests
are red until the server layer exists, and a package import here would break
collection for the whole suite instead of only the red test file.
"""

import os

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run ``@pytest.mark.anyio`` tests on asyncio only (SDK documentation pattern)."""
    return "asyncio"


@pytest.fixture
def nc_env() -> dict[str, str]:
    """Fake Nextcloud connection values for unit tests. Plain strings on purpose."""
    return {
        "base_url": "http://nc.test",
        "user": "alice",
        "secret": "app-password-test",
    }


@pytest.fixture
def live_env() -> dict[str, str | None]:
    """Connection values of a real test Nextcloud, read from the environment."""
    return {
        "base_url": os.environ.get("NC_MCP_URL"),
        "user": os.environ.get("NC_MCP_USER"),
        "secret": os.environ.get("NC_MCP_APP_PASSWORD"),
    }


@pytest.fixture
def exapp_env() -> dict[str, str]:
    """The AppAPI deploy identity that ``scripts/bootstrap_exapp.sh`` writes into ``.env.exapp``.

    This is the seam of the DAV spike (D-30): the values here let a test build the fourth
    credential mode ``appapi`` and impersonate a user with ``APP_SECRET`` alone, exactly as
    the deployed ExApp does. ``AA_VERSION`` is the one optional value, because HaRP writes a
    hard coded placeholder into that header and nothing in this project evaluates it
    (02-RESEARCH.md, pitfall 8).

    When one of the required values is missing the caller skips with the variable named, the
    same shape ``test_permission_fidelity.py`` uses. The skip is what keeps the default suite
    green without the HaRP topology: ``pytest_collection_modifyitems`` deselects the
    integration marker anyway, and an explicit ``-m integration`` run without ``.env.exapp``
    lands here instead of erroring.
    """
    required = {
        "base_url": "NC_MCP_URL",
        "app_id": "APP_ID",
        "app_secret": "APP_SECRET",
        "app_version": "APP_VERSION",
        "alice": "NC_MCP_TEST_USER",
        "bob": "NC_MCP_TEST_USER2",
    }
    values = {key: (os.environ.get(name) or "").strip() for key, name in required.items()}
    missing = sorted(required[key] for key, value in values.items() if not value)
    if missing:
        pytest.skip(f"no ExApp topology configured (missing: {', '.join(missing)})")
    values["aa_version"] = (os.environ.get("AA_VERSION") or "").strip()
    return values


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests when no test Nextcloud is configured.

    The Linux Docker engine does not run on the development host, so the default
    suite must stay green without Docker. ``addopts`` already deselects the
    ``integration`` marker; this guard additionally turns an explicit
    ``-m integration`` run without ``NC_MCP_URL`` into skips instead of failures.

    Not under ``NC_MCP_REQUIRE_LIVE=1`` (W3 of phase 31, plan 32-05b): a CI step that sets
    it demands a live run, and a missing ``NC_MCP_URL`` there is a broken topology. The
    tests then reach their own ``skip_or_fail`` and fail with the variable named, instead of
    turning into green skips here. The name is spelled out because this module imports
    nothing from the test helpers either.
    """
    if os.environ.get("NC_MCP_URL"):
        return
    if (os.environ.get("NC_MCP_REQUIRE_LIVE") or "").strip() == "1":
        return
    skip_integration = pytest.mark.skip(
        reason="NC_MCP_URL is not set: no test Nextcloud available (Docker engine off)"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)

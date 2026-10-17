"""Integration tests against a real Nextcloud 34 (opt-in, marker ``integration``).

This file carries the proof for TOOL-09: the overwrite protection is not our own check but
Nextcloud's answer to ``If-None-Match: *``. The sabre/dav source says 412, and only a run
against a real instance shows whether Nextcloud's own PUT plugins keep it that way, so the
conflict test asserts the raw status code as well as the message the model gets.

Run it with:
    docker compose -f compose.test.yml up -d --wait
    bash scripts/bootstrap_test_nc.sh
    set -a && . ./.env.test && set +a && uv run pytest -m integration -q

Without ``NC_MCP_URL`` the conftest guard skips everything here, so the default suite stays
green on a machine without Docker.
"""

import time
import uuid
from urllib.parse import quote

import httpx
import pytest

from mcp_connector.config import normalize_base_url
from mcp_connector.errors import ConflictError, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


def _unique_path() -> str:
    """A fresh target per test, so a leftover file from an earlier run never lies to us."""
    return f"/mcp-connector-test-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.md"


@pytest.fixture
def clients(live_env: dict[str, str | None]) -> NcClients:
    missing = [name for name, value in live_env.items() if not value]
    if missing:
        pytest.skip(f"no test Nextcloud configured (missing: {', '.join(sorted(missing))})")

    user = live_env["user"]
    assert user != "admin", "integration tests run as a normal user, never as admin"

    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False, timeout=30.0),
        creds=Credentials(
            base_url=normalize_base_url(str(live_env["base_url"])),
            user=str(user),
            secret=str(live_env["secret"]),
        ),
    )


async def test_upload_creates_a_new_file(clients: NcClients) -> None:
    path = _unique_path()
    result = await files_tools.upload(clients, path=path, content="# Erste Zeile\n")

    assert result["path"] == path
    assert result["created"] is True
    assert result["etag"], "Nextcloud returns an etag for a created file"


async def test_read_returns_exactly_what_was_uploaded(clients: NcClients) -> None:
    path = _unique_path()
    content = "# Notiz mit Umlauten\nGrüße aus Hamburg, Straße 1\n"
    await files_tools.upload(clients, path=path, content=content)

    result = await files_tools.read(clients, path=path)

    assert result["content"] == content
    assert result["truncated"] is False
    assert result["size"] == len(content.encode("utf-8"))


async def test_second_upload_to_the_same_path_is_refused_with_412(clients: NcClients) -> None:
    """The create-only proof (assumption A1): the real server refuses, not our client."""
    path = _unique_path()
    await files_tools.upload(clients, path=path, content="original\n")

    raw = await clients.client.put(
        dav.files_url(clients.creds, path),
        content=b"overwrite attempt\n",
        headers={"If-None-Match": "*", "Content-Type": "text/markdown"},
        auth=httpx.BasicAuth(clients.creds.user, clients.creds.secret),
    )
    assert raw.status_code == 412, (
        "Nextcloud must answer a PUT with If-None-Match: * on an existing file with 412; "
        "anything else breaks the no-overwrite promise of this server"
    )

    with pytest.raises(ConflictError) as excinfo:
        await files_tools.upload(clients, path=path, content="overwrite attempt\n")
    text = f"{excinfo.value.message} {excinfo.value.hint}"
    assert f"A file already exists at {path}." in text
    assert "This server never overwrites files." in text

    unchanged = await files_tools.read(clients, path=path)
    assert unchanged["content"] == "original\n", "the first content must still be there"


async def test_read_of_a_missing_file_reports_not_found(clients: NcClients) -> None:
    with pytest.raises(ToolError) as excinfo:
        await files_tools.read(clients, path=_unique_path())

    assert "not found" in excinfo.value.message.lower()
    assert excinfo.value.hint


async def test_stale_if_match_returns_412_and_preserves_content(
    clients: NcClients,
) -> None:
    path = _unique_path()
    await files_tools.upload(clients, path=path, content="original\n")
    stale_etag = (await dav.stat(clients.client, clients.creds, path))["etag"]
    await files_tools.update(clients, path=path, content="updated\n", etag=stale_etag)

    raw = await clients.client.put(
        dav.files_url(clients.creds, path),
        content=b"stale overwrite\n",
        headers={"If-Match": stale_etag, "Content-Type": "text/markdown"},
        auth=httpx.BasicAuth(clients.creds.user, clients.creds.secret),
    )
    assert raw.status_code == 412
    assert (await files_tools.read(clients, path=path))["content"] == "updated\n"


async def test_correct_if_match_returns_204_and_replaces_content(
    clients: NcClients,
) -> None:
    path = _unique_path()
    await files_tools.upload(clients, path=path, content="before\n")
    etag = (await dav.stat(clients.client, clients.creds, path))["etag"]

    raw = await clients.client.put(
        dav.files_url(clients.creds, path),
        content=b"after\n",
        headers={"If-Match": etag, "Content-Type": "text/markdown"},
        auth=httpx.BasicAuth(clients.creds.user, clients.creds.secret),
    )
    assert raw.status_code == 204
    assert (await files_tools.read(clients, path=path))["content"] == "after\n"


async def test_update_retains_previous_version(clients: NcClients) -> None:
    path = _unique_path()
    original = "previous version\n"
    await files_tools.upload(clients, path=path, content=original)
    etag = (await dav.stat(clients.client, clients.creds, path))["etag"]

    await files_tools.update(clients, path=path, content="replacement\n", etag=etag)

    info = await dav.stat(clients.client, clients.creds, path)
    response = await clients.client.get(
        f"{clients.creds.base_url}/ocs/v2.php/apps/files_versions/api/v1/versions/{info['fileid']}",
        params={"format": "json"},
        headers={"OCS-APIRequest": "true"},
        auth=httpx.BasicAuth(clients.creds.user, clients.creds.secret),
    )
    response.raise_for_status()
    versions = response.json()["ocs"]["data"]
    assert versions, "Nextcloud should retain a previous version after replacement"

    previous = next(
        (version for version in versions if version.get("timestamp") or version.get("version")),
        None,
    )
    assert previous is not None, "a retained version must identify its revision"
    revision = previous.get("timestamp") or previous.get("version")

    version_url = (
        f"{clients.creds.base_url}/remote.php/dav/versions/"
        f"{quote(clients.creds.user, safe='')}/versions/"
        f"{info['fileid']}/{quote(str(revision), safe='')}"
    )
    download = await clients.client.get(
        version_url,
        auth=httpx.BasicAuth(clients.creds.user, clients.creds.secret),
    )
    download.raise_for_status()
    assert download.text == original

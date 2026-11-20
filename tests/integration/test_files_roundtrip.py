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

import asyncio
import base64
import io
import time
import uuid
import zipfile

import httpx
import pytest
import respx

from mcp_connector.config import normalize_base_url
from mcp_connector.errors import ConflictError, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.clients import xml as dav_xml
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
    assert "Uploads never overwrite existing files." in text

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
    # Nextcloud's ETag changes with mtime granularity (one second on local storage), so
    # two writes in the same second can share one ETag. The pause makes the staleness
    # real instead of racing the clock; the limit itself is documented in client-setup.
    await asyncio.sleep(1.1)
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
    """``versioned: true`` is backed by the version listing growing around the write.

    Only the listing is asserted, not a GET of the version file: downloading an old
    version over DAV is Nextcloud's own feature and answers 404 on some releases, which
    says nothing about this server's promise.
    """
    path = _unique_path()
    await files_tools.upload(clients, path=path, content="previous version\n")
    read = await files_tools.read(clients, path=path)
    await asyncio.sleep(1.1)

    result = await files_tools.update(
        clients, path=path, content="replacement\n", etag=read["etag"]
    )
    assert result["versioned"] is True

    info = await dav.stat(clients.client, clients.creds, path)
    listing = await clients.client.request(
        "PROPFIND",
        dav.versions_url(clients.creds, info["fileid"]),
        headers={"Depth": "1"},
        auth=httpx.BasicAuth(clients.creds.user, clients.creds.secret),
    )
    assert listing.status_code == 207
    # The first entry is the collection itself; every later one is a retained version.
    assert len(dav_xml.parse_multistatus(listing.content)) >= 2


async def test_vacuous_if_match_shapes_are_refused_before_any_write(
    clients: NcClients,
) -> None:
    """``*``, an empty value and a list never reach SabreDAV, which would honour them."""
    path = _unique_path()
    await files_tools.upload(clients, path=path, content="untouched\n")
    current = (await files_tools.read(clients, path=path))["etag"]

    for vacuous in ("*", "", f"{current}, {current}", 'W/"weak"'):
        with pytest.raises(ToolError) as excinfo:
            await files_tools.update(clients, path=path, content="smuggled\n", etag=vacuous)
        assert "not one strong ETag" in excinfo.value.message

    assert (await files_tools.read(clients, path=path))["content"] == "untouched\n"


async def test_read_then_update_round_trip_uses_the_returned_etag(
    clients: NcClients,
) -> None:
    """The loop a real client runs: read hands out the ETag that update consumes."""
    path = _unique_path()
    await files_tools.upload(clients, path=path, content="first\n")

    read = await files_tools.read(clients, path=path)
    assert read["etag"], "files_read must return the CAS handle"

    result = await files_tools.update(clients, path=path, content="second\n", etag=read["etag"])
    assert result["path"] == path
    assert result["size"] == len(b"second\n")

    after = await files_tools.read(clients, path=path)
    assert after["content"] == "second\n"
    assert after["etag"] == result["etag"]


class _OneShotStream(httpx.AsyncByteStream):
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def __aiter__(self):
        yield self.data


DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


_PKG = "http://schemas.openxmlformats.org/package/2006"
_ODOC = "http://schemas.openxmlformats.org/officeDocument/2006"
_WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


def _minimal_docx(text: str) -> bytes:
    """A valid OOXML package with one paragraph, built in memory."""
    head = '<?xml version="1.0" encoding="UTF-8"?>'
    parts = {
        "[Content_Types].xml": (
            f'{head}<Types xmlns="{_PKG}/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/word/document.xml" ContentType="{_WORD}"/></Types>'
        ),
        "_rels/.rels": (
            f'{head}<Relationships xmlns="{_PKG}/relationships">'
            f'<Relationship Id="rId1" Type="{_ODOC}/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": (
            f'{head}<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body><w:p><w:r>'
            f"<w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        for name, xml in parts.items():
            package.writestr(name, xml)
    return buffer.getvalue()


async def test_update_attachment_replaces_a_binary_and_guards_with_the_download_etag(
    clients: NcClients,
) -> None:
    """Only the ChatGPT file source is simulated; every Nextcloud request is real."""
    path = _unique_path().replace(".md", ".docx")
    source_url = "https://files.oaiusercontent.com/file-roundtrip?sig=test"
    edited = _minimal_docx("edited")
    original = _minimal_docx("original")
    await files_tools.upload_binary(
        clients,
        path=path,
        content_base64=base64.b64encode(original).decode("ascii"),
        total_bytes=len(original),
        final=True,
        content_type=DOCX_TYPE,
    )
    downloaded = await files_tools.download(clients, path=path, max_bytes=len(original))
    assert downloaded["etag"], "files_download must return the CAS handle"
    assert downloaded["content_type"] == DOCX_TYPE
    later_chunk = await files_tools.download(clients, path=path, offset=1, max_bytes=2)
    assert "etag" not in later_chunk, "only the first chunk carries the ETag"
    await asyncio.sleep(1.1)

    with respx.mock(assert_all_called=False) as mock:
        mock.route(host=httpx.URL(clients.creds.base_url).host).pass_through()
        mock.get(source_url).mock(
            return_value=httpx.Response(
                200,
                stream=_OneShotStream(edited),
                headers={"Content-Length": str(len(edited))},
            )
        )
        result = await files_tools.update_attachment(
            clients,
            path=path,
            etag=downloaded["etag"],
            download_url=source_url,
            file_id="file_roundtrip",
            mime_type=DOCX_TYPE,
        )
        assert result["size"] == len(edited)
        assert result["versioned"] is not False

        after = await files_tools.download(clients, path=path, max_bytes=len(edited))
        assert after["content"] == edited
        with zipfile.ZipFile(io.BytesIO(after["content"])) as package:
            assert b"edited" in package.read("word/document.xml")
        assert after["etag"] == result["etag"]
        assert after["content_type"] == DOCX_TYPE

        with pytest.raises(ConflictError):
            await files_tools.update_attachment(
                clients,
                path=path,
                etag=downloaded["etag"],
                download_url=source_url,
                file_id="file_roundtrip",
            )

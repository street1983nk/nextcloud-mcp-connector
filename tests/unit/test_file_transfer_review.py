"""Regression checks for transfer bounds and directory isolation."""

import base64

import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files, search

CREDS = Credentials("https://nc.test", "alice", "test-password")


class LargeStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.reads = 0
        self.closed = False

    async def __aiter__(self):
        for _ in range(1000):
            self.reads += 1
            yield b"x" * 65536

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_empty_text_response_cannot_produce_a_nonadvancing_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def nonempty_stat(*args, **kwargs):
        return {"is_collection": False, "size": 10, "content_type": "text/plain"}

    monkeypatch.setattr(dav, "stat", nonempty_stat)
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            mock.get(dav.files_url(CREDS, "/a.txt")).respond(200, content=b"")
            with pytest.raises(ToolError, match="empty chunk"):
                await files.read(NcClients(client, CREDS), "/a.txt")


@pytest.mark.anyio
async def test_ignored_range_stops_reading_and_closes_the_stream() -> None:
    stream = LargeStream()
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            mock.get(dav.files_url(CREDS, "/large.pdf")).respond(200, stream=stream)
            result = await dav.get_range(client, CREDS, "/large.pdf", offset=65536, limit=10)
    assert result == b"x" * 10
    assert stream.reads == 2
    assert stream.closed


@pytest.mark.parametrize("path", ["/Docs2/secret", "/Docs/../secret", "/Other/secret"])
def test_search_metadata_cannot_escape_root(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    assert not search._entry_in_files_root("files", {"attributes": {"path": path}})


def test_dav_filters_returned_paths_and_supports_subpath_installations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    creds = Credentials("https://nc.test/cloud", "alice", "test-password")
    body = b"""<d:multistatus xmlns:d="DAV:">
      <d:response><d:href>/cloud/remote.php/dav/files/alice/Docs/ok.pdf</d:href>
        <d:propstat><d:prop/><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
      <d:response><d:href>/cloud/remote.php/dav/files/alice/Other/secret.pdf</d:href>
        <d:propstat><d:prop/><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
      <d:response><d:href>/cloud/remote.php/dav/files/alice/Docs/%2e%2e/secret.pdf</d:href>
        <d:propstat><d:prop/><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
    </d:multistatus>"""
    assert [entry["path"] for entry in dav.parse_entries(body, creds)] == ["/Docs/ok.pdf"]


def test_upload_ids_are_isolated_by_root_and_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    first = dav.uploads_url(CREDS, "browser-upload", path="/Docs/a.pdf")
    assert "/browser-upload" not in first
    assert first == dav.uploads_url(CREDS, "browser-upload", path="/Docs/a.pdf")
    assert first != dav.uploads_url(CREDS, "browser-upload", path="/Docs/b.pdf")
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    assert first != dav.uploads_url(CREDS, "browser-upload", path="/Docs/a.pdf")


@pytest.mark.anyio
@pytest.mark.parametrize("binary", [False, True])
async def test_upload_cannot_replace_bound_root(binary: bool, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    async with httpx.AsyncClient() as client:
        clients = NcClients(client=client, creds=CREDS)
        with respx.mock as mock:
            call = (
                files.upload_binary(clients, "/Docs", "", 0, final=True)
                if binary
                else files.upload(clients, "/Docs", "")
            )
            with pytest.raises(ToolError, match="root folder"):
                await call
            assert not mock.calls


@pytest.mark.anyio
@pytest.mark.parametrize("status", [200, 204])
async def test_assembly_does_not_report_replacement_as_creation(status: int) -> None:
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            mock.route(method="MOVE").respond(status)
            with pytest.raises(ToolError, match="replaced"):
                await dav.finish_chunked_upload(client, CREDS, "/a.pdf", "test-upload", 10)


@pytest.mark.anyio
async def test_oversized_base64_rejected_before_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(files, "HARD_UPLOAD_CHUNK_BYTES", 3)

    def unexpected_decode(*args, **kwargs):
        raise AssertionError("Oversized input must not be decoded")

    monkeypatch.setattr(base64, "b64decode", unexpected_decode)
    async with httpx.AsyncClient() as client:
        with pytest.raises(ToolError, match="encoded chunk"):
            await files.upload_binary(NcClients(client, CREDS), "/a.pdf", "A" * 8, 6)


@pytest.mark.anyio
@pytest.mark.parametrize("header", ["bytes 0-9/100", "bytes 10-99/100", "bad"])
async def test_wrong_content_range_is_rejected(header: str) -> None:
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            mock.get(dav.files_url(CREDS, "/a.pdf")).respond(
                206, content=b"0123456789", headers={"Content-Range": header}
            )
            with pytest.raises(ToolError, match="different byte range"):
                await dav.get_range(client, CREDS, "/a.pdf", offset=10, limit=10)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"total_bytes": 1, "chunk_index": 2, "upload_id": "test", "final": True},
        {"total_bytes": files.HARD_UPLOAD_CHUNK_BYTES * files.MAX_UPLOAD_CHUNKS + 1},
        {
            "total_bytes": files.HARD_UPLOAD_CHUNK_BYTES * files.MAX_UPLOAD_CHUNKS,
            "chunk_index": files.MAX_UPLOAD_CHUNKS,
        },
    ],
)
async def test_impossible_uploads_are_rejected_before_network(kwargs: dict) -> None:
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            with pytest.raises(ToolError):
                await files.upload_binary(NcClients(client, CREDS), "/a.pdf", "YQ==", **kwargs)
            assert not mock.calls


@pytest.mark.anyio
@pytest.mark.parametrize("binary", [False, True])
async def test_empty_files_never_trigger_unbounded_get(
    binary: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def empty_stat(*args, **kwargs):
        return {"is_collection": False, "size": 0, "content_type": "text/plain"}

    monkeypatch.setattr(dav, "stat", empty_stat)
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            operation = files.download if binary else files.read
            result = await operation(NcClients(client, CREDS), "/empty.txt")
            assert result["content"] == (b"" if binary else "")
            assert result["truncated"] is False
            assert not mock.calls


@pytest.mark.anyio
@pytest.mark.parametrize("binary", [False, True])
async def test_mime_type_cannot_end_in_newline(binary: bool) -> None:
    async with httpx.AsyncClient() as client:
        clients = NcClients(client, CREDS)
        with respx.mock as mock:
            call = (
                files.upload_binary(
                    clients, "/a.pdf", "YQ==", 1, final=True, content_type="text/plain\n"
                )
                if binary
                else files.upload(clients, "/a.txt", "a", content_type="text/plain\n")
            )
            with pytest.raises(ToolError, match="mimetype"):
                await call
            assert not mock.calls

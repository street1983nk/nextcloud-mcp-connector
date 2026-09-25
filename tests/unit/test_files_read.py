"""Unit tests for the DAV client and the ``files_read`` tool logic.

All paths are covered on purpose: happy, 404, 403, 401, 429, 5xx, oversize, binary, path
traversal and the ranged continuation read. respx mocks the httpx layer, so these tests
run without Nextcloud and without Docker.
"""

import base64

import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"
NOTES_URL = f"{FILES_ROOT}/Docs/notes.md"
CONTENT = "# Notes\nline two\n"


def test_configured_files_root_is_a_virtual_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/rtc/mth/knsk")

    assert dav.safe_path("/") == "/rtc/mth/knsk"
    assert dav.safe_path("/scan.pdf") == "/rtc/mth/knsk/scan.pdf"
    assert dav.safe_path("/rtc/mth/knsk/scan.pdf") == "/rtc/mth/knsk/scan.pdf"
    assert dav.safe_path("/other") == "/rtc/mth/knsk/other"
    assert dav.search_scope(Credentials("http://nc.test", "alice", "secret")) == (
        "/files/alice/rtc/mth/knsk"
    )


def _propfind_body(
    *,
    length: int,
    content_type: str = "text/markdown",
    href: str = "/remote.php/dav/files/alice/Docs/notes.md",
) -> str:
    return f"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>{href}</d:href>
    <d:propstat>
      <d:prop>
        <d:getcontentlength>{length}</d:getcontentlength>
        <d:getcontenttype>{content_type}</d:getcontenttype>
        <d:getlastmodified>Thu, 14 Aug 2026 10:00:00 GMT</d:getlastmodified>
        <d:getetag>&quot;etag-1&quot;</d:getetag>
        <d:resourcetype/>
        <oc:fileid>4711</oc:fileid>
        <oc:permissions>RGDNVW</oc:permissions>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


@pytest.mark.anyio
async def test_read_returns_content_and_stable_fields(clients: NcClients) -> None:
    body = CONTENT.encode("utf-8")
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(207, text=_propfind_body(length=len(body)))
        )
        mock.route(method="GET", url=NOTES_URL).mock(return_value=httpx.Response(200, content=body))
        result = await files_tools.read(clients, path="/Docs/notes.md")

    assert result == {
        "path": "/Docs/notes.md",
        "content": CONTENT,
        "size": len(body),
        "content_type": "text/markdown",
        "truncated": False,
    }
    assert "next_offset" not in result


@pytest.mark.anyio
async def test_read_sends_basic_auth_per_request_and_depth_zero(clients: NcClients) -> None:
    body = CONTENT.encode("utf-8")
    with respx.mock as mock:
        propfind = mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(207, text=_propfind_body(length=len(body)))
        )
        mock.route(method="GET", url=NOTES_URL).mock(return_value=httpx.Response(200, content=body))
        await files_tools.read(clients, path="/Docs/notes.md")

    request = propfind.calls[0].request
    expected = base64.b64encode(f"{USER}:{SECRET}".encode()).decode()
    assert request.headers["authorization"] == f"Basic {expected}"
    assert request.headers["depth"] == "0"
    assert b"getcontentlength" in request.content


@pytest.mark.anyio
async def test_oversize_file_returns_the_first_slice_instead_of_failing(
    clients: NcClients,
) -> None:
    """WR-03: a file above HARD_MAX_BYTES is answered with a marked slice, not an error."""
    total = 3_000_000
    first_slice = files_tools.DEFAULT_MAX_BYTES
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(207, text=_propfind_body(length=total))
        )
        get = mock.route(method="GET", url=NOTES_URL).mock(
            return_value=httpx.Response(206, content=b"x" * first_slice)
        )
        result = await files_tools.read(clients, path="/Docs/notes.md")

    sent = get.calls[0].request.headers["range"]
    assert sent == f"bytes=0-{first_slice - 1}", "only the slice is downloaded, never the file"
    assert result["size"] == total
    assert result["truncated"] is True
    assert result["next_offset"] == first_slice
    assert len(result["content"]) == first_slice


@pytest.mark.anyio
async def test_binary_file_is_rejected_without_base64(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=f"{FILES_ROOT}/Photos/cat.png").mock(
            return_value=httpx.Response(
                207,
                text=_propfind_body(
                    length=2048,
                    content_type="image/png",
                    href="/remote.php/dav/files/alice/Photos/cat.png",
                ),
            )
        )
        get = mock.route(method="GET", url=f"{FILES_ROOT}/Photos/cat.png")
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Photos/cat.png")

    assert "image/png" in excinfo.value.message
    assert not get.called


@pytest.mark.anyio
async def test_download_returns_a_complete_binary_file(clients: NcClients) -> None:
    body = b"%PDF-1.7\nhandwritten notes\n%%EOF"
    url = f"{FILES_ROOT}/Docs/scan.pdf"
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=url).mock(
            return_value=httpx.Response(
                207,
                text=_propfind_body(
                    length=len(body),
                    content_type="application/pdf",
                    href="/remote.php/dav/files/alice/Docs/scan.pdf",
                ),
            )
        )
        get = mock.route(method="GET", url=url).mock(return_value=httpx.Response(200, content=body))
        result = await files_tools.download(clients, path="/Docs/scan.pdf")

    assert result == {
        "path": "/Docs/scan.pdf",
        "size": len(body),
        "content_type": "application/pdf",
        "offset": 0,
        "bytes": len(body),
        "truncated": False,
        "content": body,
    }
    assert get.calls[0].request.headers["range"] == f"bytes=0-{len(body) - 1}"
    assert "next_offset" not in result


@pytest.mark.anyio
async def test_download_slices_a_file_larger_than_the_per_call_limit(clients: NcClients) -> None:
    url = f"{FILES_ROOT}/Docs/large.pdf"
    total = files_tools.HARD_DOWNLOAD_BYTES * 4
    chunk = b"chunk"
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=url).mock(
            return_value=httpx.Response(
                207,
                text=_propfind_body(
                    length=total,
                    content_type="application/pdf",
                    href="/remote.php/dav/files/alice/Docs/large.pdf",
                ),
            )
        )
        get = mock.route(method="GET", url=url).mock(
            return_value=httpx.Response(206, content=chunk)
        )
        result = await files_tools.download(clients, path="/Docs/large.pdf", offset=100)

    assert get.calls[0].request.headers["range"] == (
        f"bytes=100-{100 + files_tools.DEFAULT_DOWNLOAD_BYTES - 1}"
    )
    assert result["size"] == total
    assert result["offset"] == 100
    assert result["bytes"] == len(chunk)
    assert result["truncated"] is True
    assert result["next_offset"] == 100 + len(chunk)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "text/markdown", "application/json", "application/xml", "application/yaml"],
)
async def test_text_like_mimetypes_are_accepted(clients: NcClients, content_type: str) -> None:
    body = b"{}"
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(
                207, text=_propfind_body(length=len(body), content_type=content_type)
            )
        )
        mock.route(method="GET", url=NOTES_URL).mock(return_value=httpx.Response(200, content=body))
        result = await files_tools.read(clients, path="/Docs/notes.md")

    assert result["content_type"] == content_type


@pytest.mark.anyio
async def test_offset_read_sends_a_range_header_and_returns_next_offset(
    clients: NcClients,
) -> None:
    total = 1_000_000
    slice_size = 1024
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(207, text=_propfind_body(length=total))
        )
        get = mock.route(method="GET", url=NOTES_URL).mock(
            return_value=httpx.Response(206, content=b"x" * slice_size)
        )
        result = await files_tools.read(
            clients, path="/Docs/notes.md", offset=100, max_bytes=slice_size
        )

    sent = get.calls[0].request.headers["range"]
    assert sent == f"bytes=100-{100 + slice_size - 1}"
    assert result["truncated"] is True
    assert result["next_offset"] == 100 + slice_size
    assert result["size"] == total


@pytest.mark.anyio
async def test_a_200_answer_to_a_range_request_is_cut_to_the_requested_window(
    clients: NcClients,
) -> None:
    """WR-05: a server that ignores Range answers 200 with the full body; the slice
    bookkeeping (content, truncated, next_offset) must still describe the asked window."""
    body = b"0123456789" * 10  # 100 bytes of full file
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(207, text=_propfind_body(length=len(body)))
        )
        get = mock.route(method="GET", url=NOTES_URL).mock(
            return_value=httpx.Response(200, content=body)
        )
        result = await files_tools.read(clients, path="/Docs/notes.md", offset=20, max_bytes=30)

    assert get.calls[0].request.headers["range"] == "bytes=20-49"
    assert result["content"] == body[20:50].decode()
    assert result["truncated"] is True
    assert result["next_offset"] == 50
    assert result["size"] == len(body)


@pytest.mark.anyio
async def test_get_range_with_an_open_end_cuts_a_200_answer_at_the_offset(
    clients: NcClients,
) -> None:
    body = b"abcdefghij"
    with respx.mock as mock:
        mock.route(method="GET", url=NOTES_URL).mock(return_value=httpx.Response(200, content=body))
        data = await dav.get_range(clients.client, clients.creds, "/Docs/notes.md", offset=4)

    assert data == b"efghij", "an open-ended range on a 200 keeps only the tail"


@pytest.mark.anyio
async def test_a_206_answer_is_taken_as_the_slice_it_already_is(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="GET", url=NOTES_URL).mock(
            return_value=httpx.Response(206, content=b"efgh")
        )
        data = await dav.get_range(
            clients.client, clients.creds, "/Docs/notes.md", offset=4, limit=4
        )

    assert data == b"efgh", "a 206 body is already the window and must not be cut again"


@pytest.mark.anyio
async def test_offset_beyond_the_end_is_rejected(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(207, text=_propfind_body(length=10))
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs/notes.md", offset=99)

    assert "10" in excinfo.value.message


@pytest.mark.anyio
async def test_max_bytes_above_the_hard_ceiling_is_rejected(clients: NcClients) -> None:
    with respx.mock, pytest.raises(ToolError) as excinfo:
        await files_tools.read(clients, path="/Docs/notes.md", max_bytes=5_000_000)
    assert str(files_tools.HARD_MAX_BYTES) in excinfo.value.message
    assert "max_bytes" not in excinfo.value.hint, (
        "the registered tool has no max_bytes parameter; the hint must not name it (WR-03)"
    )


@pytest.mark.anyio
async def test_missing_file_reports_the_path(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(return_value=httpx.Response(404))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs/notes.md")

    assert "not found" in excinfo.value.message.lower()
    assert "/Docs/notes.md" in excinfo.value.message


@pytest.mark.anyio
async def test_forbidden_reports_a_permission_hint(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(return_value=httpx.Response(403))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs/notes.md")

    assert "permission" in (excinfo.value.message + excinfo.value.hint).lower()


@pytest.mark.anyio
async def test_server_error_is_degraded_not_leaked(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(500, text="<html>stack trace</html>")
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs/notes.md")

    assert "500" in excinfo.value.message
    assert "stack trace" not in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_rejected_app_password_is_final_without_a_retry(clients: NcClients) -> None:
    with respx.mock as mock:
        route = mock.route(method="PROPFIND", url=NOTES_URL).mock(return_value=httpx.Response(401))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs/notes.md")

    assert route.call_count == 1, "never retry a failed auth: it feeds the brute force guard"
    assert "app password" in excinfo.value.message.lower()
    assert SECRET not in excinfo.value.message + excinfo.value.hint


@pytest.mark.anyio
async def test_rate_limit_asks_the_caller_to_wait(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(return_value=httpx.Response(429))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs/notes.md")

    assert "wait" in (excinfo.value.message + excinfo.value.hint).lower()


@pytest.mark.anyio
async def test_redirect_is_reported_as_a_configuration_error(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(301, headers={"location": "https://elsewhere.test/"})
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs/notes.md")

    assert "redirect" in (excinfo.value.message + excinfo.value.hint).lower()
    assert "elsewhere.test" not in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/Docs/../../etc/passwd",
        "/..",
        "../secrets.txt",
        "/Docs\\notes.md",
        "",
        "   ",
        "/Docs/notes\x00.md",
    ],
)
async def test_unsafe_paths_never_reach_the_network(clients: NcClients, path: str) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path=path)
        assert len(mock.calls) == 0, "the path guard must run before any request"
    assert excinfo.value.hint


def test_safe_path_normalises_without_changing_meaning() -> None:
    assert dav.safe_path("Docs/notes.md") == "/Docs/notes.md"
    assert dav.safe_path("/Docs//notes.md") == "/Docs/notes.md"
    assert dav.safe_path("/Docs/./notes.md") == "/Docs/notes.md"
    assert dav.safe_path("/") == "/"


def test_files_url_quotes_special_characters() -> None:
    creds = Credentials(BASE, USER, SECRET)
    url = dav.files_url(creds, "/Docs/Jahres bericht & Anhang/ü.md")
    assert url.startswith(f"{FILES_ROOT}/Docs/")
    assert " " not in url
    assert "&" not in url
    assert "/Docs/" in url, "slashes stay path separators"


@pytest.mark.anyio
async def test_stat_reports_metadata(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=NOTES_URL).mock(
            return_value=httpx.Response(207, text=_propfind_body(length=42))
        )
        info = await dav.stat(clients.client, clients.creds, "/Docs/notes.md")

    assert info["size"] == 42
    assert info["content_type"] == "text/markdown"
    assert info["fileid"] == "4711"
    assert info["is_collection"] is False


@pytest.mark.anyio
async def test_reading_a_folder_is_rejected(clients: NcClients) -> None:
    folder_body = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/Docs/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
        <oc:fileid>10</oc:fileid>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=f"{FILES_ROOT}/Docs").mock(
            return_value=httpx.Response(207, text=folder_body)
        )
        get = mock.route(method="GET", url=f"{FILES_ROOT}/Docs")
        with pytest.raises(ToolError) as excinfo:
            await files_tools.read(clients, path="/Docs")

    assert "folder" in excinfo.value.message.lower()
    assert not get.called

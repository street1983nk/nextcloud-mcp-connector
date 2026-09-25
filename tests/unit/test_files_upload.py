"""Unit tests for the create-only upload (TOOL-09, threats T-01-15 and T-01-16).

The promise of this project is that the server cannot overwrite anything. That promise
rests on one header, so it gets its own assertion here, and on the server side it is
proven again against a real Nextcloud in tests/integration/test_files_roundtrip.py.

All paths are covered: created, conflict, no write permission, missing parent, rejected
app password, server error, path traversal, empty content and a payload that is not
encodable as UTF-8.
"""

import base64

import httpx
import pytest
import respx

from mcp_connector.errors import ConflictError, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"
TARGET = "/Docs/new-note.md"
TARGET_URL = f"{FILES_ROOT}/Docs/new-note.md"
CONTENT = "# Neue Notiz\nZeile zwei\n"
UPLOAD_ID = "upload-test"
UPLOAD_FOLDER_URL = dav.uploads_url(Credentials(BASE, USER, SECRET), UPLOAD_ID, path=TARGET)


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


@pytest.mark.anyio
async def test_upload_creates_the_file_and_reports_stable_fields(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PUT", url=TARGET_URL).mock(
            return_value=httpx.Response(201, headers={"etag": '"etag-new"'})
        )
        result = await files_tools.upload(clients, path=TARGET, content=CONTENT)

    assert result == {"path": TARGET, "etag": '"etag-new"', "created": True}


@pytest.mark.anyio
async def test_upload_sends_if_none_match_star_content_type_and_basic_auth(
    clients: NcClients,
) -> None:
    with respx.mock as mock:
        put = mock.route(method="PUT", url=TARGET_URL).mock(return_value=httpx.Response(201))
        await files_tools.upload(clients, path=TARGET, content=CONTENT)

    request = put.calls[0].request
    assert request.headers["if-none-match"] == "*", (
        "without this header the PUT would overwrite an existing file"
    )
    assert request.headers["content-type"] == "text/markdown"
    expected = base64.b64encode(f"{USER}:{SECRET}".encode()).decode()
    assert request.headers["authorization"] == f"Basic {expected}"
    assert request.content == CONTENT.encode("utf-8")


@pytest.mark.anyio
async def test_upload_does_not_probe_the_target_first(clients: NcClients) -> None:
    """The overwrite guard is server side, so a PROPFIND would only add a race window."""
    with respx.mock as mock:
        mock.route(method="PUT", url=TARGET_URL).mock(return_value=httpx.Response(201))
        await files_tools.upload(clients, path=TARGET, content=CONTENT)
        methods = [call.request.method for call in mock.calls]

    assert methods == ["PUT"], "no PROPFIND probe: the guard is server side and race free"


@pytest.mark.anyio
async def test_existing_file_is_refused_with_the_no_overwrite_sentence(
    clients: NcClients,
) -> None:
    with respx.mock as mock:
        put = mock.route(method="PUT", url=TARGET_URL).mock(return_value=httpx.Response(412))
        with pytest.raises(ConflictError) as excinfo:
            await files_tools.upload(clients, path=TARGET, content=CONTENT)

    assert put.call_count == 1, "a conflict is final; never retry it as an overwrite"
    text = f"{excinfo.value.message} {excinfo.value.hint}"
    assert f"A file already exists at {TARGET}." in text
    assert "This server never overwrites files." in text
    assert "Choose a different name." in text


@pytest.mark.anyio
async def test_missing_write_permission_names_the_path(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PUT", url=TARGET_URL).mock(return_value=httpx.Response(403))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path=TARGET, content=CONTENT)

    assert TARGET in excinfo.value.message
    assert "permission" in (excinfo.value.message + excinfo.value.hint).lower()


@pytest.mark.anyio
async def test_missing_parent_folder_is_reported_without_creating_it(clients: NcClients) -> None:
    with respx.mock as mock:
        put = mock.route(method="PUT", url=TARGET_URL).mock(return_value=httpx.Response(404))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path=TARGET, content=CONTENT)
        methods = [call.request.method for call in mock.calls]

    assert "folder" in excinfo.value.message.lower()
    assert "/Docs" in excinfo.value.message
    headers = put.calls[0].request.headers
    assert "x-nc-webdav-automkcol" not in headers, "creating folders is not part of the contract"
    assert methods == ["PUT"], "no MKCOL, ever"


@pytest.mark.anyio
async def test_rejected_app_password_is_final_without_a_retry(clients: NcClients) -> None:
    with respx.mock as mock:
        put = mock.route(method="PUT", url=TARGET_URL).mock(return_value=httpx.Response(401))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path=TARGET, content=CONTENT)

    assert put.call_count == 1, "never retry a failed auth: it feeds the brute force guard"
    assert "app password" in excinfo.value.message.lower()
    assert SECRET not in excinfo.value.message + excinfo.value.hint


@pytest.mark.anyio
async def test_server_error_is_degraded_not_leaked(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PUT", url=TARGET_URL).mock(
            return_value=httpx.Response(500, text="<html>stack trace</html>")
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path=TARGET, content=CONTENT)

    assert "500" in excinfo.value.message
    assert "stack trace" not in excinfo.value.message
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_redirect_is_reported_as_a_configuration_error(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PUT", url=TARGET_URL).mock(
            return_value=httpx.Response(301, headers={"location": "https://elsewhere.test/"})
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path=TARGET, content=CONTENT)

    assert "redirect" in (excinfo.value.message + excinfo.value.hint).lower()
    assert "elsewhere.test" not in excinfo.value.hint


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    ["/Docs/../../etc/passwd", "../secrets.txt", "/Docs\\note.md", "", "   "],
)
async def test_unsafe_paths_never_reach_the_network(clients: NcClients, path: str) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path=path, content=CONTENT)
        assert len(mock.calls) == 0, "the path guard must run before any request"
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_folder_target_is_refused_before_the_request(clients: NcClients) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path="/Docs/", content=CONTENT)
        assert len(mock.calls) == 0

    assert "file" in (excinfo.value.message + excinfo.value.hint).lower()


@pytest.mark.anyio
async def test_empty_content_is_allowed(clients: NcClients) -> None:
    with respx.mock as mock:
        put = mock.route(method="PUT", url=TARGET_URL).mock(return_value=httpx.Response(201))
        result = await files_tools.upload(clients, path=TARGET, content="")

    assert result["created"] is True
    assert put.calls[0].request.content == b""


@pytest.mark.anyio
async def test_content_that_is_not_utf8_encodable_is_refused(clients: NcClients) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(clients, path=TARGET, content="broken \ud800 surrogate")
        assert len(mock.calls) == 0

    assert "utf-8" in (excinfo.value.message + excinfo.value.hint).lower()


@pytest.mark.anyio
async def test_the_caller_can_choose_the_content_type(clients: NcClients) -> None:
    with respx.mock as mock:
        put = mock.route(method="PUT", url=f"{FILES_ROOT}/data.json").mock(
            return_value=httpx.Response(201)
        )
        await files_tools.upload(
            clients, path="/data.json", content="{}", content_type="application/json"
        )

    assert put.calls[0].request.headers["content-type"] == "application/json"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "content_type",
    ["text/markdown\r\nX-Injected: 1", "text/markdown; charset=utf-8", "markdown", ""],
)
async def test_a_content_type_that_is_not_a_bare_mimetype_is_refused(
    clients: NcClients, content_type: str
) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload(
                clients, path=TARGET, content=CONTENT, content_type=content_type
            )
        assert len(mock.calls) == 0, "a header value from the model never reaches httpx unchecked"

    assert "mimetype" in excinfo.value.message.lower()


@pytest.mark.anyio
async def test_put_new_file_quotes_special_characters_in_the_target(clients: NcClients) -> None:
    with respx.mock as mock:
        put = mock.route(method="PUT").mock(return_value=httpx.Response(201))
        await dav.put_new_file(
            clients.client,
            clients.creds,
            "/Docs/Jahres bericht & Anhang/ü.md",
            b"x",
            "text/markdown",
        )

    url = str(put.calls[0].request.url)
    assert url.startswith(f"{FILES_ROOT}/Docs/")
    assert " " not in url
    assert "&" not in url


@pytest.mark.anyio
async def test_binary_upload_assembles_a_pdf_without_replacing_an_existing_file(
    clients: NcClients,
) -> None:
    pdf = b"%PDF-1.7\nhandwritten scan\n"
    encoded = base64.b64encode(pdf).decode("ascii")
    with respx.mock(assert_all_called=True) as mock:
        mkcol = mock.route(method="MKCOL", url=UPLOAD_FOLDER_URL).mock(
            return_value=httpx.Response(201)
        )
        put = mock.route(method="PUT", url=f"{UPLOAD_FOLDER_URL}/00001").mock(
            return_value=httpx.Response(201)
        )
        move = mock.route(method="MOVE", url=f"{UPLOAD_FOLDER_URL}/.file").mock(
            return_value=httpx.Response(201, headers={"etag": '"pdf-etag"'})
        )

        result = await files_tools.upload_binary(
            clients,
            path=TARGET,
            content_base64=encoded,
            total_bytes=len(pdf),
            upload_id=UPLOAD_ID,
            final=True,
            content_type="application/pdf",
        )

    assert mkcol.calls[0].request.headers["destination"] == TARGET_URL
    assert put.calls[0].request.content == pdf
    assert put.calls[0].request.headers["oc-total-length"] == str(len(pdf))
    assert put.calls[0].request.headers["content-type"] == "application/pdf"
    assert move.calls[0].request.headers["destination"] == TARGET_URL
    assert move.calls[0].request.headers["overwrite"] == "F"
    assert result == {
        "path": TARGET,
        "etag": '"pdf-etag"',
        "created": True,
        "upload_id": UPLOAD_ID,
        "chunk_index": 1,
        "bytes": len(pdf),
        "total_bytes": len(pdf),
        "completed": True,
    }


@pytest.mark.anyio
async def test_binary_upload_returns_a_continuation_for_a_large_file(clients: NcClients) -> None:
    chunk = b"x" * files_tools.MIN_UPLOAD_CHUNK_BYTES
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="MKCOL", url=UPLOAD_FOLDER_URL).mock(return_value=httpx.Response(201))
        put = mock.route(method="PUT", url=f"{UPLOAD_FOLDER_URL}/00001").mock(
            return_value=httpx.Response(201)
        )

        result = await files_tools.upload_binary(
            clients,
            path=TARGET,
            content_base64=base64.b64encode(chunk).decode("ascii"),
            total_bytes=len(chunk) + 10,
            upload_id=UPLOAD_ID,
            final=False,
        )

    assert put.calls[0].request.content == chunk
    assert result == {
        "path": TARGET,
        "upload_id": UPLOAD_ID,
        "chunk_index": 1,
        "bytes": len(chunk),
        "total_bytes": len(chunk) + 10,
        "completed": False,
        "next_chunk": 2,
    }


@pytest.mark.anyio
async def test_binary_upload_rejects_invalid_base64_before_network(clients: NcClients) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.upload_binary(
                clients,
                path=TARGET,
                content_base64="not base64!",
                total_bytes=10,
                final=True,
            )
        assert len(mock.calls) == 0

    assert "base64" in excinfo.value.message.lower()

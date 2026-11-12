"""Unit tests for the folder client: one MKCOL without a body and its named branches (FOLD-01).

The status matrix comes from the measurement of phase 30 (docs/spike-tasks.md, sections 1.3
and 1.4): 201 is the only success and carries the id in the ``oc-fileid`` header, 405 reads
the same for a folder and a file, 409 and 404 mean a missing parent, 400 an invalid name,
403 a missing right, 423 a lock and 507 a full quota. No branch may end in the catch-all
sentence of another status handler.
"""

import httpx
import pytest
import respx

from mcp_connector.errors import REASON_PERMISSION_DENIED, ToolError
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"
TARGET = "/Projekte/2026"
TARGET_URL = f"{FILES_ROOT}/Projekte/2026"

#: The header exactly as Nextcloud 35.0.0 sent it (phase 30, raw/nc35-mkcol.txt line 87).
OC_FILEID = "00023274oclxpo7v8s2m"

#: Every status that has a named branch of its own.
NAMED_STATUSES = (301, 400, 401, 403, 404, 409, 423, 429, 500, 502, 503, 507)

#: The statuses that are handed on to ``dav._check``.
SHARED_STATUSES = (301, 401, 429, 500, 502, 503)

#: A status no branch names: the technical rest.
UNNAMED_STATUS = 418


@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, USER, SECRET)


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


def triple(error: ToolError) -> tuple[str, str, str]:
    return (error.message, error.hint, error.reason)


async def refused(client: httpx.AsyncClient, creds: Credentials, status: int) -> ToolError:
    """The error of one MKCOL that Nextcloud answers with ``status``."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.route(method="MKCOL", url=TARGET_URL).mock(return_value=httpx.Response(status))
        with pytest.raises(ToolError) as caught:
            await dav.make_folder(client, creds, TARGET)
    assert route.call_count == 1, "a refusal is final; no retry"
    return caught.value


def shared_error(status: int) -> ToolError:
    """What ``dav._check`` says about ``status``, the one source of those sentences."""
    with pytest.raises(ToolError) as caught:
        dav._check(httpx.Response(status), TARGET)
    return caught.value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (OC_FILEID, "23274"),
        ("", ""),
        ("abc", ""),
        ("12345", ""),
        (" 00000007ocabc ", "7"),
    ],
)
def test_fileid_from_header_reads_the_padded_id_before_the_instance_id(
    value: str, expected: str
) -> None:
    assert dav.fileid_from_header(value) == expected


@pytest.mark.anyio
async def test_a_free_name_is_created_and_the_id_comes_from_the_header(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="MKCOL", url=TARGET_URL).mock(
            return_value=httpx.Response(201, headers={"oc-fileid": OC_FILEID})
        )
        result = await dav.make_folder(client, creds, TARGET)
        requests = [call.request for call in mock.calls]

    assert result == {"created": True, "fileid": "23274"}
    assert [request.method for request in requests] == ["MKCOL"]
    assert requests[0].content == b"", "a body without an XML type would earn a 415"
    assert "content-type" not in requests[0].headers


@pytest.mark.anyio
async def test_a_created_folder_without_the_header_has_no_id(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="MKCOL", url=TARGET_URL).mock(return_value=httpx.Response(201))
        result = await dav.make_folder(client, creds, TARGET)

    assert result == {"created": True, "fileid": ""}


@pytest.mark.anyio
async def test_an_occupied_name_is_reported_without_an_error(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    """405 reads the same for a folder and a file; the caller decides with one PROPFIND."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.route(method="MKCOL", url=TARGET_URL).mock(return_value=httpx.Response(405))
        result = await dav.make_folder(client, creds, TARGET)

    assert result == {"created": False, "fileid": ""}
    assert route.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("status", [404, 409])
async def test_a_missing_parent_is_the_shared_parent_missing_error(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    error = await refused(client, creds, status)

    assert triple(error) == triple(dav.parent_missing(TARGET))


@pytest.mark.anyio
async def test_a_missing_right_names_the_path_and_the_reason(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await refused(client, creds, 403)

    assert error.message == f"No permission to create a folder at {TARGET}."
    assert error.hint == (
        "The share, group folder or storage does not allow creating folders there; "
        "ask its owner for the create permission."
    )
    assert error.reason == REASON_PERMISSION_DENIED


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "message", "hint"),
    [
        (
            400,
            f"Nextcloud does not accept the folder name in {TARGET}.",
            (
                "Avoid reserved names such as .htaccess, a backslash, a trailing space or "
                "dot, and very long names."
            ),
        ),
        (
            423,
            f"{TARGET} is locked in Nextcloud.",
            "Wait until the other client releases the lock, then try again.",
        ),
        (
            507,
            f"Not enough space in Nextcloud to create {TARGET}.",
            "Free up quota in Nextcloud and try again.",
        ),
    ],
)
async def test_name_lock_and_quota_have_a_sentence_each(
    client: httpx.AsyncClient, creds: Credentials, status: int, message: str, hint: str
) -> None:
    error = await refused(client, creds, status)

    assert (error.message, error.hint) == (message, hint)


@pytest.mark.anyio
@pytest.mark.parametrize("status", SHARED_STATUSES)
async def test_redirect_auth_rate_limit_and_server_errors_use_the_shared_sentences(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    error = await refused(client, creds, status)

    assert triple(error) == triple(shared_error(status))


@pytest.mark.anyio
async def test_an_unnamed_status_ends_in_the_technical_rest(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await refused(client, creds, UNNAMED_STATUS)

    assert error.message == (
        f"Nextcloud answered creating the folder {TARGET} with status {UNNAMED_STATUS}."
    )
    assert error.hint == (
        "Check the Nextcloud log for that request; the folder was probably not created."
    )
    assert "unexpected" not in error.message


@pytest.mark.anyio
@pytest.mark.parametrize("status", NAMED_STATUSES)
async def test_every_named_status_has_a_branch_of_its_own(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    """Counter check with a positive control: the rest exists, and no named status hits it."""
    rest = await refused(client, creds, UNNAMED_STATUS)
    assert str(UNNAMED_STATUS) in rest.message, "the rest must be reachable to prove anything"

    error = await refused(client, creds, status)

    assert "unexpected status" not in error.message
    assert error.message != rest.message.replace(str(UNNAMED_STATUS), str(status))
    assert not error.message.startswith("Nextcloud answered creating the folder")


@pytest.mark.anyio
async def test_a_traversal_path_never_reaches_nextcloud(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        with pytest.raises(ToolError):
            await dav.make_folder(client, creds, "/Projekte/../../etc")

    assert route.call_count == 0


def test_the_parent_hint_names_the_folder_tool_and_the_web_way() -> None:
    hint = dav.parent_missing("/A/b.txt").hint

    assert "files_create_folder" in hint
    assert "in Nextcloud" in hint


# --- probe_folder: the lean read of folder creation (D-31-05) -----------------------------


def multistatus(fileid: str, *, folder: bool) -> httpx.Response:
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:response>'
        f"<d:href>/remote.php/dav/files/{USER}{TARGET}</d:href><d:propstat><d:prop>"
        f"<oc:fileid>{fileid}</oc:fileid>"
        f"<d:resourcetype>{'<d:collection/>' if folder else ''}</d:resourcetype>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        "</d:response></d:multistatus>"
    )
    return httpx.Response(207, content=body.encode(), headers={"Content-Type": "application/xml"})


async def probed(
    client: httpx.AsyncClient, creds: Credentials, response: httpx.Response
) -> tuple[dict | None, httpx.Request]:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=TARGET_URL).mock(return_value=response)
        result = await dav.probe_folder(client, creds, TARGET)
        assert mock.calls.call_count == 1
        request = mock.calls[0].request
    return result, request


async def probe_refused(client: httpx.AsyncClient, creds: Credentials, status: int) -> ToolError:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=TARGET_URL).mock(return_value=httpx.Response(status))
        with pytest.raises(ToolError) as caught:
            await dav.probe_folder(client, creds, TARGET)
    return caught.value


@pytest.mark.anyio
async def test_probe_reports_a_folder_with_its_id(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    result, _ = await probed(client, creds, multistatus("120", folder=True))

    assert result == {"path": TARGET, "is_collection": True, "fileid": "120"}


@pytest.mark.anyio
async def test_probe_reports_a_file_as_not_a_folder(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    result, _ = await probed(client, creds, multistatus("121", folder=False))

    assert result == {"path": TARGET, "is_collection": False, "fileid": "121"}


@pytest.mark.anyio
@pytest.mark.parametrize("status", [404, 409])
async def test_probe_reads_404_and_409_as_missing(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    """409 is a node below a file (assumption A5): missing, not a status without a name."""
    result, _ = await probed(client, creds, httpx.Response(status))

    assert result is None


@pytest.mark.anyio
async def test_probe_names_a_refused_name(client: httpx.AsyncClient, creds: Credentials) -> None:
    error = await probe_refused(client, creds, 400)

    assert triple(error) == triple(dav.name_rejected(TARGET))
    assert error.message == f"Nextcloud does not accept the folder name in {TARGET}."
    assert "unexpected status" not in error.message


@pytest.mark.anyio
@pytest.mark.parametrize("status", [403, 500])
async def test_probe_hands_every_other_status_to_the_shared_sentences(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    error = await probe_refused(client, creds, status)

    assert triple(error) == triple(shared_error(status))


@pytest.mark.anyio
async def test_probe_asks_for_the_node_type_and_the_id_and_nothing_else(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    _, request = await probed(client, creds, multistatus("120", folder=True))

    assert request.headers["depth"] == "0"
    assert b"resourcetype" in request.content
    assert b"fileid" in request.content
    assert b"permissions" not in request.content, "D-31-05: no rights pre-check"
    assert b"getcontentlength" not in request.content


@pytest.mark.anyio
async def test_the_mkcol_name_refusal_is_the_public_factory(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    error = await refused(client, creds, 400)

    assert triple(error) == triple(dav.name_rejected(TARGET))

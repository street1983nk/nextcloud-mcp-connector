"""Unit tests for the folder tool logic: answer shape, chain, cap, partial abort, sandbox.

``files.create_folder`` is the second writer of the file surface (FOLD-01 to FOLD-04). Each
decision of phase 31 is nailed down by name here:

*   D-31-01: with ``parents`` the missing folders are counted before the first MKCOL, and
    more than ten are refused with nothing created.
*   D-31-02: a failure inside the chain keeps its sentence and names what was created.
    Since plan 31-04b that holds for a network failure too, which also names the one
    folder whose state is unknown: the MKCOL that was under way.
*   D-31-03: the answer is ``path``, ``created``, ``id`` and, with ``parents``, the list
    ``created_folders``.
*   D-31-04: the id of an existing folder comes out of the read that tells folder from file.
*   D-31-05: no rights pre-check; without ``parents`` no read goes out before the write.

The ``kein-ki`` guard is switched to ``untagged`` here; its states are tested in
``test_files_create_folder_exclusion.py``.
"""

import inspect

import guard_routes
import httpx
import pytest
import respx

from mcp_connector import config, server
from mcp_connector.errors import (
    REASON_PERMISSION_DENIED,
    REASON_TIMEOUT,
    REASON_UNREACHABLE,
    ConflictError,
    ToolError,
)
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
DAV_HOME = f"/remote.php/dav/files/{USER}"
FILES_ROOT = f"{BASE}{DAV_HOME}"
TARGET = "/Projekte/2026"

#: The header exactly as Nextcloud 35.0.0 sent it (phase 30, raw/nc35-mkcol.txt line 87).
OC_FILEID = "00023274oclxpo7v8s2m"

CHAIN = ["/A/b", "/A/b/c", "/A/b/c/d"]
CHAIN_TARGET = CHAIN[-1]
SUFFIX_AFTER_ONE = " Already created in this call and left in place: /A/b."

#: The retry is safe either way: a second call keeps what exists (E5, idempotent).
CHAIN_RETRY_HINT = (
    "Call again with the same path and parents=true; that is safe: folders that exist "
    "are kept and only the missing ones are created."
)
SINGLE_RETRY_HINT = "Call again with the same path; that is safe: a folder that exists is kept."


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    guard_routes.patch_untagged(monkeypatch)


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def _mock() -> respx.MockRouter:
    """Every request must hit a route: an unplanned one fails the test by itself."""
    return respx.mock(assert_all_mocked=True, assert_all_called=False)


def url(path: str) -> str:
    return f"{FILES_ROOT}{path}"


def node(fileid: str, *, folder: bool = True) -> httpx.Response:
    """A minimal 207 of a Depth 0 PROPFIND: the id and the node type, nothing else."""
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}"><d:response>'
        f"<d:href>{DAV_HOME}/x</d:href><d:propstat><d:prop>"
        f"<oc:fileid>{fileid}</oc:fileid>"
        f"<d:resourcetype>{'<d:collection/>' if folder else ''}</d:resourcetype>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        "</d:response></d:multistatus>"
    )
    return httpx.Response(207, content=body.encode(), headers={"Content-Type": "application/xml"})


def made(fileid: int) -> httpx.Response:
    return httpx.Response(201, headers={"oc-fileid": f"{fileid:08d}oclxpo7v8s2m"})


def propfind(mock: respx.MockRouter, path: str, response: httpx.Response) -> respx.Route:
    return mock.route(method="PROPFIND", url=url(path)).mock(return_value=response)


def mkcol(mock: respx.MockRouter, path: str, response: httpx.Response) -> respx.Route:
    return mock.route(method="MKCOL", url=url(path)).mock(return_value=response)


def requests_of(mock: respx.MockRouter) -> list[tuple[str, str]]:
    """Method and home path of every request, in the order they went out."""
    return [
        (call.request.method, call.request.url.path.removeprefix(DAV_HOME)) for call in mock.calls
    ]


def assert_lean_reads(mock: respx.MockRouter) -> None:
    """D-31-05: no read of this tool asks for rights, before or after a MKCOL.

    The two positive controls prove that the body is really inspected: a body that never
    reached this check could not carry the two properties the tool does ask for.
    """
    reads = [call.request for call in mock.calls if call.request.method == "PROPFIND"]
    assert reads, "this check needs at least one PROPFIND to prove anything"
    for request in reads:
        assert b"permissions" not in request.content
        assert b"fileid" in request.content
        assert b"resourcetype" in request.content


def branch_error(status: int, path: str) -> ToolError:
    """What the MKCOL client says about ``status``, the one source of those sentences."""
    with pytest.raises(ToolError) as caught:
        dav._check_mkcol(httpx.Response(status), path)
    return caught.value


def triple(error: ToolError) -> tuple[str, str, str]:
    return (error.message, error.hint, error.reason)


def chain_reads(mock: respx.MockRouter) -> None:
    """Three missing folders below the existing folder /A."""
    for path in CHAIN:
        propfind(mock, path, httpx.Response(404))
    propfind(mock, "/A", node("100"))


# --- Without parents ----------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_free_path_costs_one_mkcol_and_answers_path_created_id(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(201, headers={"oc-fileid": OC_FILEID}))
        result = await files_tools.create_folder(clients, path=TARGET)
        requests = requests_of(mock)

    assert requests == [("MKCOL", TARGET)], "D-31-05: no read before the write"
    assert result == {"path": TARGET, "created": True, "id": "file:23274"}
    assert "created_folders" not in result


@pytest.mark.anyio
async def test_an_existing_folder_is_a_success_with_the_id_of_the_one_read(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(405))
        propfind(mock, TARGET, node("120"))
        result = await files_tools.create_folder(clients, path=TARGET)
        requests = requests_of(mock)
        assert_lean_reads(mock)

    assert requests == [("MKCOL", TARGET), ("PROPFIND", TARGET)], "D-31-04: one read, no second"
    assert result == {"path": TARGET, "created": False, "id": "file:120"}


@pytest.mark.anyio
async def test_a_file_at_the_path_is_a_conflict(clients: NcClients) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(405))
        propfind(mock, TARGET, node("121", folder=False))
        with pytest.raises(ConflictError) as caught:
            await files_tools.create_folder(clients, path=TARGET)
        requests = requests_of(mock)

    assert caught.value.message == f"A file, not a folder, already exists at {TARGET}."
    assert caught.value.hint == "Choose another name; this tool never replaces a file."
    assert requests == [("MKCOL", TARGET), ("PROPFIND", TARGET)], "no request after the conflict"


@pytest.mark.anyio
async def test_a_node_that_vanished_after_the_405_is_a_concurrent_change(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(405))
        propfind(mock, TARGET, httpx.Response(404))
        with pytest.raises(ConflictError) as caught:
            await files_tools.create_folder(clients, path=TARGET)

    assert caught.value.message == f"{TARGET} changed concurrently while the folder was created."
    assert caught.value.hint == "List the parent folder and try again."


@pytest.mark.anyio
async def test_a_missing_parent_is_the_shared_parent_missing_error(clients: NcClients) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(409))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=TARGET)
        requests = requests_of(mock)

    assert triple(caught.value) == triple(dav.parent_missing(TARGET))
    assert requests == [("MKCOL", TARGET)]


@pytest.mark.anyio
async def test_a_refused_right_is_the_branch_sentence_byte_for_byte(clients: NcClients) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(403))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=TARGET)

    assert triple(caught.value) == triple(branch_error(403, TARGET))
    assert caught.value.reason == REASON_PERMISSION_DENIED
    assert "Already created" not in caught.value.message


@pytest.mark.anyio
async def test_a_created_folder_without_the_header_gets_its_id_from_one_lean_read(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(201))
        propfind(mock, TARGET, node("130"))
        result = await files_tools.create_folder(clients, path=TARGET)
        requests = requests_of(mock)
        assert_lean_reads(mock)

    assert requests == [("MKCOL", TARGET), ("PROPFIND", TARGET)]
    assert result == {"path": TARGET, "created": True, "id": "file:130"}


@pytest.mark.anyio
@pytest.mark.parametrize("status", [500, 404])
async def test_a_failed_id_read_after_the_write_leaves_the_id_out(
    clients: NcClients, status: int
) -> None:
    """Once Nextcloud accepted the write, no follow-up read turns the answer into an error."""
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(201))
        propfind(mock, TARGET, httpx.Response(status))
        result = await files_tools.create_folder(clients, path=TARGET)

    assert result == {"path": TARGET, "created": True}


@pytest.mark.anyio
async def test_an_id_read_that_cannot_connect_leaves_the_id_out(clients: NcClients) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(201))
        mock.route(method="PROPFIND", url=url(TARGET)).mock(side_effect=httpx.ConnectError)
        result = await files_tools.create_folder(clients, path=TARGET)

    assert result == {"path": TARGET, "created": True}


# --- With parents: count from below, create from above -------------------------------------


@pytest.mark.anyio
async def test_the_chain_counts_from_below_and_creates_from_above(clients: NcClients) -> None:
    with _mock() as mock:
        chain_reads(mock)
        for number, path in enumerate(CHAIN, start=201):
            mkcol(mock, path, made(number))
        result = await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)
        requests = requests_of(mock)
        assert_lean_reads(mock)

    assert requests == [
        ("PROPFIND", "/A/b/c/d"),
        ("PROPFIND", "/A/b/c"),
        ("PROPFIND", "/A/b"),
        ("PROPFIND", "/A"),
        ("MKCOL", "/A/b"),
        ("MKCOL", "/A/b/c"),
        ("MKCOL", "/A/b/c/d"),
    ], "D-31-01: every read of the count precedes the first MKCOL"
    assert result == {
        "path": CHAIN_TARGET,
        "created": True,
        "id": "file:203",
        "created_folders": CHAIN,
    }


@pytest.mark.anyio
async def test_a_chain_below_the_home_root_never_reads_the_root(clients: NcClients) -> None:
    with _mock() as mock:
        propfind(mock, "/neu/unten", httpx.Response(404))
        propfind(mock, "/neu", httpx.Response(404))
        mkcol(mock, "/neu", made(301))
        mkcol(mock, "/neu/unten", made(302))
        result = await files_tools.create_folder(clients, path="/neu/unten", parents=True)
        requests = requests_of(mock)

    assert requests == [
        ("PROPFIND", "/neu/unten"),
        ("PROPFIND", "/neu"),
        ("MKCOL", "/neu"),
        ("MKCOL", "/neu/unten"),
    ]
    assert result["created_folders"] == ["/neu", "/neu/unten"]


@pytest.mark.anyio
async def test_an_existing_target_costs_one_read_and_no_write(clients: NcClients) -> None:
    with _mock() as mock:
        propfind(mock, CHAIN_TARGET, node("140"))
        write = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        result = await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)
        requests = requests_of(mock)
        assert_lean_reads(mock)

    assert requests == [("PROPFIND", CHAIN_TARGET)]
    assert write.call_count == 0
    assert result == {
        "path": CHAIN_TARGET,
        "created": False,
        "id": "file:140",
        "created_folders": [],
    }


@pytest.mark.anyio
async def test_a_file_as_ancestor_is_a_conflict_without_a_write(clients: NcClients) -> None:
    with _mock() as mock:
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b/c", httpx.Response(404))
        propfind(mock, "/A/b", node("150", folder=False))
        write = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        with pytest.raises(ConflictError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == "A file, not a folder, already exists at /A/b."
    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_file_as_target_is_a_conflict_without_a_write(clients: NcClients) -> None:
    with _mock() as mock:
        propfind(mock, CHAIN_TARGET, node("151", folder=False))
        write = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        with pytest.raises(ConflictError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == f"A file, not a folder, already exists at {CHAIN_TARGET}."
    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_blocked_name_during_the_count_is_reported_for_the_target(
    clients: NcClients,
) -> None:
    """Measured live on 35.0.0 (plan 31-05): the read of ``.htaccess`` answers 500."""
    blocked = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">\n'
        "  <s:exception>OCP\\Files\\ForbiddenException</s:exception>\n"
        "  <s:message>Invalid path: files/A/b/c</s:message>\n"
        "</d:error>\n"
    )
    with _mock() as mock:
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b/c", httpx.Response(500, content=blocked.encode()))
        write = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert triple(caught.value) == triple(dav.name_rejected(CHAIN_TARGET))
    assert "server error" not in caught.value.message
    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_refused_name_during_the_count_is_reported_for_the_target(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b/c", httpx.Response(400))
        write = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert triple(caught.value) == triple(dav.name_rejected(CHAIN_TARGET))
    assert "unexpected status" not in caught.value.message
    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_409_during_the_count_is_a_missing_node_and_the_count_goes_on(
    clients: NcClients,
) -> None:
    """A node below a file answers 409 (assumption A5); the file above it is then found."""
    with _mock() as mock:
        propfind(mock, "/A/f.txt/x/y", httpx.Response(409))
        propfind(mock, "/A/f.txt/x", httpx.Response(409))
        propfind(mock, "/A/f.txt", node("160", folder=False))
        write = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        with pytest.raises(ConflictError) as caught:
            await files_tools.create_folder(clients, path="/A/f.txt/x/y", parents=True)
        requests = requests_of(mock)

    assert [path for _, path in requests] == ["/A/f.txt/x/y", "/A/f.txt/x", "/A/f.txt"]
    assert caught.value.message == "A file, not a folder, already exists at /A/f.txt."
    assert "unexpected status" not in caught.value.message
    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_409_during_the_count_below_a_folder_still_ends_in_a_chain(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        propfind(mock, "/A/b/c", httpx.Response(409))
        propfind(mock, "/A/b", httpx.Response(404))
        propfind(mock, "/A", node("100"))
        mkcol(mock, "/A/b", made(401))
        mkcol(mock, "/A/b/c", made(402))
        result = await files_tools.create_folder(clients, path="/A/b/c", parents=True)

    assert result["created_folders"] == ["/A/b", "/A/b/c"]
    assert result["id"] == "file:402"


def deep_path(depth: int) -> str:
    return "".join(f"/s{number}" for number in range(1, depth + 1))


@pytest.mark.anyio
async def test_ten_missing_folders_are_created(clients: NcClients) -> None:
    target = deep_path(10)
    with _mock() as mock:
        mock.route(method="PROPFIND").mock(return_value=httpx.Response(404))
        mkcol_route = mock.route(method="MKCOL").mock(return_value=made(500))
        result = await files_tools.create_folder(clients, path=target, parents=True)

    assert mkcol_route.call_count == 10
    assert result["created"] is True
    assert len(result["created_folders"]) == 10
    assert result["created_folders"][0] == "/s1"
    assert result["created_folders"][-1] == target


@pytest.mark.anyio
async def test_eleven_missing_folders_are_refused_before_any_write(clients: NcClients) -> None:
    target = deep_path(11)
    with _mock() as mock:
        reads = mock.route(method="PROPFIND").mock(return_value=httpx.Response(404))
        mkcol_route = mock.route(method="MKCOL").mock(return_value=made(500))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=target, parents=True)

    assert mkcol_route.call_count == 0, "D-31-01: the cap alone leaves nothing behind"
    assert reads.call_count == 11, "the count runs to the end, so the number is exact"
    assert caught.value.message == (
        f"Creating {target} needs 11 new folders; one call creates at most 10."
    )
    assert "11" in caught.value.message
    assert "at most 10" in caught.value.message
    assert caught.value.hint == (
        "Create the upper part of the path first, then call again with the rest."
    )


# --- Partial abort (D-31-02) ----------------------------------------------------------------


@pytest.mark.anyio
async def test_a_refused_right_in_the_chain_names_what_was_created(clients: NcClients) -> None:
    with _mock() as mock:
        chain_reads(mock)
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", httpx.Response(403))
        third = mkcol(mock, "/A/b/c/d", made(203))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    message = caught.value.message
    assert message.startswith("No permission to create a folder at /A/b/c.")
    assert message.endswith("Already created in this call and left in place: /A/b.")
    assert message == f"No permission to create a folder at /A/b/c.{SUFFIX_AFTER_ONE}"
    assert caught.value.reason == REASON_PERMISSION_DENIED
    assert third.call_count == 0, "no write after the failure"


@pytest.mark.anyio
@pytest.mark.parametrize("status", [507, 423, 400, 500])
async def test_every_other_failure_in_the_chain_keeps_its_sentence_plus_the_list(
    clients: NcClients, status: int
) -> None:
    branch = branch_error(status, "/A/b/c")
    with _mock() as mock:
        chain_reads(mock)
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", httpx.Response(status))
        third = mkcol(mock, "/A/b/c/d", made(203))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == f"{branch.message}{SUFFIX_AFTER_ONE}"
    assert caught.value.hint == branch.hint
    assert caught.value.reason == branch.reason
    assert third.call_count == 0


@pytest.mark.anyio
async def test_a_vanished_parent_in_the_chain_names_the_target_not_the_segment(
    clients: NcClients,
) -> None:
    expected = dav.parent_missing(CHAIN_TARGET)
    with _mock() as mock:
        chain_reads(mock)
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", httpx.Response(409))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == f"{expected.message}{SUFFIX_AFTER_ONE}"
    assert caught.value.hint == expected.hint
    assert caught.value.reason == expected.reason


@pytest.mark.anyio
async def test_a_failure_at_the_first_segment_is_the_branch_byte_for_byte(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        chain_reads(mock)
        mkcol(mock, "/A/b", httpx.Response(403))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert triple(caught.value) == triple(branch_error(403, "/A/b"))


@pytest.mark.anyio
async def test_a_folder_that_appeared_meanwhile_is_passed_and_not_listed(
    clients: NcClients,
) -> None:
    """Race: after the count answered 404, another writer created /A/b/c first."""
    with _mock() as mock:
        mock.route(method="PROPFIND", url=url("/A/b/c")).mock(
            side_effect=[httpx.Response(404), node("170")]
        )
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b", httpx.Response(404))
        propfind(mock, "/A", node("100"))
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", httpx.Response(405))
        mkcol(mock, "/A/b/c/d", made(203))
        result = await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert result == {
        "path": CHAIN_TARGET,
        "created": True,
        "id": "file:203",
        "created_folders": ["/A/b", "/A/b/c/d"],
    }


@pytest.mark.anyio
async def test_a_file_that_appeared_meanwhile_is_a_conflict_with_the_list(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        mock.route(method="PROPFIND", url=url("/A/b/c")).mock(
            side_effect=[httpx.Response(404), node("171", folder=False)]
        )
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b", httpx.Response(404))
        propfind(mock, "/A", node("100"))
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", httpx.Response(405))
        third = mkcol(mock, "/A/b/c/d", made(203))
        with pytest.raises(ConflictError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == (
        f"A file, not a folder, already exists at /A/b/c.{SUFFIX_AFTER_ONE}"
    )
    assert third.call_count == 0


# --- Network failure inside the chain (D-31-02, owner decision of 2026-11-12) ---------------


def raising(
    mock: respx.MockRouter, method: str, path: str, failure: type[Exception]
) -> respx.Route:
    return mock.route(method=method, url=url(path)).mock(side_effect=failure)


@pytest.mark.anyio
async def test_a_timeout_at_the_second_mkcol_parts_created_from_unknown(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        chain_reads(mock)
        mkcol(mock, "/A/b", made(201))
        raising(mock, "MKCOL", "/A/b/c", httpx.ReadTimeout)
        third = mkcol(mock, "/A/b/c/d", made(203))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == (
        "Nextcloud did not respond in time while creating /A/b/c; whether that folder "
        f"exists now is unknown.{SUFFIX_AFTER_ONE}"
    )
    assert caught.value.hint == CHAIN_RETRY_HINT
    assert caught.value.reason == REASON_TIMEOUT
    assert type(caught.value) is ToolError
    assert third.call_count == 0, "no write after the failure"


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [httpx.ReadError, httpx.RemoteProtocolError])
async def test_a_broken_connection_at_the_third_mkcol_lists_both_created_folders(
    clients: NcClients, failure: type[Exception]
) -> None:
    with _mock() as mock:
        chain_reads(mock)
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", made(202))
        raising(mock, "MKCOL", "/A/b/c/d", failure)
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == (
        "Could not reach Nextcloud while creating /A/b/c/d; whether that folder exists "
        "now is unknown. Already created in this call and left in place: /A/b, /A/b/c."
    )
    assert caught.value.hint == CHAIN_RETRY_HINT
    assert caught.value.reason == REASON_UNREACHABLE


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failure", "opening", "reason"),
    [
        (httpx.ReadTimeout, "Nextcloud did not respond in time", REASON_TIMEOUT),
        (httpx.ConnectTimeout, "Nextcloud did not respond in time", REASON_TIMEOUT),
        (httpx.ConnectError, "Could not reach Nextcloud", REASON_UNREACHABLE),
    ],
)
async def test_a_cut_at_the_first_mkcol_names_it_unknown_and_nothing_created(
    clients: NcClients, failure: type[Exception], opening: str, reason: str
) -> None:
    with _mock() as mock:
        chain_reads(mock)
        raising(mock, "MKCOL", "/A/b", failure)
        second = mkcol(mock, "/A/b/c", made(202))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == (
        f"{opening} while creating /A/b; whether that folder exists now is unknown. "
        "No other folder was created in this call."
    )
    assert "Already created" not in caught.value.message
    assert caught.value.hint == CHAIN_RETRY_HINT
    assert caught.value.reason == reason
    assert second.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failure", "opening", "reason"),
    [
        (httpx.ReadTimeout, "Nextcloud did not respond in time", REASON_TIMEOUT),
        (httpx.ReadError, "Could not reach Nextcloud", REASON_UNREACHABLE),
    ],
)
async def test_a_cut_at_the_only_mkcol_without_parents_names_the_target_unknown(
    clients: NcClients, failure: type[Exception], opening: str, reason: str
) -> None:
    with _mock() as mock:
        raising(mock, "MKCOL", TARGET, failure)
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=TARGET)
        requests = requests_of(mock)

    assert caught.value.message == (
        f"{opening} while creating {TARGET}; whether that folder exists now is unknown. "
        "No other folder was created in this call."
    )
    assert caught.value.hint == SINGLE_RETRY_HINT
    assert "parents" not in caught.value.hint
    assert caught.value.reason == reason
    assert requests == [("MKCOL", TARGET)], "no read follows the cut"


@pytest.mark.anyio
async def test_a_cut_read_between_two_segments_names_the_list_and_nothing_unknown(
    clients: NcClients,
) -> None:
    """No MKCOL was under way: /A/b/c answered 405, the read behind it never came back."""
    with _mock() as mock:
        mock.route(method="PROPFIND", url=url("/A/b/c")).mock(
            side_effect=[httpx.Response(404), httpx.ConnectError("down")]
        )
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b", httpx.Response(404))
        propfind(mock, "/A", node("100"))
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", httpx.Response(405))
        third = mkcol(mock, "/A/b/c/d", made(203))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == f"Could not reach Nextcloud.{SUFFIX_AFTER_ONE}"
    assert "unknown" not in caught.value.message
    assert caught.value.hint == CHAIN_RETRY_HINT
    assert caught.value.reason == REASON_UNREACHABLE
    assert third.call_count == 0


@pytest.mark.anyio
async def test_a_timed_out_read_between_two_segments_keeps_the_timeout_class(
    clients: NcClients,
) -> None:
    with _mock() as mock:
        mock.route(method="PROPFIND", url=url("/A/b/c")).mock(
            side_effect=[httpx.Response(404), httpx.ReadTimeout("slow")]
        )
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b", httpx.Response(404))
        propfind(mock, "/A", node("100"))
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", httpx.Response(405))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert caught.value.message == f"Nextcloud did not respond in time.{SUFFIX_AFTER_ONE}"
    assert caught.value.reason == REASON_TIMEOUT


@pytest.mark.anyio
async def test_a_cut_read_behind_the_first_segment_stays_the_plain_network_error(
    clients: NcClients,
) -> None:
    """Nothing created and no MKCOL under way: as before, the caller sees the httpx error."""
    with _mock() as mock:
        mock.route(method="PROPFIND", url=url("/A/b")).mock(
            side_effect=[httpx.Response(404), httpx.ConnectError("down")]
        )
        propfind(mock, "/A/b/c/d", httpx.Response(404))
        propfind(mock, "/A/b/c", httpx.Response(404))
        propfind(mock, "/A", node("100"))
        mkcol(mock, "/A/b", httpx.Response(405))
        second = mkcol(mock, "/A/b/c", made(202))
        with pytest.raises(httpx.ConnectError):
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert second.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [httpx.ReadTimeout, httpx.ConnectError])
@pytest.mark.parametrize("broken", [*CHAIN, "/A"])
async def test_a_network_failure_during_the_count_is_unchanged_and_writes_nothing(
    clients: NcClients, failure: type[Exception], broken: str
) -> None:
    with _mock() as mock:
        for path in CHAIN:
            if path != broken:
                propfind(mock, path, httpx.Response(404))
        if broken != "/A":
            propfind(mock, "/A", node("100"))
        raising(mock, "PROPFIND", broken, failure)
        write = mock.route(method="MKCOL").mock(return_value=made(201))
        with pytest.raises(failure):
            await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_network_failure_reading_the_sandbox_root_is_unchanged(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Sandbox")
    with _mock() as mock:
        propfind(mock, "/Sandbox/x", httpx.Response(404))
        raising(mock, "PROPFIND", "/Sandbox", httpx.ReadTimeout)
        write = mock.route(method="MKCOL").mock(return_value=made(201))
        with pytest.raises(httpx.ReadTimeout):
            await files_tools.create_folder(clients, path="/x", parents=True)

    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_cut_read_behind_a_405_without_parents_is_unchanged(clients: NcClients) -> None:
    with _mock() as mock:
        mkcol(mock, TARGET, httpx.Response(405))
        raising(mock, "PROPFIND", TARGET, httpx.ReadTimeout)
        with pytest.raises(httpx.ReadTimeout):
            await files_tools.create_folder(clients, path=TARGET)


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [httpx.ReadTimeout, httpx.ConnectError])
async def test_a_cut_id_read_after_the_last_mkcol_of_a_chain_stays_a_success(
    clients: NcClients, failure: type[Exception]
) -> None:
    """31-02: once the write was accepted, no follow-up read turns the answer into an error."""
    with _mock() as mock:
        mock.route(method="PROPFIND", url=url("/A/b/c/d")).mock(
            side_effect=[httpx.Response(404), failure("gone")]
        )
        propfind(mock, "/A/b/c", httpx.Response(404))
        propfind(mock, "/A/b", httpx.Response(404))
        propfind(mock, "/A", node("100"))
        mkcol(mock, "/A/b", made(201))
        mkcol(mock, "/A/b/c", made(202))
        mkcol(mock, "/A/b/c/d", httpx.Response(201))
        result = await files_tools.create_folder(clients, path=CHAIN_TARGET, parents=True)

    assert result == {"path": CHAIN_TARGET, "created": True, "created_folders": CHAIN}


def test_the_network_sentences_open_like_the_ones_of_the_server_wrapper() -> None:
    """The two openings are the sentences ``graceful`` gives a bare httpx error."""
    wrapper = inspect.getsource(server.graceful)
    assert "Nextcloud did not respond in time." in wrapper
    assert "Could not reach Nextcloud." in wrapper


# --- Path guard and sandbox (FOLD-04) -------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("parents", [False, True])
async def test_the_home_root_is_refused_without_a_request(
    clients: NcClients, parents: bool
) -> None:
    with _mock() as mock:
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path="/", parents=parents)
        assert mock.calls.call_count == 0

    assert caught.value.message == "The folder path is the root folder, which always exists."
    assert caught.value.hint == "Name a folder below the root, for example /Projects/2026."


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/", "/Sandbox"])
async def test_the_sandbox_root_is_refused_without_a_request(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Sandbox")
    with _mock() as mock:
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=path, parents=True)
        assert mock.calls.call_count == 0

    assert caught.value.message == "The folder path is the root folder, which always exists."


@pytest.mark.anyio
async def test_a_missing_sandbox_root_is_a_missing_parent_and_is_never_created(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Sandbox")
    with _mock() as mock:
        propfind(mock, "/Sandbox/x", httpx.Response(404))
        propfind(mock, "/Sandbox", httpx.Response(404))
        write = mock.route(method="MKCOL").mock(return_value=httpx.Response(201))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path="/x", parents=True)
        requests = requests_of(mock)
        assert_lean_reads(mock)

    assert triple(caught.value) == triple(dav.parent_missing("/Sandbox/x"))
    assert requests == [("PROPFIND", "/Sandbox/x"), ("PROPFIND", "/Sandbox")]
    assert write.call_count == 0


@pytest.mark.anyio
async def test_a_chain_in_the_sandbox_stays_below_the_root(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Sandbox")
    with _mock() as mock:
        propfind(mock, "/Sandbox/x/y", httpx.Response(404))
        propfind(mock, "/Sandbox/x", httpx.Response(404))
        propfind(mock, "/Sandbox", node("180"))
        mock.route(method="MKCOL").mock(return_value=made(181))
        result = await files_tools.create_folder(clients, path="/x/y", parents=True)
        requests = requests_of(mock)
        assert_lean_reads(mock)

    written = [path for method, path in requests if method == "MKCOL"]
    assert written == ["/Sandbox/x", "/Sandbox/x/y"]
    assert all(path.startswith("/Sandbox/") for path in written)
    assert "/Sandbox" not in written, "the root is read, never created"
    assert result == {
        "path": "/Sandbox/x/y",
        "created": True,
        "id": "file:181",
        "created_folders": ["/Sandbox/x", "/Sandbox/x/y"],
    }


@pytest.mark.anyio
async def test_a_single_folder_in_the_sandbox_is_written_below_the_root(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Sandbox")
    with _mock() as mock:
        mkcol(mock, "/Sandbox/x", made(182))
        result = await files_tools.create_folder(clients, path="/x")
        requests = requests_of(mock)

    assert requests == [("MKCOL", "/Sandbox/x")]
    assert result == {"path": "/Sandbox/x", "created": True, "id": "file:182"}


@pytest.mark.anyio
@pytest.mark.parametrize("parents", [False, True])
async def test_a_traversal_path_is_refused_without_a_request(
    clients: NcClients, parents: bool
) -> None:
    with _mock() as mock:
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path="/A/../../etc", parents=parents)
        assert mock.calls.call_count == 0

    assert "points outside the user's files" in caught.value.message


# --- Whitespace at the edge of a folder name (D-31-08, owner decision of 2026-11-12) --------

PADDED_HINT = (
    "Remove the whitespace at the start and the end of every folder name and call again; "
    "nothing was created."
)


def padded(path: str, segment: str) -> tuple[str, str, str]:
    """The refusal of a padded folder name, spelled out here and not taken from the code."""
    return (
        f"The folder name {segment!r} in {path!r} starts or ends with whitespace.",
        PADDED_HINT,
        "unspecified",
    )


#: Everything ``str.strip`` removes at an edge, which is what ``dav.safe_path`` trims at the
#: end of a path: the space, the tab, the line break, the no-break space, the wide space.
EDGES = [" ", "\t", "\n", "\r\n", "\u00a0", "\u3000", "  "]


@pytest.mark.anyio
@pytest.mark.parametrize("parents", [False, True])
@pytest.mark.parametrize("edge", EDGES)
async def test_a_target_name_ending_in_whitespace_is_refused_without_a_request(
    clients: NcClients, edge: str, parents: bool
) -> None:
    """Live finding 2 of plan 31-05: trimmed, the folder would get another name than asked."""
    path = f"/A/ende-leer{edge}"
    with _mock() as mock:
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=path, parents=parents)
        assert mock.calls.call_count == 0

    assert not isinstance(caught.value, ConflictError)
    assert triple(caught.value) == padded(path, f"ende-leer{edge}")


@pytest.mark.anyio
@pytest.mark.parametrize("parents", [False, True])
@pytest.mark.parametrize(
    ("path", "segment"),
    [
        ("/A/ anfang-leer", " anfang-leer"),
        ("/A/mitte-leer /kind", "mitte-leer "),
        ("/A/\u00a0mitte/kind", "\u00a0mitte"),
        ("/ oben/b/c", " oben"),
        ("/A/ /b", " "),
        (" /A/b", " "),
        ("A/b ", "b "),
        ("/A/b /", "b "),
        ("/A/b/ ", " "),
        ("/A/. /b", ". "),
    ],
)
async def test_every_padded_segment_is_refused_without_a_request(
    clients: NcClients, path: str, segment: str, parents: bool
) -> None:
    """Each segment counts, with and without ``parents``; the first padded one is named."""
    with _mock() as mock:
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=path, parents=parents)
        assert mock.calls.call_count == 0

    assert triple(caught.value) == padded(path, segment)


@pytest.mark.anyio
async def test_the_chain_of_the_live_finding_creates_nothing(clients: NcClients) -> None:
    """The very call of the line ``ZUSATZ`` of plan 31-05: no MKCOL for ``mitte-leer``."""
    path = "/zusatz/mitte-leer /kind"
    with _mock() as mock:
        write = mock.route(method="MKCOL").mock(return_value=made(1))
        read = mock.route(method="PROPFIND").mock(return_value=httpx.Response(404))
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=path, parents=True)

    assert write.call_count == 0
    assert read.call_count == 0
    assert "Already created" not in caught.value.message
    assert triple(caught.value) == padded(path, "mitte-leer ")


@pytest.mark.anyio
@pytest.mark.parametrize("parents", [False, True])
async def test_a_padded_name_in_the_sandbox_is_refused_without_a_request(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch, parents: bool
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Sandbox")
    with _mock() as mock:
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path="/x /y", parents=parents)
        assert mock.calls.call_count == 0

    assert triple(caught.value) == padded("/x /y", "x ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "fragment"),
    [
        ("   ", "No path was given."),
        ("/ ", "The folder path is the root folder, which always exists."),
        (" / ", "The folder path is the root folder, which always exists."),
        ("/A /../../etc", "points outside the user's files"),
        ("/A \\b", "contains a backslash"),
        ("/A\t/b ", "contains a control character"),
    ],
)
async def test_the_older_refusals_keep_their_sentence(
    clients: NcClients, path: str, fragment: str
) -> None:
    """The name check comes after the path checks that were there before, not instead."""
    with _mock() as mock:
        with pytest.raises(ToolError) as caught:
            await files_tools.create_folder(clients, path=path, parents=True)
        assert mock.calls.call_count == 0

    assert fragment in caught.value.message
    assert "whitespace" not in caught.value.message


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "sent"),
    [
        ("/A/mit leer", "/A/mit leer"),
        ("/A/ende-punkt.", "/A/ende-punkt."),
        ("/A/b/", "/A/b"),
        ("//A//b", "/A/b"),
        ("/A/./b", "/A/b"),
    ],
)
async def test_names_the_path_guard_does_not_change_are_still_created(
    clients: NcClients, path: str, sent: str
) -> None:
    """Positive control: only a name that would be trimmed is refused, nothing else.

    A space inside a name and a dot at its end reach Nextcloud as they were asked for, so
    there is nothing to refuse; no rule beyond the trimming was invented.
    """
    with _mock() as mock:
        mkcol(mock, sent, made(190))
        result = await files_tools.create_folder(clients, path=path)
        requests = requests_of(mock)

    assert requests == [("MKCOL", sent)]
    assert result == {"path": sent, "created": True, "id": "file:190"}


def test_the_path_guard_of_the_other_tools_still_trims() -> None:
    """``safe_path`` serves every file tool and is not part of this decision."""
    assert dav.safe_path("/A/b ") == "/A/b"
    assert dav.safe_path(" /A/b\t") == "/A/b"
    assert dav.safe_path("/A/mitte-leer /kind") == "/A/mitte-leer /kind"

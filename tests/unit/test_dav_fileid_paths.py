"""The two error factories of dav.py and the batch lookup of file ids (paths_of_fileids).

The factories are the one source of the "not found" and "parent missing" sentences: the
exclusion paths of phase 27 answer with the very same objects, which is what the paired
tests of phase 28 compare byte for byte. The batch lookup turns the ids of search hits
into home paths inside NC_MCP_FILES_ROOT with one SEARCH per block of ids.
"""

import httpx
import pytest
import respx
from lxml import etree

from mcp_connector import config
from mcp_connector.errors import REASON_UNKNOWN_ID, ToolError
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
SEARCH_URL = f"{BASE}/remote.php/dav/"
XML_HEADERS = {"Content-Type": "application/xml; charset=utf-8"}

NOT_FOUND_HINT = "List the parent folder first to get the exact spelling of the path."
PARENT_HINT = (
    "Create the missing folder first, in Nextcloud or with files_create_folder where that "
    "tool is offered (parents=true creates the whole chain), and check that no file stands "
    "in the path."
)


@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, USER, SECRET)


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


def triple(error: ToolError) -> tuple[str, str, str]:
    return (error.message, error.hint, error.reason)


def multistatus(*entries: tuple[str, str]) -> bytes:
    """A 207 SEARCH answer; each entry is (href suffix below the home, fileid)."""
    responses = "".join(
        f"<d:response><d:href>/remote.php/dav/files/{USER}/{suffix}</d:href><d:propstat>"
        f"<d:prop><oc:fileid>{fileid}</oc:fileid><d:resourcetype/></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for suffix, fileid in entries
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">{responses}</d:multistatus>'
    ).encode()


def listed(body: bytes) -> httpx.Response:
    return httpx.Response(207, content=body, headers=XML_HEADERS)


def literals(body: bytes) -> list[str]:
    root = etree.fromstring(body, parser=davxml.hardened_parser())
    return [str(element.text) for element in root.iter(f"{{{davxml.DAV}}}literal")]


def nresults(body: bytes) -> str:
    root = etree.fromstring(body, parser=davxml.hardened_parser())
    element = root.find(f".//{{{davxml.DAV}}}nresults")
    assert element is not None
    return str(element.text)


def has_or(body: bytes) -> bool:
    root = etree.fromstring(body, parser=davxml.hardened_parser())
    return root.find(f".//{{{davxml.DAV}}}or") is not None


# --- the error factories -------------------------------------------------------------------


def test_not_found_builds_the_sentence_of_a_404() -> None:
    assert triple(dav.not_found("/A/x.md")) == (
        "File not found: /A/x.md.",
        NOT_FOUND_HINT,
        REASON_UNKNOWN_ID,
    )


def test_parent_missing_names_the_parent_folder() -> None:
    assert triple(dav.parent_missing("/A/b.txt")) == (
        "The parent folder /A of /A/b.txt does not exist.",
        PARENT_HINT,
        REASON_UNKNOWN_ID,
    )
    assert dav.parent_missing("b.txt").message == "The parent folder / of b.txt does not exist."


def test_a_404_raises_exactly_the_not_found_object() -> None:
    with pytest.raises(ToolError) as excinfo:
        dav._check(httpx.Response(404), "/A/x.md")

    assert triple(excinfo.value) == triple(dav.not_found("/A/x.md"))


@pytest.mark.parametrize("status", [404, 409])
def test_a_missing_parent_on_write_raises_exactly_the_parent_missing_object(status: int) -> None:
    with pytest.raises(ToolError) as excinfo:
        dav._check_write(httpx.Response(status), "/A/b.txt")

    assert triple(excinfo.value) == triple(dav.parent_missing("/A/b.txt"))


@pytest.mark.parametrize("status", [404, 409])
def test_a_missing_parent_on_a_chunk_raises_exactly_the_parent_missing_object(
    status: int,
) -> None:
    with pytest.raises(ToolError) as excinfo:
        dav._check_chunk_response(httpx.Response(status), "/A/b.txt")

    assert triple(excinfo.value) == triple(dav.parent_missing("/A/b.txt"))


# --- the batch body ------------------------------------------------------------------------


def test_one_id_builds_the_single_id_body() -> None:
    assert dav.build_fileids_body("/files/alice", ["12"]) == dav.build_fileid_body(
        "/files/alice", "12"
    )
    assert not has_or(dav.build_fileids_body("/files/alice", ["12"]))


def test_several_ids_become_one_or_of_equals() -> None:
    body = dav.build_fileids_body("/files/alice", ["12", "7"])

    root = etree.fromstring(body, parser=davxml.hardened_parser())
    either = root.find(f".//{{{davxml.DAV}}}where/{{{davxml.DAV}}}or")
    assert either is not None
    equals = either.findall(f"{{{davxml.DAV}}}eq")
    assert len(equals) == 2
    assert all(eq.find(f"{{{davxml.DAV}}}prop/{{{davxml.OC}}}fileid") is not None for eq in equals)
    assert literals(body) == ["12", "7"]
    assert nresults(body) == "2"


# --- paths_of_fileids ----------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_ids_cost_no_request(client: httpx.AsyncClient, creds: Credentials) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        search = mock.route(method="SEARCH", url=SEARCH_URL)

        assert await dav.paths_of_fileids(client, creds, []) == {}

    assert search.call_count == 0


@pytest.mark.anyio
async def test_duplicates_are_asked_once_in_one_search(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=listed(multistatus(("A/x.md", "12"), ("B/y.md", "7")))
        )

        found = await dav.paths_of_fileids(client, creds, ["12", "12", "7"])

    assert found == {"12": "/A/x.md", "7": "/B/y.md"}
    assert search.call_count == 1
    body = search.calls[0].request.content
    assert has_or(body)
    assert literals(body) == ["12", "7"]
    assert nresults(body) == "2"


@pytest.mark.anyio
async def test_a_single_id_asks_without_an_or(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=listed(multistatus(("A/x.md", "12")))
        )

        found = await dav.paths_of_fileids(client, creds, ["12"])

    assert found == {"12": "/A/x.md"}
    body = search.calls[0].request.content
    assert body == dav.build_fileid_body(dav.search_scope(creds), "12")
    assert search.calls[0].request.headers["Content-Type"] == "text/xml"


@pytest.mark.anyio
async def test_a_hundred_and_twenty_ids_cost_three_searches(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    ids = [str(number) for number in range(1000, 1120)]
    with respx.mock(assert_all_mocked=True) as mock:
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=listed(multistatus())
        )

        found = await dav.paths_of_fileids(client, creds, ids)

    assert found == {}
    assert search.call_count == 3
    sizes = sorted((len(literals(call.request.content)) for call in search.calls), reverse=True)
    assert sizes == [50, 50, 20]
    asked = [literal for call in search.calls for literal in literals(call.request.content)]
    assert sorted(asked) == ids


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["12a", "١٢", "", " 12", "-1"])
async def test_a_non_digit_id_raises_before_any_request(
    client: httpx.AsyncClient, creds: Credentials, bad: str
) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        search = mock.route(method="SEARCH", url=SEARCH_URL)

        with pytest.raises(ValueError, match="file id"):
            await dav.paths_of_fileids(client, creds, ["12", bad])

    assert search.call_count == 0


@pytest.mark.anyio
async def test_an_entry_outside_the_files_root_is_missing_from_the_result(
    client: httpx.AsyncClient, creds: Credentials, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Shared/KI")
    with respx.mock(assert_all_mocked=True) as mock:
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=listed(
                multistatus(("Shared/KI/inside.md", "12"), ("Private/outside.md", "7"))
            )
        )

        found = await dav.paths_of_fileids(client, creds, ["12", "7"])

    assert found == {"12": "/Shared/KI/inside.md"}
    root = etree.fromstring(search.calls[0].request.content, parser=davxml.hardened_parser())
    href = root.find(f".//{{{davxml.DAV}}}scope/{{{davxml.DAV}}}href")
    assert href is not None
    assert href.text == "/files/alice/Shared/KI"


@pytest.mark.anyio
async def test_an_id_that_was_not_asked_is_not_in_the_result(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=listed(multistatus(("A/x.md", "12"), ("A/other.md", "99")))
        )

        found = await dav.paths_of_fileids(client, creds, ["12", "7"])

    assert found == {"12": "/A/x.md"}


@pytest.mark.anyio
async def test_a_failing_search_raises(client: httpx.AsyncClient, creds: Credentials) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(return_value=httpx.Response(500))

        with pytest.raises(ToolError):
            await dav.paths_of_fileids(client, creds, ["12", "7"])

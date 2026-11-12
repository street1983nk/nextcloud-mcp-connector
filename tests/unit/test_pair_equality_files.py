"""GATE-03 on the unit level, family files: a tagged target answers like a missing one.

For every pair case of the family ``files`` in ``tool_classes.PAIR_CASES`` the tool is called
through the real registry (``Client(mcp)``) twice: once with a target tagged ``kein-ki`` and
once with a target that does not exist. What is compared is the whole ``CallToolResult``
after ``result.model_dump(mode="json", by_alias=True)``: every text part, the structured
content and ``isError``. Before the comparison ``result_shapes.normalised`` replaces the
requested id by ``<ID>``, in the definition of ``requested_forms``: "requested id = the
argument, its path prefixes and for fetch the bare id". Nothing else is replaced.

The guard requests are mocked for real through ``guard_routes`` (no ``patch_untagged``), in
five states: active, 412 once (listed anew and then active), 412 twice, timeout and 5xx. The
response time is not part of the comparison (D-28-12); ``normalised`` carries no time value,
and ``test_time_is_not_part_of_the_comparison`` pins that.

A request that no route of a side expects is caught by a last catch-all route and fails the
test, so two sides that both run into the same unmocked request cannot pass as equal.

``tests/contract`` is on the pytest path (``pyproject.toml``) but not on the one of pyright,
hence the ``reportMissingImports`` ignore on the imports from there.
"""

import base64
import time
from collections.abc import Callable, Iterator
from typing import Any

import guard_routes
import httpx
import pytest
import respx
from mcp import Client
from result_shapes import normalised
from tool_classes import NAMED_EXCEPTIONS, PAIR_CASES

from mcp_connector.nextcloud import capabilities
from mcp_connector.server import mcp
from mcp_connector.tools import files as files_tools

BASE = guard_routes.BASE
USER = guard_routes.USER
SECRET = "app-password-test"
FILES = f"{BASE}/remote.php/dav/files/{USER}"
DAV_ROOT = f"{BASE}/remote.php/dav/"
UPLOADS = f"{BASE}/remote.php/dav/uploads/{USER}/"
CONTENT = b"streng vertraulich\n"

Node = tuple[str, str, bool]
Mocks = Callable[[respx.MockRouter], None]

GUARD_MODES = ("active", "stale_once", "stale_twice", "timeout", "server_error")

TAGGED_FILE: Node = ("Docs/geheim.txt", "901", False)
TAGGED_FOLDER: Node = ("Projekt", "900", True)
TAGS = (TAGGED_FILE, TAGGED_FOLDER)

#: Every pair case of the family, compared here; pinned against ``PAIR_CASES``.
COVERED = {
    ("files_read", "path"),
    ("files_download", "path"),
    ("files_read_as_markdown", "path"),
    ("files_list", "folder"),
    ("files_search", "folder"),
    ("files_upload", "text"),
    ("files_upload", "binary_chunk1"),
    ("files_create_folder", "path"),
    ("fetch", "file"),
}
#: The cases of the family that are named exceptions (D-28-16), each with its own test.
#: None since 28-06: B5 was fixed (D-28-19) and B6 has no finding (D-28-20).
NAMED_HERE: set[tuple[str, str]] = set()


@pytest.fixture(autouse=True)
def _fresh_caches() -> None:
    guard_routes.reset()
    capabilities.clear_cache()


@pytest.fixture(autouse=True)
def stdio_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment an in-memory client call resolves its credentials from."""
    monkeypatch.setenv("NC_MCP_URL", BASE)
    monkeypatch.setenv("NC_MCP_USER", USER)
    monkeypatch.setenv("NC_MCP_APP_PASSWORD", SECRET)
    monkeypatch.delenv("NC_MCP_STATIC_BEARER", raising=False)


# --- guard states ---------------------------------------------------------------------------


def _stale_once(mock: respx.MockRouter, *nodes: Node) -> None:
    """412 on the first REPORT, then the tagged nodes: the guard lists anew and is active."""
    mock.route(method="PROPFIND", url=guard_routes.TAGS).mock(
        return_value=guard_routes.listed(
            guard_routes.tag_list(guard_routes.KEIN_KI, guard_routes.OTHER_TAG)
        )
    )
    answers = iter([httpx.Response(412)])

    def report(_request: httpx.Request) -> httpx.Response:
        return next(answers, None) or guard_routes.listed(guard_routes.report_207(*nodes))

    mock.route(method="REPORT", url=guard_routes.HOME).mock(side_effect=report)


def arm_guard(mock: respx.MockRouter, mode: str, *nodes: Node) -> None:
    """Mock the guard requests of one of the five states of ``GUARD_MODES``."""
    if mode == "active":
        guard_routes.active(mock, *nodes)
    elif mode == "stale_once":
        _stale_once(mock, *nodes)
    elif mode == "stale_twice":
        guard_routes.stale(mock)
    elif mode == "timeout":
        guard_routes.timeout(mock)
    elif mode == "server_error":
        guard_routes.unverifiable(mock)
    else:  # pragma: no cover - a typo in a parametrisation
        raise AssertionError(f"unknown guard mode {mode!r}")


@pytest.fixture
def unexpected() -> Iterator[list[str]]:
    """Requests no route of a side expected; every test asserts the list stays empty."""
    found: list[str] = []
    yield found
    assert not found, f"unmocked requests: {found}"


async def _call(
    tool: str,
    args: dict[str, Any],
    mode: str,
    mocks: Mocks,
    unexpected: list[str],
) -> Any:
    guard_routes.reset()
    capabilities.clear_cache()
    with respx.mock(assert_all_called=False) as mock:
        arm_guard(mock, mode, *TAGS)
        mocks(mock)

        def catch_all(request: httpx.Request) -> httpx.Response:
            unexpected.append(f"{request.method} {request.url}")
            return httpx.Response(599)

        mock.route().mock(side_effect=catch_all)
        async with Client(mcp) as client:
            return await client.call_tool(tool, args)


async def pair(
    tool: str,
    tagged_args: dict[str, Any],
    unknown_args: dict[str, Any],
    tagged_value: str | tuple[str, ...],
    unknown_value: str | tuple[str, ...],
    mock_tagged: Mocks,
    mock_unknown: Mocks,
    mode: str,
    unexpected: list[str],
) -> tuple[str, str]:
    """Both answers of one pair, each normalised on its own requested id.

    A value may be a tuple when the tool echoes the argument in a second spelling, as
    files_search does with its scope ``/files/<user><folder>`` (D-28-19).
    """
    tagged = await _call(tool, tagged_args, mode, mock_tagged, unexpected)
    unknown = await _call(tool, unknown_args, mode, mock_unknown, unexpected)
    return (
        normalised(tagged, *_values(tagged_value)),
        normalised(unknown, *_values(unknown_value)),
    )


def _values(value: str | tuple[str, ...]) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else value


#: The guard states in which the guard answers ``active``; the others are ``unverifiable``.
ANSWERED = ("active", "stale_once")
#: A fragment of every answer while the check cannot be answered, refusal or degraded entry.
UNANSWERED = "could not be answered"
#: Fragments of the refusals under an active guard, after the requested id became <ID>.
NOT_FOUND = "File not found: <ID>."
PARENT_MISSING = "of <ID> does not exist."
NO_FILEID = "This account has no file with the id <ID>."


def _assert_equal(tagged: str, unknown: str, mode: str, answered: str) -> None:
    """Equal, and the refusal of the expected state, not an input error on both sides.

    ``answered`` is a fragment of the answer the guard state ``active`` must give.
    """
    assert tagged == unknown, f"tagged:  {tagged}\nunknown: {unknown}"
    expected = answered if mode in ANSWERED else UNANSWERED
    assert expected in tagged, f"expected {expected!r} in {tagged}"


# --- WebDAV answers -------------------------------------------------------------------------


def _props(*, fileid: str, folder: bool = False, name: str = "") -> str:
    resourcetype = "<d:collection/>" if folder else ""
    type_prop = "" if folder else "<d:getcontenttype>text/plain</d:getcontenttype>"
    name_prop = f"<d:displayname>{name}</d:displayname>" if name else ""
    return (
        f"{name_prop}<d:getcontentlength>{len(CONTENT)}</d:getcontentlength>{type_prop}"
        f"<d:resourcetype>{resourcetype}</d:resourcetype><oc:fileid>{fileid}</oc:fileid>"
    )


def _multistatus(*entries: tuple[str, str]) -> str:
    """A 207 body; each entry is (path below the home, props)."""
    responses = "".join(
        f"<d:response><d:href>/remote.php/dav/files/{USER}{path}</d:href>"
        f"<d:propstat><d:prop>{props}</d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for path, props in entries
    )
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        f'xmlns:oc="http://owncloud.org/ns">{responses}</d:multistatus>'
    )


def _existing_file(path: str, fileid: str) -> Mocks:
    """PROPFIND and GET of a file that exists; the GET is never reached for a tagged one."""

    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PROPFIND", url=f"{FILES}{path}").mock(
            return_value=httpx.Response(207, text=_multistatus((path, _props(fileid=fileid))))
        )
        mock.route(method="GET", url=f"{FILES}{path}").mock(
            return_value=httpx.Response(200, content=CONTENT)
        )

    return mocks


def _missing(path: str) -> Mocks:
    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PROPFIND", url=f"{FILES}{path}").mock(return_value=httpx.Response(404))

    return mocks


def _existing_folder(path: str, fileid: str, *children: tuple[str, str]) -> Mocks:
    """A Depth-1 listing: the folder plus (name, fileid) file children."""
    entries = [(path, _props(fileid=fileid, folder=True))]
    entries += [(f"{path}/{name}", _props(fileid=cid, name=name)) for name, cid in children]
    body = _multistatus(*entries)

    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PROPFIND", url=f"{FILES}{path}").mock(
            return_value=httpx.Response(207, text=body)
        )

    return mocks


#: (tagged path, its fileid) for a tagged file and a file below a tagged folder.
TAGGED_READ_TARGETS = (("/Docs/geheim.txt", "901"), ("/Projekt/a.txt", "905"))
UNKNOWN_PATH = "/Docs/fehlt.txt"


# --- files_read / files_download ------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_read_answers_a_tagged_path_like_a_missing_one(
    mode: str, unexpected: list[str]
) -> None:
    for path, fileid in TAGGED_READ_TARGETS:
        tagged, unknown = await pair(
            "files_read",
            {"path": path},
            {"path": UNKNOWN_PATH},
            path,
            UNKNOWN_PATH,
            _existing_file(path, fileid),
            _missing(UNKNOWN_PATH),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown, mode, NOT_FOUND)
        assert '"isError": true' in tagged


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_read_as_markdown_answers_a_tagged_path_like_a_missing_one(
    mode: str, unexpected: list[str]
) -> None:
    # The mocked file is text/plain, which the converter refuses for an untagged path; a
    # tagged one must answer "not found" before its type is ever looked at.
    for path, fileid in TAGGED_READ_TARGETS:
        tagged, unknown = await pair(
            "files_read_as_markdown",
            {"path": path},
            {"path": UNKNOWN_PATH},
            path,
            UNKNOWN_PATH,
            _existing_file(path, fileid),
            _missing(UNKNOWN_PATH),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown, mode, NOT_FOUND)
        assert '"isError": true' in tagged
        assert "text already" not in tagged


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_download_answers_a_tagged_path_like_a_missing_one(
    mode: str, unexpected: list[str]
) -> None:
    for path, fileid in TAGGED_READ_TARGETS:
        tagged, unknown = await pair(
            "files_download",
            {"path": path},
            {"path": UNKNOWN_PATH},
            path,
            UNKNOWN_PATH,
            _existing_file(path, fileid),
            _missing(UNKNOWN_PATH),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown, mode, NOT_FOUND)
        assert '"isError": true' in tagged


# --- files_list -----------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_list_answers_a_tagged_folder_like_an_invented_one(
    mode: str, unexpected: list[str]
) -> None:
    targets = (
        ("/Projekt", _existing_folder("/Projekt", "900", ("a.txt", "905"))),
        ("/Projekt/Unter", _existing_folder("/Projekt/Unter", "906")),
    )
    for path, mocks in targets:
        tagged, unknown = await pair(
            "files_list",
            {"path": path},
            {"path": "/erfunden-1"},
            path,
            "/erfunden-1",
            mocks,
            _missing("/erfunden-1"),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown, mode, NOT_FOUND)


# --- fetch(file:) ---------------------------------------------------------------------------


def _found(fileid: str, path: str) -> httpx.Response:
    name = path.rsplit("/", 1)[-1]
    return httpx.Response(207, text=_multistatus((path, _props(fileid=fileid, name=name))))


def _nothing() -> httpx.Response:
    return httpx.Response(207, text=_multistatus())


def _fetchable(fileid: str, path: str) -> Mocks:
    """Lookup, stat and content of one file."""

    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=_found(fileid, path))
        _existing_file(path, fileid)(mock)

    return mocks


def _no_file(mock: respx.MockRouter) -> None:
    mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=_nothing())


UNKNOWN_FILEID = "999999999"


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_fetch_file_answers_a_tagged_id_like_an_unknown_one(
    mode: str, unexpected: list[str]
) -> None:
    for path, fileid in TAGGED_READ_TARGETS:
        tagged, unknown = await pair(
            "fetch",
            {"id": f"file:{fileid}"},
            {"id": f"file:{UNKNOWN_FILEID}"},
            f"file:{fileid}",
            f"file:{UNKNOWN_FILEID}",
            _fetchable(fileid, path),
            _no_file,
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown, mode, NO_FILEID)
        assert "geheim" not in tagged
        assert '"isError": true' in tagged


@pytest.mark.anyio
@pytest.mark.parametrize("status", [500, 503])
async def test_fetch_file_answers_a_failing_lookup_alike(
    status: int, unexpected: list[str]
) -> None:
    """D-28-17: a 5xx of the fileid SEARCH answers a tagged id and an invented one alike."""

    def failing(mock: respx.MockRouter) -> None:
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=httpx.Response(status))

    tagged, unknown = await pair(
        "fetch",
        {"id": "file:901"},
        {"id": f"file:{UNKNOWN_FILEID}"},
        "file:901",
        f"file:{UNKNOWN_FILEID}",
        failing,
        failing,
        "active",
        unexpected,
    )
    assert tagged == unknown, f"tagged:  {tagged}\nunknown: {unknown}"
    assert NO_FILEID not in tagged, "the error of the lookup answers, not an unknown id"
    assert '"isError": true' in tagged


# --- files_search(folder) -------------------------------------------------------------------

#: The SEARCH answer of an invented scope as nc35 gave it in 28-01 (A3): a Sabre 404.
_SEARCH_404 = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">'
    "<s:exception>Sabre\\DAV\\Exception\\NotFound</s:exception>"
    "<s:message>File with name /erfunden-1 could not be located</s:message></d:error>"
)


def _search_answers(status: int, body: str) -> Mocks:
    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="SEARCH", url=DAV_ROOT).mock(
            return_value=httpx.Response(status, text=body)
        )

    return mocks


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_search_answers_a_tagged_folder_like_an_invented_one(
    mode: str, unexpected: list[str]
) -> None:
    """The tagged root gets an empty 207 and the invented one a 404, as measured in 28-01.

    The refusal names the folder as the search scope ``/files/<user><folder>``, the wording
    D-28-19 fixed; that spelling is the requested folder as well, so it is replaced too. The
    word boundary of ``normalised`` would not see ``/Projekt`` after ``/files/alice``.
    """
    for folder in ("/Projekt", "/Projekt/Unter"):
        tagged, unknown = await pair(
            "files_search",
            {"query": "budget", "folder": folder},
            {"query": "budget", "folder": "/erfunden-1"},
            (folder, f"/files/{USER}{folder}"),
            ("/erfunden-1", f"/files/{USER}/erfunden-1"),
            _search_answers(207, _multistatus()),
            _search_answers(404, _SEARCH_404),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown, mode, NOT_FOUND)


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["500", "503", "timeout"])
async def test_files_search_answers_a_failing_search_alike(
    failure: str, unexpected: list[str]
) -> None:
    """D-28-17 (review WR-01): a failing SEARCH answers a tagged and an invented root alike.

    The error of the SEARCH is read before the tag decides, so the outage of the neighbour
    request does not tell a tagged root (``File not found``) from an invented one.
    """

    def failing(mock: respx.MockRouter) -> None:
        route = mock.route(method="SEARCH", url=DAV_ROOT)
        if failure == "timeout":
            route.mock(side_effect=httpx.ReadTimeout("slow"))
        else:
            route.mock(return_value=httpx.Response(int(failure)))

    tagged, unknown = await pair(
        "files_search",
        {"query": "budget", "folder": "/Projekt"},
        {"query": "budget", "folder": "/erfunden-1"},
        ("/Projekt", f"/files/{USER}/Projekt"),
        ("/erfunden-1", f"/files/{USER}/erfunden-1"),
        failing,
        failing,
        "active",
        unexpected,
    )
    assert tagged == unknown, f"tagged:  {tagged}\nunknown: {unknown}"
    assert NOT_FOUND not in tagged, "the error of the SEARCH answers, not a missing root"
    assert '"isError": true' in tagged


# --- files_upload: text and the first binary chunk ------------------------------------------

INVENTED_FOLDER = "/erfunden-1"


def _text_put(path: str, status: int) -> Mocks:
    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PUT", url=f"{FILES}{path}").mock(return_value=httpx.Response(status))

    return mocks


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_upload_text_into_a_tagged_target_answers_like_an_invented_folder(
    mode: str, unexpected: list[str]
) -> None:
    """A tagged folder and a tagged file under a visible parent against a missing parent."""
    invented = f"{INVENTED_FOLDER}/neu.txt"
    for path in ("/Projekt/neu.txt", "/Docs/geheim.txt"):
        tagged, unknown = await pair(
            "files_upload",
            {"path": path, "content": "# Neue Notiz\n"},
            {"path": invented, "content": "# Neue Notiz\n"},
            path,
            invented,
            _text_put(path, 201),
            _text_put(invented, 409),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown, mode, PARENT_MISSING)
        assert '"isError": true' in tagged


def _staging(chunk_status: int) -> Mocks:
    """MKCOL of the staging folder and the chunk PUT, below the upload area of the user."""

    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="MKCOL", url__startswith=UPLOADS).mock(return_value=httpx.Response(201))
        mock.route(method="PUT", url__startswith=UPLOADS).mock(
            return_value=httpx.Response(chunk_status)
        )

    return mocks


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_upload_first_binary_chunk_answers_like_an_invented_folder(
    mode: str, unexpected: list[str]
) -> None:
    """Chunk 1 of several (B6, D-28-20): Nextcloud refuses the invented folder at the PUT."""
    chunk = b"x" * files_tools.MIN_UPLOAD_CHUNK_BYTES
    args = {
        "content_base64": base64.b64encode(chunk).decode("ascii"),
        "total_bytes": len(chunk) + 4,
        "chunk_index": 1,
        "final": False,
    }
    path = "/Projekt/neu.bin"
    invented = f"{INVENTED_FOLDER}/neu.bin"
    tagged, unknown = await pair(
        "files_upload",
        {"path": path, **args},
        {"path": invented, **args},
        path,
        invented,
        _staging(201),
        _staging(404),
        mode,
        unexpected,
    )
    _assert_equal(tagged, unknown, mode, PARENT_MISSING)
    assert '"isError": true' in tagged


# --- files_create_folder: one folder, without parents --------------------------------------


def _mkcol(path: str, status: int, seen: list[respx.Route] | None = None) -> Mocks:
    """The MKCOL of one folder below the home; ``seen`` collects the route for counting."""

    def mocks(mock: respx.MockRouter) -> None:
        route = mock.route(method="MKCOL", url=f"{FILES}{path}").mock(
            return_value=httpx.Response(status)
        )
        if seen is not None:
            seen.append(route)

    return mocks


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_create_folder_in_a_tagged_folder_answers_like_an_invented_parent(
    mode: str, unexpected: list[str]
) -> None:
    """A new folder below a tagged folder against a new folder below a missing parent.

    Only without ``parents``: with it the invented side would simply be created, so the
    case has no natural counterpart (the chain is covered by
    tests/unit/test_files_create_folder_exclusion.py).

    The tagged side must not send its MKCOL at all, which is why its 201 route is counted.
    The 409 route of the invented side is the positive control of that count: it is reached
    whenever the guard answers, so a zero on the tagged side is not a route that never
    matches.
    """
    path = "/Projekt/neu"
    invented = f"{INVENTED_FOLDER}/neu"
    accepted: list[respx.Route] = []
    refused: list[respx.Route] = []
    tagged, unknown = await pair(
        "files_create_folder",
        {"path": path},
        {"path": invented},
        path,
        invented,
        _mkcol(path, 201, accepted),
        _mkcol(invented, 409, refused),
        mode,
        unexpected,
    )
    _assert_equal(tagged, unknown, mode, PARENT_MISSING)
    assert '"isError": true' in tagged
    assert [route.call_count for route in accepted] == [0], "no MKCOL into a tagged folder"
    assert [route.call_count for route in refused] == [1 if mode in ANSWERED else 0]


# --- coverage and time ----------------------------------------------------------------------


def test_the_files_family_covers_exactly_its_pair_cases() -> None:
    """No pair case of the family is skipped quietly, and no named exception is hidden."""
    family = {case for case, name in PAIR_CASES.items() if name == "files"}
    assert family == COVERED
    named = {case for case in NAMED_EXCEPTIONS if PAIR_CASES.get(case) == "files"}
    assert named == NAMED_HERE, "a named exception of the family needs its own named test"


@pytest.mark.anyio
async def test_time_is_not_part_of_the_comparison(unexpected: list[str]) -> None:
    """D-28-12: a slow and a fast answer of the same refusal normalise to the same string.

    The response time is no field of the answer, so ``normalised`` carries no time value;
    a timing oracle is accepted and documented in phase 29.
    """

    def slow(mock: respx.MockRouter) -> None:
        def answer(_request: httpx.Request) -> httpx.Response:
            time.sleep(0.2)
            return httpx.Response(404)

        mock.route(method="PROPFIND", url=f"{FILES}{UNKNOWN_PATH}").mock(side_effect=answer)

    fast, delayed = await pair(
        "files_read",
        {"path": UNKNOWN_PATH},
        {"path": UNKNOWN_PATH},
        UNKNOWN_PATH,
        UNKNOWN_PATH,
        _missing(UNKNOWN_PATH),
        slow,
        "active",
        unexpected,
    )
    assert fast == delayed

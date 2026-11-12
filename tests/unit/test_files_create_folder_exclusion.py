"""The ``kein-ki`` guard on folder creation: fail-closed and without an oracle (FOLD-04).

A folder inside a tagged folder is refused before any request to the files endpoint, with
exactly the refusal Nextcloud gives for a missing parent folder, so the answer cannot tell
"withheld" from "not there". No ``patch_untagged`` here: the guard requests are mocked
through ``guard_routes``, and every refusal counts the MKCOL and the PROPFIND requests on
the files endpoint, because a read before the check would itself be an existence oracle.

Two counter checks keep the refusals honest. The neighbour ``/Projektplan`` shares a prefix
with the tagged ``/Projekt`` and must be created: the guard matches whole segments. And the
same call without the tag creates ``/Projekt/neu``: without that positive control a refusal
could come from anywhere.
"""

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools
from mcp_connector.tools import withhold

BASE = guard_routes.BASE
USER = guard_routes.USER
SECRET = "app-password-test"
HOME = f"{BASE}/remote.php/dav/files/{USER}"

TAGGED_FOLDER = ("Projekt", "900", True)
TAGGED_FILE = ("Docs/geheim.txt", "901", False)
#: A tag somewhere else: the guard is active and asks its REPORT, the target is free.
TAGGED_ELSEWHERE = ("Geheim", "902", True)

TARGET = "/Projekt/neu"
OC_FILEID = "00023274oclxpo7v8s2m"


@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()


def _clients() -> NcClients:
    """One bundle per tool call, as ``deps.resolve_clients`` builds it: one guard each."""
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def _untagged(mock: respx.MockRouter) -> respx.Route:
    """The untagged state after an active one: drop the cached tag ids first."""
    guard_routes.reset()
    return guard_routes.untagged(mock)


def _tuple(err: ToolError) -> tuple[str, str, str]:
    return (err.message, err.hint, err.reason)


def _mock() -> respx.MockRouter:
    return respx.mock(assert_all_mocked=True, assert_all_called=False)


class _Files:
    """Every request this tool can send to the files endpoint, counted by method.

    Routes added through :meth:`folder` answer before the catch-alls, so a test can let
    single nodes exist while everything else is missing.
    """

    def __init__(self, mock: respx.MockRouter, mkcol_status: int = 201) -> None:
        self._mock = mock
        self._nodes: list[respx.Route] = []
        self._mkcol_status = mkcol_status
        self._sealed = False
        self._mkcol: respx.Route | None = None
        self._propfind: respx.Route | None = None

    def folder(self, path: str, fileid: str) -> None:
        """Let ``path`` exist as a folder. Must be called before :meth:`seal`."""
        assert not self._sealed
        body = guard_routes.report_207((path.strip("/"), fileid, True))
        self._nodes.append(
            self._mock.route(method="PROPFIND", url=f"{HOME}{path}").mock(
                return_value=guard_routes.listed(body)
            )
        )

    def seal(self) -> "_Files":
        self._sealed = True
        self._mkcol = self._mock.route(method="MKCOL", url__startswith=f"{HOME}/").mock(
            return_value=httpx.Response(self._mkcol_status, headers={"oc-fileid": OC_FILEID})
        )
        self._propfind = self._mock.route(method="PROPFIND", url__startswith=f"{HOME}/").mock(
            return_value=httpx.Response(404)
        )
        return self

    @property
    def mkcol_count(self) -> int:
        assert self._mkcol is not None
        return self._mkcol.call_count

    @property
    def propfind_count(self) -> int:
        assert self._propfind is not None
        return self._propfind.call_count + sum(route.call_count for route in self._nodes)


async def _refused(path: str, *, parents: bool) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await files_tools.create_folder(_clients(), path=path, parents=parents)
    return caught.value


@pytest.mark.anyio
@pytest.mark.parametrize("parents", [False, True])
async def test_a_folder_in_a_tagged_folder_reads_like_a_missing_parent(parents: bool) -> None:
    with _mock() as mock:
        _, report = guard_routes.active(mock, TAGGED_FOLDER)
        files = _Files(mock).seal()
        tagged = await _refused(TARGET, parents=parents)
        assert report.call_count == 1

    assert files.mkcol_count == 0, "no write before the refusal"
    assert files.propfind_count == 0, "no read before the refusal: it would be an oracle"
    assert _tuple(tagged) == _tuple(dav.parent_missing(TARGET))


@pytest.mark.anyio
async def test_a_chain_below_a_tagged_ancestor_sends_nothing_but_the_tag_check() -> None:
    path = "/Projekt/a/b/c"
    with _mock() as mock:
        _, report = guard_routes.active(mock, TAGGED_FOLDER)
        files = _Files(mock).seal()
        tagged = await _refused(path, parents=True)
        methods = [call.request.method for call in mock.calls]

    assert methods == ["PROPFIND", "REPORT"], "the tag listing and the one REPORT, nothing else"
    assert report.call_count == 1
    assert files.mkcol_count == 0
    assert files.propfind_count == 0
    assert _tuple(tagged) == _tuple(dav.parent_missing(path))


@pytest.mark.anyio
async def test_a_tagged_target_answers_like_the_same_path_with_a_missing_parent() -> None:
    """The pair on one path: withheld by the guard against the real 409 of Nextcloud."""
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FOLDER)
        files = _Files(mock).seal()
        tagged = await _refused(TARGET, parents=False)

    with _mock() as mock:
        _untagged(mock)
        real = _Files(mock, mkcol_status=409).seal()
        missing = await _refused(TARGET, parents=False)

    assert files.mkcol_count == 0
    assert files.propfind_count == 0
    assert real.mkcol_count == 1, "the comparison side really asked Nextcloud"
    assert _tuple(tagged) == _tuple(missing)


@pytest.mark.anyio
async def test_a_tagged_target_answers_like_an_invented_folder() -> None:
    """The pair on two paths: only the path itself differs, as in the paired tests."""
    invented = "/erfunden-1/neu"
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FOLDER)
        files = _Files(mock).seal()
        tagged = await _refused(TARGET, parents=False)

    with _mock() as mock:
        _untagged(mock)
        real = _Files(mock, mkcol_status=409).seal()
        unknown = await _refused(invented, parents=False)

    assert files.mkcol_count == 0
    assert files.propfind_count == 0
    assert real.mkcol_count == 1
    assert invented in unknown.message, "the control side names its own path"
    renamed = tuple(part.replace("/erfunden-1", "/Projekt") for part in _tuple(unknown))
    assert _tuple(tagged) == renamed


@pytest.mark.anyio
async def test_a_tagged_file_as_target_gets_the_same_sentence() -> None:
    """ "A file already exists" would confirm the withheld file (edge case of D-27-01)."""
    path = "/Docs/geheim.txt"
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE)
        files = _Files(mock).seal()
        tagged = await _refused(path, parents=False)

    assert files.mkcol_count == 0
    assert files.propfind_count == 0
    assert "already exists" not in tagged.message
    assert _tuple(tagged) == _tuple(dav.parent_missing(path))


@pytest.mark.anyio
async def test_a_neighbour_with_the_same_prefix_is_created() -> None:
    """Counter check with another pattern: the guard matches segments, not prefixes."""
    path = "/Projektplan/neu"
    with _mock() as mock:
        _, report = guard_routes.active(mock, TAGGED_FOLDER)
        files = _Files(mock).seal()
        result = await files_tools.create_folder(_clients(), path=path)
        assert report.call_count == 1

    assert files.mkcol_count == 1
    assert result == {"path": path, "created": True, "id": "file:23274"}


@pytest.mark.anyio
@pytest.mark.parametrize("parents", [False, True])
async def test_without_the_tag_the_same_folder_is_created(parents: bool) -> None:
    """Positive control: the refusals above come from the guard and from nothing else."""
    with _mock() as mock:
        _untagged(mock)
        files = _Files(mock)
        files.folder("/Projekt", "950")
        files.seal()
        result = await files_tools.create_folder(_clients(), path=TARGET, parents=parents)

    assert files.mkcol_count == 1
    assert result["path"] == TARGET
    assert result["created"] is True
    assert result["id"] == "file:23274"


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["unverifiable", "stale", "timeout"])
@pytest.mark.parametrize("parents", [False, True])
async def test_an_unanswered_tag_check_writes_and_reads_nothing(state: str, parents: bool) -> None:
    with _mock() as mock:
        getattr(guard_routes, state)(mock)
        files = _Files(mock).seal()
        refused = await _refused("/Frei/neu", parents=parents)

    assert files.mkcol_count == 0, "fail-closed: nothing is written unchecked"
    assert files.propfind_count == 0
    assert _tuple(refused) == _tuple(withhold.unavailable_error())


@pytest.mark.anyio
async def test_a_chain_checks_before_every_mkcol_and_asks_one_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked: list[str] = []
    original = files_tools._writable

    async def counting(clients: NcClients, target: str) -> None:
        checked.append(target)
        await original(clients, target)

    monkeypatch.setattr(files_tools, "_writable", counting)

    path = "/A/b/c/d"
    with _mock() as mock:
        _, report = guard_routes.active(mock, TAGGED_ELSEWHERE)
        files = _Files(mock)
        files.folder("/A", "960")
        files.seal()
        result = await files_tools.create_folder(_clients(), path=path, parents=True)

    assert result["created_folders"] == ["/A/b", "/A/b/c", "/A/b/c/d"]
    assert files.mkcol_count == 3
    assert report.call_count == 1, "the checks of one call share a single REPORT"
    assert len(checked) == files.mkcol_count + 1, "once at the entry, once before every MKCOL"
    assert set(checked) == {path}, "the target is checked, never the segment"

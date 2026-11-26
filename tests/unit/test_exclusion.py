"""The exclusion guard core: three states, the segment rule, the name-to-id cache, one flight."""

import asyncio
import base64
import dataclasses
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
import respx
from lxml import etree

from mcp_connector import config
from mcp_connector.nextcloud import NcClients, exclusion
from mcp_connector.nextcloud.clients import dav, systemtags
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
SECRET = "app-password-test"
SRC = Path(__file__).resolve().parents[2] / "src"

TAGS = f"{BASE}/remote.php/dav/systemtags/"
HOME = f"{BASE}/remote.php/dav/files/alice/"
ADMIN_HOME = f"{BASE}/remote.php/dav/files/admin/"
CAPABILITIES = f"{BASE}/ocs/v2.php/cloud/capabilities"
ALICE_KEY = (BASE, "alice", "alice")

XML_HEADERS = {"Content-Type": "application/xml; charset=utf-8"}

type Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    exclusion.clear_cache()
    yield
    exclusion.clear_cache()


# --- ancestors and the segment rule ------------------------------------------------------


def test_ancestors_lists_the_path_and_every_parent_up_to_the_root() -> None:
    assert exclusion.ancestors("/A/kein/x") == ("/A/kein/x", "/A/kein", "/A", "/")
    assert exclusion.ancestors("/A") == ("/A", "/")
    assert exclusion.ancestors("/") == ("/",)


@pytest.mark.parametrize("path", ["/A/kein", "/A/kein/x", "/A/keine", "/A", "/", "/A/kein/x/y.md"])
@pytest.mark.parametrize("tagged", [{"/A/kein"}, {"/"}, {"/A/keine"}])
def test_ancestors_draws_the_same_boundary_as_the_segment_rule(path: str, tagged: set[str]) -> None:
    by_ancestors = any(a in tagged for a in exclusion.ancestors(path))
    by_within = any(dav.within(path, t) for t in tagged)

    assert by_ancestors == by_within


# --- TagScope ----------------------------------------------------------------------------


def test_an_active_scope_covers_the_tagged_folder_and_below_but_not_a_sibling() -> None:
    scope = exclusion.TagScope("active", paths=frozenset({"/A/kein"}))

    assert scope.excludes(path="/A/kein/x") is True
    assert scope.excludes(path="/A/kein") is True
    assert scope.excludes(path="/A/keine") is False
    assert scope.excludes(path="/A") is False


def test_an_active_scope_matches_file_ids() -> None:
    scope = exclusion.TagScope("active", fileids=frozenset({"957"}))

    assert scope.excludes(fileid="957") is True
    assert scope.excludes(fileid="958") is False


def test_an_active_scope_refuses_to_be_asked_about_nothing() -> None:
    """Both arguments None is a caller bug (wrong dict keys), never a silent "allowed"."""
    scope = exclusion.TagScope("active", paths=frozenset({"/A/kein"}))

    with pytest.raises(ValueError, match="path or a fileid"):
        scope.excludes()
    with pytest.raises(ValueError, match="path or a fileid"):
        scope.excludes(path=None, fileid=None)


@pytest.mark.parametrize("path", ["Docs/a.md", "A/kein/x", ""])
def test_an_active_scope_refuses_a_relative_path(path: str) -> None:
    """A relative path never matches an ancestor of the tagged set, so it must raise."""
    scope = exclusion.TagScope("active", paths=frozenset({"/A/kein"}), fileids=frozenset({"955"}))

    with pytest.raises(ValueError, match="absolute home path"):
        scope.excludes(path=path)
    with pytest.raises(ValueError, match="absolute home path"):
        scope.excludes(path=path, fileid="955")


def test_an_untagged_scope_excludes_nothing_and_leaves_no_trace() -> None:
    scope = exclusion.UNTAGGED
    entries = [
        {"path": "/A/kein", "fileid": "955", "type": "folder"},
        {"path": "/A/doc.md", "fileid": "957", "type": "file", "size": 12},
        {"path": "/", "fileid": "1", "type": "folder"},
    ]

    kept = [e for e in entries if not scope.excludes(path=e["path"], fileid=e["fileid"])]

    assert scope.state == "untagged"
    assert scope.excludes() is False
    assert scope.excludes(path="/A/kein", fileid="955") is False
    assert kept == entries
    assert json.dumps(kept) == json.dumps(entries)


def test_an_unverifiable_scope_refuses_to_answer() -> None:
    scope = exclusion.TagScope("unverifiable", reason="status")

    with pytest.raises(ValueError, match="unverifiable"):
        scope.excludes(path="/A")
    with pytest.raises(ValueError, match="unverifiable"):
        scope.excludes(fileid="1")
    with pytest.raises(ValueError, match="unverifiable"):
        scope.excludes()


def test_a_scope_is_immutable() -> None:
    with pytest.raises(AttributeError):
        exclusion.UNTAGGED.state = "active"  # type: ignore[misc]


# --- names and ids -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (" kein-ki", True),
        ("KEIN-KI", True),
        ("Kein-KI", True),
        ("kein-ki", True),
        ("kein-ki-alt", False),
        ("keinki", False),
        ("", False),
    ],
)
def test_is_exclude_name_ignores_case_and_surrounding_blanks(name: str, expected: bool) -> None:
    assert exclusion.is_exclude_name(name) is expected


def test_the_tag_name_is_fixed() -> None:
    assert exclusion.EXCLUDE_TAG == "kein-ki"


def test_exclude_tag_ids_keeps_the_lowest_id_per_exact_spelling() -> None:
    tags = [
        systemtags.Tag(id="65", name="kein-ki"),
        systemtags.Tag(id="64", name="kein-ki"),
        systemtags.Tag(id="70", name="projekt"),
        systemtags.Tag(id="67", name="Kein-KI"),
    ]

    assert exclusion.exclude_tag_ids(tags) == ("64", "67")


def test_exclude_tag_ids_sorts_numerically_and_is_empty_without_a_match() -> None:
    tags = [systemtags.Tag(id="100", name="KEIN-KI"), systemtags.Tag(id="9", name="kein-ki")]

    assert exclusion.exclude_tag_ids(tags) == ("9", "100")
    assert exclusion.exclude_tag_ids([systemtags.Tag(id="1", name="projekt")]) == ()


# --- the name-to-id cache ----------------------------------------------------------------


def test_the_cache_stores_positive_results_only() -> None:
    key = ("http://nc.test", "alice", "alice")

    exclusion._store_ids(key, ())
    assert exclusion._tag_ids == {}
    assert exclusion._cached_ids(key) is None

    exclusion._store_ids(key, ("64",))
    assert exclusion._cached_ids(key) == ("64",)

    exclusion._drop_ids(key)
    assert exclusion._cached_ids(key) is None
    exclusion._drop_ids(key)  # dropping twice is harmless


def test_a_cache_entry_expires_after_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    key = ("http://nc.test", "alice", "alice")
    exclusion._tag_ids[key] = (100.0, ("64",))

    monkeypatch.setattr(exclusion.time, "monotonic", lambda: 100.0 + exclusion.TTL_SECONDS - 1)
    assert exclusion._cached_ids(key) == ("64",)

    monkeypatch.setattr(exclusion.time, "monotonic", lambda: 100.0 + exclusion.TTL_SECONDS)
    assert exclusion._cached_ids(key) is None


def test_clear_cache_drops_every_entry() -> None:
    exclusion._tag_ids[("http://nc.test", "alice", "alice")] = (0.0, ("64",))
    exclusion._tag_ids[("http://nc.test", "admin", "admin")] = (0.0, ("63",))

    exclusion.clear_cache()

    assert exclusion._tag_ids == {}


# --- helpers for the flight tests --------------------------------------------------------


def _clients(user: str = "alice", base_url: str = BASE) -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(base_url, user, SECRET),
    )


@pytest.fixture
def clients() -> NcClients:
    return _clients("alice")


@pytest.fixture
def admin() -> NcClients:
    return _clients("admin")


def multistatus(*responses: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">'
        f"{''.join(responses)}</d:multistatus>"
    ).encode()


def _response(href: str, props: str) -> str:
    return (
        f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{props}</d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
    )


def tag_list(*tags: tuple[str, str]) -> bytes:
    """A 207 tag listing: the collection itself (no id) plus one entry per (id, name)."""
    entries = [_response("/remote.php/dav/systemtags/", "<oc:display-name></oc:display-name>")]
    entries += [
        _response(
            f"/remote.php/dav/systemtags/{tag_id}",
            f"<oc:id>{tag_id}</oc:id><oc:display-name>{name}</oc:display-name>",
        )
        for tag_id, name in tags
    ]
    return multistatus(*entries)


def report_207(*nodes: tuple[str, str, bool], user: str = "alice") -> bytes:
    """A 207 REPORT answer; each node is (href suffix below the home, fileid, is_collection)."""
    return multistatus(
        *(
            _response(
                f"/remote.php/dav/files/{user}/{suffix}",
                f"<oc:fileid>{fileid}</oc:fileid><d:resourcetype>"
                f"{'<d:collection/>' if folder else ''}</d:resourcetype>",
            )
            for suffix, fileid, folder in nodes
        )
    )


def listed(body: bytes) -> httpx.Response:
    return httpx.Response(207, content=body, headers=XML_HEADERS)


def asked_ids(request: httpx.Request) -> list[str]:
    root = etree.fromstring(request.content, parser=davxml.hardened_parser())
    return [str(rule.text) for rule in root.iter(f"{{{davxml.OC}}}systemtag")]


def asked_user(request: httpx.Request) -> str:
    scheme, _, token = request.headers["Authorization"].partition(" ")
    assert scheme == "Basic"
    return base64.b64decode(token).decode().split(":", 1)[0]


def by_id(answers: dict[str, httpx.Response]) -> Handler:
    """A REPORT handler that answers per asked id and insists on exactly one id per body."""

    def handler(request: httpx.Request) -> httpx.Response:
        ids = asked_ids(request)
        assert len(ids) == 1, f"one REPORT must carry exactly one tag id, got {ids}"
        return answers[ids[0]]

    return handler


def prefill(*ids: str) -> None:
    exclusion._tag_ids[ALICE_KEY] = (time.monotonic(), ids)


async def slow(response: httpx.Response) -> httpx.Response:
    for _ in range(5):
        await asyncio.sleep(0)
    return response


# --- state untagged ----------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_listing_without_the_tag_is_untagged_sends_no_report_and_caches_nothing(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("70", "projekt"), ("71", "kein-ki-alt")))
        )
        report = mock.route(method="REPORT", url=HOME)

        scope = await exclusion.ExclusionGuard().scope(clients)
        assert scope.state == "untagged"
        assert scope.reason is None
        assert scope.excludes(path="/A", fileid="1") is False
        assert report.call_count == 0
        assert exclusion._tag_ids == {}

        again = await exclusion.ExclusionGuard().scope(clients)

    assert again.state == "untagged"
    assert listing.call_count == 2  # nothing negative was cached, so it lists again
    assert report.call_count == 0


# --- state active ------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_tagged_folder_and_file_make_the_scope_active(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki"), ("70", "projekt")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            side_effect=by_id(
                {"64": listed(report_207(("A/kein/", "955", True), ("A/doc.md", "957", False)))}
            )
        )

        scope = await exclusion.ExclusionGuard().scope(clients)

    assert scope.state == "active"
    assert scope.reason is None
    assert scope.paths == frozenset({"/A/kein", "/A/doc.md"})
    assert scope.fileids == frozenset({"955", "957"})
    assert scope.excludes(path="/A/kein/x") is True
    assert scope.excludes(path="/A/keine") is False
    assert listing.call_count == 1
    assert report.call_count == 1
    assert asked_ids(report.calls[0].request) == ["64"]
    assert exclusion._tag_ids[ALICE_KEY][1] == ("64",)
    assert scope.has_folders is True


@pytest.mark.anyio
async def test_only_tagged_files_make_an_active_scope_without_folders(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        mock.route(method="REPORT", url=HOME).mock(
            return_value=listed(report_207(("A/doc.md", "957", False), ("B/x.pdf", "958", False)))
        )

        scope = await exclusion.ExclusionGuard().scope(clients)

    assert scope.state == "active"
    assert scope.has_folders is False
    assert exclusion.UNTAGGED.has_folders is False


# --- the guard field of NcClients ----------------------------------------------------------


def test_every_bundle_gets_a_fresh_guard_and_equality_stays_as_it_was() -> None:
    client = httpx.AsyncClient(follow_redirects=False)
    creds = Credentials(BASE, "alice", SECRET)

    first = NcClients(client=client, creds=creds)
    second = NcClients(client=client, creds=creds)

    assert first == second
    assert first.exclusion is not second.exclusion
    assert isinstance(first.exclusion, exclusion.ExclusionGuard)
    assert "exclusion" not in repr(first)

    replaced = dataclasses.replace(first, exclusion=exclusion.ExclusionGuard())
    assert replaced.exclusion is not first.exclusion
    assert replaced == first


@pytest.mark.parametrize(
    "module",
    [
        "mcp_connector.nextcloud.exclusion",
        "mcp_connector.nextcloud.clients.dav",
        "mcp_connector.nextcloud",
    ],
)
def test_each_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    """The guard field must not bring back the cycle ``exclusion`` <-> ``nextcloud``."""
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    done = subprocess.run(  # noqa: S603 - a fixed argv of this test, no shell, no user input
        [sys.executable, "-c", f"import {module}"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert done.returncode == 0, done.stderr


@pytest.mark.anyio
async def test_the_capability_is_never_asked_even_when_it_says_systemtags_is_off(
    clients: NcClients,
) -> None:
    disabled = {"ocs": {"meta": {"status": "ok"}, "data": {"capabilities": {}}}}
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        capabilities = mock.get(CAPABILITIES).mock(return_value=httpx.Response(200, json=disabled))
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        mock.route(method="REPORT", url=HOME).mock(
            return_value=listed(report_207(("A/doc.md", "957", False)))
        )

        scope = await exclusion.ExclusionGuard().scope(clients)

    assert scope.state == "active"
    assert capabilities.call_count == 0


# --- state unverifiable, one test per reason ----------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("status", [500, 401, 403, 301])
async def test_a_report_status_other_than_207_or_412_is_unverifiable(
    clients: NcClients, status: int
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(status, headers={"Location": f"{BASE}/login"})
        )

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="status")
    assert report.call_count == 1  # no retry
    assert listing.call_count == 1
    with pytest.raises(ValueError, match="unverifiable"):
        scope.excludes(path="/A")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx.ConnectError("refused"), "unreachable"),
        (httpx.RemoteProtocolError("closed"), "unreachable"),
        (httpx.ReadTimeout("slow"), "timeout"),
        (httpx.ConnectTimeout("slow"), "timeout"),
    ],
)
async def test_a_transport_failure_of_the_report_is_unverifiable(
    clients: NcClients, error: Exception, reason: exclusion.Why
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(side_effect=error)

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason=reason)
    assert report.call_count == 1


@pytest.mark.anyio
async def test_a_transport_failure_of_the_listing_is_unverifiable(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            side_effect=httpx.ConnectError("refused")
        )
        report = mock.route(method="REPORT", url=HOME)

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="unreachable")
    assert listing.call_count == 1
    assert report.call_count == 0


@pytest.mark.anyio
async def test_a_report_slower_than_the_budget_is_unverifiable_and_does_not_wait(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exclusion, "TAG_BUDGET", 0.01)
    # respx records a call only once its handler returns, and this one never does, so the
    # handler counts its own entries.
    entered = 0

    async def too_slow(_request: httpx.Request) -> httpx.Response:
        nonlocal entered
        entered += 1
        await asyncio.sleep(1)
        return listed(report_207())

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(side_effect=too_slow)

        started = time.monotonic()
        scope = await exclusion.load_scope(clients)
        elapsed = time.monotonic() - started

    assert scope == exclusion.TagScope("unverifiable", reason="timeout")
    assert entered == 1  # asked once, no retry after the budget ran out
    assert report.call_count == 0  # and that one request never completed
    assert elapsed < 0.5


@pytest.mark.anyio
async def test_an_unparsable_report_is_unverifiable(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(207, content=b"<html>login", headers=XML_HEADERS)
        )

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="unparsable")
    assert report.call_count == 1


@pytest.mark.anyio
async def test_a_tagged_node_without_a_file_id_is_unverifiable(clients: NcClients) -> None:
    body = multistatus(
        _response("/remote.php/dav/files/alice/A/doc.md", "<d:resourcetype></d:resourcetype>")
    )
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        mock.route(method="REPORT", url=HOME).mock(return_value=listed(body))

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="unparsable")


@pytest.mark.anyio
async def test_a_href_under_a_foreign_prefix_is_unverifiable_never_an_empty_set(
    clients: NcClients,
) -> None:
    body = multistatus(
        _response(
            "/remote.php/dav/files/alice/A/doc.md",
            "<oc:fileid>957</oc:fileid><d:resourcetype></d:resourcetype>",
        ),
        _response(
            "/remote.php/dav/files/bob/secret.md",
            "<oc:fileid>958</oc:fileid><d:resourcetype></d:resourcetype>",
        ),
    )
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(return_value=listed(body))

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="foreign_href")
    assert report.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("suffix", ["A%2Fkein", "A%2fkein/", "A//B", "A%00B"])
async def test_an_encoded_slash_or_a_double_slash_in_a_tagged_href_is_unverifiable(
    clients: NcClients, suffix: str
) -> None:
    """IN-02/IN-03: ``A%2Fkein`` is one segment; decoding it into two would move the boundary."""
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            return_value=listed(report_207(("A/doc.md", "957", False), (suffix, "958", True)))
        )

        scope = await exclusion.ExclusionGuard().scope(clients)

    assert scope.state == "unverifiable"
    assert scope.reason == "foreign_href"
    assert report.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("status", [500, 401, 404])
async def test_a_listing_status_other_than_207_is_unverifiable(
    clients: NcClients, status: int
) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(return_value=httpx.Response(status))
        report = mock.route(method="REPORT", url=HOME)

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="status")
    assert listing.call_count == 1
    assert report.call_count == 0
    assert exclusion._tag_ids == {}


@pytest.mark.anyio
async def test_an_unparsable_listing_is_unverifiable(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=b"<html>login", headers=XML_HEADERS)
        )
        report = mock.route(method="REPORT", url=HOME)

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="unparsable")
    assert listing.call_count == 1
    assert report.call_count == 0


@pytest.mark.anyio
async def test_a_listing_entry_without_an_id_is_unverifiable(clients: NcClients) -> None:
    body = multistatus(
        _response("/remote.php/dav/systemtags/", "<oc:display-name></oc:display-name>"),
        _response("/remote.php/dav/systemtags/64", "<oc:display-name>kein-ki</oc:display-name>"),
    )
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(return_value=listed(body))
        report = mock.route(method="REPORT", url=HOME)

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="unparsable")
    assert report.call_count == 0


@pytest.mark.anyio
async def test_a_listing_with_an_odd_tag_id_is_unverifiable(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("6a", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME)

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="unparsable")
    assert report.call_count == 0


# --- 412: the id went stale, look it up exactly once more --------------------------------


@pytest.mark.anyio
async def test_a_412_then_the_tag_is_gone_gives_untagged(clients: NcClients) -> None:
    prefill("64")
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("70", "projekt")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(return_value=httpx.Response(412))

        scope = await exclusion.load_scope(clients)

    assert scope.state == "untagged"
    assert report.call_count == 1
    assert listing.call_count == 1
    assert exclusion._tag_ids == {}


@pytest.mark.anyio
async def test_a_412_then_a_new_id_gives_active_and_caches_the_new_id(clients: NcClients) -> None:
    prefill("64")
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("70", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            side_effect=by_id(
                {
                    "64": httpx.Response(412),
                    "70": listed(report_207(("A/doc.md", "957", False))),
                }
            )
        )

        scope = await exclusion.load_scope(clients)

    assert scope.state == "active"
    assert scope.fileids == frozenset({"957"})
    assert report.call_count == 2
    assert [asked_ids(call.request) for call in report.calls] == [["64"], ["70"]]
    assert listing.call_count == 1
    assert exclusion._tag_ids[ALICE_KEY][1] == ("70",)


@pytest.mark.anyio
async def test_a_412_twice_with_a_warm_cache_is_unverifiable(clients: NcClients) -> None:
    prefill("64")
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(return_value=httpx.Response(412))

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="stale_twice")
    assert report.call_count == 2
    assert listing.call_count == 1


@pytest.mark.anyio
async def test_a_412_twice_with_a_cold_cache_lists_exactly_once_more(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(return_value=httpx.Response(412))

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="stale_twice")
    assert listing.call_count == 2
    assert report.call_count == 2


@pytest.mark.anyio
async def test_a_412_then_another_status_is_unverifiable_by_status(clients: NcClients) -> None:
    prefill("64")
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("70", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            side_effect=by_id({"64": httpx.Response(412), "70": httpx.Response(500)})
        )

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="status")
    assert report.call_count == 2


@pytest.mark.anyio
async def test_a_412_then_a_failing_listing_is_unverifiable_by_status(clients: NcClients) -> None:
    prefill("64")
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(return_value=httpx.Response(503))
        report = mock.route(method="REPORT", url=HOME).mock(return_value=httpx.Response(412))

        scope = await exclusion.load_scope(clients)

    assert scope == exclusion.TagScope("unverifiable", reason="status")
    assert report.call_count == 1
    assert listing.call_count == 1
    assert exclusion._tag_ids == {}


# --- one flight per guard instance ---------------------------------------------------------


@pytest.mark.anyio
async def test_twenty_concurrent_scope_calls_cost_one_listing_and_one_report(
    clients: NcClients,
) -> None:
    async def slow_report(_request: httpx.Request) -> httpx.Response:
        return await slow(listed(report_207(("A/doc.md", "957", False))))

    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(side_effect=slow_report)
        guard = exclusion.ExclusionGuard()

        found = await asyncio.gather(*(guard.scope(clients) for _ in range(20)))

    assert report.call_count == 1
    assert listing.call_count == 1
    assert found[0].state == "active"
    assert all(scope is found[0] for scope in found)


@pytest.mark.anyio
async def test_twenty_concurrent_scope_calls_share_one_failure(clients: NcClients) -> None:
    async def slow_failure(_request: httpx.Request) -> httpx.Response:
        return await slow(httpx.Response(500))

    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(side_effect=slow_failure)
        guard = exclusion.ExclusionGuard()

        found = await asyncio.gather(*(guard.scope(clients) for _ in range(20)))

    assert report.call_count == 1
    assert found[0] == exclusion.TagScope("unverifiable", reason="status")
    assert all(scope is found[0] for scope in found)


@pytest.mark.anyio
async def test_a_guard_refuses_a_second_identity_instead_of_serving_a_foreign_scope(
    clients: NcClients, admin: NcClients
) -> None:
    """The first call binds the guard to (base_url, user); a different identity raises.

    Without the binding, a miswired reuse in phase 27 would hand the second caller the
    cached scope of the first account: foreign tagged paths, or worse, a foreign untagged.
    """
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("70", "projekt")))
        )
        guard = exclusion.ExclusionGuard()

        first = await guard.scope(clients)
        assert first.state == "untagged"
        again = await guard.scope(clients)  # the same identity stays served
        assert again is first

        with pytest.raises(ValueError, match=r"one ExclusionGuard serves exactly one"):
            await guard.scope(admin)
        with pytest.raises(ValueError, match=r"one ExclusionGuard serves exactly one"):
            await guard.scope(_clients("alice", base_url="http://other.test"))

    assert listing.call_count == 1  # the refused calls never reached the network


@pytest.mark.anyio
async def test_a_second_tool_call_fetches_the_set_anew_from_the_warm_name_cache(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            side_effect=[
                listed(report_207(("A/doc.md", "957", False))),
                listed(report_207(("A/doc.md", "957", False), ("A/new.md", "960", False))),
            ]
        )

        first = await exclusion.ExclusionGuard().scope(clients)
        second = await exclusion.ExclusionGuard().scope(clients)

    assert report.call_count == 2
    assert listing.call_count == 1
    assert first.fileids == frozenset({"957"})
    assert second.fileids == frozenset({"957", "960"})  # a tag added between calls shows


@pytest.mark.anyio
async def test_the_name_cache_is_keyed_per_user(clients: NcClients, admin: NcClients) -> None:
    def listing_for(request: httpx.Request) -> httpx.Response:
        if asked_user(request) == "admin":
            return listed(tag_list(("63", "KEIN-KI")))
        return listed(tag_list(("64", "kein-ki")))

    with respx.mock(assert_all_mocked=True) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(side_effect=listing_for)
        alice_report = mock.route(method="REPORT", url=HOME).mock(
            return_value=listed(report_207(("A/doc.md", "957", False)))
        )
        admin_report = mock.route(method="REPORT", url=ADMIN_HOME).mock(
            return_value=listed(report_207(("B/x.md", "990", False), user="admin"))
        )

        admin_scope = await exclusion.ExclusionGuard().scope(admin)
        alice_scope = await exclusion.ExclusionGuard().scope(clients)

    assert listing.call_count == 2  # the admin entry did not serve alice
    assert [asked_user(call.request) for call in listing.calls] == ["admin", "alice"]
    assert asked_ids(admin_report.calls[0].request) == ["63"]
    assert asked_ids(alice_report.calls[0].request) == ["64"]
    assert exclusion._tag_ids[(BASE, "admin", "admin")][1] == ("63",)
    assert exclusion._tag_ids[ALICE_KEY][1] == ("64",)
    assert admin_scope.fileids == frozenset({"990"})
    assert alice_scope.fileids == frozenset({"957"})


# --- spellings and visibility -------------------------------------------------------------


@pytest.mark.anyio
async def test_spelling_variants_cost_one_report_each_and_are_united(
    clients: NcClients, admin: NcClients
) -> None:
    def listing_for(request: httpx.Request) -> httpx.Response:
        # 64 public, 65 restricted, 67 a case variant; 63 is invisible and only the admin
        # sees it, so it is absent from alice's listing.
        visible = [("64", "kein-ki"), ("65", "kein-ki"), ("67", "Kein-KI")]
        if asked_user(request) == "admin":
            visible = [("63", "KEIN-KI"), *visible]
        return listed(tag_list(*visible))

    answers = {
        "63": listed(report_207(("C/hidden.md", "930", False), user="admin")),
        "64": listed(report_207(("A/kein/", "955", True))),
        "67": listed(report_207(("B/doc.md", "970", False))),
    }
    admin_answers = {
        "63": answers["63"],
        "64": listed(report_207(("A/kein/", "955", True), user="admin")),
        "67": listed(report_207(("B/doc.md", "970", False), user="admin")),
    }
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(side_effect=listing_for)
        alice_report = mock.route(method="REPORT", url=HOME).mock(side_effect=by_id(answers))
        admin_report = mock.route(method="REPORT", url=ADMIN_HOME).mock(
            side_effect=by_id(admin_answers)
        )

        alice_scope = await exclusion.ExclusionGuard().scope(clients)
        admin_scope = await exclusion.ExclusionGuard().scope(admin)

    assert alice_report.call_count == 2
    assert sorted(asked_ids(call.request)[0] for call in alice_report.calls) == ["64", "67"]
    assert alice_scope.state == "active"
    assert alice_scope.paths == frozenset({"/A/kein", "/B/doc.md"})
    assert alice_scope.fileids == frozenset({"955", "970"})

    assert admin_report.call_count == 3
    assert sorted(asked_ids(call.request)[0] for call in admin_report.calls) == ["63", "64", "67"]
    assert admin_scope.fileids == frozenset({"930", "955", "970"})


# --- a tagged ancestor above the sandbox ---------------------------------------------------


@pytest.mark.anyio
async def test_a_tagged_ancestor_above_the_sandbox_takes_effect(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Shared/KI")
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(
            return_value=listed(report_207(("Shared/", "12", True)))
        )

        scope = await exclusion.ExclusionGuard().scope(clients)

    assert report.call_count == 1
    assert scope.state == "active"
    assert scope.paths == frozenset({"/Shared"})  # not filtered by NC_MCP_FILES_ROOT
    assert scope.excludes(path="/Shared/KI/doc.md") is True
    assert scope.excludes(path="/Sharedx/doc.md") is False


# --- cancellation --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_cancelled_flight_stores_nothing_and_the_next_call_starts_anew(
    clients: NcClients,
) -> None:
    # respx records a call only once its handler returns, and the cancelled one never does,
    # so the handler counts every REPORT that went out itself.
    entered = 0

    async def first_hangs(_request: httpx.Request) -> httpx.Response:
        nonlocal entered
        entered += 1
        if entered == 1:
            await asyncio.sleep(10)
        return listed(report_207(("A/doc.md", "957", False)))

    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("64", "kein-ki")))
        )
        report = mock.route(method="REPORT", url=HOME).mock(side_effect=first_hangs)
        guard = exclusion.ExclusionGuard()

        holder = asyncio.create_task(guard.scope(clients))
        for _ in range(200):
            if entered:
                break
            await asyncio.sleep(0)
        assert entered == 1
        holder.cancel()
        with pytest.raises(asyncio.CancelledError):
            await holder

        assert guard._scope is None  # a cancellation is never stored as a state
        scope = await guard.scope(clients)

    assert scope.state == "active"
    assert entered == 2  # the later call started a new flight
    assert report.call_count == 1  # only the second REPORT ever completed

"""Live proof of ``files_create_folder`` under AppAPI impersonation (plan 31-05, D-31-06).

The question: does the tool function behind ``files_create_folder`` keep every promise of
phase 31 against a real Nextcloud when the only credential in play is ``APP_SECRET`` and the
user id travels inside the AppAPI header. Every measured call builds its credentials with
``mode="appapi"``; the identity can only come from ``AUTHORIZATION-APP-API``. The app
passwords of the test accounts are used by the harness alone: for the counter checks (an
independent PROPFIND), for the scaffolding and for the removal, never for a measured call.

Every case writes exactly one line::

    ORDNER <case> nc=<version> nutzer=<uid> status=<calls> ergebnis=<ok|befund> | <raw values>

``status`` lists every answer the measured client received as ``METHOD:status``; a request
outside ``remote.php/dav/files`` carries its area in front (``systemtags.REPORT:207``). The
hook stores the method, the path below the home and the status, nothing else. A case records
its line first and asserts afterwards, so a failing run leaves its ``befund`` in the output.
Each statement "nothing was created" is checked in the file system of the Nextcloud container
(``docker exec <nc> test -d``), a pattern the implementation does not use.

Everything the run creates lies below ``/ordner31-<stamp>`` of the measured account and is
removed by the harness in ``finally``; ``BASELINE`` lines compare the account before and
after.

Run it against Nextcloud 35 (``compose.nc35.yml``, containers started, never bootstrapped)::

    set -a && . <main checkout>/.env.nc35 && set +a
    export NC_MCP_E2E_COMPOSE_FILE=compose.nc35.yml NC_MCP_E2E_PROJECT=nc-mcp-nc35 \\
        NC_MCP_E2E_NEXTCLOUD=nc35-nc NC_MCP_E2E_HARP=nc35-harp NC_MCP_E2E_CADDY=nc35-caddy \\
        NC_MCP_E2E_CONTAINERS=nc35-nc,nc_app_mcp_connector,nc35-harp,nc35-caddy,nc35-greenmail
    PYTHONUTF8=1 uv run --no-sync pytest tests/integration/test_files_create_folder_live.py \\
        -m integration -s -q

and against the Nextcloud 32 route (``compose.exapp.yml``, default names of ``topology.py``)::

    set -a && . ./.env.exapp && set +a
    PYTHONUTF8=1 uv run --no-sync pytest tests/integration/test_files_create_folder_live.py \\
        -m integration -s -q

Without that environment it skips.
"""

import dataclasses
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import unquote

import canary_world as cw
import httpx
import pytest
import topology
from lxml import etree

from mcp_connector import config
from mcp_connector.config import normalize_base_url
from mcp_connector.errors import REASON_PERMISSION_DENIED, ConflictError, ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud import exclusion as exclusion_core
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import MODE_APPAPI, Credentials
from mcp_connector.tools import files as files_tools

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

STAMP = uuid.uuid4().hex[:8]
#: Everything this run creates in the home of the measured account lies below this folder.
P = f"/ordner31-{STAMP}"
DATA = "/var/www/html/data"
WRONG_SECRET = "0" * 64
REQUIRED = {
    "base_url": "NC_MCP_URL",
    "app_id": "APP_ID",
    "app_secret": "APP_SECRET",
    "app_version": "APP_VERSION",
    "alice": "NC_MCP_TEST_USER",
    "alice_password": "NC_MCP_TEST_APP_PASSWORD",
    "bob": "NC_MCP_TEST_USER2",
    "bob_password": "NC_MCP_TEST_APP_PASSWORD2",
    "shared_dir": "NC_MCP_TEST_SHARED_DIR",
}

_DAV = "{DAV:}"
_OC = "{http://owncloud.org/ns}"
_PROPS = (
    b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
    b"<d:prop><oc:fileid/><oc:permissions/><d:quota-used-bytes/></d:prop></d:propfind>"
)

type Seen = tuple[str, str, int]
type Watcher = Callable[[str, str, int], None]


# --- protocol -------------------------------------------------------------------------

_first_line_of_test = True


@pytest.fixture(autouse=True)
def _own_line() -> None:
    """The first line of a test starts on a line of its own, after the dot of the last one."""
    global _first_line_of_test
    _first_line_of_test = True


def record(line: str) -> None:
    """Write one protocol line to stdout; the run pipes it into the raw protocol (``-s``)."""
    global _first_line_of_test
    lead = "\n" if _first_line_of_test else ""
    _first_line_of_test = False
    sys.stdout.write(f"{lead}{line.rstrip()}\n")
    sys.stdout.flush()


def exact(exc: ToolError) -> tuple[str, str, str, str]:
    return (type(exc).__name__, exc.message, exc.hint, exc.reason)


def renamed(exc: ToolError, old: str, new: str) -> tuple[str, str, str, str]:
    """``exact`` with one path replaced, to compare two refusals that name their path."""
    return (
        type(exc).__name__,
        exc.message.replace(old, new),
        exc.hint.replace(old, new),
        exc.reason,
    )


def told(exc: ToolError) -> str:
    return f"{type(exc).__name__} reason={exc.reason} message={exc.message!r}"


def answered(answer: dict[str, Any]) -> str:
    return json.dumps(answer, ensure_ascii=True, sort_keys=True)


def calls(seen: list[Seen]) -> str:
    return ",".join(f"{method}:{status}" for method, _, status in seen) or "keine"


def methods(seen: list[Seen], method: str) -> list[int]:
    return [status for name, _, status in seen if name == method]


# --- the run --------------------------------------------------------------------------


@dataclasses.dataclass
class Run:
    """The accounts, the two harnesses and what the teardown has to undo."""

    env: dict[str, str] = dataclasses.field(repr=False)
    version: str
    harness: cw.Harness
    harness_bob: cw.Harness
    tagged: list[str] = dataclasses.field(default_factory=list)
    tag_created: str = ""
    shares: list[str] = dataclasses.field(default_factory=list)
    quota_before: str | None = None
    strays: list[tuple[str, str]] = dataclasses.field(default_factory=list)

    @property
    def alice(self) -> str:
        return self.env["alice"]

    @property
    def bob(self) -> str:
        return self.env["bob"]

    def of(self, user: str) -> cw.Harness:
        return self.harness if user == self.alice else self.harness_bob

    def other(self, user: str) -> str:
        return self.bob if user == self.alice else self.alice


def in_container(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "exec", topology.NC_CONTAINER, *argv],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def on_disk(user: str, path: str, kind: str = "-d") -> bool:
    """Whether the container's file system holds ``path`` in the home of ``user``.

    ``kind`` is the flag of ``test``: ``-d`` a folder, ``-f`` a file, ``-e`` anything.
    """
    return in_container("test", kind, f"{DATA}/{user}/files{path}").returncode == 0


def props(harness: cw.Harness, path: str, depth: str = "0") -> tuple[int, list[dict[str, str]]]:
    """``(status, [{fileid, permissions, used}])`` of a PROPFIND with the app password."""
    response = harness.request(
        "PROPFIND",
        harness.dav_url(path),
        headers={"Depth": depth, "Content-Type": "application/xml"},
        content=_PROPS,
    )
    if response.status_code != 207:
        return response.status_code, []
    found = [
        {
            "fileid": (entry.findtext(f".//{_OC}fileid") or "").strip(),
            "permissions": (entry.findtext(f".//{_OC}permissions") or "").strip(),
            "used": (entry.findtext(f".//{_DAV}quota-used-bytes") or "").strip(),
        }
        for entry in etree.fromstring(response.content).iter(f"{_DAV}response")
    ]
    return 207, found


def fileid_of(harness: cw.Harness, path: str) -> str:
    status, found = props(harness, path)
    assert status == 207, f"no entry at {path}: {status}"
    assert found[0]["fileid"], f"no fileid for {path}"
    return found[0]["fileid"]


def quota_setting(user: str) -> str:
    return cw.occ("user:setting", user, "files", "quota", check_status=False)


def restore_quota(run: Run) -> None:
    """Put the quota of alice back to what ``quota_before`` read (an absent setting stays so)."""
    if run.quota_before is None:
        return
    if "does not exist" in run.quota_before:
        cw.occ("user:setting", run.alice, "files", "quota", "--delete", check_status=False)
    else:
        cw.occ("user:setting", run.alice, "files", "quota", run.quota_before)
    run.quota_before = None


def baseline(run: Run) -> dict[str, str]:
    """What must be the same before and after: files, trash, quota, tags, shares of alice."""
    harness = run.harness
    status, entries = props(harness, "/", depth="1")
    tags = cw.tag_ids()
    assigned = sum(len(harness.tagged_fileids(tag_id)[1]) for tag_id in tags)
    shares = harness.ocs_get(cw.SHARES_API)
    try:
        share_count = str(len(shares.json()["ocs"]["data"]))
    except (ValueError, KeyError, TypeError):
        share_count = f"status {shares.status_code}"
    return {
        "dateien_alice": str(len(entries) - 1) if status == 207 else f"status {status}",
        "papierkorb_alice": str(len(harness.trash_entries(""))),
        "kontingent_alice": quota_setting(run.alice),
        "tag_zuordnungen": f"tags={','.join(tags) or 'keine'} zuordnungen={assigned}",
        "freigaben_alice": share_count,
    }


def _environment() -> dict[str, str]:
    values = {key: (os.environ.get(name) or "").strip() for key, name in REQUIRED.items()}
    missing = sorted(REQUIRED[key] for key, value in values.items() if not value)
    if missing:
        pytest.skip(f"no ExApp topology configured (missing: {', '.join(missing)})")
    values["aa_version"] = (os.environ.get("AA_VERSION") or "").strip()
    values["base_url"] = normalize_base_url(values["base_url"])
    return values


def _teardown(run: Run) -> None:
    """Remove everything of this run through the harness, never through the connector."""
    for fileid in run.tagged:
        cw.untag(fileid)
    if run.tag_created:
        cw.occ("tag:delete", run.tag_created, check_status=False)
    for share_id in run.shares:
        run.harness.ocs_delete(f"{cw.SHARES_API}/{share_id}")
    restore_quota(run)
    for user, path in run.strays:
        if run.of(user).stat(path)[0] == 207:
            run.of(user).delete(path)
    run.harness.delete(P)
    run.harness.purge_trash(STAMP)
    run.harness_bob.purge_trash(STAMP)


@pytest.fixture(scope="module")
def run() -> Iterator[Run]:
    env = _environment()
    live = cw.live_env()
    harness = cw.Harness(live)
    harness_bob = cw.Harness(cw.LiveEnv(env["base_url"], env["bob"], env["bob_password"]))
    status = json.loads(cw.occ("status", "--output=json"))
    state = Run(env=env, version=str(status["version"]), harness=harness, harness_bob=harness_bob)
    listing = in_container("ls", "-d", f"{DATA}/{state.alice}/files")
    record(f"LAUF ordner31 stempel={STAMP} wurzel={P} container={topology.NC_CONTAINER}")
    record(f"VERSION nc={state.version} versionstring={status['versionstring']} (occ status)")
    record(f"DATENPFAD ls -d exit={listing.returncode} ausgabe={listing.stdout.strip()}")
    assert listing.returncode == 0, listing.stderr
    before = baseline(state)
    exclusion_core.clear_cache()
    capabilities.clear_cache()
    try:
        harness.mkcol(P)
        yield state
    finally:
        _teardown(state)
        after = baseline(state)
        left = harness.stat(P)[0]
        record(f"RUECKBAU PROPFIND {P}: {left}")
        for key, value in before.items():
            same = "ja" if after[key] == value else "nein"
            record(f"BASELINE {key} vorher={value} nachher={after[key]} gleich={same}")
        harness.close()
        harness_bob.close()
        exclusion_core.clear_cache()
    assert left == 404, f"{P} is still there: {left}"
    assert before == after, f"baseline differs: {before} / {after}"


class Case:
    """One protocol line: collects the calls and the raw values, records, then asserts."""

    def __init__(self, run: Run, label: str, user: str | None = None) -> None:
        self.run = run
        self.label = label
        self.user = user or run.alice
        self.seen: list[Seen] = []
        self.notes: list[str] = []
        self.ok = True

    def expect(self, ok: bool, note: str) -> None:
        self.notes.append(note if ok else f"DEVIATION {note}")
        self.ok = self.ok and ok

    def note(self, note: str) -> None:
        self.notes.append(note)

    def __enter__(self) -> "Case":
        return self

    def __exit__(self, kind: object, exc: BaseException | None, trace: object) -> None:
        if exc is not None:
            self.expect(False, f"{type(exc).__name__}: {str(exc)[:300]}")
        verdict = "ok" if self.ok else "befund"
        record(
            f"ORDNER {self.label} nc={self.run.version} nutzer={self.user} "
            f"status={calls(self.seen)} ergebnis={verdict} | {'; '.join(self.notes)}"
        )
        if exc is None:
            assert self.ok, f"{self.label}: {'; '.join(self.notes)}"


def appapi_clients(
    run: Run, user: str, seen: list[Seen], watcher: Watcher | None = None, secret: str = ""
) -> NcClients:
    """Impersonating clients for one call: ``APP_SECRET`` is the only credential.

    Mirrors ``deps._credentials_from_appapi`` like ``test_exapp_dav_matrix.py`` does. The
    response hook notes the method, the path below the home and the status of every answer.
    """
    prefix = f"{dav.DAV_FILES_PREFIX}{user}"

    async def hook(response: httpx.Response) -> None:
        path = unquote(response.request.url.path)
        method = response.request.method
        if prefix in path:
            below = path.split(prefix, 1)[1] or "/"
        else:
            _, found, rest = path.partition("/remote.php/dav/")
            method, below = f"{rest.split('/', 1)[0] if found else 'ocs'}.{method}", ""
        seen.append((method, below, response.status_code))
        if watcher is not None:
            watcher(method, below, response.status_code)

    return NcClients(
        client=httpx.AsyncClient(
            follow_redirects=False, timeout=30.0, event_hooks={"response": [hook]}
        ),
        creds=Credentials(
            base_url=run.env["base_url"],
            user=user,
            secret=secret or run.env["app_secret"],
            mode=MODE_APPAPI,
            app_id=run.env["app_id"],
            app_version=run.env["app_version"],
            aa_version=run.env["aa_version"],
        ),
    )


@asynccontextmanager
async def measured(
    case: Case, watcher: Watcher | None = None, secret: str = ""
) -> AsyncIterator[NcClients]:
    """The clients of one tool call: a fresh guard, no cached tag ids, calls into ``case``."""
    exclusion_core.clear_cache()
    capabilities.clear_cache()
    clients = appapi_clients(case.run, case.user, case.seen, watcher, secret)
    async with clients.client:
        yield clients


async def create(
    case: Case,
    path: str,
    *,
    parents: bool = False,
    watcher: Watcher | None = None,
    secret: str = "",
) -> dict[str, Any]:
    async with measured(case, watcher, secret) as clients:
        return await files_tools.create_folder(clients, path=path, parents=parents)


async def refusal(call: Awaitable[dict[str, Any]]) -> ToolError:
    """The ToolError a call raises; a call that answers fails the case."""
    try:
        answer = await call
    except ToolError as exc:
        return exc
    raise AssertionError(f"expected a refusal, got an answer: {answered(answer)}")


# --- controls. Everything below them is worthless without them. ------------------------


async def test_the_measuring_process_holds_no_nextcloud_app_password(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control one: the identity cannot come from a Basic app password or a static bearer."""
    monkeypatch.delenv("NC_MCP_APP_PASSWORD", raising=False)
    monkeypatch.delenv("NC_MCP_STATIC_BEARER", raising=False)
    clients = appapi_clients(run, run.alice, [])
    await clients.client.aclose()
    held = [
        name for name in ("NC_MCP_APP_PASSWORD", "NC_MCP_STATIC_BEARER") if os.environ.get(name)
    ]
    ok = (
        not held
        and clients.creds.mode == MODE_APPAPI
        and clients.creds.secret == run.env["app_secret"]
        and clients.creds.secret not in (run.env["alice_password"], run.env["bob_password"])
    )
    record(
        f"KONTROLLE 1 nc={run.version} nutzer={run.alice} ergebnis={'ok' if ok else 'befund'} | "
        f"mode={clients.creds.mode} NC_MCP_APP_PASSWORD or NC_MCP_STATIC_BEARER set in the "
        f"process={held or 'no'}; the credential is APP_SECRET and no app password"
    )
    assert ok


async def test_a_wrong_app_secret_creates_nothing(run: Run) -> None:
    """Control two: with 64 zeros as the secret every answer is a 401 and nothing exists.

    Two calls: the tool, whose first request is the tag listing of the guard, and the
    folder request of the client alone, which ends in the named 401 sentence of ``dav``.
    """
    target = f"{P}/kontrolle-falsch"
    case = Case(run, "kontrolle-2")
    seen = case.seen
    async with measured(case, secret=WRONG_SECRET) as clients:
        tool = await refusal(files_tools.create_folder(clients, path=target))
    async with measured(case, secret=WRONG_SECRET) as clients:
        bare = await refusal(dav.make_folder(clients.client, clients.creds, target))
    statuses = {status for _, _, status in seen}
    ok = (
        statuses == {401}
        and bare.message == "Nextcloud rejected the app password."
        and not on_disk(run.alice, target, "-e")
    )
    record(
        f"KONTROLLE 2 nc={run.version} nutzer={run.alice} status={calls(seen)} "
        f"ergebnis={'ok' if ok else 'befund'} | tool: {told(tool)}; "
        f"dav.make_folder: {told(bare)}; file system has {target}="
        f"{'yes' if on_disk(run.alice, target, '-e') else 'no'}"
    )
    assert ok


# --- the ten core cases ---------------------------------------------------------------


async def test_a_free_path_is_created_with_the_id_nextcloud_reports(run: Run) -> None:
    target = f"{P}/frei"
    with Case(run, "frei") as case:
        answer = await create(case, target)
        fileid = fileid_of(run.harness, target)
        case.expect(answer.get("created") is True, answered(answer))
        case.expect(
            answer.get("id") == f"file:{fileid}", f"oc:fileid by app password PROPFIND={fileid}"
        )
        case.expect(methods(case.seen, "MKCOL") == [201], "one MKCOL 201")
        late = methods(case.seen, "PROPFIND")
        case.note(f"id read by a later PROPFIND {late}" if late else "id from oc-fileid, no read")
        case.expect(on_disk(run.alice, target), f"file system test -d {target}")


async def test_an_existing_folder_is_a_success_with_the_same_id(run: Run) -> None:
    target = f"{P}/frei"
    with Case(run, "vorhanden") as case:
        fileid = fileid_of(run.harness, target)
        answer = await create(case, target)
        case.expect(answer.get("created") is False, answered(answer))
        case.expect(
            answer.get("id") == f"file:{fileid}", f"oc:fileid by app password PROPFIND={fileid}"
        )
        case.expect(methods(case.seen, "MKCOL") == [405], "MKCOL 405")
        case.expect(methods(case.seen, "PROPFIND") == [207], "PROPFIND 207")


async def test_a_file_at_the_path_is_a_conflict(run: Run) -> None:
    """Also assumption A5: what a PROPFIND below a file answers while a chain is counted."""
    target = f"{P}/datei.txt"
    content = f"ordner31 {STAMP}\n"
    run.harness.put(target, content.encode())
    with Case(run, "datei") as case:
        plain = await refusal(create(case, target))
        case.expect(isinstance(plain, ConflictError), told(plain))
        case.expect("A file, not a folder" in plain.message, "sentence of a file at the path")
        before = len(case.seen)
        below = await refusal(create(case, f"{target}/x/y", parents=True))
        under_file = [
            f"{method} {path.removeprefix(P)}:{status}"
            for method, path, status in case.seen[before:]
            if method == "PROPFIND"
        ]
        case.expect(isinstance(below, ConflictError), f"chain below the file: {told(below)}")
        case.expect(
            all(status in (404, 409) for _, path, status in case.seen[before:] if "/x" in path),
            f"A5 PROPFIND below the file: {', '.join(under_file)}",
        )
        case.expect(not methods(case.seen[before:], "MKCOL"), "no MKCOL below the file")
        case.expect(
            run.harness.get_text(target) == (200, content), "file unchanged (GET with app password)"
        )
        case.expect(on_disk(run.alice, target, "-f"), f"file system test -f {target}")


async def test_a_missing_parent_without_parents_is_parent_missing(run: Run) -> None:
    target = f"{P}/fehlt/kind"
    with Case(run, "eltern-fehlt") as case:
        error = await refusal(create(case, target))
        case.expect(exact(error) == exact(dav.parent_missing(target)), told(error))
        case.expect(methods(case.seen, "MKCOL") == [409], "one MKCOL 409")
        case.expect(not on_disk(run.alice, f"{P}/fehlt", "-e"), f"file system without {P}/fehlt")


async def test_a_chain_names_every_folder_it_created(run: Run) -> None:
    chain = [f"{P}/k", f"{P}/k/a", f"{P}/k/a/b", f"{P}/k/a/b/c"]
    with Case(run, "kette") as case:
        answer = await create(case, chain[-1], parents=True)
        fileid = fileid_of(run.harness, chain[-1])
        case.expect(answer.get("created") is True, answered(answer))
        case.expect(answer.get("created_folders") == chain, "created_folders top down")
        case.expect(
            answer.get("id") == f"file:{fileid}", f"oc:fileid by app password PROPFIND={fileid}"
        )
        case.expect(methods(case.seen, "MKCOL") == [201] * 4, "four MKCOL 201")
        case.expect(
            all(on_disk(run.alice, path) for path in chain), "file system: all four folders"
        )


async def test_eleven_missing_folders_create_nothing(run: Run) -> None:
    target = f"{P}/d/" + "/".join(str(number) for number in range(1, 11))
    with Case(run, "deckel") as case:
        error = await refusal(create(case, target, parents=True))
        case.expect("needs 11 new folders" in error.message, told(error))
        case.expect("at most 10" in error.message, "names the cap of 10")
        case.expect(not methods(case.seen, "MKCOL"), "no MKCOL")
        case.expect(len(methods(case.seen, "PROPFIND")) == 12, "twelve PROPFIND of the count")
        case.expect(not on_disk(run.alice, f"{P}/d", "-e"), f"file system without {P}/d")


async def test_a_race_in_the_chain_names_what_was_created(run: Run) -> None:
    """Another writer puts a file where the second folder of the chain was about to go."""
    first, second, target = f"{P}/w", f"{P}/w/x", f"{P}/w/x/y"

    def other_writer(method: str, path: str, status: int) -> None:
        if (method, path, status) == ("MKCOL", first, 201):
            run.harness.put(second, b"other writer\n")

    with Case(run, "teilabbruch-wettlauf") as case:
        error = await refusal(create(case, target, parents=True, watcher=other_writer))
        case.expect(isinstance(error, ConflictError), told(error))
        case.expect(
            error.message.endswith(f"Already created in this call and left in place: {first}."),
            "the addition names what was created",
        )
        case.expect(on_disk(run.alice, first), f"file system test -d {first}")
        case.expect(on_disk(run.alice, second, "-f"), f"file system test -f {second}")
        case.expect(not on_disk(run.alice, target, "-e"), f"file system without {target}")


async def test_a_read_only_share_refuses_with_no_permission(run: Run) -> None:
    """D-31-05, D-31-07: the account that received the share without create rights."""
    shared = f"/{run.env['shared_dir']}"
    views = {user: props(run.of(user), shared) for user in (run.alice, run.bob)}
    rights = {
        user: found[0]["permissions"] if status == 207 else f"status {status}"
        for user, (status, found) in views.items()
    }
    readers = [
        user
        for user, (status, _) in views.items()
        if status == 207 and not set(rights[user]) & {"C", "K"}
    ]
    assert readers, f"nobody sees {shared} without create rights: {rights}"
    viewer = readers[0]
    owner = run.other(viewer)
    single, chain = f"{shared}/neu-{STAMP}", f"{shared}/k-{STAMP}/x"
    run.strays += [(owner, single), (owner, f"{shared}/k-{STAMP}")]
    with Case(run, "geteilt-nur-lesen", viewer) as case:
        for target, parents in ((single, False), (chain, True)):
            error = await refusal(create(case, target, parents=parents))
            case.expect(error.message.startswith("No permission to create a folder"), told(error))
            case.expect(error.reason == REASON_PERMISSION_DENIED, "reason permission_denied")
            case.expect(
                "Already created" not in error.message, "without the addition Already created"
            )
        case.expect(methods(case.seen, "MKCOL") == [403, 403], "two MKCOL 403")
        case.expect(
            not set(rights[viewer]) & {"C", "K"},
            f"oc:permissions of {shared} by app password PROPFIND: {viewer}={rights[viewer]} "
            f"{owner}={rights[owner]}",
        )
        positive = f"{P}/eigen-{STAMP}" if viewer == run.alice else f"/eigen-{STAMP}"
        run.strays.append((viewer, positive))
        made = await create(case, positive)
        case.expect(
            made.get("created") is True, f"positive control in the own home: {answered(made)}"
        )
        case.expect(
            not on_disk(owner, single, "-e") and not on_disk(owner, f"{shared}/k-{STAMP}", "-e"),
            f"file system of {owner} without neu-{STAMP} and k-{STAMP}",
        )


async def test_a_tagged_folder_answers_like_an_invented_parent(run: Run) -> None:
    locked, free, invented = f"{P}/gesperrt", f"{P}/offen", f"{P}/erfunden"
    run.harness.mkcol(locked)
    run.harness.mkcol(free)
    locked_id = fileid_of(run.harness, locked)
    tag_id, created = cw.ensure_tag()
    if created:
        run.tag_created = tag_id
    with Case(run, "kein-ki") as case:
        cw.tag(locked_id)
        run.tagged.append(locked_id)
        try:
            single = await refusal(create(case, f"{locked}/neu"))
            chain = await refusal(create(case, f"{locked}/a/b", parents=True))
            tagged_calls = list(case.seen)
            real = await refusal(create(case, f"{invented}/neu"))
            case.expect(
                renamed(single, locked, invented) == exact(real),
                f"tagged: {told(single)}; invented: {told(real)}; equal once the folder is renamed",
            )
            case.expect(
                exact(chain) == exact(dav.parent_missing(f"{locked}/a/b")),
                f"tagged chain: {told(chain)}",
            )
            case.expect(
                not methods(tagged_calls, "MKCOL") and not methods(tagged_calls, "PROPFIND"),
                f"tagged calls without MKCOL and PROPFIND on files ({calls(tagged_calls)})",
            )
            case.expect(
                not on_disk(run.alice, f"{locked}/neu", "-e")
                and not on_disk(run.alice, f"{locked}/a", "-e")
                and not on_disk(run.alice, invented, "-e"),
                "file system without gesperrt/neu, gesperrt/a and erfunden",
            )
            positive = await create(case, f"{free}/neu")
            case.expect(
                positive.get("created") is True and on_disk(run.alice, f"{free}/neu"),
                f"positive control offen/neu: {answered(positive)}",
            )
        finally:
            cw.untag(locked_id)


async def test_the_sandbox_root_is_never_created(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    root, absent = f"{P}/root", f"{P}/root-fehlt"
    run.harness.mkcol(root)
    with Case(run, "sandbox") as case:
        monkeypatch.setenv(config.ENV_FILES_ROOT, root)
        refused = await refusal(create(case, "/"))
        case.expect("root folder" in refused.message, told(refused))
        case.expect(not case.seen, "root refusal without a single request")
        made = await create(case, "/a")
        case.expect(
            made.get("created") is True and on_disk(run.alice, f"{root}/a"),
            f"/a is on the file system at {root}/a: {answered(made)}",
        )
        monkeypatch.setenv(config.ENV_FILES_ROOT, absent)
        before = len(case.seen)
        missing = await refusal(create(case, "/a", parents=True))
        case.expect(
            exact(missing) == exact(dav.parent_missing(f"{absent}/a")),
            f"missing root: {told(missing)}",
        )
        case.expect(not methods(case.seen[before:], "MKCOL"), "no MKCOL with a missing root")
        case.expect(not on_disk(run.alice, absent, "-e"), f"file system without {absent}")
        case.expect(not on_disk(run.alice, "/a", "-e"), "file system without /a above the root")


# --- the five edge cases --------------------------------------------------------------

_LOCK_BODY = (
    b'<?xml version="1.0"?><d:lockinfo xmlns:d="DAV:"><d:lockscope><d:exclusive/>'
    b"</d:lockscope><d:locktype><d:write/></d:locktype><d:owner>ordner31</d:owner></d:lockinfo>"
)
_LOCK_TOKEN = re.compile(r"opaquelocktoken:[0-9A-Za-z-]+")
#: The sentence of the one branch that names no status of its own (``dav._check_mkcol``).
_UNNAMED = ("unexpected status", "with status ")


def named(error: ToolError) -> bool:
    """Whether a refusal is one of the named sentences and not the rest for an odd status."""
    return not any(fragment in error.message for fragment in _UNNAMED)


def one_line(text: str, limit: int = 200) -> str:
    """A response body as one short line, with every lock token replaced by a placeholder."""
    flat = " ".join(_LOCK_TOKEN.sub("opaquelocktoken:<token>", text).split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


async def test_a_refused_name_inside_a_chain_is_a_named_refusal(run: Run) -> None:
    kept, target = f"{P}/n/ok", f"{P}/n/ok/.htaccess/x"
    with Case(run, "teilabbruch-name") as case:
        error = await refusal(create(case, target, parents=True))
        case.expect(named(error), told(error))
        case.expect(
            error.message.startswith(dav.name_rejected(target).message),
            "the sentence of a refused folder name, for the target",
        )
        left = [path for path in (f"{P}/n", kept) if on_disk(run.alice, path)]
        case.expect(
            all(path in error.message for path in left)
            and ("Already created" in error.message) == bool(left),
            f"file system holds {left or 'nothing of the chain'}, and the sentence says so",
        )
        case.expect(not on_disk(run.alice, f"{kept}/.htaccess", "-e"), "no .htaccess on disk")


async def test_refused_names_end_in_a_named_refusal_or_a_real_folder(run: Run) -> None:
    """One call per name; the line ``NAME`` carries the calls and the outcome of each."""
    base = f"{P}/namen"
    run.harness.mkcol(base)
    names = [".htaccess", "x.part", "x.filepart", "con", "ende-leer ", "ende-punkt."]
    with Case(run, "namen") as case:
        for name in names:
            part = Case(run, "namen")
            wanted = f"{base}/{name}"
            try:
                answer = await create(part, wanted)
            except ToolError as error:
                ok = named(error) and not on_disk(run.alice, wanted, "-e")
                outcome = f"{told(error)}; file system has it=no" if ok else told(error)
            else:
                ok = answer.get("created") is True and on_disk(run.alice, str(answer["path"]))
                outcome = f"{answered(answer)}; file system test -d of the answered path"
            record(
                f"NAME {name!r} nc={run.version} nutzer={run.alice} status={calls(part.seen)} "
                f"ergebnis={'ok' if ok else 'befund'} | {outcome}"
            )
            case.seen += [entry for entry in part.seen if entry[0] == "MKCOL"]
            case.expect(ok, f"{name!r}: {'named refusal or real folder' if ok else outcome}")
        listing = in_container("ls", "-1A", f"{DATA}/{run.alice}/files{base}")
        case.note(f"file system ls -1A {base}: {sorted(listing.stdout.splitlines())!r}")


async def test_a_trailing_space_inside_a_chain_is_recorded(run: Run) -> None:
    """Not a case of the plan: a folder name that ends in a space as a link of a chain.

    The first live run on 35.0.0 showed the tool creating the folder without the space and
    then failing below the name with it. That is an open finding of plan 31-05 for the
    owner, so this records what happens (``ZUSATZ ... befund=<ja|nein>``) and asserts
    nothing: a green run must not hide it and a red run must not block the measured cases.
    """
    base = f"{P}/zusatz"
    run.harness.mkcol(base)
    part = Case(run, "zusatz")
    wanted = f"{base}/mitte-leer /kind"
    try:
        answer = await create(part, wanted, parents=True)
        outcome, claimed = answered(answer), list(answer.get("created_folders") or [])
    except ToolError as error:
        outcome = told(error)
        claimed = [f"{base}/mitte-leer "] if "Already created" in error.message else []
    listing = in_container("ls", "-1A", f"{DATA}/{run.alice}/files{base}")
    truthful = all(on_disk(run.alice, path) for path in claimed) and "ToolError" not in outcome
    record(
        f"ZUSATZ name-mit-leerzeichen-in-kette nc={run.version} nutzer={run.alice} "
        f"status={calls(part.seen)} befund={'nein' if truthful else 'ja'} | {outcome}; "
        f"named as created: {claimed!r}; file system ls -1A {base}: "
        f"{sorted(listing.stdout.splitlines())!r}"
    )


def lock(harness: cw.Harness, path: str, user_lock: bool = False) -> tuple[int, str, str]:
    """``(status, token, body)`` of one LOCK, exclusive and of depth infinity.

    ``user_lock`` sends the form of the ``files_lock`` app instead: no body, one extra field.
    """
    fields = {"Depth": "infinity", "Timeout": "Second-600"}
    fields |= {"X-User-Lock": "1"} if user_lock else {"Content-Type": "application/xml"}
    response = harness.request(
        "LOCK", harness.dav_url(path), headers=fields, content=b"" if user_lock else _LOCK_BODY
    )
    token = response.headers.get("Lock-Token", "")
    return response.status_code, token, one_line(response.text)


def unlock(harness: cw.Harness, path: str, token: str, user_lock: bool = False) -> int:
    fields = {"X-User-Lock": "1"} if user_lock else {}
    if token:
        fields["Lock-Token"] = token
    return harness.request("UNLOCK", harness.dav_url(path), headers=fields).status_code


async def test_a_locked_folder_is_refused_or_not_reproducible(run: Run) -> None:
    """423: three ways to lock a folder; without a 423 the case says ``UNGEMESSEN``."""
    shared, own, by_app = (f"{P}/lock-{STAMP}-{letter}" for letter in "abc")
    for folder in (shared, own, by_app):
        run.harness.mkcol(folder)
    answer = run.harness.ocs_post(
        cw.SHARES_API,
        {"path": shared, "shareType": cw.SHARE_USER, "shareWith": run.bob, "permissions": 31},
    )
    try:
        run.shares.append(str(answer.json()["ocs"]["data"]["id"]))
    except (ValueError, KeyError, TypeError):
        record(f"SPERRE freigabe an {run.bob} status={answer.status_code} (keine Freigabe)")
    mount = f"/{shared.rsplit('/', 1)[-1]}"
    attempts = [
        ("bob-ueber-freigabe", run.harness_bob, mount, shared, False),
        ("alice-eigenes-token", run.harness, own, own, False),
        ("alice-x-user-lock", run.harness, by_app, by_app, True),
    ]
    with Case(run, "sperre-423") as case:
        locked_out = False
        for label, harness, lock_path, folder, user_lock in attempts:
            status, token, body = lock(harness, lock_path, user_lock)
            before = len(case.seen)
            try:
                made = await create(case, f"{folder}/kind")
                outcome = answered(made)
            except ToolError as error:
                outcome = told(error)
                case.expect(named(error), f"{label}: {outcome}")
                if 423 in methods(case.seen[before:], "MKCOL"):
                    locked_out = True
                    case.expect(
                        "is locked in Nextcloud" in error.message
                        and not on_disk(run.alice, f"{folder}/kind", "-e"),
                        f"{label}: MKCOL 423, sentence of the lock, nothing on disk",
                    )
            finally:
                released = unlock(harness, lock_path, token, user_lock)
            record(
                f"SPERRE versuch={label} nc={run.version} LOCK status={status} "
                f"token={'ja' if token else 'nein'} UNLOCK status={released} "
                f"werkzeug status={calls(case.seen[before:])} | LOCK antwort: {body or 'leer'}; "
                f"werkzeug: {outcome}"
            )
            case.note(f"{label}: LOCK {status}, MKCOL {methods(case.seen[before:], 'MKCOL')}")
        if not locked_out:
            record(
                "UNGEMESSEN sperre-423 grund=kein LOCK dieser Instanz fuehrte zu MKCOL 423 "
                "(drei Versuche, Rohausgabe in den Zeilen SPERRE); der Zweig 423 ist nur per "
                "Unit-Test belegt"
            )
            case.note("423 not reproducible on this instance")


async def test_a_parent_deleted_after_the_count_is_parent_missing(run: Run) -> None:
    """404: the parent vanishes between the count and the write; plus the source of sabre."""
    parent = f"{P}/geloescht-{STAMP}"
    target = f"{parent}/kind"
    run.harness.mkcol(parent)

    def remover(method: str, path: str, status: int) -> None:
        if (method, path, status) == ("PROPFIND", parent, 207):
            run.harness.delete(parent)

    with Case(run, "mkcol-404") as case:
        error = await refusal(create(case, target, parents=True, watcher=remover))
        written = methods(case.seen, "MKCOL")
        case.expect(exact(error) == exact(dav.parent_missing(target)), told(error))
        case.expect(written in ([404], [409]), f"MKCOL after the parent was deleted: {written}")
        case.expect(not on_disk(run.alice, parent, "-e"), f"file system without {parent}")
        source = in_container(
            "awk",
            "/function httpMkcol/{on=1} on&&/NotFound|Conflict|createCollection/"
            '{print NR": "$0} on&&/^    }/{exit}',
            "/var/www/html/3rdparty/sabre/dav/lib/DAV/CorePlugin.php",
        )
        lines = " / ".join(" ".join(line.split()) for line in source.stdout.splitlines())
        record(
            f"QUELLE mkcol-404 nc={run.version} CorePlugin.php httpMkcol exit={source.returncode} "
            f"zeilen mit NotFound, Conflict oder createCollection: {lines or 'keine'}"
        )
        if 404 not in written:
            record(
                f"UNGEMESSEN mkcol-404 grund=der MKCOL unter einem geloeschten Elternordner "
                f"antwortet {written}, nicht 404; httpMkcol in CorePlugin.php: "
                f"{lines or 'keine Zeile mit NotFound'}; der Zweig 404 ist nur per Unit-Test belegt"
            )
            case.note("404 not reproducible on this instance")


async def test_a_tight_quota_creates_and_an_exhausted_one_is_named(run: Run) -> None:
    """Three quotas: used plus 4096 bytes, used plus 1024 bytes and one byte.

    Nextcloud asks for 4096 free bytes before it creates a folder (``QuotaPlugin`` of the
    dav app, measured on 35.0.0), so the first quota has to create and the other two may
    answer 507. Whatever the instance answers, the tool either created the folder or says
    the named sentence of a full quota, and the line carries which.
    """
    base = f"{P}/q-{STAMP}"
    run.harness.mkcol(base)
    used = int(props(run.harness, "/")[1][0]["used"] or 0)
    steps = [
        ("knapp", f"{used + 4096} B", "used plus 4096 B", True),
        ("eng", f"{used + 1024} B", "used plus 1024 B", False),
        ("voll", "1 B", "1 B", False),
    ]
    with Case(run, "kontingent-knapp") as case:
        run.quota_before = quota_setting(run.alice)
        was = run.quota_before
        case.note(f"used {used} B, quota before: {was}")
        try:
            for name, quota, label, must_create in steps:
                cw.occ("user:setting", run.alice, "files", "quota", quota)
                target = f"{base}/{name}"
                before = len(case.seen)
                try:
                    made = await create(case, target)
                except ToolError as error:
                    case.expect(
                        not must_create
                        and error.message.startswith("Not enough space in Nextcloud")
                        and methods(case.seen[before:], "MKCOL") == [507]
                        and not on_disk(run.alice, target, "-e"),
                        f"quota {label}: MKCOL {methods(case.seen[before:], 'MKCOL')} "
                        f"{told(error)}; nothing on disk",
                    )
                else:
                    case.expect(
                        made.get("created") is True and on_disk(run.alice, target),
                        f"quota {label}: {answered(made)}; on disk",
                    )
        finally:
            restore_quota(run)
            case.expect(quota_setting(run.alice) == was, f"quota back to: {was}")

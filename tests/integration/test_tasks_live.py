"""Live proof of the tasks bundle under AppAPI impersonation (plan 32-05b, D-32-11, D-32-12).

The question: do ``tasks_search``, ``tasks_read`` and ``tasks_create`` keep every promise of
phase 32 against a real Nextcloud when the only credential in play is ``APP_SECRET`` and the
user id travels inside the AppAPI header, with and without the Tasks app. Every measured call
builds its credentials with ``mode="appapi"``. The app passwords of the two test accounts are
used by the harness alone: for the counter checks, the scaffolding and the removal, never for
a measured call.

Every case writes exactly one line::

    AUFGABE <case> nc=<version> nutzer=<uid> status=<calls> ergebnis=<ok|befund> | <raw values>

``status`` lists every answer the measured client received as ``METHOD:status``; a request
outside the calendar home of the user carries its area in front (``ocs.GET:200``). The hook
stores the method, the path below the home and the status, nothing else. A case records its
line first and asserts afterwards. Each statement "nothing was written" is checked with a
pattern the implementation does not use: the rows of the table ``calendarobjects`` read by
PHP in the container, or the raw object read with the app password of its owner.

Everything the run creates is named ``p32live-<stamp>`` and removed by the harness in the
module teardown (32-RULES.md section 7): shares withdrawn, every list deleted with
``X-NC-CalDAV-No-Trashbin: 1``, the calendar trash bin of both accounts emptied of this run,
the Deck board deleted, the two TASK-03 accounts and the account of D-32-18 (plan 32-09) deleted
with ``occ user:delete``.
``BASELINE`` lines per account (``calendars``, ``calendarobjects`` with and without
``deleted_at``, ``calendarsubscriptions``, ``dav_shares``) before and after must be equal.

The expected state of the Tasks app comes as ``NC_MCP_EXPECT_TASKS_APP`` (``0`` or ``1``) and is
read a second time with ``occ app:list`` in the container; a contradiction fails the run.

Run it against the Nextcloud 32 or 34 route (``compose.exapp.yml``, default names of
``topology.py``), without the Tasks app::

    set -a && . ./.env.exapp && set +a
    NC_MCP_EXPECT_TASKS_APP=0 PYTHONUTF8=1 uv run --no-sync pytest \\
        tests/integration/test_tasks_live.py -m integration -s -q

and against Nextcloud 35 (``compose.nc35.yml``, containers started, never bootstrapped)::

    set -a && . <main checkout>/.env.nc35 && set +a
    export NC_MCP_E2E_COMPOSE_FILE=compose.nc35.yml NC_MCP_E2E_PROJECT=nc-mcp-nc35 \\
        NC_MCP_E2E_NEXTCLOUD=nc35-nc NC_MCP_E2E_HARP=nc35-harp NC_MCP_E2E_CADDY=nc35-caddy \\
        NC_MCP_E2E_CONTAINERS=nc35-nc,nc_app_mcp_connector,nc35-harp,nc35-caddy,nc35-greenmail
    NC_MCP_EXPECT_TASKS_APP=1 PYTHONUTF8=1 uv run --no-sync pytest \\
        tests/integration/test_tasks_live.py -m integration -s -q

The env files are only ever loaded with ``set -a``, never read or quoted. Without that
environment the module skips; with ``NC_MCP_REQUIRE_LIVE=1`` it fails instead (W3 of phase
31), which is how the CI steps run it.
"""

import asyncio
import dataclasses
import json
import os
import secrets
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote, unquote

import canary_world as cw
import httpx
import pytest
import topology
from lxml import etree

from mcp_connector import ids
from mcp_connector.config import normalize_base_url
from mcp_connector.errors import REASON_GUARD_TRIPPED, REASON_UNKNOWN_ID, ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud import exclusion as exclusion_core
from mcp_connector.nextcloud.clients import caldav
from mcp_connector.nextcloud.clients import ocs as ocs_client
from mcp_connector.nextcloud.clients import tasks as tasks_client
from mcp_connector.nextcloud.clients import xml as dav_xml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, Credentials
from mcp_connector.tools import chatgpt as chatgpt_tools
from mcp_connector.tools import search as search_tools
from mcp_connector.tools import tasks as tasks_tools

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

STAMP = uuid.uuid4().hex[:8]
#: Every list, task, board and account of this run carries this head.
P = f"p32live-{STAMP}"
WRONG_SECRET = "0" * 64
ENV_EXPECT_TASKS_APP = "NC_MCP_EXPECT_TASKS_APP"
REQUIRED = {
    "base_url": "NC_MCP_URL",
    "app_id": "APP_ID",
    "app_secret": "APP_SECRET",
    "app_version": "APP_VERSION",
    "alice": "NC_MCP_TEST_USER",
    "alice_password": "NC_MCP_TEST_APP_PASSWORD",
    "bob": "NC_MCP_TEST_USER2",
    "bob_password": "NC_MCP_TEST_APP_PASSWORD2",
    "expect_tasks_app": ENV_EXPECT_TASKS_APP,
}
#: The measuring decision of plan 32-02 (``ENTSCHEID erkennung=keine``): the state of the
#: Tasks app cannot be read reliably, so the hint of D-32-10 never appears.
APP_STATE_DETECTION = "keine"
#: The list that is slowed down in the client for the degraded case; longer than the budget.
SLOW_SECONDS = 3.0
NO_TRASHBIN = {"X-NC-CalDAV-No-Trashbin": "1"}
OC_SHARE_NS = "http://owncloud.org/ns"
#: The due date of the full create case and the day after it, which must not appear.
DUE_DAY, DAY_AFTER, START_DAY = "2026-12-03", "20261204", "2026-12-01"
_PHP_BOOT = "<?php\nrequire_once '/var/www/html/lib/base.php';\n"

#: The baseline of 32-RULES.md section 7 for one principal, read from the database. The same
#: query as ``PHP_BASELINE`` in ``scripts/tasks_measure.py``; copied, because a test does not
#: load a measuring program.
PHP_BASELINE = (
    _PHP_BOOT
    + r"""
use OCP\DB\QueryBuilder\IQueryBuilder;
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$principal = 'principals/users/' . $argv[1];
$qb = $db->getQueryBuilder();
$qb->select('id')->from('calendars')
    ->where($qb->expr()->eq('principaluri', $qb->createNamedParameter($principal)));
$ids = array_map('intval', $qb->executeQuery()->fetchAll(\PDO::FETCH_COLUMN));
$objects = 0;
$deleted = 0;
$sharedOut = 0;
if (count($ids) > 0) {
    $qb = $db->getQueryBuilder();
    $qb->select($qb->func()->count('*', 'n'))->from('calendarobjects')
        ->where($qb->expr()->in(
            'calendarid', $qb->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)
        ))
        ->andWhere($qb->expr()->eq('calendartype', $qb->createNamedParameter(0)));
    $objects = (int)$qb->executeQuery()->fetchOne();
    $qb = $db->getQueryBuilder();
    $qb->select($qb->func()->count('*', 'n'))->from('calendarobjects')
        ->where($qb->expr()->in(
            'calendarid', $qb->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)
        ))
        ->andWhere($qb->expr()->eq('calendartype', $qb->createNamedParameter(0)))
        ->andWhere($qb->expr()->isNotNull('deleted_at'));
    $deleted = (int)$qb->executeQuery()->fetchOne();
    $qb = $db->getQueryBuilder();
    $qb->select($qb->func()->count('*', 'n'))->from('dav_shares')
        ->where($qb->expr()->in(
            'resourceid', $qb->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)
        ))
        ->andWhere($qb->expr()->eq('type', $qb->createNamedParameter('calendar')));
    $sharedOut = (int)$qb->executeQuery()->fetchOne();
}
$qb = $db->getQueryBuilder();
$qb->select($qb->func()->count('*', 'n'))->from('calendarsubscriptions')
    ->where($qb->expr()->eq('principaluri', $qb->createNamedParameter($principal)));
$subscriptions = (int)$qb->executeQuery()->fetchOne();
$qb = $db->getQueryBuilder();
$qb->select($qb->func()->count('*', 'n'))->from('dav_shares')
    ->where($qb->expr()->eq('principaluri', $qb->createNamedParameter($principal)));
$sharedIn = (int)$qb->executeQuery()->fetchOne();
echo count($ids), ' ', $objects, ' ', $deleted, ' ', $subscriptions, ' ',
    $sharedIn + $sharedOut, "\n";
"""
)

#: Live objects of one list of one owner, the independent counter of "nothing was written".
PHP_LIST_OBJECTS = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->select($qb->func()->count('*', 'n'))->from('calendarobjects', 'o')
    ->join('o', 'calendars', 'c', $qb->expr()->eq('o.calendarid', 'c.id'))
    ->where($qb->expr()->eq(
        'c.principaluri', $qb->createNamedParameter('principals/users/' . $argv[1])
    ))
    ->andWhere($qb->expr()->eq('c.uri', $qb->createNamedParameter($argv[2])))
    ->andWhere($qb->expr()->eq('o.calendartype', $qb->createNamedParameter(0)))
    ->andWhere($qb->expr()->isNull('o.deleted_at'));
echo $qb->executeQuery()->fetchOne(), "\n";
"""
)

type Seen = tuple[str, str, int]


# --- protocol -------------------------------------------------------------------------

_first_line_of_test = True


@pytest.fixture(autouse=True)
def _own_line() -> Iterator[None]:
    """The first line of a test starts on a line of its own, after the dot of the last one."""
    global _first_line_of_test
    _first_line_of_test = True
    yield
    _first_line_of_test = True


def record(line: str) -> None:
    """Write one protocol line to stdout; the run pipes it into the raw protocol (``-s``)."""
    global _first_line_of_test
    lead = "\n" if _first_line_of_test else ""
    _first_line_of_test = False
    sys.stdout.write(f"{lead}{line.rstrip()}\n")
    sys.stdout.flush()


def told(exc: ToolError) -> str:
    return f"{type(exc).__name__} reason={exc.reason} message={exc.message!r}"


def answered(answer: dict[str, Any]) -> str:
    return json.dumps(answer, ensure_ascii=True, sort_keys=True)


def calls(seen: list[Seen]) -> str:
    return ",".join(f"{method}:{status}" for method, _, status in seen) or "keine"


def methods(seen: list[Seen], method: str) -> list[int]:
    return [status for name, _, status in seen if name == method]


# --- container ------------------------------------------------------------------------


def php(snippet: str, *args: str) -> str:
    """One PHP snippet through stdin in the Nextcloud container; the last output line."""
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        [  # noqa: S607
            "docker",
            "exec",
            "-i",
            "-u",
            "www-data",
            "-w",
            "/var/www/html",
            topology.NC_CONTAINER,
            "php",
            "--",
            *args,
        ],
        input=snippet,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    lines = [line.strip() for line in (finished.stdout or "").splitlines() if line.strip()]
    assert finished.returncode == 0, f"php in the container failed: {finished.stderr[:300]}"
    return lines[-1] if lines else ""


def list_objects(owner: str, uri: str) -> int:
    value = php(PHP_LIST_OBJECTS, owner, uri)
    assert value.isdigit(), f"no count for {uri}: {value[:120]}"
    return int(value)


def baseline_of(user: str) -> str:
    raw = php(PHP_BASELINE, user).split()
    assert len(raw) == 5, f"the baseline of {user} could not be read: {raw}"
    assert all(part.isdigit() for part in raw), f"the baseline of {user} is not numeric: {raw}"
    return f"calendars={raw[0]} objekte={raw[1]} geloescht={raw[2]} shares={raw[4]} abos={raw[3]}"


def tasks_app_state() -> str:
    """``<version>``, ``aus-<version>`` or ``keine``, read with ``occ app:list``."""
    raw = cw.occ("app:list", "--output=json")
    data = json.loads(raw[raw.find("{") :])
    enabled, disabled = data.get("enabled") or {}, data.get("disabled") or {}
    if "tasks" in enabled:
        return str(enabled["tasks"])
    if "tasks" in disabled:
        return f"aus-{disabled['tasks']}"
    return "keine"


def add_account(uid: str, password: str) -> str:
    """``occ user:add`` with the password handed over through the environment only."""
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        [  # noqa: S607
            "docker",
            "exec",
            "-e",
            "OC_PASS",
            "-u",
            "www-data",
            topology.NC_CONTAINER,
            "php",
            "occ",
            "user:add",
            "--password-from-env",
            uid,
        ],
        env={**os.environ, "OC_PASS": password},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return f"exit={finished.returncode}"


# --- the run --------------------------------------------------------------------------


@dataclasses.dataclass
class Run:
    """The accounts, the harnesses, the lists of the run and every answer it received."""

    env: dict[str, str] = dataclasses.field(repr=False)
    version: str
    app_state: str
    harness: cw.Harness
    harness_bob: cw.Harness
    bob_display: str = ""
    deck_marker: str = ""
    board_id: str = ""
    card_id: str = ""
    #: key -> object name of the harness tasks, by role.
    objects: dict[str, str] = dataclasses.field(default_factory=dict)
    #: The keys of the two shared lists as alice sees them (hashed, D-32-14).
    rw_key: str = ""
    ro_key: str = ""
    #: The serialised text of every answer and every refusal of the run (D-32-06).
    answers: list[str] = dataclasses.field(default_factory=list)
    created: dict[str, str] = dataclasses.field(default_factory=dict)
    accounts: list[str] = dataclasses.field(default_factory=list)
    #: The harness of the account of D-32-18 with its one own list (plan 32-09).
    harness_out: cw.Harness | None = None

    @property
    def alice(self) -> str:
        return self.env["alice"]

    @property
    def bob(self) -> str:
        return self.env["bob"]

    @property
    def expect_app(self) -> bool:
        return self.env["expect_tasks_app"] == "1"


#: The lists of the run: role -> (owner role, uri, display name).
LISTS = {
    "a": ("alice", f"{P}-a", f"{P}-a"),
    "b": ("alice", f"{P}-b", f"{P}-b"),
    "rw": ("bob", f"{P}-rw", f"{P}-rw"),
    "ro": ("bob", f"{P}-ro", f"{P}-ro"),
}
#: The harness tasks: role -> (list role, title, extra lines).
TASKS = {
    "offen": ("a", f"{P}-offen", ()),
    "erledigt": (
        "a",
        f"{P}-erledigt",
        ("STATUS:COMPLETED", "COMPLETED:20261110T100000Z", "PERCENT-COMPLETE:100"),
    ),
    "faellig": ("a", f"{P}-faellig", ("DUE;VALUE=DATE:20261204",)),
    "spaeter": ("a", f"{P}-spaeter", ("DUE;VALUE=DATE:20261220",)),
    "zweite": ("b", f"{P}-zweite", ()),
    "fremdrw": ("rw", f"{P}-fremdrw", ()),
    "fremdro": ("ro", f"{P}-fremdro", ()),
}
FRESH, NEVER = f"{P}-frisch", f"{P}-nie"
#: D-32-18 (plan 32-09): an account with exactly one own task list, which it shares itself.
OUT_USER = f"p32live{STAMP}aus"
OUT_LIST = f"{P}-aus"


def _environment() -> dict[str, str]:
    values = {key: (os.environ.get(name) or "").strip() for key, name in REQUIRED.items()}
    missing = sorted(REQUIRED[key] for key, value in values.items() if not value)
    if missing:
        cw.skip_or_fail(f"no ExApp topology configured (missing: {', '.join(missing)})")
    if values["expect_tasks_app"] not in ("0", "1"):
        pytest.fail(f"{ENV_EXPECT_TASKS_APP} must be 0 or 1", pytrace=False)
    values["aa_version"] = (os.environ.get("AA_VERSION") or "").strip()
    values["base_url"] = normalize_base_url(values["base_url"])
    return values


def owner_harness(run: Run, role: str) -> cw.Harness:
    return run.harness if LISTS[role][0] == "alice" else run.harness_bob


def list_url(run: Run, role: str) -> str:
    return owner_harness(run, role).calendar_url(LISTS[role][1])


def share_body(user: str, *, writable: bool, remove: bool = False) -> bytes:
    """The share document of the calendar sharing plugin, as ``scripts/tasks_spike.py``."""
    root = etree.Element(f"{{{OC_SHARE_NS}}}share", nsmap={"d": dav_xml.DAV, "o": OC_SHARE_NS})
    entry = etree.SubElement(root, f"{{{OC_SHARE_NS}}}{'remove' if remove else 'set'}")
    etree.SubElement(entry, f"{{{dav_xml.DAV}}}href").text = f"principal:principals/users/{user}"
    if writable and not remove:
        etree.SubElement(entry, f"{{{OC_SHARE_NS}}}read-write")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def publish_body(*, publish: bool) -> bytes:
    """Publish or unpublish a calendar by link, as ``scripts/tasks_measure.py``."""
    name = "publish-calendar" if publish else "unpublish-calendar"
    root = etree.Element(f"{{{dav_xml.CS}}}{name}", nsmap={"cs": dav_xml.CS})
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _build(run: Run) -> None:
    """Lists, shares, tasks and the Deck board, all through the harness with app passwords."""
    for role, (_, uri, name) in LISTS.items():
        status = owner_harness(run, role).mk_task_list(uri, name)
        assert status == 201, f"MKCALENDAR {uri}: {status}"
    for role, writable in (("rw", True), ("ro", False)):
        response = run.harness_bob.request(
            "POST",
            list_url(run, role),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            content=share_body(run.alice, writable=writable),
        )
        assert response.status_code < 300, f"share {role}: {response.status_code}"
    for role, (list_role, title, extra) in TASKS.items():
        uid = f"{P}-{role}-{uuid.uuid4().hex[:6]}"
        response = owner_harness(run, list_role).request(
            "PUT",
            f"{list_url(run, list_role)}{uid}.ics",
            headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
            content=cw.todo_ics(uid, title, extra),
        )
        assert response.status_code == 201, f"PUT {role}: {response.status_code}"
        run.objects[role] = f"{uid}.ics"
    shared = {entry.name: entry for entry in run.harness.task_lists() if entry.shared}
    run.rw_key = shared[LISTS["rw"][2]].key
    run.ro_key = shared[LISTS["ro"][2]].key

    run.deck_marker = f"dk{uuid.uuid4().hex}"
    run.board_id = run.harness.deck_created("/boards", {"title": f"{P}-deck", "color": "0082c9"})
    stack = run.harness.deck_created(f"/boards/{run.board_id}/stacks", {"title": P, "order": 1})
    run.card_id = run.harness.deck_created(
        f"/boards/{run.board_id}/stacks/{stack}/cards",
        {"title": f"{P}-karte", "type": "plain", "order": 1, "description": run.deck_marker},
    )
    card = run.harness.deck("GET", f"/boards/{run.board_id}/stacks/{stack}/cards/{run.card_id}")
    assert run.deck_marker in card.text, f"deck card without its marker: {card.status_code}"


def _purge_calendar_trash(harness: cw.Harness) -> int:
    """Delete every object of this run from the calendar trash bin of the harness account.

    ``trashbin/objects/`` answers PROPFIND with 501 (plan 30-02), so it is read with a
    calendar-query and matched by the head of the run; never a database shortcut.
    """
    root = etree.Element(
        f"{{{dav_xml.CAL}}}calendar-query", nsmap={"d": dav_xml.DAV, "c": dav_xml.CAL}
    )
    prop = etree.SubElement(root, f"{{{dav_xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{dav_xml.CAL}}}calendar-data")
    scope = etree.SubElement(root, f"{{{dav_xml.CAL}}}filter")
    etree.SubElement(scope, f"{{{dav_xml.CAL}}}comp-filter", name="VCALENDAR")
    response = harness.request(
        "REPORT",
        f"{harness.calendar_home()}trashbin/objects/",
        headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
        content=etree.tostring(root, xml_declaration=True, encoding="utf-8"),
    )
    assert response.status_code == 207, f"REPORT trash bin: {response.status_code}"
    removed = 0
    origin = httpx.URL(harness.base_url)
    for entry in etree.fromstring(response.content).iter("{DAV:}response"):
        data = "".join(str(part) for part in entry.itertext())
        data = data.replace("\r\n ", "").replace("\n ", "")
        href = entry.findtext("{DAV:}href") or ""
        if P in data and href:
            harness.request(
                "DELETE", str(origin.copy_with(path=href, query=None)), headers=NO_TRASHBIN
            )
            removed += 1
    return removed


def _teardown(run: Run) -> list[str]:
    """Remove everything of this run through the harness, never through the connector."""
    lines: list[str] = []
    for role in ("rw", "ro"):
        response = run.harness_bob.request(
            "POST",
            list_url(run, role),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            content=share_body(run.alice, writable=False, remove=True),
        )
        lines.append(f"RUECKBAU freigabe {role} status={response.status_code}")
    for role in LISTS:
        status = owner_harness(run, role).delete_calendar_url(list_url(run, role))
        left = owner_harness(run, role).status_of(list_url(run, role))
        lines.append(f"RUECKBAU liste {role} delete={status} no_trashbin=1 danach={left}")
    if run.board_id:
        run.harness.deck("DELETE", f"/boards/{run.board_id}")
        lines.append(f"RUECKBAU deck board={run.board_id} {run.harness.board_state(run.board_id)}")
    for label, harness in (("alice", run.harness), ("bob", run.harness_bob)):
        lines.append(f"RUECKBAU papierkorb {label} entfernt={_purge_calendar_trash(harness)}")
    if run.harness_out is not None:
        lines.extend(_teardown_out(run, run.harness_out))
    for uid in (FRESH, NEVER, OUT_USER):
        out = cw.occ("user:delete", uid, check_status=False)
        lines.append(f"RUECKBAU konto {uid} {'geloescht' if 'deleted' in out else 'nicht da'}")
    rest = [e.uri for e in run.harness.task_lists() if P in e.name or P in e.uri]
    rest += [e.uri for e in run.harness_bob.task_lists() if P in e.uri]
    lines.append(f"RUECKBAU reste listen_mit_kopf={len(rest)}")
    return lines


def _teardown_out(run: Run, harness: cw.Harness) -> list[str]:
    """Share and link of the D-32-18 list withdrawn, list and trash bin emptied."""
    lines: list[str] = []
    url = harness.calendar_url(OUT_LIST)
    xml_head = {"Content-Type": "application/xml; charset=utf-8"}
    body = share_body(run.bob, writable=False, remove=True)
    status = harness.request("POST", url, headers=xml_head, content=body).status_code
    lines.append(f"RUECKBAU freigabe aus status={status}")
    status = harness.request(
        "POST", url, headers=xml_head, content=publish_body(publish=False)
    ).status_code
    lines.append(f"RUECKBAU link aus status={status}")
    # The object deleted after the positive control lies in the trash bin; it is purged
    # before the list goes, so the line shows it (deleting the list would take it as well).
    purged = _purge_calendar_trash(harness)
    lines.append(f"RUECKBAU papierkorb {OUT_USER} vor-liste entfernt={purged}")
    status = harness.delete_calendar_url(url)
    lines.append(
        f"RUECKBAU liste aus delete={status} no_trashbin=1 danach={harness.status_of(url)}"
    )
    lines.append(f"RUECKBAU papierkorb {OUT_USER} entfernt={_purge_calendar_trash(harness)}")
    rest = [e.uri for e in harness.task_lists() if P in e.uri]
    lines.append(f"RUECKBAU reste {OUT_USER} listen_mit_kopf={len(rest)}")
    harness.close()
    return lines


@pytest.fixture(scope="module")
def run() -> Iterator[Run]:
    env = _environment()
    live = cw.live_env()
    harness = cw.Harness(live)
    harness_bob = cw.Harness(cw.LiveEnv(env["base_url"], env["bob"], env["bob_password"]))
    status = json.loads(cw.occ("status", "--output=json"))
    state = Run(
        env=env,
        version=str(status["version"]),
        app_state=tasks_app_state(),
        harness=harness,
        harness_bob=harness_bob,
    )
    info = json.loads(cw.occ("user:info", state.bob, "--output=json"))
    state.bob_display = str(info.get("display_name") or info.get("displayname") or "")
    record(f"LAUF aufgaben32 stempel={STAMP} kopf={P} container={topology.NC_CONTAINER}")
    record(f"VERSION nc={state.version} versionstring={status['versionstring']} (occ status)")
    installed = not state.app_state.startswith("aus-") and state.app_state != "keine"
    record(
        f"TASKSAPP erwartet={env['expect_tasks_app']} occ_app_list={state.app_state} "
        f"passt={'ja' if installed == state.expect_app else 'nein'}"
    )
    assert installed == state.expect_app, (
        f"{ENV_EXPECT_TASKS_APP}={env['expect_tasks_app']} but occ app:list says {state.app_state}"
    )
    users = (state.alice, state.bob, FRESH, NEVER, OUT_USER)
    before = {user: baseline_of(user) for user in users}
    for user, value in before.items():
        record(f"BASELINE nc{state.version} konto={user} {value} phase=vorher")
    exclusion_core.clear_cache()
    capabilities.clear_cache()
    lines: list[str] = []
    try:
        _build(state)
        yield state
    finally:
        try:
            lines = _teardown(state)
        finally:
            for line in lines:
                record(line)
            harness.close()
            harness_bob.close()
            exclusion_core.clear_cache()
    after = {user: baseline_of(user) for user in users}
    for user, value in after.items():
        same = "ja" if before[user] == value else "nein"
        record(f"BASELINE nc{state.version} konto={user} {value} phase=nachher gleich={same}")
    assert before == after, f"baseline differs: {before} / {after}"
    assert lines[-1].endswith("listen_mit_kopf=0"), lines[-1]


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
            f"AUFGABE {self.label} nc={self.run.version} nutzer={self.user} "
            f"status={calls(self.seen)} ergebnis={verdict} | {'; '.join(self.notes)}"
        )
        if exc is None:
            assert self.ok, f"{self.label}: {'; '.join(self.notes)}"


def appapi_clients(
    run: Run, user: str, seen: list[Seen], secret: str = "", slow_uri: str = ""
) -> NcClients:
    """Impersonating clients for one call: ``APP_SECRET`` is the only credential.

    The response hook notes the method, the path below the calendar home and the status of
    every answer. With ``slow_uri`` it holds back the REPORT answer of that one list longer
    than the budget of a list: the outage is made in the client, the server is real.
    """
    prefix = f"{caldav.DAV_CALENDARS_PREFIX}{user}"

    async def hook(response: httpx.Response) -> None:
        path = unquote(response.request.url.path)
        method = response.request.method
        if prefix in path:
            below = path.split(prefix, 1)[1] or "/"
        else:
            _, found, rest = path.partition("/remote.php/dav/")
            method, below = f"{rest.split('/', 1)[0] if found else 'ocs'}.{method}", ""
        seen.append((method, below, response.status_code))
        if slow_uri and method == "REPORT" and f"/{slow_uri}/" in path:
            await asyncio.sleep(SLOW_SECONDS)

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
async def measured(case: Case, secret: str = "", slow_uri: str = "") -> AsyncIterator[NcClients]:
    """The clients of one tool call: fresh caches, calls into ``case``."""
    exclusion_core.clear_cache()
    capabilities.clear_cache()
    clients = appapi_clients(case.run, case.user, case.seen, secret, slow_uri)
    async with clients.client:
        yield clients


def keep(run: Run, answer: dict[str, Any]) -> dict[str, Any]:
    run.answers.append(json.dumps(answer, ensure_ascii=False))
    return answer


async def refusal(run: Run, call: Any) -> ToolError:
    """The ToolError a call raises, kept for the scan of D-32-06; an answer fails the case."""
    try:
        answer = await call
    except ToolError as exc:
        run.answers.append(f"{exc.message} {exc.hint}")
        return exc
    keep(run, answer)
    raise AssertionError(f"expected a refusal, got an answer: {answered(answer)}")


async def search(case: Case, **kwargs: Any) -> dict[str, Any]:
    async with measured(case) as clients:
        return keep(case.run, await tasks_tools.search_tasks(clients, **kwargs))


def hit_ids(answer: dict[str, Any]) -> set[str]:
    return {str(hit.get("id")) for hit in answer.get("tasks") or [] if isinstance(hit, dict)}


def task_id(run: Run, role: str) -> str:
    """The id of a harness task: an own list keeps its URI as key, a shared one its hash."""
    list_role = TASKS[role][0]
    key = {"rw": run.rw_key, "ro": run.ro_key}.get(list_role, LISTS[list_role][1])
    return ids.encode_task(key, run.objects[role])


def raw_object(run: Run, identifier: str) -> tuple[int, str]:
    """The raw iCalendar of an id, read with the app password of alice, unfolded."""
    _, (key, object_name) = ids.parse(identifier)
    response = run.harness.request("GET", run.harness.task_url(key, object_name))
    return response.status_code, response.text.replace("\r\n ", "").replace("\n ", "")


# --- controls. Everything below them is worthless without them. ------------------------


async def test_the_measuring_process_holds_no_nextcloud_app_password(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control a: the identity cannot come from a Basic app password or a static bearer."""
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
        f"KONTROLLE a nc={run.version} nutzer={run.alice} ergebnis={'ok' if ok else 'befund'} | "
        f"mode={clients.creds.mode} NC_MCP_APP_PASSWORD or NC_MCP_STATIC_BEARER set in the "
        f"process={held or 'no'}; the credential is APP_SECRET and no app password"
    )
    assert ok


async def test_a_wrong_app_secret_writes_nothing(run: Run) -> None:
    """Control b: with 64 zeros as the secret every answer is a 401 and no row appears."""
    uri = LISTS["a"][1]
    before = list_objects(run.alice, uri)
    case = Case(run, "kontrolle-b")
    async with measured(case, secret=WRONG_SECRET) as clients:
        exc = await refusal(
            run,
            tasks_tools.create_task(clients, summary=f"{P}-falsch", list_name=LISTS["a"][2]),
        )
    after = list_objects(run.alice, uri)
    statuses = {status for _, _, status in case.seen}
    ok = statuses == {401} and before == after and not methods(case.seen, "PUT")
    record(
        f"KONTROLLE b nc={run.version} nutzer={run.alice} status={calls(case.seen)} "
        f"ergebnis={'ok' if ok else 'befund'} | tool: {told(exc)}; calendarobjects {uri} "
        f"vorher={before} nachher={after}"
    )
    assert ok


# --- writing --------------------------------------------------------------------------


async def test_a_task_with_every_field_lands_in_the_named_list_as_sent(run: Run) -> None:
    with Case(run, "anlegen-mit-list") as case:
        async with measured(case) as clients:
            parent = keep(
                run,
                await tasks_tools.create_task(
                    clients, summary=f"{P}-eltern", list_name=LISTS["a"][2]
                ),
            )
        async with measured(case) as clients:
            child = keep(
                run,
                await tasks_tools.create_task(
                    clients,
                    summary=f"{P}-kind",
                    list_name=LISTS["a"][2],
                    description=f"{P} beschreibung",
                    due=DUE_DAY,
                    start=START_DAY,
                    priority=3,
                    tags=[f"{P}-x", f"{P}-y"],
                    parent=str(parent["id"]),
                ),
            )
        run.created["eltern"] = str(parent["id"])
        run.created["kind"] = str(child["id"])
        _, parent_raw = raw_object(run, str(parent["id"]))
        status, raw = raw_object(run, str(child["id"]))
        parent_uid = next(
            (line[4:] for line in parent_raw.splitlines() if line.startswith("UID:")), ""
        )
        lines = raw.splitlines()
        case.expect(status == 200, f"GET {status} with the app password")
        case.expect("DUE;VALUE=DATE:20261203" in lines, "DUE;VALUE=DATE:20261203 in the raw object")
        case.expect(DAY_AFTER not in raw, f"no {DAY_AFTER} anywhere in the raw object")
        case.expect("DTSTART;VALUE=DATE:20261201" in lines, "DTSTART;VALUE=DATE:20261201")
        categories = " ".join(line for line in lines if line.startswith("CATEGORIES"))
        case.expect(f"{P}-x" in categories and f"{P}-y" in categories, f"CATEGORIES {categories!r}")
        case.expect("PRIORITY:3" in lines, "PRIORITY:3")
        case.expect(
            bool(parent_uid)
            and any(
                line.startswith("RELATED-TO") and line.endswith(f":{parent_uid}") for line in lines
            ),
            f"RELATED-TO the UID of the parent {parent_uid}",
        )
        case.expect(
            child.get("created") is True and child.get("confirmed") is True, answered(child)
        )
        case.expect("hint" not in child and "hint" not in parent, "no hint (erkennung=keine)")


async def test_without_list_two_own_lists_are_an_error_naming_both(run: Run) -> None:
    counts = {role: list_objects(run.alice, LISTS[role][1]) for role in ("a", "b")}
    with Case(run, "ohne-list-zwei-listen") as case:
        async with measured(case) as clients:
            exc = await refusal(run, tasks_tools.create_task(clients, summary=f"{P}-ohne"))
        after = {role: list_objects(run.alice, LISTS[role][1]) for role in ("a", "b")}
        case.expect("more than one task list" in exc.message, told(exc))
        case.expect(LISTS["a"][2] in exc.hint and LISTS["b"][2] in exc.hint, f"hint {exc.hint!r}")
        case.expect(not methods(case.seen, "PUT"), "no PUT")
        case.expect(counts == after, f"calendarobjects vorher={counts} nachher={after}")


async def test_shared_lists_carry_no_owner_and_the_right_flags(run: Run) -> None:
    with Case(run, "geteilt-namen") as case:
        answer = await search(case, query=P, status="all")
        lists = {
            hit["list"]["name"]: hit["list"]
            for hit in answer.get("tasks") or []
            if isinstance(hit, dict) and isinstance(hit.get("list"), dict)
        }
        raw = run.harness.home_raw().text
        suffixed = sum(1 for role in ("rw", "ro") if f"{LISTS[role][2]} (" in raw)
        case.note(f"roher displayname mit zusatz in der discovery: {suffixed} von 2")
        case.expect(suffixed == 2, "the server really adds the owner, so stripping is proven")
        for role, writable in (("rw", True), ("ro", False)):
            entry = lists.get(LISTS[role][2])
            case.expect(
                entry == {"name": LISTS[role][2], "shared": True, "writable": writable},
                f"{role}: {entry}",
            )
        case.expect(
            lists.get(LISTS["a"][2]) == {"name": LISTS["a"][2], "shared": False, "writable": True},
            f"a: {lists.get(LISTS['a'][2])}",
        )
        case.expect(task_id(run, "fremdrw") in hit_ids(answer), "the task of the rw share is a hit")


async def test_a_named_writable_shared_list_is_written_to(run: Run) -> None:
    before = list_objects(run.bob, LISTS["rw"][1])
    with Case(run, "geteilt-rw-mit-list") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.create_task(
                    clients, summary=f"{P}-in-rw", list_name=LISTS["rw"][2]
                ),
            )
        _, (key, object_name) = ids.parse(str(answer["id"]))
        got = run.harness_bob.request("GET", f"{list_url(run, 'rw')}{quote(object_name)}")
        after = list_objects(run.bob, LISTS["rw"][1])
        case.expect(key == run.rw_key, f"the id carries the hashed key: {key == run.rw_key}")
        case.expect(
            got.status_code == 200 and f"SUMMARY:{P}-in-rw" in got.text,
            f"GET by the owner {got.status_code}",
        )
        case.expect(after == before + 1, f"calendarobjects vorher={before} nachher={after}")
        case.expect(methods(case.seen, "PUT") == [201], f"PUT {methods(case.seen, 'PUT')}")


async def test_a_read_only_shared_list_is_refused_before_any_put(run: Run) -> None:
    before = list_objects(run.bob, LISTS["ro"][1])
    with Case(run, "geteilt-ro-vorab") as case:
        async with measured(case) as clients:
            exc = await refusal(
                run,
                tasks_tools.create_task(clients, summary=f"{P}-in-ro", list_name=LISTS["ro"][2]),
            )
        after = list_objects(run.bob, LISTS["ro"][1])
        case.expect(exc.reason == REASON_GUARD_TRIPPED, told(exc))
        case.expect("read only" in exc.message, exc.message)
        case.expect(not methods(case.seen, "PUT"), "the hook saw no PUT")
        case.expect(before == after, f"calendarobjects vorher={before} nachher={after}")


async def test_the_server_refuses_a_put_into_the_read_only_list_as_the_last_word(
    run: Run,
) -> None:
    """The guard of the bundle is not the only wall: a direct PUT with the app password."""
    before = list_objects(run.bob, LISTS["ro"][1])
    with Case(run, "geteilt-ro-server") as case:
        uid = f"{P}-direkt-{uuid.uuid4().hex[:6]}"
        url = run.harness.task_url(run.ro_key, f"{uid}.ics")
        response = run.harness.request(
            "PUT",
            url,
            headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
            content=cw.todo_ics(uid, f"{P}-direkt"),
        )
        after = list_objects(run.bob, LISTS["ro"][1])
        case.note("harness PUT with the app password of alice, not the connector")
        case.expect(response.status_code in (403, 404), f"PUT {response.status_code}")
        case.expect(before == after, f"calendarobjects vorher={before} nachher={after}")


async def test_a_parent_in_a_shared_list_does_not_name_the_list(run: Run) -> None:
    """D-32-16: ``parent`` alone is no explicit naming of a shared list."""
    before = list_objects(run.bob, LISTS["rw"][1])
    with Case(run, "d-32-16") as case:
        async with measured(case) as clients:
            exc = await refusal(
                run,
                tasks_tools.create_task(
                    clients, summary=f"{P}-unter", parent=task_id(run, "fremdrw")
                ),
            )
        after = list_objects(run.bob, LISTS["rw"][1])
        case.expect("shared list" in exc.message, told(exc))
        case.expect(not methods(case.seen, "PUT"), "no PUT")
        case.expect(before == after, f"calendarobjects vorher={before} nachher={after}")


# --- reading --------------------------------------------------------------------------


async def test_the_default_search_shows_open_tasks_and_due_by_drops_undated_ones(
    run: Run,
) -> None:
    with Case(run, "suche-standard-und-faellig") as case:
        default = await search(case, query=P, list_name=LISTS["a"][2])
        completed = await search(case, query=P, list_name=LISTS["a"][2], status="completed")
        due = await search(case, query=P, list_name=LISTS["a"][2], due_by="2026-12-10")
        found, done, until = hit_ids(default), hit_ids(completed), hit_ids(due)
        case.expect(task_id(run, "offen") in found, "open task in the default search")
        case.expect(task_id(run, "erledigt") not in found, "completed task not in it")
        case.expect(task_id(run, "erledigt") in done, "completed task with status=completed")
        case.expect(task_id(run, "faellig") in until, "due 2026-12-04 within due_by 2026-12-10")
        case.expect(task_id(run, "spaeter") not in until, "due 2026-12-20 outside")
        case.expect(task_id(run, "offen") not in until, "an undated task is not due by a day")


async def test_a_list_that_does_not_answer_in_time_is_named_as_degraded(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server is real; the outage is made in the client (decision of the planning)."""
    monkeypatch.setattr(tasks_tools, "PER_LIST_TIMEOUT", 1.0)
    with Case(run, "ausfall-liste") as case:
        case.note(f"REPORT of {LISTS['b'][1]} held back {SLOW_SECONDS} s in the client hook")
        async with measured(case, slow_uri=LISTS["b"][1]) as clients:
            answer = keep(run, await tasks_tools.search_tasks(clients, query=P))
        degraded = answer.get("degraded") or []
        case.expect(
            [entry.get("list") for entry in degraded] == [LISTS["b"][2]], f"degraded {degraded}"
        )
        case.expect(task_id(run, "offen") in hit_ids(answer), "the other lists still answer")


async def test_fetch_and_tasks_read_return_the_same_task(run: Run) -> None:
    with Case(run, "fetch-gleich-read") as case:
        identifier = run.created.get("kind") or task_id(run, "faellig")
        async with measured(case) as clients:
            read = keep(run, await tasks_tools.read_task(clients, task_id=identifier))
        async with measured(case) as clients:
            fetched = keep(run, await chatgpt_tools.fetch(clients, identifier))
        metadata = fetched.get("metadata") or {}
        case.expect(read.get("id") == fetched.get("id") == identifier, f"id {identifier}")
        case.expect(read.get("summary") == fetched.get("title"), f"title {fetched.get('title')}")
        case.expect(read.get("status") == metadata.get("status"), f"status {read.get('status')}")
        case.expect(
            str(fetched.get("url") or "").endswith(quote(ids.parse(identifier)[1][1], safe="")),
            "deep link of an own list",
        )


async def test_no_deck_card_flows_out_through_the_tasks_bundle(run: Run) -> None:
    with Case(run, "deck") as case:
        deck_uri = f"{tasks_client.DECK_PREFIX}deck--board-{run.board_id}"
        components = run.harness.home_components().get(deck_uri)
        case.expect(
            components is not None and "VTODO" in components,
            f"positive control: {deck_uri} with VTODO in the discovery of alice",
        )
        card = run.harness.deck("GET", f"/boards/{run.board_id}")
        case.expect(card.status_code == 200, f"positive control: Deck REST {card.status_code}")
        answer = await search(case, query=f"{P}-karte", status="all")
        async with measured(case) as clients:
            exc = await refusal(
                run,
                tasks_tools.read_task(clients, task_id=f"task:{deck_uri}:card-{run.card_id}.ics"),
            )
        texts = [json.dumps(answer), f"{exc.message} {exc.hint}"]
        case.expect(not hit_ids(answer), f"no hit for the card title: {hit_ids(answer)}")
        case.expect(exc.reason == REASON_UNKNOWN_ID, told(exc))
        case.expect(not any(run.deck_marker in text for text in texts), "deck marker in no answer")


# --- TASK-03: accounts without a task list ---------------------------------------------


async def _no_list_account(run: Run, uid: str, *, log_in: bool) -> None:
    password = f"{secrets.token_urlsafe(18)}Aa1!"
    with Case(run, f"task-03-{'mit' if log_in else 'ohne'}-anmeldung", user=uid) as case:
        case.note(f"occ user:add {add_account(uid, password)}")
        run.accounts.append(uid)
        if log_in:
            async with httpx.AsyncClient(timeout=30.0) as basic:
                response = await basic.get(
                    f"{run.env['base_url']}/ocs/v2.php/cloud/user",
                    params={"format": "json"},
                    headers={"OCS-APIRequest": "true"},
                    auth=(uid, password),
                )
            case.expect(response.status_code == 200, f"Basic cloud/user {response.status_code}")
        async with measured(case) as clients:
            answer = keep(run, await tasks_tools.search_tasks(clients))
        async with measured(case) as clients:
            exc = await refusal(run, tasks_tools.create_task(clients, summary=f"{P}-leer"))
        case.note(f"BASELINE {baseline_of(uid)}")
        case.expect(answer == {"tasks": [], "hint": tasks_tools.NO_LIST_HINT}, answered(answer))
        case.expect(exc.message == tasks_tools.NO_LIST_MESSAGE, told(exc))
        case.expect(exc.hint == tasks_tools.NO_LIST_WAY_OUT, f"hint {exc.hint!r}")
        case.expect(not methods(case.seen, "PUT"), "no PUT")
        out = cw.occ("user:delete", uid, check_status=False)
        case.note(f"occ user:delete {'ok' if 'deleted' in out else 'nicht bestaetigt'}")


async def test_an_account_that_logged_in_once_has_no_task_list(run: Run) -> None:
    await _no_list_account(run, FRESH, log_in=True)


async def test_an_account_that_never_logged_in_has_no_task_list(run: Run) -> None:
    await _no_list_account(run, NEVER, log_in=False)


# --- the Tasks app: provider with it, an honest empty search without it ------------------


async def test_the_search_provider_of_the_tasks_app(run: Run) -> None:
    """D-32-11: with the app its hit becomes the same id; without it nothing false appears."""
    expected = task_id(run, "faellig")
    with Case(run, f"provider-tasksapp-{run.env['expect_tasks_app']}") as case:
        case.note(f"tasksapp occ={run.app_state} ENTSCHEID erkennung={APP_STATE_DETECTION}")
        async with measured(case) as clients:
            providers = [
                str(p.get("id"))
                for p in await ocs_client.list_search_providers(clients.client, clients.creds)
            ]
        async with measured(case) as clients:
            answer = keep(
                run, await search_tools.unified_search(clients, query=TASKS["faellig"][1])
            )
        hits = [hit for hit in answer.get("results") or [] if hit.get("provider") == "tasks"]
        case.note(f"provider tasks listed={'tasks' in providers} hits={[h['id'] for h in hits]}")
        if run.expect_app:
            case.expect("tasks" in providers, "the provider is listed")
            case.expect([hit["id"] for hit in hits] == [expected], f"hit id == {expected}")
            async with measured(case) as clients:
                read = keep(run, await tasks_tools.read_task(clients, task_id=expected))
            case.expect(read.get("summary") == TASKS["faellig"][1], "tasks_read of that id")
        else:
            case.expect("tasks" not in providers, "the provider is not listed")
            case.expect(not hits, "no task hit")
            case.expect(
                not any(str(hit.get("kind")) == "task" for hit in answer.get("results") or []),
                "no hit of kind task from anywhere",
            )
        # The three tools work in both states, and with erkennung=keine the hint of D-32-10
        # appears in neither: a created task answers without a hint field.
        async with measured(case) as clients:
            created = keep(
                run,
                await tasks_tools.create_task(
                    clients, summary=f"{P}-hinweis", list_name=LISTS["a"][2]
                ),
            )
        hinted = "hint" in created
        case.expect(
            created.get("created") is True and hinted == (APP_STATE_DETECTION != "keine"),
            f"tasks_create created={created.get('created')} hint={'ja' if hinted else 'nein'}",
        )


# --- plan 32-09, D-32-18: an own list the account shares itself ---------------------------


def _out_post(run: Run, body: bytes) -> int:
    assert run.harness_out is not None
    return run.harness_out.request(
        "POST",
        run.harness_out.calendar_url(OUT_LIST),
        headers={"Content-Type": "application/xml; charset=utf-8"},
        content=body,
    ).status_code


def _names_bob(run: Run, text: str) -> bool:
    folded = text.casefold()
    return any(name and name.casefold() in folded for name in (run.bob, run.bob_display))


async def _out_refused(run: Run, label: str, **kwargs: Any) -> None:
    """Without ``list`` the call is refused, the hook sees no PUT, the row count stays."""
    before = list_objects(OUT_USER, OUT_LIST)
    with Case(run, label, user=OUT_USER) as case:
        async with measured(case) as clients:
            exc = await refusal(
                run, tasks_tools.create_task(clients, summary=f"{P}-{label}", **kwargs)
            )
        after = list_objects(OUT_USER, OUT_LIST)
        text = f"{exc.message} {exc.hint}"
        case.expect(exc.reason == REASON_GUARD_TRIPPED, told(exc))
        case.expect("shared with others" in exc.message, "shared with others in the message")
        case.expect("list=" in exc.hint, f"hint {exc.hint!r}")
        case.expect(not methods(case.seen, "PUT"), "the hook saw no PUT")
        case.expect(before == after, f"calendarobjects vorher={before} nachher={after}")
        case.expect(not _names_bob(run, text), "neither the id nor the display name of bob")
        case.expect("_shared_by_" not in text, "no share marker")


async def _out_written(run: Run, label: str, **kwargs: Any) -> str:
    before = list_objects(OUT_USER, OUT_LIST)
    with Case(run, label, user=OUT_USER) as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.create_task(clients, summary=f"{P}-{label}", **kwargs),
            )
        after = list_objects(OUT_USER, OUT_LIST)
        assert run.harness_out is not None
        _, (_, object_name) = ids.parse(str(answer["id"]))
        got = run.harness_out.request(
            "GET", f"{run.harness_out.calendar_url(OUT_LIST)}{quote(object_name, safe='')}"
        )
        case.expect(methods(case.seen, "PUT") == [201], f"PUT {methods(case.seen, 'PUT')}")
        case.expect(after == before + 1, f"calendarobjects vorher={before} nachher={after}")
        case.expect(
            got.status_code == 200 and f"SUMMARY:{P}-{label}" in got.text,
            f"raw object GET {got.status_code} with the password of the account",
        )
        case.expect(
            answer.get("list") == {"name": OUT_LIST, "shared": False, "writable": True},
            f"list {answer.get('list')}",
        )
    return str(answer["id"])


async def test_d_32_18_an_own_list_shared_with_others_is_only_written_when_named(
    run: Run,
) -> None:
    """The account of this case has exactly one own task list; it shares it itself."""
    password = f"{secrets.token_urlsafe(18)}Aa1!"
    record(f"SETUP d-32-18 occ user:add {add_account(OUT_USER, password)} konto={OUT_USER}")
    run.accounts.append(OUT_USER)
    run.harness_out = cw.Harness(cw.LiveEnv(run.env["base_url"], OUT_USER, password))
    status = run.harness_out.mk_task_list(OUT_LIST, OUT_LIST)
    record(f"SETUP d-32-18 MKCALENDAR liste={OUT_LIST} status={status}")
    assert status == 201, f"MKCALENDAR {OUT_LIST}: {status}"

    # Positive control: nobody else sees the list, so it is written without list.
    first = await _out_written(run, "d-32-18-privat")
    _, (_, object_name) = ids.parse(first)
    gone = run.harness_out.request(
        "DELETE", f"{run.harness_out.calendar_url(OUT_LIST)}{quote(object_name, safe='')}"
    )
    record(f"SETUP d-32-18 DELETE privat-objekt status={gone.status_code} (Papierkorb im Rueckbau)")

    status = _out_post(run, share_body(run.bob, writable=False))
    record(f"SETUP d-32-18 FREIGABE an-bob-ro status={status}")
    assert status < 300, f"share: {status}"
    await _out_refused(run, "d-32-18-geteilt")
    parent = await _out_written(run, "d-32-18-mit-list", list_name=OUT_LIST)
    await _out_refused(run, "d-32-18-parent", parent=parent)

    status = _out_post(run, share_body(run.bob, writable=False, remove=True))
    record(f"SETUP d-32-18 FREIGABE zurueck status={status}")
    status = _out_post(run, publish_body(publish=True))
    record(f"SETUP d-32-18 LINK veroeffentlicht status={status}")
    assert status < 300, f"publish: {status}"
    await _out_refused(run, "d-32-18-link")
    status = _out_post(run, publish_body(publish=False))
    record(f"SETUP d-32-18 LINK zurueck status={status}")
    await _out_written(run, "d-32-18-zurueckgenommen")


# --- plan 32-09, D-32-17: the subline of a provider hit from a shared list ----------------


def _raw_provider_subline(run: Run, title: str) -> str | None:
    """The subline the provider sends to alice, read with her app password (harness)."""
    response = run.harness.request(
        "GET",
        f"{run.env['base_url']}/ocs/v2.php/search/providers/tasks/search",
        params={"term": title},
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
    )
    entries = response.json()["ocs"]["data"]["entries"]
    found = [entry for entry in entries if entry.get("title") == title]
    return str(found[0].get("subline") or "") if found else None


async def _connector_sublines(run: Run, case: Case, title: str) -> tuple[str | None, str | None]:
    async with measured(case) as clients:
        answer = keep(run, await search_tools.unified_search(clients, query=title))
    hits = [h for h in answer.get("results") or [] if h.get("provider") == "tasks"]
    async with measured(case) as clients:
        found = await chatgpt_tools.search(clients, title)
    run.answers.append(json.dumps(found, ensure_ascii=False))
    texts = [h["text"] for h in found if h.get("title") == title]
    sublines = [h.get("subline") for h in hits if h.get("title") == title]
    return (sublines[0] if sublines else None), (texts[0] if texts else None)


async def test_d_32_17_the_subline_of_a_shared_list_hit_names_nobody(run: Run) -> None:
    if not run.expect_app:
        record(
            f"AUFGABE d-32-17-geteilt nc={run.version} nutzer={run.alice} status=keine "
            "ergebnis=entfaellt | without the Tasks app the provider tasks does not exist"
        )
        return
    title = TASKS["fremdrw"][1]
    with Case(run, "d-32-17-geteilt") as case:
        raw = _raw_provider_subline(run, title)
        case.expect(raw is not None, "the provider finds the task of the rw share")
        raw = raw or ""
        raw_owner = _names_bob(run, raw)
        case.note(f"roh_mit_besitzer={'ja' if raw_owner else 'nein'}")
        major = int(run.version.split(".")[0])
        if major >= 34:
            case.expect(raw_owner, "positive control: the raw subline names the owner on 34+")
        subline, text = await _connector_sublines(run, case, title)
        case.note(
            f"subline_vorhanden={'ja' if subline else 'nein'} text_gleich={text == (subline or '')}"
        )
        for label, value in (("subline", subline or ""), ("text", text or "")):
            case.expect(not _names_bob(run, value), f"{label} without bob")
            case.expect("_shared_by_" not in value, f"{label} without the share marker")
        if raw_owner:
            case.expect(
                bool(subline) and str(subline).endswith(f" ({LISTS['rw'][2]})"),
                "the subline ends with the list name without the owner",
            )
        else:
            case.expect((subline or "") == raw, "without an owner the subline is the raw one")
        case.expect(text == (subline or ""), "search text equals the subline")


async def test_d_32_17_the_subline_of_an_own_list_hit_is_unchanged(run: Run) -> None:
    if not run.expect_app:
        record(
            f"AUFGABE d-32-17-eigen nc={run.version} nutzer={run.alice} status=keine "
            "ergebnis=entfaellt | without the Tasks app the provider tasks does not exist"
        )
        return
    title = TASKS["faellig"][1]
    with Case(run, "d-32-17-eigen") as case:
        raw = _raw_provider_subline(run, title)
        subline, text = await _connector_sublines(run, case, title)
        case.expect(raw is not None and subline == (raw or None), "the subline is the raw one")
        case.expect(text == (raw or ""), "search text equals the raw subline")


# --- last: nobody else's name in any answer (D-32-06, D-32-14) ---------------------------


async def test_no_answer_of_the_run_names_the_owner_of_a_shared_list(run: Run) -> None:
    """The serialised text of every answer and refusal, scanned for the owner (runs last)."""
    names = [run.bob, run.bob_display]
    with Case(run, "keine-kennung") as case:
        text = "\n".join(run.answers).casefold()
        found = [name for name in names if name and name.casefold() in text]
        case.note(f"{len(run.answers)} answers scanned for the id and the display name of bob")
        case.expect(len(run.answers) >= 15, f"answers kept: {len(run.answers)}")
        case.expect(not found, f"found {len(found)} of 2 names")
        case.expect("_shared_by_" not in text, "no _shared_by_ in any answer")

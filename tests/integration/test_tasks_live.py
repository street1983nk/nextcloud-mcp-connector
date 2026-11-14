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
with ``occ user:delete``. The test group ``p32live<stamp>grp`` of plan 32-10 (members bob and
alice) loses every share first and is deleted with ``occ group:delete`` after the lists;
``GRUPPE`` lines before and after show it absent and without a share.
``BASELINE`` lines per account (``calendars``, ``calendarobjects`` with and without
``deleted_at``, ``calendarsubscriptions``, ``dav_shares``) before and after must be equal.

The expected state of the Tasks app comes as ``NC_MCP_EXPECT_TASKS_APP`` (``0`` or ``1``) and is
read a second time with ``occ app:list`` in the container; a contradiction fails the run.

Run it against the Nextcloud 32 or 34 route (``compose.exapp.yml``, default names of
``topology.py``), without the Tasks app::

    set -a && . ./.env.exapp && set +a
    NC_MCP_EXPECT_TASKS_APP=0 PYTHONUTF8=1 uv run --no-sync pytest \\
        tests/integration/test_tasks_live.py -m integration -s -q -p no:xdist

and against Nextcloud 35 (``compose.nc35.yml``, containers started, never bootstrapped)::

    set -a && . <main checkout>/.env.nc35 && set +a
    export NC_MCP_E2E_COMPOSE_FILE=compose.nc35.yml NC_MCP_E2E_PROJECT=nc-mcp-nc35 \\
        NC_MCP_E2E_NEXTCLOUD=nc35-nc NC_MCP_E2E_HARP=nc35-harp NC_MCP_E2E_CADDY=nc35-caddy \\
        NC_MCP_E2E_CONTAINERS=nc35-nc,nc_app_mcp_connector,nc35-harp,nc35-caddy,nc35-greenmail
    NC_MCP_EXPECT_TASKS_APP=1 PYTHONUTF8=1 uv run --no-sync pytest \\
        tests/integration/test_tasks_live.py -m integration -s -q -p no:xdist

Two optional switches of plan 32-10, both unset in CI: ``NC_MCP_TASKS_CAP_SERIES=1`` builds a
list of bob with 520 open tasks for the cap of 500 (case ``deckel-500``, otherwise
``entfaellt``), and ``NC_MCP_TASKS_BOB_DISPLAY=<name>`` gives bob that display name for the run
and puts the old one back before the closing baseline (line ``ANZEIGENAME``), so the scan for
the owner also covers a display name other than the account id.

Plan 33-10 adds the live proof of the modifying tools ``tasks_complete``, ``tasks_update`` and
``tasks_move`` (TMOD-06), called as functions under the same impersonation, so the switch
``NC_MCP_TASKS_UPDATE`` plays no part here. Their objects carry the head ``p3310-<stamp>``,
live in the lists of the run and go with them. Each of those cases writes one more line
``FALL <case> nc=<version> werkzeug=<tool> status=<calls> ergebnis=<ok|befund> | <marks>``
with yes/no marks and short sha256 values of the column ``calendardata`` only, never an
object, list or account name, so the evidence can quote it as it stands.

The env files are only ever loaded with ``set -a``, never read or quoted. Without that
environment the module skips; with ``NC_MCP_REQUIRE_LIVE=1`` it fails instead (W3 of phase
31), which is how the CI steps run it.
"""

import asyncio
import base64
import dataclasses
import json
import os
import re
import secrets
import statistics
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import canary_world as cw
import httpx
import pytest
import topology
from lxml import etree

from mcp_connector import ids, provider_map
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
#: Every task object of plan 33-10 (the modifying tools) carries this head instead.
M = f"p3310-{STAMP}"
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

#: Shares of one group in ``dav_shares``: the side of the group (plan 32-10).
PHP_GROUP_SHARES = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->select($qb->func()->count('*', 'n'))->from('dav_shares')
    ->where($qb->expr()->eq(
        'principaluri', $qb->createNamedParameter('principals/groups/' . $argv[1])
    ));
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
    #: The keys of the two lists bob shared with the test group (plan 32-10).
    grw_key: str = ""
    gro_key: str = ""
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
    # Plan 32-10: two lists of bob, shared with the test group that holds alice.
    "grw": ("bob", f"{P}-grw", f"{P}-grw"),
    "gro": ("bob", f"{P}-gro", f"{P}-gro"),
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
    "fremdfaellig": ("rw", f"{P}-fremdfaellig", ("DUE;VALUE=DATE:20261204",)),
    "fremdro": ("ro", f"{P}-fremdro", ()),
    "gruppeohne": ("grw", f"{P}-gruppeohne", ()),
    "gruppefaellig": ("grw", f"{P}-gruppefaellig", ("DUE;VALUE=DATE:20261204",)),
    "gruppero": ("gro", f"{P}-gruppero", ()),
}
FRESH, NEVER = f"{P}-frisch", f"{P}-nie"
#: D-32-18 (plan 32-09): an account with exactly one own task list, which it shares itself.
OUT_USER = f"p32live{STAMP}aus"
OUT_LIST = f"{P}-aus"
#: Plan 32-10: the test group (bob and alice), the cap list of bob and two optional switches.
GROUP = f"p32live{STAMP}grp"
CAP_LIST = f"{P}-deckel"
CAP_TASKS = 520
ENV_CAP_SERIES = "NC_MCP_TASKS_CAP_SERIES"
ENV_BOB_DISPLAY = "NC_MCP_TASKS_BOB_DISPLAY"
#: The three recurring forms of plan 32-10, put into list b of alice: form -> title.
RECURRING = {
    "app": f"{P}-wieder-app",
    "instanz-erledigt": f"{P}-wieder-instanz",
    "master-erledigt": f"{P}-wieder-master",
}
#: The form of a recurring task the Tasks app 0.18.1 writes (phase 30), the template of all three.
RECURRING_TEMPLATE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "tasks_app" / "recurring.ics"
)
_SECOND_OCCURRENCE = "20261121T130000Z"
_DONE_LINES = ("STATUS:COMPLETED", "PERCENT-COMPLETE:100", "COMPLETED:20261121T140000Z")


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


def share_body(
    user: str, *, writable: bool, remove: bool = False, principal: str = "users"
) -> bytes:
    """The share document of the calendar sharing plugin, as ``scripts/tasks_spike.py``.

    ``principal="groups"`` shares with the group ``user`` instead of a person (plan 32-10).
    """
    root = etree.Element(f"{{{OC_SHARE_NS}}}share", nsmap={"d": dav_xml.DAV, "o": OC_SHARE_NS})
    entry = etree.SubElement(root, f"{{{OC_SHARE_NS}}}{'remove' if remove else 'set'}")
    etree.SubElement(
        entry, f"{{{dav_xml.DAV}}}href"
    ).text = f"principal:principals/{principal}/{user}"
    if writable and not remove:
        etree.SubElement(entry, f"{{{OC_SHARE_NS}}}read-write")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def publish_body(*, publish: bool) -> bytes:
    """Publish or unpublish a calendar by link, as ``scripts/tasks_measure.py``."""
    name = "publish-calendar" if publish else "unpublish-calendar"
    root = etree.Element(f"{{{dav_xml.CS}}}{name}", nsmap={"cs": dav_xml.CS})
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def recurring_ics(uid: str, title: str, form: str) -> str:
    """One recurring form of plan 32-10 from the Tasks app template, as the measuring program
    builds it (copied, because a test does not load a measuring program)."""
    lines = RECURRING_TEMPLATE.read_text(encoding="utf-8").replace("\r\n", "\n").splitlines()
    master = [
        f"UID:{uid}" if line.startswith("UID:") else line
        for line in (f"SUMMARY:{title}" if line.startswith("SUMMARY:") else line for line in lines)
    ]
    end = master.index("END:VTODO")
    if form == "master-erledigt":
        master[end:end] = list(_DONE_LINES)
    elif form == "instanz-erledigt":
        master[end + 1 : end + 1] = [
            "BEGIN:VTODO",
            f"UID:{uid}",
            "DTSTAMP:20261121T140000Z",
            f"SUMMARY:{title}",
            f"RECURRENCE-ID:{_SECOND_OCCURRENCE}",
            f"DUE:{_SECOND_OCCURRENCE}",
            *_DONE_LINES,
            "END:VTODO",
        ]
    return "\r\n".join(master) + "\r\n"


def group_members() -> list[str] | None:
    """The members of the test group, ``None`` when it does not exist."""
    raw = cw.occ("group:list", "--output=json")
    members = json.loads(raw[raw.find("{") :]).get(GROUP)
    if members is None:
        return None
    return [str(member) for member in members] if isinstance(members, list) else []


def group_line(run: "Run", phase: str) -> tuple[bool, str]:
    exists = group_members() is not None
    shares = php(PHP_GROUP_SHARES, GROUP)
    record(
        f"GRUPPE nc{run.version} name={GROUP} vorhanden={'ja' if exists else 'nein'} "
        f"shares={shares} phase={phase}"
    )
    return exists, shares


def display_name_of(user: str) -> str:
    info = json.loads(cw.occ("user:info", user, "--output=json"))
    return str(info.get("display_name") or info.get("displayname") or "")


def set_bob_display(run: "Run", value: str) -> str:
    """The display name of bob set to ``value``: first with occ, then through OCS as bob.

    Returns the way that carried (``occ`` or ``ocs``), empty when neither did.
    """
    cw.occ("user:setting", run.bob, "settings", "display_name", value, check_status=False)
    if display_name_of(run.bob) == value:
        return "occ"
    run.harness_bob.request(
        "PUT",
        f"{run.env['base_url']}/ocs/v2.php/cloud/users/{quote(run.bob, safe='')}",
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        data={"key": "displayname", "value": value},
    )
    if display_name_of(run.bob) == value:
        return "ocs"
    return ""


def _build(run: Run) -> None:
    """Lists, shares, tasks and the Deck board, all through the harness with app passwords."""
    for argv in (
        ("group:add", GROUP),
        ("group:adduser", GROUP, run.bob),
        ("group:adduser", GROUP, run.alice),
    ):
        cw.occ(*argv, check_status=False)
    members = set(group_members() or [])
    both = {run.alice, run.bob} <= members
    record(f"SETUP gruppe mitglieder={len(members)} alice_und_bob={'ja' if both else 'nein'}")
    assert both, "the test group does not hold bob and alice"
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
    for role, writable in (("grw", True), ("gro", False)):
        response = run.harness_bob.request(
            "POST",
            list_url(run, role),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            content=share_body(GROUP, writable=writable, principal="groups"),
        )
        assert response.status_code < 300, f"group share {role}: {response.status_code}"
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
    for form, title in RECURRING.items():
        uid = f"{P}-wieder-{form}-{uuid.uuid4().hex[:6]}"
        response = run.harness.request(
            "PUT",
            f"{list_url(run, 'b')}{uid}.ics",
            headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
            content=recurring_ics(uid, title, form),
        )
        assert response.status_code == 201, f"PUT wieder-{form}: {response.status_code}"
        run.objects[f"wieder-{form}"] = f"{uid}.ics"
    shared = {entry.name: entry for entry in run.harness.task_lists() if entry.shared}
    run.rw_key = shared[LISTS["rw"][2]].key
    run.ro_key = shared[LISTS["ro"][2]].key
    run.grw_key = shared[LISTS["grw"][2]].key
    run.gro_key = shared[LISTS["gro"][2]].key

    run.deck_marker = f"dk{uuid.uuid4().hex}"
    run.board_id = run.harness.deck_created("/boards", {"title": f"{P}-deck", "color": "0082c9"})
    stack = run.harness.deck_created(f"/boards/{run.board_id}/stacks", {"title": P, "order": 1})
    run.card_id = run.harness.deck_created(
        f"/boards/{run.board_id}/stacks/{stack}/cards",
        {"title": f"{P}-karte", "type": "plain", "order": 1, "description": run.deck_marker},
    )
    card = run.harness.deck("GET", f"/boards/{run.board_id}/stacks/{stack}/cards/{run.card_id}")
    assert run.deck_marker in card.text, f"deck card without its marker: {card.status_code}"


def _purge_calendar_trash(harness: cw.Harness) -> tuple[int, int]:
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
    found = cleared = 0
    origin = httpx.URL(harness.base_url)
    for entry in etree.fromstring(response.content).iter("{DAV:}response"):
        data = "".join(str(part) for part in entry.itertext())
        data = data.replace("\r\n ", "").replace("\n ", "")
        href = entry.findtext("{DAV:}href") or ""
        if (P in data or M in data) and href:
            gone = harness.request(
                "DELETE", str(origin.copy_with(path=href, query=None)), headers=NO_TRASHBIN
            )
            found += 1
            cleared += 1 if gone.status_code in (200, 204) else 0
    return found, cleared


def _teardown(run: Run) -> list[str]:
    """Remove everything of this run through the harness, never through the connector."""
    lines: list[str] = []
    for role, sharee, principal in (
        ("rw", run.alice, "users"),
        ("ro", run.alice, "users"),
        ("grw", GROUP, "groups"),
        ("gro", GROUP, "groups"),
    ):
        response = run.harness_bob.request(
            "POST",
            list_url(run, role),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            content=share_body(sharee, writable=False, remove=True, principal=principal),
        )
        lines.append(f"RUECKBAU freigabe {role} status={response.status_code}")
    for role in LISTS:
        status = owner_harness(run, role).delete_calendar_url(list_url(run, role))
        left = owner_harness(run, role).status_of(list_url(run, role))
        lines.append(f"RUECKBAU liste {role} delete={status} no_trashbin=1 danach={left}")
    cap_url = run.harness_bob.calendar_url(CAP_LIST)
    status = run.harness_bob.delete_calendar_url(cap_url)
    lines.append(
        f"RUECKBAU liste deckel delete={status} no_trashbin=1 "
        f"danach={run.harness_bob.status_of(cap_url)}"
    )
    if run.board_id:
        run.harness.deck("DELETE", f"/boards/{run.board_id}")
        lines.append(f"RUECKBAU deck board={run.board_id} {run.harness.board_state(run.board_id)}")
    for label, harness in (("alice", run.harness), ("bob", run.harness_bob)):
        found, cleared = _purge_calendar_trash(harness)
        lines.append(f"RUECKBAU papierkorb {label} entfernt={cleared}")
        lines.append(f"PAPIERKORB nc{run.version} konto={label} gefunden={found} geleert={cleared}")
    if run.harness_out is not None:
        lines.extend(_teardown_out(run, run.harness_out))
    for uid in (FRESH, NEVER, OUT_USER):
        out = cw.occ("user:delete", uid, check_status=False)
        lines.append(f"RUECKBAU konto {uid} {'geloescht' if 'deleted' in out else 'nicht da'}")
    if group_members() is not None:
        cw.occ("group:delete", GROUP, check_status=False)
    lines.append(f"RUECKBAU gruppe {'noch da' if group_members() is not None else 'geloescht'}")
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
    body = share_body(GROUP, writable=False, remove=True, principal="groups")
    status = harness.request("POST", url, headers=xml_head, content=body).status_code
    lines.append(f"RUECKBAU gruppenfreigabe aus status={status}")
    status = harness.request(
        "POST", url, headers=xml_head, content=publish_body(publish=False)
    ).status_code
    lines.append(f"RUECKBAU link aus status={status}")
    # The object deleted after the positive control lies in the trash bin; it is purged
    # before the list goes, so the line shows it (deleting the list would take it as well).
    found, purged = _purge_calendar_trash(harness)
    lines.append(f"RUECKBAU papierkorb {OUT_USER} vor-liste entfernt={purged}")
    lines.append(
        f"PAPIERKORB nc{run.version} konto={OUT_USER} gefunden={found} geleert={purged} "
        "phase=vor-liste"
    )
    status = harness.delete_calendar_url(url)
    lines.append(
        f"RUECKBAU liste aus delete={status} no_trashbin=1 danach={harness.status_of(url)}"
    )
    found, purged = _purge_calendar_trash(harness)
    lines.append(f"RUECKBAU papierkorb {OUT_USER} entfernt={purged}")
    lines.append(
        f"PAPIERKORB nc{run.version} konto={OUT_USER} gefunden={found} geleert={purged} "
        "phase=nach-liste"
    )
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
    group_before = group_line(state, "vorher")
    assert group_before == (False, "0"), f"the test group exists before the run: {group_before}"
    exclusion_core.clear_cache()
    capabilities.clear_cache()
    lines: list[str] = []
    display_before = state.bob_display
    wanted_display = (os.environ.get(ENV_BOB_DISPLAY) or "").strip()
    display_way = ""
    try:
        if wanted_display:
            display_way = set_bob_display(state, wanted_display)
            if display_way:
                state.bob_display = wanted_display
            else:
                record("ANZEIGENAME bob gesetzt=nein grund=kein-weg-traegt (Grenze im Beleg)")
        _build(state)
        yield state
    finally:
        try:
            lines = _teardown(state)
        finally:
            for line in lines:
                record(line)
            if display_way:
                back = set_bob_display(state, display_before)
                same = display_name_of(state.bob) == display_before
                record(
                    f"ANZEIGENAME bob gesetzt=ja zurueck={'ja' if back else 'nein'} "
                    f"gleich_vorher={'ja' if same else 'nein'} weg={display_way}"
                )
            elif not wanted_display:
                record("ANZEIGENAME bob gesetzt=nein zurueck=entfaellt gleich_vorher=ja")
            harness.close()
            harness_bob.close()
            exclusion_core.clear_cache()
    group_after = group_line(state, "nachher")
    assert group_after == (False, "0"), f"the test group is left: {group_after}"
    if display_way:
        assert display_name_of(state.bob) == display_before, "the display name of bob is not back"
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
    run: Run,
    user: str,
    seen: list[Seen],
    secret: str = "",
    slow_uri: str = "",
    on_request: Callable[[httpx.Request], Awaitable[None]] | None = None,
) -> NcClients:
    """Impersonating clients for one call: ``APP_SECRET`` is the only credential.

    The response hook notes the method, the path below the calendar home and the status of
    every answer. With ``slow_uri`` it holds back the REPORT answer of that one list longer
    than the budget of a list: the outage is made in the client, the server is real.
    ``on_request`` runs before a request leaves (plan 33-10, a change made by the harness
    between the read of the chain and one of its writes).
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

    hooks: dict[str, list[Any]] = {"response": [hook]}
    if on_request is not None:
        hooks["request"] = [on_request]
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False, timeout=30.0, event_hooks=hooks),
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
    case: Case,
    secret: str = "",
    slow_uri: str = "",
    on_request: Callable[[httpx.Request], Awaitable[None]] | None = None,
) -> AsyncIterator[NcClients]:
    """The clients of one tool call: fresh caches, calls into ``case``."""
    exclusion_core.clear_cache()
    capabilities.clear_cache()
    clients = appapi_clients(case.run, case.user, case.seen, secret, slow_uri, on_request)
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
    keys = {"rw": run.rw_key, "ro": run.ro_key, "grw": run.grw_key, "gro": run.gro_key}
    key = keys.get(list_role, LISTS[list_role][1])
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
        # Plan 33-11: a list missing from the hits is either named here (budget or error) or
        # was not in the discovery at all; without this line a failure cannot tell which.
        case.note(f"degraded {answer.get('degraded') or 'keine'}")


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
        case.expect(GROUP.casefold() not in text.casefold(), "no group id")


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


def _ensure_out(run: Run) -> cw.Harness:
    """The account of D-32-18 with exactly one own task list, made once per run."""
    if run.harness_out is not None:
        return run.harness_out
    password = f"{secrets.token_urlsafe(18)}Aa1!"
    record(f"SETUP d-32-18 occ user:add {add_account(OUT_USER, password)} konto={OUT_USER}")
    run.accounts.append(OUT_USER)
    run.harness_out = cw.Harness(cw.LiveEnv(run.env["base_url"], OUT_USER, password))
    status = run.harness_out.mk_task_list(OUT_LIST, OUT_LIST)
    record(f"SETUP d-32-18 MKCALENDAR liste={OUT_LIST} status={status}")
    assert status == 201, f"MKCALENDAR {OUT_LIST}: {status}"
    return run.harness_out


async def test_d_32_18_an_own_list_shared_with_others_is_only_written_when_named(
    run: Run,
) -> None:
    """The account of this case has exactly one own task list; it shares it itself."""
    harness_out = _ensure_out(run)

    # Positive control: nobody else sees the list, so it is written without list.
    first = await _out_written(run, "d-32-18-privat")
    _, (_, object_name) = ids.parse(first)
    gone = harness_out.request(
        "DELETE", f"{harness_out.calendar_url(OUT_LIST)}{quote(object_name, safe='')}"
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


async def _shared_subline_case(
    run: Run, label: str, role: str, *, dated: bool, list_role: str = "rw"
) -> None:
    """D-32-17 for one task of a writable share: raw subline first, then the connector."""
    if not run.expect_app:
        record(
            f"AUFGABE {label} nc={run.version} nutzer={run.alice} status=keine "
            "ergebnis=entfaellt | without the Tasks app the provider tasks does not exist"
        )
        return
    title, name = TASKS[role][1], LISTS[list_role][2]
    with Case(run, label) as case:
        raw = _raw_provider_subline(run, title)
        case.expect(raw is not None, f"the provider finds the task of the {list_role} share")
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
        for part, value in (("subline", subline or ""), ("text", text or "")):
            case.expect(not _names_bob(run, value), f"{part} without bob")
            case.expect("_shared_by_" not in value, f"{part} without the share marker")
        if raw_owner:
            # With a due date the raw subline ends with " (<raw name>)"; without one it is the
            # bare "(<raw name>)" (measured on 35). The cleaned line keeps the form, no owner.
            case.note(f"bereinigt={subline!r}")
            cleaned = str(subline or "")
            ok = (
                cleaned.endswith(f" ({name})") and len(cleaned) > len(name) + 3
                if dated
                else cleaned == f"({name})"
            )
            case.expect(ok, "the subline ends with the list name without the owner")
        else:
            case.expect((subline or "") == raw, "without an owner the subline is the raw one")
        case.expect(text == (subline or ""), "search text equals the subline")


async def test_d_32_17_the_subline_of_a_shared_list_hit_names_nobody(run: Run) -> None:
    await _shared_subline_case(run, "d-32-17-geteilt", "fremdrw", dated=False)


async def test_d_32_17_a_dated_shared_list_hit_keeps_its_date_and_names_nobody(
    run: Run,
) -> None:
    await _shared_subline_case(run, "d-32-17-geteilt-faellig", "fremdfaellig", dated=True)


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


# --- plan 32-10: an own list shared with a group (D-32-18 for groups) -----------------------


async def test_d_32_18_an_own_list_shared_with_a_group_is_only_written_when_named(
    run: Run,
) -> None:
    """The account of D-32-18 shares its one own list with the test group, read only and
    read-write; the account itself is no member of the group."""
    _ensure_out(run)
    # Positive control: before the group share the list is written without list.
    parent = await _out_written(run, "d-32-18-gruppe-privat")
    status = _out_post(run, share_body(GROUP, writable=False, principal="groups"))
    record(f"SETUP d-32-18-gruppe FREIGABE an-gruppe-ro status={status}")
    assert status < 300, f"group share: {status}"
    await _out_refused(run, "d-32-18-gruppe-ro")
    status = _out_post(run, share_body(GROUP, writable=True, principal="groups"))
    record(f"SETUP d-32-18-gruppe FREIGABE an-gruppe-rw status={status}")
    assert status < 300, f"group share: {status}"
    await _out_refused(run, "d-32-18-gruppe-rw")
    await _out_refused(run, "d-32-18-gruppe-parent", parent=parent)
    status = _out_post(run, share_body(GROUP, writable=False, remove=True, principal="groups"))
    record(f"SETUP d-32-18-gruppe FREIGABE zurueck status={status}")
    await _out_written(run, "d-32-18-gruppe-zurueck")


# --- plan 32-10: lists bob shared with a group that holds alice -----------------------------


def _names_group(text: str) -> bool:
    return GROUP.casefold() in text.casefold()


async def test_group_shares_into_the_account_carry_no_owner_and_the_right_flags(
    run: Run,
) -> None:
    with Case(run, "gruppe-rein-flags") as case:
        answer = await search(case, query=P, status="all")
        lists = {
            hit["list"]["name"]: hit["list"]
            for hit in answer.get("tasks") or []
            if isinstance(hit, dict) and isinstance(hit.get("list"), dict)
        }
        raw = run.harness.home_raw().text
        suffixed = sum(1 for role in ("grw", "gro") if f"{LISTS[role][2]} (" in raw)
        case.note(f"roher displayname mit zusatz in der discovery: {suffixed} von 2")
        case.expect(suffixed == 2, "positive control: the server adds the owner to both")
        for role, writable in (("grw", True), ("gro", False)):
            entry = lists.get(LISTS[role][2])
            case.expect(
                entry == {"name": LISTS[role][2], "shared": True, "writable": writable},
                f"{role}: {entry}",
            )
        found = hit_ids(answer)
        case.expect(task_id(run, "gruppeohne") in found, "the task of grw is a hit")
        case.expect(task_id(run, "gruppero") in found, "the task of gro is a hit")
        case.expect(not _names_group(json.dumps(answer)), "no group id in the answer")


async def test_without_list_a_group_share_is_offered_by_name_and_key_only(run: Run) -> None:
    counts = {role: list_objects(run.bob, LISTS[role][1]) for role in ("grw", "gro")}
    with Case(run, "gruppe-rein-ohne-list") as case:
        async with measured(case) as clients:
            exc = await refusal(run, tasks_tools.create_task(clients, summary=f"{P}-gohne"))
        after = {role: list_objects(run.bob, LISTS[role][1]) for role in ("grw", "gro")}
        text = f"{exc.message} {exc.hint}"
        case.expect("more than one task list" in exc.message, told(exc))
        offered = f"{LISTS['grw'][2]} (shared, key {run.grw_key})"
        case.expect(offered in exc.hint, f"hint offers the rw group share: {exc.hint!r}")
        case.expect(LISTS["gro"][2] not in exc.hint, "the read only group share is not offered")
        case.expect(not methods(case.seen, "PUT"), "the hook saw no PUT")
        case.expect(counts == after, f"calendarobjects vorher={counts} nachher={after}")
        case.expect(not _names_bob(run, text), "neither the id nor the display name of bob")
        case.expect(not _names_group(text) and "_shared_by_" not in text, "no group, no marker")


async def test_a_named_group_share_with_write_access_is_written_to(run: Run) -> None:
    before = list_objects(run.bob, LISTS["grw"][1])
    with Case(run, "gruppe-rein-rw-mit-list") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.create_task(
                    clients, summary=f"{P}-in-grw", list_name=LISTS["grw"][2]
                ),
            )
        _, (key, object_name) = ids.parse(str(answer["id"]))
        got = run.harness_bob.request("GET", f"{list_url(run, 'grw')}{quote(object_name)}")
        after = list_objects(run.bob, LISTS["grw"][1])
        case.expect(key == run.grw_key, f"the id carries the hashed key: {key == run.grw_key}")
        case.expect(
            got.status_code == 200 and f"SUMMARY:{P}-in-grw" in got.text,
            f"GET by the owner {got.status_code}",
        )
        case.expect(after == before + 1, f"calendarobjects vorher={before} nachher={after}")
        case.expect(methods(case.seen, "PUT") == [201], f"PUT {methods(case.seen, 'PUT')}")
        case.expect(
            answer.get("list") == {"name": LISTS["grw"][2], "shared": True, "writable": True},
            f"list {answer.get('list')}",
        )


async def test_a_read_only_group_share_is_refused_before_any_put(run: Run) -> None:
    before = list_objects(run.bob, LISTS["gro"][1])
    with Case(run, "gruppe-rein-ro-vorab") as case:
        async with measured(case) as clients:
            exc = await refusal(
                run,
                tasks_tools.create_task(clients, summary=f"{P}-in-gro", list_name=LISTS["gro"][2]),
            )
        after = list_objects(run.bob, LISTS["gro"][1])
        case.expect(exc.reason == REASON_GUARD_TRIPPED, told(exc))
        case.expect("read only" in exc.message, exc.message)
        case.expect(not methods(case.seen, "PUT"), "the hook saw no PUT")
        case.expect(before == after, f"calendarobjects vorher={before} nachher={after}")
        case.expect(not _names_group(f"{exc.message} {exc.hint}"), "no group id")


async def test_a_parent_in_a_group_share_does_not_name_the_list(run: Run) -> None:
    """D-32-16 for a group share: ``parent`` alone is no explicit naming."""
    before = list_objects(run.bob, LISTS["grw"][1])
    with Case(run, "gruppe-rein-parent") as case:
        async with measured(case) as clients:
            exc = await refusal(
                run,
                tasks_tools.create_task(
                    clients, summary=f"{P}-gunter", parent=task_id(run, "gruppeohne")
                ),
            )
        after = list_objects(run.bob, LISTS["grw"][1])
        case.expect("shared list" in exc.message, told(exc))
        case.expect("list=" in exc.hint, f"hint {exc.hint!r}")
        case.expect(not methods(case.seen, "PUT"), "no PUT")
        case.expect(before == after, f"calendarobjects vorher={before} nachher={after}")


async def test_fetch_of_a_group_share_task_links_the_start_page_only(run: Run) -> None:
    """D-32-15 for a group share: the deep link would carry the account id of bob."""
    identifier = task_id(run, "gruppeohne")
    with Case(run, "gruppe-rein-fetch") as case:
        async with measured(case) as clients:
            fetched = keep(run, await chatgpt_tools.fetch(clients, identifier))
        url = str(fetched.get("url") or "")
        start = f"{run.env['base_url']}{provider_map.TASKS_WEB_PREFIX}"
        case.note(f"url={url[len(run.env['base_url']) :]!r}")
        case.expect(url == start, "the link is the start page of the Tasks app")
        case.expect("_shared_by_" not in url and not _names_bob(run, url), "no owner in the link")
        case.expect((fetched.get("metadata") or {}).get("shared") == "true", "metadata shared=true")
        case.expect(fetched.get("title") == TASKS["gruppeohne"][1], f"title {fetched.get('title')}")


async def test_d_32_17_the_subline_of_a_group_share_hit_names_nobody(run: Run) -> None:
    await _shared_subline_case(run, "d-32-17-gruppe", "gruppeohne", dated=False, list_role="grw")


async def test_d_32_17_a_dated_group_share_hit_keeps_its_date_and_names_nobody(
    run: Run,
) -> None:
    await _shared_subline_case(
        run, "d-32-17-gruppe-faellig", "gruppefaellig", dated=True, list_role="grw"
    )


# --- plan 32-10: recurring tasks in the form of the Tasks app (TASK-02) ----------------------


async def _recurring_case(run: Run, form: str, *, open_hits: int, status: str) -> None:
    title = RECURRING[form]
    expected = ids.encode_task(LISTS["b"][1], run.objects[f"wieder-{form}"])
    with Case(run, f"wiederkehrend-{form}") as case:
        found: dict[str, list[dict[str, Any]]] = {}
        for wanted in ("open", "completed", "all"):
            answer = await search(case, list_name=LISTS["b"][2], status=wanted)
            found[wanted] = [
                hit
                for hit in answer.get("tasks") or []
                if isinstance(hit, dict) and hit.get("summary") == title
            ]
        case.note(" ".join(f"treffer_{key}={len(value)}" for key, value in found.items()))
        case.expect(len(found["open"]) == open_hits, f"open: {len(found['open'])}")
        case.expect(len(found["completed"]) == 1 - open_hits, f"done: {len(found['completed'])}")
        case.expect(len(found["all"]) == 1, f"all: one hit without expansion, {len(found['all'])}")
        hit = found["all"][0] if found["all"] else {}
        case.expect(hit.get("id") == expected, "the hit is the object of the harness")
        case.expect(hit.get("recurring") is True, f"recurring {hit.get('recurring')}")
        case.expect(hit.get("status") == status, f"status {hit.get('status')}")
        async with measured(case) as clients:
            read = keep(run, await tasks_tools.read_task(clients, task_id=expected))
        case.note(f"lesen status={read.get('status')} recurring={read.get('recurring')}")
        case.expect(read.get("recurring") is True, "tasks_read recurring=true")
        case.expect(read.get("status") == status, f"tasks_read status {read.get('status')}")
        case.expect(read.get("summary") == title, "the master and not the override")
        case.expect(
            read.get("due") == "2026-11-20T13:00:00+00:00", f"DUE as written {read.get('due')}"
        )


async def test_a_recurring_task_of_the_tasks_app_is_one_hit(run: Run) -> None:
    await _recurring_case(run, "app", open_hits=1, status="open")


async def test_a_recurring_task_with_a_completed_instance_stays_one_open_hit(run: Run) -> None:
    await _recurring_case(run, "instanz-erledigt", open_hits=1, status="open")


async def test_a_recurring_task_with_a_completed_master_is_one_completed_hit(run: Run) -> None:
    await _recurring_case(run, "master-erledigt", open_hits=0, status="completed")


# --- plan 32-10: the cap of 500 with 520 open tasks (only with NC_MCP_TASKS_CAP_SERIES=1) ---


def _put_cap_series(run: Run) -> tuple[int, int, float]:
    """520 open tasks into the cap list of bob, serially, with a retry on 5xx."""
    harness = run.harness_bob
    url = harness.calendar_url(CAP_LIST)
    failed = repeated = 0
    started = time.perf_counter()
    for number in range(CAP_TASKS):
        uid = f"{P}-deckel-{number:04d}"
        status = 0
        for attempt in range(4):
            status = harness.request(
                "PUT",
                f"{url}{uid}.ics",
                headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
                content=cw.todo_ics(uid, f"{P}-deckel {number:04d}"),
            ).status_code
            if status == 201 or (status == 412 and attempt):
                break
            if status < 500:
                break
            repeated += 1
            time.sleep(0.5 * (attempt + 1))
        failed += 0 if status == 201 or (status == 412 and repeated) else 1
    return failed, repeated, time.perf_counter() - started


async def test_the_cap_of_500_holds_live_with_an_honest_note(run: Run) -> None:
    if os.environ.get(ENV_CAP_SERIES) != "1":
        record(
            f"AUFGABE deckel-500 nc={run.version} nutzer={run.bob} status=keine "
            f"ergebnis=entfaellt | grund=serie-nicht-angefordert ({ENV_CAP_SERIES} is not 1)"
        )
        return
    status = run.harness_bob.mk_task_list(CAP_LIST, CAP_LIST)
    record(f"SETUP deckel-500 MKCALENDAR liste={CAP_LIST} status={status}")
    assert status == 201, f"MKCALENDAR {CAP_LIST}: {status}"
    failed, repeated, seconds = _put_cap_series(run)
    rows = list_objects(run.bob, CAP_LIST)
    record(
        f"SETUP deckel-500 aufgaben={CAP_TASKS} fehlgeschlagen={failed} wiederholt={repeated} "
        f"dauer_s={seconds:.0f} GEGENPROBE datenbank_zeilen={rows} "
        f"gleich={'ja' if rows == CAP_TASKS else 'nein'}"
    )
    assert rows == CAP_TASKS, f"the cap list holds {rows} objects"
    with Case(run, "deckel-500", user=run.bob) as case:
        pages: list[dict[str, Any]] = []
        took: list[float] = []
        cursor: str | None = None
        while len(pages) < 25:
            started = time.perf_counter()
            async with measured(case) as clients:
                answer = await tasks_tools.search_tasks(clients, list_name=CAP_LIST, cursor=cursor)
            took.append(time.perf_counter() - started)
            pages.append(answer)
            cursor = answer.get("next")
            if not cursor:
                break
        seen = [str(hit.get("id")) for page in pages for hit in page.get("tasks") or []]
        sizes = sorted({len(page.get("tasks") or []) for page in pages})
        last = pages[-1]
        case.note(
            f"seiten={len(pages)} je_seite={sizes} treffer={len(seen)} eindeutig={len(set(seen))} "
            f"letzte_truncated={last.get('truncated')} letzte_next={'next' in last} "
            f"max_seite_ms={max(took) * 1000:.0f} "
            f"median_seite_ms={statistics.median(took) * 1000:.0f} "
            f"budget_s={tasks_tools.PER_LIST_TIMEOUT:g}"
        )
        case.expect(len(pages) == 20, f"20 pages, got {len(pages)}")
        case.expect(sizes == [tasks_tools.PAGE_SIZE], f"pages of 25: {sizes}")
        case.expect(len(set(seen)) == len(seen) == 500, "500 distinct hits")
        case.expect(last.get("truncated") is True, "last page truncated")
        case.expect("next" not in last, "no next on the last page")
        case.expect(last.get("note") == tasks_tools.SEARCH_CAP_NOTE, f"note {last.get('note')!r}")
        case.expect(not any(page.get("degraded") for page in pages), "no degraded list")


# --- plan 33-10: the modifying tools, live under impersonation ---------------------------
#
# Every case below writes its AUFGABE line (with the account, for the raw protocol) and one
# line ``FALL <case> nc=<version> werkzeug=<tool> status=<calls> ergebnis=<ok|befund> | ...``
# that carries yes/no marks, field names and hashes only, never an object, list or account
# name, so docs/tasks-evidence.md can quote it as it stands. "Unchanged" is always the
# sha256 of the column ``calendardata`` read by PHP in the container (33-RULES.md section 7),
# never a status code.

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tasks_app"
#: The care fields every change brings to the same UTC second (ENTSCHEID pflegefelder_entfernen).
CARE_FIELDS = ("DTSTAMP", "LAST-MODIFIED")
#: The raw line of the Tasks app 0.18.1 completing a task (phase 30, raw/ui-sitzung.txt,
#: line ``ABHAKEN FELDER``): the field set a completion through the connector must match.
ABHAKEN_PHASE30 = (
    "hinzu=COMPLETED,PERCENT-COMPLETE,STATUS entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED"
)
REOPEN_FIELDS = (
    "hinzu=keine entfernt=COMPLETED,PERCENT-COMPLETE geaendert=DTSTAMP,LAST-MODIFIED,STATUS"
)
_DONE = ("STATUS:COMPLETED", "PERCENT-COMPLETE:100", "COMPLETED:20261113T080000Z")
_UTC_STAMP = re.compile(r"\d{8}T\d{6}Z")
#: A strong validator for calls that are refused before any request (Deck keys).
ANY_ETAG = '"p3310-etag"'

#: One live object of one list of one owner: count, sha256 and the column ``calendardata``
#: (base64, so the line ends survive the way through stdout).
PHP_OBJECT = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->select('o.calendardata')->from('calendarobjects', 'o')
    ->join('o', 'calendars', 'c', $qb->expr()->eq('o.calendarid', 'c.id'))
    ->where($qb->expr()->eq(
        'c.principaluri', $qb->createNamedParameter('principals/users/' . $argv[1])
    ))
    ->andWhere($qb->expr()->eq('c.uri', $qb->createNamedParameter($argv[2])))
    ->andWhere($qb->expr()->eq('o.uri', $qb->createNamedParameter($argv[3])))
    ->andWhere($qb->expr()->eq('o.calendartype', $qb->createNamedParameter(0)))
    ->andWhere($qb->expr()->isNull('o.deleted_at'));
$rows = $qb->executeQuery()->fetchAll();
if (count($rows) === 1) {
    $data = $rows[0]['calendardata'];
    if (is_resource($data)) {
        $data = stream_get_contents($data);
    }
    echo '1 ', hash('sha256', (string)$data), ' ', base64_encode((string)$data), "\n";
} else {
    echo count($rows), " - -\n";
}
"""
)


@dataclasses.dataclass(frozen=True)
class Obj:
    """One harness task of plan 33-10: list role, object name, UID and the id alice uses."""

    role: str
    name: str
    uid: str
    ident: str


@dataclasses.dataclass(frozen=True)
class Row:
    """One object as the database holds it: live rows, sha256 and the stored text."""

    count: int
    sha: str
    text: str

    @property
    def short(self) -> str:
        return self.sha[:12] if self.sha else "fehlt"


def list_key(run: Run, role: str) -> str:
    """The key alice sees for a list: the URI of an own list, the hash of a shared one."""
    shared = {"rw": run.rw_key, "ro": run.ro_key, "grw": run.grw_key, "gro": run.gro_key}
    return shared.get(role, LISTS[role][1])


def owner_of(run: Run, role: str) -> str:
    return run.alice if LISTS[role][0] == "alice" else run.bob


def app_form(uid: str, title: str, extra: tuple[str, ...] = ()) -> bytes:
    """A plain task in the shape the Tasks app 0.18.1 writes (CREATED, LAST-MODIFIED, CRLF)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//nc-mcp-connector//harness 33//EN",
        "BEGIN:VTODO",
        f"UID:{uid}",
        "CREATED:20261113T080000Z",
        "LAST-MODIFIED:20261113T080000Z",
        "DTSTAMP:20261113T080000Z",
        f"SUMMARY:{title}",
        *extra,
        "END:VTODO",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_bytes().decode("utf-8")


def with_time_form(uid: str, title: str) -> bytes:
    """``with_time.ics`` of the Tasks app (due and start with a time) under a new UID."""
    lines = fixture("with_time.ics").split("\r\n")
    swapped = [
        f"UID:{uid}"
        if line.startswith("UID:")
        else (f"SUMMARY:{title}" if line.startswith("SUMMARY:") else line)
        for line in lines
    ]
    return "\r\n".join(swapped).encode("utf-8")


def _fold(line: str) -> list[str]:
    """RFC 5545 folding of an ASCII line at 75 octets."""
    parts = [line[:75]]
    rest = line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return parts


def rich_form(uid: str, title: str) -> bytes:
    """The rich probe of ``scripts/tasks_spike.py`` (plan 30-04): VTIMEZONE, VALARM with its own
    DESCRIPTION, three X- properties, a parameter on SUMMARY and a folded DESCRIPTION."""
    description = (
        "DESCRIPTION:Eine Beschreibung mit mehr als fuenfundsiebzig Zeichen\\, damit die "
        "Zeile gefaltet werden muss und der Server sie beim Speichern nicht neu umbrechen darf."
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//nc-mcp-connector//harness 33//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Berlin",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:+0100",
        "TZOFFSETTO:+0200",
        "TZNAME:CEST",
        "DTSTART:19700329T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0200",
        "TZOFFSETTO:+0100",
        "TZNAME:CET",
        "DTSTART:19701025T030000",
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
        "BEGIN:VTODO",
        f"UID:{uid}",
        "DTSTAMP:20261111T100000Z",
        "CREATED:20261111T100000Z",
        "LAST-MODIFIED:20261111T100000Z",
        f"SUMMARY;X-P3310-PARAM=abc:{title}",
        *_fold(description),
        "DTSTART;TZID=Europe/Berlin:20261119T090000",
        "DUE;TZID=Europe/Berlin:20261120T101500",
        "CATEGORIES:p3310,wichtig",
        "CLASS:CONFIDENTIAL",
        "PRIORITY:1",
        "X-P3310-FOO:bar",
        "X-APPLE-SORT-ORDER:123",
        "X-OC-HIDESUBTASKS:1",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:p3310 Erinnerung",
        "TRIGGER:-PT15M",
        "END:VALARM",
        "END:VTODO",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def new_task(
    run: Run,
    role: str,
    label: str,
    extra: tuple[str, ...] = (),
    *,
    name: str = "",
    form: Callable[[str, str], bytes] | None = None,
) -> Obj:
    """One task put by the owner of the list with the app password, create-only."""
    uid = f"{M}-{label}-{uuid.uuid4().hex[:6]}"
    object_name = name or f"{uid}.ics"
    title = f"{M}-{label}"
    body = form(uid, title) if form is not None else app_form(uid, title, extra)
    response = owner_harness(run, role).request(
        "PUT",
        f"{list_url(run, role)}{quote(object_name, safe='')}",
        headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
        content=body,
    )
    assert response.status_code == 201, f"PUT {label}: {response.status_code}"
    return Obj(role, object_name, uid, ids.encode_task(list_key(run, role), object_name))


def row(run: Run, role: str, object_name: str) -> Row:
    """The object as the database of the owner holds it (independent of the connector)."""
    raw = php(PHP_OBJECT, owner_of(run, role), LISTS[role][1], object_name).split(" ")
    assert len(raw) == 3, f"no row answer: {' '.join(raw)[:120]}"
    assert raw[0].isdigit(), f"no row count: {raw[0][:40]}"
    if raw[0] != "1":
        return Row(int(raw[0]), "", "")
    return Row(1, raw[1], base64.b64decode(raw[2]).decode("utf-8"))


async def etag_of(run: Run, identifier: str) -> str:
    """The ETag tasks_read hands out, read outside the measured calls of a case."""
    reader = Case(run, "etag")
    async with measured(reader) as clients:
        answer = keep(run, await tasks_tools.read_task(clients, task_id=identifier))
    etag = str(answer.get("etag") or "")
    assert etag, f"tasks_read sent no etag: {answered(answer)}"
    return etag


def touch(run: Run, role: str, object_name: str) -> int:
    """A change by the owner between tasks_read and the tool: SUMMARY gets a suffix."""
    harness = owner_harness(run, role)
    url = f"{list_url(run, role)}{quote(object_name, safe='')}"
    got = harness.request("GET", url)
    assert got.status_code == 200, f"GET for the change of the harness: {got.status_code}"
    lines = got.content.decode("utf-8").split("\r\n")
    changed = [f"{line}-geaendert" if line.startswith("SUMMARY") else line for line in lines]
    return harness.request(
        "PUT",
        url,
        headers={
            "Content-Type": "text/calendar; charset=utf-8",
            "If-Match": got.headers.get("ETag", ""),
        },
        content="\r\n".join(changed).encode("utf-8"),
    ).status_code


def _unfold(text: str) -> list[str]:
    plain = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line for line in re.sub(r"\n[ \t]", "", plain).split("\n") if line.strip()]


def _prop(line: str) -> str:
    return re.split(r"[;: ]", line.strip(), maxsplit=1)[0].upper()


def _value(line: str) -> str:
    quoted = False
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == ":" and not quoted:
            return line[index + 1 :]
    return ""


def todo_lines(text: str) -> dict[str, list[str]]:
    """Logical lines directly inside ``VCALENDAR/VTODO`` by property name, as ``line_diff``
    of ``scripts/tasks_modify_measure.py`` reads them (copied: a test loads no measuring
    program)."""
    stack: list[str] = []
    found: dict[str, list[str]] = {}
    for line in _unfold(text):
        upper = line.strip().upper()
        if upper.startswith("BEGIN:"):
            stack.append(upper[6:])
        elif upper.startswith("END:"):
            if stack:
                stack.pop()
        elif stack == ["VCALENDAR", "VTODO"]:
            found.setdefault(_prop(line), []).append(line.rstrip())
    return {name: sorted(lines) for name, lines in found.items()}


def field_diff(before: str, after: str) -> str:
    """``hinzu=... entfernt=... geaendert=...`` (and ``leer=...`` when a value went empty),
    in the form of the raw line ``ABHAKEN FELDER`` of phase 30."""
    old, new = todo_lines(before), todo_lines(after)
    parts: dict[str, list[str]] = {"hinzu": [], "entfernt": [], "geaendert": [], "leer": []}
    for name in sorted(old.keys() | new.keys()):
        was, now = old.get(name, []), new.get(name, [])
        if was == now:
            continue
        if not was:
            parts["hinzu"].append(name)
        elif not now:
            parts["entfernt"].append(name)
        elif all(not _value(line).strip() for line in now) and any(
            _value(line).strip() for line in was
        ):
            parts["leer"].append(name)
        else:
            parts["geaendert"].append(name)
    text = " ".join(
        f"{key}={','.join(parts[key]) or 'keine'}" for key in ("hinzu", "entfernt", "geaendert")
    )
    return f"{text} leer={','.join(parts['leer'])}" if parts["leer"] else text


def shape(text: str, names: tuple[str, ...]) -> list[str]:
    """The lines of ``names`` with every UTC stamp replaced: the written form, not the time."""
    lines = todo_lines(text)
    return [_UTC_STAMP.sub("<utc>", line) for name in names for line in lines.get(name, [])]


def crlf_only(text: str) -> bool:
    return text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")


def physical_kept(text: str, touched: set[str]) -> list[str]:
    """The physical lines of every logical line whose property is not in ``touched``."""
    groups: list[list[str]] = []
    for line in text.split("\r\n"):
        if line.startswith((" ", "\t")) and groups:
            groups[-1].append(line)
        elif line:
            groups.append([line])
    return [line for group in groups if _prop(group[0]) not in touched for line in group]


def block(text: str, component: str) -> list[str]:
    """The physical lines from ``BEGIN:<component>`` to its ``END``, as stored."""
    lines = text.split("\r\n")
    try:
        first = lines.index(f"BEGIN:{component}")
        last = lines.index(f"END:{component}", first)
    except ValueError:
        return []
    return lines[first : last + 1]


def flag(value: bool) -> str:
    return "ja" if value else "nein"


class Fall(Case):
    """A case of plan 33-10: the AUFGABE line plus one quotable FALL line."""

    def __init__(self, run: Run, label: str, tool: str) -> None:
        super().__init__(run, label)
        self.tool = tool
        self.marks: list[str] = []

    def __enter__(self) -> "Fall":
        return self

    def mark(self, name: str, value: bool | int | str) -> None:
        shown = flag(value) if isinstance(value, bool) else str(value)
        self.marks.append(f"{name}={shown}")

    def check(self, name: str, ok: bool, note: str) -> None:
        """A yes/no mark that is also an expectation of the case."""
        self.mark(name, ok)
        self.expect(ok, note)

    def __exit__(self, kind: object, exc: BaseException | None, trace: object) -> None:
        verdict = "ok" if self.ok and exc is None else "befund"
        record(
            f"FALL {self.label} nc={self.run.version} werkzeug={self.tool} "
            f"status={calls(self.seen)} ergebnis={verdict} | {' '.join(self.marks)}"
        )
        super().__exit__(kind, exc, trace)


def writes(seen: list[Seen]) -> list[int]:
    return methods(seen, "PUT") + methods(seen, "MOVE")


# --- success criterion 1: completing and reopening -------------------------------------


async def test_p3310_completing_writes_the_field_set_of_the_tasks_app(run: Run) -> None:
    task = new_task(run, "a", "abhaken")
    etag = await etag_of(run, task.ident)
    before = row(run, "a", task.name)
    with Fall(run, "aendern-abhaken", "tasks_complete") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.complete_task(
                    clients, task_id=task.ident, etag=etag, completed=True
                ),
            )
        after = row(run, "a", task.name)
        got = field_diff(before.text, after.text)
        names = ("STATUS", "PERCENT-COMPLETE", "COMPLETED")
        stamps = {
            _value(todo_lines(after.text).get(name, [""])[0])
            for name in (*CARE_FIELDS, "COMPLETED")
        }
        case.note(f"felder {got}")
        case.check("felder_wie_phase30", got == ABHAKEN_PHASE30, f"{got} / {ABHAKEN_PHASE30}")
        case.check(
            "form_wie_completed_ics",
            shape(after.text, names) == shape(fixture("completed.ics"), names),
            f"{shape(after.text, names)}",
        )
        case.check("eine_sekunde", len(stamps) == 1, f"COMPLETED, DTSTAMP, LAST-MODIFIED {stamps}")
        case.check("ein_put", len(writes(case.seen)) == 1, f"writes {writes(case.seen)}")
        case.check("crlf", crlf_only(after.text), "the stored text keeps CRLF")
        case.check("antwort", answer.get("status") == "completed", answered(answer))
        case.mark("sha_vorher", before.short)
        case.mark("sha_nachher", after.short)


async def test_p3310_reopening_writes_the_field_set_of_the_tasks_app(run: Run) -> None:
    task = new_task(run, "a", "oeffnen", _DONE)
    etag = await etag_of(run, task.ident)
    before = row(run, "a", task.name)
    with Fall(run, "aendern-wiederoeffnen", "tasks_complete") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.complete_task(
                    clients, task_id=task.ident, etag=etag, completed=False
                ),
            )
        after = row(run, "a", task.name)
        got = field_diff(before.text, after.text)
        names = ("STATUS", "PERCENT-COMPLETE", "COMPLETED")
        case.note(f"felder {got}")
        case.check("felder", got == REOPEN_FIELDS, f"{got} / {REOPEN_FIELDS}")
        case.check(
            "form_wie_reopened_ics",
            shape(after.text, names) == shape(fixture("reopened.ics"), names),
            f"{shape(after.text, names)}",
        )
        case.check("ein_put", len(writes(case.seen)) == 1, f"writes {writes(case.seen)}")
        case.check("antwort", answer.get("status") == "open", answered(answer))
        case.mark("sha_vorher", before.short)
        case.mark("sha_nachher", after.short)


async def test_p3310_completing_a_completed_task_sends_no_put(run: Run) -> None:
    task = new_task(run, "a", "schon", _DONE)
    etag = await etag_of(run, task.ident)
    before = row(run, "a", task.name)
    with Fall(run, "aendern-schon-erledigt", "tasks_complete") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.complete_task(
                    clients, task_id=task.ident, etag=etag, completed=True
                ),
            )
        after = row(run, "a", task.name)
        case.check("kein_put", not writes(case.seen), f"writes {writes(case.seen)}")
        case.check("already", answer.get("already") is True, answered(answer))
        case.check("sha_gleich", before.sha == after.sha, f"{before.short} / {after.short}")
        case.mark("sha", after.short)


async def test_p3310_completing_a_parent_completes_its_subtasks_first(run: Run) -> None:
    parent = new_task(run, "a", "kinder-eltern")
    first = new_task(run, "a", "kinder-k1", (f"RELATED-TO:{parent.uid}",))
    grandchild = new_task(run, "a", "kinder-k1a", (f"RELATED-TO:{first.uid}",))
    second = new_task(run, "a", "kinder-k2", (f"RELATED-TO:{parent.uid}",))
    order = [grandchild, first, second, parent]
    etag = await etag_of(run, parent.ident)
    with Fall(run, "aendern-kinder", "tasks_complete") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.complete_task(
                    clients, task_id=parent.ident, etag=etag, completed=True
                ),
            )
        rows = [row(run, "a", task.name) for task in order]
        put_paths = [below for method, below, _ in case.seen if method == "PUT"]
        in_order = len(put_paths) == len(order) and all(
            path.endswith(f"/{task.name}") for path, task in zip(put_paths, order, strict=False)
        )
        done = all("STATUS:COMPLETED" in todo_lines(item.text).get("STATUS", []) for item in rows)
        case.check("puts_nachordnung", in_order, f"PUT order {len(put_paths)} of {len(order)}")
        case.check("alle_erledigt", done, "parent, children and grandchild STATUS:COMPLETED")
        case.check(
            "changed_nachordnung",
            answer.get("changed") == [task.ident for task in order],
            answered(answer),
        )
        case.check(
            "kinder_crlf", all(crlf_only(item.text) for item in rows[:-1]), "CRLF after REPORT"
        )
        case.check("eltern_crlf", crlf_only(rows[-1].text), "CRLF of the parent")
        case.mark("puts", len(methods(case.seen, "PUT")))


# --- success criterion 2: exactly the named fields --------------------------------------


async def _update_step(
    run: Run, task: Obj, label: str, step: str, fields: dict[str, Any]
) -> tuple[Row, Row, dict[str, Any], list[Seen]]:
    etag = await etag_of(run, task.ident)
    before = row(run, task.role, task.name)
    case = Case(run, label)
    async with measured(case) as clients:
        answer = keep(
            run, await tasks_tools.update_task(clients, task_id=task.ident, etag=etag, **fields)
        )
    after = row(run, task.role, task.name)
    case.note(step)
    return before, after, answer, case.seen


async def test_p3310_update_changes_exactly_the_named_fields_like_the_tasks_app(
    run: Run,
) -> None:
    task = new_task(run, "a", "felder", form=with_time_form)
    tags = [f"{M}-eins", f"{M}-zwei"]
    app_tags = field_diff(fixture("cleared_priority.ics"), fixture("cleared_tags.ics"))
    app_description = field_diff(fixture("cleared_start.ics"), fixture("cleared_description.ics"))
    app_due_gone = "DUE" not in todo_lines(fixture("cleared_due.ics"))
    steps: list[tuple[str, dict[str, Any], str, list[str]]] = [
        (
            "setzen",
            {"due": "2026-12-05T10:30:00Z", "tags": tags, "description": f"{M} beschreibung"},
            "hinzu=CATEGORIES,DESCRIPTION entfernt=keine geaendert=DTSTAMP,DUE,LAST-MODIFIED",
            ["description", "due", "tags"],
        ),
        (
            "due-entfernen",
            {"due": ""},
            "hinzu=keine entfernt=DUE geaendert=DTSTAMP,LAST-MODIFIED",
            ["due"],
        ),
        ("tags-entfernen", {"tags": []}, app_tags, ["tags"]),
        ("beschreibung-entfernen", {"description": ""}, app_description, ["description"]),
    ]
    for number, (step, fields, expected, changed) in enumerate(steps):
        if number:
            # A new UTC second, so the care fields of two steps can never coincide.
            await asyncio.sleep(1.1)
        with Fall(run, "aendern-felder", "tasks_update") as case:
            case.mark("schritt", step)
            before, after, answer, seen = await _update_step(
                run, task, "aendern-felder-schritt", step, fields
            )
            case.seen.extend(seen)
            got = field_diff(before.text, after.text)
            case.note(f"felder {got}")
            case.check("felder_wie_app", got == expected, f"{got} / {expected}")
            case.check("antwort_changed", answer.get("changed") == changed, answered(answer))
            case.check("ein_put", len(writes(seen)) == 1, f"writes {writes(seen)}")
            if step == "setzen":
                due_form = shape(after.text, ("DUE",)) == shape(fixture("with_time.ics"), ("DUE",))
                categories = todo_lines(after.text).get("CATEGORIES", [])
                one_line = categories == [f"CATEGORIES:{','.join(tags)}"]
                tags_form = len(todo_lines(fixture("tags.ics")).get("CATEGORIES", [])) == 1
                case.check("due_form_wie_with_time_ics", due_form, f"{shape(after.text, ('DUE',))}")
                case.check("tags_eine_zeile_wie_tags_ics", one_line and tags_form, f"{categories}")
            if step == "due-entfernen":
                case.check("form_zeile_weg_wie_app", app_due_gone, "cleared_due.ics has no DUE")
            case.mark("sha_vorher", before.short)
            case.mark("sha_nachher", after.short)


async def test_p3310_update_keeps_every_untouched_line_of_a_rich_object(run: Run) -> None:
    task = new_task(run, "a", "reich", form=rich_form)
    etag = await etag_of(run, task.ident)
    before = row(run, "a", task.name)
    touched = {"SUMMARY", "PRIORITY", *CARE_FIELDS}
    with Fall(run, "aendern-reich", "tasks_update") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.update_task(
                    clients, task_id=task.ident, etag=etag, summary=f"{M}-reich-neu", priority=2
                ),
            )
        after = row(run, "a", task.name)
        got = field_diff(before.text, after.text)
        expected = "hinzu=keine entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED,PRIORITY,SUMMARY"
        folded = [line for line in before.text.split("\r\n") if line.startswith(" ")]
        x_before = [line for line in before.text.split("\r\n") if line.startswith("X-")]
        x_after = [line for line in after.text.split("\r\n") if line.startswith("X-")]
        summary = todo_lines(after.text).get("SUMMARY", [])
        case.note(f"felder {got}")
        case.check("vorher_gefaltet", bool(folded), "the probe really holds a folded line")
        case.check("felder", got == expected, f"{got} / {expected}")
        case.check(
            "unberuehrte_zeilen_woertlich",
            physical_kept(before.text, touched) == physical_kept(after.text, touched),
            "every physical line of an untouched property as stored",
        )
        case.check(
            "valarm_gleich",
            block(before.text, "VALARM") == block(after.text, "VALARM") != [],
            "VALARM",
        )
        case.check(
            "vtimezone_gleich",
            block(before.text, "VTIMEZONE") == block(after.text, "VTIMEZONE") != [],
            "VTIMEZONE",
        )
        case.check("x_zeilen_gleich", x_before == x_after and len(x_before) == 3, f"{x_after}")
        case.check(
            "parameter_summary",
            summary == [f"SUMMARY;X-P3310-PARAM=abc:{M}-reich-neu"],
            f"{summary}",
        )
        case.check("antwort", answer.get("changed") == ["summary", "priority"], answered(answer))
        case.mark("sha_vorher", before.short)
        case.mark("sha_nachher", after.short)


async def test_p3310_update_without_a_difference_writes_nothing(run: Run) -> None:
    task = new_task(run, "a", "gleich")
    etag = await etag_of(run, task.ident)
    before = row(run, "a", task.name)
    with Fall(run, "aendern-ohne-unterschied", "tasks_update") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.update_task(
                    clients, task_id=task.ident, etag=etag, summary=f"{M}-gleich", priority=0
                ),
            )
        after = row(run, "a", task.name)
        case.check("kein_put", not writes(case.seen), f"writes {writes(case.seen)}")
        case.check("changed_leer", answer.get("changed") == [], answered(answer))
        case.check("sha_gleich", before.sha == after.sha, f"{before.short} / {after.short}")
        case.mark("sha", after.short)


# --- success criterion 3: stale, read only, recurring, Deck ------------------------------

ToolCall = Callable[[NcClients, str, str], Awaitable[dict[str, Any]]]


def _complete(clients: NcClients, identifier: str, etag: str) -> Awaitable[dict[str, Any]]:
    return tasks_tools.complete_task(clients, task_id=identifier, etag=etag, completed=True)


def _update(clients: NcClients, identifier: str, etag: str) -> Awaitable[dict[str, Any]]:
    return tasks_tools.update_task(clients, task_id=identifier, etag=etag, summary=f"{M}-neu")


def _move(clients: NcClients, identifier: str, etag: str) -> Awaitable[dict[str, Any]]:
    return tasks_tools.move_task(clients, task_id=identifier, etag=etag, list_name=LISTS["b"][2])


MODIFYING: dict[str, ToolCall] = {
    "tasks_complete": _complete,
    "tasks_update": _update,
    "tasks_move": _move,
}


@pytest.mark.parametrize("tool", list(MODIFYING))
async def test_p3310_a_change_between_read_and_write_is_refused(run: Run, tool: str) -> None:
    task = new_task(run, "a", f"veraltet-{tool}")
    etag = await etag_of(run, task.ident)
    changed_by_owner = touch(run, "a", task.name)
    between = row(run, "a", task.name)
    with Fall(run, "aendern-veraltet", tool) as case:
        async with measured(case) as clients:
            exc = await refusal(run, MODIFYING[tool](clients, task.ident, etag))
        after = row(run, "a", task.name)
        elsewhere = row(run, "b", task.name)
        case.note(told(exc))
        case.check("harness_aenderung", changed_by_owner == 204, f"PUT {changed_by_owner}")
        case.check("abgelehnt", "changed since it was read" in exc.message, told(exc))
        case.check("kein_schreiben", not writes(case.seen), f"writes {writes(case.seen)}")
        case.check(
            "sha_gleich_nach_harness", between.sha == after.sha, f"{between.short} {after.short}"
        )
        case.check("nicht_im_ziel", elsewhere.count == 0, f"target rows {elsewhere.count}")
        case.mark("sha", after.short)


@pytest.mark.parametrize("tool", list(MODIFYING))
async def test_p3310_a_read_only_shared_list_is_refused_by_every_tool(run: Run, tool: str) -> None:
    task = new_task(run, "ro", f"nurlesend-{tool}")
    etag = await etag_of(run, task.ident)
    before = row(run, "ro", task.name)
    with Fall(run, "aendern-nur-lesend", tool) as case:
        async with measured(case) as clients:
            exc = await refusal(run, MODIFYING[tool](clients, task.ident, etag))
        after = row(run, "ro", task.name)
        case.note(told(exc))
        case.check("abgelehnt_nur_lesend", "read only" in exc.message, told(exc))
        case.check("kein_schreiben", not writes(case.seen), f"writes {writes(case.seen)}")
        case.check("sha_beim_eigentuemer_gleich", before.sha == after.sha, after.short)
        case.mark("sha", after.short)


async def test_p3310_the_server_refuses_a_conditional_put_and_move_in_the_read_only_list(
    run: Run,
) -> None:
    """The guard of the tools is not the only wall: the same writes by the harness of alice."""
    task = new_task(run, "ro", "nurlesend-server")
    before = row(run, "ro", task.name)
    url = run.harness.task_url(run.ro_key, task.name)
    got = run.harness.request("GET", url)
    etag = got.headers.get("ETag", "")
    with Fall(run, "aendern-nur-lesend-server", "harness") as case:
        put = run.harness.request(
            "PUT",
            url,
            headers={"Content-Type": "text/calendar; charset=utf-8", "If-Match": etag},
            content=got.content.replace(b"SUMMARY:", b"SUMMARY:x"),
        )
        move = run.harness.request(
            "MOVE",
            url,
            headers={
                "Destination": f"{list_url(run, 'a')}{quote(task.name, safe='')}",
                "Overwrite": "F",
                "If-Match": etag,
            },
        )
        after = row(run, "ro", task.name)
        moved = row(run, "a", task.name)
        case.check("get_lesbar", got.status_code == 200 and bool(etag), f"GET {got.status_code}")
        case.check("put_abgelehnt", put.status_code in (403, 404), f"PUT {put.status_code}")
        case.check("move_abgelehnt", move.status_code in (403, 404), f"MOVE {move.status_code}")
        case.check("sha_beim_eigentuemer_gleich", before.sha == after.sha, after.short)
        case.check("nicht_im_ziel", moved.count == 0, f"target rows {moved.count}")
        case.mark("put_status", put.status_code)
        case.mark("move_status", move.status_code)


@pytest.mark.parametrize("tool", list(MODIFYING))
async def test_p3310_a_recurring_task_is_refused_by_every_tool(run: Run, tool: str) -> None:
    object_name = run.objects["wieder-app"]
    identifier = ids.encode_task(LISTS["b"][1], object_name)
    etag = await etag_of(run, identifier)
    before = row(run, "b", object_name)
    with Fall(run, "aendern-wiederkehrend", tool) as case:
        async with measured(case) as clients:
            call = MODIFYING[tool]
            if tool == "tasks_move":
                exc = await refusal(
                    run,
                    tasks_tools.move_task(
                        clients, task_id=identifier, etag=etag, list_name=LISTS["a"][2]
                    ),
                )
            else:
                exc = await refusal(run, call(clients, identifier, etag))
        after = row(run, "b", object_name)
        case.note(told(exc))
        case.check("abgelehnt_wiederkehrend", "recurring" in exc.message, told(exc))
        case.check("kein_schreiben", not writes(case.seen), f"writes {writes(case.seen)}")
        case.check("sha_gleich", before.sha == after.sha, after.short)
        case.mark("sha", after.short)


@pytest.mark.parametrize("tool", list(MODIFYING))
async def test_p3310_a_deck_card_is_unknown_to_every_tool(run: Run, tool: str) -> None:
    deck_uri = f"{tasks_client.DECK_PREFIX}deck--board-{run.board_id}"
    card = f"task:{deck_uri}:card-{run.card_id}.ics"
    with Fall(run, "aendern-deck", tool) as case:
        async with measured(case) as clients:
            exc = await refusal(run, MODIFYING[tool](clients, card, ANY_ETAG))
        text = f"{exc.message} {exc.hint}"
        case.note(told(exc))
        case.check("wie_unbekannt", exc.reason == REASON_UNKNOWN_ID, told(exc))
        case.check("keine_anfrage", not case.seen, f"requests {calls(case.seen)}")
        case.check("keine_deck_marke", run.deck_marker not in text, "marker in no answer")
        if tool == "tasks_move":
            task = new_task(run, "a", "deck-ziel")
            target = Case(run, "deck-ziel")
            async with measured(target) as clients:
                exc = await refusal(
                    run,
                    tasks_tools.move_task(
                        clients, task_id=task.ident, etag=ANY_ETAG, list_name=deck_uri
                    ),
                )
            target_seen = target.seen
            case.check("deck_ziel_abgelehnt", not target_seen, f"requests {calls(target_seen)}")
            case.check(
                "deck_ziel_keine_marke",
                run.deck_marker not in f"{exc.message} {exc.hint}",
                told(exc),
            )


# --- success criterion 4: relocating into a named list ---------------------------------


async def test_p3310_relocating_into_a_named_list_keeps_uid_and_text(run: Run) -> None:
    for target in ("rw", "b"):
        task = new_task(run, "a", f"verschieben-{target}")
        etag = await etag_of(run, task.ident)
        before = row(run, "a", task.name)
        with Fall(run, "verschieben-genannt", "tasks_move") as case:
            case.mark("ziel", "geteilt-schreibbar" if target == "rw" else "eigene")
            async with measured(case) as clients:
                answer = keep(
                    run,
                    await tasks_tools.move_task(
                        clients, task_id=task.ident, etag=etag, list_name=LISTS[target][2]
                    ),
                )
            source, landed = row(run, "a", task.name), row(run, target, task.name)
            new_id = ids.encode_task(list_key(run, target), task.name)
            case.check("quelle_leer", source.count == 0, f"source rows {source.count}")
            case.check("im_ziel", landed.count == 1, f"target rows {landed.count}")
            case.check("text_gleich", landed.sha == before.sha, f"{before.short} {landed.short}")
            case.check("gleiche_uid", f"UID:{task.uid}" in _unfold(landed.text), "UID")
            case.check("neue_id", answer.get("id") == new_id, answered(answer))
            case.check("ein_move", methods(case.seen, "MOVE") == [201], calls(case.seen))
            case.mark("sha", landed.short)


async def test_p3310_a_taken_name_in_the_target_is_refused_and_both_stay(run: Run) -> None:
    task = new_task(run, "a", "belegt")
    occupant = new_task(run, "b", "belegt-ziel", name=task.name)
    etag = await etag_of(run, task.ident)
    source_before, target_before = row(run, "a", task.name), row(run, "b", task.name)
    with Fall(run, "verschieben-belegt", "tasks_move") as case:
        async with measured(case) as clients:
            exc = await refusal(
                run,
                tasks_tools.move_task(
                    clients, task_id=task.ident, etag=etag, list_name=LISTS["b"][2]
                ),
            )
        source_after, target_after = row(run, "a", task.name), row(run, "b", task.name)
        case.note(f"{told(exc)} occupant uid differs={occupant.uid != task.uid}")
        case.check("abgelehnt", "already holds" in exc.message, told(exc))
        case.check("kein_move", not writes(case.seen), f"writes {writes(case.seen)}")
        case.check("quelle_gleich", source_before.sha == source_after.sha, source_after.short)
        case.check("ziel_gleich", target_before.sha == target_after.sha, target_after.short)
        case.mark("sha_quelle", source_after.short)
        case.mark("sha_ziel", target_after.short)


async def test_p3310_relocating_a_parent_takes_its_subtasks_along(run: Run) -> None:
    parent = new_task(run, "a", "zug-eltern")
    first = new_task(run, "a", "zug-k1", (f"RELATED-TO:{parent.uid}",))
    second = new_task(run, "a", "zug-k2", (f"RELATED-TO:{parent.uid}",))
    order = [first, second, parent]
    before = {task.name: row(run, "a", task.name).sha for task in order}
    etag = await etag_of(run, parent.ident)
    with Fall(run, "verschieben-kinder", "tasks_move") as case:
        async with measured(case) as clients:
            answer = keep(
                run,
                await tasks_tools.move_task(
                    clients, task_id=parent.ident, etag=etag, list_name=LISTS["b"][2]
                ),
            )
        sources = [row(run, "a", task.name).count for task in order]
        landed = [row(run, "b", task.name) for task in order]
        move_paths = [below for method, below, _ in case.seen if method == "MOVE"]
        in_order = len(move_paths) == len(order) and all(
            path.endswith(f"/{task.name}") for path, task in zip(move_paths, order, strict=False)
        )
        case.check("quelle_leer", sources == [0, 0, 0], f"source rows {sources}")
        case.check(
            "alle_im_ziel_unveraendert",
            [item.sha for item in landed] == [before[task.name] for task in order],
            "texts as before",
        )
        case.check("moves_nachordnung", in_order, f"MOVE order {len(move_paths)}")
        case.check(
            "moved",
            answer.get("moved")
            == [ids.encode_task(LISTS["b"][1], task.name) for task in (first, second)],
            answered(answer),
        )
        case.mark("moves", len(move_paths))


# --- success criterion 5: a chain that meets 412 at its second descendant ---------------


async def test_p3310_a_chain_stops_at_the_second_descendant_and_keeps_the_parent(
    run: Run,
) -> None:
    parent = new_task(run, "a", "kette-eltern")
    children = [
        new_task(run, "a", f"kette-k{number}", (f"RELATED-TO:{parent.uid}",))
        for number in (1, 2, 3)
    ]
    etag = await etag_of(run, parent.ident)
    before = {task.name: row(run, "a", task.name) for task in (parent, *children)}
    puts = 0
    touched: dict[str, str] = {}

    async def change_the_second(request: httpx.Request) -> None:
        nonlocal puts
        if request.method != "PUT":
            return
        puts += 1
        if puts == 2:
            name = unquote(request.url.path.rsplit("/", 1)[-1])
            touched["status"] = str(touch(run, "a", name))
            touched["name"] = name
            touched["sha"] = row(run, "a", name).sha

    with Fall(run, "kette-teilfehler", "tasks_complete") as case:
        async with measured(case, on_request=change_the_second) as clients:
            answer = keep(
                run,
                await tasks_tools.complete_task(
                    clients, task_id=parent.ident, etag=etag, completed=True
                ),
            )
        after = {task.name: row(run, "a", task.name) for task in (parent, *children)}
        first, second, third = children
        statuses = methods(case.seen, "PUT")
        case.note(answered(answer))
        case.check(
            "harness_aenderte_den_zweiten",
            touched.get("name") == second.name and touched.get("status") == "204",
            f"harness PUT {touched.get('status')}",
        )
        case.check("gestoppt", answer.get("failed") == second.ident, answered(answer))
        case.check("grund_412", answer.get("reason") == "conflict", f"{answer.get('reason')}")
        case.check("changed_genau_erster", answer.get("changed") == [first.ident], "changed")
        case.check(
            "puts", len(statuses) == 2 and statuses[0] < 300 and statuses[1] == 412, f"{statuses}"
        )
        case.check(
            "eltern_sha_gleich",
            before[parent.name].sha == after[parent.name].sha,
            after[parent.name].short,
        )
        case.check(
            "zweiter_sha_wie_harness", after[second.name].sha == touched.get("sha"), "second"
        )
        case.check("dritter_sha_gleich", before[third.name].sha == after[third.name].sha, "third")
        case.check(
            "erster_erledigt",
            "STATUS:COMPLETED" in todo_lines(after[first.name].text).get("STATUS", []),
            "first",
        )
        case.mark("sha_eltern", after[parent.name].short)


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

"""The measurements of plan 32-02, taken before any product code of the tasks bundle exists.

Phase 32 builds ``tasks_search``, ``tasks_read`` and ``tasks_create``. Several of their
constants and rules rest on assumptions the research only read out of the server source.
This program asks a running Nextcloud instead:

* the sub task query (``REPORT`` with a ``text-match`` on ``RELATED-TO``) at 2000 tasks in
  one list, for a parent without, with one and with 25 children, in the measured form
  without ``collation`` and in the form ``collation="i;octet"`` the research recommends,
  plus the parent lookup by ``UID`` (D-32-03, deviation H of 32-PATTERNS.md);
* the modes ``offen`` and ``alle`` of the search under impersonation (TASK-02);
* the name of a shared list against ``{http://nextcloud.com/ns}owner-displayname`` (A2,
  D-32-14), printed only as yes/no marks;
* the calendar home of an account without any login, and the discovery of an account whose
  only calendar carries VEVENT (A1, TASK-03);
* whether navigation and the list of search providers mirror the state of the Tasks app (A3,
  D-32-10);
* the link form for ``fetch`` and the link of the search provider ``tasks`` (A5, D-32-15).

Subcommands::

    uv run --no-sync python scripts/tasks_measure.py throwaway --db sqlite --out <file>
    uv run --no-sync python scripts/tasks_measure.py up --instance nc35 --out <file>
    uv run --no-sync python scripts/tasks_measure.py live --instance nc35 \
        --env-file .env.nc35 --steps baseline,children,search,names,link,home,appstate \
        --out <file>
    uv run --no-sync python scripts/tasks_measure.py teardown --instance nc35 \
        --env-file .env.nc35 --out <file>
    uv run --no-sync python scripts/tasks_measure.py stop --instance nc35 --out <file>
    uv run --no-sync python scripts/tasks_measure.py privileges --fixture <xml>
    uv run --no-sync python scripts/tasks_measure.py scan --env-file <f> ... <file> ...

``throwaway`` runs one Nextcloud 35.0.2 from ``compose.spike-tags.yml`` (SQLite) or
``compose.spike-tags-pg.yml`` (PostgreSQL) and takes it down with ``down -v``. ``live``
measures a standing instance under AppAPI impersonation (``nc35`` or the Nextcloud 32
topology ``nc32``) and always takes back what it created, compared against a baseline read
from the database. ``up`` and ``stop`` only use ``docker start`` and ``docker stop``.

The helpers of the spike (RAM gate, throwaway instance, DAV request, secret scan) are loaded
from ``scripts/tasks_spike.py`` by path and not copied. Every protocol line goes through the
secret scan of the spike before it is written.
"""

import argparse
import asyncio
import base64
import importlib.util
import math
import re
import secrets
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
from lxml import etree

from mcp_connector.nextcloud.clients import xml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, Credentials

REPO_ROOT = Path(__file__).resolve().parents[1]
SPIKE_FILE = REPO_ROOT / "scripts" / "tasks_spike.py"


def _load_spike() -> ModuleType:
    """The measuring script of phase 30, loaded from its file instead of being repeated."""
    spec = importlib.util.spec_from_file_location("tasks_spike", SPIKE_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{SPIKE_FILE} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


spike = _load_spike()

# --- what this round creates ---------------------------------------------------------------------

#: Every list, task and account of this plan carries this prefix; the teardown goes by it.
PREFIX = "p3202"
LIST_SERIES = f"{PREFIX}-serie"
LIST_OWN = f"{PREFIX}-eigen"
LIST_RW = f"{PREFIX}-rw"
LIST_RO = f"{PREFIX}-ro"
LIST_SPECIAL = f"{PREFIX}-sonder-äö"
SPECIAL_DISPLAY = f"{PREFIX} Sonder & <Zeichen> äö (x)"
FRESH_USER = f"{PREFIX}frisch"
NEVER_USER = f"{PREFIX}nie"
LINK_TERM = f"{PREFIX}link"
TASKS_APP = "tasks"
NC_NS = "http://nextcloud.com/ns"
OWNER_DISPLAYNAME = f"{{{NC_NS}}}owner-displayname"
NO_TRASHBIN = {"X-NC-CalDAV-No-Trashbin": "1"}
THROWAWAY_TAG = "35.0.2-apache"

TOTAL_TASKS = 2000
DONE_TASKS = 1900
#: Number of children -> number of the parent task in the series.
PARENTS = {0: 1999, 1: 1998, 25: 1997}
#: Number of a child task -> number of its parent: one child of 1998, 25 of 1997 that span
#: the border between done and open tasks.
CHILDREN = {1996: 1998, **dict.fromkeys(range(1890, 1915), 1997)}
COLLATIONS: tuple[str | None, ...] = (None, "i;octet")

NAME_PROPS = (
    f"{{{xml.DAV}}}displayname",
    f"{{{xml.DAV}}}resourcetype",
    f"{{{xml.CAL}}}supported-calendar-component-set",
    f"{{{xml.DAV}}}current-user-privilege-set",
    f"{{{xml.OC}}}read-only",
    OWNER_DISPLAYNAME,
)


@dataclass(frozen=True, slots=True)
class Target:
    """A standing instance this program may measure under impersonation."""

    name: str
    base_url: str
    container: str
    #: Started and stopped with ``docker start``/``docker stop``, never with compose.
    containers: tuple[str, ...]
    alice: str = "alice"
    bob: str = "bob"


TARGETS = {
    "nc35": Target(
        "nc35", "http://127.0.0.1:8082", "nc35-nc", ("nc35-nc", "nc35-harp", "nc35-caddy")
    ),
    "nc32": Target(
        "nc32",
        "http://127.0.0.1:8081",
        "nc-mcp-exapp-nc",
        ("nc-mcp-exapp-nc", "nc-mcp-exapp-caddy"),
    ),
}

#: The baseline of 32-RULES.md section 7 for one principal, read from the database.
PHP_BASELINE = (
    spike._PHP_BOOT
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


# --- pure helpers (tests/unit/test_tasks_measure.py) ---------------------------------------------


def _todo_text_match(prop: str, value: str, collation: str | None) -> bytes:
    """A ``calendar-query`` for the VTODOs whose ``prop`` contains ``value``, built with lxml."""
    if not value:
        raise ValueError(f"a text-match on {prop} needs a value")
    root = etree.Element(f"{{{xml.CAL}}}calendar-query", nsmap={"d": xml.DAV, "c": xml.CAL})
    prop_element = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop_element, f"{{{xml.DAV}}}getetag")
    etree.SubElement(prop_element, f"{{{xml.CAL}}}calendar-data")
    scope = etree.SubElement(root, f"{{{xml.CAL}}}filter")
    outer = etree.SubElement(scope, f"{{{xml.CAL}}}comp-filter", name="VCALENDAR")
    todo = etree.SubElement(outer, f"{{{xml.CAL}}}comp-filter", name="VTODO")
    matched = etree.SubElement(todo, f"{{{xml.CAL}}}prop-filter", name=prop)
    attrib = {"match-type": "contains"}
    if collation is not None:
        attrib["collation"] = collation
    match = etree.SubElement(matched, f"{{{xml.CAL}}}text-match", attrib=attrib)
    match.text = value
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def children_filter(parent_uid: str, collation: str | None) -> bytes:
    """The sub task query: ``RELATED-TO`` contains ``parent_uid``.

    ``collation=None`` is the form the spike measured (``match-type="contains"`` and no
    ``collation`` attribute, sabre then uses ``i;ascii-casemap``); ``"i;octet"`` is the form
    the research recommends.
    """
    return _todo_text_match("RELATED-TO", parent_uid, collation)


def uid_filter(uid: str, collation: str | None) -> bytes:
    """The parent lookup of ``tasks_read``: ``UID`` contains ``uid``, same form as above."""
    return _todo_text_match("UID", uid, collation)


def owner_suffix_strip(displayname: str, owner_displayname: str) -> str | None:
    """The list name without exactly ``" (" + owner_displayname + ")"`` at its end.

    ``None`` when the name does not end with that suffix, when the owner name is blank or
    when nothing but the suffix would be left: in each case the rule of D-32-14 does not
    carry, and nothing is guessed.
    """
    if not owner_displayname.strip():
        return None
    suffix = f" ({owner_displayname})"
    if not displayname.endswith(suffix):
        return None
    name = displayname[: -len(suffix)]
    return name if name.strip() else None


def derive_budget(max_seconds: float) -> int:
    """The derivation rule of the spike: twice the largest maximum, rounded up, at least 1 s."""
    return max(1, math.ceil(2 * max_seconds - 1e-9))


def navigation_lists(payload: Any, app: str) -> bool | None:
    """Whether a navigation answer carries ``app``; ``None`` when the answer says nothing.

    An entry counts by its ``app`` or its ``id``, as ``capabilities._navigation_lists_mail``
    reads it. An empty or deformed answer is ``None`` and never "missing": every Nextcloud
    lists at least one app.
    """
    if not isinstance(payload, list) or not payload:
        return None
    entries = [entry for entry in payload if isinstance(entry, dict)]
    if not entries:
        return None
    return any(app in (entry.get("app"), entry.get("id")) for entry in entries)


# --- small helpers -------------------------------------------------------------------------------


def note(line: str) -> None:
    spike.note(line)


def yes_no(value: bool) -> str:
    return "ja" if value else "nein"


def tri(value: bool | None) -> str:
    return "unklar" if value is None else yes_no(value)


def home_url(base: str, user: str) -> str:
    return f"{base}/remote.php/dav/calendars/{quote(user, safe='')}/"


def list_url(base: str, user: str, uri: str) -> str:
    return f"{home_url(base, user)}{quote(uri, safe='')}/"


def object_url(base: str, user: str, uri: str, name: str) -> str:
    return f"{list_url(base, user, uri)}{quote(name, safe='')}"


def series_uid(run: str, number: int) -> str:
    return f"{PREFIX}-{run}-{number:04d}"


def series_todo(run: str, number: int) -> tuple[str, str]:
    """Object name and text of task ``number`` of the series of 2000.

    The first ``DONE_TASKS`` are checked off the way the Tasks app writes it; the sub tasks
    of ``CHILDREN`` carry ``RELATED-TO`` with the UID of their parent.
    """
    uid = series_uid(run, number)
    extra = [
        (
            "DESCRIPTION:Eine Aufgabe der Messreihe mit einer Beschreibung von "
            "ueblicher Laenge\\, damit die Antwort nicht kuenstlich klein ausfaellt."
        ),
        f"DUE:202612{number % 28 + 1:02d}T100000Z",
        f"CATEGORIES:{PREFIX}",
    ]
    if number < DONE_TASKS:
        extra += ["STATUS:COMPLETED", "PERCENT-COMPLETE:100", "COMPLETED:20261101T100000Z"]
    if number in CHILDREN:
        extra.append(f"RELATED-TO:{series_uid(run, CHILDREN[number])}")
    return f"{uid}.ics", spike.simple_todo(uid, f"{PREFIX} serie {number:04d}", extra)


def expected_children(count: int) -> int:
    return sum(1 for parent in CHILDREN.values() if parent == PARENTS[count])


def hrefs_of(result: Any) -> frozenset[str]:
    if result.status != 207:
        return frozenset()
    return frozenset(href for href, _ in xml.parse_multistatus(result.body))


@dataclass
class Measurement:
    """One series: every measured answer, and whether the client limit was hit."""

    results: list[Any] = field(default_factory=list)
    timed_out: bool = False

    def line(self) -> str:
        if len(self.results) < 2:
            return f"status=ungemessen zeitlimit={yes_no(self.timed_out)} (n={len(self.results)})"
        stats = spike.summarize([result.seconds for result in self.results])
        statuses = "/".join(str(code) for code in sorted({r.status for r in self.results}))
        sizes = sorted({len(r.body) for r in self.results})
        hits = sorted({spike.response_count(r) for r in self.results})
        span = f"{sizes[0]}" if len(sizes) == 1 else f"{sizes[0]}..{sizes[-1]}"
        hit_span = f"{hits[0]}" if len(hits) == 1 else f"{hits[0]}..{hits[-1]}"
        return (
            f"status={statuses} median_ms={stats['median'] * 1000:.0f} "
            f"max_ms={stats['max'] * 1000:.0f} min_ms={stats['min'] * 1000:.0f} "
            f"p95_zweitgroesster_ms={stats['p95_second_largest'] * 1000:.0f} bytes={span} "
            f"treffer={hit_span} (n={len(self.results)})"
        )

    def max_seconds(self) -> float | None:
        if self.timed_out or len(self.results) < 2:
            return None
        return max(result.seconds for result in self.results)


async def measure(
    creds: Credentials,
    url: str,
    body: bytes,
    containers: Sequence[str],
    *,
    warm: int,
    runs: int,
) -> Measurement:
    """``warm`` discarded and ``runs`` measured REPORTs of Depth 1, after the instance rests."""
    await spike.wait_until_idle(containers)
    found = Measurement()
    async with spike.new_client() as client:
        try:
            for _ in range(warm):
                await spike.dav_request(client, creds, "REPORT", url, depth="1", body=body)
            for _ in range(runs):
                found.results.append(
                    await spike.dav_request(client, creds, "REPORT", url, depth="1", body=body)
                )
        except httpx.TimeoutException:
            found.timed_out = True
    return found


def appapi_creds(env: Mapping[str, str], base: str, user: str) -> Credentials:
    """Impersonation of ``user``; ``APP_SECRET`` is the only secret in play."""
    secret = env.get("APP_SECRET", "")
    if not secret:
        raise spike.RunFailed("the environment file names no APP_SECRET")
    spike.remember_secret(
        f"APPAPI_TOKEN_{user}", base64.b64encode(f"{user}:{secret}".encode()).decode()
    )
    return Credentials(
        base_url=base,
        user=user,
        secret=secret,
        mode=MODE_APPAPI,
        app_id=env.get("APP_ID", ""),
        app_version=env.get("APP_VERSION", ""),
        aa_version=env.get("AA_VERSION", ""),
    )


# --- building ------------------------------------------------------------------------------------


async def make_list(
    client: httpx.AsyncClient,
    creds: Credentials,
    uri: str,
    display: str | None = None,
    components: Sequence[str] = ("VTODO",),
) -> None:
    made = await spike.dav_request(
        client,
        creds,
        "MKCALENDAR",
        list_url(creds.base_url, creds.user, uri),
        body=spike.mkcalendar_body(display or uri, components),
    )
    note(f"SETUP MKCALENDAR liste={uri} status={made.status}")
    if made.status != 201:
        raise spike.RunFailed(f"MKCALENDAR {uri} answered {made.status}")


async def put_task(
    client: httpx.AsyncClient, creds: Credentials, uri: str, name: str, text: str
) -> int:
    url = object_url(creds.base_url, creds.user, uri, name)
    result = await spike.dav_request(
        client,
        creds,
        "PUT",
        url,
        body=text.encode(),
        content_type=spike.ICS_TYPE,
        extra_headers={"If-None-Match": "*"},
    )
    return result.status


async def build_series(
    creds: Credentials, container: str, run: str, *, parallel: int, label: str
) -> None:
    """The list of 2000 tasks, 1900 of them done, with parents of 0, 1 and 25 children."""
    async with spike.new_client() as client:
        await make_list(client, creds, LIST_SERIES)
        gate = asyncio.Semaphore(parallel)
        failed: list[str] = []
        repeated = 0

        async def put(number: int) -> None:
            nonlocal repeated
            name, text = series_todo(run, number)
            async with gate:
                status = 0
                for attempt in range(6):
                    try:
                        status = await put_task(client, creds, LIST_SERIES, name, text)
                    except httpx.HTTPError:
                        status = 0
                    if status in (201, 204) or (status == 412 and attempt):
                        return
                    if 0 < status < 500:
                        break
                    repeated += 1
                    await asyncio.sleep(0.5 * (attempt + 1))
                failed.append(f"{number}:{status}")

        started = time.perf_counter()
        await asyncio.gather(*(put(number) for number in range(TOTAL_TASKS)))
        seconds = time.perf_counter() - started
    if failed:
        raise spike.RunFailed(f"{len(failed)} PUT of the series failed, first: {failed[:3]}")
    rows = spike.php(container, spike.PHP_COUNT_LIST_OBJECTS, creds.user, LIST_SERIES)
    note(
        f"AUFBAU {label} aufgaben={TOTAL_TASKS} erledigt={DONE_TASKS} "
        f"kinder_von_eltern={','.join(f'{n}' for n in PARENTS)} dauer_s={seconds:.0f} "
        f"gleichzeitig={parallel} wiederholte_put={repeated} "
        f"GEGENPROBE datenbank_zeilen={rows} gleich={yes_no(rows == str(TOTAL_TASKS))}"
    )
    if rows != str(TOTAL_TASKS):
        raise spike.RunFailed(f"the database holds {rows} objects of {LIST_SERIES}")


# --- the measured series -------------------------------------------------------------------------


async def children_series(
    creds: Credentials,
    containers: Sequence[str],
    run: str,
    *,
    db: str,
    impersonation: bool,
    warm: int,
    runs: int,
) -> dict[str, float]:
    """``KOSTEN kinder`` for 0, 1 and 25 children and ``KOSTEN eltern-uid``, both forms."""
    url = list_url(creds.base_url, creds.user, LIST_SERIES)
    marker = " impersonation=ja" if impersonation else ""
    tail = "" if impersonation else " impersonation=nein"
    maxima: dict[str, float] = {}
    sets: dict[str, dict[str | None, frozenset[str]]] = {}
    expected_ok = True
    for count, parent in PARENTS.items():
        sets[f"kinder{count}"] = {}
        for collation in COLLATIONS:
            body = children_filter(series_uid(run, parent), collation)
            found = await measure(creds, url, body, containers, warm=warm, runs=runs)
            form = collation or "ohne"
            note(
                f"KOSTEN kinder{marker} kinder={count} collation={form} db={db} "
                f"{found.line()}{tail}"
            )
            if found.results:
                hits = hrefs_of(found.results[-1])
                sets[f"kinder{count}"][collation] = hits
                expected_ok = expected_ok and len(hits) == expected_children(count)
            worst = found.max_seconds()
            if worst is not None:
                maxima[f"kinder-{count}-{form}"] = worst
    sets["eltern"] = {}
    for collation in COLLATIONS:
        body = uid_filter(series_uid(run, PARENTS[25]), collation)
        found = await measure(creds, url, body, containers, warm=warm, runs=runs)
        form = collation or "ohne"
        note(f"KOSTEN eltern-uid{marker} collation={form} db={db} {found.line()}{tail}")
        if found.results:
            hits = hrefs_of(found.results[-1])
            sets["eltern"][collation] = hits
            expected_ok = expected_ok and len(hits) == 1
        worst = found.max_seconds()
        if worst is not None:
            maxima[f"eltern-{form}"] = worst
    same = all(len(by_form) == 2 and len(set(by_form.values())) == 1 for by_form in sets.values())
    detail = " ".join(
        f"{key}={'/'.join(str(len(by_form.get(c, frozenset()))) for c in COLLATIONS)}"
        for key, by_form in sets.items()
    )
    note(
        f"GEGENPROBE collation db={db} treffer_gleich={yes_no(same)} "
        f"erwartete_anzahl={yes_no(expected_ok)} {detail} (Mengen der Objekt-Hrefs, "
        "ohne/i;octet; erwartet kinder0=0 kinder1=1 kinder25=25 eltern=1)"
    )
    return maxima


async def search_series(
    creds: Credentials,
    containers: Sequence[str],
    *,
    db: str,
    impersonation: bool,
    warm: int,
    runs: int,
) -> dict[str, float]:
    """``KOSTEN suche`` for the modes ``offen`` (prefilter) and ``alle`` (no prefilter)."""
    url = list_url(creds.base_url, creds.user, LIST_SERIES)
    maxima: dict[str, float] = {}
    for mode in ("offen", "alle"):
        found = await measure(
            creds, url, spike.build_todo_filter(mode), containers, warm=warm, runs=runs
        )
        note(
            f"KOSTEN suche modus={mode} impersonation={yes_no(impersonation)} db={db} "
            f"{found.line()}"
        )
        worst = found.max_seconds()
        if worst is not None:
            maxima[mode] = worst
    return maxima


# --- throwaway -----------------------------------------------------------------------------------


async def throwaway(db: str) -> None:
    """Task 3: one Nextcloud 35.0.2 with ``db``, the Tasks app, the series and both forms."""
    spike.section(f"wegwerf db={db} nc-tag={THROWAWAY_TAG}, start {spike.now_stamp()}")
    async with spike.throwaway_instance(THROWAWAY_TAG, db, (spike.ALICE,)) as inst:
        container = inst.container
        installed = spike._one_line(spike.occ(container, "app:install", TASKS_APP, check=False))
        note(f"occ app:install {TASKS_APP} -> {installed[:200]}")
        spike.restart_instance(container)
        version = spike.app_version(container, TASKS_APP)
        note(f"TASKSAPP wegwerf-{db} version={version or 'nicht-aktiv'}")
        creds = inst.session.basic(spike.ALICE)
        run = datetime.now(UTC).strftime("%H%M%S")
        await build_series(
            creds,
            container,
            run,
            parallel=4 if inst.setup.db_container else 1,
            label=f"wegwerf-{db}",
        )
        containers = inst.setup.containers()
        maxima = await search_series(creds, containers, db=db, impersonation=False, warm=3, runs=15)
        maxima |= await children_series(
            creds, containers, run, db=db, impersonation=False, warm=3, runs=15
        )
        worst = max(maxima.values(), default=0.0)
        note(f"VORSCHLAG wegwerf-{db} groesster_max_s={worst:.3f} budget_s={derive_budget(worst)}")


# --- live: baseline, setup, teardown -------------------------------------------------------------


def accounts(target: Target) -> tuple[str, ...]:
    return (target.alice, target.bob, FRESH_USER, NEVER_USER)


def baseline(target: Target, phase: str) -> dict[str, str]:
    """One ``BASELINE`` line per account, read in the container through PHP."""
    found: dict[str, str] = {}
    for user in accounts(target):
        raw = spike.php(target.container, PHP_BASELINE, user).split()
        if len(raw) != 5 or not all(part.isdigit() for part in raw):
            raise spike.RunFailed(f"the baseline of {user} could not be read: {raw}")
        value = (
            f"calendars={raw[0]} objekte={raw[1]} geloescht={raw[2]} shares={raw[4]} abos={raw[3]}"
        )
        found[user] = value
        note(f"BASELINE {target.name} konto={user} {value} phase={phase}")
    return found


def tasks_app_state(container: str) -> str:
    data = spike._json_or_text(spike.occ(container, "app:list", "--output=json", check=False))
    if not isinstance(data, dict):
        raise spike.RunFailed("occ app:list --output=json returned no JSON object")
    enabled = data.get("enabled") or {}
    disabled = data.get("disabled") or {}
    if TASKS_APP in enabled:
        return str(enabled[TASKS_APP])
    if TASKS_APP in disabled:
        return f"aus-{disabled[TASKS_APP]}"
    return "keine"


def restart(target: Target) -> None:
    answer = spike.docker("restart", target.container).strip()
    note(f"docker restart {target.container} -> {answer}")
    spike.wait_for_http(target.base_url)
    spike.wait_for_install(target.container)


def ensure_tasks_app(target: Target) -> str:
    state = tasks_app_state(target.container)
    if state.startswith("aus-"):
        out = spike.occ(target.container, "app:enable", TASKS_APP, check=False)
        note(f"occ app:enable {TASKS_APP} -> {spike._one_line(out)[:160]}")
    elif state == "keine":
        out = spike.occ(target.container, "app:install", TASKS_APP, check=False)
        note(f"occ app:install {TASKS_APP} -> {spike._one_line(out)[:160]}")
    restart(target)
    version = tasks_app_state(target.container)
    note(f"TASKSAPP {target.name} messung={version}")
    if version in ("keine",) or version.startswith("aus-"):
        raise spike.RunFailed(f"the Tasks app is not enabled: {version}")
    return version


def restore_tasks_app(target: Target, before: str) -> None:
    """The Tasks app back into the state ``before``, then a restart."""
    now = tasks_app_state(target.container)
    if now != before:
        if before == "keine":
            # app:remove disables the app itself. Measured on 32.0.15: it refuses an app that
            # is already disabled ("tasks is not enabled"), so a disabled one is enabled first.
            if tasks_app_state(target.container).startswith("aus-"):
                out = spike.occ(target.container, "app:enable", TASKS_APP, check=False)
                note(f"occ app:enable {TASKS_APP} -> {spike._one_line(out)[:160]}")
            out = spike.occ(target.container, "app:remove", TASKS_APP, check=False)
            note(f"occ app:remove {TASKS_APP} -> {spike._one_line(out)[:160]}")
            for key in spike.APP_STATE_KEYS:
                spike.occ(target.container, "config:app:delete", TASKS_APP, key, check=False)
            left = spike.occ(target.container, "config:list", TASKS_APP, check=False)
            note(f"occ config:app:delete {TASKS_APP} -> config:list: {spike._one_line(left)}")
        elif before.startswith("aus-"):
            out = spike.occ(target.container, "app:disable", TASKS_APP, check=False)
            note(f"occ app:disable {TASKS_APP} -> {spike._one_line(out)[:160]}")
        else:
            out = spike.occ(target.container, "app:enable", TASKS_APP, check=False)
            note(f"occ app:enable {TASKS_APP} -> {spike._one_line(out)[:160]}")
    restart(target)
    after = tasks_app_state(target.container)
    note(
        f"RUECKBAU {target.name} tasksapp={'wie-vorher' if after == before else 'abweichend'} "
        f"vorher={before} nachher={after}"
    )


async def prefixed_lists(client: httpx.AsyncClient, creds: Credentials) -> list[Any]:
    result = await spike.dav_request(
        client,
        creds,
        "PROPFIND",
        home_url(creds.base_url, creds.user),
        depth="1",
        body=spike.propfind_body(NAME_PROPS),
    )
    if result.status != 207:
        return []
    return [entry for entry in spike.parse_home(result.body) if entry.uri.startswith(PREFIX)]


async def purge_trash(client: httpx.AsyncClient, creds: Credentials) -> int:
    """Delete every object of this plan from the calendar trash bin of ``creds.user``.

    The collection ``trashbin/objects/`` answers PROPFIND with 501 and names its objects
    ``<id>.ics`` (measured in plan 30-02), so it is read with a calendar-query and matched by
    UID. Deleted calendars stay in the home with the resourcetype ``deleted-calendar`` and
    fall with the list loop of ``teardown``.
    """
    url = f"{home_url(creds.base_url, creds.user)}trashbin/objects/"
    listed = await spike.dav_request(
        client, creds, "REPORT", url, depth="1", body=spike.report_body("calendar-query")
    )
    if listed.status != 207:
        note(f"PAPIERKORB konto={creds.user} objects status={listed.status}")
        return 0
    removed = 0
    for href, props in xml.parse_multistatus(listed.body):
        data = props.get(f"{{{xml.CAL}}}calendar-data", "")
        if f"UID:{PREFIX}" not in spike.unfold(data):
            continue
        path = urlsplit(href).path
        gone = await spike.dav_request(
            client, creds, "DELETE", f"{creds.base_url}{path}", extra_headers=NO_TRASHBIN
        )
        removed += 1
        note(f"PAPIERKORB konto={creds.user} objekt_geloescht status={gone.status}")
    return removed


async def teardown(target: Target, env: Mapping[str, str]) -> None:
    """Shares back, lists deleted without trash bin, trash emptied, accounts deleted."""
    spike.section(f"rueckbau {target.name}")
    async with spike.new_client() as client:
        bob = appapi_creds(env, target.base_url, target.bob)
        for uri in (LIST_RW, LIST_RO):
            unshare = etree.Element(
                f"{{{spike.OC_SHARE_NS}}}share", nsmap={"d": xml.DAV, "o": spike.OC_SHARE_NS}
            )
            entry = etree.SubElement(unshare, f"{{{spike.OC_SHARE_NS}}}remove")
            etree.SubElement(
                entry, f"{{{xml.DAV}}}href"
            ).text = f"principal:principals/users/{target.alice}"
            result = await spike.dav_request(
                client,
                bob,
                "POST",
                list_url(target.base_url, target.bob, uri),
                body=etree.tostring(unshare, xml_declaration=True, encoding="utf-8"),
            )
            note(f"RUECKBAU freigabe_entfernt liste={uri} status={result.status}")
        for user in (target.alice, target.bob):
            creds = appapi_creds(env, target.base_url, user)
            for entry in await prefixed_lists(client, creds):
                if "_shared_by_" in entry.uri:
                    continue
                gone = await spike.dav_request(
                    client,
                    creds,
                    "DELETE",
                    list_url(target.base_url, user, entry.uri),
                    extra_headers=NO_TRASHBIN,
                )
                note(f"RUECKBAU liste_geloescht konto={user} status={gone.status} no_trashbin=1")
            removed = await purge_trash(client, creds)
            note(f"RUECKBAU papierkorb konto={user} entfernte_eintraege={removed}")
            left = await prefixed_lists(client, creds)
            note(f"RUECKBAU reste konto={user} listen_mit_praefix={len(left)}")
    for user in (FRESH_USER, NEVER_USER):
        out = spike.occ(target.container, "user:delete", user, check=False)
        note(f"occ user:delete {user} -> {spike._one_line(out)[:120]}")


# --- live: names ---------------------------------------------------------------------------------


def owner_names(body: bytes) -> dict[str, str | None]:
    """``uri -> owner-displayname`` of a 2xx propstat, ``None`` where it was not found."""
    root = xml.parse_root(body)
    found: dict[str, str | None] = {}
    for response in root.findall(f"{{{xml.DAV}}}response"):
        path = urlsplit((response.findtext(f"{{{xml.DAV}}}href") or "").strip()).path
        uri = unquote(path.rstrip("/").rsplit("/", 1)[-1])
        value: str | None = None
        for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
            if " 2" not in (propstat.findtext(f"{{{xml.DAV}}}status") or ""):
                continue
            element = propstat.find(f"{{{xml.DAV}}}prop/{{{NC_NS}}}owner-displayname")
            if element is not None:
                value = element.text or ""
        found[uri] = value
    return found


def collection_kind(uri: str, own_lists: Sequence[str]) -> str | None:
    if uri.startswith("app-generated--"):
        return "deck"
    if uri.startswith(f"{LIST_RW}_shared_by_"):
        return "rw"
    if uri.startswith(f"{LIST_RO}_shared_by_"):
        return "ro"
    if uri in own_lists:
        return "eigen"
    return None


async def names(
    target: Target, env: Mapping[str, str], own_list: str, *, setup: bool = True
) -> None:
    """Shared lists of bob in the discovery of alice, as yes/no marks only."""
    async with spike.new_client() as client:
        alice = appapi_creds(env, target.base_url, target.alice)
        bob = appapi_creds(env, target.base_url, target.bob)
        if setup:
            for uri, writable in ((LIST_RW, True), (LIST_RO, False)):
                await make_list(client, bob, uri)
                shared = await spike.dav_request(
                    client,
                    bob,
                    "POST",
                    list_url(target.base_url, target.bob, uri),
                    body=spike.share_body(target.alice, writable=writable),
                )
                note(
                    f"SETUP FREIGABE liste={uri} schreibrecht={yes_no(writable)} "
                    f"status={shared.status}"
                )
        result = await spike.dav_request(
            client,
            alice,
            "PROPFIND",
            home_url(target.base_url, target.alice),
            depth="1",
            body=spike.propfind_body(NAME_PROPS),
        )
        note(f"PROPFIND Depth 1 kalender-home status={result.status} bytes={len(result.body)}")
        if result.status != 207:
            raise spike.RunFailed(f"the discovery answered {result.status}")
        owners = owner_names(result.body)
        own_owner = owners.get(own_list)
        originals = {"rw": LIST_RW, "ro": LIST_RO, "eigen": own_list}
        deck_seen = False
        for entry in spike.parse_home(result.body):
            kind = collection_kind(entry.uri, (own_list,))
            if kind is None or (kind == "deck" and deck_seen):
                continue
            deck_seen = deck_seen or kind == "deck"
            owner = owners.get(entry.uri)
            readable = owner is not None and bool(owner.strip())
            stripped = owner_suffix_strip(entry.display, owner) if owner else None
            original = originals.get(kind)
            same = "n/a" if original is None else yes_no((stripped or entry.display) == original)
            read_only = "fehlt" if entry.read_only is None else (entry.read_only or "leer")
            note(
                f"NAMEN {target.name} sammlung={kind} owner_displayname_lesbar={yes_no(readable)} "
                f"zusatz_passt={yes_no(stripped is not None)} "
                f"name_ohne_zusatz_gleich_original={same} "
                f"owner_gleich_eigenem_owner={yes_no(owner is not None and owner == own_owner)} "
                f"read_only={read_only} privilegien={','.join(sorted(set(entry.privileges)))} "
                f"schreibrecht_spike_menge={yes_no(spike.writable(entry))} "
                f"shared_by_in_uri={yes_no('_shared_by_' in entry.uri)} "
                f"komponenten={','.join(entry.components) or 'keine'}"
            )
        if not deck_seen:
            note(f"NAMEN {target.name} sammlung=deck vorhanden=nein (kein Deck-Kalender bei alice)")


# --- live: links ---------------------------------------------------------------------------------


_TASKS_SCRIPT = re.compile(rb"tasks/js/tasks-main")


async def provider_links(
    client: httpx.AsyncClient, creds: Credentials, term: str
) -> tuple[int, list[str] | None]:
    """Status and the links of the provider ``tasks``; ``None`` for an unreadable answer.

    Unlike ``provider_search`` of the spike nothing of the raw answer is printed: the links
    of a shared list carry an account id.
    """
    response = await client.get(
        f"{creds.base_url}/ocs/v2.php/search/providers/tasks/search",
        params={"term": term},
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=creds.auth(),
    )
    try:
        entries = response.json()["ocs"]["data"]["entries"]
    except (ValueError, KeyError, TypeError):
        return response.status_code, None
    if not isinstance(entries, list):
        return response.status_code, None
    return response.status_code, [
        str(entry.get("resourceUrl", "")) for entry in entries if isinstance(entry, dict)
    ]


def neutral_link(link: str, target: Target) -> str:
    """A link with the base replaced and every account id of this run replaced."""
    text = link.replace(target.base_url, "{base}")
    for user in (target.alice, target.bob):
        text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(user)}(?![A-Za-z0-9])", "<konto>", text)
    return text


def link_target(status: int, location: str, body: bytes) -> str:
    """``aufgabe`` only for a 200 that loads the script of the Tasks app itself."""
    if status == 200:
        return "aufgabe" if _TASKS_SCRIPT.search(body) else "seite-ohne-tasks-app"
    if 300 <= status < 400:
        return "login" if "/login" in location else "weiterleitung"
    return "fehler"


async def links(target: Target, env: Mapping[str, str], own_list: str, run: str) -> None:
    """Provider links for an own, a shared and a special list; the deep link in two forms."""
    async with spike.new_client() as client:
        alice = appapi_creds(env, target.base_url, target.alice)
        bob = appapi_creds(env, target.base_url, target.bob)
        await make_list(client, alice, LIST_SPECIAL, SPECIAL_DISPLAY)
        placed = {
            "eigen": (alice, own_list, f"{PREFIX}-link-eigen-{run}"),
            "geteilt": (bob, LIST_RW, f"{PREFIX}-link-geteilt-{run}"),
            "sonderzeichen": (alice, LIST_SPECIAL, f"{PREFIX}-link-sonder-ä&+ {run}"),
        }
        for case, (creds, uri, uid) in placed.items():
            text = spike.simple_todo(uid, f"{LINK_TERM} {case} & <ä>")
            status = await put_task(client, creds, uri, f"{uid}.ics", text)
            note(f"SETUP PUT link-aufgabe fall={case} status={status}")
        status, found = await provider_links(client, alice, LINK_TERM)
        count = "unlesbar" if found is None else str(len(found))
        note(f"PROVIDER suche status={status} eintraege={count}")
        by_case: dict[str, str] = {}
        for link in found or []:
            parts = spike.provider_link_parts(link)
            name = parts[1] if parts else unquote(link.rsplit("/", 1)[-1])
            for case, (_, _, uid) in placed.items():
                if name == f"{uid}.ics":
                    by_case[case] = link
        for case, (_, _, uid) in placed.items():
            link = by_case.get(case)
            if link is None:
                note(f"PROVIDERLINK {target.name} fall={case} vorhanden=nein")
                continue
            parts = spike.provider_link_parts(link)
            resolvable = "nein"
            if parts is not None:
                calendar_uri, object_name = parts
                got = await spike.dav_request(
                    client,
                    alice,
                    "GET",
                    object_url(target.base_url, target.alice, calendar_uri, object_name),
                )
                resolvable = yes_no(got.status == 200 and f"UID:{uid}" in got.body.decode())
            path = urlsplit(link).path
            note(
                f"PROVIDERLINK {target.name} fall={case} "
                f"form={'fragment' if '#' in link else 'pfad'} "
                f"index_php={yes_no('/index.php/' in path)} aufloesbar={resolvable} "
                f"shared_by_im_link={yes_no('_shared_by_' in link)} "
                f"prozentkodiert={yes_no('%' in link)} link={neutral_link(link, target)}"
            )
        uid = placed["eigen"][2]
        tail = f"apps/tasks/calendars/{quote(own_list, safe='')}/tasks/{quote(uid, safe='')}.ics"
        for form, prefix in (("index.php", "/index.php/"), ("ohne", "/")):
            url = f"{target.base_url}{prefix}{tail}"
            for auth, creds in (("anonym", None), ("impersonation", alice)):
                response = await client.get(url, auth=creds.auth() if creds else None)
                location = response.headers.get("location", "")
                note(
                    f"LINK {target.name} form={form} auth={auth} status={response.status_code} "
                    f"ziel={link_target(response.status_code, location, response.content)} "
                    f"location={neutral_link(location, target) or '-'}"
                )
        start = f"{target.base_url}/index.php/apps/tasks/"
        response = await client.get(start, auth=alice.auth())
        reached = link_target(
            response.status_code, response.headers.get("location", ""), response.content
        )
        note(
            f"LINK {target.name} form=startseite auth=impersonation "
            f"status={response.status_code} ziel={reached}"
        )


# --- live: home ----------------------------------------------------------------------------------


async def home(target: Target, env: Mapping[str, str]) -> None:
    """A fresh account after one login and an account that never logged in, impersonated."""
    password = secrets.token_urlsafe(24)
    spike.remember_secret("PASSWORD_FRESH", password)
    spike.occ_pw(target.container, password, "user:add", "--password-from-env", FRESH_USER)
    note(f"occ user:add --password-from-env {FRESH_USER} (password via stdin)")
    never = secrets.token_urlsafe(24)
    spike.remember_secret("PASSWORD_NEVER", never)
    spike.occ_pw(target.container, never, "user:add", "--password-from-env", NEVER_USER)
    note(f"occ user:add --password-from-env {NEVER_USER} (password via stdin, never used)")
    async with spike.new_client() as client:
        response = await client.get(
            f"{target.base_url}/ocs/v2.php/cloud/user",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            auth=(FRESH_USER, password),
        )
        count, _ = spike.calendars_db(target.container, FRESH_USER)
        note(
            f"ERSTANMELDUNG konto=frisch basic GET /ocs/v2.php/cloud/user "
            f"status={response.status_code} kalender_db={count}"
        )
        for case, user in (("frisch", FRESH_USER), ("nie", NEVER_USER)):
            before, _ = spike.calendars_db(target.container, user)
            creds = appapi_creds(env, target.base_url, user)
            results = []
            for _ in range(2):
                results.append(
                    await spike.dav_request(
                        client,
                        creds,
                        "PROPFIND",
                        home_url(target.base_url, user),
                        depth="1",
                        body=spike.propfind_body(NAME_PROPS),
                    )
                )
            after, _ = spike.calendars_db(target.container, user)
            first = results[0]
            entries = spike.parse_home(first.body) if first.status == 207 else []
            calendars = [entry for entry in entries if "calendar" in entry.types]
            only_vevent = bool(calendars) and all(
                entry.components == ("VEVENT",) for entry in calendars
            )
            note(
                f"HOME {target.name} konto={case} status={first.status} "
                f"vtodo_listen={len(spike.task_lists(entries))} kalender={len(calendars)} "
                f"nur_vevent={yes_no(only_vevent)} zweiter_status={results[1].status} "
                f"kalender_db_vorher={before} kalender_db_danach={after} "
                f"fehler={spike.describe_error(first.body)[:120] or '-'}"
            )


# --- live: app state -----------------------------------------------------------------------------


async def app_signals(target: Target, env: Mapping[str, str]) -> tuple[str, str, str]:
    alice = appapi_creds(env, target.base_url, target.alice)
    async with spike.new_client() as client:
        nav = await client.get(
            f"{target.base_url}/ocs/v2.php/core/navigation/apps",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            auth=alice.auth(),
        )
        try:
            nav_payload = nav.json()["ocs"]["data"]
        except (ValueError, KeyError, TypeError):
            nav_payload = None
        providers = await client.get(
            f"{target.base_url}/ocs/v2.php/search/providers",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            auth=alice.auth(),
        )
        try:
            provider_payload = providers.json()["ocs"]["data"]
        except (ValueError, KeyError, TypeError):
            provider_payload = None
        provider: bool | None = None
        if providers.status_code == 200 and isinstance(provider_payload, list) and provider_payload:
            provider = any(
                isinstance(entry, dict) and entry.get("id") == TASKS_APP
                for entry in provider_payload
            )
        status, found = await provider_links(client, alice, LINK_TERM)
    navigation = navigation_lists(nav_payload, TASKS_APP) if nav.status_code == 200 else None
    hits = "unlesbar" if found is None else str(len(found))
    return (
        tri(navigation),
        tri(provider),
        f"nav_status={nav.status_code} provider_suche_status={status} provider_treffer={hits}",
    )


async def appstate(target: Target, env: Mapping[str, str]) -> None:
    """Navigation and provider list: on, disabled without restart, after restart, on again."""

    async def record(state: str) -> None:
        navigation, provider, extra = await app_signals(target, env)
        note(
            f"APPSTATE {target.name} zustand={state} navigation={navigation} provider={provider} "
            f"app_list={tasks_app_state(target.container)} {extra}"
        )

    await record("an")
    out = spike.occ(target.container, "app:disable", TASKS_APP, check=False)
    note(f"occ app:disable {TASKS_APP} -> {spike._one_line(out)[:160]}")
    await record("disable-ohne-neustart")
    restart(target)
    await record("disable-nach-neustart")
    out = spike.occ(target.container, "app:enable", TASKS_APP, check=False)
    note(f"occ app:enable {TASKS_APP} -> {spike._one_line(out)[:160]}")
    await record("enable-ohne-neustart")
    restart(target)
    await record("wieder-an")


# --- live: the run -------------------------------------------------------------------------------


def info_xml_version() -> str:
    text = (REPO_ROOT / "appinfo" / "info.xml").read_text(encoding="utf-8")
    found = re.search(r"<version>([^<]+)</version>", text)
    return found[1].strip() if found else ""


def live_preconditions(target: Target, env: Mapping[str, str]) -> None:
    """The instance answers, and the version sent to AppAPI is the real one (32-RULES.md 8)."""
    version = info_xml_version()
    if not version or env.get("APP_VERSION") != version:
        raise spike.RunFailed("APP_VERSION of the environment file is not the one of info.xml")
    listed = spike.occ(target.container, "app_api:app:list", check=False)
    registered = [line.strip() for line in listed.splitlines() if "mcp_connector" in line]
    note(f"EXAPP {target.name} info_xml={version} registriert={' | '.join(registered) or 'keine'}")
    if not any(f": {version} [enabled]" in line for line in registered):
        # AppAPI takes the version header of a request as the new registered version; a run
        # that sent another one would change the registration (32-02: it stays unchanged).
        raise spike.RunFailed("the registered app is not enabled with the version of info.xml")
    status = httpx.get(f"{target.base_url}/status.php", timeout=10.0).status_code
    note(f"GET {target.base_url}/status.php -> HTTP {status}")
    if status != 200:
        raise spike.RunFailed(f"{target.name} does not answer; run the subcommand up first")
    out = spike.occ(target.container, "status", check=False)
    found = re.search(r"versionstring:\s*(\S+)", out)
    note(f"VERSION OF RECORD {target.name} {found[1] if found else '(not readable)'}")
    note(f"dbtype: {spike.occ(target.container, 'config:system:get', 'dbtype', check=False)}")


async def control(target: Target, env: Mapping[str, str]) -> None:
    alice = appapi_creds(env, target.base_url, target.alice)
    async with spike.new_client() as client:
        response = await client.get(
            f"{target.base_url}/ocs/v2.php/cloud/user",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            auth=alice.auth(),
        )
    try:
        seen = str(response.json()["ocs"]["data"]["id"])
    except (ValueError, KeyError, TypeError):
        seen = ""
    note(
        f"KONTROLLE impersonation status={response.status_code} "
        f"gleich={yes_no(seen == target.alice)}"
    )
    if seen != target.alice:
        raise spike.RunFailed("the impersonation control failed; nothing was changed")


async def live(target: Target, env: Mapping[str, str], steps: Sequence[str]) -> None:
    """Task 4 and 5: everything under impersonation, then the teardown and the baseline."""
    spike.section(f"live {target.name} steps={','.join(steps)}, start {spike.now_stamp()}")
    live_preconditions(target, env)
    await control(target, env)
    before_app = tasks_app_state(target.container)
    note(f"TASKSAPP {target.name} vorher={before_app}")
    async with spike.new_client() as client:
        for user in (target.alice, target.bob):
            left = await prefixed_lists(client, appapi_creds(env, target.base_url, user))
            if left:
                raise spike.RunFailed(f"{len(left)} lists of this plan are left; teardown first")
    before = baseline(target, "vorher")
    run = datetime.now(UTC).strftime("%H%M%S")
    containers = (target.container,)
    try:
        ensure_tasks_app(target)
        alice = appapi_creds(env, target.base_url, target.alice)
        series = "search" in steps or "children" in steps
        own_list = LIST_SERIES if series else LIST_OWN
        if series:
            await build_series(alice, target.container, run, parallel=1, label=target.name)
        if "search" in steps:
            await search_series(
                alice, containers, db=target.name, impersonation=True, warm=3, runs=15
            )
        if "children" in steps:
            await children_series(
                alice, containers, run, db=target.name, impersonation=True, warm=1, runs=6
            )
        if not series:
            async with spike.new_client() as client:
                await make_list(client, alice, LIST_OWN)
        if "names" in steps:
            await names(target, env, own_list)
        if "link" in steps:
            await links(target, env, own_list, run)
        if "home" in steps:
            await home(target, env)
        if "appstate" in steps:
            await appstate(target, env)
    except Exception as failure:
        note(f"BLOCK FAILED | live {target.name} | {type(failure).__name__}: {str(failure)[:300]}")
        raise
    finally:
        await teardown(target, env)
        restore_tasks_app(target, before_app)
        after = baseline(target, "nachher")
        for user, value in before.items():
            note(
                f"BASELINE-VERGLEICH {target.name} konto={user} "
                f"gleich={yes_no(after.get(user) == value)}"
            )


# --- docker --------------------------------------------------------------------------------------


def up(target: Target) -> None:
    spike.section(f"up {target.name}")
    running = spike.docker("ps", "--format", "{{.Names}}", check=False).split()
    others = [name for t in TARGETS.values() if t != target for name in t.containers]
    if any(name in running for name in others) or any(
        name.startswith(spike.SPIKE_NAME_FILTER) for name in running
    ):
        raise spike.RunFailed("another instance of this plan is running; one at a time")
    spike.ram_gate(target.containers)
    for name in target.containers:
        note(f"docker start {name} -> {spike.docker('start', name).strip()}")
    spike.wait_for_http(target.base_url)
    spike.wait_for_install(target.container)


def stop(target: Target) -> None:
    spike.section(f"stop {target.name}")
    for name in target.containers:
        out = spike.docker("stop", name, check=False).strip()
        running = spike.docker("inspect", "--format", "{{.State.Running}}", name, check=False)
        note(f"docker stop {name} -> {out[:80]} | laeuft={running.strip()}")


# --- privileges of the fixture -------------------------------------------------------------------


def fixture_privileges(path: Path) -> None:
    """Per collection of a discovery fixture: kind, read-only and the privilege set."""
    for entry in spike.parse_home(path.read_bytes()):
        read_only = "fehlt" if entry.read_only is None else (entry.read_only or "leer")
        note(
            f"FIXTURE {path.name} art={spike.classify_collection(entry)} read_only={read_only} "
            f"privilegien={','.join(sorted(set(entry.privileges))) or 'keine'}"
        )


# --- secret scan ---------------------------------------------------------------------------------


def scan(env_files: Sequence[Path], files: Sequence[Path]) -> int:
    """Every value of the env files, and its first 12 chars, against every line of ``files``.

    Only the variable name and the place are printed, never a value.
    """
    wanted: dict[str, str] = {}
    for env_file in env_files:
        for name, value in spike.read_env_file(env_file).items():
            if value.strip():
                wanted[f"{env_file.name}:{name}"] = value
                if len(value) > 12:
                    wanted[f"{env_file.name}:{name}[:12]"] = value[:12]
    hits = 0
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for name, value in wanted.items():
                if value in line:
                    hits += 1
                    print(f"TREFFER {path.name}:{number}: {name}")
            if spike.APPAPI_HEADER in line:
                hits += 1
                print(f"TREFFER {path.name}:{number}: header name")
    print(f"scan: {hits} hit(s) in {len(files)} file(s)")
    return 0


# --- main ----------------------------------------------------------------------------------------


def _env(path: Path) -> dict[str, str]:
    env = spike.read_env_file(path)
    spike.remember_env_secrets(env)
    return env


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("throwaway")
    one.add_argument("--db", choices=spike.COST_DBS, required=True)
    one.add_argument("--out", type=Path, required=True)
    for name in ("up", "stop", "live", "teardown"):
        command = sub.add_parser(name)
        command.add_argument("--instance", choices=sorted(TARGETS), required=True)
        command.add_argument("--out", type=Path, required=True)
        if name in ("live", "teardown"):
            command.add_argument("--env-file", type=Path, required=True)
        if name == "teardown":
            command.add_argument(
                "--tasks-before", help="state of the Tasks app before the run, e.g. keine"
            )
        if name == "live":
            command.add_argument("--steps", default="names,link,home,appstate")
    fixture = sub.add_parser("privileges")
    fixture.add_argument("--fixture", type=Path, required=True)
    scanner = sub.add_parser("scan")
    scanner.add_argument("--env-file", type=Path, action="append", default=[])
    scanner.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args(argv)

    if args.command == "scan":
        return scan(args.env_file, args.files)
    if args.command == "privileges":
        fixture_privileges(args.fixture)
        return 0
    header = f"# tasks_measure.py {args.command} {spike.now_stamp()}"
    code = 0
    try:
        if args.command == "throwaway":
            asyncio.run(throwaway(args.db))
        else:
            target = TARGETS[args.instance]
            if args.command == "up":
                up(target)
            elif args.command == "stop":
                stop(target)
            elif args.command == "teardown":
                env = _env(args.env_file)
                asyncio.run(teardown(target, env))
                if args.tasks_before:
                    restore_tasks_app(target, args.tasks_before)
                baseline(target, "nach-teardown")
            else:
                env = _env(args.env_file)
                steps = [step.strip() for step in args.steps.split(",") if step.strip()]
                asyncio.run(live(target, env, steps))
    except spike.RunFailed as failure:
        note(f"ABBRUCH {failure}")
        code = 1
    finally:
        spike.write_protocol(args.out, header)
    return code


if __name__ == "__main__":
    sys.exit(main())

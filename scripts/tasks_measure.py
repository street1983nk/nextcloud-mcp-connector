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
* plan 32-09: how the discovery tells an own list the account shares itself (candidates
  ``oc:invite``, ``cs:invite``, ``DAV:share-access``, ``cs:publish-url``; step ``hinaus``,
  D-32-18) and the form of the provider subline for a shared list (step ``subline``,
  D-32-17), both printed as marks and counts only.
* plan 32-10: a list shared with a group, out of the account and into it (step ``gruppe``),
  three forms of a recurring task (step ``wieder``) and the cap of 500 with the budget of
  one list at 600 and 2000 open tasks (step ``deckel``).

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
import os
import re
import secrets
import statistics
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

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import tasks as tasks_client
from mcp_connector.nextcloud.clients import xml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials
from mcp_connector.tools import tasks as tasks_tools

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
#: Plan 32-09: an own list of alice it shares itself, a list bob shares with alice.
GAP_PREFIX = "p3209"
LIST_OUT = f"{GAP_PREFIX}-aus"
LIST_IN = f"{GAP_PREFIX}-rein"
SUBLINE_TERM = f"{GAP_PREFIX}sub"
#: Plan 32-10: group shares, recurring tasks and the cap.
GROUP_PREFIX = "p3210"
PREFIXES = (PREFIX, GAP_PREFIX, GROUP_PREFIX)
#: The anonymised raw discoveries of plan 32-09 go here, never into the repository.
SCRATCH_DIR = Path(os.environ.get("P3209_SCRATCH", ".")).resolve()

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


#: The candidates of plan 32-09 (D-32-18) for "an own list the account shares itself".
SHARE_CANDIDATES = (
    f"{{{xml.OC}}}invite",
    f"{{{xml.CS}}}invite",
    f"{{{xml.DAV}}}share-access",
    f"{{{xml.CS}}}publish-url",
)
#: Children of ``share-access`` that say "nobody else".
_NOT_SHARED = frozenset({"not-shared"})


@dataclass(frozen=True, slots=True)
class ShareMark:
    """One candidate of one collection: propstat status, filled or not, number of entries.

    Never a href, a principal or a name: the entries are only counted.
    """

    status: str
    filled: bool
    entries: int


def _share_entries(element: etree._Element) -> int:
    local = etree.QName(element).localname
    children = [child for child in element if isinstance(child.tag, str)]
    if local == "invite":
        return sum(1 for child in children if etree.QName(child).localname == "user")
    if local == "share-access":
        return sum(1 for child in children if etree.QName(child).localname not in _NOT_SHARED)
    hrefs = [child for child in children if (child.text or "").strip()]
    if hrefs:
        return len(hrefs)
    return 1 if (element.text or "").strip() else 0


def share_state(response: etree._Element) -> dict[str, ShareMark]:
    """Every candidate of ``SHARE_CANDIDATES`` in one ``DAV:response`` of a discovery."""
    marks = {name: ShareMark("fehlt", False, 0) for name in SHARE_CANDIDATES}
    for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
        status_line = propstat.findtext(f"{{{xml.DAV}}}status") or ""
        code = next((part for part in status_line.split() if part.isdigit()), "")
        for name in SHARE_CANDIDATES:
            element = propstat.find(f"{{{xml.DAV}}}prop/{name}")
            if element is None:
                continue
            if code.startswith("2"):
                entries = _share_entries(element)
                marks[name] = ShareMark("2xx", entries > 0, entries)
            else:
                marks[name] = ShareMark(code or "unklar", False, 0)
    return marks


def share_states(body: bytes) -> dict[str, dict[str, ShareMark]]:
    """``uri -> share_state`` for every response of a discovery."""
    root = xml.parse_root(body)
    found: dict[str, dict[str, ShareMark]] = {}
    for response in root.findall(f"{{{xml.DAV}}}response"):
        path = urlsplit((response.findtext(f"{{{xml.DAV}}}href") or "").strip()).path
        found[unquote(path.rstrip("/").rsplit("/", 1)[-1])] = share_state(response)
    return found


def share_line(instance: str, state: str, auth: str, prop: str, mark: ShareMark) -> str:
    return (
        f"HINAUS {instance} zustand={state} auth={auth} prop={prop} status={mark.status} "
        f"belegt={yes_no(mark.filled)} eintraege={mark.entries}"
    )


def subline_form(subline: str, raw_display: str, owner: str) -> dict[str, bool]:
    """Yes/no marks of one provider subline against the raw list name and the owner name.

    ``bereinigt_moeglich``: the subline ends with `` (<raw name>)``, the raw name carries
    exactly the owner suffix of D-32-14, and after the replacement the owner is gone.
    """
    ends = bool(raw_display) and subline.endswith(f" ({raw_display})")
    has_owner = bool(owner.strip()) and owner.casefold() in subline.casefold()
    stripped = owner_suffix_strip(raw_display, owner) if raw_display else None
    possible = False
    if ends and stripped is not None:
        cleaned = f"{subline[: -len(f' ({raw_display})')]} ({stripped})"
        possible = owner.casefold() not in cleaned.casefold()
    return {
        "endet_mit_rohname": ends,
        "enthaelt_besitzer": has_owner,
        "bereinigt_moeglich": possible,
    }


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


# --- pure helpers of plan 32-10 (tests/unit/test_tasks_measure.py) -------------------------------


def group_share_body(gid: str, *, writable: bool, remove: bool = False) -> bytes:
    """The share document for the group ``gid``: set (read only or read-write) or remove."""
    root = etree.Element(
        f"{{{spike.OC_SHARE_NS}}}share", nsmap={"d": xml.DAV, "o": spike.OC_SHARE_NS}
    )
    entry = etree.SubElement(root, f"{{{spike.OC_SHARE_NS}}}{'remove' if remove else 'set'}")
    etree.SubElement(entry, f"{{{xml.DAV}}}href").text = f"principal:principals/groups/{gid}"
    if writable and not remove:
        etree.SubElement(entry, f"{{{spike.OC_SHARE_NS}}}read-write")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


@dataclass(frozen=True, slots=True)
class InviteShape:
    """The form of one ``oc:invite``: number of entries, local names of the entries, kinds.

    Never a href, a principal or a name: ``kinds`` is ``users``, ``groups``, ``andere`` or a
    ``+`` join of them, ``keine`` without any entry.
    """

    entries: int
    children: tuple[str, ...]
    kinds: str


def _principal_kind(entry: etree._Element) -> str:
    href = next(
        (
            (element.text or "").strip()
            for element in entry.iter(f"{{{xml.DAV}}}href")
            if (element.text or "").strip()
        ),
        "",
    )
    if "principals/users/" in href:
        return "users"
    if "principals/groups/" in href:
        return "groups"
    return "andere"


def invite_shape(element: etree._Element) -> InviteShape:
    entries = [child for child in element if isinstance(child.tag, str)]
    children = tuple(sorted({etree.QName(child).localname for child in entries}))
    kinds = "+".join(sorted({_principal_kind(child) for child in entries})) or "keine"
    return InviteShape(len(entries), children, kinds)


#: The form of a recurring task the Tasks app 0.18.1 writes (measured in phase 30).
RECURRING_TEMPLATE = REPO_ROOT / "tests" / "fixtures" / "tasks_app" / "recurring.ics"
RECURRING_FORMS = ("app", "instanz-erledigt", "master-erledigt")
#: The second occurrence of the template (DUE 2026-11-20 13:00 UTC, daily).
_SECOND_OCCURRENCE = "20261121T130000Z"
_DONE_LINES = ("STATUS:COMPLETED", "PERCENT-COMPLETE:100", "COMPLETED:20261121T140000Z")


def recurring_todo(uid: str, summary: str, form: str) -> str:
    """One of the three recurring forms of plan 32-10, built from the Tasks app template.

    ``app``: the template with ``uid`` and ``summary``. ``instanz-erledigt``: the same master
    and, in the same object, an override of the second occurrence that is done.
    ``master-erledigt``: the master with the rule, done.
    """
    if form not in RECURRING_FORMS:
        raise ValueError(f"unknown recurring form {form!r}")
    lines = RECURRING_TEMPLATE.read_text(encoding="utf-8").replace("\r\n", "\n").splitlines()
    master: list[str] = []
    for line in lines:
        if line.startswith("UID:"):
            line = f"UID:{uid}"
        elif line.startswith("SUMMARY:"):
            line = f"SUMMARY:{summary}"
        master.append(line)
    end = master.index("END:VTODO")
    if form == "master-erledigt":
        master[end:end] = list(_DONE_LINES)
    elif form == "instanz-erledigt":
        override = [
            "BEGIN:VTODO",
            f"UID:{uid}",
            "DTSTAMP:20261121T140000Z",
            f"SUMMARY:{summary}",
            f"RECURRENCE-ID:{_SECOND_OCCURRENCE}",
            f"DUE:{_SECOND_OCCURRENCE}",
            *_DONE_LINES,
            "END:VTODO",
        ]
        master[end + 1 : end + 1] = override
    return "\r\n".join(spike.fold_line(line) for line in master) + "\r\n"


@dataclass(frozen=True, slots=True)
class PagingSummary:
    """A walk through the pages of ``tasks_search``: only counts and yes/no."""

    pages: int
    per_page: int
    hits: int
    unique: int
    last_note: bool
    last_next: bool
    degraded: bool


def paging_summary(pages: Sequence[Mapping[str, Any]]) -> PagingSummary:
    ids_seen: list[str] = []
    per_page = 0
    for page in pages:
        tasks = [hit for hit in page.get("tasks") or [] if isinstance(hit, dict)]
        per_page = max(per_page, len(tasks))
        ids_seen.extend(str(hit.get("id")) for hit in tasks)
    last = pages[-1] if pages else {}
    return PagingSummary(
        pages=len(pages),
        per_page=per_page,
        hits=len(ids_seen),
        unique=len(set(ids_seen)),
        last_note=bool(last.get("note")),
        last_next=bool(last.get("next")),
        degraded=any(page.get("degraded") for page in pages),
    )


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
    return [entry for entry in spike.parse_home(result.body) if entry.uri.startswith(PREFIXES)]


async def purge_trash(client: httpx.AsyncClient, creds: Credentials) -> tuple[int, int]:
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
        return 0, 0
    removed = 0
    cleared = 0
    for href, props in xml.parse_multistatus(listed.body):
        data = props.get(f"{{{xml.CAL}}}calendar-data", "")
        if not any(f"UID:{p}" in spike.unfold(data) for p in PREFIXES):
            continue
        path = urlsplit(href).path
        gone = await spike.dav_request(
            client, creds, "DELETE", f"{creds.base_url}{path}", extra_headers=NO_TRASHBIN
        )
        removed += 1
        cleared += 1 if gone.status in (200, 204) else 0
        note(f"PAPIERKORB konto={creds.user} objekt_geloescht status={gone.status}")
    return removed, cleared


async def teardown(target: Target, env: Mapping[str, str]) -> None:
    """Shares back, lists deleted without trash bin, trash emptied, accounts deleted."""
    spike.section(f"rueckbau {target.name}")
    await group_teardown(target, env)
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
        alice = appapi_creds(env, target.base_url, target.alice)
        for label, creds, owner, uri, body in (
            ("freigabe_entfernt", alice, target.alice, LIST_OUT, _unshare_body(target.bob)),
            ("link_entfernt", alice, target.alice, LIST_OUT, _publish_body(False)),
            ("freigabe_entfernt", bob, target.bob, LIST_IN, _unshare_body(target.alice)),
        ):
            result = await spike.dav_request(
                client, creds, "POST", list_url(target.base_url, owner, uri), body=body
            )
            note(f"RUECKBAU {label} liste={uri} status={result.status}")
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
            removed, cleared = await purge_trash(client, creds)
            note(f"RUECKBAU papierkorb konto={user} entfernte_eintraege={removed}")
            note(f"PAPIERKORB {target.name} konto={user} gefunden={removed} geleert={cleared}")
            left = await prefixed_lists(client, creds)
            note(f"RUECKBAU reste konto={user} listen_mit_praefix={len(left)}")
    for user in (FRESH_USER, NEVER_USER):
        out = spike.occ(target.container, "user:delete", user, check=False)
        note(f"occ user:delete {user} -> {spike._one_line(out)[:120]}")
    group_delete(target)


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


# --- live: lists the account shares itself, and the subline (plan 32-09) ----------------------


def basic_creds(env: Mapping[str, str], base: str, user: str, key: str) -> Credentials:
    """The app password of a test account from the environment file, never printed."""
    secret = env.get(key, "")
    if not secret:
        raise spike.RunFailed(f"the environment file names no {key}")
    spike.remember_secret(key, secret)
    return Credentials(base_url=base, user=user, secret=secret, mode=MODE_BASIC)


def display_name(target: Target, user: str) -> str:
    raw = spike._json_or_text(spike.occ(target.container, "user:info", user, "--output=json"))
    if not isinstance(raw, dict):
        raise spike.RunFailed(f"occ user:info {user} returned no JSON object")
    return str(raw.get("display_name") or raw.get("displayname") or "")


def _publish_body(publish: bool) -> bytes:
    name = "publish-calendar" if publish else "unpublish-calendar"
    root = etree.Element(f"{{{xml.CS}}}{name}", nsmap={"cs": xml.CS})
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _unshare_body(user: str) -> bytes:
    root = etree.Element(
        f"{{{spike.OC_SHARE_NS}}}share", nsmap={"d": xml.DAV, "o": spike.OC_SHARE_NS}
    )
    entry = etree.SubElement(root, f"{{{spike.OC_SHARE_NS}}}remove")
    etree.SubElement(entry, f"{{{xml.DAV}}}href").text = f"principal:principals/users/{user}"
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def anonymise(body: bytes, target: Target, bob_display: str) -> bytes:
    """The discovery with every trace of the sharee replaced and every public token cut."""
    text = body.decode("utf-8")
    if bob_display:
        text = text.replace(bob_display, "Sharee")
    text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(target.bob)}(?![A-Za-z0-9])", "sharee", text)
    text = re.sub(r"public-calendars/[^<\"\s]+", "public-calendars/TOKEN", text)
    return text.replace(target.base_url, "https://nextcloud.example").encode("utf-8")


async def _discovery(client: httpx.AsyncClient, creds: Credentials) -> bytes:
    result = await spike.dav_request(
        client,
        creds,
        "PROPFIND",
        home_url(creds.base_url, creds.user),
        depth="1",
        body=spike.propfind_body((*NAME_PROPS, *SHARE_CANDIDATES)),
    )
    if result.status != 207:
        raise spike.RunFailed(f"the discovery answered {result.status}")
    return result.body


async def gap(target: Target, env: Mapping[str, str], steps: Sequence[str], run: str) -> None:
    """Steps ``hinaus`` and ``subline``: only marks, counts and yes/no, never a name."""
    base = target.base_url
    alice = basic_creds(env, base, target.alice, "NC_MCP_TEST_APP_PASSWORD")
    bob = basic_creds(env, base, target.bob, "NC_MCP_TEST_APP_PASSWORD2")
    alice_aa = appapi_creds(env, base, target.alice)
    bob_display = display_name(target, target.bob)
    if bob_display and bob_display != target.bob:
        spike.remember_secret("BOB_DISPLAY", bob_display)
    out_url = list_url(base, target.alice, LIST_OUT)
    in_url = list_url(base, target.bob, LIST_IN)
    async with spike.new_client() as client:
        await make_list(client, alice, LIST_OUT)
        await make_list(client, bob, LIST_IN)
        shared = await spike.dav_request(
            client, bob, "POST", in_url, body=spike.share_body(target.alice, writable=True)
        )
        note(f"SETUP FREIGABE liste={LIST_IN} an=alice schreibrecht=ja status={shared.status}")

        async def probe(state: str) -> None:
            for auth, creds in (("basic", alice), ("appapi", alice_aa)):
                body = await _discovery(client, creds)
                marks = share_states(body)
                own = marks.get(LIST_OUT)
                if own is None:
                    raise spike.RunFailed(f"{LIST_OUT} is missing in the discovery")
                for prop in SHARE_CANDIDATES:
                    note(share_line(target.name, state, auth, prop, own[prop]))
                if state == "privat":
                    inbound = [
                        m for uri, m in marks.items() if uri.startswith(f"{LIST_IN}_shared_by_")
                    ]
                    for mark in inbound[:1]:
                        for prop in SHARE_CANDIDATES:
                            note(share_line(target.name, "hineingeteilt", auth, prop, mark[prop]))
                    if not inbound:
                        note(
                            f"HINAUS {target.name} zustand=hineingeteilt auth={auth} vorhanden=nein"
                        )
                if auth == "basic" and state in ("an-bob-ro", "veroeffentlicht"):
                    keep = SCRATCH_DIR / f"discovery-hinaus-{state}-{target.name}.xml"
                    keep.write_bytes(anonymise(body, target, bob_display))
                    note(f"ROHKOERPER zustand={state} anonymisiert bytes={keep.stat().st_size}")

        async def post(creds: Credentials, url: str, body: bytes, label: str) -> None:
            result = await spike.dav_request(client, creds, "POST", url, body=body)
            note(f"SETUP {label} status={result.status}")

        if "hinaus" in steps:
            await probe("privat")
            await post(
                alice, out_url, spike.share_body(target.bob, writable=False), "FREIGABE an-bob-ro"
            )
            await probe("an-bob-ro")
            await post(
                alice, out_url, spike.share_body(target.bob, writable=True), "FREIGABE an-bob-rw"
            )
            await probe("an-bob-rw")
            await post(alice, out_url, _unshare_body(target.bob), "FREIGABE zurueck")
            await post(alice, out_url, _publish_body(True), "LINK veroeffentlicht")
            await probe("veroeffentlicht")
            await post(alice, out_url, _publish_body(False), "LINK zurueck")
            await probe("zurueckgenommen")
            note(f"HINAUS {target.name} zustand=gruppe entfaellt grund=nicht-freigegeben")

        if "subline" in steps:
            placed = {
                "eigen": (alice, LIST_OUT, f"{GAP_PREFIX}-sub-eigen-{run}"),
                "geteilt": (bob, LIST_IN, f"{GAP_PREFIX}-sub-geteilt-{run}"),
            }
            for case, (creds, uri, uid) in placed.items():
                text = spike.simple_todo(uid, f"{SUBLINE_TERM} {case}", ["DUE:20261120T090000Z"])
                status = await put_task(client, creds, uri, f"{uid}.ics", text)
                note(f"SETUP PUT subline-aufgabe fall={case} status={status}")
            body = await _discovery(client, alice)
            raw_names = {e.uri: e.display for e in spike.parse_home(body)}
            owners = owner_names(body)
            in_uri = next((u for u in raw_names if u.startswith(f"{LIST_IN}_shared_by_")), "")
            response = await client.get(
                f"{base}/ocs/v2.php/search/providers/tasks/search",
                params={"term": SUBLINE_TERM},
                headers={"OCS-APIRequest": "true", "Accept": "application/json"},
                auth=alice.auth(),
            )
            try:
                entries = response.json()["ocs"]["data"]["entries"]
            except (ValueError, KeyError, TypeError):
                entries = None
            count = "unlesbar" if not isinstance(entries, list) else str(len(entries))
            note(f"PROVIDER subline status={response.status_code} eintraege={count}")
            for case in placed:
                title = f"{SUBLINE_TERM} {case}"
                entry = next(
                    (e for e in entries or [] if isinstance(e, dict) and e.get("title") == title),
                    None,
                )
                if entry is None:
                    note(f"SUBLINE {target.name} liste={case} vorhanden=nein")
                    continue
                subline = str(entry.get("subline") or "")
                raw = raw_names.get(in_uri if case == "geteilt" else LIST_OUT, "")
                owner = (owners.get(in_uri) or "") if case == "geteilt" else bob_display
                form = subline_form(subline, raw, owner or bob_display)
                has_id = re.search(
                    rf"(?<![A-Za-z0-9]){re.escape(target.bob)}(?![A-Za-z0-9])", subline
                )
                note(
                    f"SUBLINE {target.name} liste={case} "
                    + " ".join(f"{key}={yes_no(value)}" for key, value in form.items())
                    + f" enthaelt_kennung={yes_no(has_id is not None)} leer={yes_no(not subline)}"
                    + f" owner_displayname_gleich_anzeigename={yes_no(owner == bob_display)}"
                )


# --- live: group shares, recurring tasks and the cap (plan 32-10) ------------------------------

#: The group of this plan. Its id names neither alice nor bob; it is only printed in the
#: lines ``GRUPPE``.
GROUP_ID = f"{GROUP_PREFIX}grp"
LIST_GROUP_OUT = f"{GROUP_PREFIX}-aus"
LIST_GROUP_RW = f"{GROUP_PREFIX}-rein-rw"
LIST_GROUP_RO = f"{GROUP_PREFIX}-rein-ro"
LIST_RECURRING = f"{GROUP_PREFIX}-wieder"
LIST_CAP = f"{GROUP_PREFIX}-deckel"
GROUP_TERM = f"{GROUP_PREFIX}sub"
CAP_SIZES = (600, 2000)
GROUP_STEPS = ("gruppe", "wieder", "deckel")
#: The budget of a list while the wall clock of one call is measured: high enough that the
#: product budget never cuts the measurement short.
MEASURING_BUDGET = 60.0
SHARED_MARKER_TEXT = "_shared_by_"

#: Shares of one group, counted in ``dav_shares`` (32-10: the side of the group).
PHP_GROUP_SHARES = (
    spike._PHP_BOOT
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


def group_members(target: Target, gid: str) -> list[str] | None:
    """The members of ``gid``, ``None`` when the group does not exist."""
    listed = spike._json_or_text(
        spike.occ(target.container, "group:list", "--output=json", check=False)
    )
    if not isinstance(listed, dict):
        raise spike.RunFailed("occ group:list --output=json returned no JSON object")
    members = listed.get(gid)
    if members is None:
        return None
    return [str(member) for member in members] if isinstance(members, list) else []


def group_state(target: Target, phase: str) -> bool:
    exists = group_members(target, GROUP_ID) is not None
    shares = spike.php(target.container, PHP_GROUP_SHARES, GROUP_ID).strip()
    note(
        f"GRUPPE {target.name} name={GROUP_ID} vorhanden={yes_no(exists)} shares={shares} "
        f"phase={phase}"
    )
    return exists


def nc_clients(creds: Credentials) -> NcClients:
    return NcClients(client=httpx.AsyncClient(follow_redirects=False, timeout=60.0), creds=creds)


async def product_discovery(client: httpx.AsyncClient, creds: Credentials) -> bytes:
    """The discovery with exactly the body of the product."""
    result = await spike.dav_request(
        client,
        creds,
        "PROPFIND",
        home_url(creds.base_url, creds.user),
        depth="1",
        body=tasks_client.build_task_discovery_body(),
    )
    if result.status != 207:
        raise spike.RunFailed(f"the discovery answered {result.status}")
    return result.body


def _responses(body: bytes) -> dict[str, etree._Element]:
    root = xml.parse_root(body)
    found: dict[str, etree._Element] = {}
    for response in root.findall(f"{{{xml.DAV}}}response"):
        path = urlsplit((response.findtext(f"{{{xml.DAV}}}href") or "").strip()).path
        found[unquote(path.rstrip("/").rsplit("/", 1)[-1])] = response
    return found


def _in_propstat(response: etree._Element, name: str) -> tuple[str, etree._Element | None]:
    """``2xx``, the other status code or ``fehlt``, with the element of a 2xx propstat."""
    for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
        element = propstat.find(f"{{{xml.DAV}}}prop/{name}")
        if element is None:
            continue
        status_line = propstat.findtext(f"{{{xml.DAV}}}status") or ""
        code = next((part for part in status_line.split() if part.isdigit()), "")
        if code.startswith("2"):
            return "2xx", element
        return code or "unklar", None
    return "fehlt", None


def _text(element: etree._Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _names_owner(text: str, account: str, display: str) -> bool:
    by_id = re.search(rf"(?<![A-Za-z0-9]){re.escape(account)}(?![A-Za-z0-9])", text) is not None
    return by_id or (bool(display.strip()) and display.casefold() in text.casefold())


def anonymise_group(body: bytes, target: Target, bob_display: str) -> bytes:
    return anonymise(body, target, bob_display).replace(GROUP_ID.encode(), b"testgroup")


async def group_steps(target: Target, env: Mapping[str, str], run: str) -> None:
    """Step ``gruppe``: only marks, counts and yes/no, never a name or a href."""
    base = target.base_url
    alice = basic_creds(env, base, target.alice, "NC_MCP_TEST_APP_PASSWORD")
    bob = basic_creds(env, base, target.bob, "NC_MCP_TEST_APP_PASSWORD2")
    alice_aa = appapi_creds(env, base, target.alice)
    bob_display = display_name(target, target.bob)
    if bob_display and bob_display != target.bob:
        spike.remember_secret("BOB_DISPLAY", bob_display)
    home_path = urlsplit(home_url(base, target.alice)).path
    for argv in (
        ("group:add", GROUP_ID),
        ("group:adduser", GROUP_ID, target.bob),
        ("group:adduser", GROUP_ID, target.alice),
    ):
        spike.occ(target.container, *argv, check=False)
    members = group_members(target, GROUP_ID) or []
    both = {target.alice, target.bob} <= set(members)
    note(f"SETUP GRUPPE angelegt mitglieder={len(members)} alice_und_bob={yes_no(both)}")
    if not both:
        raise spike.RunFailed("the test group does not hold both test accounts")
    out_url = list_url(base, target.alice, LIST_GROUP_OUT)
    async with spike.new_client() as client:

        async def post(creds: Credentials, url: str, body: bytes, label: str) -> None:
            result = await spike.dav_request(client, creds, "POST", url, body=body)
            note(f"SETUP {label} status={result.status}")
            if result.status >= 300:
                raise spike.RunFailed(f"{label} answered {result.status}")

        await make_list(client, alice, LIST_GROUP_OUT)

        async def probe_out(state: str) -> None:
            for auth, creds in (("basic", alice), ("appapi", alice_aa)):
                body = await product_discovery(client, creds)
                responses = _responses(body)
                response = responses.get(LIST_GROUP_OUT)
                if response is None:
                    raise spike.RunFailed(f"{LIST_GROUP_OUT} is missing in the discovery")
                status, invite = _in_propstat(response, f"{{{xml.OC}}}invite")
                shape = invite_shape(invite) if invite is not None else InviteShape(0, (), "keine")
                lists = tasks_client.parse_task_home(body, home_path=home_path)
                own = next((entry for entry in lists if entry.uri == LIST_GROUP_OUT), None)
                if own is None:
                    raise spike.RunFailed(f"parse_task_home does not hold {LIST_GROUP_OUT}")
                note(
                    f"GRUPPE-HINAUS {target.name} zustand={state} auth={auth} "
                    f"invite_status={status} eintraege={shape.entries} "
                    f"kinder={','.join(shape.children) or 'keine'} principal_art={shape.kinds} "
                    f"shared_out={yes_no(own.shared_out)}"
                )
                if state.startswith("an-gruppe"):
                    seen = sum(1 for uri in responses if uri.startswith(LIST_GROUP_OUT))
                    note(
                        f"GRUPPE-SELBST {target.name} zustand={state} auth={auth} "
                        f"eigene_liste_doppelt={yes_no(seen > 1)}"
                    )
                if auth == "basic":
                    keep = SCRATCH_DIR / f"discovery-gruppe-{state}-{target.name}.xml"
                    keep.write_bytes(anonymise_group(body, target, bob_display))
                    note(f"ROHKOERPER zustand={state} anonymisiert bytes={keep.stat().st_size}")

        await probe_out("privat")
        await post(
            alice, out_url, group_share_body(GROUP_ID, writable=False), "FREIGABE an-gruppe-ro"
        )
        await probe_out("an-gruppe-ro")
        await post(
            alice, out_url, group_share_body(GROUP_ID, writable=True), "FREIGABE an-gruppe-rw"
        )
        await probe_out("an-gruppe-rw")
        await post(
            alice,
            out_url,
            group_share_body(GROUP_ID, writable=False, remove=True),
            "FREIGABE an-gruppe zurueck",
        )
        await probe_out("zurueckgenommen")

        # Into the account: two lists of bob, shared with the group that holds alice.
        placed: dict[tuple[str, bool], str] = {}
        for kind, uri, writable in (("rw", LIST_GROUP_RW, True), ("ro", LIST_GROUP_RO, False)):
            await make_list(client, bob, uri)
            await post(
                bob,
                list_url(base, target.bob, uri),
                group_share_body(GROUP_ID, writable=writable),
                f"FREIGABE {kind} an-gruppe",
            )
            for due in (False, True):
                form = "faellig" if due else "ohne"
                uid = f"{GROUP_PREFIX}-rein-{kind}-{form}-{run}"
                title = f"{GROUP_TERM} {kind} {form}"
                extra = ["DUE:20261204T090000Z"] if due else []
                status = await put_task(
                    client, bob, uri, f"{uid}.ics", spike.simple_todo(uid, title, extra)
                )
                note(f"SETUP PUT gruppe-aufgabe liste={kind} faellig={yes_no(due)} status={status}")
                placed[(kind, due)] = title

        shared: dict[str, tasks_client.TaskList] = {}
        raw_names: dict[str, str] = {}
        owners: dict[str, str] = {}
        for auth, creds in (("basic", alice), ("appapi", alice_aa)):
            body = await product_discovery(client, creds)
            responses = _responses(body)
            lists = tasks_client.parse_task_home(body, home_path=home_path)
            for kind, uri in (("rw", LIST_GROUP_RW), ("ro", LIST_GROUP_RO)):
                matching = [found for found in responses if found.startswith(uri)]
                if not matching:
                    note(f"GRUPPE-REIN {target.name} liste={kind} auth={auth} sichtbar=nein")
                    continue
                found_uri = matching[0]
                response = responses[found_uri]
                ro_status, _ = _in_propstat(response, f"{{{xml.OC}}}read-only")
                owner = _text(_in_propstat(response, OWNER_DISPLAYNAME)[1])
                raw = _text(_in_propstat(response, f"{{{xml.DAV}}}displayname")[1])
                entry = next((item for item in lists if item.uri == found_uri), None)
                if entry is None:
                    note(f"GRUPPE-REIN {target.name} liste={kind} auth={auth} parse=fehlt")
                    continue
                if auth == "basic":
                    shared[kind] = entry
                    raw_names[kind] = raw
                    owners[kind] = owner
                clean_name = (
                    entry.name == uri
                    and not _names_owner(entry.name, target.bob, bob_display)
                    and SHARED_MARKER_TEXT not in entry.name
                )
                note(
                    f"GRUPPE-REIN {target.name} liste={kind} auth={auth} sichtbar=ja "
                    f"eintraege={len(matching)} "
                    f"uri_mit_marker={yes_no(SHARED_MARKER_TEXT in found_uri)} "
                    f"read_only_2xx={yes_no(ro_status == '2xx')} "
                    f"owner_displayname_passt={yes_no(bool(owner) and owner == bob_display)} "
                    f"shared={yes_no(entry.shared)} writable={yes_no(entry.writable)} "
                    f"name_ohne_besitzer={yes_no(clean_name)}"
                )
            if auth == "basic":
                keep = SCRATCH_DIR / f"discovery-gruppe-rein-{target.name}.xml"
                keep.write_bytes(anonymise_group(body, target, bob_display))
                note(f"ROHKOERPER zustand=rein anonymisiert bytes={keep.stat().st_size}")

        response = await client.get(
            f"{base}/ocs/v2.php/search/providers/tasks/search",
            params={"term": GROUP_TERM},
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            auth=alice.auth(),
        )
        try:
            entries = response.json()["ocs"]["data"]["entries"]
        except (ValueError, KeyError, TypeError):
            entries = None
        count = "unlesbar" if not isinstance(entries, list) else str(len(entries))
        note(f"PROVIDER gruppe status={response.status_code} eintraege={count}")
        for (kind, due), title in placed.items():
            hit = next(
                (e for e in entries or [] if isinstance(e, dict) and e.get("title") == title), None
            )
            task_list = shared.get(kind)
            if hit is None or task_list is None:
                note(
                    f"GRUPPE-SUBLINE {target.name} liste={kind} faellig={yes_no(due)} "
                    "vorhanden=nein"
                )
                continue
            subline = str(hit.get("subline") or "")
            raw = raw_names.get(kind, "")
            owner = owners.get(kind) or bob_display
            cleaned = tasks_client.clean_subline(subline, task_list)
            if cleaned is None:
                outcome, without = "weggelassen", True
            else:
                outcome = "unveraendert" if cleaned == subline else "bereinigt"
                without = not _names_owner(cleaned, target.bob, owner)
            note(
                f"GRUPPE-SUBLINE {target.name} liste={kind} faellig={yes_no(due)} "
                f"endet_mit_rohname={yes_no(bool(raw) and subline.endswith(f'({raw})'))} "
                f"enthaelt_besitzer={yes_no(_names_owner(subline, target.bob, owner))} "
                f"clean_subline={outcome} clean_subline_ohne_besitzer={yes_no(without)}"
            )


async def recurring_steps(target: Target, env: Mapping[str, str], run: str) -> None:
    """Step ``wieder``: the three recurring forms in one own list of alice."""
    base = target.base_url
    alice = appapi_creds(env, base, target.alice)
    titles: dict[str, str] = {}
    names_by_form: dict[str, str] = {}
    async with spike.new_client() as client:
        await make_list(client, alice, LIST_RECURRING)
        for form in RECURRING_FORMS:
            uid = f"{GROUP_PREFIX}-wieder-{form}-{run}"
            title = f"{GROUP_PREFIX}wieder {form}"
            status = await put_task(
                client, alice, LIST_RECURRING, f"{uid}.ics", recurring_todo(uid, title, form)
            )
            note(f"SETUP PUT wiederkehrend form={form} status={status}")
            if status not in (201, 204):
                raise spike.RunFailed(f"PUT of the recurring form {form} answered {status}")
            titles[form] = title
            names_by_form[form] = f"{uid}.ics"
        report = await spike.dav_request(
            client,
            alice,
            "REPORT",
            list_url(base, target.alice, LIST_RECURRING),
            depth="1",
            body=tasks_client.build_todo_query(False),
        )
        prefiltered = {unquote(urlsplit(href).path.rsplit("/", 1)[-1]) for href in hrefs_of(report)}
    answers: dict[str, dict[str, Any]] = {}
    for status in ("open", "completed", "all"):
        clients = nc_clients(alice)
        async with clients.client:
            answers[status] = await tasks_tools.search_tasks(
                clients, list_name=LIST_RECURRING, status=status
            )
    for form in RECURRING_FORMS:
        hits = {
            status: [h for h in answer.get("tasks") or [] if h.get("summary") == titles[form]]
            for status, answer in answers.items()
        }
        every = hits["all"]
        recurring = bool(every) and all(hit.get("recurring") is True for hit in every)
        state = str(every[0].get("status")) if every else "fehlt"
        read_recurring, read_status = "fehlt", "fehlt"
        if every:
            clients = nc_clients(alice)
            async with clients.client:
                read = await tasks_tools.read_task(clients, task_id=str(every[0]["id"]))
            read_recurring = yes_no(read.get("recurring") is True)
            read_status = str(read.get("status"))
        note(
            f"WIEDER {target.name} form={form} "
            f"filter_offen={yes_no(names_by_form[form] in prefiltered)} "
            f"treffer_offen={len(hits['open'])} treffer_erledigt={len(hits['completed'])} "
            f"treffer_alle={len(every)} recurring={yes_no(recurring)} status={state} "
            f"lesen_recurring={read_recurring} lesen_status={read_status}"
        )


def cap_todo(run: str, number: int) -> tuple[str, str]:
    """Task ``number`` of the open series of the cap: never done, every second one due."""
    uid = f"{GROUP_PREFIX}-deckel-{run}-{number:04d}"
    extra = [
        (
            "DESCRIPTION:Eine offene Aufgabe der Messreihe mit einer Beschreibung von "
            "ueblicher Laenge\\, damit die Antwort nicht kuenstlich klein ausfaellt."
        ),
        f"CATEGORIES:{GROUP_PREFIX}",
    ]
    if number % 2 == 0:
        extra.append(f"DUE:202612{number % 28 + 1:02d}T100000Z")
    return f"{uid}.ics", spike.simple_todo(uid, f"{GROUP_PREFIX} deckel {number:04d}", extra)


async def fill_cap(creds: Credentials, target: Target, run: str, start: int, stop: int) -> None:
    """Serial PUTs with a retry on 5xx, then the rows counted in the database."""
    failed: list[str] = []
    repeated = 0
    started = time.perf_counter()
    async with spike.new_client() as client:
        for number in range(start, stop):
            name, text = cap_todo(run, number)
            status = 0
            for attempt in range(6):
                try:
                    status = await put_task(client, creds, LIST_CAP, name, text)
                except httpx.HTTPError:
                    status = 0
                if status in (201, 204) or (status == 412 and attempt):
                    status = 201
                    break
                if 0 < status < 500:
                    break
                repeated += 1
                await asyncio.sleep(0.5 * (attempt + 1))
            if status not in (201, 204):
                failed.append(f"{number}:{status}")
    seconds = time.perf_counter() - started
    if failed:
        raise spike.RunFailed(f"{len(failed)} PUT of the cap failed, first: {failed[:3]}")
    rows = spike.php(target.container, spike.PHP_COUNT_LIST_OBJECTS, creds.user, LIST_CAP).strip()
    note(
        f"AUFBAU {target.name} aufgaben={stop} neu={stop - start} erledigt=0 "
        f"mit_faelligkeit={(stop + 1) // 2} dauer_s={seconds:.0f} gleichzeitig=1 "
        f"wiederholte_put={repeated} GEGENPROBE datenbank_zeilen={rows} "
        f"gleich={yes_no(rows == str(stop))}"
    )
    if rows != str(stop):
        raise spike.RunFailed(f"the database holds {rows} objects of {LIST_CAP}")


async def timed_search(creds: Credentials, **kwargs: Any) -> tuple[float, dict[str, Any] | str]:
    """One call of ``search_tasks`` and its wall clock; a refusal comes back as its message."""
    clients = nc_clients(creds)
    async with clients.client:
        started = time.perf_counter()
        try:
            answer: dict[str, Any] | str = await tasks_tools.search_tasks(clients, **kwargs)
        except ToolError as exc:
            answer = exc.message
        return time.perf_counter() - started, answer


async def cap_steps(target: Target, env: Mapping[str, str], run: str) -> None:
    """Step ``deckel``: 600, then 2000 open tasks in one own list of alice."""
    alice = appapi_creds(env, target.base_url, target.alice)
    url = list_url(target.base_url, target.alice, LIST_CAP)
    containers = (target.container,)
    async with spike.new_client() as client:
        await make_list(client, alice, LIST_CAP)
    filled = 0
    worst = 0.0
    for size in CAP_SIZES:
        await fill_cap(alice, target, run, filled, size)
        filled = size
        found = await measure(
            alice, url, tasks_client.build_todo_query(False), containers, warm=3, runs=15
        )
        note(f"KOSTEN deckel-report aufgaben={size} impersonation=ja {found.line()}")
        budget = tasks_tools.PER_LIST_TIMEOUT
        tasks_tools.PER_LIST_TIMEOUT = MEASURING_BUDGET
        try:
            await timed_search(alice, list_name=LIST_CAP)
            calls = [await timed_search(alice, list_name=LIST_CAP) for _ in range(10)]
        finally:
            tasks_tools.PER_LIST_TIMEOUT = budget
        stats = spike.summarize([entry[0] for entry in calls])
        worst = max(worst, stats["max"])
        answered = all(isinstance(entry[1], dict) for entry in calls)
        note(
            f"KOSTEN deckel-aufruf aufgaben={size} median_ms={stats['median'] * 1000:.0f} "
            f"max_ms={stats['max'] * 1000:.0f} beantwortet={yes_no(answered)} "
            f"budget_waehrend_messung_s={MEASURING_BUDGET:g} (n={len(calls)})"
        )
        pages: list[dict[str, Any]] = []
        page_seconds: list[float] = []
        cursor: str | None = None
        refused = False
        while len(pages) <= 40:
            took, answer = await timed_search(alice, list_name=LIST_CAP, cursor=cursor)
            page_seconds.append(took)
            if isinstance(answer, str):
                refused = True
                break
            pages.append(answer)
            cursor = answer.get("next")
            if not cursor:
                break
        summary = paging_summary(pages)
        same_note = bool(pages) and pages[-1].get("note") == tasks_tools.SEARCH_CAP_NOTE
        note(
            f"DECKEL {target.name} aufgaben={size} seiten={summary.pages} "
            f"je_seite={summary.per_page} treffer={summary.hits} eindeutig={summary.unique} "
            f"letzte_note={yes_no(summary.last_note)} letzte_next={yes_no(summary.last_next)} "
            f"note_gleich={yes_no(same_note)} degraded={yes_no(summary.degraded or refused)} "
            f"max_seite_ms={max(page_seconds) * 1000:.0f} "
            f"median_seite_ms={statistics.median(page_seconds) * 1000:.0f} "
            f"budget_s={tasks_tools.PER_LIST_TIMEOUT:g}"
        )
    note(
        f"MESSWERT per_list_timeout_s={derive_budget(worst)} max_s={worst:.3f} "
        f"quelle={target.name}-impersonation"
    )


async def group_teardown(target: Target, env: Mapping[str, str]) -> None:
    """The group shares of this plan back; the lists fall with the loop of ``teardown``."""
    async with spike.new_client() as client:
        for user, uri in (
            (target.alice, LIST_GROUP_OUT),
            (target.bob, LIST_GROUP_RW),
            (target.bob, LIST_GROUP_RO),
        ):
            creds = appapi_creds(env, target.base_url, user)
            result = await spike.dav_request(
                client,
                creds,
                "POST",
                list_url(target.base_url, user, uri),
                body=group_share_body(GROUP_ID, writable=False, remove=True),
            )
            note(f"RUECKBAU gruppenfreigabe_entfernt liste={uri} status={result.status}")


def group_delete(target: Target) -> None:
    if group_members(target, GROUP_ID) is None:
        note("RUECKBAU gruppe entfaellt grund=nicht-vorhanden")
        return
    spike.occ(target.container, "group:delete", GROUP_ID, check=False)
    left = group_members(target, GROUP_ID) is not None
    note(f"RUECKBAU gruppe_geloescht noch_vorhanden={yes_no(left)}")


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
    if "gruppe" in steps and group_state(target, "vorher"):
        raise spike.RunFailed("the test group exists before the run; nothing was changed")
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
        if not series and not set(steps) <= set(GROUP_STEPS):
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
        if "hinaus" in steps or "subline" in steps:
            await gap(target, env, steps, run)
        if "gruppe" in steps:
            await group_steps(target, env, run)
        if "wieder" in steps:
            await recurring_steps(target, env, run)
        if "deckel" in steps:
            await cap_steps(target, env, run)
    except Exception as failure:
        note(f"BLOCK FAILED | live {target.name} | {type(failure).__name__}: {str(failure)[:300]}")
        raise
    finally:
        await teardown(target, env)
        if "gruppe" in steps:
            group_state(target, "nachher")
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

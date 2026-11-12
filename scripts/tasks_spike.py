"""The measuring run of phase 30: tasks and folders, measured before any product code.

Phases 31 to 33 rest on assumptions the research only read out of the server source. This
script asks a running Nextcloud instead. Its first question is the one phase 31 stands or
falls with: what does ``MKCOL`` on ``files/`` answer under AppAPI impersonation for a free
name? After that the status matrix of ``MKCOL`` (existing folder, existing file, missing
parent, invalid name, share without write permission, the sandbox root, an exhausted
quota), and folder creation inside a group folder with an ACL rule, with a negative test.

Run it against the Nextcloud 35 topology of ``compose.nc35.yml``::

    uv run --no-sync python scripts/tasks_spike.py --env-file <path to .env.nc35> \
        --block <name> --out <file>

``--block`` may be given several times; the blocks then run in the order named, in one
process, so the app passwords of the measuring accounts stay in memory and never touch a
file. The blocks are ``nc35-up`` (start the standing topology with ``docker start``, never
``up`` and never ``down``, and read the versions of record from the running instance),
``controls`` (baseline inventory, the measuring accounts, the three identity controls),
``mkcol`` (the first measuring point and the status matrix), ``groupfolder`` (group folder
with ACL, negative test, read-only external storage), ``modify`` (``PUT`` with ``If-Match``
under impersonation, a stale ETag, foreign properties, a list shared read-only, the server
side of recurring tasks and sub tasks), ``ui-prepare`` (the Tasks app and the account of the
browser session), ``ui-snapshot`` (every object of that account as a file, before and after
the browser session), ``ui-teardown`` (take all of that back and compare against the
baseline the kept run wrote), ``move`` (``MOVE`` between two task lists under impersonation,
the abort measurement of MESS-06 first, then a taken target, shared lists, a Deck calendar,
sub tasks, and ``DELETE`` with the restore out of the calendar trash bin),
``ui-evaluate-move`` (what the Tasks app did to sub tasks, read from the snapshots),
``delete-matrix`` (one throwaway instance per ``--nc-tag`` from ``compose.spike-tags.yml``:
deleting with the calendar trash bin on and off, for shared lists, the retention and the
pretest; it needs no environment file and ends with ``down -v``), ``delete-verdict`` (the
decision rule of E13 over the four raw files of the delete matrix, no Docker),
``discovery-matrix`` (one throwaway instance per ``--nc-tag``; ``--parts`` picks
``discovery``: a fresh account after its first login and a prepared one with every kind of
collection, ``query``: six ``calendar-query`` filters against the same filter applied here,
``provider``: the link of the search provider ``tasks``), ``cost`` (``--db sqlite`` or
``--db pg``: one list with 2000 tasks, the series of the modes ``offen`` and ``alle``,
``calendar-search`` once, and the proposal of the derivation rule), ``vtodo-create`` (a
create-only ``PUT`` of a VTODO under impersonation on nc35), ``fixtures`` (no Docker: the
objects the Tasks app wrote in plan 30-02 and the discovery answers as test fixtures),
``nc35-stop`` (``docker stop`` of the
same four containers) and ``secret-scan`` (the gate over every raw protocol of the phase
folder and the report before a commit). Whatever the measuring blocks created is taken back
in a ``finally`` and compared against the baseline, before ``nc35-stop`` runs.

Every block that uses a Nextcloud instance is a heavy run and starts behind a RAM gate: at
least 4 GB of free host memory and no foreign Nextcloud, database or connector container
next to it. The gate never stops a foreign container; it ends the run instead.

**No secret reaches a protocol.** The values of the environment file, every password and
token generated during a run and the name of the AppAPI authorization header are scanned
for before a protocol is written; a hit aborts the write. Passwords travel to ``occ``
through stdin only, never as an argument.
"""

import argparse
import asyncio
import base64
import hashlib
import io
import json
import math
import os
import re
import secrets
import statistics
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Coroutine, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
import icalendar
from lxml import etree

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import caldav, dav, ocs, xml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials
from mcp_connector.nextcloud.http import NoCookieJar

# --- the measured topology ------------------------------------------------------------------

NC_CONTAINER = "nc35-nc"
EXAPP_CONTAINER = "nc_app_mcp_connector"
NC35_CONTAINERS = ("nc35-nc", "nc35-harp", "nc35-caddy", "nc_app_mcp_connector")
BASE_URL = "http://127.0.0.1:8082"
DATA_DIR = "/var/www/html/data"

#: Everything this phase creates on nc35 carries this prefix; the rollback goes by it.
PREFIX = "spike30"
USER_A = "spike30a"
USER_B = "spike30b"
#: The account of the browser session of plan 30-02; it falls with ui-teardown.
UI_USER = "spike30ui"

#: The RAM rule of the phase: a heavy run needs this much free host memory.
MIN_FREE_HOST_GB = 4.0
#: A foreign container above this CPU share counts as another Docker run in progress.
IDLE_CPU_PERCENT = 10.0
#: Images that make a foreign container a run this one must not start next to.
_HEAVY_IMAGE = re.compile(r"nextcloud|postgres|mariadb|mysql|mcp_connector", re.IGNORECASE)

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE_DIR = REPO_ROOT / ".planning" / "phases" / "30-mess-spike-aufgaben-und-ordner"
RAW_DIR = PHASE_DIR / "raw"
REPORT_FILE = REPO_ROOT / "docs" / "spike-tasks.md"
#: The heading of the report below which every backtick quote has to stand in a raw file.
RAW_HEADING = "## 12. Rohausgaben"

#: The header name whose value is base64 of ``user:APP_SECRET``; never in a protocol.
APPAPI_HEADER = "AUTHORIZATION-APP-API"

#: Environment names whose values are secrets, whatever else the file carries.
_SECRET_NAME = re.compile(r"(SECRET|PASSWORD|TOKEN|_KEY)")

#: Response headers that never reach a protocol: credentials and session cookies.
_HIDDEN_HEADER = re.compile(r"authorization|cookie", re.IGNORECASE)

SABRE = "http://sabredav.org/ns"
DAV_FILES = "/remote.php/dav/files/"
TIMEOUT = httpx.Timeout(60.0)

#: Further blocks follow in plans 30-03 to 30-05.
BLOCKS = (
    "nc35-up",
    "controls",
    "mkcol",
    "groupfolder",
    "nachlauf",
    "modify",
    "ui-prepare",
    "ui-snapshot",
    "ui-log",
    "ui-evaluate",
    "inventory",
    "ui-teardown",
    "move",
    "ui-evaluate-move",
    "delete-matrix",
    "delete-verdict",
    "discovery-matrix",
    "cost",
    "vtodo-create",
    "fixtures",
    "nc35-stop",
    "secret-scan",
)

#: The rows of the group folder measurement (plan 30-01 task 3), in the order they run.
GF_KEYS = (
    "acl-rw",
    "acl-ro",
    "acl-ro-kontrolle-b",
    "acl-ro-nach-regelentzug",
    "gruppe-nur-lesen",
)

SHARES_PATH = "/apps/files_sharing/api/v1/shares"

GF_GROUP = f"{PREFIX}grp"
GF_READ_GROUP = f"{PREFIX}lesen"
GF_FOLDER = f"{PREFIX}gf"
GF_READ_FOLDER = f"{PREFIX}gf-lesen"
GF_DATA = f"{DATA_DIR}/__groupfolders"
EXT_MOUNT = f"{PREFIX}ext"
EXT_DIR = f"{DATA_DIR}/{EXT_MOUNT}"
#: The app config keys Nextcloud writes when an app is enabled for the first time. An app
#: that was never enabled before a run carries none of them, and gets none back.
APP_STATE_KEYS = ("installed_version", "enabled", "types")

#: One MKCOL from inside the ExApp container, the exact production way (http://caddy).
#: Fed to ``/app/.venv/bin/python -`` through stdin with the user and the path as arguments.
#: It reads APP_SECRET from its own environment and prints nothing but the status.
EXAPP_MKCOL_PROGRAM = r"""
import base64, os, sys
from urllib.parse import quote
import httpx

user, path = sys.argv[1], sys.argv[2]
token = base64.b64encode(("%s:%s" % (user, os.environ["APP_SECRET"])).encode()).decode()
headers = {
    "AA-VERSION": os.environ.get("AA_VERSION", ""),
    "EX-APP-ID": os.environ.get("APP_ID", ""),
    "EX-APP-VERSION": os.environ.get("APP_VERSION", ""),
    "AUTHORIZATION-APP-API": token,
}
base = os.environ.get("NEXTCLOUD_URL", "http://caddy").rstrip("/")
url = base + "/remote.php/dav/files/" + quote(user, safe="") + quote(path, safe="/")
response = httpx.request("MKCOL", url, headers=headers, timeout=60.0)
print(response.status_code)
"""

# --- PHP one shot snippets ------------------------------------------------------------------
# Handed to ``php --`` through stdin; nothing of them lands in the repository as a .php file.

_PHP_BOOT = "<?php\nrequire_once '/var/www/html/lib/base.php';\n"

#: Rows in the calendar trash bin: deleted calendar objects and deleted calendars.
PHP_COUNT_CALENDAR_TRASH = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
foreach (['calendarobjects', 'calendars'] as $table) {
    $qb = $db->getQueryBuilder();
    $qb->select($qb->func()->count('*', 'n'))->from($table)
        ->where($qb->expr()->isNotNull('deleted_at'));
    echo $qb->executeQuery()->fetchOne(), ' ';
}
echo "\n";
"""
)


class RunFailed(RuntimeError):
    """A step did not answer the way a measuring run needs it to."""


@dataclass(frozen=True, slots=True)
class DavResult:
    """One measured DAV request: status line, headers, body and wall clock."""

    status: int
    reason: str
    headers: tuple[tuple[str, str], ...]
    body: bytes
    seconds: float


# --- pure helpers: what a measured row means -------------------------------------------------


def mkcol_expectations() -> dict[str, int]:
    """The rows of the MKCOL status matrix with the status the research expects.

    The expectation is written down before the first measurement. A measured status that
    differs is a finding about Nextcloud, never a reason to change this table.
    """
    return {
        "frei": 201,
        "ordner-vorhanden": 405,
        "datei-vorhanden": 405,
        "eltern-fehlt": 409,
        "eltern-ist-datei": 409,
        "name-htaccess": 400,
        "name-backslash": 400,
        "name-ueberlang": 400,
        "share-ro": 403,
        "share-rw": 201,
        "root-vorhanden": 201,
        "root-fehlt": 409,
        "root-selbst": 405,
        "quota": 201,
    }


MKCOL_KEYS = tuple(mkcol_expectations())


def abort_mess01(status: int) -> bool:
    """The abort criterion of MESS-01: anything but a 201 for a free name triggers it."""
    return status != 201


def refused(status: int, *, created: bool) -> bool:
    """Whether a request counts as refused: a status outside 2xx and nothing created.

    A refusal status with a created folder is a contradiction between the answer and the
    file system. It is raised and never quietly counted as a refusal.
    """
    success = 200 <= status < 300
    if not success and created:
        raise ValueError(f"contradiction: status {status} says refused, but the folder was created")
    return not success


def same_status(left: Mapping[str, int], right: Mapping[str, int]) -> tuple[bool, list[str]]:
    """Compare two status series row by row; names every row that differs or is missing."""
    differing = [key for key in left if right.get(key) != left[key]]
    differing.extend(key for key in right if key not in left)
    return (not differing, differing)


def describe_error(body: bytes) -> str:
    """``s:exception`` and ``s:message`` of a Sabre ``d:error`` body, one line.

    An empty body gives an empty string: a 201 of MKCOL carries none, and a made up note
    in its place would read like something Nextcloud said.
    """
    if not body.strip():
        return ""
    try:
        root = xml.parse_root(body)
    except ToolError:
        return "(not XML)"
    parts = []
    for name in ("exception", "message"):
        element = root.find(f"{{{SABRE}}}{name}")
        if element is not None and (element.text or "").strip():
            parts.append(" ".join((element.text or "").split()))
    if parts:
        return " ".join(parts)[:400]
    return f"(root {root.tag})"


def raw_answer(
    status: int, reason: str, headers: Iterable[tuple[str, str]], body: bytes
) -> list[str]:
    """The raw answer of one request as indented protocol lines.

    Status line, the headers without any authorization or cookie line, and the body up to
    2000 characters. Session cookies are left out for the same reason as credentials: they
    are a way in for as long as the account exists.
    """
    lines = [f"    HTTP {status} {reason}".rstrip()]
    lines.extend(
        f"    {name}: {value}" for name, value in headers if not _HIDDEN_HEADER.search(name)
    )
    text = body.decode("utf-8", errors="replace").replace("\r", "")[:2000]
    if text.strip():
        lines.append("    (body)")
        lines.extend(f"    {line}" for line in text.splitlines() if line.strip())
    else:
        lines.append("    (no body)")
    return lines


# --- pure helpers: the RAM gate --------------------------------------------------------------


def free_host_memory_gb(probe: str) -> float:
    """Free host memory in GB from the probe output, which is in KiB.

    Reads the single number Windows prints for ``FreePhysicalMemory`` or the
    ``MemAvailable`` line of ``/proc/meminfo``. Anything unreadable is 0.0, so a broken
    probe keeps the gate shut instead of opening it.
    """
    available = re.search(r"^MemAvailable:\s*(\d+)", probe, re.MULTILINE)
    if available:
        return round(int(available[1]) / 1024**2, 2)
    for line in probe.splitlines():
        if line.strip().isdigit():
            return round(int(line.strip()) / 1024**2, 2)
    return 0.0


def foreign_runs(lines: Iterable[str], own: Iterable[str]) -> list[str]:
    """The running containers a heavy run must not start next to.

    Each line is ``<name> <image> <cpu>%`` (image and CPU may be missing). A container of
    ``own`` is skipped. A foreign one is reported when its image is a Nextcloud, a database
    or this connector, or when it is busy above ``IDLE_CPU_PERCENT``. A quiet foreign helper
    is listed by the gate, but not reported. An image shown as a bare id cannot be told
    apart by name; such a container is only caught by its CPU share.
    """
    mine = set(own)
    reported = []
    for line in lines:
        parts = line.split()
        if not parts or parts[0] in mine:
            continue
        image = parts[1] if len(parts) > 1 and not parts[1].endswith("%") else ""
        cpu = 0.0
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)%", parts[-1])
        if match:
            cpu = float(match[1])
        if _HEAVY_IMAGE.search(image) or cpu > IDLE_CPU_PERCENT:
            reported.append(line)
    return reported


def ram_gate_ok(free_gb: float, foreign: Sequence[str]) -> bool:
    """The gate itself: enough free host memory and no foreign run."""
    return free_gb >= MIN_FREE_HOST_GB and not foreign


# --- pure helpers: quotes of the report -------------------------------------------------------


def quoted_lines(report_text: str, heading: str = RAW_HEADING) -> list[str]:
    """Every protocol line the report quotes below ``heading``.

    A quote is an inline backtick span or a line of a fenced block, between ``heading`` and
    the next heading of the same level. Fenced lines are returned without their indent.
    """
    quotes: list[str] = []
    inside = False
    fenced = False
    for line in report_text.splitlines():
        if not fenced and line.startswith("## "):
            inside = line.strip() == heading
            continue
        if not inside:
            continue
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            if line.strip():
                quotes.append(line.strip())
            continue
        quotes.extend(span for span in re.findall(r"`([^`]+)`", line) if span.strip())
    return quotes


def missing_quotes(report_text: str, raw_texts: Mapping[str, str]) -> list[str]:
    """The quotes of the report that stand word for word in none of the raw files."""
    return [
        quote_
        for quote_ in quoted_lines(report_text)
        if not any(quote_ in text for text in raw_texts.values())
    ]


# --- pure helpers: iCalendar texts (plan 30-02) ----------------------------------------------


def unfold(text: str) -> str:
    """An iCalendar text with LF line ends and every folded line joined again (RFC 5545 3.1)."""
    plain = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", plain)


def property_name(line: str) -> str:
    """The name of a content line: everything before the first ``;``, ``:`` or blank."""
    return re.split(r"[;: ]", line.strip(), maxsplit=1)[0].upper()


def ics_line_set(text: str) -> set[tuple[str, str]]:
    """The content lines of an iCalendar text as ``(component path, unfolded line)``.

    Empty lines are dropped. ``BEGIN`` and ``END`` do not count as content, but every
    component path gets one line ``BEGIN x<n>`` with the number of components of that path:
    a set would otherwise hide that the second of two equal alarms went missing.
    """
    stack: list[str] = []
    lines: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for line in unfold(text).split("\n"):
        if not line.strip():
            continue
        name = property_name(line)
        if name == "BEGIN":
            stack.append(line.split(":", 1)[1].strip().upper())
            path = "/".join(stack)
            counts[path] = counts.get(path, 0) + 1
        elif name == "END":
            if stack:
                stack.pop()
        else:
            lines.add(("/".join(stack), line))
    lines.update((path, f"BEGIN x{count}") for path, count in counts.items())
    return lines


def _diff_name(path: str, line: str) -> str:
    """How a changed property is named: bare inside the VTODO, else with its component."""
    name = property_name(line)
    component = path.rsplit("/", 1)[-1]
    return name if component in ("VTODO", "VEVENT") else f"{component}.{name}"


def line_diff(before: str, after: str) -> tuple[list[str], list[str], set[str]]:
    """``(added, removed, changed names)`` between two iCalendar texts.

    A property that stands on both sides with a different line counts as changed and is
    named once; it shows up in neither of the two lists. Added and removed lines are
    written as ``<component path>:<line>``.
    """
    old, new = ics_line_set(before), ics_line_set(after)
    only_old, only_new = old - new, new - old
    keys_old = {(path, property_name(line)) for path, line in only_old}
    keys_new = {(path, property_name(line)) for path, line in only_new}
    both = keys_old & keys_new
    added = sorted(
        f"{path}:{line}" for path, line in only_new if (path, property_name(line)) not in both
    )
    removed = sorted(
        f"{path}:{line}" for path, line in only_old if (path, property_name(line)) not in both
    )
    changed = {
        _diff_name(path, line) for path, line in only_new if (path, property_name(line)) in both
    }
    return added, removed, changed


def preserved(
    before: str, after: str, allowed: Iterable[str] = ("SUMMARY",)
) -> tuple[bool, list[str]]:
    """Whether ``after`` differs from ``before`` in nothing but the ``allowed`` properties.

    The second value names every offence: ``entfernt <line>``, ``hinzu <line>`` and
    ``geaendert <name>``. This is the abort criterion of MESS-05 for foreign properties.
    """
    added, removed, changed = line_diff(before, after)
    permitted = {name.upper() for name in allowed}
    offences = [f"entfernt {line}" for line in removed]
    offences.extend(f"hinzu {line}" for line in added)
    offences.extend(f"geaendert {name}" for name in sorted(changed - permitted))
    return (not offences, offences)


def abort_if_match(
    *, status_current: int, etag_changed: bool, status_stale: int, unchanged_after_stale: bool
) -> tuple[bool, str]:
    """The abort criterion of MESS-05 for ``If-Match``: ``(triggered, reason)``.

    Not triggered only if the PUT with the current ETag answered 2xx, the ETag is another
    one afterwards, the PUT with the stale ETag answered exactly 412 and the object is
    unchanged after it.
    """
    reasons = []
    if not 200 <= status_current < 300:
        reasons.append(f"PUT mit der aktuellen ETag lieferte {status_current} statt 2xx")
    if not etag_changed:
        reasons.append("die ETag ist nach dem PUT dieselbe")
    if status_stale != 412:
        reasons.append(f"PUT mit der veralteten ETag lieferte {status_stale} statt 412")
    if not unchanged_after_stale:
        reasons.append("das Objekt ist nach dem abgelehnten PUT veraendert")
    return (bool(reasons), "; ".join(reasons) or "keiner")


def value_form(text: str) -> str:
    """The form of a time value: ``utc``, ``tzid``, ``floating``, ``date`` or ``other``.

    Takes a bare value or a whole content line; a ``TZID`` parameter wins over the value.
    """
    head, _, value = text.rpartition(":")
    if "TZID=" in head.upper():
        return "tzid"
    value = value.strip()
    if re.fullmatch(r"\d{8}T\d{6}Z", value):
        return "utc"
    if re.fullmatch(r"\d{8}T\d{6}", value):
        return "floating"
    if re.fullmatch(r"\d{8}", value):
        return "date"
    return "other"


def property_value(text: str, name: str) -> str:
    """The value of the first ``name`` line of an iCalendar text, unfolded; else empty."""
    match = re.search(rf"^{re.escape(name)}(?:;[^:\n]*)?:(.*)$", unfold(text), re.MULTILINE)
    return match[1].strip() if match else ""


def fold_line(line: str) -> str:
    """One content line folded at 75 octets, continuation lines starting with a space."""
    parts = []
    rest = line
    limit = 75
    while len(rest.encode()) > limit:
        parts.append(rest[:limit])
        rest = rest[limit:]
        limit = 74
    parts.append(rest)
    return "\r\n ".join(parts)


def _ics(lines: Iterable[str]) -> str:
    return "".join(f"{fold_line(line)}\r\n" for line in lines)


def simple_todo(uid: str, summary: str, extra: Iterable[str] = ()) -> str:
    """A plain VTODO with CRLF line ends; ``extra`` lines go in before the end of it."""
    return _ics(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//spike30//tasks_spike//EN",
            "BEGIN:VTODO",
            f"UID:{uid}",
            "DTSTAMP:20261111T100000Z",
            "CREATED:20261111T100000Z",
            "LAST-MODIFIED:20261111T100000Z",
            f"SUMMARY:{summary}",
            *extra,
            "END:VTODO",
            "END:VCALENDAR",
        ]
    )


def build_probe_todo(uid: str, summary: str) -> str:
    """The object of the second abort measurement: everything a modifying PUT has to keep.

    A VTIMEZONE, an alarm, three X- properties, an unknown parameter at SUMMARY, two
    categories, a class and a description long enough to be folded.
    """
    description = (
        "Eine Beschreibung mit mehr als fuenfundsiebzig Zeichen\\, damit die Zeile gefaltet "
        "werden muss und der Server sie beim Speichern nicht neu umbrechen darf."
    )
    return _ics(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//spike30//tasks_spike//EN",
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
            f"SUMMARY;X-SPIKE30-PARAM=abc:{summary}",
            f"DESCRIPTION:{description}",
            "DTSTART;TZID=Europe/Berlin:20261119T090000",
            "DUE;TZID=Europe/Berlin:20261120T101500",
            "CATEGORIES:spike30,wichtig",
            "CLASS:CONFIDENTIAL",
            "PRIORITY:1",
            "X-SPIKE30-FOO:bar",
            "X-APPLE-SORT-ORDER:123",
            "X-OC-HIDESUBTASKS:1",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:spike30 Erinnerung",
            "TRIGGER:-PT15M",
            "END:VALARM",
            "END:VTODO",
            "END:VCALENDAR",
        ]
    )


def set_summary(text: str, summary: str) -> str:
    """Replace the value of the SUMMARY line, textually; parameters and all else stay.

    On purpose not through icalendar: a parser would rewrite the whole object, and the
    measurement is about what the server does with a text it is handed.
    """
    changed, count = re.subn(
        r"(?m)^(SUMMARY(?:;[^:\r\n]*)?):[^\r\n]*", lambda match: f"{match[1]}:{summary}", text
    )
    if count != 1:
        raise ValueError(f"expected exactly one SUMMARY line, found {count}")
    return changed


def complete_todo(text: str, stamp: str) -> str:
    """Add the three lines of checking off right before ``END:VTODO``, textually."""
    lines = f"STATUS:COMPLETED\r\nPERCENT-COMPLETE:100\r\nCOMPLETED:{stamp}\r\n"
    if text.count("END:VTODO") != 1:
        raise ValueError("expected exactly one VTODO")
    return text.replace("END:VTODO", f"{lines}END:VTODO")


def short_etag(etag: str) -> str:
    """The first twelve characters of an ETag without quotes and weak marker; ``-`` if none."""
    bare = etag.strip().removeprefix("W/").strip('"')
    return bare[:12] or "-"


def etag_kind(etag: str) -> str:
    """``stark``, ``schwach`` or ``fehlt``."""
    if not etag.strip():
        return "fehlt"
    return "schwach" if etag.strip().startswith("W/") else "stark"


def calendar_collections(body: str | bytes) -> list[tuple[str, str, tuple[str, ...]]]:
    """Every calendar collection of a discovery answer: ``(uri, display name, components)``.

    Unlike ``caldav.parse_calendar_home`` this keeps task lists and shared collections; the
    inbox, the outbox, the trash bin and the home itself are no calendars and drop out.
    """
    root = xml.parse_root(body)
    found = []
    for response in root.findall(f"{{{xml.DAV}}}response"):
        if response.find(f".//{{{xml.DAV}}}resourcetype/{{{xml.CAL}}}calendar") is None:
            continue
        href = response.findtext(f"{{{xml.DAV}}}href") or ""
        uri = unquote(href.strip().rstrip("/").rsplit("/", 1)[-1])
        name = (response.findtext(f".//{{{xml.DAV}}}displayname") or "").strip()
        comps = tuple(
            str(comp.get("name"))
            for comp in response.iterfind(
                f".//{{{xml.CAL}}}supported-calendar-component-set/{{{xml.CAL}}}comp"
            )
        )
        found.append((uri, name or uri, comps))
    return found


#: The tasks the browser session of plan 30-02 creates in round A, by SUMMARY. The
#: recurring one is not in here: whether the Tasks app can create it is itself a finding.
UI_EXPECTED = (
    "s30 ganztag",
    "s30 uhrzeit",
    "s30 tags",
    "s30 notiz",
    "s30 unberuehrt",
    "s30 eltern-abhaken",
    "s30 kind-abhaken",
    "s30 eltern-umzug",
    "s30 kind-umzug",
    "s30 eltern-loeschen",
    "s30 kind-loeschen",
    "s30 abhaken",
    "s30 wieder-oeffnen",
    "s30 umzug-einzeln",
)
UI_RECURRING = "s30 wiederkehrend"


def missing_names(summaries: Iterable[str]) -> list[str]:
    """The expected task names a snapshot does not carry."""
    seen = set(summaries)
    return [name for name in UI_EXPECTED if name not in seen]


@dataclass(frozen=True, slots=True)
class SnapshotObject:
    """One calendar object of a snapshot of the browser session, bytes as the server sent."""

    collection: str
    name: str
    etag: str
    data: bytes
    trashed: bool


def write_snapshot(raw_dir: Path, label: str, objects: Sequence[SnapshotObject]) -> list[str]:
    """Write one file per object into ``raw_dir/ui-<label>/`` and return the file names.

    The file name is the object name; an object of the trash bin gets the prefix ``trash-``,
    and a second object of the same name gets its collection in front. Files of an earlier
    snapshot under the same label are removed first, so no stale object survives.
    """
    target = raw_dir / f"ui-{label}"
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob("*.ics"):
        stale.unlink()
    written: list[str] = []
    for item in objects:
        name = f"trash-{item.name}" if item.trashed else item.name
        if name in written:
            name = f"{item.collection}--{name}"
        (target / name).write_bytes(item.data)
        written.append(name)
    return written


def baseline_from_protocol(text: str) -> dict[str, str]:
    """The baseline of the last ``controls`` block of a raw protocol, from its own lines.

    A run that keeps its accounts for the browser session ends without a rollback. The
    teardown in a later process compares against the ``BASELINE-START`` lines that run
    wrote, so the baseline needs no file of its own.
    """
    baseline: dict[str, str] = {}
    for line in text.splitlines():
        if line.strip() == "== controls ==":
            baseline = {}
        elif line.startswith("BASELINE-START "):
            name, _, value = line.removeprefix("BASELINE-START ").partition("=")
            baseline[name] = value
    return baseline


def read_ui_file(path: Path) -> tuple[str, str, str]:
    """User, login password and base URL of the browser account, one per line.

    The file lives outside the repository; its second line is a secret and never printed.
    """
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    if len(lines) < 3 or not all(line.strip() for line in lines[:3]):
        raise RunFailed(f"{path.name} does not carry user, password and base URL; run ui-prepare")
    return lines[0].strip(), lines[1].strip(), lines[2].strip()


# --- protocol -------------------------------------------------------------------------------

_protocol: list[str] = []
_secrets: dict[str, str] = {}


def now_stamp() -> str:
    """The moment a line was measured, in UTC."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def note(line: str) -> None:
    """One protocol line, printed and kept for the scanned write at the end.

    A known secret value is replaced before the line is printed, so it reaches neither the
    console nor the list; the scan in ``write_protocol`` stays the second line of defence.
    """
    for name, value in _secrets.items():
        if value in line:
            line = line.replace(value, f"<redacted:{name}>")
    print(line)
    _protocol.append(line)


def section(title: str) -> None:
    """One heading per measured block, so the raw output can be quoted by the block."""
    note(f"\n== {title} ==")


def row(block: str, command: str, status: int | str, raw: str) -> str:
    """Timestamp | block | command | HTTP status | raw excerpt (at most 300 chars)."""
    excerpt = raw.replace("\r", "").replace("\n", " ")[:300]
    line = f"{now_stamp()} | {block} | {command} | HTTP {status} | {excerpt}"
    note(line)
    return line


def remember_secret(name: str, value: str) -> None:
    """Register a value the protocol must never contain."""
    if value.strip():
        _secrets[name] = value


def scan_for_secrets(texts: Mapping[str, str], secrets: Mapping[str, str]) -> list[str]:
    """Every line of ``texts`` that carries a secret value or the AppAPI header name.

    A finding names the text, the line number and the *name* of the secret, never the value,
    so the report of a hit is itself safe to print. Empty values are ignored: an unset
    variable would otherwise match every line.
    """
    wanted = [(name, value) for name, value in secrets.items() if value.strip()]
    findings: list[str] = []
    for label, text in texts.items():
        for number, line in enumerate(text.splitlines(), start=1):
            findings.extend(f"{label}:{number}: {name}" for name, value in wanted if value in line)
            if APPAPI_HEADER in line:
                findings.append(f"{label}:{number}: {APPAPI_HEADER}")
    return findings


def write_protocol(out: Path, header: str) -> None:
    """Append this run to ``out``, but only after the secret scan came back clean."""
    text = "\n".join([header, *_protocol]) + "\n"
    findings = scan_for_secrets({"protocol": text}, _secrets)
    if findings:
        raise RunFailed(f"protocol NOT written, secret values found at: {', '.join(findings)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# --- processes ------------------------------------------------------------------------------


def run(
    argv: Sequence[str],
    *,
    stdin: str | None = None,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> str:
    """One external command, no shell, fixed argument list, output as text.

    ``env`` is added to the inherited environment of this one child process only; that is
    how a secret reaches ``docker compose`` without ever being an argument.
    """
    child_env = None if env is None else {**os.environ, **env}
    finished = subprocess.run(  # noqa: S603 - a fixed argument list, never a shell
        list(argv),
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=child_env,
    )
    if check and finished.returncode != 0:
        raise RunFailed(
            f"{' '.join(argv[:6])} exited {finished.returncode}: "
            f"{(finished.stderr or finished.stdout).strip()[:400]}"
        )
    return ((finished.stdout or "") + (finished.stderr or "")).replace("\r", "")


def docker(*argv: str, stdin: str | None = None, check: bool = True) -> str:
    """One docker call. ``docker`` is on PATH by contract, as in every script here."""
    return run(["docker", *argv], stdin=stdin, check=check)


def occ(container: str, *argv: str, check: bool = True) -> str:
    """One ``occ`` call inside ``container``, output stripped of carriage returns."""
    return docker("exec", "-u", "www-data", container, "php", "occ", *argv, check=check).strip()


def occ_pw(container: str, password: str, *argv: str, check: bool = True) -> str:
    """One ``occ`` call that needs a password: it travels through stdin as ``OC_PASS``."""
    snippet = 'OC_PASS="$(cat)"; export OC_PASS; exec php occ "$@"'
    return docker(
        "exec",
        "-i",
        "-u",
        "www-data",
        container,
        "sh",
        "-c",
        snippet,
        "sh",
        *argv,
        stdin=password,
        check=check,
    ).strip()


def php(container: str, snippet: str, *args: str) -> str:
    """Run one PHP snippet through stdin; returns the last non-empty output line."""
    output = docker(
        "exec",
        "-i",
        "-u",
        "www-data",
        "-w",
        "/var/www/html",
        container,
        "php",
        "--",
        *args,
        stdin=snippet,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def shell_in(container: str, script: str, *args: str) -> str:
    """One fixed ``sh -c`` script inside ``container`` as www-data, arguments as ``$1``.."""
    return docker(
        "exec", "-u", "www-data", container, "sh", "-c", script, "sh", *args, check=False
    ).strip()


def dir_exists(path: str, container: str = NC_CONTAINER) -> bool:
    """Whether ``path`` is a directory in the file system of ``container``.

    This is the counter probe of every MKCOL row: it does not ask DAV, so an answer DAV got
    wrong cannot confirm itself.
    """
    return shell_in(container, 'if [ -d "$1" ]; then echo ja; else echo nein; fi', path) == "ja"


def container_now(container: str = NC_CONTAINER) -> str:
    """The clock of the container, which stamps the lines of its logs."""
    stamp = docker("exec", container, "date", "-u", "+%Y-%m-%dT%H:%M:%SZ", check=False).strip()
    return stamp or now_stamp()


def wait_for_install(container: str) -> None:
    """Poll ``occ status`` until the instance answers as installed (60 x 5 s)."""
    for attempt in range(1, 61):
        if "installed: true" in occ(container, "status", check=False):
            note(f"{container}: installed (attempt {attempt})")
            return
        time.sleep(5)
    raise RunFailed(f"{container} is still not installed after five minutes")


def read_env_file(path: Path) -> dict[str, str]:
    """The values ``scripts/bootstrap_exapp.sh`` wrote, as a mapping. Never printed."""
    if not path.is_file():
        raise RunFailed(f"{path} is not there; the owner runs scripts/bootstrap_exapp.sh --nc35")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def remember_env_secrets(env: Mapping[str, str]) -> None:
    """Every secret-like value of the environment file, plus the derived AppAPI tokens."""
    for name, value in env.items():
        if _SECRET_NAME.search(name):
            remember_secret(name, value)
    secret = env.get("APP_SECRET", "")
    for user in (env.get("NC_MCP_TEST_USER", ""), USER_A, USER_B, UI_USER):
        if user and secret:
            token = base64.b64encode(f"{user}:{secret}".encode()).decode()
            remember_secret(f"APPAPI_TOKEN_{user}", token)


def impersonation_lines(since: str, user: str, method: str) -> list[str]:
    """Lines of ``data/exapp_impersonation.log`` for ``user`` and ``method`` since ``since``.

    The server side proof of an impersonated request: Nextcloud itself names the account it
    resolved. ``since`` is a stamp of the container clock (``container_now``).
    """
    log = docker(
        "exec",
        NC_CONTAINER,
        "tail",
        "-n",
        "600",
        f"{DATA_DIR}/exapp_impersonation.log",
        check=False,
    )
    hits = [
        line.strip()
        for line in log.splitlines()
        if f'"method":"{method}"' in line and f'"user":"{user}"' in line
    ]
    return [line for line in hits if _log_time(line) >= since]


def _log_time(line: str) -> str:
    """The ISO timestamp of one JSON log line, normalised to ``YYYY-MM-DDTHH:MM:SSZ``."""
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return ""
    raw = str(record.get("time") or record.get("timestamp") or "")
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- the RAM gate ----------------------------------------------------------------------------


def host_memory_probe() -> str:
    """The free memory of the host in KiB, as the operating system reports it."""
    if sys.platform == "win32":
        return run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory",
            ],
            check=False,
        )
    meminfo = Path("/proc/meminfo")
    return meminfo.read_text(encoding="utf-8") if meminfo.is_file() else ""


def docker_stats() -> None:
    """Memory and CPU of every running container right now."""
    note(
        docker(
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}}  mem {{.MemUsage}}  cpu {{.CPUPerc}}",
            check=False,
        ).strip()
        or "(no running container)"
    )


def container_lines() -> list[str]:
    """Every running container as ``<name> <image> <cpu>%``, the input of ``foreign_runs``."""
    images = {}
    for line in docker("ps", "--format", "{{.Names}} {{.Image}}", check=False).splitlines():
        name, _, image = line.strip().partition(" ")
        if name:
            images[name] = image
    loads = {}
    stats = docker("stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}}", check=False)
    for line in stats.splitlines():
        name, _, load = line.strip().partition(" ")
        if name:
            loads[name] = load
    return [f"{name} {image} {loads.get(name, '')}".strip() for name, image in images.items()]


def ram_gate(own_containers: Iterable[str], *, enforce: bool = True) -> None:
    """The RAM rule of the phase, written into the protocol and enforced.

    Raises when the host has less than ``MIN_FREE_HOST_GB`` free or a foreign run is in
    progress. It never stops a foreign container. ``enforce=False`` only records: stopping
    the topology frees memory and must not be held back by the gate.
    """
    own = set(own_containers)
    free = free_host_memory_gb(host_memory_probe())
    enough = "ok" if free >= MIN_FREE_HOST_GB else "zu wenig"
    note(f"RAM frei_host_gb={free:.2f} schwelle={MIN_FREE_HOST_GB} ergebnis={enough}")
    docker_stats()
    lines = container_lines()
    foreign = foreign_runs(lines, own)
    for line in lines:
        if line.split()[0] not in own:
            note(f"FREMDER CONTAINER {line} gemeldet={'ja' if line in foreign else 'nein'}")
    if enforce and not ram_gate_ok(free, foreign):
        raise RunFailed(
            f"RAM gate shut: {free:.2f} GB free (needs {MIN_FREE_HOST_GB}), "
            f"foreign runs: {[line.split()[0] for line in foreign]}; nothing was stopped"
        )


# --- baseline and rollback -------------------------------------------------------------------


def _one_line(text: str) -> str:
    return " ".join(text.split())


def yes_no(value: bool) -> str:
    return "ja" if value else "nein"


def _json_or_text(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def app_list() -> tuple[dict[str, str], dict[str, str]]:
    """Enabled and disabled apps with their versions, read from the running instance."""
    data = _json_or_text(occ(NC_CONTAINER, "app:list", "--output=json", check=False))
    if not isinstance(data, dict):
        raise RunFailed("occ app:list --output=json returned no JSON object")
    enabled = data.get("enabled") or {}
    disabled = data.get("disabled") or {}
    return (
        {str(name): str(version) for name, version in dict(enabled).items()},
        {str(name): str(version) for name, version in dict(disabled).items()},
    )


def _count_entries(path: str, script: str) -> str:
    return shell_in(NC_CONTAINER, script, path)


def baseline_nc35(env: Mapping[str, str]) -> dict[str, str]:
    """The inventory of nc35 a run of this phase has to leave behind unchanged."""
    alice = env.get("NC_MCP_TEST_USER", "alice")
    bob = env.get("NC_MCP_TEST_USER2", "bob")
    enabled, disabled = app_list()
    calendar_trash = php(NC_CONTAINER, PHP_COUNT_CALENDAR_TRASH).split()
    return {
        "apps_an": json.dumps(enabled, sort_keys=True),
        "apps_aus": json.dumps(disabled, sort_keys=True),
        "nutzer": _one_line(occ(NC_CONTAINER, "user:list", "--output=json", check=False)),
        "gruppen": _one_line(occ(NC_CONTAINER, "group:list", "--output=json", check=False)),
        "dateien_alice": _count_entries(f"{DATA_DIR}/{alice}/files", 'find "$1" -type f | wc -l'),
        "papierkorb_alice": _count_entries(
            f"{DATA_DIR}/{alice}/files_trashbin/files",
            'if [ -d "$1" ]; then find "$1" -mindepth 1 -maxdepth 1 | wc -l; else echo 0; fi',
        ),
        "kalender_alice": _one_line(occ(NC_CONTAINER, "dav:list-calendars", alice, check=False)),
        "kalender_bob": _one_line(occ(NC_CONTAINER, "dav:list-calendars", bob, check=False)),
        "geloeschte_kalenderobjekte": calendar_trash[0] if calendar_trash else "?",
        "geloeschte_kalender": calendar_trash[1] if len(calendar_trash) > 1 else "?",
        "calendar_retention": _one_line(
            occ(NC_CONTAINER, "config:app:get", "dav", "calendarRetentionObligation", check=False)
        ),
        "quota_alice": _one_line(
            occ(NC_CONTAINER, "user:setting", alice, "files", "quota", check=False)
        ),
    }


def compare_baseline(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    """One line per field: before, after and whether both are the same."""
    lines = []
    for name, value in before.items():
        other = after.get(name, "")
        same = "ja" if value == other else "nein"
        lines.append(f"BASELINE {name} vorher={value} nachher={other} gleich={same}")
    return lines


def _names_with_prefix(command: str) -> list[str]:
    """The keys of an ``occ <command> --output=json`` object that carry the spike prefix."""
    data = _json_or_text(occ(NC_CONTAINER, command, "--output=json", check=False))
    if not isinstance(data, dict):
        return []
    return sorted(str(name) for name in data if str(name).startswith(PREFIX))


def remove_spike_objects() -> None:
    """Delete every group and every account of this phase; idempotent, driven by the prefix.

    Deleting an account takes its home, its shares and its app passwords with it.
    """
    for group in _names_with_prefix("group:list"):
        note(f"occ group:delete {group} -> {occ(NC_CONTAINER, 'group:delete', group, check=False)}")
    for user in _names_with_prefix("user:list"):
        note(f"occ user:delete {user} -> {occ(NC_CONTAINER, 'user:delete', user, check=False)}")


def restore_apps(before: Mapping[str, str]) -> None:
    """Bring the app set back: remove what this run installed, switch back what it toggled."""
    was_enabled = json.loads(before["apps_an"])
    was_disabled = json.loads(before["apps_aus"])
    enabled, disabled = app_list()
    for app in sorted(enabled):
        if app in was_enabled:
            continue
        note(f"occ app:disable {app} -> {occ(NC_CONTAINER, 'app:disable', app, check=False)}")
        if app not in was_disabled:
            note(f"occ app:remove {app} -> {occ(NC_CONTAINER, 'app:remove', app, check=False)}")
        if "(installed" not in was_disabled.get(app, ""):
            # Measured on 35.0.0: an app that was enabled once keeps three config values
            # after app:disable and even after app:remove, and occ app:list then shows it
            # as "(installed ...)". They did not exist before this run, so they go again.
            for key in APP_STATE_KEYS:
                occ(NC_CONTAINER, "config:app:delete", app, key, check=False)
            left = _one_line(occ(NC_CONTAINER, "config:list", app, check=False))
            note(f"occ config:app:delete {app} {' '.join(APP_STATE_KEYS)} -> config:list: {left}")
    for app in sorted(disabled):
        if app in was_enabled:
            note(f"occ app:enable {app} -> {occ(NC_CONTAINER, 'app:enable', app, check=False)}")
        elif app not in was_disabled:
            note(f"occ app:remove {app} -> {occ(NC_CONTAINER, 'app:remove', app, check=False)}")


def _mounts_with_prefix(command: str) -> list[str]:
    """The ids of the mounts ``occ <command> --output=json`` lists with the spike prefix."""
    data = _json_or_text(occ(NC_CONTAINER, command, "--output=json", check=False))
    entries = list(data.values()) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return []
    ids = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        # files_external writes mount_point, groupfolders 23 writes mountPoint (read from
        # the running instance; the first rollback of this plan missed the second spelling).
        raw_point = entry.get("mount_point", entry.get("mountPoint", ""))
        mount_point = str(raw_point).lstrip("/")
        mount_id = entry.get("mount_id", entry.get("id"))
        if mount_point.startswith(PREFIX) and mount_id is not None:
            ids.append(str(mount_id))
    return ids


def remove_spike_mounts(before: Mapping[str, str]) -> None:
    """Delete the external storages and group folders of this phase, and their directories."""
    enabled, _ = app_list()
    if "files_external" in enabled:
        for mount_id in _mounts_with_prefix("files_external:list"):
            gone = occ(NC_CONTAINER, "files_external:delete", "--yes", mount_id, check=False)
            note(f"occ files_external:delete --yes {mount_id} -> {_one_line(gone)[:160]}")
    removed = shell_in(NC_CONTAINER, 'rm -rf "$1" && echo entfernt', EXT_DIR)
    note(f"rm -rf {EXT_DIR} -> {removed}")
    if "groupfolders" in enabled:
        for folder_id in _mounts_with_prefix("groupfolders:list"):
            gone = occ(NC_CONTAINER, "groupfolders:delete", "--force", folder_id, check=False)
            note(f"occ groupfolders:delete --force {folder_id} -> {_one_line(gone)[:160]}")
        listed = occ(NC_CONTAINER, "groupfolders:list", "--output=json", check=False)
        note(f"occ groupfolders:list --output=json (nach dem Loeschen) -> {_one_line(listed)}")
    known = {**json.loads(before["apps_an"]), **json.loads(before["apps_aus"])}
    if "groupfolders" not in known:
        # The app did not exist before this run, so nothing else can own this directory.
        files = shell_in(
            NC_CONTAINER,
            'if [ -d "$1" ]; then find "$1" -type f | wc -l; else echo fehlt; fi',
            GF_DATA,
        )
        removed = shell_in(NC_CONTAINER, 'rm -rf "$1" && echo entfernt', GF_DATA)
        note(f"rm -rf {GF_DATA} (Dateien darin vorher: {files}) -> {removed}")


def rollback_nc35(before: Mapping[str, str], env: Mapping[str, str]) -> None:
    """Take everything back and compare against the baseline, as the last protocol lines."""
    section("rueckbau")
    remove_spike_mounts(before)
    remove_spike_objects()
    restore_apps(before)
    left = _names_with_prefix("user:list") + _names_with_prefix("group:list")
    note(f"RUECKBAU reste_mit_praefix_{PREFIX}={left or 'keine'}")
    enabled, disabled = app_list()
    note(f"RUECKBAU occ user:list -> {_one_line(occ(NC_CONTAINER, 'user:list', check=False))}")
    note(
        f"RUECKBAU occ app:list groupfolders_vorhanden="
        f"{yes_no('groupfolders' in enabled or 'groupfolders' in disabled)} "
        f"files_external_an={yes_no('files_external' in enabled)}"
    )
    boards = php(NC_CONTAINER, PHP_COUNT_DECK_BOARDS, PREFIX)
    note(f"RUECKBAU deck_boards_mit_praefix_{PREFIX}={boards} (Tabelle deck_boards, per PHP)")
    for line in compare_baseline(before, baseline_nc35(env)):
        note(line)


# --- DAV and credentials ---------------------------------------------------------------------


@dataclass
class Session:
    """What the blocks of one process share: the client, the accounts, the baseline."""

    env: Mapping[str, str]
    client: httpx.AsyncClient
    before: dict[str, str] | None = None
    app_passwords: dict[str, str] = field(default_factory=dict)

    def basic(self, user: str) -> Credentials:
        """App password credentials of one measuring account."""
        if user not in self.app_passwords:
            raise RunFailed(f"no app password for {user} in this process; run --block controls")
        return Credentials(
            base_url=_base_url(self.env),
            user=user,
            secret=self.app_passwords[user],
            mode=MODE_BASIC,
        )

    def appapi(self, user: str, secret: str | None = None) -> Credentials:
        """AppAPI impersonation credentials: ``APP_SECRET`` is the only secret in play."""
        return Credentials(
            base_url=_base_url(self.env),
            user=user,
            secret=self.env["APP_SECRET"] if secret is None else secret,
            mode=MODE_APPAPI,
            app_id=self.env.get("APP_ID", ""),
            app_version=self.env.get("APP_VERSION", ""),
            aa_version=self.env.get("AA_VERSION", ""),
        )


def _base_url(env: Mapping[str, str]) -> str:
    return (env.get("NC_MCP_URL") or BASE_URL).rstrip("/")


def new_client() -> httpx.AsyncClient:
    """One client per process, with the production posture of ``nextcloud/http.py``.

    ``NoCookieJar`` is load bearing: this run speaks as two accounts and as their
    impersonated selves through one client, and a session cookie Nextcloud set for one of
    them would carry the next request under the wrong identity (measured in phase 25).
    """
    return httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT, cookies=NoCookieJar())


def propfind_body(props: Sequence[str]) -> bytes:
    """A PROPFIND body for the given Clark-notation property names, built with lxml."""
    root = etree.Element(f"{{{xml.DAV}}}propfind", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    for name in props:
        etree.SubElement(prop, name)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def home_url(creds: Credentials, sub: str = "/", *, owner: str | None = None) -> str:
    """The WebDAV URL below a home, by default the one of the account of ``creds``.

    Deliberately not ``dav.files_url``: that one maps the path into ``NC_MCP_FILES_ROOT``,
    and this run measures Nextcloud. Only the sandbox rows of the matrix use ``files_url``.
    """
    home = quote(owner or creds.user, safe="")
    return f"{creds.base_url}{DAV_FILES}{home}{quote(sub, safe='/')}"


async def dav_request(
    client: httpx.AsyncClient,
    creds: Credentials,
    method: str,
    url: str,
    *,
    depth: str | None = None,
    body: bytes | None = None,
    content_type: str | None = "application/xml; charset=utf-8",
    extra_headers: Mapping[str, str] | None = None,
) -> DavResult:
    """One DAV request, timed; a 4xx is returned, never raised.

    Without ``body`` no body and no ``Content-Type`` is sent, which is how ``MKCOL`` goes
    out in every row of this phase.
    """
    headers: dict[str, str] = {}
    if depth is not None:
        headers["Depth"] = depth
    if body is not None and content_type is not None:
        headers["Content-Type"] = content_type
    headers.update(extra_headers or {})
    started = time.perf_counter()
    response = await client.request(method, url, headers=headers, content=body, auth=creds.auth())
    seconds = time.perf_counter() - started
    return DavResult(
        status=response.status_code,
        reason=response.reason_phrase,
        headers=tuple(response.headers.items()),
        body=response.content,
        seconds=seconds,
    )


async def guarded(name: str, work: Coroutine[Any, Any, None]) -> None:
    """One sub block, and its failure reported as a measured outcome instead of an abort."""
    try:
        await work
    except Exception as failure:
        note(f"BLOCK FAILED | {name} | {type(failure).__name__}: {str(failure)[:300]}")


def new_app_password(container: str, user: str, password: str, secret_name: str) -> str:
    """An app password for ``user`` (login password via stdin), remembered as a secret."""
    raw = occ_pw(
        container, password, "user:auth-tokens:add", user, "--password-from-env", "--name", PREFIX
    )
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    # stdout and stderr arrive joined; a warning on stderr would otherwise pose as the
    # token, so the line after the "app password:" label wins over the last line.
    labels = [n for n, line in enumerate(lines) if line == "app password:"]
    if labels and labels[-1] + 1 < len(lines):
        token = lines[labels[-1] + 1]
    else:
        token = lines[-1] if lines else ""
    if len(token) < 20 or " " in token:
        # Only lines with a space are shown: a token never has one, so none can leak here.
        prose = [line[:80] for line in lines if " " in line]
        raise RunFailed(f"no app password could be parsed for {user}; output: {prose}")
    remember_secret(secret_name, token)
    note(f"occ user:auth-tokens:add {user} --password-from-env --name {PREFIX} (token kept)")
    return token


# --- blocks ---------------------------------------------------------------------------------


def versions_of_record() -> None:
    """The versions this run measured against, read from the running instance."""
    status = occ(NC_CONTAINER, "status", check=False)
    note(status)
    match = re.search(r"versionstring:\s*(\S+)", status)
    note(f"VERSION OF RECORD {match[1] if match else '(not readable)'}")
    note(f"dbtype: {occ(NC_CONTAINER, 'config:system:get', 'dbtype', check=False)}")
    enabled, _ = app_list()
    note(f"APP app_api version={enabled.get('app_api', '(not enabled)')} (occ app:list)")
    note("occ app_api:app:list:")
    for line in occ(NC_CONTAINER, "app_api:app:list", check=False).splitlines():
        note(f"  {line}")


def block_nc35_up() -> None:
    """Start the standing nc35 topology with ``docker start`` and name what is running."""
    section("nc35-up")
    ram_gate(NC35_CONTAINERS)
    known = set(docker("ps", "-a", "--format", "{{.Names}}", check=False).split())
    missing = [name for name in NC35_CONTAINERS if name not in known]
    if any(name != EXAPP_CONTAINER for name in missing):
        raise RunFailed(
            f"containers {missing} do not exist; see .planning/STATE.md, section "
            "'ExApp-Topologie'. This script never runs compose up or a bootstrap."
        )
    note(f"docker start {NC_CONTAINER} -> {docker('start', NC_CONTAINER).strip()}")
    wait_for_install(NC_CONTAINER)
    for name in ("nc35-harp", "nc35-caddy"):
        note(f"docker start {name} -> {docker('start', name).strip()}")
    started = docker("start", EXAPP_CONTAINER, check=False).strip()
    note(f"docker start {EXAPP_CONTAINER} -> {started[:200]}")

    deadline = time.monotonic() + 120
    status = 0
    while time.monotonic() < deadline:
        try:
            status = httpx.get(f"{BASE_URL}/status.php", timeout=10.0).status_code
        except httpx.HTTPError:
            status = 0
        if status == 200:
            break
        time.sleep(3)
    note(f"GET {BASE_URL}/status.php -> HTTP {status}")
    if status != 200:
        raise RunFailed(f"{BASE_URL}/status.php did not answer 200 within 120 s (last {status})")

    versions_of_record()
    for name in NC35_CONTAINERS:
        state = docker(
            "inspect",
            "--format",
            "{{.State.Running}} StartedAt={{.State.StartedAt}} image={{.Config.Image}}",
            name,
            check=False,
        ).strip()
        note(f"CONTAINER {name} laeuft={state}")
    running = docker("inspect", "--format", "{{.State.Running}}", EXAPP_CONTAINER, check=False)
    note(f"EXAPP-CONTAINER laeuft={'ja' if running.strip() == 'true' else 'nein'}")


def block_nc35_stop() -> None:
    """Stop the four containers again; the topology itself stays, volumes included."""
    section("nc35-stop")
    ram_gate(NC35_CONTAINERS, enforce=False)
    for name in NC35_CONTAINERS:
        stopped = docker("stop", name, check=False).strip()
        running = docker("inspect", "--format", "{{.State.Running}}", name, check=False).strip()
        note(f"docker stop {name} -> {stopped[:120]} | laeuft={running}")


async def block_controls(session: Session) -> None:
    """Baseline, the measuring accounts, and the identity controls every later row needs."""
    section("controls")
    ram_gate(NC35_CONTAINERS)
    leftovers = _names_with_prefix("user:list") + _names_with_prefix("group:list")
    if leftovers:
        note(f"RESTE eines frueheren Laufs vor der Baseline entfernt: {leftovers}")
        remove_spike_objects()
    session.before = baseline_nc35(session.env)
    for name, value in session.before.items():
        note(f"BASELINE-START {name}={value}")

    for user in (USER_A, USER_B):
        password = secrets.token_urlsafe(24)
        remember_secret(f"PASSWORD_{user}", password)
        added = occ_pw(NC_CONTAINER, password, "user:add", "--password-from-env", user)
        note(f"occ user:add --password-from-env {user} (password via stdin) -> {added[:120]}")
        token = new_app_password(NC_CONTAINER, user, password, f"APP_PASSWORD_{user}")
        session.app_passwords[user] = token
        # The home of a fresh account is set up by its first authenticated DAV request; it
        # is asked for here, so no measured row depends on that side effect.
        creds = session.basic(user)
        home = await dav_request(
            session.client,
            creds,
            "PROPFIND",
            home_url(creds, "/"),
            depth="0",
            body=propfind_body([f"{{{xml.OC}}}fileid"]),
        )
        row("controls", f"PROPFIND Depth 0 home of {user} (app password)", home.status, "home")

    since = container_now()
    await asyncio.sleep(1)
    creds = session.appapi(USER_A)
    response = await ocs.ocs_get(session.client, creds, "/cloud/user")
    if response.status_code == 401:
        row("controls", f"a: GET /ocs/v2.php/cloud/user (AppAPI as {USER_A})", 401, "refused")
        raise RunFailed("APP_SECRET stale, ask the owner before bootstrap_exapp.sh")
    data = ocs.parse_ocs(response, what="the impersonated user")
    seen = str(data.get("id") or "") if isinstance(data, dict) else ""
    row(
        "controls",
        f"a: GET /ocs/v2.php/cloud/user (AppAPI as {USER_A})",
        response.status_code,
        f"id={seen} erwartet={USER_A} gleich={'ja' if seen == USER_A else 'nein'}",
    )
    if seen != USER_A:
        raise RunFailed(f"control a: cloud/user names {seen!r}, not {USER_A}")
    wrong = await ocs.ocs_get(session.client, session.appapi(USER_A, "0" * 64), "/cloud/user")
    row(
        "controls",
        f"b: GET /ocs/v2.php/cloud/user (AppAPI as {USER_A}, wrong APP_SECRET)",
        wrong.status_code,
        f"abgelehnt={'ja' if wrong.status_code != 200 else 'nein'}",
    )
    if wrong.status_code == 200:
        raise RunFailed("control b: a wrong APP_SECRET was accepted")
    lines = impersonation_lines(since, USER_A, "GET")
    note(
        f"KONTROLLE c: exapp_impersonation.log, GET-Zeilen von {USER_A} seit {since}: {len(lines)}"
    )
    for line in lines[-2:]:
        note(f"  {line[:300]}")


@dataclass(frozen=True, slots=True)
class Measured:
    """One MKCOL with its counter probe in the file system."""

    result: DavResult
    created: bool

    @property
    def status(self) -> int:
        return self.result.status


def auth_label(creds: Credentials) -> str:
    """How a row names its authentication: ``appapi`` or ``basic``."""
    return "appapi" if creds.mode == MODE_APPAPI else "basic"


def fs_home(user: str, sub: str) -> str:
    """The path of ``sub`` below the home of ``user`` in the data directory."""
    return f"{DATA_DIR}/{user}/files{sub}"


async def measure_mkcol(session: Session, creds: Credentials, url: str, fs_path: str) -> Measured:
    """One ``MKCOL`` without body and without ``Content-Type``, and what the disk says.

    ``created`` means: the folder is in the file system after the call and was not there
    before it. A folder that already existed is not counted as created.
    """
    before = dir_exists(fs_path)
    result = await dav_request(session.client, creds, "MKCOL", url)
    return Measured(result, dir_exists(fs_path) and not before)


def mkcol_line(key: str, creds: Credentials, measured: Measured) -> str:
    """``MKCOL <key> auth=.. status=.. angelegt=.. erwartet=.. | exception message``."""
    return (
        f"{now_stamp()} | MKCOL {key} auth={auth_label(creds)} status={measured.status} "
        f"angelegt={yes_no(measured.created)} erwartet={mkcol_expectations()[key]} "
        f"| {describe_error(measured.result.body)[:300]}"
    )


def note_raw(result: DavResult) -> None:
    for line in raw_answer(result.status, result.reason, result.headers, result.body):
        note(line)


async def setup_request(
    session: Session, creds: Credentials, method: str, sub: str, body: bytes | None = None
) -> int:
    """A preparing request, written as a ``SETUP`` line so it is never read as a measured row."""
    result = await dav_request(
        session.client,
        creds,
        method,
        home_url(creds, sub),
        body=body,
        content_type="application/octet-stream",
    )
    note(
        f"{now_stamp()} | SETUP {method} {sub} nutzer={creds.user} "
        f"auth={auth_label(creds)} status={result.status}"
    )
    return result.status


@dataclass
class Matrix:
    """The state of one mkcol block: the names of this run and the measured statuses."""

    session: Session
    stamp: str
    base: str = f"/{PREFIX}"
    statuses: dict[str, dict[str, int]] = field(default_factory=lambda: {"appapi": {}, "basic": {}})

    async def row(
        self,
        key: str,
        creds: Credentials,
        sub: str,
        *,
        url: str | None = None,
        fs: str | None = None,
    ) -> Measured:
        """Measure one row of the matrix and write its line and its raw answer."""
        measured = await measure_mkcol(
            self.session,
            creds,
            url or home_url(creds, sub),
            fs or fs_home(USER_A, sub),
        )
        self.statuses[auth_label(creds)][key] = measured.status
        note(mkcol_line(key, creds, measured))
        note_raw(measured.result)
        return measured


def production_way(user: str, sub: str) -> None:
    """The same MKCOL from inside the ExApp container against ``http://caddy``."""
    running = docker("inspect", "--format", "{{.State.Running}}", EXAPP_CONTAINER, check=False)
    if running.strip() != "true":
        note(f"PRODUKTIONSWEG ungemessen grund=ExApp-Container {EXAPP_CONTAINER} laeuft nicht")
        return
    output = docker(
        "exec",
        "-i",
        EXAPP_CONTAINER,
        "/app/.venv/bin/python",
        "-",
        user,
        sub,
        stdin=EXAPP_MKCOL_PROGRAM,
        check=False,
    ).strip()
    last = output.splitlines()[-1].strip() if output else ""
    if not last.isdigit():
        note(f"PRODUKTIONSWEG ungemessen grund=keine Statuszeile aus dem Container: {last[:200]}")
        return
    created = dir_exists(fs_home(user, sub))
    note(
        f"{now_stamp()} | PRODUKTIONSWEG MKCOL status={last} angelegt={yes_no(created)} "
        f"nutzer={user} pfad={sub} (aus {EXAPP_CONTAINER} gegen http://caddy)"
    )


async def mkcol_first_point(matrix: Matrix, free: str) -> bool:
    """M1.1, the first measuring point of the phase; returns whether MESS-01 aborts."""
    session = matrix.session
    creds = session.appapi(USER_A)
    resourcetype = propfind_body([f"{{{xml.DAV}}}resourcetype"])
    pre = await dav_request(
        session.client, creds, "PROPFIND", home_url(creds, free), depth="0", body=resourcetype
    )
    note(
        f"{now_stamp()} | KONTROLLE vorher PROPFIND Depth 0 {free} auth=appapi "
        f"nutzer={USER_A} status={pre.status} erwartet=404"
    )
    since = container_now()
    await asyncio.sleep(1)
    measured = await measure_mkcol(session, creds, home_url(creds, free), fs_home(USER_A, free))
    matrix.statuses["appapi"]["frei"] = measured.status
    note(mkcol_line("frei", creds, measured))
    aborted = abort_mess01(measured.status)
    note(f"ABBRUCHKRITERIUM MESS-01 ausgeloest={yes_no(aborted)} status={measured.status}")
    note(f"  Aufruf: MKCOL {DAV_FILES}{USER_A}{free} ohne Body, nutzer={USER_A}, auth=appapi")
    note_raw(measured.result)
    present = dir_exists(fs_home(USER_A, free))
    note(f"DATEISYSTEM frei vorhanden={yes_no(present)} pfad={fs_home(USER_A, free)}")
    after = await dav_request(
        session.client, creds, "PROPFIND", home_url(creds, free), depth="0", body=resourcetype
    )
    note(
        f"{now_stamp()} | KONTROLLE nachher PROPFIND Depth 0 {free} auth=appapi "
        f"nutzer={USER_A} status={after.status}"
    )
    lines = impersonation_lines(since, USER_A, "MKCOL")
    note(f"KONTROLLE exapp_impersonation.log, MKCOL-Zeilen von {USER_A} seit {since}: {len(lines)}")
    for line in lines[-3:]:
        note(f"  {line[:400]}")

    wrong_sub = f"{free}-falsches-secret"
    wrong = await measure_mkcol(
        session,
        session.appapi(USER_A, "0" * 64),
        home_url(creds, wrong_sub),
        fs_home(USER_A, wrong_sub),
    )
    note(
        f"{now_stamp()} | GEGENPROBE falsches-secret MKCOL {wrong_sub} nutzer={USER_A} "
        f"status={wrong.status} angelegt={yes_no(wrong.created)} "
        f"| {describe_error(wrong.result.body)[:300]}"
    )
    foreign_sub = f"/{PREFIX}-fremd"
    foreign = await measure_mkcol(
        session,
        creds,
        home_url(creds, foreign_sub, owner=USER_B),
        fs_home(USER_B, foreign_sub),
    )
    note(
        f"{now_stamp()} | GEGENPROBE fremdes-home MKCOL {DAV_FILES}{USER_B}{foreign_sub} "
        f"nutzer={USER_A} status={foreign.status} angelegt={yes_no(foreign.created)} "
        f"| {describe_error(foreign.result.body)[:300]}"
    )
    production_way(USER_A, f"{free}-produktionsweg")
    return aborted


async def mkcol_matrix(matrix: Matrix, creds: Credentials, free_dir: str) -> None:
    """M1.2: the rows that need nothing but the own home, for one way of authenticating."""
    auth = auth_label(creds)
    base = matrix.base
    if "frei" not in matrix.statuses[auth]:
        await matrix.row("frei", creds, free_dir)
    await matrix.row("ordner-vorhanden", creds, free_dir)
    file_sub = f"{base}/datei-{auth}.txt"
    await setup_request(matrix.session, creds, "PUT", file_sub, b"spike30\n")
    await matrix.row("datei-vorhanden", creds, file_sub)
    await matrix.row("eltern-fehlt", creds, f"{base}/fehlt-{auth}/kind")
    await matrix.row("eltern-ist-datei", creds, f"{file_sub}/kind")
    await matrix.row("name-htaccess", creds, f"{free_dir}/.htaccess")
    note(
        "  name-backslash: das Segment ist bs%5Cx und wird roh an die URL gehaengt, weil "
        "dav.safe_path einen Backslash vor jeder Anfrage ablehnt"
    )
    await matrix.row(
        "name-backslash",
        creds,
        f"{free_dir}/bs%5Cx",
        url=f"{home_url(creds, free_dir)}/bs%5Cx",
        fs=fs_home(USER_A, f"{free_dir}/bs\\x"),
    )
    note("  name-ueberlang: das Segment besteht aus 300 mal x")
    await matrix.row("name-ueberlang", creds, f"{free_dir}/{'x' * 300}")


async def mkcol_shares(matrix: Matrix) -> None:
    """M1.3: a share without and a share with create permission, from USER_B to USER_A."""
    session = matrix.session
    owner = session.basic(USER_B)
    targets: dict[str, tuple[str, str]] = {}
    for key, permissions in (("share-ro", 1), ("share-rw", 15)):
        folder = f"/{PREFIX}-{key}"
        await setup_request(session, owner, "MKCOL", folder)
        response = await ocs.ocs_post(
            session.client,
            owner,
            SHARES_PATH,
            {"path": folder, "shareType": 0, "shareWith": USER_A, "permissions": permissions},
        )
        data = ocs.parse_ocs(response, what=f"the share of {folder}")
        share_id = str(data.get("id", "")) if isinstance(data, dict) else ""
        target = str(data.get("file_target", "")) if isinstance(data, dict) else ""
        note(
            f"{now_stamp()} | SETUP POST shares path={folder} shareWith={USER_A} "
            f"permissions={permissions} nutzer={USER_B} status={response.status_code} "
            f"id={share_id} file_target={target}"
        )
        if not target:
            raise RunFailed(f"the share of {folder} returned no file_target")
        targets[key] = (folder, target)
    for creds in (session.appapi(USER_A), session.basic(USER_A)):
        for key, (folder, target) in targets.items():
            name = f"neu-{auth_label(creds)}"
            await matrix.row(key, creds, f"{target}/{name}", fs=fs_home(USER_B, f"{folder}/{name}"))
    creds = session.appapi(USER_A)
    for folder, target in targets.values():
        answer = await dav_request(
            session.client,
            creds,
            "PROPFIND",
            home_url(creds, target),
            depth="0",
            body=propfind_body([f"{{{xml.OC}}}permissions"]),
        )
        permissions = ""
        if answer.status == 207:
            entries = xml.parse_multistatus(answer.body)
            permissions = entries[0][1].get(f"{{{xml.OC}}}permissions", "") if entries else ""
        note(
            f"{now_stamp()} | KONTROLLE oc:permissions {target} (Ordner {folder} von {USER_B}) "
            f"aus Sicht von {USER_A} auth=appapi status={answer.status} "
            f"permissions={permissions or '(leer)'}"
        )


def files_url_with_root(creds: Credentials, root: str, virtual: str) -> str:
    """The URL ``dav.files_url`` builds for ``virtual`` while ``NC_MCP_FILES_ROOT`` is ``root``.

    ``config.files_root`` reads the process environment on every call, so the variable is
    set for exactly this one call and put back afterwards.
    """
    previous = os.environ.get(config.ENV_FILES_ROOT)
    os.environ[config.ENV_FILES_ROOT] = root
    try:
        return dav.files_url(creds, virtual)
    finally:
        if previous is None:
            del os.environ[config.ENV_FILES_ROOT]
        else:
            os.environ[config.ENV_FILES_ROOT] = previous


async def mkcol_root(matrix: Matrix) -> None:
    """M1.4: the three sandbox rows, measured at the URL the connector itself would build."""
    session = matrix.session
    root = f"{matrix.base}/root"
    await setup_request(session, session.basic(USER_A), "MKCOL", root)
    for creds in (session.appapi(USER_A), session.basic(USER_A)):
        auth = auth_label(creds)
        cases = (
            ("root-vorhanden", root, f"/unter-{auth}"),
            ("root-fehlt", f"{root}-fehlt", f"/unter-{auth}"),
            ("root-selbst", root, "/"),
        )
        for key, env_root, virtual in cases:
            url = files_url_with_root(creds, env_root, virtual)
            real = env_root if virtual == "/" else f"{env_root}{virtual}"
            note(
                f"FILES_ROOT {key} auth={auth} {config.ENV_FILES_ROOT}={env_root} "
                f"pfad={virtual} url={url[len(creds.base_url) :]}"
            )
            await matrix.row(key, creds, real, url=url)


async def mkcol_quota(matrix: Matrix) -> None:
    """M1.5: MKCOL with an exhausted quota; a PUT shows first that the quota bites."""
    session = matrix.session
    setting = ("user:setting", USER_A, "files", "quota")
    previous = occ(NC_CONTAINER, *setting, check=False)
    was_set = "does not exist" not in previous
    note(f"occ user:setting {USER_A} files quota (vorher) -> {previous}")
    note(f"occ user:setting {USER_A} files quota '1 KB' -> {occ(NC_CONTAINER, *setting, '1 KB')}")
    try:
        for creds in (session.appapi(USER_A), session.basic(USER_A)):
            auth = auth_label(creds)
            probe = f"{matrix.base}/quota-probe-{auth}.bin"
            put = await dav_request(
                session.client,
                creds,
                "PUT",
                home_url(creds, probe),
                body=b"x" * 2048,
                content_type="application/octet-stream",
            )
            note(
                f"{now_stamp()} | KONTROLLE kontingent PUT 2048 Bytes {probe} auth={auth} "
                f"nutzer={USER_A} status={put.status} wirkt={yes_no(put.status == 507)} "
                f"| {describe_error(put.body)[:300]}"
            )
            if put.status != 507:
                note(
                    f"M1.5 ungemessen auth={auth} grund=die Positivkontrolle lieferte "
                    f"{put.status} statt 507, das Kontingent wirkt nicht"
                )
            await matrix.row("quota", creds, f"{matrix.base}/quota-{auth}")
    finally:
        if was_set:
            restored = occ(NC_CONTAINER, *setting, previous, check=False)
        else:
            restored = occ(NC_CONTAINER, *setting, "--delete", check=False)
        note(f"occ user:setting {USER_A} files quota zurueckgesetzt -> {restored or 'ok'}")


async def block_mkcol(session: Session) -> None:
    """MESS-01: the first measuring point, then the status matrix under both ways in."""
    section("mkcol")
    ram_gate(NC35_CONTAINERS)
    matrix = Matrix(session=session, stamp=datetime.now(UTC).strftime("%H%M%S"))
    basic = session.basic(USER_A)
    appapi = session.appapi(USER_A)

    # The base folder is set up by a PUT that creates its parent, so that the very first
    # MKCOL of this phase is the measured one and not a preparing one.
    setup = await session.client.put(
        home_url(basic, f"{matrix.base}/setup.txt"),
        content=b"spike30\n",
        headers={"X-NC-WebDAV-Auto-Mkcol": "1"},
        auth=basic.auth(),
    )
    base_ready = dir_exists(fs_home(USER_A, matrix.base))
    note(
        f"{now_stamp()} | SETUP PUT {matrix.base}/setup.txt mit X-NC-WebDAV-Auto-Mkcol "
        f"nutzer={USER_A} auth=basic status={setup.status_code} "
        f"basisordner_vorhanden={yes_no(base_ready)}"
    )
    free = f"{matrix.base}/frei-{matrix.stamp}" if base_ready else f"/{PREFIX}-frei-{matrix.stamp}"
    aborted = await mkcol_first_point(matrix, free)
    if not base_ready:
        await setup_request(session, basic, "MKCOL", matrix.base)
    if aborted:
        note(
            "ABBRUCHKRITERIUM MESS-01 ist ausgeloest: die Matrix laeuft als Diagnose weiter, "
            "Phase 31 wird nicht geplant, der Befund geht an den Owner"
        )

    free_basic = f"{matrix.base}/frei-basic-{matrix.stamp}"
    await guarded("mkcol matrix appapi", mkcol_matrix(matrix, appapi, free))
    await guarded("mkcol matrix basic", mkcol_matrix(matrix, basic, free_basic))
    await guarded("mkcol shares", mkcol_shares(matrix))
    await guarded("mkcol root", mkcol_root(matrix))
    await guarded("mkcol quota", mkcol_quota(matrix))

    section("mkcol summary")
    expected = mkcol_expectations()
    for key in MKCOL_KEYS:
        seen_appapi = matrix.statuses["appapi"].get(key, "fehlt")
        seen_basic = matrix.statuses["basic"].get(key, "fehlt")
        differs = [
            auth for auth in ("appapi", "basic") if matrix.statuses[auth].get(key) != expected[key]
        ]
        note(
            f"MKCOL ZEILE {key} appapi={seen_appapi} basic={seen_basic} "
            f"erwartet={expected[key]} abweichung_von_erwartung={','.join(differs) or 'keine'}"
        )
    same, differing = same_status(matrix.statuses["appapi"], matrix.statuses["basic"])
    note(f"MKCOL GLEICH appapi_basic={yes_no(same)} abweichend={differing or 'keine'}")


def note_help(*commands: str) -> None:
    """The help text of ``occ`` commands, raw: the commands below are built after it."""
    for command in commands:
        note(f"HILFE occ {command} --help:")
        for line in occ(NC_CONTAINER, command, "--help", check=False).splitlines():
            if line.strip():
                note(f"    {line.rstrip()}")


def occ_noted(*argv: str) -> str:
    """One ``occ`` call written into the protocol with its answer."""
    answer = occ(NC_CONTAINER, *argv, check=False)
    note(f"occ {' '.join(argv)} -> {_one_line(answer)[:300] or '(keine Ausgabe)'}")
    return answer


@dataclass
class GroupFolders:
    """The state of one groupfolder block: ids, the data path and the measured rows."""

    session: Session
    folder_id: str = ""
    read_folder_id: str = ""
    data_path: str = ""
    rows: dict[tuple[str, str], Measured] = field(default_factory=dict)

    async def row(self, key: str, creds: Credentials, sub: str, fs_path: str) -> Measured:
        """Measure one row and write ``GF <key> auth=.. nutzer=.. status=.. angelegt=..``."""
        measured = await measure_mkcol(self.session, creds, home_url(creds, sub), fs_path)
        self.rows[(key, auth_label(creds))] = measured
        note(
            f"{now_stamp()} | GF {key} auth={auth_label(creds)} nutzer={creds.user} "
            f"status={measured.status} angelegt={yes_no(measured.created)} "
            f"| {describe_error(measured.result.body)[:300]}"
        )
        note(f"  Aufruf: MKCOL {DAV_FILES}{creds.user}{sub} ohne Body, Dateisystem: {fs_path}")
        note_raw(measured.result)
        return measured


def install_groupfolders() -> None:
    """Install or enable the app and name its version from the running instance."""
    enabled, disabled = app_list()
    installed_before = "groupfolders" in enabled or "groupfolders" in disabled
    if "groupfolders" not in enabled:
        command = "app:enable" if "groupfolders" in disabled else "app:install"
        occ_noted(command, "groupfolders")
    enabled, _ = app_list()
    version = enabled.get("groupfolders", "")
    if not version:
        note(
            "GRUPPENORDNER ungemessen grund=die App groupfolders liess sich in dieser Instanz "
            "nicht einschalten, Rohausgabe in der Zeile darueber"
        )
        raise RunFailed(
            "groupfolders could not be installed; E12 demands the measurement, so the "
            "finding goes to the owner instead of guessing another instance"
        )
    note(
        f"GRUPPENORDNER version={version} installiert_vorher={yes_no(installed_before)} "
        "(gelesen mit occ app:list --output=json)"
    )


async def groupfolder_setup(state: GroupFolders) -> None:
    """Groups, two group folders, ACL switched on; the command forms follow the help texts."""
    note_help(
        "groupfolders:create",
        "groupfolders:group",
        "groupfolders:permissions",
        "groupfolders:delete",
    )
    occ_noted("group:add", GF_GROUP)
    occ_noted("group:adduser", GF_GROUP, USER_A)
    occ_noted("group:adduser", GF_GROUP, USER_B)
    occ_noted("group:add", GF_READ_GROUP)
    occ_noted("group:adduser", GF_READ_GROUP, USER_A)
    for name, attribute in ((GF_FOLDER, "folder_id"), (GF_READ_FOLDER, "read_folder_id")):
        created = occ_noted("groupfolders:create", name)
        digits = re.findall(r"\d+", created)
        if not digits:
            raise RunFailed(f"groupfolders:create {name} returned no id")
        setattr(state, attribute, digits[-1])
    occ_noted("groupfolders:group", state.folder_id, GF_GROUP, "read", "write", "share", "delete")
    occ_noted("groupfolders:permissions", state.folder_id, "--enable")
    occ_noted("groupfolders:group", state.read_folder_id, GF_READ_GROUP)
    note(f"occ groupfolders:list -> {_one_line(occ(NC_CONTAINER, 'groupfolders:list'))[:900]}")

    creds = state.session.appapi(USER_A)
    listing = await dav_request(
        state.session.client,
        creds,
        "PROPFIND",
        home_url(creds, "/"),
        depth="1",
        body=propfind_body([f"{{{xml.OC}}}permissions"]),
    )
    hrefs = [href for href, _ in xml.parse_multistatus(listing.body)] if listing.body else []
    seen = {
        name: any(href.rstrip("/").endswith(f"/{name}") for href in hrefs)
        for name in (GF_FOLDER, GF_READ_FOLDER)
    }
    note(
        f"{now_stamp()} | KONTROLLE PROPFIND Depth 1 home auth=appapi nutzer={USER_A} "
        f"status={listing.status} {GF_FOLDER}_sichtbar={yes_no(seen[GF_FOLDER])} "
        f"{GF_READ_FOLDER}_sichtbar={yes_no(seen[GF_READ_FOLDER])}"
    )

    # The two sub folders are created by the impersonated account itself. Where they land
    # in the data directory is read from the disk afterwards, not assumed.
    for name in ("acl-rw", "acl-ro"):
        made = await dav_request(
            state.session.client, creds, "MKCOL", home_url(creds, f"/{GF_FOLDER}/{name}")
        )
        note(
            f"{now_stamp()} | GF-AUFBAU MKCOL /{GF_FOLDER}/{name} auth=appapi nutzer={USER_A} "
            f"status={made.status} | {describe_error(made.body)[:300]}"
        )
    found = shell_in(NC_CONTAINER, 'find "$1" -maxdepth 4 -type d | sort', GF_DATA)
    note(f"DATEISYSTEM ls {GF_DATA} (find -maxdepth 4 -type d):")
    for line in found.splitlines():
        note(f"    {line}")
    hits = [line for line in found.splitlines() if line.endswith("/acl-rw")]
    if len(hits) != 1:
        raise RunFailed(f"acl-rw was found {len(hits)} times below {GF_DATA}, expected once")
    state.data_path = hits[0][: -len("/acl-rw")]
    note(f"DATEISYSTEM gruppenordner {GF_FOLDER} id={state.folder_id} pfad={state.data_path}")


async def groupfolder_acl_probe(state: GroupFolders) -> None:
    """Counter probe: what DAV itself says about the two sub folders, as USER_A."""
    creds = state.session.appapi(USER_A)
    props = [f"{{{xml.OC}}}permissions", f"{{{xml.NC}}}acl-enabled", f"{{{xml.NC}}}acl-list"]
    for name in ("acl-rw", "acl-ro"):
        answer = await dav_request(
            state.session.client,
            creds,
            "PROPFIND",
            home_url(creds, f"/{GF_FOLDER}/{name}"),
            depth="0",
            body=propfind_body(props),
        )
        permissions = ""
        if answer.status == 207:
            entries = xml.parse_multistatus(answer.body)
            permissions = entries[0][1].get(f"{{{xml.OC}}}permissions", "") if entries else ""
        note(
            f"{now_stamp()} | KONTROLLE oc:permissions /{GF_FOLDER}/{name} aus Sicht von "
            f"{USER_A} auth=appapi status={answer.status} permissions={permissions or '(leer)'}"
        )
        note(f"  PROPFIND-Antwort (oc:permissions, nc:acl-enabled, nc:acl-list) fuer {name}:")
        for line in answer.body.decode("utf-8", errors="replace")[:2500].splitlines():
            if line.strip():
                note(f"    {line.rstrip()}")


async def groupfolder_rows(state: GroupFolders) -> None:
    """M2.1 to M2.3: with write permission, with the ACL rule, two controls, read-only group."""
    session = state.session
    rule = ("groupfolders:permissions", state.folder_id, "--user", USER_A, "acl-ro")
    occ_noted(*rule, "--", "+read", "-write", "-create", "-delete")
    occ_noted("groupfolders:permissions", state.folder_id, "--user", USER_A, "--test", "acl-ro")
    occ_noted("groupfolders:permissions", state.folder_id)
    await groupfolder_acl_probe(state)

    base = f"/{GF_FOLDER}"
    for user_a, user_b in (
        (session.appapi(USER_A), session.appapi(USER_B)),
        (session.basic(USER_A), session.basic(USER_B)),
    ):
        auth = auth_label(user_a)
        await state.row(
            "acl-rw", user_a, f"{base}/acl-rw/neu-{auth}", f"{state.data_path}/acl-rw/neu-{auth}"
        )
        await state.row(
            "acl-ro", user_a, f"{base}/acl-ro/neu-{auth}", f"{state.data_path}/acl-ro/neu-{auth}"
        )
        await state.row(
            "acl-ro-kontrolle-b",
            user_b,
            f"{base}/acl-ro/neu-b-{auth}",
            f"{state.data_path}/acl-ro/neu-b-{auth}",
        )

    occ_noted(*rule, "clear")
    occ_noted("groupfolders:permissions", state.folder_id)
    for creds in (session.appapi(USER_A), session.basic(USER_A)):
        auth = auth_label(creds)
        await state.row(
            "acl-ro-nach-regelentzug",
            creds,
            f"{base}/acl-ro/nach-{auth}",
            f"{state.data_path}/acl-ro/nach-{auth}",
        )

    read_path = shell_in(
        NC_CONTAINER, 'find "$1" -maxdepth 2 -type d | sort', f"{GF_DATA}/{state.read_folder_id}"
    )
    note(f"DATEISYSTEM {GF_READ_FOLDER} id={state.read_folder_id}: {_one_line(read_path)}")
    read_base = state.data_path.replace(f"/{state.folder_id}", f"/{state.read_folder_id}", 1)
    for creds in (session.appapi(USER_A), session.basic(USER_A)):
        auth = auth_label(creds)
        await state.row(
            "gruppe-nur-lesen", creds, f"/{GF_READ_FOLDER}/neu-{auth}", f"{read_base}/neu-{auth}"
        )


def groupfolder_verdict(state: GroupFolders) -> None:
    """The closing lines of E12, decided by ``refused`` and never by the status alone."""
    for key in GF_KEYS:
        seen = {
            auth: state.rows[(key, auth)].status if (key, auth) in state.rows else "fehlt"
            for auth in ("appapi", "basic")
        }
        note(f"GF ZEILE {key} appapi={seen['appapi']} basic={seen['basic']}")
    positive = state.rows.get(("acl-rw", "appapi"))
    negative = state.rows.get(("acl-ro", "appapi"))
    if positive is None or negative is None:
        note("E12 ungemessen grund=die Zeilen acl-rw oder acl-ro fehlen, siehe BLOCK FAILED")
        return
    try:
        was_refused = refused(negative.status, created=negative.created)
    except ValueError as contradiction:
        note(f"E12 NEGATIVTEST widerspruch: {contradiction}")
        return
    other = state.rows.get(("acl-ro", "basic"))
    a8 = "belegt" if was_refused and negative.status == 403 else "widerlegt"
    note(
        f"E12 NEGATIVTEST abgelehnt={yes_no(was_refused)} status={negative.status} a8_403={a8} "
        f"(auth=appapi nutzer={USER_A}; auth=basic status={other.status if other else 'fehlt'})"
    )
    note(
        f"E12 POSITIV angelegt={yes_no(positive.created)} status={positive.status} "
        f"(auth=appapi nutzer={USER_A})"
    )
    controls = {
        key: state.rows[(key, "appapi")].status if (key, "appapi") in state.rows else "fehlt"
        for key in ("acl-ro-kontrolle-b", "acl-ro-nach-regelentzug")
    }
    note(
        f"E12 KONTROLLEN kontrolle_b={controls['acl-ro-kontrolle-b']} "
        f"nach_regelentzug={controls['acl-ro-nach-regelentzug']} (auth=appapi)"
    )


async def external_storage(session: Session) -> None:
    """M2.4: a local external storage for USER_A, first read-only, then writable."""
    section("externer-speicher")
    enabled, _ = app_list()
    note(f"EXTERN files_external an_vorher={yes_no('files_external' in enabled)}")
    if "files_external" not in enabled:
        occ_noted("app:enable", "files_external")
    note_help("files_external:create", "files_external:option", "files_external:applicable")
    made = shell_in(NC_CONTAINER, 'mkdir -p "$1" && echo angelegt', EXT_DIR)
    note(f"mkdir -p {EXT_DIR} (als www-data) -> {made}")
    created = occ_noted(
        "files_external:create", EXT_MOUNT, "local", "null::null", "-c", f"datadir={EXT_DIR}"
    )
    match = re.search(r"id (\d+)", created)
    if not match:
        note(
            "EXTERN ungemessen grund=files_external:create lieferte keine Mount-Id, "
            "Rohausgabe in der Zeile darueber"
        )
        return
    mount_id = match[1]
    occ_noted("files_external:applicable", mount_id, "--add-user", USER_A)
    occ_noted("files_external:option", mount_id, "readonly", "true")
    occ_noted("files_external:list")

    measured: dict[tuple[str, str], Measured] = {}
    for mode in ("ro", "rw"):
        if mode == "rw":
            occ_noted("files_external:option", mount_id, "readonly", "false")
        for creds in (session.appapi(USER_A), session.basic(USER_A)):
            auth = auth_label(creds)
            sub = f"/{EXT_MOUNT}/neu-{mode}-{auth}"
            result = await measure_mkcol(
                session, creds, home_url(creds, sub), f"{EXT_DIR}/neu-{mode}-{auth}"
            )
            measured[(mode, auth)] = result
            note(
                f"{now_stamp()} | EXTERN {mode} auth={auth} nutzer={USER_A} "
                f"status={result.status} angelegt={yes_no(result.created)} "
                f"| {describe_error(result.result.body)[:300]}"
            )
            note(f"  Aufruf: MKCOL {DAV_FILES}{USER_A}{sub} ohne Body")
            note_raw(result.result)
        if mode == "ro":
            creds = session.appapi(USER_A)
            answer = await dav_request(
                session.client,
                creds,
                "PROPFIND",
                home_url(creds, f"/{EXT_MOUNT}"),
                depth="0",
                body=propfind_body([f"{{{xml.OC}}}permissions"]),
            )
            entries = xml.parse_multistatus(answer.body) if answer.status == 207 else []
            permissions = entries[0][1].get(f"{{{xml.OC}}}permissions", "") if entries else ""
            note(
                f"{now_stamp()} | KONTROLLE oc:permissions /{EXT_MOUNT} (readonly=true) aus "
                f"Sicht von {USER_A} auth=appapi status={answer.status} "
                f"permissions={permissions or '(leer)'}"
            )

    read_only, writable = measured[("ro", "appapi")], measured[("rw", "appapi")]
    if writable.status != 201:
        note(
            f"EXTERN ungemessen grund=die Positivkontrolle ohne readonly lieferte "
            f"{writable.status} statt 201, der Speicher traegt also gar nicht"
        )
        return
    try:
        was_refused = refused(read_only.status, created=read_only.created)
    except ValueError as contradiction:
        note(f"EXTERN widerspruch: {contradiction}")
        return
    a8 = "belegt" if was_refused and read_only.status == 403 else "widerlegt"
    note(
        f"EXTERN A8 abgelehnt={yes_no(was_refused)} status={read_only.status} a8_403={a8} "
        f"positivkontrolle_rw={writable.status} (auth=appapi nutzer={USER_A})"
    )


async def block_groupfolder(session: Session) -> None:
    """MESS-02: group folder with ACL and negative test, then read-only external storage."""
    section("groupfolder")
    ram_gate(NC35_CONTAINERS)
    install_groupfolders()
    state = GroupFolders(session=session)
    await groupfolder_setup(state)
    await guarded("groupfolder rows", groupfolder_rows(state))
    section("groupfolder summary")
    groupfolder_verdict(state)
    await guarded("externer-speicher", external_storage(session))


async def block_nachlauf(session: Session) -> None:
    """A follow-up rollback: group folders an earlier run left behind in the database.

    Removing the app does not remove its folders: their rows survive and come back with the
    next installation. This block takes a baseline, installs the app again and shows what is
    left; the rollback in the ``finally`` then deletes the folders, removes the app and
    compares against the baseline.
    """
    section("nachlauf")
    ram_gate(NC35_CONTAINERS)
    session.before = baseline_nc35(session.env)
    for name, value in session.before.items():
        note(f"BASELINE-START {name}={value}")
    note(
        "NACHLAUF grund=der Rueckbau des Laufs davor fand die Gruppenordner nicht (das Feld "
        "heisst mountPoint, nicht mount_point); sie blieben in der Datenbank, die App war weg"
    )
    install_groupfolders()
    listed = occ(NC_CONTAINER, "groupfolders:list", "--output=json", check=False)
    note(f"occ groupfolders:list --output=json (vor dem Loeschen) -> {_one_line(listed)}")


# --- plan 30-02: modifying access (MESS-05) ---------------------------------------------------

LIST_A = f"{PREFIX}-a"
LIST_B = f"{PREFIX}-b"
LIST_RO = f"{PREFIX}-b-ro"
LIST_RW = f"{PREFIX}-b-rw"
ICS_TYPE = "text/calendar; charset=utf-8"
OC_SHARE_NS = "http://owncloud.org/ns"
PROBE_X_LINE = "X-SPIKE30-FOO:bar\r\n"
#: Blocks whose accounts and lists a later call still needs; ui-teardown takes them back.
KEEP_BLOCKS = ("modify", "ui-prepare")

#: Row count, sha256 and length of the column calendardata for one object name.
PHP_OBJECT_HASH = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->select('calendardata')->from('calendarobjects')
    ->where($qb->expr()->eq('uri', $qb->createNamedParameter($argv[1])))
    ->andWhere($qb->expr()->isNull('deleted_at'));
$out = [];
foreach ($qb->executeQuery()->fetchAll() as $row) {
    $data = $row['calendardata'];
    if (is_resource($data)) {
        $data = stream_get_contents($data);
    }
    $out[] = hash('sha256', (string)$data) . ':' . strlen((string)$data);
}
echo count($out), ' ', implode(',', $out), "\n";
"""
)

#: The substitute way if MKCALENDAR is refused under impersonation: the backend itself.
PHP_CREATE_TASK_LIST = (
    _PHP_BOOT
    + r"""
$backend = \OCP\Server::get(\OCA\DAV\CalDAV\CalDavBackend::class);
$id = $backend->createCalendar('principals/users/' . $argv[1], $argv[2], [
    '{DAV:}displayname' => $argv[2],
    '{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set'
        => new \Sabre\CalDAV\Xml\Property\SupportedCalendarComponentSet(['VTODO']),
]);
echo 'angelegt id=', $id, "\n";
"""
)


def sha_of(text: str | bytes) -> str:
    """``<sha256>:<length>`` of a body, the form ``PHP_OBJECT_HASH`` prints per row."""
    data = text.encode() if isinstance(text, str) else text
    return f"{hashlib.sha256(data).hexdigest()}:{len(data)}"


def db_hash(object_name: str) -> str:
    """``<rows> <sha256>:<length>`` of the stored object, read from the database.

    The counter probe of every modifying row: it does not ask DAV.
    """
    return php(NC_CONTAINER, PHP_OBJECT_HASH, object_name)


def header_of(result: DavResult, name: str) -> str:
    """One response header by name, empty if the answer does not carry it."""
    return next((value for key, value in result.headers if key.lower() == name.lower()), "")


def mkcalendar_body(name: str, components: Sequence[str] = ("VTODO",)) -> bytes:
    """A MKCALENDAR body; by default a list that takes VTODO only, as the Tasks app has it."""
    root = etree.Element(f"{{{xml.CAL}}}mkcalendar", nsmap={"d": xml.DAV, "c": xml.CAL})
    prop = etree.SubElement(etree.SubElement(root, f"{{{xml.DAV}}}set"), f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}displayname").text = name
    comps = etree.SubElement(prop, f"{{{xml.CAL}}}supported-calendar-component-set")
    for component in components:
        etree.SubElement(comps, f"{{{xml.CAL}}}comp", name=component)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def share_body(user: str, *, writable: bool) -> bytes:
    """The share document of the calendar sharing plugin (namespace owncloud.org/ns)."""
    root = etree.Element(f"{{{OC_SHARE_NS}}}share", nsmap={"d": xml.DAV, "o": OC_SHARE_NS})
    entry = etree.SubElement(root, f"{{{OC_SHARE_NS}}}set")
    etree.SubElement(entry, f"{{{xml.DAV}}}href").text = f"principal:principals/users/{user}"
    if writable:
        etree.SubElement(entry, f"{{{OC_SHARE_NS}}}read-write")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def report_body(kind: str, hrefs: Sequence[str] = ()) -> bytes:
    """``calendar-multiget`` for ``hrefs`` or ``calendar-query`` without a narrowing filter."""
    root = etree.Element(f"{{{xml.CAL}}}{kind}", nsmap={"d": xml.DAV, "c": xml.CAL})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}getetag")
    etree.SubElement(prop, f"{{{xml.CAL}}}calendar-data")
    if kind == "calendar-query":
        scope = etree.SubElement(root, f"{{{xml.CAL}}}filter")
        etree.SubElement(scope, f"{{{xml.CAL}}}comp-filter", name="VCALENDAR")
    for href in hrefs:
        etree.SubElement(root, f"{{{xml.DAV}}}href").text = href
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def plain(text: str) -> str:
    """A calendar text with LF line ends and no outer blanks, to compare two ways of reading."""
    return text.replace("\r\n", "\n").strip()


async def put_object(
    session: Session,
    creds: Credentials,
    url: str,
    text: str,
    *,
    if_match: str | None = None,
    if_none_match: str | None = None,
) -> DavResult:
    """One PUT of a calendar object with exactly the conditional headers given."""
    headers = {}
    if if_match is not None:
        headers["If-Match"] = if_match
    if if_none_match is not None:
        headers["If-None-Match"] = if_none_match
    return await dav_request(
        session.client,
        creds,
        "PUT",
        url,
        body=text.encode(),
        content_type=ICS_TYPE,
        extra_headers=headers,
    )


async def get_object(session: Session, creds: Credentials, url: str) -> tuple[DavResult, str, str]:
    """One GET of a calendar object: the answer, its ETag header and the body as text."""
    result = await dav_request(session.client, creds, "GET", url)
    return result, header_of(result, "etag"), result.body.decode("utf-8", errors="replace")


async def report(
    session: Session, creds: Credentials, uri: str, body: bytes, *, url: str | None = None
) -> tuple[int, list[tuple[str, str, str]]]:
    """One REPORT on a list: status and ``(object name, etag, calendar-data)`` per object.

    ``url`` replaces the URL of the list ``uri``, for a collection that is no calendar.
    """
    target = url or caldav.calendar_url(creds, uri)
    result = await dav_request(session.client, creds, "REPORT", target, depth="1", body=body)
    if result.status != 207:
        return result.status, []
    rows = []
    for href, props in xml.parse_multistatus(result.body):
        name = unquote(href.rstrip("/").rsplit("/", 1)[-1])
        etag = props.get(f"{{{xml.DAV}}}getetag", "")
        rows.append((name, etag, props.get(f"{{{xml.CAL}}}calendar-data", "")))
    return result.status, rows


def measure_line(
    name: str, creds: Credentials, result: DavResult, before: str, after: str, raw: str
) -> None:
    """``<MESSUNG> auth=.. nutzer=.. status=.. etag_vorher=.. etag_nachher=.. | raw``."""
    note(
        f"{now_stamp()} | {name} auth={auth_label(creds)} nutzer={creds.user} "
        f"status={result.status} etag_vorher={short_etag(before)} "
        f"etag_nachher={short_etag(after)} | {raw}"
    )


def note_lines(title: str, text: str) -> None:
    """The unfolded content lines of an object, so the compared line sets stand in the raw file."""
    note(f"  {title}:")
    for line in unfold(text).split("\n"):
        if line.strip():
            note(f"      {line}")


@dataclass
class Modify:
    """The state of one modify block: the session, the stamp of its names, its objects."""

    session: Session
    stamp: str
    names: dict[str, str] = field(default_factory=dict)

    def name(self, key: str) -> str:
        """The object name of this run for ``key``; the UID is the name without ``.ics``."""
        return self.names.setdefault(key, f"s30-{key}-{self.stamp}.ics")

    async def create(self, creds: Credentials, uri: str, key: str, text: str) -> str:
        """A create-only PUT (``If-None-Match: *``), written as a SETUP line; returns the URL."""
        url = caldav.object_url(creds, uri, self.name(key))
        made = await put_object(self.session, creds, url, text, if_none_match="*")
        note(
            f"{now_stamp()} | SETUP PUT create-only {uri}/{self.name(key)} nutzer={creds.user} "
            f"auth={auth_label(creds)} status={made.status} antwort_etag="
            f"{short_etag(header_of(made, 'etag'))} | {describe_error(made.body)[:200]}"
        )
        if made.status not in (201, 204):
            raise RunFailed(f"create-only PUT of {self.name(key)} answered {made.status}")
        return url


async def modify_setup(state: Modify) -> dict[str, str]:
    """The four lists, the two shares and what USER_A sees of them; returns the shared URIs."""
    session = state.session
    creds = session.appapi(USER_A)
    since = container_now()
    await asyncio.sleep(1)
    for uri in (LIST_A, LIST_B):
        made = await dav_request(
            session.client,
            creds,
            "MKCALENDAR",
            caldav.calendar_url(creds, uri),
            body=mkcalendar_body(uri),
        )
        note(
            f"{now_stamp()} | MKCALENDAR auth=appapi status={made.status} liste={uri} "
            f"nutzer={USER_A} komponenten=VTODO | {describe_error(made.body)[:300]}"
        )
        note_raw(made)
        if made.status != 201:
            answer = php(NC_CONTAINER, PHP_CREATE_TASK_LIST, USER_A, uri)
            note(f"MKCALENDAR ersatzweg=php liste={uri} nutzer={USER_A} -> {answer}")
    lines = impersonation_lines(since, USER_A, "MKCALENDAR")
    note(f"KONTROLLE exapp_impersonation.log, MKCALENDAR-Zeilen von {USER_A}: {len(lines)}")
    for line in lines[-2:]:
        note(f"  {line[:400]}")

    owner = session.basic(USER_B)
    for uri, writable in ((LIST_RO, False), (LIST_RW, True)):
        url = caldav.calendar_url(owner, uri)
        made = await dav_request(
            session.client, owner, "MKCALENDAR", url, body=mkcalendar_body(uri)
        )
        note(
            f"{now_stamp()} | SETUP MKCALENDAR liste={uri} nutzer={USER_B} auth=basic "
            f"status={made.status}"
        )
        shared = await dav_request(
            session.client, owner, "POST", url, body=share_body(USER_A, writable=writable)
        )
        note(
            f"{now_stamp()} | FREIGABE liste={uri} an={USER_A} schreibrecht={yes_no(writable)} "
            f"nutzer={USER_B} auth=basic status={shared.status} (POST mit dem share-Dokument, "
            f"Namensraum {OC_SHARE_NS})"
        )
        note_raw(shared)

    home = await dav_request(
        session.client,
        creds,
        "PROPFIND",
        caldav.calendars_home_url(creds),
        depth="1",
        body=caldav.build_discovery_body(),
    )
    found = calendar_collections(home.body) if home.status == 207 else []
    note(f"{now_stamp()} | DISCOVERY PROPFIND Depth 1 auth=appapi nutzer={USER_A} {home.status}")
    for uri, name, comps in found:
        note(f"  DISCOVERY liste={uri} name={name} komponenten={','.join(comps)}")
    shared_uris = {}
    for key, uri in (("ro", LIST_RO), ("rw", LIST_RW)):
        wanted = f"{uri}_shared_by_{USER_B}"
        if any(wanted == seen for seen, _, _ in found):
            shared_uris[key] = wanted
    return shared_uris


async def if_match_sequence(
    state: Modify, creds: Credentials, *, controls: bool
) -> tuple[int, bool, int, bool]:
    """M3.1 and M3.2 for one way in: PUT with the current ETag, then with the stale one.

    Returns the four values ``abort_if_match`` decides on.
    """
    session = state.session
    auth = auth_label(creds)
    key = f"ifmatch-{auth}"
    name = state.name(key)
    uid = name.removesuffix(".ics")
    url = await state.create(creds, LIST_A, key, simple_todo(uid, "s30 if-match v0"))
    path = url[len(creds.base_url) :]
    _, etag0, text0 = await get_object(session, creds, url)
    since = container_now()
    await asyncio.sleep(1)
    text1 = set_summary(text0, "s30 if-match v1")
    hash0 = db_hash(name)
    put1 = await put_object(session, creds, url, text1, if_match=etag0)
    _, etag1, text_now = await get_object(session, creds, url)
    hash1 = db_hash(name)
    measure_line(
        "IF-MATCH aktuell",
        creds,
        put1,
        etag0,
        etag1,
        f"antwort_etag={yes_no(bool(header_of(put1, 'etag')))} etag_art={etag_kind(etag1)} "
        f"inhalt_neu={yes_no(text_now == text1)} db_hash_geaendert={yes_no(hash0 != hash1)} "
        f"db_gleich_gesendet={yes_no(hash1 == f'1 {sha_of(text1)}')}",
    )
    note(f"  Aufruf: PUT {path} mit If-Match auf die gelesene ETag, nur SUMMARY geaendert")
    note_raw(put1)
    if controls:
        lines = impersonation_lines(since, creds.user, "PUT")
        note(f"KONTROLLE exapp_impersonation.log, PUT-Zeilen von {creds.user}: {len(lines)}")
        for line in lines[-2:]:
            note(f"  {line[:400]}")
        other = session.basic(creds.user)
        href = caldav.object_url(other, LIST_A, name)[len(other.base_url) :]
        status, rows = await report(
            session, other, LIST_A, report_body("calendar-multiget", [href])
        )
        data = rows[0][2] if rows else ""
        note(
            f"{now_stamp()} | GEGENPROBE multiget REPORT calendar-multiget auth=basic "
            f"nutzer={other.user} status={status} objekte={len(rows)} "
            f"inhalt_gleich_gesendet={yes_no(plain(data) == plain(text1))}"
        )
        wrong = await put_object(
            session,
            session.appapi(creds.user, "0" * 64),
            url,
            set_summary(text1, "s30 if-match falsches secret"),
            if_match=etag1,
        )
        note(
            f"{now_stamp()} | GEGENPROBE falsches-secret PUT mit If-Match nutzer={creds.user} "
            f"status={wrong.status} db_hash_unveraendert={yes_no(db_hash(name) == hash1)} "
            f"| {describe_error(wrong.body)[:300]}"
        )

    hash_before = db_hash(name)
    stale = await put_object(
        session, creds, url, set_summary(text1, "s30 if-match veraltet"), if_match=etag0
    )
    _, etag2, text_after = await get_object(session, creds, url)
    hash_after = db_hash(name)
    unchanged = hash_before == hash_after and text_after == text_now and etag2 == etag1
    measure_line("IF-MATCH veraltet", creds, stale, etag1, etag2, describe_error(stale.body)[:300])
    note(
        f"  HASH calendardata vorher={hash_before} nachher={hash_after} "
        f"gleich={yes_no(hash_before == hash_after)} "
        f"get_byte_gleich={yes_no(text_after == text_now)}"
    )
    note(f"  Aufruf: PUT {path} mit If-Match auf die erste, jetzt veraltete ETag")
    note_raw(stale)
    return (put1.status, bool(etag1) and etag1 != etag0, stale.status, unchanged)


async def modify_if_match(state: Modify) -> None:
    """The first abort measurement of MESS-05, then the same sequence with the app password."""
    session = state.session
    values = await if_match_sequence(state, session.appapi(USER_A), controls=True)
    aborted, reason = abort_if_match(
        status_current=values[0],
        etag_changed=values[1],
        status_stale=values[2],
        unchanged_after_stale=values[3],
    )
    note(f"ABBRUCHKRITERIUM MESS-05 IF-MATCH ausgeloest={yes_no(aborted)} grund={reason}")
    other = await if_match_sequence(state, session.basic(USER_A), controls=False)
    note(
        f"IF-MATCH GLEICH appapi_basic={yes_no(values == other)} "
        f"appapi={values} basic={other} (status aktuell, etag geaendert, status veraltet, "
        "danach unveraendert)"
    )


async def modify_unconditional(state: Modify) -> None:
    """M3.3: what a PUT without ``If-Match`` and one with ``If-Match: *`` does to an object."""
    session = state.session
    creds = session.appapi(USER_A)
    name = state.name("ifmatch-appapi")
    url = caldav.object_url(creds, LIST_A, name)
    for label, condition in (("PUT ohne-if-match", None), ("PUT if-match-stern", "*")):
        _, etag_before, text = await get_object(session, creds, url)
        hash_before = db_hash(name)
        put = await put_object(
            session, creds, url, set_summary(text, f"s30 {label}"), if_match=condition
        )
        _, etag_after, _ = await get_object(session, creds, url)
        hash_after = db_hash(name)
        measure_line(
            label,
            creds,
            put,
            etag_before,
            etag_after,
            f"ueberschrieben={yes_no(hash_before != hash_after)} "
            f"| {describe_error(put.body)[:200]}",
        )
        note(f"  HASH calendardata vorher={hash_before} nachher={hash_after}")
        note_raw(put)


async def modify_properties(state: Modify) -> None:
    """M3.4, the second abort measurement: does a modifying PUT keep foreign properties?"""
    session = state.session
    creds = session.appapi(USER_A)
    name = state.name("eigenschaften")
    sent = build_probe_todo(name.removesuffix(".ics"), "s30 eigenschaften v0")
    url = caldav.object_url(creds, LIST_A, name)
    made = await put_object(session, creds, url, sent, if_none_match="*")
    _, etag0, text0 = await get_object(session, creds, url)
    measure_line("EIGENSCHAFTEN anlegen", creds, made, "", etag0, describe_error(made.body)[:200])
    note_raw(made)
    stored = db_hash(name)
    verbatim = stored == f"1 {sha_of(sent)}"
    note(
        f"SPEICHERUNG woertlich={yes_no(verbatim)} gesendet={sha_of(sent)} datenbank={stored} "
        f"get_gleich_gesendet={yes_no(text0 == sent)}"
    )
    if not verbatim or text0 != sent:
        added, removed, changed = line_diff(sent, text0)
        note(
            f"  SPEICHERUNG differenz gesendet gegen gelesen: hinzu={added or 'keine'} "
            f"entfernt={removed or 'keine'} geaendert={sorted(changed) or 'keine'}"
        )

    text1 = set_summary(text0, "s30 eigenschaften v1")
    put = await put_object(session, creds, url, text1, if_match=etag0)
    _, etag1, text2 = await get_object(session, creds, url)
    measure_line("EIGENSCHAFTEN aendern", creds, put, etag0, etag1, describe_error(put.body)[:200])
    note("  Aufruf: PUT mit If-Match, der gelesene Text mit genau einer geaenderten Zeile")
    note_raw(put)
    stored = db_hash(name)
    note(
        f"SPEICHERUNG nach_aendern woertlich={yes_no(stored == f'1 {sha_of(text1)}')} "
        f"gesendet={sha_of(text1)} datenbank={stored} get_gleich_gesendet={yes_no(text2 == text1)}"
    )
    added, removed, changed = line_diff(text0, text2)
    note(
        f"EIGENSCHAFTEN differenz zeilen_vorher={len(ics_line_set(text0))} "
        f"zeilen_nachher={len(ics_line_set(text2))} hinzu={added or 'keine'} "
        f"entfernt={removed or 'keine'} geaendert={sorted(changed) or 'keine'}"
    )
    note_lines("ZEILEN vorher (entfaltet)", text0)
    note_lines("ZEILEN nachher (entfaltet)", text2)
    ok, lost = preserved(text0, text2)

    # The control object: the same PUT, but the text sent back lacks one X- line on purpose.
    control_url = await state.create(
        creds,
        LIST_A,
        "eigenschaften-kontrolle",
        build_probe_todo(state.name("eigenschaften-kontrolle")[:-4], "s30 kontrolle v0"),
    )
    _, control_etag, control0 = await get_object(session, creds, control_url)
    cut = set_summary(control0, "s30 kontrolle v1").replace(PROBE_X_LINE, "")
    control_put = await put_object(session, creds, control_url, cut, if_match=control_etag)
    _, _, control2 = await get_object(session, creds, control_url)
    _, control_lost = preserved(control0, control2)
    control_ok = control_lost == [f"entfernt VCALENDAR/VTODO:{PROBE_X_LINE.strip()}"]
    note(
        f"{now_stamp()} | KONTROLLE eigenschaften kontrollobjekt ohne die Zeile "
        f"{PROBE_X_LINE.strip()} zurueckgeschrieben status={control_put.status} "
        f"verloren={control_lost or 'keine'} genau_die_entfernte={yes_no(control_ok)}"
    )

    maintained = sorted(
        (changed - {"SUMMARY"}) | {property_name(line.split(":", 1)[1]) for line in added}
    )
    note(f"PFLEGEFELDER server={','.join(maintained) or 'keine'}")
    written = 200 <= put.status < 300 and "SUMMARY" in changed
    aborted = not ok or not written
    note(
        f"ABBRUCHKRITERIUM MESS-05 EIGENSCHAFTEN ausgeloest={yes_no(aborted)} "
        f"verloren={lost or 'keine'} put_status={put.status} "
        f"aenderung_angekommen={yes_no(written)} "
        f"kontrolle={'ok' if control_ok else 'fehlgeschlagen'}"
    )


async def modify_shared(state: Modify, shared: Mapping[str, str]) -> None:
    """M3.5: PUT into a list shared read-only, and the same into one shared with write access."""
    session = state.session
    if set(shared) != {"ro", "rw"}:
        note(
            "NUR-LESEN ungemessen grund=die geteilten Listen erscheinen nicht in der Discovery "
            f"von {USER_A} (gefunden: {dict(shared) or 'keine'}), Rohantwort der Freigabe oben"
        )
        return
    owner = session.basic(USER_B)
    owner_urls = {}
    for key, uri in (("ro", LIST_RO), ("rw", LIST_RW)):
        name = state.name(f"geteilt-{key}")
        text = simple_todo(name.removesuffix(".ics"), f"s30 geteilt {key} v0")
        owner_urls[key] = await state.create(owner, uri, f"geteilt-{key}", text)
    statuses: dict[tuple[str, str], int] = {}
    for creds in (session.appapi(USER_A), session.basic(USER_A)):
        auth = auth_label(creds)
        for key, label in (("ro", "NUR-LESEN put"), ("rw", "SCHREIBRECHT put")):
            name = state.name(f"geteilt-{key}")
            url = caldav.object_url(creds, shared[key], name)
            got, etag, text = await get_object(session, creds, url)
            note(
                f"{now_stamp()} | LESEN geteilt {shared[key]}/{name} auth={auth} "
                f"nutzer={creds.user} status={got.status}"
            )
            if got.status != 200:
                raise RunFailed(f"the shared object {name} could not be read: {got.status}")
            hash_before = db_hash(name)
            put = await put_object(
                session, creds, url, set_summary(text, f"s30 geteilt {key} {auth}"), if_match=etag
            )
            _, owner_etag, _ = await get_object(session, owner, owner_urls[key])
            hash_after = db_hash(name)
            statuses[(key, auth)] = put.status
            measure_line(
                label,
                creds,
                put,
                etag,
                owner_etag,
                f"beim_eigentuemer_unveraendert={yes_no(hash_before == hash_after)} "
                f"| {describe_error(put.body)[:300]}",
            )
            note(
                f"  HASH calendardata vorher={hash_before} nachher={hash_after}; etag_nachher "
                f"ist als {USER_B} mit App-Passwort gelesen"
            )
            note_raw(put)
        fresh = state.name(f"geteilt-ro-neu-{auth}")
        made = await put_object(
            session,
            creds,
            caldav.object_url(creds, shared["ro"], fresh),
            simple_todo(fresh.removesuffix(".ics"), "s30 geteilt ro neu"),
            if_none_match="*",
        )
        rows = db_hash(fresh).split()[0]
        statuses[("neu", auth)] = made.status
        measure_line(
            "NUR-LESEN anlegen",
            creds,
            made,
            "",
            "",
            f"angelegt={yes_no(rows != '0')} | {describe_error(made.body)[:300]}",
        )
        note_raw(made)
    refused_ro = not 200 <= statuses[("ro", "appapi")] < 300
    note(
        f"NUR-LESEN ERGEBNIS abgelehnt={yes_no(refused_ro)} "
        f"status={statuses[('ro', 'appapi')]} anlegen={statuses[('neu', 'appapi')]} "
        f"positivkontrolle_schreibrecht={statuses[('rw', 'appapi')]} (auth=appapi); "
        f"auth=basic: {statuses[('ro', 'basic')]}, {statuses[('neu', 'basic')]}, "
        f"{statuses[('rw', 'basic')]}"
    )


async def object_names(session: Session, creds: Credentials, uri: str) -> list[str]:
    """The object names of one list, read with a calendar-query REPORT."""
    _, rows = await report(session, creds, uri, report_body("calendar-query"))
    return sorted(name for name, _, _ in rows)


async def modify_recurring(state: Modify) -> None:
    """M3.6: the server side of checking off the master of a recurring task with one PUT."""
    session = state.session
    creds = session.appapi(USER_A)
    name = state.name("wiederkehrend")
    extra = ["DTSTART:20261112T090000Z", "DUE:20261112T100000Z", "RRULE:FREQ=DAILY"]
    text = simple_todo(name.removesuffix(".ics"), "s30 wiederkehrend server", extra)
    url = await state.create(creds, LIST_A, "wiederkehrend", text)
    _, etag0, text0 = await get_object(session, creds, url)
    before = await object_names(session, creds, LIST_A)
    done = complete_todo(text0, datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    put = await put_object(session, creds, url, done, if_match=etag0)
    _, etag1, text2 = await get_object(session, creds, url)
    after = await object_names(session, creds, LIST_A)
    stored = db_hash(name)
    note(
        f"{now_stamp()} | WIEDERKEHREND server status={put.status} "
        f"rrule_erhalten={yes_no('RRULE:FREQ=DAILY' in unfold(text2))} "
        f"status_completed_gespeichert={yes_no('STATUS:COMPLETED' in unfold(text2))} "
        f"woertlich_gespeichert={yes_no(stored == f'1 {sha_of(done)}')} "
        f"objekte_vorher={len(before)} objekte_nachher={len(after)} "
        f"neue_objekte={sorted(set(after) - set(before)) or 'keine'} auth=appapi nutzer={USER_A} "
        f"etag_vorher={short_etag(etag0)} etag_nachher={short_etag(etag1)}"
    )
    added, removed, changed = line_diff(text0, text2)
    note(
        f"  WIEDERKEHREND differenz hinzu={added or 'keine'} entfernt={removed or 'keine'} "
        f"geaendert={sorted(changed) or 'keine'}; datenbank={stored}"
    )
    note_raw(put)


async def modify_subtask(state: Modify) -> None:
    """M3.7: does the server touch a sub task when its parent is checked off with one PUT?"""
    session = state.session
    creds = session.appapi(USER_A)
    parent_name, child_name = state.name("eltern"), state.name("kind")
    parent_uid = parent_name.removesuffix(".ics")
    parent_url = await state.create(
        creds, LIST_A, "eltern", simple_todo(parent_uid, "s30 eltern server")
    )
    child_url = await state.create(
        creds,
        LIST_A,
        "kind",
        simple_todo(
            child_name.removesuffix(".ics"), "s30 kind server", [f"RELATED-TO:{parent_uid}"]
        ),
    )
    _, child_etag0, child0 = await get_object(session, creds, child_url)
    child_hash0 = db_hash(child_name)
    _, parent_etag0, parent0 = await get_object(session, creds, parent_url)
    done = complete_todo(parent0, datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    put = await put_object(session, creds, parent_url, done, if_match=parent_etag0)
    _, parent_etag1, _ = await get_object(session, creds, parent_url)
    _, child_etag1, child1 = await get_object(session, creds, child_url)
    child_hash1 = db_hash(child_name)
    same = child_etag0 == child_etag1 and child0 == child1 and child_hash0 == child_hash1
    note(
        f"{now_stamp()} | UNTERAUFGABE server unveraendert={yes_no(same)} "
        f"eltern_status={put.status} "
        f"eltern_etag_geaendert={yes_no(bool(parent_etag1) and parent_etag0 != parent_etag1)} "
        f"kind_etag_vorher={short_etag(child_etag0)} kind_etag_nachher={short_etag(child_etag1)} "
        f"kind_hash_gleich={yes_no(child_hash0 == child_hash1)} auth=appapi nutzer={USER_A}"
    )
    note(f"  HASH calendardata der Unteraufgabe vorher={child_hash0} nachher={child_hash1}")
    note_raw(put)


async def block_modify(session: Session) -> None:
    """MESS-05, server side: the two abort measurements first, then the rest.

    The block does not take its lists back: the browser session and the evaluation after it
    still need the instance, and ui-teardown rolls everything back.
    """
    section("modify")
    ram_gate(NC35_CONTAINERS)
    state = Modify(session=session, stamp=datetime.now(UTC).strftime("%H%M%S"))
    shared = await modify_setup(state)
    await guarded("modify if-match", modify_if_match(state))
    await guarded("modify ohne if-match", modify_unconditional(state))
    await guarded("modify eigenschaften", modify_properties(state))
    await guarded("modify nur-lesen", modify_shared(state, shared))
    await guarded("modify wiederkehrend", modify_recurring(state))
    await guarded("modify unteraufgabe", modify_subtask(state))


def outside_repository(path: Path) -> Path:
    """``path`` resolved, refused if it lies inside the repository (threat T-30-08)."""
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise RunFailed("the file with the browser login has to lie outside the repository")
    return resolved


async def block_ui_prepare(session: Session, ui_file: Path) -> None:
    """The Tasks app and the account of the browser session; the login goes to ``ui_file``."""
    section("ui-prepare")
    ram_gate(NC35_CONTAINERS)
    target = outside_repository(ui_file)
    enabled, disabled = app_list()
    installed_before = "tasks" in enabled or "tasks" in disabled
    if "tasks" not in enabled:
        occ_noted("app:enable" if "tasks" in disabled else "app:install", "tasks")
    enabled, _ = app_list()
    version = enabled.get("tasks", "")
    if not version:
        note(
            "TASKS-APP ungemessen grund=die App tasks liess sich in dieser Instanz nicht "
            "einschalten, Rohausgabe in der Zeile darueber"
        )
        raise RunFailed("the Tasks app could not be installed; a finding for the owner")
    note(
        f"TASKS-APP version={version} installiert_vorher={yes_no(installed_before)} "
        "(gelesen mit occ app:list --output=json)"
    )

    password = secrets.token_urlsafe(24)
    remember_secret(f"PASSWORD_{UI_USER}", password)
    added = occ_pw(NC_CONTAINER, password, "user:add", "--password-from-env", UI_USER)
    note(f"occ user:add --password-from-env {UI_USER} (password via stdin) -> {added[:120]}")
    session.app_passwords[UI_USER] = new_app_password(
        NC_CONTAINER, UI_USER, password, f"APP_PASSWORD_{UI_USER}"
    )
    # A fixed interface language, so the written steps of the browser session name the
    # labels the app really shows; both values fall with the account.
    occ_noted("user:setting", UI_USER, "core", "lang", "de")
    occ_noted("user:setting", UI_USER, "core", "locale", "de_DE")
    basic = session.basic(UI_USER)
    home = await dav_request(
        session.client,
        basic,
        "PROPFIND",
        home_url(basic, "/"),
        depth="0",
        body=propfind_body([f"{{{xml.OC}}}fileid"]),
    )
    note(f"{now_stamp()} | SETUP PROPFIND Depth 0 home of {UI_USER} auth=basic -> {home.status}")
    for creds in (basic, session.appapi(UI_USER)):
        listing = await dav_request(
            session.client,
            creds,
            "PROPFIND",
            caldav.calendars_home_url(creds),
            depth="1",
            body=caldav.build_discovery_body(),
        )
        found = calendar_collections(listing.body) if listing.status == 207 else []
        lists = [f"{uri} ({','.join(comps)})" for uri, _, comps in found]
        note(
            f"{now_stamp()} | UI-KONTO DISCOVERY auth={auth_label(creds)} nutzer={UI_USER} "
            f"status={listing.status} listen={lists or 'keine'}"
        )
    page = await session.client.get(f"{basic.base_url}/apps/tasks/", auth=basic.auth())
    note(
        f"{now_stamp()} | UI-KONTO GET /apps/tasks/ auth=basic nutzer={UI_USER} "
        f"status={page.status_code} html={yes_no('<html' in page.text[:2000].lower())}"
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"{UI_USER}\n{password}\n{basic.base_url}\n")
    note(
        f"UI-KONTO nutzer={UI_USER} adresse={basic.base_url}/apps/tasks/ zugangsdaten=in einer "
        "Datei ausserhalb des Repositorys (drei Zeilen: Nutzer, Passwort, Basis-URL)"
    )
    # Console only, never the protocol: the path names a local account directory.
    print(f"UI-LOGIN nutzer={UI_USER} zugangsdatei={target}")


async def ui_seed_recurring(
    session: Session, creds: Credentials, lists: Sequence[tuple[str, str, tuple[str, ...]]]
) -> None:
    """Create the recurring task by PUT if the Tasks app offers no recurrence."""
    wanted = "spike30-liste-1"
    target = next((uri for uri, name, _ in lists if wanted in (name, uri)), "")
    if not target:
        raise RunFailed(f"--seed-recurring needs the list {wanted}, which the account lacks")
    name = "s30-wiederkehrend-skript.ics"
    extra = ["DTSTART:20261112T090000Z", "DUE:20261112T100000Z", "RRULE:FREQ=DAILY"]
    put = await put_object(
        session,
        creds,
        caldav.object_url(creds, target, name),
        simple_todo(name.removesuffix(".ics"), UI_RECURRING, extra),
        if_none_match="*",
    )
    note(
        f"UI-NACHGELEGT {UI_RECURRING} status={put.status} liste={target} objekt={name} "
        "(vom Skript per PUT mit RRULE:FREQ=DAILY angelegt, keine von der App geschriebene Fixture)"
    )


async def ui_compare(session: Session) -> None:
    """The comparison object of M3.8: a task the script itself checks off with one PUT.

    Whatever differs afterwards beyond the three lines the script sent is maintained by the
    server; everything else the browser session shows is therefore written by the Tasks app.
    It lives in a list of USER_A, so the account of the browser session stays untouched.
    """
    creds = session.appapi(USER_A)
    name = f"s30-vergleich-{datetime.now(UTC).strftime('%H%M%S')}.ics"
    url = caldav.object_url(creds, LIST_A, name)
    text = simple_todo(name.removesuffix(".ics"), "s30 vergleich skript")
    made = await put_object(session, creds, url, text, if_none_match="*")
    _, etag0, text0 = await get_object(session, creds, url)
    done = complete_todo(text0, datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    put = await put_object(session, creds, url, done, if_match=etag0)
    _, etag1, text1 = await get_object(session, creds, url)
    added, removed, changed = line_diff(done, text1)
    maintained = sorted(changed | {property_name(line.split(":", 1)[1]) for line in added})
    sent, _, _ = line_diff(text0, done)
    note(
        f"{now_stamp()} | VERGLEICH skript_put pflegefelder_server="
        f"{','.join(maintained) or 'keine'} anlegen={made.status} abhaken={put.status} "
        f"etag_vorher={short_etag(etag0)} etag_nachher={short_etag(etag1)} "
        f"gesendet_hinzu={[line.split(':', 1)[1] for line in sent]} "
        f"vom_server_entfernt={removed or 'keine'} "
        f"woertlich_gespeichert={yes_no(db_hash(name) == f'1 {sha_of(done)}')} "
        f"auth=appapi nutzer={USER_A} liste={LIST_A} objekt={name}"
    )


async def block_ui_snapshot(session: Session, label: str, seed: bool, ui_file: Path) -> None:
    """Every object of the browser account as one file below ``raw/ui-<label>/``.

    Read under impersonation with one GET per object, so the files carry the bytes the
    server sent; the counter probe reads the same lists with an app password and a REPORT.
    """
    section(f"ui-snapshot {label}")
    ram_gate(NC35_CONTAINERS)
    user, password, _ = read_ui_file(ui_file)
    remember_secret(f"PASSWORD_{user}", password)
    session.app_passwords[user] = new_app_password(
        NC_CONTAINER, user, password, f"APP_PASSWORD_{user}_{label}"
    )
    creds, basic = session.appapi(user), session.basic(user)
    home_url_ = caldav.calendars_home_url(creds)
    home = await dav_request(
        session.client, creds, "PROPFIND", home_url_, depth="1", body=caldav.build_discovery_body()
    )
    if home.status != 207:
        raise RunFailed(f"the discovery of {user} answered {home.status}")
    lists = calendar_collections(home.body)
    for uri, name, comps in lists:
        note(f"UI-LISTE stand={label} liste={uri} name={name} komponenten={','.join(comps)}")
    if seed:
        await ui_seed_recurring(session, creds, lists)

    objects: list[SnapshotObject] = []
    differing: list[str] = []
    for uri, _, _ in lists:
        status, rows = await report(session, creds, uri, report_body("calendar-query"))
        other_status, other_rows = await report(session, basic, uri, report_body("calendar-query"))
        other = {name: plain(data) for name, _, data in other_rows}
        note(
            f"{now_stamp()} | UI-REPORT stand={label} liste={uri} auth=appapi status={status} "
            f"objekte={len(rows)} | auth=basic status={other_status} objekte={len(other_rows)}"
        )
        for name, _, _ in rows:
            got, etag, text = await get_object(session, creds, caldav.object_url(creds, uri, name))
            if got.status != 200:
                raise RunFailed(f"GET of {uri}/{name} answered {got.status}")
            objects.append(SnapshotObject(uri, name, etag, got.body, False))
            if other.get(name) != plain(text):
                differing.append(f"{uri}/{name}")
        differing.extend(f"{uri}/{name}" for name in other if name not in {r[0] for r in rows})

    # The trash bin answers a PROPFIND with 501 (measured on 35.0.0); its collection only
    # implements the calendar-query REPORT, which lists every deleted object as <id>.ics.
    trash_url = f"{home_url_}trashbin/objects/"
    trash_status, trash_rows = await report(
        session, creds, "", report_body("calendar-query"), url=trash_url
    )
    note(
        f"{now_stamp()} | UI-PAPIERKORB-LESEN stand={label} REPORT calendar-query "
        f"trashbin/objects auth=appapi status={trash_status} objekte={len(trash_rows)}"
    )
    for name, etag, data in trash_rows:
        got, got_etag, _ = await get_object(session, creds, f"{trash_url}{quote(name, safe='')}")
        if got.status == 200:
            objects.append(SnapshotObject("trashbin", name, got_etag or etag, got.body, True))
        else:
            # The REPORT carried the text already; XML parsing left it with LF line ends.
            note(f"  UI-PAPIERKORB objekt={name} GET status={got.status}, Text aus dem REPORT")
            objects.append(SnapshotObject("trashbin", name, etag, data.encode(), True))

    files = write_snapshot(RAW_DIR, label, objects)
    summaries = []
    for item, file_name in zip(objects, files, strict=True):
        summary = property_value(item.data.decode("utf-8", errors="replace"), "SUMMARY")
        if not item.trashed:
            summaries.append(summary)
        note(
            f"UI-OBJEKT stand={label} liste={item.collection} name={file_name} "
            f"summary={summary} etag={short_etag(item.etag)}"
        )
    note(f"UI-GLEICH appapi_basic={yes_no(not differing)} abweichend={differing or 'keine'}")
    note(f"UI-STAND {label} objekte={len(objects)}")
    if label == "a":
        for name in missing_names(summaries):
            note(f"UI-FEHLT name={name}")
        note(f"UI-WIEDERKEHREND vorhanden={yes_no(UI_RECURRING in summaries)}")
    else:
        await ui_compare(session)


# --- plan 30-02 task 3: evaluation of the browser session -------------------------------------


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """One object of a written snapshot: its file name, its text, and whether it is trash."""

    file: str
    text: str
    trashed: bool


def load_snapshot(directory: Path) -> dict[str, SnapshotEntry]:
    """The objects of ``raw/ui-<label>/`` keyed by UID.

    The UID is what stays the same when the Tasks app moves an object to another list or the
    server renames it on its way into the trash bin; the file name does not.
    """
    entries: dict[str, SnapshotEntry] = {}
    for path in sorted(directory.glob("*.ics")):
        text = path.read_bytes().decode("utf-8", errors="replace")
        uid = property_value(text, "UID") or path.name
        entries[uid] = SnapshotEntry(path.name, text, path.name.startswith("trash-"))
    return entries


def snapshot_lists(protocol: str, label: str) -> dict[str, str]:
    """File name to list for one state, from the ``UI-OBJEKT`` lines of the session protocol.

    A later run under the same label replaces the state, so a later line wins.
    """
    lists: dict[str, str] = {}
    pattern = re.compile(rf"^UI-OBJEKT stand={label} liste=(\S+) name=(\S+) ")
    for line in protocol.splitlines():
        match = pattern.match(line)
        if match:
            lists[match[2]] = match[1]
    return lists


def _names(lines: Iterable[str]) -> list[str]:
    """The property names of ``<component path>:<line>`` entries, sorted and unique."""
    return sorted({property_name(line.split(":", 1)[1]) for line in lines})


def field_diff(before: str, after: str) -> str:
    """``hinzu=.. entfernt=.. geaendert=..`` by property name, or ``leer`` for no difference."""
    added, removed, changed = line_diff(before, after)
    if not added and not removed and not changed:
        return "leer"
    return (
        f"hinzu={','.join(_names(added)) or 'keine'} "
        f"entfernt={','.join(_names(removed)) or 'keine'} "
        f"geaendert={','.join(sorted(changed)) or 'keine'}"
    )


def _line_of(text: str, name: str) -> str:
    """The first unfolded content line of the property ``name``, or empty."""
    for line in unfold(text).split("\n"):
        if property_name(line) == name:
            return line
    return ""


def _added_lines(before: str, after: str) -> list[str]:
    added, _, _ = line_diff(before, after)
    return [line.split(":", 1)[1] for line in added]


def evaluate_snapshots(
    before: Mapping[str, SnapshotEntry],
    after: Mapping[str, SnapshotEntry],
    lists_before: Mapping[str, str],
    lists_after: Mapping[str, str],
) -> list[str]:
    """The lines of ui-evaluate: what the Tasks app wrote between state a and state b.

    Objects are matched by UID. A task the evaluation needs and does not find in both states
    gives an ``ungemessen`` line with the reason, never a guessed value.
    """
    by_name = {property_value(entry.text, "SUMMARY"): uid for uid, entry in before.items()}
    lines: list[str] = []

    def pair(name: str) -> tuple[SnapshotEntry, SnapshotEntry] | None:
        uid = by_name.get(name)
        if uid is None or uid not in after:
            return None
        return before[uid], after[uid]

    def missing(label: str, name: str) -> str:
        return f"{label} ungemessen grund=das Objekt {name} fehlt in Stand a oder in Stand b"

    checked = pair("s30 abhaken")
    checked_names: list[str] = []
    if checked is None:
        lines.append(missing("ABHAKEN FELDER", "s30 abhaken"))
    else:
        old, new = checked
        completed = _line_of(new.text, "COMPLETED")
        checked_names = _names(line_diff(old.text, new.text)[0])
        lines.append(
            f"ABHAKEN FELDER {field_diff(old.text, new.text)} "
            f"zeitform_completed={value_form(completed) if completed else 'fehlt'}"
        )
        lines.append(f"  ABHAKEN zeilen_hinzu={_added_lines(old.text, new.text) or 'keine'}")

    reopened = pair("s30 wieder-oeffnen")
    if reopened is None:
        lines.append(missing("WIEDEROEFFNEN FELDER", "s30 wieder-oeffnen"))
    else:
        old, new = reopened
        present = {property_name(line) for _, line in ics_line_set(new.text)}
        gone = [name for name in checked_names if name not in present]
        lines.append(f"WIEDEROEFFNEN FELDER {field_diff(old.text, new.text)}")
        lines.append(
            f"  WIEDEROEFFNEN zeilen_hinzu={_added_lines(old.text, new.text) or 'keine'} "
            f"abhaken_felder_danach_fehlend={','.join(gone) or 'keine'} "
            f"status_danach={property_value(new.text, 'STATUS') or 'fehlt'}"
        )

    parent, child = pair("s30 eltern-abhaken"), pair("s30 kind-abhaken")
    if parent is None or child is None:
        lines.append(missing("ELTERN ABHAKEN", "s30 eltern-abhaken oder s30 kind-abhaken"))
    else:
        child_diff = field_diff(child[0].text, child[1].text)
        parent_diff = field_diff(parent[0].text, parent[1].text)
        lines.append(
            f"ELTERN ABHAKEN kind_geaendert={yes_no(child_diff != 'leer')} "
            f"kind_differenz={child_diff} | eltern_geaendert={yes_no(parent_diff != 'leer')} "
            f"eltern_differenz={parent_diff}"
        )
        lines.append(
            f"  ELTERN ABHAKEN kind_zeilen_hinzu="
            f"{_added_lines(child[0].text, child[1].text) or 'keine'} "
            f"eltern_status_stand_b={property_value(parent[1].text, 'STATUS') or 'fehlt'}"
        )

    new_uids = sorted(uid for uid in after if uid not in before)
    gone_uids = sorted(uid for uid in before if uid not in after)
    recurring = pair(UI_RECURRING)
    if recurring is None:
        lines.append(missing("WIEDERKEHREND app", UI_RECURRING))
    else:
        old, new = recurring
        lines.append(
            f"WIEDERKEHREND app differenz {field_diff(old.text, new.text)} "
            f"due_vorher={property_value(old.text, 'DUE') or 'fehlt'} "
            f"due_nachher={property_value(new.text, 'DUE') or 'fehlt'} "
            f"rrule_nachher={property_value(new.text, 'RRULE') or 'fehlt'} "
            f"status_nachher={property_value(new.text, 'STATUS') or 'fehlt'} "
            f"completed_nachher={property_value(new.text, 'COMPLETED') or 'fehlt'} "
            f"neue_objekte={len(new_uids)}"
        )

    control = pair("s30 unberuehrt")
    if control is None:
        lines.append(missing("KONTROLLE unberuehrt", "s30 unberuehrt"))
    else:
        lines.append(
            f"KONTROLLE unberuehrt differenz={field_diff(control[0].text, control[1].text)}"
        )

    moved = []
    for uid, new in sorted(after.items(), key=lambda item: item[1].file):
        if new.trashed or uid not in before:
            continue
        old = before[uid]
        source, target = lists_before.get(old.file, "?"), lists_after.get(new.file, "?")
        if source != target:
            moved.append(
                f"UI-UMZUG objekt={property_value(new.text, 'SUMMARY')} von={source} "
                f"nach={target} dateiname_gleich={yes_no(old.file == new.file)} "
                f"inhalt_gleich={yes_no(old.text == new.text)}"
            )
    second = sorted(name for name, target in lists_after.items() if target.endswith("-liste-2"))
    lines.append(f"UI-UMZUG objekte_in_liste_2={len(second)} verschoben={len(moved)}")
    lines.extend(moved)

    trash = [(uid, entry) for uid, entry in sorted(after.items()) if entry.trashed]
    lines.append(f"UI-PAPIERKORB objekte={len(trash)}")
    for uid, entry in trash:
        same = uid in before and before[uid].text == entry.text
        lines.append(
            f"UI-PAPIERKORB objekt={property_value(entry.text, 'SUMMARY')} datei={entry.file} "
            f"datei_stand_a={before[uid].file if uid in before else 'fehlt'} "
            f"inhalt_gleich_stand_a={yes_no(same)}"
        )

    lines.append(f"UI-NEU objekte={len(new_uids)} uids={new_uids or 'keine'}")
    lines.append(f"UI-VERSCHWUNDEN objekte={len(gone_uids)} uids={gone_uids or 'keine'}")
    for uid, old in sorted(
        before.items(), key=lambda item: property_value(item[1].text, "SUMMARY")
    ):
        if uid in after:
            lines.append(
                f"UI-DIFFERENZ name={property_value(old.text, 'SUMMARY')} "
                f"differenz={field_diff(old.text, after[uid].text)}"
            )
    for label, state in (("a", before), ("b", after)):
        for _, entry in sorted(
            state.items(), key=lambda item: property_value(item[1].text, "SUMMARY")
        ):
            forms = [
                f"{name}={value_form(_line_of(entry.text, name))}"
                for name in ("DTSTART", "DUE", "COMPLETED", "CREATED", "LAST-MODIFIED", "DTSTAMP")
                if _line_of(entry.text, name)
            ]
            lines.append(
                f"ZEITFORM stand={label} name={property_value(entry.text, 'SUMMARY')} "
                f"{' '.join(forms)}"
            )
    return lines


_ACCESS_WRITE = re.compile(
    r'\[([^\]]+)\] "(PUT|MOVE|DELETE|MKCOL|MKCALENDAR|PROPPATCH|COPY) '
    r'/remote\.php/dav/calendars/([^/ ]+)/(\S*) HTTP/[^"]*" (\d{3})'
)


def access_writes(log: str, user: str) -> list[tuple[str, str, str, int]]:
    """``(time, method, path below the calendar home, status)`` of every writing request.

    Read from the access log of the web server, which is not what the Tasks app shows and
    not what DAV answers later: the third way of knowing what the browser session wrote.
    """
    rows = []
    for line in log.splitlines():
        match = _ACCESS_WRITE.search(line)
        if match and match[3] == user:
            rows.append((match[1], match[2], match[4], int(match[5])))
    return rows


#: What a client sees of a list: asked for once more before the browser account is deleted,
#: because plan 30-04 evaluates how a list the Tasks app created looks in the discovery.
UI_DISCOVERY_PROPS = (
    f"{{{xml.DAV}}}displayname",
    f"{{{xml.DAV}}}resourcetype",
    f"{{{xml.DAV}}}owner",
    f"{{{xml.DAV}}}current-user-privilege-set",
    f"{{{xml.DAV}}}sync-token",
    f"{{{xml.CAL}}}supported-calendar-component-set",
    f"{{{xml.CS}}}getctag",
    "{http://apple.com/ns/ical/}calendar-color",
    "{http://apple.com/ns/ical/}calendar-order",
    f"{{{xml.OC}}}calendar-enabled",
)


async def ui_discovery_raw(session: Session, user: str) -> None:
    """The raw discovery answer of the browser account under impersonation, line by line."""
    creds = session.appapi(user)
    result = await dav_request(
        session.client,
        creds,
        "PROPFIND",
        caldav.calendars_home_url(creds),
        depth="1",
        body=propfind_body(UI_DISCOVERY_PROPS),
    )
    note(
        f"{now_stamp()} | UI-DISCOVERY-ROH PROPFIND Depth 1 auth=appapi nutzer={user} "
        f"status={result.status} bytes={len(result.body)}"
    )
    for line in result.body.decode("utf-8", errors="replace").splitlines():
        if line.strip():
            note(f"    {line.rstrip()}")


async def block_ui_log(session: Session, ui: "UiOptions") -> None:
    """The writing requests of the browser account and the server errors behind a 5xx."""
    section("ui-log")
    ram_gate(NC35_CONTAINERS)
    user, password, _ = read_ui_file(ui.file())
    remember_secret(f"PASSWORD_{user}", password)
    await ui_discovery_raw(session, user)
    log = docker("logs", "--tail", "60000", NC_CONTAINER, check=False)
    rows = access_writes(log, user)
    note(f"UI-ZUGRIFFE nutzer={user} schreibende_anfragen={len(rows)} (Zugriffsprotokoll)")
    for stamp, method, path, status in rows:
        note(f"UI-ZUGRIFF {stamp} {method} {path} status={status}")
    failed = [row for row in rows if row[3] >= 400]
    note(f"UI-ZUGRIFFE mit_fehlerstatus={len(failed)}")
    server_log = docker(
        "exec", NC_CONTAINER, "tail", "-n", "4000", f"{DATA_DIR}/nextcloud.log", check=False
    )
    for line in server_log.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or record.get("user") != user:
            continue
        if int(record.get("level", 0)) < 3 or record.get("method") not in ("PUT", "MOVE", "DELETE"):
            continue
        message = record.get("message")
        text = message if isinstance(message, str) else json.dumps(message)
        note(
            f"UI-SERVERFEHLER {record.get('time')} {record.get('method')} "
            f"{str(record.get('url'))[-70:]} | {_one_line(text)[:200]}"
        )


def block_ui_evaluate(ui: "UiOptions") -> None:
    """Read ``raw/ui-a`` and ``raw/ui-b`` and write what differs; needs no instance."""
    section("ui-evaluate")
    if ui.out is None or not ui.out.is_file():
        raise RunFailed("ui-evaluate appends to the protocol of the snapshots; --out names it")
    protocol = ui.out.read_text(encoding="utf-8")
    before, after = load_snapshot(RAW_DIR / "ui-a"), load_snapshot(RAW_DIR / "ui-b")
    note(f"UI-AUSWERTUNG stand_a_objekte={len(before)} stand_b_objekte={len(after)} (nach UID)")
    lists_a, lists_b = snapshot_lists(protocol, "a"), snapshot_lists(protocol, "b")
    for line in evaluate_snapshots(before, after, lists_a, lists_b):
        note(line)


# --- plan 30-02 task 3: inventory of gates and promises (A17) ----------------------------------


@dataclass(frozen=True, slots=True)
class Hit:
    """One line a search pattern found: file, line number, wording, and which pattern."""

    file: str
    line: int
    text: str
    patterns: str


@dataclass(frozen=True, slots=True)
class Rule:
    """One hand written verdict: the first rule whose two patterns match a hit decides.

    ``klasse`` is a class of the inventory or ``ausgeschlossen``; ``target`` is then the
    phase that has to deal with the place, or the reason for leaving it out.
    """

    path: str
    text: str
    klasse: str
    methods: str
    target: str


#: Pattern 1: the wording of the promise in English, German and French.
PROMISE_WORDS = re.compile(
    r"create-only|create only|read and create|never delet|no delet|not delet|cannot delete|"
    r"deleting|deletes|never overwr|overwrit|nothing destructive|destructive|"
    r"\bmov(?:e|es|ing)\b|renam|gel\u00f6scht|l\u00f6sch|\u00fcberschr|destruktiv|verschieb|"
    r"umbenenn|nur anlegen|jamais|destructi|supprim|\u00e9cras|d\u00e9plac|renomm",
    re.IGNORECASE,
)
#: Pattern 2, the technical side: constants of the gates, method literals, test names, and
#: the HTTP vocabulary in the public texts, which does not depend on the language.
GATE_NAMES = re.compile(
    r"\b(?:EXPECTED_PUT_CALLS|FORBIDDEN|CHUNK_ASSEMBLY_MOVE|CREATE_TOOLS|destructive_hint|"
    r"idempotent_hint|MUST_REFUSE|FILE_WRITERS|PARAM_ALLOWLIST)\b"
)
METHOD_LITERALS = re.compile(r'"(?:PUT|MOVE|DELETE|PROPPATCH|COPY|MKCOL)"|client\.(?:put|delete)\(')
TEST_NAMES = re.compile(r"def test_\w*(?:create|destructive|overwrit|readonly|read_only)")
HTTP_WORDS = re.compile(
    r"\b(?:PUT|DELETE|MOVE|MKCOL|PROPPATCH|If-None-Match|If-Match)\b|Papierkorb|corbeille|\btrash"
)

PUBLIC_TEXTS = (
    "README.md",
    "README.de.md",
    "README.fr.md",
    "appinfo/info.xml",
    ".planning/PROJECT.md",
    "CHANGELOG*.md",
    "docs/**/*.md",
)
GATE_FILE = "tests/contract/test_no_destructive_calls.py"
#: The report of this phase quotes the promises it inventories and is left out of both.
INVENTORY_SKIP = ("docs/spike-tasks.md",)

#: How far from a gate constant a hit of pattern 1 may stand to count as reaching it.
CONTROL_REACH = 12
#: The six places the research named; pattern 1 has to find each of them.
CONTROL_PLACES = (
    "EXPECTED_PUT_CALLS",
    "FORBIDDEN",
    "README-Rechtetabelle",
    "threat-model",
    "Store-Text",
    "Server-Instruktion",
)

_ALL = "PUT,MOVE,DELETE"
_OLD_TOOL = "Aussage ueber ein bestehendes Werkzeug, das unveraendert bleibt"
_OTHER = "anderes Thema, keine Aussage ueber schreibende Werkzeuge"
_REPORT = "Messbericht oder Anleitung zu einem anderen Thema, keine Zusage ueber Werkzeuge"
_HISTORY = "Historie eines frueheren Release, wird nicht umgeschrieben"
_V18 = "beschreibt schon den geplanten Stand von v1.8 oder ist Verfahrenstext"

#: Written after reading every hit of both patterns on the commit named in the raw file.
INVENTORY_RULES: tuple[Rule, ...] = (
    # --- the destructive gate ---
    Rule(
        GATE_FILE,
        r"TALK_ROUTES|MAIL_ROUTES|SYSTEMTAGS|Talk segments|Mail segments|tag needle|"
        r"path forms exist|mail_modules|Tables|read marker|draft|thread|[Mm]ail|renames it or|"
        r"login flow|app password|purge|exemption would|pin somebody|ordinary prose",
        "ausgeschlossen",
        "",
        "Nadeln und Ausnahmen fuer Talk, Mail, Tables, Tags oder den Login-Flow, kein "
        "Aufgaben-Zugriff",
    ),
    Rule(
        GATE_FILE,
        r"EXPECTED_PUT_CALLS|compare-and-swap|compare_and_swap|could overwrite|"
        r"overwrite unconditionally|"
        r"init-progress|Every PUT",
        "gate",
        "PUT",
        "Phase 33",
    ),
    Rule(
        GATE_FILE,
        r"CHUNK_ASSEMBLY_MOVE|user-facing move|chunk-assembly|MOVE exemption|"
        r"one MOVE|final MOVE",
        "gate",
        "MOVE",
        "Phase 33",
    ),
    Rule(GATE_FILE, r"never delete, overwrite", "gate", _ALL, "Phase 33"),
    Rule(GATE_FILE, r"", "gate", "MOVE,DELETE", "Phase 33"),
    # --- other contract tests ---
    Rule(
        r"^tests/contract/test_tool_surface\.py$",
        r'"it can only|"a second call|def test_',
        "ausgeschlossen",
        "",
        _OLD_TOOL,
    ),
    Rule(
        r"^tests/contract/test_tool_surface\.py$",
        r"FORBIDDEN_PROPERTIES",
        "ausgeschlossen",
        "",
        _OTHER,
    ),
    Rule(r"^tests/contract/test_tool_surface\.py$", r"", "gate", _ALL, "Phase 33"),
    Rule(r"^tests/contract/(tool_classes|test_tool_classes)\.py$", r"", "gate", _ALL, "Phase 33"),
    Rule(r"^tests/contract/test_audit_surface\.py$", r"PARAM_ALLOWLIST", "audit", _ALL, "Phase 33"),
    Rule(r"^src/mcp_connector/audit/", r"PARAM_ALLOWLIST", "audit", _ALL, "Phase 33"),
    Rule(r"^tests/integration/test_canary\.py$", r"MUST_REFUSE", "kanarie", _ALL, "Phase 33"),
    Rule(
        r"^tests/",
        r"",
        "ausgeschlossen",
        "",
        "Test eines bestehenden Werkzeugs oder eines anderen Themas, vom Aufgaben-Zugriff "
        "nicht beruehrt",
    ),
    # --- the server ---
    Rule(
        r"^src/mcp_connector/server/__init__\.py$",
        r"Read and create|never deleted",
        "zusage-server",
        _ALL,
        "Phase 34",
    ),
    Rule(r"^src/mcp_connector/server/__init__\.py$", r"_hint", "annotation", _ALL, "Phase 33"),
    Rule(r"^src/mcp_connector/server/", r"", "ausgeschlossen", "", _OLD_TOOL),
    Rule(
        r"^src/mcp_connector/nextcloud/clients/",
        r'"MOVE"',
        "ausgeschlossen",
        "",
        "die Ausnahme CHUNK_ASSEMBLY_MOVE des Datei-Uploads, bleibt",
    ),
    Rule(
        r"^src/mcp_connector/nextcloud/clients/",
        r"",
        "ausgeschlossen",
        "",
        "bestehender Aufruf, den EXPECTED_PUT_CALLS zaehlt oder eine eigene Nadel haelt; "
        "selbst keine Zusage",
    ),
    Rule(r"^src/", r"", "ausgeschlossen", "", _OTHER),
    # --- store text ---
    Rule(
        r"^appinfo/info\.xml$",
        r"Nothing destructive|Nichts Destruktives|Rien de destructif",
        "zusage-store",
        _ALL,
        "Phase 34",
    ),
    Rule(
        r"^appinfo/info\.xml$",
        r"",
        "ausgeschlossen",
        "",
        "Datei-Upload oder Route der Einstellungsseite, kein Aufgaben-Zugriff",
    ),
    # --- changelogs and planning ---
    Rule(r"^CHANGELOG", r"", "ausgeschlossen", "", _HISTORY),
    Rule(
        r"^\.planning/PROJECT\.md$",
        r"Schreibzusage|destruktive Ops|Destruktive Operationen|"
        r"keine destruktiven Writes",
        "zusage-doku",
        _ALL,
        "Phase 34",
    ),
    Rule(r"^\.planning/PROJECT\.md$", r"", "ausgeschlossen", "", _V18),
    # --- the three READMEs ---
    Rule(
        r"^README",
        r"NC_MCP_FILES_UPDATE|files_update|ETag",
        "ausgeschlossen",
        "",
        "beschreibt files_update, das unveraendert bleibt",
    ),
    Rule(
        r"^README",
        r"^\| `",
        "ausgeschlossen",
        "",
        "Tabellenzeile eines bestehenden Werkzeugs; die Tabelle bekommt neue Zeilen, diese bleibt",
    ),
    Rule(
        r"^README",
        r"[Mm]ail|Anhang|pi\u00e8ce|private chunk|chunk assembly|Bl\u00f6cke|blocs",
        "ausgeschlossen",
        "",
        "Mail oder Datei-Upload, kein Aufgaben-Zugriff",
    ),
    Rule(r"^README", r"DELETE", "zusage-doku", "DELETE", "Phase 34"),
    Rule(
        r"^README",
        r"overwriting|\u00dcberschreiben|\u00e9crasement",
        "zusage-doku",
        "PUT",
        "Phase 34",
    ),
    Rule(
        r"^README",
        r"moving|renaming|Verschieben|Umbenennen|d\u00e9placement|renommage",
        "zusage-doku",
        "MOVE",
        "Phase 34",
    ),
    Rule(
        r"^README",
        r"create-only\*\*|test_no_destructive_calls|destructive call|destruktiven|"
        r"destructif|ne supprime jamais|modifies or removes",
        "zusage-doku",
        _ALL,
        "Phase 34",
    ),
    Rule(r"^README", r"", "ausgeschlossen", "", _OTHER),
    # --- docs ---
    Rule(
        r"^docs/(hardening|threat-model|privacy|faq)",
        r"jamais (voir|un|avec)|kein-ki|[Mm]ail|"
        r"message|volume|encryption key|app data|its data|the record|trifecta|chunks|"
        r"RETENTION|draft|flags",
        "ausgeschlossen",
        "",
        "Mail, Deinstallation, Audit-Protokoll oder anderes Thema, kein Aufgaben-Zugriff",
    ),
    Rule(r"^docs/(hardening|threat-model|privacy|faq)", r"", "zusage-doku", _ALL, "Phase 34"),
    Rule(r"^docs/n8n-setup\.md$", r"delete", "zusage-doku", "DELETE", "Phase 34"),
    Rule(r"^docs/conference-", r"no delete|No delete", "zusage-doku", "MOVE,DELETE", "Phase 34"),
    Rule(r"^docs/exapp-install\.md$", r"Read and create", "zusage-doku", _ALL, "Phase 34"),
    Rule(r"^docs/client-setup\.md$", r"Nothing here deletes", "zusage-doku", _ALL, "Phase 34"),
    Rule(r"^docs/", r"", "ausgeschlossen", "", _REPORT),
)


def _files(root: Path, globs: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in globs:
        found.extend(
            path
            for path in sorted(root.glob(pattern))
            if path.is_file() and "__pycache__" not in path.parts
        )
    return found


def search(
    root: Path, globs: Iterable[str], pattern: re.Pattern[str]
) -> list[tuple[str, int, str]]:
    """``(file, line number, stripped line)`` for every line ``pattern`` finds below ``root``."""
    hits = []
    for path in _files(root, globs):
        relative = path.relative_to(root).as_posix()
        if relative in INVENTORY_SKIP:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                hits.append((relative, number, line.strip()))
    return hits


def inventory_hits(root: Path) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """The hits of pattern 1 and of pattern 2, two searches that share no search term."""
    first = search(
        root, (*PUBLIC_TEXTS, "src/mcp_connector/server/**/*.py", GATE_FILE), PROMISE_WORDS
    )
    second = [
        *search(root, ("tests/**/*.py", "src/**/*.py"), GATE_NAMES),
        *search(root, ("src/mcp_connector/nextcloud/clients/*.py",), METHOD_LITERALS),
        *search(root, ("tests/**/*.py",), TEST_NAMES),
        *search(root, PUBLIC_TEXTS, HTTP_WORDS),
    ]
    return first, second


def merge_hits(
    first: Iterable[tuple[str, int, str]], second: Iterable[tuple[str, int, str]]
) -> list[Hit]:
    """Both hit lists as one, sorted; a line both patterns found carries ``1+2``."""
    found: dict[tuple[str, int], tuple[str, set[str]]] = {}
    for label, hits in (("1", first), ("2", second)):
        for file, line, text in hits:
            found.setdefault((file, line), (text, set()))[1].add(label)
    return [
        Hit(file, line, text, "+".join(sorted(labels)))
        for (file, line), (text, labels) in sorted(found.items())
    ]


def classify(hit: Hit, rules: Sequence[Rule]) -> tuple[str, str, str]:
    """``(klasse, methods, target)`` of the first matching rule, else ``ungeklaert``."""
    for rule in rules:
        if re.search(rule.path, hit.file) and re.search(rule.text, hit.text):
            return rule.klasse, rule.methods, rule.target
    return "ungeklaert", "", ""


def inventory_line(hit: Hit, verdict: tuple[str, str, str]) -> str:
    """One line of ``raw/inventar.txt`` for a kept or an excluded hit."""
    klasse, methods, target = verdict
    head = f"INVENTAR {klasse} {hit.file}:{hit.line} | {hit.text[:200]} | "
    if klasse == "ausgeschlossen":
        return f"{head}grund={target} | muster={hit.patterns}"
    return f"{head}beruehrt_von={methods} | abzuarbeiten_in={target} | muster={hit.patterns}"


def gate_anchors(root: Path) -> dict[str, list[int]]:
    """The line numbers of the two gate constants in the destructive gate."""
    anchors: dict[str, list[int]] = {"EXPECTED_PUT_CALLS": [], "FORBIDDEN": []}
    path = root / GATE_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    for number, line in enumerate(lines, start=1):
        for name, numbers in anchors.items():
            if re.search(rf"\b{name}\b", line):
                numbers.append(number)
    return anchors


def positive_control(
    hits: Iterable[tuple[str, int, str]], anchors: Mapping[str, Sequence[int]]
) -> list[str]:
    """Which of the six researched places the hits of pattern 1 reach, in the fixed order.

    Pattern 1 searches wording, so it cannot name a constant. A gate constant counts as
    reached if a hit of pattern 1 stands in the gate file within ``CONTROL_REACH`` lines of
    it: the sentence that says what the constant guards.
    """
    found = set()
    for file, line, text in hits:
        if file == GATE_FILE:
            for name, numbers in anchors.items():
                if any(abs(line - number) <= CONTROL_REACH for number in numbers):
                    found.add(name)
        elif file == "README.md" and "create-only" in text:
            found.add("README-Rechtetabelle")
        elif file == "docs/threat-model.md":
            found.add("threat-model")
        elif file == "appinfo/info.xml" and "destructive" in text.lower():
            found.add("Store-Text")
        elif file == "src/mcp_connector/server/__init__.py" and "never deleted" in text:
            found.add("Server-Instruktion")
    return [place for place in CONTROL_PLACES if place in found]


E15_NAMES = re.compile(r"NC_MCP_FILES_UPDATE|files_update_enabled|ENV_FILES_UPDATE")


def block_inventory() -> int:
    """A17: every gate and every promise an overwriting PUT, a MOVE and a DELETE touch."""
    section("inventory")
    commit = run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], check=False).strip()
    dirty = run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "status",
            "--porcelain",
            "--",
            "src",
            "tests",
            "appinfo",
            "README.md",
            "README.de.md",
            "README.fr.md",
            "docs",
            "CHANGELOG.md",
            ".planning/PROJECT.md",
        ],
        check=False,
    ).strip()
    note(f"INVENTAR commit={commit} (die Zeilennummern gelten auf diesem Commit)")
    note(
        "INVENTAR arbeitsbaum_abweichend="
        f"{[line for line in dirty.splitlines() if 'spike-tasks.md' not in line] or 'nein'} "
        f"ausgelassen={list(INVENTORY_SKIP)} (der Bericht dieser Phase zitiert die Zusagen selbst)"
    )
    first, second = inventory_hits(REPO_ROOT)
    reached = positive_control(first, gate_anchors(REPO_ROOT))
    note(f"INVENTAR MUSTER 1 treffer={len(first)} | MUSTER 2 treffer={len(second)}")
    note(
        f"INVENTAR POSITIVKONTROLLE gefunden={len(reached)}/{len(CONTROL_PLACES)} "
        f"stellen={reached} fehlend={[p for p in CONTROL_PLACES if p not in reached] or 'keine'}"
    )
    merged = merge_hits(first, second)
    verdicts = [(hit, classify(hit, INVENTORY_RULES)) for hit in merged]
    order = (
        "gate",
        "annotation",
        "audit",
        "kanarie",
        "zusage-server",
        "zusage-store",
        "zusage-doku",
        "ungeklaert",
        "ausgeschlossen",
    )
    for klasse in order:
        for hit, verdict in verdicts:
            if verdict[0] == klasse:
                note(inventory_line(hit, verdict))
    counts = {klasse: sum(1 for _, v in verdicts if v[0] == klasse) for klasse in order}
    only_second = [
        hit for hit, verdict in verdicts if hit.patterns == "2" and verdict[0] != "ausgeschlossen"
    ]
    note(f"INVENTAR SUMME treffer={len(merged)} {' '.join(f'{k}={n}' for k, n in counts.items())}")
    note(
        f"INVENTAR GEGENPROBE nur_muster_2_im_inventar={len(only_second)} "
        "(Stellen, die Muster 1 nicht fand und die trotzdem im Inventar stehen)"
    )
    section("inventory e15")
    chain = search(
        REPO_ROOT, ("src/**/*.py", "appinfo/info.xml", "scripts/*.sh", "compose*.yml"), E15_NAMES
    )
    for file, line, text in chain:
        note(f"E15-KETTE {file}:{line} | {text[:160]}")
    tests: dict[str, int] = {}
    for file, _, _ in search(REPO_ROOT, ("tests/**/*.py",), E15_NAMES):
        tests[file] = tests.get(file, 0) + 1
    for file, count in sorted(tests.items()):
        note(f"E15-KETTE-TEST {file} treffer={count}")
    public = search(REPO_ROOT, PUBLIC_TEXTS, E15_NAMES)
    note(
        f"E15-KETTE SUMME quelltext={len(chain)} testdateien={len(tests)} "
        f"testtreffer={sum(tests.values())} oeffentliche_texte={len(public)} "
        f"dateien_oeffentlich={sorted({file for file, _, _ in public})}"
    )
    return 1 if counts["ungeklaert"] or len(reached) != len(CONTROL_PLACES) else 0


# --- plan 30-03: moving and deleting (MESS-06) -------------------------------------------------

LIST_EVENTS = f"{PREFIX}-nur-termine"
DECK_BOARD = f"{PREFIX}-board"
DECK_PREFIX = "app-generated--deck--board-"
DAV_CALENDARS = "/remote.php/dav/calendars/"
#: How a state of ``child_fate`` names the trash bin of the calendar.
TRASH = "trashbin"
#: The protocol of the browser session of plan 30-02; ui-evaluate-move reads its lines.
UI_PROTOCOL = "ui-sitzung.txt"

#: Where the dav app lies in a running instance, and what has to be confirmed there before
#: any path or switch of the calendar trash bin is used: file and the pattern of its lines.
SOURCE_DIR = "/var/www/html/apps/dav/lib"
SOURCE_CHECKS: tuple[tuple[str, str], ...] = (
    ("CalDAV/RetentionService.php", r"RETENTION_CONFIG_KEY =|DEFAULT_RETENTION_SECONDS ="),
    ("CalDAV/Trashbin/TrashbinHome.php", r"const NAME"),
    (
        "CalDAV/Trashbin/DeletedCalendarObjectsCollection.php",
        r"const NAME|function calendarQuery|new NotImplemented",
    ),
    ("CalDAV/Trashbin/RestoreTarget.php", r"const NAME|function moveInto"),
    (
        "CalDAV/Trashbin/Plugin.php",
        r"PROPERTY_RETENTION_DURATION =|X-NC-CalDAV-No-Trashbin|nc-calendar-trashbin",
    ),
    (
        "CalDAV/CalDavBackend.php",
        (
            r"function deleteCalendarObject|function restoreCalendarObject"
            r"|function moveCalendarObject|RETENTION_CONFIG_KEY\) === "
        ),
    ),
    ("CalDAV/CalendarHome.php", r"new TrashbinHome"),
    ("Command/RetentionCleanupCommand.php", r"parent::__construct\("),
)

#: Every row of the table calendarobjects that carries one UID, with its place, its trash
#: mark and the hash of its text. The UID is the key because the server renames the object
#: on its way into the trash bin (``<name>-deleted.ics``) and a MOVE may rename it too.
PHP_OBJECT_ROWS = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->select('o.uri', 'o.deleted_at', 'o.calendardata')
    ->selectAlias('c.uri', 'calendar')
    ->selectAlias('c.principaluri', 'principal')
    ->from('calendarobjects', 'o')
    ->join('o', 'calendars', 'c', $qb->expr()->eq('o.calendarid', 'c.id'))
    ->where($qb->expr()->eq('o.uid', $qb->createNamedParameter($argv[1])))
    ->andWhere($qb->expr()->eq('o.calendartype', $qb->createNamedParameter(0)))
    ->orderBy('o.id');
$out = [];
foreach ($qb->executeQuery()->fetchAll() as $row) {
    $data = $row['calendardata'];
    if (is_resource($data)) {
        $data = stream_get_contents($data);
    }
    $out[] = basename($row['principal']) . '/' . $row['calendar'] . '/' . $row['uri']
        . '|' . ($row['deleted_at'] === null ? 'leer' : 'gesetzt')
        . '|' . hash('sha256', (string)$data) . ':' . strlen((string)$data);
}
echo count($out), ' ', implode(' ', $out), "\n";
"""
)

#: Deck boards whose title carries the spike prefix, deleted ones included.
PHP_COUNT_DECK_BOARDS = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
try {
    $qb = $db->getQueryBuilder();
    $qb->select($qb->func()->count('*', 'n'))->from('deck_boards')
        ->where($qb->expr()->like('title', $qb->createNamedParameter($argv[1] . '%')));
    echo $qb->executeQuery()->fetchOne(), "\n";
} catch (\Throwable $e) {
    echo 'keine-tabelle', "\n";
}
"""
)

#: One MOVE from inside the ExApp container, the exact production way (http://caddy). The
#: Destination header is built on the base the container itself talks to. Prints the status.
EXAPP_MOVE_PROGRAM = r"""
import base64, os, sys
import httpx

user, source, target = sys.argv[1], sys.argv[2], sys.argv[3]
token = base64.b64encode(("%s:%s" % (user, os.environ["APP_SECRET"])).encode()).decode()
headers = {
    "AA-VERSION": os.environ.get("AA_VERSION", ""),
    "EX-APP-ID": os.environ.get("APP_ID", ""),
    "EX-APP-VERSION": os.environ.get("APP_VERSION", ""),
    "AUTHORIZATION-APP-API": token,
    "Overwrite": "F",
}
base = os.environ.get("NEXTCLOUD_URL", "http://caddy").rstrip("/")
headers["Destination"] = base + target
response = httpx.request("MOVE", base + source, headers=headers, timeout=60.0)
print(response.status_code)
"""


def abort_move(
    *,
    status: int,
    source_gone: bool,
    target_readable: bool,
    uid_same: bool,
    content_same: bool = True,
) -> tuple[bool, str]:
    """The abort criterion of MESS-06 for ``MOVE``: ``(triggered, reason)``.

    Not triggered only if the MOVE from an own list into an own list answered 201 or 204,
    the source is gone afterwards, the target can be read, and UID and content are the same.
    """
    reasons = []
    if status not in (201, 204):
        reasons.append(f"MOVE lieferte {status} statt 201 oder 204")
    if not source_gone:
        reasons.append("die Quelle ist nach dem MOVE noch da")
    if not target_readable:
        reasons.append("das Ziel ist nach dem MOVE nicht lesbar")
    if not uid_same:
        reasons.append("die UID am Ziel ist eine andere")
    if not content_same:
        reasons.append("der Inhalt am Ziel ist ein anderer")
    return (bool(reasons), "; ".join(reasons) or "keiner")


def destination_header(base_url: str, user: str, calendar: str, name: str) -> str:
    """The value of the ``Destination`` header for one object of a calendar of ``user``."""
    return (
        f"{base_url.rstrip('/')}{DAV_CALENDARS}{quote(user, safe='')}/"
        f"{quote(calendar, safe='')}/{quote(name, safe='')}"
    )


def uid_of(text: str) -> str:
    """The UID of the VTODO of a calendar text; a text without a VTODO is refused."""
    match = re.search(r"(?ms)^BEGIN:VTODO$(.*?)^END:VTODO$", unfold(text))
    if match is None:
        raise ValueError("the text carries no VTODO")
    uid = re.search(r"(?m)^UID(?:;[^:\n]*)?:(.*)$", match[1])
    if uid is None:
        raise ValueError("the VTODO carries no UID")
    return uid[1].strip()


@dataclass(frozen=True, slots=True)
class Placed:
    """One object of a state: the collection it lies in and its text."""

    collection: str
    text: str


def child_fate(
    before: Mapping[str, Placed],
    after: Mapping[str, Placed],
    parent_summary: str,
    child_summary: str,
) -> str:
    """What became of a sub task between two states, both keyed by UID.

    ``kind bleibt in quelle``, ``kind zieht mit``, ``kind geloescht`` or ``kind im
    papierkorb``. A state a without the parent or the sub task is refused: the evaluation
    then has nothing to stand on and writes an ``ungemessen`` line instead.
    """
    by_name = {property_value(item.text, "SUMMARY"): uid for uid, item in before.items()}
    for wanted in (parent_summary, child_summary):
        if wanted not in by_name:
            raise ValueError(f"state a carries no object named {wanted}")
    parent_uid, child_uid = by_name[parent_summary], by_name[child_summary]
    if child_uid not in after:
        return "kind geloescht"
    child = after[child_uid]
    if child.collection == TRASH:
        return "kind im papierkorb"
    if child.collection == before[child_uid].collection:
        return "kind bleibt in quelle"
    parent = after.get(parent_uid)
    if parent is not None and parent.collection == child.collection:
        return "kind zieht mit"
    return f"kind in {child.collection}"


@dataclass(frozen=True, slots=True)
class DbRow:
    """One row of calendarobjects for a UID: owner, calendar, object name, trash mark, hash."""

    owner: str
    calendar: str
    uri: str
    deleted: bool
    digest: str


def parse_db_rows(line: str) -> list[DbRow]:
    """The rows ``PHP_OBJECT_ROWS`` printed: ``<n> <owner>/<calendar>/<uri>|<mark>|<hash>``."""
    rows = []
    for entry in line.split()[1:]:
        place, mark, digest = entry.split("|")
        owner, calendar, uri = place.split("/", 2)
        rows.append(DbRow(owner, calendar, uri, mark == "gesetzt", digest))
    return rows


def db_rows(uid: str, container: str = NC_CONTAINER) -> list[DbRow]:
    """Where the database holds the object with this UID; the counter probe that asks no DAV."""
    return parse_db_rows(php(container, PHP_OBJECT_ROWS, uid))


def rows_text(rows: Sequence[DbRow]) -> str:
    """Database rows as one protocol value, ``keine`` for none."""
    return (
        ",".join(
            f"{row.owner}/{row.calendar}/{row.uri}:"
            f"{'deleted_at_gesetzt' if row.deleted else 'deleted_at_leer'}:{row.digest[:12]}"
            for row in rows
        )
        or "keine"
    )


@dataclass(frozen=True, slots=True)
class TrashSource:
    """What the source of the running instance says about the calendar trash bin."""

    key: str
    default_seconds: int
    off_value: str
    home: str
    objects: str
    restore: str
    retention_property: str
    cleanup: str


#: What documentation and research expected; a version that reads differently is a finding.
EXPECTED_SOURCE = TrashSource(
    key="calendarRetentionObligation",
    default_seconds=2592000,
    off_value="0",
    home="trashbin",
    objects="objects",
    restore="restore",
    retention_property="{http://nextcloud.com/ns}trash-bin-retention-duration",
    cleanup="dav:retention:clean-up",
)


def parse_trash_source(found: Mapping[str, Sequence[str]]) -> TrashSource:
    """Key, default, paths and clean-up command out of the grepped source lines per file.

    Raises ``ValueError`` naming what could not be read: without the confirmation no path
    and no switch is used.
    """

    def pick(file: str, pattern: str) -> str:
        for line in found.get(file, ()):
            match = re.search(pattern, line)
            if match:
                return match[1]
        raise ValueError(f"{file}: no line matches {pattern}")

    product = pick("CalDAV/RetentionService.php", r"DEFAULT_RETENTION_SECONDS = ([0-9* ]+);")
    seconds = 1
    for factor in product.split("*"):
        seconds *= int(factor)
    return TrashSource(
        key=pick("CalDAV/RetentionService.php", r"RETENTION_CONFIG_KEY = '(\w+)'"),
        default_seconds=seconds,
        off_value=pick("CalDAV/CalDavBackend.php", r"RETENTION_CONFIG_KEY\) === '([^']*)'"),
        home=pick("CalDAV/Trashbin/TrashbinHome.php", r"const NAME = '(\w+)'"),
        objects=pick(
            "CalDAV/Trashbin/DeletedCalendarObjectsCollection.php", r"const NAME = '(\w+)'"
        ),
        restore=pick("CalDAV/Trashbin/RestoreTarget.php", r"const NAME = '(\w+)'"),
        retention_property=pick(
            "CalDAV/Trashbin/Plugin.php", r"PROPERTY_RETENTION_DURATION = '([^']+)'"
        ),
        cleanup=pick("Command/RetentionCleanupCommand.php", r"parent::__construct\('([^']+)'\)"),
    )


def confirm_sources(container: str) -> TrashSource:
    """Grep the trash bin sources of the running instance and write them as QUELLE lines."""
    found: dict[str, list[str]] = {}
    for file, pattern in SOURCE_CHECKS:
        output = docker(
            "exec", container, "grep", "-nE", pattern, f"{SOURCE_DIR}/{file}", check=False
        )
        found[file] = [line.strip() for line in output.splitlines() if line.strip()]
        for line in found[file]:
            number, _, wording = line.partition(":")
            note(f"QUELLE apps/dav/lib/{file}:{number} | {_one_line(wording)[:220]}")
        if not found[file]:
            note(f"QUELLE apps/dav/lib/{file} | (keine Zeile zum Muster {pattern})")
    try:
        source = parse_trash_source(found)
    except ValueError as failure:
        raise RunFailed(f"trash bin source not confirmed: {failure}") from failure
    listed = occ(container, "list", "dav", check=False)
    commands = [line.split()[0] for line in listed.splitlines() if "retention" in line]
    note(f"QUELLE occ list dav | {' '.join(commands) or '(kein Kommando mit retention)'}")
    if source.cleanup not in commands:
        raise RunFailed(f"occ list dav does not name {source.cleanup}")
    for name in TrashSource.__slots__:
        got, expected = getattr(source, name), getattr(EXPECTED_SOURCE, name)
        if got != expected:
            note(f"QUELLE ABWEICHUNG {name} gelesen={got} erwartet={expected}")
    note(
        f"QUELLE BESTAETIGT schluessel={source.key} standard_sekunden={source.default_seconds} "
        f"aus_wert={source.off_value} sammlung={source.home}/{source.objects} "
        f"wiederherstellung=Verschieben nach {source.home}/{source.restore}/<name> "
        f"eigenschaft={source.retention_property} aufraeumen=occ {source.cleanup}"
    )
    return source


def trash_url(creds: Credentials, source: TrashSource, tail: str = "") -> str:
    """The URL of the calendar trash bin of the account of ``creds``, or of ``tail`` in it."""
    return f"{caldav.calendars_home_url(creds)}{source.home}/{tail}"


async def trash_names(session: Session, creds: Credentials, source: TrashSource) -> dict[str, str]:
    """UID to object name for the trash bin of one account, read with a REPORT.

    The collection answers a PROPFIND with 501 (measured in plan 30-02); it implements the
    calendar-query REPORT only and names every object ``<id>.ics``.
    """
    status, rows = await report(
        session,
        creds,
        "",
        report_body("calendar-query"),
        url=trash_url(creds, source, f"{source.objects}/"),
    )
    if status != 207:
        raise RunFailed(f"REPORT on the trash bin of {creds.user} answered {status}")
    return {property_value(data, "UID"): name for name, _, data in rows}


async def restore_object(
    session: Session, creds: Credentials, source: TrashSource, name: str
) -> DavResult:
    """Restore one trash bin entry: a MOVE onto the restore target, as the source reads."""
    return await dav_request(
        session.client,
        creds,
        "MOVE",
        trash_url(creds, source, f"{source.objects}/{quote(name, safe='')}"),
        extra_headers={"Destination": trash_url(creds, source, f"{source.restore}/file")},
    )


@dataclass(frozen=True, slots=True)
class MoveOutcome:
    """One measured MOVE: the answer and what source and target say afterwards."""

    result: DavResult
    source_after: int
    target_after: int
    uid_same: str
    content_same: bool
    etag_before: str
    etag_after: str

    def values(self) -> tuple[int, int, int, str, bool]:
        """What two ways in are compared by."""
        return (
            self.result.status,
            self.source_after,
            self.target_after,
            self.uid_same,
            self.content_same,
        )


async def measure_move(
    session: Session,
    creds: Credentials,
    source_url: str,
    destination: str,
    headers: Mapping[str, str] | None = None,
    *,
    target_url: str | None = None,
) -> MoveOutcome:
    """One MOVE with the given ``Destination``, read back at the source and at the target.

    ``target_url`` is where the target is read afterwards, if the header names it in another
    form than this client can ask for (a bare path, a foreign host).
    """
    _, etag0, text0 = await get_object(session, creds, source_url)
    result = await dav_request(
        session.client,
        creds,
        "MOVE",
        source_url,
        extra_headers={"Destination": destination, **(headers or {})},
    )
    source_after, _, _ = await get_object(session, creds, source_url)
    target_after, etag1, text1 = await get_object(session, creds, target_url or destination)
    uid_same = "-"
    if target_after.status == 200:
        try:
            uid_same = yes_no(uid_of(text1) == uid_of(text0))
        except ValueError:
            uid_same = "nein"
    return MoveOutcome(
        result=result,
        source_after=source_after.status,
        target_after=target_after.status,
        uid_same=uid_same,
        content_same=target_after.status == 200 and text1 == text0,
        etag_before=etag0,
        etag_after=etag1,
    )


def move_line(key: str, creds: Credentials, outcome: MoveOutcome, raw: str = "") -> None:
    """``MOVE <key> auth=.. status=.. quelle_danach=.. ziel_danach=.. uid_gleich=.. | raw``."""
    excerpt = describe_error(outcome.result.body)[:300]
    note(
        f"{now_stamp()} | MOVE {key} auth={auth_label(creds)} status={outcome.result.status} "
        f"quelle_danach={outcome.source_after} ziel_danach={outcome.target_after} "
        f"uid_gleich={outcome.uid_same} etag_vorher={short_etag(outcome.etag_before)} "
        f"etag_nachher={short_etag(outcome.etag_after)} | "
        f"inhalt_gleich={yes_no(outcome.content_same)} {raw} {excerpt}".rstrip()
    )


async def put_new(session: Session, creds: Credentials, uri: str, name: str, text: str) -> str:
    """A create-only PUT under a given name, written as a SETUP line; returns the URL."""
    url = caldav.object_url(creds, uri, name)
    made = await put_object(session, creds, url, text, if_none_match="*")
    note(
        f"{now_stamp()} | SETUP PUT create-only {uri}/{name} nutzer={creds.user} "
        f"auth={auth_label(creds)} status={made.status} | {describe_error(made.body)[:200]}"
    )
    if made.status not in (201, 204):
        raise RunFailed(f"create-only PUT of {name} answered {made.status}")
    return url


@dataclass
class Move:
    """The state of one move block: session, names of this run, targets, confirmed source."""

    session: Session
    stamp: str
    source: TrashSource
    shared: dict[str, str] = field(default_factory=dict)
    deck_uri: str = ""
    board_id: str = ""

    def name(self, key: str) -> str:
        """The object name of this run for ``key``; the UID is the name without ``.ics``."""
        return f"s30-{key}-{self.stamp}.ics"

    async def put(self, creds: Credentials, uri: str, name: str, text: str) -> str:
        """A create-only PUT under a given name in a list of this run; returns the URL."""
        return await put_new(self.session, creds, uri, name, text)

    async def todo(self, creds: Credentials, uri: str, key: str, extra: Iterable[str] = ()) -> str:
        """A plain task named after ``key`` in the list ``uri``; returns its URL."""
        name = self.name(key)
        text = simple_todo(name.removesuffix(".ics"), f"s30 {key}", extra)
        return await self.put(creds, uri, name, text)

    def target(self, uri: str, key: str) -> str:
        """The Destination for the object of ``key`` in a list of USER_A, same object name."""
        return destination_header(_base_url(self.session.env), USER_A, uri, self.name(key))


async def deck_board(state: Move) -> None:
    """A Deck board of USER_A over the REST interface, and its calendar in the discovery."""
    session = state.session
    creds = session.basic(USER_A)
    response = await session.client.post(
        f"{creds.base_url}/index.php/apps/deck/api/v1.0/boards",
        json={"title": DECK_BOARD, "color": "0082c9"},
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=creds.auth(),
    )
    try:
        data = response.json()
    except ValueError:
        data = {}
    state.board_id = str(data.get("id") or "") if isinstance(data, dict) else ""
    note(
        f"{now_stamp()} | SETUP DECK POST /index.php/apps/deck/api/v1.0/boards titel={DECK_BOARD} "
        f"nutzer={USER_A} auth=basic status={response.status_code} board_id="
        f"{state.board_id or '-'}"
    )
    appapi = session.appapi(USER_A)
    home = await dav_request(
        session.client,
        appapi,
        "PROPFIND",
        caldav.calendars_home_url(appapi),
        depth="1",
        body=caldav.build_discovery_body(),
    )
    found = calendar_collections(home.body) if home.status == 207 else []
    for uri, name, comps in found:
        note(f"  DISCOVERY liste={uri} name={name} komponenten={','.join(comps)}")
    wanted = f"{DECK_PREFIX}{state.board_id}"
    state.deck_uri = next((uri for uri, _, _ in found if state.board_id and uri == wanted), "")
    note(
        f"DECK-KALENDER in_der_discovery={yes_no(bool(state.deck_uri))} uri={state.deck_uri or '-'}"
    )


async def move_setup(state: Move) -> None:
    """The lists of the modify block, a calendar for events only, and a Deck board."""
    session = state.session
    state.shared = await modify_setup(Modify(session=session, stamp=state.stamp))
    creds = session.appapi(USER_A)
    made = await dav_request(
        session.client,
        creds,
        "MKCALENDAR",
        caldav.calendar_url(creds, LIST_EVENTS),
        body=mkcalendar_body(LIST_EVENTS, ("VEVENT",)),
    )
    note(
        f"{now_stamp()} | SETUP MKCALENDAR liste={LIST_EVENTS} nutzer={USER_A} auth=appapi "
        f"status={made.status} komponenten=VEVENT"
    )
    await guarded("move deck-board", deck_board(state))


async def move_own(state: Move) -> None:
    """M4.1, the abort measurement: MOVE from an own list into an own list."""
    session = state.session
    creds = session.appapi(USER_A)
    name = state.name("eigen")
    uid = name.removesuffix(".ics")
    text = build_probe_todo(uid, "s30 eigen")
    source_url = await state.put(creds, LIST_A, name, text)
    since = container_now()
    await asyncio.sleep(1)
    outcome = await measure_move(session, creds, source_url, state.target(LIST_B, "eigen"))
    move_line("eigen", creds, outcome)
    aborted, reason = abort_move(
        status=outcome.result.status,
        source_gone=outcome.source_after == 404,
        target_readable=outcome.target_after == 200,
        uid_same=outcome.uid_same == "ja",
        content_same=outcome.content_same,
    )
    note(f"ABBRUCHKRITERIUM MESS-06 MOVE ausgeloest={yes_no(aborted)} grund={reason}")
    note(
        f"  Aufruf: Methode wie in der Zeile darueber, Quelle {source_url[len(creds.base_url) :]}"
        f", Destination {state.target(LIST_B, 'eigen')}, keine weitere Kopfzeile"
    )
    note_raw(outcome.result)
    lines = impersonation_lines(since, USER_A, "MOVE")
    note(f"KONTROLLE exapp_impersonation.log, Zeilen der Methode von {USER_A}: {len(lines)}")
    for line in lines[-2:]:
        note(f"  {line[:400]}")
    basic = session.basic(USER_A)
    in_source = name in await object_names(session, basic, LIST_A)
    in_target = name in await object_names(session, basic, LIST_B)
    rows = db_rows(uid)
    note(
        f"{now_stamp()} | GEGENPROBE eigen auflistung REPORT calendar-query auth=basic "
        f"nutzer={USER_A} in_{LIST_A}={yes_no(in_source)} in_{LIST_B}={yes_no(in_target)} | "
        f"datenbank={rows_text(rows)} db_gleich_gesendet="
        f"{yes_no(len(rows) == 1 and rows[0].digest == sha_of(text))}"
    )

    wrong_url = await state.todo(creds, LIST_A, "eigen-falsches-secret")
    wrong_uid = state.name("eigen-falsches-secret").removesuffix(".ics")
    wrong = await dav_request(
        session.client,
        session.appapi(USER_A, "0" * 64),
        "MOVE",
        wrong_url,
        extra_headers={"Destination": state.target(LIST_B, "eigen-falsches-secret")},
    )
    note(
        f"{now_stamp()} | GEGENPROBE eigen falsches-secret status={wrong.status} "
        f"datenbank={rows_text(db_rows(wrong_uid))} | {describe_error(wrong.body)[:200]}"
    )

    basic_name = state.name("eigen-basic")
    basic_url = await state.put(
        basic,
        LIST_A,
        basic_name,
        build_probe_todo(basic_name.removesuffix(".ics"), "s30 eigen basic"),
    )
    other = await measure_move(session, basic, basic_url, state.target(LIST_B, "eigen-basic"))
    move_line("eigen", basic, other)
    note_raw(other.result)
    note(
        f"MOVE GLEICH appapi_basic={yes_no(outcome.values() == other.values())} "
        f"appapi={outcome.values()} basic={other.values()} (status, quelle danach, ziel danach, "
        "uid gleich, inhalt gleich)"
    )


def production_move(state: Move, source_path: str, target_path: str, uid: str) -> None:
    """The same MOVE from inside the ExApp container against ``http://caddy``."""
    running = docker("inspect", "--format", "{{.State.Running}}", EXAPP_CONTAINER, check=False)
    if running.strip() != "true":
        note(f"PRODUKTIONSWEG MOVE ungemessen grund=ExApp-Container {EXAPP_CONTAINER} laeuft nicht")
        return
    output = docker(
        "exec",
        "-i",
        EXAPP_CONTAINER,
        "/app/.venv/bin/python",
        "-",
        USER_A,
        source_path,
        target_path,
        stdin=EXAPP_MOVE_PROGRAM,
        check=False,
    ).strip()
    last = output.splitlines()[-1].strip() if output else ""
    if not last.isdigit():
        note(f"PRODUKTIONSWEG MOVE ungemessen grund=keine Statuszeile: {last[:200]}")
        return
    rows = db_rows(uid)
    moved = len(rows) == 1 and rows[0].calendar == LIST_B and not rows[0].deleted
    note(
        f"{now_stamp()} | PRODUKTIONSWEG MOVE status={last} verschoben={yes_no(moved)} "
        f"nutzer={USER_A} datenbank={rows_text(rows)} (aus {EXAPP_CONTAINER} gegen "
        f"http://caddy, Destination auf http://caddy, Overwrite F; lauf={state.stamp})"
    )


async def move_destination_forms(state: Move) -> None:
    """Which base ``Destination`` may carry: the production base, a bare path, a foreign host."""
    session = state.session
    creds = session.appapi(USER_A)
    base = creds.base_url
    url = await state.todo(creds, LIST_A, "produktion")
    production_move(
        state,
        url[len(base) :],
        state.target(LIST_B, "produktion")[len(base) :],
        state.name("produktion").removesuffix(".ics"),
    )
    for key, form in (("ziel-nur-pfad", ""), ("ziel-fremder-host", "http://spike30.invalid")):
        url = await state.todo(creds, LIST_A, key)
        real = state.target(LIST_B, key)
        outcome = await measure_move(
            session, creds, url, f"{form}{real[len(base) :]}", target_url=real
        )
        move_line(key, creds, outcome, f"destination_basis={form or '(keine, nur Pfad)'}")
        note_raw(outcome.result)


async def move_occupied(state: Move) -> None:
    """M4.2: a MOVE onto a name that is taken, with ``Overwrite: F`` and without the header."""
    session = state.session
    creds = session.appapi(USER_A)
    variants: tuple[tuple[str, dict[str, str]], ...] = (
        ("belegt-overwrite-f", {"Overwrite": "F"}),
        ("belegt-ohne-kopf", {}),
    )
    for key, headers in variants:
        name = state.name(key)
        uid = name.removesuffix(".ics")
        target_uid = f"{uid}-ziel"
        source_url = await state.put(creds, LIST_A, name, simple_todo(uid, f"s30 {key} quelle"))
        await state.put(creds, LIST_B, name, simple_todo(target_uid, f"s30 {key} ziel"))
        source_before, target_before = db_rows(uid), db_rows(target_uid)
        outcome = await measure_move(session, creds, source_url, state.target(LIST_B, key), headers)
        source_now, target_now = db_rows(uid), db_rows(target_uid)
        live = [row for row in target_now if not row.deleted]
        if not target_now:
            old = "endgueltig_weg"
        elif not live:
            old = "papierkorb"
        else:
            old = "unveraendert" if target_now == target_before else "veraendert"
        move_line(
            key,
            creds,
            outcome,
            f"ueberschrieben={yes_no(old != 'unveraendert')} altes_ziel={old} "
            f"quelle_unveraendert={yes_no(source_now == source_before)}",
        )
        note(
            f"  HASH ziel vorher={rows_text(target_before)} nachher={rows_text(target_now)} | "
            f"quelle vorher={rows_text(source_before)} nachher={rows_text(source_now)}"
        )
        note_raw(outcome.result)


async def move_same_uid(state: Move) -> None:
    """M4.3: the target list already holds an object with the same UID under another name."""
    session = state.session
    creds = session.appapi(USER_A)
    name = state.name("gleiche-uid")
    uid = name.removesuffix(".ics")
    source_url = await state.put(creds, LIST_A, name, simple_todo(uid, "s30 gleiche-uid quelle"))
    await state.put(
        creds, LIST_B, state.name("gleiche-uid-ziel"), simple_todo(uid, "s30 gleiche-uid ziel")
    )
    before = db_rows(uid)
    outcome = await measure_move(session, creds, source_url, state.target(LIST_B, "gleiche-uid"))
    after = db_rows(uid)
    move_line("gleiche-uid", creds, outcome, f"datenbank_unveraendert={yes_no(before == after)}")
    note(f"  DATENBANK uid={uid} vorher={rows_text(before)} nachher={rows_text(after)}")
    note_raw(outcome.result)
    basic = session.basic(USER_A)
    in_a = [n for n in await object_names(session, basic, LIST_A) if "gleiche-uid" in n]
    in_b = [n for n in await object_names(session, basic, LIST_B) if "gleiche-uid" in n]
    note(
        f"{now_stamp()} | GEGENPROBE gleiche-uid auflistung auth=basic nutzer={USER_A} "
        f"{LIST_A}={in_a} {LIST_B}={in_b}"
    )


async def move_targets(state: Move) -> None:
    """M4.4: a shared list with and without write access, a Deck calendar, events only."""
    session = state.session
    creds = session.appapi(USER_A)
    owner = session.basic(USER_B)
    no_share = "die Freigabe fehlt in der Discovery"
    targets = (
        ("geteilt-rw", state.shared.get("rw", ""), LIST_RW, no_share),
        ("geteilt-ro", state.shared.get("ro", ""), LIST_RO, no_share),
        ("deck", state.deck_uri, "", "der Deck-Kalender erscheint nicht in der Discovery"),
        ("nur-termine", LIST_EVENTS, "", ""),
    )
    for key, uri, owner_uri, reason in targets:
        if not uri:
            note(f"MOVE {key} ungemessen grund={reason} von {USER_A} (Rohzeilen DISCOVERY oben)")
            continue
        name = state.name(key)
        uid = name.removesuffix(".ics")
        source_url = await state.todo(creds, LIST_A, key)
        before = db_rows(uid)
        outcome = await measure_move(session, creds, source_url, state.target(uri, key))
        after = db_rows(uid)
        move_line(
            key,
            creds,
            outcome,
            f"ziel={uri} quelle_unveraendert={yes_no(before == after)} "
            f"datenbank_nachher={rows_text(after)}",
        )
        note_raw(outcome.result)
        if owner_uri:
            seen, _, _ = await get_object(session, owner, caldav.object_url(owner, owner_uri, name))
            note(
                f"{now_stamp()} | GEGENPROBE {key} lesen als Eigentuemer nutzer={USER_B} "
                f"auth=basic liste={owner_uri} status={seen.status}"
            )


async def move_if_match(state: Move) -> None:
    """M4.5: MOVE with ``If-Match`` on the current and on a stale ETag."""
    session = state.session
    creds = session.appapi(USER_A)
    basic = session.basic(USER_A)
    for key, stale in (("if-match-aktuell", False), ("if-match-veraltet", True)):
        name = state.name(key)
        uid = name.removesuffix(".ics")
        url = await state.todo(creds, LIST_A, key)
        _, etag, text = await get_object(session, creds, url)
        if stale:
            changed = await put_object(
                session, creds, url, set_summary(text, f"s30 {key} v1"), if_match=etag
            )
            note(
                f"{now_stamp()} | SETUP PUT aendert {name}, die gelesene ETag ist danach "
                f"veraltet status={changed.status}"
            )
        before = db_rows(uid)
        outcome = await measure_move(
            session, creds, url, state.target(LIST_B, key), {"If-Match": etag}
        )
        after = db_rows(uid)
        in_target = name in await object_names(session, basic, LIST_B)
        move_line(
            key,
            creds,
            outcome,
            f"if_match={short_etag(etag)} datenbank_unveraendert={yes_no(before == after)} "
            f"auflistung_basic_in_{LIST_B}={yes_no(in_target)}",
        )
        note_raw(outcome.result)


async def move_subtask(state: Move) -> None:
    """M4.6: what the server does to a sub task when only its parent moves or is deleted."""
    session = state.session
    creds = session.appapi(USER_A)
    for key in ("verschieben", "loeschen"):
        parent_key, child_key = f"eltern-{key}", f"kind-{key}"
        parent_uid = state.name(parent_key).removesuffix(".ics")
        child_uid = state.name(child_key).removesuffix(".ics")
        parent_url = await state.todo(creds, LIST_A, parent_key)
        child_url = await state.todo(creds, LIST_A, child_key, [f"RELATED-TO:{parent_uid}"])
        _, child_etag0, child0 = await get_object(session, creds, child_url)
        child_rows0 = db_rows(child_uid)
        if key == "verschieben":
            outcome = await measure_move(
                session, creds, parent_url, state.target(LIST_B, parent_key)
            )
            status = outcome.result.status
            done = status in (201, 204) and outcome.source_after == 404
        else:
            _, parent_etag, _ = await get_object(session, creds, parent_url)
            deleted = await dav_request(
                session.client, creds, "DELETE", parent_url, extra_headers={"If-Match": parent_etag}
            )
            status = deleted.status
            gone, _, _ = await get_object(session, creds, parent_url)
            done = status == 204 and gone.status == 404
        got, child_etag1, child1 = await get_object(session, creds, child_url)
        child_rows1 = db_rows(child_uid)
        same = (
            got.status == 200
            and child_etag0 == child_etag1
            and child0 == child1
            and child_rows0 == child_rows1
        )
        place = child_rows1[0].calendar if len(child_rows1) == 1 else rows_text(child_rows1)
        action = "verschoben" if key == "verschieben" else "geloescht"
        tail = (
            f"eltern_status={status} eltern_{action}={yes_no(done)} kind_get={got.status} "
            f"kind_etag_vorher={short_etag(child_etag0)} "
            f"kind_etag_nachher={short_etag(child_etag1)} auth=appapi nutzer={USER_A} | "
            f"datenbank kind vorher={rows_text(child_rows0)} nachher={rows_text(child_rows1)} "
            f"eltern={rows_text(db_rows(parent_uid))}"
        )
        if key == "verschieben":
            note(
                f"{now_stamp()} | UNTERAUFGABE server-verschieben ort={place} "
                f"unveraendert={yes_no(same)} {tail}"
            )
        else:
            note(
                f"{now_stamp()} | UNTERAUFGABE server-loeschen vorhanden="
                f"{yes_no(got.status == 200)} unveraendert={yes_no(same)} {tail}"
            )


async def move_delete(state: Move) -> None:
    """M4.8: DELETE under impersonation with the trash bin as delivered, and the restore."""
    session = state.session
    creds = session.appapi(USER_A)
    source = state.source
    switch = occ(NC_CONTAINER, "config:app:get", "dav", source.key, check=False)
    note(
        f"PAPIERKORB zustand={_one_line(switch) or 'leer'} (occ config:app:get dav {source.key}; "
        f"leer heisst Standard, laut Quelle {source.default_seconds} Sekunden; auf nc35 wird "
        "der Schalter nie veraendert)"
    )
    name = state.name("loeschen")
    uid = name.removesuffix(".ics")
    text = build_probe_todo(uid, "s30 loeschen")
    url = await state.put(creds, LIST_A, name, text)
    _, etag, _ = await get_object(session, creds, url)
    since = container_now()
    await asyncio.sleep(1)
    deleted = await dav_request(
        session.client, creds, "DELETE", url, extra_headers={"If-Match": etag}
    )
    gone, _, _ = await get_object(session, creds, url)
    note(
        f"{now_stamp()} | DELETE impersonation status={deleted.status} auth=appapi "
        f"nutzer={USER_A} if_match={short_etag(etag)} get_danach={gone.status} | "
        f"{describe_error(deleted.body)[:200]}"
    )
    note_raw(deleted)
    lines = impersonation_lines(since, USER_A, "DELETE")
    note(f"KONTROLLE exapp_impersonation.log, DELETE-Zeilen von {USER_A}: {len(lines)}")
    for line in lines[-2:]:
        note(f"  {line[:400]}")

    stale_uid = state.name("loeschen-veraltet").removesuffix(".ics")
    stale_url = await state.todo(creds, LIST_A, "loeschen-veraltet")
    _, etag0, text0 = await get_object(session, creds, stale_url)
    await put_object(
        session, creds, stale_url, set_summary(text0, "s30 veraltet v1"), if_match=etag0
    )
    before = db_rows(stale_uid)
    refused = await dav_request(
        session.client, creds, "DELETE", stale_url, extra_headers={"If-Match": etag0}
    )
    after = db_rows(stale_uid)
    note(
        f"{now_stamp()} | DELETE veraltet status={refused.status} "
        f"objekt_unveraendert={yes_no(before == after)} auth=appapi nutzer={USER_A} | "
        f"datenbank vorher={rows_text(before)} nachher={rows_text(after)} | "
        f"{describe_error(refused.body)[:200]}"
    )
    note_raw(refused)

    probe = await dav_request(
        session.client,
        creds,
        "PROPFIND",
        trash_url(creds, source, f"{source.objects}/"),
        depth="1",
        body=propfind_body([f"{{{xml.DAV}}}getetag"]),
    )
    note(
        f"{now_stamp()} | PAPIERKORB PROPFIND Depth 1 {source.home}/{source.objects} "
        f"status={probe.status} | {describe_error(probe.body)[:120]}"
    )
    names = await trash_names(session, creds, source)
    note(
        f"{now_stamp()} | PAPIERKORB eintrag={yes_no(uid in names)} name={names.get(uid, '-')} "
        f"eintraege={len(names)} (REPORT calendar-query, auth=appapi nutzer={USER_A}) | "
        f"GEGENPROBE datenbank={rows_text(db_rows(uid))}"
    )
    if uid not in names:
        note("WIEDERHERSTELLUNG ungemessen grund=das Objekt steht nicht im Papierkorb")
        return
    restored = await restore_object(session, creds, source, names[uid])
    back, _, text1 = await get_object(session, creds, url)
    same_uid = back.status == 200 and uid_of(text1) == uid
    note(
        f"{now_stamp()} | WIEDERHERSTELLUNG status={restored.status} "
        f"uid_gleich={yes_no(same_uid)} inhalt_gleich={yes_no(text1 == text)} "
        f"get_danach={back.status} auth=appapi nutzer={USER_A} | GEGENPROBE datenbank="
        f"{rows_text(db_rows(uid))} | {describe_error(restored.body)[:200]}"
    )
    note(
        f"  Aufruf: Verschieben von {source.home}/{source.objects}/{names[uid]} mit "
        f"Destination {source.home}/{source.restore}/file"
    )
    note_raw(restored)


async def move_teardown(state: Move) -> None:
    """Delete the Deck board and empty the calendar trash bins of the measuring accounts."""
    session = state.session
    if state.board_id:
        creds = session.basic(USER_A)
        gone = await session.client.delete(
            f"{creds.base_url}/index.php/apps/deck/api/v1.0/boards/{state.board_id}",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            auth=creds.auth(),
        )
        note(f"RUECKBAU DECK DELETE boards/{state.board_id} status={gone.status_code}")
    for user in (USER_A, USER_B):
        creds = session.basic(user)
        names = await trash_names(session, creds, state.source)
        for name in names.values():
            url = trash_url(creds, state.source, f"{state.source.objects}/{quote(name, safe='')}")
            purged = await dav_request(session.client, creds, "DELETE", url)
            note(f"RUECKBAU PAPIERKORB {user} {name} endgueltig status={purged.status}")
        note(f"RUECKBAU PAPIERKORB {user} eintraege_vorher={len(names)}")


async def block_move(session: Session) -> None:
    """MESS-06 on nc35: the abort measurement first, then every other target and DELETE."""
    section("move")
    ram_gate(NC35_CONTAINERS)
    source = confirm_sources(NC_CONTAINER)
    state = Move(session=session, stamp=datetime.now(UTC).strftime("%H%M%S"), source=source)
    try:
        await move_setup(state)
        await move_own(state)
        await guarded("move destination", move_destination_forms(state))
        await guarded("move belegt", move_occupied(state))
        await guarded("move gleiche-uid", move_same_uid(state))
        await guarded("move ziele", move_targets(state))
        await guarded("move if-match", move_if_match(state))
        await guarded("move unteraufgabe", move_subtask(state))
        await guarded("move delete", move_delete(state))
    finally:
        await guarded("move rueckbau", move_teardown(state))


def placed_state(directory: Path, lists: Mapping[str, str]) -> dict[str, Placed]:
    """A written snapshot as a state of ``child_fate``: UID to collection and text."""
    return {
        uid: Placed(TRASH if entry.trashed else lists.get(entry.file, "?"), entry.text)
        for uid, entry in load_snapshot(directory).items()
    }


def block_ui_evaluate_move() -> None:
    """M4.7: what the Tasks app did to the sub tasks, read from ``raw/ui-a`` and ``raw/ui-b``."""
    section("ui-evaluate-move")
    protocol_file = RAW_DIR / UI_PROTOCOL
    protocol = protocol_file.read_text(encoding="utf-8") if protocol_file.is_file() else ""
    files_a = {uid: entry.file for uid, entry in load_snapshot(RAW_DIR / "ui-a").items()}
    files_b = {uid: entry.file for uid, entry in load_snapshot(RAW_DIR / "ui-b").items()}
    before = placed_state(RAW_DIR / "ui-a", snapshot_lists(protocol, "a"))
    after = placed_state(RAW_DIR / "ui-b", snapshot_lists(protocol, "b"))
    note(
        f"APP AUSWERTUNG quelle=raw/ui-a ({len(before)} Objekte) und raw/ui-b ({len(after)} "
        f"Objekte), Listen aus den Zeilen UI-OBJEKT in raw/{UI_PROTOCOL}; nur gelesen, kein "
        "Aufruf gegen eine Instanz"
    )
    names = {property_value(item.text, "SUMMARY"): uid for uid, item in before.items()}

    def place(name: str) -> str:
        item = after.get(names.get(name, ""))
        return item.collection if item is not None else "fehlt"

    for label, parent, child in (
        ("APP VERSCHIEBEN", "s30 eltern-umzug", "s30 kind-umzug"),
        ("APP LOESCHEN", "s30 eltern-loeschen", "s30 kind-loeschen"),
    ):
        try:
            fate = child_fate(before, after, parent, child)
        except ValueError as failure:
            note(f"{label} eltern={parent} ungemessen grund={failure}")
            continue
        if label == "APP VERSCHIEBEN":
            note(
                f"{label} eltern={parent} kind={fate.removeprefix('kind ')} "
                f"eltern_uid_gleich={yes_no(names[parent] in after)} "
                f"eltern_ort_danach={place(parent)} kind_ort_danach={place(child)}"
            )
        else:
            note(
                f"{label} eltern={parent} kind={fate} eltern_ort_danach={place(parent)} "
                f"kind_ort_danach={place(child)}"
            )

    single = names.get("s30 umzug-einzeln")
    if single is None or single not in after:
        note("APP VERSCHIEBEN einzeln ungemessen grund=s30 umzug-einzeln fehlt in Stand a oder b")
    else:
        moved = after[single].collection != before[single].collection
        note(
            f"APP VERSCHIEBEN einzeln uid_gleich=ja dateiname_gleich="
            f"{yes_no(files_a[single] == files_b[single])} "
            f"inhalt_gleich={yes_no(before[single].text == after[single].text)} "
            f"von={before[single].collection} nach={after[single].collection} "
            f"positivkontrolle_umzug_stattgefunden={yes_no(moved)}"
        )
    control = names.get("s30 unberuehrt")
    if control is None or control not in after:
        note("KONTROLLE unberuehrt ungemessen grund=s30 unberuehrt fehlt in Stand a oder b")
    else:
        same_place = before[control].collection == after[control].collection
        note(
            f"KONTROLLE unberuehrt differenz="
            f"{field_diff(before[control].text, after[control].text)} "
            f"ort_gleich={yes_no(same_place)}"
        )
    for label, state in (("a", before), ("b", after)):
        counts: dict[str, int] = {}
        for item in state.values():
            counts[item.collection] = counts.get(item.collection, 0) + 1
        note(f"GEGENPROBE objektzahl stand={label} {json.dumps(counts, sort_keys=True)}")


# --- plan 30-03 task 2: delete matrix on throwaway instances (A18, E13) -----------------------

SPIKE_CONTAINER = "nc-spike-tags"
SPIKE_BASE_URL = "http://127.0.0.1:8083"
SPIKE_COMPOSE = "compose.spike-tags.yml"
#: The full name of its volume; it must be absent before ``up``, or the run would upgrade.
SPIKE_VOLUME = "nc-mcp-spike-tags_nc-spike-tags-data"
#: The patch releases of the store window the delete matrix measures; the version of record
#: is ``occ status`` of the running instance, never this tuple.
DELETE_TAGS = ("32.0.15-apache", "33.0.9-apache", "34.0.4-apache", "35.0.2-apache")
DELETE_MAJORS = (32, 33, 34, 35)

#: The three words plan 30-03 may end with (E13). Blanks are real blanks.
VERDICT_RESTORABLE = "wiederherstellbar"
VERDICT_LOST = "nicht wiederherstellbar"
VERDICT_UNCLEAR = "nicht eindeutig"

ALICE = "alice"
BOB = "bob"
DEL_OWN = f"{PREFIX}-eigen"
DEL_RW = f"{PREFIX}-geteilt-rw"
DEL_RO = f"{PREFIX}-geteilt-ro"
#: The DAV feature the trash bin plugin announces (read in Trashbin/Plugin.php).
TRASH_FEATURE = "nc-calendar-trashbin"
#: The candidates of the pretest (M4.12), in the order they are asked.
PRETESTS = (
    "papierkorb-propfind",
    "frist-eigenschaft",
    "frist-eigenschaft-home",
    "home-kind-trashbin",
    "capabilities-dav",
    "dav-kopf",
)
#: The sections whose positive control has to hold for ``g=ja``.
CONTROL_SECTIONS = (
    "an-eigen",
    "an-geteilt",
    "unterauftrag",
    "aus-eigen",
    "aus-geteilt",
    "vorabtest",
    "aufraeumen",
)


@dataclass(frozen=True, slots=True)
class VersionRow:
    """The collected line of one delete matrix run: version and the five values of the rule."""

    major: int
    version: str
    g: bool
    w1: bool
    w2: bool
    w3: bool
    w4: bool
    who: str


def parse_version_line(line: str) -> VersionRow:
    """``LOESCHEN VERSION <version> g=.. w1=.. w2=.. w3=.. w4=.. wer=..`` as a row.

    A value other than ``ja`` or ``nein`` is refused: a line the rule cannot read must not
    be read as a no.
    """
    match = re.match(r"LOESCHEN VERSION ((\d+)\.\S+) (.+)$", line.strip())
    if match is None:
        raise ValueError(f"not a LOESCHEN VERSION line: {line[:80]!r}")
    fields: dict[str, str] = {}
    for part in match[3].split():
        key, _, value = part.partition("=")
        fields[key] = value
    flags: dict[str, bool] = {}
    for name in ("g", "w1", "w2", "w3", "w4"):
        value = fields.get(name)
        if value not in ("ja", "nein"):
            raise ValueError(f"{name}={value!r} is neither ja nor nein")
        flags[name] = value == "ja"
    return VersionRow(
        major=int(match[2]),
        version=match[1],
        g=flags["g"],
        w1=flags["w1"],
        w2=flags["w2"],
        w3=flags["w3"],
        w4=flags["w4"],
        who=fields.get("wer", ""),
    )


def version_rows(protocol: str) -> list[VersionRow]:
    """Every collected line of one raw file, run by run.

    A run that declares itself a repeat (``WIEDERHOLUNG Grund:``, written for a tool error
    only) replaces the runs before it; without that line two runs of one version both
    count, and a contradiction between them is the rule's business.
    """
    rows: list[VersionRow] = []
    for run_text in re.split(r"(?m)^# Lauf ", protocol):
        if re.search(r"(?m)^WIEDERHOLUNG Grund:", run_text):
            rows = []
        rows.extend(
            parse_version_line(line)
            for line in run_text.splitlines()
            if line.startswith("LOESCHEN VERSION ")
        )
    return rows


def delete_verdict(rows: Iterable[VersionRow]) -> str:
    """The decision rule of plan 30-03 for deleting (E13), word for word and nothing more.

    ``wiederherstellbar``: for all four versions G and W1 and W2 and (W3 or W4).
    ``nicht wiederherstellbar``: for at least one version G holds, and W1 is no or W2 is no
    or (W3 is no and W4 is no). ``nicht eindeutig``: everything else, that is a missing or
    unmeasured version, a failed positive control, or two runs of one version that differ.
    A version outside 32 to 35 is refused.
    """
    by_major: dict[int, set[tuple[bool, bool, bool, bool, bool]]] = {}
    for row in rows:
        if row.major not in DELETE_MAJORS:
            raise ValueError(f"version {row.major} is not one of {DELETE_MAJORS}")
        by_major.setdefault(row.major, set()).add((row.g, row.w1, row.w2, row.w3, row.w4))
    settled = {major: next(iter(runs)) for major, runs in by_major.items() if len(runs) == 1}

    def good(values: tuple[bool, bool, bool, bool, bool]) -> bool:
        g, w1, w2, w3, w4 = values
        return g and w1 and w2 and (w3 or w4)

    def bad(values: tuple[bool, bool, bool, bool, bool]) -> bool:
        g, w1, w2, w3, w4 = values
        return g and (not w1 or not w2 or (not w3 and not w4))

    if all(major in settled and good(settled[major]) for major in DELETE_MAJORS):
        return VERDICT_RESTORABLE
    if any(bad(values) for values in settled.values()):
        return VERDICT_LOST
    return VERDICT_UNCLEAR


def consequence(word: str) -> str:
    """The fixed consequence of a verdict word for TMOD-07, without a question to the owner."""
    if word == VERDICT_RESTORABLE:
        return (
            "TMOD-07 ist planbar (Phase 33), mit den Auflagen aus den Messwerten: Vorab-Test "
            "vor dem L\u00f6schen, wer wiederherstellen kann, Aufbewahrungsfrist."
        )
    if word in (VERDICT_LOST, VERDICT_UNCLEAR):
        return (
            "kein L\u00f6schen in 0.8.0, ohne R\u00fcckfrage; TMOD-07 wandert nach Out of "
            "Scope, und der Store-Text nennt die Grenze (EXAPP-13)."
        )
    raise ValueError(f"{word!r} is none of the three verdict words")


def validate_delete_tag(tag: str, *, allow_other: bool = False) -> str:
    """The image tag the delete matrix may start: one of ``DELETE_TAGS``, others on request."""
    if tag in DELETE_TAGS:
        return tag
    if allow_other and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-apache", tag):
        return tag
    raise ValueError(
        f"--nc-tag {tag!r} is not one of {', '.join(DELETE_TAGS)}; "
        "another patch release needs --allow-other-tag"
    )


def _trash_keys(data: Any) -> list[Any]:
    """The values of every key that names the trash bin or a retention, at any depth."""
    found: list[Any] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if re.search(r"trash|retention", str(key), re.IGNORECASE):
                found.append(value)
            found.extend(_trash_keys(value))
    elif isinstance(data, list):
        for value in data:
            found.extend(_trash_keys(value))
    return found


def pretest_shows(name: str, value: str) -> str:
    """What one pretest candidate says about the trash bin: ``an``, ``aus`` or ``unklar``.

    The reading is fixed before the measurement: a candidate only counts if it says ``an``
    while the trash bin works and ``aus`` while it is switched off.
    """
    if name == "papierkorb-propfind":
        return {"207": "an", "404": "aus"}.get(value, "unklar")
    if name in ("frist-eigenschaft", "frist-eigenschaft-home"):
        if not value.isdigit():
            return "unklar"
        return "an" if int(value) > 0 else "aus"
    if name in ("home-kind-trashbin", "dav-kopf"):
        return {"ja": "an", "nein": "aus"}.get(value, "unklar")
    if name == "capabilities-dav":
        keys = _trash_keys(_json_or_text(value))
        if not keys:
            return "unklar"
        return "an" if all(keys) else "aus"
    return "unklar"


def pretest_distinguishing(on: Mapping[str, str], off: Mapping[str, str]) -> list[str]:
    """The candidates that are right in both states, in the order of ``PRETESTS``."""
    return [
        name
        for name in PRETESTS
        if pretest_shows(name, on.get(name, "")) == "an"
        and pretest_shows(name, off.get(name, "")) == "aus"
    ]


def compose(
    action: Sequence[str],
    compose_env: Mapping[str, str],
    *,
    check: bool = True,
    file: str = SPIKE_COMPOSE,
) -> str:
    """One ``docker compose`` call on a throwaway file; secrets only in ``compose_env``."""
    argv = ["docker", "compose", "-f", str(REPO_ROOT / file), *action]
    return run(argv, env=compose_env, check=check)


def spike_leftovers() -> tuple[str, str]:
    """The ids of a throwaway container and of its volume, empty strings when absent."""
    container = docker("ps", "-a", "--filter", f"name={SPIKE_CONTAINER}", "-q", check=False)
    volume = docker("volume", "ls", "-q", "--filter", f"name={SPIKE_VOLUME}", check=False)
    return container.strip(), volume.strip()


def delete_preconditions() -> None:
    """Never next to nc35, never two throwaway instances, never an old volume, enough RAM."""
    section("vorbedingungen")
    running = docker("ps", "--format", "{{.Names}}", check=False).split()
    standing = [name for name in running if name in NC35_CONTAINERS]
    if standing:
        raise RunFailed(f"nc35 erst stoppen: {standing} laufen noch (--block nc35-stop)")
    ram_gate(())
    container, volume = spike_leftovers()
    note(f"VORBEDINGUNG Container {SPIKE_CONTAINER} vorhanden: {yes_no(bool(container))}")
    note(f"VORBEDINGUNG Volume {SPIKE_VOLUME} vorhanden: {yes_no(bool(volume))}")
    if container or volume:
        raise RunFailed(
            f"a throwaway container or the volume {SPIKE_VOLUME} is still there; "
            "take it down with down -v first"
        )


def wait_for_http(base_url: str) -> None:
    """Wait until ``status.php`` answers 200 again after a start or a restart (120 s)."""
    deadline = time.monotonic() + 120
    status = 0
    while time.monotonic() < deadline:
        try:
            status = httpx.get(f"{base_url}/status.php", timeout=10.0).status_code
        except httpx.HTTPError:
            status = 0
        if status == 200:
            return
        time.sleep(2)
    raise RunFailed(f"{base_url}/status.php did not answer 200 within 120 s (last {status})")


async def spike_app_password(session: Session, user: str, password: str) -> str:
    """An app password on the throwaway instance; falls back to OCS where occ is broken.

    Measured in phase 25: ``occ user:auth-tokens:add`` has no ``--name`` on 32 and breaks
    with ``--password-from-env`` on 33.0.9. The fallback sends the login password in the
    basic auth header of one loopback request, never as an argument.
    """
    try:
        return new_app_password(SPIKE_CONTAINER, user, password, f"SPIKE_APP_{user}")
    except RunFailed as failure:
        note(
            f"BEFUND occ user:auth-tokens:add --name scheitert auf dieser Version "
            f"({_one_line(str(failure))[-160:]}); Rueckfall GET /ocs/v2.php/core/getapppassword"
        )
    response = await session.client.get(
        f"{SPIKE_BASE_URL}/ocs/v2.php/core/getapppassword",
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=(user, password),
    )
    try:
        token = str(response.json()["ocs"]["data"]["apppassword"])
    except (ValueError, KeyError, TypeError):
        token = ""
    if len(token) < 20:
        raise RunFailed(f"getapppassword for {user} answered {response.status_code}, no token")
    remember_secret(f"SPIKE_APP_{user}", token)
    note(f"GET /ocs/v2.php/core/getapppassword als {user} -> HTTP {response.status_code} (kept)")
    return token


@dataclass
class DeleteRun:
    """The state of one delete matrix run on one throwaway instance."""

    session: Session
    container: str
    source: TrashSource
    stamp: str
    shared: dict[str, str] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)
    controls: dict[str, bool] = field(default_factory=dict)
    unmeasured: list[str] = field(default_factory=list)
    pretests: dict[str, dict[str, str]] = field(default_factory=dict)
    permanent: dict[str, bool] = field(default_factory=dict)
    who: str = "keiner"

    def name(self, key: str) -> str:
        """The object name of this run for ``key``; the UID is the name without ``.ics``."""
        return f"s30-{key}-{self.stamp}.ics"

    def rows(self, uid: str) -> list[DbRow]:
        """The database rows of one UID on the instance of this run."""
        return db_rows(uid, self.container)


async def measured(run_: DeleteRun, name: str, work: Coroutine[Any, Any, None]) -> None:
    """One section of the matrix; a failure makes it ``ungemessen`` and costs ``g``."""
    section(name)
    try:
        await work
    except Exception as failure:
        reason = f"{type(failure).__name__}: {_one_line(str(failure))[:240]}"
        note(f"BLOCK FAILED | {name} | {reason}")
        note(f"ABSCHNITT {name} ungemessen grund={reason}")
        run_.unmeasured.append(name)


def trash_mark(rows: Sequence[DbRow]) -> str:
    """``gesetzt``, ``leer`` or ``weg``: the column deleted_at of the rows of one UID."""
    if not rows:
        return "weg"
    return "gesetzt" if all(row.deleted for row in rows) else "leer"


def has_uid(text: str, uid: str) -> bool:
    """Whether ``text`` is a calendar text whose VTODO carries ``uid``."""
    try:
        return uid_of(text) == uid
    except ValueError:
        return False


async def delete_with_etag(session: Session, creds: Credentials, url: str) -> DavResult:
    """Read the ETag and DELETE with ``If-Match`` on it, the way TMOD-07 would."""
    _, etag, _ = await get_object(session, creds, url)
    headers = {"If-Match": etag} if etag else {}
    return await dav_request(session.client, creds, "DELETE", url, extra_headers=headers)


async def make_list(run_: DeleteRun, creds: Credentials, uri: str) -> None:
    """A task list (VTODO only) of the account of ``creds``, written as a SETUP line."""
    made = await dav_request(
        run_.session.client,
        creds,
        "MKCALENDAR",
        caldav.calendar_url(creds, uri),
        body=mkcalendar_body(uri),
    )
    note(
        f"{now_stamp()} | SETUP MKCALENDAR liste={uri} nutzer={creds.user} auth=basic "
        f"status={made.status} komponenten=VTODO"
    )
    if made.status != 201:
        raise RunFailed(f"MKCALENDAR {uri} answered {made.status}")


async def retention_facts(run_: DeleteRun) -> None:
    """The configured retention and the default the source names."""
    source = run_.source
    value = _one_line(occ(run_.container, "config:app:get", "dav", source.key, check=False))
    note(
        f"FRIST konfiguriert={value or 'leer'} standard_laut_quelle={source.default_seconds} "
        f"einheit=Sekunden (occ config:app:get dav {source.key}; leer heisst Standard; Einheit "
        "gelesen aus der Konstante DEFAULT_RETENTION_SECONDS, gemessen im Abschnitt aufraeumen)"
    )


async def delete_own_on(run_: DeleteRun) -> None:
    """M4.9, W1: delete an own task with the trash bin on, find it there, restore it."""
    session, source = run_.session, run_.source
    alice = session.basic(ALICE)
    await make_list(run_, alice, DEL_OWN)
    name, other = run_.name("an-eigen"), run_.name("an-nachbar")
    uid, other_uid = name.removesuffix(".ics"), other.removesuffix(".ics")
    text = build_probe_todo(uid, "s30 an-eigen")
    url = await put_new(session, alice, DEL_OWN, name, text)
    other_url = await put_new(
        session, alice, DEL_OWN, other, simple_todo(other_uid, "s30 an-nachbar")
    )
    deleted = await delete_with_etag(session, alice, url)
    names = await trash_names(session, alice, source)
    rows = run_.rows(uid)
    in_trash = uid in names
    note(
        f"{now_stamp()} | LOESCHEN an-eigen status={deleted.status} "
        f"im_papierkorb={yes_no(in_trash)} db_deleted_at={trash_mark(rows)} | nutzer={ALICE} "
        f"auth=basic if_match=ja papierkorb_name={names.get(uid, '-')} "
        f"datenbank={rows_text(rows)} {describe_error(deleted.body)[:200]}".rstrip()
    )
    note_raw(deleted)
    alive, _, _ = await get_object(session, alice, other_url)
    control = other_uid not in names and alive.status == 200
    note(
        f"KONTROLLE an-eigen nachbar_im_papierkorb={yes_no(other_uid in names)} "
        f"nachbar_lesbar={yes_no(alive.status == 200)} gegriffen={yes_no(control)}"
    )
    run_.controls["an-eigen"] = control
    restored_ok = False
    if in_trash:
        restored = await restore_object(session, alice, source, names[uid])
        back, _, text1 = await get_object(session, alice, url)
        rows1 = run_.rows(uid)
        same_place = (
            len(rows1) == 1
            and not rows1[0].deleted
            and (rows1[0].calendar, rows1[0].uri) == (DEL_OWN, name)
            and rows1[0].digest == sha_of(text)
        )
        note(
            f"{now_stamp()} | WIEDERHERSTELLUNG an-eigen status={restored.status} "
            f"uid_gleich={yes_no(has_uid(text1, uid))} inhalt_gleich={yes_no(text1 == text)} | "
            f"get_danach={back.status} sha256_vorher={sha_of(text)[:12]} "
            f"sha256_nachher={sha_of(text1)[:12]} db_deleted_at={trash_mark(rows1)} "
            f"am_alten_ort={yes_no(same_place)} datenbank={rows_text(rows1)} "
            f"{describe_error(restored.body)[:200]}".rstrip()
        )
        note_raw(restored)
        restored_ok = (
            200 <= restored.status < 300
            and back.status == 200
            and has_uid(text1, uid)
            and text1 == text
            and same_place
        )
    else:
        note(
            "WIEDERHERSTELLUNG an-eigen status=- uid_gleich=nein inhalt_gleich=nein | nicht "
            "moeglich, das Objekt steht nicht im Papierkorb"
        )
    run_.flags["w1"] = (
        deleted.status == 204 and in_trash and trash_mark(rows) == "gesetzt" and restored_ok
    )


async def shared_setup(run_: DeleteRun) -> None:
    """Two lists of bob, shared with alice with and without write access."""
    session = run_.session
    alice, bob = session.basic(ALICE), session.basic(BOB)
    for uri, writable in ((DEL_RW, True), (DEL_RO, False)):
        await make_list(run_, bob, uri)
        shared = await dav_request(
            session.client,
            bob,
            "POST",
            caldav.calendar_url(bob, uri),
            body=share_body(ALICE, writable=writable),
        )
        note(
            f"{now_stamp()} | FREIGABE liste={uri} an={ALICE} schreibrecht={yes_no(writable)} "
            f"nutzer={BOB} auth=basic status={shared.status}"
        )
    home = await dav_request(
        session.client,
        alice,
        "PROPFIND",
        caldav.calendars_home_url(alice),
        depth="1",
        body=caldav.build_discovery_body(),
    )
    found = calendar_collections(home.body) if home.status == 207 else []
    for uri, name, comps in found:
        note(f"  DISCOVERY liste={uri} name={name} komponenten={','.join(comps)}")
    for key, uri in (("rw", DEL_RW), ("ro", DEL_RO)):
        wanted = f"{uri}_shared_by_{BOB}"
        if any(wanted == seen for seen, _, _ in found):
            run_.shared[key] = wanted
    if set(run_.shared) != {"rw", "ro"}:
        raise RunFailed(f"the shared lists are not in the discovery of {ALICE}: {run_.shared}")


async def restore_by_either(run_: DeleteRun, label: str, uid: str, text: str, url: str) -> str:
    """Try the restore as the deleting account, then as the owner; returns who managed it."""
    session, source = run_.session, run_.source
    bob = session.basic(BOB)
    for who, creds in (("loeschender", session.basic(ALICE)), ("eigentuemer", bob)):
        names = await trash_names(session, creds, source)
        if uid not in names:
            note(
                f"WIEDERHERSTELLUNG {label} versuch={who} status=- | kein Eintrag im "
                f"Papierkorb von {creds.user}"
            )
            continue
        restored = await restore_object(session, creds, source, names[uid])
        back, _, text1 = await get_object(session, bob, url)
        rows = run_.rows(uid)
        done = (
            200 <= restored.status < 300
            and back.status == 200
            and has_uid(text1, uid)
            and text1 == text
            and trash_mark(rows) == "leer"
        )
        note(
            f"{now_stamp()} | WIEDERHERSTELLUNG {label} versuch={who} status={restored.status} "
            f"uid_gleich={yes_no(has_uid(text1, uid))} inhalt_gleich={yes_no(text1 == text)} | "
            f"nutzer={creds.user} get_als_eigentuemer={back.status} "
            f"db_deleted_at={trash_mark(rows)} datenbank={rows_text(rows)} "
            f"{describe_error(restored.body)[:200]}".rstrip()
        )
        note_raw(restored)
        if done:
            return who
    return "keiner"


async def delete_shared(run_: DeleteRun, label: str, key: str) -> tuple[DavResult, str, str, str]:
    """alice deletes an object of bob's list shared with write access.

    Returns the answer, whose trash bin lists the object, the trash mark of the database
    row, and who restored it.
    """
    session, source = run_.session, run_.source
    alice, bob = session.basic(ALICE), session.basic(BOB)
    name = run_.name(key)
    uid = name.removesuffix(".ics")
    text = build_probe_todo(uid, f"s30 {key}")
    owner_url = await put_new(session, bob, DEL_RW, name, text)
    deleted = await delete_with_etag(
        session, alice, caldav.object_url(alice, run_.shared["rw"], name)
    )
    in_alice = uid in await trash_names(session, alice, source)
    in_bob = uid in await trash_names(session, bob, source)
    rows = run_.rows(uid)
    if in_alice and in_bob:
        whose = "beide"
    elif in_alice:
        whose = "loeschender"
    else:
        whose = "eigentuemer" if in_bob else "keiner"
    note(
        f"{now_stamp()} | GELOESCHT {label} status={deleted.status} nutzer={ALICE} auth=basic "
        f"if_match=ja papierkorb_von={whose} db_deleted_at={trash_mark(rows)} "
        f"datenbank={rows_text(rows)} {describe_error(deleted.body)[:200]}".rstrip()
    )
    note_raw(deleted)
    by = await restore_by_either(run_, label, uid, text, owner_url)
    return deleted, whose, trash_mark(rows), by


async def delete_shared_on(run_: DeleteRun) -> None:
    """M4.10, W2: the same on a shared list, and the refusal without write access."""
    session, source = run_.session, run_.source
    alice, bob = session.basic(ALICE), session.basic(BOB)
    await shared_setup(run_)
    deleted, whose, mark, by = await delete_shared(run_, "an-geteilt", "an-geteilt")
    note(
        f"LOESCHEN an-geteilt status={deleted.status} papierkorb_von={whose} "
        f"wiederhergestellt_durch={by} | db_deleted_at_nach_dem_loeschen={mark}"
    )
    run_.flags["w2"] = (
        deleted.status == 204 and whose != "keiner" and mark == "gesetzt" and by != "keiner"
    )
    run_.who = by
    run_.controls["an-geteilt"] = run_.flags.get("w1", False)

    # Whether the owner can restore too, on a second object the deleting account leaves alone.
    name = run_.name("an-geteilt-eigentuemer")
    uid = name.removesuffix(".ics")
    text = simple_todo(uid, "s30 an-geteilt-eigentuemer")
    owner_url = await put_new(session, bob, DEL_RW, name, text)
    second = await delete_with_etag(
        session, alice, caldav.object_url(alice, run_.shared["rw"], name)
    )
    names = await trash_names(session, bob, source)
    if uid in names:
        restored = await restore_object(session, bob, source, names[uid])
        back, _, text1 = await get_object(session, bob, owner_url)
        note(
            f"{now_stamp()} | WIEDERHERSTELLUNG an-geteilt-eigentuemer status={restored.status} "
            f"uid_gleich={yes_no(has_uid(text1, uid))} inhalt_gleich={yes_no(text1 == text)} | "
            f"geloescht_von={ALICE} ({second.status}) wiederhergestellt_von={BOB} "
            f"get_danach={back.status} datenbank={rows_text(run_.rows(uid))}"
        )
    else:
        note(
            f"WIEDERHERSTELLUNG an-geteilt-eigentuemer status=- | geloescht_von={ALICE} "
            f"({second.status}), kein Eintrag im Papierkorb von {BOB}; datenbank="
            f"{rows_text(run_.rows(uid))}"
        )

    ro_name = run_.name("an-geteilt-ro")
    ro_uid = ro_name.removesuffix(".ics")
    await put_new(session, bob, DEL_RO, ro_name, simple_todo(ro_uid, "s30 an-geteilt-ro"))
    before = run_.rows(ro_uid)
    ro_url = caldav.object_url(alice, run_.shared["ro"], ro_name)
    seen, _, _ = await get_object(session, alice, ro_url)
    refused = await delete_with_etag(session, alice, ro_url)
    after = run_.rows(ro_uid)
    note(
        f"{now_stamp()} | LOESCHEN an-geteilt-ro status={refused.status} "
        f"objekt_unveraendert={yes_no(before == after)} | nutzer={ALICE} auth=basic "
        f"lesen_vorher={seen.status} datenbank={rows_text(after)} "
        f"{describe_error(refused.body)[:200]}".rstrip()
    )
    note_raw(refused)


def property_text(result: DavResult, name: str) -> str:
    """The text of one property of the first response of a PROPFIND, ``fehlt`` if absent."""
    if result.status != 207:
        return "fehlt"
    entries = xml.parse_multistatus(result.body)
    return (entries[0][1].get(name) or "fehlt") if entries else "fehlt"


async def pretest_values(run_: DeleteRun) -> dict[str, str]:
    """What each pretest candidate answers for alice right now (M4.12)."""
    session, source = run_.session, run_.source
    alice = session.basic(ALICE)
    home_url_ = caldav.calendars_home_url(alice)
    wanted = propfind_body([source.retention_property])
    values: dict[str, str] = {}
    probe = await dav_request(
        session.client, alice, "PROPFIND", trash_url(alice, source), depth="0", body=wanted
    )
    values["papierkorb-propfind"] = str(probe.status)
    values["frist-eigenschaft"] = property_text(probe, source.retention_property)
    at_home = await dav_request(
        session.client, alice, "PROPFIND", home_url_, depth="0", body=wanted
    )
    values["frist-eigenschaft-home"] = property_text(at_home, source.retention_property)
    children = await dav_request(
        session.client,
        alice,
        "PROPFIND",
        home_url_,
        depth="1",
        body=propfind_body([f"{{{xml.DAV}}}resourcetype"]),
    )
    listed = xml.parse_multistatus(children.body) if children.status == 207 else []
    hrefs = [href for href, _ in listed]
    values["home-kind-trashbin"] = yes_no(
        any(unquote(href).rstrip("/").endswith(f"/{source.home}") for href in hrefs)
    )
    response = await ocs.ocs_get(session.client, alice, "/cloud/capabilities")
    data = ocs.parse_ocs(response, what="the capabilities")
    capabilities = data.get("capabilities") if isinstance(data, dict) else None
    dav_part = capabilities.get("dav") if isinstance(capabilities, dict) else None
    values["capabilities-dav"] = json.dumps(dav_part, sort_keys=True)
    options = await dav_request(session.client, alice, "OPTIONS", home_url_)
    values["dav-kopf"] = yes_no(TRASH_FEATURE in header_of(options, "dav"))
    return values


async def pretest(run_: DeleteRun, state: str) -> None:
    """Ask every candidate in one state of the trash bin and write one line per candidate."""
    values = await pretest_values(run_)
    run_.pretests[state] = values
    for name in PRETESTS:
        note(
            f"VORABTEST {name} zustand={state} wert={values[name][:300]} "
            f"zeigt={pretest_shows(name, values[name])}"
        )


async def delete_subtask(run_: DeleteRun) -> None:
    """A21, server side per version: the parent is deleted, what becomes of the sub task."""
    session = run_.session
    alice = session.basic(ALICE)
    parent, child = run_.name("eltern"), run_.name("kind")
    parent_uid, child_uid = parent.removesuffix(".ics"), child.removesuffix(".ics")
    parent_url = await put_new(
        session, alice, DEL_OWN, parent, simple_todo(parent_uid, "s30 eltern")
    )
    child_url = await put_new(
        session,
        alice,
        DEL_OWN,
        child,
        simple_todo(child_uid, "s30 kind", [f"RELATED-TO:{parent_uid}"]),
    )
    _, etag0, text0 = await get_object(session, alice, child_url)
    rows0 = run_.rows(child_uid)
    deleted = await delete_with_etag(session, alice, parent_url)
    got, etag1, text1 = await get_object(session, alice, child_url)
    rows1 = run_.rows(child_uid)
    same = got.status == 200 and etag0 == etag1 and text0 == text1 and rows0 == rows1
    note(
        f"{now_stamp()} | UNTERAUFGABE loeschen vorhanden={yes_no(got.status == 200)} "
        f"unveraendert={yes_no(same)} eltern_status={deleted.status} nutzer={ALICE} auth=basic | "
        f"datenbank kind={rows_text(rows1)} eltern={rows_text(run_.rows(parent_uid))}"
    )
    run_.controls["unterauftrag"] = deleted.status == 204


def set_switch(run_: DeleteRun, value: str | None, label: str) -> None:
    """Set or delete the retention key, prove it with occ, restart, prove it again.

    occ on the command line does not clear the cache of the web server (measured in phase
    25), so every change of the switch is followed by a restart of the container.
    """
    container, key = run_.container, run_.source.key
    if value is None:
        done = occ(container, "config:app:delete", "dav", key, check=False)
        note(f"SCHALTER {label} occ config:app:delete dav {key} -> {_one_line(done)[:160]}")
    else:
        done = occ(container, "config:app:set", "dav", key, f"--value={value}", check=False)
        note(
            f"SCHALTER {label} occ config:app:set dav {key} --value={value} -> "
            f"{_one_line(done)[:160]}"
        )
    before = _one_line(occ(container, "config:app:get", "dav", key, check=False))
    restarted = docker("restart", container, check=False).strip()
    wait_for_install(container)
    wait_for_http(SPIKE_BASE_URL)
    after = _one_line(occ(container, "config:app:get", "dav", key, check=False))
    note(
        f"SCHALTER {label} occ config:app:get dav {key} vor_neustart={before or 'leer'} "
        f"nach_neustart={after or 'leer'} (docker restart {restarted})"
    )
    if after != (value or ""):
        raise RunFailed(f"the switch {key} reads {after!r} after the restart, not {value!r}")


async def switch_off(run_: DeleteRun) -> None:
    """Switch the trash bin off with the value the source compares against."""
    set_switch(run_, run_.source.off_value, "aus")


async def delete_own_off(run_: DeleteRun) -> None:
    """M4.11, W3: delete an own task with the trash bin switched off."""
    session, source = run_.session, run_.source
    alice = session.basic(ALICE)
    name = run_.name("aus-eigen")
    uid = name.removesuffix(".ics")
    text = build_probe_todo(uid, "s30 aus-eigen")
    url = await put_new(session, alice, DEL_OWN, name, text)
    deleted = await delete_with_etag(session, alice, url)
    names = await trash_names(session, alice, source)
    rows = run_.rows(uid)
    attempt, recovered = "nicht moeglich", False
    if uid in names:
        restored = await restore_object(session, alice, source, names[uid])
        attempt = str(restored.status)
        back, _, text1 = await get_object(session, alice, url)
        recovered = 200 <= restored.status < 300 and back.status == 200 and text1 == text
    gone, _, _ = await get_object(session, alice, url)
    note(
        f"{now_stamp()} | LOESCHEN aus-eigen status={deleted.status} "
        f"im_papierkorb={yes_no(uid in names)} db_zeile={'vorhanden' if rows else 'weg'} "
        f"wiederherstellung={attempt} | nutzer={ALICE} auth=basic if_match=ja "
        f"get_danach={gone.status} papierkorb_eintraege={len(names)} "
        f"datenbank={rows_text(rows)} {describe_error(deleted.body)[:200]}".rstrip()
    )
    note_raw(deleted)
    run_.flags["w3_own"] = recovered
    run_.permanent["eigen"] = deleted.status == 204 and uid not in names and not rows
    run_.controls["aus-eigen"] = run_.flags.get("w1", False)


async def delete_shared_off(run_: DeleteRun) -> None:
    """The same on the list shared with write access, trash bin switched off."""
    session, source = run_.session, run_.source
    alice, bob = session.basic(ALICE), session.basic(BOB)
    name = run_.name("aus-geteilt")
    uid = name.removesuffix(".ics")
    text = build_probe_todo(uid, "s30 aus-geteilt")
    owner_url = await put_new(session, bob, DEL_RW, name, text)
    deleted = await delete_with_etag(
        session, alice, caldav.object_url(alice, run_.shared["rw"], name)
    )
    listed = {}
    for creds in (alice, bob):
        names = await trash_names(session, creds, source)
        if uid in names:
            listed[creds.user] = (creds, names[uid])
    rows = run_.rows(uid)
    attempt, recovered = "nicht moeglich", False
    for creds, entry in listed.values():
        restored = await restore_object(session, creds, source, entry)
        attempt = str(restored.status)
        back, _, text1 = await get_object(session, bob, owner_url)
        recovered = 200 <= restored.status < 300 and back.status == 200 and text1 == text
        if recovered:
            break
    gone, _, _ = await get_object(session, bob, owner_url)
    note(
        f"{now_stamp()} | LOESCHEN aus-geteilt status={deleted.status} "
        f"im_papierkorb={yes_no(bool(listed))} db_zeile={'vorhanden' if rows else 'weg'} "
        f"wiederherstellung={attempt} | geloescht_von={ALICE} auth=basic "
        f"get_als_eigentuemer_danach={gone.status} papierkorb_von={sorted(listed) or 'keinem'} "
        f"datenbank={rows_text(rows)} {describe_error(deleted.body)[:200]}".rstrip()
    )
    note_raw(deleted)
    run_.flags["w3_shared"] = recovered
    run_.permanent["geteilt"] = deleted.status == 204 and not listed and not rows
    run_.controls["aus-geteilt"] = run_.flags.get("w2", False)


async def pretest_off(run_: DeleteRun) -> None:
    """The candidates again with the trash bin off, and which of them tell the two apart."""
    await pretest(run_, "aus")
    names = pretest_distinguishing(run_.pretests.get("an", {}), run_.pretests["aus"])
    note(
        f"VORABTEST ERGEBNIS unterscheidet={yes_no(bool(names))} "
        f"kandidat={','.join(names) or 'keiner'}"
    )
    run_.flags["w4"] = bool(names)
    # The two states are proven by behaviour, not by the switch: with the trash bin on the
    # object came back, with it off the row is gone for good.
    behaviour = run_.flags.get("w1", False) and run_.permanent.get("eigen", False)
    note(
        f"KONTROLLE vorabtest zustand_am_verhalten_belegt={yes_no(behaviour)} "
        f"(an: wiederhergestellt={yes_no(run_.flags.get('w1', False))}, aus: endgueltig "
        f"geloescht={yes_no(run_.permanent.get('eigen', False))})"
    )
    run_.controls["vorabtest"] = behaviour and "an" in run_.pretests


async def retention_cleanup(run_: DeleteRun) -> None:
    """M4.13: the clean-up run keeps a deleted object by default and removes it after 1 s."""
    session, source = run_.session, run_.source
    alice = session.basic(ALICE)
    set_switch(run_, None, "standard")
    name = run_.name("frist")
    uid = name.removesuffix(".ics")
    url = await put_new(session, alice, DEL_OWN, name, simple_todo(uid, "s30 frist"))
    deleted = await delete_with_etag(session, alice, url)
    rows0 = run_.rows(uid)
    out = occ(run_.container, source.cleanup, check=False)
    rows1 = run_.rows(uid)
    standard = "bleibt" if rows1 else "weg"
    note(
        f"{now_stamp()} | AUFRAEUMEN standardfrist geloescht={deleted.status} occ "
        f"{source.cleanup} -> {_one_line(out) or '(keine Ausgabe)'} | datenbank "
        f"vorher={rows_text(rows0)} nachher={rows_text(rows1)}"
    )
    set_switch(run_, "1", "frist-1s")
    await pretest(run_, "frist-1s")
    await asyncio.sleep(3)
    out = occ(run_.container, source.cleanup, check=False)
    rows2 = run_.rows(uid)
    short = "bleibt" if rows2 else "weg"
    note(
        f"{now_stamp()} | AUFRAEUMEN frist=1 nach 3 s occ {source.cleanup} -> "
        f"{_one_line(out) or '(keine Ausgabe)'} | datenbank nachher={rows_text(rows2)}"
    )
    note(f"FRIST AUFRAEUMEN standard={standard} frist_1s={short}")
    run_.controls["aufraeumen"] = trash_mark(rows0) == "gesetzt" and standard == "bleibt"


def collected_line(version: str, run_: DeleteRun) -> None:
    """The collected line: ``g`` only if nothing is unmeasured and every control held."""
    held = {name: run_.controls.get(name, False) for name in CONTROL_SECTIONS}
    w3 = run_.flags.get("w3_own", False) and run_.flags.get("w3_shared", False)
    g = not run_.unmeasured and all(held.values())
    note(
        f"KONTROLLEN {json.dumps({name: yes_no(ok) for name, ok in held.items()})} "
        f"ungemessen={run_.unmeasured or 'keine'}"
    )
    note(
        f"LOESCHEN VERSION {version} g={yes_no(g)} w1={yes_no(run_.flags.get('w1', False))} "
        f"w2={yes_no(run_.flags.get('w2', False))} w3={yes_no(w3)} "
        f"w4={yes_no(run_.flags.get('w4', False))} wer={run_.who}"
    )


async def delete_sections(session: Session, version: str) -> None:
    """Every measured section of one version, then the collected line."""
    section("quelle")
    source = confirm_sources(SPIKE_CONTAINER)
    run_ = DeleteRun(
        session=session,
        container=SPIKE_CONTAINER,
        source=source,
        stamp=datetime.now(UTC).strftime("%H%M%S"),
    )
    await measured(run_, "frist", retention_facts(run_))
    await measured(run_, "an-eigen", delete_own_on(run_))
    await measured(run_, "an-geteilt", delete_shared_on(run_))
    await measured(run_, "vorabtest-an", pretest(run_, "an"))
    await measured(run_, "unterauftrag", delete_subtask(run_))
    await measured(run_, "aus", switch_off(run_))
    await measured(run_, "aus-eigen", delete_own_off(run_))
    await measured(run_, "aus-geteilt", delete_shared_off(run_))
    await measured(run_, "vorabtest-aus", pretest_off(run_))
    await measured(run_, "aufraeumen", retention_cleanup(run_))
    section("ergebnis")
    collected_line(version, run_)


async def block_delete_matrix(tag: str, *, other: bool) -> None:
    """One version from an empty machine to a removed volume, deleting measured in between."""
    section(f"delete-matrix nc-tag={tag}, start {now_stamp()}")
    if other:
        note(f"RUECKFALL-TAG {tag}: nicht einer der Soll-Tags {DELETE_TAGS} (--allow-other-tag)")
    delete_preconditions()
    passwords = {name: secrets.token_urlsafe(24) for name in ("admin", ALICE, BOB)}
    for name, value in passwords.items():
        remember_secret(f"SPIKE_PASSWORD_{name}", value)
    compose_env = {"NC_SPIKE_TAG": tag, "NC_SPIKE_ADMIN_PASSWORD": passwords["admin"]}
    section("aufbau")
    started_all = time.perf_counter()
    try:
        started = time.perf_counter()
        output = compose(["up", "-d", "--wait"], compose_env)
        note(f"docker compose up -d --wait: {time.perf_counter() - started:.1f} s")
        note(" / ".join(line.strip() for line in output.splitlines()[-4:] if line.strip()))
        started = time.perf_counter()
        wait_for_install(SPIKE_CONTAINER)
        note(f"Installation abgewartet: {time.perf_counter() - started:.1f} s")
        switched = occ(
            SPIKE_CONTAINER,
            "config:system:set",
            "auth.bruteforce.protection.enabled",
            "--value=false",
            "--type=boolean",
        )
        note(f"bruteforce protection aus (Wegwerf-Instanz) -> {switched[:120]}")
        status = occ(SPIKE_CONTAINER, "status")
        note(status)
        found = re.search(r"versionstring:\s*(\S+)", status)
        if found is None:
            raise RunFailed("occ status names no versionstring")
        note(f"VERSION OF RECORD {found[1]}")
        note(f"dbtype: {occ(SPIKE_CONTAINER, 'config:system:get', 'dbtype', check=False)}")
        memcache = occ(SPIKE_CONTAINER, "config:system:get", "memcache.local", check=False)
        note(f"memcache.local: {memcache or '(leer, nicht gesetzt)'}")
        docker_stats()
        async with new_client() as client:
            session = Session(env={"NC_MCP_URL": SPIKE_BASE_URL}, client=client)
            for user in (ALICE, BOB):
                occ_pw(SPIKE_CONTAINER, passwords[user], "user:add", "--password-from-env", user)
                note(f"occ user:add --password-from-env {user} (password via stdin)")
                session.app_passwords[user] = await spike_app_password(
                    session, user, passwords[user]
                )
            await delete_sections(session, found[1])
        docker_stats()
    finally:
        section("abbau")
        output = compose(["down", "-v"], compose_env, check=False)
        note(" / ".join(line.strip() for line in output.splitlines()[-4:] if line.strip()))
        container, volume = spike_leftovers()
        note(f"ABBAU Container vorhanden: {yes_no(bool(container))}")
        note(f"ABBAU Volume vorhanden: {yes_no(bool(volume))}")
        note(f"DAUER {time.perf_counter() - started_all:.0f} s; ENDE {now_stamp()}")


def block_delete_verdict() -> int:
    """Apply the rule to the collected lines of the four raw files and print the outcome.

    Needs no Docker and no environment file. A missing file or a missing collected line
    leaves that version out, which the rule answers with ``nicht eindeutig``.
    """
    rows: list[VersionRow] = []
    for major in DELETE_MAJORS:
        path = RAW_DIR / f"loeschen-{major}.txt"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        found = version_rows(text)
        if not found:
            print(f"EINGANG {path.name}: keine Zeile LOESCHEN VERSION")
        for row in found:
            flags = " ".join(
                f"{name}={yes_no(getattr(row, name))}" for name in ("g", "w1", "w2", "w3", "w4")
            )
            fits = row.major == major
            print(
                f"EINGANG {path.name}: LOESCHEN VERSION {row.version} {flags} wer={row.who}"
                f"{'' if fits else ' (falsche Version fuer diese Datei, nicht gewertet)'}"
            )
            if fits:
                rows.append(row)
    word = delete_verdict(rows)
    print(f"ERGEBNIS LOESCHEN (E13): {word}")
    print(f"KONSEQUENZ: {consequence(word)}")
    return 0


# --- plan 30-04: discovery, queries, provider link, search cost, fixtures (MESS-03, MESS-04) ---

SPIKE_PG_COMPOSE = "compose.spike-tags-pg.yml"
SPIKE_PG_CONTAINER = "nc-spike-tags-pg"
SPIKE_PG_DB_CONTAINER = "nc-spike-tags-pgdb"
#: Every throwaway container and volume of both compose files carries this in its name.
SPIKE_NAME_FILTER = "nc-spike-tags"
COST_DBS = ("sqlite", "pg")
DISCOVERY_PARTS = ("discovery", "query", "provider")

FRESH = "fresh30"
LIST_TASKS = f"{PREFIX}-aufgaben"
LIST_MIXED = f"{PREFIX}-gemischt"
LIST_SUBSCRIBED = f"{PREFIX}-abo"
LIST_DELETED = f"{PREFIX}-geloescht"
LIST_COST = f"{PREFIX}-kosten"
LIST_CREATE = f"{PREFIX}-anlegen"
#: The source of the subscription: the loopback of the instance itself, the discard port.
#: Nothing listens there and nothing outside the container is ever asked (T-30-22).
SUBSCRIPTION_SOURCE = "http://127.0.0.1:9/keine.ics"

#: What the discovery of plan 30-04 asks for per collection.
DISCOVERY_PROPS = (
    f"{{{xml.DAV}}}resourcetype",
    f"{{{xml.DAV}}}displayname",
    f"{{{xml.CAL}}}supported-calendar-component-set",
    f"{{{xml.CS}}}source",
    f"{{{xml.DAV}}}current-user-privilege-set",
    f"{{{OC_SHARE_NS}}}read-only",
)
#: The kinds a task tool may ever use, before the component set is looked at.
TASK_LIST_KINDS = ("aufgabenliste", "gemischt", "geteilt-schreibbar", "geteilt-nur-lesen")
#: The kinds the prepared account of the discovery part has to show (positive control M5.2).
PREPARED_KINDS = (
    "aufgabenliste",
    "gemischt",
    "abo",
    "papierkorb",
    "scheduling",
    "geteilt-schreibbar",
    "geteilt-nur-lesen",
    "deck",
)

TODO_MODES = ("alle", "offen", "erledigt", "fenster", "text", "eltern")
#: The six queries of M5.3 as ``(name in the protocol, mode)``.
QUERIES = (
    ("ohne-filter", "alle"),
    ("offen", "offen"),
    ("fenster", "fenster"),
    ("text", "text"),
    ("eltern", "eltern"),
    ("erledigt", "erledigt"),
)
QUERY_WINDOW = ("20261119T000000Z", "20261122T000000Z")
QUERY_TERM = "q-offen"
QUERY_PARENT = "q-offen-im-fenster"
#: The eight tasks of M5.3 with the lines that make them what their name says.
QUERY_TASKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("q-offen-undatiert", ()),
    (QUERY_PARENT, ("DUE:20261120T100000Z",)),
    ("q-offen-ausserhalb", ("DUE:20270301T100000Z",)),
    ("q-erledigt", ("STATUS:COMPLETED", "PERCENT-COMPLETE:100", "COMPLETED:20261110T090000Z")),
    ("q-abgebrochen", ("STATUS:CANCELLED",)),
    ("q-in-arbeit", ("STATUS:IN-PROCESS", "PERCENT-COMPLETE:50", "DUE:20261121T080000Z")),
    ("q-wiederkehrend", ("DTSTART:20261101T080000Z", "DUE:20261101T090000Z", "RRULE:FREQ=DAILY")),
    ("q-kind", ()),
)

COST_TASKS = 2000
COST_DONE = 1900
COST_TERM = "kostenprobe"
COST_TERM_TASKS = 10
WARMUP_RUNS = 3
MEASURED_RUNS = 15
LONG_TIMEOUT_SECONDS = 300.0

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "tasks_app"
FIXTURE_FRESH = REPO_ROOT / "tests" / "fixtures" / "caldav_home_fresh_account.xml"
FIXTURE_LISTS = REPO_ROOT / "tests" / "fixtures" / "caldav_home_task_lists.xml"
RAW_FRESH = "discovery-frisch"
RAW_PREPARED = "discovery-vorbereitet"
#: ``(kind, fixture file, snapshot state, SUMMARY in the browser session of plan 30-02)``.
#: The state is ``a`` (before the changes of round B) for everything but the two kinds
#: that only exist after them.
FIXTURE_FILES: tuple[tuple[str, str, str, str], ...] = (
    ("ganztag", "all_day.ics", "a", "s30 ganztag"),
    ("uhrzeit", "with_time.ics", "a", "s30 uhrzeit"),
    ("unteraufgabe", "subtask.ics", "a", "s30 kind-abhaken"),
    ("unteraufgabe", "subtask_parent.ics", "a", "s30 eltern-abhaken"),
    ("wiederkehrend", "recurring.ics", "a", "s30 wiederkehrend"),
    ("tags", "tags.ics", "a", "s30 tags"),
    ("abgehakt", "completed.ics", "b", "s30 abhaken"),
    ("wieder-geoeffnet", "reopened.ics", "b", "s30 wieder-oeffnen"),
)
#: Hosts a discovery answer may name: XML namespaces and the loopback of the instance.
_PROBE_HOSTS = (
    "127.0.0.1",
    "127.0.0.1:9",
    "127.0.0.1:8083",
    "sabredav.org",
    "sabre.io",
    "owncloud.org",
    "nextcloud.org",
    "nextcloud.com",
    "calendarserver.org",
    "apple.com",
)
_PROVIDER_LINK = re.compile(r"/apps/tasks/(?:#/)?calendars/([^/?#]+)/tasks/([^/?#]+)$")

#: The calendars of one principal as the table has them: uri, component set, trash mark.
PHP_CALENDARS_OF = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->select('uri', 'components', 'deleted_at')->from('calendars')
    ->where($qb->expr()->eq(
        'principaluri', $qb->createNamedParameter('principals/users/' . $argv[1])
    ))
    ->orderBy('id');
$out = [];
foreach ($qb->executeQuery()->fetchAll() as $row) {
    $out[] = $row['uri'] . ':' . $row['components'] . ':'
        . ($row['deleted_at'] === null ? 'leer' : 'gesetzt');
}
echo count($out), ' ', implode(' ', $out), "\n";
"""
)

#: The live objects of one calendar of one principal, counted in the database.
PHP_COUNT_LIST_OBJECTS = (
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


# --- pure helpers of plan 30-04 ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Collection:
    """One collection of a calendar home, with only the properties the server found."""

    uri: str
    display: str
    types: tuple[str, ...]
    components: tuple[str, ...]
    #: ``None`` if the property came back as not found; else its text, possibly empty.
    read_only: str | None
    privileges: tuple[str, ...]
    source: str


def _local_names(parent: etree._Element | None) -> tuple[str, ...]:
    if parent is None:
        return ()
    return tuple(etree.QName(child).localname for child in parent if isinstance(child.tag, str))


def parse_home(body: str | bytes) -> list[Collection]:
    """Every collection below a calendar home; the home itself (the shortest path) drops out.

    Only the properties of a 2xx propstat count: a property the server names under 404 is
    absent, which is the difference between ``read_only=fehlt`` and an empty value.
    """
    root = xml.parse_root(body)
    responses = root.findall(f"{{{xml.DAV}}}response")
    paths = [
        urlsplit((response.findtext(f"{{{xml.DAV}}}href") or "").strip()).path.rstrip("/")
        for response in responses
    ]
    home = min((path for path in paths if path), key=len, default="")
    found: list[Collection] = []
    for response, path in zip(responses, paths, strict=True):
        if not path or path == home:
            continue
        props: dict[str, etree._Element] = {}
        for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
            if " 2" not in (propstat.findtext(f"{{{xml.DAV}}}status") or ""):
                continue
            for child in propstat.findall(f"{{{xml.DAV}}}prop/*"):
                if isinstance(child.tag, str):
                    props[child.tag] = child
        comp_set = props.get(f"{{{xml.CAL}}}supported-calendar-component-set")
        privilege_set = props.get(f"{{{xml.DAV}}}current-user-privilege-set")
        read_only = props.get(f"{{{OC_SHARE_NS}}}read-only")
        source = props.get(f"{{{xml.CS}}}source")
        name = props.get(f"{{{xml.DAV}}}displayname")
        privileges: list[str] = []
        if privilege_set is not None:
            for privilege in privilege_set:
                privileges.extend(_local_names(privilege))
        found.append(
            Collection(
                uri=unquote(path.rsplit("/", 1)[-1]),
                display=(name.text or "").strip() if name is not None else "",
                types=_local_names(props.get(f"{{{xml.DAV}}}resourcetype")),
                components=tuple(
                    (comp.get("name") or "").upper()
                    for comp in (comp_set if comp_set is not None else ())
                    if isinstance(comp.tag, str)
                ),
                read_only=None if read_only is None else (read_only.text or "").strip(),
                privileges=tuple(privileges),
                source=(
                    (source.findtext(f"{{{xml.DAV}}}href") or "").strip()
                    if source is not None
                    else ""
                ),
            )
        )
    return found


def classify_collection(entry: Collection) -> str:
    """The kind of one collection, by the marks a connector can read in the discovery.

    The order is the order of exclusion: a Deck calendar is ``deck`` whatever its component
    set says, and a share is told apart by the read-only property before its components.
    """
    if entry.uri.startswith("app-generated--"):
        return "deck"
    if entry.uri == TRASH or "trash-bin" in entry.types:
        return "papierkorb"
    if entry.uri in ("inbox", "outbox") or {"schedule-inbox", "schedule-outbox"} & set(entry.types):
        return "scheduling"
    if "subscribed" in entry.types:
        return "abo"
    if "_shared_by_" in entry.uri:
        read_only = entry.read_only is not None and entry.read_only.lower() not in (
            "",
            "0",
            "false",
        )
        return "geteilt-nur-lesen" if read_only else "geteilt-schreibbar"
    if not entry.components:
        return "ohne-komponenten"
    if "VTODO" in entry.components:
        return "gemischt" if "VEVENT" in entry.components else "aufgabenliste"
    return "terminkalender" if "VEVENT" in entry.components else "andere"


def task_lists(entries: Iterable[Collection]) -> list[Collection]:
    """The collections a task tool may use: the right kind and ``VTODO`` in the set."""
    return [
        entry
        for entry in entries
        if classify_collection(entry) in TASK_LIST_KINDS and "VTODO" in entry.components
    ]


def writable(entry: Collection) -> bool:
    """Whether the privilege set of the asking account carries a writing privilege."""
    return bool({"write", "write-content", "bind", "all"} & set(entry.privileges))


def build_todo_filter(
    mode: str, start: str = "", end: str = "", *, term: str = "", parent_uid: str = ""
) -> bytes:
    """A ``calendar-query`` for the VTODOs of one list, narrowed the way ``mode`` says.

    ``alle`` has no narrowing filter, ``offen`` is the one prop-filter the Tasks app uses
    (``COMPLETED`` not defined), ``erledigt`` its opposite, ``fenster`` a time-range,
    ``text`` a text-match at ``SUMMARY`` and ``eltern`` one at ``RELATED-TO``. Built with
    lxml: a term is always text, never markup.
    """
    if mode not in TODO_MODES:
        raise ValueError(f"mode {mode!r} is not one of {', '.join(TODO_MODES)}")
    root = etree.Element(f"{{{xml.CAL}}}calendar-query", nsmap={"d": xml.DAV, "c": xml.CAL})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}getetag")
    etree.SubElement(prop, f"{{{xml.CAL}}}calendar-data")
    scope = etree.SubElement(root, f"{{{xml.CAL}}}filter")
    outer = etree.SubElement(scope, f"{{{xml.CAL}}}comp-filter", name="VCALENDAR")
    todo = etree.SubElement(outer, f"{{{xml.CAL}}}comp-filter", name="VTODO")
    if mode == "offen":
        completed = etree.SubElement(todo, f"{{{xml.CAL}}}prop-filter", name="COMPLETED")
        etree.SubElement(completed, f"{{{xml.CAL}}}is-not-defined")
    elif mode == "erledigt":
        etree.SubElement(todo, f"{{{xml.CAL}}}prop-filter", name="COMPLETED")
    elif mode == "fenster":
        if not start or not end:
            raise ValueError("mode fenster needs start and end")
        etree.SubElement(todo, f"{{{xml.CAL}}}time-range", start=start, end=end)
    elif mode in ("text", "eltern"):
        name, needle = ("SUMMARY", term) if mode == "text" else ("RELATED-TO", parent_uid)
        if not needle:
            raise ValueError(f"mode {mode} needs a value to match")
        matched = etree.SubElement(todo, f"{{{xml.CAL}}}prop-filter", name=name)
        match = etree.SubElement(
            matched, f"{{{xml.CAL}}}text-match", attrib={"match-type": "contains"}
        )
        match.text = needle
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def objects_in(report_body: str | bytes) -> list[str]:
    """The calendar texts of a REPORT answer, in the order the server sent them."""
    root = xml.parse_root(report_body)
    return [element.text or "" for element in root.iter(f"{{{xml.CAL}}}calendar-data")]


def names_in(report_body: str | bytes) -> set[str]:
    """The SUMMARY values of a REPORT answer."""
    names = {property_value(text, "SUMMARY") for text in objects_in(report_body)}
    return names - {""}


def _moment(text: str, name: str) -> str:
    """The value of a time property as ``YYYYMMDDTHHMMSSZ`` for comparing, else empty."""
    value = property_value(text, name)
    form = value_form(value)
    if form == "utc":
        return value
    if form == "floating":
        return f"{value}Z"
    return f"{value}T000000Z" if form == "date" else ""


def client_filter(
    objects: Iterable[str],
    mode: str,
    start: str = "",
    end: str = "",
    *,
    term: str = "",
    parent_uid: str = "",
) -> set[str]:
    """The names the connector wants from a query, filtered here instead of in the server.

    This is the counter probe of M5.3 and at the same time the semantics TASK-02 asks for:
    a due window never takes an undated task, and a recurring task counts with the dates
    it carries, without expansion. A difference to the server's answer is a finding.
    """
    if mode not in TODO_MODES:
        raise ValueError(f"mode {mode!r} is not one of {', '.join(TODO_MODES)}")
    wanted: set[str] = set()
    for text in objects:
        completed = bool(property_value(text, "COMPLETED"))
        if mode == "offen":
            keep = not completed
        elif mode == "erledigt":
            keep = completed
        elif mode == "fenster":
            moments = [_moment(text, "DUE"), _moment(text, "DTSTART")]
            keep = any(start <= moment < end for moment in moments if moment)
        elif mode == "text":
            keep = term.casefold() in property_value(text, "SUMMARY").casefold()
        elif mode == "eltern":
            keep = property_value(text, "RELATED-TO") == parent_uid
        else:
            keep = True
        if keep:
            wanted.add(property_value(text, "SUMMARY"))
    return wanted - {""}


def same_sets(by_version: Mapping[str, Mapping[str, Iterable[str]]]) -> dict[str, list[str]]:
    """Per query the versions whose hit set differs; an empty list means all are equal.

    The reference is the most frequent set (the first one on a tie). A version that has no
    answer for a query differs: a missing measurement is never an equal one.
    """
    queries: list[str] = []
    for sets in by_version.values():
        queries.extend(name for name in sets if name not in queries)
    result: dict[str, list[str]] = {}
    for query in queries:
        answers = {
            version: frozenset(sets[query]) if query in sets else None
            for version, sets in by_version.items()
        }
        known = [answer for answer in answers.values() if answer is not None]
        reference = max(known, key=known.count)
        result[query] = [version for version, answer in answers.items() if answer != reference]
    return result


def provider_link_parts(link: str) -> tuple[str, str] | None:
    """Calendar URI and object name out of a link of the search provider ``tasks``.

    Only the form ``.../apps/tasks/calendars/<uri>/tasks/<name>`` (with or without ``#/``)
    resolves. Anything else is ``None``: a link of another form is never guessed at.
    """
    match = _PROVIDER_LINK.search(link.strip())
    if match is None:
        return None
    return unquote(match[1]), unquote(match[2])


def proposal(median_all_seconds: float, max_seconds: float) -> str:
    """The derivation rule of plan 30-04 for cap and time budget, applied to two numbers.

    ``median_all_seconds`` is the reference value (median of mode ``alle`` at 2000 tasks),
    ``max_seconds`` the largest measured maximum. A proposal for phase 32, not a product
    value.
    """
    budget = max(1, math.ceil(2 * max_seconds - 1e-9))
    tail = (
        f"das Doppelte des größten gemessenen Maximalwerts {max_seconds:.3f} s, "
        "aufgerundet auf volle Sekunden); zweite Größe ist die "
        "Antwortgröße in Bytes je Modus"
    )
    if median_all_seconds <= 1.0:
        return (
            f"Bezugswert {median_all_seconds:.3f} s (höchstens 1,0 s): eine Abfrage je "
            "Liste ohne zusätzlichen Deckel unterhalb von 2000 Objekten, "
            f"Zeitbudget je Liste {budget} s ({tail}"
        )
    return (
        f"Bezugswert {median_all_seconds:.3f} s (über 1,0 s): Standardmodus offen als "
        "einziger Weg ohne Hinweis; Modus alle mit ehrlicher Notiz und "
        f"Zeitbudget je Liste {budget} s ({tail}; der Deckel der zurückgegebenen "
        "Aufgaben folgt der Antwortgröße, nicht der Laufzeit"
    )


def summarize(values: Sequence[float]) -> dict[str, float]:
    """min, median, the second largest value and max of one series.

    With 15 runs the 95th percentile is no measured value, so the key says what it is.
    """
    if len(values) < 2:
        raise ValueError("a series needs at least two values")
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p95_second_largest": ordered[-2],
        "max": ordered[-1],
    }


def _span(values: Sequence[int]) -> str:
    if not values:
        return "-"
    low, high = min(values), max(values)
    return str(low) if low == high else f"{low}..{high}"


def series_line(
    label: str,
    statuses: Sequence[int],
    hits: Sequence[int],
    sizes: Sequence[int],
    stats: Mapping[str, float],
) -> str:
    """One protocol line per measured series, wall clock in milliseconds.

    Status, hits and bytes are spans, so a series that changed its answer midway cannot
    hide behind its last run.
    """
    status = "/".join(str(value) for value in sorted(set(statuses)))
    return (
        f"{label} status={status} treffer={_span(hits)} bytes={_span(sizes)} "
        f"min={stats['min'] * 1000:.0f} median={stats['median'] * 1000:.0f} "
        f"p95_zweitgroesster={stats['p95_second_largest'] * 1000:.0f} "
        f"max={stats['max'] * 1000:.0f} (n={len(statuses)})"
    )


def pick_fixtures[T](
    objects_a: Mapping[str, T], objects_b: Mapping[str, T]
) -> tuple[dict[str, tuple[str, str, T]], list[str]]:
    """``({fixture file: (kind, state, object)}, missing kinds)`` by the SUMMARY alone.

    A kind whose object is not there is named as missing and gets no stand-in; a sub task
    without its parent is no pair and counts as missing as a whole.
    """
    picked: dict[str, tuple[str, str, T]] = {}
    missing: list[str] = []
    kinds: list[str] = []
    for kind, _, _, _ in FIXTURE_FILES:
        if kind not in kinds:
            kinds.append(kind)
    for kind in kinds:
        rows = [entry for entry in FIXTURE_FILES if entry[0] == kind]
        sources = [
            (objects_a if state == "a" else objects_b).get(summary) for _, _, state, summary in rows
        ]
        if any(source is None for source in sources):
            missing.append(kind)
            continue
        for (_, name, state, _), source in zip(rows, sources, strict=True):
            if source is not None:
                picked[name] = (kind, state, source)
    return picked, missing


def probe_values_only(text: str, users: Iterable[str]) -> list[str]:
    """Everything in a discovery answer that is no probe value; empty means it may be kept.

    Checked are account names in paths and principals, host names of URLs and anything
    that looks like a mail address (counted, never quoted).
    """
    allowed = set(users)
    offences: set[str] = set()
    for pattern in (
        r"/calendars/([^/<\"\s]+)",
        r"principals/users/([^/<\"\s]+)",
        r"_shared_by_([^/<\"\s]+)",
    ):
        offences.update(
            f"konto {name}" for name in re.findall(pattern, text) if unquote(name) not in allowed
        )
    offences.update(
        f"host {host}"
        for host in re.findall(r"https?://([^/\s<\"]+)", text)
        if host not in _PROBE_HOSTS
    )
    addresses = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if addresses:
        offences.add(f"adresse x{len(addresses)}")
    return sorted(offences)


def time_form(value: Any) -> str:
    """The form of a time value as icalendar read it; the counter probe of ``value_form``."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return "floating"
        return "utc" if value.utcoffset() == timedelta(0) and value.tzname() == "UTC" else "tzid"
    return "date" if isinstance(value, date) else "other"


def raw_body_from_protocol(protocol: str, label: str) -> bytes | None:
    """The body ``note_raw_body`` wrote under ``label``, byte for byte, or ``None``.

    The last block with that label counts (a repeated run replaces the earlier one). The
    body is only handed out if its sha256 is the one the run noted for the bytes it got.
    """
    pattern = re.compile(
        rf"(?ms)^ROHANTWORT-ANFANG {re.escape(label)} .*?sha256=([0-9a-f]{{64}})\n(.*?)"
        rf"^ROHANTWORT-ENDE {re.escape(label)}$"
    )
    blocks = pattern.findall(protocol)
    if not blocks:
        return None
    digest, block = blocks[-1]
    lines = [line[4:] if line.startswith("    ") else line for line in block.split("\n")[:-1]]
    body = "\n".join(lines).encode()
    return body if hashlib.sha256(body).hexdigest() == digest else None


# --- the throwaway instance of plan 30-04 ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpikeSetup:
    """Compose file and containers of one throwaway instance, and the dbtype it must name."""

    compose_file: str
    container: str
    #: Empty for SQLite: the database lives inside the Nextcloud container.
    db_container: str
    dbtype: str

    def containers(self) -> tuple[str, ...]:
        return (self.container, self.db_container) if self.db_container else (self.container,)


def spike_setup(db: str) -> SpikeSetup:
    """The SQLite instance of ``compose.spike-tags.yml`` or the PostgreSQL pair next to it."""
    if db == "sqlite":
        return SpikeSetup(SPIKE_COMPOSE, SPIKE_CONTAINER, "", "sqlite3")
    if db == "pg":
        return SpikeSetup(SPIKE_PG_COMPOSE, SPIKE_PG_CONTAINER, SPIKE_PG_DB_CONTAINER, "pgsql")
    raise ValueError(f"--db {db!r} is not one of {', '.join(COST_DBS)}")


def any_spike_leftovers() -> tuple[str, str]:
    """Container and volume ids of any throwaway instance, SQLite or PostgreSQL pair."""
    container = docker("ps", "-a", "-q", "--filter", f"name={SPIKE_NAME_FILTER}", check=False)
    volume = docker("volume", "ls", "-q", "--filter", f"name={SPIKE_NAME_FILTER}", check=False)
    return " ".join(container.split()), " ".join(volume.split())


def throwaway_preconditions() -> None:
    """Never next to nc35, never a second throwaway instance or an old volume, enough RAM."""
    section("vorbedingungen")
    running = docker("ps", "--format", "{{.Names}}", check=False).split()
    standing = [name for name in running if name in NC35_CONTAINERS]
    if standing:
        raise RunFailed(f"nc35 erst stoppen: {standing} laufen noch (--block nc35-stop)")
    ram_gate(())
    container, volume = any_spike_leftovers()
    note(f"VORBEDINGUNG Container {SPIKE_NAME_FILTER}* vorhanden: {yes_no(bool(container))}")
    note(f"VORBEDINGUNG Volume {SPIKE_NAME_FILTER}* vorhanden: {yes_no(bool(volume))}")
    if container or volume:
        raise RunFailed("a throwaway container or volume is still there; down -v it first")


@dataclass
class Instance:
    """One running throwaway instance: session, containers, version, generated passwords."""

    session: Session
    setup: SpikeSetup
    version: str
    passwords: dict[str, str]
    stamp: str

    @property
    def container(self) -> str:
        return self.setup.container

    def login(self, user: str) -> Credentials:
        """Credentials with the login password itself, for an account without a token."""
        return Credentials(
            base_url=SPIKE_BASE_URL, user=user, secret=self.passwords[user], mode=MODE_BASIC
        )


@asynccontextmanager
async def throwaway_instance(tag: str, db: str, users: Sequence[str]) -> AsyncIterator[Instance]:
    """One version from an empty machine to removed volumes, with accounts in between."""
    setup = spike_setup(db)
    throwaway_preconditions()
    passwords = {name: secrets.token_urlsafe(24) for name in ("admin", *users)}
    for name, value in passwords.items():
        remember_secret(f"SPIKE_PASSWORD_{name}", value)
    compose_env = {"NC_SPIKE_TAG": tag, "NC_SPIKE_ADMIN_PASSWORD": passwords["admin"]}
    if setup.db_container:
        compose_env["NC_SPIKE_DB_PASSWORD"] = secrets.token_urlsafe(24)
        remember_secret("SPIKE_DB_PASSWORD", compose_env["NC_SPIKE_DB_PASSWORD"])
    section("aufbau")
    started_all = time.perf_counter()
    container = setup.container
    try:
        started = time.perf_counter()
        output = compose(["up", "-d", "--wait"], compose_env, file=setup.compose_file)
        note(
            f"docker compose -f {setup.compose_file} up -d --wait: "
            f"{time.perf_counter() - started:.1f} s"
        )
        note(" / ".join(line.strip() for line in output.splitlines()[-4:] if line.strip()))
        started = time.perf_counter()
        wait_for_install(container)
        note(f"Installation abgewartet: {time.perf_counter() - started:.1f} s")
        switched = occ(
            container,
            "config:system:set",
            "auth.bruteforce.protection.enabled",
            "--value=false",
            "--type=boolean",
        )
        note(f"bruteforce protection aus (Wegwerf-Instanz) -> {switched[:120]}")
        status = occ(container, "status")
        note(status)
        found = re.search(r"versionstring:\s*(\S+)", status)
        if found is None:
            raise RunFailed("occ status names no versionstring")
        note(f"VERSION OF RECORD {found[1]}")
        dbtype = occ(container, "config:system:get", "dbtype", check=False)
        note(f"dbtype: {dbtype}")
        if dbtype != setup.dbtype:
            raise RunFailed(f"dbtype is {dbtype!r}, not {setup.dbtype}")
        if setup.db_container:
            psql = ["exec", setup.db_container, "psql", "-U", "nextcloud", "-d", "nextcloud"]
            note(f"select version(): {docker(*psql, '-tAc', 'select version()').strip()}")
            note(f"show shared_buffers: {docker(*psql, '-tAc', 'show shared_buffers').strip()}")
            digest = docker(
                "image",
                "inspect",
                "--format",
                "{{index .RepoDigests 0}}",
                "postgres:17-alpine",
                check=False,
            ).strip()
            note(f"postgres-Image: {digest}")
        memcache = occ(container, "config:system:get", "memcache.local", check=False)
        note(f"memcache.local: {memcache or '(leer, nicht gesetzt)'}")
        docker_stats()
        async with new_client() as client:
            session = Session(env={"NC_MCP_URL": SPIKE_BASE_URL}, client=client)
            for user in users:
                occ_pw(container, passwords[user], "user:add", "--password-from-env", user)
                note(f"occ user:add --password-from-env {user} (password via stdin)")
                try:
                    token = new_app_password(container, user, passwords[user], f"SPIKE_APP_{user}")
                except RunFailed as failure:
                    note(
                        f"BEFUND occ user:auth-tokens:add --name scheitert auf dieser Version "
                        f"({_one_line(str(failure))[-160:]}); Rueckfall getapppassword"
                    )
                    token = await ocs_app_password(session, user, passwords[user])
                session.app_passwords[user] = token
            yield Instance(
                session=session,
                setup=setup,
                version=found[1],
                passwords=passwords,
                stamp=datetime.now(UTC).strftime("%H%M%S"),
            )
        docker_stats()
    finally:
        section("abbau")
        output = compose(["down", "-v"], compose_env, file=setup.compose_file, check=False)
        note(" / ".join(line.strip() for line in output.splitlines()[-4:] if line.strip()))
        left_container, left_volume = any_spike_leftovers()
        note(f"ABBAU Container vorhanden: {yes_no(bool(left_container))}")
        note(f"ABBAU Volume vorhanden: {yes_no(bool(left_volume))}")
        note(f"DAUER {time.perf_counter() - started_all:.0f} s; ENDE {now_stamp()}")


async def ocs_app_password(session: Session, user: str, password: str) -> str:
    """An app password over ``/ocs/v2.php/core/getapppassword``, the login in the header."""
    response = await session.client.get(
        f"{SPIKE_BASE_URL}/ocs/v2.php/core/getapppassword",
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=(user, password),
    )
    try:
        token = str(response.json()["ocs"]["data"]["apppassword"])
    except (ValueError, KeyError, TypeError):
        token = ""
    if len(token) < 20:
        raise RunFailed(f"getapppassword for {user} answered {response.status_code}, no token")
    remember_secret(f"SPIKE_APP_{user}", token)
    note(f"GET /ocs/v2.php/core/getapppassword als {user} -> HTTP {response.status_code} (kept)")
    return token


async def part(name: str, work: Coroutine[Any, Any, None]) -> None:
    """One measured part; a failure makes it ``ungemessen`` instead of ending the run."""
    section(name)
    try:
        await work
    except Exception as failure:
        reason = f"{type(failure).__name__}: {_one_line(str(failure))[:240]}"
        note(f"BLOCK FAILED | {name} | {reason}")
        note(f"ABSCHNITT {name} ungemessen grund={reason}")


def note_raw_body(label: str, result: DavResult) -> None:
    """A whole answer body in the protocol, so that it can be read back byte for byte."""
    digest = hashlib.sha256(result.body).hexdigest()
    note(
        f"ROHANTWORT-ANFANG {label} status={result.status} bytes={len(result.body)} sha256={digest}"
    )
    for line in result.body.decode("utf-8", errors="replace").split("\n"):
        note(f"    {line}")
    note(f"ROHANTWORT-ENDE {label}")


def calendars_db(container: str, user: str) -> tuple[int, str]:
    """Count and ``uri:components:trash mark`` of the calendars of ``user`` in the table."""
    line = php(container, PHP_CALENDARS_OF, user)
    count, _, listing = line.partition(" ")
    return (int(count) if count.isdigit() else -1), listing.strip()


def app_version(container: str, app: str) -> str:
    """The version of an enabled app on ``container``, empty if it is not enabled."""
    data = _json_or_text(occ(container, "app:list", "--output=json", check=False))
    enabled = data.get("enabled", {}) if isinstance(data, dict) else {}
    return str(enabled.get(app, "")) if isinstance(enabled, dict) else ""


async def propfind_home(session: Session, creds: Credentials, user: str = "") -> DavResult:
    """The discovery of plan 30-04: PROPFIND Depth 1 on a calendar home."""
    url = f"{creds.base_url}{DAV_CALENDARS}{quote(user or creds.user, safe='')}/"
    return await dav_request(
        session.client, creds, "PROPFIND", url, depth="1", body=propfind_body(DISCOVERY_PROPS)
    )


def collection_lines(entries: Sequence[Collection]) -> None:
    """One ``SAMMLUNG`` line per collection, with the marks ``classify_collection`` used."""
    for entry in entries:
        read_only = "fehlt" if entry.read_only is None else (entry.read_only or "leer")
        note(
            f"SAMMLUNG uri={entry.uri} art={classify_collection(entry)} "
            f"komponenten={','.join(entry.components) or 'keine'} read_only={read_only} "
            f"schreibrecht={yes_no(writable(entry))} typen={','.join(entry.types) or 'keine'}"
            f"{f' quelle={entry.source}' if entry.source else ''} name={entry.display or '-'}"
        )


# --- discovery-matrix: fresh account (M5.1) ------------------------------------------------------


def form_login(base_url: str, user: str, password: str) -> int:
    """The login over the web form, with a cookie jar of its own; returns the last status."""
    with httpx.Client(follow_redirects=True, timeout=60.0) as browser:
        page = browser.get(f"{base_url}/login")
        token = re.search(r'data-requesttoken="([^"]+)"', page.text)
        if token is None:
            return 0
        answer = browser.post(
            f"{base_url}/login",
            data={
                "user": user,
                "password": password,
                "requesttoken": token[1],
                "timezone": "Europe/Berlin",
                "timezone_offset": "1",
            },
        )
        return answer.status_code


async def first_login(inst: Instance, user: str) -> str:
    """Log ``user`` in for the first time; returns the way that created a calendar."""
    session = inst.session
    response = await session.client.get(
        f"{SPIKE_BASE_URL}/ocs/v2.php/cloud/user",
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=(user, inst.passwords[user]),
    )
    count, listing = calendars_db(inst.container, user)
    note(
        f"{now_stamp()} | ERSTANMELDUNG versuch=basic GET /ocs/v2.php/cloud/user nutzer={user} "
        f"status={response.status_code} kalender_db_danach={count} {listing}"
    )
    if count > 0:
        return "basic"
    status = form_login(SPIKE_BASE_URL, user, inst.passwords[user])
    count, listing = calendars_db(inst.container, user)
    note(
        f"{now_stamp()} | ERSTANMELDUNG versuch=formular GET /login, POST /login nutzer={user} "
        f"status={status} kalender_db_danach={count} {listing}"
    )
    return "formular" if count > 0 else "keiner"


async def discovery_fresh(inst: Instance) -> None:
    """M5.1: an account after its real first login, and how many task lists it has."""
    session, container = inst.session, inst.container
    inst.passwords[FRESH] = secrets.token_urlsafe(24)
    remember_secret(f"SPIKE_PASSWORD_{FRESH}", inst.passwords[FRESH])
    occ_pw(container, inst.passwords[FRESH], "user:add", "--password-from-env", FRESH)
    note(f"occ user:add --password-from-env {FRESH} (password via stdin)")
    count, listing = calendars_db(container, FRESH)
    before = await propfind_home(session, inst.login("admin"), FRESH)
    collections = len(parse_home(before.body)) if before.status == 207 else 0
    note(
        f"FRISCHES KONTO vor_anmeldung status={before.status} sammlungen={collections} "
        f"kalender_db={count} {listing} (PROPFIND Depth 1 als admin auf calendars/{FRESH}/: "
        "das Konto selbst hat sich noch nie angemeldet, eine Anfrage in seinem Namen waere "
        f"schon die Anmeldung) | {describe_error(before.body)[:160]}"
    )
    way = await first_login(inst, FRESH)
    note(f"ERSTANMELDUNG weg={way}")
    result = await propfind_home(session, inst.login(FRESH))
    note(
        f"{now_stamp()} | PROPFIND Depth 1 calendars/{FRESH}/ nutzer={FRESH} auth=basic "
        f"status={result.status} bytes={len(result.body)}"
    )
    note_raw_body(RAW_FRESH, result)
    if result.status != 207:
        raise RunFailed(f"the discovery of {FRESH} answered {result.status}")
    entries = parse_home(result.body)
    calendars = [entry for entry in entries if "calendar" in entry.types]
    shown = ",".join(f"{entry.uri}({'+'.join(entry.components)})" for entry in calendars)
    note(f"FRISCHES KONTO aufgabenlisten={len(task_lists(entries))} kalender={shown or 'keine'}")
    collection_lines(entries)
    if way == "keiner":
        note(
            "FRISCHES KONTO ungemessen grund=weder die Anfrage mit Basic noch das Web-Formular "
            "hat einen Standardkalender erzeugt; die Antwort ohne Kalender ist gesichert"
        )
    listed = occ(container, "dav:list-calendars", FRESH, check=False)
    for line in listed.splitlines():
        note(f"  occ dav:list-calendars {FRESH}: {line}")
    count, listing = calendars_db(container, FRESH)
    with_todo = sum(
        1 for item in listing.split() if item.endswith(":leer") and "VTODO" in item.upper()
    )
    note(
        f"GEGENPROBE frisches konto kalender_db={count} {listing} aufgabenlisten_db={with_todo} "
        "(Tabelle calendars, Spalte components, per PHP und nicht ueber DAV)"
    )


# --- discovery-matrix: prepared account (M5.2) ---------------------------------------------------


def subscription_body(name: str, source: str) -> bytes:
    """The extended MKCOL that creates a calendar subscription, as the Calendar app sends it."""
    root = etree.Element(f"{{{xml.DAV}}}mkcol", nsmap={"d": xml.DAV, "cs": xml.CS})
    prop = etree.SubElement(etree.SubElement(root, f"{{{xml.DAV}}}set"), f"{{{xml.DAV}}}prop")
    kind = etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    etree.SubElement(kind, f"{{{xml.DAV}}}collection")
    etree.SubElement(kind, f"{{{xml.CS}}}subscribed")
    etree.SubElement(prop, f"{{{xml.DAV}}}displayname").text = name
    href = etree.SubElement(etree.SubElement(prop, f"{{{xml.CS}}}source"), f"{{{xml.DAV}}}href")
    href.text = source
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def make_calendar(
    session: Session, creds: Credentials, uri: str, components: Sequence[str] = ("VTODO",)
) -> None:
    """A calendar of the account of ``creds`` with the given component set, as a SETUP line."""
    made = await dav_request(
        session.client,
        creds,
        "MKCALENDAR",
        caldav.calendar_url(creds, uri),
        body=mkcalendar_body(uri, components),
    )
    note(
        f"{now_stamp()} | SETUP MKCALENDAR liste={uri} nutzer={creds.user} "
        f"auth={auth_label(creds)} status={made.status} komponenten={','.join(components)}"
    )
    if made.status != 201:
        raise RunFailed(f"MKCALENDAR {uri} answered {made.status}")


async def deck_calendar(session: Session, creds: Credentials) -> str:
    """A Deck board of the account of ``creds`` over the REST interface; returns its id."""
    response = await session.client.post(
        f"{creds.base_url}/index.php/apps/deck/api/v1.0/boards",
        json={"title": DECK_BOARD, "color": "0082c9"},
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=creds.auth(),
    )
    try:
        data = response.json()
    except ValueError:
        data = {}
    board_id = str(data.get("id") or "") if isinstance(data, dict) else ""
    note(
        f"{now_stamp()} | SETUP DECK POST /index.php/apps/deck/api/v1.0/boards titel={DECK_BOARD} "
        f"nutzer={creds.user} auth={auth_label(creds)} status={response.status_code} "
        f"board_id={board_id or '-'}"
    )
    return board_id


async def prepare_account(inst: Instance) -> None:
    """Everything the discovery of alice has to show besides the task list."""
    session, container = inst.session, inst.container
    alice, bob = session.basic(ALICE), session.basic(BOB)
    await make_calendar(session, alice, LIST_MIXED, ("VEVENT", "VTODO"))
    made = await dav_request(
        session.client,
        alice,
        "MKCOL",
        caldav.calendar_url(alice, LIST_SUBSCRIBED),
        body=subscription_body(LIST_SUBSCRIBED, SUBSCRIPTION_SOURCE),
    )
    note(
        f"{now_stamp()} | SETUP MKCOL abo={LIST_SUBSCRIBED} quelle={SUBSCRIPTION_SOURCE} "
        f"nutzer={ALICE} auth=basic status={made.status} | {describe_error(made.body)[:160]}"
    )
    await make_calendar(session, alice, LIST_DELETED)
    gone = await dav_request(
        session.client, alice, "DELETE", caldav.calendar_url(alice, LIST_DELETED)
    )
    count, listing = calendars_db(container, ALICE)
    note(
        f"{now_stamp()} | SETUP DELETE kalender={LIST_DELETED} nutzer={ALICE} auth=basic "
        f"status={gone.status} kalender_db={count} {listing}"
    )
    for uri, writable_ in ((LIST_RW, True), (LIST_RO, False)):
        await make_calendar(session, bob, uri)
        shared = await dav_request(
            session.client,
            bob,
            "POST",
            caldav.calendar_url(bob, uri),
            body=share_body(ALICE, writable=writable_),
        )
        note(
            f"{now_stamp()} | FREIGABE liste={uri} an={ALICE} schreibrecht={yes_no(writable_)} "
            f"nutzer={BOB} auth=basic status={shared.status}"
        )
    installed = _one_line(occ(container, "app:install", "deck", check=False))
    version = app_version(container, "deck")
    note(f"occ app:install deck -> {installed[:200]}")
    if not version:
        note(f"DECK ungemessen grund=occ app:install deck: {installed[:200] or 'keine Ausgabe'}")
        return
    note(f"DECK-APP version={version} (gelesen mit occ app:list --output=json)")
    board_id = await deck_calendar(session, alice)
    if not board_id:
        note("DECK ungemessen grund=die Deck-REST-Schnittstelle hat kein Board angelegt")


async def discovery_prepared(inst: Instance) -> None:
    """M5.2: every kind of collection in the discovery answer of the prepared account."""
    session, container = inst.session, inst.container
    alice = session.basic(ALICE)
    await prepare_account(inst)
    result = await propfind_home(session, alice)
    note(
        f"{now_stamp()} | PROPFIND Depth 1 calendars/{ALICE}/ nutzer={ALICE} auth=basic "
        f"status={result.status} bytes={len(result.body)}"
    )
    note_raw_body(RAW_PREPARED, result)
    if result.status != 207:
        raise RunFailed(f"the discovery of {ALICE} answered {result.status}")
    entries = parse_home(result.body)
    collection_lines(entries)
    kinds = {entry.uri: classify_collection(entry) for entry in entries}
    seen = sorted(set(kinds.values()))
    lacking = [kind for kind in PREPARED_KINDS if kind not in seen]
    note(f"ARTEN vorhanden={','.join(seen)} fehlen={','.join(lacking) or 'keine'}")
    note(f"POSITIVKONTROLLE aufgabenlisten_{ALICE}={len(task_lists(entries))} (mindestens 1)")

    by_uri = {entry.uri: entry for entry in entries}
    read_only = by_uri.get(f"{LIST_RO}_shared_by_{BOB}")
    read_write = by_uri.get(f"{LIST_RW}_shared_by_{BOB}")

    def shown(entry: Collection | None) -> str:
        if entry is None:
            return "sammlung-fehlt"
        return "fehlt" if entry.read_only is None else (entry.read_only or "leer")

    readable = read_only is not None and kinds[read_only.uri] == "geteilt-nur-lesen"
    told_apart = readable and (read_write is None or kinds[read_write.uri] == "geteilt-schreibbar")
    note(
        f"READ-ONLY EIGENSCHAFT abrufbar={yes_no(told_apart)} nur_lesen={shown(read_only)} "
        f"schreibbar={shown(read_write)} schreibrecht_nur_lesen="
        f"{yes_no(writable(read_only)) if read_only else '-'} schreibrecht_schreibbar="
        f"{yes_no(writable(read_write)) if read_write else '-'} (A4)"
    )
    trash = by_uri.get(TRASH)
    deleted_listed = LIST_DELETED in by_uri
    note(
        f"PAPIERKORB in_discovery={yes_no(trash is not None)} komponenten="
        f"{(','.join(trash.components) or 'keine') if trash else 'keine'} "
        f"typen={(','.join(trash.types) or 'keine') if trash else '-'} "
        f"geloeschter_kalender_im_home={yes_no(deleted_listed)} "
        f"aufgabenliste_laut_auswertung={yes_no(trash in task_lists(entries))} (A5)"
    )
    home_path = f"{DAV_CALENDARS}{ALICE}/"
    event_uris = {ref.uri for ref in caldav.parse_calendar_home(result.body, home_path)}
    task_uris = {entry.uri for entry in task_lists(entries)}
    note(
        f"GEMISCHT in_beiden={yes_no(LIST_MIXED in event_uris and LIST_MIXED in task_uris)} "
        f"terminfilter={yes_no(LIST_MIXED in event_uris)} "
        f"aufgabenfilter={yes_no(LIST_MIXED in task_uris)} (A11; Terminfilter ist "
        "caldav.parse_calendar_home des Connectors, Aufgabenfilter ist task_lists)"
    )
    note(
        f"TERMINFILTER heute liefert={','.join(sorted(event_uris)) or 'keine'} "
        f"AUFGABENFILTER liefert={','.join(sorted(task_uris)) or 'keine'}"
    )
    note("FOEDERIERT ungemessen grund=zweite Instanz noetig, in dieser Phase nicht vorgesehen")

    for label, entry in (("nur-lesen", read_only), ("schreibbar", read_write)):
        if entry is None:
            note(f"SCHREIBVERSUCH {label} ungemessen grund=die Freigabe fehlt in der Discovery")
            continue
        uid = f"s30-schreibversuch-{label}-{inst.stamp}"
        url = caldav.object_url(alice, entry.uri, f"{uid}.ics")
        put = await put_object(
            session, alice, url, simple_todo(uid, f"s30 {label}"), if_none_match="*"
        )
        rows = db_rows(uid, container)
        note(
            f"{now_stamp()} | SCHREIBVERSUCH {label} PUT create-only liste={entry.uri} "
            f"nutzer={ALICE} auth=basic status={put.status} angelegt_db={yes_no(bool(rows))} "
            f"| {describe_error(put.body)[:160]}"
        )
    listed = occ(container, "dav:list-calendars", ALICE, check=False)
    for line in listed.splitlines():
        note(f"  occ dav:list-calendars {ALICE}: {line}")
    count, listing = calendars_db(container, ALICE)
    in_home = sum(1 for entry in entries if "calendar" in entry.types)
    note(
        f"GEGENPROBE vorbereitetes konto kalender_db={count} {listing} | Sammlungen mit "
        f"resourcetype calendar in der Discovery={in_home} (eigene Kalender; Freigaben, Deck "
        "und Abos stehen nicht in der Tabelle calendars dieses Kontos)"
    )


# --- discovery-matrix: queries (M5.3) and provider link (M5.4) -----------------------------------


@dataclass
class QueryState:
    """The tasks of the query part: name to UID, and the texts as they were sent."""

    uids: dict[str, str] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)


async def query_setup(inst: Instance, state: QueryState) -> None:
    """The eight tasks of M5.3 in the task list of alice."""
    session = inst.session
    alice = session.basic(ALICE)
    for name, _ in QUERY_TASKS:
        state.uids[name] = f"s30-{name}-{inst.stamp}"
    for name, lines in QUERY_TASKS:
        extra = (f"RELATED-TO:{state.uids[QUERY_PARENT]}",) if name == "q-kind" else lines
        state.texts[name] = simple_todo(state.uids[name], name, extra)
        await put_new(session, alice, LIST_TASKS, f"{state.uids[name]}.ics", state.texts[name])


async def query_part(inst: Instance, state: QueryState) -> None:
    """M5.3: six queries, each with the set the server sent and the set filtered here."""
    session = inst.session
    alice = session.basic(ALICE)
    url = caldav.calendar_url(alice, LIST_TASKS)
    start, end = QUERY_WINDOW
    arguments = {"term": QUERY_TERM, "parent_uid": state.uids[QUERY_PARENT]}
    note(
        f"ABFRAGEN liste={LIST_TASKS} nutzer={ALICE} auth=basic REPORT calendar-query Depth 1; "
        f"fenster={start}..{end} text={QUERY_TERM} eltern=UID von {QUERY_PARENT}; client ist "
        "die Menge, die der Connector will (derselbe Filter im Skript ueber die ungefilterte "
        "Antwort), gleich=nein ist ein Befund ueber den Serverfilter"
    )
    unfiltered: list[str] = []
    for name, mode in QUERIES:
        body = build_todo_filter(mode, start, end, **arguments)
        result = await dav_request(session.client, alice, "REPORT", url, depth="1", body=body)
        if result.status != 207:
            note(
                f"ABFRAGE {name} status={result.status} treffer=ungemessen | "
                f"{describe_error(result.body)[:200]}"
            )
            continue
        hits = names_in(result.body)
        note(f"ABFRAGE {name} status={result.status} treffer={','.join(sorted(hits)) or 'keine'}")
        if mode == "alle":
            unfiltered = objects_in(result.body)
            wanted = set(state.texts)
        elif not unfiltered:
            note(f"ABFRAGE {name} client=ungemessen grund=die ungefilterte Antwort fehlt")
            continue
        else:
            wanted = client_filter(unfiltered, mode, start, end, **arguments)
        note(
            f"ABFRAGE {name} client={','.join(sorted(wanted)) or 'keine'} "
            f"gleich={yes_no(hits == wanted)}"
            f"{'' if hits == wanted else f' nur_server={sorted(hits - wanted)}'}"
            f"{'' if hits == wanted else f' nur_client={sorted(wanted - hits)}'}"
        )


async def provider_search(session: Session, creds: Credentials, term: str) -> tuple[int, list[str]]:
    """One search of the provider ``tasks``: status and the links of the entries."""
    response = await session.client.get(
        f"{creds.base_url}/ocs/v2.php/search/providers/tasks/search",
        params={"term": term},
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=creds.auth(),
    )
    try:
        entries = response.json()["ocs"]["data"]["entries"]
    except (ValueError, KeyError, TypeError):
        entries = []
    links = [
        str(entry.get("resourceUrl", ""))
        for entry in (entries if isinstance(entries, list) else [])
        if isinstance(entry, dict)
    ]
    note(
        f"{now_stamp()} | GET /ocs/v2.php/search/providers/tasks/search?term={term} "
        f"nutzer={creds.user} auth={auth_label(creds)} status={response.status_code} "
        f"eintraege={len(links)} | {_one_line(response.text)[:300]}"
    )
    return response.status_code, links


async def provider_ids(session: Session, creds: Credentials) -> str:
    """The ids of the search providers the instance offers this account."""
    response = await session.client.get(
        f"{creds.base_url}/ocs/v2.php/search/providers",
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        auth=creds.auth(),
    )
    try:
        data = response.json()["ocs"]["data"]
    except (ValueError, KeyError, TypeError):
        data = []
    ids = sorted(str(entry.get("id")) for entry in data if isinstance(entry, dict))
    return f"status={response.status_code} tasks_dabei={yes_no('tasks' in ids)} ids={','.join(ids)}"


async def provider_part(inst: Instance, state: QueryState) -> None:
    """M5.4: the link of the search provider ``tasks`` and what it resolves to."""
    session, container = inst.session, inst.container
    alice = session.basic(ALICE)
    note(f"PROVIDER liste vor_installation {await provider_ids(session, alice)}")
    before, links_before = await provider_search(session, alice, QUERY_TERM)
    note(f"PROVIDER tasks app_nie_installiert status={before} eintraege={len(links_before)}")
    installed = _one_line(occ(container, "app:install", "tasks", check=False))
    note(f"occ app:install tasks -> {installed[:200]}")
    version = app_version(container, "tasks")
    note(f"TASKS-APP version={version or 'nicht aktiv'} (gelesen mit occ app:list --output=json)")
    if not version:
        raise RunFailed(f"the Tasks app is not enabled: {installed[:200]}")
    note(f"PROVIDER liste app_an {await provider_ids(session, alice)}")
    _, links = await provider_search(session, alice, QUERY_TERM)
    note(f"PROVIDER tasks treffer={len(links)} link={links[0] if links else '-'}")
    for link in links[1:]:
        note(f"  weiterer link={link}")
    parts = provider_link_parts(links[0]) if links else None
    if parts is None:
        note(
            "PROVIDER aufloesung ungemessen grund="
            f"{'kein Treffer' if not links else 'die Form des Links ist nicht die erwartete'}"
        )
    else:
        calendar_uri, object_name = parts
        url = caldav.object_url(alice, calendar_uri, object_name)
        result, _, text = await get_object(session, alice, url)
        wanted = object_name.removesuffix(".ics")
        ours = wanted in state.uids.values()
        note(
            f"PROVIDER aufloesung status={result.status} uid_gleich="
            f"{yes_no(result.status == 200 and has_uid(text, wanted) and ours)} "
            f"kalender={calendar_uri} objekt={object_name} (GET auf die aus dem Link gebaute "
            "DAV-URL; die UID der angelegten Aufgabe ist ihr Objektname ohne .ics)"
        )
    disabled = _one_line(occ(container, "app:disable", "tasks", check=False))
    note(f"occ app:disable tasks -> {disabled[:160]}")
    note(f"docker restart {container} -> {docker('restart', container).strip()}")
    wait_for_http(SPIKE_BASE_URL)
    wait_for_install(container)
    note(f"PROVIDER liste app_aus {await provider_ids(session, alice)}")
    status, links_off = await provider_search(session, alice, QUERY_TERM)
    note(f"PROVIDER tasks app_aus treffer={len(links_off)} status={status}")


async def block_discovery_matrix(tag: str, parts: Sequence[str], *, other: bool) -> None:
    """One version: discovery of a fresh and a prepared account, queries, provider link."""
    section(f"discovery-matrix nc-tag={tag} parts={','.join(parts)}, start {now_stamp()}")
    if other:
        note(f"RUECKFALL-TAG {tag}: nicht einer der Soll-Tags {DELETE_TAGS} (--allow-other-tag)")
    async with throwaway_instance(tag, "sqlite", (ALICE, BOB)) as inst:
        section("liste")
        await make_calendar(inst.session, inst.session.basic(ALICE), LIST_TASKS)
        if "discovery" in parts:
            await part("frisches-konto", discovery_fresh(inst))
            await part("sammlungsarten", discovery_prepared(inst))
        state = QueryState()
        if "query" in parts or "provider" in parts:
            await part("abfragen-aufbau", query_setup(inst, state))
        if "query" in parts:
            await part("abfragen", query_part(inst, state))
        if "provider" in parts:
            await part("provider", provider_part(inst, state))


# --- cost (M6.1 to M6.3) -------------------------------------------------------------------------


def cost_todo(number: int) -> tuple[str, str]:
    """Object name and text of task ``number`` of the cost list.

    The first ``COST_DONE`` are checked off the way the Tasks app writes it, the rest is
    open, and the last ``COST_TERM_TASKS`` of the open ones carry the search term.
    """
    uid = f"s30-kosten-{number:04d}"
    summary = f"s30 kosten {number:04d}"
    if number >= COST_TASKS - COST_TERM_TASKS:
        summary += f" {COST_TERM}"
    extra = [
        (
            "DESCRIPTION:Eine Aufgabe der Kostenmessung mit einer Beschreibung von "
            "ueblicher Laenge\\, damit die Antwort nicht kuenstlich klein ausfaellt."
        ),
        f"DUE:202612{number % 28 + 1:02d}T100000Z",
        "CATEGORIES:spike30",
    ]
    if number < COST_DONE:
        extra += ["STATUS:COMPLETED", "PERCENT-COMPLETE:100", "COMPLETED:20261101T100000Z"]
    return f"{uid}.ics", simple_todo(uid, summary, extra)


async def cost_build(inst: Instance) -> None:
    """One list with 2000 tasks over DAV, 1900 of them done, and the database count."""
    session = inst.session
    alice = session.basic(ALICE)
    await make_calendar(session, alice, LIST_COST)
    # SQLite answers two writes at once with "database is locked" (measured in plan 30-02),
    # so the build is serial there; PostgreSQL takes the four the plan allows.
    parallel = 4 if inst.setup.db_container else 1
    gate = asyncio.Semaphore(parallel)
    repeated = 0
    failed: list[str] = []

    async def put(number: int) -> None:
        nonlocal repeated
        name, text = cost_todo(number)
        url = caldav.object_url(alice, LIST_COST, name)
        async with gate:
            status = 0
            for attempt in range(6):
                try:
                    made = await put_object(session, alice, url, text, if_none_match="*")
                    status = made.status
                except httpx.HTTPError:
                    status = 0
                if status in (201, 204) or (status == 412 and attempt):
                    return
                if 0 < status < 500:
                    break
                repeated += 1
                await asyncio.sleep(0.5 * (attempt + 1))
            failed.append(f"{name}:{status}")

    started = time.perf_counter()
    await asyncio.gather(*(put(number) for number in range(COST_TASKS)))
    seconds = time.perf_counter() - started
    if failed:
        raise RunFailed(f"{len(failed)} PUT of the cost list failed, first: {failed[:3]}")
    _, sample = cost_todo(0)
    note(
        f"AUFBAU aufgaben={COST_TASKS} erledigt={COST_DONE} dauer_s={seconds:.0f} "
        f"offen={COST_TASKS - COST_DONE} mit_suchbegriff={COST_TERM_TASKS} "
        f"gleichzeitig={parallel} wiederholte_put={repeated} objekt_bytes={len(sample.encode())} "
        f"(PUT create-only ueber DAV als {ALICE}, Liste {LIST_COST})"
    )
    rows = php(inst.container, PHP_COUNT_LIST_OBJECTS, ALICE, LIST_COST)
    note(
        f"GEGENPROBE datenbank zeilen={rows} erwartet={COST_TASKS} "
        f"gleich={yes_no(rows == str(COST_TASKS))} (Tabelle calendarobjects, per PHP)"
    )
    if rows != str(COST_TASKS):
        raise RunFailed(f"the database holds {rows} objects of {LIST_COST}, not {COST_TASKS}")


def cpu_percent(container: str) -> float | None:
    """The CPU share ``docker stats --no-stream`` reports for ``container`` right now."""
    output = docker("stats", "--no-stream", "--format", "{{.CPUPerc}}", container, check=False)
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)%", output)
    return float(match[1]) if match else None


async def wait_until_idle(containers: Sequence[str]) -> float:
    """Seconds until every container is idle again, at most ``LONG_TIMEOUT_SECONDS``.

    A request the client gave up on keeps running in PHP and in the database; a run started
    next to it would measure two requests at once.
    """
    started = time.perf_counter()
    while time.perf_counter() - started < LONG_TIMEOUT_SECONDS:
        loads = [cpu_percent(container) for container in containers]
        if all(load is not None and load < IDLE_CPU_PERCENT for load in loads):
            break
        await asyncio.sleep(5)
    return time.perf_counter() - started


def response_count(result: DavResult) -> int:
    """The number of objects a REPORT answer carries; 0 for anything but a Multi-Status."""
    if result.status != 207:
        return 0
    return len(xml.parse_root(result.body).findall(f"{{{xml.DAV}}}response"))


@dataclass
class Series:
    """One measured series: the warm runs, and what happened if the client limit was hit."""

    results: list[DavResult] = field(default_factory=list)
    timed_out: bool = False
    single: DavResult | None = None

    def stats(self) -> dict[str, float] | None:
        if len(self.results) < 2:
            return None
        return summarize([result.seconds for result in self.results])


async def measure_series(
    inst: Instance,
    label: str,
    method: str,
    url: str,
    *,
    depth: str | None = None,
    body: bytes | None = None,
) -> Series:
    """``WARMUP_RUNS`` discarded runs, then ``MEASURED_RUNS`` measured ones, one client.

    A run over the 60 s client limit is a measured outcome, not a tool failure: the series
    stops there, the protocol names the limit, and one single run with 300 s says how long
    the answer really takes.
    """
    creds = inst.session.basic(ALICE)
    containers = inst.setup.containers()
    waited = await wait_until_idle(containers)
    note(f"  {label}: Instanz ruht nach {waited:.0f} s (docker stats CPU unter 10 %)")
    series = Series()
    warm_done = 0
    async with new_client() as client:
        try:
            for _ in range(WARMUP_RUNS):
                await dav_request(client, creds, method, url, depth=depth, body=body)
                warm_done += 1
            for _ in range(MEASURED_RUNS):
                series.results.append(
                    await dav_request(client, creds, method, url, depth=depth, body=body)
                )
        except httpx.TimeoutException as failure:
            series.timed_out = True
            note(
                f"{label} ZEITLIMIT {TIMEOUT.read:.0f} s ueberschritten "
                f"({type(failure).__name__}) nach {warm_done} von {WARMUP_RUNS} "
                f"Aufwaermlaeufen und {len(series.results)} von {MEASURED_RUNS} Messlaeufen; "
                "Reihe abgebrochen"
            )
    if series.timed_out:
        waited = await wait_until_idle(containers)
        note(f"  {label}: der abgebrochene Lauf rechnete weiter, Ruhe nach {waited:.0f} s")
        long_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(LONG_TIMEOUT_SECONDS),
            cookies=NoCookieJar(),
        )
        async with long_client:
            try:
                series.single = await dav_request(
                    long_client, creds, method, url, depth=depth, body=body
                )
            except httpx.TimeoutException as failure:
                note(
                    f"{label} EINZELLAUF zeitlimit={LONG_TIMEOUT_SECONDS:.0f} s: keine Antwort "
                    f"({type(failure).__name__})"
                )
        if series.single is not None:
            note(
                f"{label} EINZELLAUF zeitlimit={LONG_TIMEOUT_SECONDS:.0f} s "
                f"status={series.single.status} treffer={response_count(series.single)} "
                f"bytes={len(series.single.body)} ms={series.single.seconds * 1000:.0f}"
            )
    return series


def note_series(label: str, series: Series, *, hits: bool = True) -> None:
    """The line of one series, and the Sabre message of a failed run if there was one."""
    stats = series.stats()
    if stats is None:
        return
    results = series.results
    note(
        series_line(
            label,
            [result.status for result in results],
            [response_count(result) for result in results] if hits else [],
            [len(result.body) for result in results],
            stats,
        )
    )
    failed = [result for result in results if result.status >= 400]
    if failed:
        note(
            f"  {label} fehler={describe_error(failed[0].body)[:200]} "
            f"({len(failed)} von {len(results)})"
        )


def calendar_search_body(term: str, limit: int, offset: int) -> bytes:
    """The Nextcloud REPORT ``calendar-search`` for VTODOs whose SUMMARY carries ``term``.

    The element names are read from ``CalendarSearchReport.php`` of the dav app (namespace
    ``http://nextcloud.com/ns``): a filter with comp-filter, prop-filter and search-term,
    then limit and offset.
    """
    space = "http://nextcloud.com/ns"
    root = etree.Element(
        f"{{{space}}}calendar-search", nsmap={"d": xml.DAV, "c": xml.CAL, "nc": space}
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}getetag")
    etree.SubElement(prop, f"{{{xml.CAL}}}calendar-data")
    scope = etree.SubElement(root, f"{{{space}}}filter")
    etree.SubElement(scope, f"{{{space}}}comp-filter", name="VTODO")
    etree.SubElement(scope, f"{{{space}}}prop-filter", name="SUMMARY")
    etree.SubElement(scope, f"{{{space}}}search-term").text = term
    etree.SubElement(root, f"{{{space}}}limit").text = str(limit)
    etree.SubElement(root, f"{{{space}}}offset").text = str(offset)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def cost_calendar_search(inst: Instance, all_objects: Sequence[str]) -> None:
    """M6.2: one call of ``calendar-search`` on the calendar home with Depth 2."""
    session = inst.session
    alice = session.basic(ALICE)
    await wait_until_idle(inst.setup.containers())
    wanted = client_filter(all_objects, "text", term=COST_TERM)
    try:
        result = await dav_request(
            session.client,
            alice,
            "REPORT",
            caldav.calendars_home_url(alice),
            depth="2",
            body=calendar_search_body(COST_TERM, 50, 0),
        )
    except httpx.TimeoutException as failure:
        note(
            f"KOSTEN calendar-search ungemessen grund=Zeitlimit {TIMEOUT.read:.0f} s "
            f"({type(failure).__name__})"
        )
        return
    if result.status != 207:
        for line in raw_answer(result.status, result.reason, result.headers, result.body):
            note(line)
        note(
            f"KOSTEN calendar-search ungemessen grund=status {result.status} "
            f"{describe_error(result.body)[:200]}"
        )
        return
    hits = names_in(result.body)
    note(
        f"KOSTEN calendar-search status={result.status} treffer={response_count(result)} "
        f"bytes={len(result.body)} ms={result.seconds * 1000:.0f} (ein Aufruf, REPORT auf dem "
        f"Kalender-Home, Depth 2, Suchbegriff {COST_TERM}, comp-filter VTODO, prop-filter "
        "SUMMARY, limit 50, offset 0)"
    )
    note(
        f"GEGENPROBE calendar-search namen_gleich={yes_no(hits == wanted)} "
        f"erwartet={len(wanted)} server={len(hits)} (dieselben Namen clientseitig aus der "
        f"Antwort alle gefiltert; Positivkontrolle: der Suchbegriff steht in "
        f"{COST_TERM_TASKS} vorbereiteten Aufgaben)"
    )


async def cost_series(inst: Instance) -> None:
    """M6.1 to M6.3: the series of both modes, calendar-search once, the reference values."""
    alice = inst.session.basic(ALICE)
    list_url = caldav.calendar_url(alice, LIST_COST)
    docker_stats()
    measured: dict[str, Series] = {}
    for mode in ("offen", "alle"):
        measured[mode] = await measure_series(
            inst,
            f"KOSTEN {mode}",
            "REPORT",
            list_url,
            depth="1",
            body=build_todo_filter(mode),
        )
        note_series(f"KOSTEN {mode}", measured[mode])
    everything = measured["alle"].results[-1:] or [
        result for result in [measured["alle"].single] if result is not None
    ]
    all_objects = objects_in(everything[0].body) if everything else []
    open_client = client_filter(all_objects, "offen")
    open_hits = [response_count(result) for result in measured["offen"].results[-1:]]
    note(
        f"GEGENPROBE offen treffer_server={open_hits[0] if open_hits else 'ungemessen'} "
        f"erwartet={COST_TASKS - COST_DONE} alle_treffer={len(all_objects)} "
        f"erwartet_alle={COST_TASKS} alle_ohne_completed={len(open_client)} (Objekte ohne "
        "COMPLETED, clientseitig in der Antwort alle gezaehlt)"
    )
    await cost_calendar_search(inst, all_objects)
    discovery = await measure_series(
        inst,
        "BEZUG discovery",
        "PROPFIND",
        caldav.calendars_home_url(alice),
        depth="1",
        body=caldav.build_discovery_body(),
    )
    stats = discovery.stats()
    if stats is not None:
        codes = sorted({result.status for result in discovery.results})
        note(
            f"BEZUG discovery median={stats['median'] * 1000:.0f} status={codes} "
            f"max={stats['max'] * 1000:.0f} (ms, n={len(discovery.results)}, PROPFIND Depth 1)"
        )
    status_php = await measure_series(
        inst, "BEZUG status.php", "GET", f"{SPIKE_BASE_URL}/status.php"
    )
    stats = status_php.stats()
    if stats is not None:
        codes = sorted({result.status for result in status_php.results})
        note(
            f"BEZUG status.php median={stats['median'] * 1000:.0f} status={codes} "
            f"max={stats['max'] * 1000:.0f} (ms, n={len(status_php.results)})"
        )
    docker_stats()

    def worst(series: Series) -> float | None:
        found = series.stats()
        if found is not None and not series.timed_out:
            return found["max"]
        if series.single is not None:
            return series.single.seconds
        return LONG_TIMEOUT_SECONDS if series.timed_out else None

    all_stats = measured["alle"].stats()
    reference = (
        all_stats["median"]
        if all_stats is not None and not measured["alle"].timed_out
        else worst(measured["alle"])
    )
    maxima = [value for value in (worst(measured["offen"]), worst(measured["alle"])) if value]
    if reference is None or not maxima:
        note("VORSCHLAG ungemessen grund=die Reihe alle lieferte keinen Wert")
        return
    note(
        f"VORSCHLAG {proposal(reference, max(maxima))} (nur mit den Zahlen dieser Datenbank "
        f"{inst.setup.dbtype}; die Ableitungsregel nimmt als Bezugswert den größeren "
        "Median beider Datenbanken, der Bericht wendet sie auf beide Dateien an)"
    )


async def block_cost(tag: str, db: str, *, other: bool) -> None:
    """The cost of the task search at 2000 tasks on one throwaway instance."""
    section(f"cost db={db} nc-tag={tag}, start {now_stamp()}")
    if other:
        note(f"RUECKFALL-TAG {tag}: nicht einer der Soll-Tags {DELETE_TAGS} (--allow-other-tag)")
    async with throwaway_instance(tag, db, (ALICE,)) as inst:
        section("datenaufbau")
        await cost_build(inst)
        section("kosten")
        await cost_series(inst)


# --- vtodo-create on nc35 (M5.5) -----------------------------------------------------------------


async def create_only_pair(session: Session, creds: Credentials, key: str) -> tuple[int, int, bool]:
    """A create-only PUT and a second one on the same name: both codes, and ``unchanged``."""
    uid = f"s30-anlegen-{key}"
    name = f"{uid}.ics"
    url = caldav.object_url(creds, LIST_CREATE, name)
    text = simple_todo(uid, f"s30 anlegen {key}")
    since = container_now()
    await asyncio.sleep(1)
    first = await put_object(session, creds, url, text, if_none_match="*")
    label = auth_label(creds)
    note(
        f"VTODO anlegen auth={label} status={first.status} nutzer={creds.user} "
        f"If-None-Match=* objekt={LIST_CREATE}/{name} etag={etag_kind(header_of(first, 'etag'))} "
        f"| {describe_error(first.body)[:160]}"
    )
    rows = db_rows(uid)
    stored = rows[0].digest if len(rows) == 1 else ""
    note(
        f"  GEGENPROBE datenbank zeilen={len(rows)} {rows_text(rows)} "
        f"gesendet={sha_of(text)} gleich={yes_no(stored == sha_of(text))}"
    )
    if label == "appapi":
        lines = impersonation_lines(since, creds.user, "PUT")
        note(f"  KONTROLLE exapp_impersonation.log PUT-Zeilen von {creds.user}: {len(lines)}")
        for line in lines[-1:]:
            note(f"    {line[:300]}")
        basic = session.basic(creds.user)
        status, objects = await report(
            session,
            basic,
            LIST_CREATE,
            report_body("calendar-multiget", [urlsplit(url).path]),
        )
        same = any(plain(data) == plain(text) for _, _, data in objects)
        note(
            f"  GEGENPROBE REPORT calendar-multiget auth=basic status={status} "
            f"objekte={len(objects)} text_gleich={yes_no(same)}"
        )
    second = await put_object(
        session, creds, url, set_summary(text, f"s30 anlegen {key} zweiter"), if_none_match="*"
    )
    after = db_rows(uid)
    unchanged = len(after) == 1 and after[0].digest == stored and bool(stored)
    _, _, read_back = await get_object(session, creds, url)
    unchanged = unchanged and plain(read_back) == plain(text)
    note(
        f"VTODO anlegen zweiter status={second.status} objekt_unveraendert={yes_no(unchanged)} "
        f"auth={label} | {describe_error(second.body)[:160]}"
    )
    return first.status, second.status, unchanged


async def block_vtodo_create(session: Session) -> None:
    """M5.5: a create-only PUT of a VTODO under AppAPI impersonation, and with an app password."""
    section("vtodo-create")
    ram_gate(NC35_CONTAINERS)
    stamp = datetime.now(UTC).strftime("%H%M%S")
    appapi, basic = session.appapi(USER_A), session.basic(USER_A)
    await make_calendar(session, appapi, LIST_CREATE)
    impersonated = await create_only_pair(session, appapi, f"appapi-{stamp}")
    uid = f"s30-anlegen-falsch-{stamp}"
    wrong = await put_object(
        session,
        session.appapi(USER_A, "0" * 64),
        caldav.object_url(appapi, LIST_CREATE, f"{uid}.ics"),
        simple_todo(uid, "s30 anlegen falsch"),
        if_none_match="*",
    )
    note(
        f"VTODO anlegen falsches_secret status={wrong.status} "
        f"angelegt_db={yes_no(bool(db_rows(uid)))}"
    )
    with_password = await create_only_pair(session, basic, f"basic-{stamp}")
    note(
        f"VTODO GLEICH appapi_basic={yes_no(impersonated == with_password)} "
        f"appapi={impersonated[0]}/{impersonated[1]}/{yes_no(impersonated[2])} "
        f"basic={with_password[0]}/{with_password[1]}/{yes_no(with_password[2])}"
    )
    board_id = ""
    try:
        section("deck-discovery")
        deck = app_version(NC_CONTAINER, "deck")
        note(f"DECK-APP version={deck or 'nicht aktiv'} (occ app:list --output=json)")
        if deck:
            board_id = await deck_calendar(session, basic)
        result = await propfind_home(session, appapi)
        note(
            f"{now_stamp()} | PROPFIND Depth 1 calendars/{USER_A}/ nutzer={USER_A} auth=appapi "
            f"status={result.status} bytes={len(result.body)}"
        )
        if result.status == 207:
            collection_lines(parse_home(result.body))
    finally:
        if board_id:
            gone = await session.client.delete(
                f"{basic.base_url}/index.php/apps/deck/api/v1.0/boards/{board_id}",
                headers={"OCS-APIRequest": "true", "Accept": "application/json"},
                auth=basic.auth(),
            )
            note(f"RUECKBAU DECK DELETE boards/{board_id} status={gone.status_code}")


# --- fixtures (M5.6, no Docker) ------------------------------------------------------------------

#: The mark a fixture of each kind has to carry, so that a file named after a kind is one.
_FIXTURE_MARKS: dict[str, tuple[str, str]] = {
    "all_day.ics": ("DUE als Datum", r"(?m)^DUE;VALUE=DATE:\d{8}\r?$"),
    "with_time.ics": ("DUE mit Uhrzeit", r"(?m)^DUE(;[^:\r\n]*)?:\d{8}T\d{6}Z?\r?$"),
    "subtask.ics": ("RELATED-TO", r"(?m)^RELATED-TO"),
    "subtask_parent.ics": ("kein RELATED-TO", r"(?m)\A(?![\s\S]*^RELATED-TO)"),
    "recurring.ics": ("RRULE", r"(?m)^RRULE:"),
    "tags.ics": ("CATEGORIES", r"(?m)^CATEGORIES"),
    "completed.ics": (
        "STATUS:COMPLETED und COMPLETED",
        r"(?ms)\A(?=.*^STATUS:COMPLETED)(?=.*^COMPLETED:)",
    ),
    "reopened.ics": ("STATUS:NEEDS-ACTION", r"(?m)^STATUS:NEEDS-ACTION"),
}

PROVENANCE_TEXT = """# Provenance of the fixtures in this directory

Every `.ics` file here is an object the Nextcloud Tasks app wrote. Nothing was edited: each
file is a byte for byte copy of a raw file of the measuring spike of phase 30 (plan 30-02,
browser session; plan 30-04, block `fixtures` of `scripts/tasks_spike.py`), CRLF line ends
included.

- Nextcloud: {nextcloud} (`occ status` of the running instance, raw file `{nextcloud_file}`)
- Tasks app: {tasks} (`occ app:list` of the running instance, raw file `{tasks_file}`;
  every object also names it in its `PRODID`)
- Database: SQLite
- Date of the session: {date}
- Account: `spike30ui`, a measuring account that existed only for this session; language
  German, browser time zone Europe/Berlin
- Raw files: `.planning/phases/30-mess-spike-aufgaben-und-ordner/raw/ui-a/` (state before
  the changes of round B) and `raw/ui-b/` (state after them)

| File | Kind | State | Raw file | sha256 |
|------|------|-------|----------|--------|
{rows}

`subtask.ics` and `subtask_parent.ics` belong together: `RELATED-TO` of the first is the
`UID` of the second, and both lay in the same list.

Kinds without a file here were not written by the app in that session and were not rebuilt
by hand: {missing}.

{discovery}
"""


def ui_objects(state: str) -> dict[str, Path]:
    """The raw objects of one snapshot state of plan 30-02, by their SUMMARY."""
    found: dict[str, Path] = {}
    for path in sorted((RAW_DIR / f"ui-{state}").glob("*.ics")):
        text = path.read_bytes().decode("utf-8", errors="replace")
        summary = property_value(text, "SUMMARY")
        if summary:
            found[summary] = path
    return found


def _first(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match[1] if match else "(not readable)"


def write_provenance(
    rows: Sequence[str], missing: Sequence[str], discovery_files: Sequence[str]
) -> None:
    """``PROVENANCE.md`` with the versions the raw protocols name."""
    modify = (RAW_DIR / "nc35-aendern.txt").read_text(encoding="utf-8", errors="replace")
    session = (RAW_DIR / UI_PROTOCOL).read_text(encoding="utf-8", errors="replace")
    discovery_file = RAW_DIR / "discovery-35.txt"
    discovery = (
        discovery_file.read_text(encoding="utf-8", errors="replace")
        if discovery_file.is_file()
        else ""
    )
    discovery_version = _first(r"(?m)^VERSION OF RECORD (\S+)", discovery)
    text = PROVENANCE_TEXT.format(
        nextcloud=_first(r"(?m)^VERSION OF RECORD (\S+)", modify),
        nextcloud_file="raw/nc35-aendern.txt",
        tasks=_first(r"(?m)^TASKS-APP version=(\S+)", modify),
        tasks_file="raw/nc35-aendern.txt",
        date=_first(r"(?m)^# Lauf blocks=ui-snapshot start=(\d{4}-\d{2}-\d{2})", session),
        rows="\n".join(rows),
        missing=", ".join(missing) or "none",
        discovery=(
            f"The discovery answers next to this directory ({', '.join(discovery_files)}) are "
            f"unchanged answers of a throwaway Nextcloud {discovery_version} (raw file "
            "`raw/discovery-35.txt`), asked for by the accounts `fresh30` and `alice`."
            if discovery_files
            else "No discovery answer was kept as a fixture; the protocol names the reason."
        ),
    )
    (FIXTURE_DIR / "PROVENANCE.md").write_text(text, encoding="ascii", newline="\n")


def fixture_objects(discovery_files: Sequence[str]) -> list[str]:
    """M5.6: copy the picked objects unchanged, name what is missing; returns the files."""
    state_a, state_b = ui_objects("a"), ui_objects("b")
    picked, missing = pick_fixtures(state_a, state_b)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    written: list[str] = []
    reasons = dict.fromkeys(missing, "kein Objekt mit dieser SUMMARY in raw/ui-a oder raw/ui-b")
    for name, (kind, state, source) in picked.items():
        data = source.read_bytes()
        text = data.decode("utf-8", errors="replace")
        what, pattern = _FIXTURE_MARKS[name]
        by_app = "Nextcloud Tasks" in property_value(text, "PRODID")
        if not by_app or re.search(pattern, text) is None:
            reasons[kind] = (
                f"{source.name} traegt das Merkmal nicht ({what}) oder stammt nicht von der "
                "Tasks-App (PRODID)"
            )
            continue
        target = FIXTURE_DIR / name
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        same = hashlib.sha256(target.read_bytes()).hexdigest() == digest
        raw_name = f"raw/ui-{state}/{source.name}"
        note(
            f"FIXTURE {kind} quelle={raw_name} sha256_gleich={yes_no(same)} datei="
            f"tests/fixtures/tasks_app/{name} sha256={digest} merkmal={what} prodid_tasks_app=ja"
        )
        rows.append(f"| `{name}` | {kind} | {state} | `{raw_name}` | `{digest}` |")
        written.append(name)
    for kind, reason in reasons.items():
        note(f"FIXTURE {kind} fehlt grund={reason}")
    untouched_a, untouched_b = state_a.get("s30 unberuehrt"), state_b.get("s30 unberuehrt")
    same = (
        untouched_a is not None
        and untouched_b is not None
        and untouched_a.read_bytes() == untouched_b.read_bytes()
    )
    note(f"KONTROLLE s30 unberuehrt in_beiden_staenden_gleich={yes_no(same)} (Positivkontrolle)")
    write_provenance(rows, sorted(reasons), discovery_files)
    note("PROVENANCE tests/fixtures/tasks_app/PROVENANCE.md geschrieben")
    return written


def fixture_assumptions(written: Sequence[str]) -> None:
    """A2 and A3 read from the fixtures, A3 once more with icalendar."""
    session = (RAW_DIR / UI_PROTOCOL).read_text(encoding="utf-8", errors="replace")
    texts = {
        name: (FIXTURE_DIR / name).read_bytes().decode("utf-8", errors="replace")
        for name in written
    }
    if "subtask.ics" in texts and "subtask_parent.ics" in texts:
        child, parent = texts["subtask.ics"], texts["subtask_parent.ics"]
        line = _line_of(child, "RELATED-TO")
        reltype = re.search(r"RELTYPE=([^;:]+)", line)
        lists = []
        for text in (child, parent):
            summary = re.escape(property_value(text, "SUMMARY"))
            found = re.search(
                rf"(?m)^UI-OBJEKT stand=a liste=(\S+) name=\S+ summary={summary} ", session
            )
            lists.append(found[1] if found else "?")
        same_list = lists[0] == lists[1] and lists[0] != "?"
        note(
            f"A2 related_to_gleich_eltern_uid="
            f"{yes_no(property_value(child, 'RELATED-TO') == uid_of(parent))} "
            f"gleiche_liste={yes_no(same_list)} reltype={reltype[1] if reltype else 'fehlt'} "
            f"related_to={property_value(child, 'RELATED-TO')} eltern_uid={uid_of(parent)} "
            f"liste_kind={lists[0]} liste_eltern={lists[1]} (Listen aus den Zeilen UI-OBJEKT "
            f"stand=a in raw/{UI_PROTOCOL})"
        )
    else:
        note("A2 ungemessen grund=die Fixtures der Unteraufgabe und ihrer Elternaufgabe fehlen")
    names = ("DUE", "DTSTART", "COMPLETED")
    by_line: dict[str, set[str]] = {name: set() for name in names}
    by_library: dict[str, set[str]] = {name: set() for name in names}
    for file_name, text in texts.items():
        todo = next(iter(icalendar.Calendar.from_ical(text).walk("VTODO")))
        shown = []
        for name in names:
            line = _line_of(text, name)
            if not line:
                continue
            form = value_form(line)
            by_line[name].add(form)
            by_library[name].add(time_form(todo.decoded(name)))
            shown.append(f"{name}={form}")
        note(f"ZEITFORM fixture={file_name} {' '.join(shown) or '(keine Zeitangabe)'}")

    def joined(forms: Mapping[str, set[str]]) -> str:
        return " ".join(
            f"{name.lower()}={'+'.join(sorted(forms[name])) or 'fehlt'}" for name in names
        )

    note(f"A3 zeitform {joined(by_line)} (value_form ueber die Zeile, alle Fixtures)")
    note(
        f"A3 gegenprobe icalendar {joined(by_library)} gleich={yes_no(by_line == by_library)} "
        "(dieselben Werte mit der Bibliothek icalendar gelesen)"
    )
    floating = any("floating" in forms for forms in by_line.values())
    note(
        f"A3 schwebend_vorhanden={yes_no(floating)} tzid_vorhanden="
        f"{yes_no(any('tzid' in forms for forms in by_line.values()))}"
    )


def fixture_discovery() -> list[str]:
    """The two discovery answers of Nextcloud 35 as fixtures, unchanged or not at all."""
    source = RAW_DIR / "discovery-35.txt"
    protocol = source.read_text(encoding="utf-8", errors="replace") if source.is_file() else ""
    created: list[str] = []
    for label, target, users in (
        (RAW_FRESH, FIXTURE_FRESH, (FRESH,)),
        (RAW_PREPARED, FIXTURE_LISTS, (ALICE, BOB)),
    ):
        shown = target.relative_to(REPO_ROOT).as_posix()
        body = raw_body_from_protocol(protocol, label)
        if body is None:
            note(
                f"FIXTURE discovery {shown} nicht angelegt grund=die Rohantwort {label} fehlt in "
                f"raw/{source.name} oder ihr sha256 stimmt nicht"
            )
            continue
        offences = probe_values_only(body.decode("utf-8", errors="replace"), users)
        if offences:
            note(
                f"FIXTURE discovery {shown} nicht angelegt grund=Werte, die keine Probewerte "
                f"sind: {offences}"
            )
            continue
        target.write_bytes(body)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        entries = parse_home(body)
        note(
            f"FIXTURE discovery {shown} quelle=raw/{source.name} ({label}) "
            f"sha256_gleich={yes_no(digest == hashlib.sha256(body).hexdigest())} sha256={digest} "
            f"bytes={len(body)} sammlungen={len(entries)} "
            f"aufgabenlisten={len(task_lists(entries))} "
            "nur_probewerte=ja"
        )
        created.append(f"`{target.name}`")
    return created


def query_sets(protocol: str) -> dict[str, set[str]]:
    """The hit sets of the ``ABFRAGE`` lines of one raw file; a later run replaces an earlier."""
    sets: dict[str, set[str]] = {}
    for name, hits in re.findall(r"(?m)^ABFRAGE (\S+) status=207 treffer=(\S+)$", protocol):
        sets[name] = set() if hits == "keine" else set(hits.split(","))
    return sets


def fixture_queries() -> None:
    """A1: the hit sets of the six queries, compared over the four versions."""
    by_version: dict[str, dict[str, set[str]]] = {}
    for major in DELETE_MAJORS:
        path = RAW_DIR / f"discovery-{major}.txt"
        protocol = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        versions = re.findall(r"(?m)^VERSION OF RECORD (\S+)", protocol)
        by_version[versions[-1] if versions else f"{major} (keine Datei)"] = query_sets(protocol)
    differing = same_sets(by_version)
    for name, _ in QUERIES:
        if name not in differing:
            note(f"A1 abfrage={name} ungemessen grund=keine Zeile ABFRAGE in den Rohdateien")
            continue
        versions = differing[name]
        reference = next(
            (
                sets[name]
                for version, sets in by_version.items()
                if version not in versions and name in sets
            ),
            set(),
        )
        note(
            f"A1 abfrage={name} gleich={yes_no(not versions)} abweichend="
            f"{','.join(versions) or 'keine'} treffer={','.join(sorted(reference)) or 'keine'}"
        )
    complete = all(name in differing for name, _ in QUERIES) and len(by_version) == 4
    equal = complete and not any(differing.values())
    note(
        f"A1 alle_sechs_abfragen_auf_allen_versionen_gleich={yes_no(equal)} "
        f"versionen={','.join(by_version)} vollstaendig={yes_no(complete)}"
    )


def block_fixtures() -> None:
    """Fixtures out of the raw objects of plan 30-02 and the raw answers of this plan."""
    section(f"fixtures, start {now_stamp()}")
    section("discovery-fixtures")
    discovery_files = fixture_discovery()
    section("objekte der tasks-app")
    written = fixture_objects(discovery_files)
    section("annahmen A2 und A3")
    fixture_assumptions(written)
    section("abfragen A1")
    fixture_queries()


def block_ui_teardown(session: Session, ui: "UiOptions") -> None:
    """Hand the baseline of the kept run to the rollback and delete the login file.

    The rollback itself runs in the ``finally`` of ``run_blocks``: it deletes every account
    with the prefix, removes the Tasks app if it was not there before, and compares.
    """
    section("ui-teardown")
    ram_gate(NC35_CONTAINERS)
    if ui.out is None or not ui.out.is_file():
        raise RunFailed("ui-teardown appends to the protocol of the kept run; --out names it")
    before = baseline_from_protocol(ui.out.read_text(encoding="utf-8"))
    if not before:
        raise RunFailed(f"{ui.out.name} carries no BASELINE-START line to compare against")
    note(f"UI-TEARDOWN baseline aus {ui.out.name} gelesen: {len(before)} Felder")
    if ui.ui_file is not None and ui.ui_file.is_file():
        outside_repository(ui.ui_file).unlink()
        note("UI-TEARDOWN die Datei mit den Zugangsdaten des Browser-Kontos ist geloescht")
    session.before = before


@dataclass(frozen=True, slots=True)
class UiOptions:
    """The options of the browser blocks: snapshot label, seed, login file, protocol file."""

    label: str = ""
    seed_recurring: bool = False
    ui_file: Path | None = None
    out: Path | None = None

    def file(self) -> Path:
        if self.ui_file is None:
            raise RunFailed("--ui-file is required for the browser blocks")
        return self.ui_file


async def run_blocks(env: Mapping[str, str], blocks: Sequence[str], ui: UiOptions) -> None:
    """The named blocks in order; the rollback and the stop run whatever happened before.

    The rollback is put off only if a run with one of ``KEEP_BLOCKS`` came to its end: the
    browser session needs the accounts and lists, and ui-teardown takes them back later. A
    run that broke off is rolled back as ever, so a repeat starts from the baseline.
    """
    async with new_client() as client:
        session = Session(env=env, client=client)
        keep = False
        try:
            for name in blocks:
                if name == "nc35-up":
                    block_nc35_up()
                elif name == "controls":
                    await block_controls(session)
                elif name == "mkcol":
                    await block_mkcol(session)
                elif name == "groupfolder":
                    await block_groupfolder(session)
                elif name == "nachlauf":
                    await block_nachlauf(session)
                elif name == "modify":
                    await block_modify(session)
                elif name == "ui-prepare":
                    await block_ui_prepare(session, ui.file())
                elif name == "ui-snapshot":
                    await block_ui_snapshot(session, ui.label, ui.seed_recurring, ui.file())
                elif name == "ui-teardown":
                    block_ui_teardown(session, ui)
                elif name == "ui-log":
                    await block_ui_log(session, ui)
                elif name == "ui-evaluate":
                    block_ui_evaluate(ui)
                elif name == "move":
                    await block_move(session)
                elif name == "ui-evaluate-move":
                    block_ui_evaluate_move()
                elif name == "vtodo-create":
                    await block_vtodo_create(session)
                elif name == "inventory" and block_inventory():
                    raise RunFailed("inventory incomplete: an unruled hit or a missed place")
            keep = any(name in KEEP_BLOCKS for name in blocks)
        finally:
            try:
                if session.before is not None and keep:
                    note(
                        "RUECKBAU ausgesetzt: Konten, Listen und die Tasks-App bleiben fuer die "
                        "Browser-Sitzung stehen; der Block ui-teardown baut zurueck und "
                        "vergleicht mit den BASELINE-START-Zeilen dieses Laufs"
                    )
                elif session.before is not None:
                    rollback_nc35(session.before, env)
            finally:
                if "nc35-stop" in blocks:
                    block_nc35_stop()


def secret_scan(env_file: Path) -> int:
    """The gate before a commit: no secret in a raw file or the report, every quote real.

    Prints file and line number of a hit, never the value. The second half checks that every
    protocol line the report quotes below its raw output heading stands in a raw file.
    """
    env = read_env_file(env_file)
    remember_env_secrets(env)
    raw_files = (
        sorted(path for path in RAW_DIR.rglob("*") if path.is_file()) if RAW_DIR.is_dir() else []
    )
    raw_texts = {
        str(path.relative_to(REPO_ROOT)): path.read_text(encoding="utf-8", errors="replace")
        for path in raw_files
    }
    texts = dict(raw_texts)
    report = REPORT_FILE.read_text(encoding="utf-8") if REPORT_FILE.is_file() else ""
    if report:
        texts[str(REPORT_FILE.relative_to(REPO_ROOT))] = report
    hits = scan_for_secrets(texts, _secrets)
    for hit in hits:
        print(f"SECRET FOUND | {hit}")
    print(f"secret-scan: {len(texts)} files, {len(hits)} findings")
    missing = missing_quotes(report, raw_texts)
    for quote_ in missing:
        print(f"QUOTE NOT IN A RAW FILE | {quote_[:160]}")
    print(f"quotes: {len(quoted_lines(report))} checked, {len(missing)} missing")
    return 1 if hits or missing else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--env-file", default=".env.nc35", help="the file the bootstrap wrote")
    parser.add_argument(
        "--block",
        required=True,
        action="append",
        choices=BLOCKS,
        help="a block to run; repeat the option to run several in the order given",
    )
    parser.add_argument("--out", help="the protocol file this run appends to")
    parser.add_argument(
        "--repeat-reason",
        help="why this run repeats an earlier one; written as the line WIEDERHOLUNG Grund",
    )
    parser.add_argument(
        "--nc-tag",
        help="the image tag delete-matrix, discovery-matrix and cost start, e.g. 35.0.2-apache",
    )
    parser.add_argument(
        "--parts",
        default=",".join(DISCOVERY_PARTS),
        help=f"the parts of discovery-matrix, comma separated: {', '.join(DISCOVERY_PARTS)}",
    )
    parser.add_argument("--db", choices=COST_DBS, help="the database of the block cost")
    parser.add_argument(
        "--allow-other-tag",
        action="store_true",
        help="let delete-matrix start a patch release outside the four planned tags",
    )
    parser.add_argument("--label", choices=("a", "b"), help="the state ui-snapshot writes")
    parser.add_argument(
        "--seed-recurring",
        action="store_true",
        help="ui-snapshot creates the recurring task by PUT, if the Tasks app could not",
    )
    parser.add_argument(
        "--ui-file",
        help="the file outside the repository with user, password and base URL of the "
        "browser account, one per line; written by ui-prepare, read by ui-snapshot",
    )
    options = parser.parse_args(argv)
    blocks: list[str] = options.block
    if isinstance(sys.stdout, io.TextIOWrapper):
        # The protocol carries German prose; a Windows console code page must not garble it.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if "secret-scan" in blocks:
        if len(blocks) > 1:
            parser.error("secret-scan runs on its own")
        return secret_scan(Path(options.env_file))
    if "delete-verdict" in blocks:
        if len(blocks) > 1:
            parser.error("delete-verdict runs on its own")
        return block_delete_verdict()
    if not options.out:
        parser.error("--out is required for a measuring block")
    matrix_tag = ""
    throwaway = [name for name in ("delete-matrix", "discovery-matrix", "cost") if name in blocks]
    parts = [name.strip() for name in str(options.parts).split(",") if name.strip()]
    if "fixtures" in blocks and len(blocks) > 1:
        parser.error("fixtures runs on its own")
    if throwaway:
        if len(blocks) > 1:
            parser.error(f"{throwaway[0]} runs on its own, one version per call")
        if "cost" in blocks and not options.db:
            parser.error("--db is required for cost")
        if "discovery-matrix" in blocks and (
            not parts or any(name not in DISCOVERY_PARTS for name in parts)
        ):
            parser.error(f"--parts takes {', '.join(DISCOVERY_PARTS)}, comma separated")
        try:
            matrix_tag = validate_delete_tag(
                options.nc_tag or "", allow_other=options.allow_other_tag
            )
        except ValueError as failure:
            parser.error(str(failure))
    if "nc35-stop" in blocks and blocks[-1] != "nc35-stop":
        parser.error("nc35-stop has to be the last block")
    if {"ui-prepare", "ui-snapshot", "ui-log"} & set(blocks) and not options.ui_file:
        parser.error("--ui-file is required for ui-prepare, ui-snapshot and ui-log")
    if "ui-snapshot" in blocks and not options.label:
        parser.error("--label is required for ui-snapshot")
    ui = UiOptions(
        label=options.label or "",
        seed_recurring=options.seed_recurring,
        ui_file=Path(options.ui_file) if options.ui_file else None,
        out=Path(options.out),
    )

    out = Path(options.out)
    mode = "angehaengt an bestehende Datei" if out.exists() else "neue Datei"
    header = f"\n# Lauf blocks={','.join(blocks)} start={now_stamp()} ({mode})"
    # A throwaway instance has its own generated secrets and no ExApp, and the block
    # fixtures talks to nothing; the environment file of nc35 is neither needed nor read.
    standalone = bool(matrix_tag) or "fixtures" in blocks
    env = {} if standalone else read_env_file(Path(options.env_file))
    remember_env_secrets(env)
    os.environ.setdefault("PYTHONUTF8", "1")
    if options.repeat_reason:
        note(f"WIEDERHOLUNG Grund: {options.repeat_reason}")
    code = 0
    try:
        other = matrix_tag not in DELETE_TAGS
        if "delete-matrix" in blocks:
            asyncio.run(block_delete_matrix(matrix_tag, other=other))
        elif "discovery-matrix" in blocks:
            asyncio.run(block_discovery_matrix(matrix_tag, parts, other=other))
        elif "cost" in blocks:
            asyncio.run(block_cost(matrix_tag, options.db, other=other))
        elif "fixtures" in blocks:
            block_fixtures()
        else:
            asyncio.run(run_blocks(env, blocks, ui))
    except (RunFailed, ToolError, httpx.HTTPError) as failure:
        note(f"RUN FAILED | {type(failure).__name__}: {str(failure)[:300]}")
        code = 1
    finally:
        write_protocol(out, header)
    return code


if __name__ == "__main__":
    sys.exit(main())

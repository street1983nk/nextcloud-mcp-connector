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
baseline the kept run wrote), ``nc35-stop`` (``docker stop`` of the
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
import os
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Coroutine, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import httpx
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


def run(argv: Sequence[str], *, stdin: str | None = None, check: bool = True) -> str:
    """One external command, no shell, fixed argument list, output as text."""
    finished = subprocess.run(  # noqa: S603 - a fixed argument list, never a shell
        list(argv),
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
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


def mkcalendar_body(name: str) -> bytes:
    """A MKCALENDAR body for a list that takes VTODO only, as the Tasks app creates one."""
    root = etree.Element(f"{{{xml.CAL}}}mkcalendar", nsmap={"d": xml.DAV, "c": xml.CAL})
    prop = etree.SubElement(etree.SubElement(root, f"{{{xml.DAV}}}set"), f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}displayname").text = name
    comps = etree.SubElement(prop, f"{{{xml.CAL}}}supported-calendar-component-set")
    etree.SubElement(comps, f"{{{xml.CAL}}}comp", name="VTODO")
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


def block_ui_log(session: Session, ui: "UiOptions") -> None:
    """The writing requests of the browser account and the server errors behind a 5xx."""
    section("ui-log")
    ram_gate(NC35_CONTAINERS)
    user, password, _ = read_ui_file(ui.file())
    remember_secret(f"PASSWORD_{user}", password)
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
                    block_ui_log(session, ui)
                elif name == "ui-evaluate":
                    block_ui_evaluate(ui)
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
    if not options.out:
        parser.error("--out is required for a measuring block")
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
    env = read_env_file(Path(options.env_file))
    remember_env_secrets(env)
    os.environ.setdefault("PYTHONUTF8", "1")
    if options.repeat_reason:
        note(f"WIEDERHOLUNG Grund: {options.repeat_reason}")
    code = 0
    try:
        asyncio.run(run_blocks(env, blocks, ui))
    except (RunFailed, ToolError, httpx.HTTPError) as failure:
        note(f"RUN FAILED | {type(failure).__name__}: {str(failure)[:300]}")
        code = 1
    finally:
        write_protocol(out, header)
    return code


if __name__ == "__main__":
    sys.exit(main())

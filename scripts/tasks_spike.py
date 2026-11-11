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
with ACL, negative test, read-only external storage), ``nc35-stop`` (``docker stop`` of the
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
from urllib.parse import quote

import httpx
from lxml import etree

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import ocs, xml
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

#: Further blocks follow in plans 30-02 to 30-05.
BLOCKS = ("nc35-up", "controls", "mkcol", "groupfolder", "nc35-stop", "secret-scan")

#: The rows of the group folder measurement (plan 30-01 task 3), in the order they run.
GF_KEYS = (
    "acl-rw",
    "acl-ro",
    "acl-ro-kontrolle-b",
    "acl-ro-nach-regelentzug",
    "gruppe-nur-lesen",
)

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
    for user in (env.get("NC_MCP_TEST_USER", ""), USER_A, USER_B):
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
    for app in sorted(disabled):
        if app in was_enabled:
            note(f"occ app:enable {app} -> {occ(NC_CONTAINER, 'app:enable', app, check=False)}")
        elif app not in was_disabled:
            note(f"occ app:remove {app} -> {occ(NC_CONTAINER, 'app:remove', app, check=False)}")


def rollback_nc35(before: Mapping[str, str], env: Mapping[str, str]) -> None:
    """Take everything back and compare against the baseline, as the last protocol lines."""
    section("rueckbau")
    remove_spike_objects()
    restore_apps(before)
    left = _names_with_prefix("user:list") + _names_with_prefix("group:list")
    note(f"RUECKBAU reste_mit_praefix_{PREFIX}={left or 'keine'}")
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


async def run_blocks(env: Mapping[str, str], blocks: Sequence[str]) -> None:
    """The named blocks in order; the rollback and the stop run whatever happened before."""
    async with new_client() as client:
        session = Session(env=env, client=client)
        try:
            for name in blocks:
                if name == "nc35-up":
                    block_nc35_up()
                elif name == "controls":
                    await block_controls(session)
                elif name in ("mkcol", "groupfolder"):
                    raise RunFailed(f"block {name} is not built yet (plan 30-01, tasks 2 and 3)")
        finally:
            try:
                if session.before is not None:
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
        asyncio.run(run_blocks(env, blocks))
    except (RunFailed, ToolError, httpx.HTTPError) as failure:
        note(f"RUN FAILED | {type(failure).__name__}: {str(failure)[:300]}")
        code = 1
    finally:
        write_protocol(out, header)
    return code


if __name__ == "__main__":
    sys.exit(main())

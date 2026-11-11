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

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import dav, ocs, xml
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
BLOCKS = (
    "nc35-up",
    "controls",
    "mkcol",
    "groupfolder",
    "nachlauf",
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
                elif name == "mkcol":
                    await block_mkcol(session)
                elif name == "groupfolder":
                    await block_groupfolder(session)
                elif name == "nachlauf":
                    await block_nachlauf(session)
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

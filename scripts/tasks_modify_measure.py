"""The measurements of plans 33-01, 33-01b and 33-01c, taken before the modifying task tools.

Phase 33 builds ``tasks_complete``, ``tasks_update`` and ``tasks_move``. Before any product
code exists, this program asks a running Nextcloud what the research could only read:

* ``snapshot`` and ``diff`` (M-1, M-2, CANCELLED): every object of one list read under
  impersonation, raw bytes and ETag per object, cross-checked against a REPORT with the app
  password; two snapshots compared line by line, per field in the form of a removal;
* ``chain`` (M-3): the wall clock of one REPORT plus 51 conditional writes (``PUT`` with
  ``If-Match`` or ``MOVE`` with ``Overwrite: F`` and ``If-Match``), descendants in post
  order, the root last, for a chain of depth 1 or 3;
* ``etag-altered`` (M-4): whether an accepted ``PUT`` with ``If-Match`` still answers with a
  strong ETag when the server could change the text on storing it;
* ``baseline``: the counts of 33-RULES.md section 7 per account, read through PHP;
* ``cleanup``: every list of this plan dropped without trash bin, the trash bin emptied;
* ``inventory``: the A17 inventory of the spike on HEAD, each place assigned to one plan;
* ``cap``: the chain cap from the slowest whole chain, by the rule fixed before measuring.

Subcommands::

    uv run --no-sync python scripts/tasks_modify_measure.py inventory
    uv run --no-sync python scripts/tasks_modify_measure.py baseline --instance nc35 \
        --accounts alice,bob --phase vorher --protocol <file>
    uv run --no-sync python scripts/tasks_modify_measure.py snapshot --instance nc35 \
        --env-file .env.nc35 --account alice --list p3301-liste-1 --out <dir> --protocol <file>
    uv run --no-sync python scripts/tasks_modify_measure.py diff --before <dir> --after <dir> \
        --protocol <file>
    uv run --no-sync python scripts/tasks_modify_measure.py chain --instance nc35 \
        --env-file .env.nc35 --mode put --depth 1 --runs 5 --protocol <file>
    uv run --no-sync python scripts/tasks_modify_measure.py etag-altered --instance nc35 \
        --env-file .env.nc35 --protocol <file>
    uv run --no-sync python scripts/tasks_modify_measure.py cleanup --instance nc35 \
        --env-file .env.nc35 --accounts alice --protocol <file>
    uv run --no-sync python scripts/tasks_modify_measure.py cap --max-seconds 12.3 \
        --protocol <file>

No subcommand starts, stops or registers anything: the instance stands already (``up`` and
``stop`` of ``scripts/tasks_measure.py``). Writes go strictly one after the other, never in
parallel (SQLite). The helpers of the spike and of ``scripts/tasks_measure.py`` are loaded by
path and not copied. Every protocol line goes through the secret scan of the spike.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import os
import re
import secrets
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote, urlsplit

import httpx

from mcp_connector.nextcloud.clients import xml
from mcp_connector.nextcloud.credentials import Credentials

REPO_ROOT = Path(__file__).resolve().parents[1]
MEASURE_FILE = REPO_ROOT / "scripts" / "tasks_measure.py"
PHASE_DIR = REPO_ROOT / ".planning" / "phases" / "33-aufgaben-aendern"
BASE_FILE = PHASE_DIR / "33-BASE.txt"
INVENTORY_OUT = PHASE_DIR / "raw" / "33-01-inventar.txt"
REPORT_FILE = REPO_ROOT / "docs" / "spike-tasks.md"


def _load_measure() -> ModuleType:
    """The measuring program of phase 32; it loads the spike of phase 30 itself."""
    spec = importlib.util.spec_from_file_location("tasks_measure", MEASURE_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{MEASURE_FILE} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


measure = _load_measure()
spike = measure.spike
derive_budget = measure.derive_budget

# --- what this round creates ---------------------------------------------------------------------

#: Every list, task and account of phase 33 carries this prefix; ``cleanup`` goes by it.
PREFIX = "p3301"
LIST_CHAIN_A = f"{PREFIX}-kette-a"
LIST_CHAIN_B = f"{PREFIX}-kette-b"
LIST_ETAG = f"{PREFIX}-etag"
CHAIN_SIZE = 50
#: The app passwords of the two measuring accounts in the environment file.
PASSWORD_KEYS = {"alice": "NC_MCP_TEST_APP_PASSWORD", "bob": "NC_MCP_TEST_APP_PASSWORD2"}
STAMP = "20261113T120000Z"
ETAG_CASES = ("ohne-prodid", "lf", "uid-case")
#: The fields M-2 removes, by the name the protocol gives them.
FIELDS = {
    "due": "DUE",
    "start": "DTSTART",
    "description": "DESCRIPTION",
    "priority": "PRIORITY",
    "tags": "CATEGORIES",
    "parent": "RELATED-TO",
}
GETETAG = f"{{{xml.DAV}}}getetag"
CALENDAR_DATA = f"{{{xml.CAL}}}calendar-data"
PREVIOUS_PHASE_33 = 62


def note(line: str) -> None:
    spike.note(line)


def yes_no(value: bool) -> str:
    return "ja" if value else "nein"


# --- pure helpers (tests/unit/test_tasks_modify_measure.py) --------------------------------------


def _split_line(line: str) -> tuple[str, str]:
    """``(name with parameters, value)`` of a content line; a ``:`` in quotes does not split."""
    quoted = False
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == ":" and not quoted:
            return line[:index], line[index + 1 :]
    return line, ""


def _todo_lines(text: str) -> dict[str, list[str]]:
    """Logical lines directly inside ``VCALENDAR/VTODO``, by property name, sorted per name."""
    stack: list[str] = []
    found: dict[str, list[str]] = {}
    for line in spike.unfold(text).split("\n"):
        if not line.strip():
            continue
        upper = line.strip().upper()
        if upper.startswith("BEGIN:"):
            stack.append(upper[6:])
            continue
        if upper.startswith("END:"):
            if stack:
                stack.pop()
            continue
        if stack != ["VCALENDAR", "VTODO"]:
            continue
        found.setdefault(spike.property_name(line), []).append(line.rstrip())
    return {name: sorted(lines) for name, lines in found.items()}


def _all_empty(lines: Sequence[str]) -> bool:
    return bool(lines) and all(not _split_line(line)[1].strip() for line in lines)


def line_diff(before: str, after: str) -> dict[str, list[str]]:
    """Which property names of the task were added, removed, changed or cleared.

    Compared are the unfolded logical lines of the stack ``VCALENDAR/VTODO`` only, so the
    ``DESCRIPTION`` of an alarm does not count. A line ``NAME:`` with an empty value where a
    value stood before counts as ``leer``, not as ``entfernt``.
    """
    old = _todo_lines(before)
    new = _todo_lines(after)
    result: dict[str, list[str]] = {"hinzu": [], "entfernt": [], "geaendert": [], "leer": []}
    for name in sorted(old.keys() | new.keys()):
        was = old.get(name, [])
        now = new.get(name, [])
        if was == now:
            continue
        if not was:
            result["hinzu"].append(name)
        elif not now:
            result["entfernt"].append(name)
        elif _all_empty(now) and not _all_empty(was):
            result["leer"].append(name)
        else:
            result["geaendert"].append(name)
    return result


def removal_form(before: str, after: str, name: str) -> str:
    """``zeile-weg``, ``leer``, ``wert-0`` or ``unveraendert``; any other change ``geaendert``."""
    was = _todo_lines(before).get(name, [])
    now = _todo_lines(after).get(name, [])
    if was == now:
        return "unveraendert"
    if was and not now:
        return "zeile-weg"
    if _all_empty(now):
        return "leer"
    if now and all(_split_line(line)[1].strip() == "0" for line in now):
        return "wert-0"
    return "geaendert"


@dataclass(frozen=True, slots=True)
class ChainObject:
    """One descendant of a chain: its UID, its parent's UID, its level and its text."""

    uid: str
    parent: str
    level: int
    text: str


def todo_text(uid: str, summary: str, parent: str | None = None) -> str:
    """A plain open task with CRLF line ends, the form the server stores verbatim."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//p3301//tasks_modify_measure//EN",
        "BEGIN:VTODO",
        f"UID:{uid}",
        f"DTSTAMP:{STAMP}",
        f"CREATED:{STAMP}",
        f"LAST-MODIFIED:{STAMP}",
        f"SUMMARY:{summary}",
        "STATUS:NEEDS-ACTION",
    ]
    if parent is not None:
        lines.append(f"RELATED-TO:{parent}")
    lines += ["END:VTODO", "END:VCALENDAR", ""]
    return "\r\n".join(lines)


def _level_sizes(count: int, depth: int) -> list[int]:
    if depth not in (1, 3):
        raise ValueError(f"depth must be 1 or 3, not {depth}")
    base, rest = divmod(count, depth)
    return [base + (1 if index < rest else 0) for index in range(depth)]


def chain_objects(parent_uid: str, count: int, depth: int, prefix: str) -> list[ChainObject]:
    """``count`` descendants of ``parent_uid``, every parent listed before its children.

    Depth 1: all children of the root. Depth 3: spread evenly over three levels, the parents
    of one level taken in turn from the level above.
    """
    found: list[ChainObject] = []
    parents = [parent_uid]
    number = 0
    for level, size in enumerate(_level_sizes(count, depth), start=1):
        current: list[str] = []
        for index in range(size):
            number += 1
            uid = f"{prefix}-{number:03d}"
            parent = parents[index % len(parents)]
            found.append(ChainObject(uid, parent, level, todo_text(uid, uid, parent)))
            current.append(uid)
        parents = current or parents
    return found


def write_order(root_uid: str, objects: Sequence[ChainObject]) -> list[str]:
    """Descendants in post order (every child before its parent), the root last."""
    return [obj.uid for obj in reversed(objects)] + [root_uid]


def completed_text(text: str, stamp: str) -> str:
    """The fields of checking a task off, in the line ends of ``text``."""
    newline = "\r\n" if "\r\n" in text else "\n"
    done = newline.join(["STATUS:COMPLETED", "PERCENT-COMPLETE:100", f"COMPLETED:{stamp}"])
    kept = [line for line in text.split(newline) if not line.upper().startswith("STATUS:")]
    end = kept.index("END:VTODO")
    return newline.join([*kept[:end], done, *kept[end:]])


def chain_cap(max_total_seconds: float, limit_seconds: int = 30, base: int = 50) -> int:
    """The rule of 33-01c task 1, fixed before the measurement.

    ``base`` stays if the budget of the slowest whole chain is at most ``limit_seconds``;
    otherwise the largest multiple of 5 whose share of that chain keeps the budget within
    the limit, but never below 10.
    """
    if derive_budget(max_total_seconds) <= limit_seconds:
        return base
    cap = base - 5
    while cap > 10:
        if derive_budget(max_total_seconds * cap / base) <= limit_seconds:
            return cap
        cap -= 5
    return 10


# --- inventory assignment -------------------------------------------------------------------------

GATE_FILE = "tests/contract/test_no_destructive_calls.py"
CLASS_FILES = (
    "tests/contract/test_tool_classes.py",
    "tests/contract/tool_classes.py",
    "tests/contract/test_tool_surface.py",
)


def assign(file: str, klasse: str, methods: str, target: str) -> tuple[str, str, str]:
    """``(touched, plan, reason)`` of one inventory place; an empty plan means unassigned."""
    named = {part.strip() for part in methods.split(",")}
    touched = ",".join(method for method in ("PUT", "MOVE") if method in named)
    if not touched:
        return "", "entfaellt", "TMOD-07 gestrichen"
    if target == "Phase 34":
        return touched, "34", "Zusage-Text"
    if target != "Phase 33":
        return touched, "", ""
    if file == GATE_FILE:
        return touched, "33-03", "Destruktiv-Gate und PUT-/MOVE-Zaehlung"
    if klasse == "annotation":
        return touched, "33-02", "Annotationen"
    if klasse == "audit":
        return touched, "33-02", "Audit-Gate"
    if file in CLASS_FILES:
        return touched, "33-02", "Klassen und Annotationen der Werkzeugflaeche"
    if klasse == "kanarie":
        return touched, "33-09", "Kanarie"
    return touched, "", ""


def _cells(row: str) -> list[str]:
    inner = row.strip()
    inner = inner.removeprefix("|").removesuffix("|")
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", inner)]


def previous_places(report: str) -> list[tuple[str, str]]:
    """``(file, wording)`` of every Phase 33 row of section 7.1 of the spike report."""
    found: list[tuple[str, str]] = []
    inside = False
    for line in report.splitlines():
        if line.startswith("### "):
            inside = line.startswith("### 7.1")
            continue
        if not inside or not line.startswith("| "):
            continue
        cells = _cells(line)
        if len(cells) < 6 or cells[4] != "Phase 33":
            continue
        file = cells[1].strip("`").rsplit(":", 1)[0]
        found.append((file, cells[2]))
    return found


def match_places(
    previous: Sequence[tuple[str, str]], current: Sequence[tuple[str, int, str]]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Current places the report did not list, and report places no longer found.

    Matched by file and wording (the report cut the wording short and wrote backticks as
    apostrophes), never by line number: the lines moved since the report.
    """
    left = list(previous)
    new: list[str] = []
    for file, line, text in current:
        plain = text.replace("`", "'")
        for index, (old_file, wording) in enumerate(left):
            if old_file == file and plain.startswith(wording.rstrip()):
                del left[index]
                break
        else:
            new.append(f"{file}:{line}")
    return new, left


# --- instance helpers -----------------------------------------------------------------------------


def basic(env: Mapping[str, str], base: str, account: str, key: str | None) -> Credentials:
    """The app password of ``account``: from the environment file, else the process."""
    name = key or PASSWORD_KEYS.get(account, "")
    if not name:
        raise spike.RunFailed(f"no app password key known for {account}; pass --password-key")
    if name not in env:
        value = os.environ.get(name, "")
        env = {**env, name: value}
    return measure.basic_creds(env, base, account, name)


def header(result: object, name: str) -> str:
    for key, value in getattr(result, "headers", ()):
        if key.lower() == name.lower():
            return value
    return ""


def _uid_of(text: str) -> str:
    match = re.search(r"^UID[;:](.*)$", spike.unfold(text), re.MULTILINE)
    return _split_line(match.group(0))[1].strip() if match else ""


def _short(uid: str) -> str:
    return uid[:8] if not uid.startswith(PREFIX) else uid


async def _report(
    client: httpx.AsyncClient, creds: Credentials, list_uri: str
) -> dict[str, tuple[str, str, str]]:
    """``uid -> (path, etag, text)`` of one list, from a calendar-query without a filter."""
    result = await spike.dav_request(
        client,
        creds,
        "REPORT",
        measure.list_url(creds.base_url, creds.user, list_uri),
        depth="1",
        body=spike.report_body("calendar-query"),
    )
    if result.status != 207:
        raise spike.RunFailed(f"REPORT {list_uri} answered {result.status}")
    found: dict[str, tuple[str, str, str]] = {}
    for href, props in xml.parse_multistatus(result.body):
        text = props.get(CALENDAR_DATA, "")
        if text:
            found[_uid_of(text)] = (urlsplit(href).path, props.get(GETETAG, ""), text)
    return found


async def ensure_list(client: httpx.AsyncClient, creds: Credentials, uri: str) -> None:
    probe = await spike.dav_request(
        client,
        creds,
        "PROPFIND",
        measure.list_url(creds.base_url, creds.user, uri),
        depth="0",
        body=spike.propfind_body((GETETAG,)),
    )
    if probe.status == 404:
        await measure.make_list(client, creds, uri)
    elif probe.status != 207:
        raise spike.RunFailed(f"PROPFIND {uri} answered {probe.status}")


async def drop_objects(
    client: httpx.AsyncClient, creds: Credentials, list_uri: str, prefix: str
) -> tuple[int, set[int]]:
    """Every object of ``list_uri`` whose UID starts with ``prefix``, without trash bin."""
    statuses: set[int] = set()
    count = 0
    for uid, (path, _, _) in (await _report(client, creds, list_uri)).items():
        if not uid.startswith(prefix):
            continue
        gone = await spike.dav_request(
            client, creds, "DELETE", f"{creds.base_url}{path}", extra_headers=measure.NO_TRASHBIN
        )
        statuses.add(gone.status)
        count += 1
    return count, statuses


# --- baseline ---------------------------------------------------------------------------------


def baseline(instance: str, accounts: Sequence[str], phase: str) -> None:
    target = measure.TARGETS[instance]
    for account in accounts:
        raw = spike.php(target.container, measure.PHP_BASELINE, account).split()
        if len(raw) != 5 or not all(part.isdigit() for part in raw):
            raise spike.RunFailed(f"the baseline of {account} could not be read: {raw}")
        note(
            f"BASELINE {instance} konto={account} calendars={raw[0]} objekte={raw[1]} "
            f"geloescht={raw[2]} shares={raw[4]} abos={raw[3]} phase={phase}"
        )


# --- snapshot and diff ------------------------------------------------------------------------


async def snapshot(
    instance: str,
    env: Mapping[str, str],
    account: str,
    list_uri: str,
    out: Path,
    password_key: str | None,
) -> dict[str, tuple[str, bytes]]:
    """Every object of one list under impersonation: object name -> (ETag, raw bytes).

    The cross-check reads the same list with a REPORT and the app password. The XML parser
    turns CRLF into LF inside ``calendar-data``, so texts are compared with LF line ends.
    """
    target = measure.TARGETS[instance]
    spike.section(f"snapshot {instance} liste={list_uri}")
    imp = measure.appapi_creds(env, target.base_url, account)
    app = basic(env, target.base_url, account, password_key)
    files: dict[str, tuple[str, bytes]] = {}
    async with spike.new_client() as client:
        listing = await spike.dav_request(
            client,
            imp,
            "PROPFIND",
            measure.list_url(target.base_url, account, list_uri),
            depth="1",
            body=spike.propfind_body((GETETAG,)),
        )
        if listing.status != 207:
            raise spike.RunFailed(f"PROPFIND {list_uri} answered {listing.status}")
        read: dict[str, tuple[str, bytes]] = {}
        for href, props in xml.parse_multistatus(listing.body):
            path = urlsplit(href).path
            if not path.endswith(".ics"):
                continue
            got = await spike.dav_request(
                client, imp, "GET", f"{target.base_url}{path}", content_type=None
            )
            name = unquote(path.rsplit("/", 1)[-1])
            etag = header(got, "ETag") or props.get(GETETAG, "")
            files[name] = (etag, got.body)
            read[path] = (etag, got.body)
            note(f"SNAPSHOT objekt={name} status={got.status} bytes={len(got.body)}")
        cross = await _report(client, app, list_uri)
    by_path = {path: (etag, text) for path, etag, text in cross.values()}
    same = by_path.keys() == read.keys() and all(
        by_path[path][0] == etag and spike.plain(by_path[path][1]) == spike.plain(body.decode())
        for path, (etag, body) in read.items()
    )
    note(f"SNAPSHOT gleich_appapi_basic={yes_no(same)} objekte={len(read)} ziel={out.name}")
    return files


def save_snapshot(out: Path, files: Mapping[str, tuple[str, bytes]]) -> None:
    """Raw bytes byte-exact (never through ``read_text``) and the ETag next to each object."""
    out.mkdir(parents=True, exist_ok=True)
    for name, (etag, body) in files.items():
        (out / name).write_bytes(body)
        (out / f"{name}.etag").write_text(etag, encoding="utf-8")


def _read_dir(folder: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted(folder.glob("*.ics")):
        text = path.read_bytes().decode("utf-8")
        found[_uid_of(text)] = text
    return found


def diff(before: Path, after: Path) -> None:
    spike.section(f"diff {before.name} -> {after.name}")
    old = _read_dir(before)
    new = _read_dir(after)
    for uid in sorted(old.keys() | new.keys()):
        if uid not in new:
            note(f"DIFF uid={_short(uid)} objekt=weg")
            continue
        if uid not in old:
            note(f"DIFF uid={_short(uid)} objekt=neu")
            continue
        found = line_diff(old[uid], new[uid])
        forms = " ".join(
            f"form_{field}={form}"
            for field, name in FIELDS.items()
            if (form := removal_form(old[uid], new[uid], name)) != "unveraendert"
        )
        parts = " ".join(f"{key}={','.join(names) or '-'}" for key, names in found.items())
        note(f"DIFF uid={_short(uid)} {parts} {forms}".rstrip())


# --- M-3: chain --------------------------------------------------------------------------------


async def _build_chain(
    client: httpx.AsyncClient, app: Credentials, root: str, objects: Sequence[ChainObject]
) -> None:
    texts = [(root, todo_text(root, root)), *((obj.uid, obj.text) for obj in objects)]
    for uid, text in texts:
        status = await measure.put_task(client, app, LIST_CHAIN_A, f"{uid}.ics", text)
        if status != 201:
            raise spike.RunFailed(f"building the chain: PUT {uid} answered {status}")


async def _write_chain(
    client: httpx.AsyncClient, imp: Credentials, mode: str, order: Sequence[str]
) -> tuple[float, float, set[int]]:
    """One REPORT and the writes in ``order``; returns both wall clocks in ms and statuses."""
    started = time.perf_counter()
    listed = await _report(client, imp, LIST_CHAIN_A)
    reported = time.perf_counter()
    statuses: set[int] = set()
    for uid in order:
        path, etag, text = listed[uid]
        url = f"{imp.base_url}{path}"
        if mode == "put":
            result = await spike.dav_request(
                client,
                imp,
                "PUT",
                url,
                body=completed_text(text, STAMP).encode(),
                content_type=spike.ICS_TYPE,
                extra_headers={"If-Match": etag},
            )
        else:
            name = path.rsplit("/", 1)[-1]
            destination = f"{measure.list_url(imp.base_url, imp.user, LIST_CHAIN_B)}{name}"
            result = await spike.dav_request(
                client,
                imp,
                "MOVE",
                url,
                content_type=None,
                extra_headers={"Destination": destination, "Overwrite": "F", "If-Match": etag},
            )
        statuses.add(result.status)
    written = time.perf_counter()
    return (reported - started) * 1000, (written - reported) * 1000, statuses


async def chain(instance: str, env: Mapping[str, str], mode: str, depth: int, runs: int) -> None:
    target = measure.TARGETS[instance]
    spike.section(f"kette {instance} modus={mode} tiefe={depth}")
    account = target.alice
    imp = measure.appapi_creds(env, target.base_url, account)
    app = basic(env, target.base_url, account, None)
    totals: list[float] = []
    async with spike.new_client() as client:
        for uri in (LIST_CHAIN_A, LIST_CHAIN_B):
            await ensure_list(client, app, uri)
        for run in range(1, runs + 1):
            tag = f"{PREFIX}-k{depth}-{secrets.token_hex(3)}"
            root = f"{tag}-root"
            objects = chain_objects(root, CHAIN_SIZE, depth, tag)
            try:
                await _build_chain(client, app, root, objects)
                await spike.wait_until_idle(target.containers)
                async with spike.new_client() as measuring:
                    report_ms, write_ms, statuses = await _write_chain(
                        measuring, imp, mode, write_order(root, objects)
                    )
                total = report_ms + write_ms
                totals.append(total)
                note(
                    f"KETTE {instance} modus={mode} tiefe={depth} lauf={run} "
                    f"report_ms={report_ms:.0f} schreiben_ms={write_ms:.0f} gesamt_ms={total:.0f} "
                    f"status={sorted(statuses)}"
                )
            finally:
                for uri in (LIST_CHAIN_A, LIST_CHAIN_B):
                    count, gone = await drop_objects(client, app, uri, tag)
                    note(
                        f"RUECKBAU kette lauf={run} liste={uri} objekte={count} "
                        f"status={sorted(gone)} no_trashbin=1"
                    )
    if totals:
        note(
            f"KETTE {instance} modus={mode} tiefe={depth} min_ms={min(totals):.0f} "
            f"median_ms={statistics.median(totals):.0f} max_ms={max(totals):.0f} "
            f"laeufe={len(totals)}"
        )


# --- M-4: etag after an altered text -----------------------------------------------------------


def altered_text(original: str, case: str) -> str:
    """The changed text of one case of M-4: a new summary plus the alteration of the case."""
    text = original.replace("SUMMARY:", "SUMMARY:geaendert ", 1)
    if case == "ohne-prodid":
        return "\r\n".join(line for line in text.split("\r\n") if not line.startswith("PRODID:"))
    if case == "lf":
        return text.replace("\r\n", "\n")
    if case == "uid-case":
        uid = _uid_of(text)
        return text.replace(f"UID:{uid}", f"UID:{uid.swapcase()}", 1)
    raise ValueError(f"unknown case {case!r}")


async def etag_altered(instance: str, env: Mapping[str, str]) -> None:
    target = measure.TARGETS[instance]
    spike.section(f"etag-altered {instance}")
    account = target.alice
    imp = measure.appapi_creds(env, target.base_url, account)
    app = basic(env, target.base_url, account, None)
    run = secrets.token_hex(3)
    async with spike.new_client() as client:
        await ensure_list(client, app, LIST_ETAG)
        for case in ETAG_CASES:
            uid = f"{PREFIX}-etag-{run}-{case}" + ("-MiXeD" if case == "uid-case" else "")
            name = f"{uid.lower()}.ics"
            url = measure.object_url(target.base_url, account, LIST_ETAG, name)
            original = todo_text(uid, f"{PREFIX} etag {case}")
            try:
                made = await measure.put_task(client, imp, LIST_ETAG, name, original)
                if made != 201:
                    note(f"ETAGFORM {instance} fall={case} anlegen_status={made}")
                    continue
                got = await spike.dav_request(client, imp, "GET", url, content_type=None)
                sent = altered_text(original, case).encode()
                put = await spike.dav_request(
                    client,
                    imp,
                    "PUT",
                    url,
                    body=sent,
                    content_type=spike.ICS_TYPE,
                    extra_headers={"If-Match": header(got, "ETag")},
                )
                in_head = header(put, "ETag")
                stored = spike.php(target.container, spike.PHP_OBJECT_HASH, name).split()
                wanted = f"{hashlib.sha256(sent).hexdigest()}:{len(sent)}"
                same = "unklar" if not stored or stored[0] != "1" else yes_no(stored[1] == wanted)
                after = await spike.dav_request(client, imp, "GET", url, content_type=None)
                head_vs_get = yes_no(in_head == header(after, "ETag")) if in_head else "-"
                note(
                    f"ETAGFORM {instance} fall={case} status={put.status} "
                    f"etag_im_kopf={yes_no(bool(in_head))} text_gleich_gesendet={same} "
                    f"etag_gleich_get={head_vs_get}"
                )
            finally:
                gone = await spike.dav_request(
                    client, app, "DELETE", url, extra_headers=measure.NO_TRASHBIN
                )
                note(f"RUECKBAU etag fall={case} status={gone.status} no_trashbin=1")


# --- cleanup -----------------------------------------------------------------------------------


async def _own_lists(client: httpx.AsyncClient, creds: Credentials) -> list[str]:
    result = await spike.dav_request(
        client,
        creds,
        "PROPFIND",
        measure.home_url(creds.base_url, creds.user),
        depth="1",
        body=spike.propfind_body(measure.NAME_PROPS),
    )
    if result.status != 207:
        return []
    return [
        entry.uri
        for entry in spike.parse_home(result.body)
        if entry.uri.startswith(PREFIX) and "_shared_by_" not in entry.uri
    ]


async def _purge_trash(client: httpx.AsyncClient, creds: Credentials) -> tuple[int, int]:
    url = f"{measure.home_url(creds.base_url, creds.user)}trashbin/objects/"
    listed = await spike.dav_request(
        client, creds, "REPORT", url, depth="1", body=spike.report_body("calendar-query")
    )
    if listed.status != 207:
        note(f"PAPIERKORB konto={creds.user} objects status={listed.status}")
        return 0, 0
    found = 0
    cleared = 0
    for href, props in xml.parse_multistatus(listed.body):
        if not _uid_of(props.get(CALENDAR_DATA, "")).startswith(PREFIX):
            continue
        gone = await spike.dav_request(
            client,
            creds,
            "DELETE",
            f"{creds.base_url}{urlsplit(href).path}",
            extra_headers=measure.NO_TRASHBIN,
        )
        found += 1
        cleared += 1 if gone.status in (200, 204) else 0
    return found, cleared


async def cleanup(instance: str, env: Mapping[str, str], accounts: Sequence[str]) -> None:
    target = measure.TARGETS[instance]
    spike.section(f"rueckbau {instance}")
    async with spike.new_client() as client:
        for account in accounts:
            creds = measure.appapi_creds(env, target.base_url, account)
            for _ in range(2):  # a dropped list may stay as a deleted calendar once
                for uri in await _own_lists(client, creds):
                    gone = await spike.dav_request(
                        client,
                        creds,
                        "DELETE",
                        measure.list_url(target.base_url, account, uri),
                        extra_headers=measure.NO_TRASHBIN,
                    )
                    note(f"RUECKBAU liste_geloescht konto={account} status={gone.status}")
            found, cleared = await _purge_trash(client, creds)
            note(f"PAPIERKORB {instance} konto={account} gefunden={found} geleert={cleared}")
            left = await _own_lists(client, creds)
            note(f"RUECKBAU reste konto={account} listen_mit_praefix={len(left)}")


# --- inventory ---------------------------------------------------------------------------------


def base_sha() -> str:
    sha = BASE_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise spike.RunFailed(f"{BASE_FILE.name} holds no full SHA")
    return sha


def inventory() -> int:
    """A17 on HEAD with the unchanged patterns of the spike, each place assigned to a plan."""
    note(f"INVENTAR BASIS {base_sha()}")
    code = spike.block_inventory()
    first, second = spike.inventory_hits(REPO_ROOT)
    merged = spike.merge_hits(first, second)
    verdicts = [(hit, spike.classify(hit, spike.INVENTORY_RULES)) for hit in merged]
    kept = [(hit, verdict) for hit, verdict in verdicts if verdict[0] != "ausgeschlossen"]
    spike.section("zuordnung")
    missing = 0
    plans: dict[str, int] = {}
    for hit, (klasse, methods, target) in kept:
        touched, plan, reason = assign(hit.file, klasse, methods, target)
        if not plan:
            missing += 1
        plans[plan or "OHNE"] = plans.get(plan or "OHNE", 0) + 1
        note(
            f"ZUORDNUNG {hit.file}:{hit.line} beruehrt={touched or 'DELETE'} plan={plan} "
            f"grund={reason or 'keine Regel'} klasse={klasse}"
        )
    phase33 = [(hit.file, hit.line, hit.text) for hit, v in kept if v[2] == "Phase 33"]
    note(
        f"INVENTAR ZUORDNUNG SUMME phase33={len(phase33)} "
        + " ".join(f"{plan}={count}" for plan, count in sorted(plans.items()))
        + f" ohne_plan={missing}"
    )
    report = REPORT_FILE.read_text(encoding="utf-8")
    previous = previous_places(report)
    new, gone = match_places(previous, phase33)
    note(
        f"INVENTAR VERGLEICH bericht_7_1_phase33={len(previous)} jetzt={len(phase33)} "
        f"neu={len(new)} nicht_mehr_gefunden={len(gone)}"
    )
    if len(phase33) != PREVIOUS_PHASE_33:
        note(f"INVENTAR ABWEICHUNG vorher={PREVIOUS_PHASE_33} jetzt={len(phase33)} neu={new}")
    for file, wording in gone:
        note(f"INVENTAR WEG {file} | {wording[:120]}")
    return 1 if code or missing else 0


# --- main --------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--out", type=Path, default=INVENTORY_OUT)
    base = sub.add_parser("baseline")
    base.add_argument("--accounts", required=True)
    base.add_argument("--phase", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--account", required=True)
    snap.add_argument("--list", dest="list_uri", required=True)
    snap.add_argument("--out", type=Path, required=True)
    snap.add_argument("--password-key")
    compare = sub.add_parser("diff")
    compare.add_argument("--before", type=Path, required=True)
    compare.add_argument("--after", type=Path, required=True)
    links = sub.add_parser("chain")
    links.add_argument("--mode", choices=("put", "move"), required=True)
    links.add_argument("--depth", type=int, choices=(1, 3), required=True)
    links.add_argument("--runs", type=int, default=5)
    etag = sub.add_parser("etag-altered")
    clean = sub.add_parser("cleanup")
    clean.add_argument("--accounts", required=True)
    cap = sub.add_parser("cap")
    cap.add_argument("--max-seconds", type=float, required=True)
    for command in (base, snap, links, etag, clean):
        command.add_argument("--instance", choices=sorted(measure.TARGETS), required=True)
    for command in (snap, links, etag, clean):
        command.add_argument("--env-file", type=Path, required=True)
    for command in (base, snap, compare, links, etag, clean, cap):
        command.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args(argv)

    out: Path = args.out if args.command == "inventory" else args.protocol
    if args.command == "inventory" and out.exists():
        out.unlink()
    header_line = f"# tasks_modify_measure.py {args.command} {spike.now_stamp()}"
    code = 0
    try:
        if args.command == "inventory":
            code = inventory()
        elif args.command == "diff":
            diff(args.before, args.after)
        elif args.command == "cap":
            note(
                f"CAP chain_cap={chain_cap(args.max_seconds)} max_gesamt_s={args.max_seconds} "
                f"budget_s={derive_budget(args.max_seconds)} regel=33-01c-task-1"
            )
        elif args.command == "baseline":
            baseline(args.instance, args.accounts.split(","), args.phase)
        else:
            env = measure._env(args.env_file)
            if args.command == "snapshot":
                files = asyncio.run(
                    snapshot(
                        args.instance, env, args.account, args.list_uri, args.out, args.password_key
                    )
                )
                save_snapshot(args.out, files)
            elif args.command == "chain":
                asyncio.run(chain(args.instance, env, args.mode, args.depth, args.runs))
            elif args.command == "etag-altered":
                asyncio.run(etag_altered(args.instance, env))
            else:
                asyncio.run(cleanup(args.instance, env, args.accounts.split(",")))
    except spike.RunFailed as failure:
        note(f"ABBRUCH {failure}")
        code = 1
    finally:
        spike.write_protocol(out, header_line)
    return code


if __name__ == "__main__":
    sys.exit(main())

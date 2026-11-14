"""Plan 33-11: the first ``tasks_search`` after a cold restart, measured list by list.

In run 1 of plan 33-10 on Nextcloud 32 the read only shared list was missing from the first
search right after a restart of the container. This program asks whether the budget of one
list (``PER_LIST_TIMEOUT``), the discovery or a server error dropped it.

Per instance: bob creates the list ``p3311-ro`` with one task and shares it read only with
alice. A warm positive control must find the task; a planted hold of the REPORT of that list
in the client must make the independent check report it missing. Then every cold cycle
restarts the Nextcloud container and runs one first call right after it answers again:

* ``wahr``: the product search with a measuring budget of 60 s, so every list answers and
  its real duration is seen;
* ``produkt``: the product search with the budget unchanged, so the behaviour is seen;
* ``parallel7``: the product discovery, then seven REPORTs of the list at once, the load of
  the seven lists of the live run.

Every request goes through a timing transport that reads the whole body. Lists are named by
role only (``home``, ``ro``, ``eigen``); the URI of a shared list carries the account id of
its owner and is never printed. The teardown takes the share back, deletes the list without
trash bin and compares the baseline read from the database.

Subcommands::

    uv run --no-sync python scripts/tasks_coldstart.py up --instance nc35 --out <file>
    uv run --no-sync python scripts/tasks_coldstart.py run --instance nc35 \
        --env-file .env.nc35 --cycles 9 --out <file>
    uv run --no-sync python scripts/tasks_coldstart.py stop --instance nc35 --out <file>
"""

import argparse
import asyncio
import importlib.util
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit

import httpx
from lxml import etree

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud import exclusion as exclusion_core
from mcp_connector.nextcloud.clients import tasks as tasks_client
from mcp_connector.nextcloud.clients import xml
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.nextcloud.http import NoCookieJar
from mcp_connector.tools import tasks as tasks_tools

REPO_ROOT = Path(__file__).resolve().parents[1]
MEASURE_FILE = REPO_ROOT / "scripts" / "tasks_measure.py"


def _load_measure() -> ModuleType:
    """The measuring program of phase 32, loaded from its file instead of being repeated."""
    spec = importlib.util.spec_from_file_location("tasks_measure", MEASURE_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{MEASURE_FILE} could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tm = _load_measure()
spike = tm.spike

PREFIX = "p3311"
LIST_RO = f"{PREFIX}-ro"
TASK_TITLE = f"{PREFIX}-fremdro"
#: The teardown helpers of tasks_measure go by this tuple.
vars(tm)["PREFIXES"] = (*tm.PREFIXES, PREFIX)
#: Budget of one list while the true duration is measured; nothing real takes that long.
MEASURING_BUDGET = 60.0
#: How long the planted hold keeps back the REPORT of the list in the negative control.
HOLD_SECONDS = 3.0
PARALLEL = 7
KINDS = ("wahr", "produkt", "parallel7")


# --- pure helpers (tests/unit/test_tasks_coldstart.py) -------------------------------------------


def role_of(path: str, user: str) -> str:
    """``home`` for the calendar home of ``user``, the role of a list of this plan, or ``eigen``.

    A shared list keeps its URI, ``<uri>_shared_by_<owner>``; the part after the marker is
    cut, so the role (``ro``, ``gro``, ...) never carries the owner. A list of this plan is
    named by its URI without the prefix; any other list of the account is ``eigen``.
    Anything outside the calendars of ``user`` is ``andere``.
    """
    marker = f"/remote.php/dav/calendars/{user}/"
    if marker not in path:
        return "andere"
    below = path.split(marker, 1)[1].strip("/")
    if not below:
        return "home"
    uri = below.split("/", 1)[0].split("_shared_by_", 1)[0]
    return uri.removeprefix(f"{PREFIX}-") if uri.startswith(f"{PREFIX}-") else "eigen"


def discovery_lines(body: bytes, user: str) -> list[str]:
    """The discovery, one line per collection: role, status, read-only, components.

    Built from the raw Multi-Status the product received; the href is reduced to its role,
    so neither the owner of a share nor a URI reaches the protocol.
    """
    try:
        root = etree.fromstring(body)
    except etree.XMLSyntaxError:
        return [f"unlesbar bytes={len(body)}"]
    lines: list[str] = []
    for response in root.findall(f"{{{xml.DAV}}}response"):
        href = (response.findtext(f"{{{xml.DAV}}}href") or "").strip()
        role = role_of(urlsplit(href).path, user)
        if role == "home":
            continue
        statuses: list[str] = []
        read_only = "fehlt"
        comps: list[str] = []
        for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
            status = (propstat.findtext(f"{{{xml.DAV}}}status") or "").split(" ")
            statuses.append(status[1] if len(status) > 1 else "?")
            prop = propstat.find(f"{{{xml.DAV}}}prop")
            if prop is None or not statuses[-1].startswith("2"):
                continue
            flag = prop.find(f"{{{xml.OC}}}read-only")
            if flag is not None:
                read_only = (flag.text or "").strip() or "leer"
            comps.extend(
                str(comp.get("name"))
                for comp in prop.iter(f"{{{xml.CAL}}}comp")
                if comp.get("name")
            )
        lines.append(
            f"{role}:status={'/'.join(statuses) or 'keine'},read_only={read_only},"
            f"comp={'+'.join(comps) or 'keine'}"
        )
    return sorted(lines)


def kind_of(cycle: int) -> str:
    return KINDS[cycle % len(KINDS)]


@dataclass(frozen=True, slots=True)
class Timing:
    method: str
    role: str
    status: str
    seconds: float


def timings_line(timings: Sequence[Timing]) -> str:
    """Per role: count, statuses and the largest duration in ms, ordered by role."""
    parts: list[str] = []
    for role in sorted({entry.role for entry in timings}):
        mine = [entry for entry in timings if entry.role == role]
        statuses = "/".join(sorted({entry.status for entry in mine}))
        worst = max(entry.seconds for entry in mine) * 1000
        parts.append(f"{role}:n={len(mine)},status={statuses},max_ms={worst:.0f}")
    return " ".join(parts) or "keine"


def server_errors(timings: Sequence[Timing]) -> int:
    return sum(1 for entry in timings if entry.status.isdigit() and int(entry.status) >= 500)


# --- the timing transport ------------------------------------------------------------------------


class TimingTransport(httpx.AsyncBaseTransport):
    """Times every request including its body; optionally holds back the REPORT of ``ro``."""

    def __init__(self, user: str, hold_ro: float = 0.0) -> None:
        self._inner = httpx.AsyncHTTPTransport()
        self._user = user
        self._hold_ro = hold_ro
        self.timings: list[Timing] = []
        self.discovery = b""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        role = role_of(request.url.path, self._user)
        started = time.perf_counter()
        try:
            response = await self._inner.handle_async_request(request)
            body = await response.aread()
            if role == "home" and request.method == "PROPFIND":
                self.discovery = body
            if self._hold_ro and role == "ro" and request.method == "REPORT":
                await asyncio.sleep(self._hold_ro)
        except asyncio.CancelledError:
            self.timings.append(
                Timing(request.method, role, "abgebrochen", time.perf_counter() - started)
            )
            raise
        self.timings.append(
            Timing(request.method, role, str(response.status_code), time.perf_counter() - started)
        )
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()


def alice_creds(target: Any, env: Mapping[str, str]) -> Credentials:
    """Impersonation of alice with the version header of the environment file."""
    creds: Credentials = tm.appapi_creds(env, target.base_url, target.alice)
    return creds


def timing_clients(creds: Credentials, transport: TimingTransport) -> NcClients:
    exclusion_core.clear_cache()
    capabilities.clear_cache()
    client = httpx.AsyncClient(
        transport=transport, follow_redirects=False, timeout=60.0, cookies=NoCookieJar()
    )
    return NcClients(client=client, creds=creds)


@dataclass(slots=True)
class Outcome:
    seconds: float
    timings: list[Timing]
    ro_listed: bool
    ro_hit: bool
    degraded: str
    refused: str
    hit_lists: str = ""
    discovery: bytes = b""


async def product_call(
    target: Any, env: Mapping[str, str], *, budget: float, hold_ro: float = 0.0
) -> Outcome:
    """One ``search_tasks`` of alice for the prefix, every status, under ``budget``."""
    transport = TimingTransport(target.alice, hold_ro)
    clients = timing_clients(alice_creds(target, env), transport)
    before = tasks_tools.PER_LIST_TIMEOUT
    tasks_tools.PER_LIST_TIMEOUT = budget
    refused = ""
    answer: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        async with clients.client:
            answer = await tasks_tools.search_tasks(clients, query=PREFIX, status="all")
    except ToolError as exc:
        refused = f"{exc.message} | {exc.hint}"
    finally:
        tasks_tools.PER_LIST_TIMEOUT = before
    seconds = time.perf_counter() - started
    hits = [hit for hit in answer.get("tasks") or [] if isinstance(hit, dict)]
    degraded = answer.get("degraded") or []
    return Outcome(
        seconds=seconds,
        timings=transport.timings,
        # Independent of the answer: did a request to the list leave at all?
        ro_listed=any(entry.role == "ro" for entry in transport.timings),
        ro_hit=any(hit.get("summary") == TASK_TITLE for hit in hits),
        degraded=";".join(
            f"{item.get('list')}={item.get('reason')}"
            for item in degraded
            if isinstance(item, dict)
        )
        or "keine",
        refused=refused,
        hit_lists=",".join(
            sorted(
                {
                    str(hit["list"].get("name", "")).removeprefix(f"{PREFIX}-")
                    for hit in hits
                    if isinstance(hit.get("list"), dict)
                }
            )
        )
        or "keine",
        discovery=transport.discovery,
    )


def outcome_line(label: str, outcome: Outcome) -> str:
    return (
        f"{label} gesamt_ms={outcome.seconds * 1000:.0f} "
        f"ro_gelistet={spike.yes_no(outcome.ro_listed)} "
        f"ro_treffer={spike.yes_no(outcome.ro_hit)} status_5xx={server_errors(outcome.timings)} "
        f"degraded={outcome.degraded} verweigert={outcome.refused or 'nein'} "
        f"trefferlisten={outcome.hit_lists or 'keine'} | {timings_line(outcome.timings)}"
    )


async def parallel_call(target: Any, env: Mapping[str, str]) -> str:
    """The product discovery, then seven REPORTs of the list at once, without any budget."""
    transport = TimingTransport(target.alice)
    clients = timing_clients(alice_creds(target, env), transport)
    started = time.perf_counter()
    async with clients.client:
        lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
        mine = [entry for entry in lists if entry.uri.startswith(LIST_RO)]
        if mine:
            body = tasks_client.build_todo_query(None)
            await asyncio.gather(
                *(
                    tasks_client.query_todos(clients.client, clients.creds, mine[0], body)
                    for _ in range(PARALLEL)
                ),
                return_exceptions=True,
            )
    seconds = time.perf_counter() - started
    return (
        f"gesamt_ms={seconds * 1000:.0f} ro_gelistet={spike.yes_no(bool(mine))} "
        f"listen={len(lists)} status_5xx={server_errors(transport.timings)} "
        f"| {timings_line(transport.timings)}"
    )


# --- setup, teardown -----------------------------------------------------------------------------


async def setup(target: Any, env: Mapping[str, str]) -> None:
    bob = tm.appapi_creds(env, target.base_url, target.bob)
    async with spike.new_client() as client:
        await tm.make_list(client, bob, LIST_RO)
        status = await tm.put_task(
            client, bob, LIST_RO, f"{PREFIX}-1.ics", spike.simple_todo(f"{PREFIX}-1", TASK_TITLE)
        )
        spike.note(f"SETUP PUT aufgabe liste=ro status={status}")
        shared = await spike.dav_request(
            client,
            bob,
            "POST",
            tm.list_url(target.base_url, target.bob, LIST_RO),
            body=spike.share_body(target.alice, writable=False),
        )
        spike.note(f"SETUP FREIGABE ro an=alice nur_lesen=ja status={shared.status}")
        if status != 201 or shared.status not in (200, 204):
            raise spike.RunFailed("the setup of the shared list failed")


async def teardown(target: Any, env: Mapping[str, str]) -> None:
    spike.section(f"rueckbau {target.name}")
    bob = tm.appapi_creds(env, target.base_url, target.bob)
    async with spike.new_client() as client:
        result = await spike.dav_request(
            client,
            bob,
            "POST",
            tm.list_url(target.base_url, target.bob, LIST_RO),
            body=tm._unshare_body(target.alice),
        )
        spike.note(f"RUECKBAU freigabe_entfernt liste=ro status={result.status}")
        for user in (target.alice, target.bob):
            creds = tm.appapi_creds(env, target.base_url, user)
            for entry in await tm.prefixed_lists(client, creds):
                if "_shared_by_" in entry.uri:
                    continue
                gone = await spike.dav_request(
                    client,
                    creds,
                    "DELETE",
                    tm.list_url(target.base_url, user, entry.uri),
                    extra_headers=tm.NO_TRASHBIN,
                )
                spike.note(
                    f"RUECKBAU liste_geloescht konto={user} status={gone.status} no_trashbin=1"
                )
            removed, cleared = await tm.purge_trash(client, creds)
            spike.note(
                f"PAPIERKORB {target.name} konto={user} gefunden={removed} geleert={cleared}"
            )
            left = await tm.prefixed_lists(client, creds)
            spike.note(f"RUECKBAU reste konto={user} listen_mit_praefix={len(left)}")


# --- the run -------------------------------------------------------------------------------------


def preconditions(target: Any, env: Mapping[str, str]) -> None:
    """The registration stays as it is: the version header is the registered version."""
    sent = env.get("APP_VERSION", "")
    listed = spike.occ(target.container, "app_api:app:list", check=False)
    registered = [line.strip() for line in listed.splitlines() if "mcp_connector" in line]
    spike.note(
        f"EXAPP {target.name} info_xml={tm.info_xml_version()} kopf={sent} "
        f"registriert={' | '.join(registered) or 'keine'}"
    )
    if not sent or not any(f": {sent} [enabled]" in line for line in registered):
        raise spike.RunFailed("the version header is not the registered version; nothing changed")
    out = spike.occ(target.container, "status", check=False)
    version = next(
        (line.split(":", 1)[1].strip() for line in out.splitlines() if "  - version:" in line), "?"
    )
    spike.note(f"VERSION {target.name} nc={version}")
    spike.note(
        f"TASKSAPP {target.name} zustand={tm.tasks_app_state(target.container)} (unveraendert)"
    )


async def run(target: Any, env: Mapping[str, str], cycles: int) -> None:
    spike.section(f"kaltstart {target.name} zyklen={cycles}, start {spike.now_stamp()}")
    preconditions(target, env)
    await tm.control(target, env)
    async with spike.new_client() as client:
        for user in (target.alice, target.bob):
            if await tm.prefixed_lists(client, tm.appapi_creds(env, target.base_url, user)):
                raise spike.RunFailed("lists of this plan are left; teardown first")
    before = tm.baseline(target, "vorher")
    budget = tasks_tools.PER_LIST_TIMEOUT
    try:
        await setup(target, env)
        warm = await product_call(target, env, budget=budget)
        spike.note(outcome_line(f"KONTROLLE warm budget_s={budget:g}", warm))
        held = await product_call(target, env, budget=budget, hold_ro=HOLD_SECONDS)
        spike.note(
            outcome_line(f"GEGENPROBE ro_gehalten_s={HOLD_SECONDS:g} budget_s={budget:g}", held)
        )
        spike.note(
            f"GEGENPROBE erkannt={spike.yes_no(warm.ro_hit and not held.ro_hit)} "
            f"degraded_nennt_ro={spike.yes_no(LIST_RO in held.degraded)}"
        )
        for cycle in range(cycles):
            kind = kind_of(cycle)
            tm.restart(target)
            label = f"KALT {target.name} zyklus={cycle + 1} art={kind}"
            if kind == "parallel7":
                spike.note(f"{label} {await parallel_call(target, env)}")
                continue
            used = MEASURING_BUDGET if kind == "wahr" else budget
            first = await product_call(target, env, budget=used)
            spike.note(outcome_line(f"{label} budget_s={used:g}", first))
            second = await product_call(target, env, budget=budget)
            spike.note(
                outcome_line(f"WARM {target.name} zyklus={cycle + 1} budget_s={budget:g}", second)
            )
    except Exception as failure:
        spike.note(f"BLOCK FAILED | {target.name} | {type(failure).__name__}: {str(failure)[:300]}")
        raise
    finally:
        await teardown(target, env)
        after = tm.baseline(target, "nachher")
        for user, value in before.items():
            spike.note(
                f"BASELINE-VERGLEICH {target.name} konto={user} "
                f"gleich={spike.yes_no(after.get(user) == value)}"
            )


# --- the reproduction of run 1 of plan 33-10 (owner approval of 2026-11-14) ----------------------

GROUP = f"{PREFIX}grp"
TASKS_VERSION = "0.18.1"
#: role -> (owner, share): "" none, "user-rw", "user-ro", "group-rw", "group-ro"
REPRO_LISTS = {
    "a": ("alice", ""),
    "b": ("alice", ""),
    "rw": ("bob", "user-rw"),
    "ro": ("bob", "user-ro"),
    "grw": ("bob", "group-rw"),
    "gro": ("bob", "group-ro"),
}


def free_gb() -> str:
    return f"{spike.free_host_memory_gb(spike.host_memory_probe()):.2f}"


def install_tasks(target: Any) -> str:
    out = spike.occ(target.container, "app:install", tm.TASKS_APP, check=False)
    spike.note(f"occ app:install {tm.TASKS_APP} -> {spike._one_line(out)[:160]}")
    version: str = tm.tasks_app_state(target.container)
    spike.note(f"TASKSAPP {target.name} nach_installation={version}")
    if version != TASKS_VERSION:
        raise spike.RunFailed(f"the Tasks app is {version}, not {TASKS_VERSION}; stopped")
    return version


async def setup_seven(target: Any, env: Mapping[str, str]) -> None:
    """Group, six lists of this plan with one task each, and the shares; with personal: 7."""
    for argv in (
        ("group:add", GROUP),
        ("group:adduser", GROUP, target.bob),
        ("group:adduser", GROUP, target.alice),
    ):
        spike.occ(target.container, *argv, check=False)
    members = tm.group_members(target, GROUP) or []
    spike.note(f"SETUP gruppe mitglieder={len(members)}")
    if sorted(members) != sorted((target.alice, target.bob)):
        raise spike.RunFailed("the test group does not hold both test accounts")
    async with spike.new_client() as client:
        for role, (owner, share) in REPRO_LISTS.items():
            user = target.alice if owner == "alice" else target.bob
            creds = tm.appapi_creds(env, target.base_url, user)
            uri = f"{PREFIX}-{role}"
            await tm.make_list(client, creds, uri)
            title = TASK_TITLE if role == "ro" else f"{PREFIX}-{role}-aufgabe"
            status = await tm.put_task(
                client, creds, uri, f"{PREFIX}-{role}.ics", spike.simple_todo(f"{uri}-1", title)
            )
            spike.note(f"SETUP PUT liste={role} status={status}")
            if status != 201:
                raise spike.RunFailed(f"the task of list {role} was not created")
            if not share:
                continue
            kind, mode = share.split("-")
            body = (
                spike.share_body(target.alice, writable=mode == "rw")
                if kind == "user"
                else tm.group_share_body(GROUP, writable=mode == "rw")
            )
            shared = await spike.dav_request(
                client, creds, "POST", tm.list_url(target.base_url, user, uri), body=body
            )
            spike.note(f"SETUP FREIGABE liste={role} art={share} status={shared.status}")
            if shared.status not in (200, 204):
                raise spike.RunFailed(f"the share of list {role} failed")


async def repro_teardown(target: Any, env: Mapping[str, str]) -> None:
    spike.section(f"rueckbau nachstellen {target.name}")
    bob = tm.appapi_creds(env, target.base_url, target.bob)
    async with spike.new_client() as client:
        for role, (_, share) in REPRO_LISTS.items():
            if not share:
                continue
            body = (
                tm._unshare_body(target.alice)
                if share.startswith("user")
                else tm.group_share_body(GROUP, writable=False, remove=True)
            )
            result = await spike.dav_request(
                client,
                bob,
                "POST",
                tm.list_url(target.base_url, target.bob, f"{PREFIX}-{role}"),
                body=body,
            )
            spike.note(f"RUECKBAU freigabe_entfernt liste={role} status={result.status}")
    await teardown(target, env)
    if tm.group_members(target, GROUP) is not None:
        spike.occ(target.container, "group:delete", GROUP, check=False)
    left = tm.group_members(target, GROUP) is not None
    shares = spike.php(target.container, tm.PHP_GROUP_SHARES, GROUP).strip()
    spike.note(f"RUECKBAU gruppe {GROUP} noch_vorhanden={spike.yes_no(left)} shares={shares}")


async def repro_search(target: Any, env: Mapping[str, str], label: str, budget: float) -> None:
    """One first call; its outcome, then the discovery it received, one line per list."""
    outcome = await product_call(target, env, budget=budget)
    spike.note(outcome_line(f"{label} budget_s={budget:g} ram_gb={free_gb()}", outcome))
    lines = discovery_lines(outcome.discovery, target.alice)
    spike.note(f"DISCOVERY-ROH {label} sammlungen={len(lines)} bytes={len(outcome.discovery)}")
    for line in lines:
        spike.note(f"  {line}")


async def reproduce(target: Any, env: Mapping[str, str], cycles: int) -> None:
    """Run 1 of 33-10: install, restart, seven lists, search; then more install cycles."""
    spike.section(f"nachstellen {target.name} zyklen={cycles}, start {spike.now_stamp()}")
    preconditions(target, env)
    await tm.control(target, env)
    async with spike.new_client() as client:
        for user in (target.alice, target.bob):
            if await tm.prefixed_lists(client, tm.appapi_creds(env, target.base_url, user)):
                raise spike.RunFailed("lists of this plan are left; teardown first")
    if tm.group_members(target, GROUP) is not None:
        raise spike.RunFailed("the test group exists before the run; nothing was changed")
    before_app: str = tm.tasks_app_state(target.container)
    before = tm.baseline(target, "vorher")
    budget = tasks_tools.PER_LIST_TIMEOUT
    try:
        install_tasks(target)
        tm.restart(target)
        await setup_seven(target, env)
        await repro_search(target, env, f"NACH {target.name} zyklus=1 art=wie-lauf1", budget)
        await repro_search(target, env, f"WARM {target.name} zyklus=1", budget)
        for cycle in range(2, cycles + 1):
            tm.restore_tasks_app(target, before_app)
            install_tasks(target)
            tm.restart(target)
            used = budget if cycle % 2 else MEASURING_BUDGET
            label = f"NACH {target.name} zyklus={cycle}"
            await repro_search(target, env, f"{label} art=neu-installiert", used)
            tm.restart(target)
            await repro_search(target, env, f"{label} art=neustart", used)
    except Exception as failure:
        spike.note(f"BLOCK FAILED | {target.name} | {type(failure).__name__}: {str(failure)[:300]}")
        raise
    finally:
        await repro_teardown(target, env)
        tm.restore_tasks_app(target, before_app)
        after = tm.baseline(target, "nachher")
        for user, value in before.items():
            spike.note(
                f"BASELINE-VERGLEICH {target.name} konto={user} "
                f"gleich={spike.yes_no(after.get(user) == value)}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("up", "stop", "run", "nachstellen"):
        command = sub.add_parser(name)
        command.add_argument("--instance", choices=sorted(tm.TARGETS), required=True)
        command.add_argument("--out", type=Path, required=True)
        if name in ("run", "nachstellen"):
            command.add_argument("--env-file", type=Path, required=True)
            command.add_argument("--cycles", type=int, default=9)
    args = parser.parse_args(argv)
    target = tm.TARGETS[args.instance]
    header = f"# tasks_coldstart.py {args.command} {spike.now_stamp()}"
    code = 0
    try:
        if args.command == "up":
            tm.up(target)
        elif args.command == "stop":
            tm.stop(target)
        elif args.command == "nachstellen":
            asyncio.run(reproduce(target, tm._env(args.env_file), args.cycles))
        else:
            asyncio.run(run(target, tm._env(args.env_file), args.cycles))
    except spike.RunFailed as failure:
        spike.note(f"ABBRUCH {failure}")
        code = 1
    finally:
        spike.write_protocol(args.out, header)
    return code


if __name__ == "__main__":
    sys.exit(main())

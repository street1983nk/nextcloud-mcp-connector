"""Live harness of phase 28; a helper module, not a test module.

The measurements of plan 28-01, the canary of plan 28-10 and the live pairs of plan 28-11 all
need the same scaffolding against a running Nextcloud: WebDAV and OCS writes as the test
account, a Tables table with a link column, ``kein-ki`` tagging through ``occ``, a tool call
through the in-memory ``Client(mcp)`` exactly as a client makes it, an injected outage of the
tag REPORT, and a cleanup that reads every removal back instead of trusting it.

Why a module and not ``conftest.py``: a fixture in ``tests/integration/conftest.py`` would
reach every integration test, including the ones of the CI job that has no ExApp topology,
and the helpers here reach into a container. This module is imported by name;
``pyproject.toml`` puts ``tests/integration`` on the import path for it.

``occ`` runs in :data:`topology.NC_CONTAINER` and nowhere else. The live module of plan 27-07
spelled its container out, which is the trap ``topology.py`` describes: a run against another
topology would tag one instance and assert against a second one.

Nothing here logs a header, a password or an environment value; :func:`record` only ever
receives tool results and raw answers of the instance (T-28-04).
"""

import contextlib
import dataclasses
import io
import json
import os
import shutil
import subprocess
import uuid
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import quote

import httpx
import pytest
import respx
import topology
from lxml import etree
from mcp import Client
from mcp.types import CallToolResult

from mcp_connector import config, ids
from mcp_connector.config import normalize_base_url
from mcp_connector.nextcloud import capabilities, exclusion
from mcp_connector.nextcloud.clients import caldav as caldav_client
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.clients import deck as deck_client
from mcp_connector.nextcloud.clients import systemtags as systemtags_client
from mcp_connector.nextcloud.clients import tables as tables_client
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.server import mcp
from mcp_connector.tools import talk as talk_tools
from mcp_connector.tools import withhold

__all__ = [
    "RAW_DIR",
    "TAG",
    "Cleanup",
    "Harness",
    "LiveEnv",
    "World",
    "call",
    "canary_world",
    "check",
    "credentials",
    "ensure_tag",
    "fresh_guard",
    "guard_outage",
    "live_env",
    "mcp_env",
    "occ",
    "record",
    "refusal_problem",
    "run_id",
    "skip_or_fail",
    "tag",
    "tag_ids",
    "untag",
]

RAW_DIR = (
    Path(__file__).resolve().parents[2] / ".planning" / "phases" / "28-gates-und-beweise" / "raw"
)
TAG = exclusion.EXCLUDE_TAG
REQUIRED_ENV = ("NC_MCP_URL", "NC_MCP_TEST_USER", "NC_MCP_TEST_APP_PASSWORD")

_DAV = "{DAV:}"
_OC = "{http://owncloud.org/ns}"
_PROPFIND = (
    b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
    b"<d:prop><oc:fileid/><d:getetag/></d:prop></d:propfind>"
)
_OCS_HEADERS = {"OCS-APIRequest": "true", "Accept": "application/json"}
_NC = "{http://nextcloud.org/ns}"
_TRASH_PROPFIND = (
    b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:nc="http://nextcloud.org/ns">'
    b"<d:prop><nc:trashbin-filename/></d:prop></d:propfind>"
)
NOTES_API = "/index.php/apps/notes/api/v1"
SHARES_API = "/apps/files_sharing/api/v1/shares"
TALK_ROOMS = "/apps/spreed/api/v4/room"
TALK_CHAT = "/apps/spreed/api/v1/chat"
#: Share types of ``OCP\\Share\\IShare``: a user, a Talk room and a Deck card.
SHARE_USER, SHARE_ROOM, SHARE_DECK = 0, 10, 12
#: Nextcloud keeps a deleted calendar and object in its calendar trash bin unless told not to.
_NO_CAL_TRASH = {"X-NC-CalDAV-No-Trashbin": "1"}

#: Set by the CI step of GATE-02/03 (review WR-04 of phase 28): a missing prerequisite there
#: is a broken topology, not an absent one, so it fails instead of skipping. A renamed
#: container or a changed ``.env.exapp`` would otherwise turn both gates into green skips.
ENV_REQUIRE_LIVE = "NC_MCP_REQUIRE_LIVE"


def skip_or_fail(reason: str) -> NoReturn:
    """Skip without a live setup; fail when the run demands one (:data:`ENV_REQUIRE_LIVE`)."""
    if (os.environ.get(ENV_REQUIRE_LIVE) or "").strip() == "1":
        pytest.fail(f"{ENV_REQUIRE_LIVE}=1 but {reason}", pytrace=False)
    pytest.skip(reason)


# --- protocol -------------------------------------------------------------------------


def record(raw: Path, line: str) -> None:
    """Append one line to a raw protocol."""
    raw.parent.mkdir(parents=True, exist_ok=True)
    with raw.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")


def short(value: str, limit: int = 240) -> str:
    """``value`` cut to ``limit`` characters, marked when it was cut."""
    return value if len(value) <= limit else value[: limit - 3] + "..."


def check(raw: Path, criterion: str, tool: str, case: str, ok: bool, raw_value: str) -> None:
    """Record ``<criterion> <tool> <case>: <ja|nein> (<raw>)`` first, then assert ``ok``."""
    cut = short(raw_value)
    record(raw, f"{criterion} {tool} {case}: {'ja' if ok else 'nein'} ({cut})")
    assert ok, f"{criterion} {tool} {case}: {cut}"


# --- environment ----------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class LiveEnv:
    """The account a live run acts as, read from the environment once."""

    url: str
    user: str
    app_password: str
    user2: str | None = None


def live_env() -> LiveEnv:
    """The live account, or a skip naming what is missing.

    The CI job ``integration`` has no ExApp variables and no container of this name, so every
    test built on this skips there instead of failing. The step of the ``canary-nc35`` job
    that runs the gates sets :data:`ENV_REQUIRE_LIVE`, and there the same gaps fail (review
    WR-04).
    """
    values = {name: (os.environ.get(name) or "").strip() for name in REQUIRED_ENV}
    missing = [name for name, value in values.items() if not value]
    if missing:
        skip_or_fail(f"no live run configured (missing: {', '.join(missing)})")
    assert values["NC_MCP_TEST_USER"] != "admin", "the live run acts as a normal user"
    if shutil.which("docker") is None:
        skip_or_fail("docker is not on PATH, occ cannot tag")
    probe = subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "inspect", "-f", "{{.State.Running}}", topology.NC_CONTAINER],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or "true" not in probe.stdout:
        skip_or_fail(f"the container {topology.NC_CONTAINER} is not running")
    return LiveEnv(
        url=normalize_base_url(values["NC_MCP_URL"]),
        user=values["NC_MCP_TEST_USER"],
        app_password=values["NC_MCP_TEST_APP_PASSWORD"],
        user2=(os.environ.get("NC_MCP_TEST_USER2") or "").strip() or None,
    )


def credentials(env: LiveEnv) -> Credentials:
    return Credentials(base_url=env.url, user=env.user, secret=env.app_password)


def mcp_env(monkeypatch: pytest.MonkeyPatch, env: LiveEnv) -> None:
    """The environment an in-memory client call resolves its credentials from.

    The two switches that change a code path are neutralised (review WR-05 of phase 28): with
    ``NC_MCP_TALK_SEND`` off, ``talk_send`` refuses before the guard is asked, and with a
    ``NC_MCP_FILES_ROOT`` the sandbox answers first; either would let a gate prove a path
    other than the one it names. A test that wants a switch sets it after this call.
    """
    monkeypatch.setenv("NC_MCP_URL", env.url)
    monkeypatch.setenv("NC_MCP_USER", env.user)
    monkeypatch.setenv("NC_MCP_APP_PASSWORD", env.app_password)
    monkeypatch.delenv("NC_MCP_STATIC_BEARER", raising=False)
    monkeypatch.delenv(config.ENV_FILES_ROOT, raising=False)
    monkeypatch.delenv(config.ENV_TALK_SEND, raising=False)


#: The refusal each write of the canary has to answer with, by mode (review WR-05 of phase
#: 28). In the normal state it is the "does not exist" sentence of D-27-01, and any other
#: error (a 5xx, a missing app, a switched off channel) is a failure of the gate. In an
#: outage it is the one sentence of the unanswered check, or the normal refusal when the
#: forced outage let the guard answer after all (a stale listing that recovers).
PARENT_MISSING_FRAGMENTS = ("The parent folder ", " does not exist.")


def refusal_problem(tool: str, args: dict[str, Any], mode: str, text: str) -> str | None:
    """Why ``text`` is not the refusal ``tool`` owes in ``mode``, or ``None`` when it is."""
    if tool == "talk_send":
        normal: tuple[str, ...] = (talk_tools._unknown_token(str(args.get("token") or "")).message,)
    elif tool in ("files_upload", "notes_create", "files_create_folder"):
        normal = PARENT_MISSING_FRAGMENTS
    else:
        return f"no refusal is defined for {tool}"
    choices = [normal] if mode == "normal" else [normal, (withhold.EXCLUSION_UNAVAILABLE,)]
    if any(all(fragment in text for fragment in wanted) for wanted in choices):
        return None
    return f"expected one of {choices!r}"


# --- occ and tagging ------------------------------------------------------------------


def occ(*argv: str, check_status: bool = True) -> str:
    """One ``occ`` call inside :data:`topology.NC_CONTAINER` (harness only, EXCL-07)."""
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "exec", "-u", "www-data", topology.NC_CONTAINER, "php", "occ", *argv],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = ((finished.stdout or "") + (finished.stderr or "")).replace("\r", "").strip()
    if check_status and finished.returncode != 0:
        raise AssertionError(f"occ {' '.join(argv)} failed: {output[:300]}")
    return output


def tag_ids() -> list[str]:
    """The ids of every tag ``occ tag:list`` knows under a spelling of ``kein-ki``."""
    raw = occ("tag:list", "--output=json", check_status=False)
    start = min((i for i in (raw.find("{"), raw.find("[")) if i >= 0), default=-1)
    try:
        data = json.loads(raw[start:]) if start >= 0 else []
    except json.JSONDecodeError:
        return []
    items: list[tuple[str, str]] = []
    if isinstance(data, dict):
        items = [(str(k), str(v.get("name", ""))) for k, v in data.items() if isinstance(v, dict)]
    elif isinstance(data, list):
        items = [
            (str(v.get("id", "")), str(v.get("name", ""))) for v in data if isinstance(v, dict)
        ]
    return [tag_id for tag_id, tag_name in items if exclusion.is_exclude_name(tag_name)]


def ensure_tag() -> tuple[str, bool]:
    """``(id, created)`` of the ``kein-ki`` tag; created by this run when it was missing."""
    existing = tag_ids()
    if existing:
        return existing[0], False
    output = occ("tag:add", TAG, "public", "--output=json")
    start = output.find("{")
    created = json.loads(output[start:]) if start >= 0 else {}
    tag_id = str(created.get("id") or "")
    assert tag_id.isdigit(), f"occ tag:add gave no id: {output[:200]}"
    return tag_id, True


def tag(fileid: str) -> None:
    """Tag one node by its file id; the id form is the one the 27-07 run measured."""
    occ("tag:files:add", fileid, TAG, "public")


def untag(fileid: str) -> None:
    occ("tag:files:delete", fileid, TAG, "public", check_status=False)


# --- harness --------------------------------------------------------------------------


class Harness:
    """Synchronous writes of the test data as the test account, never through the tools."""

    def __init__(self, env: LiveEnv) -> None:
        self.base_url = env.url
        self.user = env.user
        self.http = httpx.Client(
            auth=(env.user, env.app_password), timeout=60.0, follow_redirects=False
        )

    def close(self) -> None:
        self.http.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One request with the app password alone, never with a session cookie.

        Measured on nc35 in plan 27-07: a session cookie set by an app API turned every later
        WebDAV request of the same client into a 401, so a cleanup deleted nothing.
        """
        self.http.cookies.clear()
        return self.http.request(method, url, **kwargs)

    def dav_url(self, path: str) -> str:
        return f"{self.base_url}/remote.php/dav/files/{quote(self.user)}{quote(path)}"

    def mkcol(self, path: str) -> None:
        response = self.request("MKCOL", self.dav_url(path))
        assert response.status_code == 201, f"MKCOL {path}: {response.status_code}"

    def put(self, path: str, data: bytes) -> None:
        response = self.request("PUT", self.dav_url(path), content=data)
        assert response.status_code in (201, 204), f"PUT {path}: {response.status_code}"

    def delete(self, path: str) -> int:
        return self.request("DELETE", self.dav_url(path)).status_code

    def stat_url(self, url: str) -> tuple[int, str]:
        """(status, fileid) of one WebDAV URL; the status alone when it is not a 207."""
        response = self.request(
            "PROPFIND",
            url,
            headers={"Depth": "0", "Content-Type": "application/xml"},
            content=_PROPFIND,
        )
        if response.status_code != 207:
            return response.status_code, ""
        tree = etree.fromstring(response.content)
        return 207, (tree.findtext(f".//{_OC}fileid") or "").strip()

    def stat(self, path: str) -> tuple[int, str]:
        """(status, fileid) of one entry below the home; status 404 for a missing one."""
        return self.stat_url(self.dav_url(path))

    def fileid(self, path: str) -> str:
        status, fileid = self.stat(path)
        assert status == 207, f"no entry at {path}: {status}"
        assert fileid, f"no fileid for {path}"
        return fileid

    def search_raw(self, scope: str, term: str, limit: int = 10) -> httpx.Response:
        """The SEARCH ``dav.search`` sends, with the body it builds, answered raw."""
        return self.request(
            "SEARCH",
            f"{self.base_url}{dav.DAV_ROOT_PATH}",
            headers={"Content-Type": "text/xml"},
            content=dav.build_search_body(scope, term, limit),
        )

    def _ocs(self, method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return self.request(
            method, f"{self.base_url}/ocs/v2.php{path}", headers=_OCS_HEADERS, json=body
        )

    def ocs_get(self, path: str) -> httpx.Response:
        return self._ocs("GET", path)

    def ocs_post(self, path: str, body: dict[str, Any]) -> httpx.Response:
        return self._ocs("POST", path, body)

    def ocs_delete(self, path: str) -> httpx.Response:
        return self._ocs("DELETE", path)

    @staticmethod
    def ocs_data(response: httpx.Response, what: str) -> Any:
        assert response.status_code < 300, f"{what}: {response.status_code} {response.text[:300]}"
        return response.json()["ocs"]["data"]

    # Tables: scaffolding only, the connector itself never creates a table or a column.

    def create_table(self, title: str) -> str:
        response = self.ocs_post(
            f"{tables_client.V2_PREFIX}/tables", {"title": title, "template": "custom"}
        )
        return str(self.ocs_data(response, f"create table {title}")["id"])

    def create_link_column(self, table_id: str, title: str) -> str:
        """A text column of subtype ``link`` with the ``files`` provider allowed.

        ``textAllowedPattern`` is where the Tables column form stores the allowed link
        providers, comma separated; ``subtype`` is load bearing (``TextLinkBusiness``).
        """
        response = self.ocs_post(
            f"{tables_client.V2_PREFIX}/columns/text",
            {
                "baseNodeId": int(table_id),
                "baseNodeType": "table",
                "title": title,
                "subtype": "link",
                "textAllowedPattern": "url,files",
            },
        )
        return str(self.ocs_data(response, f"create link column {title}")["id"])

    def create_row(self, table_id: str, data: dict[str, Any]) -> dict[str, Any]:
        response = self.ocs_post(
            f"{tables_client.V2_PREFIX}/{tables_client.NODE_COLLECTION_TABLES}/{table_id}/rows",
            {"data": data},
        )
        return self.ocs_data(response, f"create row in table {table_id}")

    def rows_simple_raw(self, table_id: str) -> tuple[int, str]:
        response = self.request(
            "GET",
            f"{self.base_url}{tables_client.V1_PREFIX}/tables/{table_id}/rows/simple",
            params={"limit": 50, "offset": 0},
            headers=dict(tables_client.TABLES_HEADERS),
        )
        return response.status_code, response.text

    def table_status(self, table_id: str) -> int:
        response = self.request(
            "GET",
            f"{self.base_url}{tables_client.V1_PREFIX}/tables/{table_id}",
            headers=dict(tables_client.TABLES_HEADERS),
        )
        return response.status_code

    def delete_table(self, table_id: str) -> int:
        response = self.request(
            "DELETE",
            f"{self.base_url}{tables_client.V1_PREFIX}/tables/{table_id}",
            headers=dict(tables_client.TABLES_HEADERS),
        )
        return response.status_code

    def row_request(self, method: str, row_id: str) -> int:
        response = self.request(
            method,
            f"{self.base_url}{tables_client.V1_PREFIX}/rows/{row_id}",
            headers=dict(tables_client.TABLES_HEADERS),
        )
        return response.status_code

    # Files: plain reads and the tag REPORT the guard itself sends.

    def get_text(self, path: str) -> tuple[int, str]:
        response = self.request("GET", self.dav_url(path))
        return response.status_code, response.text

    def tagged_fileids(self, tag_id: str) -> tuple[int, set[str]]:
        """``(status, fileids)`` of the ``REPORT oc:filter-files`` over the whole home."""
        response = self.request(
            "REPORT",
            f"{self.base_url}{dav.DAV_FILES_PREFIX}{quote(self.user, safe='')}/",
            headers={"Content-Type": "application/xml"},
            content=systemtags_client.filter_files_body(tag_id),
        )
        if response.status_code != 207:
            return response.status_code, set()
        tree = etree.fromstring(response.content)
        found = {(node.text or "").strip() for node in tree.iter(f"{_OC}fileid")}
        return 207, {fileid for fileid in found if fileid}

    def trash_entries(self, needle: str) -> list[str]:
        """The hrefs of every trash bin entry whose original name contains ``needle``."""
        response = self.request(
            "PROPFIND",
            f"{self.base_url}/remote.php/dav/trashbin/{quote(self.user)}/trash/",
            headers={"Depth": "1", "Content-Type": "application/xml"},
            content=_TRASH_PROPFIND,
        )
        if response.status_code != 207:
            return []
        tree = etree.fromstring(response.content)
        hrefs: list[str] = []
        for entry in tree.iter(f"{_DAV}response"):
            name = entry.findtext(f".//{_NC}trashbin-filename") or ""
            href = entry.findtext(f"{_DAV}href") or ""
            if needle in name and href:
                hrefs.append(href)
        return hrefs

    def purge_trash(self, needle: str) -> None:
        origin = httpx.URL(self.base_url)
        for href in self.trash_entries(needle):
            self.request("DELETE", str(origin.copy_with(path=href, query=None)))

    # Notes.

    def notes(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        response = self.request(
            method, f"{self.base_url}{NOTES_API}{path}", headers=_OCS_HEADERS, json=body
        )
        assert response.status_code < 300, f"notes {method} {path}: {response.status_code}"
        return response.json() if response.content else None

    def note_status(self, note_id: str) -> int:
        return self.request(
            "GET", f"{self.base_url}{NOTES_API}/notes/{note_id}", headers=_OCS_HEADERS
        ).status_code

    def delete_note(self, note_id: str) -> int:
        return self.request(
            "DELETE", f"{self.base_url}{NOTES_API}/notes/{note_id}", headers=_OCS_HEADERS
        ).status_code

    def note_ids(self) -> set[str]:
        listing = self.notes("GET", "/notes?exclude=content") or []
        return {str(n["id"]) for n in listing if isinstance(n, dict) and "id" in n}

    # Shares.

    def share(self, path: str, share_type: int, share_with: str) -> tuple[int, str, str]:
        """``(status, share id, raw)``; the caller decides whether a refusal is fatal."""
        response = self.ocs_post(
            SHARES_API, {"path": path, "shareType": share_type, "shareWith": share_with}
        )
        share_id = ""
        with contextlib.suppress(ValueError, KeyError, TypeError):
            share_id = str(response.json()["ocs"]["data"]["id"])
        return response.status_code, share_id, short(response.text, 300)

    def share_status(self, share_id: str) -> int:
        return self.ocs_get(f"{SHARES_API}/{share_id}").status_code

    # Talk.

    def room_tokens(self) -> set[str]:
        data = self.ocs_data(self.ocs_get(TALK_ROOMS), "list rooms")
        return {str(r.get("token")) for r in data or [] if isinstance(r, dict)}

    # Calendar.

    def calendar_url(self, calendar_uri: str) -> str:
        return (
            f"{self.base_url}{caldav_client.DAV_CALENDARS_PREFIX}{quote(self.user, safe='')}/"
            f"{quote(calendar_uri, safe='')}/"
        )

    def mkcalendar(self, calendar_uri: str, name: str) -> int:
        body = (
            '<?xml version="1.0"?><c:mkcalendar xmlns:d="DAV:" '
            'xmlns:c="urn:ietf:params:xml:ns:caldav"><d:set><d:prop>'
            f"<d:displayname>{name}</d:displayname>"
            '<c:supported-calendar-component-set><c:comp name="VEVENT"/>'
            "</c:supported-calendar-component-set></d:prop></d:set></c:mkcalendar>"
        ).encode()
        return self.request(
            "MKCALENDAR",
            self.calendar_url(calendar_uri),
            headers={"Content-Type": "application/xml"},
            content=body,
        ).status_code

    def delete_calendar_url(self, url: str) -> int:
        return self.request("DELETE", url, headers=_NO_CAL_TRASH).status_code

    def status_of(self, url: str) -> int:
        return self.request(
            "PROPFIND",
            url,
            headers={"Depth": "0", "Content-Type": "application/xml"},
            content=_PROPFIND,
        ).status_code

    # Deck: scaffolding only, the connector never creates a board or a stack.

    def deck(self, method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return self.request(
            method,
            f"{self.base_url}{deck_client.DECK_API_PREFIX}{path}",
            headers=dict(deck_client.DECK_HEADERS),
            json=body,
        )

    def deck_created(self, path: str, body: dict[str, Any]) -> str:
        response = self.deck("POST", path, body)
        assert response.status_code < 300, f"deck POST {path}: {response.status_code}"
        return str(response.json()["id"])

    def deck_state(self, path: str) -> str:
        """``404``, ``gelöscht`` (soft deleted, ``deletedAt`` set) or what the entry still is."""
        response = self.deck("GET", path)
        if response.status_code != 200:
            return str(response.status_code)
        try:
            deleted = int(response.json().get("deletedAt") or 0)
        except (ValueError, TypeError, AttributeError):
            return f"unlesbar {short(response.text, 80)}"
        return "gelöscht" if deleted > 0 else "noch aktiv"

    def card_listed(self, board_id: str, card_id: str) -> str:
        """``entfernt`` when no stack of the board lists the card, else ``gelistet``."""
        response = self.deck("GET", f"/boards/{board_id}/stacks")
        if response.status_code != 200:
            return f"stacks {response.status_code}"
        for stack in response.json():
            cards = stack.get("cards") or [] if isinstance(stack, dict) else []
            if any(isinstance(c, dict) and str(c.get("id")) == card_id for c in cards):
                return "gelistet"
        return "entfernt"

    def board_state(self, board_id: str) -> str:
        """The board as the board list shows it: absent, soft deleted or still active."""
        response = self.deck("GET", "/boards")
        if response.status_code != 200:
            return f"liste {response.status_code}"
        for board in response.json():
            if isinstance(board, dict) and str(board.get("id")) == board_id:
                return "gelöscht" if int(board.get("deletedAt") or 0) > 0 else "noch aktiv"
        return "entfernt"


# --- cleanup --------------------------------------------------------------------------


@dataclasses.dataclass
class _Step:
    what: str
    undo: Callable[[], object]
    read: Callable[[], str]


class Cleanup:
    """Every side effect of a run with the call that removes it and the call that proves it.

    :meth:`run` removes in reverse order of registration and reads every raw value back
    afterwards, so a line says what the instance answers now and never what the harness
    intended. A failing removal does not stop the others.
    """

    def __init__(self) -> None:
        self.steps: list[_Step] = []

    def add(self, what: str, undo: Callable[[], object], read: Callable[[], str]) -> None:
        self.steps.append(_Step(what, undo, read))

    def add_path(self, harness: Harness, path: str) -> None:
        self.add(
            f"PROPFIND {path}", lambda: harness.delete(path), lambda: str(harness.stat(path)[0])
        )

    def add_upload(self, harness: Harness, label: str, url: str) -> None:
        def undo() -> object:
            status, _ = harness.stat_url(url)
            return harness.request("DELETE", url).status_code if status == 207 else status

        self.add(f"uploads/{label}", undo, lambda: str(harness.stat_url(url)[0]))

    def add_folder(self, harness: Harness, path: str) -> None:
        """A folder ``files_create_folder`` has to refuse, removed if it was created anyway.

        The connector cannot delete, so the harness does, with the account's own WebDAV
        access. The folder goes before the world's root does and would therefore be a trash
        bin entry of its own, under a name without the stem; its name carries the run stamp,
        so the bin is purged by that name and the read back covers both places.
        """
        name = path.rsplit("/", 1)[-1]

        def undo() -> object:
            status, _ = harness.stat(path)
            if status == 207:
                harness.delete(path)
                harness.purge_trash(name)
            return status

        def read() -> str:
            status = str(harness.stat(path)[0])
            return f"{status} und noch im Papierkorb" if harness.trash_entries(name) else status

        self.add(f"ordner {path}", undo, read)

    def add_table(self, harness: Harness, table_id: str) -> None:
        self.add(
            f"table {table_id}",
            lambda: harness.delete_table(table_id),
            lambda: str(harness.table_status(table_id)),
        )

    def add_tag(self, tag_id: str, created: bool, fileids: list[str]) -> None:
        """A created tag is deleted; a tag that existed keeps living, without our nodes."""
        if created:
            self.add(
                f"tag {TAG}",
                lambda: occ("tag:delete", tag_id, check_status=False),
                lambda: "entfernt" if not tag_ids() else f"noch da {tag_ids()}",
            )
            return

        def undo() -> object:
            for fileid in fileids:
                untag(fileid)
            return None

        self.add(f"tag {TAG}", undo, lambda: "vorbestehend")

    def run(self) -> list[str]:
        for step in reversed(self.steps):
            with contextlib.suppress(Exception):
                step.undo()
        lines: list[str] = []
        for step in self.steps:
            try:
                value = step.read()
            except Exception as exc:
                value = f"lesefehler {type(exc).__name__}"
            lines.append(f"CLEANUP {step.what}: {value}")
        return lines


#: The read back raw values a cleanup line may end on; anything else is a residue.
CLEANUP_OK = (": 404", ": leer", ": entfernt", ": vorbestehend", ": gelöscht")


def cleanup_ok(line: str) -> bool:
    return line.endswith(CLEANUP_OK)


# --- tool calls -----------------------------------------------------------------------


async def call(tool: str, args: dict[str, Any]) -> CallToolResult:
    """One tool call through the in-memory client, exactly as a client makes it.

    Errors are not raised into the caller: a tool error comes back as ``isError`` with its
    text, which is the form a model sees and therefore the form every comparison of phase 28
    is about.
    """
    async with Client(mcp) as client:
        return await client.call_tool(tool, args)


def dump(result: CallToolResult) -> dict[str, Any]:
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


def fresh_guard() -> None:
    """Forget cached tag ids and capabilities, so a call sees the tag state of now."""
    exclusion.clear_cache()
    capabilities.clear_cache()


@contextlib.contextmanager
def guard_outage(env: LiveEnv, mode: str) -> Iterator[respx.Route]:
    """Let the tag REPORT fail in ``mode`` and pass every other request through.

    ``mode`` is ``"500"``, ``"412"`` or ``"timeout"``. The route is yielded, so the caller can
    record ``call_count`` and prove the outage was actually hit.
    """
    home = systemtags_client.home_url(credentials(env))
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        route = router.route(method="REPORT", url=home)
        if mode == "500":
            route.mock(return_value=httpx.Response(500))
        elif mode == "412":
            route.mock(return_value=httpx.Response(412))
        elif mode == "timeout":
            route.mock(side_effect=httpx.ReadTimeout("injected by guard_outage"))
        else:
            raise ValueError(f"unknown outage mode {mode!r}")
        router.route().pass_through()
        yield route


def run_id() -> tuple[str, str]:
    """``(stem, marker)`` of one run: lower case ASCII letters and digits only (pitfall 5)."""
    return f"kanarie28x{uuid.uuid4().hex[:8]}", f"mk{uuid.uuid4().hex}"


# --- the canary world (plan 28-07) ------------------------------------------------------

#: What a write tool of the canary may leave behind, see :meth:`World.register_tool_write`.
WRITE_KINDS = ("event", "card", "row", "note", "message")


def _fold(line: str) -> str:
    """One iCalendar content line folded at 75 octets (RFC 5545 section 3.1), ASCII only."""
    parts, rest = [line[:75]], line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(parts)


def _absent(values: set[str], wanted: str) -> str:
    return "entfernt" if wanted not in values else "noch gelistet"


@dataclasses.dataclass(frozen=True)
class World:
    """Everything one canary run built, tagged and will remove again.

    No name a later tool receives as an argument carries the marker: path arguments point at
    ``Gesperrt-<h>`` below the root, the search word is the stem, and the tagged category is
    ``<stem>-kat``. The marker only lives in the name of the tagged file and note (which the
    guard must hide) and in the content of every tagged node. The control marker lives in an
    untagged file and note, so an empty index or a wrong container shows up as a missing
    control hit instead of a green canary.

    The instance is frozen; the three collections at the end are mutable on purpose:
    ``proof`` carries the raw values of the build proof, ``writes_ledger`` what a write tool
    created, and ``cleanup_lines`` the read back cleanup after the block.
    """

    h: str
    stamm: str
    marker: str
    control_marker: str
    env: LiveEnv
    harness: Harness
    notes_root: str = "/Notes"
    fileids: dict[str, str] = dataclasses.field(default_factory=dict)
    note_id: str = ""
    control_note_id: str = ""
    category_note_id: str = ""
    talk_token: str = ""
    file_room_token: str = ""
    table_id: str = ""
    column_id: str = ""
    row_ids: tuple[str, ...] = ()
    calendar_uri: str = ""
    event_uid: str = ""
    board_id: str = ""
    stack_id: str = ""
    card_id: str = ""
    deck_attachment: str = ""
    tag_id: str = ""
    proof: dict[str, str] = dataclasses.field(default_factory=dict)
    writes_ledger: list[str] = dataclasses.field(default_factory=list)
    cleanup_lines: list[str] = dataclasses.field(default_factory=list)

    @property
    def root(self) -> str:
        return f"/{self.stamm}"

    @property
    def tagged_file(self) -> str:
        return f"/{self.stamm}/{self.stamm}-{self.marker}.txt"

    @property
    def tagged_name(self) -> str:
        return self.tagged_file.rsplit("/", 1)[-1]

    @property
    def locked_dir(self) -> str:
        return f"/{self.stamm}/Gesperrt-{self.h}"

    @property
    def locked_file(self) -> str:
        return f"{self.locked_dir}/inhalt-{self.h}.txt"

    @property
    def refused_folder(self) -> str:
        """The folder ``files_create_folder`` is asked for below the locked folder."""
        return f"{self.locked_dir}/ordner-{self.h}"

    @property
    def refused_chain(self) -> str:
        """The top of the chain ``files_create_folder`` is asked for with ``parents``."""
        return f"{self.locked_dir}/a-{self.h}"

    @property
    def refused_folders(self) -> tuple[str, str]:
        """Both of them: what the cleanup removes if a call created it after all."""
        return (self.refused_folder, self.refused_chain)

    @property
    def control_file(self) -> str:
        return f"/{self.stamm}/{self.stamm}-kontrolle-{self.control_marker}.txt"

    @property
    def locked_doc(self) -> str:
        return f"{self.locked_dir}/inhalt-{self.h}.docx"

    @property
    def control_doc(self) -> str:
        return f"/{self.stamm}/{self.stamm}-kontrolle-{self.control_marker}.docx"

    @property
    def control_name(self) -> str:
        return self.control_file.rsplit("/", 1)[-1]

    @property
    def tagged_category(self) -> str:
        return f"{self.stamm}-kat"

    @property
    def category_path(self) -> str:
        return f"{self.notes_root}/{self.tagged_category}"

    @property
    def calendar_url(self) -> str:
        return self.harness.calendar_url(self.calendar_uri or self.stamm)

    def link_cell(self, name: str, fileid: str) -> str:
        """A Tables link cell in the form plan 28-01 measured (finding A1)."""
        return json.dumps(
            {"title": name, "value": f"{self.env.url}/f/{fileid}", "providerId": "files"},
            ensure_ascii=False,
        )

    def register_tool_write(self, kind: str, ident: str) -> None:
        """Book one thing a write tool created, so the cleanup removes and reads it back.

        ``kind`` is one of :data:`WRITE_KINDS`; ``ident`` is the id the tool answered
        (``event:<cal>:<object>``, ``card:<b>:<s>:<c>``, a row id, ``note:<id>`` or
        ``message:<token>:<id>``).
        """
        if kind not in WRITE_KINDS:
            raise ValueError(f"unknown write kind {kind!r}, expected one of {WRITE_KINDS}")
        if not ident or " " in ident:
            raise ValueError(f"not a usable id for {kind}: {ident!r}")
        self.writes_ledger.append(f"{kind} {ident}")


def _add_share(cleanup: Cleanup, harness: Harness, share_id: str, label: str) -> None:
    cleanup.add(
        f"share {label} {share_id}",
        lambda: harness.ocs_delete(f"{SHARES_API}/{share_id}"),
        lambda: str(harness.share_status(share_id)),
    )


def _message_state(harness: Harness, token: str, message_id: str) -> str:
    response = harness.ocs_get(f"{TALK_CHAT}/{token}/{message_id}/context?limit=1")
    if response.status_code != 200:
        return str(response.status_code)
    data = response.json()["ocs"]["data"] or []
    for message in data:
        if isinstance(message, dict) and str(message.get("id")) == message_id:
            deleted = message.get("messageType") == "comment_deleted"
            return "gelöscht" if deleted else "noch da"
    return "entfernt"


def _add_tool_write(cleanup: Cleanup, harness: Harness, entry: str) -> None:
    """One ledger entry as a cleanup step with its read back, removed before the world."""
    kind, _, ident = entry.partition(" ")
    # A row has no prefix in ids.py; every other kind is read with the codec of the tools.
    coded = kind != "row" and ident.startswith(f"{kind}:")
    parts = ids.parse(ident)[1] if coded else tuple(ident.split(":"))
    if kind == "event":
        url = f"{harness.calendar_url(parts[0])}{quote(parts[-1], safe='')}"
        cleanup.add(
            f"tool {entry}",
            lambda: harness.delete_calendar_url(url),
            lambda: str(harness.status_of(url)),
        )
    elif kind == "card":
        assert len(parts) == 3, f"a card needs board, stack and card: {entry}"
        board_id, card_id = parts[0], parts[2]
        path = f"/boards/{board_id}/stacks/{parts[1]}/cards/{card_id}"
        right_after: list[str] = []

        def undo_card() -> object:
            status = harness.deck("DELETE", path).status_code
            right_after.append(f"DELETE {status} {harness.card_listed(board_id, card_id)}")
            return None

        def read_card() -> str:
            # Measured on nc35: Deck answers GET on a deleted card with 403, and once the
            # board is soft deleted too, it answers its stack listing with 403 as well. So
            # the stack listing read right after the card's own DELETE is the proof, and the
            # board state of now is its second half.
            state = harness.deck_state(path)
            if state in ("404", "gelöscht"):
                return state
            listed = harness.card_listed(board_id, card_id)
            if listed == "entfernt":
                return listed
            board = harness.board_state(board_id)
            if right_after == ["DELETE 200 entfernt"] and board in ("gelöscht", "entfernt"):
                return "gelöscht"
            return f"{state} karte danach {right_after} liste {listed} board {board}"

        cleanup.add(f"tool {entry}", undo_card, read_card)
    elif kind == "row":
        row_id = parts[-1]
        cleanup.add(
            f"tool {entry}",
            lambda: harness.row_request("DELETE", row_id),
            lambda: str(harness.row_request("GET", row_id)),
        )
    elif kind == "note":
        note_id = parts[-1]
        cleanup.add(
            f"tool {entry}",
            lambda: harness.delete_note(note_id),
            lambda: str(harness.note_status(note_id)),
        )
    else:
        token, message_id = parts[0], parts[-1]
        cleanup.add(
            f"tool {entry}",
            lambda: harness.ocs_delete(f"{TALK_CHAT}/{token}/{message_id}"),
            lambda: _message_state(harness, token, message_id),
        )


def _event_ics(world: World, uid: str, tagged_fileid: str) -> bytes:
    """One event whose ATTACH points at the tagged file, the way the Calendar app links one."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//nc-mcp-connector//canary 28-07//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        "DTSTAMP:20260928T080000Z",
        "DTSTART:20261005T090000Z",
        "DTEND:20261005T100000Z",
        f"SUMMARY:{world.stamm}",
        (
            f"ATTACH;FMTTYPE=text/plain;FILENAME={world.tagged_name};"
            f"X-NC-FILE-ID={tagged_fileid}:{world.env.url}/f/{tagged_fileid}"
        ),
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")


def minimal_docx(text: str) -> bytes:
    """The smallest Word file python-docx opens: one paragraph, no styles part."""
    wp = "application/vnd.openxmlformats-officedocument.wordprocessingml."
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    body = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/word/document.xml" ContentType="{wp}document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}" Target="word/document.xml"/></Relationships>',
        )
        archive.writestr("word/document.xml", body)
    return buffer.getvalue()


def _build_files(world: World, cleanup: Cleanup) -> None:
    harness, marker = world.harness, world.marker
    harness.mkcol(world.root)
    cleanup.add_path(harness, world.root)
    harness.put(world.tagged_file, f"getaggt {world.stamm} {marker}\n".encode())
    harness.mkcol(world.locked_dir)
    # Registered after the root, so they run before it: a folder a refused call created
    # anyway is removed and read back on its own (pitfall 11 of phase 31).
    for folder in world.refused_folders:
        cleanup.add_folder(harness, folder)
    harness.put(world.locked_file, f"gesperrt {world.stamm} {marker}\n".encode())
    harness.put(world.control_file, f"kontrolle {world.stamm} {world.control_marker}\n".encode())
    # The same pair for files_read_as_markdown: a Word file below the locked folder and an
    # untagged one whose text carries the control marker.
    harness.put(world.locked_doc, minimal_docx(f"gesperrt {world.stamm} {marker}"))
    harness.put(world.control_doc, minimal_docx(f"kontrolle {world.stamm} {world.control_marker}"))
    for key, path in (
        ("root", world.root),
        ("tagged_file", world.tagged_file),
        ("locked_dir", world.locked_dir),
        ("locked_file", world.locked_file),
        ("control_file", world.control_file),
        ("locked_doc", world.locked_doc),
        ("control_doc", world.control_doc),
    ):
        world.fileids[key] = harness.fileid(path)
    world.proof["dateien"] = "PROPFIND 207 " + " ".join(
        f"{key}={value}" for key, value in world.fileids.items()
    )


def _build_notes(world: World, cleanup: Cleanup) -> dict[str, str]:
    harness = world.harness
    note_ids: list[str] = []
    cleanup.add_path(harness, world.category_path)
    cleanup.add(
        "notes",
        lambda: [harness.delete_note(note_id) for note_id in note_ids],
        lambda: "leer" if not set(note_ids) & harness.note_ids() else "noch da",
    )
    planned = {
        "note": (f"{world.stamm}-{world.marker}", f"{world.marker} getaggte Notiz", ""),
        "category_note": (
            f"{world.stamm}-katnotiz",
            f"{world.marker} Notiz in getaggter Kategorie",
            world.tagged_category,
        ),
        "control_note": (f"{world.stamm}-kontrolle", f"{world.control_marker} Kontrolle", ""),
    }
    created: dict[str, str] = {}
    for key, (title, text, category) in planned.items():
        body: dict[str, Any] = {"title": title, "content": f"{title}\n{text}\n"}
        if category:
            body["category"] = category
        note = harness.notes("POST", "/notes", body)
        created[key] = str(note["id"])
        note_ids.append(created[key])
    world.fileids["category"] = harness.fileid(world.category_path)
    listed = harness.note_ids()
    assert set(note_ids) <= listed, f"notes not listed: {set(note_ids) - listed}"
    world.proof["notizen"] = f"{len(note_ids)} angelegt und gelistet {created}"
    return created


def _build_talk(world: World, cleanup: Cleanup) -> tuple[str, str]:
    harness, user2 = world.harness, world.env.user2 or ""
    response = harness.ocs_post(TALK_ROOMS, {"roomType": 2, "roomName": world.stamm})
    token = str(harness.ocs_data(response, f"create room {world.stamm}")["token"])
    cleanup.add(
        f"talk raum {world.stamm}",
        lambda: harness.ocs_delete(f"{TALK_ROOMS}/{token}"),
        lambda: _absent(harness.room_tokens(), token),
    )
    status, share_id, raw = harness.share(world.tagged_file, SHARE_ROOM, token)
    assert status == 200, f"share into room: {status} {raw}"
    assert share_id, f"share into room without id: {raw}"
    _add_share(cleanup, harness, share_id, "raum")

    status, share_id, raw = harness.share(world.tagged_file, SHARE_USER, user2)
    assert status == 200, f"share with {user2}: {status} {raw}"
    assert share_id, f"share with {user2} without id: {raw}"
    _add_share(cleanup, harness, share_id, "user2")
    data = harness.ocs_data(
        harness.ocs_get(f"/apps/spreed/api/v1/file/{world.fileids['tagged_file']}"), "file room"
    )
    file_token = str((data or {}).get("token") or "")
    assert file_token, f"no file conversation: {data}"
    cleanup.add(
        "talk datei-raum",
        lambda: harness.ocs_delete(f"{TALK_ROOMS}/{file_token}/participants/self"),
        lambda: _absent(harness.room_tokens(), file_token),
    )
    harness.ocs_post(f"{TALK_ROOMS}/{file_token}/participants/active", {})
    # A message written in the file conversation, the way the Files sidebar chat writes one:
    # its search hit is titled "<actor> in <file name>" (review CR-01 of phase 28), so the
    # stem search of the canary has to meet it and find it withheld.
    posted = harness.ocs_data(
        harness.ocs_post(
            f"{TALK_CHAT}/{file_token}", {"message": f"{world.stamm} datei-raum-nachricht"}
        ),
        "message in file room",
    )
    file_message_id = str((posted or {}).get("id") or "")
    assert file_message_id, f"message in file room without id: {posted}"
    cleanup.add(
        f"talk datei-raum-nachricht {file_message_id}",
        lambda: harness.ocs_delete(f"{TALK_CHAT}/{file_token}/{file_message_id}"),
        lambda: _message_state(harness, file_token, file_message_id),
    )
    harness.ocs_delete(f"{TALK_ROOMS}/{file_token}/participants/active")
    tokens = harness.room_tokens()
    assert token in tokens, "the harness room is not listed"
    assert file_token in tokens, "the file conversation is not listed"
    world.proof["talk"] = f"raum {token} gelistet, datei geteilt (typ 10)"
    world.proof["datei-raum"] = f"{file_token} gelistet nach Freigabe an {user2} (typ 0)"
    return token, file_token


def _build_table(world: World, cleanup: Cleanup) -> tuple[str, str, tuple[str, ...]]:
    harness = world.harness
    table_id = harness.create_table(f"{world.stamm}-t")
    cleanup.add_table(harness, table_id)
    column_id = harness.create_link_column(table_id, "Verweis")
    rows = (
        harness.create_row(
            table_id,
            {column_id: world.link_cell(world.tagged_name, world.fileids["tagged_file"])},
        ),
        harness.create_row(
            table_id,
            {column_id: world.link_cell(world.control_name, world.fileids["control_file"])},
        ),
    )
    status, raw = harness.rows_simple_raw(table_id)
    wire = raw.replace("\\/", "/")
    assert status == 200, f"rows/simple {table_id}: {status}"
    assert world.tagged_name in wire, "row 1 does not carry the tagged name, the canary is blunt"
    assert f"/f/{world.fileids['tagged_file']}" in wire, "row 1 does not link the tagged file"
    assert world.control_name in wire, "row 2 does not carry the control name"
    world.proof["tables-link"] = f"tabelle {table_id} rows/simple {status} roh: {short(raw, 400)}"
    return table_id, column_id, tuple(str(row["id"]) for row in rows)


def _build_calendar(world: World, cleanup: Cleanup) -> str:
    harness, url = world.harness, world.calendar_url
    status = harness.mkcalendar(world.stamm, world.stamm)
    assert status == 201, f"MKCALENDAR {world.stamm}: {status}"
    cleanup.add(
        f"kalender {world.stamm}",
        lambda: harness.delete_calendar_url(url),
        lambda: str(harness.status_of(url)),
    )
    uid = f"{world.stamm}-{uuid.uuid4().hex[:8]}"
    event_url = f"{url}{uid}.ics"
    response = harness.request(
        "PUT",
        event_url,
        headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
        content=_event_ics(world, uid, world.fileids["tagged_file"]),
    )
    assert response.status_code == 201, f"PUT event: {response.status_code}"
    read = harness.request("GET", event_url)
    unfolded = read.text.replace("\r\n ", "").replace("\n ", "")
    attach = next((line for line in unfolded.splitlines() if line.startswith("ATTACH")), "")
    assert read.status_code == 200, f"GET event: {read.status_code}"
    assert world.tagged_name in attach, f"no ATTACH to the tagged file: {short(unfolded)}"
    world.proof["kalender-attach"] = f"GET {read.status_code} {attach}"
    return uid


def _build_deck(world: World, cleanup: Cleanup) -> tuple[str, str, str, str]:
    harness = world.harness
    board_id = harness.deck_created("/boards", {"title": world.stamm, "color": "0082c9"})
    cleanup.add(
        f"deck board {board_id}",
        lambda: harness.deck("DELETE", f"/boards/{board_id}"),
        lambda: harness.board_state(board_id),
    )
    stack_id = harness.deck_created(
        f"/boards/{board_id}/stacks", {"title": world.stamm, "order": 1}
    )
    card_id = harness.deck_created(
        f"/boards/{board_id}/stacks/{stack_id}/cards",
        {"title": world.stamm, "type": "plain", "order": 999},
    )
    # A file attachment of Deck is a share of type 12 at the card, which is what the Deck
    # frontend creates when a file from Files is attached; a refusal is recorded, not fatal.
    status, share_id, raw = harness.share(world.tagged_file, SHARE_DECK, card_id)
    if status == 200 and share_id:
        _add_share(cleanup, harness, share_id, "deck")
        attachment = f"share typ 12 an karte {card_id}: {status} id {share_id}"
    else:
        attachment = f"share typ 12 an karte {card_id} abgelehnt: {status} {raw}"
    world.proof["deck"] = f"board {board_id} stack {stack_id} karte {card_id}; {attachment}"
    return board_id, stack_id, card_id, attachment


def _tag_world(world: World, cleanup: Cleanup, created_notes: dict[str, str]) -> str:
    tag_id, created = ensure_tag()
    tagged: list[str] = []
    cleanup.add_tag(tag_id, created, tagged)
    for fileid in (
        world.fileids["tagged_file"],
        world.fileids["locked_dir"],
        created_notes["note"],
        world.fileids["category"],
    ):
        tag(fileid)
        tagged.append(fileid)
    status, found = world.harness.tagged_fileids(tag_id)
    missing = set(tagged) - found
    assert status == 207, f"tag REPORT: {status}"
    assert not missing, f"not tagged: {sorted(missing)}"
    control = {world.fileids["control_file"], created_notes["control_note"]} & found
    assert not control, f"a control node is tagged: {sorted(control)}"
    world.proof["tags"] = (
        f"REPORT {status} tag {tag_id} ({'angelegt' if created else 'vorbestehend'}) "
        f"getaggt {sorted(tagged)} kontrolle ungetaggt"
    )
    return tag_id


@contextlib.contextmanager
def canary_world(env: LiveEnv, raw: Path) -> Iterator[World]:
    """Build, tag and prove the canary world of one run, and remove it with read back proof.

    Every side effect is booked in a :class:`Cleanup` the moment it exists, so a failing
    build removes what was made so far. The cleanup lines go to ``raw`` and into
    :attr:`World.cleanup_lines`; asserting them is the caller's part.
    """
    if not env.user2:
        skip_or_fail("NC_MCP_TEST_USER2 is missing, the file conversation needs a second account")
    harness = Harness(env)
    cleanup = Cleanup()
    stamm, marker = run_id()
    base = World(
        h=stamm.removeprefix("kanarie28x"),
        stamm=stamm,
        marker=marker,
        control_marker=f"ck{uuid.uuid4().hex}",
        env=env,
        harness=harness,
    )
    # Registered first, so it runs last: whatever the deletions above moved into the trash
    # bin is purged by the stem, which no foreign entry carries.
    cleanup.add(
        f"papierkorb {stamm}",
        lambda: harness.purge_trash(stamm),
        lambda: "leer" if not harness.trash_entries(stamm) else "noch da",
    )
    try:
        settings = harness.notes("GET", "/settings") or {}
        notes_root = "/" + str(settings.get("notesPath") or "Notes").strip("/")
        base = dataclasses.replace(base, notes_root=notes_root)
        _build_files(base, cleanup)
        created_notes = _build_notes(base, cleanup)
        talk_token, file_room_token = _build_talk(base, cleanup)
        table_id, column_id, row_ids = _build_table(base, cleanup)
        event_uid = _build_calendar(base, cleanup)
        board_id, stack_id, card_id, attachment = _build_deck(base, cleanup)
        tag_id = _tag_world(base, cleanup, created_notes)
        world = dataclasses.replace(
            base,
            note_id=created_notes["note"],
            control_note_id=created_notes["control_note"],
            category_note_id=created_notes["category_note"],
            talk_token=talk_token,
            file_room_token=file_room_token,
            table_id=table_id,
            column_id=column_id,
            row_ids=row_ids,
            calendar_uri=stamm,
            event_uid=event_uid,
            board_id=board_id,
            stack_id=stack_id,
            card_id=card_id,
            deck_attachment=attachment,
            tag_id=tag_id,
        )
        yield world
    finally:
        for entry in base.writes_ledger:
            _add_tool_write(cleanup, harness, entry)
        lines = cleanup.run()
        base.cleanup_lines.extend(lines)
        for line in lines:
            record(raw, line)
        harness.close()
        fresh_guard()

# Phase 31: Ordner anlegen (`files_create_folder`) - Pattern Map

**Mapped:** 2026-11-12
**Files analyzed:** 30 (neu oder geändert)
**Analogs found:** 29 / 30 (nur `docs/folder-evidence.md` ohne echtes Vorbild im Code; Muster ist die Evidenzseite `docs/nc35-evidence.md`)

Leitvorbild für alles ist `files_upload`: Client in `dav.py`, Werkzeuglogik in `tools/files.py`, Registrierung in `server/reg_files.py`, Gates in `tests/contract`, Paartests in `tests/unit/test_pair_equality_files.py`, Kanarie und Live-Paar in `tests/integration`.

## File Classification

| Neue/geänderte Datei | Rolle | Data Flow | Nächstes Vorbild | Match |
|---|---|---|---|---|
| `src/mcp_connector/nextcloud/clients/dav.py` (`make_folder`, `_check_mkcol`, `oc-fileid`-Parser, `_PARENT_HINT`, Modul-Docstring) | Client | request-response (WebDAV-Write) | `dav.start_chunked_upload` (Z. 981-999) + `_check_write` (Z. 1100-1158) + `put_new_file` (Z. 775-799) | exact |
| `src/mcp_connector/tools/files.py` (`create_folder`, Kette, Zählung, Deckel, Abbruch-Hülle) | Service/Tool-Logik | request-response, Batch (Kette) | `files.upload` (Z. 615-660), `upload_binary` (Z. 1037-1078), `_writable` (Z. 1081-1101), `_visible_stat` (Z. 1140-1152) | exact (Kette: role-match) |
| `src/mcp_connector/server/__init__.py` (`CREATE_IDEMPOTENT`, `__all__`) | Config | , | `CREATE_ONLY`/`UPDATE_EXISTING` (Z. 42-50, 76-89) | exact |
| `src/mcp_connector/server/reg_files.py` (`files_create_folder`) | Registrierung | request-response | `files_list`/`files_read` (Z. 70-96), `files_update` (Z. 251-276) | exact |
| `src/mcp_connector/audit/allowlist.py` | Config | , | Eintrag `files_upload` (Z. 57-59) | exact |
| `tests/unit/test_files_create_folder.py` (neu) | Test (Unit) | request-response | `tests/unit/test_files_upload.py` | exact |
| `tests/unit/test_files_create_folder_exclusion.py` (neu) | Test (Unit, Guard) | request-response | `tests/unit/test_files_upload_exclusion.py` | exact |
| `tests/unit/test_pair_equality_files.py` | Test (Paar) | request-response | `test_files_upload_text_into_a_tagged_target_answers_like_an_invented_folder` (Z. 520-552) | exact |
| `tests/unit/test_dav_fileid_paths.py` | Test (Pin) | , | `PARENT_HINT` Z. 27 | exact |
| `tests/unit/test_canary_refusals.py` | Test (Unit-Spiegel Kanarie) | , | Parametrierung Z. 33-44 | exact |
| `tests/unit/test_docs_exclusion_truth.py` | Test (Doku-Wahrheit) | file-I/O | `TECH_ANCHORS`/`EVIDENCE_ANCHORS` (Z. 83-114), `test_each_limit_cites_a_finding_that_exists` (Z. 229-238) | role-match (neuer Anker-Typ) |
| `tests/contract/tool_classes.py` | Test-Tabelle | , | `FILE_WRITERS` (Z. 68-82), `PAIR_CASES` (Z. 122-138) | exact |
| `tests/contract/test_tool_classes.py` | Contract-Gate | , | `TOTAL` Z. 18, Aufteilung Z. 101-113 | exact |
| `tests/contract/test_tool_surface.py` | Contract-Gate | , | `EXPECTED_TOOLS`/`CREATE_TOOLS` (Z. 43-80), Annotations-Gate (Z. 744-777), README-Tabelle (Z. 817-845) | exact |
| `tests/contract/test_tool_bundles.py` | Contract-Gate | , | `BUNDLE_TOOLS["files"]` (Z. 29-38) | exact |
| `tests/contract/test_no_destructive_calls.py` (MKCOL-Nadel) | Contract-Gate (AST) | , | `_unconditional_puts` + `EXPECTED_PUT_CALLS` + `_PLANTED_PUTS` (Z. 478-603) | exact |
| `tests/contract/test_audit_surface.py` | Contract-Gate | , | wird durch Allowlist + `@graceful` grün, keine eigene Änderung nötig | , |
| `tests/integration/test_canary.py` | Test (Live) | , | `EXPECTED_TOOLS` Z. 63, `MUST_REFUSE` Z. 89, `plan()` Z. 150-161 | exact |
| `tests/integration/canary_world.py` | Test-Harness | , | `refusal_problem` (Z. 214-228) | exact |
| `tests/integration/test_pair_equality_live.py` | Test (Live-Paar) | , | `CASES` Eintrag `("files_upload", "text")` (Z. 170-172) | exact |
| `tests/integration/test_files_create_folder_live.py` (neu) | Test (Live, Impersonation) | request-response | `tests/integration/test_exapp_dav_matrix.py` (Z. 40-101) + `test_files_roundtrip.py` (Z. 35-65) | exact |
| `scripts/acceptance_all_tools.py` | Script | request-response | Block `# --- files` (Z. 146-161) | exact |
| `scripts/check_tool_budget.py` | Script (Kommentar) | , | Messzeilen Z. 89-103 | exact |
| `README.md`, `README.de.md`, `README.fr.md` | Doku | , | Zeile `files_upload` (README.md Z. 71), Zahl Z. 25, Bundle-Liste Z. 121-122 | exact |
| `docs/exclusion.md`, `.de.md`, `.fr.md` | Doku | , | Abschnitt `tech-upload-oracle` (exclusion.md Z. 310-316, .de Z. 320-326, .fr Z. 326-332) | exact |
| `docs/folder-evidence.md` (neu) | Doku (Beleg) | , | `docs/nc35-evidence.md` (Evidenzseite unter `docs/`) | partial |
| `CHANGELOG.md`, `.de.md`, `.fr.md` | Doku | , | `## [0.7.0]` / `### Added` (CHANGELOG.md Z. 34-42) | exact |

## Pattern Assignments

### `src/mcp_connector/nextcloud/clients/dav.py` (Client, request-response)

**Analog:** derselbe Modul; `start_chunked_upload`, `put_new_file`, `_check_write`, `_check`.

**Imports** (Z. 15-34), alles schon vorhanden, nichts Neues nötig (`re` ist importiert):
```python
import re
...
from ...errors import (
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
```

**Hinweistext, eine Quelle** (Z. 54-55, 72-84). `_PARENT_HINT` ändern, `parent_missing` selbst bleibt unverändert; gleicher Wortlaut gleichzeitig in `tests/unit/test_dav_fileid_paths.py:27`. Pitfall 8: `notes.py:283` nutzt dieselbe Fabrik, Hinweis muss auch ohne Bundle `files` tragen.
```python
_PARENT_HINT = "Create the folder in Nextcloud first, or upload into a folder that exists."

def parent_missing(path: str) -> ToolError:
    parent = dirname(path) or "/"
    return ToolError(
        message=f"The parent folder {parent} of {path} does not exist.",
        hint=_PARENT_HINT,
        reason=REASON_UNKNOWN_ID,
    )
```

**MKCOL-Aufruf, Kernmuster** (Z. 981-999). Für `make_folder` kopieren, aber Ziel `files_url(creds, target)` statt `uploads_url`, **kein** `headers=` mit Body-Bezug, kein `content=`/`data=`/`json=`/`files=` (MKCOL-Nadel). Der Aufruf muss die Form `client.request("MKCOL", ...)` mit Literal als erstem Argument behalten, sonst zählt die Nadel ihn nicht:
```python
async def start_chunked_upload(client, creds, path, upload_id) -> None:
    target = safe_path(path)
    response = await client.request(
        "MKCOL",
        uploads_url(creds, upload_id, path=target),
        headers={"Destination": files_url(creds, target)},
        auth=creds.auth(),
    )
    if response.status_code == 405:
        return
    _check_chunk_response(response, target)
```

**Rückgabeform** (Z. 787-799, `put_new_file`): `safe_path` zuerst, dann Request, dann Prüfer, dann Dict mit `path` und `created`:
```python
    target = safe_path(path)
    response = await client.put(...)
    _check_write(response, target)
    return {
        "path": target,
        "etag": response.headers.get("etag", ""),
        "created": True,
    }
```

**Statusprüfer, Vorbild für `_check_mkcol`** (Z. 1100-1158, `_check_write`). Reihenfolge der Zweige übernehmen; 405 gehört bei MKCOL NICHT in den Prüfer (wird in `make_folder` vor dem Prüfer als `created: False` zurückgegeben, Aufrufer macht `stat`). 412 und 413 entfallen, 400 kommt neu dazu:
```python
def _check_write(response: httpx.Response, path: str) -> None:
    status = response.status_code
    if status == 201:
        return
    ...
    if status == 403:
        raise ToolError(
            message=f"No permission to write to {path}.",
            hint="Check the share permissions of the target folder in Nextcloud.",
            reason=REASON_PERMISSION_DENIED,
        )
    if status in (404, 409):
        raise parent_missing(path)
    ...
    if status == 423:
        raise ToolError(
            message=f"{path} is locked in Nextcloud.",
            hint="Wait until the other client releases the lock, or choose another name.",
        )
    if status == 507:
        raise ToolError(
            message=f"Not enough space in Nextcloud for {path}.",
            hint="Free up quota in Nextcloud and try again.",
        )
    _check(response, path)
    raise ToolError(
        message=f"Nextcloud answered the upload of {path} with an unexpected status {status}.",
        hint="Check the Nextcloud log for that request; the file was probably not created.",
    )
```
Wichtig für Byte-Gleichheit: der 409-Zweig muss `parent_missing(<Ziel>)` werfen; bei der Kette übergibt das Werkzeug deshalb dem Prüfer bzw. der Hülle das Ziel, nicht das Segment (RESEARCH Pattern 4).

**Restzweige über `_check`** (Z. 1161-1205): 3xx, 401, 429, 5xx sind dort schon benannt; nicht duplizieren.

**`stat` für 405 und Zählung** (Z. 183-212): liefert `is_collection` und `fileid` in einem PROPFIND (D-31-04). 404 erscheint als `ToolError` mit `reason == REASON_UNKNOWN_ID` (über `not_found`, Z. 1185-1186).

**Nach angenommenem Schreiben kein Fehler mehr** (Z. 939-944 Docstring `update_file`, Z. 913-927 `_count_versions` mit `except (httpx.HTTPError, ToolError, ValueError, etree.LxmlError): return None`): Vorbild für den Rückfall, wenn `oc-fileid` fehlt und das Folge-`stat` scheitert, dann `id` weglassen.

**Modul-Docstring** (Z. 1-13): Ordner anlegen ergänzen; der Satz "No tool exposes delete, copy, rename ..." bleibt Prosa (Gate `test_the_gate_would_notice_a_destructive_call_in_real_code`, `test_no_destructive_calls.py:633`).

---

### `src/mcp_connector/tools/files.py` (Tool-Logik, request-response + Kette)

**Analog:** `upload` (Z. 615-660) für Reihenfolge, `upload_binary` (Z. 1037-1044) für "Guard vor jedem Write", `_visible_stat` (Z. 1149-1152) für 404-Erkennung, `_as_item` (Z. 346-347) für die Id-Form.

**Imports** (Z. 31-37), bereits vorhanden: `config`, `ids`, `REASON_UNKNOWN_ID`, `ConflictError`, `ToolError`, `NcClients`, `dav`, `withhold`.

**Reihenfolge safe_path, Wurzel, Guard, dann Netz** (Z. 638-660):
```python
    target = dav.safe_path(path)
    if target == config.files_root():
        raise ToolError(
            message="The upload target is the root folder, not a file.",
            hint=_FILE_TARGET_HINT,
        )
    ...
    await _writable(clients, target)
    return await dav.put_new_file(clients.client, clients.creds, target, data, content_type)
```

**Guard vor jedem Write, ein REPORT je Aufruf** (Z. 1037-1044):
```python
    # The check guards every write of every chunk call, not only the first ...
    # One guard per tool call, so the checks of one call share a single REPORT.
    if chunk_index == 1:
        await _writable(clients, target)
        await dav.start_chunked_upload(clients.client, clients.creds, target, raw_id)
    await _writable(clients, target)
```
Für die Kette: `await _writable(clients, target)` (immer mit dem **Ziel**) vor jedem `dav.make_folder(segment)`.

**`_writable` unverändert wiederverwenden** (Z. 1081-1101):
```python
async def _writable(clients: NcClients, target: str) -> None:
    scope = await clients.exclusion.scope(clients)
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    if scope.excludes(path=target):
        raise dav.parent_missing(target)
```

**404 eines `stat` erkennen** (Z. 1149-1152):
```python
    if isinstance(info, BaseException):
        if missing_as_conflict and isinstance(info, ToolError) and info.reason == REASON_UNKNOWN_ID:
            raise _update_conflict(target) from None
        raise info
```
Für die Zählung von unten: `try: await dav.stat(...) except ToolError as err: if err.reason != REASON_UNKNOWN_ID: raise`; Kandidaten nur `dav.within(p, root) and p != root` (`dav.py:703-709`).

**Id-Form** (Z. 346-347):
```python
    if entry["fileid"]:
        item["id"] = ids.encode_file(entry["fileid"])
```

**Konflikt-Muster** (`_update_conflict`, Z. 825 ff.; `ConflictError` aus `errors`): für "Datei am Pfad" nach 405 bzw. Datei als Vorfahr.

**Docstring-Stil** (Z. 621-631): Zweck, Entscheidungs-Ids (D-31-xx), Verweis auf `_writable` für den Ausschluss. Modul-Docstring Z. 16-17 ("`upload` is the only write in this package") anpassen.

---

### `src/mcp_connector/server/__init__.py` (Config)

**Analog** (Z. 42-50, 76-89):
```python
__all__ = [
    "CREATE_ONLY",
    "READ_ONLY",
    "UPDATE_EXISTING",
    ...
]

CREATE_ONLY = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)
```
Neu: `CREATE_IDEMPOTENT` gleich gebaut mit `idempotent_hint=True`, alphabetisch in `__all__`. Server-Instruktion (Z. 61-70) NICHT anfassen (Phase 34).

---

### `src/mcp_connector/server/reg_files.py` (Registrierung)

**Imports** (Z. 15-18): Zeile 18 um `CREATE_IDEMPOTENT` erweitern:
```python
from . import CREATE_ONLY, READ_ONLY, UPDATE_EXISTING, compact, graceful, mcp
```

**Registrierungsmuster** (Z. 87-96, `files_read`), schlank mit `Annotated[..., Field(description=...)]`, `ctx` zuletzt, `deps.resolve_clients(ctx)`, `compact(...)`:
```python
@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_read(
    path: Annotated[str, Field(description="Path inside the user's files, e.g. /Docs/notes.md")],
    offset: Annotated[int, Field(ge=0, description="Byte offset for a continued read")] = 0,
    ctx: Context | None = None,
) -> str:
    """Read a text file from Nextcloud; large files come back truncated with a next offset."""
    clients = deps.resolve_clients(ctx)
    return compact(await files_tools.read(clients, path=path, offset=offset))
```
Platzierung: nach `files_upload` (Z. 246), vor dem bedingten `files_update`-Block (Z. 249). Kein `user`-Parameter (Gate `test_no_input_schema_accepts_a_user_parameter`). Budget: Werkzeug rund 510 Bytes, Decke 1400.

---

### `src/mcp_connector/audit/allowlist.py` (Config)

**Analog** (Z. 56-59), alphabetisch einsortieren nach `"files_download"`:
```python
    "files_search": frozenset({"cursor", "folder", "limit", "query"}),
    "files_upload": frozenset(
        {"chunk_index", "content_type", "final", "path", "total_bytes", "upload_id"}
    ),
```
Neu: `"files_create_folder": frozenset({"parents", "path"}),` (alphabetisch vor `files_download`).

---

### `tests/unit/test_files_create_folder.py` (neu, Unit)

**Analog:** `tests/unit/test_files_upload.py`

**Kopf, Konstanten, Fixtures** (Z. 1-50):
```python
import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ConflictError, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"

@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    guard_routes.patch_untagged(monkeypatch)

@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )
```

**Erfolgsfall mit Kopfwert** (Z. 53-61), hier mit echtem Kopf aus der Rohdatei `oc-fileid: 00023274oclxpo7v8s2m`:
```python
@pytest.mark.anyio
async def test_upload_creates_the_file_and_reports_stable_fields(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PUT", url=TARGET_URL).mock(
            return_value=httpx.Response(201, headers={"etag": '"etag-new"'})
        )
        result = await files_tools.upload(clients, path=TARGET, content=CONTENT)
    assert result == {"path": TARGET, "etag": '"etag-new"', "created": True}
```

**Request-Reihenfolge festnageln** (Z. 82-90), Vorbild für "ohne `parents` kein PROPFIND vor MKCOL" und "kein Body":
```python
        methods = [call.request.method for call in mock.calls]
    assert methods == ["PUT"], "no PROPFIND probe: the guard is server side and race free"
```

**Fehlerzweig mit Zählung** (Z. 93-106): `call_count == 1`, Text-Fragmente prüfen. Für jeden Zweig 400, 403, 405-Datei, 409, 423, 507, 5xx je ein Test; Sandbox-Fälle mit `monkeypatch.setenv(config.ENV_FILES_ROOT, ...)` wie `tests/unit/test_canary_refusals.py:77`.

---

### `tests/unit/test_files_create_folder_exclusion.py` (neu, Guard)

**Analog:** `tests/unit/test_files_upload_exclusion.py` Z. 1-150.

**Clients je Aufruf, Tupelvergleich, Write-Zähler** (Z. 42-88):
```python
def _clients() -> NcClients:
    """One bundle per tool call, as ``deps.resolve_clients`` builds it: one guard each."""
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )

def _tuple(err: ToolError) -> tuple[str, str, str]:
    return (err.message, err.hint, err.reason)

class _Writes:
    def __init__(self, mock: respx.MockRouter, path: str, status: int = 201) -> None:
        ...
    @property
    def count(self) -> int:
        return sum(r.call_count for r in (self.put, self.mkcol, self.chunk, self.move))

def _mock() -> respx.MockRouter:
    return respx.mock(assert_all_mocked=True, assert_all_called=False)
```

**Kernpaar getaggt gegen fehlend** (Z. 114-130):
```python
    with _mock() as mock:
        _, report = guard_routes.active(mock, TAGGED_FOLDER)
        writes = _Writes(mock, path)
        tagged = await _text(path)
        assert report.call_count == 1
    with _mock() as mock:
        _untagged(mock)
        _Writes(mock, path, status=409)
        missing = await _text(path)
    assert writes.count == 0, "no write request before the refusal"
    assert _tuple(tagged) == _tuple(missing)
    assert _tuple(tagged) == _tuple(dav.parent_missing(path))
```
Zusätzlich: `parents=True` getaggt (kein PROPFIND, kein MKCOL), Kette über drei Segmente mit `report.call_count == 1` (Pitfall 5), fail-closed mit `withhold.unavailable_error()`.

---

### `tests/unit/test_pair_equality_files.py` (Paar, Unit)

**Analog** (Z. 58-67 `COVERED`, Z. 520-552 Text-Upload, Z. 555-564 `_staging` mit MKCOL-Route):
```python
def _text_put(path: str, status: int) -> Mocks:
    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PUT", url=f"{FILES}{path}").mock(return_value=httpx.Response(status))
    return mocks

@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_upload_text_into_a_tagged_target_answers_like_an_invented_folder(
    mode: str, unexpected: list[str]
) -> None:
    invented = f"{INVENTED_FOLDER}/neu.txt"
    for path in ("/Projekt/neu.txt", "/Docs/geheim.txt"):
        tagged, unknown = await pair(
            "files_upload",
            {"path": path, "content": "# Neue Notiz\n"},
            {"path": invented, "content": "# Neue Notiz\n"},
            path, invented,
            _text_put(path, 201), _text_put(invented, 409),
            mode, unexpected,
        )
        _assert_equal(tagged, unknown, mode, PARENT_MISSING)
        assert '"isError": true' in tagged
```
Neu: `_mkcol(path, status)` mit `method="MKCOL", url=f"{FILES}{path}"`, Test mit `/Projekt/neu` gegen `f"{INVENTED_FOLDER}/neu"`, `COVERED` um `("files_create_folder", "path")` erweitern. `test_the_files_family_covers_exactly_its_pair_cases` (Z. 600-605) hält es gegen `PAIR_CASES`.

---

### `tests/unit/test_dav_fileid_paths.py` (Pin)

Z. 26-27, nur die Konstante gleichzeitig mit `dav._PARENT_HINT` ändern:
```python
PARENT_HINT = "Create the folder in Nextcloud first, or upload into a folder that exists."
```

### `tests/unit/test_canary_refusals.py` (Unit-Spiegel)

Z. 33-44 und 47-59 je eine Zeile `("files_create_folder", {"path": ...}, parent_missing())` bzw. mit `SERVER_ERROR`; Pfad `UPLOAD`-artig unter `/kanarie28xab/Gesperrt-ab/`.

### `tests/unit/test_docs_exclusion_truth.py` (Doku-Wahrheit)

**Analog** (Z. 83-114, 229-238):
```python
TECH_ANCHORS = ("tech-sqlite", "tech-upload-oracle", ...)
#: All 21 ids, the contract of plan 29-08.
ALL_ANCHORS = LIMIT_ANCHORS + TECH_ANCHORS + SECTION_ANCHORS
EVIDENCE_ANCHORS = LIMIT_ANCHORS + TECH_ANCHORS
FINDINGS_PREFIX = "../.planning/phases/"

@page_params
def test_each_limit_cites_a_finding_that_exists(lang: str) -> None:
    text = read(PAGES[lang])
    for anchor in EVIDENCE_ANCHORS:
        cited = [link for link in links_in(section_at(text, anchor)) if FINDINGS_PREFIX in link]
        assert cited, ...
        for link in cited:
            target = (DOCS / link.split("#", 1)[0]).resolve()
            assert target.is_file(), ...
```
Neu: `STABLE_EVIDENCE_ANCHORS = ("tech-folder-oracle",)` in `ALL_ANCHORS` (21 auf 22, Docstrings), NICHT in `EVIDENCE_ANCHORS`; eigener Test nach obigem Muster, aber Link ohne `../`-Präfix auf eine Datei unter `docs/` (z. B. `folder-evidence.md`), die existiert und nicht unter `.planning/` liegt.

---

### `tests/contract/tool_classes.py`

**`FILE_WRITERS`** (Z. 68-82), Satz mit `file:line`-Anker, endet mit Punkt, mindestens 20 Zeichen (`MIN_REASON`, Z. 117):
```python
FILE_WRITERS: dict[str, str] = {
    "files_upload": (
        "Creates a file at a path and checks _writable before every write "
        "(tools/files.py:484-529, :705-725)."
    ),
```
**`PAIR_CASES`** (Z. 122-138): `("files_create_folder", "path"): "files",` nach den Upload-Fällen; nur `parents=false` (Pitfall 6).

### `tests/contract/test_tool_classes.py`

Z. 18 `TOTAL = 23` auf 24; Z. 33 Meldungstext; Z. 101-113 `(13, 3, 7)` auf `(13, 4, 7)`, Docstring "twenty-fourth" auf "twenty-fifth".

### `tests/contract/test_tool_surface.py`

**Mengen** (Z. 43-80): `files_create_folder` in `EXPECTED_TOOLS`; neue Menge daneben:
```python
CREATE_TOOLS = {
    "files_upload",
    ...
}
```
**Annotations-Gate** (Z. 758-777), eigenen Zweig vor `elif name in CREATE_TOOLS` einfügen, Muster des `files_update`-Zweigs:
```python
        if name == "files_update":
            assert annotations.read_only_hint is False
            assert annotations.destructive_hint is True
            assert annotations.idempotent_hint is False
        elif name in CREATE_TOOLS:
            ...
            assert annotations.idempotent_hint is False, (
                f"a second {name} call is a second object, not a no-op"
            )
```
**README-Tabelle** (Z. 837-845): die neue Menge auf `"create-only"` abbilden (`if name in CREATE_TOOLS or name in IDEMPOTENT_CREATE_TOOLS`). Zahlen Z. 565 (`== 23`, "twenty-three"), Z. 746 ("six create-only tools"), Z. 803 ("all 23 schemas") nachziehen.

### `tests/contract/test_tool_bundles.py`

Z. 29-38, `"files_create_folder"` in das `frozenset` des Bundles `files`. Die Bundle-Zuordnung selbst entsteht automatisch über das Modul `reg_files` (`server/__init__.py:167-177`).

### `tests/contract/test_no_destructive_calls.py` (MKCOL-Nadel)

**Analog** (Z. 478-480, 505-556, 559-574, 577-603). Zählpin, AST-Erkennung mit `call.func.attr == "request"` und `args[0].value == ...`, Gegenproben gepflanzt:
```python
EXPECTED_PUT_CALLS = 6

    def _is_put(call: ast.Call) -> bool:
        ...
        return (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "request"
            and bool(call.args)
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == "PUT"
        )

def test_every_put_carries_a_usable_precondition() -> None:
    findings: list[str] = []
    total = 0
    for path in _source_files():
        relative = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found, seen = _unconditional_puts(relative, tree)
        ...
    assert total == EXPECTED_PUT_CALLS, (...)

_PLANTED_PUTS = [
    "async def f(client, url, data):\n    await client.put(url, content=data)\n",
    ...
]
def test_the_put_gate_flags_each_planted_bypass() -> None:
    for source in _PLANTED_PUTS:
        findings, seen = _unconditional_puts("planted.py", ast.parse(source))
        assert seen == 1, source
        assert findings, ...
```
Neu: `EXPECTED_MKCOL_CALLS = 2`, `MKCOL_HOME = "nextcloud/clients/dav.py"` (wie `CHUNK_ASSEMBLY_MOVE`, Z. 142), `_mkcol_findings` (Skizze RESEARCH "Code Examples"), `_PLANTED_MKCOLS` mit Body, fremder Datei und `method="MKCOL"`. `EXPECTED_PUT_CALLS` bleibt 6.

---

### `tests/integration/test_canary.py` und `canary_world.py`

**Analog** (`test_canary.py` Z. 63, 89, 161):
```python
EXPECTED_TOOLS = 23
MUST_REFUSE = ("files_upload", "notes_create", "talk_send")
        "files_upload": [{"path": f"{world.locked_dir}/neu-{world.h}.txt", "content": "x"}],
```
Neu: 24; `files_create_folder` in `MUST_REFUSE`; Plan `[{"path": f"{world.locked_dir}/ordner-{world.h}"}, {"path": f"{world.locked_dir}/a-{world.h}/b", "parents": True}]`.

**`refusal_problem`** (`canary_world.py` Z. 221):
```python
    elif tool in ("files_upload", "notes_create"):
        normal = PARENT_MISSING_FRAGMENTS
```
`files_create_folder` in dieses Tupel aufnehmen.

### `tests/integration/test_pair_equality_live.py`

**Analog** (Z. 170-172):
```python
    ("files_upload", "text"): lambda w: _path_pair(
        "files_upload", f"{w.locked_dir}/neu.txt", f"{_missing(w)}/neu.txt", content="x"
    ),
```
Neu: `("files_create_folder", "path"): lambda w: _path_pair("files_create_folder", f"{w.locked_dir}/neu-ordner", f"{_missing(w)}/neu-ordner"),`. `test_every_pair_case_is_measured_live` erzwingt den Eintrag.

### `tests/integration/test_files_create_folder_live.py` (neu, Impersonation)

**Analog Impersonation** (`test_exapp_dav_matrix.py` Z. 40-93): Kopf mit Laufanleitung (Z. 31-37), `_appapi_clients` mit `mode=MODE_APPAPI`, `secret=exapp_env["app_secret"]`, Fixture `alice_clients`/`bob_clients`, `pytestmark = [pytest.mark.integration, pytest.mark.anyio]`, Kontrollen "kein App-Passwort im Prozess" und "falsches Secret 401" (ab Z. 109).
```python
def _appapi_clients(exapp_env: dict[str, str], user: str) -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False, timeout=30.0),
        creds=Credentials(
            base_url=normalize_base_url(exapp_env["base_url"]),
            user=user,
            secret=exapp_env["app_secret"],
            mode=MODE_APPAPI,
            app_id=exapp_env["app_id"],
            app_version=exapp_env["app_version"],
            aa_version=exapp_env["aa_version"],
        ),
    )
```
**Analog eindeutiger Pfad je Lauf** (`test_files_roundtrip.py` Z. 35-37):
```python
def _unique_path() -> str:
    return f"/mcp-connector-test-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.md"
```
Aufräumen über Harness-Adminweg (Pitfall 11), nie über den Connector.

---

### `scripts/acceptance_all_tools.py`

**Analog** (Z. 146-153):
```python
    # --- files ------------------------------------------------------------------------
    path = f"/{marker}-{stamp}.md"
    await call(
        client,
        report,
        "files_upload",
        {"path": path, "content": f"# {marker}\nAbnahmelauf Phase 1, Straßenbau.\n"},
    )
```
Neu im selben Block: `call(client, report, "files_create_folder", {"path": f"/{marker}-{stamp}-ordner/a/b", "parents": True})`, zweiter Aufruf mit `loads(...)` und Prüfung `created is False`, sonst `report.add("files_create_folder", "FAIL", ...)` (Muster Z. 154-157).

### `scripts/check_tool_budget.py`

Messzeilen-Stil (Z. 89-103), neue Zeile anhängen, `BUDGET_BYTES = 18_000` unverändert:
```python
#   Measurement 2026-09-30, all 23 curated tools registered (files_read_as_markdown of
#               TOOL-14): 17763 bytes
#   Budget      unchanged at 18000, because the measurement fits below it
```

### `README.md`, `README.de.md`, `README.fr.md`

Tabelle (README.md Z. 64-72), Zeile nach `files_upload`, Stufe exakt `create-only` (Test liest nur `README.md`):
```markdown
| `files_upload` | create-only | A new text file or any-size binary upload in base64 chunks; an existing path is refused, never overwritten |
```
Zahl Z. 25 ("23 tools") auf 24; Bundle-Liste Z. 121-122 um `files_create_folder`. In de/fr dieselben drei Stellen.

### `docs/exclusion.md`, `.de.md`, `.fr.md`

Abschnittsmuster (exclusion.md Z. 310-316), neuer Abschnitt `tech-folder-oracle` direkt danach; Beleglink auf `folder-evidence.md` (stabiler Ort, siehe Truth-Test):
```markdown
<a id="tech-upload-oracle"></a>
### Upload next to a tagged file

An upload to a tagged destination gets the refusal of a missing parent folder; for a tagged
file below a visible parent folder that refusal still shows that something is special there,
which cannot be avoided without writing.
Source: [27-SECURITY.md, A-27-03](../.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-SECURITY.md).
```
Deutsch: Überschrift-Stil "Upload neben einer getaggten Datei", "Quelle:"; Französisch: "Source :" mit geschütztem Leerzeichen-Stil wie Z. 332.

### `CHANGELOG.md`, `.de.md`, `.fr.md`

Unter `## [Unreleased]` (Z. 12) einen Block nach dem Muster Z. 36-42:
```markdown
### Added

- Native ChatGPT file attachments in `files_upload` (`openai/fileParams`): ...
```
`tests/unit/test_changelog_translations.py` hält die Abschnitte der drei Sprachen gleich. Keine "closes #N"-Wörter.

## Shared Patterns

### Pfad und Sandbox
**Quelle:** `dav.safe_path` (`dav.py:125-162`), `dav.within` (`dav.py:703-709`), Wurzel-Ablehnung `files.py:638-643`
**Gilt für:** `make_folder`, `create_folder`, Kettenkandidaten
Ziel gleich `config.files_root()` vorab ablehnen; Kandidaten nur `within(p, root) and p != root`.

### Ausschluss `kein-ki` (fail-closed, byte-gleich)
**Quelle:** `files._writable` (`files.py:1081-1101`), `withhold.unavailable_error()`, `dav.parent_missing` (`dav.py:72-84`)
**Gilt für:** jeden `MKCOL` der Kette, immer mit dem Ziel als Argument, nie mit dem Segment. Kein PROPFIND vor `_writable`.

### Fehlerklassen und Gründe
**Quelle:** `errors.py` (`ToolError`, `ConflictError`, `REASON_PERMISSION_DENIED`, `REASON_UNKNOWN_ID`), Zweigtexte aus `_check_write`/`_check_chunk_response` (`dav.py:1058-1158`)
**Gilt für:** `_check_mkcol`, Abbruch-Hülle. Kein Servertext (`s:message`) in Meldungen; `reason` nur an den Statuszweigen (Kommentar Z. 1128-1130).

### Audit und Fehlerübersetzung
**Quelle:** `@graceful` (`server/__init__.py:97 ff.`), `PARAM_ALLOWLIST` (`audit/allowlist.py:45-71`)
**Gilt für:** Registrierung; Parameter `path`, `parents` nur als Namen.

### Antwortserialisierung
**Quelle:** `compact` (`server/__init__.py:92-94`), `ids.encode_file` (`ids.py:58-59`)
**Gilt für:** Erfolgsantwort `{"path", "created", "id"[, "created_folders"]}`; leere Felder weglassen wie `_as_item` (`files.py:330-348`).

### Testmuster Guard
**Quelle:** `guard_routes` (`active`, `untagged`, `stale`, `timeout`, `unverifiable`, `reset`), `GUARD_MODES` (`test_pair_equality_files.py:51`), Catch-all-Route (Z. 143-147)
**Gilt für:** alle Exklusions- und Paartests.

## No Analog Found

| Datei | Rolle | Data Flow | Grund |
|---|---|---|---|
| `docs/folder-evidence.md` | Doku (Live-Beleg) | , | Bisher liegen Belege unter `.planning/phases/`; ein stabiler Ort unter `docs/` ist neu. Nächstes Formvorbild ist `docs/nc35-evidence.md`. |
| Kettenlogik "von unten zählen, von oben anlegen" in `create_folder` | Tool-Logik | Batch | Keine mehrstufige Schreibkette im Code; RESEARCH Pattern 3 und 4 sind die Vorlage, Bausteine (`stat`, `_writable`, `make_folder`) existieren. |
| Strecke Nextcloud 32 unter Impersonation | Infrastruktur | , | Nie gelaufen; `compose.exapp.yml` + `scripts/bootstrap_exapp.sh` mit `NC_EXAPP_NEXTCLOUD_IMAGE=nextcloud:32.0.15-apache` (RESEARCH Pitfall 10). |

## Metadata

**Analog search scope:** `src/mcp_connector/{nextcloud/clients,tools,server,audit}`, `tests/{unit,contract,integration}`, `scripts/`, `docs/`, READMEs, CHANGELOG
**Files scanned:** 24
**Pattern extraction date:** 2026-11-12

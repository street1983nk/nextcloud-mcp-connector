---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 03
subsystem: caldav-client
tags: [caldav, vtodo, ids, discovery, byte-pin, create-only, datenschutz]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-02 (collation=i;octet, writable_privilegien, namensregel=owner-displayname, home404=e6)
provides:
  - tests/unit/test_caldav_bytes_pin.py, sha256-Pin der zwei Kalenderkörper vor jeder Änderung an caldav.py
  - caldav.WriteWording, caldav.EVENT_WORDING, caldav.put_new_object (der eine PUT), put_event als Hülle
  - ids.task_list_key, ids.encode_task, ids.SHARED_BY_MARKER, Parse-Zweig task (neun Formen im Hinweis)
  - clients/tasks.py mit TaskList, TodoObject, Discovery, Klassifikation, Namensregel, REPORT-Körpern, GET, Statusprüfer, TASK_WORDING
affects: [32-04, 32-04b, 32-05, 32-06]

tech-stack:
  added: []
  patterns:
    - "Ein create-only-PUT je Modul, Wortlaut als Parameter (WriteWording) statt eines zweiten PUT"
    - "Geteilte Liste: Schlüssel s plus 16 Hex von sha256(uri), Name ohne Besitzerzusatz, uri nur für Request-URLs"
    - "Eigenschaften über alle 2xx-Propstats einsammeln, nicht nur das erste"

key-files:
  created:
    - tests/unit/test_caldav_bytes_pin.py
    - tests/unit/test_caldav_writer.py
    - src/mcp_connector/nextcloud/clients/tasks.py
    - tests/unit/test_tasks_client.py
  modified:
    - src/mcp_connector/nextcloud/clients/caldav.py
    - src/mcp_connector/ids.py
    - tests/unit/test_ids.py
    - vulture_whitelist.py

key-decisions:
  - "put_new_object gibt die Sammlungs-URI nicht zurück (nur object_name, etag, created); put_event ergänzt calendar und liefert dasselbe Dict wie vorher"
  - "Ersatzname einer geteilten Liste ohne passenden Zusatz: URI-Teil vor _shared_by_, bei leerem Rest der Schlüssel; nie der rohe displayname"
  - "Ausschluss nach lokalen Namen des resourcetype (trash-bin, deleted-calendar, schedule-inbox/-outbox, subscribed) plus URI trashbin/inbox/outbox; Pflicht ist {urn:ietf:params:xml:ns:caldav}calendar"
  - "build_related_query: leerer Wert ist ToolError mit REASON_GUARD_TRIPPED vor jedem Request, andere Eigenschaft als RELATED-TO/UID ist ValueError (Programmierfehler)"
  - "query_todos überspringt hrefs mit Schrägstrich am Ende (Sammlung, kein Objekt) und Antworten ohne calendar-data; ICS-Bytes ungeparst, CRLF bleibt"

patterns-established:
  - "Vorübergehende vulture-Einträge mit Kommentar 'until reg_tasks.py registers the bundle (32-05)'"

requirements-completed: []

duration: ca. 30min
completed: 2026-11-13
---

# Phase 32 Plan 03: Client-Schicht des Aufgaben-Bundles Summary

**Kalenderkörper per sha256 gepinnt, der eine create-only-PUT in caldav.py mit wählbarem Wortlaut (put_event als Hülle, Sätze Wort für Wort gleich), Id-Codec `task:<list>:<object>` mit neutralem Schlüssel `s`+16 Hex für geteilte Listen und `clients/tasks.py` mit eigener Discovery, die Deck, Papierkorb, gelöschte Kalender, Scheduling und Abos ausschließt und geteilte Listen ohne Besitzernamen liefert.**

## Ergebnis je Task

| Task | Ergebnis | Commits |
|---|---|---|
| 1: Byte-Pin, generischer Schreiber | Pin vor der Änderung (3 Tests), `WriteWording`/`EVENT_WORDING`/`put_new_object`, `_check_write` heißt `_check_new_object`, Zweige und `reason` unverändert; genau ein `.put(` in caldav.py, `EXPECTED_PUT_CALLS` bleibt 6; 22 Schreibertests | `69840d7` (test, Pin), `09711fa` (refactor) |
| 2: Codec `task:` | `task_list_key`, `encode_task`, Zweig `task` mit vollem Split, `_HINT` und Docstring mit `task:<list>:<object>`, Tests auf neun Formen gehoben samt Namen | `cb48348` (test, RED), `8a8d222` (feat) |
| 3: clients/tasks.py | Discovery, Klassifikation, Namensregel, `build_todo_query`, `build_related_query`, `query_todos`, `get_todo`, `_check`, `TASK_WORDING`; 73 Tests | `56bf266` (test, RED), `c7d60e3` (feat) |

## Öffentliche Schnittstelle von clients/tasks.py

```python
NS_NEXTCLOUD_COM = "http://nextcloud.com/ns"
DECK_PREFIX = "app-generated--"
SHARED_MARKER = ids.SHARED_BY_MARKER            # "_shared_by_"
WRITE_PRIVILEGES = frozenset({"write", "write-content", "bind", "all"})
RELATED_PROPERTIES = ("RELATED-TO", "UID")
TEXT_MATCH_COLLATION = "i;octet"

@dataclass(frozen=True, slots=True)
class TaskList:
    uri: str          # nur für Request-URLs, bei geteilten Listen nie in eine Antwort
    key: str          # ids.task_list_key(uri)
    name: str         # ohne Besitzerzusatz
    shared: bool
    writable: bool
    @property
    def own(self) -> bool: ...

@dataclass(frozen=True, slots=True)
class TodoObject:
    object_name: str  # aus dem href
    ics: bytes        # roh, ungeparst

TASK_WORDING: caldav.WriteWording

def build_task_discovery_body() -> bytes
async def discover_task_lists(client: httpx.AsyncClient, creds: Credentials) -> list[TaskList]
def parse_task_home(body: str | bytes, home_path: str = "") -> list[TaskList]
def build_todo_query(completed: bool | None = None) -> bytes
def build_related_query(prop: str, value: str) -> bytes
async def query_todos(client: httpx.AsyncClient, creds: Credentials, task_list: TaskList, body: bytes) -> list[TodoObject]
async def get_todo(client: httpx.AsyncClient, creds: Credentials, task_list: TaskList, object_name: str) -> bytes
```

Dazu in caldav.py:

```python
@dataclass(frozen=True, slots=True)
class WriteWording:  # replaced, exists, forbidden, missing, unsupported, unexpected je mit _hint, dazu what
EVENT_WORDING: WriteWording
async def put_new_object(client, creds, collection_uri, object_name, ics_bytes, wording, label) -> dict[str, Any]
# Rückgabe {"object_name", "etag", "created"}; Platzhalter {label}, {name}, {status}
```

und in ids.py: `SHARED_BY_MARKER`, `task_list_key(uri) -> str`, `encode_task(list_key, object_name) -> str`.

## Angewandte Entscheide aus 32-02

- `collation=i;octet`: `build_related_query` sendet `text-match collation="i;octet" match-type="contains"`; die exakte Nachprüfung bleibt Sache des Aufrufers (32-04).
- `writable_privilegien=write,write-content,bind,all`: `WRITE_PRIVILEGES`, mindestens eines; `write-properties` allein zählt nicht (getestet).
- `namensregel=owner-displayname`: Zusatz ` (<owner-displayname>)` wird nur bei genauem Ende entfernt; `owner-displayname` aus `http://nextcloud.com/ns`, nie ausgegeben.
- `home404=e6`: Home 404 und leere 207 ergeben `[]`, kein Fehler.

## Vorübergehende vulture-Einträge

In `vulture_whitelist.py`, Abschnitt "The client layer of the tasks bundle, plan 32-03", je mit Kommentar "until reg_tasks.py registers the bundle (32-05)":
`encode_task`, `TASK_WORDING`, `discover_task_lists`, `build_todo_query`, `build_related_query`, `query_todos`, `get_todo`.
`task_list_key` stand zwischen Task 2 und Task 3 dort und ging mit seinem Aufrufer `clients/tasks.py`.

## Gates (32-RULES.md Abschnitt 3, Stand c7d60e3)

- pytest unit+contract: 6105 passed, 35 skipped, Exit 0 (vorher 5996; neu 3 Pin, 22 Schreiber, 11 ids, 73 Aufgaben-Client)
- check_tool_budget: `tools/list: 16222 bytes, 24 tools, budget 18000`, Exit 0 (unverändert, kein Werkzeug registriert)
- ruff check: All checks passed; ruff format --check: 383 files already formatted
- pyright (latest): 0 errors, 0 warnings, 0 informations
- vulture: Exit 0

## TASK-01-Beweis

- Positivkontrolle Basis `b40f7623a5111b95a3fe3cf6e5295c4965ca7056` ist Vorfahr von HEAD.
- `git diff "$B" -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py` leer; Gegentreffer `git diff "$B" -- src/mcp_connector/nextcloud/clients/caldav.py | grep -c "def put_new_object"` = 1.
- Pin-Commit `69840d7` liegt vor dem ersten Commit, der caldav.py ändert (`09711fa`).
- `grep -c '\.put(' caldav.py` = 1; `test_no_destructive_calls` grün mit `EXPECTED_PUT_CALLS = 6`.

## TDD Gate Compliance

- Task 1: Pin-Commit `69840d7` grün auf unverändertem Code (so verlangt). Die Schreibertests waren vor dem Umbau rot (fehlendes `WriteWording`), wurden laut Plan aber im selben Commit wie der Umbau eingecheckt (`09711fa`, refactor); kein eigener RED-Commit, so im Plan vorgesehen.
- Task 2 RED `cb48348`: rot nur `tests/unit/test_ids.py` (11 Tests, AttributeError für `encode_task`/`task_list_key`), pyright 12 Fehler nur in dieser Datei; alle übrigen 6021 Tests, ruff, format, vulture grün. GREEN `8a8d222`: alles grün.
- Task 3 RED `56bf266`: rot nur `tests/unit/test_tasks_client.py` (Sammelfehler, Modul fehlt), pyright 1 Fehler nur in dieser Datei; mit `--continue-on-collection-errors` übrige 6032 Tests, ruff, format, vulture grün. GREEN `c7d60e3`: alles grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] vulture-Einträge schon in Task 2**
- **Found during:** Task 2 (GREEN)
- **Issue:** `encode_task` und `task_list_key` haben nach Task 2 nur Testaufrufer; vulture wäre rot gewesen, der Plan nennt die Einträge erst in Task 3.
- **Fix:** beide als vorübergehende Einträge im feat-Commit von Task 2; `task_list_key` in Task 3 wieder entfernt (Aufrufer `clients/tasks.py`).
- **Commit:** `8a8d222`, `c7d60e3`

**2. [Rule 1 - Bug] Hilfsname enthielt die verbotene Zeichenkette**
- **Found during:** Task 3
- **Issue:** Der erste Name des Einsammel-Helfers enthielt `_ok_props` als Teilzeichenkette; der Quelltext-Test (I3) schlug an.
- **Fix:** Helfer heißt `_collect_props`.
- **Commit:** `c7d60e3`

**3. [Rule 1 - Bug] href einer Sammlung als Objektname**
- **Found during:** Task 3
- **Issue:** Ein href mit Schrägstrich am Ende ergab nach `rstrip("/")` den Namen der Liste als Objektnamen.
- **Fix:** hrefs mit Schrägstrich am Ende werden übersprungen (Test vorhanden).
- **Commit:** `c7d60e3`

### Andere Abweichungen

- `put_new_object` liefert keinen Schlüssel `calendar` bzw. `collection`, damit die URI einer geteilten Liste das Client-Ergebnis nicht verlässt; `put_event` ergänzt `calendar` und liefert dasselbe Dict wie vorher.
- Testname des RED-Commits in Task 2: "test(32-03): task ids and the neutral key of a shared list".

## Known Stubs

Keine. Die Client-Funktionen haben bis 32-04/32-05 keinen Aufrufer im Produktcode (vulture-Einträge oben), das ist im Plan so vorgesehen.

## Hinweise für 32-04

- `query_todos` liefert Rohbytes; Parsen je Objekt mit Überspringen und Zählung, Objektnamen mit `:` scheitern an `ids.encode_task` (Guard) und sind zu überspringen.
- Kinder- und Eltern-Treffer aus `build_related_query` sind Kandidaten ("contains"), exakt nachprüfen.
- Bekannt bis 32-06: `fetch` mit `task:`-Id landet im Standardzweig "unfetchable".

## Self-Check: PASSED

Vier neue Dateien vorhanden (test_caldav_bytes_pin.py, test_caldav_writer.py, clients/tasks.py, test_tasks_client.py), sechs Commits (69840d7, 09711fa, cb48348, 8a8d222, 56bf266, c7d60e3) im Verlauf, keiner mit Trailer.

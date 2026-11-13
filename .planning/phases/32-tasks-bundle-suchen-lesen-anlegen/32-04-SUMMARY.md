---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 04
subsystem: tasks-tools
tags: [caldav, vtodo, zeitmatrix, suche, blaettern, unteraufgaben, datenschutz]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-02 (per_list_timeout_s=1, subtask_timeout_s=1, max_results=500), 32-03 (clients/tasks.py, task:-Codec)
provides:
  - tools/tasks.py mit _read_todo (Zeitmatrix), search_tasks, read_task, _resolve_list (für 32-04b)
  - Konstanten PAGE_SIZE, PER_LIST_TIMEOUT, SUBTASK_TIMEOUT, MAX_RESULTS, MAX_SUBTASKS, MAX_DESCRIPTION_BYTES, SEARCH_CAP_NOTE, NO_LIST_HINT
  - tests/unit/test_tasks_time_matrix.py, test_tasks_search.py, test_tasks_read.py
affects: [32-04b, 32-05, 32-06]

tech-stack:
  added: []
  patterns:
    - "Zeitfeld über isoformat ohne Umrechnung; schwebend bekommt <feld>_floating"
    - "Variante V-B: Vorfilter im Modus open, zweiter REPORT derselben Liste nur bei fehlender Elternaufgabe, beide unter dem Budget der Liste"
    - "Nebenabfragen von tasks_read mit eigenem Budget; Ausfall ergibt einen Satz statt eines Fehlers"

key-files:
  created:
    - src/mcp_connector/tools/tasks.py
    - tests/unit/test_tasks_time_matrix.py
    - tests/unit/test_tasks_search.py
    - tests/unit/test_tasks_read.py
  modified:
    - vulture_whitelist.py

key-decisions:
  - "COMPLETED mit TZID: icalendar liest es ohne Zone; die Wandzeit bekommt die genannte IANA-Zone per replace (nie Umrechnung), sonst bliebe sie fälschlich schwebend"
  - "Zweiter REPORT im Modus open teilt das Zeitbudget der Liste; scheitert er, ist die Liste degraded"
  - "tasks_read: ein Objekt ohne VTODO antwortet wie eine unbekannte Id (REASON_UNKNOWN_ID)"
  - "Eingaben des Aufrufers werden in Meldungen nur ohne _shared_by_ wiederholt, sonst steht 'that name'"
  - "subtasks_total steht nur, wenn der Deckel greift"

patterns-established:
  - "Vorübergehende vulture-Einträge search_tasks und read_task mit Kommentar 'until reg_tasks.py registers the bundle (32-05)'"

requirements-completed: []  # TASK-02 und TASK-04 im Code erfüllt; abgehakt erst mit der Registrierung (32-05)

duration: ca. 75min
completed: 2026-11-13
---

# Phase 32 Plan 04: tools/tasks.py lesend Summary

**VTODO-Leser mit benannter Zeitmatrix (schwebend bleibt schwebend und ist gekennzeichnet), `search_tasks` über eigene und geteilte Listen mit Status-, Text- und Fälligkeitsfilter, fester Seite 25, Cursor mit Bereichsbindung, Deckel 500, Budget 1 s je Liste, `degraded` und `skipped`, und `read_task` mit gekappter Beschreibung, Elternbezug und direkten Unteraufgaben unter eigenem Budget von 1 s.**

## Ergebnis je Task

| Task | Ergebnis | Commits |
|---|---|---|
| 1: VTODO-Leser und Zeitmatrix | `_time_field`, `_read_todo`; 15 benannte Matrixtests (DUE, DTSTART, COMPLETED je ganztägig, Zone, UTC, schwebend, ohne Datum) plus Leser-Tests (Status-Regel, CATEGORIES flach und dedupliziert, RELATED-TO einzeln und als Liste samt RELTYPE, RRULE/RDATE, RECURRENCE-ID, ATTACH, ungültig, alle acht Fixtures); 47 Tests | `8b70913` (test, RED), `baa1984` (feat) |
| 2: search_tasks | Status open/completed/all, Vorfilter nur im Modus open, CANCELLED im Connector aussortiert, Elternverweis nach V-B, Textsuche casefold, due_by als Datum oder Zeitpunkt, Sortierung, Blättern 25/25/10, Bereichsbindung q/s/d/l, Deckel mit Notiz, Budget, degraded, skipped, recurring, Listenauflösung, E6; 52 Tests | `48a55df` (test, RED), `23b616a` (feat) |
| 3: read_task | Felder samt Liste, Beschreibung ohne Marker und an einer UTF-8-Grenze gekappt, Ablehnungen vor jedem Request, eine Antwort für jede unbekannte Id, Kinder exakt nachgeprüft und sortiert, Deckel 50, subtasks_unavailable, Elternbezug mit found false und parent_unavailable; 34 Tests | `77b7565` (test, RED), `41e0f69` (feat) |

## Werte der Konstanten

| Konstante | Wert | Herkunft |
|---|---|---|
| `PAGE_SIZE` | 25 | D-32-08 |
| `PER_LIST_TIMEOUT` | 1.0 s | `MESSWERT per_list_timeout_s=1` (32-02, 2026-11-13) |
| `SUBTASK_TIMEOUT` | 1.0 s | `MESSWERT subtask_timeout_s=1` (32-02, 2026-11-13) |
| `MAX_RESULTS` | 500 | `MESSWERT max_results=500 bestaetigt` (32-02, 2026-11-13) |
| `MAX_SUBTASKS` | 50 | Entscheidung der Planung |
| `MAX_DESCRIPTION_BYTES` | 4096 | Entscheidung der Planung |
| `SEARCH_CAP_NOTE` | `result window capped at 500 tasks; narrow with query, list or due_by` | Stil `files.py` |

Jede der drei gemessenen Konstanten trägt im Code ihre Messzeile samt Datum; `test_limit_policy_constants_are_the_measured_values` pinnt Wert und Zeile.

## Antwortform

`search_tasks(clients, *, query=None, status="open", due_by=None, list_name=None, cursor=None)`, Beispiel ohne echte Kennungen:

```json
{
  "tasks": [
    {"id": "task:projekte:a1b2.ics", "summary": "Angebot prüfen", "status": "open",
     "due": "2026-11-20", "priority": 1, "tags": ["kunde"],
     "list": {"name": "projekte", "shared": false, "writable": true}},
    {"id": "task:s0123456789abcdef:c3d4.ics", "summary": "Folien", "status": "in_progress",
     "due": "2026-11-21T09:00:00", "due_floating": true,
     "list": {"name": "Team", "shared": true, "writable": false},
     "parent": {"id": "task:s0123456789abcdef:e5f6.ics", "summary": "Vortrag"}},
    {"id": "task:projekte:g7h8.ics", "summary": "Wochenbericht", "status": "open",
     "list": {"name": "projekte", "shared": false, "writable": true},
     "parent": {"found": false}, "recurring": true}
  ],
  "truncated": true,
  "next": "<cursor>",
  "degraded": [{"list": "Archiv", "reason": "The task list did not answer within 1 second."}],
  "skipped": 1
}
```

Am Deckel statt `next`: `"note": "result window capped at 500 tasks; narrow with query, list or due_by"`. Konto ohne Aufgabenliste: `{"tasks": [], "hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on."}`. Alle Listen ausgefallen: `ToolError "None of the task lists could be read."`, Gründe im Hinweis.

`read_task(clients, *, task_id)`, Beispiel:

```json
{
  "id": "task:projekte:e5f6.ics", "summary": "Vortrag",
  "description": "Gliederung ...", "description_truncated": true,
  "status": "open", "due": "2026-11-25T14:00:00+01:00", "start": "2026-11-18",
  "priority": 2, "tags": ["konferenz"],
  "list": {"name": "projekte", "shared": false, "writable": true},
  "subtasks": [
    {"id": "task:projekte:c3d4.ics", "summary": "Folien", "status": "in_progress"},
    {"id": "task:projekte:i9j0.ics", "summary": "Raum buchen", "status": "completed"}
  ]
}
```

Weitere Felder je nach Objekt: `completed` (und `completed_floating`), `recurring`, `parent` (`{"id", "summary"}` oder `{"found": false}`) bzw. `parent_unavailable`, `subtasks_truncated` mit `subtasks_total`, statt `subtasks` der Satz `subtasks_unavailable` ("The subtasks could not be read within 1 second." oder "The subtasks could not be read."). Unbekannte Id, Deck-Liste, Papierkorb, Abo, 404 und Objekt ohne VTODO: `"Nextcloud does not know the task '...'."` mit `REASON_UNKNOWN_ID`; eine Id anderer Form: `REASON_GUARD_TRIPPED` vor jedem Request.

## Gates (32-RULES.md Abschnitt 3, Stand 41e0f69 und gleich auf 7c5892a)

- pytest unit+contract: 6238 passed, 35 skipped, Exit 0
- check_tool_budget: `tools/list: 16222 bytes, 24 tools, budget 18000`, Exit 0 (unverändert, kein Werkzeug registriert)
- ruff check: All checks passed; ruff format --check: 387 files already formatted
- pyright (latest): 0 errors, 0 warnings, 0 informations
- vulture: Exit 0

Verlauf pytest: 6105 (Stand 32-03) auf 6152 (Task 1, +47), 6204 (Task 2, +52), 6238 (Task 3, +34), je 35 skipped.

## TASK-01-Beweis

- Positivkontrolle: Basis `b40f7623a5111b95a3fe3cf6e5295c4965ca7056` ist 40 Hex und Vorfahr von HEAD.
- `git diff "$B" -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py` leer (0 Zeilen); `git diff "$B" -- src/mcp_connector/tools/calendar.py` leer; Gegentreffer im selben Lauf: `git diff "$B" -- src/mcp_connector/tools/tasks.py | grep -c "def search_tasks"` = 1.
- `tools/tasks.py` enthält weder `_value_of` noch `parse_ics`, `_ok_props`, `parse_calendar_home` oder `astimezone` (grep ohne Treffer, auch in Kommentaren und Docstrings). Aus `tools/calendar.py` wird nur das öffentliche `parse_instant` genutzt; `test_module_boundaries` grün.

## TDD Gate Compliance

- Task 1 RED `8b70913`: rot nur `tests/unit/test_tasks_time_matrix.py` (Sammelfehler, Modul `tools/tasks.py` fehlt; mit `--continue-on-collection-errors` 6105 passed, 35 skipped), pyright 1 Fehler nur in dieser Datei, ruff, format, vulture grün. GREEN `baa1984`: alles grün.
- Task 2 RED `48a55df`: rot nur `tests/unit/test_tasks_search.py` (52 failed, `search_tasks` fehlt), pyright 48 Fehler nur in dieser Datei, ruff, format, vulture grün; alle übrigen Tests unverändert seit dem grünen Lauf auf `baa1984`. GREEN `23b616a`: alles grün.
- Task 3 RED `77b7565`: rot nur `tests/unit/test_tasks_read.py` (34 failed, `read_task` fehlt), pyright 27 Fehler nur in dieser Datei, ruff, format, vulture grün. GREEN `41e0f69`: alles grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] COMPLETED mit TZID kam schwebend heraus**
- **Found during:** Task 1 (GREEN)
- **Issue:** icalendar parst `COMPLETED;TZID=Europe/Berlin:...` als Zeit ohne Zone; die Matrixzeile "mit Zone behält die Zone" war rot, und die Zeit hätte fälschlich `completed_floating` getragen.
- **Fix:** `_with_named_zone`: trägt der Wert einen `TZID`-Parameter und keine Zone, bekommt die unveränderte Wandzeit die IANA-Zone per `replace` (keine Umrechnung); unbekannter Name lässt den Wert stehen.
- **Files modified:** src/mcp_connector/tools/tasks.py
- **Commit:** `baa1984`

**2. [Rule 3 - Blocking] vorübergehende vulture-Einträge zwischen den Tasks**
- **Found during:** Task 1 und Task 2
- **Issue:** `_read_todo` hatte nach Task 1 nur Testaufrufer, `SUBTASK_TIMEOUT` nach Task 2 noch keinen Nutzer; vulture wäre rot gewesen.
- **Fix:** `_read_todo` (Task 1 bis 2) und `SUBTASK_TIMEOUT` (Task 2 bis 3) kurz in der Liste, je mit ihrem Aufrufer wieder entfernt. Die Client-Einträge aus 32-03 `encode_task`, `discover_task_lists`, `build_todo_query`, `query_todos` (Task 2) und `build_related_query`, `get_todo` (Task 3) gingen mit ihrem Aufrufer; neu bis 32-05: `search_tasks`, `read_task`. `TASK_WORDING` bleibt bis 32-04b.
- **Files modified:** vulture_whitelist.py
- **Commits:** `baa1984`, `23b616a`, `41e0f69`

**3. [Rule 1 - Bug] pyright-Typfehler im Fan-out von read_task**
- **Found during:** Task 3 (Gates vor dem feat-Commit)
- **Issue:** eine Liste aus zwei Koroutinen mit verschiedenem Rückgabetyp.
- **Fix:** zwei getrennte `asyncio.gather`-Aufrufe je nach vorhandenem Elternbezug; Verhalten gleich, vor dem Commit behoben.
- **Commit:** `41e0f69`

**4. [Rule 1 - Bug] Nicht-ASCII-Zeichen in einer Testdatei**
- **Found during:** Abschlussprüfung
- **Issue:** In `test_tasks_read.py` stand im Kappungstest ein wörtliches Umlautzeichen statt der Escape-Form; Code bleibt nach 32-RULES Abschnitt 9 ASCII.
- **Fix:** Escape-Form (Backslash, u00e4) statt des Zeichens, Verhalten gleich, Gates davor grün (6238 passed, 35 skipped).
- **Commit:** `7c5892a`

### Andere Abweichungen

- `nextcloud/capabilities.py` (in 32-PATTERNS.md unter 32-04 genannt) bleibt unberührt: der Plan listet die Datei nicht, und 32-02 hat `erkennung=keine` entschieden.
- Hilfsfunktionen der Testdateien (Multi-Status-Bau) stehen in `test_tasks_search.py` und `test_tasks_read.py` je einzeln, kein gemeinsames Hilfsmodul außerhalb der Dateiliste.

## Known Stubs

Keine. `search_tasks` und `read_task` haben bis 32-05 keinen Aufrufer im Produktcode (vulture-Einträge oben), so im Plan vorgesehen.

## Threat Flags

Keine neuen Flächen über das Bedrohungsmodell hinaus: kein neuer Endpunkt, nur REPORT und GET auf Sammlungen der Discovery. T-32-04-01 bis T-32-04-05 umgesetzt (without_marks auf Titel, Beschreibung, Tags, Listenname; Deck-Präfix vor jeder Anfrage abgelehnt; Antworten nur aus TaskList.name und key, Tests durchsuchen die serialisierte Antwort nach `bob`, `Bob Builder`, `carol`, `Carol Owner` und `_shared_by_`; Budgets und Deckel; Cursor über paging mit Bereichsbindung).

## Hinweise für 32-04b und 32-05

- `_resolve_list(lists, wanted)` löst Schlüssel (bei eigenen Listen die URI) oder Namen casefold auf; Mehrdeutigkeit nennt Name, Schlüssel und geteilt/eigen. Für das Schreiben fehlt noch die Regel "genau eine eigene beschreibbare Liste" (E4).
- `read_task` ist der Leser für `fetch` (32-06); er braucht nur `clients` und die Id.
- `NO_LIST_HINT` nennt die Tasks-App; `tasks_create` braucht einen eigenen Fehler mit Ausweg (E6).

## Self-Check: PASSED

Vier Dateien vorhanden (tools/tasks.py, test_tasks_time_matrix.py, test_tasks_search.py, test_tasks_read.py), alle sieben Commits (8b70913, baa1984, 48a55df, 23b616a, 77b7565, 41e0f69, 7c5892a) im Verlauf, keiner mit Trailer, kein Push.

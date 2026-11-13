---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 04b
subsystem: tasks-tools
tags: [caldav, vtodo, anlegen, zielwahl, geteilte-listen, injektion, datenschutz]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-02 (ENTSCHEID erkennung=keine), 32-03 (clients/tasks.py, TASK_WORDING, caldav.put_new_object), 32-04 (tools/tasks.py lesend, _resolve_list, _read_todo, _time_field)
provides:
  - create_task in tools/tasks.py mit Prüfungen vor jedem Request, Zielwahl nach E4 und D-32-16, VTODO-Bau über icalendar, create-only-Schreiben und Rücklesen
  - tests/unit/test_tasks_create.py, tests/unit/test_tasks_app_hint.py, drei Korpusfälle in tests/unit/test_injection_corpus.py
affects: [32-05, 32-06, 32-07]

tech-stack:
  added: []
  patterns:
    - "Zielwahl _pick_target(lists, wanted, parent_list): benannte Liste gewinnt, sonst Liste einer eigenen Elternaufgabe, sonst genau eine eigene beschreibbare Liste; nie personal, nie 'genau eine Liste insgesamt'"
    - "Zeit beim Schreiben: Datum bleibt Datum (VALUE=DATE), Zeit mit Zone ohne timezone in UTC, mit timezone in dieser IANA-Zone samt VTIMEZONE aus zoneinfo"
    - "Rücklesen: confirmed nur bei lesbarem Objekt mit gleicher UID; jeder Fehler ergibt confirmed false, nie einen Fehlschlag"

key-files:
  created:
    - tests/unit/test_tasks_create.py
    - tests/unit/test_tasks_app_hint.py
  modified:
    - src/mcp_connector/tools/tasks.py
    - tests/unit/test_injection_corpus.py
    - vulture_whitelist.py

key-decisions:
  - "D-32-10 nach ENTSCHEID erkennung=keine (32-02) und Owner-Bestätigung vom 13.11.2026 ('Ok'): keine Erkennung der Tasks-App, kein Hinweis; capabilities.py bleibt unberührt"
  - "Ohne list und mit mehr als einer oder keiner eigenen beschreibbaren Liste: Fehler mit allen beschreibbaren Listen (geteilte mit Schlüssel); ohne jede beschreibbare Liste: Fehler mit Ausweg über die Tasks-App"
  - "Tags werden vor dem Schreiben getrimmt; leere und casefold-gleiche verworfen, Reihenfolge der ersten Nennung"
  - "Das Ziel wird vor dem GET der Elternaufgabe gewählt: D-32-16 und 'andere Liste' kosten keinen Request"

patterns-established:
  - "Vorübergehender vulture-Eintrag create_task bis reg_tasks.py (32-05); TASK_WORDING verließ die Liste mit seinem Aufrufer"

requirements-completed: []  # TASK-03, TASK-05, TASK-06 und der Korpusteil von TASK-07 im Code erfüllt; abgehakt erst mit der Registrierung (32-05)

duration: ca. 30min
completed: 2026-11-13
---

# Phase 32 Plan 04b: tasks_create, Zielwahl, Tasks-App-Hinweis und Injektionskorpus Summary

**`create_task` schreibt eine Aufgabe genau dorthin, wo der Assistent es ausdrücklich gesagt hat, oder gar nicht: alle Eingaben vor dem ersten Request geprüft, Zielwahl nach E4 und D-32-16, ein VTODO über icalendar, create-only über `caldav.put_new_object` mit `TASK_WORDING`, Rücklesen mit UID-Vergleich; der Hinweis zur Tasks-App entfällt nach dem Messentscheid `erkennung=keine`.**

## Ergebnis je Task

| Task | Ergebnis | Commits |
|---|---|---|
| 1: Erkennung der Tasks-App | Nach `ENTSCHEID erkennung=keine` (32-02) nichts gebaut: kein Feld `tasks_available`, kein `load_tasks_app`, kein `_tasks_app_hint`, kein `require_app("tasks")`. 6 Tests belegen die Abwesenheit (Struktur, keine Antwort mit dem Satz, null OCS-Requests je Route bei E6, Suche und Lesen); 2 weitere für tasks_create kamen mit dem RED von Task 2 | `54ad9dc` (test) |
| 2: create_task | Prüfungen, Zielwahl, VTODO-Bau, Schreiben, Rücklesen, E6; 55 Tests in test_tasks_create.py plus 2 in test_tasks_app_hint.py | `6f4cd33` (test, RED), `a2d51f6` (feat) |
| 3: Injektionskorpus | Drei Fälle aus der geteilten Liste `spike30-b-rw`: Titel und Tags wörtlich nur im Inhaltsfeld, Beschreibung nicht im Treffer; lange Beschreibung in tasks_read nur in `description`, gekappt auf 4096 Bytes, `description_truncated` true, kein Marker; gefälschte Markerfolge im Titel gefiltert | `e18b0fa` (test) |

## Owner-Bestätigung zu D-32-10

Am 13.11.2026 hat der Owner bestätigt, dass der Messentscheid `erkennung=keine` aus 32-02 gilt und der Hinweis auf die fehlende Tasks-App entfällt ("Ok"). Das deckt sich mit der Klausel in D-32-10 "Lässt sich der Zustand der App nicht verlässlich erkennen, entfällt der Hinweis". Gebauter Erkennungsweg: **keiner**. `nextcloud/capabilities.py` und `tests/unit/test_ocs_capabilities.py` bleiben unverändert (Diff seit 32-04 leer); die Mail-Tests laufen unverändert grün.

## Signatur und Antwort

```python
async def create_task(
    clients: NcClients,
    *,
    summary: str,
    list_name: str | None = None,
    description: str | None = None,
    due: str | None = None,
    start: str | None = None,
    priority: int | None = None,
    tags: Sequence[str] | None = None,
    timezone: str | None = None,
    parent: str | None = None,
) -> dict[str, Any]
```

Erfolg, Beispiel ohne echte Kennungen:

```json
{"id": "task:projekte:0f8e...c1.ics", "summary": "Angebot",
 "list": {"name": "projekte", "shared": false, "writable": true},
 "created": true, "confirmed": true, "due": "2026-11-20"}
```

`start` steht, wenn gesetzt; Zeiten wie geschrieben (ohne `timezone` in UTC, `+00:00`; mit `timezone` in dieser Zone). Kein Feld `hint`.

## Hinweistexte und Meldungen (englisch)

| Fall | message | hint |
|---|---|---|
| E6 (keine Liste) | `This account has no task list.` | `Create a list in the Nextcloud Tasks app, then try again.` |
| Tasks-App aus | entfällt (erkennung=keine) | entfällt |
| zwei oder mehr eigene beschreibbare Listen | `This account has more than one task list to write to, so list has to be named.` | `Name the list with list=<name>. Writable task lists: ...` (geteilte als `<name> (shared, key s...)`) |
| nur geteilte beschreibbare Listen | `This account has no own task list to write to, and a shared list is only written to when it is named.` | wie oben |
| keine beschreibbare Liste | `None of the task lists of this account can be written to.` | Ausweg Tasks-App |
| D-32-16 | `The parent task lives in a shared list, and a shared list is only written to when it is named.` | `To create the subtask there, name that list with list='<name>'.` |
| parent und list verschieden | `The parent task lives in another list.` | Ausweg list weglassen oder anderen parent |
| nur lesbare Liste benannt | `The task list '<name>' is read only for this account.` | beschreibbare Listen |
| timezone ohne Zeitangabe | `timezone only applies to a due or start with a time.` | |
| Server 403/404/412 | Wortlaut `TASK_WORDING` aus 32-03 mit Listenname als label (404: "was not found or does not allow writing") | |

Jede Ablehnung vor dem Request trägt `REASON_GUARD_TRIPPED`; eine unbekannte oder Deck-Elternaufgabe antwortet wie `read_task` mit `REASON_UNKNOWN_ID`. Keine Meldung trägt eine URI mit `_shared_by_` oder den Besitzer.

## Gates (32-RULES.md Abschnitt 3)

| Stand | pytest unit+contract | budget | ruff | format | pyright | vulture |
|---|---|---|---|---|---|---|
| `54ad9dc` (Task 1) | 6244 passed, 35 skipped | Exit 0 | grün | 388 Dateien | 0/0/0 | Exit 0 |
| `a2d51f6` (Task 2) | 6301 passed, 35 skipped | Exit 0 | grün | 389 Dateien | 0/0/0 | Exit 0 |
| `e18b0fa` (Task 3, Planende) | 6304 passed, 35 skipped | `tools/list: 16222 bytes, 24 tools, budget 18000`, Exit 0 | grün | 389 Dateien | 0/0/0 | Exit 0 |

Bytegröße von `tasks_create`: noch nicht messbar. Das Werkzeug wird erst in 32-05 registriert; `check_tool_budget.py` misst nur registrierte Werkzeuge und meldet unverändert `tools/list: 16222 bytes, 24 tools, budget 18000`.

`EXPECTED_PUT_CALLS` bleibt 6 (test_no_destructive_calls grün; `grep -rn "\.put(" src/mcp_connector` zählt 6). `tools/tasks.py` enthält weder `_all_day_window` noch `put_event`; geschrieben wird nur über `caldav.put_new_object`.

## TASK-01-Beweis

- Positivkontrolle: Basis `b40f7623a5111b95a3fe3cf6e5295c4965ca7056` ist 40 Hex und Vorfahr von HEAD.
- `git diff "$B" -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py`: 0 Zeilen; `git diff "$B" -- src/mcp_connector/tools/calendar.py src/mcp_connector/server/reg_calendar.py`: 0 Zeilen; Gegentreffer im selben Lauf: `git diff "$B" -- src/mcp_connector/tools/tasks.py | grep -c "def create_task"` = 1.
- `clients/caldav.py` und `capabilities.py` seit 32-04 (`abaa6eb`) unverändert. Das Kalender-Bundle bleibt unverändert.

## TDD Gate Compliance

- Task 1 `54ad9dc`: reiner Test-Commit, grün. Nach `erkennung=keine` gibt es nichts zu bauen; die Tests belegen eine Abwesenheit und können nicht rot sein. Darum kein feat-Commit für Task 1 (siehe Abweichungen).
- Task 2 RED `6f4cd33`: rot nur `tests/unit/test_tasks_create.py` (55 failed) und die zwei neuen Fälle in `tests/unit/test_tasks_app_hint.py` (`create_task` fehlt; 6 alte Fälle grün); pyright 23 Fehler nur in diesen zwei Dateien; ruff, format, vulture grün. GREEN `a2d51f6`: alles grün.
- Task 3: reiner Test-Commit; die drei Korpusfälle sind sofort grün, weil `search_tasks` und `read_task` (32-04) die Marker schon filtern und kappen. Das ist der Zweck des Korpus (Beleg des bestehenden Vertrags), kein übersprungenes RED.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Escape-Test zählte Teilzeichenketten statt Komponenten**
- **Found during:** Task 2 (GREEN)
- **Issue:** Der RED-Test prüfte `body.count("BEGIN:VTODO") == 1`; der korrekt escapte Titel `x\nEND:VTODO\nBEGIN:VTODO...` enthält die Zeichenfolge als Text auf derselben Inhaltszeile. Der Test war falsch, nicht der Code.
- **Fix:** Test zählt ganze Zeilen nach `\r\n` und prüft per icalendar, dass genau `VCALENDAR` und `VTODO` entstehen.
- **Files modified:** tests/unit/test_tasks_create.py
- **Commit:** `a2d51f6`

**2. [Rule 3 - Blocking] vulture-Liste**
- `TASK_WORDING` verließ die Liste mit seinem Aufrufer `create_task`; `create_task` steht vorübergehend darin bis 32-05.
- **Commit:** `a2d51f6`

### Andere Abweichungen

- Task 1 ohne feat-Commit und ohne Änderung an `capabilities.py`, `test_ocs_capabilities.py` und `tools/tasks.py`: der Plan sieht diesen Zweig für `erkennung=keine` ausdrücklich vor ("keine Erkennung bauen, kein Hinweis, ein Test belegt die Abwesenheit"). Der geplante Commit-Titel "feat(32-04b): say once when the Tasks app is off" entfällt.
- Die zwei tasks_create-Fälle der Abwesenheit stehen in `test_tasks_app_hint.py` und kamen mit dem RED-Commit von Task 2, weil `create_task` vorher nicht existierte.
- Ein `summary` mit `\r\n` wird von icalendar als `\n` escaped (CR fällt weg); die Antwort wiederholt den Titel wie übergeben. Kein Sicherheitsthema (eine einzige VTODO-Komponente belegt), nur festgehalten.

## Known Stubs

Keine. `create_task` hat bis 32-05 keinen Aufrufer im Produktcode (vulture-Eintrag), so vorgesehen.

## Threat Flags

Keine neuen Flächen über das Bedrohungsmodell hinaus. T-32-04b-01 (Zielwahl, D-32-16, writable vor dem Request, 403/404 als letzte Instanz), T-32-04b-02 (`If-None-Match: *`, frische UUID), T-32-04b-03 (icalendar, eine VTODO-Komponente belegt), T-32-04b-04 (Deck-URI als list und als parent: unbekannt, kein Request an Deck), T-32-04b-05 (Korpus) umgesetzt; T-32-04b-06 entfällt mangels Erkennung (null OCS-Requests belegt).

## Self-Check: PASSED

Fünf Dateien vorhanden (tools/tasks.py, test_tasks_create.py, test_tasks_app_hint.py, test_injection_corpus.py, vulture_whitelist.py), alle vier Commits (54ad9dc, 6f4cd33, a2d51f6, e18b0fa) im Verlauf, keiner mit Trailer oder closes/fixes/resolves, kein Push.

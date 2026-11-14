---
phase: 33-aufgaben-aendern
plan: 08
subsystem: tasks-move
tags: [tasks, tasks_move, etag, if-match, overwrite-f, kette, schalter, budget]
requires: ["33-02", "33-03", "33-05", "33-06", "33-07"]
provides:
  - "tools/tasks.move_task(clients, *, task_id, etag, list_name) -> dict"
  - "Werkzeug tasks_move hinter config.tasks_update_enabled(), MODIFY_EXISTING, @graceful, 611 Bytes"
  - "Allowlist tasks_move: {etag, list, task_id}"
  - "tools/tasks._list_matches (aus _resolve_list herausgelöst) und _read_for_change mit optionaler Discovery des Aufrufers"
affects: [33-09, 33-10]
tech-stack:
  added: []
  patterns: ["Ziel nur aus der Discovery (_resolve_list), nie positionsabhängig", "Vorabprüfung der Zielliste per REPORT auf Objektname und UID", "Kette aus 33-05 mit move_todo als Schreibfunktion"]
key-files:
  created:
    - tests/unit/test_tasks_move.py
    - .planning/phases/33-aufgaben-aendern/33-08-SUMMARY.md
  modified:
    - src/mcp_connector/tools/tasks.py
    - src/mcp_connector/server/reg_tasks.py
    - src/mcp_connector/audit/allowlist.py
    - scripts/check_tool_budget.py
    - vulture_whitelist.py
    - tests/contract/optional_surface.py
    - tests/contract/test_tool_surface.py
    - tests/contract/test_tool_classes.py
    - tests/contract/tool_classes.py
    - tests/unit/test_exapp_tasks_update_switch.py
    - README.md
    - README.de.md
    - README.fr.md
decisions:
  - "Reihenfolge der Prüfungen: Form (Id, Deck, ETag, Ziel) vor jeder Anfrage; nach der Discovery Quelle unbekannt, Ziel unbekannt, mehrdeutig, nur lesbar; dann GET der Quelle (_read_for_change); Ziel gleich Quelle erst nach dem GET (Erfolg nur für eine Aufgabe, die es mit dieser ETag gibt)"
  - "Unbekanntes Ziel: Hinweis nennt nur beschreibbare Aufgabenlisten (_writable_hint), ein reiner Terminkalender ist unbekannt"
  - "Antwort bei Erfolg: id (neu), previous_id, list (Ziel), moved (neue Ids der Nachfahren), skipped, etag nur wenn der GET sie gesendet hat, sonst note"
  - "Antwort bei Stopp: id (alt), list, moved, failed, reason, message; 412 heißt changed_or_name_taken, 204 heißt replaced (lauter Fehler), 409 uid_conflict; bei ungewissem Ausgang nennt die Meldung die mögliche neue Id"
  - "Budget 26000 (Messung 22198 mit allen Schaltern an plus 15 Prozent, auf 500 aufgerundet)"
metrics:
  completed: 2026-11-14
  tasks: 2
---

# Phase 33 Plan 08: tasks_move Summary

`tasks_move(task_id, etag, list)` verschiebt eine Aufgabe samt Nachfahren in eine ausdrücklich genannte, beschreibbare Aufgabenliste: Ziel nur aus der Discovery, Vorabprüfung der Zielliste auf Objektnamen und UIDs, dann die Kette aus 33-05 mit `move_todo` (Nachfahren in Nachordnung, Elternaufgabe zuletzt, je `Overwrite: F` und `If-Match`), Stopp beim ersten Fehler mit den neuen Ids des schon Verschobenen; registriert nur bei eingeschaltetem `NC_MCP_TASKS_UPDATE`.

## Commits

| Teil | Schritt | Commit | Inhalt |
|------|---------|--------|--------|
| 1 | RED | df493ce | test(33-08): tasks_move behaviour |
| 1 | GREEN | 59eed3a | feat(33-08): move a task with its subtasks into a named list |
| 2 | RED | 0e3e205 | test(33-08): tasks_move in the surface gates |
| 2 | GREEN | 033c2fc | feat(33-08): register tasks_move behind the tasks_update switch |

Alle als `street1983nk <k.cherif@outlook.de>`, ohne Trailer, ohne closes-Wörter, nur lokal, kein Push. STATE, ROADMAP und REQUIREMENTS nicht angefasst (Vorgabe der Hauptsitzung).

### Rote Tests der RED-Commits

- df493ce: 54 failed, alle in `tests/unit/test_tasks_move.py` (`move_task` fehlt).
- 0e3e205: 8 failed: `test_tool_classes.py` (4), `test_tool_surface.py` (1), `test_exapp_tasks_update_switch.py` (3); alle übrigen grün.

## Werkzeug und Budget

- Schema `tasks_move`: **611 Bytes** (Decke 1400, Erwartung um 560).
- Budgetzeilen wörtlich:

```
tools/list with every switch on: 22198 bytes, 31 tools, budget 26000
  tasks_create: 1380 bytes
  files_upload: 1377 bytes
  tasks_update: 1324 bytes
  mail_browse: 1237 bytes
  calendar_create_event: 1165 bytes
control, standard state: 18770 bytes, 27 tools
```

- Kommentar im Skript: "Measurement 2026-11-14, with tasks_move, every switch on: 22198 bytes, 31 tools", Budget "22198 + 15 percent = 25527.7, rounded up to the next 500 = 26000 bytes". `MAX_TOOL_BYTES` bleibt 1400.
- Beschreibung: "Move a task into the named list; needs its etag from tasks_read. Its subtasks move along. A taken name in the target is never overwritten. Recurring tasks are refused." Parameter `list` Pflicht ("Target list name or key from tasks_search").

## Umgesetzte Entscheide

- TMOD-08 / Pattern 6: Ziel Pflicht, aufgelöst mit `_resolve_list` gegen die Discovery (Name oder Schlüssel, Mehrdeutigkeit mit Schlüsseln, nie URI); eine geteilte Liste ist nur Ziel, wenn ein Name sie eindeutig trifft (gleiche Mehrdeutigkeitsregel wie tasks_create, D-32-18); Schreibrecht für Quelle (`_read_for_change`) und Ziel; Deck-Präfix für Quelle (`_task_key`) und Ziel vor jeder Anfrage; Ziel gleich Quelle: `already: true` ohne REPORT und ohne MOVE.
- Pitfall 2: ein REPORT der Zielliste vor dem ersten MOVE; Objektname (auch eines nicht lesbaren Objekts) oder UID der Aufgabe oder eines Nachfahren schon dort: Ablehnung ohne MOVE, Text nennt Liste und Task-Id, nie URI. Gegenprobe (Mutation, zurückgesetzt): Vorabprüfung aus macht genau die 5 Belegt-Fälle rot.
- D-33-00c, D-33-09: Nachfahren in Nachordnung, Elternaufgabe zuletzt, Nachfahren mit der ETag des REPORTs, die Elternaufgabe mit der des Assistenten; streng nacheinander (`max_open == 1`); kein Zeitbudget um ein MOVE, nur um die beiden REPORTs.
- D-33-10, D-33-11: CHAIN_CAP 50 (genau 50 gehen, 51 abgelehnt), wiederkehrender Nachfahr (auch Enkel) und Nachfahr ohne UTF-8 vor dem ersten MOVE abgelehnt (`check_chain`).
- D-33-00a: wiederkehrende Aufgabe und mehrere VTODO abgelehnt; ETag ungleich: ConflictError ohne REPORT des Ziels.
- 412 nach der Vorabprüfung: Meldung "it changed since it was read or its name is already taken in the target list (412)", Aufforderung neu zu lesen; Gegenprobe (412-Umdeutung aus): 1 Test rot. 204: lauter Fehler `replaced`, nie Erfolg; 409: `uid_conflict`.
- UID, Objektname, Text und ETag bleiben (Teststore prüft Bytes und ETag am Ziel).

## Gates (Endstand, alle Exit 0)

- pytest unit+contract: 8149 passed, 35 skipped (nach Task 1: 8145 passed, 35 skipped)
- Plan-Verify Task 1: test_tasks_move + test_tasks_chain + test_no_destructive_calls: 196 passed
- check_tool_budget: Exit 0 (Zeilen oben)
- ruff check grün; ruff format --check: 403 Dateien formatiert
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0; `grep -q '"tasks_move"' src/mcp_connector/audit/allowlist.py`: Treffer
- MOVE-Gate: weiter genau zwei Zeilen `"MOVE",` unter `src` (Chunk-Montage und `move_todo`), `test_no_destructive_calls.py` grün; `move_task` ruft nur `move_todo`
- TASK-01: SHA-Form und Vorfahr ok, Diff über caldav.py, calendar.py und die vier Kalendertests 0 Zeilen; Gegentreffer tools/tasks.py (1084 Einfügungen gegen die Basis)
- Pitfall 1: keine Teilstrings MOVE/DELETE/COPY/PROPPATCH in tools/tasks.py, reg_tasks.py, allowlist.py; kein U+2013/U+2014 in den berührten Dateien
- Kein Docker gebraucht, kein Container gestartet

## Deviations from Plan

1. [Rule 1, Schnittstelle] Der Test des RED-Commits rief `move_task(..., list=...)`; im GREEN-Commit auf `list_name=` umgestellt, wie `search_tasks` und `create_task` (der Name `list` im Funktionsrumpf würde den eingebauten Typ verdecken). Der Draht-Name bleibt `list` (reg_tasks mit `noqa: A002`).
2. [Rule 1, Wiederverwendung] `_list_matches` aus `_resolve_list` herausgelöst (unbekanntes Ziel nennt die beschreibbaren Listen, Mehrdeutigkeit bleibt bei `_resolve_list`); `_read_for_change` nimmt optional die Discovery des Aufrufers (eine Discovery je Aufruf, Test); `_Stored` trägt die ETag des GET (für die Antwort). tasks_complete und tasks_update unverändert grün.
3. [Rule 2] Zwei Stoppgründe in `_CHAIN_STOPS` ergänzt (`changed_or_name_taken`, `replaced`); 204 wird über den Text `(status 204)` der Client-Meldung erkannt, im selben Stil wie 409 in `_chain_reason`.
4. Bekannte Grenze: der REPORT der Zielliste fragt nur VTODO ab (`build_todo_query`); ein VEVENT gleichen Namens in einer gemischten Liste sieht die Vorabprüfung nicht. Dann antwortet der Server mit 412 auf `Overwrite: F`, die Kette stoppt mit der Meldung "changed or name taken"; überschrieben wird nichts.
5. `tests/contract/tool_classes.py`: Zeilenverweise von tasks_complete und tasks_update auf den aktuellen Stand nachgezogen, tasks_move mit eigenen Verweisen ergänzt.
6. README-Zeilen `tasks_move | modify` in README.md, README.de.md und README.fr.md im selben Commit wie der OPTIONAL_TOOLS-Eintrag (033c2fc). Owner bitte Wortlaut prüfen. Die Bundle-Zeile `tasks: ...` der READMEs nennt die schaltbaren Werkzeuge weiter nicht (wie nach 33-06 und 33-07), Sache von 33-09.

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche über das Threat Model hinaus. T-33-08-01 (Vorab-REPORT, `Overwrite: F` als Literal mit AST-Pin, 204 laut), -02 (writable für Quelle und Ziel aus der Discovery, 404 bleibt als letzte Wand `not_found_or_read_only`), -03 (Deck-Präfix für Quelle und Ziel vor jeder Anfrage), -04 (Ziel Pflicht, `_resolve_list`, Mehrdeutigkeit abgelehnt), -05 (Vorprüfung, Nachordnung, Bericht der verschobenen Ids) umgesetzt.

## Self-Check: PASSED

tests/unit/test_tasks_move.py und diese SUMMARY vorhanden; Commits df493ce, 59eed3a, 0e3e205, 033c2fc im Log; `async def move_task` in tools/tasks.py, `tasks_move` in reg_tasks.py und allowlist.py. Scratchpad-Ordner p33 gelöscht.

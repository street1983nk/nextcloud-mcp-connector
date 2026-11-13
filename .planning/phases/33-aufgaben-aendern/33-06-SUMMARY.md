---
phase: 33-aufgaben-aendern
plan: 06
subsystem: tasks-complete
tags: [tasks, tasks_complete, kette, etag, if-match, schalter, budget]
requires: ["33-02", "33-03", "33-04", "33-05"]
provides:
  - "tools/tasks.complete_task(clients, *, task_id, etag, completed) -> dict"
  - "tools/tasks._crlf: Zeilenenden vor jeder Bearbeitung deterministisch auf CRLF"
  - "Werkzeug tasks_complete hinter config.tasks_update_enabled(), MODIFY_EXISTING, @graceful"
  - "Allowlist tasks_complete: {completed, etag, task_id}"
  - "README-Stufe modify (EN/DE/FR) und LEVELS im README-Tabellen-Test"
affects: [33-07, 33-08, 33-09, 33-10]
tech-stack:
  added: []
  patterns: ["alle neuen Texte vor dem ersten PUT bauen und prüfen", "Kettenlauf aus 33-05 auch für eine einzelne Aufgabe (leere Nachfahrenliste)"]
key-files:
  created:
    - tests/unit/test_tasks_complete.py
    - .planning/phases/33-aufgaben-aendern/33-06-SUMMARY.md
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
  - "Zeilenenden: jeder Text (GET und REPORT) wird vor inspect/apply/verify auf CRLF normalisiert; ein CRLF-Text bleibt Byte für Byte, ein LF-Text wird CRLF (RFC 5545)"
  - "Alle Nutztexte der Kette werden vor dem ersten PUT gebaut und mit ics_edit.verify geprüft; decide liefert nur noch Vorberechnetes, also fällt jede Ablehnung vor dem ersten Schreiben"
  - "Schreibrecht wird direkt nach der Discovery geprüft (vor dem GET), ETag-Vergleich nach dem GET; If-Match geht trotzdem mit"
  - "Wiederöffnen läuft ohne REPORT über run_chain mit leerer Nachfahrenliste (eine Fehlerlehre für beide Richtungen)"
  - "Antwort: id, already, status, list, changed (genannte Aufgabe zuletzt), unchanged, left_alone, skipped, bei Stopp failed/reason/message; etag nur mit ETag-Kopf, sonst note 'read the task again for its new etag'"
  - "Budget 23500 (Messung 20262 mit allen Schaltern an plus 15 Prozent, auf 500 aufgerundet)"
metrics:
  completed: 2026-11-14
  tasks: 2
---

# Phase 33 Plan 06: tasks_complete Summary

`tasks_complete(task_id, etag, completed)` hakt eine Aufgabe ab oder öffnet sie wieder, mit `If-Match` auf die ETag aus `tasks_read`; beim Abhaken laufen alle Nachfahren in Nachordnung zuerst über den Kettenlauf aus 33-05 (erledigte ohne PUT, abgebrochene unberührt und als `left_alone` genannt), beim Wiederöffnen nur die genannte Aufgabe; registriert nur bei eingeschaltetem `NC_MCP_TASKS_UPDATE`.

## Commits

| Task | Schritt | Commit | Inhalt |
|------|---------|--------|--------|
| 1 | RED | bce8cc4 | test(33-06): tasks_complete behaviour |
| 1 | GREEN | 61e2f25 | feat(33-06): complete and reopen a task, subtasks first |
| 2 | RED | b63ac13 | test(33-06): tasks_complete in the surface gates |
| 2 | GREEN | ea25a08 | feat(33-06): register tasks_complete behind the tasks_update switch |

Alle als `street1983nk <k.cherif@outlook.de>` (Autor und Committer), ohne Trailer, ohne closes-Wörter, nur lokal, kein Push.

### Rote Tests der RED-Commits

- bce8cc4: 54 failed, alle in `tests/unit/test_tasks_complete.py` (`AttributeError: ... no attribute 'complete_task'`); pyright: 4 Fehler, alle in dieser Datei.
- b63ac13: 15 failed: test_tool_surface.py (3, darunter der README-Tabellen-Test), test_tool_classes.py (5), test_exapp_tasks_update_switch.py (3), dazu test_audit_surface.py (2) und test_tool_bundles.py (2). Die letzten beiden Dateien sind nicht geändert, sie fallen über die geänderte Hilfsdatei `optional_surface.py` (OPTIONAL_TOOLS nennt tasks_complete, das noch nicht registriert war). pyright und vulture grün.

## Werkzeug und Budget

- Schema `tasks_complete` mit allen Schaltern an: **579 Bytes** (Decke 1400, Erwartung um 600).
- Budgetzeilen wörtlich:

```
tools/list with every switch on: 20262 bytes, 29 tools, budget 23500
  tasks_create: 1380 bytes
  files_upload: 1377 bytes
  mail_browse: 1237 bytes
  calendar_create_event: 1165 bytes
  files_update: 912 bytes
control, standard state: 18770 bytes, 27 tools
```

- Kommentar im Skript: "Measurement 2026-11-14, with tasks_complete, every switch on: 20262 bytes, 29 tools", Budget "20262 + 15 percent = 23301.3, rounded up to the next 500 = 23500 bytes". `MAX_TOOL_BYTES` bleibt 1400.

## Umgesetzte Entscheide

- D-33-00a, D-33-11: wiederkehrende genannte Aufgabe und wiederkehrender Nachfahr abgelehnt vor jedem PUT (genannte Aufgabe: `ics_edit.inspect` plus `_read_todo`; Nachfahren: `check_chain`).
- D-33-03: `dav.normalize_etag` vor jeder Anfrage (leer, `*`, `W/`, Liste abgelehnt), Vergleich mit der ETag des GET, `ConflictError` mit "read the task again with tasks_read"; 412 vom Server ohne zweiten Versuch.
- D-33-05/D-33-06: `ENTSCHEID wiederoeffnen_kinder=bleiben`, `OWNERFRAGE entfaellt`; Wiederöffnen ohne REPORT, ein PUT.
- D-33-08: Felder wie gemessen, ein UTC-Zeitpunkt mit `Z` für COMPLETED, LAST-MODIFIED und DTSTAMP, kein SEQUENCE (Test `-k sequence`: 6 passed); Zielzustand ohne PUT und ohne REPORT, `already: true`.
- D-33-09, D-33-10: Kette mit CHAIN_CAP 50 (51 abgelehnt, 50 geschrieben), Stopp beim ersten Fehler, genannte Aufgabe unverändert.
- D-33-14: `ENTSCHEID cancelled_kette=unberuehrt` (left_alone), `ENTSCHEID cancelled_direkt=abhaken-und-oeffnen`.
- ENTSCHEID etag_nach_veraendertem_text=fehlt: ohne ETag-Kopf kein `etag`, stattdessen `note`.

## Gates (Endstand nach ea25a08)

- pytest unit+contract: 7638 passed, 35 skipped (nach Task 1: 7634 passed, 35 skipped)
- Plan-Verify Task 1: test_tasks_complete + test_tasks_chain + test_ics_edit 1018 passed; `-k sequence` 6 passed
- check_tool_budget: Exit 0 (Zeilen oben)
- ruff check grün; ruff format --check: 401 Dateien formatiert
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0; `grep -q '"tasks_complete"' src/mcp_connector/audit/allowlist.py`: Treffer
- TASK-01: SHA-Form und Vorfahr ok, Diff über caldav.py, calendar.py und die vier Kalendertests 0 Zeilen; Gegentreffer tools/tasks.py (484 Einfügungen gegen die Basis)
- Pitfall 1: keine Teilstrings MOVE/DELETE/COPY/PROPPATCH in tools/tasks.py, reg_tasks.py, allowlist.py; kein U+2013/U+2014 in den berührten Dateien
- Kein Docker gebraucht, kein Container gestartet

## Gegenproben

- Mutation `_crlf` als Identität: genau die zwei LF-Tests rot.
- Mutation Zielzustandsprüfung aus: 6 Tests rot (already-Fälle).
- Annotations-Gate: `test_tasks_complete_with_a_planted_class_turns_the_gate_red` (READ_ONLY, CREATE_ONLY, CREATE_IDEMPOTENT, UPDATE_EXISTING je rot, MODIFY_EXISTING grün).

## Deviations from Plan

1. [Rule 3, Gate-Widerspruch] `test_the_readme_permission_table_matches_the_live_registry` (aus 33-02) verlangt jedes Werkzeug aus OPTIONAL_TOOLS im README, kannte aber die Stufe `modify` erst ab 33-09; ohne Änderung wäre das Gate nur durch Lockern grün geworden. Gelöst durch Verschärfen statt Lockern: `LEVELS` mit `modify`, MODIFY_TOOLS müssen `modify` tragen; dazu je eine Tabellenzeile `tasks_complete | modify` in README.md, README.de.md und README.fr.md (Satz nach 33-09 Task 3: nur mit ETag aus tasks_read, Unteraufgaben zuerst, wiederkehrende abgelehnt, nur mit NC_MCP_TASKS_UPDATE). READMEs nicht in files_modified. Für 33-09: die drei Zeilen und die Stufe stehen; offen bleiben Schalterabschnitt, Changelogs, die Prüfung von README.de/fr und die Gegenprobe. 33-07 und 33-08 brauchen ihre Zeile im selben Commit wie ihren OPTIONAL_TOOLS-Eintrag. Owner bitte Wortlaut der drei Zeilen prüfen.
2. [Rule 1, Testzählung] `test_tool_classes.py`: zwei Tests zählten die Klassen nur gegen die Standard-Registry (13/4/10, TOTAL 27) und erwarteten ohne Schalter-Namen nur den Probe-Eintrag als stale. Mit `tasks_complete` in UNAFFECTED: Literal `CLASSIFIED_OPTIONAL = {"tasks_complete"}`, Zählung `10 + len(CLASSIFIED_OPTIONAL)`. Im RED-Commit übersehen, im GREEN-Commit ea25a08 nachgezogen.
3. [Rule 2, Vorprüfung] Alle Nutztexte (genannte Aufgabe und Nachfahren) werden vor dem ersten PUT gebaut und verifiziert, statt in `decide` während des Laufs; damit fällt auch ein `apply`/`verify`-Fehler eines Nachfahren vor dem ersten Schreiben.
4. [Rule 2, Zeilenenden] Vorgabe der Hauptsitzung umgesetzt: `_crlf` normalisiert jeden Text vor der Bearbeitung auf CRLF, Tests für LF-Eingabe (genannte Aufgabe per GET und Nachfahr per REPORT) und für Byte-Erhalt bei CRLF. **Live-Prüfung für 33-10:** ob der echte REPORT von Nextcloud CRLF als `&#13;` überträgt, ist weiter offen; das Werkzeug ist für beide Fälle robust, ein Rundlauf gegen nc35 sollte zeigen, dass ein CRLF-Objekt nach dem Abhaken einer Elternaufgabe in den Kindern unverändert CRLF trägt.
5. Ein Text, der kein UTF-8 ist, wird beim genannten Objekt abgelehnt. Für Nachfahren dekodiert `chain_entries` (33-05) mit `errors="replace"`; ein ungültiges Byte würde dort als U+FFFD geschrieben. Nicht geändert (33-05-Code, seltener Fall), Hinweis für 33-07/33-08.
6. vulture: entfernt `put_existing_todo`, `apply`, `verify`, `chain_entries`, `descendants_post_order`, `check_chain`, `read_chain_list`, `run_chain`, `as_answer` (Task 1) und `tasks_update_enabled` (Task 2); `complete_task` stand befristet zwischen Task 1 und 2 auf der Liste; `tasks_complete` steht in der Werkzeugliste; `move_todo` bleibt bis 33-08.

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche über das Threat Model hinaus. T-33-06-01 (ETag-Vergleich plus If-Match, 412 ohne Retry), -02 (writable aus der Discovery, 404 als `not_found_or_read_only`), -03 (Deck-Präfix vor jeder Anfrage), -04 (Wiederholung vor dem PUT, auch Nachfahren), -05 (Allowlist nur Parameternamen, @graceful, Audit-Gate mit Schaltern an grün) umgesetzt.

## Self-Check: PASSED

tests/unit/test_tasks_complete.py und diese SUMMARY vorhanden; Commits bce8cc4, 61e2f25, b63ac13, ea25a08 im Log; `async def complete_task` in tools/tasks.py, `tasks_complete` in reg_tasks.py und allowlist.py.

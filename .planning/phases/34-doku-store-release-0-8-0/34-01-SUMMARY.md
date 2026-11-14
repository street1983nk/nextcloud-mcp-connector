---
phase: 34-doku-store-release-0-8-0
plan: 01
subsystem: doku
tags: [doc-05, readme, server-instruction, contract-test]
requires: []
provides:
  - "Wahrheitstest der Schreibzusage gegen die Registry (tests/contract/test_write_promise_truth.py)"
  - "READMEs EN/DE/FR mit Aufgaben-Ausnahmen und Löschgrenze"
  - "Server-Instruktion mit Satz 'Tasks are never deleted.'"
affects: [34-02, 34-03, 34-04, 34-05]
key-files:
  created:
    - tests/contract/test_write_promise_truth.py
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-01-inventar.txt
  modified:
    - README.md
    - README.de.md
    - README.fr.md
    - src/mcp_connector/server/__init__.py
    - tests/contract/test_tool_surface.py
decisions:
  - "Die Menge der ändernden Werkzeuge kommt aus den Annotationen einer frischen Registry (read_only_hint false und destructive_hint true), nicht aus MODIFY_TOOLS"
  - "Der Gate-Satz unter dem Abschnitt nennt beide MOVE-Ausnahmen (private Chunk-Montage und move_todo), weil test_no_destructive_calls.py beide erlaubt"
metrics:
  completed: 2026-11-14
  tasks: 2
  files: 7
---

# Phase 34 Plan 01: Schreibzusage präzisiert (DOC-05) Summary

Die drei READMEs und die Server-Instruktion sagen jetzt genau, was 0.8.0 an Bestehendem ändert (files_update, tasks_complete, tasks_update, tasks_move, je mit Schalter) und dass Aufgaben nie gelöscht werden; ein Contract-Test hält das gegen die Registry mit allen Schaltern an.

## Commits

| Task | Commit | Text |
|------|--------|------|
| 1 (RED) | ccf9a7c | test(34-01): the write promise of the readmes and the instruction against the registry |
| 2 (GREEN) | 557478d | docs(34-01): the write promise names the task exceptions and the delete limit |

## RED-Commit: rote Tests

Nur die neuen Tests in `tests/contract/test_write_promise_truth.py` waren rot (7 failed, 8175 passed, 35 skipped):

- `test_the_delete_limit_names_tasks[README.md|README.de.md|README.fr.md]`
- `test_every_point_denying_moving_names_the_tasks_move_exception[README.md|README.de.md|README.fr.md]`
- `test_the_instruction_says_tasks_are_never_deleted`

Grün im RED-Lauf: Registry-Test A (gemessen: genau 4 von 31 Werkzeugen), Test B je README und die vier Gegenproben.

## Gates (nach Task 2)

- pytest unit+contract: 8182 passed, 35 skipped, Exit 0
- check_tool_budget: 22198 Bytes / 31 Werkzeuge (alle Schalter, Budget 26000), 18770 Bytes / 27 Werkzeuge (Standard), Exit 0, unverändert
- ruff check: grün; ruff format --check: 406 Dateien formatiert
- pyright: 0 errors, 0 warnings
- vulture: Exit 0
- Strich-Prüfung: Positivkontrolle Exit 0, README.md/README.de.md/README.fr.md/server/__init__.py/Testdateien Exit 1
- Diff-Beweis: `git diff --stat $B -- src/` zeigt nur `server/__init__.py` (Gegentreffer 1)
- 16 Inventarzeilen `ERLEDIGT` in raw/34-01-inventar.txt

UMLAUT README.de.md geprueft=3 fehler=0 (bewusst, Assistenten, zuerst: echt)

## Absichtliche Teständerung

`BASE_INSTRUCTION` in `tests/contract/test_tool_surface.py` trägt jetzt zusätzlich `" Tasks are never deleted."`. Keine Lockerung: der Test bleibt ein Vollvergleich je Schalterkombination; die Schaltersätze sind byte-gleich.

## Deviations from Plan

1. Test B (README nennt jedes ändernde Werkzeug mit Schalter) war im RED-Lauf schon grün, weil 33-09 den Aufgaben-Punkt bereits mit allen drei Werkzeugen und `NC_MCP_TASKS_UPDATE` geschrieben hatte. Der Test hält die Aussage weiter; die Gegenprobe (alter Abschnitt ohne `tasks_update`) belegt, dass er greift.
2. Der Gate-Satz nennt zwei MOVE-Ausnahmen statt einer (Plan nannte nur move_todo), weil `test_no_destructive_calls.py` auch das MOVE der privaten Chunk-Montage erlaubt; sonst wäre der Satz falsch.
3. DE und FR: der Überschreib-Punkt ist wie EN gebaut (Plan Punkt 2); dabei fiel der Teilsatz zu Base64-Blöcken beliebiger Gesamtgröße weg, der in EN nicht steht. FR nutzt jetzt durchgehend gerade Apostrophe (vorher fünf typografische im Abschnitt).
4. Die Inventarzeilen der Legende (README.md:60, README.de.md:68, README.fr.md:71/72) waren schon in 33-09 präzisiert; geprüft und unverändert als ERLEDIGT protokolliert.

## Self-Check: PASSED

- tests/contract/test_write_promise_truth.py vorhanden, raw/34-01-inventar.txt vorhanden
- Commits ccf9a7c und 557478d im Log

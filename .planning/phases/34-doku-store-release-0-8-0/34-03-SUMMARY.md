---
phase: 34-doku-store-release-0-8-0
plan: 03
subsystem: doku
tags: [doc-04, doc-05, threat-model, hardening, privacy, docs-truth-test]
requires: []
provides:
  - "Doku-Wahrheitstest tests/unit/test_docs_tasks_truth.py (Threat-Model, Hardening EN/DE/FR, Privacy)"
  - "Threat-Model mit Aufgaben als Asset, Absatz 'Text from shared task lists' und Löschgrenze"
  - "Hardening EN/DE/FR und Privacy mit NC_MCP_TASKS_UPDATE und der Ausnahme tasks_move"
affects: [34-04, 34-06]
key-files:
  created:
    - tests/unit/test_docs_tasks_truth.py
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-03-inventar.txt
  modified:
    - docs/threat-model.md
    - docs/hardening.md
    - docs/hardening.de.md
    - docs/hardening.fr.md
    - docs/privacy.md
decisions:
  - "Der Absatz zu geteilten Listen nennt kein-ki ausdrücklich als NICHT wirksam: der Tag markiert Dateien und Ordner, keine Aufgabenlisten (im Code geprüft, tools/tasks.py ruft keinen Ausschluss auf)"
  - "Das ETag wird ehrlich als Schutz gegen Überschreiben eines neueren Stands beschrieben, nicht als Schutz gegen die Injektion selbst"
  - "Die Absatzprüfung trennt Listenpunkte, damit ein tasks_move im Nachbarpunkt einen pauschalen Satz nicht entschuldigt"
metrics:
  completed: 2026-11-14
  tasks: 2
  files: 7
---

# Phase 34 Plan 03: Sicherheitsdoku nennt die Aufgabenfamilie Summary

Threat-Model, Hardening EN/DE/FR und Privacy nennen jetzt die drei ändernden Aufgabenwerkzeuge hinter `NC_MCP_TASKS_UPDATE`, die einzige Verschiebe-Ausnahme `tasks_move`, das ausgeschlossene Löschen und den Fremdtext geteilter Aufgabenlisten als Injektionsfläche; ein Doku-Wahrheitstest mit Gegenproben aus dem alten Wortlaut hält das.

## Commits

| Task | Commit | Text |
|------|--------|------|
| 1 (RED) | 1934210 | test(34-03): security docs name the task family and its write exception |
| 2 (GREEN) | 72cd4c0 | docs(34-03): threat model, hardening and privacy name the task family |

## RED-Commit: rote Tests

Nur `tests/unit/test_docs_tasks_truth.py` rot (17 failed, 8187 passed, 35 skipped); übrige Gates grün:

- `test_the_threat_model_names_the_task_family[tasks_complete|tasks_update|tasks_move|NC_MCP_TASKS_UPDATE|tasks-evidence.md]`
- `test_the_threat_model_names_shared_task_lists_as_a_way_in`, `test_the_threat_model_keeps_deleting_a_task_as_a_limit`
- `test_no_paragraph_denies_moving_without_the_task_exception[threat-model.md|privacy.md|hardening.md|hardening.de.md|hardening.fr.md]`
- `test_each_hardening_guide_names_the_switch_and_the_move_tool[en|de|fr]`
- `test_the_privacy_page_names_the_modifying_task_tools[NC_MCP_TASKS_UPDATE|tasks_move]`

Grün im RED-Lauf: die fünf Gegenproben (alter Wortlaut EN/DE/FR wird gemeldet, Listenpunkte bleiben getrennt, alter Injektionsabschnitt ohne Absatz zu geteilten Listen).

## Gates (nach Task 2, alle Exit 0)

- pytest unit+contract: 8204 passed, 35 skipped
- check_tool_budget: 22198 Bytes / 31 Werkzeuge (alle Schalter, Budget 26000), 18770 Bytes / 27 Werkzeuge (Standard), unverändert
- ruff check grün; ruff format --check: 407 Dateien formatiert
- pyright: 0 errors, 0 warnings
- vulture: Exit 0
- Strich-Prüfung: Positivkontrolle Exit 0; threat-model.md, hardening.md/.de.md/.fr.md, privacy.md und Testdatei Exit 1
- Diff-Beweis: Basis-Positivkontrolle grün, `git diff --stat $B -- src/` ohne andere Datei als `server/__init__.py` (aus 34-01)
- 15 Inventarzeilen `ERLEDIGT` in raw/34-03-inventar.txt

UMLAUT docs/hardening.de.md geprueft=4 fehler=0 (zuverlässig, stattdessen, lassen, Assistent: echt)

## Audit-Grund `unspecified`

Weder hardening*.md noch privacy.md zählen die Audit-Gründe einzelner Werkzeuge auf (`guard_tripped` kommt nicht vor; privacy.md nennt nur die Gruppen der Token-Austausch-Ablehnungen). Deshalb nur dieser Vermerk: die Ablehnung eines veralteten ETags steht im Audit als `rejected` mit Grund `unspecified` (33-10). Kein Code-Fix.

## Deviations from Plan

1. **kein-ki nicht als Grenze genannt.** Der Plan nannte "Ausschluss kein-ki" als Grenze der Aufgabenänderung. Der Code prüft den Tag bei Aufgaben nicht (keine Ausschlussprüfung in `tools/tasks.py`, kein-ki markiert Dateien und Ordner). Der Absatz sagt deshalb ehrlich, dass kein-ki hier nicht hilft. Bitte vom Owner bestätigen lassen.
2. **Zusätzlich geprüft:** die Absatzprüfung gilt auch für privacy.md, hardening.de.md und hardening.fr.md (Plan: threat-model.md und hardening.md), mit je einer Gegenprobe aus dem alten DE- und FR-Wortlaut.
3. **Neben den Inventarstellen** wurden in threat-model.md Trust boundaries ("a task in a shared list") und die Angreifertabelle A2 ("share folders and task lists") ergänzt, und privacy.md bekam einen eigenen Punkt zu `NC_MCP_TASKS_UPDATE` und dem Fremdtext geteilter Listen.
4. Der Hinweis auf den Contract-Test im threat-model nennt die zweite erlaubte Ausnahme (private Chunk-Montage der Uploads), damit "exactly these exceptions" stimmt.

## Known Stubs

Keine.

## Self-Check: PASSED

- tests/unit/test_docs_tasks_truth.py und raw/34-03-inventar.txt vorhanden
- Commits 1934210 und 72cd4c0 im Log

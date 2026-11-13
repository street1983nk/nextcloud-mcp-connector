---
phase: 33-aufgaben-aendern
plan: 01
subsystem: messung
tags: [tasks, caldav, inventar, freigabe]
requires: []
provides:
  - "scripts/tasks_modify_measure.py (inventory, baseline, snapshot, diff, chain, etag-altered, cleanup, cap)"
  - "33-BASE.txt"
  - "raw/33-01-inventar.txt (A17 auf HEAD mit Planzuordnung)"
  - "raw/33-01-messung.txt mit FREIGABE zustand=option-a"
affects: [33-01b, 33-01c, 33-02, 33-03, 33-09, 33-10]
tech-stack:
  added: []
  patterns: ["Helfer von tasks_spike.py und tasks_measure.py per Dateipfad geladen", "Protokoll nur über write_protocol mit Geheimnisprüfung"]
key-files:
  created:
    - .planning/phases/33-aufgaben-aendern/33-BASE.txt
    - scripts/tasks_modify_measure.py
    - tests/unit/test_tasks_modify_measure.py
    - .planning/phases/33-aufgaben-aendern/raw/33-01-inventar.txt
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt
  modified: []
decisions:
  - "Owner-Freigabe option-a (nc35 und NC 32) am 2026-11-13, gilt für 33-01b, 33-01c und 33-10"
  - "Inventar: 71 statt 62 Phase-33-Fundstellen, Zuwachs aus Phase 31/32; jede Fundstelle genau einem Plan zugeordnet"
metrics:
  completed: 2026-11-13
  tasks: 3
---

# Phase 33 Plan 01: Basis, Messprogramm, Inventar und Owner-Freigabe Summary

Messprogramm `scripts/tasks_modify_measure.py` für M-1 bis M-4 mit 40 grünen Helfertests, Inventar A17 auf HEAD mit vollständiger Planzuordnung und die gemeinsame Owner-Freigabe option-a; keine Instanz angefasst.

## Tasks

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 (RED) | Tests der Helfer `line_diff`, `removal_form`, `chain_objects`, `chain_cap` | 1f8aeaa |
| 1 (GREEN) | 33-BASE.txt, Messprogramm | 3779083 |
| 2 | Inventar A17 auf HEAD mit Planzuordnung | 41ea21c |
| 3 | Owner-Freigabe im Rohprotokoll | bc9a030 |

RED-Commit: alle Tests der neuen Datei scheiterten beim Laden (`FileNotFoundError`, Skript fehlte); sonst nichts rot.

## Ergebnisse

- Basis-SHA: `86358131af91c55d79d743048ceefccdefcf51a6` (docs(33): create phase plan), Positivkontrolle grün.
- Freigabe wörtlich: `FREIGABE zustand=option-a datum=2026-11-13 umfang=nc35+nc32 quelle=owner-antwort-checkpoint-33-01-task-3`
- Inventar wörtlich:
  - `INVENTAR POSITIVKONTROLLE gefunden=6/6 stellen=['EXPECTED_PUT_CALLS', 'FORBIDDEN', 'README-Rechtetabelle', 'threat-model', 'Store-Text', 'Server-Instruktion'] fehlend=keine`
  - `INVENTAR SUMME treffer=665 gate=53 annotation=6 audit=10 kanarie=2 zusage-server=2 zusage-store=3 zusage-doku=47 ungeklaert=0 ausgeschlossen=542`
  - `INVENTAR ZUORDNUNG SUMME phase33=71 33-02=41 33-03=28 33-09=2 34=48 entfaellt=4 ohne_plan=0`
  - `INVENTAR ABWEICHUNG vorher=62 jetzt=71`: 11 neu (u. a. `server/__init__.py:91/92`, sieben Stellen in `test_tool_surface.py`, `test_no_destructive_calls.py:612`, `test_canary.py:99` mit `files_create_folder`), 2 nicht mehr gefunden (alte Fassungen von `MUST_REFUSE` und des `CREATE_TOOLS`-Kommentars).
  - Zahl der Phase-33-Fundstellen: 71.

## Gates (vor dem feat-Commit)

- pytest unit+contract: 6472 passed, 35 skipped
- check_tool_budget: 18770 Bytes, 27 Werkzeuge, Budget 22000
- ruff check, ruff format --check, pyright (0 Fehler), vulture: grün
- `git status --porcelain src` leer

## Deviations from Plan

1. [Rule 2] Zusätzlicher Unterbefehl `cap --max-seconds` (Zeile `CAP chain_cap=...`), damit 33-01c die Regel direkt anwendet und `chain_cap` ohne vulture-Whitelist erreicht ist; `vulture_whitelist.py` blieb unverändert.
2. [Rule 2] Zusätzlicher Unterbefehl `cleanup` (Listen `p3301*` ohne Papierkorb löschen, Papierkorb leeren, Reste zählen) für den Rückbau nach 33-RULES.md Abschnitt 7.
3. [Rule 1] `snapshot` vergleicht GET und REPORT mit LF-Zeilenenden, weil der XML-Parser CRLF in `calendar-data` zu LF macht; Dateien werden byte-genau geschrieben.
4. Zusätzliche Helfer `assign`, `previous_places`, `match_places`, `write_order` mit eigenen Tests (Planzuordnung und Abgleich mit Bericht 7.1).

## Known Stubs / Offen

- `snapshot`, `chain`, `etag-altered`, `baseline`, `cleanup` sind nur typgeprüft; ihr erster Lauf gegen eine Instanz ist 33-01b/33-01c.
- STATE.md und ROADMAP.md sind von diesem Plan nicht fortgeschrieben (Auftrag: nach 33-01 anhalten).

## Self-Check: PASSED

Dateien vorhanden; Commits 1f8aeaa, 3779083, 41ea21c, bc9a030 im Log.

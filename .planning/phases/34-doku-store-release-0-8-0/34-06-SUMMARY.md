---
phase: 34-doku-store-release-0-8-0
plan: 06
subsystem: release
tags: [exapp-14, doc-04, doc-05, version, changelog, inventar]
requires: ["34-02", "34-03", "34-04", "34-05"]
provides:
  - "Version 0.8.0 an allen gekoppelten Stellen (pyproject.toml, __version__, info.xml version und image-tag, uv.lock)"
  - "0.8.0-Block in CHANGELOG.md, CHANGELOG.de.md, CHANGELOG.fr.md (Added 18, Changed 3, Fixed 1 je Sprache)"
  - "Abschlussprotokoll raw/34-06-abschluss.txt: INVENTAR offen=0, Sprachprüfung, GATE-Zeilen"
affects: [34-07, 34-08, 34-09, 34-10]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-06-abschluss.txt
  modified:
    - pyproject.toml
    - src/mcp_connector/__init__.py
    - appinfo/info.xml
    - uv.lock
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md
decisions:
  - "Zwei Commits statt einem: der Zwischenstand Version ohne Changelog-Block ist grün (445 Tests der betroffenen Dateien plus contract), der Endstand lief durch alle Gates"
  - "Das Budget je Aufgabenliste (3 s) steht nicht im Block, weil der Block sonst keine Zeitbudgets nennt (Plan-Regel)"
  - "DE/FR bekommen genau die zwei Linkzeilen [Unreleased] und [0.8.0]; [0.7.3] und [0.7.2] bleiben dort ohne Linkziel wie bisher"
metrics:
  completed: 2026-11-14
  tasks: 2
  files: 8
---

# Phase 34 Plan 06: Version 0.8.0, Changelog und Abschluss Summary

Version 0.8.0 steht an allen fünf gekoppelten Stellen, die drei Changelogs tragen denselben 0.8.0-Block (aus [Unreleased] geschnitten, um Changed ergänzt), das Inventar aus Phase 30 ist mit 48 von 48 Zeilen geschlossen und alle Gates samt Vollsuite und pip-audit sind grün.

## Commits

| Task | Commit | Text |
|------|--------|------|
| 1 | 6907dd3 | docs(34-06): inventory of phase 30 closed and language audit |
| 2 | 4c1694e | release: 0.8.0 |
| 2 | 3008cce | docs(34-06): changelog 0.8.0 in three languages |

## Inventar

INVENTAR gesamt=48 erledigt=48 offen=0 (34-01: 16, 34-03: 15, 34-04: 14, 34-05: 3; keine Doppelten, keine ERLEDIGT ohne ZUORDNUNG).

## Sprachprüfung

- UMLAUT README.de.md geprueft=12 fehler=0
- UMLAUT docs/hardening.de.md geprueft=4 fehler=0
- UMLAUT appinfo/info.xml geprueft=1 fehler=0
- UMLAUT CHANGELOG.de.md geprueft=1 fehler=0 (ganzer 0.8.0-Block zusätzlich gelesen, alles echt)
- FRANZ README.fr.md geprueft=44 fehler=0, docs/hardening.fr.md 14, appinfo/info.xml 5, CHANGELOG.fr.md 15, je fehler=0
- DASH README*, CHANGELOG*, docs/*.md, info.xml: 0 Treffer (Positivkontrolle Exit 0)
- "die ETag"/"der ETag" in CHANGELOG.de.md: 0; Schließwort vor #: 0

## Gates (Endstand, alle Exit 0)

- pytest unit+contract: 8212 passed, 35 skipped
- check_tool_budget: 22198 Bytes / 31 Werkzeuge (Budget 26000), 18770 Bytes / 27 Werkzeuge, unverändert
- ruff check grün; ruff format --check: 407 Dateien
- pyright: 0 errors, 0 warnings
- vulture: Exit 0
- Runbook-Vollsuite `pytest -q -p no:xdist`: 8212 passed, 35 skipped
- pip-audit (uv export --no-dev --extra documents): No known vulnerabilities found
- uv.lock-Diff: nur nextcloud-mcp-connector 0.7.3 -> 0.8.0
- Diff-Beweis src/: nur server/__init__.py und mcp_connector/__init__.py

## Deviations from Plan

1. `scripts/build_store_release.sh 0.8.0` (optional) nicht gelaufen: das Skript signiert mit dem Store-Schlüssel; Signatur gehört zu 34-10 mit eigener Freigabe.
2. Offener Owner-Punkt aus 34-02 bleibt sichtbar: der DE/FR-Block nennt das Schalter-Label übersetzt ("Bestehende Aufgaben ändern erlauben" / « Autoriser la modification des tâches existantes »), die Oberfläche zeigt es nur englisch. Nicht geändert, weil README und Test SWITCH_LABELS dieselbe Form halten.

## Known Stubs

Keine.

## Self-Check: PASSED

- raw/34-06-abschluss.txt vorhanden, CHANGELOG*.md tragen `## [0.8.0]`
- Commits 6907dd3, 4c1694e, 3008cce im Log

---
phase: 34-doku-store-release-0-8-0
plan: 04
subsystem: doku
tags: [doc-04, doc-05, exapp-install, update-only, project-md]
requires: []
provides:
  - "docs/exapp-install.md: Abschnitt 'Write switches' mit beiden Schaltern, Config-Schlüsseln, Formular-Labels und dem belegten occ-Befehl samt --update-only"
  - "faq.md, client-setup.md, conference-demo.md, conference-talk.md auf dem Stand 0.8.0"
  - ".planning/PROJECT.md: Schreibzusage an fünf Stellen präzisiert"
affects: [34-05, 34-06]
key-files:
  created:
    - .planning/phases/34-doku-store-release-0-8-0/raw/34-04-inventar.txt
  modified:
    - docs/exapp-install.md
    - docs/faq.md
    - docs/client-setup.md
    - docs/conference-demo.md
    - docs/conference-talk.md
    - .planning/PROJECT.md
decisions:
  - "Der occ-Befehl steht wörtlich wie in raw/33-10-nc35.txt (Schlüssel tasks_update, --value off --update-only, config:get, disable, enable), ohne Geheimnisse"
  - "Formular-Labels aus exapp/ui/strings.py ('Allow editing existing text files', 'Allow changing existing tasks'), nicht die abweichenden display-name aus info.xml"
  - "Vortragsmaterial: datierte Läufe bleiben, Gegenwartssätze präzisiert, conference-talk.md bekommt einen Absatz zum Stand 0.8.0"
metrics:
  completed: 2026-11-14
  tasks: 2
  files: 7
---

# Phase 34 Plan 04: Schreibschalter mit --update-only und die Aufgaben-Ausnahme in der übrigen Doku Summary

Die Admin-Anleitung erklärt beide Schreibschalter samt dem in 33-10 belegten Fallstrick (ohne `--update-only` bleibt ein vorhandener Wert stillschweigend stehen), die übrigen Inventarstellen in docs/ und PROJECT.md sagen das Ausgelieferte: nichts löscht, auch keine Aufgabe, und außer `tasks_move` verschiebt nichts.

## Commits

| Task | Commit | Text |
|------|--------|------|
| 1 | f02ab4c | docs(34-04): write switches with --update-only and the task exception across docs |
| 2 | b44b6d7 | docs(34-04): the write promise in PROJECT.md says what 0.8.0 ships |

## Gates (vor Commit Task 1, alle Exit 0)

- pytest unit+contract: 8204 passed, 35 skipped (Zähltest IN-04 grün; exapp-install.md nennt 27 und 31 mit Verweis auf `tests/contract/test_tool_surface.py`)
- check_tool_budget: 22198 Bytes / 31 Werkzeuge (alle Schalter, Budget 26000), 18770 Bytes / 27 Werkzeuge (Standard), unverändert
- ruff check grün; ruff format --check: 407 Dateien formatiert
- pyright: 0 errors, 0 warnings
- vulture: Exit 0
- Strich-Prüfung: Positivkontrolle Exit 0; exapp-install.md, faq.md, client-setup.md, conference-demo.md, conference-talk.md und PROJECT.md Exit 1
- Diff-Beweis: kein src/-Diff aus diesem Plan (außer `server/__init__.py` aus 34-01 nichts)
- Task-2-Prüfung: 5 PROJECT-Zeilen, Platzhaltersatz weg, `NC_MCP_TASKS_UPDATE` vorhanden, CLAUDE.md, STATE.md, ROADMAP.md, REQUIREMENTS.md seit der Basis unberührt
- raw/34-04-inventar.txt: 14 ERLEDIGT-Zeilen (9 docs, 5 PROJECT.md) plus `BESTAETIGT docs/n8n-setup.md:40 plan=entfaellt` (bleibt wahr)

UMLAUT .planning/PROJECT.md geprueft=7 fehler=0 (ausgeschlossen 6x, Assistent: echt)

Geheimnisprüfung: das Zitat aus raw/33-10-nc35.txt besteht nur aus dem occ-Befehl und der occ-Antwort `ExApp mcp_connector config tasks_update already exists. Use --update-only flag.`; keine Werte aus Env-Dateien.

## Audit-Grund `unspecified`

docs/exapp-install.md zählt keine Audit-Gründe auf (`guard_tripped` kommt nicht vor). Nur Vermerk: die Ablehnung eines veralteten ETags steht im Audit als `rejected` mit Grund `unspecified` (33-10); kein Code-Fix.

## CLAUDE.md

Der Security-Satz in CLAUDE.md ("keine destruktiven Writes in v1") wird aus PROJECT.md erzeugt und ist hier nicht angefasst; die Hauptsitzung erzeugt ihn bei Bedarf neu.

## Deviations from Plan

1. **exapp-install.md:240** ist ein protokollierter Lauf von 0.1.0 (Instruktion von damals). Die Zeile bleibt wörtlich; darunter steht ein Absatz, welcher Stand das ist und was die Instruktion seit 0.8.0 sagt, mit Verweis auf `tests/contract/test_tool_surface.py`. Die Inventarzeile zeigt deshalb auf den neuen Absatz (neu=288).
2. **Ein Satz ohne Messung:** "A key that was never set is created by the same command without `--update-only`" stützt sich auf den ersten Befehl des Laufs (Zeile 59/60 in raw/33-10-nc35.txt, `set to on`); ob der Schlüssel davor schon existierte, sagt das Protokoll nicht ausdrücklich. Ebenfalls nicht gemessen: `--update-only` auf einem nie gesetzten Schlüssel.
3. client-setup.md: der folgende Satz zum ETag-Grenzfall (eine Sekunde) gilt nur für Dateien und heißt jetzt "the file guard".

## Known Stubs

Keine.

## Self-Check: PASSED

- raw/34-04-inventar.txt vorhanden, docs/exapp-install.md enthält `--update-only` und `NC_MCP_TASKS_UPDATE`
- Commits f02ab4c und b44b6d7 im Log

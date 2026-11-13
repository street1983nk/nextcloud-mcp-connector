---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 08
subsystem: tasks-abnahme-ci
tags: [owner-abnahme, playwright, tasks-app, ci, nextcloud-35, nextcloud-34]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-07 (ganze Kette auf nc35, scripts/tasks_chain_evidence.py, docs/tasks-evidence.md), 32-05b (CI-Schritte mit und ohne Tasks-App), 32-02 (FREIGABE zustand=option-a)
provides:
  - raw/32-08-abnahme.txt (Vorbereitung, Owner-Abnahme, Rückbau, Stopp)
  - raw/32-08-ci.txt (FREIGABE push=ja, CI-Jobs, Zitate der neuen Schritte)
  - docs/tasks-evidence.md mit den Abschnitten Owner acceptance und CI run
affects: [33, 34]

tech-stack:
  added: []
  patterns:
    - "Abnahme-Objekte über die ganze Kette anlegen, Owner prüft die Sicht der Ziel-App gemeinsam per Playwright, danach Rückbau mit Papierkorb-REPORT als Positivkontrolle"
    - "CI-Belege nur aus den neuen Schritten zitieren (gh run view --log, Schritt-Filter, Zeitstempel weg, Secret-Scan vorher)"

key-files:
  created:
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-08-abnahme.txt
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-08-ci.txt
  modified:
    - docs/tasks-evidence.md

key-decisions:
  - "Owner-Abnahme 13.11.2026: abgenommen (Unteraufgabe eingerückt unter der Elternaufgabe, fällig 20.11. ganztägig ohne Folgetag, Start 18.11., Tags, Priorität 3: hoch)"
  - "Owner-Freigabe Push 13.11.2026 (FREIGABE push=ja); gepusht hat die Hauptsitzung per Fast-Forward 7c9445c..dcda6c8, kein Force"
  - "Abnahme-Objekte ohne list in die einzige eigene Liste personal geschrieben, keine eigene Abnahme-Liste angelegt"

requirements-completed: [TASK-05, TASK-07]

duration: ca. 60min
completed: 2026-11-13
---

# Phase 32 Plan 08: Owner-Abnahme in der Tasks-App und CI-Lauf beider Beine Summary

**Der Owner hat am 13.11.2026 gemeinsam per Playwright in der Tasks-App 0.18.1 auf nc35 abgenommen, dass die über die ganze Kette angelegte Unteraufgabe am 20.11.2026 fällig ist (ganztägig, kein Folgetag), am 18.11. beginnt, beide Tags und Priorität 3 trägt und unter ihrer Elternaufgabe steht; CI-Lauf 43453276557 auf dcda6c8 ist in allen fünf Jobs grün, mit 17 passed ohne Tasks-App (Nextcloud 34.0.3) und 17 passed mit Tasks-App 0.18.1 (Nextcloud 35.0.1).**

## Owner-Abnahme (Task 1 und 2)

| | Wert |
|---|---|
| Instanz | nc35 (35.0.0), Tasks-App 0.18.1 für die Abnahme installiert, danach wieder entfernt |
| Anlegen | über die ganze Kette als alice: Elternaufgabe "p3208 Projekt Abnahme", Unteraufgabe "p3208 Teilschritt" mit parent, due 2026-11-20, start 2026-11-18, tags abnahme und p3208, priority 3; 4 KETTE-Zeilen, alle fehler=nein |
| Sicht der App | eingerückt unter der Elternaufgabe; "Beginnt am 18. November 2026", "Fällig am 20. November 2026", ganztägig; Tags; "Priorität 3: hoch"; Liste personal |
| Screenshots | außerhalb des Repos im Scratchpad (`abnahme/`, drei Breiten, hell und dunkel) |
| Ergebnis | `ABNAHME owner=abgenommen datum=2026-11-13` |

**BASELINE alice auf nc35:** vorher calendars=1 objekte=31 geloescht=0 shares=0 abos=0; nach dem Anlegen objekte=33; nach dem DELETE objekte=33 geloescht=2 (Papierkorb, Befund 1 aus 32-07 bestätigt); nach dem Leeren des Papierkorbs objekte=31 geloescht=0, `gleich=ja`. Tasks-App zurück auf `keine` (app:remove, Konfigurationsschlüssel gelöscht, `config:list tasks` leer).

## CI-Lauf (Task 3 und 4)

| Lauf | Commit | Job | Ergebnis |
|---|---|---|---|
| CI 43453276557 | dcda6c8 | unit | success |
| | | image | success |
| | | integration | success |
| | | exapp (Nextcloud 34.0.3, ohne Tasks-App) | success, `17 passed, 1 warning in 16.63s`, `TASKSAPP erwartet=0 occ_app_list=keine passt=ja` |
| | | canary-nc35 (Nextcloud 35.0.1, mit Tasks-App) | success, `  - tasks: 0.18.1`, `TASKSAPP erwartet=1 occ_app_list=0.18.1 passt=ja`, `17 passed, 1 warning in 19.34s` |
| Security scans 43453276506 | dcda6c8 | REUSE, pip-audit, CodeQL (python) | success |

Die Jobs exapp und canary-nc35 tragen seit der Basis nur hinzugefügte Schritte (`git diff "$B" -- .github/workflows/ci.yml` nur Zeilen mit `+`); beide grün heißt, der Bootstrap-Umbau aus 32-01 hat auf 34 und 35 nichts geändert (D-32-13). Die "1 warning" der pytest-Zeile ist die bekannte PytestRemovedIn10Warning aus anyio; der Abschnitt "warnings summary" steht nicht im Protokoll.

## Task Commits

1. **Task 1: Abnahme vorbereiten** - `577635c` (docs)
2. **Task 2: Owner-Abnahme, Rückbau, Stopp** - `7c7d5b8` (docs)
3. **Task 3: Owner-Freigabe Push** - `dcda6c8` (docs, Hauptsitzung)
4. **Task 4: CI-Beleg** - `8941fd9` (docs)

## Gates (32-RULES.md Abschnitt 3)

Vor `8941fd9`, alle Exit 0:
- pytest unit+contract: 6344 passed, 35 skipped
- check_tool_budget: `tools/list: 18747 bytes, 27 tools, budget 22000`
- ruff check: All checks passed; ruff format --check: 392 files already formatted
- pyright (latest): 0 errors, 0 warnings, 0 informations
- vulture: leer

Prüfungen aus dem Plan: Task 1 (`grep -c "^KETTE "` = 4), Task 2 (ABNAHME-Zeile, `docker ps -q --filter name=nc35-` leer) und Task 4 (beide Abschnitte, `CI job=exapp` und `CI job=canary-nc35` mit success) grün.

docs/tasks-evidence.md: alle Zeilen in Codeblöcken wörtlich in einem Rohprotokoll (205 Zeilen, 0 fehlen); kein `bob`, kein U+2013/U+2014. Secret-Scan beider Protokolle gegen .env.nc35 und .env.exapp: Treffer nur auf öffentliche Werte (Kontoname, App-Id, Version, lokale URL).

## Deviations from Plan

**1. Push durch die Hauptsitzung, nicht durch diesen Executor**
- Task 3 (Owner-Frage) und der Push lagen bei der Hauptsitzung; Task 4 hier ohne erneuten Push, nur Auswertung und Beleg.

**2. Zusätzliche KETTE-Zeilen**
- Neben den zwei Anlege-Aufrufen beide Aufgaben per tasks_read zurückgelesen (4 statt 2 KETTE-Zeilen).

**3. Job exapp auf Nextcloud 34.0.3**
- Das Bein ohne Tasks-App läuft im CI auf 34.0.3, nicht auf 35; der Fall ohne Tasks-App auf 35 ruht auf 32-07. Im Beleg unter "Not reproducible or not measured" so benannt.

## Docker-Zustand am Ende

Kein Container läuft. nc35 (nc35-nc, nc35-harp, nc35-caddy, nc_app_mcp_connector) per `docker stop` gestoppt; keine fremden Container angefasst. Token und Hilfsskripte im Scratchpad gelöscht.

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche. Keine Zugangsdaten in Protokoll oder Ausgabe (T-32-08-03); CI-Log nur aus drei Schritten, ohne env-Zeilen, vorher gescannt (T-32-08-02); Push nur nach FREIGABE push=ja, ohne Force (T-32-08-01).

## Offen

Phasen-Verifikation von Phase 32 (gsd-verifier) steht noch aus. Der Commit des CI-Belegs und dieser Abschluss-Commit sind lokal und nicht gepusht.

## Self-Check: PASSED

- Vier Dateien vorhanden; Commits 577635c, 7c7d5b8, dcda6c8, 8941fd9 im Verlauf, Autor street1983nk, ohne Trailer, ohne closes/fixes/resolves; nach dcda6c8 nichts gepusht.

---
phase: 33-aufgaben-aendern
plan: 01b
subsystem: messung
tags: [tasks, caldav, tasks-app, fixtures, cancelled]
requires: ["33-01"]
provides:
  - "ENTSCHEID-Zeilen M-1, M-2, CANCELLED in raw/33-01-messung.txt"
  - "33-01-BROWSER-SCHRITTE.md"
  - "Fixtures cleared_*.ics, cancelled.ics, cancelled_completed.ics mit PROVENANCE"
affects: [33-01c, 33-04, 33-06, 33-07]
tech-stack:
  added: []
  patterns: ["Browser-Sitzung als Checkpoint an die Hauptsitzung (wie 30-02)", "Stände per snapshot, Auswertung per diff"]
key-files:
  created:
    - .planning/phases/33-aufgaben-aendern/33-01-BROWSER-SCHRITTE.md
    - tests/fixtures/tasks_app/cleared_due.ics
    - tests/fixtures/tasks_app/cleared_start.ics
    - tests/fixtures/tasks_app/cleared_description.ics
    - tests/fixtures/tasks_app/cleared_priority.ics
    - tests/fixtures/tasks_app/cleared_tags.ics
    - tests/fixtures/tasks_app/cleared_parent.ics
    - tests/fixtures/tasks_app/cancelled.ics
    - tests/fixtures/tasks_app/cancelled_completed.ics
  modified:
    - .planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt
    - tests/fixtures/tasks_app/PROVENANCE.md
decisions:
  - "wiederoeffnen_kinder=bleiben: die Tasks-App öffnet nur die Elternaufgabe wieder (D-33-05 bestätigt)"
  - "Entfernen: due, start, parent, priority, tags als Zeile weg; description als leere Zeile DESCRIPTION:"
  - "CANCELLED: abgebrochenes Kind bleibt beim Abhaken der Elternaufgabe unberührt; direkt abhaken und wieder öffnen geht (D-33-14 bestätigt)"
metrics:
  completed: 2026-11-13
  tasks: 2
---

# Phase 33 Plan 01b: Verhalten der Tasks-App beim Wiederöffnen, Entfernen und bei abgebrochenen Aufgaben Summary

Tasks 0.18.1 auf nc35 gemessen: Wiederöffnen der Elternaufgabe lässt Kinder erledigt, entfernte Felder verschwinden als Zeile (nur die Beschreibung bleibt als `DESCRIPTION:` stehen), abgebrochene Kinder bleiben beim Abhaken der Elternaufgabe unberührt; acht neue Fixtures mit sha256.

## Tasks

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 (Vorbereitung) | Instanz, Tasks-App 0.18.1, Konto p3301ui, Schrittdatei | 8fbbafb |
| 1 | Auswertung, Zugriffsprotokoll, Rückbau, nc35 gestoppt | 3f2aff6 |
| 2 | ENTSCHEID-Zeilen, Fixtures, PROVENANCE, Fixture-Test auf p3301 erweitert | 881461e |

Die Browser-Schritte fuhr die Hauptsitzung (Checkpoint, Executor ohne Playwright).

## TASKSAPP- und ENTSCHEID-Zeilen wörtlich

- `TASKSAPP nc35 vorher=keine`
- `TASKSAPP nc35 messung=0.18.1`
- `RUECKBAU nc35 tasksapp=wie-vorher vorher=keine nachher=keine`
- `ENTSCHEID wiederoeffnen_kinder=bleiben quelle=M1 (D-33-05 bestätigt, kein Auslöser für 33-01c Task 4)`
- `ENTSCHEID entfernen_due=zeile-weg quelle=M2`
- `ENTSCHEID entfernen_start=zeile-weg quelle=M2`
- `ENTSCHEID entfernen_description=leer quelle=M2 rohzeile=DESCRIPTION:`
- `ENTSCHEID entfernen_parent=zeile-weg quelle=M2`
- `ENTSCHEID entfernen_priority=zeile-weg quelle=M2 (wie D-33-07)`
- `ENTSCHEID entfernen_tags=zeile-weg quelle=M2 (wie D-33-07)`
- `ENTSCHEID pflegefelder_entfernen=DTSTAMP,LAST-MODIFIED`
- `ENTSCHEID cancelled_kette=unberuehrt quelle=CANCELLED kette (wie D-33-14)`
- `ENTSCHEID cancelled_direkt=abhaken-und-oeffnen abhaken=STATUS:COMPLETED,PERCENT-COMPLETE:100,COMPLETED(UTC) oeffnen=STATUS:NEEDS-ACTION,COMPLETED und PERCENT-COMPLETE entfernt pflegefelder=DTSTAMP,LAST-MODIFIED (wie D-33-14)`
- `ABWEICHUNG D-33-05/D-33-07/D-33-14 keine`

Damit kein Auslöser für 33-01c Task 4 aus diesem Plan.

## Weitere Befunde

- M-1 ist mit einem erledigten Kind gemessen, nicht mit zwei: beim Abhaken der Elternaufgabe scheiterte der PUT auf `p3301 kind-1` mit 500 (`SQLSTATE[HY000]: General error: 5 database is locked`), die App schreibt Kinder und Eltern parallel. `kind-2` blieb nach dem Wiederöffnen erledigt; das trägt die Aussage.
- Dasselbe beim Abhaken von `p3301 eltern-ab` (500, einmal wiederholt, dann 204). Zwei Fehlschläge, beide SQLite, wie Phase 30 Abschnitt 3.6.
- Ein wieder geöffneter abgebrochener Eintrag wird `NEEDS-ACTION`, nicht wieder `CANCELLED`.
- Das Schlagwort-Entfernen sind zwei PUTs (je Schlagwort einer).
- Das Kontrollobjekt `p3301 unberuehrt` hat in allen 12 Ständen gleichen sha256 und gleiche ETag, auch nachdem `kind-lösen` auf seine Zeile gezogen wurde.
- BASELINE alice und bob vorher gleich nachher; `p3301ui` gelöscht, Liste ohne Papierkorb entfernt.

## Deviations from Plan

1. [Rule 3] Kein Playwright im Executor: die Browser-Schritte fuhr die Hauptsitzung nach der Schrittdatei; die Stände liefen über das Kommando aus der Schrittdatei.
2. Das Konto hatte nach der ersten Anmeldung die Kalender `personal` (Server) und `aufgaben` (MKCOL der App), entgegen "has no calendars" vor der Anmeldung; mit `user:delete` entfernt.
3. Schritt 3: Tastatureingabe des Fälligkeitsdatums warf in der App `RangeError: Invalid time value`, vor Stand a über den Datumswähler korrigiert.
4. Konto anlegen, Protokoll des Zugriffs und Rückbau über Hilfsskripte im Scratchpad (nicht im Repo), die die Helfer von `tasks_modify_measure.py` laden.
5. Geheimnisprüfung meldet nur Nicht-Geheimnisse: Basis-URL und die Kontonamen der BASELINE-Zeilen.

## Known Stubs

Keine.

6. [Rule 3] `test_every_fixture_of_the_tasks_app_is_read` verlangte den Titelkopf `s30 `; die neuen Fixtures tragen `p3301 `. Erlaubt sind jetzt beide Köpfe, die übrigen Prüfungen (lesbar, gültiger Status) bleiben. Vorher 8 rot, danach grün.

## Gates

- pytest unit+contract: 6480 passed, 35 skipped
- check_tool_budget: 18770 Bytes, 27 Werkzeuge, Budget 22000
- ruff check, ruff format --check, pyright (0 Fehler), vulture: grün
- TASK-01-Diff gegen 33-BASE leer; kein `src/` geändert
- Am Planende läuft kein eigener Container (nc35 gestoppt), kein fremder lief

## Self-Check: PASSED

Commits 8fbbafb, 3f2aff6, 881461e im Log; acht Fixtures, PROVENANCE, Schrittdatei vorhanden; sha256 der Fixtures gleich PROVENANCE.

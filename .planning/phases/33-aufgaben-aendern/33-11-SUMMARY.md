---
phase: 33-aufgaben-aendern
plan: 11
subsystem: tasks
tags: [gap-closure, kaltstart, tasks_search, budget, live-messung]
requires: [33-10]
provides: [kaltstart-messung, degraded-notiz-im-live-fall]
affects: [tests/integration/test_tasks_live.py]
tech-stack:
  added: []
  patterns: [messender httpx-Transport mit Körperzeit, Gegenprobe über gehaltenes REPORT]
key-files:
  created:
    - scripts/tasks_coldstart.py
    - tests/unit/test_tasks_coldstart.py
    - .planning/phases/33-aufgaben-aendern/raw/33-11-kaltstart.txt
    - .planning/phases/33-aufgaben-aendern/33-11-PLAN.md
  modified:
    - tests/integration/test_tasks_live.py
decisions:
  - "PER_LIST_TIMEOUT bleibt 2 s: kaltes Maximum je Liste 0,377 s (Hausregel ergäbe 1 s), das Budget aus 32-10 (2000 offene Aufgaben, 0,831 s) bleibt maßgeblich"
  - "Kein Produkt-Fix: ein reiner Kaltstart lässt die Liste nicht fallen, und ein Ausfall wird ehrlich unter degraded gemeldet"
  - "Der Live-Fall geteilt-namen notiert künftig degraded, damit ein erneuter Ausfall Budget/Fehler von fehlender Discovery unterscheidet"
metrics:
  completed: 2026-11-14
---

# Phase 33 Plan 11: Kaltstart-Befund geteilt-namen Summary

Kaltstart-Messung auf NC 35.0.0 und NC 32.0.15 (je 9 Neustarts, Positivkontrolle und Gegenprobe):
die nur lesbare geteilte Liste wird nach einem Neustart immer gelistet und beantwortet, kalt
höchstens 0,12 s einzeln und 0,38 s bei 7 gleichzeitigen REPORTs; das Budget von 2 s ist nicht die
Ursache eines reinen Kaltstarts, und ein Ausfall wird ehrlich unter `degraded` genannt.

## Messwerte (raw/33-11-kaltstart.txt)

| Instanz | Discovery kalt max | Liste kalt max (einzeln) | 7 parallel max | Aufruf gesamt max | 5xx | ro gelistet / Treffer |
|---|---|---|---|---|---|---|
| nc35 35.0.0.10 | 446 ms | 120 ms (ro), 111 ms (eigen) | 377 ms | 570 ms | 0 | 9/9 gelistet, 6/6 Treffer |
| nc32 32.0.15.1 | 351 ms | 96 ms (ro), 68 ms (eigen) | 283 ms | 449 ms | 0 | 9/9 gelistet, 6/6 Treffer |

- Warm danach: 82 bis 158 ms je Aufruf.
- Positivkontrolle warm: ro-Treffer ja (beide).
- Gegenprobe (REPORT der ro-Liste im Transport 3 s gehalten, Budget 2 s): unabhängige Prüfung meldet
  "ro-Treffer fehlt", Antwort nennt `degraded: p3311-ro = The task list did not answer within 2 seconds.`
  (beide Instanzen). Die Prüfung erkennt also einen Ausfall, und das Produkt verschweigt ihn nicht.
- Hausregel aus dem kalten Maximum: max(1, ceil(2 × 0,377)) = 1 s. Das geltende Budget 2 s
  (32-10: 2000 offene Aufgaben, 0,831 s) liegt darüber und bleibt.

## Antworten

1. **Ursache:** In 18 kalten Zyklen (davon 12 Produktsuchen, 6 mit Produktbudget 2 s) war die ro-Liste
   immer in der Discovery, jede Antwort 207, nie ein 5xx, nie über 0,6 s. Weder Budget noch Discovery
   noch Serverfehler lassen die Liste bei einem reinen Kaltstart fallen. Die Vermutung "Budget bei
   kaltem Server" ist damit für den Kaltstart widerlegt. Lauf 1 von 33-10 unterschied sich in Dingen,
   die nicht freigegeben waren und hier nicht nachgestellt wurden: erster Neustart direkt nach
   `occ app:install tasks`, 7 Listen samt zwei Gruppenfreigaben, knapper Hostspeicher (RAM-Gate
   zuerst rot, Cache geleert). Welcher dieser Faktoren es war, lässt sich aus dem Protokoll von
   33-10 nicht mehr sagen: der Fall notierte `degraded` nicht, und der Hook sieht abgebrochene
   Anfragen nicht. Ein Beleg für eine Ursache in Nextcloud selbst liegt nicht vor; deshalb kein
   Abbruch mit Core-Befund, sondern offen mit Messvorschlag (unten).
2. **Kalte Dauer je Liste:** siehe Tabelle; Maximum 0,377 s (nc35, 7 parallel).
3. **Ehrlichkeit:** Ja. Fällt eine Liste aus (Budget, Netz, Serverfehler), steht sie mit Grund unter
   `degraded`; fallen alle aus, gibt es einen ToolError. Stumm wäre nur eine Liste, die der Server
   in der Discovery gar nicht liefert; das wurde in keinem Zyklus beobachtet, und der Connector kann
   eine nicht gelieferte Liste nicht kennen.

## Änderungen

- `scripts/tasks_coldstart.py` (neu, R6: nicht unter src): messender Transport, Zyklusarten wahr,
  produkt, parallel7, Positivkontrolle, Gegenprobe, Rückbau mit BASELINE.
- `tests/unit/test_tasks_coldstart.py` (neu): reine Helfer des Messprogramms.
- `tests/integration/test_tasks_live.py`: Fall `geteilt-namen` notiert `degraded`, damit ein
  erneuter Ausfall sofort zeigt, ob Budget/Fehler (Liste genannt) oder Discovery (nicht genannt).
- Kein Produktcode geändert, `PER_LIST_TIMEOUT` unverändert 2.0.

## Deviations from Plan

- Task 3 (TDD-Fix) entfällt: die Messung zeigt keinen Fehler im Produkt, der einen Fix verlangt.
  Statt eines RED/GREEN-Paars nur die Diagnose-Notiz im Live-Test.
- Kopf der Impersonation: registrierte Version 0.7.2 statt info.xml 0.7.3 (seit dem Merge f464455),
  damit AppAPI die Registrierung nicht ändert. `tasks_measure.live_preconditions` hätte deshalb
  abgebrochen; das neue Programm prüft "Kopf = registrierte Version".
- nc32 nur mit `nc-mcp-exapp-nc` und `nc-mcp-exapp-caddy` gestartet (wie 32-10), kein lokaler
  ExApp-Prozess nötig (Impersonation über APP_SECRET).

## Offener Vorschlag (braucht Owner-Freigabe)

Wer die Ursache von Lauf 1 genau wissen will: dieselbe Messung mit `occ app:install tasks` und
erstem Neustart danach sowie 7 Listen (2 Gruppenfreigaben), mit Rückbau der Tasks-App. Alternativ
abwarten: tritt es im nächsten Live-Lauf wieder auf, zeigt die neue `degraded`-Notiz die Spur.

## Gates und Rückbau

Siehe Abschnitt Self-Check. BASELINE vorher = nachher für alice, bob, p3202frisch, p3202nie auf
nc35 und nc32; Papierkorb gefunden=0; Listen mit Präfix p3311: 0; Tasks-App unverändert "keine";
kein Container läuft, kein lokaler nc-mcp-exapp-Prozess, Port 23001 frei.

## Commits

- 8eb8ade docs(33-11): plan the cold start check of the first task search
- baf714c test(33-11): probe the first task search after a cold restart per list
- ac2d997 test(33-11): note degraded lists in the live case of shared list names

## Self-Check: PASSED

- pytest unit+contract (`-p no:xdist`): 8165 passed, 35 skipped
- check_tool_budget: grün (Standardzustand 18770 Bytes, 27 Werkzeuge; größtes Schema calendar_create_event 1165 Bytes)
- ruff check, ruff format --check (405 Dateien), pyright (0 Fehler), vulture: grün
- TASK-01-Diff gegen 33-BASE leer (Positivkontrolle Basis ok, Gegentreffer tasks.py 1180 Zeilen)
- Dateien vorhanden: scripts/tasks_coldstart.py, tests/unit/test_tasks_coldstart.py, raw/33-11-kaltstart.txt, 33-11-PLAN.md
- Commits 8eb8ade, baf714c, ac2d997 vorhanden, Autor street1983nk, ohne Trailer; kein Push

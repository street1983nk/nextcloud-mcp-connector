---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 10
subsystem: tasks-bundle
tags: [gap-closure, caldav, vtodo, sharing, groups, recurring, cap, live-proof]
gap_closure: true
requires:
  - phase: 32-09
    provides: shared_out aus oc:invite, clean_subline, Live-Test mit Testkonto p32live<stempel>aus
provides:
  - "Messung Gruppe hinaus und hinein, wiederkehrend, Deckel bei 600 und 2000 offenen Aufgaben (raw/32-10-messung.txt)"
  - "tests/fixtures/caldav_home_group_share.xml mit Regressionstests für Discovery und Zielwahl"
  - "PER_LIST_TIMEOUT 2 s aus der Messung bei 2000 offenen Aufgaben (RED ed22627, fix 0f98fd4)"
  - "Live-Fälle d-32-18-gruppe-*, gruppe-rein-*, d-32-17-gruppe*, wiederkehrend-*, deckel-500, ANZEIGENAME"
  - "Abschnitt Gap closure 32-10 in docs/tasks-evidence.md, Messkommentar 18770 Bytes"
affects: [32-verification, 33, 34]
tech-stack:
  added: []
  patterns:
    - "Gruppenfreigabe erscheint in oc:invite als oc:user mit href auf principals/groups/: dieselbe Regel wie bei Personen"
    - "Zeitbudget je Liste: Messung des ganzen Aufrufs mit angehobenem Budget, Blättern mit dem Produktbudget"
key-files:
  created:
    - tests/fixtures/caldav_home_group_share.xml
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-10-messung.txt
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-10-nc35.txt
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-10-nc32.txt
  modified:
    - scripts/tasks_measure.py
    - tests/unit/test_tasks_measure.py
    - tests/unit/test_tasks_client.py
    - tests/unit/test_tasks_create.py
    - tests/unit/test_tasks_search.py
    - tests/unit/test_tasks_read.py
    - src/mcp_connector/tools/tasks.py
    - tests/integration/test_tasks_live.py
    - docs/tasks-evidence.md
    - scripts/check_tool_budget.py
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-CONTEXT.md
key-decisions:
  - "ENTSCHEID gruppe_hinaus=erkannt: oc:invite trägt die Gruppenfreigabe als oc:user mit href principals/groups/, auf 35 und 32 unter App-Passwort und Impersonation gleich; _shares_itself unverändert"
  - "ENTSCHEID gruppe_rein=geteilt-erkannt: per Gruppe hineingeteilte Liste mit _shared_by_ in der URI und oc:read-only im 2xx-propstat; shared=ja, writable passend, Name ohne Besitzer"
  - "ENTSCHEID gruppe_subline=bereinigt: auf 35 ersetzt clean_subline den Besitzer mit und ohne DUE, auf 32 enthält die subline keinen Besitzer"
  - "ENTSCHEID wiederkehrend=wie-erwartet: app und instanz-erledigt je ein offener Treffer, master-erledigt ein erledigter, immer recurring=true, ohne Expansion"
  - "ENTSCHEID deckel_budget=anheben-auf-2: max 0.831 s je Aufruf bei 2000 offenen Aufgaben, mit 1 s brach auf 35 schon die erste Seite ab; PER_LIST_TIMEOUT 2.0"
requirements-completed: []
metrics:
  completed: 2026-11-13
  duration: "etwa 60 min (17:50 bis 18:50 UTC)"
---

# Phase 32 Plan 10: Gap Closure Gruppe, wiederkehrend, Deckel Summary

**Gruppenfreigaben tragen in beide Richtungen ohne Codeänderung (gemessen und live belegt auf Nextcloud 35 und 32), wiederkehrende Aufgaben verhalten sich live wie geplant, der Deckel 500 hält live; das Zeitbudget je Liste brach bei 2000 offenen Aufgaben und steht jetzt testgetrieben auf 2 s.**

## Ergebnis je Task

| Task | Ergebnis | Commits |
|---|---|---|
| 1 Messung | Schritte gruppe, wieder, deckel auf nc35 und nc32; alle ENTSCHEID-Zeilen; BASELINE gleich, Gruppe vorher und nachher nicht da | b64a27b (RED), 1f7293b, ad389ef |
| 2 Gruppe in der Discovery | Fall A: Fixture und Regressionstests, kein Produktcode | 5b949cb |
| 3 Wiederkehrend und Budget | Wiederkehrend: Regressionstests. Budget: Befund, RED und Fix | c40a49b, ed22627 (RED), 0f98fd4 (fix) |
| 4 Live-Fälle | 13 neue Fallgruppen, vier Läufe grün | dd45b56, fa5b5cf |
| 5 Beleg | Abschnitt Gap closure 32-10, ABGLEICH ohne Fehlstelle, Messkommentar 18770 | 4a75334 |
| 6 Push-Frage | ANGEHALTEN, an die Hauptsitzung; raw/32-10-push.txt noch nicht angelegt | - |

## Messentscheide (raw/32-10-messung.txt)

- `gruppe_hinaus=erkannt`: GRUPPE-HINAUS je Instanz 8 Zeilen; an-gruppe-ro und -rw `eintraege=1 kinder=user principal_art=groups shared_out=ja`, privat und zurueckgenommen `eintraege=0 shared_out=nein`. GRUPPE-SELBST: alice sieht ihre eigene Liste trotz Mitgliedschaft nur einmal.
- `gruppe_rein=geteilt-erkannt`: GRUPPE-REIN je Instanz 4 Zeilen, alle `uri_mit_marker=ja read_only_2xx=ja owner_displayname_passt=ja shared=ja name_ohne_besitzer=ja`, writable ja für rw, nein für ro.
- `gruppe_subline=bereinigt`: nc35 alle vier Sublines mit Besitzer, clean_subline `bereinigt`; nc32 ohne Besitzer, `unveraendert`.
- `wiederkehrend=wie-erwartet`: auf beiden Instanzen gleich, Vorfilter des Servers lässt app und instanz-erledigt durch (filter_offen=ja), master-erledigt nicht.
- `deckel_budget=anheben-auf-2`: KOSTEN deckel-aufruf max 819 ms (nc35) und 831 ms (nc32) bei 2000 offenen Aufgaben, REPORT allein max 220 ms; DECKEL bei 600 auf beiden und bei 2000 auf nc32 wie erwartet (20 Seiten, 500 eindeutig, Notiz, kein next); bei 2000 auf nc35 mit Budget 1 s `degraded=ja seiten=0`. Regel max(1,ceil(2*0.831)) = 2, unter der Abbruchgrenze 5 s.

## Befunde und Fixes

1. **Budget je Liste zu knapp bei vielen offenen Aufgaben** (Befund aus Task 1, behoben in Task 3): Mit 2000 offenen Aufgaben in einer Liste brach `tasks_search` auf nc35 schon die erste Seite ab ("None of the task lists could be read."). Ursache: Parsen von 1,4 MB im Client innerhalb von `asyncio.timeout(PER_LIST_TIMEOUT)`. RED ed22627 (`test_limit_policy_constants_are_the_measured_values` erwartet 2 und `MESSWERT per_list_timeout_s=2`), fix 0f98fd4 (`PER_LIST_TIMEOUT = 2.0`, Kommentar mit Quelle plan 32-10). Live danach: deckel-500 mit `budget_s=2`, max_seite_ms 204 und 197 (nc35), 203 und 258 (nc32), Median je Seite 186 bis 193 ms.
2. Sonst kein Befund gegen D-32-14 bis D-32-18, E4 oder TASK-02.

## Rote Tests der RED-Commits

- b64a27b: 13 neue Tests in tests/unit/test_tasks_measure.py (`test_group_share_body_*` 3, `test_invite_shape_*` 3, `test_recurring_todo_*` 4, `test_paging_summary_*` 3); Gesamtlauf 13 failed, 6399 passed, 35 skipped; ruff, format, pyright, vulture grün.
- ed22627: genau `test_limit_policy_constants_are_the_measured_values`; Gesamtlauf 1 failed, 6432 passed, 35 skipped; übrige Gates grün.
- Kein RED nötig, Messung zeigt korrektes Verhalten: 5b949cb (Gruppe in Discovery und Zielwahl: 9 Tests in test_tasks_client.py, 7 in test_tasks_create.py) und c40a49b (wiederkehrend: 2 Tests in test_tasks_search.py, 2 in test_tasks_read.py). Beide beim ersten Lauf grün; der einzige Fehlschlag vorher war ein fehlender `etree`-Import im Testmodul.

## Live-Läufe (Stand dd45b56, je 34 Fälle)

| Instanz | Tasks-App | Anzeigename bob | Ergebnis | Stempel |
|---|---|---|---|---|
| Nextcloud 35.0.0 | keine | unverändert | 34 passed (d-32-17-* entfaellt) | 8bf1c038 |
| Nextcloud 35.0.0 | 0.18.1 | gesetzt, zurück | 34 passed | 5f3e61c4 |
| Nextcloud 32.0.15 | keine | unverändert | 34 passed (d-32-17-* entfaellt) | c0bc8112 |
| Nextcloud 32.0.15 | 0.18.1 | gesetzt, zurück | 34 passed | c408b127 |

- Alle vier Läufe mit `NC_MCP_TASKS_CAP_SERIES=1`; deckel-500 in jedem Lauf ok (20 Seiten zu 25, 500 eindeutig, Notiz gleich SEARCH_CAP_NOTE, kein next, kein degraded).
- D-32-18 für Gruppen (Testkonto, kein Gruppenmitglied): privat geschrieben, an-gruppe-ro und -rw abgelehnt ohne PUT, parent abgelehnt, zurück wieder geschrieben; keine Meldung nennt Gruppe, bob oder `_shared_by_`.
- Hinein: gruppe-rein-flags, -ohne-list (Hinweis führt `<name> (shared, key <key>)`, ro nicht), -rw-mit-list, -ro-vorab, -parent, -fetch (nur Startseite der Tasks-App) ok; d-32-17-gruppe und -faellig mit Tasks-App ok (35: Rohsubline mit Besitzer als Positivkontrolle, bereinigt; 32: ohne Besitzer, unverändert).
- wiederkehrend-app, -instanz-erledigt, -master-erledigt in allen vier Läufen ok.
- keine-kennung: 51 bzw. 62 Antworten ohne Kennung und ohne Anzeigenamen von bob.
- Ein Vorlauf auf nc35 ohne Tasks-App (a92a3537, vor dem Commit dd45b56, gleicher Inhalt) ist im Rohprotokoll eingerückt vermerkt; er wurde wiederholt, weil das doppelte `-q` die Summenzeile unterdrückte.

## Anzeigename

- Vor dem ersten Setzen per grep geprüft: Nur tests/integration/test_tasks_live.py liest den Anzeigenamen von bob (aus `occ user:info`, nicht aus einer Konstanten); kein anderes Integrationsmodul erwartet ihn; Läufe seriell ohne xdist.
- Weg: `occ user:setting <bob> settings display_name <wert>` trägt auf 35 und 32 (Rücklesen über `occ user:info`), OCS war nicht nötig. Zeilen `ANZEIGENAME bob gesetzt=ja zurueck=ja gleich_vorher=ja weg=occ` in beiden Läufen mit Tasks-App, `gesetzt=nein zurueck=entfaellt` ohne. Der Wert kommt in keinem Rohprotokoll vor.

## BASELINE, Gruppe, Papierkorb

- Messung: nc35 alice calendars=1 objekte=31, bob 2/1; nc32 alice 1/3, bob 2/1; p3202frisch und p3202nie 0; vorher gleich nachher (BASELINE-VERGLEICH gleich=ja).
- Live: BASELINE vorher gleich nachher für alice, bob, die zwei TASK-03-Konten und das Testkonto in allen vier Läufen (dieselben Endwerte wie oben).
- GRUPPE vorher und nachher `vorhanden=nein shares=0` in der Messung und in jedem Lauf.
- PAPIERKORB: alice und bob gefunden=0; Testkonto vor dem Löschen der Liste gefunden=1 geleert=1 (Objekt nach der Positivkontrolle von 32-09), danach 0.
- Tasks-App auf beiden Instanzen wieder `keine`, Konfigurationsschlüssel gelöscht.

## Gates (32-RULES Abschnitt 3, pytest mit -p no:xdist), letzter Lauf vor 4a75334

- RAM frei vor dem Lauf 4,72 GB (4717784 KiB); vor den Containerstarts 5,26 / 4,57 GB (Läufe), 5,2 / 4,7 GB (Messung).
- pytest unit+contract: 6433 passed, 35 skipped (Exit 0)
- check_tool_budget: tools/list 18770 Bytes, 27 Werkzeuge, Budget 22000; tasks_create 1380, tasks_search 870, tasks_read 295 Bytes
- ruff check, ruff format --check (392 Dateien), pyright (0 errors), vulture: alle Exit 0
- TASK-01: Diff der drei Kalender-Testdateien gegen 32-BASE leer, Gegentreffer im selben Diff mit tests/integration/test_tasks_live.py; caldav.py und tools/calendar.py in 32-10 unverändert (Diff gegen d1025b3 leer).
- Messkommentar: Diff von scripts/check_tool_budget.py gegen d1025b3 nur Kommentarzeilen, BUDGET_BYTES = 22_000.

## CHANGELOG und README

- CHANGELOG entfaellt: Der einzige fix-Commit ändert `PER_LIST_TIMEOUT`; kein Satz unter `[Unreleased]` nennt das Budget, kein Wortlaut wird falsch. READMEs nennen das Budget nicht.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Zeitbudget je Liste aus der Messung angehoben**
- Gefunden in Task 1 (DECKEL nc35 aufgaben=2000 degraded=ja), im Plan als Fall "anheben-auf-<n>" vorgesehen; RED ed22627, fix 0f98fd4.

**2. Messweise des Budgets präzisiert**
- `KOSTEN deckel-aufruf` lief mit einem angehobenen Budget von 60 s (Zeile `budget_waehrend_messung_s=60`), damit das Produktbudget die Messung nicht abschneidet; das Blättern (DECKEL) lief mit dem Produktbudget. Der Plan nannte das nicht ausdrücklich.

**3. Fixture aus nc35 mit umbenannten Listen**
- Die Zustände privat, an-gruppe-ro, an-gruppe-rw stammen aus derselben Liste `p3210-aus` zu verschiedenen Zeitpunkten und heißen in der Fixture `p3210-privat`, `p3210-aus-ro`, `p3210-aus-rw`; `_shared_by_Sharee` wurde zu `_shared_by_sharee` vereinheitlicht. nc32 trägt oc:invite in derselben Form, darum keine zweite Form.

**4. Rückbau-Zeilen**
- `_purge_calendar_trash` im Live-Test und `purge_trash` im Messprogramm geben jetzt gefunden und geleert getrennt zurück (Zeilen PAPIERKORB); `geleert` zählt nur 2xx-Antworten.

**5. Wiederkehrende Formen in Liste b von alice**
- Vorher geprüft: Kein bestehender Fall erwartet eine exakte Treffermenge von Liste b (`ausfall-liste` erwartet nur, dass b als degraded erscheint; `ohne-list-zwei-listen` zählt Objekte vorher gleich nachher).

**6. Gates vor dem Commit des Live-Tests**
- Für dd45b56 liefen ruff, format, pyright, vulture und tests/unit/test_live_requirement.py; der Unit-Lauf von pytest ist von einer Integrationsdatei unabhängig und lief für 0f98fd4 und 4a75334 voll.

## Grenzen

- Keine ganze Kette über die installierte ExApp; Beweis auf Funktionsebene unter Impersonation wie 32-07 und 32-09.
- Wie die Tasks-App selbst eine Instanz abhakt, braucht einen Browser, nicht gemessen.
- Die Serie mit 2000 offenen Aufgaben lief nur im Messprogramm; der Live-Test nutzt 520. In CI sind beide Schalter (`NC_MCP_TASKS_CAP_SERIES`, `NC_MCP_TASKS_BOB_DISPLAY`) nicht gesetzt.
- Nextcloud 33 und 34 nur über die Quelle.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche über das `<threat_model>` hinaus. Testgruppe, Gruppenfreigaben, Serie und Anzeigename werden je Lauf angelegt und zurückgebaut.

## Offen für die Hauptsitzung

- Task 6: Push-Frage an den Owner. Antwort als `FREIGABE push=<ja|nein> datum=...` in raw/32-10-push.txt, Commit `docs(32-10): owner answer on the push`. Auch bei ja pusht dieser Plan nicht.
- Phase 32 ist NICHT als complete markiert; die erneute Verifikation macht die Hauptsitzung.

## Self-Check: PASSED

- Dateien vorhanden: tests/fixtures/caldav_home_group_share.xml, raw/32-10-messung.txt, raw/32-10-nc35.txt, raw/32-10-nc32.txt
- Commits vorhanden: b64a27b, 1f7293b, ad389ef, 5b949cb, c40a49b, ed22627, 0f98fd4, dd45b56, fa5b5cf, 4a75334

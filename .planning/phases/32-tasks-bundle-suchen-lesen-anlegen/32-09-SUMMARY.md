---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 09
subsystem: tasks-bundle
tags: [gap-closure, caldav, vtodo, unified-search, sharing, live-proof]
gap_closure: true
requires:
  - phase: 32-08
    provides: Tasks-Bundle samt Live-Test, Beleg und CI-Lauf
provides:
  - "TaskList.shared_out aus oc:invite (plus cs:publish-url), D-32-18 in _pick_target"
  - "clean_subline und Bereinigung der Provider-subline in unified_search und search (D-32-17)"
  - "fetch mit metadata.truncated und <feld>_floating (W2), query-Beschreibung (W3)"
  - "Live-Fälle d-32-17-* und d-32-18-* in tests/integration/test_tasks_live.py"
  - "W4 und Gap-closure-Abschnitt in docs/tasks-evidence.md"
affects: [32-verification, 33, 34]
tech-stack:
  added: []
  patterns:
    - "Freigabestand eigener Listen nur zählen, nie speichern; unlesbar gilt als hinausgeteilt"
    - "subline geteilter Treffer: ersetzen, wo sicher, sonst weglassen (fail closed)"
key-files:
  created:
    - tests/fixtures/caldav_home_shared_out.xml
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-messung.txt
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-nc35.txt
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-nc32.txt
  modified:
    - src/mcp_connector/nextcloud/clients/tasks.py
    - src/mcp_connector/tools/tasks.py
    - src/mcp_connector/tools/search.py
    - src/mcp_connector/tools/chatgpt.py
    - src/mcp_connector/server/reg_tasks.py
    - scripts/tasks_measure.py
    - tests/integration/test_tasks_live.py
    - docs/tasks-evidence.md
    - README.md
    - README.de.md
    - README.fr.md
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md
key-decisions:
  - "ENTSCHEID erkennung_hinaus=oc:invite, erkennung_link=oc:invite mit cs:publish-url als zweitem Merkmal, punkt6=unlesbar-gilt-als-hinausgeteilt, sublineregel=ersetzen (raw/32-09-messung.txt)"
  - "Live auf 35 gefunden: subline einer Aufgabe ohne Fälligkeit ist nur \"(<Rohname>)\"; clean_subline ersetzt auch diese Form (fix 39c1be9)"
requirements-completed: []
metrics:
  completed: 2026-11-13
  duration: "Teil 1 (früherer Executor) bis 8bc247b; Fortsetzung 2026-11-13 etwa 16:40 bis 17:20 UTC"
---

# Phase 32 Plan 09: Gap Closure Summary

**Eine eigene, an andere geteilte oder per Link veröffentlichte Aufgabenliste ist ohne `list` kein Schreibziel mehr (oc:invite, gemessen auf 32 und 35). `unified_search` und `search` nennen den Besitzer einer geteilten Liste nicht mehr. `fetch` kennzeichnet gekürzte Beschreibungen und schwebende Zeiten. Alles ist live auf Nextcloud 35 und 32 belegt, je ohne und mit Tasks-App.**

## Ergebnis je Task

| Task | Ergebnis | Commits |
|---|---|---|
| 1 Messung vor dem Bau | ENTSCHEID-Zeilen auf 35 und 32 (siehe key-decisions), BASELINE gleich, Papierkorb leer | c1e3389 (RED), 2cda29a, f2b9b3b |
| 2 W2 und W3 | fetch: `truncated`, `<feld>_floating`; query "Words in title, description or tags; default: all" | 6ad04b2 (RED), 997dc1e |
| 3 D-32-17 | `owner_suffix`, `clean_subline`, eine Discovery je Aufruf nur bei geteilten tasks-Treffern | ecb91d6 (RED), 03cbe34 |
| 4 D-32-18 | `shared_out`, Zielwahl nach Punkt 1, 2, 4 und 7, Werkzeugtexte | 8bc247b (RED), dc7bb9f |
| 5 Live-Beweis, W4, Doku | 35 und 32 je ohne und mit Tasks-App grün; Befund zu D-32-17 behoben | e672187 (RED), 39c1be9 (fix), 83030c1, b0cadfe, ca68abd |
| 6 Push-Frage | ANGEHALTEN, an die Hauptsitzung übergeben; kein Push, `raw/32-09-push.txt` noch nicht angelegt | - |

## Rote Tests der RED-Commits

- c1e3389, e672187 und 8bc247b: Die Namen der neu angelegten Tests stehen unten. Für die RED-Commits von Teil 1 hat der frühere Executor sie als rot gemeldet; in dieser Sitzung wurde das nicht nachgemessen.
- c1e3389: neun `test_share_state_*`, `test_share_line_*` und `test_subline_form_*` in tests/unit/test_tasks_measure.py
- 6ad04b2: `test_a_cut_task_description_is_marked_truncated`, `test_a_short_task_description_carries_no_truncated_key`, `test_a_floating_task_time_is_marked_in_the_text_and_the_metadata`, `test_a_zoned_or_all_day_task_time_carries_no_floating_mark`, `test_the_query_parameter_names_title_description_and_tags_not_the_list`, `test_a_word_of_the_description_finds_a_task_and_the_list_name_does_not`
- ecb91d6: Die Tests zu `owner_suffix` und `clean_subline` in test_tasks_client.py, dazu die Fälle in test_unified_search.py und test_chatgpt_search.py (16 neue Tests).
- 8bc247b: 16 neue Tests zu `shared_out` und zur Zielwahl in test_tasks_client.py und test_tasks_create.py.
- e672187 (in dieser Sitzung gemessen): Genau `test_clean_subline_replaces_a_subline_that_is_only_the_raw_name` war rot, Gesamtlauf 1 failed, 6398 passed, 35 skipped. Der mitgelieferte Gegentest `test_clean_subline_drops_a_bare_raw_name_with_text_in_front_and_no_space` war schon grün.

## Gates (32-RULES Abschnitt 3), letzter Lauf vor ca68abd

- pytest unit+contract: 6399 passed, 35 skipped (Exit 0, ohne xdist, freier RAM vorher 5,3 GB)
- check_tool_budget: tools/list 18770 Bytes, 27 Werkzeuge, Budget 22000; tasks_create 1380 Bytes, tasks_search 870 Bytes
- ruff check, ruff format --check (392 Dateien), pyright (0 errors), vulture: alle Exit 0
- TASK-01: Diff der drei Kalender-Testdateien gegen 32-BASE leer, Gegentreffer in tests/integration/test_tasks_live.py; caldav.py und tools/calendar.py in 32-09 unverändert

## Live-Läufe (Endstand, je 21 Fälle)

| Instanz | Tasks-App | Ergebnis | Stempel |
|---|---|---|---|
| Nextcloud 35.0.0 | 0.18.1 | 21 passed | ec5b284e |
| Nextcloud 35.0.0 | keine | 21 passed (d-32-17 entfaellt) | 3ac5b8a4 |
| Nextcloud 32.0.15 | keine | 21 passed (d-32-17 entfaellt) | a4ff82e2 |
| Nextcloud 32.0.15 | 0.18.1 | 21 passed | 7c9842bf |

- D-32-18, auf beiden Instanzen ok: `d-32-18-privat` (Positivkontrolle geschrieben), `-geteilt` (Fehler mit "shared with others" und "list=", kein PUT, Zähler gleich, kein Name), `-mit-list` (geschrieben), `-parent` (Fehler, kein PUT), `-link` (veröffentlicht: Fehler), `-zurueckgenommen` (wieder geschrieben).
- D-32-17, nur mit Tasks-App ok:
  - Auf 35 nennt die rohe subline den Besitzer (Positivkontrolle). Bereinigt wird ohne Fälligkeit `(p32live-...-rw)` geliefert, mit Fälligkeit `Fällig am 04.12.2026 (p32live-...-rw)`, `text` jeweils gleich.
  - Auf 32 enthält die rohe subline keinen Besitzer und bleibt wie geliefert.
  - `d-32-17-eigen` ist auf beiden unverändert.
- `keine-kennung`: In 28 bis 35 Antworten je Lauf kommt weder die Kennung noch der Anzeigename von bob vor.
- BASELINE vorher = nachher für alice, bob, die zwei TASK-03-Konten und das Testkonto `p32live<stempel>aus` in jedem Lauf. Endwerte: nc35 alice calendars=1 objekte=31, bob 2/1; nc32 alice 1/3, bob 2/1; alle anderen 0.
- PAPIERKORB: alice und bob gefunden=0. Testkonto gefunden=1 geleert=1, das ist das nach der Positivkontrolle gelöschte Objekt; nach dem Löschen der Liste gefunden=0.
- Tasks-App auf beiden Instanzen wieder `keine`, Konfigurationsschlüssel gelöscht. Alle Instanzen gestoppt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] subline einer geteilten Aufgabe ohne Fälligkeit fiel weg statt bereinigt zu werden**
- **Gefunden in:** Task 5, Lauf nc35 mit Tasks-App (stempel adacae78)
- **Problem:** Ohne DUE liefert Nextcloud 35 die subline als `(<Rohname>)` ohne führendes Leerzeichen. Die Regel der Planung kannte nur das Ende ` (<Rohname>)`, deshalb gab `clean_subline` None zurück. Das war sicher, weil kein Name nach außen ging, aber die Zeile fehlte. Die Messung von Task 1 hatte nur eine Aufgabe mit DUE.
- **Fix:** Eine subline, die genau `(<Rohname>)` ist, wird `(<Name>)`. Vorher steht der RED-Test, ein Gegentest prüft Text davor ohne Leerzeichen (bleibt None).
- **Dateien:** src/mcp_connector/nextcloud/clients/tasks.py, tests/unit/test_tasks_client.py
- **Commits:** e672187, 39c1be9

**2. [Rule 1 - Bug] Live-Test prüfte die bereinigte Form mit führendem Leerzeichen; zweiter Fall mit Fälligkeit ergänzt**
- **Gefunden in:** Task 5, Lauf nach dem Fix (stempel 897be3e2)
- **Fix:** Der Fall ohne Fälligkeit erwartet `(<Name>)`. Neuer Fall `d-32-17-geteilt-faellig` mit Aufgabe `fremdfaellig` (DUE 2026-12-04) in der rw-Liste. Die bereinigte subline wird protokolliert, sie enthält keinen Namen.
- **Commit:** b0cadfe

**3. [Rule 2] Papierkorb des Testkontos vor dem Löschen der Liste leeren**
- Im ersten Rückbau ging das gelöschte Objekt mit der Liste weg, die Zeile zeigte entfernt=0. Jetzt wird der Papierkorb vor dem Löschen der Liste geleert (`vor-liste entfernt=1`) und danach noch einmal geprüft (0). Teil von 83030c1.

**4. Entwurf t5_live.py ergänzt:**
- Ergänzt: `OUT_USER`, `OUT_LIST`, `publish_body`, `Run.harness_out`, Rückbau `_teardown_out`, das Testkonto in der BASELINE und in `occ user:delete`.
- Vergleich bei Rohsubline ohne Besitzer auf `(subline or "") == raw` geändert: Eine leere subline erscheint im Treffer nicht als Schlüssel.

**5. Vorläufe im Rohprotokoll:**
- Die verworfenen Läufe stehen eingerückt in raw/32-09-nc35.txt, Abschnitt (2), samt Befundzeilen und Ursache.
- Die Endläufe kamen nach allen Commits; ohne Tasks-App lief nc35 deshalb nach dem Entfernen der App ein zweites Mal.

## Grenzen

- Keine Gruppenfreigabe gemessen (nicht freigegeben). Keine ganze Kette über die ExApp; der Beweis läuft auf Funktionsebene unter Impersonation, wie in 32-07.
- Ob eine Gruppenfreigabe in `oc:invite` erscheint, ist offen und steht so in docs/tasks-evidence.md.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche über das `<threat_model>` hinaus. Das Testkonto `p32live<stempel>aus` wird je Lauf angelegt und gelöscht.

## Offen für die Hauptsitzung

- Task 6: Push-Frage an den Owner; die Antwort gehört als `FREIGABE push=<ja|nein> datum=...` in raw/32-09-push.txt (Commit `docs(32-09): owner answer on the push`).
- Phase 32 ist NICHT als complete markiert; die erneute Verifikation macht die Hauptsitzung.

## Self-Check: PASSED

- Dateien vorhanden: tests/fixtures/caldav_home_shared_out.xml, raw/32-09-messung.txt, raw/32-09-nc35.txt, raw/32-09-nc32.txt
- Commits vorhanden: c1e3389, 2cda29a, f2b9b3b, 6ad04b2, 997dc1e, ecb91d6, 03cbe34, 8bc247b, dc7bb9f, e672187, 39c1be9, 83030c1, b0cadfe, ca68abd

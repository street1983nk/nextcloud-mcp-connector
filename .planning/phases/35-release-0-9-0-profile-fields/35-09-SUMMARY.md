---
phase: 35-release-0-9-0-profile-fields
plan: 09
subsystem: release
tags: [release, app-store, nachweise, security]
requires: ["35-08"]
provides: ["Runbook-Schritt 8 für 0.9.0 geschlossen, Runbook-Zeilen 0.9.0, Sicherheitsvertrag mit Register 35-07 bis 35-09, Nachtrag auf main"]
affects: ["Hauptsitzung: /gsd:secure-phase 35, STATE, ROADMAP"]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-09-nachweise.txt
  modified:
    - docs/store-submission.md
    - tests/unit/test_tasks_create.py
    - .planning/phases/35-release-0-9-0-profile-fields/35-SECURITY.md
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-freigaben.txt
decisions:
  - "Datumsabhängiger Test test_a_due_date_is_that_very_day nach Owner-Entscheid (b) datumsfest gemacht: das Folgedatum wird nur noch in den Datumszeilen DUE und DTSTART gesucht"
  - "Katalog nicht in einer Warteschleife gemessen (Auftrag der Hauptsitzung); die Nachmessung nach der Regeneration 02:30:15Z kam noch in derselben Sitzung und schließt die Step-8-Zeile"
  - "Nachtrag nach FREIGABE push-runbook antwort=push per Fast-Forward auf main und plan/release-090 gepusht"
metrics:
  completed: 2026-11-21
---

# Phase 35 Plan 09: Nachweise, Runbook-Zeilen und Sicherheitsnachtrag 0.9.0 Summary

Schritt 8 für 0.9.0 ist vollständig: Asset 302/200 mit 64052 Bytes, OCI-Index amd64 und arm64, Tag 0.9.0 in der Registry, Autor-Mail gleich am Tag, Katalog nach der Regeneration (Last-Modified 02:30:15Z) mit 0.9.0 oben; die Store-Seite rendert die Links zu Findling und zum README in EN, DE und FR; Runbook-Zeilen und Sicherheitsvertrag (59 Einträge, 0 offen) liegen auf main.

## Ablauf

| Task | Ergebnis | Freigabe | Commit |
|------|----------|----------|--------|
| 1 Nachweise, Runbook, Sicherheit | fünf Nachweise plus Detailseite und gerenderte Links; Gate-Lauf am 2026-11-21 zuerst rot (datumsabhängiger Test), nach Owner-Entscheid Testfix mit Positivkontrolle, danach alle Gates grün; Runbook-Zeilen "Steps 1 to 7 are done for 0.9.0" und "Step 8 for 0.9.0"; 35-SECURITY.md mit T-35-07-01 bis T-35-09-04 | `FREIGABE test-datumsfest antwort=b` | 96538001, 89026ad3, 0251e216, 9e188bb2 |
| 2 Owner-Frage Push | push | `FREIGABE push-runbook antwort=push datum=2026-11-21` | dfa102d2 |
| 3 Push und Übergabe | PRUEFUNG vor=push-runbook commits=12 autor_committer_fremd=0 trailer=0 closes_woerter=0; main und plan/release-090 b70a860f..1679c2c5 per Fast-Forward, kein force; CI auf main siehe unten | | 1679c2c5, dieser SUMMARY-Commit |

## Gates (nach dem Testfix, 2026-11-21)

- unit+contract: 8394 passed, 35 skipped (zweimal, zuletzt auf dem endgültigen Text der Runbook-Zeilen)
- check_tool_budget: 27 Werkzeuge 18611 Bytes, 32 Werkzeuge 22938 Bytes, Budget 26000
- ruff check ok, ruff format 419 Dateien, pyright 0 errors, vulture 0
- Runbook-Lauf `pytest -q -p no:xdist`: Exit 0, keine FAILED- oder ERROR-Zeile
- Dash-Prüfung mit Positivkontrolle über docs/store-submission.md, 35-SECURITY.md und raw/35-09-nachweise.txt: 0 Treffer

## CI auf main (1679c2c5)

Ein `gh run watch` auf CI 44857695880, danach je ein `gh run view`: alle neun Jobs success, kein Abbruch durch concurrency.

| Lauf | Jobs |
|------|------|
| CI 44857695880 | unit, image, exapp, canary-nc35, integration: success |
| Security scans 44857695962 | CodeQL (python), pip-audit over the locked set, REUSE licensing lint: success |
| OpenSSF Scorecard 44857696039 | Scorecard analysis: success |

## Abweichungen

- **[Rule 1, nach Owner-Entscheid] Datumsabhängiger Test:** `tests/unit/test_tasks_create.py::test_a_due_date_is_that_very_day` prüfte `"20261121" not in body`; der Körper trägt CREATED, DTSTAMP und LAST-MODIFIED mit dem Laufdatum, der Test war damit genau am 2026-11-21 (UTC) rot. Kein Produktfehler. Nach `FREIGABE test-datumsfest antwort=b` prüft der Test das Folgedatum nur noch in den Zeilen DUE und DTSTART, gleich streng; Positivkontrolle mit derselben Hilfsfunktion (gepflanztes DUE oder DTSTART 20261121 wird rot). Mustersuche: einziger Treffer dieser Art; `tests/unit/test_connections_page.py:242` ist verwandt, heute grün, nicht geändert. Commit 89026ad3.
- Der Runbook-Commit kam deshalb erst nach dem Sicherheitsnachtrag (Reihenfolge der Commits anders als im Plan).
- Gate-Zahl der Zeile "Steps 1 to 7" stammt aus dem neuen grünen Lauf vom 2026-11-21 (8394 passed, 35 skipped), nicht aus raw/35-03-abschluss.txt (8338 vor 35-10 bis 35-12).
- Zusätzlich zum Plan: Headless-Chrome-Abzug der Store-Seite als Beleg, dass die Markdown-Links als `<a href>` gerendert werden (Auftrag der Hauptsitzung).

## Übergabe an den Owner

- Dankesentwurf für PR #49: `.planning/phases/35-release-0-9-0-profile-fields/raw/35-03-dank-pr49.md`, jetzt postbar, durch den Owner (0.9.0 steht im Store und im Katalog). Claude hat nichts gepostet.
- Lücke NC35: die Rechte der App Profile Fields auf Nextcloud 35 sind ungemessen, weil der Store für 35 nur einen Nightly führt (AR-35-02, `FREIGABE pf-nc35 antwort=luecke`). Nachprüfung, sobald ein stabiles Release für 35 im Store ist (35-05-SUMMARY).
- Offene HINWEIS-Zeilen aus 35-04: die zwei Sprach-Hinweise (files_download, 403-Hinweis) sind durch 35-11 erledigt; offen bleibt nur der bewusste Store-Summary-Hinweis (DE "MCP Server für Nextcloud" ohne Bindestrich als Suchwort, FR-Summary kürzer), keine Änderung nötig.
- Vorgemerkt: Tag-Alias no-ai (eigene kleine Phase), Audit-Grund unspecified bei veraltetem ETag, Forum-Post zurückgestellt, Folgepunkt ocs-data-message nach 0.9.0 (`FOLGEPUNKT ocs-data-message`).

## Übergabe an die Hauptsitzung

- `/gsd:secure-phase 35` (State A, 35-SECURITY.md vorhanden, 59 Einträge, threats_open 0, audited_head 7c62bf3e) läuft vor dem Abhaken der Phase in ROADMAP und STATE.
- STATE und ROADMAP: Release 0.9.0 im Store (Submit-Lauf 44854983055, HTTP 201), Katalog seit 02:30:15Z mit 0.9.0; Phase 35 nach secure-phase abhaken. STATE, ROADMAP und REQUIREMENTS hat dieser Plan nicht geändert (35-RULES Abschnitt 4).
- Worktree release-090 bleibt bis zur Entscheidung der Hauptsitzung stehen.
- Dieser SUMMARY-Commit ist nur lokal; ob er gepusht wird, fragt die Hauptsitzung den Owner separat.

## Threat-Register

| Threat | Status |
|--------|--------|
| T-35-09-01 unbelegte Zahl | geschlossen: jede Zahl per grep in raw/35-0x bzw. raw/35-freigaben.txt (`ZAHLEN`), Katalog in der Zeile selbst geschlossen |
| T-35-09-02 Nachweisausgaben | geschlossen: Scratchpad zuerst, Geheimnisprüfung nur öffentliche Treffer, ghcr-Token nie gespeichert, Scratchpad gelöscht |
| T-35-09-03 Kommentar ohne Auftrag | geschlossen: nichts gepostet, Dankesentwurf beim Owner |
| T-35-09-04 Phase ohne Sicherheitsvertrag | geschlossen: Nachtrag mit threats_open 0, Übergabe von /gsd:secure-phase 35 oben |

## Self-Check

PASSED: raw/35-09-nachweise.txt vorhanden; Commits 96538001, 89026ad3, 0251e216, 9e188bb2, dfa102d2, 1679c2c5 vorhanden; origin/main = 1679c2c5; Runbook enthält "Steps 1 to 7 are done for 0.9.0" und "Step 8 for 0.9.0"; 35-SECURITY.md threats_open 0 mit T-35-09-Einträgen.

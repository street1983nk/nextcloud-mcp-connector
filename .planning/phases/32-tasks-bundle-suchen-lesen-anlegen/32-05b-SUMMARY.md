---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 05b
subsystem: tasks-live-harness
tags: [kanarie, abnahme, live-test, impersonation, ci, w3, deck]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-02 (FREIGABE zustand=option-a, ENTSCHEID erkennung=keine), 32-05 (Bundle tasks registriert), 32-06 (fetch für task:-Ids, Provider tasks)
provides:
  - Kanarie mit 27 Werkzeugen, Aufgabenliste der Kanarienwelt (nur VTODO), Schreibart task, Deck-Marker samt Positivkontrolle
  - Abnahmeskript mit Block tasks (anlegen ohne list, Suche per Id, tasks_read und fetch gleich)
  - tests/integration/test_tasks_live.py unter AppAPI-Impersonation, beide Läufe aus D-32-11, BASELINE und Rückbau ohne Papierkorb
  - CI-Schritte im Job exapp (ohne Tasks-App) und im Job canary-nc35 (Installation vor, Messung nach der Kanarie), Pins
  - tests/conftest.py lässt Integrationstests unter NC_MCP_REQUIRE_LIVE=1 nicht mehr still überspringen (W3)
affects: [32-07, 32-08]

tech-stack:
  added: []
  patterns:
    - "Live-Test mit cw.skip_or_fail statt pytest.skip; Erwartung der Tasks-App als NC_MCP_EXPECT_TASKS_APP, gegengelesen per occ app:list"
    - "Ausfall einer Liste im Client: Response-Hook hält die REPORT-Antwort einer Liste länger als PER_LIST_TIMEOUT zurück"
    - "Rückbau der Kalender-Papierkörbe per calendar-query auf trashbin/objects/ und DAV-DELETE, nie per Datenbank"

key-files:
  created:
    - tests/integration/test_tasks_live.py
  modified:
    - tests/integration/test_canary.py
    - tests/integration/canary_world.py
    - tests/integration/test_canary_world.py
    - scripts/acceptance_all_tools.py
    - tests/conftest.py
    - .github/workflows/ci.yml
    - tests/unit/test_live_requirement.py

key-decisions:
  - "Titel und Suchwort der Kanarie sind der Stamm, nie der Marker (D-28-06); 'Weltmarker' im Plan als Stamm gelesen"
  - "Die Aufgabenliste der Welt heißt wie der Stamm, URI <stamm>-aufgaben; der Kalender der Welt bleibt VEVENT und wird im Aufbau als VEVENT geprüft (TASK-01)"
  - "tests/conftest.py überspringt unter NC_MCP_REQUIRE_LIVE=1 nicht mehr: sonst wäre der Schalter ohne NC_MCP_URL wirkungslos (W3)"
  - "Fremder Ursprung: nichts gebaut, was der vorläufigen Linie aus 32-06 widerspricht; der Live-Test prüft nur eigene Listen auf die task:-Id des Provider-Treffers"

requirements-completed: []

duration: ca. 75min
completed: 2026-11-13
---

# Phase 32 Plan 05b: Live-Harness des Tasks-Bundles Summary

**Kanarie, Abnahmeskript, Live-Test unter Impersonation und die zwei CI-Läufe aus D-32-11 stehen als Code; ohne Umgebung überspringt der Live-Test, mit `NC_MCP_REQUIRE_LIVE=1` scheitert er. Ausgeführt wird live erst in 32-07 und im CI nach einer Push-Freigabe.**

## Ergebnis je Task

| Task | Ergebnis | Commit |
|---|---|---|
| 1: Kanarie, Kanarienwelt, Abnahmeskript | `EXPECTED_TOOLS = 27`, `"tasks_create": "task"`; Plan-Einträge `tasks_search` (Stamm, offen und alle), `tasks_read` (Aufgabe der Welt und eine Deck-Karte als task:-Id), `tasks_create` (Liste der Welt), dazu `fetch` der task:-Id; `control_expected` um `tasks_search`, `tasks_read` und `fetch` der Welt-Aufgabe erweitert (Titel trägt den Kontrollmarker); `DECK`-Prüfung aller Antworten der drei Aufgabenwerkzeuge. Welt: `_build_tasks` (lxml-Körper `task_list_body`, nur VTODO, Aufgabe per PUT, GET-Beweis, Discovery eigen und schreibbar, Kalender der Welt bleibt VEVENT), Rückbau mit `X-NC-CalDAV-No-Trashbin` und PROPFIND 404; `_build_deck` setzt `deck_marker` in die Kartenbeschreibung, Positivkontrolle per Deck-REST und Discovery (`app-generated--deck--board-<id>` mit VTODO) in `world.proof`; `_add_tool_write` mit eigenem Zweig `task` (Schlüssel über die Discovery, Fehler als Restzeile) und `else` als Restzeile statt stiller Talk-Aufräumung. Abnahme: `_tasks` mit "more than one task list" als eigenem FAIL, Treffer per Id, tasks_read und fetch vergleichen id, Titel, Status | `55b4216` |
| 2: test_tasks_live.py | 17 Tests, Protokollzeile `AUFGABE <fall> nc=... nutzer=... status=... ergebnis=...`; Kontrollen a und b zuerst; anlegen mit allen Feldern (Rohobjekt: `DUE;VALUE=DATE:20261203`, kein `20261204`, `DTSTART;VALUE=DATE`, `CATEGORIES`, `PRIORITY:3`, `RELATED-TO` = UID der Elternaufgabe); ohne list bei zwei eigenen Listen; geteilte Listen (Namen ohne Zusatz, Positivkontrolle "Zusatz roh vorhanden", shared/writable); rw nur mit list; ro vorab abgelehnt ohne PUT; Server 403/404 per Harness-PUT; D-32-16; Standard nur offen, due_by ohne undatierte; degraded per Client-Hook; fetch gleich tasks_read; Deck-Ausschluss mit Positivkontrolle; zwei TASK-03-Konten (mit und ohne Anmeldung); Provider mit/ohne Tasks-App samt Hinweis-Prüfung nach `erkennung=keine`; zuletzt Scan aller Antworten nach Kennung und Anzeigenamen von bob und `_shared_by_`. BASELINE je Konto (alice, bob, beide TASK-03-Konten) vorher und nachher, Rückbau nach Abschnitt 7 | `58816dc` |
| 3: CI und Pins | Job `exapp`: Schritt "Tasks bundle live without the Tasks app (TASK-03, D-32-11)" nach der DAV-Matrix; Job `canary-nc35`: "Install the Tasks app and restart Nextcloud (D-32-11)" vor der Kanarie (Installation, "already installed" abgefangen, `compose restart nextcloud`, Warten auf `status.php` mit `"installed": true`, höchstens 60 x 2 s, `grep -E '^  - tasks: '` in der Liste der aktiven Apps), "Tasks bundle live with the Tasks app (TASK-09, D-32-11)" nach der Kanarie; Schalter und `NC_MCP_EXPECT_TASKS_APP` nur an Schritten; vier neue Pins | `41ac266` |

## Gate-Zahlen

Vor jedem der drei Commits alle Exit 0:

| Stand | pytest unit+contract | budget | ruff | format | pyright | vulture |
|---|---|---|---|---|---|---|
| `55b4216` | 6340 passed, 35 skipped | `tools/list: 18747 bytes, 27 tools, budget 22000` | grün | 390 Dateien | 0/0/0 | leer |
| `58816dc` | 6340 passed, 35 skipped | wie oben | grün | 391 Dateien | 0/0/0 | leer |
| `41ac266` | 6344 passed, 35 skipped | wie oben | grün | 391 Dateien | 0/0/0 | leer |

Verify der Tasks:
- Task 1: `test_canary.py` und `test_canary_world.py` sammeln (5 Tests), ruff, pyright 0 Fehler.
- Task 2: ohne Umgebung 17 skipped; mit `NC_MCP_REQUIRE_LIVE=1` Exit 1, 17 Fehler mit "NC_MCP_REQUIRE_LIVE=1 but no ExApp topology configured (missing: ...)".
- Task 3: `test_live_requirement.py` 9 passed; genau ein Schritt mit `tests/integration/test_canary.py`. Gegenprobe gegen das alte ci.yml: die zwei Schritt-Pins rot, die zwei Zustands-Pins (kein Job-Schalter, conftest) grün, wie erwartet.
- YAML lokal: mit PyYAML (`uv run --isolated --no-project --with pyyaml==6.0.2`) geparst, die drei neuen Schritte mit ihren env-Blöcken gelesen, kein env auf Job-Ebene außer dem Image-Pin von canary-nc35; Shell-Körper der drei Schritte mit `bash -n` geprüft. actionlint und shellcheck sind nicht installiert.

TASK-01: Basis-Positivkontrolle grün; `git diff "$B"` über test_caldav_client.py, test_calendar_tools.py, test_calendar_roundtrip.py leer (Gegentreffer im selben Diff: 17 `def test_` in test_tasks_live.py). `src/` seit 32-06 unverändert (0 Diffzeilen). `Harness.mkcalendar` unverändert.

Keine U+2013/U+2014 im Diff des Plans.

## Live-Läufe

Keine. Kein Docker gestartet, keine BASELINE gemessen; laut Plan läuft der Live-Test erst in 32-07.

## Deviations from Plan

**1. [Rule 2 - W3] tests/conftest.py ließ den Schalter ins Leere laufen**
- **Gefunden in:** Task 2 (Verify "mit Schalter rot" lief grün mit 17 skipped)
- **Problem:** `pytest_collection_modifyitems` markiert ohne `NC_MCP_URL` jeden Integrationstest als skip, bevor `skip_or_fail` greift. Ein CI-Schritt mit Schalter, dem `NC_MCP_URL` fehlt, wäre grün geworden; das trifft auch die Kanarie.
- **Fix:** unter `NC_MCP_REQUIRE_LIVE=1` kein Skip-Marker; Pin `test_the_switch_keeps_integration_tests_from_the_skip_of_the_shared_conftest`. Ohne Schalter unverändert (Job integration).
- **Commits:** `58816dc` (conftest), `41ac266` (Pin)

**2. [Rule 3] test_canary_world.py bucht jede Schreibart**
- Der Weltentest prüft "ein Harness-Eintrag je Art in `WRITE_KINDS`"; mit `task` braucht er eine Harness-Aufgabe, sonst wäre er live rot. Nicht in `files_modified` des Plans. Commit `55b4216`.

**3. Auslegung "summary mit dem Weltmarker"**
- Der Marker darf nie Argument sein (D-28-06, `run_tool` assertet das); Titel ist `<stamm>-neu`, Liste ist der Stamm.

**4. Zusätzlich zum Plan**
- `fetch` der Welt-Aufgabe in der Kanarie, eine Deck-Karte als task:-Id in `tasks_read`; das letzte `else` von `_add_tool_write` ist keine stille Talk-Aufräumung mehr.
- Im Live-Test wird der Hinweis nach D-32-10 an einer echten Antwort von `tasks_create` geprüft (kein Feld `hint`, weil `erkennung=keine`).
- `app:enable` im Installationsschritt weggelassen: `app:install` aktiviert, und die Prüfung der aktiven Apps fängt jeden anderen Zustand.

## Hinweise für 32-07

- Lokal: `NC_MCP_EXPECT_TASKS_APP` setzen (0 oder 1); die Tasks-App auf nc35 nach Freigabe `option-a` installieren und neu starten, Rückbau wie in 32-02 (`app:remove` im aktiven Zustand).
- Der Live-Test legt zwei Konten `p32live-<stempel>-frisch` und `-nie` an und löscht sie; BASELINE umfasst sie.
- Die Positivkontrolle "Zusatz roh vorhanden" erwartet `<name> (` im rohen displayname der geteilten Listen (gemessen in 32-02).
- Zu bestätigen: die Deck-Kalender-URI `app-generated--deck--board-<id>` (30-04) und dass Deck eine Karte ohne Fälligkeit als VTODO zeigt; die Kanarienwelt verlangt nur die Sammlung mit VTODO.
- Fremder Ursprung (32-06): bleibt vorläufig task:-Id, Owner-Entscheid in 32-07.

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche im Produktcode. Der Live-Test legt Konten per `occ user:add` an; das Passwort entsteht im Test und geht nur über die Umgebung von `docker exec` (`OC_PASS`), nie in eine Ausgabe (T-32-05b-01). Der CI-Schritt installiert die offizielle Tasks-App aus dem App Store (T-32-SC, accept).

## Docker-Zustand

Kein Container gestartet, keiner läuft (`docker ps` leer). Kein Prozess gestartet.

## Self-Check: PASSED

- Commits 55b4216, 58816dc, 41ac266 im Log, Autor street1983nk, ohne Trailer, ohne closes/fixes/resolves; nichts gepusht.
- tests/integration/test_tasks_live.py vorhanden; alle sieben geänderten Dateien im Diff seit 83df4eb.

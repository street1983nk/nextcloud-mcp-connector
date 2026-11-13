---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 05b
type: execute
wave: 8
depends_on: ["32-05", "32-06"]
files_modified:
  - tests/integration/test_canary.py
  - tests/integration/canary_world.py
  - scripts/acceptance_all_tools.py
  - tests/integration/test_tasks_live.py
  - .github/workflows/ci.yml
  - tests/unit/test_live_requirement.py
autonomous: true
# Abweichung vom Planschnitt der Recherche: der Live-Harness steht in einem eigenen Plan
# (siehe Begründung in 32-05) und läuft NACH 32-06, weil Abnahmeskript und Live-Test auch
# fetch mit einer task:-Id prüfen (Erfolgskriterium 4) und fetch das erst ab 32-06 kann.
requirements: [TASK-01, TASK-02, TASK-03, TASK-05, TASK-06, TASK-07, TASK-09]

must_haves:
  truths:
    - "Die Kanarie zählt 27 Werkzeuge, ruft tasks_search, tasks_read und tasks_create wirklich auf, baut in der Kanarienwelt eine eigene Aufgabenliste (nur VTODO) mit Aufräumbeweis, bucht tasks_create als Schreibart task mit eigenem Aufräumzweig und belegt mit einem eigenen Marker in einer Deck-Kartenbeschreibung samt Positivkontrolle, dass keine Deck-Karte über das Tasks-Bundle abfließt (TASK-07)"
    - "Das Abnahmeskript ruft tasks_create, findet die Aufgabe per Id über tasks_search, liest sie mit tasks_read und mit fetch und prüft, dass beide dieselbe Aufgabe liefern (TASK-07, TASK-09)"
    - "tests/integration/test_tasks_live.py prüft unter AppAPI-Impersonation: Kontrollen zuerst (kein App-Passwort im Prozess, falsches APP_SECRET schreibt nichts), DUE;VALUE=DATE auf genau dem Tag im Rohobjekt, Startdatum, Tags, Priorität und Elternaufgabe im Rohobjekt, Zielwahl ohne list, geteilte Listen mit und ohne Schreibrecht samt Server-404 als letzte Instanz, D-32-16, kein Besitzername und keine Kontokennung in irgendeiner Antwort, Deck-Ausschluss, ein degraded-Eintrag bei einer im Client verzögerten Liste, die zwei TASK-03-Konten, fetch und tasks_read auf dieselbe Id und, mit Tasks-App, der Provider-Treffer auf dieselbe Id"
    - "Ohne Live-Umgebung überspringt der Test; mit NC_MCP_REQUIRE_LIVE=1 scheitert er (Schalter aus canary_world.skip_or_fail, W3); der Schalter steht nur an den CI-Schritten, nie am Job"
    - "CI misst beide Läufe aus D-32-11: im Job exapp (34.0.3) ein Schritt ohne Tasks-App, im Job canary-nc35 ein Schritt, der die Tasks-App installiert, Nextcloud neu startet und die Fassung zeigt, vor der Kanarie, und ein Schritt mit Tasks-App danach; test_live_requirement pinnt die neuen Schritte; es bleibt genau ein Schritt mit test_canary.py"
    - "Die Kalender-Termin-Werkzeuge sind im Live-Test und in der Kanarie unverändert; ihre Kanarienwelt bleibt bei VEVENT (die Aufgabenliste ist eine zweite Sammlung) (TASK-01)"
  artifacts:
    - path: "tests/integration/test_tasks_live.py"
      provides: "Live-Test des Bundles unter Impersonation, beide Läufe"
      contains: "skip_or_fail"
    - path: "tests/integration/canary_world.py"
      provides: "Aufgabenliste der Welt, Schreibart task, Deck-Marker"
      contains: "\"task\""
    - path: ".github/workflows/ci.yml"
      provides: "Schritte ohne und mit Tasks-App"
      contains: "test_tasks_live.py"
  key_links:
    - from: ".github/workflows/ci.yml"
      to: "tests/integration/test_tasks_live.py"
      via: "Schritte mit NC_MCP_REQUIRE_LIVE=1 und NC_MCP_EXPECT_TASKS_APP=0|1"
      pattern: "NC_MCP_EXPECT_TASKS_APP"
    - from: "tests/integration/canary_world.py _add_tool_write"
      to: "harness.delete_calendar_url"
      via: "eigener elif-Zweig für die Art task"
      pattern: "kind == \"task\""
---

<objective>
Den Live-Harness für das Bundle bauen: Kanarie und Kanarienwelt, Abnahmeskript, einen Live-Test unter Impersonation für beide Topologien und die CI-Schritte für die zwei Läufe aus D-32-11. Ausgeführt werden die Live-Teile erst in 32-07 (lokal) und nach Owner-Freigabe im CI.

Purpose: TASK-07 (Kanarie mit Aufgabenliste und Deck-Beweis, Abnahmeskript) und die Live-Belege für TASK-01 bis TASK-06 und TASK-09; schließt W3 aus Phase 31 für dieses Bundle.
Output: sechs geänderte oder neue Dateien.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-RULES.md
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-CONTEXT.md
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-RESEARCH.md
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-PATTERNS.md
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-02-SUMMARY.md
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-04b-SUMMARY.md
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-06-SUMMARY.md
@.planning/phases/31-ordner-anlegen/31-VERIFICATION.md

Rahmen: 32-RULES.md (verbindlich: Commits ohne Trailer, nur lokal, uv, Gates, Docker seriell mit RAM-Gate, keine Secrets, Owner-Freigaben, Rückbau ohne Papierkorb). In diesem Plan kein Docker-Lauf und kein Push: der Live-Test wird lokal nur gesammelt (`--collect-only`) und ohne Umgebung als "skipped" belegt; laufen lässt ihn 32-07.

## Entscheidungen der Planung

- D-32-11 als zwei Abschnitte in vorhandenen Jobs statt eines neuen Jobs (Empfehlung der Recherche F10): `exapp` (34.0.3, ohne Tasks-App, bringt zusätzlich eine Messung auf 34) und `canary-nc35` (35.0.1, Tasks-App per Schritt installiert). Die Tasks-App kommt nicht in die feste `ensure_app`-Liste des Bootstraps.
- Der erwartete Zustand der Tasks-App kommt als Umgebungsvariable `NC_MCP_EXPECT_TASKS_APP` (`0` oder `1`) an den Test; der Test prüft ihn zusätzlich über `occ app:list` im Container (unabhängiges Muster) und scheitert bei Widerspruch.
- Ausfall einer Liste live (Erfolgskriterium 2): der Server ist echt, der Ausfall wird im Client herbeigeführt (ein Response-Hook verzögert die REPORT-Antwort genau einer Liste über ein per monkeypatch auf 1 s gesetztes PER_LIST_TIMEOUT); der Beleg nennt das so.
- Byte-Gleichheit der Termin-Werkzeuge (Erfolgskriterium 2) wird nicht hier, sondern in 32-07 über die ganze Kette vor und nach dem Image-Wechsel gemessen.

<interfaces>
tests/integration/test_canary.py: Docstring Z. 16 ("n == 24"), `EXPECTED_TOOLS = 24` Z. 63, `WRITE_KINDS` Z. 80-86, `plan()` Z. 197-211, `control_expected` Z. 233-247, `book_write` Z. 277-286 (liest `data.get("id")`).
tests/integration/canary_world.py: `_NO_CAL_TRASH` Z. 108, `ENV_REQUIRE_LIVE` und `skip_or_fail` Z. 113-120, `mkcalendar` Z. 541-554 (f-String, nur VEVENT; nicht ändern, zweite Sammlung anlegen), `delete_calendar_url` Z. 556-557, `deck(...)` Z. 569-575, `WRITE_KINDS` Z. 774, `register_tool_write` Z. 903-914, `_add_tool_write` Z. 937-998 (letzter else-Zweig ist stillschweigend "message"), `_build_calendar` Z. 1193-1217, `_build_deck` Z. 1220-1244, `world.proof`.
scripts/tasks_spike.py: `mkcalendar_body(name, components=("VTODO",))` Z. 2405-2414 (lxml), `share_body` ab Z. 2416.
scripts/acceptance_all_tools.py: Werkzeugmenge aus tools/list Z. 183-199, Ordner-Block Z. 209-228, `# --- calendar` Z. 269-291.
tests/integration/test_files_create_folder_live.py: Kopf Z. 1-41, REQUIRED Z. 77-87, Lauf Z. 269-327, `Case` Z. 330-360, `appapi_clients` Z. 363-398, Kontrollen Z. 434-490; Topologie-Helfer in tests/integration/topology.py.
.github/workflows/ci.yml: Job `exapp` ab Z. 69 (DAV-Matrix-Schritt Z. 102-106), Job `canary-nc35` ab Z. 165 (Versionsprüfung Z. 188-194, Kanarien-Schritt Z. 201-219), Job `integration` ab Z. 243 (`uv run pytest -m integration` ohne ExApp-Variablen: dort muss die neue Datei überspringen).
tests/unit/test_live_requirement.py: `test_the_ci_step_of_the_gates_sets_the_switch` Z. 39-48 (genau ein Schritt mit test_canary.py), `test_the_gates_run_on_nextcloud_35_only` Z. 56-74; Schritte per `re.split(r"\n      - name: ", workflow)`.
Neustart nach app:install (Pitfall 8): Navigation und Provider-Liste zeigen bis zum neuen PHP-Prozess die alte Wahrheit; Warteschleife nach dem Muster tests/integration/test_oauth_flow_exapp.py (bis Z. 232).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Kanarie, Kanarienwelt und Abnahmeskript</name>
  <files>tests/integration/test_canary.py, tests/integration/canary_world.py, scripts/acceptance_all_tools.py</files>
  <read_first>
    - tests/integration/test_canary.py (Z. 1-300)
    - tests/integration/canary_world.py (Z. 100-125, 530-580, 760-1000, 1180-1250)
    - scripts/acceptance_all_tools.py (Z. 170-300)
    - scripts/tasks_spike.py (Z. 2400-2440)
  </read_first>
  <action>
test_canary.py: Zahl 27 (Konstante und Docstring), `"tasks_create": "task"` in WRITE_KINDS, Plan-Einträge für die drei Werkzeuge (`tasks_create` mit `"list": world.stamm` plus summary mit dem Weltmarker, `tasks_search` mit query auf den Weltmarker, `tasks_read` mit der Id einer Aufgabe der Welt), `control_expected` nur erweitern, wenn die Welt eine Aufgabe mit Kontrollmarker anlegt (dann tasks_search hinein). canary_world.py: zweite Sammlung der Welt nur mit VTODO (lxml-Körper nach `mkcalendar_body`, eigene Funktion; `mkcalendar` des Kalenders bleibt unverändert), eine Aufgabe darin, Aufräumen mit `X-NC-CalDAV-No-Trashbin` und Lesebeweis 404; "task" in `WRITE_KINDS`, eigener `elif kind == "task"`-Zweig in `_add_tool_write` nach dem Vorbild `event` (Id `task:<schlüssel>:<objekt>` über die Discovery der Welt in eine URL übersetzt, nie über die Kontokennung geraten); `_build_deck` setzt eine Beschreibung mit eigenem Marker (`world.deck_marker`, nicht `world.marker`, Pitfall 9) und hält in `world.proof` die Positivkontrolle (Deck-REST zeigt den Marker; die Discovery mit App-Passwort zeigt die app-generated---Sammlung mit VTODO); eine Prüfung, dass der Deck-Marker in keiner Antwort der drei Aufgabenwerkzeuge steht.

acceptance_all_tools.py: Block `# --- tasks` nach dem Kalenderblock: `tasks_create` ohne list (Testinstanz: alice hat genau eine eigene Liste `personal`; antwortet das Werkzeug mit dem Fehler "more than one", ist das ein FAIL mit dem Satz), `tasks_search` findet die Id (per Id, nie per Position), `tasks_read` liest sie, `fetch` liest dieselbe Id; summary und status von tasks_read und fetch gleich, sonst FAIL. Keine Zahl im Skript.

Lokal: `uv run --no-sync pytest tests/integration/test_canary.py --collect-only -q` und ruff/pyright über die drei Dateien. Commit "test(32-05b): canary and acceptance cover the tasks bundle".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/integration/test_canary.py --collect-only -q -o addopts="" --import-mode=importlib && grep -q "EXPECTED_TOOLS = 27" tests/integration/test_canary.py && grep -q 'kind == "task"' tests/integration/canary_world.py && grep -q "tasks_create" scripts/acceptance_all_tools.py && uv run --no-sync ruff check tests/integration scripts && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright tests/integration/canary_world.py tests/integration/test_canary.py scripts/acceptance_all_tools.py</automated>
  </verify>
  <acceptance_criteria>
    - Kanarie sammelt, 27 Werkzeuge, Schreibart task mit eigenem Aufräumzweig, Deck-Marker samt Positivkontrolle
    - `mkcalendar` des Kalenders unverändert (git diff zeigt keine Änderung in dieser Funktion)
  </acceptance_criteria>
  <done>Die Kanarie kennt das Bundle und beweist den Deck-Ausschluss mit eigenem Marker.</done>
</task>

<task type="auto">
  <name>Task 2: tests/integration/test_tasks_live.py unter Impersonation für beide Läufe</name>
  <files>tests/integration/test_tasks_live.py</files>
  <read_first>
    - tests/integration/test_files_create_folder_live.py (ganz)
    - tests/integration/topology.py (Z. 1-120)
    - tests/integration/canary_world.py (Z. 100-125: live_env, Harness, skip_or_fail)
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-02-SUMMARY.md (HOME-, NAMEN-, APPSTATE-Zeilen)
  </read_first>
  <action>
Neue Datei nach dem Vorbild test_files_create_folder_live.py, mit `cw.skip_or_fail(...)` statt `pytest.skip` (W3). Kopf: Frage, Form der Protokollzeile `AUFGABE <fall> nc=<version> nutzer=<uid> status=<calls> ergebnis=<ok|befund> | ...`, Laufanleitung für nc-mcp-exapp (32 und 34) und nc35 (Env-Dateien nur per `set -a && . <datei> && set +a`). Erst protokollieren, dann prüfen (`Case`). Caches vor jedem Fall leeren (`capabilities.clear_cache()`). Aufbau und Rückbau nur über das Harness mit App-Passwort und occ im Container, nie über den Connector; Rückbau nach 32-RULES.md Abschnitt 7 (jedes CalDAV-DELETE mit `X-NC-CalDAV-No-Trashbin: 1`, Papierkorb der Konten danach geleert, BASELINE je Konto aus `calendars`, `calendarobjects` samt `deleted_at` und `dav_shares` vor und nach dem Lauf als eigene Prüfung, die bei Abweichung scheitert); Kopf aller Testobjekte `p32live-<stempel>`.

Fälle (Gegenprobe jeweils mit unabhängigem Muster: Rohobjekt per Harness-GET mit App-Passwort oder Zeilen der Tabelle calendarobjects per occ/PHP im Container): Kontrollen a (kein App-Passwort im Prozess) und b (falsches APP_SECRET schreibt nichts); anlegen mit list in einer eigenen Liste, Rohobjekt enthält `DUE;VALUE=DATE:<tag>` und keinen Folgetag, DTSTART, CATEGORIES, PRIORITY und RELATED-TO wie gesendet; ohne list bei zwei eigenen Listen Fehler mit beiden Namen, nichts geschrieben; geteilte Listen von bob (rw und ro, share_body des Spikes über das Harness): Namen ohne Besitzerzusatz, shared und writable richtig, Schreiben in rw nur mit list, Schreiben in ro vorab abgelehnt (der Response-Hook zeigt keinen PUT), Server-404 als letzte Instanz per direktem PUT mit App-Passwort im Harness; D-32-16 (parent in rw ohne list: Fehler, nichts geschrieben); der serialisierte Rohtext ALLER Antworten des Laufs enthält weder die Kennung von bob noch dessen Anzeigenamen; Deck-Board mit Karte samt Beschreibungsmarker: Marker in keiner Antwort, Positivkontrolle über Deck-REST; Suche im Standard nur offen, due_by ohne undatierte; ausgefallene Liste per Client-Hook (Entscheidung der Planung) ergibt degraded mit dem Namen; TASK-03: Konto per `occ user:add` mit Passwort und einer Basic-Anfrage auf cloud/user (nur VEVENT) und Konto ohne jede Anmeldung: tasks_search leer mit hint, tasks_create Fehler mit Ausweg; Rückbau `occ user:delete`; fetch und tasks_read auf dieselbe Id liefern dieselbe Aufgabe; mit `NC_MCP_EXPECT_TASKS_APP=1`: unified_search findet die angelegte Aufgabe über den Provider tasks, provider_map übersetzt den Treffer in genau diese Id; mit `0`: der Provider fehlt und unified_search antwortet leer statt falsch, die drei Werkzeuge arbeiten, und der Hinweis zur Tasks-App erscheint genau dann, wenn ENTSCHEID erkennung nicht `keine` ist. Der Zustand der App wird zusätzlich per `occ app:list` gelesen (Fassung in die Protokollzeile); Widerspruch zu `NC_MCP_EXPECT_TASKS_APP` ist ein Fehler.

Lokal ohne Umgebung: läuft als skipped; mit `NC_MCP_REQUIRE_LIVE=1` und ohne Umgebung scheitert er. Commit "test(32-05b): live test of the tasks bundle under AppAPI impersonation".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/integration/test_tasks_live.py -m integration -q -o addopts="" --import-mode=importlib -rs 2>&1 | grep -q "skipped" && ! NC_MCP_REQUIRE_LIVE=1 uv run --no-sync pytest tests/integration/test_tasks_live.py -m integration -q -o addopts="" --import-mode=importlib && grep -q "skip_or_fail" tests/integration/test_tasks_live.py && uv run --no-sync ruff check tests/integration/test_tasks_live.py && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright tests/integration/test_tasks_live.py</automated>
  </verify>
  <acceptance_criteria>
    - Ohne Umgebung skipped, mit Schalter rot; jeder genannte Fall als eigener Test oder eigener Case
    - Keine Env-Datei wird gelesen oder zitiert; App-Version nur aus der Umgebung
    - Rückbau ohne Papierkorb und BASELINE-Prüfung (calendarobjects samt deleted_at) sind Teil des Tests
  </acceptance_criteria>
  <done>Ein Test belegt das Bundle live auf jeder Topologie, mit und ohne Tasks-App.</done>
</task>

<task type="auto">
  <name>Task 3: CI-Schritte für beide Läufe und ihre Pins, volle Gates</name>
  <files>.github/workflows/ci.yml, tests/unit/test_live_requirement.py</files>
  <read_first>
    - .github/workflows/ci.yml (ganz)
    - tests/unit/test_live_requirement.py (ganz)
    - scripts/install_findling.sh (Muster: App in laufende Topologie installieren)
    - tests/integration/test_oauth_flow_exapp.py (Z. 200-235: Warten nach Neustart)
  </read_first>
  <action>
ci.yml (per D-32-11): im Job `exapp` nach dem DAV-Matrix-Schritt ein Schritt "Tasks bundle live without the Tasks app (TASK-03, D-32-11)" mit `env: NC_MCP_REQUIRE_LIVE: "1"`, `NC_MCP_EXPECT_TASKS_APP: "0"`, `PYTHONUTF8: "1"` und `run: set -a && . ./.env.exapp && set +a` plus `uv run pytest tests/integration/test_tasks_live.py -m integration`. Im Job `canary-nc35` VOR dem Kanarien-Schritt ein Schritt "Install the Tasks app and restart Nextcloud (D-32-11)": `occ app:install tasks` (Fehler, wenn schon installiert, abfangen), Neustart des Nextcloud-Containers der Topologie, Warten bis status.php `installed: true` liefert (Schleife mit Obergrenze), danach `occ app:list` mit `grep "tasks" >/dev/null` (nie -q hinter einer Pipe) und Ausgabe der Fassung ins Log; NACH dem Kanarien-Schritt ein Schritt "Tasks bundle live with the Tasks app (TASK-09, D-32-11)" mit `NC_MCP_REQUIRE_LIVE: "1"`, `NC_MCP_EXPECT_TASKS_APP: "1"`. Der Kanarien-Schritt selbst bleibt der einzige mit test_canary.py; Job `integration` bleibt unverändert (dort überspringt die Datei).

test_live_requirement.py: drei neue Pins im Stil von Z. 39-48: der Schritt im Job exapp nennt test_tasks_live.py mit Schalter und EXPECT 0; im Job canary-nc35 steht der Installationsschritt vor dem Kanarien-Schritt, der Schritt mit EXPECT 1 danach; kein Job setzt NC_MCP_REQUIRE_LIVE auf Job-Ebene. Volle Gates nach 32-RULES.md. Commit "ci(32-05b): tasks bundle live with and without the Tasks app".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit/test_live_requirement.py -q -o addopts="" --import-mode=importlib && test "$(grep -c 'tests/integration/test_canary.py' .github/workflows/ci.yml)" = 1 && grep -q 'NC_MCP_EXPECT_TASKS_APP: "0"' .github/workflows/ci.yml && grep -q 'NC_MCP_EXPECT_TASKS_APP: "1"' .github/workflows/ci.yml && uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib && uv run --no-sync python scripts/check_tool_budget.py && uv run --no-sync ruff check . && uv run --no-sync ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright && uv run --no-sync vulture src scripts vulture_whitelist.py</automated>
  </verify>
  <acceptance_criteria>
    - Pins grün; genau ein Schritt mit test_canary.py; Schalter nur an Schritten
    - Volle Gates Exit 0; kein Push (der CI-Lauf ist Teil von 32-07 nach Owner-Freigabe)
  </acceptance_criteria>
  <done>CI kann beide Läufe aus D-32-11 bei jedem Push wiederholen, sobald der Owner den Push freigibt.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CI-Runner zu Secrets | .env.exapp entsteht im Job, Ausgaben landen im öffentlichen Log |
| Live-Test zu Instanz | legt Konten, Listen, Freigaben an |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-32-05b-01 | Information Disclosure | CI-Log, pytest-Ausgabe | mitigate | Env nur per set -a geladen, keine Werte gedruckt, Protokollzeilen nur Status und Kennungen der Testkonten |
| T-32-05b-02 | Tampering | Testinstanz | mitigate | Aufbau und Rückbau über das Harness, Kopf p32live-, Aufräumbeweis |
| T-32-05b-03 | Repudiation | falsch grüner Live-Test | mitigate | Kontrollen a/b zuerst, NC_MCP_REQUIRE_LIVE an den Schritten, Zustand der Tasks-App unabhängig per occ geprüft |
| T-32-05b-04 | Information Disclosure | Deck-Karten | mitigate | eigener Marker, Positivkontrolle, Prüfung aller Antworten der drei Werkzeuge |
| T-32-SC | Tampering | Tasks-App aus dem App Store im CI | accept | offizielle Nextcloud-App, Fassung im Log, keine Paketinstallation |
</threat_model>

<verification>
- Kanarie, Abnahme, Live-Test und CI-Schritte vorhanden und lokal gesammelt bzw. gepinnt
- Gates grün; lokale Commits ohne Trailer; kein Push
</verification>

<success_criteria>
- Alle Live-Belege für 32-07 sind als Code vorhanden; W3 ist für das Bundle geschlossen, sobald CI läuft
</success_criteria>

<output>
Create `.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-05b-SUMMARY.md` when done.
</output>

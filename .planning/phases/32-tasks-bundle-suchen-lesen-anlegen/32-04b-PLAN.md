---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 04b
type: execute
wave: 5
depends_on: ["32-04"]
files_modified:
  - src/mcp_connector/nextcloud/capabilities.py
  - tests/unit/test_ocs_capabilities.py
  - src/mcp_connector/tools/tasks.py
  - tests/unit/test_tasks_create.py
  - tests/unit/test_tasks_app_hint.py
  - tests/unit/test_injection_corpus.py
  - vulture_whitelist.py
autonomous: true
# Abweichung vom Planschnitt der Recherche (32-04 als ein Plan): aufgeteilt in 32-04 (Lesen)
# und 32-04b (Anlegen, Erkennung der Tasks-App, Injektionskorpus), weil ein Plan mit allen
# drei Werkzeugen, der Erkennung und dem Korpus deutlich über 50 Prozent Kontext läge
# (sieben Dateien, drei Teilsysteme). Benennung wie 31-04b und 31-05b in Phase 31.
requirements: [TASK-03, TASK-05, TASK-06, TASK-07]

must_haves:
  truths:
    - "create_task schreibt create-only über caldav.put_new_object mit TASK_WORDING; kein neuer .put(-Aufruf entsteht, EXPECTED_PUT_CALLS bleibt 6 (TASK-05, TASK-07)"
    - "due ohne Uhrzeit (YYYY-MM-DD) ergibt DUE;VALUE=DATE auf genau diesem Tag; mit Uhrzeit ist ISO 8601 mit Zone Pflicht; mit timezone wird die Zeit in dieser IANA-Zone samt VTIMEZONE geschrieben, ohne als UTC mit Z; calendar._all_day_window wird nicht benutzt (TASK-05)"
    - "priority außerhalb 0 bis 9, start mit anderem Werttyp als due oder nicht vor due, leeres summary, timezone ohne eine Zeitangabe und ein ungültiger parent werden vor jedem Request abgelehnt (TASK-05, D-31-08)"
    - "Zielwahl nach E4: list gewinnt und wird nur gegen die Discovery aufgelöst; ohne list wird nur geschrieben, wenn es genau eine eigene beschreibbare Liste gibt, sonst Fehler mit den echten Listennamen; eine nicht beschreibbare Liste wird vor dem Request abgelehnt; in eine geteilte Liste nur bei ausdrücklicher Nennung; Deck nie; 403 und 404 des Servers bleiben letzte Instanz mit ehrlichem Satz (TASK-06)"
    - "Nennt tasks_create nur parent und liegt die Elternaufgabe in einer geteilten Liste, kommt ein Fehler mit dem Hinweis, die Liste ausdrücklich zu nennen; geschrieben wird nichts (D-32-16)"
    - "parent ist eine task:-Id; die Elternaufgabe muss in der Zielliste liegen; geschrieben wird RELATED-TO:<uid> ohne RELTYPE (TASK-05)"
    - "Das Rücklesen meldet confirmed true nur, wenn das Objekt lesbar ist und die UID stimmt; ein Fehler beim Rücklesen macht den Schreibvorgang nie zum Fehlschlag (TASK-05)"
    - "Ein Konto ohne Aufgabenliste: tasks_create antwortet mit einem Fehler samt Ausweg über die Tasks-App (E6, TASK-03)"
    - "Der Hinweis, dass Aufgaben in der Oberfläche nur mit der Tasks-App sichtbar sind, steht genau einmal in der Erfolgsantwort von tasks_create und in den E6-Antworten, und nur, wenn der in 32-02 entschiedene Erkennungsweg sicher 'aus' meldet; ist er 'keine' oder die Erkennung unklar, entfällt der Hinweis; die Werkzeuge arbeiten in jedem Fall normal (D-32-10)"
    - "Der Injektionskorpus belegt für Titel, Beschreibung (gekappt) und Tags aus einer geteilten Liste: wörtlich nur im Inhaltsfeld, eine gefälschte Markerfolge wird gefiltert (TASK-07)"
  artifacts:
    - path: "src/mcp_connector/tools/tasks.py"
      provides: "create_task, Zielwahl, VTODO-Bau, Rücklesen, Hinweis Tasks-App"
      exports: ["create_task"]
    - path: "src/mcp_connector/nextcloud/capabilities.py"
      provides: "Erkennung der Tasks-App, dreiwertig, wirft nie (nur wenn ENTSCHEID erkennung nicht 'keine' ist)"
    - path: "tests/unit/test_tasks_create.py"
      provides: "Anlegen, Zielwahl, Prüfungen, Rücklesen"
  key_links:
    - from: "src/mcp_connector/tools/tasks.py create_task"
      to: "src/mcp_connector/nextcloud/clients/caldav.py put_new_object"
      via: "TASK_WORDING aus clients/tasks.py, label = Listenname"
      pattern: "put_new_object\\("
---

<objective>
Das Anlegen von Aufgaben bauen (`create_task`), die Erkennung der Tasks-App für den Hinweis aus D-32-10 (nur in der in 32-02 gemessenen Form), die E6-Antworten mit Hinweis und den Injektionskorpus für Aufgaben.

Purpose: TASK-05, TASK-06, der Anlegeteil von TASK-03, der Korpusteil von TASK-07; D-32-10 und D-32-16.
Output: create_task in tools/tasks.py, gegebenenfalls Erkennung in capabilities.py, drei Testdateien, ein erweiterter Korpus.
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
@.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-04-SUMMARY.md

Rahmen: 32-RULES.md (verbindlich: Commits ohne Trailer, nur lokal, uv, Gates, Docker seriell mit RAM-Gate, keine Secrets, Owner-Freigaben, Rückbau ohne Papierkorb). Kein Docker.

## Entscheidungen der Planung (delegiert, "Festschreiben" vom 13.11.2026)

- Parameter von `create_task(clients, *, summary, list_name=None, description=None, due=None, start=None, priority=None, tags=None, timezone=None, parent=None)`; auf dem Draht heißt `list_name` später `list` (32-05).
- `summary` leer oder nur Leerraum: Ablehnung; sonst unverändert geschrieben (ablehnen statt still verändern, D-31-08). `tags`: Leerwerte und Duplikate (casefold) verworfen, Reihenfolge der ersten Nennung, eine CATEGORIES-Zeile.
- `timezone` ohne `due` oder `start` mit Uhrzeit: Ablehnung ("timezone only applies to a due or start with a time"), statt sie still zu ignorieren.
- `start` und `due`: gleicher Werttyp (Datum gegen Datum, Zeit gegen Zeit), `start` echt vor `due` (Wortlaut TASK-05 "davor liegen"); `start` allein ist erlaubt.
- `parent` ohne `list`: Ziel ist die Liste der Elternaufgabe, wenn sie eine eigene beschreibbare Liste ist; liegt sie in einer geteilten Liste, Fehler nach D-32-16. `parent` mit `list`: liegen beide nicht in derselben Liste, Fehler ("the parent task lives in another list"), nichts geschrieben.
- Objekt: `icalendar.Todo` mit `UID` (frische UUID, Objektname `<uid>.ics`), `DTSTAMP`, `CREATED`, `LAST-MODIFIED` (UTC), `SUMMARY`, optional `DESCRIPTION`, `DUE`, `DTSTART`, `PRIORITY`, `CATEGORIES`, `RELATED-TO` (ohne RELTYPE), `PRODID` = `calendar.PRODID`; Form im Übrigen wie die Fixture einer neu angelegten Aufgabe unter tests/fixtures/tasks_app/ (zum Beispiel `STATUS:NEEDS-ACTION`, falls die Tasks-App ihn setzt). `VTIMEZONE` über `icalendar.Timezone.from_tzinfo` wie `calendar.build_ics` (Z. 404-416), nie von Hand.
- Erfolgsantwort: `id`, `summary`, `list` {name, shared, writable}, `created: true`, `confirmed`, `due`, `start` (wie geschrieben, über `_time_field`), optional `hint` (Tasks-App).
- Hinweistexte (englisch): E6 "This account has no task list." mit Ausweg "Create a list in the Nextcloud Tasks app, then try again."; Tasks-App aus: "Tasks show up in the Nextcloud web interface only with the Tasks app, which is not enabled for this account."
- Erkennung der Tasks-App nach `ENTSCHEID erkennung` aus 32-02: `navigation` (Eintrag mit `app` oder `id` gleich `tasks` in NAVIGATION_PATH) oder `provider` (Id `tasks` in `/ocs/v2.php/search/providers`); im selben Cache-Eintrag wie Mail (`capabilities._cache`, kein zweiter Modulzustand, ALLOWED_MODULE_STATE in tests/contract/test_no_destructive_calls.py Z. 360-365); bei ToolError, httpx.TimeoutException, httpx.RequestError oder deformierter Antwort `None`. Bei `keine`: keine Erkennung bauen, kein Hinweis, ein Test belegt die Abwesenheit des Hinweises.

<interfaces>
Aus 32-03/32-04: `clients/tasks.py` (`TaskList`, `discover_task_lists`, `get_todo`, `TASK_WORDING`), `caldav.put_new_object(client, creds, collection_uri, object_name, ics_bytes, wording, label)`, in `tools/tasks.py` die privaten `_resolve_list`, `_read_todo`, `_time_field` und die öffentlichen `search_tasks`, `read_task`.
Aus src/mcp_connector/tools/calendar.py (öffentlich): `parse_instant` Z. 129-145, `resolve_zone` Z. 148-158, `PRODID` Z. 48; Vorbild ohne Import: `create_event` Z. 252-319, `_pick_target` Z. 187-221 (Rückfall auf personal und "genau ein Kalender insgesamt" NICHT übernehmen), `_read_back` Z. 322-342, `build_ics` Z. 383-430.
Aus src/mcp_connector/nextcloud/capabilities.py: `__all__` Z. 37-47, `Capabilities` mit `mail_available` Z. 124-128, `has` Z. 130-147, `load_mail` Z. 168-195, `require_app` Z. 203-217 (NIE für tasks), `_navigation_lists_mail` Z. 220-245 (wirft bei deformierter Antwort; für Aufgaben nicht übernehmen), `NAVIGATION_PATH`.
Aus tests/unit/test_injection_corpus.py: Kalenderfall Z. 137-181, `everything_but` Z. 88-96, `INJECTION` aus test_tools_context.py.
Aus tests/unit/test_ocs_capabilities.py: Mail-Navigation Z. 562-715.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Erkennung der Tasks-App (nach ENTSCHEID erkennung) und Hinweis in den E6-Antworten</name>
  <files>src/mcp_connector/nextcloud/capabilities.py, tests/unit/test_ocs_capabilities.py, src/mcp_connector/tools/tasks.py, tests/unit/test_tasks_app_hint.py</files>
  <read_first>
    - src/mcp_connector/nextcloud/capabilities.py (ganz)
    - tests/unit/test_ocs_capabilities.py (Z. 1-60, 562-715)
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-02-SUMMARY.md (ENTSCHEID erkennung, APPSTATE-Zeilen)
  </read_first>
  <behavior>
    - Bei erkennung=navigation oder provider: `tasks_available` ist True bei Eintrag, False bei vollständiger Liste ohne Eintrag, None bei leerer Liste, Nicht-Array, 5xx, Timeout, Netzwerkfehler; die Funktion wirft in keinem Fall; zweiter Aufruf im Cache-Fenster stellt keinen Request
    - E6 in search_tasks: bei False steht der Satz zur Tasks-App genau einmal im hint; bei True oder None steht er nicht darin; die Antwort bleibt in allen drei Fällen {"tasks": [], "hint": ...}
    - Bei erkennung=keine: keine Erkennungsfunktion, und ein Test belegt, dass keine Antwort des Bundles den Satz zur Tasks-App enthält
    - Die Erkennung wird nur in den Fällen mit Hinweis angefragt (E6 und Erfolg von tasks_create), nie bei jeder Suche (Routenzählung)
  </behavior>
  <action>
Nach ENTSCHEID erkennung (per D-32-10): bei navigation oder provider ein Feld `tasks_available: bool | None = None` in `Capabilities`, eine Ladefunktion `load_tasks_app(clients) -> Capabilities` nach dem Muster von `load_mail` (Nachfüllen in denselben Cache-Eintrag mit ursprünglichem Zeitstempel), aber mit eigener, nie werfender Auswertung; in `__all__` aufnehmen; `Capabilities.has` nur erweitern, wenn ein Aufrufer `has("tasks")` braucht (sonst nicht). In tools/tasks.py eine private Funktion `_tasks_app_hint(clients) -> str | None`, die den Satz nur bei False liefert. Die E6-Antwort von search_tasks hängt den Satz an den hint an. Kein `require_app("tasks")` irgendwo.

Tests zuerst, dann Umsetzung. Commits "test(32-04b): ..." vor "feat(32-04b): say once when the Tasks app is off".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit/test_ocs_capabilities.py tests/unit/test_tasks_app_hint.py tests/unit/test_tasks_search.py tests/contract/test_no_destructive_calls.py -q -o addopts="" --import-mode=importlib && ! grep -n 'require_app("tasks")' src/mcp_connector -r</automated>
  </verify>
  <acceptance_criteria>
    - Verhalten nach ENTSCHEID erkennung getestet; Erkennung wirft nie; kein zweiter Modulzustand
    - Bestehende Mail-Tests in test_ocs_capabilities.py unverändert grün
  </acceptance_criteria>
  <done>Der Hinweis zur Tasks-App kommt nur, wenn er sicher stimmt, und nie auf Kosten der Funktion.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: create_task mit Prüfungen, Zielwahl nach E4 und D-32-16, VTODO-Bau, create-only-Schreiben und Rücklesen</name>
  <files>src/mcp_connector/tools/tasks.py, tests/unit/test_tasks_create.py, vulture_whitelist.py</files>
  <read_first>
    - src/mcp_connector/tools/calendar.py (Z. 180-320, 380-430)
    - tests/unit/test_calendar_tools.py (Z. 557-612, 699-802: Schreibfehler, Rücklesen, Zielwahl)
    - tests/fixtures/tasks_app/ (eine neu angelegte Aufgabe als Formvorbild)
  </read_first>
  <behavior>
    - due "2026-11-20" ergibt im gesendeten Körper `DUE;VALUE=DATE:20261120` und kein `20261121`; due "2026-11-20T09:00:00+01:00" ohne timezone ergibt `DUE:20261120T080000Z`; mit timezone "Europe/Berlin" `DUE;TZID=Europe/Berlin:20261120T090000` und eine VTIMEZONE; due "2026-11-20T09:00:00" ohne Zone abgelehnt; timezone "Mars/Olympus" abgelehnt
    - priority -1 und 10 abgelehnt, 0 und 9 angenommen; start Datum mit due Zeit abgelehnt; start gleich oder nach due abgelehnt; summary "" und "   " abgelehnt; timezone ohne Zeitangabe abgelehnt; jede Ablehnung ohne gerufene PUT-Route (und ohne Discovery, wo die Prüfung vorher möglich ist)
    - tags ["a,b", "wichtig", "", "Wichtig"] ergibt eine CATEGORIES-Zeile mit "a\,b" und "wichtig" einmal
    - summary mit Zeilenumbruch, Komma, Semikolon wird escaped (eine einzige VTODO-Komponente im Körper)
    - Zielwahl: ohne list und genau eine eigene beschreibbare Liste: geschrieben; zwei eigene Listen: Fehler mit beiden Namen; nur geteilte Listen: Fehler mit den Namen, keine PUT-Route; list auf geteilte beschreibbare Liste: geschrieben; list auf geteilte nur lesbare: Ablehnung vor dem Request; list unbekannt oder Deck-URI: Fehler mit verfügbaren Namen; zwei geteilte Listen gleichen Namens: Fehler mit beiden Schlüsseln
    - D-32-16: parent in geteilter Liste ohne list: Fehler mit Ausweg "name the list with list=", keine PUT-Route; parent in eigener Liste ohne list bei zwei eigenen Listen: Ziel ist die Liste der Elternaufgabe; parent und list in verschiedenen Listen: Fehler
    - parent: Körper enthält `RELATED-TO:<uid der elternaufgabe>` ohne RELTYPE; unbekannter parent: unbekannte Id, keine PUT-Route
    - PUT trägt `If-None-Match: *`; 412 ConflictError; Server-403 und Server-404 als letzte Instanz mit dem Aufgabenwortlaut (404: "not found or does not allow writing"), Meldungen ohne URI einer geteilten Liste
    - Rücklesen: GET ok und UID gleich: confirmed true; GET 500 oder Timeout: created true, confirmed false, kein Fehler; UID abweichend: confirmed false
    - Konto ohne Liste: ToolError "This account has no task list." mit Ausweg; Tasks-App aus (nach Task 1): Satz zusätzlich im hint
    - Erfolg: Antwortform nach den Entscheidungen der Planung, id ist eine task:-Id, die read_task wieder auflöst (Rundlauf über respx)
  </behavior>
  <action>
`async def create_task(...) -> dict[str, Any]` in tools/tasks.py (per E4, E7, TASK-05, TASK-06, D-32-16). Reihenfolge: alle Eingaben prüfen (vor jedem Request), Discovery, E6, Ziel wählen (eigene private Funktion `_pick_target(lists, wanted, parent_list)`; Regel "genau eine eigene beschreibbare Liste", nie Rückfall auf `personal`, nie "genau eine Liste insgesamt"), parent auflösen (Liste per Schlüssel, `get_todo`, UID lesen), Objekt bauen, `caldav.put_new_object(..., tasks_client.TASK_WORDING, target.name)`, Rücklesen nach `_read_back` nachgebaut mit UID-Vergleich, Hinweis Tasks-App aus Task 1 (genau einmal). Die neue Funktion schreibt nie über `caldav.put_event`. Vorübergehender vulture-Eintrag "until reg_tasks.py registers the bundle (32-05)".

Tests zuerst (rot), Umsetzung (grün), Gates nach 32-RULES.md inklusive `tests/contract/test_no_destructive_calls.py` (EXPECTED_PUT_CALLS 6). Commits "test(32-04b): ..." vor "feat(32-04b): create a task, never silently into a shared list".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit/test_tasks_create.py tests/contract/test_no_destructive_calls.py tests/contract/test_module_boundaries.py -q -o addopts="" --import-mode=importlib && ! grep -n "_all_day_window\|put_event" src/mcp_connector/tools/tasks.py && grep -q "put_new_object" src/mcp_connector/tools/tasks.py</automated>
  </verify>
  <acceptance_criteria>
    - Jeder Verhaltenspunkt getestet und grün; EXPECTED_PUT_CALLS weiter 6
    - tools/tasks.py nutzt weder `_all_day_window` noch `put_event`
  </acceptance_criteria>
  <done>Eine Aufgabe landet genau dort und so, wie der Assistent es ausdrücklich gesagt hat, oder gar nicht.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Injektionskorpus für Aufgaben aus einer geteilten Liste und volle Gates</name>
  <files>tests/unit/test_injection_corpus.py</files>
  <read_first>
    - tests/unit/test_injection_corpus.py (Z. 1-100, 137-181)
    - tests/unit/test_truncation_marks.py (Form der gefälschten Markerfolge)
  </read_first>
  <behavior>
    - search_tasks über eine geteilte Liste mit einer Aufgabe, deren summary und tags INJECTION tragen: INJECTION steht wörtlich in tasks[0].summary bzw. tasks[0].tags und nicht in `everything_but(result, "tasks")`; die Beschreibung erscheint gar nicht
    - read_task derselben Aufgabe mit INJECTION in einer Beschreibung über MAX_DESCRIPTION_BYTES: INJECTION nur in description, description_truncated true, kein Marker im Text
    - eine gefälschte Markerfolge im summary einer geteilten Aufgabe wird von without_marks entfernt
  </behavior>
  <action>Drei Fälle im Stil des Kalenderfalls ergänzen (respx, Fixture-Form aus 32-03). Danach volle Gates nach 32-RULES.md und TASK-01-Diff-Beweis. Commit "test(32-04b): injection corpus covers tasks from shared lists".</action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && export PYTHONPATH=src PYTHONUTF8=1 && uv run --no-sync pytest tests/unit/test_injection_corpus.py -q -o addopts="" --import-mode=importlib && uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib && uv run --no-sync ruff check . && uv run --no-sync ruff format --check . && uv run --no-sync vulture src scripts vulture_whitelist.py</automated>
  </verify>
  <acceptance_criteria>
    - Drei neue Korpusfälle grün; volle Gates nach 32-RULES.md Exit 0; TASK-01-Diff leer
  </acceptance_criteria>
  <done>Fremdtext aus geteilten Listen kommt nur als Daten an.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Assistent zu Schreibziel | list und parent kommen vom Modell |
| Connector zu Nextcloud PUT | neues Objekt in einer Sammlung, die andere Personen sehen können |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-32-04b-01 | Elevation of Privilege | Schreiben in geteilte Liste | mitigate | E4-Zielwahl, D-32-16, writable aus Discovery, Ablehnung vor dem Request; 403/404 als letzte Instanz |
| T-32-04b-02 | Tampering | Überschreiben | mitigate | put_new_object mit If-None-Match *, frische UUID |
| T-32-04b-03 | Tampering | ICS-Einschleusung über summary/description | mitigate | icalendar baut und escaped; Test auf genau eine VTODO-Komponente |
| T-32-04b-04 | Information Disclosure | Deck-Kalender als Ziel | mitigate | Discovery schließt app-generated-- aus; Test mit Deck-URI als list |
| T-32-04b-05 | Tampering | Prompt-Injektion aus geteilten Listen | mitigate | without_marks, Kappung, Korpus |
| T-32-04b-06 | Denial of Service | Erkennung der Tasks-App | mitigate | nur in zwei Fällen angefragt, Cache, wirft nie |
| T-32-SC | Tampering | Paketinstallationen | accept | keine neue Abhängigkeit |
</threat_model>

<verification>
- Anlegen, Zielwahl, Erkennung und Korpus getestet; EXPECTED_PUT_CALLS 6
- Gates grün; TASK-01-Diff leer; lokale Commits ohne Trailer
</verification>

<success_criteria>
- TASK-05, TASK-06 im Code erfüllt; TASK-03 komplett auf Unit-Ebene; D-32-10 und D-32-16 umgesetzt
</success_criteria>

<output>
Create `.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-04b-SUMMARY.md` when done; darin die Signatur von create_task, die Hinweistexte und welcher Erkennungsweg gebaut wurde.
</output>

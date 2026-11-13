---
phase: 33-aufgaben-aendern
plan: 03
subsystem: schreibschiene
tags: [tasks, caldav, etag, if-match, move, destruktiv-gate]
requires: ["33-02"]
provides:
  - "TodoObject.etag (aus getetag des REPORT und dem ETag-Kopf des GET), get_todo liefert TodoObject"
  - "tasks_read legt etag in die Antwort (Form wie vom Server, fehlt sie, kein Feld)"
  - "clients/tasks.put_existing_todo(client, creds, task_list, object_name, ics_bytes, etag) -> neue ETag oder leer"
  - "clients/tasks.move_todo(client, creds, source, target, object_name, etag) -> None, nur 201 ist Erfolg"
  - "Destruktiv-Gate: EXPECTED_PUT_CALLS = 7, TASK_MOVE, MOVE_HOMES, _move_gate, _put_pin_findings mit Gegenproben"
affects: [33-06, 33-07, 33-08, 33-09]
tech-stack:
  added: []
  patterns: ["Kopf als Literal-Dict, damit das AST-Gate ihn liest", "eigene Statusprüfer neben _check, kein zweiter Versuch", "Gegenprobe über dieselbe Prüffunktion wie das Gate"]
key-files:
  created:
    - .planning/phases/33-aufgaben-aendern/33-03-SUMMARY.md
  modified:
    - src/mcp_connector/nextcloud/clients/tasks.py
    - src/mcp_connector/tools/tasks.py
    - tests/unit/test_tasks_client.py
    - tests/unit/test_tasks_read.py
    - tests/unit/test_chatgpt_fetch.py
    - tests/contract/tool_classes.py
    - tests/contract/test_no_destructive_calls.py
    - tests/contract/test_tool_surface.py
    - vulture_whitelist.py
decisions:
  - "Werkzeugbeschreibung von tasks_read unverändert: das Feld heißt etag und steht in jeder Antwort mit ETag-Kopf; Mehrbytes im Budget 0"
  - "get_todo gibt ein TodoObject (object_name, ics, etag) zurück statt eines Tupels; die drei Aufrufer lesen .ics"
  - "Die normalisierte ETag wird auf den Parameter etag zurückgebunden (etag = dav.normalize_etag(etag)); der PUT-Pin verlangt genau diese Zeile vor dem PUT und If-Match auf den Namen etag"
  - "404 beim Schreiben trägt REASON_UNKNOWN_ID (wie die Fehlerlehre in errors.py), der Text sagt nur 'not found or no write permission'"
  - "Timeout beim Schreiben: REASON_TIMEOUT, Text 'Outcome unknown', Hinweis 'read the task again with tasks_read'"
metrics:
  completed: 2026-11-13
  tasks: 3
  duration: "ca. 20 min (21:50 bis 22:10 UTC)"
---

# Phase 33 Plan 03: ETag in tasks_read, bedingter PUT und bewachtes MOVE, Destruktiv-Gate auf 7 PUT und 2 MOVE Summary

`tasks_read` gibt die ETag des einen GET aus, `clients/tasks.py` hat genau einen überschreibenden PUT (`put_existing_todo`, `If-Match` auf eine normalisierte starke ETag) und genau ein MOVE (`move_todo`, `Overwrite: F` plus `If-Match`, nur 201 ist Erfolg), beide ohne zweiten Versuch und ohne eigenen Timeout; das Destruktiv-Gate zählt bewusst 7 PUT und pinnt die zwei MOVE per Syntaxbaum mit Gegenproben.

## Commits

| Task | Schritt | Commit | Inhalt |
|------|---------|--------|--------|
| 1 | RED | a57691c | test(33-03): etag in task reads |
| 1 | GREEN | 762d000 | feat(33-03): tasks_read returns the etag of the task |
| 2 | RED | cd27f7c | test(33-03): conditional task writes |
| 2 | GREEN | 8d65a51 | feat(33-03): compare-and-swap PUT and guarded MOVE for tasks |
| 3 | Test (umgekehrt) | aa94f00 | test(33-03): AST pins and counter-probes for task PUT and MOVE |

Alle als `street1983nk <k.cherif@outlook.de>` (Autor und Committer), ohne Trailer, ohne closes-Wörter, nur lokal, kein Push.

### Rote Tests der RED-Commits

- a57691c: 6 failed, nur in den drei geänderten Testdateien: `test_get_todo_returns_the_stored_bytes`, `test_get_todo_returns_the_etag_of_the_same_get_as_the_server_sent_it`, `test_query_todos_keeps_the_etag_of_every_object`, `test_a_todo_object_carries_no_etag_unless_one_is_given` (test_tasks_client.py), `test_read_returns_the_etag_of_its_get_as_the_server_sent_it` (test_tasks_read.py), `test_a_fetched_task_carries_no_etag_while_tasks_read_does` (test_chatgpt_fetch.py).
- cd27f7c: 43 failed, alle in test_tasks_client.py (fehlende `put_existing_todo`/`move_todo`); pyright meldete genau 2 Fehler, beide in dieser Datei (Zeilen 783, 787, unbekannte Attribute).

## Werte für die Folgepläne

- **EXPECTED_PUT_CALLS = 7** (vorher 6). Grund im Kommentar: der eine überschreibende PUT in `clients/tasks.put_existing_todo` (TMOD-01, D-33-03); kein Eintrag in `UNCONDITIONAL_PUTS`. Gegenprobe `test_a_planted_eighth_put_changes_the_count` (Zählung 8).
- **MOVE-Pin:** `MOVE_HOMES = {("nextcloud/clients/dav.py", "finish_chunked_upload"), ("nextcloud/clients/tasks.py", "move_todo")}`, `EXPECTED_MOVE_CALLS = 2`. `_move_gate` prüft: nur `.request("MOVE", ...)` an diesen zwei Stellen, je genau einmal; Literal-Kopf mit `"Overwrite": "F"` und `Destination`; in `TASK_MOVE` zusätzlich `If-Match` auf einen Namen (keine Konstante); `method="MOVE"`, entpackte Keywords und `**` im Kopf werden gemeldet; Zahl der `"MOVE"`-Literale je Heimatdatei gleich der Zahl der Aufrufe, kein Literal anderswo. Im Quelltext: `grep -rc '"MOVE",' src` summiert 2.
- **PUT-Pin:** `_put_pin_findings`: `caldav.put_new_object` trägt `If-None-Match: *` und kein `If-Match`; `tasks.put_existing_todo` hat genau einen `.put(`, `If-Match` auf den Namen `etag`, davor `etag = dav.normalize_etag(etag)`, kein `If-None-Match`; nie beides.
- **Budget:** unverändert 19683 Bytes mit allen Schaltern an (28 Werkzeuge), Standard 18770 (27), Budget 22000. Mehrbytes `tasks_read`: 0 (Beschreibung nicht geändert, die ETag ist ein Antwortfeld, kein Schemafeld). Kein Neuverankern nötig.
- **Schreib-Rückgabe:** `put_existing_todo` gibt die ETag aus dem Kopf `etag` zurück oder `""`; leer heißt nach 33-01c (`etag_nach_veraendertem_text=fehlt`): der Server hat den Text verändert, der Werkzeugplan muss dann neu lesen bzw. keine ETag melden (Pitfall 10).
- **Statuswörter** (für Werkzeugtests 33-06 bis 33-08): PUT 200/204 ok; 412 `ConflictError` "...changed since it was read (412)", Hinweis "read the task again with tasks_read"; 404 "not found or no write permission" (REASON_UNKNOWN_ID); 403 REASON_PERMISSION_DENIED; 5xx "server error (<n>) ... the outcome is not known"; Timeout REASON_TIMEOUT "Outcome unknown". MOVE nur 201; 204 "replaced an existing object"; 409 `ConflictError` mit "UID"; 412 `ConflictError` "changed since it was read or the target name is already taken"; 404, 403, 5xx, Timeout wie beim PUT; 3xx, 401, 429 über das vorhandene `_check`.
- vulture: `put_existing_todo` und `move_todo` stehen befristet in `vulture_whitelist.py` (Begründung "used by tasks_complete/tasks_update (33-06/33-07) and tasks_move (33-08)"); der erste aufrufende Werkzeugplan entfernt den jeweiligen Eintrag.

## Gegenproben rot gegen gepflanzte Fehler (Task 3, umgekehrter Nachweis)

Mutationen der echten `clients/tasks.py` im Speicher, geprüft mit den Gate-Funktionen (Skript im Scratchpad, danach gelöscht). `text_gate` ist die Nadel-Prüfung `_violations` allein; sie lässt jede dieser Mutationen durch, erst die Syntaxbaum-Pins werden rot:

```
REAL move_gate: [] puts: 7
MUTATION move ohne Overwrite: rot=True move_gate=1 put_pin=[] put_count=7 text_gate=0
    nextcloud/clients/tasks.py:574 in move_todo: MOVE without the literal header Overwrite: F
MUTATION move Overwrite T: rot=True move_gate=1 put_pin=[] put_count=7 text_gate=0
    nextcloud/clients/tasks.py:574 in move_todo: MOVE without the literal header Overwrite: F
MUTATION move If-Match *: rot=True move_gate=1 put_pin=[] put_count=7 text_gate=0
    nextcloud/clients/tasks.py:574 in move_todo: task MOVE without If-Match on a variable ETag
MUTATION put If-Match *: rot=True move_gate=0 put_pin=['put_existing_todo: compare-and-swap PUT without If-Match on the variable etag'] put_count=7 text_gate=0
MUTATION put ohne normalize: rot=True move_gate=0 put_pin=['put_existing_todo: etag is not normalized before the PUT'] put_count=7 text_gate=0
MUTATION zweites MOVE in tasks.py: rot=True move_gate=2 put_pin=[] put_count=7 text_gate=0
    nextcloud/clients/tasks.py:745 in relocate_again: MOVE outside its two named places
    expected exactly one MOVE in each of [...dav.py finish_chunked_upload, ...tasks.py move_todo], found [... plus tasks.py relocate_again]
MUTATION achter PUT: rot=True move_gate=0 put_pin=[] put_count=8 text_gate=0
```

Gegenrichtung: die Prüffunktionen `_move_gate` und `_put_pin_findings` durch "findet nie etwas" ersetzt, dann die neuen Gegenproben-Tests aufgerufen:

```
NEUTRALISIERT test_the_move_gate_flags_each_planted_task_move: rot=11/11
NEUTRALISIERT test_the_put_pin_flags_each_planted_task_put: rot=5/5
NEUTRALISIERT test_the_put_pin_leaves_the_honest_forms_and_flags_swapped_ones: rot=1/1
NEUTRALISIERT test_the_move_gate_flags_a_move_in_another_file_and_leaves_the_honest_form: rot=1/1
NEUTRALISIERT test_the_text_gate_alone_would_let_a_second_task_move_line_through: rot=1/1
NEUTRALISIERT test_every_move_lives_in_its_two_named_places_with_its_guards: rot=0/1
NEUTRALISIERT test_the_gate_would_notice_a_destructive_call_in_the_task_client: rot=0/1
```

Die beiden mit 0/1 sind der saubere Lauf über den echten Code bzw. die Nadel-Gegenprobe ohne diese Funktionen; sie sind die Positivseite, ihre Gegenproben sind die Zeilen darüber. Gepflanzte MOVE-Fälle (11): ohne Overwrite, `"T"`, `If-Match: "*"`, konstante ETag, ohne If-Match, zweites MOVE in `move_todo`, zweites MOVE in anderer Funktion von clients/tasks.py, `method="MOVE"`, entpackte Keywords, `**` im Kopf, Verb in einer Variablen; dazu MOVE in `tools/tasks.py` und fehlendes MOVE. Gepflanzte PUT-Fälle (5): `If-Match: "*"`, konstante ETag, ohne Normalisierung, beide Vorbedingungen, zwei PUT; `If-Match: "*"` fällt zusätzlich in `_unconditional_puts`.

## Inventarzeilen (raw/33-01-inventar.txt, ZUORDNUNG ... plan=33-03)

Alle 28 Zeilen in `tests/contract/test_no_destructive_calls.py` (Zeilennummern Stand 33-01) abgehakt:

- :4 Modul-Docstring: Absatz ergänzt, Löschen, Umbenennen und Teilen bleiben verboten, Überschreiben und Umziehen nur an den benannten Stellen, immer bedingt.
- :11 Satz über den Docstring von dav.py: bleibt wahr (dav.py implementiert weiter kein MOVE außer der Chunk-Montage), unverändert.
- :32 Kommentar zu den Großbuchstaben-Nadeln: unverändert gültig.
- :86, :88 `FORBIDDEN["MOVE"]`: Text jetzt "no tool may rename anything, and a MOVE lives only in its two named places".
- :139, :140, :142 Kommentar und `CHUNK_ASSEMBLY_MOVE`: Kommentar auf zwei MOVE umgeschrieben, `TASK_MOVE` daneben.
- :387 `_code_lines`-Docstring: unverändert gültig.
- :421, :424 `_violations`: Ausnahme gilt für `CHUNK_ASSEMBLY_MOVE` und `TASK_MOVE`, weiter nur auf exakten Zeilentext `"MOVE",`.
- :440, :447 Haupttest: unverändert, läuft grün mit der zweiten Ausnahme.
- :450, :451 Datei-PUT-Pin: unverändert; daneben neuer Pin `test_task_writes_keep_create_and_compare_and_swap_puts_distinct`.
- :470, :471 `UNCONDITIONAL_PUTS`: unverändert, kein dritter Eintrag.
- :480 `EXPECTED_PUT_CALLS`: 7 mit Begründungskommentar.
- :506, :560, :571, :573 PUT-Prüfung und Zählung: unverändert, zählen jetzt 7.
- :612 Kommentar zu `MKCOL_HOME`: unverändert gültig.
- :821, :830, :831, :836, :841 Test `test_the_gate_would_notice_a_destructive_call_in_real_code`: Docstring verweist auf die gleiche Probe für clients/tasks.py (`test_the_gate_would_notice_a_destructive_call_in_the_task_client`: sauberer Lauf, genau eine Zeile `"MOVE",`, injiziertes DELETE und MOVE in anderer Schreibweise gemeldet).

## Gates (Endstand nach aa94f00)

- pytest unit+contract: 6616 passed, 35 skipped (nach Task 1: 6548, nach Task 2: 6592)
- check_tool_budget: Exit 0, 19683 Bytes, 28 Werkzeuge, Budget 22000; Standard 18770, 27
- ruff check: grün; ruff format --check: 396 Dateien formatiert
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0
- TASK-01: Positivkontrolle SHA und Vorfahre ok, `git diff "$B"` über caldav.py, calendar.py und die vier Kalendertests: 0 Zeilen; Gegentreffer im selben Werkzeug: clients/tasks.py 276 Diffzeilen
- Pitfall 1: in `src/` außer der einen Zeile `"MOVE",` in `move_todo` keine Teilstrings MOVE/DELETE/COPY/PROPPATCH in clients/tasks.py und tools/tasks.py; kein U+2013/U+2014 in den berührten Dateien (Gegenkontrolle mit gepflanztem Zeichen gezählt)
- Kein Docker gebraucht, kein Container gestartet

## Deviations from Plan

1. [Rule 1, veralteter Kommentar] `tests/contract/test_tool_surface.py` Z. 88-92 sagte "EXPECTED_PUT_CALLS stays six"; im GREEN-Commit 8d65a51 nachgezogen (Datei nicht in files_modified).
2. `src/mcp_connector/server/reg_tasks.py` und `scripts/check_tool_budget.py` (in files_modified) blieben unverändert: der Plan erlaubt die Beschreibungsänderung nur, wenn das Modell die ETag sonst nicht fände; das Antwortfeld heißt `etag`, die Werkzeuge ab 33-06 nennen in ihren Parametern "etag from tasks_read". Budget damit unverändert, kein Neuverankern.
3. Die Hilfe `_with(**planted)` der Gegenproben schreibt Modulpfade als Schlüsselwörter (`nextcloud__clients__tasks_py=`); reine Testhilfe.
4. Die Zeilenverweise in `tool_classes.py` wurden neu gezogen (`tasks_read` :603-645, `tasks_create` :810-821) und der Text von `tasks_read` nennt jetzt die ETag.

## Known Stubs

Keine. `put_existing_todo` und `move_todo` sind bis 33-06/33-08 ohne Aufrufer (geplant, vulture-Eintrag mit Begründung).

## Threat Flags

Keine neue Fläche über das Threat Model hinaus: beide Schreibwege existieren nur in der Client-Schicht, kein Werkzeug ruft sie bisher; T-33-03-01 bis -04 sind umgesetzt (If-Match normalisiert, Overwrite F als Literal, nur 201, Meldungen nur mit Listennamen, Timeout "Outcome unknown").

## Self-Check: PASSED

Commits a57691c, 762d000, cd27f7c, 8d65a51, aa94f00 im Log; `async def move_todo` und `async def put_existing_todo` in clients/tasks.py; `EXPECTED_PUT_CALLS = 7` und `TASK_MOVE` im Gate; Scratchpad-Ordner p33 gelöscht.

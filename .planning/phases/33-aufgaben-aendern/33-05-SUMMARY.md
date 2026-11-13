---
phase: 33-aufgaben-aendern
plan: 05
subsystem: kettenlogik
tags: [tasks, kette, nachfahren, etag, if-match, chain_cap]
requires: ["33-01c", "33-03", "33-04"]
provides:
  - "tools/tasks.CHAIN_CAP = 50 mit MESSWERT-Kommentar (Rohzeile aus raw/33-01-messung.txt wörtlich)"
  - "tools/tasks.chain_entries(task_list, objects) -> (entries, skipped): Felder von _read_todo plus id, object_name, etag, text"
  - "tools/tasks.descendants_post_order(root_uid, entries): Nachfahren iterativ in Nachordnung, Geschwister nach Objektname"
  - "tools/tasks.check_chain(task_list, descendants): Vorprüfung ohne Anfrage (Schreibrecht, CHAIN_CAP, ics_edit.inspect, recurring)"
  - "tools/tasks.read_chain_list(clients, task_list): ein REPORT ohne Vorfilter unter PER_LIST_TIMEOUT"
  - "tools/tasks.run_chain(task_list, root, root_etag, descendants, decide, write, skipped=) -> ChainReport"
  - "tools/tasks.ChainSkip (UNCHANGED, LEFT_ALONE), ChainDecide, ChainWrite, ChainReport.as_answer()"
  - "tests/unit/task_store.py: TaskStore mit If-Match, ETag im GET, REPORT- und MOVE-Route, Zähler offener Schreibaufrufe"
affects: [33-06, 33-07, 33-08]
tech-stack:
  added: []
  patterns: ["Schreibfunktion als Parameter des Laufs", "Nachordnung per Stapel statt Rekursion", "Zähler offener Aufrufe im async side_effect mit Positivkontrolle"]
key-files:
  created:
    - tests/unit/test_tasks_chain.py
    - tests/unit/task_store.py
    - .planning/phases/33-aufgaben-aendern/33-05-SUMMARY.md
  modified:
    - src/mcp_connector/tools/tasks.py
    - vulture_whitelist.py
    - pyproject.toml
decisions:
  - "CHAIN_CAP = 50 aus MESSWERT chain_cap=50 (33-01c, OWNERFRAGE entfaellt)"
  - "Vorprüfung nutzt ics_edit.inspect je Nachfahr: mehrere VTODO, kaputter Text, fehlende UID und doppelte Einzelfelder lehnen die ganze Kette vor dem ersten Schreiben ab"
  - "Die genannte Aufgabe wird von check_chain nicht geprüft; das bleibt beim Werkzeugplan (33-06 bis 33-08)"
  - "Stoppgrund aus den Fehlern von clients/tasks.py: ConflictError mit '(409)' heißt uid_conflict, sonst conflict; REASON_UNKNOWN_ID not_found_or_read_only; REASON_PERMISSION_DENIED und EditRefused refused; REASON_TIMEOUT und httpx.RequestError outcome_unknown; alles andere server_error"
  - "Der Bericht trägt nie einen Servertext, nur eigene Sätze, task:-Ids und _list_info"
metrics:
  completed: 2026-11-13
  tasks: 2
---

# Phase 33 Plan 05: Gemeinsame Kettenlogik für Abhaken und Verschieben Summary

Nachfahren einer Aufgabe werden aus einem REPORT der ganzen Liste iterativ in Nachordnung bestimmt (exakte UID, nur `RELATED-TO` ohne `RELTYPE` oder mit `PARENT`, Zyklenschutz), vor dem ersten Schreiben gegen `CHAIN_CAP = 50`, Schreibrecht, Wiederholung und Bearbeitbarkeit geprüft und dann streng nacheinander geschrieben, die genannte Aufgabe zuletzt; beim ersten Fehler stoppt der Lauf mit einem Bericht aus `task:`-Ids, Grund und Satz. Noch kein Werkzeug registriert.

## Commits

| Task | Schritt | Commit | Inhalt |
|------|---------|--------|--------|
| 1 | RED | f77edec | test(33-05): descendants and pre-checks of a task chain |
| 1 | GREEN | ed73cd2 | feat(33-05): descendants in post-order with cap and pre-checks |
| 2 | RED | 4966428 | test(33-05): sequential task chain that stops at the first failure |
| 2 | GREEN | 83afdaf | feat(33-05): task chain runner with an honest report |

Alle als `street1983nk <k.cherif@outlook.de>` (Autor und Committer), ohne Trailer, ohne closes-Wörter, nur lokal, kein Push.

### Rote Tests der RED-Commits

- f77edec: 20 failed, alle in `tests/unit/test_tasks_chain.py` (fehlende `CHAIN_CAP`, `chain_entries`, `descendants_post_order`, `check_chain`); pyright-Befunde nur in dieser Datei.
- 4966428: 29 failed, alle in `tests/unit/test_tasks_chain.py` (fehlende `read_chain_list`, `run_chain`, `ChainSkip`, `ChainReport`; eine davon der Quelltexttest auf `run_chain`); pyright: 10 Fehler, alle in dieser Datei. Die 20 Tests aus Task 1 und die Positivkontrolle des Überlappungszählers liefen grün.

## Werte für die Folgepläne

- **CHAIN_CAP = 50**, Herkunft: `MESSWERT chain_cap=50 regel=derive_budget(max_gesamt_s)<=30 budget_s=8 quelle=nc35+nc32 (D-33-10 bestätigt)` aus `raw/33-01-messung.txt` (33-01c, 2026-11-13), wörtlich im Kommentar über der Konstante; ein Test liest die Rohzeile aus der Datei und findet sie im Kommentar.
- **Kettenbericht bei voller Kette:** 50 Nachfahren mit UUID-Objektnamen geändert, Stopp mit 412 an der genannten Aufgabe: `MESSWERT kettenbericht_bytes=3641 ids=50` (JSON, UTF-8, `ensure_ascii=False`, Test `test_the_size_of_a_full_chain_report`, Grenze im Test 8000).
- **Aufruf für 33-06 bis 33-08:** `entries, skipped = await read_chain_list(clients, task_list)`; die genannte Aufgabe in `entries` suchen (`object_name`); `descendants = descendants_post_order(root["uid"], entries)`; `check_chain(task_list, descendants)`; `report = await run_chain(task_list, root, etag_des_assistenten, descendants, decide, write, skipped=skipped)`; `report.as_answer()` in die Antwort. `decide(entry)` gibt neue Bytes, `ChainSkip.UNCHANGED` (Zielzustand) oder `ChainSkip.LEFT_ALONE` (CANCELLED beim Abhaken, D-33-14) zurück und darf `ics_edit.EditRefused` werfen; `write(entry, payload, etag)` ruft `put_existing_todo` bzw. `move_todo` (Payload dann `b""`) und gibt die neue ETag oder `""` zurück.
- **Antwortform** `as_answer()`: `list` (`_list_info`), `changed` (Ids in Reihenfolge, die genannte Aufgabe zuletzt, wenn geschrieben), `unchanged` (Zahl), `left_alone` (nur wenn nicht leer), `skipped` (nur wenn > 0), bei Stopp `failed`, `reason` und `message`. `message` nennt die Id, an der gestoppt wurde, den Grund, die Zahl der schon geänderten Nachfahren, "the named task <id> was not changed" (außer wenn die genannte Aufgabe selbst scheiterte) und "read the task again with tasks_read". `report.root_etag` ist die neue ETag der genannten Aufgabe nach ihrem Schreiben (`None` ohne Schreiben, `""` ohne ETag-Kopf: dann neu lesen, Pitfall 10).
- **Gründe:** `conflict`, `uid_conflict`, `not_found_or_read_only`, `refused`, `server_error`, `outcome_unknown`.
- **Timeout beim REPORT:** `ToolError` mit "The task list did not answer in time (2 seconds): nothing was changed in <Liste>.", `REASON_TIMEOUT`; kein Schreibaufruf.
- **Testhilfe** `tests/unit/task_store.py` (`TaskStore`, `mount`, `multistatus`, `list_url`): `fail[name]` pflanzt einen Status oder eine Ausnahme für den nächsten Schreibaufruf eines Objekts, `writes` hält (Methode, Objektname, If-Match), `max_open` die größte Zahl gleichzeitig offener Schreibaufrufe. Der REPORT schreibt CR als `&#13;`, sonst macht der XML-Parser aus CRLF ein LF.

## Gates (Endstand nach 83afdaf)

- pytest unit+contract: 7580 passed, 35 skipped (nach Task 1: 7550 passed, 35 skipped)
- check_tool_budget: Exit 0, Standard 18770 Bytes, 27 Werkzeuge; kein neues Werkzeug, Budget unverändert
- ruff check: grün; ruff format --check: 400 Dateien formatiert
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0
- `! grep -nE "gather\(" src/mcp_connector/tools/tasks.py | grep -iE "put|move|chain"`: kein Treffer; zusätzlich prüft `test_no_write_runs_under_a_time_budget_or_side_by_side` den Quelltext von `run_chain` (enthält `await write(`, weder `timeout` noch `gather`), und `test_writes_never_overlap` zeigt `max_open == 1` bei 13 Schreibaufrufen; Positivkontrolle `test_the_overlap_counter_sees_parallel_writes` mit zwei `put_existing_todo` per `asyncio.gather` zeigt `max_open == 2`.
- TASK-01: Positivkontrolle SHA und Vorfahre ok, `git diff "$B"` über caldav.py, calendar.py und die vier Kalendertests: 0 Zeilen; Gegentreffer `src/mcp_connector/tools/tasks.py`: 370 Diffzeilen.
- Pitfall 1: in `src/mcp_connector/tools/tasks.py` keine Teilstrings MOVE, DELETE, COPY, PROPPATCH; kein U+2013/U+2014 in den berührten Dateien.
- Kein Docker gebraucht, kein Container gestartet.

## Deviations from Plan

1. [Rule 3, Testhilfe] Die Store-Erweiterung liegt als gemeinsame Testhilfe in `tests/unit/task_store.py` (vom Plan erlaubt). Der Kommentar in `pyproject.toml` über die Hilfsmodule von `tests/unit` sagte "genau eines"; im RED-Commit 4966428 auf zwei nachgezogen (Datei nicht in files_modified).
2. [Rule 2, Vorprüfung] `check_chain` prüft jeden Nachfahren zusätzlich mit `ics_edit.inspect` (nicht nur "mehrere VTODO"): kaputter Text, fehlende UID und doppelte Einzelfelder lehnen ebenfalls vor dem ersten Schreiben ab, damit `apply` in 33-06 nicht mitten in der Kette scheitert.
3. [Rule 2, Lauf] Wirft `decide` unterwegs `EditRefused`, stoppt der Lauf ohne Anfrage mit `reason=refused` (Test `test_an_edit_refused_on_the_way_stops_without_a_request`).
4. Ein `ConflictError` des Clients trägt keinen eigenen Grund-Code; `uid_conflict` wird an "(409)" im Text von `_check_relocation` erkannt. Test für 409 beim Verschieben vorhanden; ändert sich der Text in `clients/tasks.py`, wird dieser Test rot.
5. PUT mit 409 ist nicht als eigener Fall getestet: `_check_change` kennt 409 nicht und meldet "unexpected status", der Lauf ordnet das `server_error` zu.
6. Drei Fehler in eigener Testhilfe und eigenen RED-Tests im GREEN-Commit 83afdaf behoben: der Quelltexttest suchte nach `run_chain` drei Zeilenumbrüche, die am Dateiende fehlen; die langsame REPORT-Route muss nach `mount` gesetzt werden, weil respx eine Route mit gleichem Muster ersetzt. Außerdem schrieb `task_store.multistatus` CR nicht als `&#13;`, der Parser lieferte LF statt CRLF; jetzt als Zeichenreferenz. Ob der echte REPORT von Nextcloud CRLF so überträgt, ist hier nicht live geprüft (offener Punkt für 33-06: der Kettenlauf baut den neuen Text aus dem REPORT-Text; ein Rundlauftest mit CRLF gegen nc35 sollte das belegen).

## Known Stubs

Keine. `chain_entries`, `descendants_post_order`, `check_chain`, `read_chain_list`, `run_chain` und `as_answer` sind bis 33-06 ohne Aufrufer (geplant, vulture-Einträge mit Begründung).

## Threat Flags

Keine neue Fläche: kein Werkzeug registriert, keine neue Anfrageart. T-33-05-01 bis -04 umgesetzt (Vorprüfung vor dem ersten Schreiben, Nachordnung, genannte Aufgabe zuletzt, besuchte Menge, CHAIN_CAP, Zeitbudget nur um den REPORT, If-Match je Objekt ohne Retry, streng seriell im Test belegt).

## Self-Check: PASSED

Dateien test_tasks_chain.py, task_store.py und diese SUMMARY vorhanden; Commits f77edec, ed73cd2, 4966428, 83afdaf im Log.

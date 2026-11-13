---
phase: 33-aufgaben-aendern
plan: 07
subsystem: tasks-update
tags: [tasks, tasks_update, etag, if-match, ics_edit, rundlauf, schalter, budget, utf-8]
requires: ["33-02", "33-03", "33-04", "33-05", "33-06"]
provides:
  - "tools/tasks.update_task(clients, *, task_id, etag, summary, description, due, start, priority, tags, parent) -> dict"
  - "tools/tasks._task_key und _read_for_change: gemeinsamer Lader der ändernden Werkzeuge (complete_task nutzt ihn jetzt auch)"
  - "Werkzeug tasks_update hinter config.tasks_update_enabled(), MODIFY_EXISTING, @graceful, 1324 Bytes"
  - "Allowlist tasks_update: {due, etag, parent, priority, start, tags, task_id}"
  - "Kettenvorprüfung lehnt einen Nachfahren ab, dessen Text kein UTF-8 ist"
affects: [33-08, 33-09, 33-10]
tech-stack:
  added: []
  patterns: ["Prüfungen von tasks_create auf dem zusammengeführten Stand", "Unterschied vor dem Schreiben gegen den gelesenen Stand, sonst kein PUT", "Rundlauf-Beweis aus 33-04 auf Werkzeugebene"]
key-files:
  created:
    - tests/unit/test_tasks_update.py
    - .planning/phases/33-aufgaben-aendern/33-07-SUMMARY.md
  modified:
    - src/mcp_connector/tools/tasks.py
    - src/mcp_connector/server/reg_tasks.py
    - src/mcp_connector/audit/allowlist.py
    - scripts/check_tool_budget.py
    - vulture_whitelist.py
    - tests/contract/optional_surface.py
    - tests/contract/test_tool_surface.py
    - tests/contract/test_tool_classes.py
    - tests/contract/tool_classes.py
    - tests/unit/test_exapp_tasks_update_switch.py
    - tests/unit/test_tasks_chain.py
    - tests/unit/test_tasks_complete.py
    - README.md
    - README.de.md
    - README.fr.md
decisions:
  - "Leerraum gilt wie leer: description, due, start und parent aus nur Leerraum entfernen das Feld; tags, die nach dem Bereinigen leer sind, entfernen CATEGORIES"
  - "Eine vorhandene schwebende Zeit oder eine Zeit mit TZID neben einer neuen UTC-Zeit wird abgelehnt (Hinweis: due und start zusammen setzen); eine vorhandene UTC-Zeit wird verglichen"
  - "DURATION vorhanden: jede Änderung an due oder start abgelehnt, auch das Entfernen"
  - "Kein Unterschied heißt: gleicher Text, gleiche Tags in gleicher Reihenfolge über alle CATEGORIES-Zeilen, gleicher Zeitpunkt in gleichem Werttyp (zonierte Zeit gleichen Moments zählt als gleich, schwebende nie), Feld schon weg; DESCRIPTION leeren zählt auch dann als Änderung, wenn nur X-ALT-DESC steht"
  - "Zeiten mit Sekundenbruchteilen werden abgelehnt statt abgeschnitten"
  - "Antwort: id, list, changed (Feldnamen in fester Reihenfolge), removed und html_description_removed nur wenn zutreffend, etag nur aus dem PUT-Kopf, sonst note"
  - "Budget 25000 (Messung 21587 mit allen Schaltern an plus 15 Prozent, auf 500 aufgerundet)"
metrics:
  completed: 2026-11-14
  tasks: 2
---

# Phase 33 Plan 07: tasks_update Summary

`tasks_update(task_id, etag, summary, description, due, start, priority, tags, parent)` ändert oder entfernt genau die genannten Felder einer Aufgabe mit `If-Match` auf die ETag aus `tasks_read`, prüft wie `tasks_create` auf dem Stand nach der Änderung, schreibt ohne Unterschied nichts und hält den Rundlauf-Beweis aus 33-04 auf Werkzeugebene über alle Fixtures; registriert nur bei eingeschaltetem `NC_MCP_TASKS_UPDATE`. Dazu die Zusatzkorrektur: ein Nachfahr, dessen Text kein UTF-8 ist, lehnt die ganze Kette vor dem ersten Schreiben ab.

## Commits

| Teil | Schritt | Commit | Inhalt |
|------|---------|--------|--------|
| UTF-8 | RED | 9ad7b54 | test(33-07): a subtask that is not UTF-8 refuses the whole chain |
| UTF-8 | GREEN | e047afb | fix(33-07): refuse a task chain whose subtask text is not UTF-8 |
| 1 | RED | d086933 | test(33-07): tasks_update behaviour and round trip |
| 1 | GREEN | eb3c1ca | feat(33-07): change or clear named fields of a task |
| 2 | RED | e7e3cdc | test(33-07): tasks_update in the surface gates |
| 2 | GREEN | 05dd7b2 | feat(33-07): register tasks_update behind the tasks_update switch |

Alle als `street1983nk <k.cherif@outlook.de>` (Autor und Committer), ohne Trailer, ohne closes-Wörter, nur lokal, kein Push. STATE, ROADMAP und REQUIREMENTS nicht angefasst (Vorgabe der Hauptsitzung).

### Rote Tests der RED-Commits

- 9ad7b54: 3 failed (2 in `test_tasks_chain.py`, 1 in `test_tasks_complete.py`); die Positivkontrolle `test_the_same_descendant_in_utf8_passes_the_check` lief grün. pyright und vulture grün.
- d086933: 444 failed, 1 passed, alle in `tests/unit/test_tasks_update.py` (`AttributeError: ... no attribute 'update_task'`); pyright: 5 Fehler, alle in dieser Datei.
- e7e3cdc: 8 failed: `test_tool_classes.py` (4, über die geänderte Hilfsdatei `tool_classes.py`), `test_tool_surface.py` (1), `test_exapp_tasks_update_switch.py` (3). pyright grün.

## Die UTF-8-Korrektur (Zusatzauftrag)

`chain_entries` (33-05) dekodierte Nachfahren mit `errors="replace"`; ein ungültiges Byte wäre beim Abhaken als U+FFFD dauerhaft gespeichert worden. Jetzt: strenge Dekodierung, bei Fehler `text = None` (der Eintrag bleibt, er ist ein Nachfahr, und wird nicht als `skipped` versteckt); `check_chain` lehnt ihn vor dem ersten Schreiben ab: "The subtask task:... cannot be changed safely: its text is not UTF-8.", Hinweis "Nothing was changed. ...", gleiche Form wie bei der genannten Aufgabe. Belegt auf Kettenebene (Eintrag ohne Text, Ablehnung mit Id, Positivkontrolle mit gültigem UTF-8) und auf Werkzeugebene (`tasks_complete` mit einem Enkel in Latin-1: ein REPORT, null PUT). Der REPORT des Teststores kann ein solches Byte über XML nicht tragen, deshalb gibt der Werkzeugtest die Objekte über ein ersetztes `query_todos` mit den gespeicherten Bytes weiter. `tasks_update` braucht die Nachfahren nur für die Eltern-Prüfung und schreibt keinen Nachfahren.

## Werkzeug und Budget

- Schema `tasks_update` mit allen Schaltern an: **1324 Bytes** (Decke 1400, Prototyp 1368); keine Kürzung nötig.
- Budgetzeilen wörtlich:

```
tools/list with every switch on: 21587 bytes, 30 tools, budget 25000
  tasks_create: 1380 bytes
  files_upload: 1377 bytes
  tasks_update: 1324 bytes
  mail_browse: 1237 bytes
  calendar_create_event: 1165 bytes
control, standard state: 18770 bytes, 27 tools
```

- Kommentar im Skript: "Measurement 2026-11-14, with tasks_update, every switch on: 21587 bytes, 30 tools", Budget "21587 + 15 percent = 24825.05, rounded up to the next 500 = 25000 bytes". `MAX_TOOL_BYTES` bleibt 1400.
- Beschreibung: "Change fields of a task; needs its etag from tasks_read. Omit or null keeps a field, an empty value clears it ("", [], priority 0); summary cannot be empty. Times with offset or Z, dates as YYYY-MM-DD." Kein Parameter `list`, kein `timezone`, kein Status.

## Umgesetzte Entscheide

- D-33-03: `normalize_etag` vor jeder Anfrage, Vergleich mit der ETag des GET, `If-Match` beim PUT, 412 ohne zweiten Versuch (Test mit gepflanztem 412: genau ein PUT).
- D-33-07, D-33-15: weglassen oder null bleibt, leer entfernt (`""`, `[]`, `priority=0`), leerer Titel abgelehnt; Entfernen in der gemessenen Form über `ics_edit` (Zeile weg, Beschreibung als leere `DESCRIPTION:`-Zeile); Zeiten in UTC mit `Z`, Daten als `VALUE=DATE`, Fälligkeit als Datum bleibt der genannte Tag.
- D-33-13: Beschreibung gesetzt oder entfernt auf `HTML_DESCRIPTION`: `X-ALT-DESC` und `ALTREP` weg, `html_description_removed: true`; der Semantik-Beweis meldet ohne benannte Ausnahme genau `X-ALT-DESC`, mit ihr nichts. Eine andere Änderung lässt beides stehen.
- TMOD-04: Prüfungen von `tasks_create` wiederverwendet (`_parse_task_time`, `_check_times` mit `zone=None`, `_check_priority`, `_clean_tags`, `_parse_parent`), Elternaufgabe gleiche Liste, nicht selbst (vor der Anfrage und per UID), kein Nachfahr (ein REPORT, `descendants_post_order` aus 33-05).
- TMOD-02: genau ein PUT je Änderung; Differenz genau {Feld} plus LAST-MODIFIED und DTSTAMP (ENTSCHEID pflegefelder_entfernen).

## Rundlauf auf Werkzeugebene

- Matrix: 24 Objekte (alle Fixtures der Tasks-App außer `recurring.ics` plus die 9 Handobjekte aus 33-04) mal 15 Fälle (je Feld setzen; due und start je als Zeit und Datum; entfernen von description, due, start, priority, tags, parent) = 360 Tests: 239 mit PUT (Byte-Beweis gegen den auf CRLF gebrachten Vorzustand und Semantik-Beweis je ohne Befund, Werte mit icalendar zurückgelesen, beide Pflegefelder gleicher UTC-Zeitpunkt), 108 ohne Unterschied (kein PUT, `changed: []`), 13 abgelehnt durch die Prüfung auf dem Endstand (kein PUT). Die Erwartung "abgelehnt" und "schon so" rechnet der Test selbst mit icalendar aus, nicht über die Werkzeuglogik.
- Abgleich mit der Tasks-App (`line_diff`): Entfernen von due, start, description, priority, tags und parent: 6 von 6 gleich. Für due und parent gibt es keinen gemessenen Vorzustand als Datei; der Vorzustand ist das App-Objekt plus die eine Zeile und mit früheren Pflegefeldern.
- Gegenproben (Mutation, danach zurückgesetzt): Endstandsprüfung aus: 24 rot; "kein Unterschied" aus: 118 rot; `X-ALT-DESC` nicht entfernt: 2 rot; Zeilenenden der Eingabe nicht normalisiert: 1 rot.

## Gates (Endstand nach 05dd7b2, alle Exit 0)

- pytest unit+contract: 8091 passed, 35 skipped (nach Task 1: 8087 passed, 35 skipped; nach der UTF-8-Korrektur: 7642 passed, 35 skipped)
- Plan-Verify Task 1: test_tasks_update + test_tasks_create + test_ics_edit (+ test_tasks_complete, test_tasks_chain): 1537 passed
- `python -W error` über test_tasks_update, test_tasks_chain, test_tasks_complete (mit anyio, nur die bekannte `PytestRemovedIn10Warning` des Plugins ausgenommen): 553 passed
- check_tool_budget: Exit 0 (Zeilen oben)
- ruff check grün; ruff format --check: 402 Dateien formatiert
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0; `grep -q '"tasks_update"' src/mcp_connector/audit/allowlist.py`: Treffer
- TASK-01: SHA-Form und Vorfahr ok, Diff über caldav.py, calendar.py und die vier Kalendertests 0 Zeilen; Gegentreffer tools/tasks.py (833 Einfügungen gegen die Basis)
- Pitfall 1: keine Teilstrings MOVE/DELETE/COPY/PROPPATCH in tools/tasks.py, reg_tasks.py, allowlist.py; kein U+2013/U+2014 in den berührten Dateien
- Kein Docker gebraucht, kein Container gestartet

## Deviations from Plan

1. [Zusatzauftrag der Hauptsitzung] UTF-8-Korrektur in `chain_entries`/`check_chain` als eigenes RED/GREEN-Paar vor dem Werkzeug (siehe oben); berührt `test_tasks_chain.py` und `test_tasks_complete.py` (nicht in files_modified).
2. [Rule 1, Wiederverwendung] Discovery, Schreibrecht, GET, ETag-Vergleich, UTF-8, `inspect` und Wiederholung von `complete_task` in `_task_key` und `_read_for_change` ausgelagert; `update_task` und `complete_task` nutzen denselben Lader, Tests von `tasks_complete` unverändert grün (55 passed).
3. [Rule 2, Eingabe] Sekundenbruchteile in due/start werden abgelehnt (ics_edit hätte sonst nach der Prüfung abgelehnt); `tags` als einzelner Text statt Liste wird abgelehnt.
4. [Rule 1, eigene Tests im GREEN-Commit eb3c1ca] Drei Fehler im RED-Test behoben: konstruierter Vorzustand für den App-Abgleich trug die Pflegefelder des Nachzustands; ein Ausweg-Test entfernte ein nicht vorhandenes `DUE`; die Leck-Prüfung der Antwort schlug auf die ETag des Teststores an, die dessen Listen-URI enthält (die ETag kommt vom Server, die Antwort sonst nennt keine URI).
5. `tests/contract/tool_classes.py`: die Zeilenverweise von `tasks_complete` auf den Stand nach dem Auslagern nachgezogen; `test_tool_surface.py`: der Gegenprobentest der Klasse gilt jetzt für `tasks_complete` und `tasks_update` (umbenannt in `test_a_modifying_task_tool_with_a_planted_class_turns_the_gate_red`).
6. README-Zeilen `tasks_update | modify` in README.md, README.de.md und README.fr.md im selben Commit wie der OPTIONAL_TOOLS-Eintrag (05dd7b2), nach dem Muster von 33-06. Owner bitte Wortlaut prüfen.
7. `python -W error -m pytest ... -p no:anyio` geht für die async-Testdateien nicht (ohne Plugin ist `pytest.mark.anyio` unbekannt); stattdessen mit Plugin und nur dessen `PytestRemovedIn10Warning` ausgenommen.

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche über das Threat Model hinaus. T-33-07-01 (Byte- und Semantik-Beweis auf Werkzeugebene, einzige benannte Ausnahme X-ALT-DESC), -02 (Werte nur über icalendar, `verify` mit gleicher UID und genau einem VTODO, Schmuggeltest, CR normalisiert), -03 (Elternaufgabe gleiche Liste, nicht selbst, kein Nachfahr), -04 (summary und description bleiben FORBIDDEN_PARAMS, Allowlist ohne sie), -05 (ETag-Vergleich und If-Match, 412 ohne Retry) umgesetzt.

## Self-Check: PASSED

tests/unit/test_tasks_update.py und diese SUMMARY vorhanden; Commits 9ad7b54, e047afb, d086933, eb3c1ca, e7e3cdc, 05dd7b2 im Log; `async def update_task` in tools/tasks.py, `tasks_update` in reg_tasks.py und allowlist.py.

---
phase: 33-aufgaben-aendern
plan: 04
subsystem: zeilen-editor
tags: [tasks, icalendar, vtodo, tmod-02, rundlauf, tdd]
requires: ["33-01c", "33-03"]
provides:
  - "tools/ics_edit.inspect(text) -> TodoFacts(uid, recurring, line_end, fields); EditRefused bei kaputtem Text, nicht genau einem VTODO, doppeltem einwertigem Feld"
  - "tools/ics_edit.apply(text, *, set_fields, drop_fields) -> str; lehnt Wiederholung ab; PARENT als Sondername, X-ALT-DESC entfernbar"
  - "tools/ics_edit.verify(before, after, expected) -> None; None in expected heißt entfernt (DESCRIPTION: leer gilt als entfernt)"
  - "tests/unit/test_ics_edit.py: byte_proof, semantic_proof, check_values, line_diff als Beweis-Hilfen für 33-06 und 33-07"
affects: [33-05, 33-06, 33-07, 33-08]
tech-stack:
  added: []
  patterns: ["Zeilen-Editor auf logischen Zeilen mit Komponentenstapel", "neue Zeilen nur per Wegwerf-Todo und to_ical(sorted=False)", "zwei unabhängige Beweise (Bytes, Semantik) plus Positivkontrolle"]
key-files:
  created:
    - src/mcp_connector/tools/ics_edit.py
    - tests/unit/test_ics_edit.py
    - .planning/phases/33-aufgaben-aendern/33-04-SUMMARY.md
  modified:
    - vulture_whitelist.py
decisions:
  - "inspect meldet Wiederholung nur (recurring), apply lehnt sie ab; ein zweites VTODO lehnt schon inspect ab"
  - "Parameter bleiben beim Ersetzen nur für SUMMARY, DESCRIPTION, CATEGORIES und RELATED-TO; ALTREP und VALUE fallen immer weg; DUE, DTSTART und Zeitstempel bekommen frische Zeilen ohne alte Parameter (TZID weicht UTC mit Z)"
  - "Eine Zeit gilt nur als UTC, wenn Versatz 0 und Zonenname UTC (timezone.utc oder ZoneInfo('UTC')); Europe/London im Winter wird abgelehnt; Mikrosekunden werden abgelehnt statt abgeschnitten"
  - "DESCRIPTION entfernen schreibt eine leere Zeile DESCRIPTION: ohne Parameter an der Stelle der alten Zeile; fehlt DESCRIPTION, bleibt das Objekt unverändert"
  - "verify vergleicht Werte wörtlich: ein Wagenrücklauf im Text kommt aus icalendar als Zeilenumbruch zurück und führt zur Ablehnung; die Werkzeuge in 33-07 normalisieren Zeilenenden vorher"
metrics:
  completed: 2026-11-13
  tasks: 2
  duration: "ca. 45 min"
---

# Phase 33 Plan 04: Zeilen-Editor für ein bestehendes VTODO Summary

`tools/ics_edit.py` ändert nur die genannten Felder des einen VTODO auf logischen Zeilen (Komponentenstapel, Original samt Faltung und Zeilenende bleibt je unberührter Zeile erhalten), erzeugt neue Zeilen ausschließlich mit icalendar (`Todo().add(...)`, `to_ical(sorted=False)`) und besteht Byte- und Semantik-Beweis auf allen 15 bearbeitbaren Fixtures der Tasks-App und 9 Handobjekten in je 18 Änderungsarten.

## Commits

| Schritt | Commit | Inhalt |
|---------|--------|--------|
| RED | `50811a9` | `test(33-04): round-trip proofs for the task line editor` |
| GREEN | `d46d2c7` | `feat(33-04): line editor that keeps every untouched property` |

Kein REFACTOR-Commit nötig. Autor und Committer `street1983nk <k.cherif@outlook.de>`, ohne Trailer.

## Rote Tests des RED-Commits

- `-k positive_control`: 6 passed (die Beweise erkennen den gepflanzten Fehler schon ohne Editor).
- `-k "not positive_control"`: 907 failed, 1 passed (`test_every_fixture_of_the_tasks_app_is_covered`); 906 mit `ImportError: cannot import name 'ics_edit'`, 1 mit `FileNotFoundError` (Quelltextregel). `test ! -e src/mcp_connector/tools/ics_edit.py` wahr.
- pyright im RED-Commit: 11 Fehler, alle `"ics_edit" is unknown import symbol` in `tests/unit/test_ics_edit.py`; alle übrigen Gates grün (6616 passed, 35 skipped, ohne die neue Datei).

## Fälle je Objekt

Objekte (24): alle `tests/fixtures/tasks_app/*.ics` außer `recurring.ics` (15: die acht aus Phase 30 ohne `recurring.ics` plus die acht aus 33-01b) und 9 Handobjekte: Probeobjekt des Spikes (VTIMEZONE mit `RRULE BYMONTH=3;BYDAY=-1SU`, VALARM mit DESCRIPTION, drei X-Eigenschaften, `SUMMARY;X-SPIKE30-PARAM`, gefaltete DESCRIPTION, `SEQUENCE:2`), dessen LF-Variante, Faltung bei 40 Zeichen (Leerzeichen und Tab), Kleinschreibung, zwei CATEGORIES-Zeilen, RELATED-TO mit SIBLING, CHILD und zwei Elternzeilen, unbekannte Komponente X-THING, `X-ALT-DESC;FMTTYPE=text/html` mit `DESCRIPTION;ALTREP=...;LANGUAGE=de` und `SUMMARY;LANGUAGE=de`, Objekt ohne DTSTAMP und LAST-MODIFIED vor einem VALARM.

Änderungsarten (18 je Objekt, jede mit LAST-MODIFIED und DTSTAMP auf denselben UTC-Zeitpunkt): abhaken, wieder öffnen, SUMMARY, DESCRIPTION, DUE als Zeit, DUE als Datum, DTSTART als Zeit, DTSTART als Datum, PRIORITY, CATEGORIES, PARENT setzen; DUE, DTSTART, DESCRIPTION, PRIORITY, CATEGORIES, PARENT entfernen; X-ALT-DESC entfernen.

Matrix: 24 x 18 = 432 Fälle, je zweimal geprüft (Byte- plus Semantik-Beweis plus Wertprüfung mit icalendar; dazu `verify` des Editors), also 864 Tests. `recurring.ics` wird abgelehnt (eigener Test). Insgesamt 914 Tests in der Datei.

## Beweise und Positivkontrolle

- Byte-Beweis (ohne Unfalten, Substring-Suche der physischen Zeilen am Zeilenanfang, in Reihenfolge; alles vor `BEGIN:VTODO` und ab `END:VTODO` gleich): 432 von 432 ohne Befund.
- Semantik-Beweis (icalendar-Multimenge je Komponentenpfad `(NAME, Parameter, to_ical(Wert))`, Differenz nur in genannten Feldern plus LAST-MODIFIED und DTSTAMP, RELATED-TO nur als Elternbezug): 432 von 432 ohne Befund.
- Positivkontrolle (6 Tests, schon im RED grün): ein falscher Editor, der `X-SPIKE30-FOO:bar` verliert, wird vom Byte-Beweis als genau `["X-SPIKE30-FOO:bar\r\n"]` und vom Semantik-Beweis als genau `[("VCALENDAR/VTODO#0", "X-SPIKE30-FOO", (), b"bar")]` gemeldet; beide schweigen bei unverändertem Objekt (alle 16 Fixtures und 9 Handobjekte); eine neu gefaltete Zeile meldet nur der Byte-Beweis; eine geänderte DESCRIPTION im VALARM melden beide trotz genanntem Feld DESCRIPTION; eine verlorene SIBLING-Zeile melden beide trotz genanntem PARENT. Nach GREEN zusätzlich: echte Abhak-Bearbeitung plus gepflanzter Verlust wird genau an dieser Zeile gemeldet.
- Abgleich mit der Tasks-App (Feldmenge per `line_diff` wie in 33-01 und volle Multimenge gleich): abhaken (Zustand a von `completed.ics` aus `raw/ui-a` zu `completed.ics`), abgebrochen abhaken (`cancelled.ics` zu `cancelled_completed.ics`), wieder öffnen (Zustand a von `reopened.ics`, abhaken, wieder öffnen zu `reopened.ics`), Entfernen von DTSTART, DESCRIPTION (leere Zeile), PRIORITY und CATEGORIES an den Paaren `cleared_due` bis `cleared_tags`: 7 von 7 gleich. Für `cleared_parent.ics` gibt es keinen gemessenen Vorzustand als Fixture; das Entfernen von PARENT ist über die Matrix und einen eigenen Test belegt.
- `-W error`: `python -W error -m pytest tests/unit/test_ics_edit.py -p no:xdist -p no:anyio`: 914 passed, keine Warnung; die Datei setzt zusätzlich `pytestmark = filterwarnings("error")`.

## Gates (vor dem GREEN-Commit, alle Exit 0)

- `pytest tests/unit tests/contract -m "not integration and not matrix" -p no:xdist`: 7530 passed, 35 skipped
- `scripts/check_tool_budget.py`: Exit 0, Standardzustand 18770 Bytes, 27 Werkzeuge (unverändert, kein Werkzeug neu)
- `ruff check .`: grün; `ruff format --check .`: 398 Dateien formatiert
- `pyright`: 0 Fehler
- `vulture src scripts vulture_whitelist.py`: grün
- Plan-Prüfungen: kein `foldline` in `ics_edit.py`, `sorted=False` vorhanden, kein Import aus `tools/tasks.py` (eigener Quelltexttest)
- TASK-01: `git diff "$B"` über caldav.py, calendar.py und deren Tests leer (Basis geprüft: SHA-Form und Vorfahr von HEAD; Gegentreffer im selben Lauf: `git diff "$B" -- src/mcp_connector/tools/` zeigt die Änderung an tasks.py aus 33-03)
- Keine U+2013/U+2014; `ics_edit.py` reines ASCII; keine Teilstrings MOVE, DELETE, COPY, PROPPATCH unter dem neuen Modul

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug im Test] Eingeschmuggelter Titel mit Wagenrücklauf**
- **Found during:** Task 2 (GREEN)
- **Issue:** Der RED-Test erwartete, dass ein Titel mit `\r\n` wörtlich zurückkommt. RFC 5545 TEXT kennt kein Escape für CR; icalendar schreibt CR und CRLF als `\n`. `verify` lehnte deshalb zu Recht ab.
- **Fix:** Der Test schmuggelt `END:VTODO`/`BEGIN:VTODO`/`UID:` mit `\n` (bleibt ein Wert, `verify` besteht) und pinnt zusätzlich den CR-Fall: ein VTODO, UID unverändert, `verify` lehnt ab. Kein Produktcode gelockert.
- **Files modified:** tests/unit/test_ics_edit.py
- **Commit:** d46d2c7

**2. [Rule 3 - Blocking] `-W error` und das anyio-Plugin von pytest**
- **Found during:** Task 2, Verify
- **Issue:** `python -W error -m pytest ...` bricht vor dem Sammeln ab, weil `anyio/pytest_plugin.py` beim Laden `PytestRemovedIn10Warning` (CallSpec2) auslöst. Vorhanden vor diesem Plan, betrifft keine Datei von 33-04.
- **Fix:** Lauf mit `-p no:anyio` (die Datei hat keine async-Tests); dort 914 passed ohne Warnung. Das Plugin selbst nicht angefasst (außerhalb des Umfangs).
- **Commit:** keiner nötig

**3. [Rule 3 - Blocking] pyright zu `Todo.add(parameters=None)`**
- **Found during:** Task 2
- **Fix:** immer ein Dict übergeben (`parameters=dict(params)`), Ausgabe unverändert.
- **Commit:** d46d2c7

## Deferred Issues

- anyio-Plugin-Warnung unter `-W error` (siehe Abweichung 2); für 33-06/33-07, falls deren Verify `-W error` verlangt: `-p no:anyio` setzen.

## Known Stubs

Keine. `apply` und `verify` stehen bis 33-06 bis 33-08 ohne Aufrufer im Produktcode, mit Eintrag in `vulture_whitelist.py` ("used by tasks_complete, tasks_update, tasks_move (33-06 to 33-08)"); `inspect` braucht keinen Eintrag, `apply` ruft es.

## Threat Flags

Keine neue Oberfläche: reine Funktionen ohne Netz, ohne Datei- oder Datenbankzugriff. T-33-04-01 (Byte- und Semantik-Beweis), T-33-04-02 (Werte nur über icalendar, Nachprüfung ein VTODO und gleiche UID, Schmuggeltest) und T-33-04-03 (Vorprüfung lehnt kaputten Text ab) umgesetzt.

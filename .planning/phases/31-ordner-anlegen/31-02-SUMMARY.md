---
phase: 31-ordner-anlegen
plan: 02
subsystem: api
tags: [webdav, mkcol, files, kein-ki, sandbox, tdd]

requires:
  - phase: 30-mess-spike-aufgaben-und-ordner
    provides: Statusmatrix des MKCOL und Kopf oc-fileid (00023274oclxpo7v8s2m)
  - phase: 31-ordner-anlegen
    provides: Basis-SHA in 31-BASE.txt (Plan 31-01)
provides:
  - dav.make_folder, dav._check_mkcol, dav.fileid_from_header (MKCOL ohne Body, benannte Zweige)
  - dav.probe_folder mit schlankem Body (_PROBE_PROPS, _probe_body) und dav.name_rejected
  - files.create_folder (Kette, Vorab-Zählung, Deckel 10, Abbruch-Hülle, Ausschluss, Sandbox)
  - neuer Hinweistext von dav.parent_missing mit files_create_folder
  - drei Unit-Testdateien für Client, Werkzeuglogik und Ausschluss
affects: [31-03, 31-04, 31-05, notes_create]

tech-stack:
  added: []
  patterns:
    - "Lesen für Ordneranlage nur über dav.probe_folder (resourcetype und fileid), nie über dav.stat"
    - "Kette: von unten zählen, von oben anlegen, _writable(clients, target) vor jedem MKCOL"
    - "Abbruch-Hülle _with_created: ohne Angelegtes byte-gleich zum Zweig"

key-files:
  created:
    - tests/unit/test_dav_make_folder.py
    - tests/unit/test_files_create_folder.py
    - tests/unit/test_files_create_folder_exclusion.py
  modified:
    - src/mcp_connector/nextcloud/clients/dav.py
    - src/mcp_connector/tools/files.py
    - tests/unit/test_dav_fileid_paths.py
    - vulture_whitelist.py

key-decisions:
  - "_check_mkcol ruft dav._check nur für 3xx, 401, 429 und 5xx; jeder übrige Status endet im eigenen Rest ohne das Wort unexpected"
  - "Ein Commit je Task (Tests und Code zusammen), RED jeweils vorher gesehen, wie im Plan benannt"
  - "Netzfehler mitten in der Kette (Timeout, nicht erreichbar) tragen den Zusatz zum Angelegten nicht; nicht gebaut, als offener Punkt gemeldet"

patterns-established:
  - "Zählklasse _Files in den Exklusionstests: MKCOL und PROPFIND auf files/ getrennt gezählt"

requirements-completed: []

duration: 13min
completed: 2026-11-12
---

# Phase 31 Plan 02: Kern von files_create_folder Summary

**MKCOL-Client mit benannten Zweigen in dav.py und die Werkzeuglogik files.create_folder mit Vorab-Zählung, Deckel 10, Abbruch-Hülle, Ausschluss kein-ki und Sandbox, belegt durch 98 neue Unit-Tests; noch nicht registriert.**

## Performance

- **Duration:** ca. 13 min
- **Started:** 2026-11-12T13:56:04Z
- **Completed:** 2026-11-12
- **Tasks:** 3 von 3
- **Files modified:** 7 (3 neu, 4 geändert)

## Accomplishments

- `dav.make_folder` schickt genau einen MKCOL ohne Body und ohne Content-Type; 201 liefert die Id aus `oc-fileid` (00023274oclxpo7v8s2m ergibt 23274), 405 liefert `created: False` ohne Fehler.
- `_check_mkcol` hat eigene Zweige für 400, 403, 404/409, 423, 507; 3xx, 401, 429, 5xx laufen über `dav._check`; keine Meldung enthält "unexpected status".
- `files.create_folder`: ohne `parents` genau ein MKCOL und kein PROPFIND davor; mit `parents` Zählung von unten, Anlegen von oben, mehr als 10 fehlende Ordner werden vor dem ersten MKCOL abgelehnt.
- Jeder PROPFIND des Werkzeugs geht über `dav.probe_folder` mit dem Body aus `_PROBE_PROPS` (nur `resourcetype` und `fileid`); `_STAT_PROPS`, `_stat_body` und `stat` sind unverändert.
- Ausschluss: Ziel in oder unter einem kein-ki-Ordner ergibt exakt `dav.parent_missing(Ziel)` ohne MKCOL und ohne PROPFIND auf files/; nicht beantwortbare Prüfung ergibt `withhold.unavailable_error()`; ein REPORT je Aufruf.
- Hinweistext von `parent_missing` nennt `files_create_folder`, wortgleich in dav.py und tests/unit/test_dav_fileid_paths.py.

## Task Commits

1. **Task 1: MKCOL-Client mit benannten Zweigen** - `ae5db07` (feat)
2. **Task 2: create_folder mit Kette, Zählung, Deckel, Hülle, Sandbox** - `7c0bec1` (feat)
3. **Task 3: Ausschluss und fail-closed, voller Lauf R1** - `227401d` (test)

## Files Created/Modified

- `src/mcp_connector/nextcloud/clients/dav.py` - make_folder, _check_mkcol, fileid_from_header, probe_folder, _probe_body, _PROBE_PROPS, name_rejected, neuer _PARENT_HINT, Modul-Docstring
- `src/mcp_connector/tools/files.py` - create_folder, MAX_NEW_FOLDERS und Helfer (_missing_folders, _probe, _existing_folder, _late_fileid, _with_created, _parent_missing_of, _folder_answer), Modul-Docstring
- `tests/unit/test_dav_make_folder.py` - 44 Tests: Zweige des Clients, Kopf-Parser, probe_folder samt Body
- `tests/unit/test_files_create_folder.py` - 38 Tests: Antwortform, Kette, Deckel 10 und 11, Teilabbruch, Wettlauf, Sandbox
- `tests/unit/test_files_create_folder_exclusion.py` - 16 Tests: kein-ki, fail-closed, Paar, Präfix-Nachbar, Positivkontrolle, ein REPORT
- `tests/unit/test_dav_fileid_paths.py` - Konstante PARENT_HINT auf den neuen Wortlaut
- `vulture_whitelist.py` - vorübergehender Eintrag `create_folder` (31-03 entfernt ihn)

## Verifikation (gesehene Ausgaben)

- verify Task 1: Exit 0 (pytest der fünf Dateien, ruff check, ruff format --check, pyright)
- verify Task 2: Exit 0 (pytest, ruff, format, pyright, vulture, sed-Prüfungen, Positivkontrolle der Basis, Diff-Prüfungen gegen 31-BASE.txt)
- verify Task 3: Exit 0; `pytest tests/unit tests/contract`: 5812 passed, 35 skipped; `check_tool_budget.py`: 15706 Bytes, 23 Werkzeuge, Budget 18000; ruff check, ruff format --check (373 Dateien), pyright (0 Fehler), vulture je Exit 0
- Akzeptanzzahlen: `"MKCOL"` in dav.py 2 (vorher 1); "unexpected status" in dav.py 4 (vorher 4); `_writable(clients, target)` in files.py 8 (Basis 6); Diff files.py gegen Basis: 1 Treffer `async def create_folder`, 0 Treffer `permissions`; Diff dav.py: 0 entfernte Zeilen mit `permissions`
- RED je Task gesehen: Task 1 vor der Implementierung rot (Importfehler der neuen Namen), Task 2 mit 47 roten Tests vor der Implementierung
- Mutationsprobe Task 3: ohne die Eingangsprüfung `_writable` in create_folder werden 14 der 16 Exklusionstests rot; Änderung danach verworfen
- Neue Zeilen in src, tests und vulture_whitelist.py: 0 Nicht-ASCII-Zeichen
- Drei Commits als street1983nk, ohne Trailer; kein Push

## Decisions Made

- D-31-01 bis D-31-05 sind je durch benannte Tests festgenagelt (Docstring von tests/unit/test_files_create_folder.py nennt die Zuordnung).
- Wahl im Ermessensraum wie im Plan: Feld `created_folders`, Zählung von unten.

## Deviations from Plan

**1. _check_mkcol ruft _check bedingt**
- Der Plan schreibt "danach `_check(response, path)` für 3xx, 401, 429, 5xx; als technischer Rest am Ende". Ein unbedingter Aufruf hätte den Rest unerreichbar gemacht, weil `_check` für jeden übrigen Status selbst mit "unexpected status" wirft. Der Aufruf steht deshalb hinter der Bedingung 3xx, 401, 429, 5xx; alles andere (zum Beispiel 418, 204) endet im eigenen Rest. Test: `test_an_unnamed_status_ends_in_the_technical_rest`.

**2. Ein Commit je Task statt getrennter RED- und GREEN-Commits**
- Der Plan nennt drei Commit-Betreffs; die Tests wurden je Task zuerst geschrieben und rot gesehen, dann mit dem Code zusammen committet.

**3. Paartest gegen den erfundenen Pfad mit Umbenennung**
- "Getaggt /Projekt/neu gegen /erfunden-1/neu ergibt identische Tupel" ist wörtlich nicht möglich, weil die Meldung den Pfad nennt. Zwei Tests decken es: derselbe Pfad getaggt gegen echtes 409 (Tupel identisch) und der erfundene Pfad, dessen Ordnername im Tupel ersetzt wird.

**4. Zusätzliche Tests über den Block behavior hinaus**
- Unter anderem: Verbindungsfehler beim Nachlesen der Id, Kette direkt unter der Home-Wurzel (Wurzel wird nie gelesen), 403 am ersten Segment byte-gleich zum Zweig, getaggte Datei als Ziel, einzelner Ordner in der Sandbox.

**5. Wurzel der Sandbox ist eine Datei**
- Vom Plan nicht genannt: liefert das Lesen der Wurzel eine Datei, endet der Aufruf im Konflikt "A file, not a folder", ohne MKCOL. Kein eigener Test.

## Issues Encountered

- Der Arbeitsbaum liegt mit CRLF vor (core.autocrlf=true); Quelländerungen wurden mit erhaltenen Zeilenenden geschrieben. Git meldet für die neuen Testdateien die übliche Umwandlungswarnung.

## Offene Punkte

- Netzfehler mitten in der Kette (httpx-Timeout oder Verbindungsabbruch nach mindestens einem angelegten Ordner) laufen unverändert zu `@graceful` und nennen das bereits Angelegte nicht. D-31-02 nennt Rechte, Sperre, Serverfehler, Kontingent und Wettlauf; ob Netzfehler dazugehören sollen, ist eine Entscheidung für Owner oder Hauptsitzung. Ein erneuter Aufruf mit `parents=true` ist idempotent.
- Annahme A5 (PROPFIND unter einer Datei antwortet 404 oder 409) ist nur per Unit-Test abgedeckt; der Live-Beleg gehört zu 31-05.
- `create_folder` ist nicht registriert; der vulture-Eintrag muss in 31-03 wieder heraus.
- STATE.md, ROADMAP.md und REQUIREMENTS.md wurden nicht angefasst; FOLD-01 bis FOLD-05 sind nicht als erledigt markiert (Registrierung, Gates und Live-Beweis folgen).

## Next Phase Readiness

- 31-03 kann `files_tools.create_folder(clients, path=..., parents=...)` registrieren; Antwortform `{path, created, id[, created_folders]}`.
- 31-04 findet genau zwei `client.request("MKCOL", ...)` in dav.py, beide ohne Body.

## Self-Check: PASSED

- Alle sieben Dateien vorhanden und committet
- Commits ae5db07, 7c0bec1, 227401d im Log gefunden

---
phase: 31-ordner-anlegen
plan: 03
subsystem: api
tags: [mcp, registrierung, annotationen, contract-gates, budget, readme]

requires:
  - phase: 31-ordner-anlegen
    provides: files.create_folder mit Antwort {path, created, id[, created_folders]} (Plan 31-02)
provides:
  - Registriertes Werkzeug files_create_folder im Bundle files (@graceful, Audit {parents, path})
  - Annotationsklasse CREATE_IDEMPOTENT in server/__init__.py
  - Gate-Menge IDEMPOTENT_CREATE_TOOLS mit eigenem Zweig und gepflanzter Gegenprobe
  - Klassifikations-Freeze 24 Werkzeuge (13, 4, 7), FILE_WRITERS und PAIR_CASES mit files_create_folder
  - Unit-Paartest in allen GUARD_MODES
  - Budget-Messzeile für 24 Werkzeuge (16222 Bytes)
  - Zahl 24 und Tabellenzeile in drei READMEs, Bundle-Liste in README.md
affects: [31-04, 31-05, 31-06, 32, 34]

tech-stack:
  added: []
  patterns:
    - "Annotations-Gate als Hilfsfunktion _check_annotations: dieselben Zeilen prüfen die Registry und die gepflanzte Gegenprobe"
    - "Paartest zählt die Schreibroute der getaggten Seite (0) und nutzt die Route der Gegenseite als Positivkontrolle"

key-files:
  created: []
  modified:
    - src/mcp_connector/server/__init__.py
    - src/mcp_connector/server/reg_files.py
    - src/mcp_connector/audit/allowlist.py
    - vulture_whitelist.py
    - tests/contract/test_tool_surface.py
    - tests/contract/test_tool_bundles.py
    - tests/contract/tool_classes.py
    - tests/contract/test_tool_classes.py
    - tests/unit/test_pair_equality_files.py
    - scripts/check_tool_budget.py
    - README.md
    - README.de.md
    - README.fr.md

key-decisions:
  - "Budget bleibt 18000 (Fall a): Messung 16222 liegt darunter; die Hausregel ergäbe heute 19000, die Neuverankerung folgt am Endstand (E1, TASK-08, Phase 32)"
  - "Docstring des Werkzeugs auf zwei Zeilen umbrochen (Zeilenlänge 100), Wortlaut wie im Plan"
  - "README.de.md und README.fr.md haben keinen Abschnitt zu Bundles; er wurde nicht neu übersetzt, sondern als offener Punkt gemeldet"

patterns-established:
  - "Eigene Werkzeugklasse je ehrlicher Annotation: Menge im Gate, Zweig, Gegenprobe mit pytest.raises"

requirements-completed: []

duration: 25min
completed: 2026-11-12
---

# Phase 31 Plan 03: Registrierung und Oberflächen-Gates von files_create_folder Summary

**files_create_folder ist mit der neuen Klasse CREATE_IDEMPOTENT registriert und durch Audit, Werkzeugmenge (24), Bundle, Klassifikations-Freeze (13, 4, 7), Unit-Paartest und Budget (16222 Bytes) geführt; die drei READMEs nennen Zahl und Tabellenzeile, die Bundle-Liste existiert nur in README.md.**

## Performance

- **Duration:** ca. 25 min
- **Started:** 2026-11-12T14:10Z (ungefähr, Startzeit nicht gestempelt)
- **Completed:** 2026-11-12T14:35Z
- **Tasks:** 3 von 3 (Task 3 mit einer offenen Verify-Klausel, siehe Abweichung 1)
- **Files modified:** 13

## Accomplishments

- `files_create_folder(path, parents=False)` ist nach `files_upload` registriert: `@mcp.tool(annotations=CREATE_IDEMPOTENT, structured_output=False)`, `@graceful`, kein Nutzerparameter, Rumpf ruft `files_tools.create_folder`.
- `CREATE_IDEMPOTENT` (read_only False, destructive False, idempotent True, open_world False) steht neben `CREATE_ONLY`, in `__all__` alphabetisch.
- Annotations-Gate: `IDEMPOTENT_CREATE_TOOLS = {"files_create_folder"}` mit eigenem Zweig vor `CREATE_TOOLS`; `CREATE_TOOLS` bleibt bei sechs (eigene Zusicherung `len(CREATE_TOOLS) == 6`).
- Gegenprobe T-31-14: `CREATE_ONLY`, `UPDATE_EXISTING` und zusätzlich `READ_ONLY` für `files_create_folder` ergeben je einen `AssertionError`; die echte Klasse besteht als Positivkontrolle.
- Audit-Erlaubnisliste: `"files_create_folder": frozenset({"parents", "path"})`.
- Freeze: `TOTAL = 24`, Aufteilung (13, 4, 7), `FILE_WRITERS` mit Anker `tools/files.py:669-762, :708, :748`, `PAIR_CASES` mit `("files_create_folder", "path")`.
- Unit-Paartest über fünf GUARD_MODES: getaggt `/Projekt/neu` gegen erfunden `/erfunden-1/neu` byte-gleich; die 201-Route der getaggten Seite hat `call_count` 0, die 409-Route der Gegenseite 1 in den beantworteten Modi und 0 in den nicht beantwortbaren.
- `create_folder` ist aus `vulture_whitelist.py` heraus, `files_create_folder` steht im Abschnitt der registrierten Werkzeugfunktionen.

## Task Commits

1. **Task 1: Registrierung, Audit, Werkzeugmenge, Annotations-Gate, Bundle** - `3328ccd` (feat)
2. **Task 2: Freeze, Paarfall, Unit-Paartest, Budget-Messzeile** - `085897e` (test)
3. **Task 3: Drei READMEs, voller Lauf R1** - `620ab4e` (docs)

## Files Created/Modified

- `src/mcp_connector/server/__init__.py` - `CREATE_IDEMPOTENT` und `__all__`
- `src/mcp_connector/server/reg_files.py` - Registrierung `files_create_folder`
- `src/mcp_connector/audit/allowlist.py` - Eintrag `{parents, path}`
- `vulture_whitelist.py` - `create_folder` entfernt, `files_create_folder` aufgenommen
- `tests/contract/test_tool_surface.py` - Menge 24, `IDEMPOTENT_CREATE_TOOLS`, `_check_annotations`, Gegenprobe, README-Abbildung, Zahlen und Texte
- `tests/contract/test_tool_bundles.py` - Bundle files mit sieben Werkzeugen
- `tests/contract/tool_classes.py` - `FILE_WRITERS`, `PAIR_CASES`
- `tests/contract/test_tool_classes.py` - `TOTAL = 24`, (13, 4, 7), Zählwörter
- `tests/unit/test_pair_equality_files.py` - `_mkcol`, Paartest, `COVERED`
- `scripts/check_tool_budget.py` - Messzeile 2026-11-12
- `README.md` - Zahl 24, Tabellenzeile, Bundle-Liste
- `README.de.md`, `README.fr.md` - Zahl 24, Tabellenzeile

## Verifikation (gesehene Ausgaben)

- verify Task 1: Exit 0 (pytest der drei Contract-Dateien ohne README-Tests, `check_tool_budget.py`, vulture). Ohne den Filter `-k` waren vor Task 3 genau zwei Tests rot: `test_the_readme_permission_table_matches_the_live_registry` und `test_a_documented_tool_count_is_the_current_one_or_says_which_run_it_is_from`.
- verify Task 2: Exit 0 (pytest `test_tool_classes.py` und `test_pair_equality_files.py`, Budget, ruff check, ruff format --check). RED vorher gesehen: vier rote Tests (drei in `test_tool_classes.py`, dazu `test_the_files_family_covers_exactly_its_pair_cases`), bevor `tool_classes.py` die Einträge bekam.
- verify Task 3, Klausel für Klausel:
  - `grep -c files_create_folder README.md` ergibt 2: Exit 0
  - `grep -c files_create_folder README.de.md` ergibt 1, verlangt mindestens 2: **Exit 1**
  - `grep -c files_create_folder README.fr.md` ergibt 1, verlangt mindestens 2: **Exit 1**
  - Dash-Prüfung der drei READMEs: kein Treffer; Positivkontrolle des Musters mit einem gepflanzten U+2014 greift
  - ASCII-Umlaut-Prüfung README.de.md: kein Treffer
  - `pytest tests/unit tests/contract`: Exit 0, 5821 passed, 35 skipped (vorher 5812; neun neue Fälle: vier im Annotations-Gate, fünf im Paartest)
  - `check_tool_budget.py`: Exit 0, 16222 Bytes, 24 Werkzeuge, Budget 18000
  - ruff check: Exit 0; ruff format --check: Exit 0 (373 Dateien); pyright: Exit 0 (0 Fehler); vulture: Exit 0
- Akzeptanzzahlen: `"files_create_folder"` in `tool_classes.py` 2 Treffer; `TOTAL = 24` Zeile 19; "24 curated tools" im Budget-Skript 1 Treffer; `^MAX_TOOL_BYTES = 1400$` 1 Treffer; `^BUDGET_BYTES = 18_000$` 1 Treffer; `EXPECTED_PUT_CALLS = 6` unverändert; `create-only` mit `files_create_folder` in README.md 1 Treffer; "- 23 " an der Zahlstelle in keinem README mehr, "- 24 " in jedem genau einmal.
- Diff-Prüfungen gegen 31-BASE.txt (Positivkontrolle der Basis bestanden): `appinfo/info.xml`, `docs/n8n-setup.md`, `docs/store-submission.md`, `tests/contract/test_no_destructive_calls.py` 0 geänderte Dateien; Server-Instruktion 0 geänderte Zeilen; Gegentreffer im selben Diff: `+CREATE_IDEMPOTENT = ToolAnnotations` 1, `+async def files_create_folder` 1.
- Mutationsprobe Paartest: ohne die Eingangsprüfung `_writable` in `create_folder` werden alle fünf Fälle des neuen Paartests rot; Änderung danach verworfen (`git checkout -- src/mcp_connector/tools/files.py`).
- Neue Zeilen in src, tests, scripts: 0 Nicht-ASCII-Zeichen. Neue README-Zeilen: keine Zeichen über U+2000.
- Drei Commits als street1983nk, ohne Trailer; kein Push.

## Budget

- Messung: 16222 Bytes bei 24 Werkzeugen (vorher 15706 bei 23). Das Werkzeug selbst misst 515 Bytes.
- Hausregel auf dieser Zahl: 16222 + 15 Prozent = 18656, auf die nächsten 500 gerundet 19000.
- Fall (a) des Plans: die Messung liegt unter 18000, `BUDGET_BYTES` bleibt 18_000, `MAX_TOOL_BYTES` bleibt 1400. Die Messzeile nennt die Rechnung und verweist auf E1 und TASK-08 (Phase 32).
- Restluft bis zur Grenze: 1778 Bytes.

## Decisions Made

- `READ_ONLY` als dritte gepflanzte Klasse in der Gegenprobe (der Plan nennt zwei).
- Der Paartest prüft zusätzlich die Route der Gegenseite, damit die Null der getaggten Seite keine Route ist, die nie greift.

## Deviations from Plan

**1. README.de.md und README.fr.md haben keine Bundle-Liste (Verify-Klausel offen)**
- **Gefunden in:** Task 3
- **Befund:** Der Plan nennt in allen drei READMEs drei Stellen (Zahl, Rechtetabelle, Bundle-Liste) und verlangt je Datei mindestens zwei Zeilen mit `files_create_folder`. Der Abschnitt "Switching tool bundles off" mit der Bundle-Liste existiert nur in README.md; in README.de.md und README.fr.md fehlt er schon in der Basis der Phase (`NC_MCP_DISABLED_TOOLS` dort 0 Treffer, in README.md 3).
- **Getan:** Zahl und Tabellenzeile in allen drei Sprachen, Bundle-Liste nur in README.md. Der fehlende Abschnitt wurde nicht neu übersetzt: das wäre neuer nutzersichtbarer Text von rund 30 Zeilen je Sprache außerhalb des Plans.
- **Folge:** Die beiden Zählklauseln des Verify-Befehls für README.de.md und README.fr.md enden mit Exit 1; alle übrigen Klauseln mit Exit 0. Entscheidung der Hauptsitzung nötig (siehe Offene Punkte).
- **Commit:** 620ab4e

**2. Docstring des Werkzeugs umbrochen**
- Der Wortlaut des Plans ergibt als eine Zeile 104 Zeichen (ruff E501, Grenze 100). Er steht auf zwei Zeilen; die Beschreibung auf dem Draht enthält deshalb einen Zeilenumbruch statt eines Leerzeichens zwischen "moves" und "or deletes." (gleiche Bytezahl im JSON plus 1).

**3. Hilfsfunktion statt Zweig in der Schleife**
- Das Annotations-Gate liegt jetzt in `_check_annotations(name, annotations)`; die Schleife über die Registry und die Gegenprobe rufen dieselbe Funktion. Der Plan verlangt die Hilfsfunktion ausdrücklich, der bisherige Zweig für `files_update`, `CREATE_TOOLS` und Leser ist wortgleich hineingezogen.

**4. Zusätze über den Plan hinaus**
- Zusicherungen `len(CREATE_TOOLS) == 6` und "ein Werkzeug gehört zu genau einer Klasse"; Positivkontrolltest der echten Klasse; `test_the_six_file_tools_...` heißt jetzt `test_the_seven_file_tools_...` und prüft `files_create_folder` mit.
- Kommentar in `test_tool_surface.py` Zeile 37 von "twenty-third" auf "twenty-fifth" (der alte Wert war schon vor diesem Plan überholt).
- Im vulture-Abschnitt steht statt der gelöschten Zeile ein kurzer Vermerk im Stil der Datei ("Empty on purpose").

**5. TDD-Gate Task 2**
- Ein Commit für Tests und Tabelleneinträge, RED vorher gesehen (wie in 31-02). Der neue Paartest selbst war sofort grün, weil die Logik aus 31-02 schon steht; seine Schärfe belegt die Mutationsprobe.

## Issues Encountered

- `pytest -q` zeigt wegen `addopts = "... -q ..."` keine Summenzeile; die Testzahlen stammen aus einem zweiten Lauf mit überschriebenem `addopts` ohne das zweite `-q` (gleiche Marker, gleicher Importmodus).

## Offene Punkte

- **Bundle-Abschnitt in README.de.md und README.fr.md:** entweder den Abschnitt "Switching tool bundles off" in beide Sprachen übersetzen (dann ist auch die Verify-Klausel erfüllt) oder die Klausel als nicht anwendbar festhalten. FOLD-06 (README-Teil) ist bis dahin nur für Zahl und Tabelle erfüllt.
- **Vorbestehende Lücke, nicht angefasst:** Die Tabellen in README.de.md und README.fr.md führen `files_read_as_markdown` und `files_update` nicht (23 Zeilen gegen 25 in README.md), nennen aber 24 Tools. Kein Test liest diese beiden Dateien.
- Budget: Die Hausregel ergäbe auf dem heutigen Stand 19000; die Anhebung ist Sache von TASK-08 in Phase 32.
- STATE.md, ROADMAP.md und REQUIREMENTS.md wurden nicht angefasst; FOLD-03, FOLD-05 und FOLD-06 sind nicht als erledigt markiert.
- Die Kanarie (`EXPECTED_TOOLS = 23`, `MUST_REFUSE`), das Live-Paar, die MKCOL-Nadel und das Abnahmeskript kennen das Werkzeug noch nicht; das sind die Pläne 31-04 und folgende. `test_every_pair_case_is_measured_live` gehört zur Integrationsschicht und lief hier nicht.

## Known Stubs

Keine.

## Next Phase Readiness

- 31-04 findet das Werkzeug in der Registry (24 Werkzeuge), in `FILE_WRITERS` und in `PAIR_CASES`; die Kanarie und das Live-Paar müssen den Eintrag nachziehen.
- Kein Docker in diesem Plan.

## Self-Check: PASSED

- Alle 13 Dateien geändert und committet, Arbeitsbaum vor dem SUMMARY-Commit sauber
- Commits 3328ccd, 085897e, 620ab4e im Log gefunden

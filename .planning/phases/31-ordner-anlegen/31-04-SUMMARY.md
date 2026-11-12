---
phase: 31-ordner-anlegen
plan: 04
subsystem: testing
tags: [mkcol, destruktiv-gate, kanarie, live-paar, abnahme, contract-gates]

requires:
  - phase: 31-ordner-anlegen
    provides: zwei MKCOL-Aufrufe in dav.py (Plan 31-02), registriertes Werkzeug files_create_folder mit PAIR_CASES-Eintrag (Plan 31-03)
provides:
  - Positive MKCOL-Nadel im Destruktiv-Gate (EXPECTED_MKCOL_CALLS = 2, MKCOL_HOME, kein Body, Literal nur in dav.py)
  - Kanarie mit 24 Werkzeugen, files_create_folder in MUST_REFUSE, zwei Aufrufe (ohne und mit parents)
  - refusal_problem kennt files_create_folder, Unit-Spiegel mit acht neuen Fällen
  - Rückbau der Kanarienwelt für fälschlich angelegte Ordner (Cleanup.add_folder)
  - Live-Paarfall (files_create_folder, path) mit Rücklesen beider Ziele
  - Abnahmeskript mit zweitem, idempotentem Aufruf
affects: [31-05, 31-06, 32, 34]

tech-stack:
  added: []
  patterns:
    - "Positive Nadel statt Verbotsnadel: Ort, Form und Anzahl eines erlaubten Schreibverbs werden festgenagelt"
    - "Zählpin plus Literalzählung im Heimatmodul: ein Verb in einer Variablen oder in build_request fällt auf, weil Literale und gezählte Aufrufe auseinanderlaufen"

key-files:
  created: []
  modified:
    - tests/contract/test_no_destructive_calls.py
    - tests/integration/test_canary.py
    - tests/integration/canary_world.py
    - tests/unit/test_canary_refusals.py
    - tests/integration/test_pair_equality_live.py
    - scripts/acceptance_all_tools.py

key-decisions:
  - "Die Nadel meldet zusätzlich entpackte Schlüsselwörter (**extra) und verlangt in dav.py genau so viele Literale MKCOL wie gezählte Aufrufe"
  - "Kanarie: ein fälschlich angelegter Ordner wird über den Harness gelöscht und aus dem Papierkorb entfernt (Name trägt den Lauf-Stempel)"
  - "Live-Paar: ein Ordner an einem der beiden Ziele wird nicht einzeln gelöscht, sondern als Befund gelesen; entfernt wird er mit der Wurzel der Welt"

patterns-established:
  - "Gepflanzte Gegenproben zweifach: als Quelltext im Test und einmal real in src gepflanzt, rot gesehen, verworfen"

requirements-completed: []

duration: 45min
completed: 2026-11-12
---

# Phase 31 Plan 04: MKCOL-Nadel, Kanarie, Live-Paar und Abnahme für files_create_folder Summary

**Das Destruktiv-Gate nagelt MKCOL auf zwei Aufrufe ohne Body in dav.py fest und ist durch real gepflanzte Umgehungen als wirksam belegt; Kanarie, Live-Paar und Abnahmeskript kennen files_create_folder als Code, ausgeführt werden sie erst in 31-05.**

## Performance

- **Duration:** ca. 45 min
- **Completed:** 2026-11-12
- **Tasks:** 2 von 2
- **Files modified:** 6

## Accomplishments

- `EXPECTED_MKCOL_CALLS = 2`, `MKCOL_HOME = "nextcloud/clients/dav.py"`, `_MKCOL_BODY_KEYWORDS`; `_mkcol_findings` meldet MKCOL in fremder Datei, mit `content`, `data`, `json` oder `files`, mit entpackten Schlüsselwörtern und als `method="MKCOL"`.
- `_mkcol_literals` zählt die Konstante `"MKCOL"` im Code (Docstrings ausgenommen, Teile eines f-Strings eingeschlossen); außerhalb von dav.py ist jeder Treffer ein Befund, in dav.py muss die Zahl der Literale der Zahl der gezählten Aufrufe gleichen.
- Kanarie: `EXPECTED_TOOLS = 24`, `MUST_REFUSE` mit `files_create_folder`, Plan mit `{locked_dir}/ordner-{h}` und `{locked_dir}/a-{h}/b` mit `parents=true`.
- `refusal_problem` verlangt für `files_create_folder` die Fragmente von `parent_missing`; im Ausfall zusätzlich den Satz der unbeantworteten Prüfung.
- `Cleanup.add_folder`: löscht einen trotz Ablehnung angelegten Ordner über den Harness, leert dessen Papierkorb-Eintrag und liest beides zurück; `assert_cleanup` der Kanarie verlangt die Zeile `CLEANUP ordner <Pfad>: 404` für beide Ordner.
- Live-Paar: `("files_create_folder", "path")` mit `{locked_dir}/neu-ordner` gegen `{root}/fehlt-{h}/neu-ordner`; `cleanup_folders` liest beide Ziele zurück.
- Abnahmeskript: `files_create_folder` mit `/{marker}-{stamp}-ordner/a/b` und `parents=true`, danach derselbe Aufruf noch einmal; ist `created` nicht `false`, entsteht eine FAIL-Zeile mit der ersten Zeile der Antwort.

## Task Commits

1. **Task 1: Positive MKCOL-Nadel mit Zählpin und gepflanzten Gegenproben** - `571f5a0` (test)
2. **Task 2: Kanarie, Unit-Spiegel, Live-Paarfall und Abnahmeskript, voller Lauf R1** - `eff3f55` (test)

## Files Created/Modified

- `tests/contract/test_no_destructive_calls.py` - MKCOL-Nadel, Literalprüfung, drei neue Tests, gepflanzte Quelltexte
- `tests/integration/test_canary.py` - 24 Werkzeuge, MUST_REFUSE, Plan, Rücklese-Zusicherung, Docstring-Zahlen
- `tests/integration/canary_world.py` - `refusal_problem`, `Cleanup.add_folder`, `World.refused_folder`, `refused_chain`, `refused_folders`, Registrierung in `_build_files`
- `tests/unit/test_canary_refusals.py` - acht neue Fälle für files_create_folder
- `tests/integration/test_pair_equality_live.py` - CASES-Eintrag, `cleanup_folders`
- `scripts/acceptance_all_tools.py` - zwei Aufrufe im Block files

## Verifikation (gesehene Ausgaben)

- verify Task 1: Exit 0. `test_no_destructive_calls.py`: 65 passed (vorher 62).
- RED Task 1: mit leeren Funktionen 2 failed, 1 passed (der Literal-Test ist mit einer leeren Funktion trivial grün; seine Schärfe belegen die gepflanzten Literale im dritten Test und Probe (d) unten).
- Real gepflanzte Umgehungen in src, je einzeln, Gate rot gesehen, danach mit `git checkout -- <Datei>` verworfen, Endstand wieder 65 passed:
  - (a) `content=b"<x/>"` am MKCOL von `make_folder`: 1 failed, "dav.py:1107: MKCOL with a body"
  - (b) `client.request("MKCOL", url)` in `tools/files.py`: 2 failed, "MKCOL outside nextcloud/clients/dav.py" und "the literal MKCOL outside"
  - (c) `client.request(method="MKCOL", url=url)` in dav.py: 1 failed, "MKCOL passed as keyword"
  - (d) `_VERB = "MKCOL"` in `tools/notes.py`: 1 failed, Literal-Test
  - (e) `client.send(client.build_request("MKCOL", url))` in dav.py: 1 failed, "spells the verb 3 times but sends it in 2 counted calls"
- Diff von `test_no_destructive_calls.py` gegen 31-BASE.txt (Positivkontrolle der Basis bestanden): 0 entfernte Zeilen, 0 geänderte Zeilen mit `EXPECTED_PUT_CALLS`, `FORBIDDEN` oder einer Zuweisung an `CHUNK_ASSEMBLY_MOVE`; Gegentreffer `+EXPECTED_MKCOL_CALLS = 2` 1. Eine neue Kommentarzeile nennt `CHUNK_ASSEMBLY_MOVE` als Verweis.
- RED Task 2: Unit-Spiegel vor der Änderung an `refusal_problem` 4 failed, 14 passed.
- verify Task 2, Klausel für Klausel, je Exit 0: pytest `test_canary_refusals.py` und `test_live_requirement.py` (23 passed), vier grep-Klauseln, `--collect-only -m integration` (test_canary.py 4, test_pair_equality_live.py 6), `pytest tests/unit tests/contract`, `check_tool_budget.py` (16222 Bytes, 24 Werkzeuge, Budget 18000), ruff check, ruff format --check (373 Dateien), pyright (0 Fehler), vulture.
- Testzahl: `pytest tests/unit tests/contract` 5832 passed, 35 skipped (vorher 5821; elf neue Fälle: drei im Destruktiv-Gate, acht im Unit-Spiegel). Die Zahl stammt aus einem zweiten Lauf mit überschriebenem `addopts` ohne `-q`, gleiche Marker, gleicher Importmodus.
- Ohne Instanz geprüft, was live erst in 31-05 läuft:
  - `test_every_pair_case_is_measured_live` überspringt ohne `NC_MCP_URL` (Meldung "no test Nextcloud available"). Seine Zusicherung direkt aufgerufen: bestanden, 16 Fälle auf beiden Seiten; ohne den neuen CASES-Eintrag `AssertionError [('files_create_folder', 'path')]`.
  - `plan()` der Kanarie gegen die Registry des In-Memory-Clients: 24 gegen 24, keine Abweichung; alle vier Namen aus `MUST_REFUSE` stehen im Plan; die Argumente tragen den Marker nicht.
  - `Cleanup.add_folder` mit einem nachgebauten Harness: nie angelegt ergibt zweimal `404` ohne Löschaufruf; angelegt ergibt DELETE, Papierkorb-Leerung und `404`; bleibt der Papierkorb-Eintrag stehen, endet die Zeile auf "404 und noch im Papierkorb" und gilt als Rückstand.
- Neue Zeilen: keine Nicht-ASCII-Zeichen, außer dem schon vorhandenen Wort "geprüft" in der Docstring-Zeile der Kanarie, in der nur die Zahl 23 zu 24 wurde.
- Zwei Commits als street1983nk, ohne Trailer; kein Push.

## Decisions Made

- Die Literalprüfung vergleicht auf Gleichheit mit `"MKCOL"`, wie der Plan es vorgibt. Ein Satz, der das Wort nur enthält (Fehlermeldung, Docstring), ist kein Treffer.
- `MUST_REFUSE` führt `files_create_folder` an zweiter Stelle, neben `files_upload`.

## Deviations from Plan

**1. Nadel schärfer als die Skizze (Zusatz)**
- Über die drei Fälle des Plans hinaus meldet `_mkcol_findings` entpackte Schlüsselwörter (`**extra` könnte einen Body tragen), und der erste Test verlangt, dass dav.py das Literal genau so oft schreibt, wie Aufrufe gezählt werden. Grund: `build_request("MKCOL", ...)` oder eine Variable in dav.py wären sonst weder gezählt noch gemeldet. `_PLANTED_MKCOLS` hat deshalb vier Einträge als Tripel (Datei, Quelltext, erwartete Zählung), dazu `_HONEST_MKCOL` und `_PLANTED_MKCOL_LITERALS`.

**2. Live-Paar: Rücklesen statt Löschen**
- Der Plan sagt, ein angelegter Ordner werde im Rückbau des Paars entfernt, "falls der bestehende Rückbau nur Dateien kennt". Der bestehende Rückbau löscht die Wurzel der Welt rekursiv und leert den Papierkorb nach dem Stamm; beide Ziele liegen darunter. Ein einzelnes Löschen von `neu-ordner` hätte einen Papierkorb-Eintrag ohne Stamm und ohne Lauf-Stempel hinterlassen, den niemand mehr gezielt entfernen kann. `cleanup_folders` liest deshalb beide Ziele zurück; ein Status ungleich 404 lässt `assert_cleanup` scheitern, entfernt wird der Ordner mit der Wurzel.

**3. Rückbau der Kanarie als eigene Methode**
- Statt `add_upload` zu erweitern (die Methode gehört zu den Staging-Ordnern unter uploads/) gibt es `Cleanup.add_folder`. Die beiden Pfade stehen als Eigenschaften an `World` (`refused_folder`, `refused_chain`), damit Plan der Kanarie und Rückbau dieselbe Quelle haben; die Pfade selbst sind die des Plans.

**4. Ein Commit je Task**
- Tests und Umsetzung liegen je Task in einem Commit, RED vorher gesehen (wie in 31-02 und 31-03).

**5. Zusätze im Unit-Spiegel und in der Kanarie**
- Acht statt mindestens zwei neue Fälle (Erfolgstext als Nicht-Ablehnung, Ausfallmodus). In `test_canary.py` wurden die Docstring-Angaben "six write tools" und "n == 23" auf sieben und 24 nachgezogen.

**6. Abnahmeskript: keine doppelte FAIL-Zeile**
- Scheitert der zweite Aufruf selbst, hat `call` die FAIL-Zeile schon geschrieben; die Prüfung auf `created` läuft nur bei einer Antwort.

## Issues Encountered

- Der volle Lauf überschreitet 180 Sekunden; er lief im Hintergrund weiter und endete mit Exit 0.

## Offene Punkte

- Kanarie, Live-Paar und Abnahmeskript sind nie gegen eine Instanz gelaufen; das ist 31-05. Insbesondere ungeprüft: ob der Papierkorb einen einzeln gelöschten Ordner unter seinem Basisnamen als `trashbin-filename` führt (Annahme von `add_folder`; der Fall tritt nur ein, wenn die Kanarie ohnehin rot ist).
- Das Abnahmeskript lässt den Ordner `/{marker}-{stamp}-ordner/a/b` in der Testinstanz stehen, wie schon die hochgeladene Datei; der Connector kann nicht löschen.
- Die Protokolldateien der Live-Läufe heißen weiter `28-10-canary.txt` und `28-11-pairs-live.txt` (nicht angefasst).
- STATE.md, ROADMAP.md und REQUIREMENTS.md wurden nicht angefasst; FOLD-05 ist nicht als erledigt markiert (der Live-Teil fehlt).

## Known Stubs

Keine.

## Next Phase Readiness

- 31-05 kann Kanarie und Live-Paar ohne weitere Codeänderung fahren; erwartet werden `KANARIE <modus> geprüft 24 von 24`, je zwei ABWEISUNG-Zeilen für files_create_folder und je Modus die Zeilen `CLEANUP ordner ...: 404`.
- Kein Docker in diesem Plan.

## Self-Check: PASSED

- Alle sechs Dateien geändert und committet, Arbeitsbaum vor dem SUMMARY-Commit sauber
- Commits 571f5a0 und eff3f55 im Log gefunden

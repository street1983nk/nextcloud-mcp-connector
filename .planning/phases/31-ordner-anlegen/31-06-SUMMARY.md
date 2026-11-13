---
phase: 31-ordner-anlegen
plan: 06
subsystem: docs
tags: [files_create_folder, exclusion, changelog, readme, tool-bundles, files_update, umlaut-audit, gates, push-entscheid]

requires:
  - phase: 31-ordner-anlegen
    provides: Live-Beweis docs/folder-evidence.md (31-05, 31-05b), README-Zeilen aus 31-03, Netzfehler-Meldung aus 31-04b
provides:
  - Abschnitt tech-folder-oracle in docs/exclusion.md, .de.md und .fr.md mit Befundlink unter docs/
  - Truth-Test mit 22 Ankern und der Prüfung stabiler Befundlinks samt gepflanzter Gegenprobe
  - Abschnitt zum Abschalten von Tool-Bundles und zwei Tabellenzeilen in README.de.md und README.fr.md, files_update in der Bundle-Liste aller drei READMEs
  - Contract-Test, der files_update an das Bundle files bindet
  - Einträge unter [Unreleased] in CHANGELOG.md, .de.md und .fr.md (je 8 Punkte)
  - Owner-Entscheid option-push vom 2026-11-13
affects: [32, 34]

tech-stack:
  added: []
  patterns:
    - "Befund einer Grenze an stabilem Ort unter docs/, eigene Ankergruppe STABLE_EVIDENCE_ANCHORS neben den 17 Abschnitten mit Befund unter .planning/phases/"
    - "README-Aussage über ein optionales Werkzeug wird von einem Contract-Test im frischen Interpreter gehalten"

key-files:
  created:
    - .planning/phases/31-ordner-anlegen/31-06-SUMMARY.md
  modified:
    - docs/exclusion.md
    - docs/exclusion.de.md
    - docs/exclusion.fr.md
    - tests/unit/test_docs_exclusion_truth.py
    - tests/contract/test_tool_bundles.py
    - README.md
    - README.de.md
    - README.fr.md
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md

key-decisions:
  - "Owner, 2026-11-13: option-push. Der Push ist freigegeben und wird von der Hauptsitzung ausgeführt, nicht von diesem Plan"
  - "files_update steht in der Bundle-Liste files aller drei READMEs mit dem Zusatz 'nur wenn aktiviert', weil Code und Lauf belegen, dass es mit dem Bundle abgeschaltet wird"
  - "Neue Verhaltensweisen (Netzfehler, Leerraum am Rand, x.part, Namensmeldung auf Nextcloud 35) stehen nur in den CHANGELOGs, nicht in den READMEs"
  - "CHANGELOG-Zeilen ohne 'nicht mehr': das Werkzeug war nie veröffentlicht, ein Leser des Release-Eintrags kennt kein Vorher"

patterns-established:
  - "Vor einer Aussage 'Push löst CI aus' die Trigger in .github/workflows lesen und prüfen, ob eine PR auf dem Branch liegt"

requirements-completed: [FOLD-06]

duration: ca. 1h
completed: 2026-11-13
---

# Phase 31 Plan 06: Doku-Pflichten, CHANGELOGs, Audit und Gates Summary

**Die Grenze "Ordner neben einem getaggten Ordner" steht dreisprachig in den exclusion-Seiten mit einem Befundlink unter docs/, den ein Test samt gepflanzter Gegenprobe hält; README.de.md und README.fr.md haben den Bundle-Abschnitt und die zwei fehlenden Tabellenzeilen, die drei CHANGELOGs je acht gleichlaufende Punkte unter [Unreleased]; alle Gates sind grün (5961 passed, 35 skipped, 16222 Bytes, 24 Werkzeuge). Owner-Entscheid: option-push.**

## Performance

- **Duration:** ca. 1h
- **Completed:** 2026-11-13
- **Tasks:** 3 von 3 (Task 3 mit Klauseln, die wegen einer widerlegten Annahme des Plans nicht wörtlich erfüllbar sind, siehe unten)
- **Files modified:** 12 (1 neu, 11 geändert)

## Owner-Entscheid zum Push (Task 3)

- **Antwort:** option-push, Owner am 2026-11-13, über die Hauptsitzung übermittelt (wörtlich "Go für alle Empfehlungen" auf die Empfehlung, den Branch zu pushen).
- **Stand beim Schreiben dieser Datei:** Push vom Owner freigegeben, wird von der Hauptsitzung ausgeführt. Dieser Plan hat nichts gepusht, keine PR angelegt und keinen Kommentar geschrieben.
- **Annahme des Plans widerlegt: ein reiner Branch-Push löst keinen CI-Lauf aus.** Beleg aus `.github/workflows` (nur gelesen):
  - `ci.yml`: `push` nur für `branches: [main]`, dazu `pull_request`; kein `workflow_dispatch`. Jobs: unit, image, exapp, canary-nc35, integration.
  - `security.yml`: `push` nur `main`, `pull_request`, Zeitplan. Jobs: codeql, reuse, pip-audit.
  - `scorecard.yml`: `push` nur `main`, Zeitplan.
  - `release.yml`: nur Tags `v*` und `workflow_dispatch`.
  - `issue-notify.yml`: nur Issues und `workflow_dispatch`.
  - `gh pr list --head plan/v1.8-tasks-080 --state all` ergab `[]`: es liegt keine PR auf dem Branch, die mitlaufen würde.
- **Folge:** Es gibt keine Lauf-URL. Der CI-Beleg (unter anderem canary-nc35) entsteht erst mit einer PR. Ob und wann eine PR angelegt wird, ist eine eigene Owner-Frage und noch nicht entschieden.
- **Was der Push veröffentlicht:** bei Abgabe des Checkpoints 52 Commits vor origin (origin laut `git ls-remote` auf c2e8fe9, Fast-Forward), dazu der Abschluss-Commit dieser Datei.
- **Prüfung auf Dinge, die nicht auf origin gehören (Diff gegen origin/plan/v1.8-tasks-080, 66 Dateien):** kein Pfad mit `.env`, `harp-certs`, `.pem`, `.key`, `.crt`, `.p12`, `.kdbx`, auch nicht in einem der Commits hinzugefügt und wieder entfernt; `.env.exapp` und `.harp-certs/` sind laut `git check-ignore` ignoriert; die 6 Geheimniswerte der lokalen `.env.exapp` kommen im Diff nicht vor (Vergleich ohne Ausgabe der Werte, Kontrolle mit bekanntem String greift); keine privaten Schlüssel, keine Token-Formen, keine App-Passwort-Form. Zur Kenntnis: 28 Dateien unter `.planning/phases` werden öffentlich, darunter Zeilen mit dem Pfad `C:/Users/Student` und eine Planzeile mit der Commit-Mailadresse; beides steht in dieser Form schon auf origin.

## Was geändert wurde

- **docs/exclusion.md, .de.md, .fr.md:** nach `tech-upload-oracle` der Abschnitt `<a id="tech-folder-oracle"></a>` mit Überschrift, einem Satz und der Quellzeile auf `folder-evidence.md#folder-next-to-a-tagged-folder`.
- **tests/unit/test_docs_exclusion_truth.py:** `STABLE_EVIDENCE_ANCHORS`, `ALL_ANCHORS` mit 22 Einträgen, `_stable_finding_problems`, der Seitentest je Sprache, die Gegenprobe mit gepflanztem Link auf `.planning/phases/` und mit einem Text ohne Link, ein Test für die Zahlen 22 und 17.
- **README.de.md, README.fr.md:** Abschnitt zum Abschalten von Tool-Bundles vor dem Abschnitt zum Tag `kein-ki`, Tabellenzeilen `files_read_as_markdown` und `files_update`, nach `31-06-README-ENTWURF.md` (Owner-Freigabe 13.11.2026).
- **README.md, README.de.md, README.fr.md:** `files_update` in der Bundle-Liste `files` mit "(only when enabled)", "(nur wenn aktiviert)", "(seulement si activé)".
- **tests/contract/test_tool_bundles.py:** `test_the_optional_update_tool_goes_off_with_the_files_bundle`.
- **CHANGELOG.md, .de.md, .fr.md:** unter [Unreleased] `### Added`, `### Hinzugefügt`, `### Ajouté` mit je 8 Punkten, ohne Versionsnummer, ohne Datum, ohne Issue-Nummer.

## Beleg zu files_update und Bundle files

- Code: Registrierung in `src/mcp_connector/server/reg_files.py` hinter `config.files_update_enabled()`; `_load_registrations()` in `server/__init__.py` importiert `reg_files` nicht, wenn `files` in `NC_MCP_DISABLED_TOOLS` steht.
- Lauf, je ein frischer Interpreter:
  - `NC_MCP_FILES_UPDATE=true`: 25 Werkzeuge, `files_update` dabei
  - `NC_MCP_FILES_UPDATE=true` und `NC_MCP_DISABLED_TOOLS=files`: 17 Werkzeuge, kein `files_*`
  - Standard: 24 Werkzeuge, `files_update` fehlt
- Der neue Contract-Test hält beides, mit Positivkontrolle.

## README-Klausel aus 31-03 Task 3

`grep -c files_create_folder`: README.md 2, README.de.md 2, README.fr.md 2. Zählung, Dash-Prüfung und ASCII-Umlaut-Prüfung der Klausel enden mit Exit 0. Die in 31-03 offene Klausel ist für alle drei Dateien erfüllt.

## Faktencheck der READMEs gegen die laufende Registry

- Registry im Standard: 24 Werkzeuge; alle drei READMEs nennen 24.
- Tabelle: je 25 Zeilen (24 plus `files_update`); Namen ohne `files_update` gleich der Registry; Stufen und Reihenfolge in DE und FR gleich README.md.
- Bundle-Liste in allen drei gleich den eingefrorenen `BUNDLE_TOOLS` plus `files_update`.
- `files_create_folder`: `MAX_NEW_FOLDERS = 10`, Schema "at most 10 new ones", Beschreibung "an existing folder answers created false", Annotation read_only False, destructive False, idempotent True; die Tabellenzeile sagt in allen drei Sprachen dasselbe.
- Abweichungen im Umfang der Phase: keine außer den freigegebenen Nachträgen.

### Liste für den Faktencheck in Phase 34 (gemeldet, nicht geändert)

1. README.de.md und README.fr.md sagen, die Tabelle werde nicht von Hand gepflegt, ein Contract-Test lese die laufende Registry. Der Test `test_the_readme_permission_table_matches_the_live_registry` liest nur README.md. Entweder den Test auf drei Dateien ausweiten oder den Satz anpassen.
2. Die Legende über der Tabelle erklärt in allen drei Sprachen nur `read` und `create-only`; die Tabelle führt auch `conditional-update`.
3. Der neue Abschnitt in DE und FR nennt `NC_MCP_FILES_ROOT` (freigegebener Wortlaut); die Variable wird in README.de.md und README.fr.md sonst nirgends erklärt, README.md erklärt sie im Abschnitt Clients.
4. Tabellenzeile `files_upload`: EN nennt "any-size binary upload"; DE und FR nennen die beliebige Größe nur im Abschnitt zu dem, was der Server nicht kann.
5. Abschnitt zu dem, was der Server nicht kann: EN hat "No user-visible moving or renaming" mit dem Zusatz zur privaten Chunk-Montage, DE und FR nur "Kein Verschieben, kein Umbenennen"; der Punkt zum Überschreiben ist in DE und FR anders aufgebaut als in EN.
6. README.fr.md mischt typografische Apostrophe (Zeilen 51, 53, 56) mit geraden im Rest; die neuen Zeilen nutzen gerade wie die Mehrheit.
7. README.de.md schreibt meist "Tools", im Abschnitt Enterprise "Werkzeug".
8. CHANGELOG.de.md und CHANGELOG.fr.md haben unten keine Linkzeile `[Unreleased]: ...compare...`; CHANGELOG.md hat sie.
9. `test_changelog_translations.py` vergleicht die Punktzahl nur für Versionsabschnitte, nicht für [Unreleased]; die 8, 8, 8 sind per awk gezählt und werden erst beim Versionssprung vom Test gehalten.

## Umlaut-Audit

Basis `91c3b5113c541999d3d3363ab71c6b26a9dd41c9` aus 31-BASE.txt, Positivkontrolle der Basis grün (40 Hex, Vorfahr von HEAD, 31-01-PLAN.md liegt in ihr).

- Gegentreffer: hinzugefügte Zeilen mit `files_create_folder` in README.de.md 2, in CHANGELOG.de.md 1.
- **Funde vorher (Stand 70edfad): 0. Funde nachher: 0.**
- Deutsch: 70 hinzugefügte Zeilen in README.de.md, docs/exclusion.de.md, CHANGELOG.de.md; strenge Liste 0 Treffer; alle Wörter mit ae, oe, ue gelesen: nur "Quelle", "neue", "neuer".
- Französisch: 71 hinzugefügte Zeilen; 0 akzentlose Schreibungen aus der Prüfliste, 102 Akzentbuchstaben vorhanden; das Muster greift auf einen gepflanzten Satz ohne Akzente.
- U+2013, U+2014, Emojis: 0 in den zehn nutzersichtbaren Dateien (ganze Datei) und 0 in den hinzugefügten Zeilen aller 55 in der Phase geänderten Dateien; das Muster greift auf gepflanzte Zeichen.

## Task Commits

1. **Task 1: Grenze tech-folder-oracle, Truth-Test mit Gegenprobe** - `d8fdb9b` (docs)
2. **Zusatz: README-Nachträge DE und FR, files_update in der Bundle-Liste, Contract-Test** - `d25249d` (docs)
3. **Task 2: drei CHANGELOG-Einträge, Audit, voller Lauf** - `58844ee` (docs)
4. **Task 3: Owner-Entscheid option-push** - in dieser Datei festgehalten, kein Code

## Verifikation (gesehene Ausgaben)

- Task 1, RED: 6 rote Tests (3x `test_the_page_carries_all_anchors`, 3x `test_each_stable_finding_lives_under_docs`), bevor die Seiten den Anker hatten; die Gegenprobe war schon grün. Danach `test_docs_exclusion_truth.py` und `test_exapp_env_setup.py`: 239 passed. `grep -A6 tech-folder-oracle ... | grep -c "\.planning"` ergibt 0; "All 22 ids" trifft in Zeile 110.
- Task 2, Klauseln vor dem Gate-Lauf: `files_create_folder` unter [Unreleased] in allen drei CHANGELOGs, je 8 Punkte, 0 Schließwörter mit Issue-Nummer, 0 Issue-Nummern, Gegentreffer der Basis, 0 Ersatzschreibungen, 0 Dashes in den zehn Dateien.
- Voller Lauf:

| Gate | Ergebnis |
| ---- | -------- |
| pytest tests/unit tests/contract | 5961 passed, 35 skipped, Exit 0 (vorher 5955; plus 5 im Truth-Test, plus 1 Bundle-Test) |
| check_tool_budget.py | 16222 Bytes, 24 Werkzeuge, Budget 18000, Exit 0 |
| ruff check . | Exit 0 |
| ruff format --check . | 375 Dateien, Exit 0 |
| pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest) | 0 errors, 0 warnings, Exit 0 |
| vulture src scripts vulture_whitelist.py | Exit 0 |

- Commits seit der Basis: 0 Treffer für co-authored-by, claude, assisted-by; alle Commits von street1983nk.
- Stand D-31-06: Nextcloud 32 und 35 belegt (docs/folder-evidence.md, Nachmessung 18 von 18 auf beiden).
- Kein Code von Phase 32 im Branch.

## Klauseln von Task 3 und der Plan-Verifikation

Erfüllt:

- Verify-Befehl von Task 3 (`grep -qE "option-(push|lokal)"` in dieser Datei).
- "Die SUMMARY nennt die Owner-Antwort option-push oder option-lokal mit Datum": option-push, 2026-11-13.
- "Es gibt keine PR und keinen Kommentar aus diesem Plan".
- Plan-Verifikation: drei exclusion-Seiten mit stabilem Link und grüner Gegenprobe; drei CHANGELOGs gleichlaufend; Umlaut-Audit 0 Funde, keine Dashes; voller Lauf grün ohne Phase 32; Push nur nach Owner-Freigabe.

Nicht wörtlich erfüllbar oder nicht von diesem Plan erfüllt, jeweils mit Grund:

1. **Action von Task 3, "die Lauf-URL aus `gh run list --branch plan/v1.8-tasks-080 --limit 1` in die SUMMARY":** nicht erfüllbar. Ein Branch-Push ohne PR startet keinen Workflow (Beleg oben), es gibt keinen Lauf und keine URL.
2. **Hinweis der Action und Pro-Punkt von option-push, der Push löse den CI-Lauf samt canary-nc35 aus und CI belege den grünen Stand:** trifft nicht zu. Der grüne Stand ist bisher nur lokal belegt; der CI-Beleg entsteht erst mit einer PR.
3. **Action von Task 3, "Nur bei option-push: `git push origin plan/v1.8-tasks-080`":** von diesem Plan nicht ausgeführt. Die Hauptsitzung führt den freigegebenen Push nach dem Abschluss-Commit einmal aus. Beim Schreiben dieser Datei ist der Branch deshalb noch vor origin.
4. **Akzeptanzkriterium "Ohne option-push ist `git status -sb` weiterhin ahead":** nicht anwendbar, die Antwort ist option-push.

## Deviations from Plan

### Zusätze auf Auftrag der Hauptsitzung (Owner-Freigabe 13.11.2026)

**1. Zusätzlicher Commit für die README-Nachträge**
- Bundle-Abschnitt und zwei Tabellenzeilen in README.de.md und README.fr.md, `files_update` in der Bundle-Liste aller drei READMEs. README.md, die beiden README-Übersetzungen und tests/contract/test_tool_bundles.py stehen nicht in `files_modified` des Plans.
- **Commit:** d25249d

**2. CHANGELOG mit 8 statt 4 Punkten**
- Zusätzlich: Netzfehler in der Ordnerkette (31-04b), Leerraum am Rand (D-31-08), `x.part` (D-31-09), Namensmeldung auf Nextcloud 35 (77cab44).
- **Commit:** 58844ee

### Eigene Entscheidungen

**3. Ein Contract-Test statt nur eines Laufs** für die README-Aussage zu `files_update`. Keine bestehende Erwartung geändert.

**4. Truth-Test strenger und um einen Test größer als verlangt:** `_stable_finding_problems` meldet einen Link aus docs/ hinaus auch neben einem guten Link; dazu `test_the_stable_limits_are_not_held_to_the_planning_folder` (22, 17, disjunkt) und zwei Sätze im Modul-Docstring.

**5. Task 1 als ein Commit** wie im Plan benannt, kein getrennter RED-Commit; RED wurde gesehen.

**6. Wortlaut in docs/exclusion.de.md:** "Abweisung" statt des Beispielworts "Ablehnung" aus dem Plan, weil die Seite durchgehend "Abweisung" schreibt.

**7. README-Entwurf, nur Typografie:** DE "MCP Server" statt "MCP-Server" wie im Bestand, Zeilen auf die Breite des Bestands umbrochen, FR mit geraden Apostrophen. Inhalt wie freigegeben.

**8. CHANGELOG-Wortlaut:** "`x.part` wird nicht als vorhandene Datei gemeldet" und die Zeile zu Nextcloud 35 ohne "nicht mehr", weil das Werkzeug nie veröffentlicht war. "fail-closed" ist ausgeschrieben. Der Verweis auf den Beleg steht als `docs/folder-evidence.md` in Backticks statt als Link, weil der Store den Abschnitt importiert und ein relativer Link dort bricht.

**9. pytest-Zahl** mit `-o addopts=""` plus den Filtern aus pyproject (`-m "not integration and not matrix" --import-mode=importlib`) ermittelt; die übrigen Klauseln des Verify-Befehls liefen wörtlich.

**10. Branch-Prüfung des Executor-Protokolls** (nur `worktree-agent-*`) nicht angewandt, weil der Auftrag `plan/v1.8-tasks-080` vorgibt.

**11. Annahme des Plans widerlegt:** ein Push startet keinen CI-Lauf, siehe Abschnitt zum Owner-Entscheid und die vier Klauseln oben.

**12. STATE.md, ROADMAP.md, REQUIREMENTS.md nicht angefasst** und kein gsd-sdk für den Stand benutzt; das macht die Hauptsitzung von Hand. `requirements-completed: [FOLD-06]` im Kopf dieser Datei ist die Meldung dazu, kein Eintrag in REQUIREMENTS.md.

## Issues Encountered

- Ein Hilfsskript schrieb beim ersten Versuch echte Zeilenumbrüche in ein Zeichenketten-Literal des Truth-Tests (Syntaxfehler beim Sammeln); vor dem ersten Testlauf von Hand korrigiert, nichts davon wurde committet.

## Offene Punkte

- **PR für den CI-Beleg:** eigene Owner-Frage, noch nicht entschieden. Ohne PR gibt es für diesen Stand keinen CI-Lauf.
- **Neun Punkte für den Faktencheck in Phase 34**, siehe oben.
- Kein Release, kein Tag, keine Store-Einreichung, kein Versionssprung in diesem Plan (Phase 34).

## Known Stubs

Keine.

## Next Phase Readiness

- FOLD-06 ist vollständig: READMEs, exclusion-Seiten mit stabilem Beleg, CHANGELOGs, alle Gates grün ohne Phase 32. Phase 31 ist für sich releasefähig (Rückfallschnitt gewahrt).
- Phase 32 ändert dieselben Gate-Dateien (Werkzeugmenge, Budget, READMEs, CHANGELOGs) und setzt auf diesem Stand auf.

## Self-Check: PASSED

- Dateien vorhanden: die elf geänderten Dateien und diese SUMMARY.
- Commits vorhanden: d8fdb9b, d25249d, 58844ee.

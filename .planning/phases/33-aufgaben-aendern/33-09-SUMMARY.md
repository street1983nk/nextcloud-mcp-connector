---
phase: 33-aufgaben-aendern
plan: 09
subsystem: tasks-modify-closing
tags: [tasks, budget, audit, kanarie, abnahme, readme, changelog, schalter]
requires: ["33-02", "33-06", "33-07", "33-08"]
provides:
  - "Endgültiger Budgetanker 26000 (22198 Bytes mit allen Schaltern an, 31 Werkzeuge)"
  - "Satz der Server-Instruktion zu tasks_complete, tasks_update, tasks_move nur bei NC_MCP_TASKS_UPDATE an"
  - "Audit-Gate je Aufruf für die drei ändernden Werkzeuge (Subprozess, Schalter an)"
  - "Kanarie mit Schalter an (30 Werkzeuge), echte Aufrufe mit frischer ETag, Deck-Schlüssel abgelehnt, zweite Aufgabenliste der Welt"
  - "Abnahmeskript: update, complete, move über die ETag-Kette, dann veraltete ETag abgelehnt"
  - "README EN/DE/FR: Schalter mit Label, Stufen conditional-update und modify erklärt, tasks-Bundle nennt die drei; Rechtetabellen-Gate über alle drei READMEs"
  - "CHANGELOG EN/DE/FR [Unreleased]: die drei Werkzeuge hinter dem Schalter"
affects: [33-10, 34]
key-files:
  modified:
    - scripts/check_tool_budget.py
    - src/mcp_connector/server/__init__.py
    - tests/contract/test_tool_surface.py
    - tests/contract/test_audit_surface.py
    - tests/integration/test_canary.py
    - tests/integration/canary_world.py
    - tests/unit/test_live_requirement.py
    - .github/workflows/ci.yml
    - scripts/acceptance_all_tools.py
    - README.md
    - README.de.md
    - README.fr.md
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md
decisions:
  - "Budget bleibt 26000: Endstand 22198 Bytes mit allen Schaltern an, 22198 + 15 Prozent = 25527.7, auf 500 aufgerundet 26000"
  - "Abnahmeskript verschiebt in die eigene Liste (already true), weil das Testkonto genau eine eigene Liste hat; die echte Verschiebung zwischen zwei Listen belegt die Kanarie"
  - "Der Schalter der Kanarie steht im CI-Schritt (env), weil der Server ihn beim Import liest; die Kanarie bricht ohne ihn mit klarer Meldung ab"
metrics:
  completed: 2026-11-14
  tasks: 3
---

# Phase 33 Plan 09: Abschluss Aufgaben ändern Summary

Budget aus dem Endstand verankert (26000), Server-Instruktion mit ETag-Satz nur bei eingeschaltetem `NC_MCP_TASKS_UPDATE`, Audit je Aufruf belegt, Kanarie und Abnahmeskript rufen die drei ändernden Werkzeuge mit Schalter an echt auf, drei READMEs und drei Changelogs nachgezogen, soweit Phase 33 es verlangt.

## Vorprüfung Abschnitt 11 (DROP)

- `raw/33-drop.txt` existiert nicht; keine DROP-Zeile.
- 33-06-, 33-07- und 33-08-SUMMARY vorhanden; alle drei Werkzeuge gebaut (tasks_complete 579 B, tasks_update 1324 B, tasks_move 611 B). Kein Rückbau nötig, kein Verify aus Abschnitt 11 auszuführen.

## Commits

| Task | Schritt | Commit | Inhalt |
|------|---------|--------|--------|
| 1 | RED | 24de427 | test(33-09): audit per call and instruction sentence |
| 1 | GREEN | cf5d30a | feat(33-09): budget anchored on the measured end state |
| 2 | - | 512ce54 | test(33-09): canary and acceptance with the tasks_update switch on |
| 3 | RED | faede92 | test(33-09): readme permission tier for modifying tools |
| 3 | GREEN | 1836c6c | docs(33-09): permission table, switch and changelogs for the modifying task tools |

Alle als `street1983nk <k.cherif@outlook.de>`, ohne Trailer, ohne closes-Wörter, nur lokal, kein Push. STATE, ROADMAP und REQUIREMENTS nicht angefasst (Vorgabe der Hauptsitzung).

### Rote Tests der RED-Commits

- 24de427: 2 failed, `test_the_instruction_names_the_modifying_task_tools_only_with_their_switch_on[off-on]` und `[on-on]`; Gesamtlauf 8153 passed, 35 skipped. Die neuen Audit-Fälle (answered, refused) waren schon grün: Charakterisierung, das Verhalten bestand seit 33-06 bis 33-08 über `@graceful`.
- faede92: 3 failed, `test_each_readme_documents_the_tasks_update_switch[README.md|README.de.md|README.fr.md]` (Label fehlt, Schalter nur in der Tabelle, Bundle-Zeile ohne die drei). Die Rechtetabellen aller drei READMEs waren schon richtig (Zeilen aus 33-06 bis 33-08).

## Budget (wörtlich)

Kommentar in `scripts/check_tool_budget.py`:

```
#   Measurement 2026-11-14, 31 tools with every switch on: 22198 bytes; standard state
#               18770 bytes, 27 tools. The end state of phase 33 (plan 33-09): ...
#   Budget      22198 + 15 percent = 25527.7, rounded up to the next 500 = 26000 bytes,
#               anchored by the house rule on the measured end state (D-33-04, TMOD-05).
```

Ausgabe:

```
tools/list with every switch on: 22198 bytes, 31 tools, budget 26000
  tasks_create: 1380 bytes
  files_upload: 1377 bytes
  tasks_update: 1324 bytes
  mail_browse: 1237 bytes
  calendar_create_event: 1165 bytes
control, standard state: 18770 bytes, 27 tools
```

`BUDGET_BYTES = 26_000`, `MAX_TOOL_BYTES = 1400` unverändert; kein Werkzeug über 1400.

## Umgesetzt

- Instruktion: Schalter aus byte-gleich wie vorher (Test über alle vier Kombinationen files/tasks); an: " Existing tasks can be completed, changed or moved with tasks_complete, tasks_update and tasks_move, and only with the ETag from tasks_read."
- Audit (T-33-09-02): frischer Interpreter mit Schalter an, Aufruf der registrierten (dekorierten) Funktion je Werkzeug mit echtem AuditStore; je Aufruf genau ein Eintrag, Werkzeugname, Parameternamen exakt aus der Allowlist (tasks_update: etag, priority, tags, task_id; summary und description nie), kein Wert in irgendeiner Spalte; abgelehnter Aufruf ebenso genau ein Eintrag mit `rejected`/`guard_tripped`.
- Kanarie: `EXPECTED_TOOLS = 30` (27 plus die drei, Kommentar "with NC_MCP_TASKS_UPDATE on"), `TASK_TOOLS` um die drei erweitert (DECK-Prüfung greift), Plan: complete an/aus, update setzt einen Tag, move in die zweite Liste und zurück, je mit ETag eines tasks_read direkt davor (`ETAG`-Zeilen); Deck-Schlüssel als task_id bei allen dreien und als Zielliste bei tasks_move müssen abgelehnt werden (`AENDERN`-Zeilen). `WRITE_KINDS` unverändert. canary_world.py legt die zweite Liste `<stamm>-ziel` an (VTODO, eigen, schreibbar geprüft) und baut sie ohne Papierkorb ab. CI-Schritt der Kanarie setzt `NC_MCP_TASKS_UPDATE: "on"`, gepinnt in `tests/unit/test_live_requirement.py`.
- Abnahmeskript: Schalter `NC_MCP_FILES_UPDATE`/`NC_MCP_TASKS_UPDATE` werden an den stdio-Server weitergereicht, wenn gesetzt; Kette create, read (ETag), update, complete, move, dann update mit der ersten ETag: Ablehnung erwartet, sonst FAIL; Schalter aus: "not registered (switch off)".
- READMEs: Rechtetabellen-Gate jetzt über alle drei READMEs mit Gegenprobe (falsche Stufe, fehlende Zeile, conditional-update statt modify werden gemeldet); neues Gate für Schalter-Label und Bundle-Zeile mit Gegenprobe.

## Inventar

- Abgehakt (plan=33-09): `tests/integration/test_canary.py:99` und `:349` (Kanarie, PUT/MOVE). Die Rohdatei selbst wurde nicht geändert (nur Code, Tests, Doku und SUMMARY werden committet).
- Offen für Phase 34 (plan=34, zusage-doku, -store, -server): README.md 5, README.fr.md 5, README.de.md 4, .planning/PROJECT.md 5, docs/threat-model.md 4, docs/conference-talk.md 4, docs/privacy.md 3, docs/hardening*.md 3/3/2, appinfo/info.xml 3, src/mcp_connector/server/__init__.py 2 (Wortlaut der Schreibzusage, DOC-05), docs/conference-demo.md 2, docs/faq.md, docs/exapp-install.md, docs/client-setup.md je 1. Insbesondere stehen in den READMEs noch "No user-visible moving or renaming" / "Kein Verschieben" / "Aucun déplacement" ohne Ausnahme für tasks_move bei eingeschaltetem Schalter: Präzisierung der Schreibzusage ist Phase 34.

## Gates (Endstand, alle Exit 0)

- pytest unit+contract: 8162 passed, 35 skipped
- check_tool_budget: Exit 0 (Zeilen oben)
- ruff check grün; ruff format --check: 403 Dateien formatiert
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0
- py_compile test_canary.py, canary_world.py, acceptance_all_tools.py: ok; Kanarie ohne Live-Umgebung: 4 skipped (Live in 33-10)
- Doku: NC_MCP_TASKS_UPDATE in allen drei READMEs, "Bestehende Aufgaben ändern erlauben" in README.de.md, kein U+2013/U+2014 in READMEs und Changelogs
- TASK-01: SHA-Form und Vorfahr ok, Diff über caldav.py, calendar.py und die vier Kalendertests 0 Zeilen; Gegentreffer server/__init__.py (21 Einfügungen gegen die Basis)
- Kein Docker gebraucht, kein Container gestartet

## Deviations from Plan

1. [Rule 2] `tests/unit/test_live_requirement.py` (nicht in files_modified): Pin, dass der CI-Schritt der Kanarie `NC_MCP_TASKS_UPDATE: "on"` trägt, nach dem vorhandenen Muster des Schalters NC_MCP_REQUIRE_LIVE.
2. [Rule 3] Abnahmeskript: der stdio-Server bekam bisher nur `REQUIRED_ENV`; ohne Weiterreichen des Schalters wären die drei Werkzeuge nie registriert. `FORWARDED_SWITCHES` reicht nur die zwei Schalter weiter.
3. Abnahmeskript, tasks_move: das Testkonto hat genau eine eigene Liste (tasks_create ohne list setzt das voraus), daher Verschieben in die eigene Liste mit Erwartung `already: true`; die echte Verschiebung belegt die Kanarie mit der zweiten Liste.
4. Wortlaut: DE-Schaltertext aus 33-02 sagt "mit der ETag, die tasks_read geliefert hat"; in README.de.md steht "mit dem ETag, das tasks_read geliefert hat", weil README.de.md ETag sonst durchgehend neutral/maskulin führt ("ihr ETag", "dem ETag aus tasks_read"). Owner bitte entscheiden.
5. README.fr.md, Zeile tasks_complete aus 33-06: "en la terminant, ses sous-tâches sont terminées d'abord" (hängendes Gerundium) ersetzt durch "si elle est terminée, ses sous-tâches le sont d'abord".
6. README EN/DE/FR: Einleitung der Tabelle erklärt jetzt auch **conditional-update** und **modify** (vorher nur read und create-only).
7. Ein schwacher Gegenproben-Test zum Audit (zwei Stores) vor dem RED-Commit wieder entfernt; die Gegenproben zum Audit-Gate selbst stehen weiter in den bestehenden Allowlist-Fällen.

## Geänderte nutzersichtbare Texte (zur Durchsicht)

- Server-Instruktion (EN, nur bei Schalter an): siehe oben.
- README.md: neuer Punkt unter "What this server cannot do" (Schalter, Label "Allow changing existing tasks", Text aus 33-02), Einleitung der Tabelle (conditional-update, modify), Bundle-Zeile `tasks` "..., and `tasks_complete`, `tasks_update`, `tasks_move` (only when enabled)".
- README.de.md: entsprechender Punkt unter "Was dieser Server nicht kann" (Label "Bestehende Aufgaben ändern erlauben"), Einleitung der Tabelle, Bundle-Zeile "... sowie ... (nur wenn aktiviert)".
- README.fr.md: Punkt unter "Ce que ce serveur ne peut pas faire" (interrupteur « Autoriser la modification des tâches existantes »), Einleitung, Bundle-Zeile "... et ... (seulement si activé)", Korrektur der Zeile tasks_complete.
- CHANGELOG.md / .de.md / .fr.md [Unreleased] Added/Hinzugefügt/Ajouté: je zwei Punkte (drei Werkzeuge hinter dem Schalter, ab Werk aus, Bundle tasks; tasks_read liefert die ETag, veraltete ETag und wiederkehrende Aufgaben abgelehnt).

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche über das Threat Model hinaus. T-33-09-01 (Rechtetabelle aller drei READMEs gegen die Registry), -02 (Audit je Aufruf), -03 (Kanarie mit Deck-Schlüsseln und Deck-Marken-Prüfung für die drei), -04 (Budget aus dem Endstand, Decke 1400) umgesetzt.

## Self-Check: PASSED

Commits 24de427, cf5d30a, 512ce54, faede92, 1836c6c im Log; alle geänderten Dateien vorhanden; Scratchpad-Ordner p33 wird nach dem Commit dieser SUMMARY gelöscht.

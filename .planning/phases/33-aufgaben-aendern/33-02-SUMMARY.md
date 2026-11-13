---
phase: 33-aufgaben-aendern
plan: 02
subsystem: schalter-und-gates
tags: [tasks, schalter, annotationen, audit, budget, optionale-werkzeuge]
requires: ["33-01c"]
provides:
  - "config.ENV_TASKS_UPDATE, config.tasks_update_enabled() (ab Werk aus)"
  - "Admin-Checkbox tasks_update, info.xml-Variable NC_MCP_TASKS_UPDATE, Übernahme in entry_exapp vor build_exapp_app"
  - "server.MODIFY_EXISTING (read_only False, destructive True, idempotent True, open_world False)"
  - "tests/contract/optional_surface.py: OPTIONAL_TOOLS, SWITCHES, switched_on_surface(), surface_findings()"
  - "MODIFY_TOOLS (test_tool_surface.py), SWITCHED_TOOLS (test_exapp_tasks_update_switch.py), OPTIONAL_WITHOUT_PARAMETER_RECORD (test_audit_surface.py), TOTAL_SWITCHED_ON (test_tool_classes.py)"
  - "scripts/check_tool_budget.py misst maßgeblich mit allen Schaltern an, Standard als Kontrollzeile"
affects: [33-06, 33-07, 33-08, 33-09, 33-10]
tech-stack:
  added: []
  patterns: ["Messung der Oberfläche mit allen Schaltern an im frischen Interpreter, JSON auf stdout", "Prüffunktion geteilt von Gate und Gegenprobe"]
key-files:
  created:
    - tests/contract/optional_surface.py
    - tests/unit/test_exapp_tasks_update_switch.py
  modified:
    - src/mcp_connector/config.py
    - src/mcp_connector/entry_exapp.py
    - src/mcp_connector/exapp/config_values.py
    - src/mcp_connector/exapp/admin_settings.py
    - src/mcp_connector/exapp/ui/strings.py
    - src/mcp_connector/server/__init__.py
    - appinfo/info.xml
    - scripts/check_tool_budget.py
    - vulture_whitelist.py
    - tests/contract/tool_classes.py
    - tests/contract/test_tool_surface.py
    - tests/contract/test_tool_bundles.py
    - tests/contract/test_audit_surface.py
    - tests/contract/test_tool_classes.py
    - tests/unit/test_config.py
    - tests/unit/test_exapp_config_values.py
    - tests/unit/test_exapp_admin_settings.py
    - tests/unit/test_exapp_entry.py
    - tests/unit/test_exapp_lifecycle.py
    - tests/unit/test_exapp_env_setup.py
decisions:
  - "BUDGET_BYTES bleibt 22000: Messung mit allen Schaltern an 19683 Bytes (28 Werkzeuge), Standard 18770 Bytes (27); files_update 912 Bytes, kein Werkzeug über 1400"
  - "Klassen-Gate: unclassified prüft weiter nur die Standard-Registry, stale berücksichtigt die Oberfläche mit Schaltern an (files_update bleibt unklassifiziert wie vor Phase 33)"
  - "Budget-Skript misst beide Zustände per Subprozess und nimmt NC_MCP_DISABLED_TOOLS aus der Umgebung, damit die Messung die ganze Oberfläche wiegt; main() ist jetzt synchron"
metrics:
  completed: 2026-11-13
  tasks: 3
---

# Phase 33 Plan 02: Schalter NC_MCP_TASKS_UPDATE, Klasse MODIFY_EXISTING, Gates mit Schaltern an Summary

Der Schalter `NC_MCP_TASKS_UPDATE` steht als ganze Kette nach dem Vorbild `NC_MCP_FILES_UPDATE` (ab Werk aus, Formular gewinnt vor Deploy-Variable), die Annotationsklasse `MODIFY_EXISTING` nach D-33-12 ist angelegt, und Annotations-, Bundle-, Audit-, Klassen- und Budget-Gate messen zusätzlich die Oberfläche mit allen Schaltern an; noch kein Werkzeug hängt am neuen Schalter.

## Commits

| Task | Schritt | Commit | Inhalt |
|------|---------|--------|--------|
| 1 | RED | e40f5c3 | test(33-02): tasks_update switch chain |
| 1 | GREEN | c0c7cd7 | feat(33-02): admin switch NC_MCP_TASKS_UPDATE, off by default |
| 2 | RED | 323c815 | test(33-02): annotation class and optional tools in the surface gates |
| 2 | GREEN | 3350c62 | feat(33-02): annotation class MODIFY_EXISTING and switched-on surface |
| 3 | RED | 5956240 | test(33-02): audit and class gates know optional tools |
| 3 | GREEN | 92b5b57 | feat(33-02): budget measured with every switch on |

Alle als `street1983nk <k.cherif@outlook.de>`, ohne Trailer, nur lokal.

### Rote Tests der RED-Commits

- e40f5c3: 101 failed, 5 errors, ausschließlich in den sieben geänderten bzw. neuen Unit-Testdateien (fehlendes `config.ENV_TASKS_UPDATE`/`tasks_update_enabled`, `strings.ADMIN_FIELD_TASKS_UPDATE_*`; die `start`-Hilfe in test_exapp_entry.py nennt die neue Variable, darum fallen dort viele Fälle; die 5 errors sind die Fixture `standard_tools` des Subprozess-Tests).
- 323c815: Sammelfehler in test_tool_surface.py und test_tool_bundles.py (`ImportError: cannot import name 'MODIFY_EXISTING'`).
- 5956240: 7 failed in test_tool_classes.py (4, `freeze_findings` ohne `switched_on`) und test_tool_surface.py (3, `gate.measure`, `gate.findings`, `gate.main` synchron). Die neuen Audit-Fälle waren schon grün, weil sie nur Testcode brauchen.

## Budgetzeilen (wörtlich)

```
tools/list with every switch on: 19683 bytes, 28 tools, budget 22000
  tasks_create: 1380 bytes
  files_upload: 1377 bytes
  mail_browse: 1237 bytes
  calendar_create_event: 1165 bytes
  files_update: 912 bytes
control, standard state: 18770 bytes, 27 tools
```

Kommentarzeile im Skript: "Measurement 2026-11-13, 27 standard tools plus files_update, switches on: 19683 bytes; standard state 18770 bytes." Kein Abbruchkriterium greift (19683 unter 22000, files_update 912 unter 1400). Puffer 2317 Bytes, laut RESEARCH zu wenig für alle drei ändernden Werkzeuge (Prototypen 596 + 1368 + 564 plus Mehrbytes tasks_read), darum verankern 33-06 bis 33-08 je neu.

## Gates (Endstand nach 92b5b57)

- pytest unit+contract: 6542 passed, 35 skipped
- check_tool_budget: Exit 0 (Zeilen oben)
- ruff check: grün; ruff format --check: 396 Dateien formatiert
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0
- `grep "TMOD-05.*destructive_hint=True" .planning/REQUIREMENTS.md`: Treffer (Wortlaut nach D-33-12 lag schon im Repo)
- TASK-01-Diff gegen 33-BASE leer (0 Zeilen), Positivkontrolle SHA und Vorfahre ok, Gegentreffer im selben Diff: src/mcp_connector/config.py +27 Zeilen
- Keine neuen Großbuchstaben-Nadeln MOVE/DELETE/COPY/PROPPATCH in `src/`, kein U+2013/U+2014 in den hinzugefügten Zeilen (Gegentreffer mit gepflanztem Zeichen geprüft)
- Kein Docker gebraucht, kein Container gestartet

## Was die Folgepläne eintragen

- 33-06 bis 33-08: Namen in `optional_surface.OPTIONAL_TOOLS` (Wert `NC_MCP_TASKS_UPDATE`), `MODIFY_TOOLS` in test_tool_surface.py, `SWITCHED_TOOLS` in test_exapp_tasks_update_switch.py, `TOTAL_SWITCHED_ON` in test_tool_classes.py um eins hoch, Allowlist und `UNAFFECTED`-Eintrag; 33-06 entfernt `tasks_update_enabled` wieder aus vulture_whitelist.py, sobald reg_tasks.py es liest.
- 33-09: Stufe `modify` in README-Tabelle und `test_the_readme_permission_table_matches_the_live_registry`, Server-Instruktion, DE/FR-Schaltertexte aus dem Plankontext.

## Deviations from Plan

1. [Rule 1, übersehene Zählstelle] `test_no_field_of_the_form_offers_a_level_of_recording` zählt die Formularfelder (`len(fields) == 8`); die Grep-Liste des Plans fand sie nicht. Im GREEN-Commit c0c7cd7 auf 9 gezogen.
2. [Rule 3, Gate] vulture meldete `tasks_update_enabled` als unbenutzt (der Leser ist reg_tasks.py ab 33-06). Befristeter Eintrag mit Begründung in `vulture_whitelist.py` (nicht in files_modified des Plans), Commit c0c7cd7.
3. [Rule 3] `scripts/check_tool_budget.py`: `main()` ist synchron geworden (zwei Messungen im Subprozess); `test_the_byte_gate_counts_exactly_as_many_tools_as_this_file_freezes` ruft `gate.main()` ohne `await`. Die Gegenprobe zum Budget (gepflanzte Größe) steht in test_tool_surface.py neben dem Lader des Skripts statt in einem eigenen Unit-Test; sie läuft über `gate.findings`, dieselbe Funktion wie `main`. Ein Test hält `gate.SWITCHES` gleich `optional_surface.SWITCHES`.
4. Zusätzlich zum Plan: Audit-Marker-Prüfung (`@graceful`) auch über die Oberfläche mit Schaltern an, und `test_tool_classes` ruft auch im Haupt-Gate und im Sondentest `freeze_findings(..., switched_on=...)`, damit Einträge aus 33-06 bis 33-08 dort nicht als stale fallen.
5. Beobachtung, nicht behoben (außerhalb des Umfangs): `files_update` steht weiter in keiner Klasse von tool_classes.py; das Klassen-Gate verlangt Klassifikation nur für die Standard-Registry. Ob files_update als Datei-Schreiber mit Paarfall klassifiziert werden soll, ist eine eigene Entscheidung.
6. Arbeitsweise: ein versehentlicher Aufruf von System-`python` hing auf stdin und wurde beendet; keine Wirkung auf Dateien.

## Known Stubs

Keine. `MODIFY_TOOLS` und `SWITCHED_TOOLS` sind absichtlich leer (Plan: 33-06 bis 33-08 füllen sie).

## Threat Flags

Keine neue Angriffsfläche über das Threat Model hinaus; der Schalter ist ab Werk aus und registriert noch kein Werkzeug.

## Self-Check: PASSED

Commits e40f5c3, c0c7cd7, 323c815, 3350c62, 5956240, 92b5b57 im Log; tests/contract/optional_surface.py und tests/unit/test_exapp_tasks_update_switch.py vorhanden; `<name>NC_MCP_TASKS_UPDATE</name>` in info.xml und `os.environ[config.ENV_TASKS_UPDATE]` in entry_exapp.py gefunden.

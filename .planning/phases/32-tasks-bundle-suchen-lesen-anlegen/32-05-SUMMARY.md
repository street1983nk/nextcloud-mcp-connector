---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 05
subsystem: tasks-registration
tags: [registrierung, bundle, budget, gates, readme, changelog]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-04 (search_tasks, read_task), 32-04b (create_task)
provides:
  - server/reg_tasks.py mit tasks_search, tasks_read (READ_ONLY) und tasks_create (CREATE_ONLY), Bundle tasks
  - Oberflächen-Gates auf 27 Werkzeuge, zwölf Bundles, CREATE_TOOLS sieben, UNAFFECTED zehn
  - BUDGET_BYTES 22000 nach der Hausregel aus der Messung 18747 Bytes
  - READMEs (drei Sprachen), info.xml (gültige Bundle-Namen), Verweis in docs/folder-evidence.md, drei CHANGELOGs
affects: [32-05b, 32-06, 32-07, 32-08, 33, 34]

tech-stack:
  added: []
  patterns:
    - "Drahtname list mit noqa: A002 und Weitergabe als list_name="
    - "status als Literal, priority mit Field(ge=0, le=9)"

key-files:
  created:
    - src/mcp_connector/server/reg_tasks.py
  modified:
    - src/mcp_connector/audit/allowlist.py
    - vulture_whitelist.py
    - scripts/check_tool_budget.py
    - tests/contract/test_tool_surface.py
    - tests/contract/test_tool_bundles.py
    - tests/contract/tool_classes.py
    - tests/contract/test_tool_classes.py
    - tests/unit/test_disabled_tools.py
    - README.md
    - README.de.md
    - README.fr.md
    - appinfo/info.xml
    - docs/folder-evidence.md
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md

key-decisions:
  - "tasks_create auf 1364 Bytes gekürzt (Prototyp 1417), MAX_TOOL_BYTES bleibt 1400"
  - "BUDGET_BYTES 22000: 18747 + 15 Prozent = 21560, auf die nächsten 500 = 22000; Phase 33 verankert für ihre Werkzeuge erneut (TMOD-05)"
  - "Bundle tasks steht alphabetisch nach talk (talk < tasks), nicht zwischen tables und talk wie im Plan notiert"

patterns-established:
  - "Die vorübergehenden vulture-Einträge search_tasks, read_task, create_task verließen die Liste mit ihrem Aufrufer reg_tasks.py"

requirements-completed: [TASK-02, TASK-04, TASK-05, TASK-06, TASK-08]

duration: ca. 40min
completed: 2026-11-13
---

# Phase 32 Plan 05: Registrierung des Bundles tasks, Budget und Doku Summary

**Drei Aufgabenwerkzeuge registriert (`tasks_search` 863, `tasks_read` 295, `tasks_create` 1364 Bytes), alle Oberflächen-Gates auf 27 Werkzeuge in zwölf Bundles nachgezogen, Budget nach der Hausregel auf 22000 Bytes neu verankert, Doku und CHANGELOGs dreisprachig.**

## Ergebnis je Task

| Task | Ergebnis | Commit |
|---|---|---|
| 1: reg_tasks.py, Budget, Allowlist, vulture, Gates | Registrierung nach dem Muster reg_calendar.py; Budget vor jedem anderen Gate gemessen; tasks_create schon im ersten Entwurf unter der Decke; Allowlist, vulture, sechs Gate-Dateien; Prüflauf 167 passed (mit `-k "not readme and not documented"`), vulture leer, EXPECTED_PUT_CALLS 6 und test_no_destructive_calls.py gegen die Basis unverändert (Gegentreffer: tools/tasks.py mit 1078 Zeilen im selben Diff) | gemeinsam mit Task 2 |
| 2: READMEs, info.xml, Beleg-Verweis, volle Gates | Zahlsatz 27 Werkzeuge in zehn Familien, drei Tabellenzeilen, Bundle-Zeile; info.xml nur die Beschreibung von NC_MCP_DISABLED_TOOLS; Verweiszeile am Kopf von docs/folder-evidence.md | `58f211d` |
| 3: CHANGELOGs, Sprach-Grep, volle Gates | Sieben Punkte je Sprache unter `### Added`; Sprach-Grep ohne Befund | `4573981` |

## Bytegrößen und Budget

| Werkzeug | Bytes |
|---|---|
| `tasks_search` | 863 |
| `tasks_read` | 295 |
| `tasks_create` | 1364 (Prototyp der Recherche: 1417) |

Größtes Werkzeug bleibt `files_upload` mit 1377 Bytes; `MAX_TOOL_BYTES = 1400` unverändert.

Messzeile in `scripts/check_tool_budget.py`:

```text
Measurement 2026-11-13, all 27 curated tools registered (tasks_search, tasks_read,
            tasks_create of TASK-07): 18747 bytes. The three tools are 863, 295 and
            1364 bytes; tasks_create was cut from the 1417 of its prototype to fit the
            per tool ceiling, which stays where it is.
Budget      18747 + 15 percent = 21560, rounded up to the next 500 = 22000 bytes,
            re-anchored at 22000 by the house rule (E1, TASK-08); phase 33 re-anchors
            for its own tools (TMOD-05).
```

N = 18747, X = 22000 (18747 x 1,15 = 21559,05, aufgerundet 21560). `check_tool_budget.py`: `tools/list: 18747 bytes, 27 tools, budget 22000`, Exit 0.

Gekürzt wurde gegenüber dem Prototyp vor allem bei den Feldbeschreibungen; erhalten blieben das Format von `due`/`start` ("YYYY-MM-DD, or ISO 8601 with zone"), `parent` als "Task id from tasks_search", `list` mit "required for a shared list", die Spanne von `priority` ("1 high to 9 low, 0 none") und die IANA-Zone mit Beispiel.

## Gate-Zahlen

Vor `58f211d` und vor `4573981` jeweils alle Exit 0:

- pytest unit+contract: 6305 passed, 35 skipped (beide Läufe)
- check_tool_budget.py: 18747 Bytes, 27 Werkzeuge, Budget 22000
- ruff check: All checks passed; ruff format --check: 390 files already formatted
- pyright: 0 errors, 0 warnings, 0 informations
- vulture: leer

Sprach-Grep aus Task 3 über die Diff-Zeilen gegen die Basis: DE 0 Treffer, FR 0 Treffer, U+2013/U+2014 0 Treffer. Positivkontrolle: 7 Diff-Zeilen DE mit Umlaut oder ß, 15 Diff-Zeilen FR mit Akzent.

## Erfüllte Anforderungen

- TASK-08 vollständig.
- TASK-02, TASK-04, TASK-05, TASK-06: im Code seit 32-04/32-04b erfüllt, laut den SUMMARYs von 32-04 und 32-04b "abgehakt erst mit der Registrierung (32-05)"; jetzt registriert und über die Contract-Gates erreichbar. Der Live-Beweis folgt in 32-07.
- Nicht abgehakt: TASK-03 (verlangt ausdrücklich den Live-Fall, 32-05b/32-07), TASK-07 (Kanarie, Abnahmeskript, CI in 32-05b, `docs/hardening*.md` in 32-06 stehen noch aus; der Registrierungs-, Gate-, README- und CHANGELOG-Teil ist hier erledigt), TASK-09 (32-06).

## Deviations from Plan

**1. [Rule 1 - Bug] Reihenfolge des Bundles tasks**
- **Gefunden in:** Task 1
- **Problem:** Der Plan nennt `tasks` "zwischen `tables` und `talk`". Alphabetisch steht `talk` vor `tasks` (l vor s); `bundle_names()` liefert sortiert, `test_the_bundle_names_are_frozen` war damit rot.
- **Fix:** `tasks` nach `talk` in test_tool_bundles.py, test_disabled_tools.py (`KNOWN`), in den Bundle-Listen der drei READMEs und in info.xml.
- **Commit:** `58f211d`

**2. Anker in tool_classes.py**
- Statt der geschätzten Bereiche die tatsächlichen Zeilen von tools/tasks.py: `_fields` 154-181, `_as_hit` 505-520, Antwort von read_task 603-641, Antwort von create_task 806-817.

Sonst wie geplant. Kein Docker.

## Hinweis W2 (Umfang 32-05 und 32-06)

Der Umfang (17 Dateien, überwiegend mechanisch) hat bei der Ausführung keine Probleme gemacht: Kontext reichte, die Änderungen waren je Datei klein (183 Zeilen im ersten Commit, davon 103 in reg_tasks.py). Konflikte mit 32-06 sind noch keine entstanden, weil 32-06 noch nicht lief. Für 32-06 zu beachten: README-Tabellen und CHANGELOG `### Added` sind jetzt um die Aufgabenzeilen länger; die fetch-Zeile der READMEs ist unverändert, und der neue CHANGELOG-Block endet mit dem Punkt "Measured on ... `docs/tasks-evidence.md`" (32-06 fügt seine Punkte davor oder gleichlaufend in allen drei Sprachen ein, sonst schlägt test_changelog_translations nicht an, aber die Reihenfolge wird uneinheitlich).

## Known Stubs

- CHANGELOG-Punkt "Measured on Nextcloud 32 and 35 under AppAPI impersonation, see `docs/tasks-evidence.md`" (alle drei Sprachen): die Seite und die Messung entstehen erst in 32-07; der Wortlaut ist vom Plan vorgegeben und steht unter `[Unreleased]`.

## Self-Check: PASSED

- src/mcp_connector/server/reg_tasks.py vorhanden; Commits 58f211d und 4573981 im Log; beide ohne Trailer.

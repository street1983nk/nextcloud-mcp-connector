---
type: quick
status: complete
date: 2026-09-23
task: BL-15, ehrliche Suchnote und Tool-Beschreibung von unified_search
commits:
  - 9a32764: "test(search): the tool description must not deny content hits (BL-15)"
  - 6ee0a03: "fix(search): the tool description defers to the note instead of denying content hits (BL-15)"
  - 5c4c043: "docs(backlog): close BL-15, description fix completes aed6bdd"
files_modified:
  - tests/contract/test_tool_surface.py
  - src/mcp_connector/server/reg_search.py
  - .planning/BACKLOG.md
duration: 8 min
---

# BL-15 Quick-Fix: Ehrliche Tool-Beschreibung von unified_search - Summary

**Einzeiler:** Die registrierte Tool-Beschreibung von `unified_search` behauptet nicht mehr
"not file contents", sondern verweist auf die laufzeitabhängige Note jeder Antwort; damit
ist BL-15 komplett geschlossen und BL-01 verliert seinen zweiten Blocker.

## Was passiert ist

Der Kern von BL-15 (laufzeitabhängige `_note()` mit `CONTENT_PROVIDERS`, ehrlicher
`_TERM_HINT`, Durchreichen in `prepare_context`, Tests beider Zweige) war seit `aed6bdd`
(PR #3, 0.1.12) im Code und wurde NICHT neu gebaut. Dieser Quick-Fix schloss die Restlücke:

1. **Task 1 (test-first, Commit `9a32764`):** Contract-Pin in
   `test_unified_search_is_listed_as_a_pure_read_over_all_providers` umgedreht:
   "not file contents" darf NICHT mehr in der Beschreibung stehen, "note" MUSS
   vorkommen. **Rot-Beweis beobachtet:** Der Test schlug gegen den alten Code fehl
   (AssertionError, "'not file contents' is contained here: metadata, not file contents).").
2. **Task 2 (Commit `6ee0a03`):** Docstring in `src/mcp_connector/server/reg_search.py:30`
   ersetzt durch: "Search the whole Nextcloud across all installed search providers. The
   note of every answer says whether file contents were matched." Einzeiler mit
   `# noqa: E501` beibehalten, Budget-Gate bleibt grün (+23 Bytes bei 1.588 Bytes Luft).
3. **Task 3 (Commit `5c4c043`):** BACKLOG.md BL-15 trägt einen STATUS-Block
   "2026-09-23: DONE" mit Verweis auf `aed6bdd` und die beiden Quick-Fix-Commits.

## Nicht angefasst (wie geplant)

- `src/mcp_connector/tools/files.py` und `reg_files.py` (WebDAV-Suche, Satz bleibt wahr)
- `src/mcp_connector/tools/search.py` (fertig seit `aed6bdd`)

## Gate-Ergebnisse (alle grün)

- `uv run pytest tests/contract/test_tool_surface.py tests/unit/test_unified_search.py tests/unit/test_tools_context.py`: 115 passed
- Volle Suite `uv run pytest -q`: grün (exit 0)
- `uv run ruff check .`: All checks passed
- `uv run ruff format --check .`: 251 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: leer (grün, wie CI)

## Self-Check: PASSED

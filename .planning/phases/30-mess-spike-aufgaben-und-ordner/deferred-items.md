# Phase 30: zurückgestellte Punkte

Funde außerhalb des Auftrags eines Plans. Sie sind hier benannt und nicht behoben.

## DI-30-01: Die Umgebung des Worktrees trägt das Extra `documents` nicht

- **Gefunden in:** Plan 30-01, voller Lauf am Planende (2026-11-11)
- **Befund:** In `.venv` des Worktrees `tasks-080` fehlen `docx`, `pypdf`, `pptx` und `openpyxl` (Extra `documents` aus `pyproject.toml`). `pytest tests/unit tests/contract` bricht deshalb schon beim Einsammeln ab (vier Module: `tests/unit/test_documents_docx.py`, `_pdf.py`, `_pptx.py`, `_xlsx.py`), und `pyright` über das ganze Repository meldet 19 Fehler, alle `reportMissingImports` in `src/mcp_connector/documents/`, `scripts/make_document_fixtures.py` und diesen vier Testmodulen.
- **Nicht verursacht durch Plan 30-01:** der Plan ändert nichts unter `src/`, nichts an `pyproject.toml` und nichts an `uv.lock`; keine der gemeldeten Dateien ist angefasst.
- **Nicht behoben, weil:** der Plan schreibt `uv run --no-sync` vor und schließt Paketinstallationen aus (T-30-SC). Ein `uv sync --extra documents` ist eine Entscheidung des Owners.
- **Umgang im Plan:** der volle Lauf lief ein zweites Mal ohne die vier Module (`--ignore`). Auch dann ist er nicht grün: sieben Tests scheitern, alle mit derselben Meldung "needs the documents extra, which is not installed" (`tests/unit/test_documents_convert.py` zwei, `tests/unit/test_documents_worker.py` einer, `tests/unit/test_files_read_as_markdown.py` vier). Alle übrigen Tests aus `tests/unit` und `tests/contract` bestehen. `pyright` wurde für die Dateien des Plans einzeln gefahren (0 Fehler). Das Akzeptanzkriterium "voller Lauf nach R1 endet mit Exit 0" ist in dieser Umgebung damit nicht erfüllt; so steht es auch in `30-01-SUMMARY.md`.
- **Vorschlag:** vor Plan 30-02 einmal `uv sync --all-extras` (oder das Extra, das die CI nutzt) im Worktree, dann den vollen Lauf nach R1 ohne Ausnahmen wiederholen.

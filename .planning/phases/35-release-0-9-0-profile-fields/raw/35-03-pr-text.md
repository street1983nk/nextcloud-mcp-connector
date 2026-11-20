Title: Release 0.9.0: Profile Fields tool

Base: main
Head: plan/release-090

---

Release 0.9.0, which ships `profile_fields_browse` from #49 by Vitor Mattos (@vitormattos).

- Version 0.9.0 in `pyproject.toml`, `src/mcp_connector/__init__.py`, `appinfo/info.xml` (`<version>` and `<image-tag>`) and `uv.lock`.
- Changelog 0.9.0 in English, German and French.
- Store texts in English, German and French: short, with a link to the README of each language.
- Tool descriptions and error hints without assurances, for issue #53. Behaviour, schemas and annotations unchanged; a contract test holds the wording.
- Fact check of the READMEs and docs against the registry and the code.
- Comment fix in the admin form code: it has ten fields, not seven.
- `profile_fields_browse` reports a Profile Fields app that is missing, disabled or not enabled for the account's groups as such, with a hint for the administrator, instead of passing on the Nextcloud error text; other apps keep the shared wording.
- Planning notes of the release.

Tool count: 27 by default, 28 with Profile Fields, 32 with all three switches (`scripts/check_tool_budget.py`, `tests/contract/test_tool_surface.py`).

Draft until the owner merges by fast-forward.

---
phase: 35-release-0-9-0-profile-fields
plan: 01
subsystem: docs
tags: [release, faktencheck, changelog, profile-fields]
requires: []
provides:
  - Worktree release-090 auf Branch plan/release-090
  - raw/35-01-faktencheck.txt (BASIS, GATE, FAKT, ERLEDIGT, AST, UMLAUT, FRANZ, DASH)
  - CHANGELOG [Unreleased] dreisprachig mit 6 Punkten
affects: [35-02, 35-03, 35-04, 35-05]
tech-stack:
  added: []
  patterns: [AST-Vergleich ohne Docstrings mit gepflanzter Positivkontrolle]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-01-faktencheck.txt
  modified:
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md
    - docs/hardening.md
    - docs/hardening.de.md
    - docs/hardening.fr.md
    - docs/privacy.md
    - docs/client-setup.md
    - src/mcp_connector/exapp/admin_settings.py
    - src/mcp_connector/exapp/config_values.py
decisions:
  - "Worktree vom main-Kopf 9ac9f50f (Planrevision, nur Planungsdateien) statt vom Planungscommit 9a2b0fac angelegt; Basis B bleibt 9a2b0fac"
  - "Umgebung mit uv sync --frozen --extra documents (CI-Form), weil die Gates sonst an fehlenden Dokument-Bibliotheken scheitern"
  - "docs/client-setup.md (20 tools) mitkorrigiert, obwohl nicht in files_modified: aktuelle Produktaussage, falsch"
metrics:
  duration: ca. 75 min
  completed: 2026-11-19
---

# Phase 35 Plan 01: Faktencheck vor Release 0.9.0 Summary

Worktree release-090 angelegt, READMEs, CHANGELOG [Unreleased] und Profile-Fields-docs gegen Registry und Code geprüft (69 FAKT-Zeilen); Changelog dreisprachig um Contributor-Namen, Schalterort und CI-Livebeweis ergänzt, Schalterort in hardening/privacy präzisiert, veraltete "20 tools" und "seven fields/values" berichtigt.

## Tasks

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 | Worktree, Basis, Ausgangsgates | (kein eigener Commit, Protokoll mit Task 3) |
| 2 | Faktencheck, nur Protokoll | (kein eigener Commit, Protokoll mit Task 3) |
| 3a | Texte und Protokoll | f63905a1 docs(35-01): fact check of the texts before release 0.9.0 |
| 3b | Kommentare/Docstrings | 34cb39e1 docs(35-01): admin form comments name the real field count |

## Gates (35-RULES Abschnitt 3), Ende des Plans

- pytest unit+contract: exit 0, 8312 passed, 35 skipped
- check_tool_budget: exit 0, Standard 27 Werkzeuge 18770 Bytes, alle Schalter 32 Werkzeuge 23109 Bytes, Budget 26000
- ruff check: exit 0; ruff format --check: exit 0, 416 Dateien
- pyright (latest): exit 0, 0 errors, 0 warnings
- vulture: exit 0, 0 Funde
- Nachlauf nach DE-Zeilenumbruch: test_changelog_translations, test_docs_admin_form_truth, test_tool_surface: 124 passed

## Faktencheck-Ergebnis

FAKTEN gesamt=69 stimmt=43 falsch=12 fehlt=13 (plus 1 Info-Zeile Statuszeile), danach FAKTEN offen=0.

- Werkzeugzahlen der drei READMEs (27, 31, 27/28) stimmen; kein Text behauptet den Zustand "alle Schalter", 32 ist ableitbar.
- Rechte-Aussagen zu Profile Fields in README und docs stimmen mit Code (nur ocs_get, me/definitions/values/search, Audit level/limit/offset, Schalter ab Werk aus, ungültig = aus, READ_ONLY).
- Fehlte: genauer Schalterort in CHANGELOG x3, hardening x3, privacy.md; Name Vitor Mattos und CI-Livebeweis in CHANGELOG x3.
- Falsch: "20 tools" in docs/client-setup.md (3 Stellen); "seven" an 9 Stellen in admin_settings.py/config_values.py (wirklich 10 Werte/Felder).
- Screenshot docs/screenshots/admin-settings.png: 10 Felder, stimmt.
- PUNKTE unreleased en=6 de=6 fr=6 gleich=ja.
- AST beider src-Dateien ohne Docstrings gleich zur Basis; Positivkontrolle (Zahl- und String-Literal gepflanzt) meldet ungleich.
- UMLAUT/FRANZ fehler=0, DASH treffer=0 (mit Positivkontrolle).

## Deviations from Plan

1. [Rule 3 - Blocking] main-Kopf war 9ac9f50f "docs(35): revise plans after plan check" statt "docs(35): create phase plan". Der Revisionscommit berührt nur Planungsdateien der Phase 35 (35-04..07-PLAN.md, 35-RULES.md). Worktree vom main-Kopf angelegt (sonst fehlten die revidierten Pläne); Basis B per grep = 9a2b0fac, Positivkontrolle grün. origin/main..HEAD zeigt vier statt drei street1983nk-Commits.
2. [Rule 3 - Blocking] `uv sync --frozen` ohne Extra ließ 4 Testmodule und pyright (19 Importfehler) scheitern. Zweiter Sync in der CI-Form `uv sync --frozen --extra documents` (ci.yml:26); uv.lock unverändert. 35-RULES erlaubt wörtlich nur einen Sync: bitte bestätigen.
3. [Rule 1 - Bug] docs/client-setup.md nannte "20 tools" als aktuelle Aussage (3 Stellen), Datei nicht in files_modified; korrigiert mit Verweis auf tests/contract/test_tool_surface.py.
4. Zusätzlich zur Plan-Liste "seven" auch in config_values.py:10 ("the one of the seven that ships off", heute vier ab Werk aus) und :546 ("Pull our seven values") berichtigt; admin_settings.py:87 um die letzten drei Felder ergänzt.
5. Edit-Werkzeug schrieb die Arbeitskopien mit LF; per unix2dos auf CRLF zurückgestellt. Index ist LF (text=auto), numstat zeigt nur die geänderten Zeilen.

## Befunde für den Owner (nicht geändert)

- docs/n8n-setup.md:36 und :258 nennen "23 tools" (Messung 2026-09-04 mit 0.1.11). Die Seite ist datiert und verweist auf test_tool_surface.py, Punkt 7 steht aber im Präsens ("The tool set is 23 tools"). Als Zeitzeugnis gewertet; ob er umformuliert werden soll, entscheidet der Owner.
- admin_settings.py:111 "the five switches show the state this app ships with": 8 Felder sind Checkboxen; "fünf Schalter" folgt der Zählweise aus 261118-ryx (5 Verbinden-Felder, 5 Schalter). Unverändert gelassen.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche. T-35-01-01 (Rechte-Aussagen als FAKT geprüft) und T-35-01-02 (AST-Vergleich mit Positivkontrolle, Diff-Beweis src/) umgesetzt; T-35-01-03 accept.

## Self-Check: PASSED

- raw/35-01-faktencheck.txt vorhanden, Commits f63905a1 und 34cb39e1 im Log des Branches plan/release-090.

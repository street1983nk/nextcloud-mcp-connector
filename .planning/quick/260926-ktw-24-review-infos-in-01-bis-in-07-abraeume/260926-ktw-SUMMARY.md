---
phase: quick-260926-ktw
plan: 01
subsystem: audit, oauth, exapp, docs
tags: [review-followup, v1.6, phase-24]
requires: [24-REVIEW.md IN-01..IN-07]
provides: [refusal-writer-hashable, oauth-import-gate, actor-repr-lock, single-exchange-config-read]
affects: [src/mcp_connector/audit/refusals.py, src/mcp_connector/exapp/exchange_check.py, src/mcp_connector/entry_exapp.py]
tech-stack:
  added: []
  patterns: [AST gate with counter proof through the same function, config handed in with env fallback (build_chain pattern)]
key-files:
  created: []
  modified:
    - src/mcp_connector/audit/refusals.py
    - src/mcp_connector/oauth/verifier.py
    - src/mcp_connector/exapp/exchange_check.py
    - src/mcp_connector/entry_exapp.py
    - src/mcp_connector/exapp/audit_read.py
    - docs/privacy.md
    - scripts/exchange_evidence.py
    - tests/unit/test_audit_refusals.py
    - tests/contract/test_no_claim_leak.py
    - tests/unit/test_oauth_verifier.py
    - tests/unit/test_exapp_exchange_check.py
    - .planning/milestones/v1.6-phases/24-audit-anschluss-und-nachweis/24-REVIEW.md (uncommitted, docs commit)
decisions:
  - "IN-02: gemessen neun Spalten vor 50723cd-Stand, jetzt elf (actor und removed kamen beide dazu); Docstring nennt neun zu elf, nicht zehn zu elf"
  - "IN-04: Test nutzt ENV (Deployment ohne Exchange-Schlüssel) statt {}, weil der AppAPI-Guard sein Secret aus demselben env liest"
metrics:
  duration: ~25 min
  completed: 2026-09-26
  tasks: 3
  commits: 4
---

# Quick 260926-ktw: 24-REVIEW Info-Befunde IN-01 bis IN-07 abgeräumt

Alle sieben Info-Befunde aus 24-REVIEW.md behoben: RefusalWriter hashbar und ohne Zustandsvergleich, AST-Gate für die oauth-Importrichtung von audit/refusals.py, actor-Auslassung im repr begründet und festgeschrieben, Exchange-Config nur einmal pro Anwendung geladen, drei Textkorrekturen.

## Commits

| Task | Befunde | Commit | Nachricht |
|------|---------|--------|-----------|
| 1 | IN-01, IN-07 | 017c30c | fix(audit): keep the refusal brake out of eq/hash and gate its oauth import rule (IN-01, IN-07) |
| 2 | IN-03 | 1a024a2 | docs(oauth): say why the acting party stays out of the identity repr (IN-03) |
| 2 | IN-04 | 687e161 | refactor(exapp): hand the loaded exchange config to the dry-run routes (IN-04) |
| 3 | IN-02, IN-05, IN-06 | 4b5a7ed | docs: correct the column note, name the reserved --user words and the kept test CA (IN-02, IN-05, IN-06) |

Alle Commits als street1983nk <k.cherif@outlook.de>, ohne Trailer, nicht gepusht.

## Was umgesetzt wurde

- **IN-01:** `_windows` mit `compare=False`; Test `test_a_writer_hashes_and_compares_by_where_it_writes_not_by_its_brake` war vorher rot (TypeError: unhashable dict), jetzt grün.
- **IN-07:** `_oauth_imports()` in tests/contract/test_no_claim_leak.py (Segmentvergleich, auch Aliasnamen für `from .. import oauth`); Gate `test_the_refusal_writer_imports_nothing_out_of_oauth` plus Gegenprobe über alle fünf Schreibweisen, keine Fehlalarme für `oauthless`, Kommentar oder Docstring. Moduldocstring und Fensterkommentar in refusals.py verweisen jetzt auf das Gate.
- **IN-03:** `__repr__` unverändert; Docstring begründet die Auslassung (Fremd-Realm, Logs sind kein Audit-Pfad, Verweis auf R-24-04). Festschreibtest einmal gegen eine lokal eingefügte actor-Zeile rot gesehen, Zeile wieder entfernt.
- **IN-04:** `exchange_check_routes(env, config=None)`, `config if config is not None else load_exchange_config(env)`; entry_exapp reicht `exchange_config` durch. Zwei Tests: übergebene Config gewinnt gegen env ohne Exchange-Schlüssel, Rückfall auf env unverändert.
- **IN-02:** Docstring korrigiert: neun Spalten wurden elf, actor an sechster Stelle verschiebt outcome, reason, duration_ms, params; Dokumentform von `_document` ist die schlüsselstabile Form für Skripte.
- **IN-05:** privacy.md nennt `instance` und `refusals` als reservierte Wörter von `--user`.
- **IN-06:** `--keep-armed`-Hilfetext nennt die verbleibende Test-CA; die bestehende Laufzeitzeile in `trust_the_issuer()` benennt jetzt auch den Zustand (kein Doppel).
- 24-REVIEW.md: Einleitungssatz des Info-Abschnitts angepasst und Zeile `_Info resolved: 2026-09-26 (IN-01 bis IN-07, quick 260926-ktw)_` ergänzt (uncommittet, für den Docs-Commit).

## Gates

ruff check, ruff format --check, pyright (latest, 0 Fehler), vulture, volle pytest-Suite (Exit 0) grün. Keine Em-/En-Dashes im Diff. Keine Änderung an middleware.py, appinfo/info.xml, pyproject.toml, uv.lock oder einer Versionsstelle.

## Deviations from Plan

- **IN-02 Spaltenzahl:** Messung per `git show 50723cd:src/mcp_connector/exapp/audit_read.py` ergab neun Spalten vorher (wie im Review), der Docstring sagt daher "nine columns ... became eleven".
- **IN-01 Test:** Die Fixtures `writer`/`writer_over` bauen je Aufruf einen neuen Provider, zwei Schreiber wären damit nie gleich. Der Test baut deshalb einen eigenen Provider und reicht ihn beiden Schreibern.
- **IN-04 Test:** Der Guard lehnt bei leerem env ab, daher `ENV` (ARMED ohne Exchange-Schlüssel, im Test kommentiert). Ein geprüftes JSON-Payload trägt kein `outcome`, deshalb `payload.get("outcome")`.
- **Hinweis, nicht geändert:** Die Statuszeile 65 von 24-REVIEW.md sagt weiter "7 Info offen"; der Plan verlangte nur die zwei genannten Stellen. Nachziehen beim Docs-Commit empfehlenswert.

## Known Stubs

Keine.

## Self-Check: PASSED

- Commits 017c30c, 1a024a2, 687e161, 4b5a7ed im Log vorhanden.
- Alle geänderten Dateien existieren; `compare=False`, `def test_the_refusal_writer_imports_nothing_out_of_oauth`, `config: ExchangeConfig | None = None`, `reserved words` und `exchange_check_routes(env, config=exchange_config)` per grep bestätigt.

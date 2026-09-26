---
phase: 20-jwks-schicht-und-pyjwt-stand
verified: 2026-09-19T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 20: JWKS-Schicht und PyJWT-Stand Verification Report

**Phase Goal:** Es gibt genau eine Schlüsselsatz-Schicht im Produktionsbaum, sie trägt die zwei für den unauthentisierten heißen Pfad fehlenden Fähigkeiten, und der bestehende OIDC-Fluss verhält sich unverändert
**Verified:** 2026-09-19
**Status:** passed
**Re-verification:** No, initiale Prüfung

## Vorgehen

Die SUMMARY-Dateien wurden nicht als Beleg akzeptiert. Stattdessen wurde der reale Codebestand gelesen (`src/mcp_connector/oauth/jwks.py`, `src/mcp_connector/oauth/oidc.py`, `tests/unit/test_oauth_jwks.py`), die vollständige Gate-Kette selbst gefahren (ruff check, ruff format --check, pyright, vulture, volle pytest-Suite `tests/unit tests/contract`), die sha256-Summe von `tests/unit/test_oauth_oidc.py` selbst berechnet und mit der im SUMMARY behaupteten verglichen, die Acceptance Criteria beider Pläne per grep einzeln nachgefahren und die im SUMMARY genannten Commit-Hashes gegen `git log` geprüft.

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `oauth/jwks.py` ist die einzige Stelle, an der ein Schlüsselsatz geholt, zwischengespeichert und rotiert wird; der OIDC-Fluss benutzt sie und verhält sich nachweislich gleich | VERIFIED | `grep -rln "PyJWK(" src/` nennt genau `src/mcp_connector/oauth/jwks.py`; `grep -rc '\bfetched_at' src/mcp_connector/oauth/*.py \| grep -v ":0" \| wc -l` ergibt 1; `oidc.py` importiert `KeySet`, `fetch_json`, `same_origin`, `ALLOWED_ALGORITHMS`, `MAX_RESPONSE_BYTES`, `JWKS_CACHE_SECONDS` aus `.jwks` und hält keine eigene `_KeyCache`/`_refresh_keys`/`_usable_key` mehr (`grep -c` ergibt 0). Selbst berechnete sha256 von `tests/unit/test_oauth_oidc.py` = `43d57438c73a4204e3c73e433b19ce0ede7e0617cac223b1096adc20511517c8`, identisch mit der im SUMMARY behaupteten. `keys.call_count == 2` steht in dieser Datei unverändert zweimal. Voller Testlauf grün: `uv run pytest tests/unit tests/contract` ergibt selbst gefahren 3569 passed, 33 skipped, exit 0 |
| 2 | Ein unbekanntes kid löst nicht bei jedem Aufruf einen neuen Abruf aus (Abkühlzeit) | VERIFIED | `JWKS_KID_COOLDOWN_SECONDS = 60` in `jwks.py`, Stempel `_miss_refresh_at` wird vor dem Abruf gesetzt (Code gelesen, Zeilen 153-160). Eigene Tests direkt an der Schicht gelesen und nachvollzogen: `test_a_hundred_invented_kids_against_a_fresh_cache_cost_one_fetch`, `test_inside_the_cooldown_an_unknown_kid_is_refused_without_a_fetch`, `test_after_the_cooldown_an_unknown_kid_costs_one_fetch_again`, `test_an_expired_cache_refreshes_regardless_of_the_cooldown`, `test_a_failed_miss_reload_still_spends_the_cooldown`; alle grün im selbst gefahrenen Lauf |
| 3 | Gleichzeitige Anfragen nach demselben Schlüsselsatz erzeugen genau einen ausgehenden Abruf | VERIFIED | `asyncio.Lock()` einmal im Konstruktor angelegt (`grep -c` ergibt 1), Re-Check nach Lock-Erwerb im Code gelesen. Test `test_twenty_concurrent_calls_cost_one_fetch_and_share_the_key` (Zeilen 174-186) und `test_twenty_concurrent_calls_whose_fetch_fails_are_all_refused_by_one_fetch` (Zeilen 189-205) inhaltlich gelesen: `asyncio.gather` über 20 Aufrufe, `route.call_count == 1`, geteiltes Schlüsselobjekt bzw. geteilte Ablehnung. Beide Tests laufen im vollen Suite-Lauf grün |
| 4 | Ein unerreichbarer oder unbrauchbarer Schlüsselsatz führt zur Abweisung und nie zur Annahme, auch bei abgelaufenem Cache-Eintrag; Allowlists, Origin-Prüfung und Größenlimit gelten unverändert weiter | VERIFIED | Test `test_an_expired_cache_never_serves_a_kid_when_the_reload_fails` (Zeilen 316-334) gelesen: abgelaufener Cache plus 500er-Antwort führt zur Ablehnung, kein Rückgriff auf den alten Bestand, kein `finally`-Block im Modul (`grep -v '^\s*#' jwks.py \| grep -c finally` ergibt 0). Kein `finally`, das in den Cache schreibt: Cache wird ausschließlich in `_refresh` nach vollständig geparster Antwort ersetzt. Allowlist-Tests gelesen (`oct`, `use=enc`, `key_ops=[encrypt]`, unkonfiguriertes `alg`, Doppel-kid, `MAX_KEYS`, fremder Origin ohne Abruf `call_count == 0`, Größenlimit/500/Redirect/Nicht-JSON) - alle als eigene, inhaltlich nachvollzogene Testfunktionen vorhanden und grün |
| 5 | PyJWT steht auf >=2.14,<3 mit Lock 2.14.0, cryptography im selben Lock-Schritt, `docs/dependency-audit.md` trägt den Nachtrag, alle sechs Versionsstellen-Gates grün | VERIFIED | `pyproject.toml`: `"pyjwt[crypto]>=2.14,<3"`; `uv.lock`: `name = "pyjwt"` / `version = "2.14.0"`, `name = "cryptography"` / `version = "50.0.1"`, `specifier = ">=2.14,<3"` genau einmal, Selbsteintrag `nextcloud-mcp-connector` / `version = "0.2.1"`. `uv run python -c "import jwt; print(jwt.__version__)"` gibt selbst ausgeführt `2.14.0`. Versionsstellen deckungsgleich: `pyproject.toml` 0.2.1, `__init__.py` 0.2.1, `appinfo/info.xml` `<version>0.2.1` und `<image-tag>0.2.1`. `docs/dependency-audit.md` (243 Zeilen) enthält die pyjwt-Tabellenzeile, 5 GHSA-Kennungen (9 Treffer über die fünf Muster), den Abschnitt "Raising PyJWT to 2.14", 2+ Nennungen von "PyJWKClient" und den datierten Nachtrag; keine Em-Dashes (Python-Zählung: 0 U+2014, 0 U+2013). Alle vier Gates (ruff check, ruff format --check, pyright, vulture) selbst gefahren und still |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mcp_connector/oauth/jwks.py` | Einzige Schlüsselsatz-Schicht, min. 150 Zeilen, exportiert `KeySet`, `fetch_json`, `same_origin`, `JWKS_CACHE_SECONDS`, `JWKS_KID_COOLDOWN_SECONDS`, `MAX_RESPONSE_BYTES` | VERIFIED | 304 Zeilen, `__all__` enthält alle geforderten Namen, Datei komplett gelesen: Cache, Rotation, Abkühlzeit, Single-Flight, Allowlists, Origin-Prüfung, Größenlimit vollständig implementiert, kein Stub |
| `tests/unit/test_oauth_jwks.py` | Nachweise ohne OIDC-Fluss, min. 200 Zeilen | VERIFIED | 336 Zeilen, 23 Testfunktionen, `grep -c "oidc"` ergibt 0 (kein Import von oidc), alle Tests im vollen Lauf grün |
| `src/mcp_connector/oauth/oidc.py` | Unveränderter Fluss, importiert aus `.jwks` | VERIFIED | `from .jwks import (...)` vorhanden, keine eigene JWKS-Maschinerie mehr, Datei komplett gelesen |
| `pyproject.toml` | `pyjwt[crypto]>=2.14,<3` | VERIFIED | Zeile vorhanden, `>=2.13,<3` nicht mehr vorhanden |
| `uv.lock` | pyjwt 2.14.0, cryptography aus 50.x, Selbsteintrag 0.2.1 | VERIFIED | Alle drei Werte per grep bestätigt |
| `docs/dependency-audit.md` | Nachtrag mit 5 GHSA-Kennungen, min. 200 Zeilen | VERIFIED | 243 Zeilen, alle Pflichtinhalte per grep bestätigt |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `oidc.py` | `jwks.py` | `OidcClient` hält ein `KeySet` und ruft `key()` | WIRED | `self._keys = KeySet(...)` im Konstruktor, `await self._keys.key(kid, algorithm)` in `validate_id_token` (Code gelesen) |
| `oidc.py` | `jwks.py` | Discovery und Token-Abruf über den gehärteten Client | WIRED | `_get_json`/`_request` sind dünne Weiterleitungen an `fetch_json(..., origin=self._settings.issuer, refuse=_refused)` |
| `tests/unit/test_oauth_jwks.py` | `jwks.py` | Tests sprechen `KeySet` direkt an | WIRED | Kein oidc-Import, `KeySet(` mehrfach direkt instanziiert |

### Data-Flow Trace (Level 4)

Nicht anwendbar in diesem Umfang: `jwks.py` ist keine UI-Komponente, sondern eine Backend-Schicht. Der Datenfluss (Discovery -> `jwks_uri` -> `fetch_json` -> `_refresh` -> Cache -> `_entry`) wurde stattdessen als Teil der Truth-Prüfung 1-4 durch Lesen des Codes und Ausführen der Tests nachvollzogen, nicht nur behauptet.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Volle Unit/Contract-Suite läuft grün | `uv run pytest tests/unit tests/contract` | `3569 passed, 33 skipped in 118.12s`, exit 0 | PASS |
| JWKS-Schicht-Tests isoliert grün | `uv run pytest tests/unit/test_oauth_jwks.py tests/unit/test_oauth_oidc.py -q` | alle Punkte grün, keine Fehlschläge | PASS |
| Installierte PyJWT-Version stimmt | `uv run python -c "import jwt; print(jwt.__version__)"` | `2.14.0` | PASS |
| Lint/Format/Typen/Totcode still | `ruff check .`, `ruff format --check .`, `pyright`, `vulture src scripts vulture_whitelist.py` | alle vier ohne Meldung | PASS |
| sha256 von `tests/unit/test_oauth_oidc.py` unverändert | `sha256sum tests/unit/test_oauth_oidc.py` | `43d57438c73a4204e3c73e433b19ce0ede7e0617cac223b1096adc20511517c8`, deckt sich mit SUMMARY | PASS |
| Plan 20-02 fasst Abhängigkeiten/Manifest nicht an | `git diff --stat 6ae7734..a0f283b -- pyproject.toml uv.lock appinfo/info.xml` | leer | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EXCH-01 | 20-02 | JWKS-Schicht herausgelöst, von beiden Prüfpfaden teilbar, OIDC-Fluss verhaltensgleich, Abkühlzeit und Single-Flight ergänzt | SATISFIED | Siehe Truths 1-4; Code und Tests gelesen und selbst ausgeführt |
| DEP-01 | 20-01 | PyJWT >=2.14,<3, Lock 2.14.0, cryptography mitgezogen, Audit-Nachtrag, Versionsstellen grün | SATISFIED | Siehe Truth 5; alle Werte per grep und eigenem Testlauf bestätigt |

Keine orphaned Requirements: `.planning/REQUIREMENTS.md` weist für Phase 20 ausschließlich EXCH-01 und DEP-01 aus, beide sind in den Plänen deklariert und als "Complete" markiert.

### Anti-Patterns Found

Keine. `grep -n "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` über `jwks.py`, `oidc.py`, `test_oauth_jwks.py`, `dependency-audit.md`, `pyproject.toml` ergibt keinen Treffer. Kein `finally`-Block im neuen Modul, keine hartkodierten leeren Rückgaben, keine Platzhalter-Kommentare.

### Human Verification Required

Keine. Alle Kriterien sind über Code-Lektüre, grep-Gegenproben und selbst ausgeführte Tests/Gates programmatisch verifizierbar; es bleibt kein Punkt offen, der visuelles, zeitkritisches oder externes Verhalten voraussetzt.

### Gaps Summary

Keine Lücken gefunden. Beide Pläne halten, was sie versprechen: Die JWKS-Maschinerie existiert nur noch in `oauth/jwks.py` (belegt durch `PyJWK(`- und `fetched_at`-Gegenproben), der OIDC-Fluss ist byte-identisch getestet und verhält sich nachweislich gleich (sha256-Gegenprobe, `keys.call_count == 2` unverändert), die zwei neuen Fähigkeiten (Abkühlzeit, Single-Flight) sind mit eigenen, inhaltlich gelesenen Tests belegt und nicht nur behauptet, und die PyJWT-Anhebung samt Audit-Nachtrag ist an Lock, Quellcode und Dokumentation nachvollzogen. Alle vier Qualitätsgates und die volle Testsuite wurden selbst ausgeführt (nicht aus dem SUMMARY übernommen) und liefen grün (3569 passed, 33 skipped, exit 0).

---
*Verified: 2026-09-19*
*Verifier: Claude (gsd-verifier)*

---

## Nachtrag 2026-09-19: Audit-Fixes nach der Verifikation

Diese Verifikation lief gegen den Stand 5ea9151. Danach hat der Phase-20-Audit
(20-REVIEW.md) 2 Critical und 6 Warnings gefunden, alle behoben und gepusht
(953969b..539b3d6). Zwei Anker dieser Datei sind dadurch ueberholt, ohne dass
ein Kriterium faellt:

- tests/unit/test_oauth_oidc.py ist nicht mehr byte-identisch (neuer sha256
  beginnt 8012f256): der Umzugsbeweis war mit dem Abschluss von 20-02
  eingeloest, die Aenderung kam durch IN-06 (Weiterexporte entfernt, Tests
  nennen jwks.* direkt) und ist im Commit begruendet.
- OidcClient laeuft jetzt auf time.monotonic (CR-01), KeySet kennt
  retry_seconds (CR-02). Beides staerkt Success Criterion 4 (fail-closed),
  aendert keines der fuenf Kriterien.

Nach den Fixes selbst nachgeprueft: pyjwt 2.14.0 live, genau ein
from .jwks import in oidc.py, volle Gate-Kette gruen (Fixer-Protokoll in
20-REVIEW.md, je Commit gefahren).

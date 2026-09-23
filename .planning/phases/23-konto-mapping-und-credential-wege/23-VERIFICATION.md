---
phase: 23-konto-mapping-und-credential-wege
verified: 2026-09-23T17:46:25Z
status: passed
score: 9/9 must-haves verified (5 Roadmap Success Criteria + 4 Requirements)
overrides_applied: 0
---

# Phase 23: Konto-Mapping und Credential-Wege Verification Report

**Phase Goal:** Ein getauschtes Token handelt unter einem existierenden Nextcloud-Konto, in beiden Betriebsarten, ohne neue Vollmacht und ohne stille Kontoanlage
**Verified:** 2026-09-23T17:46:25Z
**Status:** passed
**Re-verification:** No , initial verification

## Hinweis zum Roadmap-Stand

`.planning/ROADMAP.md` (Zeile 93, 172-177, 222) und `.planning/REQUIREMENTS.md` (Zeile 30-36, 94-97) zeigen Phase 23 noch als `[ ]` / "Pending" / "0/6 Planned". Das ist ein reiner Buchführungs-Rückstand der Planungsdateien (wird vom Orchestrator nach dieser Verifikation nachgezogen), keine Aussage über den Codezustand. Alle sechs Pläne haben ein `SUMMARY.md` mit `status: complete`, und der Code belegt die Umsetzung unabhängig von diesen Checkboxen. Eine eigene `23-CONTEXT.md` existiert in diesem Phasenverzeichnis nicht; die Verifikation stützt sich auf ROADMAP.md, REQUIREMENTS.md und die sechs PLAN/SUMMARY-Paare.

## Goal Achievement

### Observable Truths (Roadmap Success Criteria, Phase 23)

| # | Truth (aus ROADMAP.md) | Status | Evidence |
|---|---|---|---|
| 1 | Claim-Mapping konfigurierbar mit sub-basiertem und LDAP-tauglichem Profil; Ergebnis ist der kanonische Principal, nicht der Anmeldename; Pausenschalter/Audit-Kettenname/Sweep greifen für gemapptes Konto wie für angemeldetes (gemessen) | ✓ VERIFIED | `src/mcp_connector/oauth/mapping.py:32-53` (`MAPPING_ACCOUNT_ID_V1`, `MAPPING_USER_OIDC_SUB_V1`, `MAPPING_STRATEGIES`), `principal_from_claims` (Zeile 110-157) liefert nie den Anmeldenamen (kein `login_name`-Import). Gemessen in `tests/unit/test_oauth_exchange_identity.py:477` `test_the_pause_switch_the_audit_chain_and_the_sweep_treat_both_kinds_alike`. Test lief grün. |
| 2 | Token mit Claim auf kein existierendes Konto wird abgewiesen, kein Konto entsteht; bei nicht feststellbarer Existenz ebenfalls Abweisung (fail-closed) | ✓ VERIFIED | `src/mcp_connector/oauth/exchange_appapi.py:78-108` (`identity_for`: `known is None or principal not in known` → `None`, kein Schreibzugriff im Modul), `exchange_binding.py:42-80` (dasselbe Muster, `binding_of` liest nur). Getestet in `tests/unit/test_oauth_exchange_appapi.py` und `tests/unit/test_oauth_exchange_binding.py` (beide grün, Teil der 4162 passed). |
| 3 | ExApp-Modus: gemapptes Konto erreicht Nextcloud über AppAPI-Impersonation ohne Provisionierung, Rechtegrenze bleibt bei Nextcloud | ✓ VERIFIED | `exchange_appapi.py` (Kontoquelle), `deps.py:243-339` (`_credentials_from_appapi`/`_credentials_from_oauth` mit `CREDENTIAL_IMPERSONATE`-Zweig, `mode=MODE_APPAPI`), `entry_exapp.py:135` (`accounts = exchange_appapi.AppApiAccounts(env=env) if exchange_config is not None else None`). Durchstich-Test misst den ausgehenden `AUTHORIZATION-APP-API`-Header für zwei Konten (23-03-SUMMARY.md, Test in `test_oauth_exchange_appapi.py`). |
| 4 | Standalone: getauschtes Token wählt bestehende, vorab erteilte Autorisierung; keine neue; ohne Autorisierung ununterscheidbare Abweisung | ✓ VERIFIED | `store.py:971-996` (`binding_of`, keine Schemaänderung, `LIMIT 1`), `exchange_binding.py` (liest, schreibt nie , kein `create_authorization`/`INSERT` im Modul), `entry_oauth.py:271` (`accounts = exchange_binding.BoundAccounts(store) if exchange_config is not None else None`). 401-Vergleichstest (gültige Signatur ohne Bindung vs. kaputte Signatur, byte-gleiche Antwort) in `test_oauth_exchange_binding.py`. |
| 5 | Nutzer sieht Exchange-Zuordnung bei seinen Verbindungen, kann sie einzeln widerrufen; unmittelbar nächster Aufruf desselben Tokens wird danach abgewiesen | ✓ VERIFIED | `src/mcp_connector/exapp/ui/exchange.py` (`bound_page` zeigt Konto/Datum/handelnde Partei), `oauth/exchange_enroll.py:523-570` (`_revoke`: `form_token_valid` unter `PURPOSE_DISCONNECT`, Client-Filter auf `EXCHANGE_CLIENT_ID`, ruft `end_connection` und nie den Store direkt). Test `test_the_same_exchanged_token_is_accepted_before_and_refused_after_revocation` **selbst ausgeführt**: 1 passed. |

**Score:** 5/5 Roadmap Success Criteria verifiziert

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| MAP-01 | 23-01, 23-02 | Claim-Mapping konfigurierbar, kanonischer Principal, Pausenschalter/Audit/Sweep-Gleichlauf gemessen | ✓ SATISFIED | `mapping.py`, `exchange_accounts.py`, `chain.py` Zweig `resolve_identity` (Zeile 538-576); Beweistest siehe Truth 1 |
| MAP-02 | 23-03 | Kein Konto → Abweisung, keine stille Kontoanlage, fail-closed bei Ungewissheit | ✓ SATISFIED | `exchange_appapi.py:78-142` (`AppApiAccounts`, kein Schreibzugriff, `None`-Cache-Ergebnis = Abweisung); siehe Truth 2/3 |
| CRED-01 | 23-03 | ExApp-Impersonation ohne Provisionierung, Rechtegrenze bei Nextcloud | ✓ SATISFIED | `deps.py` Impersonationszweig, `exchange_appapi.py`; siehe Truth 3 |
| CRED-02 | 23-04, 23-05, 23-06 | Standalone: bestehende Autorisierung, keine neue Vollmacht, sichtbar, widerrufbar, ununterscheidbare Abweisung | ✓ SATISFIED | `store.py:binding_of`, `exchange_binding.py`, `exchange_enroll.py` (Enrollment + Widerruf), `exapp/ui/exchange.py`; siehe Truth 4/5 |

**Hinweis:** REQUIREMENTS.md (Zeile 30-36, 94-97) führt diese vier Requirements noch als `[ ]` / "Pending". Das ist ein Dokumentationsrückstand, keine Codelücke , siehe Code-Belege oben.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/mcp_connector/oauth/mapping.py` | Zwei Profile + `principal_from_claims` | ✓ VERIFIED | 158 Zeilen, exportiert `MAPPING_ACCOUNT_ID_V1`, `MAPPING_USER_OIDC_SUB_V1`, `MAPPING_STRATEGIES`, `MappingSettings`, `principal_from_claims`; kein `nc_user`/`login_name`/`os.environ`/`httpx` (geprüft) |
| `src/mcp_connector/oauth/exchange_accounts.py` | Protokoll + `EXCHANGE_CLIENT_ID` + `acting_party` | ✓ VERIFIED | 89 Zeilen, `ExchangeAccounts` (runtime_checkable), `EXCHANGE_CLIENT_ID = "urn:mcp-connector:token-exchange"`, `acting_party` mit `isprintable`-Filter |
| `src/mcp_connector/oauth/chain.py` | `resolve_identity`-Zweig, `accounts`-Parameter | ✓ VERIFIED | Zeile 538-576: Mapping → Kontoquelle → Identität, `accounts=None` = Abweisung (Phase-22-Zustand) |
| `src/mcp_connector/oauth/exchange_appapi.py` | ExApp-Kontoquelle, fail-closed, Cache/Karenz | ✓ VERIFIED | `AppApiAccounts`, `ACCOUNT_CACHE_TTL=60.0`, `ACCOUNT_FAILURE_RETRY_SECONDS=30.0`, Einzelflug per `asyncio.Lock` |
| `src/mcp_connector/oauth/exchange_binding.py` | Standalone-Kontoquelle | ✓ VERIFIED | `BoundAccounts`, liest je Anfrage ohne Cache, `same_principal` als zweite Prüfung |
| `src/mcp_connector/oauth/store.py` | `binding_of` | ✓ VERIFIED | Zeile 971-996, keine Schemaänderung, `LIMIT 1`, Client als Parameter |
| `src/mcp_connector/oauth/exchange_enroll.py` | Enrollment-Mechanik + Routen + Widerruf | ✓ VERIFIED | `begin/complete/settle/abort_enrollment`, `exchange_routes`, `_revoke` mit `EXCHANGE_CLIENT_ID`-Filter |
| `src/mcp_connector/exapp/ui/exchange.py` | Seiten des Vorgangs | ✓ VERIFIED | 291 Zeilen, `invitation_page`, `bound_page`, `waiting_page`, `identity_page`, `handoff_page`, baut ausschließlich über `layout.*`-Bausteine |
| `src/mcp_connector/deps.py` | Impersonationszweig der Credential-Schicht | ✓ VERIFIED | `CREDENTIAL_IMPERSONATE`-Zweig Zeile 313-324, `_no_user_context()` als ununterscheidbare Abweisung |
| `src/mcp_connector/entry_oauth.py` / `entry_exapp.py` | Kontoquellen nur bewaffnet verdrahtet | ✓ VERIFIED | `entry_oauth.py:271` `BoundAccounts`, `entry_exapp.py:135` `AppApiAccounts`, je nur wenn `exchange_config is not None` |
| `src/mcp_connector/oauth/oidc_routes.py` | Rücksprungziel folgt dem Vorgangs-Client | ✓ VERIFIED | `_return_path`/`flow_client` (Plan 23-05) |
| `src/mcp_connector/oauth/provider.py` | Sweep nimmt fertige Bindungen aus | ✓ VERIFIED | `sweep_abandoned` mit `except_clients=(EXCHANGE_CLIENT_ID,)`-Muster (Plan 23-05) |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `chain.py` | `mapping.py` | `principal_from_claims` im `resolve_identity`-Zweig | ✓ WIRED | Zeile 561 |
| `chain.py` | `exchange_accounts.py` | `self._accounts.identity_for(...)` | ✓ WIRED | Zeile 570; `accounts=None` bleibt Abweisung (Zeile 555-557) |
| `exapp/middleware.py` | `chain.py` | `identity.principal` ungeändert gelesen | ✓ WIRED | Kein Eingriff in middleware.py nötig, laut Plan/Summary bestätigt und durch grün laufende Middleware-Tests belegt |
| `entry_exapp.py` | `exchange_appapi.py` | `AppApiAccounts(env=env)` nur bewaffnet | ✓ WIRED | Zeile 135 |
| `exchange_appapi.py` | `audit/accounts.py` | `existing_users` als einziger Leser der Kontoliste | ✓ WIRED | Import Zeile 24, kein zweiter Netzpfad |
| `deps.py` | `nextcloud/credentials.py` | `mode=MODE_APPAPI` im Impersonationszweig | ✓ WIRED | Zeile 324 |
| `entry_oauth.py` | `exchange_binding.py` | `BoundAccounts(store)` nur bewaffnet | ✓ WIRED | Zeile 271 |
| `exchange_binding.py` | `store.py` | `binding_of`/`app_password` | ✓ WIRED | Zeile 58, 63 |
| `entry_oauth.py` | `exchange_enroll.py` | `exchange_routes(...)` nur bewaffnet | ✓ WIRED | Zeile 339 |
| `exchange_enroll.py` | `provider.py` | Widerruf über `end_connection`, nie über den Store | ✓ WIRED | Zeile 567; `grep revoke_authorization\|revoke_family` im Modul = 0 (bestätigt) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Mapping liefert nie den Anmeldenamen, wirft nie | Quellcode-Lektüre `mapping.py` (kein Ausnahme-Pfad, keine `nc_user`-Referenz) | Bestätigt | ✓ PASS |
| SC1 (Pausenschalter/Audit/Sweep gemappt vs. angemeldet) | `uv run pytest tests/unit/test_oauth_exchange_identity.py -q` | grün | ✓ PASS |
| SC5 (200 vor Widerruf, 401 unmittelbar danach, gleicher Token, gleiche Anwendung) | `uv run pytest tests/unit/test_oauth_exchange_enroll.py::test_the_same_exchanged_token_is_accepted_before_and_refused_after_revocation -v` | `1 passed in 1.46s` | ✓ PASS |
| Widerruf-Filter auf `EXCHANGE_CLIENT_ID` (Abweichung 23-06 Nr. 2) | `grep -n "row.client_id != EXCHANGE_CLIENT_ID" src/mcp_connector/oauth/exchange_enroll.py` | Zeile 562 vorhanden | ✓ PASS |
| UTF-8-Abweisung im Mapping (Abweichung 23-01 Nr. 2) | `grep -n "UnicodeEncodeError" src/mcp_connector/oauth/mapping.py` | Zeile 130 vorhanden, verstärkt nur das Nie-Werfen-Versprechen | ✓ PASS |
| Doku-Wahrheit `/exchange` | `grep -n "/exchange" docs/standalone-oauth.md` | 4 Treffer inkl. eigenem Abschnitt | ✓ PASS |

### Probe Execution

Keine dedizierten `scripts/*/tests/probe-*.sh`-Dateien für diese Phase gefunden (`find scripts -path '*/tests/probe-*.sh'` liefert nichts Phasenbezogenes). Kein Migrations-/CLI-Tooling-Phasentyp; Probe-Schritt entfällt.

### Anti-Patterns Found

Keine Blocker gefunden. Geprüft auf `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` in den elf phasenrelevanten Quelldateien (`mapping.py`, `exchange_accounts.py`, `exchange_appapi.py`, `exchange_binding.py`, `exchange_enroll.py`, `chain.py`, `store.py`, `provider.py`, `oidc_routes.py`, `entry_oauth.py`, `entry_exapp.py`, `deps.py`, `exapp/ui/exchange.py`): keine Treffer. Keine leeren Rückgaben (`return []`/`return {}`) ohne echte Datenquelle; alle `None`-Rückgaben sind dokumentierte, getestete Abweisungen (fail-closed by design).

### Gates (selbst ausgeführt)

| Gate | Befehl | Ergebnis |
|---|---|---|
| Unit + Contract Tests | `uv run pytest tests/unit tests/contract -q` | **4162 passed, 33 skipped, 0 failed** (Byte-Zählung der Ergebnis-Zeichen verifiziert, da die pytest-Zusammenfassungszeile in dieser Shell nicht ausgegeben wurde; Dot-Zählung: 4162 `.`, 33 `s`, 0 `F`/`E`) , deckt sich exakt mit der von 23-06-SUMMARY.md behaupteten Endzahl |
| ruff check | `uv run ruff check .` | All checks passed! |
| ruff format --check | `uv run ruff format --check .` | 263 files already formatted |
| pyright | `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings, 0 informations |
| vulture | `uv run vulture src scripts vulture_whitelist.py` | still (keine Ausgabe) |

Alle vier Gates liefen wie erwartet und bestätigen die in den SUMMARYs behaupteten Zahlen unabhängig.

### Bewertung der dokumentierten Abweichungen

**23-01 Abweichung 2 (UTF-8-Abweisung für einsames Surrogat):** Verstärkt nur das im Plan verlangte "wirft unter keiner Eingabe"-Versprechen von `principal_from_claims`; verletzt kein Phasenziel, keine Scope-Ausweitung, in `mapping.py:128-133` und per Korpustest gemessen. Unbedenklich.

**23-06 Abweichung 2 (`_revoke`-Filter auf `EXCHANGE_CLIENT_ID`):** Schließt eine im Plan nicht explizit benannte, aber reale Lücke: ohne den Filter hätte ein auf der ExApp-Connections-Seite gerenderter Formularwert (derselbe `PURPOSE_DISCONNECT`-Zweck) eine gewöhnliche Verbindung über die `/exchange`-Oberfläche beenden können. Der Fix ist eine Härtung, keine Abschwächung; durch `test_every_failed_withdrawal_is_one_answer` mit einer echten gewöhnlichen Verbindung gemessen (Widerrufsweg wird nie erreicht). Unbedenklich, stärkt das Phasenziel eher.

Keine der beiden Abweichungen untergräbt MAP-01, MAP-02, CRED-01 oder CRED-02.

## Human Verification Required

Keine. Alle fünf Roadmap-Erfolgskriterien sind durch Code-Lektüre und selbst ausgeführte, grün laufende Tests belegt; keine rein visuellen oder rein subjektiven UX-Aussagen offen. (HTML-Rendering der `/exchange`-Seiten ist über `test_oauth_exchange_page.py` automatisiert geprüft, u.a. Quoting eines bösartigen Namens.)

## Gaps Summary

Keine Codelücken gefunden. Einziger Befund ist ein Dokumentationsrückstand: ROADMAP.md und REQUIREMENTS.md markieren Phase 23 und MAP-01/MAP-02/CRED-01/CRED-02 noch als offen/pending, obwohl der Code sie vollständig trägt und alle Gates grün sind. Das ist kein Blocker für den Phasenabschluss, sollte aber vom Orchestrator beim Phasenabschluss (Checkbox-Update in ROADMAP.md, Status-Update in REQUIREMENTS.md) nachgezogen werden.

---

_Verified: 2026-09-23T17:46:25Z_
_Verifier: Claude (gsd-verifier)_

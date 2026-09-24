---
phase: 24-audit-anschluss-und-nachweis
verified: 2026-09-24T00:00:00Z
status: passed
score: 5/5 Erfolgskriterien verifiziert (9/9 Plaene abgedeckt)
overrides_applied: 0
---

# Phase 24: Audit-Anschluss und Nachweis Verification Report

**Phase Goal:** Ein über Exchange handelnder Aufruf ist genauso nachvollziehbar wie jeder andere, und die Einrichtung lässt sich ohne Live-Zugriff auf F13 verproben und belegen
**Verified:** 2026-09-24
**Status:** passed
**Re-verification:** Nein, Erstverifikation

## Goal Achievement

### Observable Truths (die 5 Erfolgskriterien der Roadmap)

| # | Truth | Status | Evidenz |
|---|-------|--------|---------|
| 1 | Ein über Exchange ausgeführter Werkzeugaufruf steht in der bestehenden hash-verketteten Kette, trägt `azp` als eigenes Feld (`actor`), Kette bleibt bei gemischten Aufrufen prüfbar | VERIFIED | `oauth/verifier.py:169` (`actor` auf `OAuthIdentity`), `audit/store.py:321/417` (Spalte `actor`, Säuberung über `ACTOR_LIMIT`), `exapp/audit_read.py` (Ausgabe beider Formen). Gemessener Beleg in `docs/exchange-evidence.md:262-284`: Zeilen 494/495 in einer Kette `u:alice`, `prev_hash` von 495 = `hash` von 494, `occ mcp_connector:audit:verify --json` meldet `"broken":false,"findings":[]"`. Gate: `tests/unit/test_docs_exchange_truth.py::test_the_quoted_call_lines_are_the_lines_this_code_prints` |
| 2 | Ein abgewiesener Exchange-Versuch ist sichtbar, ohne Token/Claims/Schlüsselmaterial in der Zeile, gehalten von einem Claim-Leak-Gate | VERIFIED | `audit/refusals.py` schreibt nur `chain, kind, at, outcome, reason, removed` (sechs Konstanten, kein Feld aus dem Token). AST-Gate `tests/contract/test_no_claim_leak.py` prüft Feldnamen, positionelle Argumente und `**`-Spreizung. Gemessener Beleg: `docs/exchange-evidence.md:293-308` (sechs Zeilen `x:exchange … rejected … exchange_issuer …`, kein Konto, kein Client, kein Subject) |
| 3 | Ein Administrator prüft ein Token mit einem Kommando gegen die aktive Konfiguration, bekommt je Prüfschritt ein benanntes Ergebnis; kein Nextcloud-Aufruf, keine Sitzung | VERIFIED | `occ mcp_connector:exchange:check` (`exapp/occ.py:193`) ruft `oauth/exchange_dryrun.dry_run` (`exapp/exchange_check.py:307`). Eigener Schlüsselsatz, keine gemeinsamen Bremsen: `tests/unit/test_oauth_exchange_dryrun.py::test_the_dry_run_does_not_spend_the_brakes_of_the_running_checker`. Kein Kontoschritt, explizit benannt in `docs/token-exchange.md:192-195` und im Docstring der Regel. Body-Grenze gemessen: `docs/token-exchange.md:236-239` |
| 4 | Eine Messdatei zeigt zwei über Exchange gemappte Konten, von denen keines die Dateien des anderen sieht, gemessen und nicht argumentiert | VERIFIED | `docs/exchange-evidence.md`, Messungen 1-3: `404` bei Pfad, Pfad-Traversal und Suche in beide Richtungen (Zeilen 119-143), serverseitiger Beleg im Apache-Zugriffslog und im `exapp_impersonation.log` (Zeilen 145-177). Messung 4 (Basic-Header eines dritten Kontos) widerlegte die im Plan formulierte Erwartung; das Dokument schreibt die Widerlegung offen aus statt sie zu verschweigen oder umzuformulieren, ordnet sie als bekannte Reihenfolge von `exapp/middleware.py` ein (kein Privilege-Escalation, erfordert bereits gültige Fremd-Anmeldung) und trägt die Konsequenz in `docs/token-exchange.md:289-305` nach. Das ist der geforderte "gemessen, nicht argumentiert"-Standard, auch wenn das Ergebnis nicht die ursprüngliche Annahme war |
| 5 | Doku unter `docs/` von Keycloak-Seite bis erster Werkzeugaufruf, Audience-Konvention, `occ oauth2:add-client`-Playbook (Rolle als offene F13-Antwort markiert), ausdrückliche Grenzen | VERIFIED | `docs/token-exchange.md`: Abschnitt 2 (Keycloak-Seite, Audience-Konvention als Empfehlung), Abschnitt 5 (erster Werkzeugaufruf), Abschnitt 7 (`occ oauth2:add-client`-Playbook, Rolle "open F13 answer, deferred on 2026-09-24", entspricht dem Owner-Entscheid), Abschnitt 9 ("What this path does not do"), Abschnitt 10 (F13s vier offene Antworten tabellarisch). Variablenliste hat eine Quelle (`oauth/chain.py`-Docstring), gehalten von einem Gate (`tests/unit/test_docs_exchange_truth.py`) |

**Score:** 5/5 Erfolgskriterien verifiziert

### Required Artifacts

| Artifact | Erwartet | Status | Details |
|----------|----------|--------|---------|
| `src/mcp_connector/audit/refusals.py` | Abweisungskette `x:exchange`, gefegt, Claim-Leak-frei | VERIFIED | `note_refusal` ruft `store.should_sweep(seq)` und fegt in derselben Fail-open-Klammer (CR-01 gefixt, `8b7f6a1`); Bremse begrenzt auf 1 Zeile je Grund und Fenster |
| `src/mcp_connector/oauth/exchange_dryrun.py` | Reine Prüfregel, eigener Schlüsselsatz | VERIFIED | Baut eigenen `KeySet` (Zeile 395), kein Zugriff auf laufende Bremsen (Test siehe oben) |
| `src/mcp_connector/oauth/chain.py` | `actor`-Auflösung, `REASON_EXCHANGE_FAILED` getrennt von `REASON_EXCHANGE_ACCOUNT` | VERIFIED | `_exchange_identity` gibt `(identity, reason)` zurück, Ausnahmezweig meldet `REASON_EXCHANGE_FAILED` (WR-02 gefixt, `11ca3ce`) |
| `src/mcp_connector/exapp/exchange_check.py` | occ-Route `exchange:check`, Bodygrenze, Fail-open-Antwortbau | VERIFIED | `_payload` gibt benannten Grund zurück statt `None` (WR-04, `be60861`); `_report`/`_machine_readable` liegen im selben `try`-Block wie `dry_run` (WR-05, `301109c`); Route im Manifest nicht deklariert (bewusst, laut Review) |
| `src/mcp_connector/exapp/occ.py` | Viertes Kommando `mcp_connector:exchange:check` | VERIFIED | `OCC_EXCHANGE_CHECK_COMMAND_NAME` registriert, Hilfetext nennt die Prozesslisten-Folge |
| `scripts/exchange_evidence.py` | Wiederholbarer Messlauf, sichere Wiederherstellung | VERIFIED | `register(armed)` unmittelbar vor dem `try`, gesamte Messkette im `try`, Wiederherstellung im `finally` (WR-06 gefixt, `922e5c8`) |
| `docs/exchange-evidence.md` | Rohausgabe-Nachweis EXCH-07/AUDIT-07 | VERIFIED | Zitierte Zeilen jetzt gegen `audit_read._line` nachgerechnet (WR-01 gefixt, `2568be5`), gehalten von `tests/unit/test_docs_exchange_truth.py` |
| `docs/token-exchange.md` | Einrichtungsdoku EXCH-08 | VERIFIED | Zehn Abschnitte, siehe Truth 5 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `oauth/verifier.OAuthIdentity.actor` | `audit/store.Entry.actor` | `oauth/chain.py` Auflösung über `azp` | WIRED | Feld durchgängig von der Tokenprüfung bis zur Spalte verfolgt |
| `audit/refusals.RefusalWriter` | `audit/store.AuditStore.sweep` | `should_sweep(seq)` im selben Schreibweg | WIRED | Nach CR-01-Fix; Grenzwerte aus `entry_exapp.build_exapp_app` (`config.audit_retention_days/size_limit`) durchgereicht (3 Fundstellen geprüft) |
| `exapp/exchange_check.py` (occ-Route) | `oauth/exchange_dryrun.dry_run` | direkter Aufruf mit `config` aus `load_exchange_config` | WIRED | Einmal beim Start gelesen (Doppel-Laden dokumentiert als offener Info-Punkt IN-04, nicht sicherheitsrelevant) |
| `scripts/exchange_evidence.py` | laufende ExApp/HaRP/Nextcloud-35-Topologie | `compose.nc35.yml`, Dienst `test-issuer` | WIRED | Live gemessen 2026-09-24, Topologie danach zurückgesetzt und live gegengeprüft |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Refusal-Sweep-Wiring nach CR-01 | `pytest -k test_audit_refusals` | alle grün (dots, kein F/E) | PASS |
| Rohausgabe-Wahrheit der Messdatei nach WR-01 | `pytest -k test_docs_exchange_truth` | alle grün | PASS |
| Claim-Leak-Gate | `pytest -k test_no_claim_leak` | alle grün | PASS |
| occ-Route Bodygrenze/Fail-open nach WR-04/WR-05 | `pytest -k test_exapp_exchange_check` | alle grün | PASS |
| Konto-Ausfall vs. Kontoabweisung nach WR-02 | `pytest -k test_oauth_exchange_identity` | alle grün | PASS |
| BL-21 (429 gegen gebaute ExApp, JWKS-Nachmessung) | `pytest -k "test_repeated_exchange_refusals_end_in_429_on_the_built_exapp_application or test_the_429_of_the_exchange_path_of_the_exapp_names_no_check_that_failed or test_without_the_appapi_headers_the_401_is_the_handshake_one_and_still_counted or test_both_levers_in_one_window_measure_thirty_six_outgoing_fetches"` | alle 4 grün | PASS |

Kein voller `pytest`-Lauf durchgeführt (Anweisung: gezielte `-k`-Läufe genügen; letzter Vollauf 4392 passed laut `24-REVIEW.md`).

### Requirements Coverage

| Requirement | Source Plan | Beschreibung | Status | Evidenz |
|-------------|-------------|--------------|--------|---------|
| AUDIT-07 | 24-01, 24-02, 24-03, 24-04, 24-07 | Exchange-Aufruf in der Audit-Kette, `azp` als Feld, Abweisungen sichtbar ohne Token-Inhalte | SATISFIED | Siehe Truth 1 und 2 |
| EXCH-06 | 24-05, 24-06 | Trockenlauf-Kommando, benanntes Ergebnis je Prüfschritt, kein Nextcloud-Aufruf | SATISFIED | Siehe Truth 3 |
| EXCH-07 | 24-08 | Zwei-Konten-Negativbeweis als Messdatei | SATISFIED | Siehe Truth 4 |
| EXCH-08 | 24-09 | Einrichtungsdoku mit Audience-Konvention, Playbook, Grenzbeschreibung | SATISFIED | Siehe Truth 5 |

**Traceability-Hinweis (Warning, keine Blockade):** `.planning/REQUIREMENTS.md` führt AUDIT-07, EXCH-06, EXCH-07 und EXCH-08 in der Traceability-Tabelle (Zeilen 98-101) weiterhin als `Pending` und die zugehörigen Checkboxen (Zeilen 44, 48-50) als nicht abgehakt, obwohl `ROADMAP.md` Phase 24 als `Complete` führt und der Code die Anforderungen nachweislich erfüllt. Keiner der neun Pläne oder SUMMARYs hat `REQUIREMENTS.md` aktualisiert. Das ist eine Dokumentationslücke, kein Funktionsdefizit: Der Code erfüllt die vier Requirements nachweislich (siehe oben). Empfehlung: `REQUIREMENTS.md` nachziehen (Checkboxen setzen, Status auf `Complete`), bevor der Milestone v1.6 als abgeschlossen gilt.

### BL-21 (Backlog)

`BACKLOG.md:788` führt BL-21 (IN-04/IN-05 der Phase 22, fällig mit AUDIT-07) als `RESOLVED`, mit Verweis auf Plan 24-07 und die beiden oben verifizierten Tests. Übereinstimmung bestätigt.

### Anti-Patterns Found

Keine `TBD`/`FIXME`/`XXX`-Marker in den von dieser Phase geänderten Dateien (`audit/refusals.py`, `oauth/exchange_dryrun.py`, `oauth/exchange.py`, `oauth/chain.py`, `exapp/exchange_check.py`, `exapp/audit_read.py`, `exapp/occ.py`, `scripts/exchange_evidence.py`, `docs/token-exchange.md`, `docs/exchange-evidence.md`). Der Code-Review (`24-REVIEW.md`) hat 1 Critical und 6 Warnings gefunden und alle in eigenen Commits behoben (`8b7f6a1`..`922e5c8`); die verifizierten Fixes wurden oben einzeln nachvollzogen, nicht nur aus dem REVIEW übernommen. Sieben Info-Befunde bleiben bewusst offen und sind im Review dokumentiert (kein Blocker, da explizit als nicht sicherheitsrelevant eingeordnet und nicht Teil des Auftrags dieser Runde).

### Human Verification Required

Keine. Die Phase liefert ausschließlich serverseitig prüfbare Artefakte (Code, Tests, Messläufe gegen eine laufende Instanz, Dokumentation); alle Erfolgskriterien sind durch Quelltext, Gates und die im Repository liegende Messdatei belegt.

### Gaps Summary

Keine Gaps, die die Zielerreichung blockieren. Ein Warning-Punkt ohne Blockade-Charakter: die Traceability-Tabelle in `REQUIREMENTS.md` ist nicht auf den aktuellen Stand nachgezogen (siehe oben). Messung 4 in `docs/exchange-evidence.md` widerlegte eine im Plan formulierte Erwartung, wurde aber ehrlich als Befund ausgeschrieben, sicherheitlich eingeordnet (keine Rechteausweitung) und in die Einrichtungsdoku übernommen; das erfüllt den Anspruch "gemessen, nicht argumentiert" der Phase und wird daher nicht als Fehlschlag gewertet.

---

_Verified: 2026-09-24_
_Verifier: Claude (gsd-verifier)_

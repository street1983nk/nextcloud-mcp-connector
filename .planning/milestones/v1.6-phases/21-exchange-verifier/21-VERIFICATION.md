---
phase: 21-exchange-verifier
verified: 2026-09-19T06:27:50Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 21: Exchange-Verifier Verification Report

**Phase Goal:** Ein fremdes Keycloak-JWS wird von freistehenden, testbaren Funktionen vollständig geprüft, und jede einzelne Abweichung hat ihren eigenen Ablehnungsgrund
**Verified:** 2026-09-19T06:27:50Z
**Status:** passed
**Re-verification:** Nein, erste Prüfung

## Goal Achievement

Die Verifikation ist am echten Bestand nachgefahren, nicht anhand der SUMMARYs: `src/mcp_connector/oauth/exchange.py` wurde vollständig gelesen, `tests/unit/test_oauth_exchange.py` wurde vollständig gelesen und ausgeführt, die volle Suite lief selbst, und der Scope-Fence-Diff wurde selbst über die Commits gezogen.

### Observable Truths (Success Criteria aus ROADMAP.md Phase 21)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Ein selbst gebautes Token mit erlaubtem Issuer, gültiger Signatur, erlaubtem Algorithmus und Schlüsseltyp, vollständigen Pflicht-Claims und passender Audience wird angenommen; fremder Issuer, falscher Schlüssel, unerlaubter Algorithmus, unerlaubter Schlüsseltyp, abgelaufen, noch nicht gültig und fehlendes aud werden je einzeln abgewiesen | VERIFIED | `test_a_complete_token_is_accepted_and_returns_its_claims` (Zeile 183) hält den Erfolgsfall inkl. `sub`-Rückgabe fest. Je ein eigener Test für fremden Issuer (Z. 194), falschen Schlüssel (Z. 201), HS256 (Z. 208), `alg=none` (Z. 215), symmetrischen JWKS-Eintrag (Z. 222), unbekanntes/fehlendes `kid` (Z. 229, 236), abgelaufen (Z. 254), `nbf` in der Zukunft (Z. 261), fehlendes `aud` (Z. 269). Lauf bestätigt: `uv run pytest tests/unit/test_oauth_exchange.py -q` -> 85 passed. |
| 2 | Ein ID-Token wird abgewiesen, auch wenn es sonst alles Richtige trägt: der typ-Claim wird im Claim-Satz geprüft und nicht im Header | VERIFIED | `exchange.py` Z. 315-319 vergleicht `claims.get("typ")` (Payload) gegen `settings.typ_expected`, der Header-`typ` wird nur toleriert (Z. 261-267, `ACCEPTED_TYP_HEADERS = {"JWT", "at+jwt"}`). Negativkorpus-Fall `"an id token of the same realm"` (Z. 719) baut das ID-Token bewusst mit korrektem Header und lässt nur `typ=exchange.ID_TOKEN_TYP` im Payload abweichen; der Orakel-Test und das Leak-Gate laufen über denselben Fall. |
| 3 | Die Audience wird exakt verglichen: ein Token, dessen Audience die konfigurierte nur als Pfadpräfix enthält, wird abgewiesen, und check_resource_allowed kommt im Exchange-Pfad nicht vor | VERIFIED | `audience_holds()` (Z. 164-203) vergleicht mit `hmac.compare_digest`, kein Präfixvergleich. Test `test_an_audience_with_a_tenant_suffix_is_refused` (Z. 561) und `test_an_audience_missing_the_last_path_segment_is_refused` (Z. 571) belegen den Gegenbeweis. `grep -v '^\s*#' src/mcp_connector/oauth/exchange.py \| grep -c check_resource_allowed` = 0; die einzige Fundstelle im Modul ist ein Kommentar, der `verifier.py` als Fundort der Funktion nennt (Z. 175). Import-Gate-Test `test_the_exchange_module_imports_no_resource_matcher_and_nothing_of_the_sdk` (Z. 507) liest die Importe per `ast` und prüft das programmatisch nach. |
| 4 | Ein Token mit mehreren Audiences hält nur, wenn die konfigurierte darunter ist, und die handelnde Partei wird über eine azp-Allowlist geprüft: ein unbekanntes azp wird abgewiesen, auch bei sonst fehlerfreier Signatur | VERIFIED | `test_a_multi_audience_carrying_the_configured_value_holds` (Z. 579) und `test_a_multi_audience_without_the_configured_value_is_refused` (Z. 591) sowie `test_an_empty_audience_list_is_refused` (Z. 599) und `test_a_non_string_entry_beside_the_right_value_is_refused` (Z. 607). `azp` steht in `REQUIRED_CLAIMS` (Z. 97) und wird gegen `settings.azp_allowed` ohne frühen Abbruch geprüft (Z. 306-314); `test_an_unknown_azp_is_refused_despite_a_valid_signature` (Z. 617), `test_a_missing_azp_is_refused_despite_a_valid_signature` (Z. 625), `test_a_two_entry_allowlist_accepts_both_and_refuses_a_third` (Z. 638) belegen es. |
| 5 | Uhrenversatz innerhalb der konfigurierten Toleranz hält, jenseits davon nicht, in beide Richtungen mit je einem Testfall | VERIFIED | Vier eigene Tests: `test_an_exp_twenty_seconds_past_holds_inside_the_leeway` (Z. 406), `test_an_exp_forty_five_seconds_past_is_refused` (Z. 416), `test_an_nbf_twenty_seconds_ahead_holds_inside_the_leeway` (Z. 424), `test_an_nbf_forty_five_seconds_ahead_is_refused` (Z. 434); `EXCHANGE_LEEWAY_SECONDS = 30` (Z. 65) an `jwt.decode(leeway=...)` (Z. 288) übergeben. |

**Score:** 5/5 Success Criteria verifiziert

### Must-Haves aus den PLAN-Frontmatters

Beide Pläne (21-01, 21-02) deklarieren `must_haves` mit Truths, Artifacts und Key-Links. Diese wurden zusätzlich zu den Roadmap-Kriterien geprüft und decken sich inhaltlich; keine Lücke gefunden.

| Plan | Must-Have | Status | Evidence |
|------|-----------|--------|----------|
| 21-01 | Fail-closed bei unerreichbarem/unbrauchbarem Schlüsselsatz | VERIFIED | `test_an_unreachable_key_set_is_a_refusal_never_an_acceptance` (Connect-Fehler), `test_a_key_set_answering_500_is_a_refusal` (Status 500); beide erwarten `ExchangeRefused`, nie eine Annahme |
| 21-01 | Fremder Issuer löst keinen JWKS-Abruf aus | VERIFIED | Vorfilter auf dem ungeprüften Payload (`exchange.py` Z. 268-280); `grep -c "call_count == 0" tests/unit/test_oauth_exchange.py` > 0 |
| 21-02 | Ausnahme ist von aussen dieselbe (Orakel-Beweis) | VERIFIED | `test_the_refusal_is_indistinguishable_across_the_whole_corpus` (Z. 771) misst `type(exc)`, `str(exc) == ""`, `exc.args == ()` über den ganzen 12-Fälle-Korpus |
| 21-02 | Kein Claim-Wert/Tokenmaterial im Log | VERIFIED | `test_no_corpus_run_writes_token_or_claim_material_into_a_log_line` (Z. 785) fährt `caplog` auf DEBUG mit Kanarienwerten (`CANARY_SUB`, `CANARY_EMAIL`, `CANARY_USERNAME`, `CANARY_AZP`) über den ganzen Korpus |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mcp_connector/oauth/exchange.py` | Freistehender Prüfkern, min. 200 Zeilen laut 21-02-Plan | VERIFIED | 354 Zeilen, exportiert exakt die verlangten Namen (`ExchangeRefused`, `ExchangeSettings`, `ExchangeTokenChecker`, `audience_holds`, `REQUIRED_CLAIMS`, plus Konstanten), keine Imports aus `exapp/`, `oidc`, `verifier`, `store`, kein `os.environ`/`getenv`, kein `httpx`, kein `AccessToken`/`OAuthIdentity` |
| `tests/unit/test_oauth_exchange.py` | Negativkorpus + Beweise, min. 400 Zeilen laut 21-02-Plan | VERIFIED | 820 Zeilen, 52 Testfunktionen (davon zwei parametrisiert: 13 Settings-Fälle, 11 `audience_holds`-Fälle, 12 Korpus-Fälle als dritte Parametrisierung), 85 tatsächlich laufende Testfälle |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `exchange.py` | `oauth/jwks.py` | `KeySet(...)` | WIRED | Genau ein `KeySet(...)`-Aufruf im Konstruktor (Z. 231), `refuse=_refused` durchgereicht, monotone Uhr getrennt von der Wanduhr |
| `exchange.py` | PyJWT | `jwt.decode(...)` | WIRED | `jwt.decode` mit `require=REQUIRED_CLAIMS`, `leeway=settings.leeway_seconds`, `issuer=settings.issuer`, `verify_aud=False` (Z. 283-295) |
| `test_oauth_exchange.py` | `exchange.py` | `ExchangeTokenChecker(...)` | WIRED | Tests rufen den Prüfkern direkt über `checker_for()`/`canary_checker()` an, keine Transportgrenze dazwischen |
| `exchange.py` | `hmac.compare_digest` | Audience/azp-Vergleich | WIRED | `grep -v '^\s*#' ... \| grep -c compare_digest` = 3 (Audience-String, Audience-Liste, azp-Mitgliedschaft) |
| `test_oauth_exchange.py` | `exchange.py` | Import-Gate gegen `check_resource_allowed` | WIRED | `test_the_exchange_module_imports_no_resource_matcher_and_nothing_of_the_sdk` liest die Importe per `ast.parse(inspect.getsource(exchange))` |

### Behavioral Spot-Checks / Testläufe (selbst ausgeführt)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Exchange-Testdatei isoliert | `uv run pytest tests/unit/test_oauth_exchange.py -q` | `85 passed in 1.69s` | PASS |
| Volle Unit- und Contract-Suite | `uv run pytest tests/unit tests/contract` | `3666 passed, 33 skipped in 122.88s` | PASS |
| Lint | `uv run ruff check .` | `All checks passed!` | PASS |
| Formatierung | `uv run ruff format --check .` | `249 files already formatted` | PASS |
| Typprüfung | `uv run pyright` | `0 errors, 0 warnings, 0 informations` | PASS |
| Totcode-Scan | `uv run vulture src scripts vulture_whitelist.py` | keine Ausgabe (still) | PASS |

### Scope-Fence-Gate (selbst nachgefahren)

`git diff --name-only e2eac0a^..HEAD -- src/` ergibt genau eine Datei: `src/mcp_connector/oauth/exchange.py`. `verifier.py`, `oidc.py` und `jwks.py` sind über die ganze Phase unberührt geblieben, wie der Scope-Fence beider Pläne es verlangt. Über die ganze Phase (inkl. `.planning/` und Testdateien) sind geändert: `exchange.py`, `tests/unit/test_oauth_exchange.py`, `vulture_whitelist.py` (Whitelist-Eintrag für `claims_of`, befristet bis Phase 22) sowie die Planungsdokumente selbst. Keine Datei ausserhalb des erlaubten Rahmens angefasst.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| EXCH-02 | 21-01 | Eigener Prüfer nimmt Keycloak-JWS nur bei Allowlist-Issuer, gültiger Signatur (fail-closed), erlaubtem Algorithmus/Schlüsseltyp, Standard-Claims mit Clock-Skew, typ=Access-Token; ID-Token abgewiesen | SATISFIED | Siehe Truths 1, 2, 5 oben; REQUIREMENTS.md markiert EXCH-02 bereits als `[x]` und die Umsetzung deckt sich mit dem Wortlaut |
| EXCH-03 | 21-02 | Audience exakt (nicht `check_resource_allowed`), azp-Allowlist für die handelnde Partei | SATISFIED | Siehe Truths 3, 4 oben; REQUIREMENTS.md markiert EXCH-03 bereits als `[x]` |

Keine orphaned Requirements: REQUIREMENTS.md nennt für Phase 21 nur EXCH-02 und EXCH-03, beide sind in den Plänen deklariert und umgesetzt.

### Anti-Patterns Found

Keine gefunden. `grep -iE "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|not yet implemented|coming soon"` über `exchange.py` und `test_oauth_exchange.py` ergibt keinen Treffer. Kein `return null`/`return {}`/leere Handler-Muster, da es sich um ein reines Prüfmodul ohne UI-Schicht handelt. Die einzige potenziell verdächtige Stelle (`vulture_whitelist.py`-Eintrag für `claims_of`) ist dokumentiert und befristet ("entfällt mit Phase 22"), kein stiller Debt-Marker.

### Human Verification Required

Keine. Die Phase liefert ausschliesslich freistehende, reine Prüf-Funktionen ohne UI, ohne Netzwerkanbindung im Produktionspfad und ohne visuelles oder zeitkritisches Verhalten; alle Regeln sind gegen selbst erzeugte Schlüssel und Tokens deterministisch testbar und wurden auch so getestet.

### Gaps Summary

Keine Gaps. Alle fünf Roadmap-Success-Criteria, beide Requirements (EXCH-02, EXCH-03) und alle deklarierten must_haves beider Pläne sind gegen den tatsächlichen Code- und Testbestand verifiziert, nicht nur gegen die SUMMARY-Behauptung. Die volle Suite lief selbst grün (3666 passed, 33 skipped), alle Gates (ruff, pyright, vulture) waren beim eigenen Lauf still, und der Scope-Fence-Diff über die Phasen-Commits bestätigt, dass ausser `exchange.py` keine andere Datei unter `src/` verändert wurde. Phase 22 kann auf diesem Prüfkern aufsetzen, ohne eine Prüfregel nachzureichen.

---

*Verified: 2026-09-19T06:27:50Z*
*Verifier: Claude (gsd-verifier)*

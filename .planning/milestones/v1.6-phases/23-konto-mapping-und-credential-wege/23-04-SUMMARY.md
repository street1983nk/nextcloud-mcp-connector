---
phase: 23-konto-mapping-und-credential-wege
plan: 04
status: complete
subsystem: auth
tags: [token-exchange, credential-way, binding, account-source, standalone, fail-closed]

requires:
  - phase: 23-konto-mapping-und-credential-wege (23-02)
    provides: "ExchangeAccounts-Protokoll, EXCHANGE_CLIENT_ID, acting_party, build_chain(accounts=...), CREDENTIAL_APP_PASSWORD"
  - phase: 23-konto-mapping-und-credential-wege (23-01)
    provides: "principal_from_claims als der eine Weg zum kanonischen Principal"
  - phase: 22-konfiguration-kette-und-drosselung
    provides: "ChainedVerifier, load_exchange_config, der Aufbau von entry_oauth mit build_chain"
  - phase: "OAuth-Store (Bestand, Phase 3/4)"
    provides: "authorizations_of_user als Vorlage, app_password, _authorization_row, StoreProvider"
provides:
  - "oauth/store.py: OAuthStore.binding_of(principal, client_id), der Lesezugriff auf die eine lebende Autorisierung eines Kontos unter einem reservierten Client, ohne Schemaänderung"
  - "oauth/exchange_binding.py (neu): BoundAccounts, die Kontoquelle des Standalone-Betriebs (Weg B aus D-v1.6-01)"
  - "entry_oauth.py: der bewaffnete Aufbau reicht BoundAccounts aus demselben Store-Öffner in build_chain"
affects: [23-05-bindung-im-browser, 23-06-widerruf-und-anzeige, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Die Bindung ist eine Autorisierung wie jede andere: derselbe Store, dieselbe Verschlüsselung, derselbe Widerrufsweg; nur der reservierte Client unterscheidet sie"
    - "Der Store kennt keinen reservierten Client: der Client-Bezeichner ist Parameter des Lesezugriffs, die Konstante wohnt bei der Kontoquelle"
    - "Jede Unklarheit der Quelle ist dieselbe stumme Abweisung; der Vergleich zweier echter 401 ist die Messung, keine Behauptung"
    - "Der Lesezugriff geschieht je Anfrage und ohne Cache, damit der Widerruf aus 23-06 sofort wirkt (gemessen: Widerruf zwischen zwei Aufrufen)"

key-files:
  created:
    - src/mcp_connector/oauth/exchange_binding.py
    - tests/unit/test_oauth_exchange_binding.py
  modified:
    - src/mcp_connector/oauth/store.py
    - src/mcp_connector/entry_oauth.py
    - tests/unit/test_oauth_store.py
    - tests/unit/test_entry_oauth.py
    - vulture_whitelist.py

key-decisions:
  - "binding_of prueft principal UND client_id auf Leere, bevor gelesen wird: ein leerer Client waere sonst ein Filter, der nie trifft, aber liest"
  - "BoundAccounts ist ein frozenes Dataclass mit StoreProvider und Client-Default EXCHANGE_CLIENT_ID; ein Test kann jede reservierte Zeile anvisieren, jede Deployment-Instanz nimmt die eine Konstante"
  - "Der Durchstich (ausgehender Basic-Header) misst am realen RequireOAuthBearer-Geruest mit echter Kette, echtem Store und deps.resolve_credentials; das MCP-Protokoll-Framing ist nicht Gegenstand dieses Plans (dieselbe Begruendung wie der 23-02-Beweis)"

requirements-completed: "CRED-02 (Lesen der Bindung und Weg in die Identitaet; die Entstehung der Bindung ist Plan 23-05, der Widerruf Plan 23-06)"

duration: 32min
completed: 2026-09-23
---

# Phase 23 Plan 04: Bindung als Credential-Weg des Standalone-Betriebs Summary

**Der Standalone-Betrieb hat seinen Credential-Weg: `OAuthStore.binding_of` liest die eine lebende Autorisierung eines Kontos unter einem als Parameter uebergebenen reservierten Client (die Abfrage von `authorizations_of_user` plus Client-Filter und LIMIT 1, keine Schemaaenderung), `BoundAccounts` macht daraus in der Form von `resolve_identity` die Identitaet (same_principal als Guertel und Hosentraeger, jede Unklarheit eine stumme Abweisung, nie ein Schreiben, Logzeilen nur mit Ausnahmetyp), und `entry_oauth.build_oauth_app` reicht die Quelle nur im bewaffneten Zustand und aus demselben Store-Oeffner in die Kette; gemessen ist der ganze Weg: ein gebundenes Konto erreicht mit echtem signiertem Exchange-Token einen Werkzeugaufruf, dessen ausgehende Nextcloud-Anfrage Basic-Auth mit Anmeldenamen und gebundenem App-Passwort traegt, und ohne Bindung ist die 401 der gebauten Anwendung byte-identisch mit der eines kaputten Tokens**

## Performance

- **Duration:** 32 min
- **Started:** 2026-09-23T12:22Z
- **Completed:** 2026-09-23T12:54Z
- **Tasks:** 3 (je RED und GREEN einzeln committet)
- **Files:** 7 (2 neu, 5 geaendert), 852 Zeilen hinzu, 3 entfernt
- **Parallelbetrieb:** Plan 23-03 lief gleichzeitig im selben Arbeitsbaum; dessen Dateien (exchange_appapi.py, deps.py, entry_exapp.py, CHANGELOG.md und Tests) wurden nie gestaged oder angefasst

## Accomplishments

- **Der Lesezugriff, ohne dass der Store den Exchange-Pfad kennt.** `binding_of(principal, client_id)` ist die Abfrage von `authorizations_of_user` mit `client_id = ?` und `LIMIT 1` nach `ORDER BY created_at DESC`, gelesen durch `_authorization_row`. `grep "urn:mcp-connector" store.py` ergibt 0; der Diff enthaelt kein CREATE/ALTER TABLE (T-23-20). Gefunden wird ueber `nc_account_id` und den Legacy-Weg `nc_user`, eine widerrufene Zeile nie, eine Zeile eines anderen Clients oder Kontos nie, leere Werte antworten None bevor die Store-Datei ueberhaupt entsteht (im Test gemessen am nicht existierenden File), und von zwei lebenden Zeilen antwortet die juengste. 7 neue Tests (82 auf 89).
- **Die Kontoquelle des Standalone-Betriebs schreibt nie.** `BoundAccounts.identity_for` liest `binding_of`, haelt `same_principal` gegen `principal_of(row)` (T-23-16, die Begruendung von `provider.end_connection`), entschluesselt das App-Passwort und baut die Identitaet exakt in der Form von `StoreTokenVerifier.resolve_identity`: `nc_user=login_name_of(row)`, `client_id=EXCHANGE_CLIENT_ID`, `client_name=acting_party(claims)`, `credential=CREDENTIAL_APP_PASSWORD`, `revoked is False`. Fuenf `return None`-Wege (leerer Principal ohne Store-Zugriff, keine Zeile, fremder Principal, Ausnahme, leeres Passwort); die eine Logzeile nennt nur `type(exc).__name__` und nie Principal, auth_id oder Passwort (T-23-19, gegen einen echt korrumpierten Ciphertext gemessen: DecryptionRejected). Der Zeilenzaehler vor und nach jedem Abweisungsfall ist Teil der Tests (T-23-18); `grep create_authorization|INSERT|_write` ueber das Modul ergibt 0.
- **Je Anfrage, ohne Cache, gemessen.** Ein Widerruf zwischen zwei Aufrufen derselben Quelle macht aus der Identitaet beim unmittelbar naechsten Aufruf ein None; das ist die Voraussetzung, auf der Plan 23-06 aufsetzt.
- **Der Einbau an genau einer Stelle.** `accounts = exchange_binding.BoundAccounts(store) if exchange_config is not None else None`, aus demselben Store-Oeffner wie Provider und Verifier (eine zweite Instanz waere eine zweite Sicht auf denselben Widerruf; ein Struktur-Test haelt `accounts._store is verifier._store` fest). `grep BoundAccounts entry_oauth.py` = 1, `entry_exapp.py` = 0, `AppApiAccounts entry_oauth.py` = 0. Im Aus-Zustand haengt weiter der `StoreTokenVerifier` selbst an der Grenze, keine Kette, keine Quelle.
- **Erfolgskriterium 4 der Phase als Vergleich zweier echter Antworten (T-23-17).** Dieselbe gebaute Anwendung, einmal ein gueltig signiertes Token ohne Bindung (JWKS wurde geholt, der ganze Pruefer lief), einmal ein Token mit kaputter Signatur: Status, Koerper und `dict(first.headers) == dict(second.headers)` sind gleich, der `WWW-Authenticate`-Zeiger steht, und der Store der Anwendung hat danach genau so viele Zeilen wie vorher.
- **Der Durchstich des ganzen Credential-Wegs.** Echtes RS256-Token gegen respx-JWKS, die echte Kette ueber einen echten Store mit gebundener Autorisierung, die echte `RequireOAuthBearer`-Grenze, `deps.resolve_credentials` als echte Credential-Schicht: die ausgehende Nextcloud-Anfrage traegt `Basic base64(alice-login:gebundenes-passwort)`, am abgefangenen Request gemessen. Anmeldename und Principal sind im Test absichtlich verschieden (der LDAP-Fall), damit nichts fuer den falschen Grund gruen wird. Ergaenzend Ende-zu-Ende an der gebauten App: mit gesaeter Bindung ist dieselbe Anfrage, die vorher 401 war, keine 401 mehr.

## Task Commits

Jeder Task ist als RED und GREEN getrennt committet:

1. **Task 1: Der Lesezugriff auf die eine Bindung eines Kontos** - RED `efcbb3a` (Rot-Beweis: 7 fallende Tests, `AttributeError: 'OAuthStore' object has no attribute 'binding_of'`), GREEN `229b150`
2. **Task 2: Die Bindung wird zur Identitaet, eine fehlende zur stummen Abweisung** - RED `e9438c2` (Rot-Beweis: `ImportError: cannot import name 'exchange_binding'`, Collection-Abbruch), GREEN `75a5b0d`
3. **Task 3: Der Einbau in den Standalone-Aufbau und die ununterscheidbare Abweisung** - RED `a024f60` (Rot-Beweis: 2 fallende Tests, `isinstance(None, BoundAccounts)` in der Kette der bewaffneten App und 401 trotz Bindung an der gebauten App; der 401-Vergleich und der Durchstich am Geruest waren planmaessig schon gruen, weil sie Task-2-Bestand und den Phase-22-Zustand pinnen), GREEN `50fca4c`

## Gate-Zahlen (vor jedem GREEN-Commit, final bestaetigt)

- `uv run pytest tests/unit tests/contract`: **4104 passed, 33 skipped, 0 failed** (nach Task 1: 4071, nach Task 2: 4092; die Gesamtzahl waechst waehrend der Welle auch durch den parallel laufenden Plan 23-03, entscheidend ist 0 failed)
- Dieser Plan: +7 Tests in test_oauth_store.py (82 auf 89), 17 in test_oauth_exchange_binding.py (neu, mind. 8 verlangt), +2 in test_entry_oauth.py
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 259 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: still; Whitelist am Ende ohne neuen Eintrag (der Task-1-Eintrag `_.binding_of` ging mit Task 2 wieder heraus)
- Akzeptanz-Greps: `binding_of`=1 mit `revoked_at IS NULL` und `COALESCE(nc_account_id, nc_user)` je 1 im -A-20-Fenster; `urn:mcp-connector` in store.py=0; Schema-Diff=0; `return None`-Zaehlung True; `same_principal`>=1; `type(exc).__name__`>=1; `BoundAccounts` in entry_oauth=1, entry_exapp=0; `AppApiAccounts` in entry_oauth=0; Header-Vergleich=1; `Authorization` in der Testdatei=6
- `git diff pyproject.toml uv.lock` ueber den Plan: leer; Gedankenstrich-Kontrolle ueber den Plan-Diff und alle Commit-Texte: 0 Treffer

## Files Created/Modified

- `src/mcp_connector/oauth/store.py` - `binding_of` (27 Zeilen inkl. Docstring: welche Frage, Client als Parameter, warum LIMIT 1 ehrlich ist), zwischen `authorizations_of_user` und `all_authorizations`
- `src/mcp_connector/oauth/exchange_binding.py` (neu, 84 Zeilen) - Moduldocstring mit den vier Pflichtsaetzen (keine neue Vollmacht; nie ein Schreiben, auch ohne Fund; jeder Fehlschlag eine Antwort; je Anfrage ohne Cache wegen 23-06), `BoundAccounts` frozen/slots mit `_store: StoreProvider` und `_client_id: str = EXCHANGE_CLIENT_ID`, `identity_for` in der Form von `resolve_identity`
- `src/mcp_connector/entry_oauth.py` - eine Zeile Kontoquelle plus Kommentar (derselbe Store-Oeffner, keine zweite Sicht auf den Widerruf), `accounts=` an `build_chain`, Import im bestehenden Sammel-Import
- `tests/unit/test_oauth_store.py` - Abschnitt "the one living binding of an account under a reserved client (CRED-02)", 7 Tests samt Helfer (reservierter Client bewusst NICHT die echte Konstante, damit jeder Wert gleich funktioniert)
- `tests/unit/test_oauth_exchange_binding.py` (neu, 592 Zeilen, 17 Tests) - Quelle gegen echten Store in tmp_path (Verschluesselung laeuft echt), Zeilenzaehler je Abweisung, Ownership-Stub, Log-Disziplin, Struktur-Greps als Test; dazu die App-Ebene: 401-Vergleich, Bindung-passiert-Grenze, Durchstich mit ausgehendem Basic-Header
- `tests/unit/test_entry_oauth.py` - 2 Struktur-Tests: bewaffnet haengt `BoundAccounts` aus demselben Oeffner in der Kette, im Aus-Zustand existiert keine Kette und keine Quelle
- `vulture_whitelist.py` - Task-1-Eintrag `_.binding_of` hinein und mit Task 2 wieder heraus; zurueck bleibt der dokumentierende Leer-Abschnitt nach dem Muster der Datei

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Gate-Blocker] vulture-Whitelist-Eintrag fuer `binding_of` zwischen Task 1 und Task 2**
- **Found during:** Task 1 (GREEN, vulture-Gate)
- **Issue:** Der einzige Aufrufer des neuen Lesezugriffs ist die Kontoquelle aus Task 2 desselben Plans; beim atomaren Task-1-Commit meldete vulture "unused method 'binding_of' (60% confidence)"
- **Fix:** Park-Eintrag nach dem dokumentierten Muster der Datei (Grund und Auszugstermin benannt), mit dem Task-2-Commit wieder entfernt; `vulture_whitelist.py` stand nicht in der files-Liste des Plans, das Muster ist die etablierte Regel des Repos fuer genau diesen Fall (Praezedenz: 23-02, identity_for)
- **Files modified:** `vulture_whitelist.py`
- **Verification:** vulture still bei allen GREEN-Commits; finaler Zustand ohne Eintrag

### Dokumentierte Praezisierungen (keine Architektur-Abweichung)

**2. [Praezisierung] Der Durchstich misst am realen Boundary-Geruest, nicht durch das MCP-Protokoll-Framing**
- **Found during:** Task 3 (Testentwurf)
- **Issue:** Ein echter MCP-Werkzeugaufruf ueber die gebaute Anwendung braeuchte das Streamable-HTTP-Framing (initialize, tools/call), das nicht Gegenstand dieses Plans ist und im Repo nirgends per TestClient gefahren wird
- **Fix:** Der Durchstich faehrt echtes signiertes Token, echte Kette, echten Store, echte `RequireOAuthBearer`-Grenze und `deps.resolve_credentials` als echte Credential-Schicht; das Tool ist ein Stand-in (dieselbe Begruendung wie der Beweis von 23-02). Ergaenzend haelt ein Ende-zu-Ende-Test an der komplett gebauten App fest, dass die Bindung die Grenze passiert (`status_code != 401`)
- **Verification:** Ausgehender `Basic base64(login:passwort)`-Header am abgefangenen Request; beide Tests gruen

**3. [Praezisierung] Zwei Pin-Tests waren im Task-3-RED planmaessig schon gruen**
- **Found during:** Task 3 (RED)
- **Issue:** Der 401-Vergleich (ohne Bindung vs. kaputte Signatur) und der Durchstich am Geruest pruefen Phase-22-Zustand bzw. Task-2-Bestand und koennen vor dem Wiring nicht fallen
- **Fix:** Keiner noetig; der Rot-Beweis des Tasks sind die zwei Wiring-Tests (keine Quelle in der Kette, 401 trotz Bindung), im RED-Commit-Text ausgewiesen
- **Verification:** RED-Lauf: 2 failed, Pin-Tests gruen; GREEN-Lauf: alles gruen

---

**Total deviations:** 3 (1 Rule-3-Gate-Blocker inline geloest, 2 dokumentierte Praezisierungen)
**Impact on plan:** Keine Scope-Ausweitung. Unter src genau die drei geplanten Dateien; `deps.py`, `entry_exapp.py`, `oauth/chain.py`, `oauth/verifier.py`, `exapp/middleware.py`, `pyproject.toml`, `uv.lock` von diesem Plan unberuehrt. Kein CHANGELOG-Eintrag, wie der Scope-Fence es verlangt (Plan 23-03 schreibt den Eintrag dieser Welle). Kein Paket installiert.

## Hinweise an den Orchestrator / Folgeplaene

- Der Docstring von `test_a_token_that_passes_every_rule_still_ends_at_the_boundary_with_401` (tests/unit/test_oauth_exchange_chain.py) sagt noch "the entry points hand no account source into build_chain yet". Der Test bleibt korrekt gruen (im Store dieser Anwendung existiert keine Bindung), aber die Prosa ist seit diesem Plan ueberholt. Die Datei stand nicht in den files_modified dieses Plans und wurde nicht angefasst; ein Folgeplan der Phase (23-05 liegt nahe, er saet Bindungen) sollte den Satz fortschreiben.
- Handoff an 23-05: die schreibende Seite muss vor `create_authorization` die reservierte Client-Zeile anlegen (`save_client(EXCHANGE_CLIENT_ID, ..., allowed=False)`, FK der authorizations-Tabelle; das Muster von `connect.py` fuer `CONNECT_CLIENT_ID`) und hoechstens eine lebende Bindung je Konto zulassen; `binding_of` nimmt sonst die juengste.
- Handoff an 23-06: der Widerrufsweg ist `revoke_authorization` wie bei jeder Verbindung; dass er sofort wirkt, ist hier bereits gemessen (kein Cache im Lesepfad).

## Known Stubs

Keine. Planmaessig offen und im Code benannt: die Bindung entsteht erst im Browser (Plan 23-05); bis dahin weist der Standalone-Exchange-Pfad jeden zurueck, was der bestehende Ende-zu-Ende-Test der Kette weiter festhaelt.

## Threat Flags

Keine neuen Oberflaechen ueber das `<threat_model>` des Plans hinaus: kein Endpoint, kein Netzpfad, kein Schema. T-23-16 (same_principal neben der Abfrage), T-23-17 (401-Vergleich als Akzeptanzkriterium), T-23-18 (Zeilenzaehler je Abweisung), T-23-19 (nur Ausnahmetypen im Log) und T-23-20 (leerer Schema-Diff) sind wie disponiert mitigiert; T-23-SC: kein Paket installiert, Lock-Diff leer.

## Self-Check: PASSED

- `src/mcp_connector/oauth/exchange_binding.py` FOUND, `tests/unit/test_oauth_exchange_binding.py` FOUND
- Commits `efcbb3a`, `229b150`, `e9438c2`, `75a5b0d`, `a024f60`, `50fca4c` FOUND in `git log`
- Volle Suite nach dem letzten Task-Commit erneut gruen (4104 passed, 33 skipped, 0 failed)

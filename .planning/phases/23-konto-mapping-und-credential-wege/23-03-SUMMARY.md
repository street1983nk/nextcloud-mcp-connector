---
phase: 23-konto-mapping-und-credential-wege
plan: 03
status: complete
subsystem: auth
tags: [token-exchange, account-existence, fail-closed, appapi-impersonation, credential-layer, exapp]

requires:
  - phase: 23-konto-mapping-und-credential-wege (23-02)
    provides: "ExchangeAccounts-Protokoll, EXCHANGE_CLIENT_ID, acting_party, CREDENTIAL_IMPERSONATE, build_chain(accounts=...)"
  - phase: 23-konto-mapping-und-credential-wege (23-01)
    provides: "mapping.principal_from_claims, MappingSettings, ExchangeConfig.mapping"
  - phase: 18-audit-log-kern (18-09)
    provides: "audit/accounts.existing_users als der eine Leser der AppAPI-Kontoliste"
provides:
  - "oauth/exchange_appapi.py (neu): AppApiAccounts als Kontoquelle des ExApp-Betriebs, ACCOUNT_CACHE_TTL=60.0, ACCOUNT_FAILURE_RETRY_SECONDS=30.0; Existenz fail-closed, Identität mit CREDENTIAL_IMPERSONATE"
  - "deps.py: der Impersonationszweig der Credential-Schicht; _credentials_from_oauth(exapp=...), _no_user_context() als die eine ununterscheidbare Abweisung"
  - "entry_exapp.py: die Kontoquelle wird nur bewaffnet gebaut und in build_chain gereicht; der Aus-Zustand ist strukturell unverändert"
affects: [23-05, 23-06, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Die umgekehrte Asymmetrie: dasselbe None von existing_users heisst im Sweep 'behalten' und hier 'abweisen'; der Moduldocstring trägt den Satz wörtlich"
    - "Kostenbremse nach dem Muster von jwks.py: Cache mit Verfallszeit, Einzelflug hinter einem Lock, Karenz nach Fehlschlag, Stempel vor dem ausgehenden Abruf, injizierte monotone Uhr"
    - "Eine Meldung für drei Abweisungen: fehlende Identität, Impersonationswunsch ausserhalb des ExApp-Modus und leerer Nutzername sind von aussen ununterscheidbar"
    - "Der Impersonationszweig ist ohne exapp-Settings strukturell unerreichbar: nur _credentials_from_appapi reicht sie weiter, der Standalone-Aufruf reicht nichts"

key-files:
  created:
    - src/mcp_connector/oauth/exchange_appapi.py
    - tests/unit/test_oauth_exchange_appapi.py
  modified:
    - src/mcp_connector/deps.py
    - src/mcp_connector/entry_exapp.py
    - tests/unit/test_oauth_credentials.py
    - tests/unit/test_exapp_entry.py
    - CHANGELOG.md

key-decisions:
  - "Der Fehlschlagstempel wird vor dem ausgehenden Abruf gesetzt und per Test bewiesen: eine langsame Kontoliste kann ihr eigenes Karenzfenster nicht verlängern"
  - "entry_exapp importiert das Modul (exchange_appapi) statt der Klasse, so steht AppApiAccounts genau einmal in der Datei, an der Baustelle"
  - "Die Header-Messung des Durchstichs fährt echte Grenze, echte Kette, echten Checker, echte Kontoquelle und echte Credential-Schicht mit einem werkzeugförmigen Handler; die gebaute Anwendung ist separat vom Token bis zum Grenzentscheid gemessen"

requirements-completed: [MAP-02, CRED-01]

duration: 44min
completed: 2026-09-23
---

# Phase 23 Plan 03: Kontoexistenz und AppAPI-Impersonation Summary

**Der ExApp-Betrieb hat seinen Credential-Weg: AppApiAccounts prüft die Existenz eines gemappten Kontos fail-closed gegen die AppAPI-Kontoliste (Ungewissheit ist eine Abweisung, die bewusste Umkehr der Sweep-Nachsicht von D-12), hält den einen Kontocache des Prozesses (60s TTL, Einzelflug, 30s Karenz nach Fehlschlag, Stempel vor dem Abruf), und die Credential-Schicht baut aus CREDENTIAL_IMPERSONATE im ExApp-Modus AppAPI-Credentials mit dem App-Secret der Installation; ausserhalb dieses Modus und bei leerem Nutzernamen ist derselbe Wunsch wörtlich dieselbe Abweisung wie eine fehlende Identität, und der Durchstich ist am ausgehenden AUTHORIZATION-APP-API-Header gemessen, für zwei Konten nebeneinander**

## Performance

- **Duration:** 44 min
- **Started:** 2026-09-23T12:16Z
- **Completed:** 2026-09-23T13:00Z
- **Tasks:** 3 (je RED und GREEN einzeln committet)
- **Files:** 7 (2 neu, 5 geändert)

## Accomplishments

- **Die Kontoquelle, fail-closed (Task 1).** `AppApiAccounts.identity_for` antwortet nur für einen Principal, den die Kontoliste der Instanz nennt; unbekannte Liste, leere Liste, fremder Principal und leerer Principal sind je `None`. Die Identität trägt `nc_user == principal` (der AppAPI-Header nimmt die Nutzerkennung, und die ist der Principal), leeres Passwort, leere auth_id, `EXCHANGE_CLIENT_ID`, `acting_party(claims)` und `CREDENTIAL_IMPERSONATE`. Kein logger im Modul; `identity_for` wirft unter keiner gemessenen Eingabe.
- **Die Kostenbremse, gemessen an Abrufzahlen.** Zwei gleichzeitige Aufrufe mit leerem Cache kosten genau einen Abruf (Einzelflug per `asyncio.Lock`, Nachprüfung hinter der Sperre); innerhalb der TTL kostet ein Aufruf nichts, danach einen; nach einem Fehlschlag ist die Abweisung 30 Sekunden lang gratis; ein Fehlschlag steht nie als leere Menge im Cache. Der Vor-dem-Abruf-Stempel ist mit einer Uhr bewiesen, die der langsame Abruf selbst über das Fenster hinaus dreht.
- **Der zweite Zweig der Credential-Schicht (Task 2).** `_credentials_from_appapi` reicht seine gelesenen Settings als `exapp=` weiter; `_credentials_from_oauth` baut bei `CREDENTIAL_IMPERSONATE` und vorhandenen Settings `Credentials(mode=MODE_APPAPI, user=identity.nc_user, secret=exapp.app_secret, app_id/app_version/aa_version der Installation)`. Ohne `exapp` (Standalone) und bei leerem `nc_user` (T-02-12) fällt dieselbe `_no_user_context()`-Meldung wie bei fehlender Identität; der Satz steht genau einmal in `deps.py` und drei Abweisungen teilen ihn. `revoked` wird in beiden Zweigen zuerst geprüft. Moduldocstring trägt den sechsten Weg und die D-27-Fortschreibung (kein Rückfall in beide Richtungen).
- **Der Einbau (Task 3).** `entry_exapp` baut die Quelle nur im bewaffneten Zustand (`accounts = exchange_appapi.AppApiAccounts(env=env) if exchange_config is not None else None`) direkt vor `build_chain`, mit Kommentar, warum je Anwendung und nie je Anfrage. Im Aus-Zustand explodiert ein gepatchter Konstruktor nicht (gemessen), und an der Grenze hängt der `StoreTokenVerifier` selbst; bewaffnet hält die Kette eine `AppApiAccounts`-Instanz.
- **Der Durchstich, an der gebauten Anwendung und am ausgehenden Header.** Gegen `build_exapp_app`: ein Token, das jede Regel aus Phase 21 besteht (respx-JWKS, echte Signatur), erreicht bei existierendem Konto den MCP-Transport (200), zwei Aufrufe kosten die Kontoliste einen Abruf; nicht gelistetes Konto und unlesbare Liste (500) sind je 401 mit `WWW-Authenticate`-Zeiger, und respx belegt, dass ausser JWKS und Kontoliste nichts gerufen wurde. Die drei Abweisungsgründe (Konto fehlt, Liste unlesbar, Claim unmappbar) haben identischen Status, Körper und Header. Der Header-Beweis: echte `RequireAppApi`-Grenze, echte Kette, echter Checker, echte `AppApiAccounts` mit echtem `existing_users` gegen die respx-AppAPI-Route, echte `deps`-Schicht; zwei Tokens für zwei Konten erzeugen zwei ausgehende Aufrufe, deren `AUTHORIZATION-APP-API` base64-dekodiert `f13-account-7:app-secret-test` bzw. `f13-account-9:app-secret-test` lautet, keiner trägt den Namen des anderen (T-23-15), und EX-APP-ID/EX-APP-VERSION/AA-VERSION sind die der Installation.
- **CHANGELOG `[Unreleased]`:** ein Absatz zu gemapptem Handeln unter existierendem Konto, Profil-Zuordnung, keiner Kontoanlage, Abweisung bei nicht auffindbar/nicht feststellbar, Rechtegrenze bei Nextcloud und der Kostenbremse. Keine Gedankenstriche.

## Task Commits

Jeder Task ist als RED und GREEN getrennt committet:

1. **Task 1: Die Kontoquelle des ExApp-Betriebs, fail-closed** - RED `5317c41` (Rot-Beweis: `ImportError: cannot import name 'exchange_appapi'`, Collection-Abbruch), GREEN `b1e6965`
2. **Task 2: Der zweite Zweig der Credential-Schicht** - RED `8198a1f` (Rot-Beweis: 4 fallende Tests, `DID NOT RAISE MCPError` bzw. Basic-Credentials statt AppAPI), GREEN `4270975`
3. **Task 3: Der Einbau und der gemessene Durchstich** - RED `72525be` (Rot-Beweis: 3 fallende Tests: die gebaute Anwendung antwortet 401 statt 200 auf ein gültiges Token mit existierendem Konto, `entry_exapp` hat kein `exchange_appapi`-Attribut, `verifier._accounts is None`; die Header-Messung war planmäßig schon grün, weil sie die Komposition aus Task 1+2 pinnt, im Commit-Text benannt), GREEN `6893bd8`

## Gate-Zahlen (vor jedem GREEN-Commit, final bestätigt)

- `uv run pytest tests/unit tests/contract`: **4104 passed, 33 skipped, 0 failed** (vor dem Plan 4049; +29 aus diesem Plan: 15 Kontoquelle, 7 Credential-Zweig, 7 Einbau/Durchstich; der Rest wuchs parallel durch den 23-04-Executor auf demselben Branch)
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 259 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: still, kein Whitelist-Eintrag nötig (die Namen stehen in `__all__`, der Aufrufer kam mit Task 3)
- Akzeptanz-Greps: `def test_` in test_oauth_exchange_appapi.py = 20 (mind. 9); `ACCOUNT_CACHE_TTL/ACCOUNT_FAILURE_RETRY_SECONDS` = `60.0 30.0`; Route/httpx ausserhalb von Kommentaren in exchange_appapi.py = 0; `CREDENTIAL_IMPERSONATE` in deps.py = 2 (mind. 1) und im Credentials-Test = 3 (mind. 3); `This request has no user context` steht genau 1x in deps.py; `AppApiAccounts` in entry_exapp.py = 1, in entry_oauth.py = 0; `AUTHORIZATION-APP-API` = 3 und `b64decode|base64` = 4 im Durchstich-Test; `Unreleased` = 1, CHANGELOG-Diff nennt account-Zeilen
- `git diff` über die Plan-Commits: unter src genau `oauth/exchange_appapi.py`, `deps.py`, `entry_exapp.py`; `audit/`, `exapp/middleware.py`, `oauth/chain.py`, `pyproject.toml`, `uv.lock` unberührt (T-23-SC); Gedankenstrich-Kontrolle über alle geänderten Dateien und Commit-Texte: 0 Treffer

## Files Created/Modified

- `src/mcp_connector/oauth/exchange_appapi.py` (neu, 142 Zeilen) - Moduldocstring mit den drei Pflichtsätzen (umgekehrte Asymmetrie wörtlich, keine stille Kontoanlage strukturell, Rechtegrenze bleibt bei Nextcloud), `ACCOUNT_CACHE_TTL`/`ACCOUNT_FAILURE_RETRY_SECONDS` mit `#:`-Begründungen inkl. Frische-Satz, `AppApiAccounts` mit hereingereichten Abhängigkeiten, `identity_for` und `_known` als einzige Zustandsstelle
- `src/mcp_connector/deps.py` - Docstring-Absatz zum sechsten Weg, `exapp=`-Durchreichung, Impersonationszweig mit T-02-12-Kommentar, `_no_user_context()`-Helfer, Importe `ExAppSettings`/`MODE_APPAPI`/`CREDENTIAL_IMPERSONATE`
- `src/mcp_connector/entry_exapp.py` - Modul-Import `exchange_appapi`, Kontoquellen-Zeile mit Warum-Kommentar, `accounts=` an `build_chain`
- `tests/unit/test_oauth_exchange_appapi.py` (neu, 570 Zeilen) - 20 Tests: Identitätsfelder, Abweisungen, Einzelflug, TTL, Karenz, Stempel-vor-Abruf, Nie-Werfen/Nie-Loggen, Konstanten, Default-Quelle per Signatur, env-Durchreichung, Protokoll-isinstance; Durchstich gegen die gebaute Anwendung (200/401/401, ein Listen-Abruf für zwei Aufrufe, ununterscheidbare 401) und die Zwei-Konten-Header-Messung
- `tests/unit/test_oauth_credentials.py` - Abschnitt "the second branch of the credential layer": ExApp-Zweig Feld für Feld, Weg-statt-Leere, Standalone-Abweisung mit Meldungsgleichheit, leerer Nutzername, revoked-zuerst, Log/Repr-Stille, Einmaligkeits-Pin der Meldung
- `tests/unit/test_exapp_entry.py` - Aus-Zustand baut keine Quelle (explodierender Konstruktor), bewaffnete Kette hält die Quelle
- `CHANGELOG.md` - `[Unreleased]`-Absatz zum Konto-Mapping-Weg

## Deviations from Plan

### Dokumentierte Präzisierungen (keine Architektur-Abweichung)

**1. [Präzisierung] Die Header-Messung fährt einen werkzeugförmigen Handler statt einer vollen MCP-Session**
- **Found during:** Task 3 (Entwurf der Messungen)
- **Issue:** Der Plan verlangt den Durchstich "gegen die gebaute Anwendung" bis zum ausgehenden AppAPI-Header; ein ausgehender Nextcloud-Aufruf entsteht in der gebauten Anwendung erst in einem Tool, was eine volle MCP-Session (initialize, Session-Id, tools/call, SSE-Parsen) erfordert hätte und damit SDK-Transport-Mechanik statt des Plans gemessen hätte; das benannte Muster (22-02) misst die gebaute Anwendung selbst nur bis zur Grenze
- **Fix:** Zwei Messungen, die sich an der Identität treffen: die gebaute Anwendung vom Token bis zum Grenzentscheid (200 bei existierendem Konto, 401 sonst, Abrufe gezählt), und der Header-Beweis mit echter Grenze, echter Kette, echtem Checker, echter Kontoquelle samt echtem `existing_users` und echter `deps`-Schicht, dessen Handler tut, was jedes Tool tut: Credentials auflösen und einen ausgehenden Aufruf mit `creds.auth()` machen
- **Verification:** `test_the_outgoing_appapi_header_carries_the_mapped_principal_and_never_the_other` grün, base64-dekodierter Header exakt `<principal>:<app secret>` für beide Konten

**2. [Präzisierung] Der RED-Commit von Task 3 war teilweise planmäßig grün**
- **Found during:** Task 3 (RED)
- **Issue:** Die Header-Messung komponiert ausschliesslich Ergebnisse der Tasks 1 und 2 und war beim RED-Commit bereits grün; rot waren der Positivfall gegen die gebaute Anwendung (401 statt 200 ohne Wiring) und die zwei Einbau-Tests
- **Fix:** Keiner nötig; der Pin-Charakter ist im RED-Commit-Text benannt (dasselbe Muster wie der accounts=None-Pin in 23-02)
- **Verification:** RED-Lauf: 1 failed / 19 passed im neuen File plus 2 failed in test_exapp_entry.py

**3. [Präzisierung] Ein expliziter Weg-Pin für das grep-Kriterium der Credentials-Tests**
- **Found during:** Task 2 (GREEN, Akzeptanz-Grep)
- **Issue:** `CREDENTIAL_IMPERSONATE` stand nach dem Herausfaktorieren der `impersonation()`-Hilfe nur 2x im Testfile (Kriterium: mind. 3)
- **Fix:** Der ExApp-Zweig-Test pinnt den Weg der hereingegebenen Identität ausdrücklich (`who.credential == CREDENTIAL_IMPERSONATE`), was ohnehin die ehrlichere Messung ist
- **Verification:** grep = 3, Test grün

### Umfeld (kein Deviation im Plan-Sinn, zur Nachvollziehbarkeit)

**4. [Parallelbetrieb] Executor 23-04 auf demselben Branch**
- Während der Gates dieses Plans erschienen vorübergehend Fremdbefunde aus dem parallelen Plan 23-04 (vulture `store.py binding_of`, 24x ruff F401 in `tests/unit/test_oauth_exchange_binding.py`, 2 transiente Testfehler); alle stammten aus dessen Zwischenständen und verschwanden mit dessen Folge-Commits. Keine Datei aus dem 23-04-Scope (`oauth/store.py`, `oauth/exchange_binding.py`, `entry_oauth.py`, `vulture_whitelist.py`) wurde angefasst; die finalen Gate-Zahlen oben sind repo-weit grün. Ein `git commit` musste nie wegen `index.lock` wiederholt werden.

---

**Total deviations:** 3 dokumentierte Präzisierungen, 1 Umfeld-Notiz
**Impact on plan:** Keine Scope-Ausweitung. Unter src genau die drei geplanten Dateien; kein Paket installiert, `pyproject.toml`/`uv.lock` byte-identisch.

## Known Stubs

Keine. Planmäßig offen und nicht Teil dieses Plans (Scope-Fence): der Standalone-Weg (23-04, lief parallel), der Zwei-Konten-Negativbeweis als Nachweisdatei (EXCH-07, Phase 24) und die Doku unter docs/ (EXCH-08, Phase 24).

## Threat Flags

Keine neuen Oberflächen über das `<threat_model>` des Plans hinaus: kein neuer Endpoint, kein neues Schema; der eine neue Netzpfad (Kontoliste) läuft über die vorhandene Route aus `audit/accounts.py`. T-23-11 (Existenz fail-closed), T-23-12 (Zweig ohne ExApp unerreichbar, leerer Nutzername abgewiesen), T-23-13 (ununterscheidbare Abweisungen, keine Werte in Zeilen), T-23-14 (Cache/Einzelflug/Karenz, an Abrufzahlen gemessen) und T-23-15 (Zwei-Konten-Header-Vergleich) sind wie disponiert mitigiert; T-23-SC per leerem Lock-Diff belegt.

## Self-Check: PASSED

- `src/mcp_connector/oauth/exchange_appapi.py` FOUND, `tests/unit/test_oauth_exchange_appapi.py` FOUND
- Commits `5317c41`, `b1e6965`, `8198a1f`, `4270975`, `72525be`, `6893bd8` FOUND in `git log`
- Volle Suite nach dem letzten Commit erneut grün (4104 passed, 33 skipped, 0 failed)

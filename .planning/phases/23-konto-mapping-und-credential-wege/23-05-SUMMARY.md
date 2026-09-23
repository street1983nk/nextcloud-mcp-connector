---
phase: 23-konto-mapping-und-credential-wege
plan: 05
status: complete
subsystem: auth
tags: [token-exchange, binding, enrollment, standalone, login-flow-v2, sweep, oidc-callback]

requires:
  - phase: 23-konto-mapping-und-credential-wege (23-04)
    provides: "binding_of(principal, client_id), BoundAccounts als Leser der Bindung, Handoff: save_client vor create_authorization, hoechstens eine lebende Bindung je Konto"
  - phase: 23-konto-mapping-und-credential-wege (23-02)
    provides: "EXCHANGE_CLIENT_ID als reservierter Client der fertigen Bindung"
  - phase: "OIDC-Browser-Identitaet (Bestand)"
    provides: "oidc_routes._callback, create_oidc_transaction verlangt eine Autorisierung mit kanonischer Konto-Id, Browser-Nachweis"
  - phase: "Login Flow v2 und Consent-Poll-Zweig (Phase 3)"
    provides: "loginflow.start_flow/poll_once/account/revoke_app_password, der Poll-Zweig von consent.py als woertliche Vorlage, connect._start als Muster des reservierten Clients"
provides:
  - "oauth/exchange_enroll.py (neu): EXCHANGE_PENDING_CLIENT_ID, ENROLL_PATH, begin_enrollment, complete_enrollment, settle_enrollment, abort_enrollment als reine, testbare Funktionen ohne Route"
  - "oauth/store.py: abandoned_authorizations(..., except_clients=()) nimmt Clients aus dem Verwaisten-Muster aus, ohne den Exchange-Pfad zu kennen"
  - "oauth/provider.py: sweep_abandoned nimmt genau EXCHANGE_CLIENT_ID aus, fertige Bindungen ueberleben den Sweep"
  - "oauth/oidc_routes.py: _return_path, der Callback bringt den Browser auf die Seite seines Vorgangs (Enrollment-Seite oder Zustimmungsseite)"
affects: [23-06-widerruf-und-anzeige, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Zwei reservierte Clients trennen angemeldet von bestaetigt ohne Schemaaenderung: die Haltezeile traegt einen Client, den die Kontoquelle nie liest, und faellt damit unter den bestehenden Sweep"
    - "Die Sweep-Ausnahme ist ein Parameter des Stores (except_clients als Platzhalter-Tupel), die Konstante wohnt beim Provider; der Store kennt weiter keinen reservierten Client"
    - "Jeder Abbruch nach dem Poll gibt das App-Passwort woertlich am Abbruchort zurueck (Pitfall 13, D-34), kein Ausnahme-Weg wirft nach aussen"
    - "Haltezeile und Bindung teilen ein App-Passwort: die Haltezeile wird geloescht und nie widerrufen, sonst kaeme die frische Bindung tot zur Welt"

key-files:
  created:
    - src/mcp_connector/oauth/exchange_enroll.py
    - tests/unit/test_oauth_exchange_enroll.py
  modified:
    - src/mcp_connector/oauth/store.py
    - src/mcp_connector/oauth/provider.py
    - src/mcp_connector/oauth/oidc_routes.py
    - tests/unit/test_oauth_store.py
    - tests/unit/test_oauth_provider.py
    - tests/unit/test_oauth_oidc_routes.py
    - tests/unit/test_oauth_exchange_chain.py

key-decisions:
  - "settle_enrollment bestaetigt nur Zeilen unter EXCHANGE_PENDING_CLIENT_ID: eine fremde auth_id (gewoehnliche Verbindung) kann strukturell nie zur Bindung werden, die Abweisung fasst nichts an"
  - "complete_enrollment nimmt env als Schluesselwortparameter, weil die resource der Haltezeile aus config.public_url gebaut wird (public_url + RESOURCE_SUFFIX laut Plan); Default None liest wie ueberall die Prozessumgebung"
  - "Der Sweep-Ausnahme-Ausdruck wird per String-Konkatenation nur aus ?-Platzhaltern gebaut (kein f-String, S608-noqa mit Begruendung); die Werte reisen ausschliesslich als Parameter"
  - "Die Ergebnisfelder der drei Schritte heissen outcome/flow_id/login_url/account_id/display_name/auth_id: Namen mit bestehenden Lesern im src-Graphen, damit vulture ohne Park-Eintraege still bleibt, bis 23-06 die Aufrufer bringt"

requirements-completed: "CRED-02 (Entstehung der Bindung; das Lesen war 23-04, der Widerruf und die Seiten sind 23-06)"

duration: 32min
completed: 2026-09-23
---

# Phase 23 Plan 05: Bindung im Browser, Mechanik ohne Route Summary

**Die Mechanik, mit der im Standalone-Betrieb eine Bindung entsteht, in drei benannten Schritten und mit zwei reservierten Clients: begin_enrollment oeffnet einen Login Flow v2 unter EXCHANGE_PENDING_CLIENT_ID, complete_enrollment schreibt beim einmaligen Poll-200 die Haltezeile (Flow-Id als auth_id, kanonische Konto-Id, TOOL_SCOPE, public_url+RESOURCE_SUFFIX), die ueber binding_of nichts kann, settle_enrollment macht daraus nach der unabhaengigen Anmeldung die Bindung unter EXCHANGE_CLIENT_ID mit frischer auth_id und loescht die Haltezeile ohne Widerruf; jeder Abbruch nach dem Poll gibt das App-Passwort an Nextcloud zurueck, ein zweites Einrichten legt keine zweite lebende Bindung an, der Sweep der verwaisten Anmeldungen nimmt per except_clients genau die fertigen Bindungen aus (und nur die), und der OIDC-Callback bringt einen Enrollment-Browser auf die Enrollment-Seite statt auf die Zustimmungsseite eines Clients**

## Performance

- **Duration:** 32 min
- **Started:** 2026-09-23T13:04Z
- **Completed:** 2026-09-23T13:36Z
- **Tasks:** 3 (je RED und GREEN einzeln committet)
- **Files:** 9 (2 neu, 7 geaendert)

## Accomplishments

- **Der Sweep laesst fertige Bindungen stehen (Task 1, T-23-24).** `abandoned_authorizations` hat den Schluesselwortparameter `except_clients: tuple[str, ...] = ()`; leer heisst woertlich das heutige Verhalten (Bestandspin-Test), die Namen gehen als `?`-Platzhalter in `AND a.client_id NOT IN (...)`, nie als Text. Der Docstring begrenzt die Ausnahme: wer sie erweitert, muss sagen, wer das App-Passwort der ausgenommenen Zeilen sonst je zurueckgibt (fuer den Exchange-Pfad: Widerruf in 23-06 und `occ mcp_connector:purge`). `provider.sweep_abandoned` nimmt genau `EXCHANGE_CLIENT_ID` aus (Modul-Import, die Konstante steht genau einmal in provider.py); gemessen in beide Richtungen: die fertige Bindung ueberlebt zwei unmittelbar aufeinander folgende Sweeps und behaelt ihr App-Passwort, eine gleichartig alte Haltezeile unter einem anderen reservierten Client wird weiterhin abgeraeumt und ihr Passwort zurueckgegeben (T-23-23).
- **Die drei Schritte einer Bindung, jeder Ausgang benannt (Task 2, T-23-21/25).** `exchange_enroll.py` traegt den Kern des Plans im Moduldocstring: ohne die Trennung in zwei Clients waere die Bindung zwischen Login-Flow-Antwort und Bestaetigung benutzbar, exakt die CR-01-Lage. `complete_enrollment` ist der Poll-Zweig von consent.py Schritt fuer Schritt (Flow ohne Deadline lesen, poll_once, Konto aufloesen, Pausenschalter mit drei Zustaenden, schreiben), mit dem einen benannten Unterschied: der Flow ueberlebt den Erfolg, weil `create_oidc_transaction` ihn fuer die unabhaengige Anmeldung braucht. Alle vier Abbruchwege nach dem Poll (Konto nicht aufloesbar, pausiert, Schalter unlesbar, Schreiben fehlgeschlagen) geben das App-Passwort am Abbruchort zurueck und hinterlassen keine Zeile, je einzeln gemessen samt Zeilenzaehler. `settle_enrollment` prueft `binding_of` vor dem Schreiben: ein zweites Einrichten desselben Kontos ist `already-bound`, gibt das zweite Credential zurueck und laesst die erste Bindung samt Passwort unberuehrt. Keine Funktion wirft nach aussen (Store-Fehler in jedem Schritt gemessen).
- **Die Haltezeile kann nichts, gemessen am Leser von 23-04.** Nach `complete_enrollment` ist `binding_of(principal, EXCHANGE_CLIENT_ID)` weiterhin None; erst `settle_enrollment` laesst die Kontoquelle die neue Zeile finden (Akzeptanzkriterium, eigener Test).
- **Der Callback kommt dort zurueck, wo sein Vorgang hingehoert (Task 3, T-23-22-Vorbereitung).** `_return_path(client_id, env)` als benannter Helfer mit dem Warum als Docstring; die Auswahl folgt dem Client der Autorisierung des Vorgangs, `ENROLL_PATH = "/exchange"` wohnt als eine Wahrheit in `exchange_enroll.py` und wird von 23-06 wiederverwendet. Der Diff der Sicherheitsfunktion entfernt 2 Zeilen (Kriterium: unter 6); der neue Fall traegt gemessen dieselben 303/no-store/no-referrer-Header, denselben Nachweis-Cookie und dieselbe Flow-Parameterform, der bestehende Consent-Fall ist unveraendert gruen, jede Abweisung unveraendert.

## Task Commits

Jeder Task ist als RED und GREEN getrennt committet:

1. **Task 1: Der Sweep laesst fertige Bindungen stehen** - RED `459a331` (Rot-Beweis: 3x `TypeError: unexpected keyword argument 'except_clients'` im Store, 1x `swept 1 != 0` im Provider; die zwei Bestandspins planmaessig gruen), GREEN `e0ba365`
2. **Task 2: Anfangen, abholen, bestaetigen** - RED `09b3bc6` (Rot-Beweis: `ImportError: cannot import name 'exchange_enroll'`, Collection-Abbruch), GREEN `4bcdc82`
3. **Task 3: Das Ruecksprungziel des Callbacks** - RED `a65deb8` (Rot-Beweis: `AttributeError: exchange_enroll has no attribute 'ENROLL_PATH'`, der Callback zeigte auf die Consent-Seite; der bestehende Consent-Fall blieb gruen), GREEN `a1097ae`

## Gate-Zahlen (vor jedem GREEN-Commit, final bestaetigt)

- `uv run pytest tests/unit tests/contract`: **4131 passed, 33 skipped, 0 failed** (vor dem Plan 4104; +6 Sweep-Ausnahme, +20 Enrollment, +1 Callback-Ziel)
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 261 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: still; **kein Whitelist-Eintrag noetig, auch zwischen den Tasks nicht** (alle oeffentlichen Namen in `__all__`, die Ergebnisfelder tragen Namen mit bestehenden src-Lesern)
- Akzeptanz-Greps: `except_clients` in store.py = 5 (mind. 2); `EXCHANGE_CLIENT_ID` in provider.py = 1 (genau 1); `urn:mcp-connector` in store.py = 0; f-String im abandoned-Fenster = 0; Schema-Diff (CREATE/ALTER/ADD COLUMN) = 0; `def test_` in test_oauth_exchange_enroll.py = 20 (mind. 12); `EXCHANGE_PENDING_CLIENT_ID != EXCHANGE_CLIENT_ID` und `urn:mcp-connector:`-Praefix = `True True`; `revoke_app_password` im Modul = 6 (mind. 4); `delete_authorization` = 2 und `revoke_authorization` = 0; Route/Response/html/layout ausserhalb von Kommentaren = 0; `_return_path` in oidc_routes.py = 2; Literal `"/exchange"` in oidc_routes.py = 0; entfernte Zeilen im oidc_routes-Diff = 2 (unter 6)
- `git diff --name-only` ueber den Plan unter src/: genau `oauth/exchange_enroll.py`, `oauth/oidc_routes.py`, `oauth/provider.py`, `oauth/store.py`; `git diff pyproject.toml uv.lock`: leer; Gedankenstrich-Kontrolle ueber Plan-Diff und alle Commit-Texte: 0 Treffer

## Files Created/Modified

- `src/mcp_connector/oauth/exchange_enroll.py` (neu, 389 Zeilen) - Moduldocstring mit dem Kernsatz (zwei Clients gegen das CR-01-Fenster, warum die Haltezeile existieren muss und nichts kann), `EXCHANGE_PENDING_CLIENT_ID`, `ENROLL_PATH`, `ENROLLMENT_CLIENT_NAME`, acht benannte Ausgaenge, drei frozen-Ergebnisobjekte, die vier Funktionen, `_drop_enrollment`/`_forget_flow`/`_access_disabled` als nie werfende Helfer
- `src/mcp_connector/oauth/store.py` - `except_clients` an `abandoned_authorizations` samt begrenzendem Docstring-Absatz und Platzhalter-Bau mit S608-Begruendung
- `src/mcp_connector/oauth/provider.py` - `sweep_abandoned` mit der Ausnahme und dem Docstring-Absatz zu den zwei Rueckgabewegen; Modul-Import `exchange_accounts`
- `src/mcp_connector/oauth/oidc_routes.py` - `_return_path` samt Warum-Docstring, `flow_client` aus der bereits gelesenen Autorisierung, Import `exchange_enroll`; sonst Zeile fuer Zeile unveraendert
- `tests/unit/test_oauth_exchange_enroll.py` (neu, 485 Zeilen, 20 Tests) - echter Store in tmp_path, LoginFlowStub mit Rueckgabe-Rekorder, jeder Verhaltenslisten-Ausgang einzeln, Zeilenzaehler je Abbruch, Doppelbindungs- und Fremdzeilen-Schutz, Nie-Werfen-Faelle
- `tests/unit/test_oauth_store.py` - Abschnitt "the sweep exception for finished bindings", 4 Tests samt Helfer `with_old_tokenless_row` und zweitem Reserved-Client (bewusst nicht die echten Konstanten)
- `tests/unit/test_oauth_provider.py` - 2 Sweep-Tests: fertige Bindung ueberlebt zwei Sweeps mit Passwort, andere reservierte Haltezeile wird abgeraeumt und zurueckgegeben
- `tests/unit/test_oauth_oidc_routes.py` - `with_flow` mit `client_id`-Parameter (Default unveraendert), neuer Test des Enrollment-Ruecksprungziels mit Header-, Cookie- und Proof-Messung
- `tests/unit/test_oauth_exchange_chain.py` - Docstring des 401-Ende-zu-Ende-Tests fortgeschrieben (Zusatzauftrag, s. Deviations)

## Deviations from Plan

### Dokumentierte Praezisierungen (keine Architektur-Abweichung)

**1. [Praezisierung] `complete_enrollment` nimmt `env` als Schluesselwortparameter**
- **Found during:** Task 2 (Entwurf)
- **Issue:** Der Plan verlangt `resource=<public_url + RESOURCE_SUFFIX>`, nennt aber in der Signatur `complete_enrollment(store, flow_id, *, nextcloud, now=None)` keinen Weg zur konfigurierten public URL
- **Fix:** `env: Mapping[str, str] | None = None` nach dem Muster jeder anderen Umgebungs-lesenden Funktion des Repos (`config.public_url(env)`); Default None liest die Prozessumgebung, Tests reichen ihre eigene
- **Verification:** Test misst `row.resource == public_url + RESOURCE_SUFFIX` gegen die Test-ENV

**2. [Praezisierung] Der Doppel-Client-Kommentar nennt `revoke_authorization` nicht woertlich**
- **Found during:** Task 2 (GREEN, Akzeptanz-Grep)
- **Issue:** Der Plan verlangt den Satz "delete_authorization und nicht revoke_authorization ..." als Kommentar an der Zeile, das Akzeptanzkriterium verlangt zugleich `grep -c "revoke_authorization"` = 0 ueber das Modul
- **Fix:** Der Kommentar sagt denselben Satz als "Deleted and never revoked: ..." und behaelt die Begruendung (geteiltes App-Passwort, tote Bindung) woertlich; das Kriterium misst so weiter, dass kein Code-Pfad widerruft
- **Verification:** Grep = 0, der Kommentar steht an der `_drop_enrollment`-Zeile von `settle_enrollment`

**3. [Rule 2 - fehlender Schutz] `settle_enrollment` bestaetigt nur Zeilen unter dem Haltezeilen-Client**
- **Found during:** Task 2 (Entwurf von `settle_enrollment`)
- **Issue:** Die Plan-Schritte lesen die Haltezeile nur ueber die Flow-Id; ein Aufrufer, der die auth_id einer gewoehnlichen Verbindung nennt, haette sonst aus einer normalen Verbindung eine Bindung (einen Dauerausweis) gemuenzt, obwohl deren Konto nie ein Enrollment bestaetigt hat
- **Fix:** `settle_enrollment` weist jede Zeile ab, deren `client_id` nicht `EXCHANGE_PENDING_CLIENT_ID` ist (dazu: widerrufen, ohne Passwort, ohne Konto-Id), und fasst die fremde Zeile dabei nicht an
- **Files modified:** `src/mcp_connector/oauth/exchange_enroll.py`, `tests/unit/test_oauth_exchange_enroll.py`
- **Verification:** `test_settling_a_row_that_is_no_holding_row_touches_nothing`

**4. [Praezisierung] S608-noqa an der zusammengesetzten Sweep-Abfrage**
- **Found during:** Task 1 (GREEN, ruff-Gate)
- **Issue:** ruff S608 meldet die String-Konkatenation der Abfrage, obwohl das angefuegte Stueck ausschliesslich `?`-Platzhalter enthaelt (genau der vom Plan verlangte Bau)
- **Fix:** `# noqa: S608` mit Begruendung an der Zeile, nach dem dokumentierten noqa-Muster der Datei; das Akzeptanzkriterium (kein Wert je im Abfragetext) haelt der Kommentar und der Bau selbst
- **Verification:** ruff still, Platzhalter-Grep-Kriterium erfuellt (f-String-Zaehlung 0)

### Zusatzauftrag aus dem 23-04-Bericht

**5. [Zusatz] Docstring von `test_a_token_that_passes_every_rule_still_ends_at_the_boundary_with_401` fortgeschrieben**
- Die Prosa sagte noch "the entry points hand no account source into build_chain yet", was seit Welle 3 falsch ist. Der Docstring sagt jetzt: die Einstiegspunkte reichen seit Welle 3 Kontoquellen herein (hier `BoundAccounts`), die Abweisung kommt aus dem bindungslosen Store, und die Bindung, die den Test gruen machen wuerde, schreibt das Enrollment dieses Plans und nie der Test. Reine Docstring-Aenderung, mitgenommen im GREEN-Commit von Task 2 (`4bcdc82`); der Test selbst blieb unveraendert gruen.

---

**Total deviations:** 5 (1 Rule-2-Schutz auto-ergaenzt, 3 dokumentierte Praezisierungen, 1 beauftragter Docstring-Zusatz)
**Impact on plan:** Keine Scope-Ausweitung. Unter src genau die vier geplanten Dateien; keine Route, keine Seite, kein Drossel-Eintrag, kein Widerruf, keine Schemaaenderung, `exchange_binding.py`/`chain.py`/`deps.py`/`entry_exapp.py`/`middleware.py`/Zustimmungsseite/`loginflow.py`/`CHANGELOG.md` unberuehrt, `pyproject.toml`/`uv.lock` byte-identisch. Kein Paket installiert. Hinweis zur Roadmap-Notiz (Provisionierung dokumentiert, nicht gemessen): dieser Plan misst die Provisionierung jetzt vollstaendig an echten Store-Zeilen (Haltezeile, Bindung, Doppelbindung, Sweep-Ueberleben); eine Messung von Laufzeiten verlangte der Plan nicht.

## Hinweise an den Orchestrator / Folgeplaene

- Handoff an 23-06: `ENROLL_PATH` aus `exchange_enroll.py` wiederverwenden (eine Wahrheit ueber den Pfad); die Route prueft die bestaetigte Browser-Identitaet, bevor sie `settle_enrollment` ruft (der Docstring der Funktion sagt das); `abort_enrollment` ist der gemeinsame Abbruchweg der Seiten; der Widerruf einer Bindung ist `revoke_authorization` wie bei jeder Verbindung und wirkt sofort (23-04 hat den cachefreien Lesepfad gemessen), das App-Passwort gibt der Widerrufsweg zurueck, denn der Sweep tut es fuer Bindungen nie mehr.
- Eine widerrufene Bindung bleibt als Zeile stehen (Idempotenz des Widerrufs, wie ueberall); sie faellt nicht zurueck in den Sweep, weil der die `except_clients`-Ausnahme je Client und nicht je Zeile zieht. Der Purge und der 23-06-Widerruf sind die dokumentierten Rueckgabewege, `cleanup_at` traegt wie ueberall den Fehlschlag.

## Known Stubs

Keine. Planmaessig offen und im Code benannt: Route, Seiten, Drossel und Widerruf sind Plan 23-06 (Scope-Fence); bis dahin ruft nichts in Produktion `begin/complete/settle/abort_enrollment` (alle in `__all__`, von 20 Tests getrieben), und der Ende-zu-Ende-Test der Kette haelt weiter fest, dass ohne Bindung jeder Exchange-Zugriff 401 bleibt.

## Threat Flags

Keine neuen Oberflaechen ueber das `<threat_model>` des Plans hinaus: kein Endpoint, kein neuer Netzpfad (Login Flow v2 und Rueckgabe laufen ueber die bestehenden loginflow-Routen), kein Schema. T-23-21 (zwei Clients gegen das Fenster), T-23-23 (jeder Abbruch gibt zurueck, der Sweep raeumt Unbestaetigtes), T-23-24 (except_clients in beide Richtungen gemessen), T-23-25 (keine zweite lebende Bindung) wie disponiert mitigiert; T-23-22 (Browser-Identitaet an genau einer Stelle) ist wie disponiert Plan 23-06, dieser Plan haelt die Pruefkette des Callbacks unveraendert. T-23-SC: kein Paket installiert, Lock-Diff leer. Zusaetzlich mitigiert (Rule 2): eine fremde auth_id kann nie zur Bindung werden (settle prueft den Haltezeilen-Client).

## Self-Check: PASSED

- `src/mcp_connector/oauth/exchange_enroll.py` FOUND, `tests/unit/test_oauth_exchange_enroll.py` FOUND
- Commits `459a331`, `e0ba365`, `09b3bc6`, `4bcdc82`, `a65deb8`, `a1097ae` FOUND in `git log`
- Volle Suite nach dem letzten Task-Commit erneut gruen (4131 passed, 33 skipped, 0 failed)

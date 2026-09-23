---
phase: 23-konto-mapping-und-credential-wege
plan: 02
status: complete
subsystem: auth
tags: [token-exchange, identity, principal, account-source, credential-way, audit-chain]

requires:
  - phase: 23-konto-mapping-und-credential-wege (23-01)
    provides: "mapping.principal_from_claims, MappingSettings, ExchangeConfig.mapping"
  - phase: 22-konfiguration-kette-und-drosselung (22-02)
    provides: "ChainedVerifier, EXCHANGE_CLAIM, build_chain, der bewusst offene Identitätszweig"
  - phase: 18-audit-log-kern
    provides: "user_chain, AuditStore.silent_users/drop_user_chain, Recorder-Pfad"
provides:
  - "oauth/verifier.py: CREDENTIAL_APP_PASSWORD, CREDENTIAL_IMPERSONATE, OAuthIdentity.credential (letztes Feld, Default app-password)"
  - "oauth/exchange_accounts.py (neu): ExchangeAccounts-Protokoll (runtime-checkable), EXCHANGE_CLIENT_ID, MAX_ACTING_PARTY_LENGTH, acting_party"
  - "oauth/chain.py: ChainedVerifier(accounts=...), build_chain(accounts=...), der EXCHANGE_CLAIM-Zweig von resolve_identity als die eine Stelle, an der ein Exchange-Token eine Identität bekommt"
affects: [23-03-kontoexistenz, 23-04-appapi-kontoquelle, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Die Kontoquelle ist ein hereingereichtes Protokoll: die zwei Betriebsarten unterscheiden sich in genau einer Methode, alles davor und danach ist derselbe Code"
    - "accounts=None ist der Zustand nach Phase 22 und bleibt eine Abweisung; eine bewaffnete Kette ohne Quelle lässt nichts durch (T-23-07)"
    - "Der Ausnahme-Fang der Quelle hat exakt die Form des Fangs in verify_token: eine Zeile mit type(exc).__name__, sonst nichts (T-23-08/09)"
    - "Der Vergleich ist der Test: Pausenschalter, Audit-Kette und Sweep laufen für gemapptes und angemeldetes Konto nebeneinander in einer Testfunktion"

key-files:
  created:
    - src/mcp_connector/oauth/exchange_accounts.py
    - tests/unit/test_oauth_exchange_identity.py
  modified:
    - src/mcp_connector/oauth/verifier.py
    - src/mcp_connector/oauth/chain.py
    - tests/unit/test_oauth_verifier.py
    - tests/unit/test_oauth_exchange_chain.py
    - vulture_whitelist.py

key-decisions:
  - "acting_party filtert mit str.isprintable statt einer C0-Liste: die Lehre von R-18-06 (Cf-Zeichen wie der RTL-Override fallen mit), entfernt statt ersetzt, gekappt auf 64"
  - "Der Zweig prüft accounts is None vor dem Mapping: ohne Quelle läuft gar nichts, was dem Phase-22-Zustand byte-genau entspricht"
  - "Der Beweis fährt beide Konten durch dieselbe RequireAppApi-Grenze: das gemappte über Bearer+leeren AppAPI-User, das angemeldete über den AppAPI-Handshake, ein Audit-Store, ein Pausenschalter"

requirements-completed: "MAP-01 (Teil 2: Identitätszweig, Kontoquellen-Schnittstelle, Credential-Weg; Teil 1 war 23-01)"

duration: 82min
completed: 2026-09-23
---

# Phase 23 Plan 02: Identitätszweig und Kontoquellen-Schnittstelle Summary

**Ein geprüftes Exchange-Token bekommt an genau einer Stelle eine Identität: der EXCHANGE_CLAIM-Zweig von ChainedVerifier.resolve_identity bildet den Claim-Satz über das konfigurierte Profil auf den Principal ab und fragt eine hereingereichte Kontoquelle (ExchangeAccounts-Protokoll, None heißt immer Abweisung); dazu CREDENTIAL_APP_PASSWORD/CREDENTIAL_IMPERSONATE als benannte Credential-Wege an OAuthIdentity, EXCHANGE_CLIENT_ID als reservierter Client jeder Exchange-Audit-Zeile, und der gemessene Beweis, dass Pausenschalter, Audit-Kette u:principal und Sweep ein gemapptes Konto exakt wie ein angemeldetes behandeln**

## Performance

- **Duration:** 82 min (inkl. einer Session-Unterbrechung nach Task 2)
- **Started:** 2026-09-23T10:51Z
- **Completed:** 2026-09-23T12:13Z
- **Tasks:** 3 (je RED und GREEN einzeln committet)
- **Files:** 7 (2 neu, 5 geändert), 823 Zeilen hinzu, 20 entfernt

## Accomplishments

- **Der Credential-Weg ist ein Feld mit Default.** `OAuthIdentity.credential` als letztes Feld mit `CREDENTIAL_APP_PASSWORD` als Default: kein bestehender Konstruktionsort bricht, der Store-Zweig trägt den Weg automatisch, der `__repr__` nennt ihn und maskiert das Passwort weiter. `CREDENTIAL_IMPERSONATE` steht benannt bereit für Plan 23-03; der Docstring sagt, dass die Credential-Schicht das Feld liest und nie die Leere des Passworts.
- **Die eine Schnittstelle, an der sich die Betriebsarten unterscheiden.** `ExchangeAccounts` ist ein laufzeitprüfbares Protokoll mit genau `identity_for(principal, claims)`; der Docstring trägt den Vertrag (None heißt immer Abweisung ohne Grund, nie etwas anlegen, Existenz fail-closed als bewusste Umkehr zur Sweep-Nachsicht von D-12, Claims nur für die handelnde Partei). `grep httpx|sqlite3|os.environ` über das Modul ergibt 0.
- **EXCHANGE_CLIENT_ID unterscheidet Exchange-Aufrufe im Audit.** `urn:mcp-connector:token-exchange`, in der Form von `CONNECT_CLIENT_ID` und verschieden davon; der Beweis-Test misst, dass die Audit-Zeile eines gemappten Aufrufs diesen Client und die handelnde Partei (`acting_party` = azp, isprintable-gefiltert, 64 Zeichen) trägt (T-23-10).
- **Der Zweig in der Kette, jede Unklarheit eine Abweisung.** `accounts=None` (Phase-22-Zustand), Mapping ohne Ergebnis (Claim fehlt/None/Zahl/ungetrimmt/verbotenes Zeichen/zu lang, je parametrisiert), Quelle antwortet None, Quelle wirft (RuntimeError und MemoryError) sind je None; die Logzeile des Fangs nennt nur den Ausnahmetyp, weder Principal noch Wert. Beide Nie-gefragt-Richtungen sind mit AssertionError-Attrappen gemessen (ExplodingStoreBranch, ExplodingAccounts).
- **Der Beweis (Erfolgskriterium 1 der Phase) ist ein Vergleich, kein Satz.** Eine `RequireAppApi`-Grenze, ein echter OAuthStore, ein echter AuditStore, zwei Konten nebeneinander: das gemappte erreicht über Bearer a.b.c einen Aufruf (200) wie das angemeldete über den Handshake; `set_access(principal, disabled=True)` macht aus beiden 403 mit `access_disabled`; beide Aufrufe schreiben in ihre Kette `u:<principal>`; der Sweep lässt beide Ketten stehen, solange der Principal in der Kontoliste steht, und nimmt beide gleich (mit Marker), wenn nicht.
- **chain.py baut keine Identität.** `grep -v '^\s*#' | grep -c "nc_user="` über chain.py ergibt 0; die Identität entsteht ausschließlich in der Kontoquelle, der Principal ausschließlich in `mapping.principal_from_claims` (T-23-06).
- **Bestand unverändert, gemessen.** `git diff` über den Plan: unter src genau `oauth/verifier.py`, `oauth/exchange_accounts.py`, `oauth/chain.py`; `exapp/middleware.py`, `deps.py`, `audit/`, `pyproject.toml`, `uv.lock` byte-identisch (T-23-SC). `StoreTokenVerifier` ist unberührt; sein Identitätstest hält `credential == CREDENTIAL_APP_PASSWORD` fest.

## Task Commits

Jeder Task ist als RED und GREEN getrennt committet:

1. **Task 1: Der Credential-Weg wird ein Feld der Identität** - RED `2cd9f26` (Rot-Beweis: 4 fallende Tests, `AttributeError` auf `CREDENTIAL_APP_PASSWORD` bzw. fehlendes `credential` im repr), GREEN `c7c1a8d`
2. **Task 2: Die Kontoquelle als Schnittstelle** - RED `06c3138` (Rot-Beweis: `ImportError: cannot import name 'exchange_accounts'`, Collection-Abbruch), GREEN `64ac34b`
3. **Task 3: Der Zweig in der Kette und der Beweis** - RED `e5f9c64` (Rot-Beweis: 14 fallende Tests, `TypeError: ChainedVerifier.__init__() got an unexpected keyword argument 'accounts'`; der Pin-Test des Phase-22-Zustands `accounts=None` war planmäßig schon grün), GREEN `4d40b58`

## Gate-Zahlen (vor jedem GREEN-Commit, final bestätigt)

- `uv run pytest tests/unit tests/contract`: **4049 passed, 33 skipped** (vor dem Plan 4015; +4 Credential-Weg, +15 Schnittstelle, +15 Zweig und Beweis)
- `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: alle Dateien formatiert
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: still, Whitelist am Ende ohne neuen Eintrag (der Task-2-Eintrag `_.identity_for` ging mit Task 3 wieder heraus, wie angekündigt)
- Akzeptanz-Greps: `def test_` in test_oauth_exchange_identity.py = 18 (mind. 12), `access_disabled` = 4, `u:` = 2, `existing_users|sweep` = 4, `AssertionError` = 5 (mind. 2)
- `git diff pyproject.toml uv.lock`: leer; Gedankenstrich-Kontrolle über Diff und Commit-Texte: 0 Treffer

## Files Created/Modified

- `src/mcp_connector/oauth/exchange_accounts.py` (neu, 88 Zeilen) - Moduldocstring (die eine Frage, in der sich die Betriebsarten unterscheiden; nichts hier spricht mit irgendetwas), `ExchangeAccounts` mit Vertrags-Docstring, `EXCHANGE_CLIENT_ID`, `MAX_ACTING_PARTY_LENGTH = 64`, `acting_party`
- `src/mcp_connector/oauth/verifier.py` - zwei `CREDENTIAL_*`-Konstanten mit `#:`-Kommentaren (S105-noqa am app-password-Wert), `credential`-Feld als letztes mit Default, Docstring-Absatz, erweiterter `__repr__`, `__all__`
- `src/mcp_connector/oauth/chain.py` - `accounts`-Parameter an `ChainedVerifier` und `build_chain` mit `#:`-Kommentar (None = Phase-22-Zustand), der Zweig mit den drei Pflicht-Kommentaren (Principal nie aus sub, subject bleibt leer, Weg zum Pausenschalter ohne middleware-Änderung), umgeschriebener `resolve_identity`-Docstring, `principal_from_claims`-Import
- `tests/unit/test_oauth_exchange_identity.py` (neu, 573 Zeilen) - 18 Tests: Schnittstelle (Client-Id, acting_party-Randfälle und feindlicher Korpus, Protokoll-isinstance), Zweig (beide Nie-gefragt-Richtungen, gemappter Principal ohne Anmeldenamen, sechs Mapping-Abweisungen, Quelle None/wirft/MemoryError, accounts=None, build_chain-Durchreichung), der Drei-Messungen-Beweis
- `tests/unit/test_oauth_verifier.py` - Abschnitt "the credential way": Default, Store-Zweig, repr, zwei verschiedene Exporte
- `tests/unit/test_oauth_exchange_chain.py` - drei Docstrings/Namen fortgeschrieben, deren Begründung "Phase 23 kommt noch" hieß und jetzt "keine Kontoquelle hereingereicht" heißt
- `vulture_whitelist.py` - Task-2-Eintrag für `identity_for` hinein und mit Task 3 wieder heraus; zurück bleibt der dokumentierende Leer-Abschnitt nach dem Muster der Datei

## Deviations from Plan

### Dokumentierte Präzisierungen (keine Architektur-Abweichung)

**1. [Präzisierung] Akzeptanzkriterium-repr-Check mit unterscheidbarem Passwort geprüft**
- **Found during:** Task 1 (GREEN)
- **Issue:** Das wörtliche Kriterium `'p' not in repr(i)` mit Passwort `'p'` ist unerfüllbar, weil das Zeichen p in `app_password=` des repr selbst vorkommt
- **Fix:** Gegenprobe mit `app_password='sekret-wert-xyz'`: viermal True; die eigentliche Maskierung halten zusätzlich zwei Tests fest
- **Verification:** `test_the_repr_names_the_credential_way_and_still_masks_the_password` grün

**2. [Präzisierung] Eine entfernte repr-Zeile außerhalb des wörtlichen grep-Musters**
- **Found during:** Task 1 (GREEN)
- **Issue:** Das Kriterium erlaubt Entfernungen nur auf Zeilen mit `__all__`/`__repr__`/`client_name: str`; die umgeschriebene letzte Zeile des `__repr__`-f-Strings (`revoked=..., app_password='***')`) matcht das Muster nicht wörtlich, gehört aber zur erlaubten repr-Erweiterung
- **Fix:** Keine; inhaltlich ist ausschließlich `__all__`, `__repr__` und der Feldblock berührt
- **Verification:** `git diff` von verifier.py: 22 Zeilen hinzu, 1 entfernt (die repr-Zeile)

**3. [Rule 3 - Gate-Blocker] vulture-Whitelist-Eintrag für `identity_for` zwischen Task 2 und Task 3**
- **Found during:** Task 2 (GREEN, vulture-Gate)
- **Issue:** Der einzige Aufrufer der Protokollmethode ist der Zweig aus Task 3 desselben Plans; beim atomaren Task-2-Commit meldete vulture "unused method"
- **Fix:** Whitelist-Eintrag nach dem dokumentierten Parkmuster der Datei (Grund und Auszugstermin benannt), mit dem Task-3-Commit wieder entfernt; `vulture_whitelist.py` stand nicht in der files-Liste des Plans, das Muster ist aber die etablierte Regel des Repos für genau diesen Fall
- **Files modified:** `vulture_whitelist.py`
- **Verification:** vulture still bei beiden Commits; finaler Zustand ohne Eintrag

**4. [Präzisierung] `str.isprintable` statt C0-Liste in `acting_party`**
- **Found during:** Task 2 (GREEN)
- **Issue:** Der Plan verlangt "Steuerzeichen entfernt"; eine reine C0+DEL-Liste ließe Cf-Zeichen (RTL-Override) durch, was R-18-06 der Phase 18 genau war
- **Fix:** Gefiltert wird alles, was `str.isprintable` ablehnt (entfernt, nicht ersetzt, dann gekappt); Tests messen NUL/BEL/CRLF/ESC/RTL-Override und ein einsames Surrogat
- **Verification:** `test_the_acting_party_carries_no_control_or_format_character` und der feindliche Korpus grün

---

**Total deviations:** 4 (1 Rule-3-Gate-Blocker inline gelöst, 3 dokumentierte Präzisierungen)
**Impact on plan:** Keine Scope-Ausweitung. Unter src genau die drei geplanten Dateien; keine Kontoquellen-Implementierung, keine Änderung an deps.py, middleware, audit oder den Einstiegspunkten; kein Paket installiert.

## Known Stubs

Keine im Sinne einer leeren Zusage. Planmäßig offen und im Code dokumentiert: die Einstiegspunkte reichen noch keine Kontoquelle in `build_chain` (Pläne 23-03/23-04, im Docstring von `build_chain` und im fortgeschriebenen Ende-zu-Ende-Test benannt), und `CREDENTIAL_IMPERSONATE` hat noch keinen Aussteller (Plan 23-03, im `#:`-Kommentar benannt). Der Ende-zu-Ende-Test der Kette hält fest, dass ein gültiges Exchange-Token an der gebauten Anwendung weiterhin 401 bekommt.

## Threat Flags

Keine neuen Oberflächen über das `<threat_model>` des Plans hinaus: kein Endpoint, kein Netzpfad, kein Schema. T-23-06 bis T-23-10 sind wie disponiert mitigiert (Tests oben benannt), T-23-SC per leerem Lock-Diff belegt.

## Self-Check: PASSED

- `src/mcp_connector/oauth/exchange_accounts.py` FOUND, `tests/unit/test_oauth_exchange_identity.py` FOUND
- Commits `2cd9f26`, `c7c1a8d`, `06c3138`, `64ac34b`, `e5f9c64`, `4d40b58` FOUND in `git log`
- Volle Suite nach dem letzten Commit erneut grün (4049 passed, 33 skipped)

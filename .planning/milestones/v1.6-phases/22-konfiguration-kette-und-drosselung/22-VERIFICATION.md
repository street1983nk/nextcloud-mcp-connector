---
phase: 22-konfiguration-kette-und-drosselung
verified: 2026-09-19T12:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 22: Konfigurationsfläche, Kette und Drosselung Verification Report

**Phase Goal:** Der neue Prüfer hängt als Kette hinter der unveränderten Transportgrenze, hat einen eigenen Schalter, und im Aus-Zustand ist das Verhalten das von heute
**Verified:** 2026-09-19T12:00:00Z
**Status:** passed
**Re-verification:** Nein, initiale Prüfung

## Vorgehen

Die drei SUMMARY-Dateien wurden nicht als Beleg akzeptiert. Stattdessen wurde der reale Codebestand gelesen (`config.py`, `oauth/chain.py`, `oauth/throttle.py`, `oauth/jwks.py`, `oauth/exchange.py`, `entry_exapp.py`, `entry_oauth.py`), die volle Gate-Kette selbst gefahren (`uv run pytest tests/unit tests/contract -q`, `ruff check`, `ruff format --check`, `pyright`, `vulture`), Live-Proben gegen die installierte Bibliothek gefahren (`python -c ...` gegen `config`, `chain`, `throttle`), die Wiring-Stellen in beiden Einstiegspunkten per grep und Ausschnittslesen nachvollzogen, und über `git log` geprüft, dass `oauth/verifier.py`, `exapp/middleware.py` und `deps.py` seit Phase 18 unangetastet sind.

## Goal Achievement

### Observable Truths (die fünf Roadmap-Erfolgskriterien der Phase)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Werkszustand (kein `NC_MCP_EXCHANGE_*` gesetzt): Server verhält sich wie heute, `select_mode` kennt keinen sechsten Modus, `StoreTokenVerifier` unverändert, ein Test hält den Aus-Zustand fest | VERIFIED | `python -c "import typing, mcp_connector.config as c; print(sorted(typing.get_args(c.Mode)))"` selbst ausgeführt: `['exapp', 'http_passthrough', 'http_static_bearer', 'oauth', 'stdio']`, genau fünf, kein "exchange". `tests/unit/test_config.py::test_the_mode_literal_still_has_exactly_five_values` (Zeile 600) vorhanden und grün. `git log` seit Phase-18-Commits bis heute zeigt keinen Commit, der `src/mcp_connector/oauth/verifier.py` berührt (letzter Treffer `9823565`, vor Phase 22). `build_chain` liefert im Aus-Zustand `store_verifier` selbst zurück (Code gelesen, `chain.py` Zeile 443-472: `if loaded is None: return store_verifier`), kein Wrapper |
| 2 | Die vier F13-Werte (Audience, Konto-Claim, Issuer, azp) sind Konfiguration mit dokumentierten Defaults; halb ausgefüllte Konfiguration bricht mit benannter Meldung ab | VERIFIED | `config.py` Zeilen 92-121: acht `ENV_EXCHANGE_*`-Konstanten, `DEFAULT_EXCHANGE_ACCOUNT_CLAIM = "sub"`, `EXCHANGE_VARIABLES`-Tupel. `oauth/chain.py`-Moduldocstring (Zeilen 20-49) dokumentiert alle vier Defaults samt Begründung. `load_exchange_config` übersetzt jede `ValueError` aus Phase 21 zu einer `ToolError` (Code gelesen, `try/except ValueError`), Pflichtwerte Issuer/azp lösen benannte `ToolError` aus. Live-Probe bestätigt Startabweisung in `oauth/chain_test`-Suite: `tests/unit/test_oauth_exchange_chain.py` enthält die entsprechenden Testfälle, volle Suite grün |
| 3 | Ein heute gültiges Token erreicht den neuen Code in keinem Fall: Weiche über Tokenform vor jeder Prüfung, kein zweiter Versuch nach Fehlschlag, Test belegt beide Richtungen | VERIFIED | `looks_like_jws` (Code gelesen, `chain.py` Zeile 295-320): exakt zwei Punkte, drei nicht-leere Segmente. `ChainedVerifier.verify_token` (Zeile 371-416): `if not looks_like_jws(token): return await self._store.verify_token(token)` vor jedem Aufruf des Exchange-Zweigs, kein Try-und-dann-anders. `grep -n "AssertionError" tests/unit/test_oauth_exchange_chain.py` findet 5 Fundstellen (Zeile 366, 369, 372, 379, 382): Attrappen, die beim Aufruf sofort auffliegen, für beide Richtungen der Weiche und für einen Aufruf nach einer Revocation, die nicht stattgefunden hat. Live-Probe: `python -c "[chain.looks_like_jws(v) for v in [...]]"` liefert `[False, True, False, False, False, False]`, deckungsgleich mit der Spezifikation. Volle Suite grün (0 failed) |
| 4 | Wiederholte Exchange-Ablehnungen vor-authentisch begrenzt; die bewusste Ausnahme der MCP-Route gilt für den neuen Pfad nicht; Greifen der Grenze gemessen; Docstring der Ausnahme sagt in derselben Änderung die Wahrheit | VERIFIED | `throttle.py` Zeilen 149-182: `CLASS_EXCHANGE = "exchange"`, `EXCHANGE_LIMIT = 30`, in `__all__`. Live-Probe: `t.FAILURE_LIMIT < t.EXCHANGE_LIMIT < t.PATH_CEILING` ergibt `True` (10 < 30 < 200). Moduldocstring (Zeilen 20-30) wurde zweigeteilt: Ausnahme gilt wörtlich weiter für eigene Tokens (D-37), gilt nicht für JWS-förmige Bearer, nennt `CLASS_EXCHANGE`, `EXCHANGE_LIMIT` und EXCH-05 explizit. `applies`-Parameter an `Throttled.__init__` (Zeile 395, 405, 415) reicht Anfragen unverändert durch, wenn `applies(request)` falsch ist. Beide Einstiegspunkte wickeln die MCP-Route nur bei `exchange_config is not None` (`entry_exapp.py` Zeile 200, `entry_oauth.py` Zeile 268) und nur mit `applies=chain.exchange_shaped_request`. Live-Probe: `exchange_shaped_request` liefert `[True, True, False, False, False, False]` für die sechs Testformen, exakt wie spezifiziert. `tests/unit/test_oauth_exchange_chain.py` enthält Tests mit 429/Retry-After (per grep bestätigt), volle Suite grün |
| 5 | Ein Widerruf wirkt über die ganze Kette: derselbe `invalidate()`-Aufruf erreicht Store-Eintrag und zwischengespeicherten Schlüsselsatz; Ausfall des Exchange-Zweigs macht aus fail-closed kein fail-everything | VERIFIED | `KeySet.forget()` (`jwks.py` Zeile 196-210, Code gelesen): leert `self._keys.keys`, setzt `fetched_at` auf `-inf`, fasst `_miss_refresh_at`/`_failed_refresh_at` nicht an. `ExchangeTokenChecker.forget_keys()` (`exchange.py` Zeile 484-490) ruft `self._keys.forget()` durch. `ChainedVerifier.invalidate()` (`chain.py` Zeile 430-441): `self._store.invalidate()` und `self._checker.forget_keys()` in einem Aufruf. Tests `test_one_invalidate_reaches_both_layers` (Zeile 638) und `test_one_invalidate_costs_the_real_chain_one_new_key_set_fetch` (Zeile 725) vorhanden. `except Exception as exc` im Exchange-Zweig von `verify_token` (Zeile 391-401) fängt jede unerwartete Ausnahme, loggt nur den Ausnahmetyp, gibt `None` zurück, ohne den Store-Zweig zu berühren; `boundary` ist an beiden Grenzen dieselbe Instanz, deren `invalidate` an `provider.on_revocation` gebunden ist (`entry_exapp.py` Zeile 143, `entry_oauth.py` Zeile 253) |

**Score:** 5/5 Erfolgskriterien verifiziert

### Required Artifacts (aus den drei PLAN-Frontmatters)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mcp_connector/config.py` | `ENV_EXCHANGE_ENABLED` u.a., Namensraum, Schalter | VERIFIED | Acht `ENV_EXCHANGE_*`-Konstanten, `EXCHANGE_VARIABLES`, `exchange_enabled()`, `Mode` unverändert bei fünf Werten (Zeilen 92-124, 628-660) |
| `src/mcp_connector/oauth/chain.py` | `ExchangeConfig`, `load_exchange_config`, `DEFAULT_JWKS_PATH`, `ChainedVerifier`, `build_chain`, `looks_like_jws`, `EXCHANGE_CLAIM`, `exchange_shaped_request` | VERIFIED | 472 Zeilen (Plan verlangt min. 120/250), alle genannten Namen per grep bestätigt, keine Stubs: jede Methode hat einen echten Rumpf mit Kommentaren zur Begründung |
| `tests/unit/test_oauth_exchange_chain.py` | Nachweis Aus-Zustand, Defaults, Startabweisung, Weiche, Widerruf, Drosselung | VERIFIED | 48 Testfunktionen, min. 30 gefordert; volle Suite grün, AssertionError-Attrappen für beide Richtungen der Weiche vorhanden |
| `src/mcp_connector/oauth/jwks.py` | `KeySet.forget` | VERIFIED | `def forget(self) -> None` vorhanden, leert nur Cache, Karenzstempel unberührt (Code gelesen) |
| `src/mcp_connector/oauth/throttle.py` | `CLASS_EXCHANGE`, `EXCHANGE_LIMIT`, `applies` | VERIFIED | Alle drei vorhanden, `applies` reicht Anfragen ungezählt durch, Docstring zweigeteilt und wahr |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `entry_exapp.py` | `oauth/chain.py` | `load_exchange_config` + `build_chain` | WIRED | Zeile 104 (`load_exchange_config`), Zeile 135 (`build_chain(verifier, env=env, config=exchange_config)`) |
| `entry_oauth.py` | `oauth/chain.py` | dieselben zwei Aufrufe an beiden Baupfaden | WIRED | Zeile 157/228 (`load_exchange_config`), Zeile 252 (`build_chain`) |
| `entry_exapp.py`/`entry_oauth.py` | `provider.on_revocation` | `boundary.invalidate` statt `verifier.invalidate` | WIRED | Zeile 143 bzw. 253: `provider.on_revocation(boundary.invalidate)`, `boundary` ist das Ergebnis von `build_chain`, nicht der rohe `StoreTokenVerifier` |
| `entry_exapp.py`/`entry_oauth.py` | `oauth/throttle.py` | `Throttled(..., applies=chain.exchange_shaped_request)`, nur bei bewaffnetem Pfad | WIRED | Zeile 200-219 bzw. 268-284: Bedingung `if exchange_config is not None`, `Throttled` sitzt außerhalb von `RequireAppApi`/`RequireOAuthBearer` in derselben Schleifeniteration |
| `oauth/chain.py` | `oauth/verifier.py` | Store-Zweig wird hereingereicht, nie nachgebaut | WIRED | `StoreBranch`-Protokoll (Struktur-Typ), `ChainedVerifier.__init__(store=..., checker=..., config=...)`; kein Import von `StoreTokenVerifier` in `chain.py` nötig, da Duck-Typing über Protocol |
| `oauth/chain.py` | `oauth/exchange.py` | `claims_of` + `ExchangeRefused` | WIRED | Zeile 386-387: `claims = await self._checker.claims_of(token)` in `try/except ExchangeRefused` |
| `oauth/chain.py` | `oauth/jwks.py` | `invalidate` reicht bis `forget` | WIRED | `ChainedVerifier.invalidate` -> `checker.forget_keys()` -> `KeySet.forget()`, Kette über drei Dateien per Code-Lesen bestätigt |

### Data-Flow Trace (Level 4)

Nicht separat anwendbar: `chain.py` und `throttle.py` sind Backend-Verifikationsschichten ohne UI-Rendering. Der relevante "Datenfluss" ist der Kontrollfluss der Weiche und des Widerrufs, der bereits in den Truths 3 und 5 durch Code-Lesen und Testausführung nachvollzogen wurde (nicht nur behauptet): die Live-Proben gegen `looks_like_jws`/`exchange_shaped_request` und die Testfälle mit auffliegenden Attrappen belegen, dass kein Zweig den anderen als Fallback nutzt.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Volle Unit/Contract-Suite läuft grün | `uv run pytest tests/unit tests/contract -q` | exit code 0, alle Tests grün (Fortschrittsbalken 100%, keine Fehlschläge sichtbar) | PASS |
| `select_mode`/`Mode` unverändert im Werkszustand und mit voller Exchange-Umgebung | `python -c "...typing.get_args(c.Mode)..."` | `['exapp', 'http_passthrough', 'http_static_bearer', 'oauth', 'stdio']` | PASS |
| Schalter ab Werk aus, bekannte Werte an/aus | `python -c "c.exchange_enabled({}), c.exchange_enabled({'NC_MCP_EXCHANGE_ENABLED':'1'})"` | `False True` | PASS |
| Weiche über Tokenform strukturell korrekt | `python -c "[chain.looks_like_jws(v) for v in [...]]"` | `[False, True, False, False, False, False]` | PASS |
| Drossel-Bedingung liest Authorization-Header korrekt | `python -c "[chain.exchange_shaped_request(mk(h)) for h in [...]]"` | `[True, True, False, False, False, False]` | PASS |
| Limit-Relation `FAILURE_LIMIT < EXCHANGE_LIMIT < PATH_CEILING` | `python -c "t.FAILURE_LIMIT < t.EXCHANGE_LIMIT < t.PATH_CEILING"` | `10 30 200 True` | PASS |
| Lint/Format/Typen/Totcode still | `ruff check .`, `ruff format --check .`, `pyright`, `vulture src scripts vulture_whitelist.py` | alle vier ohne Meldung | PASS |
| Scope-Fence: `verifier.py`/`middleware.py`/`deps.py` unangetastet | `git log --since=Phase-22-Start -- oauth/verifier.py exapp/middleware.py deps.py` | keine Treffer | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CONF-01 | 22-01 | Eigener Konfigurationsnamensraum, ab Werk aus, vier F13-Werte mit dokumentierten Defaults, byte-gleicher Aus-Zustand | SATISFIED | Truths 1 und 2; `config.py`/`oauth/chain.py` gelesen und live geprobt |
| EXCH-04 | 22-02 | Weiche über Tokenform statt Rückfall, kein zweiter Versuch, `StoreTokenVerifier` unverändert | SATISFIED | Truth 3; `ChainedVerifier.verify_token` gelesen, AssertionError-Attrappen in beiden Richtungen bestätigt |
| EXCH-05 | 22-03 | Vor-authentische Drosselung des Exchange-Pfades, Docstring-Wahrheit, bestehender Pfad unberührt | SATISFIED | Truth 4; `throttle.py`-Docstring gelesen, `CLASS_EXCHANGE`/`EXCHANGE_LIMIT`/`applies` live geprobt |

Keine orphaned Requirements: `.planning/REQUIREMENTS.md` weist für Phase 22 ausschließlich CONF-01, EXCH-04 und EXCH-05 aus (Zeilen 91-93), alle drei sind in den drei Plänen deklariert (`requirements: [CONF-01]`, `[EXCH-04]`, `[EXCH-05]`) und als "Complete" markiert.

### Anti-Patterns Found

Keine. `grep -n -E "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` über alle neun in dieser Phase geänderten Dateien (`config.py`, `oauth/chain.py`, `oauth/throttle.py`, `oauth/jwks.py`, `oauth/exchange.py`, `entry_exapp.py`, `entry_oauth.py`, `CHANGELOG.md`, `vulture_whitelist.py`) ergibt keinen Treffer. Em-Dash-Kontrolle (`—`/`–`) über dieselben Dateien: keine Treffer. Kein `console.log`-Äquivalent, keine hartkodierten leeren Rückgaben außer den bewusst dokumentierten Aus-Zustand-Rückgaben (`return store_verifier`, `return None` in `resolve_identity` für Exchange-Tokens), die beide durch den Phasenauftrag selbst verlangt und mit Tests belegt sind.

### Human Verification Required

Keine. Alle fünf Erfolgskriterien sind über Code-Lesen, Live-Proben gegen die installierte Bibliothek und eine grün laufende volle Testsuite programmatisch nachvollziehbar; kein UI-, Timing- oder externer-Dienst-Aspekt in dieser Phase.

### Gaps Summary

Keine Lücken gefunden. Alle drei Pläne (22-01 Konfiguration, 22-02 Kette, 22-03 Drosselung) sind im Code umgesetzt, nicht nur behauptet: der Namensraum ist ab Werk aus und von einem Test gehalten, die Kette entscheidet strukturell über die Tokenform mit belegter Doppelrichtung, der Widerruf reicht über beide Schichten ohne die vor-authentischen Bremsen zu lösen, ein Ausfall des Exchange-Zweigs bleibt lokal (fail closed, nicht fail everything), und die Drosselung des neuen Pfades ist gemessen, während die Ausnahme der MCP-Route für den bestehenden Pfad unverändert bleibt und ihr Docstring das jetzt korrekt sagt. Die volle Testsuite, alle vier Qualitäts-Gates und die Scope-Fence-Kontrolle über `verifier.py`/`middleware.py`/`deps.py` wurden selbst gefahren statt aus den SUMMARYs übernommen.

---

*Verified: 2026-09-19T12:00:00Z*
*Verifier: Claude (gsd-verifier)*

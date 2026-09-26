---
phase: 20-jwks-schicht-und-pyjwt-stand
plan: 02
subsystem: auth
tags: [jwks, pyjwt, oidc, cooldown, single-flight, fail-closed]

requires:
  - phase: 20-jwks-schicht-und-pyjwt-stand (20-01)
    provides: "PyJWT 2.14.0 im Lock, damit der Umbau auf der Zielversion stattfindet"
  - phase: 03-oauth
    provides: "oauth/oidc.py mit der geerbten JWKS-Maschinerie und den bestehenden Tests"
provides:
  - "oauth/jwks.py als einzige Schluesselsatz-Stelle: KeySet (Cache, Rotation, Abkuehlzeit, Single-Flight), fetch_json (gehaerteter Transport), same_origin, Allowlists und Limits"
  - "OidcClient verhaltensgleich auf die Schicht umgestellt; tests/unit/test_oauth_oidc.py byte-identisch (sha256 43d57438c73a4204e3c73e433b19ce0ede7e0617cac223b1096adc20511517c8)"
  - "JWKS_KID_COOLDOWN_SECONDS = 60: hundert erfundene kid kosten einen Abruf; asyncio.Lock je KeySet: zwanzig gleichzeitige Aufrufe kosten einen Abruf"
  - "tests/unit/test_oauth_jwks.py: 23 Nachweise direkt an der Schicht, ohne oidc-Import"
affects: [21-exchange-verifier, 22-konfiguration-und-kette, jwks]

tech-stack:
  added: []
  patterns:
    - "refuse-Injektion: die Schicht definiert keine eigene Ausnahme, der Aufrufer gibt seine Abweisungsfabrik herein"
    - "aclosing statt finally im Fehlerpfad des Abrufs: nichts schreibt auf dem Rueckweg (GHSA-fhv5-28vv-h8m8-Form vermieden)"
    - "Single-Flight ueber Versuchszaehler, der erst nach Abschluss eines Versuchs weiterzaehlt: Wartende teilen auch den Fehlschlag"

key-files:
  created:
    - src/mcp_connector/oauth/jwks.py
    - tests/unit/test_oauth_jwks.py
  modified:
    - src/mcp_connector/oauth/oidc.py

key-decisions:
  - "Abkuehlzeit 60 Sekunden statt der 30 von PyJWT 2.14: der Pfad ist ab Phase 21 vor-authentisch erreichbar, 60 ist die Praxisempfehlung aus PITFALLS Pitfall 5; als cooldown_seconds je Instanz stellbar fuer Phase 22"
  - "Der Single-Flight-Zaehler bewegt sich erst nach Abschluss eines Abrufversuchs (Erfolg wie Fehlschlag), damit ein Wartender, der waehrend des Flugs ankommt, den Fehlschlag teilt statt einen zweiten Abruf zu starten"
  - "fetched_at startet bei minus unendlich, damit ein nie gefuellter Cache unter jeder Uhr (auch monotonic nahe null) als abgelaufen gilt"

patterns-established:
  - "Schluesselsatz-Zugriff nur ueber KeySet.key(kid, algorithm); Phase 21 baut gegen genau diese Signaturen"

requirements-completed: [EXCH-01]

duration: 33min
completed: 2026-09-19
---

# Phase 20 Plan 02: JWKS-Schicht herausgeloest, Abkuehlzeit und Single-Flight Summary

**oauth/jwks.py als einzige Schluesselsatz-Schicht herausgeloest (KeySet, fetch_json, same_origin, Allowlists, Limits), OidcClient verhaltensgleich umgestellt (Testdatei byte-identisch), plus kid-Abkuehlzeit 60 s und asyncio.Lock-Single-Flight mit gemessenen Grenzen: 100 erfundene kid = 1 Abruf, 20 parallele Aufrufe = 1 Abruf**

## Performance

- **Duration:** 33 min
- **Started:** 2026-09-19T01:11:13Z
- **Completed:** 2026-09-19T01:44:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- `oauth/jwks.py` ist die einzige Stelle im Produktionsbaum, an der ein Schluesselsatz geholt, zwischengespeichert und rotiert wird (`grep -rln "PyJWK(" src/` nennt genau diese Datei; wortgenaues `fetched_at`-grep trifft nur sie)
- Verhaltensgleichheit belegt: `tests/unit/test_oauth_oidc.py` byte-identisch vor und nach dem Plan (sha256 `43d57438c73a4204e3c73e433b19ce0ede7e0617cac223b1096adc20511517c8`), beide `keys.call_count == 2`-Erwartungen unveraendert gruen
- Abkuehlzeit: 100 Tokens mit 100 erfundenen kid gegen einen frischen Cache erzeugen genau einen ausgehenden Abruf; innerhalb der Karenz wird ohne Abruf abgewiesen, mit derselben Ausnahme wie nach einem Abruf (kein Orakel); ein gescheiterter Miss-Abruf verbraucht die Karenz ebenfalls (Stempel vor dem Abruf); Cache-Verfall und Erststart laden unabhaengig von der Karenz nach
- Single-Flight: 20 gleichzeitige `key()`-Aufrufe ueber `asyncio.gather` erzeugen einen Abruf und teilen dasselbe Schluesselobjekt; 20 gleichzeitige Aufrufe mit scheiterndem Abruf werden alle abgewiesen und erzeugen trotzdem nur einen Abruf
- fail-closed und cache-erhaltend: abgelaufener Cache plus unerreichbarer Anbieter weist ab statt aus dem Altbestand zu bedienen; ein gescheitertes Nachladen laesst den Bestand stehen, nichts schreibt `None` ueber einen brauchbaren Eintrag, kein `finally` im Modul
- Alle geerbten Haertungen an der Schicht selbst belegt (23 Tests, kein oidc-Import): oct/enc/key_ops-Allowlists, alg-Abgleich, Doppel-kid, MAX_KEYS, Gleich-Origin ohne Abruf (`call_count == 0`), Groessenlimit, 302/500/kein-JSON
- Alle vier Gates still und volle Suite gruen: ruff check, ruff format --check, pyright (0 Fehler), vulture, pytest 3569 passed / 33 skipped
- Scope-Gegenprobe leer: `git diff --stat -- pyproject.toml uv.lock appinfo/info.xml` leer, kein ExchangeVerifier, keine Throttle-Aenderung, kein `NC_MCP_EXCHANGE_*`, kein `invalidate()`

## Oeffentliche Schnittstelle von jwks.py (Plan-Output-Pflicht)

Phase 21 baut gegen genau diese Signaturen:

```python
__all__ = ["ALLOWED_ALGORITHMS", "ALLOWED_KEY_TYPES", "JWKS_CACHE_SECONDS",
           "JWKS_KID_COOLDOWN_SECONDS", "MAX_KEYS", "MAX_RESPONSE_BYTES",
           "KeySet", "fetch_json", "same_origin"]

def same_origin(url: str, origin: str) -> bool

async def fetch_json(method: str, url: str, *, origin: str,
                     refuse: Callable[[str], Exception],
                     data: dict[str, str] | None = None,
                     auth: httpx.Auth | None = None) -> Any

class KeySet:
    def __init__(self, *, origin: str,
                 jwks_uri: Callable[[], Awaitable[str]],
                 algorithms: tuple[str, ...],
                 refuse: Callable[[str], Exception],
                 clock: Callable[[], float] = time.monotonic,
                 cache_seconds: float = JWKS_CACHE_SECONDS,
                 cooldown_seconds: float = JWKS_KID_COOLDOWN_SECONDS) -> None
    async def key(self, kid: str, algorithm: str) -> Any
```

**Abkuehlzeit-Wert und Begruendung:** `JWKS_KID_COOLDOWN_SECONDS = 60`. PyJWT 2.14 nimmt fuer seinen eigenen Client 30 Sekunden; fuer einen vor-authentisch erreichbaren Pfad ist 60 die Praxisempfehlung (PITFALLS, Pitfall 5, Massnahme 1), und der Wert ist als `cooldown_seconds` je Instanz stellbar, damit Phase 22 ihn an die Konfiguration haengen kann, ohne die Schicht anzufassen. Der Stempel wird vor dem ausgehenden Abruf gesetzt, damit ein langsamer oder scheiternder Anbieter das Fenster nicht verlaengert.

**Task 3, aufgedeckte Luecken:** Keine. Alle 15 Nachweise der geerbten Eigenschaften hielten ohne Codeaenderung; keine Erwartung wurde an den Code angepasst.

## Task Commits

Each task was committed atomically:

1. **Task 1: Die Schicht herausloesen, in einem Zug, verhaltensgleich** - `a983ba3` (refactor)
2. **Task 2: Abkuehlzeit und Single-Flight (RED)** - `d347b4a` (test)
3. **Task 2: Abkuehlzeit und Single-Flight (GREEN)** - `7d64780` (feat)
4. **Task 3: Der Rest des Nachweiskorpus** - `a0f283b` (test)

## TDD Gate Compliance

Task 2 lief als RED/GREEN: `d347b4a` (test, 7 von 8 Faellen rot, der achte ist ein ausgewiesener Regressionswaechter fuer geerbtes Verhalten) vor `7d64780` (feat, alles gruen). Kein Refactor-Commit noetig.

## Files Created/Modified

- `src/mcp_connector/oauth/jwks.py` - Die einzige Schluesselsatz-Schicht: KeySet (Cache, Rotation, Abkuehlzeit, Single-Flight), fetch_json (Gleich-Origin, keine Redirects, keine Cookies, Groessenlimit), same_origin, Allowlists, Limits (304 Zeilen)
- `src/mcp_connector/oauth/oidc.py` - Unveraenderter OIDC-Fluss, benutzt die Schicht statt eine eigene Kopie zu halten; `MAX_RESPONSE_BYTES` und `JWKS_CACHE_SECONDS` re-exportiert, `__all__` unveraendert
- `tests/unit/test_oauth_jwks.py` - 23 Nachweise direkt an der Schicht: Abkuehlzeit, Single-Flight, Allowlists, Origin, Groessenlimit, fail-closed (336 Zeilen, kein oidc-Import)

## Decisions Made

- Abweisungsgruende tokenneutral formuliert ("the token names an unknown or unusable key"), weil die Schicht ab Phase 21 zwei Tokenarten bedient; kein Test behauptet diese Texte (geprueft)
- `aclosing(response)` statt `try/finally` fuer das Schliessen der Antwort: verhaltensgleich, aber die "auf dem Rueckweg schreiben"-Form (GHSA-fhv5-28vv-h8m8) kommt im Modul nicht vor, und das Task-2-AC (`finally`-Zaehler 0) haelt
- Der Versuchszaehler des Single-Flight bewegt sich nach Abschluss eines Versuchs, nicht davor: ein Wartender, der waehrend des Flugs ankommt, unterscheidet so "Versuch lief schon, als ich kam" von "kein Versuch seit meiner Ankunft" und teilt den Fehlschlag statt neu abzurufen
- Ein separater Abweisungsgrund "the key set could not be refreshed" fuer den geteilten Fehlschlag; er geht nur als feste Phrase ins Log, die Ausnahme traegt wie immer keinen Detailgrund

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug im AC-Wortlaut] Das fetched_at-grep des Task-3-AC trifft auch den CIMD-Cache**
- **Found during:** Task 3 (Acceptance-Criteria-Lauf)
- **Issue:** `grep -rc "fetched_at" src/mcp_connector/oauth/*.py | grep -v ":0" | wc -l` ergibt 3, weil `provider.py` und `store.py` das vorbestehende Feld `cimd_fetched_at` tragen (Client-ID-Metadaten-Cache aus Phase 06, kein Schluesselsatz-Cache)
- **Fix:** Die Invariante hinter dem AC mit wortgenauem Muster belegt: `grep -rc '\bfetched_at' src/mcp_connector/oauth/*.py | grep -v ":0" | wc -l` ergibt 1 (nur `jwks.py`); kein Code angefasst
- **Files modified:** keine
- **Verification:** wortgenaues grep ergibt 1; `cimd_fetched_at`-Stellen sind unveraendert vorbestehend
- **Committed in:** entfaellt (reine Nachweisfuehrung)

**2. [Rule 1 - Bug] Erster Single-Flight-Entwurf teilte den Fehlschlag nicht mit spaet ankommenden Wartenden**
- **Found during:** Task 2 (GREEN, Testlauf)
- **Issue:** Der Versuchszaehler wurde vor dem Abruf erhoeht; ein Aufrufer, der waehrend des laufenden Abrufs startete, las den schon erhoehten Stand, hielt den Fehlschlag danach fuer "kein Versuch seit meiner Ankunft" und startete einen zweiten Abruf (Test: assert 2 == 1)
- **Fix:** Zaehler bewegt sich erst nach Abschluss des Versuchs, Erfolg wie Fehlschlag (`KeySet._attempt`)
- **Files modified:** src/mcp_connector/oauth/jwks.py
- **Verification:** `test_twenty_concurrent_calls_whose_fetch_fails_are_all_refused_by_one_fetch` gruen (call_count == 1)
- **Committed in:** 7d64780 (GREEN-Commit)

---

**Total deviations:** 2 auto-fixed (1 AC-Wortlaut-Nachweis, 1 Bug im ersten Entwurf innerhalb des TDD-Zyklus)
**Impact on plan:** Keiner. Kein Scope-Zuwachs; die Schutzabsicht jedes AC ist nachweislich erfuellt.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 20 ist komplett (2/2 Plaene, alle fuenf Success Criteria erfuellt); Phase 21 (ExchangeVerifier) kann gegen `KeySet.key(kid, algorithm)`, `fetch_json` und die oeffentlichen Allowlists bauen, ohne eine zweite JWKS-Implementierung anzulegen
- Offen fuer Phase 22: `cooldown_seconds` an die Konfigurationsflaeche haengen (der Haken ist vorbereitet); offen fuer die Haertungsphase: Bearer-Laengengrenze und Throttle-Pfadklasse (ausdruecklich nicht Teil dieses Plans)

## Nachtrag 2026-09-19: Audit-Fixes

Der Code-Review zu Phase 20 (`20-REVIEW.md`, deep, 14 Befunde) ist abgearbeitet, bevor die
Phase geschlossen wird. Jeder Fix hat einen eigenen Commit mit Regressionstest, und jeder
Regressionstest war vor dem Fix rot (Gegenprobe ausgeführt, Ergebnis in der
Commit-Nachricht und in `20-REVIEW.md` je Befund vermerkt). Ausnahme sind reine
Kommentar- und Konstantenkorrekturen, die ohne eigenen Test bleiben.

| Befund | Kurz | Commit |
|--------|------|--------|
| CR-01 | Schlüsselschicht läuft auf `time.monotonic` statt auf der Wanduhr | `953969b` |
| CR-02 | Fehlschlagpause im Kalt- und Ablaufzweig (`JWKS_FAILURE_RETRY_SECONDS`) | `a839300` |
| WR-01 | `_usable_key` fängt `TypeError`/`ValueError`/`AttributeError`, Audit-Nachtrag richtiggestellt | `25d6c9e` |
| WR-02 | Leere 200 gilt als Fehlschlag, der Cache bleibt stehen | `23a69b8` |
| WR-03 | `_fetches` zählt nur noch in `_attempt`, Testzusicherung darauf | `ffc28dc` |
| WR-04 | Nonce-Vergleich in Bytes statt in `str` | `5237180` |
| WR-05 | Karenz und Fehlschlagpause vor dem Schloss entschieden | `f134d9a` |
| WR-06 | `metadata()` mit Single-Flight und Fehlschlagpause | `8cfec98` |
| IN-02, IN-03, IN-06 | `aclosing`-Kommentar, `fetched_at = -inf`, Weiterexporte gestrichen | `f1bba5e` |
| IN-04 | Kommentar sagt jetzt die wahre Obergrenze (zwei Abholungen) | `995105a` |

**Bewusst offen, Zuordnung Phase 22:** IN-01 (Portnormalisierung in `same_origin`, heute
fail-closed), IN-05 (ein HTTP-Client je `KeySet` statt je Abruf, braucht eine Lebenszeit
am Anwendungsrand) und das Verhalten hinter IN-04 (der Miss-Zweig könnte ein gerade
gesetztes `fetched_at` mitprüfen, das verkürzt aber das Fenster, in dem eine echte
Rotation bemerkt wird). Alle drei sind Architektur- oder Abwägungsfragen, keine Lücken.

**Vertragsänderungen dieser Runde, für Phase 21 relevant:** `KeySet` hat einen dritten
Zeitparameter `retry_seconds` (Standard `JWKS_FAILURE_RETRY_SECONDS`, 10 Sekunden);
`oauth/oidc.py` reicht `JWKS_CACHE_SECONDS` und `MAX_RESPONSE_BYTES` nicht mehr weiter,
beide kommen aus `oauth/jwks.py`; `OidcClient(clock=...)` ist jetzt ausdrücklich eine
monotone Uhr. Fail-closed ist an keiner Stelle gelockert worden: die neuen Bremsen
verbilligen ausschließlich Abweisungen, sie erzeugen nie eine Annahme.

**Gates je Commit, in einem Zug:** `uv run ruff check .`, `uv run ruff format --check .`,
`uv run pyright` (0 Fehler), `uv run vulture src scripts vulture_whitelist.py`,
`uv run pytest -q` (volle Suite, Exitcode 0).

---
*Phase: 20-jwks-schicht-und-pyjwt-stand*
*Completed: 2026-09-19*

## Self-Check: PASSED

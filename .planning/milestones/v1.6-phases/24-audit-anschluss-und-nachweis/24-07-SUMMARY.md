---
phase: 24-audit-anschluss-und-nachweis
plan: 07
subsystem: testing
tags: [oauth, token-exchange, jwks, throttle, respx, appapi, measurement]

# Dependency graph
requires:
  - phase: 22-token-exchange-kette
    provides: "CLASS_EXCHANGE, EXCHANGE_LIMIT und die Throttled-Huelle vor der MCP-Route (EXCH-05)"
  - phase: 23-exchange-konto-und-bindung
    provides: "die Identitaet gueltiger Exchange-Tokens, die aus einer gezaehlten Abweisung eine 200 macht"
provides:
  - "der gemessene 429-Lauf des Exchange-Pfads gegen build_exapp_app (IN-04)"
  - "die gemessene Grenze ausgehender JWKS-Abrufe je Fenster nach Phase 23 (IN-05)"
  - "die Zahl 36 je 300-Sekunden-Fenster mit Rechnung und Datum im Docstring von KeySet.forget"
  - "BL-21 geschlossen, BL-22 mit zwei gemessenen Beobachtungen angelegt"
affects: [exchange-haertung, drosselgrenzen, jwks-cache, audit-sichtbarkeit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gemessene Zahl mit Datum im Docstring am Wirkort (Muster audit/store.used_bytes)"
    - "Gegenfall als eigener Testfall: der Beweis, dass ein Test den gemessenen Pfad wirklich erreicht"
    - "Verschraenkte Hebel in einem Fenster messen statt Teilzahlen addieren"

key-files:
  created: []
  modified:
    - tests/unit/test_exapp_entry.py
    - tests/unit/test_oauth_jwks.py
    - src/mcp_connector/oauth/jwks.py
    - .planning/BACKLOG.md

key-decisions:
  - "Der Gegenfall ohne AppAPI-Header prueft den fehlenden WWW-Authenticate-Header statt des Zaehlers: gemessen zaehlt die Drosselung den Handshake-401 naemlich mit"
  - "Der Schluesselsatz-Route wird die kleinste legale Antwort untergeschoben, weil jede Messung call_count == 0 zusichert und ein eigener RSA-Schluessel nur Importkosten waere"
  - "Die Gesamtzahl 36 wird als gemessene Konstante festgehalten, die Summe 31 + 5 nur als zweite Lesart danebengestellt"
  - "Keine Haertung in diesem Plan: die zwei Beobachtungen gehen als BL-22 ins BACKLOG"

patterns-established:
  - "Messen statt herleiten: jede Zahl in diesem Plan kommt aus keys.call_count oder aus einem Statuscode, keine aus throttle.py"
  - "Docstring-Zahlen tragen Datum, Umfang und die Grenzen der Messung (ein Prozess, ein Issuer)"

requirements-completed: [AUDIT-07]

# Metrics
duration: 42min
completed: 2026-09-23
---

# Phase 24 Plan 07: BL-21 nachgemessen Summary

**Der 429-Pfad des Exchange-Zweigs ist gegen die gebaute ExApp-Anwendung gemessen, und die JWKS-Abrufgrenze nach Phase 23 steht mit 36 Abrufen je 300-Sekunden-Fenster, ihrer Rechnung und ihrem Datum im Docstring von `KeySet.forget`.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-09-23
- **Completed:** 2026-09-23
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- **IN-04 gemessen.** Der 429-Lauf des Exchange-Pfads laeuft jetzt gegen `entry_exapp.build_exapp_app`, also gegen den Pfad, den F13 tatsaechlich trifft, und nicht mehr nur gegen `build_oauth_app`. `EXCHANGE_LIMIT` Bearer-401, dann 429 mit positivem `Retry-After`, `keys.call_count == 0`, und der punktlose Alt-Pfad bekommt unveraendert seinen 401.
- **IN-05 gemessen.** Die Zahl ausgehender JWKS-Abrufe, die ein Gegenueber je Fenster bestellen kann, ist nach Phase 23 nachgemessen: **36 je 300 Sekunden**, in drei Faellen (Hebel a allein, Hebel b allein, beide abwechselnd im selben Fenster).
- **Die Wechselwirkung der beiden Hebel ist gemessen und nicht gerechnet.** Ein unbekanntes `kid` gegen einen *veralteten* Cache nimmt den Ablaufzweig und verbraucht die Abkuehlzeit gar nicht; nur das zweite erfundene `kid` eines Zyklus wird von ihr gebremst. Die Aufteilung je Zyklus wurde einzeln nachgezaehlt: 26 Zyklen kosten einen Abruf, 5 kosten zwei.
- **Die Zahl steht an ihrem Wirkort.** Dritter Absatz im Docstring von `KeySet.forget`, mit Rechnung, Messdatum, Umfang (ein Prozess, ein Issuer) und dem Satz, was Phase 23 an der alten Rechnung geaendert hat.
- **BL-21 ist geschlossen**, mit Verweis auf beide Messorte und Datum. **BL-22** ist neu und traegt die zwei Beobachtungen, die die Messungen erzeugt haben.

## Task Commits

1. **Task 1: IN-04, der 429-Lauf gegen die gebaute ExApp-Anwendung** - `3dc98a5` (test)
2. **Task 2: IN-05, die JWKS-Abrufgrenze nach Phase 23 nachmessen** - `89c4975` (test)
3. **Task 3: Die gemessene Zahl an ihren Wirkort und BL-21 schliessen** - `0a844d2` (docs)

## Files Created/Modified

- `tests/unit/test_exapp_entry.py` - drei neue Faelle (117 -> 120 Tests, kein Name ueberschrieben): der gemessene 429-Lauf gegen `build_exapp_app`, das Wortgate des 429-Koerpers, und der Gegenfall ohne AppAPI-Header
- `tests/unit/test_oauth_jwks.py` - vier neue Faelle: Hebel a allein, Hebel b allein, beide verschraenkt im selben Fenster, und die Messung, dass `CLASS_CONNECTIONS` einen erfolgreichen Widerruf nicht bremst
- `src/mcp_connector/oauth/jwks.py` - dritter Absatz im Docstring von `KeySet.forget` mit der gemessenen Zahl, ihrer Rechnung und dem Datum
- `.planning/BACKLOG.md` - BL-21 auf RESOLVED mit beiden Messorten; BL-22 neu angelegt

## Die gemessenen Zahlen

### IN-04, der Exchange-429 auf der ExApp

| Was | Gemessen |
|-----|----------|
| Abweisungen bis zur Grenze | 30 (`throttle.EXCHANGE_LIMIT`), alle 401 mit `WWW-Authenticate` |
| Antwort auf den Versuch danach | 429 mit `Retry-After` > 0 |
| Ausgehende Schluesselsatz-Abrufe | 0 |
| Punktloses Token nach der 429 | 401, unveraendert (die Ausnahme der MCP-Route haelt) |
| 429-Koerper | `temporarily_unavailable`, keines der Woerter exchange/signature/issuer/audience/claim/key |

### IN-05, ausgehende JWKS-Abrufe je Fenster von 300 Sekunden

| Hebel | Gemessen |
|-------|----------|
| a: Widerruf plus gueltiger Aufruf | 31 Zyklen kosten 31 Abrufe, einer je Zyklus, ungebremst |
| b: unbekanntes `kid` | 5 Abrufe je Fenster (300 s durch 60 s Abkuehlzeit); zehn weitere erfundene `kid` je Schritt kosten nichts |
| a und b abwechselnd im selben Fenster | **36** Abrufe, aufgeteilt in 26 Zyklen zu einem und 5 Zyklen zu zwei Abrufen |
| Erfolgreicher Widerruf gegen `CLASS_CONNECTIONS` | 31 Widerrufe, alle 200, Zaehler danach weiter offen: die Klasse bremst ihn nicht |

Die 36 sind gemessen und nicht als 31 + 5 gerechnet. Dass die Summe hier zufaellig stimmt, steht im Test als zweite Lesart daneben, mit dem Satz, dass bei Widerspruch der Zaehler die Wahrheit ist.

## Decisions Made

- **Der Gegenfall misst den fehlenden `WWW-Authenticate`-Header und nicht den Zaehler.** Der Plan erwartete, dass ein 401 aus dem AppAPI-Handshake den Exchange-Zaehler nicht erhoeht. Gemessen ist das Gegenteil (siehe Deviations). Der Beweis, dass der Haupttest hinter `require_appapi` misst, haengt deshalb an dem, was die beiden 401 wirklich unterscheidet: der Bearer-401 traegt die Discovery-Challenge, der Handshake-401 traegt nichts (T-02-03).
- **Die Schluesselsatz-Route antwortet mit dem kleinsten legalen Dokument.** Jede Messung sichert `call_count == 0` zu, ein eigener RSA-Schluessel in `test_exapp_entry.py` wuerde nichts beweisen und nur Importkosten erzeugen. Der Grund steht im Docstring des Helfers.
- **Die Wortliste des 429-Gates ist buchstabiert und nicht aus `errors` gelesen.** Plan 24-02 laeuft in derselben Welle und koennte sie zu einer gemeinsamen Konstante machen; ein Test, der das vorwegnimmt, misst ein Modul, das es noch nicht gibt.
- **`forget()` wird direkt gerufen, nicht ueber `ChainedVerifier.invalidate()`.** Die Verbindung Widerruf -> `forget_keys` ist in `test_oauth_exchange_chain.py` gemessen; sie ein zweites Mal aufzubauen haette die Schichtmessung mit einer Kette vermischt. Der Docstring sagt, wo die Verbindung gemessen ist.
- **Keine Haertung in diesem Plan.** Die Verifikation des Plans verlangt genau das: messen, und was auffaellt, ins BACKLOG. Beides steht in BL-22.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Die Verhaltenszeile 6 der Aufgabe 1 war faktisch falsch und wurde durch die gemessene Aussage ersetzt**

- **Found during:** Task 1 (IN-04, der 429-Lauf gegen die gebaute ExApp-Anwendung)
- **Issue:** Der Plan verlangte: "Ein Aufruf ohne die AppAPI-Header bekommt den Handshake-401 und **erhoeht den Exchange-Zaehler nicht**." Die `Throttled`-Huelle haengt aber aussen um `RequireAppApi` und entscheidet allein am `Authorization`-Header (`applies=chain.exchange_shaped_request`, `entry_exapp.py:218-226`). Eine Anfrage mit einem JWS-foermigen Bearer und ohne AppAPI-Header wird also sehr wohl in `CLASS_EXCHANGE` gezaehlt. Ein Test, der die Plan-Zeile zugesichert haette, waere rot gewesen oder haette eine falsche Eigenschaft festgeschrieben.
- **Fix:** Der Gegenfall misst beides ehrlich. Ein Aufruf mit Handshake plus `EXCHANGE_LIMIT - 1` Aufrufe ohne Handshake fuellen die Grenze **gemeinsam**, der Aufruf danach ist die 429. Das ist der Beweis, dass beide gezaehlt werden. Der eigentliche Zweck des Falls, naemlich zu zeigen, dass der Haupttest hinter `require_appapi` misst, wird vom `WWW-Authenticate`-Header getragen: der Bearer-401 hat ihn, der Handshake-401 nicht.
- **Files modified:** `tests/unit/test_exapp_entry.py`
- **Verification:** `uv run pytest tests/unit/test_exapp_entry.py -q` gruen; der Testdocstring benennt die Abweichung samt Grund ausdruecklich.
- **Committed in:** `3dc98a5`

**2. [Rule 2 - Nachweisbarkeit] BL-22 als neuer BACKLOG-Eintrag fuer die zwei Beobachtungen der Messungen**

- **Found during:** Task 2 und Task 3
- **Issue:** Die Messungen haben zwei Dinge ans Licht gebracht, die keine Haertung in dieser Phase ausloesen duerfen (Verifikationsregel des Plans), aber auch nicht verloren gehen sollen.
- **Fix:** BL-22 angelegt mit beiden Punkten, jeweils mit der gemessenen Zahl und der kleinsten denkbaren Bremse, falls die Bewertung sich je aendert. Siehe unten.
- **Files modified:** `.planning/BACKLOG.md`
- **Verification:** `grep -c "RESOLVED" .planning/BACKLOG.md` 0 -> 1, keine CRLF, keine Em-Dashes.
- **Committed in:** `0a844d2`

---

**Total deviations:** 2 auto-fixed (1x Rule 1, 1x Rule 2)
**Impact on plan:** Kein Scope-Zuwachs. Die erste Abweichung korrigiert eine Annahme des Plans gegen die Messung, was genau der Zweck dieses Plans ist. Die zweite folgt der Verifikationsregel des Plans woertlich.

## Neue BACKLOG-Eintraege

**BL-22 (OPEN), zwei Beobachtungen ohne Termin:**

1. **Der Widerrufs-Hebel auf `jwks.forget` hat seit Phase 23 gar keine Decke mehr aus der Drosselung.** Gemessen: 31 Zyklen, 31 Abrufe, keiner gebremst. Vorher deckelte `EXCHANGE_LIMIT` die Zyklen bei 30 je Quelle. Praktisch begrenzt heute nur noch, dass jeder Zyklus eine bewiesene Browser-Identitaet braucht; 36 Abrufe je Fenster sind keine Last, die ein Identitaetsanbieter spuert. Kleinste Bremse waere eine eigene Karenz auf `forget` selbst.
2. **Ein 401 aus dem AppAPI-Handshake zaehlt in `CLASS_EXCHANGE` mit.** Fuer sich richtig (vor-authentischer Laerm auf derselben Klasse), aber: wer den App-Secret nicht kennt, kann trotzdem den geteilten `PATH_CEILING` von 200 je Fenster fuellen. Hinter HaRP signiert der Proxy jede Anfrage, der Fall verlangt also direkten Zugriff auf den Container. Stelle fuer einen spaeteren Fix waere die `applies`-Bedingung.

## Issues Encountered

Keine. Die Messumgebung stand vollstaendig: alle Helfer (`bearer_call`, `appapi_headers`, `EXCHANGE_ENV`, `with_a_local_store`, `Clock`, `serve`) waren vorhanden, und die autouse-`respx`-Huelle in `test_exapp_entry.py` vertraegt einen zweiten, verschachtelten Router ohne Weiteres (`respx.Mocker.handler` probiert alle registrierten Router der Reihe nach).

## Qualitaetsgates

Alle lokal gruen vor jedem Commit:

- `uv run ruff check .` - All checks passed
- `uv run ruff format --check .` - 263 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` - 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py` - keine Befunde (kein neuer oeffentlicher Name, also keine Ergaenzung in `vulture_whitelist.py`)
- `uv run pytest -q` - vollstaendig gruen

Zusatzpruefungen der Abnahmekriterien:

- `grep -c "2026-09" src/mcp_connector/oauth/jwks.py` = 1
- `grep -c "RESOLVED" .planning/BACKLOG.md` 0 -> 1, BL-21 traegt kein `**Status:** OPEN` mehr
- `.planning/BACKLOG.md`: 0 CRLF, 0 Em-Dashes (U+2014), 0 En-Dashes (U+2013)
- `src/mcp_connector/oauth/jwks.py`: laengste Zeile 94 Zeichen, Grenze 100
- Testzahl in `tests/unit/test_exapp_entry.py`: 117 -> 120, keine doppelten Funktionsnamen

## User Setup Required

Keine. Diese Phase installiert kein Paket und aendert keine Deployment-Variable.

## Next Phase Readiness

- AUDIT-07 hat, was es braucht: der 429-Lauf gegen die gebaute ExApp existiert und ist gemessen, die Betreiber-Sichtbarkeit abgewiesener Versuche kann darauf aufsetzen.
- Die Zahl in `KeySet.forget` ist jetzt die, die nach Phase 23 gilt. Wer sie wieder anfasst, sollte sie nachmessen und nicht fortschreiben; der Docstring sagt, unter welchen Bedingungen sie gemessen wurde.
- Offen und bewusst nicht gehaertet: BL-22.

## Threat Flags

Keine neue Angriffsflaeche. Dieser Plan legt keine Route an, oeffnet keinen Pfad und aendert kein Schema; er misst bestehende Pfade und schreibt eine Zahl in einen Docstring.

## Self-Check: PASSED

Dateien geprueft (alle vorhanden): `tests/unit/test_exapp_entry.py`, `tests/unit/test_oauth_jwks.py`, `src/mcp_connector/oauth/jwks.py`, `.planning/BACKLOG.md`, `.planning/phases/24-audit-anschluss-und-nachweis/24-07-SUMMARY.md`.

Commits geprueft (alle vorhanden): `3dc98a5`, `89c4975`, `0a844d2`.

`.planning/STATE.md` und `.planning/ROADMAP.md` wurden nicht angefasst: der Orchestrator schreibt sie, nachdem alle Worktree-Agenten der Welle fertig sind.

---
*Phase: 24-audit-anschluss-und-nachweis*
*Completed: 2026-09-23*

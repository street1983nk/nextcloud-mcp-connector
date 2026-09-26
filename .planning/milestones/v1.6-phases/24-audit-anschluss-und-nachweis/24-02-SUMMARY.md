---
phase: 24-audit-anschluss-und-nachweis
plan: 02
subsystem: auth
tags: [oauth, token-exchange, keycloak, jwt, audit, ast-gate, pyjwt]

# Dependency graph
requires:
  - phase: 21-token-exchange-pruefer
    provides: "ExchangeTokenChecker, ExchangeRefused und die 19 _refused-Aufrufstellen"
  - phase: 22-token-exchange-kette
    provides: "ChainedVerifier, die Bremse des Exchange-Pfads und die armierte Anwendung"
  - phase: 18-fehlerformat
    provides: "errors.REASONS und das AST-Gate in tests/unit/test_errors_reason.py"
provides:
  - "sechs gruppierte Ablehnungsbezeichner mit dem Praefix exchange_ in der eingefrorenen Menge errors.REASONS"
  - "ExchangeRefused traegt ein Attribut reason, Vorgabe REASON_EXCHANGE_FAILED"
  - "_refused(reason, identifier=REASON_EXCHANGE_KEY): jede der 19 Aufrufstellen vergibt ihren Bezeichner ausdruecklich"
  - "ein AST-Gate, das eine vergessene oder erfundene Gruppe an einer Aufrufstelle meldet"
  - "ein Antwort-Gate: vier verschieden scheiternde Tokens bekommen dieselbe 401-Antwort"
affects: [24-04-audit-zeile-fuer-abgewiesene-versuche, 24-05, exchange_dryrun]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gruppierte Ablehnungsbezeichner statt eines Bezeichners je fester Phrase"
    - "Quelltext-Gate ueber die Aufrufstellen einer Fabrikfunktion (ast.Call, zwei Argumente)"
    - "Antwort-Gleichheit ueber mehrere Ablehnungsgruende statt einer Wortliste"

key-files:
  created: []
  modified:
    - src/mcp_connector/errors.py
    - src/mcp_connector/oauth/exchange.py
    - tests/unit/test_errors_reason.py
    - tests/unit/test_oauth_exchange.py
    - tests/unit/test_oauth_exchange_chain.py

key-decisions:
  - "Die Gruppe steht an der Ausnahme, die achtzehn festen Phrasen bleiben in der DEBUG-Zeile: zwei Leser, zwei Aufloesungen"
  - "Der Vorgabewert von _refused ist REASON_EXCHANGE_KEY, weil nur jwks.py die Fabrik mit einem Argument erreicht"
  - "Die Decoder-Stelle waehlt zwischen exchange_key und exchange_claims, statt eine zwanzigste Aufrufstelle zu oeffnen"
  - "ExchangeRefused wird positional gebaut, nicht mit reason=: ein Parametername an reason= waere vom AST-Gate der errors als Befund gemeldet worden"

patterns-established:
  - "Der Bezeichner verlaesst den Prozess an genau einer Stelle, und das ist die Audit-Zeile aus 24-04"
  - "Argumentausdruecke eines Gates werden auf zwei erlaubte Formen eingeschraenkt (Name, Auswahl zwischen zwei Namen), alles andere ist ein Befund"

requirements-completed: [AUDIT-07]

# Metrics
duration: 25min
completed: 2026-09-23
---

# Phase 24 Plan 02: Der Ablehnungsbezeichner an der Exchange-Ausnahme

**`ExchangeRefused` traegt jetzt eine von sechs eingefrorenen Gruppen, jede der 19 Aufrufstellen vergibt sie ausdruecklich, und zwei Gates halten sie aus der HTTP-Antwort heraus.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-23T22:21:00Z
- **Completed:** 2026-09-23T22:46:00Z
- **Tasks:** 3 von 3
- **Files modified:** 5

## Accomplishments

- `errors.REASONS` hat zwoelf Eintraege: die sechs Ausgaenge eines Werkzeugaufrufs und sechs Gruppen des Exchange-Pruefers, alle mit dem Praefix `exchange_`. Ein Leser einer Audit-Zeile sieht ohne Nachschlagen, aus welchem Pfad sie stammt.
- `ExchangeRefused` traegt `reason` (Vorgabe `REASON_EXCHANGE_FAILED`), bleibt aber von aussen dasselbe Objekt: kein Argument, leerer `str()`, leeres `args`. Der bestehende Orakel-Beweis ueber den negativen Korpus laeuft unveraendert gruen.
- Alle 19 `_refused`-Aufrufstellen vergeben ihre Gruppe ausdruecklich; ein AST-Gate meldet Datei und Zeile jeder Stelle mit weniger als zwei Argumenten und jeder Stelle, deren zweites Argument kein Name aus `errors` ist.
- Vier verschieden scheiternde Tokens (unlesbarer Header, fremder `iss`, unbekannter `kid`, falsche Audience) bekommen gemessen dieselbe Antwort: gleicher Statuscode, gleicher `WWW-Authenticate`-Header, gleicher Koerper.
- Die DEBUG-Zeile ist unveraendert geblieben und ein Testfall haelt sie so: sie traegt die feste Phrase und nie den Bezeichner.

## Task Commits

1. **Task 1: Sechs gruppierte Ablehnungsbezeichner in der eingefrorenen Menge** - `a24a64c` (test, RED), `f53d429` (feat, GREEN)
2. **Task 2: Der Bezeichner an der Ausnahme, mit jeder Aufrufstelle explizit** - `5ee9319` (test, RED), `d70b75f` (feat, GREEN)
3. **Task 3: Das Antwort-Gate gegen das Orakel** - `3d578cb` (test)

_Task 3 ist reine Testarbeit: das Verhalten, das sie misst, war bereits da und ist genau das, was der Plan festnageln wollte. Ein GREEN-Schritt haette nichts zu implementieren gehabt._

## Files Created/Modified

- `src/mcp_connector/errors.py` - sechs neue Bezeichner, in `REASONS` aufgenommen; ein Kommentarabsatz nennt beide Gruppen und begruendet die Gruppierung; der Moduldocstring engt "hinaus" fuer die Exchange-Bezeichner auf die Audit-Zeile ein
- `src/mcp_connector/oauth/exchange.py` - `ExchangeRefused.__init__` mit `reason`, `_refused` mit zweitem Argument und Vorgabewert, 19 Aufrufstellen mit ihrer Gruppe, beide Docstrings neu geschrieben
- `tests/unit/test_errors_reason.py` - `ExchangeRefused` in `_ERROR_CLASSES_WITHOUT_THE_SUFFIX`, die Befundlogik in `_findings_in` herausgezogen, ein Gegenprobefall ueber dieselbe Funktion, zwoelf statt sechs Bezeichner
- `tests/unit/test_oauth_exchange.py` - AST-Gate ueber die Aufrufstellen, vier gemessene Gruppenfaelle, zwei Faelle fuer den Ein-Argument-Weg, ein Fall fuer die unveraenderte DEBUG-Zeile
- `tests/unit/test_oauth_exchange_chain.py` - das Wortgate liest die sechs Bezeichner aus `errors`, deckt jetzt auch den `WWW-Authenticate`-Header ab, und der neue Gleichheitsfall ueber vier Ablehnungsgruende

## Decisions Made

**1. Die Decoder-Stelle waehlt zwischen zwei Gruppen, statt eine zwanzigste Aufrufstelle zu oeffnen.**
Der Plan ordnet "Signatur haelt nicht" der Gruppe `exchange_key` zu und "Standard-Claims" der Gruppe `exchange_claims`. Beide fallen im Quelltext an derselben Stelle an: `_PreparsedJWT(...).decode(...)` prueft Signatur und Standard-Claims in einem Aufruf, und der `except`-Zweig kannte bisher nur eine Phrase. Statt den Zweig zu spalten (das haette 20 Aufrufstellen ergeben und das Akzeptanzkriterium "19" gebrochen) liest die Stelle die Gruppe an der Ausnahme ab: `jwt.InvalidSignatureError` ist `exchange_key`, alles andere `exchange_claims`. Die feste Phrase und die Reihenfolge der Pruefungen bleiben unberuehrt.

**2. `ExchangeRefused` wird positional gebaut.**
`_refused` gibt `ExchangeRefused(identifier)` zurueck und nicht `ExchangeRefused(reason=identifier)`. Der Grund ist das Gate aus `test_errors_reason.py` selbst: es verlangt an `reason=` einen Namen, der mit `REASON_` beginnt, und `identifier` ist ein Parametername. Die Schluesselwortform haette das Gate rot gemacht, ohne dass etwas falsch gewesen waere. Der Eintrag von `ExchangeRefused` in `_ERROR_CLASSES_WITHOUT_THE_SUFFIX` behaelt trotzdem seinen Wert: er faengt jedes kuenftige `ExchangeRefused(reason="freier Text")` an jeder anderen Stelle unter `src/`.

**3. Das Gruppen-Gate liest den Argumentausdruck, nicht nur einen nackten Namen.**
Erlaubt sind genau zwei Formen: ein Name, und eine Auswahl zwischen zwei Namen (`ast.IfExp`, Bedingung bewusst ungelesen). Jede andere Form, ein Literal, eine lokale Variable, ein Funktionsaufruf, ist ein Befund mit Zeilennummer. Eine lokale Zwischenvariable waere sonst die bequeme Umgehung gewesen.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Die Verifikationszahl fuer die `jwks`-Signatur stimmte nicht**
- **Found during:** Task 2
- **Issue:** Der Plan verlangt unter `<verification>`, dass `grep -c "refuse: Callable\[\[str\], Exception\]" src/mcp_connector/oauth/jwks.py` weiterhin **1** ergibt. Gemessen am unveraenderten Stand sind es **2**: `KeySet.__init__` (Zeile 125) und `fetch_json` (Zeile 277) nehmen die Fabrik beide als `Callable[[str], Exception]` entgegen. Die Zahl im Plan war schon vor dieser Aenderung falsch.
- **Fix:** Der Testfall `test_the_key_set_layer_still_takes_a_one_argument_factory` sichert **2** zu und sein Docstring nennt beide Stellen mit ihrem Grund: der gehaertete Rundlauf weist selbst ab (fremder Ursprung, unerreichbarer Anbieter, zu grosse Antwort). Die eigentliche Aussage der Verifikation, die Signatur ist nicht gebrochen, bleibt damit gemessen, nur mit der richtigen Zahl.
- **Files modified:** `tests/unit/test_oauth_exchange.py`
- **Verification:** `uv run pytest tests/unit/test_oauth_jwks.py -q` laeuft unveraendert gruen (115 Faelle), `jwks.py` wurde nicht angefasst.
- **Committed in:** `d70b75f`

**2. [Rule 2 - Missing critical functionality] Der Bezeichner als positionales Argument war vom bestehenden Gate nicht gedeckt**
- **Found during:** Task 2
- **Issue:** Das AST-Gate aus `test_errors_reason.py` sieht nur `reason=` an einer Fehlerkonstruktion. Der Bezeichner reist hier als zweites positionales Argument einer Fabrikfunktion, also genau dort, wo dieses Gate blind ist: ein erfundener Zeichenkettenwert an einer der 19 Stellen waere durchgelaufen.
- **Fix:** `test_every_group_handed_to_a_refusal_is_one_of_the_frozen_six` haelt jeden Argumentausdruck gegen die sechs Namen (T-24-15 auf dem Weg, den der Plan nur fuer T-24-16 vorgesehen hatte).
- **Files modified:** `tests/unit/test_oauth_exchange.py`
- **Verification:** Der Fall meldet Datei und Zeile; gegengeprueft an der Auswahlform der Decoder-Stelle, die er passieren laesst, und an den uebrigen 18, die nackte Namen sind.
- **Committed in:** `d70b75f`

**3. [Rule 2 - Missing critical functionality] Das Wortgate deckte den `WWW-Authenticate`-Header nicht ab**
- **Found during:** Task 3
- **Issue:** Gemessen ist der Koerper des 401 **leer**; die gesamte Antwort steht im `WWW-Authenticate`-Header (`invalid_token`, `Authentication required`, Scope, Resource-Metadata-URL). Ein Wortgate, das nur `response.text` liest, haette bei diesem Pfad nichts gelesen.
- **Fix:** Beide Antwort-Gates pruefen jetzt `Header + Koerper`; der Docstring des neuen Falls haelt die Messung fest, damit der naechste Leser das Gate nicht fuer staerker haelt, als es ist.
- **Files modified:** `tests/unit/test_oauth_exchange_chain.py`
- **Verification:** Der Header wurde einmal ausgelesen und ist fuer alle vier Ablehnungsgruende Zeichen fuer Zeichen derselbe.
- **Committed in:** `3d578cb`

---

**Total deviations:** 3 auto-fixed (1x Rule 1, 2x Rule 2)
**Impact on plan:** Keine Scope-Ausweitung. Die Rule-1-Korrektur betrifft eine Zahl in der Verifikation, nicht den Bau; die beiden Rule-2-Ergaenzungen schliessen Luecken in genau den Gates, die der Plan selbst verlangt.

## Issues Encountered

- **Die Reihenfolge Gegenprobe/Gate.** Die geforderte Gegenprobe "das Gate meldet einen freien Text" haette gegen eine handgeschriebene zweite Kopie der Regel nichts bewiesen. Die Befundlogik wurde deshalb nach `_findings_in` herausgezogen; Gehweg und Gegenprobe laufen jetzt durch dieselbe Funktion.
- **Zeilenlaenge.** Zwei Aufrufstellen wuchsen mit ihrem zweiten Argument ueber 100 Zeichen und wurden umgebrochen. `ruff format` laesst sie so stehen.

## Known Stubs

Keine. Alles, was dieser Plan anlegt, ist im selben Commit verdrahtet und gemessen.

## Threat Flags

Keine neue Sicherheitsflaeche: kein neuer Endpunkt, kein neuer Auth-Pfad, kein Schema. Die einzige neue Flaeche ist das Attribut `reason` an einer Ausnahme, und es ist genau die Flaeche, die der `<threat_model>`-Eintrag T-24-03 mit den beiden Antwort-Gates abdeckt.

## Verification

- `uv run pytest -q`: **4175 passed, 33 skipped, 168 deselected** in 139 s.
- `uv run ruff check .`: All checks passed.
- `uv run ruff format --check .`: 263 files already formatted.
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations.
- `uv run vulture src scripts vulture_whitelist.py`: keine Ausgabe (`vulture_whitelist.py` brauchte keine Ergaenzung, weil die neuen Namen ueber `REASONS` gelesen werden).
- `uv run pytest tests/contract -q`: gruen.

Erfolgskriterien des Plans, einzeln gemessen:

| Kriterium | Messung | Ergebnis |
|-----------|---------|----------|
| `REASONS` hat zwoelf Eintraege | `python -c "from mcp_connector.errors import REASONS; print(len(REASONS))"` | 12 |
| sechs Definitionen plus sechs Eintraege | `grep -v '^\s*#' errors.py \| grep -c 'REASON_EXCHANGE_'` | 12 |
| die alte Ueberschrift ist weg | `grep -c "The six rejection reasons" errors.py` | 0 |
| 19 Aufrufstellen, keine ohne Gruppe | AST-Zaehlung aus dem Plan | `19 0` |
| der alte Docstring-Satz ist weg | `grep -c "Carries no detail" exchange.py` | 0 |
| die DEBUG-Zeile ist unveraendert | `grep -vn '^\s*#' exchange.py \| grep -c 'logger.debug("exchange refused: %s", reason)'` | 1 |
| vier Tokens, eine Antwort | `test_four_differently_failing_tokens_get_one_and_the_same_401` | gruen |
| `ExchangeRefused` im Gegenprobe-Gate | `grep -c "ExchangeRefused" tests/unit/test_errors_reason.py` | 4 |

## TDD Gate Compliance

Die Kette haelt fuer die beiden Tasks, die Quelltext anfassen:

- Task 1: RED `a24a64c` (`test(...)`, Import-Fehler auf die sechs neuen Namen) vor GREEN `f53d429` (`feat(...)`).
- Task 2: RED `5ee9319` (`test(...)`, acht fallende Faelle) vor GREEN `d70b75f` (`feat(...)`).
- Task 3 ist test-only und hat folgerichtig keinen `feat`-Commit: das gemessene Verhalten existierte, der Plan wollte es festnageln.
- REFACTOR-Schritte waren an keiner Stelle noetig.

## Next Phase Readiness

Plan 24-04 kann den Bezeichner abholen: `except ExchangeRefused as refused: ... refused.reason` in `oauth/chain.py:524` ist die Stelle, an der die Kette die Abweisung bereits faengt, und sie ist die einzige Stelle, die weiss, ob eine Abweisung eine Zeile wert ist. Zwei Punkte fuer diesen Plan:

- Die Gruppe ist der **einzige** Wert, der aus einer ungeprueften Abweisung stammen darf. Ein `azp` aus einem Token, dessen Signatur nicht hielt, gehoert in keine Zeile (Pitfall 4 der Recherche).
- `REASON_EXCHANGE_ACCOUNT` ist vergeben, aber noch von keiner Stelle benutzt. Sein Ort ist `resolve_identity` in `oauth/chain.py`, wo eine Kontoquelle nein sagt und die Methode heute schlicht `None` antwortet.

Zwei Gates warten auf jede kuenftige Aenderung des Pruefers: eine neue `_refused`-Stelle ohne Gruppe faellt, und ein Fehlertext, der einen der sechs Bezeichner in die Antwort traegt, faellt ebenfalls.

## Self-Check: PASSED

Alle fuenf Commits (`a24a64c`, `f53d429`, `5ee9319`, `d70b75f`, `3d578cb`) stehen in `git log`, und alle fuenf geaenderten Quelldateien plus diese Zusammenfassung liegen auf der Platte. `STATE.md` und `ROADMAP.md` wurden nicht angefasst: dieser Lauf ist ein Worktree-Agent, die Schreibrechte an beiden liegen beim Orchestrator.

---
*Phase: 24-audit-anschluss-und-nachweis*
*Completed: 2026-09-23*

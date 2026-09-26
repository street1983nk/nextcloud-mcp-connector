---
phase: 22-konfiguration-kette-und-drosselung
plan: 03
subsystem: auth
tags: [throttle, token-exchange, pre-authentication, denial-of-service, path-class]

requires:
  - phase: 22-konfiguration-kette-und-drosselung (22-01)
    provides: "ExchangeConfig, load_exchange_config, Startabweisung in beiden Einstiegspunkten"
  - phase: 22-konfiguration-kette-und-drosselung (22-02)
    provides: "ChainedVerifier, build_chain, looks_like_jws als die eine Formregel"
provides:
  - "oauth/throttle.py: CLASS_EXCHANGE, EXCHANGE_LIMIT und der applies-Parameter an Throttled"
  - "oauth/chain.py: exchange_shaped_request, dieselbe Formregel gelesen aus dem Authorization-Header"
  - "entry_exapp/entry_oauth: die MCP-Route hängt bei bewaffnetem Pfad in Throttled, aussen um die Transportgrenze; ohne bewaffneten Pfad hängt dort gar nichts"
affects: [23-konto-mapping, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Der Wrapper bekommt die Bedingung hereingereicht (applies), statt die Formregel selbst zu kennen: throttle.py nennt den Exchange-Pfad nirgends, und ein grep hält das fest"
    - "Aus-Zustand als Struktur und nicht als Verhalten: ohne bewaffneten Pfad wird gar nichts gewickelt, statt einen Wrapper zu hängen, der alles durchlässt"
    - "Der Drossel-Wrapper sitzt aussen um die Transportgrenze, weil die gezählte Ablehnung der 401 dieser Grenze ist"
    - "Ein Docstring, der eine Sicherheitsentscheidung begründet, zieht in derselben Änderung mit, in der die Entscheidung eine Bedingung bekommt"

key-files:
  created: []
  modified:
    - src/mcp_connector/oauth/throttle.py
    - src/mcp_connector/oauth/chain.py
    - src/mcp_connector/entry_exapp.py
    - src/mcp_connector/entry_oauth.py
    - tests/unit/test_oauth_abuse.py
    - tests/unit/test_oauth_exchange_chain.py
    - tests/unit/test_exapp_entry.py
    - tests/unit/test_entry_oauth.py
    - CHANGELOG.md

key-decisions:
  - "EXCHANGE_LIMIT = 30, zwischen FAILURE_LIMIT (10) und PATH_CEILING (200): eine Ablehnung dieses Pfades kostet eine Signaturprüfung und im ungünstigen Fall einen ausgehenden Abruf, ist also teurer als ein abgelehnter Token-Grant; die Decke der Klasse bleibt PATH_CEILING und wird nicht gesondert gesetzt"
  - "Die Bedingung steht in chain.py und nicht in throttle.py: die Formregel darf es nur einmal geben, sonst driften Weiche und Drossel auseinander; ein Test hält exchange_shaped_request gegen looks_like_jws"
  - "Im Aus-Zustand hängt kein Wrapper an der Route, nicht einer, der alles durchlässt: ein solcher Wrapper wäre heute nicht unterscheidbar und morgen ein anderer Codepfad"
  - "boundary_of in beiden Einstiegspunkt-Testdateien läuft jetzt unter dem Drossel-Wrapper hindurch, statt ihn als Verletzung zu werten: die Grenze ist weiterhin genau eine, sie sitzt nur eine Schicht tiefer"

requirements-completed: [EXCH-05]

duration: 21min
completed: 2026-09-19
---

# Phase 22 Plan 03: Drosselung des Exchange-Pfades Summary

**Wiederholte Ablehnungen JWS-förmiger Bearer auf der MCP-Route sind vor-authentisch begrenzt: eine eigene Pfadklasse mit eigenem Limit antwortet nach dreissig Ablehnungen mit 429 und Retry-After, die bewusste Ausnahme dieser Route gilt für die eigenen Tokens dieses Servers unverändert weiter, und der Docstring, der diese Ausnahme begründet, sagt in derselben Änderung die Wahrheit über beide Hälften**

## Performance

- **Duration:** 21 min
- **Started:** 2026-09-19T09:33Z
- **Completed:** 2026-09-19T09:54Z
- **Tasks:** 2 (je RED und GREEN einzeln committet)
- **Files modified:** 9 (0 neu, 9 geändert), 404 Zeilen hinzu

## Accomplishments

- **Die Grenze greift, und sie ist an der gebauten Anwendung gemessen.** Ein `TestClient` gegen die Standalone-App schickt `EXCHANGE_LIMIT` Anfragen mit `Authorization: Bearer a.b.c`, bekommt dreissigmal 401 und beim einunddreissigsten Mal 429 mit einem `Retry-After` grösser als 0. Der Wert scheitert schon am unlesbaren JWS-Header, und die respx-Route des Schlüsselsatzes steht am Ende bei `call_count == 0`: die Zählung ist belegt, ohne dass ein einziger ausgehender Abruf stattgefunden hat.
- **Die bewusste Ausnahme der Route gilt für den bestehenden Pfad unverändert.** Im selben erschöpften Zustand bekommt ein punktloser Bearer weiterhin 401 und nie 429, und eine Anfrage ohne `Authorization`-Header wird beantwortet wie heute. Dieselbe Zusage steht in der Abweichungsmatrix noch einmal auf der Ebene des Wrappers: die Klasse wird von der Seite gefüllt, bis `retry_after` positiv antwortet, und die Anfragen, die die Bedingung durchwinkt, werden trotzdem bedient.
- **Durchgewunken heisst wirklich durchgewunken.** Sagt `applies` `False`, reicht `__call__` die Anfrage weiter, bevor ein Zähler gelesen oder geschrieben wird: kein `record_attempt`, kein `forgive`, kein 429. Ein Test misst das an `box._counters == {}` nach fünf abgelehnten und einer erfolgreichen Anfrage.
- **Die Formregel gibt es weiterhin genau einmal.** `chain.exchange_shaped_request` liest den `Authorization`-Header genau so wie `RequireAppApi._bearer_is_valid` (Präfixvergleich ohne Gross-Klein, `strip()` auf dem Rest) und gibt `looks_like_jws(token)` zurück. Ein Test hält beide über sechs Tokenformen gegeneinander, statt die erwarteten Antworten zweitzuschreiben. `throttle.py` kennt den Exchange-Pfad nicht: `grep -v '^\s*#' src/mcp_connector/oauth/throttle.py | grep -c "chain\|exchange_shaped_request\|looks_like_jws"` ergibt 0.
- **Der Docstring zog in derselben Änderung mit (T-22-16).** Der Absatz "What is throttled and what is not" behauptete ohne Einschränkung, die MCP-Route sei bewusst ausgenommen, weil ein Werkzeugaufruf mit geprüftem Bearer ankomme. Er ist jetzt zweigeteilt: die Ausnahme gilt wörtlich weiter für die eigenen Tokens (D-37), sie gilt nicht für einen JWS-förmigen Bearer, hinter dem Signaturprüfung und möglicher Schlüsselsatz-Abruf vor jeder Authentisierung stehen, diese Anfragen zählen in `CLASS_EXCHANGE` gegen `EXCHANGE_LIMIT`, die Entscheidung zwischen beiden gehört nicht in dieses Modul, und ohne bewaffneten Pfad hängt an der Route gar kein Wrapper. Der Absatz nennt EXCH-05.
- **Der Aus-Zustand ist Struktur, nicht Verhalten.** `test_without_an_armed_exchange_path_nothing_is_wrapped_around_the_boundary` misst, dass an `/mcp` unmittelbar die `RequireAppApi` hängt, und `test_the_armed_path_hangs_the_throttle_outside_the_transport_boundary` misst die Reihenfolge im bewaffneten Fall: `Throttled` aussen, Grenze innen. Aussen ist die Messung selbst, denn die gezählte Ablehnung ist der 401, den die Grenze schreibt; innen sähe der Wrapper nur Antworten des MCP-Transports.
- **Die Decke der Klasse bleibt geteiltes Schicksal.** `PATH_CEILING` gilt unverändert und wird für diese Klasse nicht angehoben (T-22-13): wer sie füllt, schliesst den Exchange-Pfad für alle, und das ist auf einem Pfad, den ein Fremder ohne Schlüssel erreicht, der richtige Handel, weil der bestehende Pfad gar nicht in dieser Klasse liegt.
- **Der 429-Körper verrät nichts (T-22-15).** `temporarily_unavailable` plus die Sekundenzahl, und ein Test prüft, dass die Wörter `exchange`, `signature`, `issuer`, `audience`, `claim` und `key` im ganzen Antworttext nicht vorkommen.
- 16 neue Testfunktionen (23 Fälle): 5 in `test_oauth_abuse.py`, 4 in `test_oauth_exchange_chain.py` (davon eine mit 8 Parametrisierungen), 2 in `test_exapp_entry.py`, dazu die angepassten Helfer. Volle Suite: 3852 passed, 33 skipped.

## Task Commits

Jeder Task ist als RED und GREEN getrennt committet:

1. **Task 1: Pfadklasse, Bedingung und die Wahrheit im Docstring** - RED `ccbde94` (14 fallende Tests: `TypeError: Throttled.__init__() got an unexpected keyword argument 'applies'` und `AttributeError` auf `CLASS_EXCHANGE` beziehungsweise `exchange_shaped_request`), GREEN `0994e98`
2. **Task 2: Der Wrapper an der MCP-Route, gemessen** - RED `8bd2a96` (3 fallende Tests: zweimal `assert 401 == 429`, einmal die Struktur im bewaffneten Fall), GREEN `55a4f6f`

## Files Created/Modified

- `src/mcp_connector/oauth/throttle.py` - der Absatz über die MCP-Ausnahme umgeschrieben und um seine zweite Hälfte ergänzt (EXCH-05), `CLASS_EXCHANGE` und `EXCHANGE_LIMIT = 30` samt Begründung als `#:`-Kommentare, beide in `__all__`, `applies` an `Throttled.__init__` und der Kurzschluss ganz am Anfang von `__call__`, vierter Absatz im Klassendocstring
- `src/mcp_connector/oauth/chain.py` - `_BEARER_PREFIX` und `exchange_shaped_request`, beide unmittelbar hinter `looks_like_jws`, plus der Eintrag in `__all__`
- `src/mcp_connector/entry_exapp.py` - der Drossel-Wrapper in der bestehenden Routenschleife, hinter `RequireAppApi` und nur bei `exchange_config is not None`, mit den zwei Kommentarsätzen zur Reihenfolge und zum Aus-Zustand
- `src/mcp_connector/entry_oauth.py` - dieselbe Stelle in `build_oauth_app`
- `tests/unit/test_oauth_abuse.py` - Abschnitt "the throttle wrapper with a condition on it", der elfte Fall der Matrix: `conditional`-Aufbau plus 5 Tests
- `tests/unit/test_oauth_exchange_chain.py` - 8 Formfälle plus die Gleichheit mit `looks_like_jws`, dazu die beiden Messungen an der gebauten Anwendung
- `tests/unit/test_exapp_entry.py` - `mcp_wrapper` als neuer Helfer, `boundary_of` läuft unter dem Drossel-Wrapper hindurch, 2 Strukturtests
- `tests/unit/test_entry_oauth.py` - dasselbe Durchlaufen in `boundary_of`
- `CHANGELOG.md` - ein Absatz im `[Unreleased]`-Block: die vor-authentische Grenze, der `Retry-After`, die unverändert geltende Ausnahme für die eigenen Tokens und der Aus-Zustand

## Decisions Made

- **`EXCHANGE_LIMIT = 30`, und die Decke bleibt `PATH_CEILING`.** Das eigene Limit, weil eine Ablehnung dieses Pfades teurer ist als ein abgelehnter Token-Grant (Signaturprüfung, bei unbekanntem `kid` ein ausgehender Abruf). Dreissig liegt weit über dem, was ein Client mit abgelaufenem Token in fünf Minuten ehrlich produziert, und weit unter einer Last, die eine Instanz spürt. Die Decke wird bewusst nicht angehoben: dass sie geteiltes Schicksal ist, steht als ausdrücklicher Satz im Kommentar, und sie kostet den bestehenden Pfad nichts, weil er gar nicht in dieser Klasse liegt.
- **Die Bedingung wird hereingereicht, nicht gewusst.** `throttle.py` bekommt ein `Callable[[Request], bool]` und fragt es; was "sieht aus wie ein fremdes Token" heisst, steht in `chain.py`. Eine zweite Schreibweise neben dem Zähler wäre beim ersten Korrekturschritt an einer der beiden Stellen auseinandergelaufen, und eine Drossel, die eine andere Menge zählt als die, die sie begrenzen soll, ist schlechter als keine.
- **Aussen um die Transportgrenze.** Der Wrapper muss den 401 sehen, den `RequireAppApi` beziehungsweise `RequireOAuthBearer` schreibt. Innen sähe er nur Antworten des MCP-Transports und zählte nie eine Ablehnung. Der Kommentar an beiden Stellen sagt genau das, weil die Reihenfolge hier die Messung ist.
- **Kein Wrapper im Aus-Zustand.** Ein `Throttled`, dessen `applies` immer `False` sagt, wäre heute nicht unterscheidbar und morgen ein anderer Codepfad. Also wird nichts gewickelt, und der Strukturtest sagt `isinstance(..., RequireAppApi)` über das äusserste Objekt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `boundary_of` in beiden Einstiegspunkt-Testdateien**
- **Found during:** Task 2 (GREEN)
- **Issue:** Beide Dateien haben einen Helfer, der das Objekt an `/mcp` direkt als Transportgrenze typisiert (`assert isinstance(guard, RequireAppApi)` beziehungsweise `RequireOAuthBearer`). Mit dem Drossel-Wrapper aussen fielen im bewaffneten Fall drei bestehende Tests aus 22-02.
- **Fix:** Der Helfer läuft jetzt in einer Schleife durch `Throttled`-Schichten hindurch und behält die Zusage, dass es genau eine Route und genau eine Grenze gibt. Die Zusagen der 22-02-Tests (Kette an der Grenze, Widerruf an der Kette, `is` im Aus-Zustand) sind unverändert und nicht gelockert; nur der Weg zu dem Objekt, über das sie reden, ist eine Schicht länger. In `test_exapp_entry.py` steht der neue Helfer `mcp_wrapper` daneben, der bewusst nichts auspackt, und auf ihm hängen die beiden Strukturtests dieses Plans.
- **Files modified:** `tests/unit/test_exapp_entry.py`, `tests/unit/test_entry_oauth.py` (letztere nicht in der Dateiliste des Plans)
- **Verification:** Die drei betroffenen 22-02-Tests sind wieder grün, ohne dass eine ihrer Zusicherungen geändert wurde

**2. [Rule 3 - Blocking] Rückgabetyp des Testhelfers `mcp_call`**
- **Found during:** Task 2 (Gate `pyright`)
- **Issue:** `TestClient.post` liefert eine `httpx2.Response` (das SDK nutzt den httpx2-Fork), die Annotation `httpx.Response` war ein Typfehler
- **Fix:** `-> Any`, wie der Nachbarhelfer `bearer_call` in `tests/unit/test_exapp_entry.py` es seit jeher macht
- **Verification:** `pyright` 0 errors

### Kriterien-Interpretationen (dokumentiert, nicht stillschweigend)

**3. [Kriterium literal gemacht] `grep -v '^\s*#' throttle.py | grep -c "chain\|..."` ergibt 0**
- **Found during:** Task 1 (Akzeptanzkriterien)
- **Issue:** Der Treffer war kein Verweis auf den Exchange-Pfad, sondern eine seit Phase 3 bestehende Zeile im Docstring von `source_of`: "because a longer chain is the proxies, not the caller" (die Proxy-Kette von RFC 7239)
- **Fix:** Die Zeile heisst jetzt "because the further entries are the proxies, not the caller". Gleiche Aussage, und das Kriterium ist damit eine automatisierbare Wache dafür, dass `throttle.py` den Exchange-Pfad nie kennenlernt, statt an einem Homonym zu scheitern
- **Verification:** `grep -v '^\s*#' src/mcp_connector/oauth/throttle.py | grep -c "chain\|exchange_shaped_request\|looks_like_jws"` ergibt 0

**4. [Testform präzisiert] Die `applies`-Tests brauchten einen eigenen Aufbau in `test_oauth_abuse.py`**
- **Found during:** Task 1
- **Issue:** Der Plan verweist für "die Testform für `Throttle` und `Throttled`" auf `tests/unit/test_oauth_abuse.py`; der `probe`-Aufbau steht tatsächlich in `tests/unit/test_oauth_provider.py`. `test_oauth_abuse.py` baut den Wrapper nirgends.
- **Fix:** Die Tests stehen wie vom Plan verlangt in `test_oauth_abuse.py`, mit einem eigenen kleinen Aufbau (`conditional`) in derselben Form wie `probe` und einem Kommentar, warum der Fall dorthin gehört: er ist der elfte Fall der Abweichungsmatrix, ein Fremder gegen die MCP-Route. Bestehende Tests wurden weder verschoben noch gelockert.
- **Verification:** `uv run pytest tests/unit/test_oauth_abuse.py tests/unit/test_oauth_exchange_chain.py -q` grün

---

**Total deviations:** 4 (2 blockierende Befunde auto-behoben, 2 dokumentierte Präzisierungen)
**Impact on plan:** Keine Scope-Ausweitung. Unter `src/` stehen genau die vier geplanten Dateien im Diff; `exapp/middleware.py`, `oauth/verifier.py`, `oauth/exchange.py` und `oauth/jwks.py` sind unberührt. Eine Testdatei über die Plan-Liste hinaus (`tests/unit/test_entry_oauth.py`), und dort genau der eine Helfer.

## Issues Encountered

- Keine offenen. Die beiden Reibungspunkte (Helfer-Typisierung, httpx2) sind oben dokumentiert und behoben.

## TDD Gate Compliance

- Task 1: RED `ccbde94` (14 fallende Tests), GREEN `0994e98`
- Task 2: RED `8bd2a96` (3 fallende Tests), GREEN `55a4f6f`
- Kein REFACTOR-Schritt nötig; `ruff format` lief vor jedem Commit.

## Verification (Plan-Ebene)

1. `uv run pytest tests/unit tests/contract`: 3852 passed, 33 skipped, 0 failed (volle Suite, kein Subset)
2. `uv run ruff check .` und `uv run ruff format --check .`: still (251 Dateien)
3. `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
4. `uv run vulture src scripts vulture_whitelist.py`: still
5. `python -c "... t.CLASS_EXCHANGE, t.FAILURE_LIMIT < t.EXCHANGE_LIMIT < t.PATH_CEILING"`: `exchange True`; `'CLASS_EXCHANGE' in t.__all__ and 'EXCHANGE_LIMIT' in t.__all__`: `True`
6. `sed -n '1,70p' throttle.py | grep -c "CLASS_EXCHANGE"`: 1; `... | grep -c "EXCH-05"`: 1
7. `grep -v '^\s*#' throttle.py | grep -c "chain\|exchange_shaped_request\|looks_like_jws"`: 0
8. Live-Probe der Formbedingung über `['Bearer a.b.c','bearer a.b.c','Bearer abc','Basic a.b.c','Bearer ','']`: `[True, True, False, False, False, False]`
9. `grep -c "CLASS_EXCHANGE"` und `grep -c "exchange_shaped_request"`: je 1 in `entry_exapp.py` und je 1 in `entry_oauth.py`
10. `grep -c "guarded" src/mcp_connector/entry_exapp.py`: 4, unverändert gegenüber dem Stand vor diesem Task
11. `grep -c "429" tests/unit/test_oauth_exchange_chain.py`: 5; `grep -c "Retry-After"`: 2
12. `git diff --name-only b9d4454..HEAD | grep '^src/'`: genau `entry_exapp.py`, `entry_oauth.py`, `oauth/chain.py`, `oauth/throttle.py`; `exapp/middleware.py`, `oauth/verifier.py`, `oauth/exchange.py`, `oauth/jwks.py` stehen nicht darunter
13. `git diff --diff-filter=D --name-only b9d4454..HEAD`: leer, nichts gelöscht
14. Gedankenstrich-Kontrolle (lange Striche) über `CHANGELOG.md`, `oauth/throttle.py`, `oauth/chain.py` und beide Einstiegspunkte: keine Treffer; ebenso über alle vier Commit-Texte

## User Setup Required

None - der Pfad ist weiterhin ab Werk aus, und im Aus-Zustand hängt an der MCP-Route derselbe Aufbau wie vor diesem Milestone.

## Next Phase Readiness

- **Phase 23 (MAP-01/MAP-02):** Die Drossel muss dafür nicht angefasst werden. Sie zählt die Ablehnungen, die die Transportgrenze schreibt; sobald das Konto-Mapping ein geprüftes Exchange-Token mit einer Identität beantwortet, wird aus dieser Antwort ein 200, und `Throttled` vergibt für sie genau eine gezählte Ablehnung, ohne dass eine Zeile dieses Plans geändert werden müsste.
- **Phase 24 (AUDIT-07):** Ein gedrosselter Versuch schreibt weiterhin keinen Audit-Eintrag. Die Stelle dafür ist `Throttled._refuse`, und die Klasse, an der ein solcher Eintrag hängt, ist `CLASS_EXCHANGE`.
- **Phase 24 (EXCH-08):** Die Einrichtungsdoku unter `docs/` fehlt weiterhin bewusst. Dokumentiert ist bisher im Moduldocstring von `throttle.py`, in den `#:`-Kommentaren der beiden Konstanten, im Docstring von `exchange_shaped_request` und im `[Unreleased]`-Block des CHANGELOG. Was dort noch fehlt: dass zwei Worker getrennt zählen und die wirksame Grenze damit das Doppelte ist, wie bei jeder anderen Klasse dieses Moduls auch.
- **Phase 22 ist damit inhaltlich fertig:** CONF-01 (22-01), EXCH-04 (22-02) und EXCH-05 (22-03).

---
*Phase: 22-konfiguration-kette-und-drosselung*
*Completed: 2026-09-19*

## Self-Check: PASSED

- Alle neun geänderten Dateien liegen auf der Platte (throttle.py, chain.py, beide Einstiegspunkte, vier Testdateien, CHANGELOG.md)
- Alle vier Task-Commits (ccbde94, 0994e98, 8bd2a96, 55a4f6f) stehen in der Historie
- Alle Gates nach dem letzten Task erneut gefahren: volle Suite 3852 passed / 33 skipped, ruff still, pyright 0/0/0, vulture still

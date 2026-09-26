---
phase: 22-konfiguration-kette-und-drosselung
reviewed: 2026-09-19T12:00:00Z
depth: deep
files_reviewed: 13
files_reviewed_list:
  - src/mcp_connector/oauth/chain.py
  - src/mcp_connector/oauth/throttle.py
  - src/mcp_connector/config.py
  - src/mcp_connector/entry_exapp.py
  - src/mcp_connector/entry_oauth.py
  - src/mcp_connector/oauth/jwks.py
  - src/mcp_connector/oauth/exchange.py
  - tests/unit/test_oauth_exchange_chain.py
  - tests/unit/test_oauth_abuse.py
  - tests/unit/test_config.py
  - tests/unit/test_exapp_entry.py
  - tests/unit/test_entry_oauth.py
  - tests/unit/test_oauth_jwks.py
findings:
  critical: 1
  warning: 4
  info: 5
  total: 10
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-09-19
**Depth:** deep (Quergriff auf `exapp/middleware.py`, `oauth/verifier.py`, `oauth/metadata.py`; Diff gegen `f88bbdd` je Datei gelesen)
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Die drei Zusagen der Phase halten dort, wo die Tests sie messen, und die Messungen sind echte: der Aus-Zustand ist mit `is` festgenagelt (dasselbe Objekt an der Grenze, kein Wrapper an der Route), die Weiche fällt strukturell über `looks_like_jws` und beide Richtungen sind mit Attrappen belegt, die beim Aufruf auffliegen, der fremde Claim-Satz reist unter genau einem verschachtelten Schlüssel, ein Widerruf erreicht Store-Cache und Schlüsselsatz und lässt die beiden vor-authentischen Bremsen nachweislich stehen (vier respx-Messungen an `call_count`), und die Drossel zählt genau die JWS-förmigen Bearer, mit `applies`-Kurzschluss vor jedem Zählerzugriff und `_counters == {}` als Beweis. Die Formregel des Headers in `exchange_shaped_request` ist zeichengleich mit der der Transportgrenze (`_BEARER_PREFIX`-Präfix ohne Gross-Klein, `strip()` auf dem Rest, `headers.get` mit denselben Erstes-Vorkommen-Semantiken), das habe ich am Quelltext beider Stellen verglichen. `throttle.py` kennt den Exchange-Pfad tatsächlich nicht, und kein Refusal-Text von `chain.py` trägt einen gelesenen Wert.

Der Kern der Befunde liegt an den Rändern, die kein Test misst. Erstens: der Audience-Default hängt an `config.public_url`, und deren Default ist `http://127.0.0.1:8765`. Ein bewaffneter Exchange-Pfad in einem ExApp ohne gesetzte Public-URL, oder nach dem `IssuerRefused`-Rebuild von `entry_exapp.main`, der die Public-URL absichtlich fallen lässt, läuft damit mit einer Audience, die auf jeder gleich fehlkonfigurierten Instanz identisch ist. Das ist genau die Instanzgrenze, die T-22-03 halten soll, und sie fällt lautlos, entgegen der eigenen Regel des Moduls, dass ein Halbzustand nie bedient wird. Zweitens: die "genau eine INFO-Zeile je Start"-Zusage der Standalone-Hälfte ist auf dem einzigen Produktionspfad (`main`) falsch, dort stehen zwei Zeilen, und der Test, der "einmal" beweist, kombiniert genau diesen Pfad nicht.

Alle Behauptungen unten sind am Quelltext beider Seiten nachvollzogen; wo eine Zahl steht, steht die Zeile daneben.

## Status der Behebung (2026-09-19)

Alle zehn Befunde sind abgearbeitet: acht behoben, zwei mit Begruendung eingeordnet. Jeder
Fix hat einen Regressionstest, der vor dem Fix rot gewesen waere; die Gegenprobe steht je
Befund unten am Eintrag. Die Phasengrenze hielt: `git diff --name-only f096d1a..HEAD` nennt
unter `src/` genau die sechs Dateien, die der Review liest (`oauth/chain.py`,
`oauth/throttle.py`, `oauth/jwks.py`, `oauth/exchange.py`, `entry_oauth.py`,
`entry_exapp.py`). `exapp/middleware.py` ist unberuehrt geblieben, obwohl WR-03 dort seine
Gegenstelle hat: der Vertragstest ist der zaunvertraegliche Fix, das Teilen der Konstante
bleibt einer Phase ueberlassen, die diese Datei anfassen darf.

| Befund | Status | Commit |
|--------|--------|--------|
| CR-01 | behoben | `c2d61d9` |
| WR-01 | behoben | `e21414d` |
| WR-02 | behoben | `ea2a7b8` |
| WR-03 | behoben (Vertragstest) | `c1b4f18` |
| WR-04 | behoben | `07eeb74` |
| IN-01 | behoben | `85fc08f` |
| IN-02 | behoben | `cd02532` |
| IN-03 | behoben | `cd02532` |
| IN-04 | eingeordnet (kein Fix, BL-21) | dieser Commit |
| IN-05 | eingeordnet (kein Fix, BL-21) | dieser Commit |

**Eine Abweichung vom vorgeschlagenen Fix, bewusst:** WR-02 schlug vor, einen Widerspruch
zwischen hereingereichten Settings und erneut gelesener Umgebung als `ToolError`
abzuweisen. Umgesetzt ist die Richtung, die keinen Aufrufer stillschweigend entwaffnet: die
Antwort der Settings gewinnt, wo sie bewaffnet ist, und die zweite Lesung kann nur noch
bewaffnen, nie entwaffnen. Die Halbkonfigurations-Abweisung der zweiten Lesung, also der
eigentliche Grund ihrer Existenz, bleibt unveraendert und ist gemessen.

**Offen fuer spaetere Phasen, aus diesen Befunden:**

- Phase 23: sobald gueltige Exchange-Tokens eine Identitaet bekommen, aendert sich die
  Rechnung aus IN-05, weil deren 200er dann vergeben statt gezaehlt werden.
- Phase 24 (AUDIT-07): die Nachmessung der Grenze aus IN-05 und der Ende-zu-Ende-429-Lauf
  gegen die ExApp aus IN-04. Beides steht als BL-21 in `.planning/BACKLOG.md`.
- Eine Phase, die `exapp/middleware.py` anfassen darf: `_BEARER_PREFIX` teilen statt
  kopieren, dann faellt der Vertragstest aus WR-03 als Absicherung weg.

Gates nach dem letzten Commit: `ruff check`, `ruff format --check`, `pyright` (0 errors,
0 warnings), `vulture` und die volle Suite (3920 Tests in `tests/unit` und
`tests/contract`, davon 14 neue Testfunktionen aus diesen Fixes) sind gruen.

## Critical Issues

### CR-01: Der Audience-Default degradiert lautlos auf `http://127.0.0.1:8765/mcp` und hebt damit die Instanzgrenze von T-22-03 auf

**Status (2026-09-19):** **behoben** in `c2d61d9`, beide Wege. `load_exchange_config` bildet den Audience-Default nur noch, wenn `NC_MCP_PUBLIC_URL` eine Adresse nennt, und weist sonst benannt ab (`_derived_audience`); eine absichtlich getippte Loopback-Adresse passiert weiterhin, abwesende tut es nicht. Der `IssuerRefused`-Rebuild in `entry_exapp.main` laesst die Adresse bei bewaffnetem Pfad stehen und endet mit Exitcode 2 plus einer Zeile, die `NC_MCP_EXCHANGE_ENABLED` und `NC_MCP_EXCHANGE_AUDIENCE` nennt; die Rettung aus Plan 05-04 bleibt fuer die Store-Installation, die diesen Namensraum nie setzt, unveraendert. Vier neue Testfaelle fuer die Abwesenheit (fehlend, leer, Leerzeichen, `/`), je einer fuer die benannte Audience und die getippte Loopback-Adresse, dazu die Abweisung an `build_chain` und drei Faelle in `test_exapp_entry.py`: der Bau, der Start ueber `main`, und der Rebuild-Pfad, der jetzt nicht mehr rettet. Gegenprobe vor dem Fix: `load_exchange_config(ARMED)` lieferte `audience == "http://127.0.0.1:8765/mcp"` statt einer Abweisung.

**File:** `src/mcp_connector/oauth/chain.py:143-146`, dazu `src/mcp_connector/config.py:128` (`DEFAULT_PUBLIC_URL`) und `src/mcp_connector/entry_exapp.py:636` (`resolved.pop(config.ENV_PUBLIC_URL, None)`)

**Issue:** Der Default der Audience ist `f"{config.public_url(source)}{RESOURCE_SUFFIX}"`. `config.public_url` antwortet mit `DEFAULT_PUBLIC_URL = "http://127.0.0.1:8765"`, wenn `NC_MCP_PUBLIC_URL` fehlt oder leer ist (`config.py:343-346`). Zwei erreichbare Wege führen einen **bewaffneten** Exchange-Pfad in diesen Zustand:

1. ExApp ohne Public-URL: `entry_exapp.main` loggt dafür seit Plan 05-04 nur einen Fehler und **bedient weiter** (Zeile 563-594). `build_exapp_app` liest den Namensraum davor (Zeile 104) und bewaffnet die Kette mit der Audience `http://127.0.0.1:8765/mcp`.
2. Der `IssuerRefused`-Rebuild: `main` entfernt die konfigurierte Public-URL aus dem Mapping (Zeile 636) und baut erneut. Auf dem zweiten Bau wird `load_exchange_config(resolved)` erneut ausgeführt und der Audience-Default aus der jetzt fehlenden Public-URL berechnet. Eine Instanz, deren Public-URL das SDK ablehnte, betreibt den Exchange-Pfad ab da mit dem Loopback-Default, obwohl der Operator eine Audience nie angefasst hat, und die zweite INFO-Zeile "the token exchange path is armed" sagt dazu nichts.

Die Folge: jede Instanz in diesem Zustand akzeptiert dieselbe Audience. In genau dem Einsatzbild, für das die Phase gebaut ist (mehrere Behörden-Instanzen hinter demselben F13-Orchestrator, also gleicher Issuer und gleiche `azp`-Allowlist), hält ein Token, das für Instanz A gemünzt wurde, damit auch an Instanz B. Das ist wörtlich der Satz, den der Moduldocstring (Zeile 36-39) und T-22-03 ausschliessen. Der Test `test_the_audience_default_is_the_resource_url_of_this_instance` (`test_oauth_exchange_chain.py:149`) setzt die Public-URL immer; der Fall "bewaffnet ohne Public-URL" steht in keinem Korpus. Dass der Store-Verifier dieselbe Default-Resource benutzt (`verifier.py:198`), ist kein Gegenargument: dessen Tokens sind Zufallswerte gegen den lokalen Store, eine Instanzverwechslung ist dort strukturell unmöglich; beim Exchange-Pfad ist die Audience die **einzige** Instanzbindung eines fremd signierten Tokens.

Das Modul misst sich selbst an "Half configured is never served" (`load_exchange_config`-Docstring, Zeile 127-133). Ein bewaffneter Pfad, dessen Audience ein Platzhalter ist, den kein Betreiber je gesehen hat, ist genau so ein Halbzustand, und er wird bedient statt abgewiesen.

**Fix:** Den Default nur bilden, wenn es eine Quelle für ihn gibt, sonst benannt abweisen:

```python
audience = _optional(source, config.ENV_EXCHANGE_AUDIENCE)
if audience is None:
    if not (source.get(config.ENV_PUBLIC_URL) or "").strip():
        raise ToolError(
            message=(
                f"{config.ENV_EXCHANGE_AUDIENCE} is not set and "
                f"{config.ENV_PUBLIC_URL} names no address to derive it from."
            ),
            hint=_HINT,
        )
    audience = f"{config.public_url(source)}{RESOURCE_SUFFIX}"
```

Damit endet auch der `IssuerRefused`-Rebuild in `entry_exapp.main` für einen bewaffneten Pfad im vorhandenen `except ToolError as second` mit Exitcode 2, was für einen Sicherheitspfad die richtige Antwort ist: das Wachbleiben von Plan 05-04 existiert für die Store-Installation ohne Deploy-Variablen, und wer den Exchange-Namensraum setzt, ist nie diese Installation. Dazu zwei Tests: `load_exchange_config(ARMED ohne NC_MCP_PUBLIC_URL)` ist eine ToolError, die beide Variablennamen nennt, und der Rebuild-Pfad mit bewaffnetem Namensraum endet in SystemExit 2 statt in einem zweiten Bau.

## Warnings

### WR-01: Der bewaffnete Standalone-Start über `main` schreibt die INFO-Zeile zweimal; die Zusage "genau eine Zeile je Start" ist auf dem Produktionspfad falsch und ungetestet

**Status (2026-09-19):** **behoben** in `e21414d`. Die Ankuendigung steht jetzt ausschliesslich in `build_oauth_app`, hinter der letzten Zeile, die die Antwort noch aendern kann; `load_settings` liest die Konfiguration und sagt nichts. Der neue Test stellt den `main`-Weg nach (`load_settings(armed)` plus `build_oauth_app(env, settings=...)`) und zaehlt die Zeile ueber beide Aufrufe zusammen; dazu je ein Test fuer die beiden anderen Wege hinein. Gegenprobe vor dem Fix: dieselbe Kombination zaehlte 2.

**File:** `src/mcp_connector/entry_oauth.py:157-158`, `219-229`, `419-428`

**Issue:** `main` ruft `load_settings()` (kündigt an, Zeile 158) und danach `build_oauth_app(settings=settings)`. Dort gilt `settings is not None`, also liest Zeile 228 den Namensraum erneut aus `os.environ` und Zeile 229 kündigt **erneut** an. Zwei INFO-Zeilen je bewaffnetem Start. Der Kommentar an Zeile 226-227 ("the announcement stays one line per start either way") und die 22-01-Summary ("es bleibt bei genau einer Zeile je Start") behaupten das Gegenteil. Die beiden Tests decken je einen Aufrufweg einzeln: `test_a_complete_exchange_configuration_is_announced_once_and_without_a_value` ruft nur `load_settings`, `test_the_application_is_announced_once_when_the_settings_are_handed_in` baut die Settings aus einer **unbewaffneten** Umgebung. Die Kombination, die `main` tatsächlich fährt (bewaffnet in beiden Schritten), misst keiner. Kein Sicherheitsschaden, aber eine gemessene Behauptung der Phase, die nicht stimmt, und doppelte Zeilen in genau dem Log, in dem ein Auditor später zählen soll, wie oft der Pfad bewaffnet wurde.

**Fix:** Die Ankündigung an genau eine Stelle: aus `load_settings` entfernen und in `build_oauth_app` nach der endgültigen `exchange_config` ausführen (beide Aufrufwege laufen dort zusammen, `main` baut genau einmal). Dazu ein Test, der den `main`-Weg nachstellt: `load_settings(armed_env)` plus `build_oauth_app(armed_env, settings=...)` und `len(announcements) == 1` über beide Aufrufe zusammen.

### WR-02: `StandaloneSettings.exchange` wird auf dem Settings-Pfad ignoriert; die Kette kann aus einer anderen Quelle gebaut werden als die hereingereichten Settings

**Status (2026-09-19):** **behoben** in `ea2a7b8`, mit der oben genannten Abweichung. Die zweite Lesung bleibt, weil sie die Halbkonfiguration der Umgebung abweist; was sie mit ihrer Antwort darf, ist jetzt einseitig: sie kann einen Pfad bewaffnen, von dem die Settings nichts wussten, und sie kann einen, den die Settings tragen, nie entwaffnen. Der Feld-Docstring sagt genau das. Zwei Tests: bewaffnete Settings plus Werksumgebung ergeben eine Anwendung mit Kette und genau eine Zeile, und die Halbkonfiguration neben bewaffneten Settings wird weiterhin abgewiesen. Gegenprobe vor dem Fix: derselbe erste Fall lieferte einen `StoreTokenVerifier` an der Grenze, ohne Fehler und ohne Zeile.

**File:** `src/mcp_connector/entry_oauth.py:94-97` (Docstring des Feldes), `218-229`

**Issue:** Zeile 219 liest `resolved.exchange`, Zeile 228 überschreibt es auf dem Settings-Pfad bedingungslos mit dem Ergebnis eines zweiten Umgebungslesens (`env`, bei `main` also `os.environ`). Damit ist das Feld auf dem Pfad, für den es laut Docstring existiert ("so that the application built from them reads the namespace exactly once"), totes Gewicht: der Namensraum wird ein zweites Mal gelesen, und was in den Settings steht, entscheidet nichts. Ein Aufrufer, der Settings mit bewaffnetem `exchange` aus Mapping A baut und `build_oauth_app(settings=...)` ohne `env` ruft, bekommt bei sauberem `os.environ` eine Anwendung **ohne** Kette, ohne Fehler und ohne Zeile: er glaubt bewaffnet und bedient unbewaffnet, das ist die stille Halbkonfiguration, gegen die T-22-02 geschrieben ist, nur eine Ebene höher. Bei `main` sind beide Quellen zufällig dieselbe, weshalb es niemand sieht.

**Fix:** Die Doppelablesung behalten (sie trägt die Abweisung der Halbkonfiguration), aber die Widersprüche abweisen statt still aufzulösen:

```python
if settings is not None:
    reread = chain.load_exchange_config(env)
    if (reread is None) != (resolved.exchange is None):
        raise ToolError(
            message=(
                "the exchange configuration of the handed-in settings and the one of "
                "this environment disagree about whether the path is armed."
            ),
            hint=_HINT,
        )
    exchange_config = reread
```

Und den Feld-Docstring auf die Wirklichkeit bringen: das Feld trägt die Antwort des `load_settings`-Weges, der Settings-Weg liest erneut und prüft Gleichheit. Ein Test mit bewaffneten Settings und leerem `env`-Mapping, der die ToolError erwartet.

### WR-03: Die Bearer-Leseweise existiert jetzt zweimal (Middleware privat, `chain._BEARER_PREFIX` als Kopie), und kein Test hält die beiden gegeneinander

**Status (2026-09-19):** **behoben** in `c1b4f18`, als Vertragstest wie vorgeschlagen. `test_the_throttle_and_the_transport_boundary_read_the_same_bearer` faehrt die echte `RequireOAuthBearer` ueber achtzehn Headerformen (Tabulator, Doppel-Leerzeichen, fehlendes Leerzeichen, `Bearer` ohne Rest, fuehrender Weissraum, Nicht-ASCII-Rest, nachlaufendes Leerzeichen) und verlangt, dass `exchange_shaped_request` genau dann `True` sagt, wenn die Grenze einen Token extrahiert hat, der `looks_like_jws` erfuellt. Die Regel steht dabei kein drittes Mal im Test: verglichen wird der Token, den die Grenze ihrem Verifier gereicht hat. Gegenprobe: mit einer absichtlich tolerant umgeschriebenen Grenze (`partition` am ersten Leerzeichen) faellt der Test auf der Tabulator- und der Weissraumform; `exapp/middleware.py` wurde danach unveraendert wiederhergestellt. Der Docstring von `_BEARER_PREFIX` nennt den Test jetzt als das, was die Kopie haelt.

**File:** `src/mcp_connector/oauth/chain.py:314-318`, `338-341`; Gegenstelle `src/mcp_connector/exapp/middleware.py:80`, `232-234`

**Issue:** Die Phase begründet `exchange_shaped_request` damit, dass die Formregel "genau einmal existieren darf" (Docstring Zeile 325-330), und hält das für `looks_like_jws` auch mit einem Test (`test_the_condition_of_the_throttle_is_the_switch_of_the_verifier_itself`). Für die andere Hälfte derselben Bedingung, die Extraktion des Tokens aus dem Header, gilt es nicht: `_BEARER_PREFIX` plus Präfixvergleich plus `strip()` stehen wortgleich in `middleware.py` (privat) und als eingestandene Kopie in `chain.py`. Heute sind sie zeichengleich (verglichen), aber nichts hält sie zusammen: die Ende-zu-Ende-Tests prüfen nur die Headerformen `Bearer/bearer/BEARER a.b.c`, `Basic`, leer und fehlend. Driftet die Middleware-Leseweise (etwa eine tolerantere Trennzeichenbehandlung), zählt die Drossel eine andere Menge als die, die die Grenze in den Exchange-Zweig schickt, und das ist wörtlich der Fall, den der eigene Docstring "schlechter als keine Drossel" nennt: entweder ungedrosselte vor-authentische Signaturarbeit oder gedrosselte eigene Tokens.

**Fix:** Ein Vertragstest, der beide Leseweisen über eine Header-Matrix (Tab statt Leerzeichen, Doppel-Leerzeichen, fehlendes Leerzeichen, `Bearer` ohne Rest, führender Weissraum, Nicht-ASCII-Rest) gegeneinander hält: für jede Form muss `exchange_shaped_request` genau dann `True` sagen, wenn die Grenze einen Token extrahiert, der `looks_like_jws` erfüllt. Da `middleware.py` ausserhalb des Phasen-Zauns liegt, ist der Test der zaunverträgliche Fix; die Konstante teilen kann eine spätere Phase.

### WR-04: `ChainedVerifier.invalidate` ohne `try/finally`: wirft die Store-Hälfte, erreicht der Widerruf den Schlüsselsatz nie

**Status (2026-09-19):** **behoben** in `07eeb74`, wortgleich mit dem vorgeschlagenen `try/finally`. Der Test reicht einen Store herein, dessen `invalidate` wirft, und haelt beide Haelften der Zusage: `forget_keys` lief, und die Ausnahme kam an. Gegenprobe vor dem Fix: `checker.forgotten` blieb 0.

**File:** `src/mcp_connector/oauth/chain.py:430-440`

**Issue:** `invalidate` ruft `self._store.invalidate()` und danach `self._checker.forget_keys()`. Der konkrete `StoreTokenVerifier.invalidate` ist ein `dict.clear()` und kann nicht werfen (geprüft, `verifier.py:207-215`), aber der Zweig ist absichtlich ein Protokoll (`StoreBranch`), damit andere Implementierungen hereingereicht werden können, und die Testdatei selbst reicht Stellvertreter herein, deren `invalidate` wirft. Für jede solche Implementierung bleibt bei einem Fehler der ersten Hälfte ein rotierter Signaturschlüssel bis zu fünf Minuten benutzbar, und zwar genau in dem Moment, in dem jemand widerrufen hat, also die stillste Form des Versagens dieser Kette. Der Docstring verspricht "One call, both layers" ohne diese Einschränkung.

**Fix:**

```python
def invalidate(self) -> None:
    try:
        self._store.invalidate()
    finally:
        self._checker.forget_keys()
```

Ein Test mit einem Store, dessen `invalidate` wirft: `forget_keys` wurde trotzdem gerufen, die Ausnahme kommt an.

## Info

### IN-01: Der Bau des `AccessToken` steht ausserhalb des Fail-closed-Fangs von T-22-09

**Status (2026-09-19):** **behoben** in `85fc08f`, mit der ersten der beiden vorgeschlagenen Varianten: die Konstruktion steht im selben `try` wie der Aufruf. Zwei Testfaelle (Claim-Satz ohne `azp`, ohne `exp`) halten den Rest von T-22-09 mit: eine Abweisung, genau eine Zeile, nur der Typ darin, und der Store-Zweig ungefragt. Gegenprobe vor dem Fix: derselbe Claim-Satz endete in einem `KeyError` aus `verify_token` heraus.

**File:** `src/mcp_connector/oauth/chain.py:399-415`

`except Exception` deckt nur den Aufruf `claims_of` ab. `str(claims["azp"])` und `int(claims["exp"])` danach werfen `KeyError`, wenn ein (per Protokoll austauschbarer) `ExchangeBranch` einen Claim-Satz ohne diese Schlüssel liefert, und das wird an der Grenze ein 500. Mit dem echten Checker unerreichbar (Phase 21 garantiert beide Claims), aber die Zusage "jede unerwartete Ausnahme dieses Zweigs ist eine Abweisung" endet vier Zeilen zu früh. Fix: die Konstruktion in denselben `try` ziehen oder die beiden Zugriffe mit `claims.get` plus Abweisung schreiben.

### IN-02: `retry_after` beschattet seinen eigenen Parameter `limit` in der Schleife

**Status (2026-09-19):** **behoben** in `cd02532`. `for key, bound in pairs:`, wie vorgeschlagen; ein Kommentar sagt, warum die Zeile umbenannt wurde, damit die naechste Hand sie nicht zurueckdreht. Kein neuer Test: die Umbenennung aendert kein Verhalten, und die vorhandenen Drossel-Tests sind die Absicherung.

**File:** `src/mcp_connector/oauth/throttle.py:264-272`

`for key, limit in pairs:` überschreibt den Parameter `limit`. Funktional korrekt, weil `pairs` vorher gebaut ist, aber genau die Zeile, an der die nächste Hand beim Lesen stolpert. Vorbestand, nicht Phase 22; beim nächsten Anfassen der Datei umbenennen (`for key, bound in pairs:`).

### IN-03: Zwei Leerzeilen-Artefakte aus dem Phasen-Diff

**Status (2026-09-19):** **behoben** in `cd02532`. Beide Leerzeilen entfernt; `ruff format --check` bleibt gruen, das Repo hat damit keine Funktion mehr in dieser Form.

**File:** `src/mcp_connector/oauth/jwks.py:213-214`, `src/mcp_connector/oauth/exchange.py:495-496`

`def _stale(...)` und `def _require_text(...)` haben durch diese Phase je eine leere Zeile zwischen Signatur und Rumpf bekommen (im Diff als eigene `+`-Zeile sichtbar). Kosmetik, aber es sind die einzigen zwei Funktionen des Repos in dieser Form. Entfernen.

### IN-04: Der 429-Pfad des ExApp-Einstiegspunkts ist nur strukturell belegt, nie Ende zu Ende

**Status (2026-09-19):** **eingeordnet, kein Fix.** Begruendung: der Wrapper ist geteilt und die Verdrahtung zeilengleich, und beides ist gemessen statt behauptet. Die ExApp-Seite hat die zwei Strukturtests (Wrapper aussen, im Aus-Zustand gar keiner), die Standalone-Seite hat die zwei Ende-zu-Ende-Laeufe gegen genau denselben `throttle.Throttled` mit derselben Bedingung `chain.exchange_shaped_request` und demselben `throttle.EXCHANGE_LIMIT`. Ein zweiter Ende-zu-Ende-Lauf misst damit den geteilten Wrapper ein zweites Mal und die Verdrahtung, die die Strukturtests schon halten, kein drittes Verhalten. Der Befund nennt das Risiko selbst klein; die Luecke ist keine Sicherheitsluecke, sondern eine fehlende Doppelmessung. Sie gehoert zu AUDIT-07 in Phase 24, wo die Betreiber-Sichtbarkeit abgewiesener Versuche ohnehin einen 429-Lauf gegen die gebaute ExApp braucht, und wird dort einmal und vollstaendig gemacht statt hier halb. Festgehalten als BL-21 in `.planning/BACKLOG.md`, damit "spaeter" nicht "nie" heisst.

**File:** `tests/unit/test_exapp_entry.py:2397-2410`, Gegenstück `tests/unit/test_oauth_exchange_chain.py:872-921`

Die beiden gemessenen 429-Läufe (Limit, Retry-After, `call_count == 0`, unberührter Alt-Pfad) laufen ausschliesslich gegen `build_oauth_app`. Für `build_exapp_app` gibt es nur die zwei Strukturtests (Wrapper aussen, nichts im Aus-Zustand). Die Verdrahtung ist zeilengleich und der Wrapper geteilt, das Risiko ist klein; trotzdem ist die ExApp der Pfad, den F13 tatsächlich trifft, und ein einziger `TestClient`-Lauf gegen die gebaute ExApp-Anwendung (mit AppAPI-Attrappe oder direkt gegen die 401 der Grenze) würde die Lücke schliessen.

### IN-05: Widerruf plus gebasteltes Token ordnet je Zyklus einen ausgehenden JWKS-Abruf an; der Deckel ist die Drossel, und das steht nirgends

**Status (2026-09-19):** **eingeordnet, kein Fix.** Der Befund verlangt selbst keinen: "Kein Fix jetzt; ein Satz im Docstring ... beziehungsweise in der Phase-24-Planung". Der Satz gehoert dorthin und nicht hierher, weil die Rechnung, die er beschreibt, erst in Phase 23 wahr wird: solange kein Exchange-Token eine Identitaet bekommt, zaehlen die gebastelten Tokens als Ablehnungen und `EXCHANGE_LIMIT`/`PATH_CEILING` sind der Deckel. Ein Docstring-Satz, der heute eine Grenze beschreibt und ab Phase 23 eine andere, waere genau die Art Dokumentation, die beim naechsten Lesen falsch ist. Festgehalten ist er darum als BL-21 in `.planning/BACKLOG.md`, faellig mit AUDIT-07 in Phase 24, wo die Grenze nachgemessen statt wiederentdeckt wird. Der heutige Zustand ist unveraendert korrekt: `forget()` laesst beide vor-authentischen Bremsen absichtlich stehen, und vier respx-Messungen an `call_count` belegen das.

**File:** `src/mcp_connector/oauth/chain.py:430-440`, `src/mcp_connector/oauth/jwks.py:196-211`

`forget()` lässt die beiden Bremsen absichtlich stehen, aber der Expiry-Abruf ist von der Miss-Abkühlzeit ausgenommen (by design, `jwks.py:184`). Ein Client mit Widerrufsrecht kann also im Takt `POST /revoke` (200, ungezählt, weil die Klasse Ablehnungen zählt) plus ein JWS-förmiges Token mit passendem `iss` und erfundenem `kid` je Zyklus genau einen Abruf beim Provider anordnen. Begrenzt wird das heute allein durch `EXCHANGE_LIMIT`/`PATH_CEILING`, weil die gebastelten Tokens als Ablehnungen zählen; sobald Phase 23 gültigen Exchange-Tokens eine Identität gibt, werden deren 200er **vergeben** statt gezählt, und die Rechnung ändert sich. Kein Fix jetzt; ein Satz im Docstring von `forget` beziehungsweise in der Phase-24-Planung (AUDIT-07), damit die Grenze dort nachgemessen wird, statt wiederentdeckt.

---

_Reviewed: 2026-09-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

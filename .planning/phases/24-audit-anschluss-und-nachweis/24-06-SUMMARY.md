---
phase: 24-audit-anschluss-und-nachweis
plan: 06
subsystem: auth
tags: [occ, appapi, exapp, token-exchange, starlette, dry-run, jwt]

requires:
  - phase: 24-05
    provides: "oauth/exchange_dryrun.py: DryRunStep, DryRunResult, STEPS (22 Schritte), LIMIT_SENTENCE und COST_SENTENCE"
  - phase: 24-03
    provides: "exapp/audit_read.REFUSALS_KEYWORD, das Wort, das in keinem occ-Hilfetext stand"
  - phase: 18-08
    provides: "exapp/audit_verify.py als Vorlage: Guard, Immer-200-Regel, begrenzter Body"
provides:
  - "exapp/exchange_check.py: die undeklarierte occ-Route des Trockenlaufs, immer 200"
  - "STEP_NAMES: die menschenlesbaren Namen der 22 Schritte, an einem Ort"
  - "occ mcp_connector:exchange:check --token=... [--json], das vierte Kommando"
  - "MAX_BODY_BYTES als Rechnung ueber MAX_TOKEN_BYTES, gemessen statt angenommen"
  - "Annahme A5 der Recherche gemessen und bestaetigt"
affects: [24-07, 24-08, 24-09]

tech-stack:
  added: []
  patterns:
    - "Regel antwortet in Daten, Konsole macht Saetze: STEP_NAMES lebt in der Shell, nicht in der Regel"
    - "Bodygrenze als Vielfaches der fachlichen Grenze statt als Literal"
    - "Ein eigener benannter Ausgang fuer den nicht konfigurierten Zustand statt lauter gefallener Schritte"

key-files:
  created:
    - src/mcp_connector/exapp/exchange_check.py
    - tests/unit/test_exapp_exchange_check.py
  modified:
    - src/mcp_connector/exapp/occ.py
    - src/mcp_connector/entry_exapp.py
    - appinfo/info.xml
    - vulture_whitelist.py
    - tests/unit/test_exapp_lifecycle.py
    - tests/unit/test_exapp_entry.py

key-decisions:
  - "MAX_BODY_BYTES ist 2 * MAX_TOKEN_BYTES und kein Literal: die 4096 der Vorlage haetten ein zulaessiges Token als Formfehler gemeldet"
  - "Der nicht konfigurierte Exchange-Pfad bekommt ein eigenes benanntes Ergebnis, weil eine Liste gefallener Schritte den Admin an das Token statt an die Konfiguration schickt"
  - "Die Token-Option ist optional und nicht required: ein fehlender Wert ist der erste benannte Schritt der Regel, kein Symfony-Nutzungsfehler ohne die Ehrlichkeitssaetze"
  - "Die Schrittnamen leben in exapp/exchange_check.py und nicht in oauth/exchange_dryrun.py, damit eine zweite Oberflaeche spaeter nur eine Datei ist"

patterns-established:
  - "Siebter bewusst undeklarierter Pfad: die Begruendung steht im Moduldocstring, im Manifest-Kommentar und in entry_exapp, und ein Test haelt sie gegen jede <url>"
  - "Zahl der Schrittzeilen und Zahl der JSON-Eintraege werden gegen len(STEPS) gehalten, abgeleitet statt getippt"

requirements-completed: [EXCH-06]

duration: 105min
completed: 2026-09-24
---

# Phase 24 Plan 06: Die Konsolenhälfte des Trockenlaufs Summary

**`occ mcp_connector:exchange:check --token=... [--json]` benennt alle 22 Prüfschritte mit ihrem Ergebnis, immer mit Status 200, ohne das Token je zu wiederholen, und Annahme A5 ist gegen die laufende NC-35-HaRP-Topologie gemessen statt angenommen: ein Optionswert von 8 193 Byte kommt ungekürzt an.**

## Performance

- **Duration:** 105 min
- **Started:** 2026-09-24T05:55:00Z
- **Completed:** 2026-09-24T07:40:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Die Route `/exchange-check` steht, mit dem wörtlich übernommenen Guard der sechs Geschwister und der Immer-200-Regel, die AppAPI erzwingt.
- Jede Antwort trägt alle 22 Schritte, auch die nicht erreichten, weil ein fehlender Schritt sich als bestandener liest (Pitfall 8).
- Das vierte occ-Kommando ist registriert, live geprüft, und seine Optionsbeschreibung sagt den Preis: der Wert steht in der Prozessliste des Nextcloud-Hosts.
- Annahme A5 ist gemessen: fünf Größen durch `ExAppOccService::buildCommand`, und die Messung steht als Zahl mit Datum im `#:`-Kommentar der Bodygrenze.
- Der Übergabepunkt aus Plan 24-03 ist eingelöst: `--user` nennt jetzt beide reservierten Wörter.

## Task Commits

1. **Task 1: Die Route des Trockenlaufs** - `d005d66` (test, RED), `b418506` (feat, GREEN)
2. **Task 2: Das vierte occ-Kommando und die Verdrahtung** - `693645f` (test, RED), `122cf97` (feat, GREEN)
3. **Task 3: Die Messung A5 gegen die laufende Topologie** - `40ae8ae` (docs)

## Files Created/Modified

- `src/mcp_connector/exapp/exchange_check.py` - die Routenfabrik, der Guard, die beiden Ausgabeformen, `STEP_NAMES`, die gemessene Bodygrenze.
- `tests/unit/test_exapp_exchange_check.py` - 21 Fälle: Guard, Statuszwang, Schrittzahl gegen `len(STEPS)`, Tokenleck, Bodygrenze, nicht konfigurierter Pfad, Fehlerzweig.
- `src/mcp_connector/exapp/occ.py` - der vierte Schema-Eintrag, vier neue Beschreibungskonstanten, `REFUSALS_KEYWORD` im Hilfetext von `--user`.
- `src/mcp_connector/entry_exapp.py` - `exchange_check_routes(env)` in der Routenliste, plus der siebte Absatz der Begründung.
- `appinfo/info.xml` - `/exchange-check` als siebter bewusst fehlender Pfad benannt.
- `vulture_whitelist.py` - die drei Felder aus Plan 24-05 haben ihren Leser und sind entfernt.
- `tests/unit/test_exapp_lifecycle.py` - vier neue Fälle, zwei bestehende von getippten Zahlen befreit.
- `tests/unit/test_exapp_entry.py` - die Route auf der gebauten Anwendung, erreicht und abgewiesen.

## Die Messung A5

**Frage:** reicht `ExAppOccService::buildCommand` einen Optionswert von mehreren Kilobyte unverändert durch?

**Orakel:** nicht der Wert (den gibt die Antwort nie zurück, Pitfall 6), sondern der gefallene Schritt. Ein Wert, der mit mehr als `MAX_TOKEN_BYTES` Byte bei der Regel ankommt, fällt an `token_size`; ein kürzerer fällt an `token_shape`. Ein Lauf mit 8 193 Byte, der an `token_size` fällt, beweist also, dass mindestens 8 193 Byte ankamen.

**Topologie, gemessen am 2026-09-24** (Rohausgabe des Laufs):

```
== containers ==
nc_app_mcp_connector  127.0.0.1:5000/mcp_connector:0.2.1  Up 2 minutes (healthy)
nc35-greenmail  greenmail/standalone:2.1.12  Up 5 days
nc35-caddy  caddy:2  Up 5 days
nc35-harp  ghcr.io/nextcloud/nextcloud-appapi-harp:release  Up 5 days (healthy)
nc35-nc  nextcloud:35.0.0-apache-local  Up 5 days (healthy)

== arming the exchange path on the deployed ExApp ==
ExApps:
mcp_connector (MCP Connector): 0.2.1 [enabled]
```

AppAPI meldet sich als 35.0.0 (`AA_VERSION` des ExApp-Containers). Aufruf je Punkt, im Nextcloud-Container:

```
V=$(head -c <n> /dev/zero | tr "\0" "a"); php occ mcp_connector:exchange:check --token="$V" --json
```

**Die fünf Punkte.** Jede Antwort trug 22 Schritte, `"checked":true` und Exitcode 0. Die beiden entscheidenden Einträge je Lauf, verbatim aus der Rohausgabe:

```
### 1000 bytes
{"step":"token_size","name":"the token stays within the size bound of this app","outcome":"passed","reason":null,"note":null}
{"step":"token_shape","name":"the token has the shape of a signed JWT","outcome":"failed","reason":"exchange_malformed","note":null}
"passed":false  "checked":true  steps=22

### 4000 bytes
{"step":"token_size","name":"the token stays within the size bound of this app","outcome":"passed","reason":null,"note":null}
{"step":"token_shape","name":"the token has the shape of a signed JWT","outcome":"failed","reason":"exchange_malformed","note":null}
"passed":false  "checked":true  steps=22

### 8000 bytes
{"step":"token_size","name":"the token stays within the size bound of this app","outcome":"passed","reason":null,"note":null}
{"step":"token_shape","name":"the token has the shape of a signed JWT","outcome":"failed","reason":"exchange_malformed","note":null}
"passed":false  "checked":true  steps=22

### 8192 bytes
{"step":"token_size","name":"the token stays within the size bound of this app","outcome":"passed","reason":null,"note":null}
{"step":"token_shape","name":"the token has the shape of a signed JWT","outcome":"failed","reason":"exchange_malformed","note":null}
"passed":false  "checked":true  steps=22

### 8193 bytes
{"step":"token_size","name":"the token stays within the size bound of this app","outcome":"failed","reason":"exchange_malformed","note":null}
{"step":"token_shape","name":"the token has the shape of a signed JWT","outcome":"skipped","reason":null,"note":null}
"passed":false  "checked":true  steps=22
```

**Folgerung: A5 ist bestätigt, nicht widerlegt.** Der Umschlagpunkt liegt exakt dort, wo unsere eigene Regel ihn zieht, also hat der Weg nichts gekürzt. Für Plan 24-09 heißt das: **in die Doku gehört keine gemessene Obergrenze unterhalb von `MAX_TOKEN_BYTES = 8192`.** Die bindende Grenze der Umgebung bleibt die schon in 24-RESEARCH.md gemessene: Apaches `LimitRequestFieldSize` (8190 Byte) trifft den `Authorization`-Header im Betrieb, nicht den occ-Optionswert. Die Optionsbeschreibung in `exapp/occ.py` nennt deshalb keine zusätzliche Zahl.

Ein fünfter Punkt (8 193) kam zu den vier geplanten dazu, weil die vier geplanten allein die Frage nicht entscheiden: ein gekürzter Wert unter der Grenze fällt am selben Schritt wie ein ungekürzter. Erst der Punkt oberhalb der Grenze trennt die beiden Fälle.

**Zustand danach:** die ExApp ist wieder mit der unveränderten Registrierung aus `scripts/bootstrap_exapp.sh` eingetragen, ohne die vier `NC_MCP_EXCHANGE_*`-Variablen des Messlaufs. Live gegengeprüft:

```
$ php occ mcp_connector:exchange:check --token=probe
the token exchange path is not configured on this instance, so there is nothing to hold a
token against. Nothing was checked and nothing about the token follows from that.
```

## Decisions Made

- **Die Bodygrenze ist `2 * MAX_TOKEN_BYTES` und steht nirgends als Zahl.** Die 4096 der Vorlage `audit_verify` sind kleiner als die harte Tokengrenze, hätten also ein zulässiges Token als Formfehler gemeldet, was die eine Antwort ist, die ein Trockenlauf nie geben darf. Ein Test liest den Quelltext und schlägt fehl, wenn das Ergebnis der Rechnung als Literal darin steht.
- **Der nicht konfigurierte Exchange-Pfad ist ein eigener benannter Ausgang** (`OUTCOME_NOT_CONFIGURED`), kein Token, das an allen Regeln scheitert. 22 rote Zeilen würden den Admin an das Token schicken, das ihm jemand gegeben hat, statt an die Konfiguration seiner Instanz.
- **`--token` ist `optional` und nicht `required`.** Ein fehlender Wert ist der erste Schritt der Regel (`token_present`), also ein benanntes Ergebnis mit den beiden Ehrlichkeitssätzen darunter. Ein Symfony-Nutzungsfehler käme ohne sie.
- **Die Schrittnamen stehen in der Konsolenhälfte.** Die Regel antwortet in Daten, wie `ChainFinding` gegen `audit_verify._report`. Eine zweite Oberfläche für den Standalone-Betrieb ist damit später eine Datei und keine Änderung an `oauth/exchange_dryrun.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `/exchange-check` im Manifest-Kommentar benannt**
- **Found during:** Task 1
- **Issue:** Der große Kommentar in `appinfo/info.xml` zählt die bewusst fehlenden Pfade auf und sagt von sich, er sei der einzige Ort, an dem sie hier stehen. Ohne einen siebten Absatz wäre diese Aussage falsch geworden, und die Begründung einer Sicherheitsentscheidung hätte nur noch im Python-Docstring gestanden.
- **Fix:** Siebter Absatz ergänzt, mit dem Verlust, der hier eigen ist: ein Orakel, kein Verzeichnis.
- **Files modified:** `appinfo/info.xml`
- **Verification:** `test_the_path_is_declared_in_no_route_of_the_manifest` hält den Pfad gegen jede `<url>`; die Zahl der Routen bleibt 13.
- **Committed in:** `b418506`

**2. [Rule 2 - Missing Critical] `REFUSALS_KEYWORD` im Hilfetext von `--user`**
- **Found during:** Task 2
- **Issue:** Plan 24-03 hat diesen Punkt ausdrücklich an 24-06 übergeben: das reservierte Wort `refusals` funktionierte, stand aber in keinem `occ list`-Hilfetext, war also nur dem Quelltext bekannt. Der Plantext von Task 2 deckt `exapp/occ.py` ab, benennt den Punkt aber nicht.
- **Fix:** `OCC_AUDIT_READ_USER_DESCRIPTION` nennt beide reservierten Wörter, beide über ihre Konstanten und nicht als Literal.
- **Files modified:** `src/mcp_connector/exapp/occ.py`
- **Verification:** `test_the_read_command_names_both_reserved_words_of_its_user_option`
- **Committed in:** `122cf97`

**3. [Rule 3 - Blocking] Zwei Registrierungstests von getippten Zahlen befreit**
- **Found during:** Task 2
- **Issue:** `test_a_refused_first_command_does_not_cost_the_second` und `test_a_first_command_that_never_arrives_does_not_cost_the_second` reichten respx drei Antworten und prüften `call_count == 3`. Mit dem vierten Kommando lief der Iterator leer und beide schlugen mit `coroutine raised StopIteration` fehl, also mit einem Fehler über etwas ganz anderes als ihren Gegenstand.
- **Fix:** Ein Helfer `_accepted()` leitet die Antworten aus `occ.command_schemes()` ab, und beide Zählungen laufen jetzt gegen `len(occ.command_schemes())`. Genau die Regel, die ein dritter Test derselben Datei seit Plan 19-07 schon formuliert.
- **Files modified:** `tests/unit/test_exapp_lifecycle.py`
- **Verification:** beide Fälle grün, `uv run pytest -q` vollständig grün
- **Committed in:** `122cf97`

**4. [Rule 3 - Blocking] Die Messung brauchte einen armierten Exchange-Pfad**
- **Found during:** Task 3
- **Issue:** Auf der laufenden Instanz ist der Exchange-Pfad aus gutem Grund nicht konfiguriert. Der Handler antwortet dann mit dem benannten Ergebnis, bevor die Regel läuft, also gibt es keinen gefallenen Schritt und damit kein Längenorakel. Ohne Armierung wäre die Messung nicht möglich gewesen.
- **Fix:** Die ExApp wurde für die Dauer des Laufs mit vier `NC_MCP_EXCHANGE_*`-Variablen registriert (Issuer auf `.invalid`, also ohne jede ausgehende Wirkung: ein Token, das an `token_shape` fällt, erreicht den Schlüsselsatz-Abruf nie), danach mit genau der Registrierung aus `scripts/bootstrap_exapp.sh` wiederhergestellt. Das Mess-Skript lag außerhalb von `src/` und ist gelöscht.
- **Files modified:** keine (Laufzeitzustand der Testtopologie)
- **Verification:** siehe die Gegenprobe oben, die ExApp antwortet wieder mit dem nicht konfigurierten Ergebnis, und `docker inspect` zeigt keine `NC_MCP_EXCHANGE_*`-Variable mehr.
- **Committed in:** nichts im Repository

---

**Total deviations:** 4 auto-fixed (2 fehlende kritische Funktionalität, 2 blockierend)
**Impact on plan:** Kein Scope Creep. Deviation 1 und 2 halten zwei Texte wahr, die sonst still falsch geworden wären, Deviation 3 ist die Folge des vierten Kommandos in einer Datei, die der Plan ohnehin anfasst, Deviation 4 war die Voraussetzung der Messung, die Task 3 verlangt.

## Issues Encountered

- **Der Bootstrap lief fünf Minuten ins Leere.** `scripts/bootstrap_exapp.sh --nc35` braucht `HP_SHARED_KEY` in der Umgebung, sonst kann `docker compose -f compose.nc35.yml` die Datei nicht einmal interpolieren, jedes `occ` schlägt fehl und die Installationsschleife läuft in ihren Timeout. Der Wert steht in `.env.nc35`. Kein Containerschaden, die Topologie war unberührt.
- **Zwei Zustände außerhalb des Repositories haben sich geändert und sind nachgezogen.** Die NC-35-Instanz trägt die ExApp jetzt als 0.2.1 statt 0.1.13, weil `app_version()` die Version aus `appinfo/info.xml` liest. Die vom Bootstrap neu geschriebene `.env.nc35` (neue App-Passwörter für alice und bob, `APP_VERSION=0.2.1`) wurde in den Hauptcheckout zurückkopiert, damit die Integrationstests dort weiter gegen die laufende Instanz passen. Beide Dateien sind git-ignoriert.
- **`# noqa: S105` gehört an die Zeile, an der die Meldung beginnt.** Bei einer mehrzeiligen impliziten Verkettung ist das die erste Stringzeile und nicht die Zuweisung; auf der Zuweisung meldet ruff zusätzlich `RUF100`.

## Verification

Alle Gates grün vor jedem Commit, der letzte Stand:

- `uv run ruff check .` : All checks passed
- `uv run ruff format --check .` : 270 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` : 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py` : ohne Befund, und die drei Einträge aus 24-05 sind entfernt
- `uv run pytest -q` : vollständig grün
- `uv run pytest tests/contract -q` : grün
- `grep -c "16384" src/mcp_connector/exapp/exchange_check.py` : 0
- `command_schemes()` : 4 Einträge, `execute_handler` aus `EXCHANGE_CHECK_PATH` abgeleitet, `arguments == []`, Modi `optional` und `none`

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Für Plan 24-09 (Doku):** A5 ist bestätigt. In `docs/token-exchange.md` gehört **keine** gemessene Obergrenze unterhalb von 8192 Byte; die relevante Umgebungsgrenze bleibt Apaches 8190 Byte auf dem `Authorization`-Header aus 24-RESEARCH.md. Dazu gehört die Prozesslisten-Warnung der Optionsbeschreibung in die Doku, und der Satz, dass der Trockenlauf zum ExApp-Betrieb gehört und der Standalone-Betrieb keine zweite Oberfläche bekommt (offene Frage 2 der Recherche, hier so entschieden und in `oauth/exchange_dryrun.py` bereits so geschrieben).
- **Für Plan 24-07 (EXCH-07):** die NC-35-Topologie läuft, die ExApp ist als 0.2.1 registriert und enabled, `.env.nc35` ist im Hauptcheckout aktuell. Wer den Exchange-Pfad dort armiert, muss die ExApp erneut mit den `NC_MCP_EXCHANGE_*`-Variablen registrieren; der Weg ist in Deviation 4 beschrieben.
- Keine Blocker.

## Self-Check: PASSED

Alle sieben genannten Dateien existieren, alle fünf Commits stehen in der Historie dieses
Worktrees (`d005d66`, `b418506`, `693645f`, `122cf97`, `40ae8ae`), und der Arbeitsbaum ist
sauber.

## TDD Gate Compliance

Beide TDD-Tasks haben ihre Tore in der richtigen Reihenfolge: `test(...)` vor `feat(...)`,
je mit einem beobachteten roten Lauf dazwischen (Task 1: ImportError auf
`mcp_connector.exapp.exchange_check`; Task 2: sechs fehlgeschlagene Fälle). Ein
REFACTOR-Commit war in beiden Fällen nicht nötig, weil die GREEN-Fassung nichts hinterließ,
das aufzuräumen gewesen wäre.

---
*Phase: 24-audit-anschluss-und-nachweis*
*Completed: 2026-09-24*

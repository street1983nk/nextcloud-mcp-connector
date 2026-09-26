---
phase: 22-konfiguration-kette-und-drosselung
plan: 01
subsystem: auth
tags: [configuration, token-exchange, keycloak, startup-refusal, namespace, off-by-default]

requires:
  - phase: 21-exchange-verifier (21-01, 21-02)
    provides: "ExchangeSettings mit allen Validierungsregeln im __post_init__, DEFAULT_EXCHANGE_ALGORITHMS, ExchangeTokenChecker"
provides:
  - "config: Namensraum NC_MCP_EXCHANGE_* (acht Namen), exchange_enabled nach dem Muster von audit_log_enabled, DEFAULT_EXCHANGE_ACCOUNT_CLAIM, EXCHANGE_VARIABLES als einzige Liste"
  - "oauth/chain.py: load_exchange_config liefert eine validierte ExchangeConfig (ExchangeSettings plus account_claim), None oder eine benannte ToolError; DEFAULT_JWKS_PATH ohne Discovery-Abruf"
  - "Startabweisung in beide Richtungen in build_exapp_app, entry_oauth.load_settings und build_oauth_app, plus genau eine INFO-Zeile ohne gelesenen Wert"
affects: [22-02-kette, 22-03-drosselung, 23-konto-mapping, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Ab Werk ausgeschalteter Schalter in der Richtung von audit_log_enabled: unbekannter Wert bleibt aus und die Warnung nennt nur den Variablennamen"
    - "Namensraum als eine Tupel-Konstante (EXCHANGE_VARIABLES), gegen die der Leser einen konfigurierten aber nicht bewaffneten Pfad prüft; ein Test hält Konstantenmenge und Liste gleich"
    - "Jede ValueError aus Phase 21 wird an genau einer Stelle zur ToolError übersetzt; die Regeln werden nicht zweitgeschrieben"
    - "Kein Variablenname als Literal in chain.py: jeder kommt aus config, auch im Hinweistext (f-String)"

key-files:
  created:
    - src/mcp_connector/oauth/chain.py
    - tests/unit/test_oauth_exchange_chain.py
  modified:
    - src/mcp_connector/config.py
    - src/mcp_connector/entry_exapp.py
    - src/mcp_connector/entry_oauth.py
    - tests/unit/test_config.py
    - tests/unit/test_exapp_entry.py
    - tests/unit/test_entry_oauth.py
    - CHANGELOG.md

key-decisions:
  - "Eine gesetzte, aber leere Variable des Namensraums ist bei bewaffnetem Schalter eine ToolError und kein Default: eine Zeile, die dasteht und nichts sagt, ist ein Tippfehler oder ein halb gefülltes Template"
  - "Die INFO-Zeile steht in load_settings; build_oauth_app ruft den Leser nur dann selbst, wenn ihm fertige Settings hereingereicht wurden. So sind beide Aufrufwege geprüft und es bleibt bei genau einer Zeile je Start"
  - "Die vier Deploy-Namen stehen in tests/unit/test_exapp_entry.py wörtlich (nicht als config-Konstante), weil dort der Vertrag zur Deploy-Umgebung hängt; ein Test hält sie gegen config.EXCHANGE_VARIABLES"

requirements-completed: [CONF-01]

duration: 25min
completed: 2026-09-19
---

# Phase 22 Plan 01: Konfigurationsfläche und Aus-Zustand Summary

**Der Exchange-Pfad hat einen eigenen Namensraum `NC_MCP_EXCHANGE_*` mit ausdrücklichem Schalter, dokumentierten Defaults für Audience, Konto-Claim, JWKS-URL und Algorithmen, und eine Startabweisung in beide Richtungen; im Werkszustand ändert sich nichts, und ein Test misst das statt es zu behaupten**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-19T08:26Z (erster Task-Commit 08:32Z)
- **Completed:** 2026-09-19T08:51Z
- **Tasks:** 3 (je RED und GREEN einzeln committet)
- **Files modified:** 9 (2 neu, 7 geändert)

## Accomplishments

- `config.py` traegt den Namensraum: acht `ENV_EXCHANGE_*`-Konstanten, `DEFAULT_EXCHANGE_ACCOUNT_CLAIM = "sub"` mit der Begründung als `#:`-Kommentar (der einzige Claim, den Keycloak in jedes getauschte Token schreibt, jeder andere hängt an einer offenen F13-Antwort) und `EXCHANGE_VARIABLES` als die eine Liste, gegen die geprüft wird. `exchange_enabled` ist wörtlich nach `audit_log_enabled` gebaut: ab Werk aus, ein unverstandener Wert bleibt aus und die Warnung nennt Variable und verstandene Schreibweisen, nie den Wert.
- Der Aus-Zustand ist gemessen: `select_mode` liefert mit vollständig gesetztem Namensraum genau die fünf Modi von heute (stdio, exapp, oauth, http_static_bearer, http_passthrough), und ein Test hält die `Mode`-Literalmenge bei fünf Einträgen ohne "exchange". `git diff` auf `config.py` zeigt null entfernte Zeilen: es kam nur etwas dazu.
- `oauth/chain.py` (229 Zeilen) liest die Umgebung zu einer validierten `ExchangeConfig` (die `ExchangeSettings` aus Phase 21 plus `account_claim`), zu `None` oder zu einer benannten `ToolError`. `DEFAULT_JWKS_PATH` wird an den Issuer gehängt, statt Discovery abzurufen: ein ausgehender Abruf beim Start macht eine Anbieterstoerung zum Startfehler, und die Gleich-Origin-Regel aus Phase 21 prüft den zusammengesetzten Wert genau wie einen von Hand gesetzten.
- Die Startabweisung geht in beide Richtungen: bewaffneter Schalter ohne `NC_MCP_EXCHANGE_ISSUER` oder `NC_MCP_EXCHANGE_AZP` bricht ab (T-22-01), jede gesetzte Variable des Namensraums ohne Schalter bricht ebenfalls ab (T-22-02). Beides fällt in die bestehenden `except ToolError`-Zweige der beiden `main`-Funktionen und wird dort zu Exitcode 2.
- Die Audience hat als Default die Resource-URL dieser Instanz (`public_url` plus `/mcp`), nie ein generisches `nextcloud` (T-22-03): ein Token für Instanz A hält damit nicht an Instanz B.
- Kein Wert aus der Umgebung steht in einer Meldung oder Logzeile (T-22-04). `chain.py` loggt gar nicht, `grep -v '^\s*#' chain.py | grep -c 'NC_MCP_EXCHANGE'` ergibt 0 (jeder Name kommt aus `config`, auch im Hinweistext), und die INFO-Zeile der Einstiegspunkte sagt nur, dass der Pfad bewaffnet ist. Ein Test faehrt den Bau mit Kanarienwerten ("secret-tenant") und prüft jede Logzeile des Laufs.
- 19 Testfunktionen (55 Faelle mit Parametrisierung) in `tests/unit/test_oauth_exchange_chain.py`, keine oeffnet einen Socket, keine setzt `os.environ` außer der einen, die genau das beweisen muss.

## Task Commits

Each task was committed atomically (TDD: RED und GREEN getrennt):

1. **Task 1: Namensraum und Schalter in config.py** - RED `d3f9db2` (test), GREEN `08b5385` (feat) - RED belegt: 26 fallende Tests, AttributeError nennt `exchange_enabled`, `EXCHANGE_VARIABLES`, `DEFAULT_EXCHANGE_ACCOUNT_CLAIM`
2. **Task 2: load_exchange_config in oauth/chain.py** - RED `b08d9a7` (test), GREEN `857b769` (feat) - RED belegt: ImportError, `chain` existierte nicht; GREEN 55 Faelle grün
3. **Task 3: Startabweisung in beiden Einstiegspunkten** - RED `d4dd9ee` (test), GREEN `2d846f3` (feat) - RED belegt: 6 fallende Tests (3x DID NOT RAISE ToolError, 3x fehlende INFO-Zeile)

## Files Created/Modified

- `src/mcp_connector/oauth/chain.py` (neu, 229 Zeilen) - Moduldocstring mit der Begründung der eigenen Datei, der Arbeitsteilung zu `exchange.py` und der Default-Liste; `DEFAULT_JWKS_PATH`, `ExchangeConfig`, `load_exchange_config`, drei private Helfer (`_refuse_a_disarmed_configuration`, `_required`, `_optional`, `_allowlist`)
- `tests/unit/test_oauth_exchange_chain.py` (neu, 254 Zeilen) - 19 Testfunktionen: Aus-Zustand, Pflichtwerte, Defaults, Kommatrennung, Übersetzung jeder Phase-21-Regel, Leak-Kontrolle, Prozessumgebung, Unveränderlichkeit
- `src/mcp_connector/config.py` - acht Konstanten, `DEFAULT_EXCHANGE_ACCOUNT_CLAIM`, `EXCHANGE_VARIABLES`, `exchange_enabled`; nichts Bestehendes geändert
- `src/mcp_connector/entry_exapp.py` - ein Aufruf in `build_exapp_app` unmittelbar nach den Sicherheitseinstellungen, plus die eine INFO-Zeile
- `src/mcp_connector/entry_oauth.py` - Aufruf in `load_settings`, zweiter Aufruf in `build_oauth_app` für den Weg mit fertigen Settings, `_announce_exchange_path` als gemeinsame Zeile
- `tests/unit/test_config.py` - 13 neue Testfunktionen (Schalter, Namensraum, Aus-Zustand von `select_mode`, `Mode`-Literalmenge, Konto-Claim-Default)
- `tests/unit/test_exapp_entry.py` - 5 neue Tests inklusive Deploy-Namen-Pin
- `tests/unit/test_entry_oauth.py` - 6 neue Tests (load_settings und build_oauth_app)
- `CHANGELOG.md` - `### Added` im `[Unreleased]`-Block: Namensraum, Werkszustand aus, die Pflichtwerte und die vier Defaults; die Platzhalterzeile ist dem Abschnitt gewichen

## Decisions Made

- **Leere gesetzte Variable ist ein Fehler, kein Default:** `_optional` wirft eine `ToolError`, wenn eine Variable des Namensraums dasteht und leer ist. Begründung am Code: jede dieser Zeilen entscheidet etwas (welcher Host die Schlüssel hält, welche Audience ein Token nennen muss, welcher Claim das Konto nennt), und ein stiller Default auf eine leere Zeile ist derselbe Halbzustand, den der Plan abweist. Im ausgeschalteten Zustand zählt eine leere Variable weiterhin als nicht gesetzt (sonst könnte ein leerer Eintrag in einer Compose-Datei einen Start verhindern, der heute laeuft).
- **Eine INFO-Zeile je Start:** `load_settings` meldet, `build_oauth_app` meldet nur, wenn es `load_settings` nicht selbst gerufen hat. Damit sind beide Aufrufwege geprüft (der Plan verlangt die doppelte Validierung ausdrücklich) und es steht trotzdem genau eine Zeile im Log.
- **`StandaloneSettings` bleibt unberührt,** wie im Plan verlangt: ein Feld, das heute niemand liest, fällt dem vulture-Gate zur Last. Plan 22-02 nimmt es auf, wenn der Verifier gebaut wird.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Heredoc-Schreibweg für die neue Testdatei**
- **Found during:** Task 2
- **Issue:** Der Bash-Heredoc brach bei der langen Testdatei ab ("unexpected EOF"), die Datei wurde nicht angelegt
- **Fix:** Datei über das Write-Werkzeug angelegt, Anhänge an bestehende Testdateien über ein kurzes Python-Skript, das die Zeilenenden der Zieldatei übernimmt (das Repo hat gemischte EOL: `src/` ist CRLF, `tests/` LF)
- **Files modified:** keine über den Plan hinaus
- **Verification:** `uv run ruff format --check .` still, 251 Dateien formatiert

### Kriterien-Interpretationen (dokumentiert, nicht stillschweigend)

**2. [Kriterium erfüllt, aber anders als wörtlich] `grep -c "NC_MCP_EXCHANGE" tests/unit/test_exapp_entry.py` ist mindestens 4**
- **Found during:** Task 3 (Akzeptanzkriterien)
- **Issue:** Die Tests waren zunaechst durchgehend über `config.ENV_EXCHANGE_*` geschrieben (Stil der Datei), womit der Literal-grep 0 ergab
- **Fix:** Die vier Namen, die ein Betreiber in eine Deploy-Umgebung schreibt, stehen jetzt wörtlich in `EXCHANGE_ENV`, mit Begründung im Kommentar (dort hängt der Vertrag zur Deploy-Doku, eine Konstante wuerde einer Umbenennung still folgen). Ein zusätzlicher Test hält diese Literale gegen `config.EXCHANGE_VARIABLES`, damit die Doppelführung nicht auseinanderlaufen kann.
- **Verification:** `grep -c "NC_MCP_EXCHANGE" tests/unit/test_exapp_entry.py` ergibt 4; neuer Test `test_the_deploy_names_of_the_exchange_namespace_are_the_ones_of_config` grün

**3. [Kriterium präzisiert] `grep -c "load_exchange_config" src/mcp_connector/entry_exapp.py` ergibt 1**
- **Found during:** Task 3
- **Issue:** Das Kriterium verlangt genau 1, der erklaerende Kommentar daneben haette den Namen ein zweites Mal genannt
- **Fix:** Der Kommentar beschreibt den Leser, ohne den Funktionsnamen zu wiederholen; in `entry_oauth.py` stehen die verlangten zwei Aufrufe (beide Aufrufwege)
- **Verification:** 1 bzw. 2 Treffer, wie verlangt

---

**Total deviations:** 3 (1 blockierender Werkzeugbefund auto-behoben, 2 dokumentierte Kriterien-Präzisierungen)
**Impact on plan:** Keine Scope-Ausweitung, kein Eingriff außerhalb der vier geplanten `src/`-Dateien.

## Issues Encountered

- Keine. Der Scope-Fence hielt: `oauth/verifier.py`, `oauth/exchange.py`, `oauth/jwks.py`, `oauth/throttle.py`, `exapp/middleware.py` und `deps.py` sind unberührt, `select_mode` hat keinen sechsten Modus.

## TDD Gate Compliance

- Task 1: RED `d3f9db2` (26 fallende Tests), GREEN `08b5385`
- Task 2: RED `b08d9a7` (ImportError auf `chain`), GREEN `857b769`
- Task 3: RED `d4dd9ee` (6 fallende Tests), GREEN `2d846f3`
- Kein REFACTOR-Schritt nötig; `ruff format` lief vor jedem Commit.

## Verification (Plan-Ebene)

1. `uv run pytest tests/unit tests/contract -q`: 3790 passed, 33 skipped, 0 failed (volle Suite, kein Subset)
2. `uv run ruff check .` und `uv run ruff format --check .`: still (251 Dateien)
3. `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
4. `uv run vulture src scripts vulture_whitelist.py`: still
5. `python -c "import typing, mcp_connector.config as c; print(len(typing.get_args(c.Mode)))"`: 5
6. `git diff --name-only f88bbdd..HEAD | grep '^src/'`: genau `config.py`, `entry_exapp.py`, `entry_oauth.py`, `oauth/chain.py`
7. `grep -rn "check_resource_allowed" src/mcp_connector/oauth/chain.py`: nichts
8. `grep -v '^\s*#' src/mcp_connector/oauth/chain.py | grep -c 'NC_MCP_EXCHANGE'`: 0
9. Gedankenstrich-Kontrolle (lange Striche) über CHANGELOG.md und oauth/chain.py: keine Treffer
10. Live-Probe: die vollständig bewaffnete Beispielumgebung liefert `.../protocol/openid-connect/certs`, `https://mcp.example.org/mcp`, `sub`, `('RS256',)`; `load_exchange_config({})` liefert `None`; Issuer ohne Schalter endet in einer `ToolError`, die beide Variablennamen nennt

## User Setup Required

None - der Pfad ist ab Werk aus und verlangt von keiner bestehenden Installation eine Änderung.

## Next Phase Readiness

- Plan 22-02 kann die Kette in dieselbe Datei haengen: die Feldnamen (`ExchangeConfig.settings`, `ExchangeConfig.account_claim`) und die Form des Lesers stehen, der Aus-Zustand ist vor der Kette festgenagelt und von Tests gehalten.
- Offen für 22-02: `StandaloneSettings` um das Exchange-Feld ergänzen, wenn der Verifier gebaut wird; `claims_of` aus der vulture-Whitelist nehmen, sobald die Kette den Prüfer ruft.
- Für Phase 23 (MAP-01): `account_claim` wird bereits gelesen und validiert, aber von niemandem ausgewertet.
- Für Phase 24 (EXCH-08): die Einrichtungsdoku unter `docs/` fehlt bewusst; dokumentiert ist bisher im Moduldocstring von `chain.py`, in den `#:`-Kommentaren von `config.py` und im CHANGELOG.

---
*Phase: 22-konfiguration-kette-und-drosselung*
*Completed: 2026-09-19*

## Self-Check: PASSED

- Alle erzeugten und geänderten Dateien liegen auf der Platte (chain.py, test_oauth_exchange_chain.py, SUMMARY)
- Alle sieben Commits (d3f9db2, 08b5385, b08d9a7, 857b769, d4dd9ee, 2d846f3, e3de0e3) stehen in der Historie
- Alle Gates nach dem letzten Task erneut gefahren: volle Suite 3790 passed / 33 skipped, ruff still, pyright 0/0/0, vulture still

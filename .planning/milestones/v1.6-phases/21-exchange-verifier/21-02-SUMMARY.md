---
phase: 21-exchange-verifier
plan: 02
subsystem: auth
tags: [keycloak, jws, pyjwt, audience, azp, token-exchange, oracle-free, log-leak-gate]

requires:
  - phase: 21-exchange-verifier (21-01)
    provides: "oauth/exchange.py als freistehender Prüfkern (ExchangeRefused, ExchangeSettings, ExchangeTokenChecker), REQUIRED_CLAIMS mit verify_aud=False als benannte Stelle, Testbaukasten (token/claims/serve/checker_for)"
provides:
  - "audience_holds: exakte Gleichheit oder exakte Listen-Mitgliedschaft, compare_digest auf UTF-8-Bytes, ein Nicht-String-Eintrag macht die Liste unbrauchbar, eine leere Liste hält nie"
  - "azp in REQUIRED_CLAIMS plus Allowlist-Mitgliedschaft ohne frühen Abbruch: die handelnde Partei als Ersatz für das fehlende act in Keycloak Standard Token Exchange V2"
  - "Negativkorpus mit 12 bewusst danebengebauten Fällen (eigener zweiter Realm mit eigenem Schlüssel und eigener JWKS-Route), Orakel-Beweis über type(exc)/str(exc)/args, Leak-Gate über caplog auf DEBUG"
  - "Import-Gate als Test: oauth/exchange.py importiert weder check_resource_allowed noch irgendetwas aus dem mcp-SDK"
affects: [22-konfiguration-und-kette, 23-konto-mapping, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Fremde Audience: eigener Exaktvergleich statt verify_aud, weil PyJWTs strict_aud (gemessen an jwt/api_jwt.py 2.14.0) beidseitig Einzel-Strings verlangt und der Nicht-Strict-Modus eine Oder-Verknüpfung über Listen ist"
    - "Vergleiche auf angreiferbestimmten Werten ohne frühen Abbruch: jeder Listeneintrag wird angesehen, compare_digest je Eintrag"
    - "Kanarienwerte im Leak-Gate: auffällige, repo-weit einmalige sub/email/preferred_username/azp-Werte, damit der caplog-Sweep nicht an Allerweltswörtern vorbeiläuft"

key-files:
  created: []
  modified:
    - src/mcp_connector/oauth/exchange.py
    - tests/unit/test_oauth_exchange.py

key-decisions:
  - "Ein Nicht-String-Eintrag in der aud-Liste macht die ganze Liste unbrauchbar (fail closed), statt übersprungen zu werden: die Form der Liste ist angreiferbestimmt"
  - "Die check_resource_allowed-Begründung steht als Kommentar, dessen Zeile verifier.py mitnennt, damit das repo-weite grep-Gate die Zeile herausfiltern kann"
  - "Task 2 als reiner test-Commit: beide Gates (Orakel, Leak) fanden keine Lücke im Modul, also gab es keine Modulkorrektur zu committen"

patterns-established:
  - "Messkommentare statt Behauptungen: die Begründung am Audience-Vergleich zitiert den installierten PyJWT- und SDK-Quelltext, nicht die Doku"

requirements-completed: [EXCH-03]

duration: 20min
completed: 2026-09-19
---

# Phase 21 Plan 02: Audience exakt, azp-Allowlist, Negativkorpus Summary

**Exakter Audience-Vergleich als audience_holds (Präfixfall abgewiesen, exakte Listen-Mitgliedschaft), azp-Allowlist ohne frühen Abbruch als Ersatz für das fehlende act, dazu ein 12er-Negativkorpus mit gemessenem Ablehnungs-Orakel und caplog-Leak-Gate**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-19T05:57:36Z
- **Completed:** 2026-09-19T06:17:49Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `audience_holds(claim, expected)`: eine Zeichenkette hält bei exakter Gleichheit, eine Liste nur bei exakter Mitgliedschaft des einen konfigurierten Werts; jeder Nicht-String-Eintrag macht die Liste unbrauchbar, eine leere Liste hält nie. Vergleich mit `hmac.compare_digest` auf UTF-8-Bytes, ohne frühen Abbruch. Der Präfix-Gegenbeweis (`aud = <konfiguriert>/tenant-b` wird abgewiesen) steht als eigener Test.
- `azp` steht in `REQUIRED_CLAIMS` (Keycloak erzwingt den Claim beim Tausch) und wird gegen `settings.azp_allowed` geprüft, über alle Einträge ohne frühen Abbruch; ein unbekanntes, fehlendes oder nicht-string-förmiges `azp` wird abgewiesen, auch bei fehlerfreier Signatur. Eine Zwei-Einträge-Allowlist nimmt beide an und einen dritten Wert nicht.
- Der Messauftrag ist erfüllt und steht als Kommentar im Modul: `check_resource_allowed` vergleicht den Pfad als Präfix (gemessen an `mcp/shared/auth_utils.py`), PyJWTs `strict_aud` verlangt beidseitig Einzel-Strings (gemessen an `jwt/api_jwt.py::_validate_aud`, 2.14.0) und kann "exakt enthalten in einer Liste" nicht ausdrücken; `verify_aud` bleibt aus, `aud` bleibt in `require`.
- Negativkorpus mit 12 sprechenden Fall-Ids (fehlendes azp, Mehrfach-aud ohne Zielwert, Präfix-aud, ID-Token, zweiter Realm mit eigenem Issuer/Schlüssel/JWKS-Route, unbekannter kid, falscher Schlüssel, HS256, alg=none, abgelaufen, nbf in der Zukunft, überlange Lebensdauer). Der Orakel-Test misst über alle Fälle: gleicher Typ, `str(exc) == ""`, `exc.args == ()`. Das Leak-Gate fährt den Korpus mit caplog auf DEBUG und findet weder den Tokenstring noch eines seiner Punkt-Segmente noch die Kanarienwerte (sub, email, preferred_username, azp) in irgendeiner Logzeile; mindestens eine Warnung je Fall belegt, dass der Logger nicht still war.
- Import-Gate als Test: die Importe von `oauth/exchange.py` werden per AST gelesen; weder `check_resource_allowed` noch ein `mcp.*`-Modul darf darunter sein.

## Task Commits

Each task was committed atomically:

1. **Task 1: Audience exakt und azp als Allowlist** - `1aaf2a3` (feat) - RED im Lauf belegt (Exitcode 1, 21 fallende Tests: 11x audience_holds AttributeError, 5x aud-Checker DID NOT RAISE, 4x azp DID NOT RAISE, 1x REQUIRED_CLAIMS), dann GRÜN mit 71 Tests
2. **Task 2: Negativkorpus, Orakel, Leak-Gate** - `ff28353` (test) - beide Gates fanden keine Lücke im Modul, 85 Tests grün

## Files Created/Modified

- `src/mcp_connector/oauth/exchange.py` - audience_holds mit Messkommentar, azp in REQUIRED_CLAIMS plus Allowlist-Prüfung, Docstring-Absatz zur instanzspezifischen Audience-Konvention (Vorschlag an F13: eine Keycloak-Client-Id je Connector-Instanz, im Zweifel die Resource-URL der Instanz); 353 Zeilen
- `tests/unit/test_oauth_exchange.py` - 85 Tests: audience_holds-Parametrisierung (11 Fälle), Checker-Tests für aud und azp, Import-Gate, Negativkorpus (12 Fälle), Orakel-Test, Leak-Gate; 820 Zeilen

## Decisions Made

- Ein Nicht-String-Eintrag in der aud-Liste macht die ganze Liste unbrauchbar statt übersprungen zu werden: fail closed auf angreiferbestimmter Form.
- Die Kommentarzeile zu `check_resource_allowed` nennt `verifier.py` auf derselben Zeile; so bleibt das repo-weite grep-Gate des Plans für den Kommentar still und die Funktion selbst bleibt aus dem Modul heraus (Import-Gate als Test).
- `azp`-Prüfung liest als "erlaubte handelnde Partei" (Kommentar nennt den Grund): `act` löst die Rolle ab, sobald Keycloak es liefert.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ruff E501/Format auf neuen Kommentar- und Korpuszeilen**
- **Found during:** Task 1 und Task 2 (Gates vor dem Commit)
- **Issue:** Eine Kommentarzeile (101 Zeichen) und eine Korpuszeile (108 Zeichen) über der 100er-Grenze; ruff format wollte zwei Stellen umbrechen
- **Fix:** Zeilen gekürzt bzw. umgebrochen, `ruff format` über die Testdatei
- **Files modified:** src/mcp_connector/oauth/exchange.py, tests/unit/test_oauth_exchange.py
- **Verification:** `uv run ruff check .` und `uv run ruff format --check .` still
- **Committed in:** 1aaf2a3 bzw. ff28353 (Task-Commits)

### Kriterien-Interpretationen (dokumentiert, nicht stillschweigend)

**2. [Kriterium wörtlich unerfüllbar] `grep -rn "check_resource_allowed" src/ | grep -vc "verifier.py"` ergibt 6, nicht 0**
- **Found during:** Task 1 (Akzeptanzkriterien)
- **Issue:** `src/mcp_connector/oauth/provider.py` (der eigene AS-Pfad, Vorbestand aus früheren Phasen) nutzt `check_resource_allowed` an 4 Stellen, wo die Präfixsemantik für eigene Tokens korrekt ist; dazu 2 pycache-Binärtreffer. Der Scope-Fence verbietet Änderungen an anderen Dateien, und dort wäre eine Änderung auch falsch.
- **Fix:** Die Absicht des Kriteriums ist erfüllt und belegt: im Exchange-Pfad 0 Nicht-Kommentar-Treffer (`grep -v '^\s*#' ... | grep -c` ergibt 0), der einzige Kommentar-Treffer nennt `verifier.py` auf derselben Zeile, und das Import-Gate steht als Test.
- **Files modified:** keine über den Plan hinaus
- **Verification:** Import-Gate-Test grün, Kriterium 4 (Nicht-Kommentar-Treffer 0) erfüllt

**3. [Kriterium interpretiert] `%s`-Zählung**
- **Found during:** Task 2 (Akzeptanzkriterien)
- **Issue:** Das Kriterium verlangt, dass die `%s`-Zahl "genau der Zahl der `_refused`-Aufrufstellen mit festem Text entspricht". Das Modul hat genau eine `%s`-Zeile (die `_refused`-Fabrik), durch die alle 17 Aufrufstellen mit festen Literalen laufen.
- **Fix:** Interpretation: jedes `%s` im Modul steht für einen festen `_refused`-Grund und nie für einen Claim-Wert. Genau das ist erfüllt (1 `%s`-Zeile, alle Aufrufstellen Literale, Leak-Gate misst es zusätzlich).
- **Verification:** `grep -v '^\s*#' ... | grep -c "%s"` ergibt 1; Leak-Gate grün

**4. [Commit-Form, wie 21-01] RED im Lauf belegt statt eigener roter Commit**
- **Found during:** Task 1
- **Issue:** Die Executor-Vorgabe verlangt vor jedem Commit die volle grüne Suite; ein separater roter test-Commit wäre zwangsläufig rot gewesen (pyright hätte zudem das fehlende `audience_holds` gemeldet)
- **Fix:** RED im Lauf belegt (Exitcode 1, genau die 21 erwarteten neuen Tests fielen, siehe Task Commits), dann Tests und Umsetzung zusammen in 1aaf2a3. Task 2 war als Messgate über bereits implementiertes Verhalten sofort grün (das ist der gewollte Ausgang: "Findet eines der beiden Gates eine Lücke, wird das Modul korrigiert", es fand keine) und ging als reiner test-Commit ff28353.
- **Verification:** RED-Ausgabe dokumentiert, Gate-Lauf je Commit dokumentiert

---

**Total deviations:** 4 (1 blockierender Gate-Befund auto-behoben, 2 dokumentierte Kriterien-Interpretationen, 1 Commit-Form-Anpassung)
**Impact on plan:** Keine Scope-Ausweitung; der Prüfkern folgt dem Plan wörtlich, die Interpretationen betreffen nur Zählweisen der Akzeptanzkriterien gegen Vorbestand.

## Issues Encountered

- Die `state.add-decision`-Aufrufe des SDK fügen einen Em-Dash in die STATE.md-Zeilen ein; nach den SDK-Aufrufen wurde die Datei geprüft und die Zeichen ersetzt (bekannte Lehre).

## TDD Gate Compliance

- Task 1 RED: im Lauf belegt (Exitcode 1, 21 fallende Tests, AttributeError nennt `audience_holds`), GREEN in `1aaf2a3`; kein separater roter Commit, weil die volle Suite vor jedem Commit grün sein muss (Präzedenz 21-01, Abweichung 3 dort)
- Task 2: Korpus, Orakel und Leak-Gate sind Messgates über in Task 1 und 21-01 implementiertes Verhalten; sie fanden keine Lücke, waren also sofort grün und gingen als test-Commit `ff28353`. Ein erzwungenes RED hätte das Modul absichtlich schwächen müssen, was der Plan ausdrücklich verbietet (nie den Test lockern, nur das Modul korrigieren).

## Verification (Plan-Ebene)

1. `uv run pytest tests/unit/test_oauth_exchange.py -q`: grün, 85 Tests (mindestens 40 verlangt)
2. `uv run pytest tests/unit tests/contract -q`: grün; volle Suite: 3666 passed, 33 skipped, 0 failed
3. `uv run ruff check .` und `uv run ruff format --check .`: still
4. `uv run pyright`: 0 errors, 0 warnings
5. `uv run vulture src scripts vulture_whitelist.py`: still
6. `grep -rn "check_resource_allowed" src/`: exchange.py nur als Kommentarzeile (nennt verifier.py), sonst verifier.py und der vorbestehende eigene AS-Pfad provider.py (siehe Abweichung 2)
7. `git diff --name-only 3a62cc6..HEAD`: genau src/mcp_connector/oauth/exchange.py und tests/unit/test_oauth_exchange.py

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 21 ist inhaltlich komplett (EXCH-02 + EXCH-03): der Prüfkern trägt alle Regeln, Phase 22 kann Kette und Konfiguration anhängen, ohne eine Prüfregel nachzureichen.
- Offen vor Phase 22: Verifier-Lauf und Audit über Phase 21 (`/gsd:verify-work 21`).
- Für Phase 22: `claims_of` aus der vulture-Whitelist nehmen, sobald die Kette den Prüfer ruft (Vermerk steht dort).

---
*Phase: 21-exchange-verifier*
*Completed: 2026-09-19*

## Self-Check: PASSED

- Beide geänderten Dateien liegen auf der Platte, SUMMARY existiert
- Beide Task-Commits (1aaf2a3, ff28353) stehen in der Historie
- Akzeptanzkriterien beider Tasks erneut ausgeführt und bestanden (zwei dokumentierte Interpretationen, siehe Abweichungen), Em-Dash-Kontrolle über SUMMARY, STATE, ROADMAP und REQUIREMENTS sauber

## Nachtrag: Audit-Fixes (2026-09-19)

Das Phase-21-Audit (`21-REVIEW.md`, tiefe Prüfung) fand 18 Befunde: 2 kritische, 11 Warnungen,
5 Hinweise. Vor dem Phasenabschluss abgearbeitet, Status je Befund steht am jeweiligen Eintrag
in `21-REVIEW.md`. Elf Commits, jeder mit einem Regressionstest, der vor dem Fix rot war:

| Commit | Befund | Inhalt |
|--------|--------|--------|
| `bfa777a` | CR-01, WR-02 | `MAX_TOKEN_BYTES` (8192) vor dem ersten Base64-Schritt, als Konstruktorparameter mit Default nach dem Muster von `jwks.py`; beide ungeprüften Parse-Schritte fangen nach Klasse statt nach Fehlerliste |
| `ca02bf9` | CR-02, WR-07 | `math.isfinite` für beide Zeitfelder, `isinstance`-Prüfung für alle fünf Zeichenkettenfelder |
| `12e0389` | WR-06 | jede Allowlist ist eine Sequenz nicht-leerer Strings, eine blanke Zeichenkette ist ein `ValueError` |
| `b0e6ead` | WR-01 | `TypeError` und `OverflowError` aus den Zeitclaims sind Ablehnungen; der falsche Kommentar richtiggestellt |
| `e17810e` | WR-03 | `_PreparsedJWT` reicht das Vorfilter-Ergebnis weiter, der Payload wird genau einmal geparst |
| `bc7e9b5` | WR-04 | `REQUIRED_CLAIMS` ist ein Tupel, Export bleibt |
| `4531200` | WR-05, IN-02 | leere Erwartung und leerer Claim halten nie; zwei Docstring-Sätze richtiggestellt |
| `2dfca3d` | WR-08 | Ablehnungen auf DEBUG, AUDIT-07 (Phase 24) im Docstring benannt; Leak-Gate sammelt am Logger statt über `caplog` |
| `3faa18e` | IN-01 | `secrets.compare_digest` wie im übrigen Repository, vom Import-Gate mitgeprüft |
| `be459fa` | IN-05 | vier strukturell kaputte Fälle im Negativkorpus als Regressionsanker |
| `291793b` | WR-09, WR-10, WR-11, IN-03 | eingeordnet statt gefixt, im Moduldocstring benannt |

**Mit Grund eingeordnet, nicht gefixt:**

- **WR-09 (Laufzeitklassen):** grobe Kostenklassen sind einem gestaffelten Prüfer inhärent, und
  die Staffelung ist der Grund, warum die billigen Klassen der Normalfall sind. Die Zusage im
  Moduldocstring ist jetzt auf das Ausnahmeobjekt eingegrenzt, der Laufzeitunterschied als
  bewusst hingenommen benannt; die Abtastrate deckelt die Drossel aus Phase 22.
- **WR-10 (voller Claim-Satz):** Phase 23 braucht den Claim, den sie auf ein Konto abbildet, und
  der muss nicht unter den sieben geprüften stehen. Der Docstring nennt die sieben und sagt vom
  Rest, dass er Transport ist.
- **WR-11 (client_credentials nicht unterscheidbar):** Keycloak-V2-Eigenschaft (kein `act`), als
  bekannte Grenze im Moduldocstring, als Punkt für die Planung von Phase 23 in `21-REVIEW.md`.
- **IN-03 (`sub`-Normalisierung):** gehört zur Kontoabbildung in Phase 23, am Code vermerkt.

**Gates vor jedem der elf Commits in einem Zug grün:** `uv run ruff check .`,
`uv run ruff format --check .`, `uv run pyright` (0 errors, 0 warnings, 0 informations),
`uv run vulture src scripts vulture_whitelist.py`, `uv run pytest -q` (volle Suite). Nach dem
letzten Commit: 3747 Tests gesammelt, davon 133 in `tests/unit/test_oauth_exchange.py` (vorher
85), grün in zufälliger und in fester Reihenfolge.

**Scope-Gate weiter dicht:** `git diff --name-only edb0f0e..HEAD` nennt
`src/mcp_connector/oauth/exchange.py`, `tests/unit/test_oauth_exchange.py` und
`vulture_whitelist.py` (Eintrag für `_decode_payload`, den PyJWT-Hook ohne eigenen Aufrufer),
unter `src/` genau eine Datei. `verifier.py`, `oidc.py`, `jwks.py` und `throttle.py` sind
unberührt; keine neue Konfigurationsfläche, kein Env-Zugriff.

**Lehren aus dem Durchgang:**

1. Eine Ausnahmeklasse, die eine Fremdbibliothek an einer Stelle fängt und an der anderen nicht
   (PyJWT: `RecursionError` am Header, nicht am Payload), ist kein Detail: wer ungeprüfte Bytes
   parst, fängt nach Klasse und nicht nach Fehlerliste.
2. `nan` besteht jede Vergleichsprüfung, weil jeder Vergleich falsch ist. Eine Zahlenprüfung
   ohne `math.isfinite` ist keine.
3. Ein Log-Gate über `caplog` ist im vollen Lauf von der Reihenfolge abhängig, sobald irgendwo
   `propagate = False` auf dem Paket-Logger gesetzt wird. Ein Handler am Logger unter Test ist es
   nicht. Der alte WARNING-Beweis war seit Phase 21-02 latent flatterhaft, ohne je rot zu werden.

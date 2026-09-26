---
phase: 21-exchange-verifier
plan: 01
subsystem: auth
tags: [keycloak, jws, pyjwt, jwks, token-exchange, typ-claim, clock-skew, fail-closed]

requires:
  - phase: 20-jwks-schicht-und-pyjwt-stand
    provides: "oauth/jwks.py als einzige Schlüsselsatz-Schicht (KeySet, same_origin, Allowlists), PyJWT 2.14 im Lock, refuse-Injektion als Vertrag"
provides:
  - "oauth/exchange.py: freistehender Prüfkern für ein fremdes Keycloak-JWS (ExchangeRefused, ExchangeSettings, ExchangeTokenChecker)"
  - "typ-Prüfung im Payload (Bearer) statt im Header; Header-typ toleriert JWT/at+jwt ohne Gross-Klein, verlangt aber nichts (Keycloak 19419)"
  - "Toleranz 30 s (halbiert gegenüber dem ID-Token-Fluss), maximale Lebensdauer und maximales Alter 900 s als eigene Regeln auf der injizierten Wanduhr"
  - "iss-Vorfilter auf dem ungeprüften Payload: ein fremder Issuer löst null ausgehende JWKS-Abrufe aus (per respx call_count gemessen)"
  - "tests/unit/test_oauth_exchange.py: 36 Testfunktionen (48 Fälle), jede EXCH-02-Regel einzeln, ohne Netz und ohne Server"
affects: [21-exchange-verifier (21-02), 22-konfiguration-und-kette, 23-konto-mapping]

tech-stack:
  added: []
  patterns:
    - "Zwei getrennte, injizierbare Uhren: monotone Uhr nur an die Schlüsselsatz-Schicht, Wanduhr nur für eigene Claim-Regeln (Pitfall 6, dritter Teil)"
    - "Vorfilter, der nur ablehnen kann: ungeprüfter iss-Vergleich vor dem Schlüsselzugriff, signaturgedeckte Wiederholung durch jwt.decode(issuer=)"
    - "_refused-Fabrik wörtlich in der oidc-Form: fester Logtext, detailfreie Ausnahme, nie ein Claim-Wert in einer Zeile"

key-files:
  created:
    - src/mcp_connector/oauth/exchange.py
    - tests/unit/test_oauth_exchange.py
  modified:
    - vulture_whitelist.py

key-decisions:
  - "audience ist in ExchangeSettings genau eine Zeichenkette, nie eine Liste: der erwartete Wert kann nie zur Oder-Verknüpfung werden (Vergleich selbst kommt in 21-02)"
  - "jwks_origin als ausdrücklich benannte zweite Herkunft für geteilte Netze; die HTTPS-Gleich-Origin-Regel bleibt immer an, nur ihr Anker ist konfigurierbar"
  - "typ wird im Claim-Satz geprüft, nicht im Header: Keycloak setzt den Header je nach Client-Alter auf JWT oder at+jwt (Diskussion 19419), eine at+jwt-Pflicht wiese jedes echte Token ab"

patterns-established:
  - "Lebensdauer-Regeln als Abweisung, nie Kürzung: exp-iat und Alter je gegen MAX_TOKEN_LIFETIME_SECONDS, nicht-numerische Zeiten sind eine Abweisung und kein TypeError"

requirements-completed: [EXCH-02]

duration: 28min
completed: 2026-09-19
---

# Phase 21 Plan 01: Exchange-Prüfkern Summary

**Freistehender Keycloak-JWS-Prüfer in oauth/exchange.py: Issuer-Vorfilter ohne Abruf, Signatur über die Schlüsselsatz-Schicht, typ=Bearer im Payload, 30 s Toleranz mit 900 s Lebensdauer- und Altersgrenze, alles als eine detailfreie ExchangeRefused**

## Performance

- **Duration:** 28 min
- **Started:** 2026-09-19T05:25:28Z
- **Completed:** 2026-09-19T05:53:53Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Jede der sechs must_haves-Wahrheiten hat einen eigenen, direkt am Prüfkern laufenden Test: Annahme mit unverändertem sub, je eine Abweisung pro Regelverletzung, ID-Token fällt am Payload-typ, Uhrenversatz hält bei 20 s und fällt bei 45 s in beide Richtungen, unerreichbarer Schlüsselsatz ist fail-closed, fremder Issuer kostet null Abrufe.
- Der Prüfkern verdrahtet nichts: kein Import aus exapp/, oidc, verifier oder store, kein Umgebungszugriff, kein Konto, kein Transport. Konfiguration existiert nur als validierte ExchangeSettings (ValueError beim Bauen, nie stille Vorgabe).
- Abkühlzeit, Single-Flight und Fehlschlagpause kommen unverändert aus jwks.py; keine der in 20-REVIEW gefixten Eigenschaften wurde berührt (jwks.py, oidc.py, verifier.py ohne Diff).

## Task Commits

Each task was committed atomically:

1. **Task 1: Der Testkorpus zuerst, rot** - `e2eac0a` (test) - RED-Beleg: Exitcode 2, Ausgabe nennt mcp_connector.oauth.exchange
2. **Task 2: Der Prüfkern, grün** - `753c858` (feat) - 34 Fälle grün, alle Gates still
3. **Task 3: typ, Uhren, Lebensdauer, Vorfilter** - `2106ee2` (feat) - sechs neue Regeln, je zuerst rot belegt, dann grün

## Files Created/Modified

- `src/mcp_connector/oauth/exchange.py` - Der Prüfkern: ExchangeRefused, ExchangeSettings (frozen, slots, validiert), ExchangeTokenChecker.claims_of, Konstanten mit Begründung (283 Zeilen)
- `tests/unit/test_oauth_exchange.py` - 36 Testfunktionen / 48 Fälle gegen selbst erzeugte RSA-Schlüssel, respx-JWKS, Hand-Uhr (490 Zeilen)
- `vulture_whitelist.py` - claims_of bis zur Verkettung in Phase 22, mit Begründung

## Decisions Made

- RED-Import in Task 1 als `import mcp_connector.oauth.exchange as exchange`, damit die rote pytest-Ausgabe den vollen Modulnamen nennt (das automatische Verify-Kommando des Plans greppt auf den Punktpfad; die ImportError-Form von `from ... import` nennt ihn nicht). In Task 2 auf die im Plan genannte Form `from mcp_connector.oauth import exchange` zurückgestellt.
- `typ_expected` wird in `__post_init__` auf nicht-leer geprüft: sinnvolle Validierung im Stil der übrigen Felder, und das Feld ist damit vor seiner Verwendung in der typ-Prüfung gelesen.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ruff S105 auf den typ-Konstanten**
- **Found during:** Task 2 (Gates vor dem Commit)
- **Issue:** S105 meldet "Possible hardcoded password" für `ACCESS_TOKEN_TYP = "Bearer"` und `ID_TOKEN_TYP = "ID"` (Namensmuster TOKEN)
- **Fix:** Inline-noqa mit Begründung, exakt in der Repo-Form (`throttle.py: CLASS_TOKEN`, `provider.py: token_type`)
- **Files modified:** src/mcp_connector/oauth/exchange.py
- **Verification:** `uv run ruff check .` still
- **Committed in:** 753c858 (Task-2-Commit)

**2. [Rule 3 - Blocking] vulture meldet claims_of als ungenutzt**
- **Found during:** Task 2 (Gates vor dem Commit)
- **Issue:** `ExchangeTokenChecker.claims_of` wird bis Phase 22 nur von Tests gerufen, die vulture nicht scannt; der Plan hatte `typ_expected`/`ID_TOKEN_TYP` als Kandidaten genannt, getroffen hat es die Methode
- **Fix:** Whitelist-Eintrag mit Begründung und Ablaufvermerk (entfällt mit Phase 22), keine gesenkte Schwelle
- **Files modified:** vulture_whitelist.py
- **Verification:** `uv run vulture src scripts vulture_whitelist.py` still
- **Committed in:** 753c858 (Task-2-Commit)

**3. [Anpassung - TDD-Commit-Form] Task 3 als ein Commit statt test+feat**
- **Found during:** Task 3
- **Issue:** Die Executor-Vorgabe verlangt vor jedem Commit die volle grüne Suite; ein separater RED-Commit für die sechs Task-3-Tests wäre zwangsläufig rot gewesen (und pyright hätte die noch fehlende Konstante ACCEPTED_TYP_HEADERS gemeldet)
- **Fix:** RED-Zustand im Lauf belegt (genau die sechs neuen Regeln fielen: ID-Token-typ, fremder Header-typ, Lebensdauer, Alter, nicht-numerisches iat, Vorfilter-call_count), dann Tests und Umsetzung zusammen in 2106ee2 committet. Task 1 bleibt als eigener roter test-Commit bestehen; dort war die volle Suite ohne die gewollt rote Datei grün und pyright meldete erwartungsgemäß genau den fehlenden Import.
- **Files modified:** keine zusätzlichen
- **Verification:** Gate-Lauf je Commit dokumentiert
- **Committed in:** 2106ee2

---

**Total deviations:** 3 (2 blockierende Gate-Befunde auto-behoben, 1 dokumentierte Commit-Form-Anpassung)
**Impact on plan:** Keine Scope-Ausweitung; alle Fixes waren für die stillen Gates nötig, der Prüfkern selbst folgt dem Plan wörtlich.

## Issues Encountered

- Angehängte Whitelist-Zeilen hatten LF in einer CRLF-Datei (bekannte Repo-Lehre zu gemischten EOL); `ruff format` hat normalisiert, danach war `ruff format --check` still.

## TDD Gate Compliance

- RED-Gate: `e2eac0a` (test), Beleg: Exitcode 2, Ausgabe nennt mcp_connector.oauth.exchange, kein Tippfehler-Rot
- GREEN-Gate: `753c858` (feat) nach RED
- Task-3-Zyklus: RED im Lauf belegt (6 Fälle), GREEN in `2106ee2`; kein Refactor-Commit nötig

## Verification (Plan-Ebene)

1. `uv run pytest tests/unit/test_oauth_exchange.py -q`: grün, 48 Fälle aus 36 Testfunktionen (mindestens 24 verlangt)
2. `uv run pytest tests/unit tests/contract -q`: grün; volle Suite: 3629 passed, 33 skipped, 0 failed
3. `uv run ruff check .` und `uv run ruff format --check .`: still
4. `uv run pyright`: 0 errors, 0 warnings
5. `uv run vulture src scripts vulture_whitelist.py`: still
6. `git diff --name-only e2eac0a^..HEAD`: genau exchange.py, test_oauth_exchange.py, vulture_whitelist.py

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 21-02 kann direkt aufsetzen: der aud-Vergleich hat seinen benannten Kommentar an der decode-Stelle, azp steht validiert in den Settings (azp_allowed), der Negativkorpus-Baukasten (token/claims/serve/checker_for) liegt in der Testdatei bereit.
- Für Phase 22: `claims_of` aus der vulture-Whitelist nehmen, sobald die Kette den Prüfer ruft.

---
*Phase: 21-exchange-verifier*
*Completed: 2026-09-19*

## Self-Check: PASSED

- Beide erzeugten Dateien und die Whitelist-Aenderung liegen auf der Platte
- Alle drei Task-Commits (e2eac0a, 753c858, 2106ee2) stehen in der Historie
- Akzeptanzkriterien aller drei Tasks erneut ausgefuehrt und bestanden, Em-Dash-Kontrolle sauber

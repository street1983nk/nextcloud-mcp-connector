---
phase: 22-konfiguration-kette-und-drosselung
plan: 02
subsystem: auth
tags: [token-exchange, chain, transport-boundary, fail-closed, revocation, jwks]

requires:
  - phase: 20-jwks-schicht-und-pyjwt-stand
    provides: "KeySet mit Cache, Abkühlzeit und Wiederholsperre"
  - phase: 21-exchange-verifier
    provides: "ExchangeTokenChecker.claims_of und ExchangeRefused"
  - phase: 22-konfiguration-kette-und-drosselung (22-01)
    provides: "ExchangeConfig, load_exchange_config, Startabweisung und INFO-Zeile in beiden Einstiegspunkten"
provides:
  - "oauth/chain.py: ChainedVerifier, build_chain, looks_like_jws, EXCHANGE_CLAIM, dazu die beiden Zweig-Protokolle StoreBranch und ExchangeBranch"
  - "oauth/jwks.py: KeySet.forget (Cache leeren, Karenzstempel stehen lassen)"
  - "oauth/exchange.py: ExchangeTokenChecker.forget_keys als einzige neue Zeile"
  - "entry_exapp/entry_oauth: die Kette hängt an beiden Transportgrenzen, der Widerruf geht an die Kette"
  - "StandaloneSettings.exchange trägt die gelesene Konfiguration zum Anwendungsbau"
affects: [22-03-drosselung, 23-konto-mapping, 24-audit-und-doku]

tech-stack:
  added: []
  patterns:
    - "Strukturelle Weiche statt Rückfallebene: die Tokenform entscheidet vor jeder Prüfung, und beide Richtungen sind mit einer Attrappe belegt, die beim Aufruf sofort auffliegt"
    - "Der geprüfte fremde Claim-Satz reist unter genau einem verschachtelten Schlüssel, damit kein fremder Claim in den Store-Zweig zeigen kann"
    - "Zwei Zweig-Protokolle (StoreBranch, ExchangeBranch) in der Form von IdentitySource und ClientLookup: hereingereicht, nie nachgebaut, und damit in einem Test durch eine Attrappe ersetzbar"
    - "Widerruf über beide Schichten, aber nur über die Caches: die vor-authentischen Bremsen bleiben stehen"

key-files:
  created: []
  modified:
    - src/mcp_connector/oauth/chain.py
    - src/mcp_connector/oauth/jwks.py
    - src/mcp_connector/oauth/exchange.py
    - src/mcp_connector/entry_exapp.py
    - src/mcp_connector/entry_oauth.py
    - vulture_whitelist.py
    - tests/unit/test_oauth_exchange_chain.py
    - tests/unit/test_oauth_jwks.py
    - tests/unit/test_oauth_exchange.py
    - tests/unit/test_exapp_entry.py
    - tests/unit/test_entry_oauth.py

key-decisions:
  - "Die beiden Zweige sind Protokolle (StoreBranch, ExchangeBranch) und keine konkreten Klassen: pyright prüft auch tests/, und der Beweis dieses Plans verlangt Attrappen, die beim Aufruf auffliegen. Mit konkreten Annotationen hätte genau der Test, der die Zusage trägt, ein type: ignore gebraucht"
  - "build_chain nimmt env und config: config ist die beim Start gelesene Antwort, env ist die Quelle, aus der sonst gelesen würde. Ohne env würde build_chain im Aus-Zustand os.environ lesen statt der Mapping-Instanz, mit der die Anwendung gebaut wurde"
  - "StandaloneSettings bekommt das Feld exchange (der offene Punkt aus 22-01): so liest build_oauth_app den Namensraum je Aufbauweg genau einmal und die Kette wird aus derselben Antwort gebaut, die die INFO-Zeile ausgelöst hat"
  - "forget() leert nur den Schlüssel-Cache; Abkühlzeit und Wiederholsperre bleiben, sonst wäre ein Widerruf ein Weg, die vor-authentische Bremse von aussen zu lösen (T-22-10)"

requirements-completed: [EXCH-04]

duration: 35min
completed: 2026-09-19
---

# Phase 22 Plan 02: Kette hinter der Transportgrenze Summary

**Der Exchange-Prüfer hängt als Kette hinter der unveränderten Transportgrenze; die Weiche fällt strukturell über die Tokenform vor jeder Prüfung, ein Fehlschlag ist nie ein zweiter Versuch im anderen Zweig, ein geprüftes Exchange-Token bekommt keine Identität und wird abgewiesen, und im Aus-Zustand hängt dort dasselbe Objekt wie vorher**

## Performance

- **Duration:** 35 min
- **Started:** 2026-09-19, erster Task-Commit 11:00
- **Completed:** 2026-09-19, letzter Task-Commit 11:27
- **Tasks:** 3 (je RED und GREEN einzeln committet)
- **Files modified:** 11 (0 neu, 11 geändert), 1097 Zeilen hinzu

## Accomplishments

- **Die Weiche ist strukturell und gemessen.** `looks_like_jws` verlangt genau zwei Punkte und drei nicht-leere Segmente. Die eigenen Access-Tokens dieses Servers sind `secrets.token_urlsafe`-Werte, deren Alphabet keinen Punkt kennt; ein kompaktes JWS hat per RFC 7515 exakt zwei. Beide Richtungen sind mit einer Attrappe belegt, die beim Aufruf sofort `AssertionError` wirft: ein punktloser Wert erreicht den fremden Prüfer in keinem Ausgang, ein kompaktes JWS erreicht den Store in keinem. Ein JWE (vier Punkte) und jede Form mit leerem Segment gehen in den Store-Zweig und werden dort als unbekanntes Token abgewiesen (T-22-06).
- **Kein zweiter Versuch.** Eine `ExchangeRefused` wird zu `None`, und der Store wird danach nicht gefragt; ein `None` aus dem Store wird zu `None`, und der Prüfer wird danach nicht gefragt. Beides misst der Test an den Aufzeichnungen der jeweils anderen Attrappe (`seen == []`), nicht an der Rückgabe.
- **Der fremde Claim-Satz reist verschachtelt.** `EXCHANGE_CLAIM = "exchange_claims"` ist der eine Schlüssel in `AccessToken.claims`. Ein Test schiebt dem geprüften Token einen Claim `auth_id` unter und belegt, dass er nicht auf der obersten Ebene landet und dass `resolve_identity` den Store-Zweig dafür nicht einmal fragt (T-22-07).
- **Fail closed, nicht fail everything.** Jede unerwartete Ausnahme des Prüfers wird zu einer Abweisung dieses einen Aufrufs plus einer Zeile, die nur `type(exc).__name__` nennt: kein Token, kein Claim, kein Ausnahmetext. Ein Test wirft einen `MemoryError` im Exchange-Zweig und belegt, dass der nächste Store-Aufruf desselben Objekts normal bedient wird (T-22-09, T-22-11).
- **Die Kette ist eine `IdentitySource`.** Das ist die Sicherheitshälfte und keine Ordnungsfrage: die Transportgrenze lässt einen Verifier ohne Identitätshälfte durch und beendet die Anfrage nur, wenn eine Identitätsquelle `None` sagt. Ein Exchange-Token hat in dieser Phase keine Identität, also muss die Kette die zweite Sorte sein (T-22-08).
- **Ein Widerruf reicht über beide Schichten, ohne die Bremse zu lösen.** `KeySet.forget` versetzt den Cache in den Zustand "nie gefüllt" und fasst weder die Abkühlzeit für unbekannte `kid` noch die Wiederholsperre nach einem Fehlschlag an. Vier Tests messen das an der Zahl ausgehender Abrufe (respx `call_count`) und an keinem privaten Attribut: nach `forget()` kostet ein bekanntes `kid` genau einen neuen Abruf, ein unbekanntes danach keinen, und nach einem fehlgeschlagenen Abruf bleibt die Sperre stehen (T-22-10).
- **Der Einbau ist je Datei eine Stelle.** `build_chain(verifier, env=env, config=exchange_config)` sitzt zwischen `StoreTokenVerifier` und Grenze; ab dort bekommt die Grenze `token_verifier=boundary` und `provider.on_revocation` bekommt `boundary.invalidate`. Der Aus-Zustand ist mit `is` festgenagelt: das Objekt hinter `token_verifier` ist dasselbe, das `on_revocation` bekommen hat, und es ist der unveränderte `StoreTokenVerifier`.
- **Ende zu Ende, in der gebauten Anwendung:** ein selbst gebautes Token, das jede Regel aus Phase 21 besteht, endet an der Transportgrenze mit 401 und dem `resource_metadata`-Zeiger. Der Test prüft zusätzlich, dass der JWKS-Abruf stattgefunden hat: damit ist belegt, dass das Token nicht schon an einer billigen Regel gefallen ist, sondern tatsächlich durch den ganzen Prüfer lief und am fehlenden Konto-Mapping scheiterte.
- 44 Testfunktionen (70 Fälle) in `tests/unit/test_oauth_exchange_chain.py`, dazu 5 neue in den beiden Phase-20/21-Testdateien und 6 in den beiden Einstiegspunkt-Testdateien. Volle Suite: 3834 passed, 33 skipped.

## Task Commits

Jeder Task ist als RED und GREEN getrennt committet:

1. **Task 1: Der Widerruf reicht bis in den Schlüsselsatz** - RED `d1ecb40` (5 fallende Tests, AttributeError nennt `forget` und `forget_keys`), GREEN `39c3075`
2. **Task 2: ChainedVerifier mit der Weiche über die Tokenform** - RED `b8fab4b` (Collection-Fehler: `chain` hat kein `ChainedVerifier`), GREEN `890825f`
3. **Task 3: Einbau an beiden Transportgrenzen** - RED `91f1f3b` (4 fallende Tests: beide bewaffneten Fälle und die Ende-zu-Ende-Abweisung; die Aus-Zustands-Tests waren absichtlich schon grün, sie nageln fest, was sich nicht ändern darf), GREEN `ed53e68`

## Files Created/Modified

- `src/mcp_connector/oauth/chain.py` (229 -> 440 Zeilen) - `EXCHANGE_CLAIM`, `StoreBranch`, `ExchangeBranch`, `looks_like_jws`, `ChainedVerifier` (verify_token, resolve_identity, invalidate, repr), `build_chain`; der Moduldocstring sagt jetzt, dass die zweite Hälfte die Kette ist
- `src/mcp_connector/oauth/jwks.py` - `KeySet.forget`, eine Methode, mit der Begründung für beide Hälften (warum es sie gibt, warum die zwei Stempel stehen bleiben)
- `src/mcp_connector/oauth/exchange.py` - `ExchangeTokenChecker.forget_keys`, reine Ergänzung (`git diff | grep '^-[^-]'` ergibt 0)
- `src/mcp_connector/entry_exapp.py` - das Ergebnis des 22-01-Lesers in einer Variablen, `build_chain` dahinter, `boundary` an Grenze und Widerruf
- `src/mcp_connector/entry_oauth.py` - dasselbe, plus das Feld `StandaloneSettings.exchange`, damit beide Aufbauwege die Kette aus derselben gelesenen Antwort bauen
- `vulture_whitelist.py` - `_.claims_of` entfernt (die Kette ruft es jetzt), `_.forget_keys` in Task 1 vorübergehend eingetragen und in Task 3 wieder entfernt; `_._decode_payload` bleibt, die Schwelle wurde nicht gesenkt
- `tests/unit/test_oauth_exchange_chain.py` (254 -> 797 Zeilen, 19 -> 44 Testfunktionen)
- `tests/unit/test_oauth_jwks.py` (+4), `tests/unit/test_oauth_exchange.py` (+1), `tests/unit/test_exapp_entry.py` (+3), `tests/unit/test_entry_oauth.py` (+3)

## Decisions Made

- **Die Zweige sind Protokolle, nicht konkrete Klassen.** Der Plan schreibt `store: IdentitySource, checker: ExchangeTokenChecker`. `IdentitySource` kennt `invalidate` nicht, und pyright läuft in diesem Repository auch über `tests/`. Mit `ExchangeTokenChecker` als Annotation hätte ausgerechnet der Test, der die Zusage dieses Plans trägt (eine Attrappe, die beim Aufruf auffliegt), ein `type: ignore` gebraucht. Also stehen zwei Protokolle in der Form von `IdentitySource` und `ClientLookup` im Modul: `StoreBranch` (`verify_token`, `resolve_identity`, `invalidate`) und `ExchangeBranch` (`claims_of`, `forget_keys`). Der Store-Zweig ist in der Anwendung weiterhin der unveränderte `StoreTokenVerifier`.
- **`build_chain` bekommt `env` und `config`.** Mit `config` allein hätte der Aus-Zustand (`config is None`) `load_exchange_config(None)` bedeutet, also `os.environ` statt der Mapping-Instanz, mit der die Anwendung gebaut wurde. Für eine Anwendung, die aus einem übergebenen Mapping gebaut wird, wäre das eine andere Quelle gewesen als die, aus der die Startabweisung gelesen hat. Beide Einstiegspunkte geben deshalb beides mit.
- **`StandaloneSettings.exchange`** ist der in 22-01 offen gelassene Punkt und löst das Problem, dass der 22-01-Leseaufruf in `build_oauth_app` nur auf einem der beiden Aufbauwege läuft. Jetzt trägt die validierte Antwort mit den Settings, und der zweite Weg (Settings hereingereicht) liest weiterhin selbst, weil er die Abweisung nicht überspringen darf.
- **Die Audience im `AccessToken` ist die konfigurierte, nicht die vom Token genannte.** Die beiden sind gleich, weil die Prüfung sie gleich gemacht hat; weitergereicht wird unsere (T-22-03).
- **`subject` bleibt leer.** Ein roher `sub` an dieser Stelle wäre der Anmeldename eines fremden Realms in der Rolle des Principals dieses Servers (Pitfall 5). Phase 23 setzt den kanonischen Principal an genau einer benannten Stelle ein: dem `EXCHANGE_CLAIM`-Zweig von `resolve_identity`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `forget_keys` brauchte zwischen Task 1 und Task 3 einen Whitelist-Eintrag**
- **Found during:** Task 1 (Gate `uv run vulture`)
- **Issue:** Der Plan lässt `forget_keys` in Task 1 entstehen und erst in Task 3 rufen. Zwischen beiden Commits hat die Methode keinen Aufrufer, und das vulture-Gate ist Teil der Akzeptanzkriterien *jedes* Tasks.
- **Fix:** Eintrag `_.forget_keys` in `vulture_whitelist.py` in der Form der Nachbarn (Begründung, wer es später ruft, Ablaufvermerk auf Task 3 dieses Plans), in Task 3 zusammen mit `_.claims_of` wieder entfernt.
- **Files modified:** `vulture_whitelist.py` (im Plan ohnehin als Datei von Task 3 vorgesehen)
- **Verification:** `grep -c "claims_of\|forget_keys" vulture_whitelist.py` ergibt jetzt 0, vulture still

### Kriterien-Interpretationen (dokumentiert, nicht stillschweigend)

**2. [Signatur präzisiert] Die Typen der beiden Zweige**
- **Found during:** Task 2
- **Issue:** Siehe "Decisions Made": die Plan-Signatur ist mit der pyright-Konfiguration dieses Repositories (include `tests`) und mit den vom Plan selbst verlangten Attrappen nicht gleichzeitig erfüllbar.
- **Fix:** Zwei Protokolle im Modul, Parameternamen und Semantik wie im Plan (`store`, `checker`, `config`).
- **Verification:** `pyright` 0 errors, und die Attrappen stehen ohne ein einziges `type: ignore` in `tests/unit/test_oauth_exchange_chain.py`

**3. [Ergänzung] `build_chain` bekommt in beiden Einstiegspunkten auch `env`**
- **Found during:** Task 3
- **Issue:** Der Plan schreibt `chain.build_chain(verifier, config=exchange_config)`. Im Aus-Zustand ist `exchange_config` `None`, und ohne `env` hätte die Fabrik dann `os.environ` gelesen statt des übergebenen Mappings.
- **Fix:** `chain.build_chain(verifier, env=env, config=exchange_config)`; die Kriterien (`grep -c "build_chain("` ergibt 1 je Datei, `load_exchange_config` einmal in `entry_exapp.py`) sind unberührt.
- **Verification:** `grep -c 'build_chain('` ergibt 1 und 1, `grep -c load_exchange_config src/mcp_connector/entry_exapp.py` ergibt 1

---

**Total deviations:** 3 (1 blockierender Gate-Befund auto-behoben, 2 dokumentierte Präzisierungen)
**Impact on plan:** Keine Scope-Ausweitung. `oauth/verifier.py`, `exapp/middleware.py`, `deps.py` und `oauth/throttle.py` sind unberührt; unter `src/` stehen genau die fünf geplanten Dateien im Diff.

## Issues Encountered

- Keine offenen. Der einzige Reibungspunkt war der Reihenfolgekonflikt zwischen Task 1 und Task 3 beim vulture-Gate (oben als Abweichung 1 dokumentiert).

## TDD Gate Compliance

- Task 1: RED `d1ecb40` (5 fallende Tests), GREEN `39c3075`
- Task 2: RED `b8fab4b` (Collection-Fehler), GREEN `890825f`
- Task 3: RED `91f1f3b` (4 fallende Tests), GREEN `ed53e68`
- Kein REFACTOR-Schritt nötig; `ruff format` lief vor jedem Commit.

## Verification (Plan-Ebene)

1. `uv run pytest tests/unit tests/contract -q`: 3834 passed, 33 skipped, 0 failed (volle Suite, kein Subset)
2. `uv run ruff check .` und `uv run ruff format --check .`: still (251 Dateien)
3. `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
4. `uv run vulture src scripts vulture_whitelist.py`: still, Schwelle unverändert
5. `git diff --name-only 089a359..HEAD | grep '^src/'`: genau `entry_exapp.py`, `entry_oauth.py`, `oauth/chain.py`, `oauth/exchange.py`, `oauth/jwks.py`; `oauth/verifier.py`, `exapp/middleware.py`, `deps.py` stehen nicht darunter
6. `grep -rn "check_resource_allowed" src/mcp_connector/oauth/chain.py`: nichts
7. `grep -v '^\s*#' src/mcp_connector/oauth/chain.py | grep -c "except Exception"`: 1, `... | grep -c "AUTH_ID_CLAIM"`: 0
8. `python -c "... [chain.looks_like_jws(v) for v in ['abc','a.b.c','a.b','a.b.c.d.e','','a..c']]"`: `[False, True, False, False, False, False]`
9. `grep -c "def test_" tests/unit/test_oauth_exchange_chain.py`: 44 (70 Fälle, grün), `grep -c "AssertionError"`: 6
10. `git diff src/mcp_connector/oauth/exchange.py | grep -c '^-[^-]'` über den ganzen Plan: 0
11. Gedankenstrich-Kontrolle (lange Striche) über alle elf geänderten Dateien und über alle sechs Commit-Texte: keine Treffer

## User Setup Required

None - der Pfad ist weiterhin ab Werk aus, und im Aus-Zustand hängt an der Transportgrenze dasselbe Objekt wie vor diesem Plan.

## Next Phase Readiness

- **Plan 22-03 (Drosselung):** `oauth/throttle.py` ist unberührt. Die Stelle, an der ein Exchange-Versuch zählbar wird, ist der Exchange-Zweig von `ChainedVerifier.verify_token`; die Weiche davor trennt schon heute Exchange-Versuche von Store-Aufrufen, so dass eine Drosselung genau die eine Klasse treffen kann.
- **Phase 23 (MAP-01/MAP-02):** die eine benannte Stelle ist der `EXCHANGE_CLAIM`-Zweig von `ChainedVerifier.resolve_identity`. Dort liegt der volle geprüfte Claim-Satz unter `access.claims[chain.EXCHANGE_CLAIM]`, und `ExchangeConfig.account_claim` sagt, welcher Claim das Konto nennt. Heute ist die Antwort dort `None`, und die Transportgrenze weist damit ab.
- **Phase 24 (AUDIT-07, EXCH-08):** abgewiesene Exchange-Versuche sind bisher nur die eine Fehlerzeile mit dem Ausnahmetyp; ein Audit-Eintrag fehlt bewusst. Die Einrichtungsdoku unter `docs/` fehlt weiterhin; das CHANGELOG wurde in diesem Plan nicht angefasst, weil sich am sichtbaren Verhalten einer Installation nichts ändert (auch bewaffnet endet ein Exchange-Token mit 401, bis das Konto-Mapping existiert).

---
*Phase: 22-konfiguration-kette-und-drosselung*
*Completed: 2026-09-19*

## Self-Check: PASSED

- Alle geänderten Dateien liegen auf der Platte (chain.py, jwks.py, exchange.py, beide Einstiegspunkte, fünf Testdateien, vulture_whitelist.py, SUMMARY)
- Alle sieben Commits (d1ecb40, 39c3075, b8fab4b, 890825f, 91f1f3b, ed53e68, f67f8e5) stehen in der Historie
- Alle Gates nach dem letzten Task erneut gefahren: volle Suite 3834 passed / 33 skipped, ruff still, pyright 0/0/0, vulture still

---
phase: 24-audit-anschluss-und-nachweis
plan: 05
subsystem: auth
tags: [oauth, token-exchange, dry-run, jwks, ast-gate, pyjwt, keycloak]

# Dependency graph
requires:
  - phase: 21-token-exchange-pruefer
    provides: "ExchangeTokenChecker.claims_of, MAX_TOKEN_BYTES, audience_holds, die 19 _refused-Aufrufstellen"
  - phase: 22-token-exchange-kette
    provides: "ExchangeConfig, load_exchange_config und looks_like_jws als Formweiche"
  - phase: 23-konto-abbildung
    provides: "mapping.principal_from_claims und die beiden Abbildungsprofile"
  - plan: 24-02
    provides: "die sechs gruppierten Ablehnungsbezeichner und der Einargument-Weg in _refused"
provides:
  - "oauth/exchange_dryrun.py: die Regel des Trockenlaufs als reine Funktion, ohne Route und ohne Umgebung"
  - "STEPS: 22 maschinenlesbare Schrittbezeichner in Prüfreihenfolge"
  - "DryRunStep und DryRunResult als Daten, nie als fertiger Satz"
  - "LIMIT_SENTENCE und COST_SENTENCE: was ein grüner Lauf nicht bedeutet und was er kostet"
  - "ein AST-Drift-Gate über die Ablehnungen von oauth/exchange.py UND oauth/jwks.py"
affects: [24-06-occ-trockenlauf, 24-09-token-exchange-doku]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Regel und Konsole getrennt: die reine Funktion hier, die Oberfläche in einer eigenen Datei"
    - "Eigene KeySet-Instanz je Lauf, damit eine Admin-Prüfung die Bremsen des heißen Pfads nicht verbraucht"
    - "Ein nicht ausgeführter Schritt steht benannt in der Antwort statt wegzufallen"
    - "AST-Gate über zwei Quelldateien, verglichen als Menge von (Datei, Phrase)-Paaren"

key-files:
  created:
    - src/mcp_connector/oauth/exchange_dryrun.py
    - tests/unit/test_oauth_exchange_dryrun.py
  modified:
    - vulture_whitelist.py

key-decisions:
  - "Der Vergleich des Gates läuft über Paare (Datei, Phrase), nie über die Zahl der Aufrufstellen: 28 Stellen, 23 Paare"
  - "jwks.py wird mitgescannt, statt key_available als Ausnahme zu führen: sonst fielen fünf echte Regeln aus dem Gate"
  - "_refused und _number werden aus exchange.py importiert statt kopiert; eine Kopie wäre genau die Drift, die dieser Plan ausschließt"
  - "Der Trockenlauf nutzt den öffentlichen jwt.decode statt des privaten _PreparsedJWT: die Doppelparsung ist eine Optimierung des heißen Pfads, kein Teil der Regel"
  - "passed ist nur wahr, wenn kein Schritt fiel UND keiner unerreicht blieb; ein skipped-Schritt ist eine offene Frage, keine bestandene"
  - "Der nicht geprüfte Kontoschritt trägt einen eigenen note-Bezeichner statt einer Ablehnungsgruppe: er wurde nicht abgelehnt, er wurde nicht gefragt"

patterns-established:
  - "Ein Ergebnisfeld trägt nie einen Wert aus dem vorgelegten Token; nachgewiesen mit einem Marker in iss, aud, azp, sub und kid, auf einem roten und auf einem grünen Lauf"
  - "Ein Drift-Gate sagt im Docstring ausdrücklich, was es nicht leistet"

requirements-completed: [EXCH-06]

# Metrics
duration: 50min
completed: 2026-09-24
---

# Phase 24 Plan 05: Die Regel des Trockenlaufs

**Ein vorgelegtes Token wird gegen die aktive Exchange-Konfiguration geprüft, jeder der 22 Schritte bekommt ein benanntes Ergebnis, der Lauf hinterlässt nichts, und ein AST-Gate über zwei Quelldateien schließt aus, dass der Trockenlauf grün sagt, wo der Betrieb rot sagt.**

## Was gebaut wurde

`src/mcp_connector/oauth/exchange_dryrun.py` hält die Regelhälfte von EXCH-06: eine `async`-Funktion `dry_run(token, config)`, die nichts aus der Umgebung liest, keine Route kennt und deren einziger Ausgang der Schlüsselsatz-Abruf ist. Die Konsole ist Plan 24-06 und bekommt hier nichts zu entscheiden.

**Die Schritte** (`STEPS`, 22 Bezeichner) folgen `ExchangeTokenChecker.claims_of` Regel für Regel, mit genau einer im Docstring festgehaltenen Abweichung: die drei eigenen Eingabegrenzen (`token_present`, `token_size`, `token_is_text`) stehen vor der Formweiche, weil der Trockenlauf seine eigene Eingabe begrenzen muss, bevor er etwas mit ihr tut. Die Abweichung ändert kein Ergebnis, weil ein Token, das an einer der drei fällt, auf beiden Seiten der Weiche abgewiesen würde.

**Was geteilt statt kopiert wird:** `looks_like_jws` (Formweiche), `audience_holds` (Audience), `principal_from_claims` (Abbildung), `MAX_TOKEN_BYTES` (Größengrenze), `ACCEPTED_TYP_HEADERS` (Header-Typ), sowie `_refused` und `_number` aus `exchange.py`. Der Trockenlauf zählt keine Punkte selbst (`grep -c 'split("\.")'` ergibt 0) und tippt die Grenze nicht neu (`grep -c "8192"` ergibt 0).

**Der eigene Schlüsselsatz** (Pitfall 7, T-24-07): je Lauf eine eigene `KeySet`-Instanz, gebaut mit denselben fünf Argumenten wie im laufenden Prüfer. Gemessen: zwei Trockenläufe gegen ein unbekanntes `kid` kosten zwei Abrufe, und der laufende Prüfer löst danach seinen dritten aus. Mit einem geteilten Schlüsselsatz hätte die Zählung bei zwei gestanden, weil dessen Abkühlzeit dann armiert gewesen wäre.

**Der nicht ausgeführte Schritt** (Pitfall 8, T-24-23): `account_exists` steht in jeder Antwort, mit `not_checked` nach einem sauberen Lauf und `skipped` hinter einer gefallenen Regel, und trägt in beiden Fällen denselben Hinweis `would_call_nextcloud`. Dazu zwei Sätze in der Antwort selbst: `LIMIT_SENTENCE` sagt, was ein grüner Lauf nicht bedeutet (Konto ungeprüft, Uhr dieses Containers, Annahme A1 aus `audit/accounts.py`), `COST_SENTENCE` nennt den Preis von einem ausgehenden Abruf.

**Das Drift-Gate** (T-24-24) scannt beide Dateien, in denen die Ablehnungen dieses Pfads leben:

| Datei | Aufrufstellen | verschiedene Phrasen | Einträge in der Abbildung |
|-------|---------------|----------------------|---------------------------|
| `oauth/exchange.py` (`_refused(`) | 19 | 18 | 18 |
| `oauth/jwks.py` (`self._refuse(`) | 9 | 5 | 5 |
| zusammen | 28 | 23 | 23 |

Verglichen wird die Menge der Paare (Datei, Phrase), nie die Zahl der Aufrufstellen. Drei Zusicherungen: Vollständigkeit vorwärts (jede gefundene Phrase hat einen Schritt), Gruppengleichheit (die Gruppe der Abbildung steht am Aufruf selbst, aufgelöst über `getattr(errors, ...)`), Vollständigkeit rückwärts (22 Schritte minus 3 benannte Ausnahmen sind 19 gedeckte Schritte). Dazu eine Laufzeitprobe über alle 21 Schritte, die fallen können, und zwei Gegenproben, die zeigen, dass das Gate in beiden Richtungen rot wird.

`STEPS_WITHOUT_A_PHRASE` hat genau drei Einträge, je mit der Deckung, die an die Stelle der Phrase tritt: `token_shape` (geteilte Funktion `looks_like_jws`), `mapping_yields_principal` (geteilte Funktion `principal_from_claims`), `account_exists` (per Entwurf nie ausgeführt). Ein Test hält die Größe auf drei.

## Aufgaben und Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 (RED) | `caedd2f` | Fehlschlagende Tests für die lokalen Schritte |
| 1 (GREEN) | `7cd71c1` | Ergebnismodell und lokale Schritte bis zum `iss`-Vorfilter |
| 2 (RED) | `7c374fb` | Fehlschlagende Tests für Schlüsselsatz, gedeckte Claims, Kontoschritt |
| 2 (GREEN) | `cb63a11` | Eigene `KeySet`-Instanz, signaturgedeckte Schritte, Ehrlichkeitssätze |
| 3 | `64b33ae` | Das Drift-Gate über beide Quelldateien, mit zwei Gegenproben |

## TDD Gate Compliance

RED- und GREEN-Gates liegen für beide Bau-Tasks vor (`test(...)` vor `feat(...)`, je Task ein Paar). Task 3 ist ein reiner Test-Task ohne Implementierungshälfte, daher ein `test(...)`-Commit ohne folgendes `feat(...)`. Ein `refactor(...)`-Commit war nicht nötig: an den grünen Fassungen war nichts aufzuräumen.

## Verifikation

| Gate | Ergebnis |
|------|----------|
| `uv run pytest -q` | 4302 passed, 33 skipped, 168 deselected |
| `uv run pytest tests/contract -q` | grün |
| `uv run pytest tests/unit/test_oauth_exchange_dryrun.py -q` | 82 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 267 files already formatted |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings |
| `uv run vulture src scripts vulture_whitelist.py` | grün (drei begründete Whitelist-Zeilen) |

Die Abnahmezahlen des Plans, nachgemessen:

| Messung | Erwartet | Gemessen |
|---------|----------|----------|
| `len(STEPS), STEPS[0], STEPS[-1]` | `22 token_present account_exists` | `22 token_present account_exists` |
| `_refused(`-Stellen / Phrasen in `exchange.py` | `19 18` | `19 18` |
| `self._refuse(`-Stellen / Phrasen in `jwks.py` | `9 5` | `9 5` |
| `grep -c "MAX_TOKEN_BYTES"` | >= 1 | 3 |
| `grep -c "8192"` | 0 | 0 |
| `looks_like_jws` außerhalb von Kommentaren | >= 2 | 3 |
| `split(".")` außerhalb von Kommentaren | 0 | 0 |
| `principal_from_claims` außerhalb von Kommentaren | >= 2 | 2 |
| `resolve_identity` außerhalb von Kommentaren | 0 | 0 |

## Abweichungen vom Plan

### 1. [Rule 1 - Bug] Die Gruppengleichheit muss zwei Bezeichner an einer Stelle vertragen

- **Gefunden bei:** Task 3
- **Befund:** Der Plan beschreibt die zweite Zusicherung als "die Gruppe aus der Konstante ist gleich dem Bezeichner, den die Aufrufstelle als zweites Argument trägt". Die Aufrufstelle `oauth/exchange.py:486` trägt aber einen `ast.IfExp` mit zwei Bezeichnern, weil derselbe Decoder-Aufruf die Signaturprüfung und die Standard-Claims zusammen trägt (Entscheidung aus Plan 24-02). Eine Gleichheit gegen einen einzelnen Namen wäre schon beim ersten Lauf rot gewesen.
- **Fix:** Das Gate löst das Argument mit demselben `groups_named_by` auf, das schon das 24-02-Gate benutzt (Name oder Auswahl zwischen zwei Namen, alles andere ist ein Befund), und prüft Mitgliedschaft statt Gleichheit. Die Laufzeitprobe prüft entsprechend `reason in groups_allowed_for(step)`. Beides ist im Testdocstring benannt.
- **Dateien:** `tests/unit/test_oauth_exchange_dryrun.py`
- **Commit:** `64b33ae`

### 2. [Rule 2 - fehlende Deckung] `passed` darf nach einem unerreichten Schritt nicht wahr sein

- **Gefunden bei:** Task 1
- **Befund:** Der Plan definiert `passed: bool` als Gesamtschlüssel, sagt aber nicht, was ein `skipped`-Schritt für ihn bedeutet. Eine Definition "kein Schritt ist gefallen" hätte einen halb gebauten Lauf (Task 1 ohne Task 2) als grün gelesen, und das ist genau die stille Zusicherung, gegen die Pitfall 8 geschrieben ist.
- **Fix:** `passed` ist nur wahr, wenn jeder Schritt entweder `passed` oder `not_checked` ist. Ein unerreichter Schritt ist eine offene Frage und hält das Ergebnis rot. Im Docstring von `DryRunResult` begründet.
- **Dateien:** `src/mcp_connector/oauth/exchange_dryrun.py`
- **Commit:** `7cd71c1`

### 3. [Rule 3 - blockierend] Zwei Testannahmen waren gegen PyJWT falsch

- **Gefunden bei:** Task 1 und Task 2
- **Befund:** (a) `jwt.get_unverified_header` dekodiert beide Segmente, also fällt ein Token mit nicht-base64-Nutzlast schon im Schritt `header_readable` und nicht in `payload_readable`. (b) Ein leeres `sub` erfüllt die `require`-Liste des Decoders (der Claim ist vorhanden) und erreicht die eigene Regel `subject_usable`.
- **Fix:** Der Nutzlast-Fall baut jetzt ein gültiges base64url-Segment mit ungültigem JSON; der Fall `sub=""` steht bei `subject_usable`, wo ihn auch `test_an_empty_sub_is_refused` des Prüfers misst. Beides ist im jeweiligen Testdocstring als Messung festgehalten.
- **Dateien:** `tests/unit/test_oauth_exchange_dryrun.py`
- **Commits:** `7cd71c1`, `cb63a11`

### 4. [Rule 2 - Werkzeuggate] Drei Whitelist-Zeilen für die noch ungelesenen Antwortfelder

- **Gefunden bei:** Task 1
- **Befund:** `vulture` meldet `passed`, `limit_sentence` und `cost_sentence` von `DryRunResult`, weil das Modul bis Plan 24-06 keinen Leser in `src/` hat. Der Plan kündigt genau das an.
- **Fix:** Drei Einträge in `vulture_whitelist.py`, je mit einer Begründungszeile und der Ankündigung, dass sie mit dem Task verschwinden, der die Felder liest (Muster der drei bestehenden Blöcke der Datei).
- **Dateien:** `vulture_whitelist.py`
- **Commit:** `7cd71c1`

## Was dieser Plan ausdrücklich nicht leistet

- **Keine Oberfläche.** Es gibt keinen occ-Einstieg und keine Route; das ist Plan 24-06. Der Standalone-Betrieb bekommt in dieser Phase keine Oberfläche, und diese Grenze gehört ausdrücklich in `docs/token-exchange.md` (Plan 24-09).
- **Das Gate deckt nicht die `refuse(...)`-Aufrufe in `jwks.fetch_json`.** Provider nicht erreichbar, Statuscode ungleich 200, zu große Antwort, keine JSON-Antwort und ein Ziel außerhalb des Origins landen alle ebenfalls in `key_available`, aber ihre Wortlaute stehen nicht in der Abbildung. Eine sechste Wortlaut-Variante dort würde unbemerkt durchgehen. Das ist im Testdocstring als benannte Grenze festgehalten, nicht als Versehen.
- **Das Gate verhindert keine unterschiedliche Umsetzung derselben Regel.** Dafür sind die gemessenen Fälle da, und für die drei Schritte ohne Phrase die geteilte Funktion.

## Known Stubs

Keine. Das Modul hat bis Plan 24-06 bewusst keinen Aufrufer in `src/`; das ist kein Stub, sondern die im Plan entschiedene Trennung von Regel und Konsole, und die drei Whitelist-Zeilen kündigen ihr eigenes Ende an.

## Threat Flags

Keine neue sicherheitsrelevante Fläche außerhalb des Bedrohungsmodells des Plans. Der eine ausgehende Abruf je Lauf ist dort als Vertrauensgrenze benannt und über die eigene `KeySet`-Instanz gemessen.

## Self-Check: PASSED

Alle angelegten Dateien existieren auf der Platte, alle fünf Commits stehen in der Historie dieses Worktrees, und der Arbeitsbaum ist außer dieser Datei sauber. `STATE.md` und `ROADMAP.md` wurden nicht angefasst.

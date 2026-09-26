---
phase: 24-audit-anschluss-und-nachweis
plan: 09
subsystem: docs
tags: [token-exchange, documentation, truth-gate, keycloak, f13, exch-08]

requires:
  - phase: 24-06
    provides: "das Kommando mcp_connector:exchange:check, die Bodygrenze als Vielfaches und die Messung A5"
  - phase: 24-08
    provides: "docs/exchange-evidence.md und den gemessenen Basic-Header-Befund aus Messung 4"
provides:
  - "docs/token-exchange.md: die Einrichtungsdoku des Exchange-Pfads, zehn Bausteine"
  - "tests/unit/test_docs_exchange_truth.py: das Wahrheitsgate ueber die neue Seite, Variablen in beide Richtungen"
  - "Die Ankuendigung in docs/standalone-oauth.md ist eingeloest und nicht mehr offen"
  - "Owner-Entscheid: die Rolle des Nextcloud-eigenen oauth2-Clients bleibt als offene F13-Antwort markiert"
affects: []

tech-stack:
  added: []
  patterns:
    - "Die Variablenliste einer Doku hat genau eine Quelle; die Doku nennt Bedeutungen und verweist fuer Werte"
    - "Ein Wahrheitsgate haelt die Variablenliste in beide Richtungen: keine erfundene und keine verschwiegene"
    - "Ein Gate-Docstring nennt ausdruecklich, welche Zahlen es NICHT haelt und warum, damit niemand eine Messung kuenstlich verankert"
    - "Eine abgeleitete Konstante steht in der Doku als das Vielfache, das sie ist; das Literal wird vom Gate als abwesend geprueft"

key-files:
  created:
    - docs/token-exchange.md
    - tests/unit/test_docs_exchange_truth.py
  modified:
    - docs/standalone-oauth.md
    - README.md

key-decisions:
  - "Owner-Entscheid vom 24.09.2026: das occ-oauth2:add-client-Playbook wird geschrieben, seine Rolle ausdruecklich als offene F13-Antwort markiert; die Frage an F13 ist vertagt"
  - "Die drei denkbaren Rollen des Clients werden als ununterscheidbar benannt statt aufgezaehlt: eine Aufzaehlung waere eine Vorauswahl ohne Faktenlage"
  - "Der Verweis auf docs/exchange-evidence.md wandert von docs/standalone-oauth.md nach docs/token-exchange.md; er steht weiterhin genau einmal im Repo"
  - "Die Vorgabewerte der NC_MCP_EXCHANGE_-Variablen stehen NICHT in der Doku: die Tabelle nennt Bedeutungen und verweist auf den Docstring von oauth/chain.py"
  - "Die Bodygrenze des Trockenlaufs steht als 'twice MAX_TOKEN_BYTES'; das Gate prueft das Literal 16384 als abwesend"

requirements-completed: [EXCH-08]

duration: 45min
completed: 2026-09-24
---

# Phase 24 Plan 09: Die Einrichtungsdoku des Token-Exchange-Pfads Summary

**`docs/token-exchange.md` fuehrt einen Betreiber in zehn Abschnitten von der Keycloak-Seite bis zum ersten Werkzeugaufruf, nennt die Audience-Konvention ausdruecklich als Empfehlung und nicht als Tatsache, schreibt das gegen Nextcloud 35.0.0 verifizierte `occ oauth2:add-client`-Playbook mit der vom Owner am 24.09.2026 vertagten Rolle als offene F13-Antwort, traegt jede Byte-Zahl mit ihrem Messdatum, und achtzehn Tests halten jede pruefbare Aussage der Seite gegen die Konstante, aus der sie stammt.**

## Performance

- **Duration:** 45 min
- **Started:** 2026-09-24T06:20:00Z (Basis-Assertion und Checkpoint-Vorlage)
- **Completed:** 2026-09-24T07:05:00Z
- **Tasks:** 3 (einer davon ein Owner-Checkpoint)
- **Files modified:** 4 (2 neu, 2 geaendert)

## Task 1: Der Owner-Entscheid, woertlich und mit Datum

Der Plan traegt als ersten Task einen blockierenden `checkpoint:decision`: wofuer der Nextcloud-eigene oauth2-Client steht, den F13s Spec-Note in Abschnitt 6 mit `occ oauth2:add-client` anlegen laesst. Die Faktenlage wurde erhoben, die drei Optionen vorgelegt, und die Frage nicht selbst beantwortet.

**Die Antwort des Owners, woertlich, vom 24.09.2026:**

> "bringe es zu ende lass es offen markiert ich vertage die frage an f13 fuer eine spaetere zeit"

**Gewaehlte Option:** `offen-markieren`.

**Was daraus fuer Baustein 7 folgt und so umgesetzt ist:** das Playbook schreibt das gegen den Quelltext von Nextcloud 35.0.0 (`apps/oauth2/lib/Command/AddClient.php`) verifizierte Kommando `occ oauth2:add-client "<name>" "<redirect-uri>"` samt seiner zwei Pflichtargumente und der `FILTER_VALIDATE_URL`-Pruefung. Seine **Rolle** steht als eine von F13s offenen Antworten da, mit dem Datum der Vertagung. Es gibt keine erfundene Begruendung. Die drei denkbaren Rollen werden als ununterscheidbar benannt statt aufgezaehlt, weil eine Aufzaehlung eine Vorauswahl ohne Faktenlage waere, und die Seite sagt stattdessen den einen Satz, der stimmt: vor dem Anlegen eines solchen Clients ist bei F13 nachzufragen.

**Die Faktenlage, die dem Entscheid zugrunde lag:**

- Das Kommando ist verifiziert, sein Zweck nicht. Die Quelle des Zwecks liegt nicht im Repo.
- Gegenprobe: `occ oauth2:add-client`, die Nextcloud-oauth2-App und ein Nextcloud-eigener oauth2-Client kamen vor diesem Plan in `docs/`, `README.md` und `src/` **nirgends** vor.
- Beide Betriebsarten dieses Connectors kommen ohne einen solchen Client aus (ExApp ueber AppAPI, Standalone ueber `NC_MCP_OIDC_*` und Login Flow v2).
- Erfolgskriterium 5 verlangt das Playbook woertlich, also war `weglassen` kein zulaessiger Weg.

## Accomplishments

- `docs/token-exchange.md` steht mit zehn nummerierten Abschnitten, die den zehn Bausteinen aus `24-RESEARCH.md` eins zu eins entsprechen.
- Die Audience-Konvention steht in einem eigenen Merkkasten mit der Ueberschrift "Recommendation, not a rule." und dem Hinweis, dass F13-Entscheidung 1 offen ist. Das ist die Mitigation von T-24-11 und Pitfall 10, und sie wird vom Gate gehalten.
- Die Ankuendigung aus `docs/standalone-oauth.md:62-66` ist **ersetzt**, nicht ergaenzt: der Satz "gets its own setup document" kommt in der Datei nicht mehr vor, an seiner Stelle steht der Verweis auf die neue Seite.
- Der gemessene Basic-Header-Befund aus Plan 24-08 ist in Abschnitt 9 ausformuliert, samt der Einordnung, dass es keine Rechteausweitung ist, und samt dem Merkmal, an dem der Fall im Audit-Log erkennbar wird.
- Jede Byte-Zahl der Seite traegt ihr Messdatum, und die bindende Umgebungsgrenze bleibt Apaches 8190 Byte auf dem `Authorization`-Header. Eine gemessene Obergrenze unterhalb von 8192 Byte wird nirgends behauptet (Vorgabe aus 24-06).
- `tests/unit/test_docs_exchange_truth.py` haelt achtzehn Aussagen der Seite gegen den Code, davon die Variablenliste in beide Richtungen.

## Task Commits

1. **Task 1: Der Owner-Checkpoint** - kein Commit; eine Entscheidung ist keine Dateiaenderung. Die Antwort steht woertlich oben und wird mit diesem SUMMARY committet.
2. **Task 2: docs/token-exchange.md, die zehn Bausteine** - `dc6b65f`
3. **Task 3: Die Verweise und das Wahrheitsgate** - `7ab3bba`

## Files Created/Modified

- `docs/token-exchange.md` - die Einrichtungsdoku: Kette im Bild, Keycloak-Seite mit Audience-Empfehlung und azp-Allowlist, die zehn Variablen mit Bedeutung statt Vorgabewert, der Kontoweg je Betriebsart, der erste Werkzeugaufruf samt `client_id` und `actor`, der Trockenlauf mit seinem Preis und dem, was ein gruener Lauf nicht bedeutet, das `occ oauth2:add-client`-Playbook mit offener Rolle, Groessen und Grenzen mit Messdaten, "What this path does not do", "What hangs on F13's four open answers".
- `tests/unit/test_docs_exchange_truth.py` - achtzehn Tests nach dem Muster von `test_docs_audit_truth.py`, plus ein Gegenproben-Test und ein Docstring, der die nicht gehaltenen Zahlen benennt.
- `docs/standalone-oauth.md` - die Ankuendigung ist durch den Verweis ersetzt; der Verweis auf die Messdatei ist an die neue Seite abgegeben.
- `README.md` - ein Satz im Enterprise-Abschnitt, an der Stelle, an der der Single-Sign-on-Weg beschrieben ist.

## Die zehn Bausteine, und wo sie stehen

| Baustein | Abschnitt der Seite |
|---|---|
| 1 Die Kette in einem Bild | `## 1. The chain in one picture` |
| 2 Die Keycloak-Seite | `## 2. The Keycloak side` |
| 3 Die Connector-Seite | `## 3. The connector side: the variables` |
| 4 Der Kontoweg je Betriebsart | `## 4. The account, per deployment mode` |
| 5 Der erste Werkzeugaufruf | `## 5. The first tool call, and where to find it` |
| 6 Der Trockenlauf | `## 6. The dry run` |
| 7 Das `occ oauth2:add-client`-Playbook | `## 7. The occ oauth2:add-client playbook` |
| 8 Groessen und Grenzen | `## 8. Sizes and limits of the route` |
| 9 Was der Pfad nicht leistet | `## 9. What this path does not do` |
| 10 F13s vier offene Antworten | `## 10. What hangs on F13's four open answers` |

## Die Zahlen der Seite, und wer sie haelt

| Zahl | Herkunft | Vom Gate gehalten |
|---|---|---|
| 8192 Byte Tokengrenze | `exchange.MAX_TOKEN_BYTES` | ja |
| 8193 Byte Messpunkt (A5, 24.09.2026) | `MAX_TOKEN_BYTES + 1` | ja |
| Bodygrenze des Trockenlaufs | `twice MAX_TOKEN_BYTES`; das Literal 16384 wird als **abwesend** geprueft | ja |
| 900 Sekunden Lebensdauer und Alter | `exchange.MAX_TOKEN_LIFETIME_SECONDS` | ja |
| 30 Sekunden Toleranz | `exchange.EXCHANGE_LEEWAY_SECONDS` | ja |
| ca. 14,9 kB ueber Caddy, ca. 15,1 kB auf HaRP (23.09.2026) | Messung gegen die Umgebung | **nein, bewusst** |
| 8190 Byte je Header-Zeile in Apache, Umschlag zwischen 8050 und 8200 (23.09.2026) | Apaches Vorgabe, gemessen | **nein, bewusst** |
| 920 / 1477 / 4132 Byte, Schwelle bei ca. 68 Rollen und 68 Gruppen (23.09.2026) | synthetische Claim-Saetze | **nein, bewusst** |
| 342 Zeichen RS256-Signatur bei 2048 Bit | Eigenschaft des Verfahrens | **nein, bewusst** |

Der Docstring des Gates sagt das ausdruecklich und nennt den Grund: diese Zahlen sind Eigenschaften fremder Software oder synthetischer Claim-Saetze. Sie sind wahr, weil eine Messung mit Datum es sagt, und eine kuenstlich erfundene Konstante wuerde eine Messung in eine Fiktion verwandeln, der ein spaeterer Leser mehr traut als der Messung.

## Decisions Made

- **Der Verweis auf die Messdatei wandert statt sich zu verdoppeln.** Der Plan verlangt den Verweis in `docs/token-exchange.md` (key_link) und gleichzeitig, dass er genau einmal im Repo steht; `24-08-SUMMARY.md:281` sieht genau diesen Fall vor ("wenn 24-09 ihn dort lieber haette, muss er in standalone-oauth.md weichen"). Er steht jetzt in `docs/token-exchange.md`, und `docs/standalone-oauth.md` schickt den Leser einen Klick weit dorthin, ohne die Aussage zu verlieren. Gegengeprueft: `grep -rl "exchange-evidence.md" docs/ README.md | wc -l` ergibt 1.
- **Die Vorgabewerte stehen nicht in der Doku.** Die Tabelle nennt je Variable, was sie entscheidet, und ein eigener Absatz sagt, dass die Werte im Docstring von `oauth/chain.py` leben und dort die einzige Quelle sind. Der einzige Vorgabewert, den die Seite ausschreibt, ist der Schluesselsatz-Pfad, weil die Keycloak-Seite dagegen eingerichtet wird, und genau dieser eine wird vom Gate gegen `chain.DEFAULT_JWKS_PATH` gehalten.
- **Die Bodygrenze steht als Vielfaches, nicht als Zahl.** Der Code schreibt sie als `2 * MAX_TOKEN_BYTES`, die Doku sagt "twice `MAX_TOKEN_BYTES`", und das Gate prueft, dass das Ergebnis der Rechnung als Literal **nicht** auf der Seite steht. Eine Zahl dort waere genau die Doppelpflege, gegen die das Gate existiert.
- **Die drei denkbaren Rollen des oauth2-Clients werden nicht aufgezaehlt.** Der Owner-Entscheid lautet "offen markiert". Eine Aufzaehlung von drei Moeglichkeiten liest sich als Vorauswahl, und die Seite haette damit doch eine Vermutung transportiert. Sie sagt stattdessen, dass die Rollen aus nichts in diesem Repo unterscheidbar sind.
- **Die Abschnitte sind nummeriert.** Das macht die Forderung "zehn erkennbare Abschnitte" pruefbar und gibt dem Gate zwei stabile Anker fuer die beiden Ehrlichkeitsabschnitte.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Der Worktree hatte kein eigenes venv**
- **Found during:** Task 2, beim ersten Verify-Lauf
- **Issue:** `uv run` fand im Worktree keine Umgebung. Ohne eigenes venv haette der Lauf ausserdem den Quellbaum des Hauptcheckouts importiert und damit nicht den Code geprueft, den dieser Plan beschreibt. Derselbe Befund steht schon in `24-08-SUMMARY.md` unter "Issues Encountered".
- **Fix:** `uv sync --all-extras` im Worktree, danach alle Laeufe mit `uv run --no-sync`.
- **Files modified:** keine (Umgebung, nicht Quelltext)
- **Verification:** `uv run --no-sync pytest` laeuft im Worktree gegen den Worktree-Baum.
- **Committed in:** kein Commit noetig

**2. [Rule 3 - Blocking] Der Verweis auf die Messdatei musste wandern statt zu entstehen**
- **Found during:** Task 3
- **Issue:** Der Plan verlangt den Verweis in `docs/token-exchange.md` und zugleich, dass er genau einmal im Repo steht. Plan 24-08 hatte ihn bereits in `docs/standalone-oauth.md` gesetzt. Beides zusammen ist nur erfuellbar, wenn er umzieht.
- **Fix:** Verweis in `docs/token-exchange.md` gesetzt, aus `docs/standalone-oauth.md` entfernt, und der Satz dort so umgeschrieben, dass der Leser die Aussage behaelt und die Messung einen Klick weiter findet. `24-08-SUMMARY.md:281` sieht diesen Fall ausdruecklich vor.
- **Files modified:** `docs/standalone-oauth.md`, `docs/token-exchange.md`
- **Verification:** `grep -rl "exchange-evidence.md" docs/ README.md | wc -l` ergibt 1.
- **Committed in:** `7ab3bba`

---

**Total deviations:** 2 auto-fixed (beide blockierend)
**Impact on plan:** Kein Scope Creep. Die erste ist Umgebung, die zweite ist die einzige Lesart, in der zwei Plan-Forderungen gleichzeitig gelten koennen.

## Authentication Gates

Keine.

## Issues Encountered

- **`ruff format --check` fiel nach dem Anlegen der Testdatei an einer Zeile.** `uv run ruff format tests/unit/test_docs_exchange_truth.py` hat sie geraderueckt, danach 274 Dateien formatiert.
- **`README.md` enthaelt ein vorbestehendes Nicht-ASCII-Zeichen (U+00E7).** Es stammt nicht aus der Aenderung dieses Plans und wurde nicht angefasst (Scope-Grenze). Em-Dashes: null in allen vier beruehrten Dateien.

## Verification

Alle Gates gruen, letzter Stand:

| Pruefung | Ergebnis |
|----------|----------|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 274 files already formatted |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings, 0 informations |
| `uv run vulture src scripts vulture_whitelist.py` | ohne Befund |
| `uv run pytest` | 4377 passed, 33 skipped, 168 deselected |
| `uv run pytest tests/unit/test_docs_exchange_truth.py tests/unit/test_docs_audit_truth.py tests/unit/test_exapp_env_setup.py -q` | gruen, 18 neue Tests darunter |
| Nummerierte Abschnitte in `docs/token-exchange.md` | 1 bis 10, vollstaendig |
| `grep -c "occ oauth2:add-client" docs/token-exchange.md` | 3 |
| `grep -c "mcp_connector:exchange:check" docs/token-exchange.md` | 2 |
| `grep -c "gets its own setup document" docs/standalone-oauth.md` | 0 |
| `grep -c "token-exchange.md" README.md` / `docs/standalone-oauth.md` | 1 / 1 |
| `grep -rl "exchange-evidence.md" docs/ README.md \| wc -l` | 1 |
| Em-Dashes (U+2014/U+2013) in den vier beruehrten Dateien | 0 |
| Nicht-ASCII in `docs/token-exchange.md` | 0 |

**Die Gegenprobe des Gates, gefahren statt behauptet.** Eine erfundene Variable `NC_MCP_EXCHANGE_TELEPORT` wurde in `docs/token-exchange.md` eingefuegt und der Lauf wiederholt:

```
FAILED tests/unit/test_docs_exchange_truth.py::test_the_page_invents_no_variable
AssertionError: docs/token-exchange.md names variables the code does not have:
['NC_MCP_EXCHANGE_TELEPORT']. config.EXCHANGE_VARIABLES is the list that exists
```

Die Injektion wurde danach mit `git checkout -- docs/token-exchange.md` zurueckgenommen und die Abwesenheit gegengeprueft (`grep -c TELEPORT` ergibt 0). Dieselbe Gegenprobe laeuft zusaetzlich bei jedem Lauf in-process als `test_the_counter_check_of_the_variable_gate`, damit sie nicht nur einmal von Hand stattgefunden hat.

## Threat Model Coverage

| Threat ID | Disposition | Wie erfuellt |
|-----------|-------------|--------------|
| T-24-11 (Spoofing, Fehlleitung) | mitigate | Die Audience-Konvention steht als "Recommendation, not a rule." mit dem Verweis auf die offene F13-Entscheidung 1; die Rolle des oauth2-Clients ist als offene Antwort markiert; beide Ehrlichkeitsabschnitte sind eigene Abschnitte und ihre Anwesenheit ist ein Test |
| T-24-35 (Tampering, Doppelpflege) | mitigate | Die Vorgabewerte stehen nur im Docstring von `oauth/chain.py`; das Gate haelt die Variablenliste in beide Richtungen und prueft das Literal der Bodygrenze als abwesend |
| T-24-06 (Information Disclosure, Trockenlauf) | mitigate | Abschnitt 6 sagt, dass der Tokenwert in der Prozessliste des Nextcloud-Hosts und in der Shell-Historie steht, warum es keinen Weg daran vorbei gibt, und empfiehlt ausdruecklich ein kurzlebiges Testtoken |
| T-24-36 (Information Disclosure, PHP-Strecke) | mitigate | Abschnitt 9 sagt, dass HaRP die Kopfzeilen an den `user-info`-Weg weitergibt, das fremde Token also bei jeder Anfrage durch Apache laeuft, und dass die 400-Zeile eine Eigenschaft der Umgebung ist |
| T-24-37 (Denial of Service, fetter Mapper) | mitigate | Abschnitt 8 nennt die gemessene Schwelle (ca. 68 Rollen und 68 Gruppen) und richtet den Rat, den Mapper schlank zu halten, ausdruecklich an die F13-Seite |
| T-24-SC (Supply Chain) | accept | Dieser Plan installiert kein Paket; `pyproject.toml` und `uv.lock` sind im Diff nicht enthalten |

## Known Stubs

Keine. Die Seite beschreibt ausschliesslich Code, der existiert, und Messungen, die gefahren wurden. Die einzige bewusst unbeantwortete Stelle ist die Rolle des `occ oauth2:add-client`-Schritts, und sie ist auf Owner-Entscheid als offen markiert statt stillschweigend gefuellt.

## Threat Flags

Keine neue Angriffsflaeche: dieser Plan aendert vier Dateien, von denen drei Prosa sind und die vierte ein Test ist, der nichts ausfuehrt ausser Lesen.

## Next Phase Readiness

- **EXCH-08 ist erfuellt.** Die Seite existiert, ist aus beiden Nachbardokumenten verlinkt und an den Code gebunden.
- **Vertagt, nicht erledigt:** die Frage an F13 nach der Rolle des Nextcloud-eigenen oauth2-Clients. Der Owner hat sie am 24.09.2026 vertagt. Wenn die Antwort kommt, ist die Stelle im Repo eindeutig: der Merkkasten in Abschnitt 7 von `docs/token-exchange.md` und der Test `test_the_playbook_marks_the_role_of_the_client_as_open`, der beim Umschreiben rot wird und damit daran erinnert.
- **Ebenfalls offen, extern getaktet:** F13s vier Entscheidungen (Audience-Konvention, Konto-Claim, Beispiel-Token und Realm-Export, Exchange-Ziel-Eintrag). Alles, was daran haengt, ist Konfigurationsflaeche mit dokumentiertem Vorgabewert.
- **Kein Release, kein Tag, keine Store-Aktion.** Diese Phase endet mit der Doku.

`.planning/STATE.md` und `.planning/ROADMAP.md` wurden von diesem Agenten bewusst nicht angefasst.

## Self-Check: PASSED

- `docs/token-exchange.md` existiert (FOUND)
- `tests/unit/test_docs_exchange_truth.py` existiert (FOUND)
- `docs/standalone-oauth.md` und `README.md` sind im Diff der beiden Commits (FOUND)
- Commit `dc6b65f` steht in der Historie dieses Worktrees (FOUND)
- Commit `7ab3bba` steht in der Historie dieses Worktrees (FOUND)
- Keine der beiden Commits loescht eine verfolgte Datei (geprueft mit `git diff --diff-filter=D`)
- Der Arbeitsbaum war nach Task 3 sauber

---
*Phase: 24-audit-anschluss-und-nachweis*
*Plan: 09*
*Completed: 2026-09-24*

---
phase: 24-audit-anschluss-und-nachweis
plan: 04
subsystem: auth
tags: [oauth, token-exchange, audit-trail, ast-gate, wiring, layering]

# Dependency graph
requires:
  - phase: 24-02
    provides: "die sechs Ablehnungsbezeichner an ExchangeRefused.reason, die eine Abweisungszeile traegt"
  - phase: 24-03
    provides: "RefusalWriter.note_refusal, die Kettenart x:exchange und die Zeilenart refusal"
  - phase: 23-02
    provides: "build_chain(..., accounts=None) als die Form, in der eine Faehigkeit hereingereicht wird"
provides:
  - "oauth/chain.RefusalNote: der Typalias der hereingereichten Ablehnungsmeldung"
  - "build_chain(..., refusals=None) und ChainedVerifier(..., refusals=None)"
  - "ChainedVerifier._note: eine Meldung je abgewiesenem Versuch, die nie eine Antwort aendert"
  - "ChainedVerifier._exchange_identity: die vier Kontoabweisungen mit einer Antwort und einer Zeile"
  - "die Verdrahtung des Schreibers in entry_exapp.build_exapp_app"
  - "tests/contract/test_no_claim_leak.py: drei Gates gegen einen Claim in der Abweisungszeile"
affects: [24-06, 24-07, 24-08, 24-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Eine Faehigkeit als Typalias hereinreichen statt als Protokollklasse zu importieren, wenn die Importrichtung zu bleiben soll"
    - "Mehrere Abweisungszweige hinter eine Methode ziehen, damit 'eine Zeile je Abweisung' strukturell statt gewohnheitsmaessig gilt"
    - "AST-Gate ueber Aufrufstellen plus Wortgrenzen-Gate ueber gemessene Quelltextzeilen, beide mit Gegenprobe ueber dieselbe Funktion"

key-files:
  created:
    - tests/contract/test_no_claim_leak.py
  modified:
    - src/mcp_connector/oauth/chain.py
    - src/mcp_connector/entry_exapp.py
    - src/mcp_connector/entry_oauth.py
    - vulture_whitelist.py
    - tests/unit/test_oauth_exchange_chain.py
    - tests/unit/test_exapp_entry.py
    - tests/unit/test_entry_oauth.py

key-decisions:
  - "Ein Typalias RefusalNote statt einer Protokollklasse aus audit/: die Kette weiss nur, dass sie eine asynchrone Funktion mit einer Zeichenkette rufen darf, und oauth/ importiert weiterhin nichts aus audit/"
  - "Die vier Kontoabweisungen ziehen in _exchange_identity und werden an einer Stelle gemeldet: 'eine Zeile je abgewiesenem Versuch' ist damit eine Eigenschaft der Struktur und keine Gewohnheit von vier Zweigen"
  - "Auch eine Kontoquelle, die nein sagt, erzeugt eine Zeile: errors.py fuehrt diesen Fall ausdruecklich unter exchange_account, und er ist die haeufigste Abweisung eines armierten Betriebs"
  - "entry_oauth bekommt refusals=None, ausdruecklich und begruendet am Aufrufort: der Standalone-Betrieb hat keinen Recorder, keinen Sweep und keinen Leser"
  - "Der Audit-Opener zieht in entry_exapp.py ueber den Kettenbau, nicht der geoeffnete Store: die Reihenfolge kostet nichts, weil der Opener nichts oeffnet"
  - "Das Namensgate arbeitet auf Wortgrenzen und nicht auf Teilzeichenketten: audit_store traegt aud, substr traegt sub"

patterns-established:
  - "Buchhaltung an einer Transportgrenze: jede Ausnahme des Schreibers endet in einer Zeile mit type(exc).__name__, nie in der Antwort"
  - "Eine bewusst ausgelassene Verdrahtung steht als benanntes Argument mit Begruendung am Aufrufort und wird von einem Test gehalten"

requirements-completed: [AUDIT-07]

# Metrics
duration: 70min
completed: 2026-09-24
---

# Phase 24 Plan 04: Der Ablehnungsschreiber an der Pruefkette Summary

**Ein abgewiesener Exchange-Versuch hinterlaesst im ExApp-Betrieb mit eingeschaltetem Audit-Log genau eine Zeile in `x:exchange`, die einen der sechs Bezeichner traegt und keinen Wert aus dem Token, und drei Quelltext-Gates halten das gegen jeden kuenftigen Diff.**

## Performance

- **Duration:** ca. 70 min
- **Tasks:** 3 von 3
- **Commits:** 5 (zwei TDD-Paare plus ein reiner Test-Commit)
- **Files modified:** 8 (1 neu, 7 geaendert), 912 Zeilen hinzu, 25 entfernt

## Accomplishments

- **Die Faehigkeit reist, der Import nicht.** `type RefusalNote = Callable[[str], Awaitable[None]]` in `oauth/chain.py`, vierter Schluesselwortparameter von `build_chain` und von `ChainedVerifier`. `grep -c "from ..audit\|from mcp_connector.audit" src/mcp_connector/oauth/chain.py` ergibt 0: die Schichtregel haelt, weil der Einstiegspunkt die gebundene Methode hereinreicht und die Kette nur weiss, dass sie eine asynchrone Funktion mit einem Bezeichner rufen darf. Dieselbe Form, in der `accounts` seit Phase 23 reist.
- **Eine Meldung je Abweisung, und nie eine geaenderte Antwort.** `ChainedVerifier._note` ruft den Schreiber, wenn einer da ist, und verschluckt jede Ausnahme daraus in einer Zeile mit `type(exc).__name__` (T-24-19). Gemessen mit einem Schreiber, der `OSError` wirft: `verify_token` antwortet `None`, nichts verlaesst die Methode, und die Zeile traegt den Typ und nicht die Meldung, weil die Meldung eines Store-Fehlers einen Pfad traegt (D-13).
- **Die Kontoabweisungen haben eine Antwort.** Die vier Wege, auf denen `resolve_identity` nein sagt (keine Kontoquelle, kein Mapping-Ergebnis, eine Quelle die nein sagt, eine Quelle die wirft), liegen jetzt in `_exchange_identity` und werden an genau einer Stelle gemeldet. Eine fuenfte Abweisung dort unten wird damit mitgeschrieben, ohne dass jemand an die Meldung denken muss.
- **Die Verdrahtung, mit beiden Bedingungen.** `entry_exapp.py` baut den Schreiber genau dann, wenn `config.audit_log_enabled(env)` wahr ist **und** `exchange_config is not None`, und er bekommt den Opener, den auch der `Recorder` bekommt. Das ist mit `is` gemessen: ein zweiter Opener waere ein zweiter `AuditStore` auf derselben Datei, und die Groessengrenze von D-11 rechnete ueber einen davon, waehrend beide schrieben.
- **Der Beweis am Ende der Strecke.** Ein `Bearer a.b.c` gegen die gebaute ExApp-Anwendung erzeugt genau eine Zeile: `chain=x:exchange`, `kind=refusal`, `outcome=rejected`, `reason=exchange_malformed`, `removed=1`, `actor` leer, `nc_user` leer. Kein Wert des Tokens, des Issuers, der `azp`-Liste oder des Kontoclaims steht in der Zeile, und die Schluesselsatz-Route bleibt bei null Abrufen. Mit ausgeschaltetem Audit-Log liefert dieselbe Anfrage dieselbe 401 und **keine Datei**.
- **Das Gate.** `tests/contract/test_no_claim_leak.py` mit neun Faellen: drei Gates und zu jedem seine Gegenprobe ueber dieselbe Funktion, plus zwei Faelle, die beweisen, dass weder die Aufrufstellen-Liste noch die Namensliste Dekoration ist.

## Task Commits

1. **Task 1: Der Ablehnungsschreiber als hereingereichte Faehigkeit** - `4cbc04a` (test, RED) / `63f0e79` (feat, GREEN)
2. **Task 2: Die Verdrahtung an beiden Einstiegspunkten** - `3a2ce8a` (test, RED) / `d8d86c0` (feat, GREEN)
3. **Task 3: Das Gate gegen Claim-Leaks** - `c4098f5` (test)

Task 3 ist reine Testarbeit und hat folgerichtig keinen `feat`-Commit: das Verhalten, das sie misst, ist der Quelltext selbst, und der war an der Stelle bereits richtig. Ein GREEN-Schritt haette nichts zu implementieren gehabt. Dasselbe Muster wie Task 3 von Plan 24-02. Ein REFACTOR-Schritt war in keinem der drei Zyklen noetig.

## Files Created/Modified

- `src/mcp_connector/oauth/chain.py` - `RefusalNote`, der vierte Parameter an beiden Stellen, `_note`, `_exchange_identity`, die Meldungen in den beiden `except`-Zweigen von `verify_token`, der neue Absatz im Docstring von `build_chain`.
- `src/mcp_connector/entry_exapp.py` - der Audit-Opener zieht ueber den Kettenbau, der Schreiber wird mit seinen zwei Bedingungen gebaut, `refusals=` an `build_chain`.
- `src/mcp_connector/entry_oauth.py` - `refusals=None` als benanntes Argument, mit dem Absatz, der sagt warum (siehe Entscheidung unten).
- `vulture_whitelist.py` - `_.note_refusal` ist raus; der Eintrag hatte sein Ende selbst angekuendigt, und dieser Plan ist der Aufrufer.
- `tests/contract/test_no_claim_leak.py` (neu) - 331 Zeilen, neun Faelle.
- `tests/unit/test_oauth_exchange_chain.py` - dreizehn Faelle: der Aus-Zustand mit und ohne Schreiber, die sechs Verhaltenszeilen, der werfende Schreiber, der Store-Token der nie gemeldet wird, und die drei Faelle um `build_chain`.
- `tests/unit/test_exapp_entry.py` - `refusal_writer_of`, fuenf Faelle: die beiden Bedingungen, der gemeinsame Opener, die Zeile am Ende der Strecke und die fehlende Datei im Aus-Zustand.
- `tests/unit/test_entry_oauth.py` - ein parametrisierter Fall, der die Entscheidung fuer den Standalone-Betrieb haelt.

## Entscheidung: `entry_oauth.py` fuehrt keine Abweisungszeilen

Der Plan verlangt fuer diesen Punkt eine ausdrueckliche Entscheidung statt eines stillen Auslassens (T-24-21). Sie lautet: **`refusals=None`**, als benanntes Argument am Aufrufort, mit der Begruendung im Kommentar darueber und mit einem Test, der sie haelt. Gemessen am Stand vor diesem Plan fehlen dem Standalone-Betrieb alle drei Dinge, die eine solche Zeile erst wertvoll machen:

| Was fehlt | Gemessen an | Folge fuer eine Abweisungszeile |
|-----------|-------------|----------------------------------|
| Ein `Recorder` | `entry_oauth.py` baut keinen; `grep -c audit` ergab 0 Treffer im Quelltext | Kein Werkzeugaufruf dieses Prozesses wird aufgezeichnet. Der Schalter `NC_MCP_AUDIT_LOG` entscheidet hier heute nichts, und eine Verdrahtung nur der Abweisungen gaebe einer Variablen zwei verschiedene Bedeutungen in zwei Betriebsarten |
| Ein Sweep | `audit/record.py:263` (`should_sweep` am Schreibweg des Recorders) und `entry_exapp._audit_startup` sind die beiden einzigen Ausloeser | Die Zeilen saessen weder das Verfallsfenster noch die Groessengrenze ab, die `docs/privacy.md` ihnen zusagt. Auf einem Weg, den ein Fremder faehrt, waere das eine Datei, die waechst und die niemand fegt |
| Ein Leser | `audit_read_routes` und `audit_verify_routes` haengen nur in `entry_exapp.py`, occ existiert nur im ExApp-Modus | Niemand koennte die Zeilen zurueckholen |

Das ist dieselbe Grenze, die die Recherche fuer den Trockenlauf gezogen hat (Open Question 2, aufgeloest in Plan 24-05: nur der ExApp-Betrieb bekommt eine Oberflaeche). **Was das aendern wuerde,** ist ein Audit-Pfad fuer die fuenfte Betriebsart, also ein `Recorder`, ein Sweep-Ausloeser und ein Leseweg: eine eigene Phase und kein Schluesselwortargument. Bis dahin steht die Entscheidung im Quelltext, im Test `test_the_standalone_chain_notes_no_refusal_whatever_the_audit_switch_says` (parametrisiert **mit** eingeschaltetem Audit-Log, damit die Abwesenheit genau fuer die Umgebung gilt, in der ein Betreiber etwas erwarten wuerde) und hier.

**`config.EXCHANGE_VARIABLES` ist unangetastet:** zehn Eintraege vor und nach diesem Plan, `git diff e44d89f..HEAD -- src/mcp_connector/config.py` ist leer. Es ist keine Umgebungsvariable hinzugekommen; die Fensterlaenge der Bremse bleibt fest verdrahtet in `audit/refusals.REFUSAL_WINDOW_SECONDS`. `uv run pytest tests/unit/test_exapp_env_setup.py -q` laeuft gruen.

## Decisions Made

**1. Ein Typalias und keine Protokollklasse.**
`oauth/` darf nichts aus `audit/` importieren, und eine Protokollklasse aus `audit/refusals.py` waere genau dieser Import gewesen. Der Alias sagt alles, was die Kette wissen darf: eine asynchrone Funktion, ein Zeichenkettenargument, keine Antwort. Gehalten wird die Richtung vom grep-Kriterium dieses Plans, nicht von `tests/contract/test_module_boundaries.py` (die Datei prueft etwas anderes, nachgesehen am 2026-09-23 und im Moduldocstring von `audit/refusals.py` festgehalten).

**2. Die vier Kontoabweisungen bekommen eine Antwort und eine Meldung.**
Der Plantext nennt "genau vier Stellen" fuer die Hilfsmethode. Umgesetzt sind es **drei**: zwei in `verify_token` und eine in `resolve_identity`, weil die vier Abweisungswege des Kontozweigs in `_exchange_identity` gezogen wurden und von aussen eine Antwort sind. Der Grund ist derselbe, den `oauth/verifier.py` fuer seine eigenen Abweisungen gibt und den `oauth/exchange_accounts.py` fuer diese Naht wiederholt: von aussen ist es eine Antwort. Der Gewinn ist, dass "eine Zeile je abgewiesenem Versuch" strukturell gilt: ein fuenfter Abweisungsweg in dieser Methode wird mitgeschrieben, ohne dass jemand an eine fuenfte Meldezeile denken muss. Die Alternative waeren vier gleiche Einzeiler gewesen, also genau die Form, aus der R-18-06 dieses Repos entstanden ist.

**3. Der Aus-Zustand ist eine Abwesenheit und kein leerer Schreiber.**
`refusals=None` heisst: kein Objekt, kein Store, kein Codepfad. Gemessen an drei Stellen: `build_chain` im Aus-Zustand gibt weiter das Argument selbst zurueck (auch mit einem Schreiber in der Hand), die armierte Kette ohne Schalter traegt `None`, und der Konstruktor von `RefusalWriter` explodiert im Test, wenn der Exchange-Pfad aus ist.

**4. Das Namensgate arbeitet auf Wortgrenzen.**
`aud` steckt in `audit_store`, `sub` in `substr`, und ein Gate auf Teilzeichenketten waere am Tag seiner Entstehung rot gewesen. Repariert haette man es, indem man eine Variable umbenennt, was nichts beweist. Die Muster sind `\bname\b`, gross-/kleinschreibungsunempfindlich, damit auch ein `Claims` in einem Typnamen faellt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Eine Kontoquelle, die nein sagt, erzeugt jetzt ebenfalls eine Zeile**

- **Found during:** Task 1
- **Issue:** Die Verhaltenszeile des Plans nennt drei Kontofaelle (fehlende Quelle, kein Mapping-Ergebnis, werfende Quelle) und laesst den vierten aus: eine vorhandene Kontoquelle, die `None` antwortet. Das ist im armierten Betrieb die **haeufigste** Abweisung ueberhaupt: ein geprueftes Token eines gemappten Principals, fuer den es keine Bindung beziehungsweise kein Konto gibt (CRED-02). Ohne Zeile waere genau der Fall unsichtbar geblieben, den ein Betreiber am ehesten sucht, und `errors.py:50` fuehrt ihn ausdruecklich unter `exchange_account` ("the mapping yields no principal, there is no account source, **or the source says no**").
- **Fix:** Die vier Wege liegen in `_exchange_identity`; `resolve_identity` meldet einmal, wenn dort nichts herauskommt. Damit ist der Fall gedeckt, ohne dass eine vierte Meldezeile entsteht.
- **Files modified:** `src/mcp_connector/oauth/chain.py`
- **Verification:** `test_an_account_source_that_says_no_is_noted_as_an_account_refusal`, plus die drei Faelle der uebrigen Wege und `test_a_served_call_is_never_noted` als Gegenprobe.
- **Committed in:** `63f0e79`

**2. [Rule 3 - Blocking] Der Audit-Opener musste ueber den Kettenbau ziehen**

- **Found during:** Task 2
- **Issue:** `audit_opener(env)` stand in `entry_exapp.py` rund zwanzig Zeilen **unter** `build_chain`, und der Schreiber braucht ihn als Argument. Der Plan sagt "Loese es ueber den Opener und ziehe die Reihenfolge nicht um".
- **Fix:** Genau das: die eine Zuweisung `audit_store = audit_opener(env)` zieht mitsamt ihrem Kommentar ueber den Kettenbau, und was hereingereicht wird, ist der Opener und nie ein geoeffneter Store. Die Reihenfolge der **Oeffnung** aendert sich dadurch nicht, denn der Opener oeffnet nichts: die erste Zeile, die die Datei braucht, bezahlt das Oeffnen, genau wie beim `Recorder`. Der Kommentar an der Zuweisung sagt das jetzt ausdruecklich, damit niemand sie spaeter wieder nach unten schiebt.
- **Files modified:** `src/mcp_connector/entry_exapp.py`
- **Verification:** `test_the_armed_path_with_the_log_on_writes_into_the_store_of_this_application` (`writer.store_provider is recorder.store_provider`) und die Zeile am Ende der Strecke, die in derselben Datei landet.
- **Committed in:** `d8d86c0`

**3. [Rule 2 - Missing Critical] `vulture_whitelist.py` ausserhalb der Dateiliste**

- **Found during:** Task 2
- **Issue:** Der Verifikationsteil des Plans verlangt, dass die Eintraege aus Plan 24-03 wieder entfernt werden, `files_modified` nennt die Datei aber nicht. Ohne die Entfernung waere der Eintrag `_.note_refusal` eine Whitelist-Zeile fuer ein Symbol mit Aufrufer geworden, also genau die tote Zeile, gegen die die Datei geschrieben ist.
- **Fix:** Der Eintrag ist raus, der Abschnitt bleibt mit dem Satz stehen, der sagt, dass er sein Ende selbst angekuendigt hatte (dieselbe Form wie die drei Abschnitte darueber aus den Phasen 23 und 24-05). Die drei Eintraege von Plan 24-05 (`_.passed`, `_.limit_sentence`, `_.cost_sentence`) bleiben unberuehrt: sie kuendigen Plan 24-06 als ihr Ende an.
- **Files modified:** `vulture_whitelist.py`
- **Verification:** `uv run vulture src scripts vulture_whitelist.py` ohne Befund.
- **Committed in:** `d8d86c0`

---

**Total deviations:** 3 auto-fixed (2 fehlende kritische Funktionalitaet, 1 blockierend)
**Impact on plan:** Kein Scope Creep. Deviation 1 schliesst den Fall, den `errors.py` selbst zu diesem Bezeichner zaehlt, Deviation 2 ist die vom Plan verlangte Loesung ueber den Opener, Deviation 3 ist eine Datei, die der Plantext verlangt und in seiner Dateiliste vergessen hat.

## Issues Encountered

- **`recorder_of` sieht bei armiertem Pfad nichts.** Der bestehende Helfer in `test_exapp_entry.py` liest `route.app._audit_recorder` von der aeussersten Schicht der `/mcp`-Route. Mit armiertem Exchange-Pfad ist das die `Throttled`-Huelle von EXCH-05 und nicht die Transportgrenze, also antwortete er `None`. Der neue Fall liest den Recorder ueber `boundary_of(app)`, mit einem Kommentar, der den Grund nennt. `recorder_of` selbst bleibt unveraendert: seine bisherigen Aufrufer bauen alle unarmierte Anwendungen.
- **Ein Teilzeichenketten-Gate waere sofort rot gewesen.** Der erste Entwurf der Namensliste suchte nach `aud` und traf `audit_store` in der Datei, die er bewacht. Die Wortgrenzen sind die Antwort, und der Kommentar an den Mustern nennt beide Beispiele, damit die naechste Hand es nicht anders herum repariert.

## Verification

Alle Gates vor jedem Commit gruen, am Ende noch einmal vollstaendig:

- `uv run pytest -q`: **4331 passed, 33 skipped, 168 deselected** in 144 s
- `uv run ruff check .`: All checks passed
- `uv run ruff format --check .`: 267 files already formatted
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings, 0 informations
- `uv run vulture src scripts vulture_whitelist.py`: ohne Befund
- `uv run pytest tests/contract -q`: gruen, einschliesslich `test_no_claim_leak.py`

Akzeptanzkriterien einzeln gemessen:

| Kriterium | Messung | Ergebnis |
|-----------|---------|----------|
| Der `is`-Fall des Aus-Zustands laeuft unveraendert | `test_the_off_state_hands_back_the_very_same_verifier` | gruen, plus der neue Zwilling mit Schreiber |
| Sechs Verhaltenszeilen als Faelle | Abweisung, unerwartete Ausnahme, drei Kontowege plus der vierte, Erfolgsfall | 13 neue Faelle in `test_oauth_exchange_chain.py` |
| Werfender Schreiber | `test_a_writer_that_throws_leaves_the_answer_and_the_request_untouched` | `None` zurueck, nichts geworfen, eine Zeile mit `OSError` |
| `exapp/middleware.py` unveraendert | `git diff --stat src/mcp_connector/exapp/middleware.py` | leer |
| Keine Importrichtung nach `audit/` | `grep -c "from ..audit\|from mcp_connector.audit" src/mcp_connector/oauth/chain.py` | 0 |
| Eine Zeile in derselben Audit-Datei | `test_a_refused_exchange_attempt_becomes_one_row_of_the_refusal_chain` | 1 Zeile, `x:exchange`/`refusal`/`rejected`/`exchange_malformed`/`removed=1` |
| Audit-Log aus: keine Zeile, keine Datei | `test_with_the_audit_log_off_the_same_attempt_leaves_no_file_at_all` | `audit.sqlite3` existiert nicht |
| Kein Schreiber ohne Exchange-Pfad | `test_without_the_exchange_namespace_no_writer_is_built_at_all` | Konstruktor explodiert, Bau gelingt |
| `refusals=` je Einstiegspunkt | `grep -vn '^\s*#' entry_exapp.py \| grep -c "refusals="` / dasselbe fuer `entry_oauth.py` | 1 / 1 |
| Keine neue Umgebungsvariable | `tests/unit/test_exapp_env_setup.py`, `len(config.EXCHANGE_VARIABLES)` | gruen, 10 |
| Das Gate ist gruen und hat Gegenproben | `uv run pytest tests/contract/test_no_claim_leak.py -q` | 9 passed |
| `_code_lines` genau einmal, mit beiden Filtern | `grep -c "def _code_lines" tests/contract/test_no_claim_leak.py` | 1 |
| Befundtext beginnt mit Datei und Zeile | `test_the_gate_would_notice_the_acting_party_in_the_refusal_writer` | `audit/refusals.py:2:` |

## Known Stubs

Keine. Jede Funktion dieses Plans ist verdrahtet und von Tests gefahren. `refusals=None` in `entry_oauth.py` ist kein Stub, sondern eine benannte, begruendete und getestete Entscheidung (Abschnitt oben).

## Threat Flags

Keine. Dieser Plan legt keine neue Netzwerkoberflaeche, keinen neuen Auth-Pfad und keine Schemaaenderung an einer Vertrauensgrenze an. Die einzige neue Schreibstelle ist der bereits gebremste Schreiber aus Plan 24-03, jetzt mit Aufrufer, und die vier Eintraege des `<threat_model>` sind einzeln gemessen: T-24-04 (das Gate), T-24-03 (die Byte-Gleichheit der vier Tokens laeuft unveraendert gruen), T-24-19 (der werfende Schreiber), T-24-20 (`middleware.py` unveraendert), T-24-21 (die begruendete Entscheidung plus ihr Test).

## An die Folgeplaene uebergeben

- **24-06 (occ):** Der Eintrag `REFUSALS_KEYWORD` in `OCC_AUDIT_READ_USER_DESCRIPTION` steht weiterhin aus (aus 24-03 uebergeben) und ist jetzt erst recht faellig: ab diesem Plan stehen tatsaechlich Zeilen in der Kette, die das Wort liest.
- **24-09 (`docs/token-exchange.md`):** Die Grenze des Standalone-Betriebs gehoert benannt, in derselben Zeile wie die des Trockenlaufs: im ExApp-Betrieb sind abgewiesene Versuche in der Audit-Kette sichtbar, im Standalone-Betrieb nicht. Die Tabelle oben ist die Quelle dafuer.
- **24-07/24-08 (Nachweis):** Eine abgewiesene Anfrage ist ab jetzt in `occ mcp_connector:audit:read --user=refusals` sichtbar; der Messnachweis kann sie zeigen, ohne den Ablauf zu veraendern.

## Self-Check: PASSED

Alle acht in diesem SUMMARY genannten Dateien liegen auf der Platte, alle fuenf genannten Commits (`4cbc04a`, `63f0e79`, `3a2ce8a`, `d8d86c0`, `c4098f5`) stehen in `git log`. Die TDD-Tore halten fuer die beiden Tasks, die Quelltext anfassen: je ein `test(...)` vor seinem `feat(...)`. `STATE.md` und `ROADMAP.md` wurden nicht angefasst: dieser Lauf ist ein Worktree-Agent, die Schreibrechte an beiden liegen beim Orchestrator.

---
*Phase: 24-audit-anschluss-und-nachweis*
*Completed: 2026-09-24*

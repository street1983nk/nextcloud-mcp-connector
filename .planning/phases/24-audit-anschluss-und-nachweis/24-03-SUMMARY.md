---
phase: 24-audit-anschluss-und-nachweis
plan: 03
subsystem: audit
tags: [sqlite, audit-trail, hash-chain, rate-limit, oauth-token-exchange, occ]

# Dependency graph
requires:
  - phase: 24-01
    provides: "die actor-Spalte und ihre Reinigungsregel, gegen die die Abweisungszeile sich abgrenzt (actor bleibt leer)"
  - phase: 24-02
    provides: "die sechs Ablehnungsbezeichner in errors.REASONS, die eine Abweisungszeile in reason traegt"
  - phase: 18
    provides: "AuditStore, Sweep, Groessengrenze, Kontocheck D-12, verify_chains"
provides:
  - "Eine dritte Kettenart x:exchange (CHAIN_EXCHANGE) mit EXCHANGE_CHAIN_PREFIX, die gefegt und geprueft wird"
  - "KIND_REFUSAL als vierten Wert der Spalte kind, ohne Migration und ohne Hashaenderung"
  - "_SILENT_CHAINS mit positivem Praefixfilter auf USER_CHAIN_PREFIX: der Kontocheck sieht nur noch Kontoketten"
  - "audit/refusals.RefusalWriter: die gebremste Schreibstelle des vor-authentischen Pfads"
  - "errors.known_reason als gemeinsame Regel beider Schreiber einer reason-Spalte"
  - "exapp/audit_read.REFUSALS_KEYWORD und eine removed-Spalte in Text und JSON"
affects: [24-04, 24-05, 24-06, 24-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Positiver Praefixfilter statt negativer Ausnahmeliste, sobald eine dritte Sorte derselben Spalte existiert"
    - "Schreibbremse je Bezeichner und Zeitfenster mit nachgeholter Zaehlung (removed)"
    - "Ein zweites reserviertes Wort einer --user-Option, mit demselben Aufloesungsmuster und demselben benannten Preis wie INSTANCE_KEYWORD"

key-files:
  created:
    - src/mcp_connector/audit/refusals.py
    - tests/unit/test_audit_refusals.py
  modified:
    - src/mcp_connector/audit/store.py
    - src/mcp_connector/audit/record.py
    - src/mcp_connector/errors.py
    - src/mcp_connector/exapp/audit_read.py
    - docs/privacy.md
    - vulture_whitelist.py
    - tests/unit/test_audit_store.py
    - tests/unit/test_audit_accounts.py
    - tests/unit/test_exapp_audit_read.py
    - tests/unit/test_docs_audit_truth.py

key-decisions:
  - "Die Abweisungen bekommen eine eigene Kettenart x:exchange, nicht i:instance, weil die Instanz-Kette von keiner der vier Sweep-Anweisungen angefasst wird und fremdbestellte Zeilen dort nie verfielen"
  - "_SILENT_CHAINS filtert positiv auf USER_CHAIN_PREFIX statt negativ auf CHAIN_INSTANCE: eine vierte Kettenart faellt damit per Voreinstellung heraus"
  - "Der Praefixvergleich ist substr(chain, 1, ?) = ? und nicht LIKE, weil SQLite in LIKE ASCII-Gross-/Kleinschreibung faltet"
  - "Die Bremse wird VOR dem Schreiben gestellt, nicht danach: ein Schreiber, der nur nach Erfolg bremst, geht bei einem defekten Store bei jeder Anfrage erneut hin"
  - "Ein rueckwaerts gestellter Zeitgeber oeffnet ein neues Fenster statt es fuer die Dauer des Sprungs zu schliessen"
  - "_known_reason zieht aus audit/record.py nach errors.py als known_reason, weil dort das frozenset liegt, das die Regel bewacht (R-18-06)"
  - "REFUSALS_KEYWORD gewinnt gegen ein gleichnamiges Konto, mit demselben benannten Preis, den INSTANCE_KEYWORD seit Plan 19-06 traegt"
  - "Die Spalte removed wird in Text und JSON sichtbar, weil sie der einzige Wert einer Abweisungszeile ist"

patterns-established:
  - "Neue Kettenart: Praefixkonstante plus fester Bezeichner, mit einem #:-Kommentar, der sagt warum sie nicht die Instanz-Kette ist"
  - "Neue Zeilenart: ein Wert in der bestehenden Spalte kind, nie eine achtzehnte Spalte"
  - "Eine umgedeutete Spalte bekommt beide Bedeutungen in den Schemakommentar, sonst ist die zweite eine stille Umdeutung"

requirements-completed: [AUDIT-07]

# Metrics
duration: 95min
completed: 2026-09-24
---

# Phase 24 Plan 03: Die Ablage und die Bremse der Abweisungen Summary

**Eine dritte, gefegte Kettenart `x:exchange` mit der Zeilenart `refusal`, eine Schreibbremse von hoechstens einer Zeile je Ablehnungsgrund und Fuenfminutenfenster mit nachgeholter Zaehlung, und ein reserviertes Wort, unter dem ein Betreiber die Kette mit `occ mcp_connector:audit:read` liest.**

## Performance

- **Duration:** ca. 95 min
- **Tasks:** 3 von 3
- **Commits:** 6 (drei TDD-Paare aus test und feat)
- **Files modified:** 12 (2 neu, 10 geaendert)

## Accomplishments

- **Der Ort.** `CHAIN_EXCHANGE = "x:exchange"` mit `EXCHANGE_CHAIN_PREFIX` und `KIND_REFUSAL = "refusal"`. Die Kette faellt ohne eine einzige geaenderte SQL-Anweisung unter Verfallsfenster und Groessengrenze, weil alle vier Sweep-Anweisungen `chain <> CHAIN_INSTANCE` tragen. `CANONICAL_FIELDS` wurde nicht angefasst, kein `ALTER TABLE` im Diff, kein Hash aendert sich.
- **Die Luecke, die das aufgerissen haette, ist zu.** `_SILENT_CHAINS` liefert nur noch Ketten mit dem Nutzerpraefix. Ohne diesen Filter haette der Kontocheck von D-12 die neue Kette nach 30 stillen Tagen als nicht existierendes Konto gemeldet und `drop_user_chain` haette sie geloescht (Pitfall 5, T-24-18). Ein Test in `test_audit_accounts.py` faehrt den **echten** Kontocheck mit einer gelesenen Kontoliste und beweist beides: das wirklich verschwundene Konto verliert seine Kette, die Abweisungskette steht.
- **Die Bremse.** `RefusalWriter.note_refusal` schreibt die erste Abweisung eines Grundes sofort und danach keine mehr, bis das Fenster um ist; die naechste Zeile traegt die unterdrueckten plus sich selbst. 1000 Abweisungen in einem Fenster sind genau eine Zeile mit `removed == 1`, die naechste traegt `removed == 1000`. Keine gezaehlte Abweisung geht verloren.
- **Die Sichtbarkeit.** `occ mcp_connector:audit:read --user=refusals` liest die Kette, in Text und in JSON, und `docs/privacy.md` beschreibt sie: was drinsteht, was ausdruecklich nicht (kein Token, kein Claim, keine Adresse, kein Schluesselmaterial), und dass sie unter demselben Fenster und derselben Grenze steht wie eine Nutzerkette.

## Task Commits

1. **Task 1: Die dritte Kettenart und die Zeilenart der Abweisung** - `09c75e4` (test, RED) / `99c2fa6` (feat, GREEN)
2. **Task 2: Die Schreibbremse des vor-authentischen Pfads** - `5706d74` (test, RED) / `7d35b7e` (feat, GREEN)
3. **Task 3: Die Abweisungskette lesbar machen und benennen** - `a0423ec` (test, RED) / `c363a29` (feat, GREEN)

Kein REFACTOR-Schritt war noetig; in keinem der drei Zyklen war der GREEN-Stand aufzuraeumen.

## Files Created/Modified

- `src/mcp_connector/audit/refusals.py` (neu) - `RefusalWriter` und `REFUSAL_WINDOW_SECONDS`. Das einzige Modul der Anwendung, das einen Zaehler haelt, und der Moduldocstring sagt warum das hier kein Widerspruch zu D-20 ist: hier **ist** der Zustand die Bremse.
- `tests/unit/test_audit_refusals.py` (neu) - elf Faelle, darunter der 1000-auf-1-Fall, die Fensterkante von beiden Seiten und der defekte Store, der genau einmal je Fenster gefragt wird.
- `src/mcp_connector/audit/store.py` - die beiden Kettenkonstanten, `KIND_REFUSAL`, die Schemakommentare fuer `chain`, `kind` und `removed`, der Praefixfilter in `_SILENT_CHAINS`.
- `src/mcp_connector/errors.py` - `known_reason` zieht hierher, zu dem `frozenset`, das sie bewacht.
- `src/mcp_connector/audit/record.py` - benutzt `known_reason` statt einer eigenen privaten Fassung.
- `src/mcp_connector/exapp/audit_read.py` - `REFUSALS_KEYWORD`, der Zweig in `_chain_of`, die Spalte `removed` in `_line` und `_document`.
- `docs/privacy.md` - ein eigener Abschnitt ueber die Abweisungskette, eine Zeile mehr in der Speichertabelle, ein Absatz im Retention-Teil.
- `vulture_whitelist.py` - ein Eintrag fuer `note_refusal`, der sein eigenes Ende ankuendigt (Plan 24-04 ruft die Methode auf).

## Leser der Spalte `chain`, einzeln geprueft

Die Liste aus 24-PATTERNS.md, Decision Point 3, Leser fuer Leser:

| Leser | Verhalten gegenueber `x:exchange` | Befund |
|-------|-----------------------------------|--------|
| `_SILENT_CHAINS` (store.py) | lieferte die Kette als Konto | **geaendert**: positiver Filter auf `USER_CHAIN_PREFIX` |
| `_account_of` (store.py) | schneidet nur `u:` ab, gaebe `x:exchange` unveraendert zurueck | unveraendert richtig, weil ihn nur noch Kontoketten erreichen |
| `_SWEEPABLE_TOTAL` (store.py) | zaehlt die Zeilen mit | richtig, Test `..._is_not_the_instance_chain` |
| `_EXPIRED_ROWS`, `_DROP_EXPIRED` | nehmen den verfallenen Praefix der Kette | richtig, Test `..._retention_window_takes_the_refusal_chain...` |
| `_OLDEST_ROWS`, `_DROP_OLDEST` | duerfen die Zeilen nehmen | richtig, Test `..._upper_bound_may_take_a_refusal_row` |
| `_CHAINS` / `verify_chains` | laeuft ueber die Kette wie ueber jede andere | richtig, Test `..._changed_refusal_row_is_found_like_any_other` |
| `_COUNT_OF_CHAIN`, `_DROP_CHAIN` | erreichbar nur aus `drop_user_chain`, das jeden Bezeichner durch `user_chain` praefixt | kann die Kette konstruktiv nicht treffen |
| `_write_markers` / Grabsteine | haengt den Grabstein in die Instanz-Kette, `gap_chain = x:exchange` | richtig, im Verfallstest mitgeprueft |
| `audit_read._chain_of` + `INSTANCE_KEYWORD` | haette `refusals` zu `u:refusals` gemacht | **geaendert**: zweiter Zweig auf `CHAIN_EXCHANGE` |
| `audit_read._line` / `_document` | drucken den Bezeichner durch `printable` | unveraendert richtig; die fehlende Spalte `removed` war der eigentliche Befund, siehe Deviation 1 |
| `audit_verify._printable` | reinigt jeden Bezeichner gleich | unveraendert richtig |

## Decisions Made

- **Positiver statt negativer Filter in `_SILENT_CHAINS`.** Der Plan verlangte einen Praefixfilter zusaetzlich zur bestehenden Ausnahme. Umgesetzt ist die Ausnahme **ersetzt**: `chain <> CHAIN_INSTANCE` und "jede Kontokette" waren dasselbe, solange es zwei Kettenarten gab, und hoeren mit der dritten auf, es zu sein. Eine vierte Kettenart faellt damit per Voreinstellung heraus, statt darauf zu warten, dass jemand an die Ausnahme denkt.
- **`substr(chain, 1, ?) = ?` statt `LIKE`.** SQLite faltet in `LIKE` die ASCII-Gross- und Kleinschreibung, ein Bezeichner mit grossem Buchstaben vor dem Doppelpunkt kaeme durch ein Muster aus dem kleingeschriebenen Praefix. Beide Werte reisen als Platzhalter aus `USER_CHAIN_PREFIX`, das geforderte `grep -c "'u:%'"` ergibt 0.
- **Die Bremse steht vor dem Schreiben.** Wer erst nach einem erfolgreichen `append` bremst, geht bei vollem Datentraeger bei **jeder** vor-authentischen Anfrage erneut zum Store, also genau bei der Last, gegen die die Klasse geschrieben ist. Der Preis steht im Docstring: eine gescheiterte Zeile verliert die Versuche, fuer die sie gestanden haette, und die Logzeile sagt es.
- **Ein Zeitgebersprung nach hinten oeffnet ein neues Fenster.** Sonst waere `at - opened` negativ und damit "unter dem Fenster", was bei einem grossen Sprung Stunden Stille bedeutet haette.
- **`known_reason` zieht nach `errors.py`.** Der Plan liess die Wahl zwischen Herausziehen und Importieren. Der private Name eines Nachbarmoduls ist ein Versprechen, das sein Besitzer zuruecknehmen darf; das `frozenset`, das die Regel bewacht, liegt in `errors.py`, also liegt die Regel jetzt dort. `record.py` und `refusals.py` benutzen dieselbe Funktion, nicht zwei Fassungen (R-18-06).
- **`REFUSALS_KEYWORD` gewinnt gegen ein gleichnamiges Konto.** Die Alternative waere eine zweite Aufloesungsregel neben der von `INSTANCE_KEYWORD` gewesen. Ein Unterschied zwischen zwei reservierten Woertern derselben Option ist der Unterschied, den an der Konsole niemand erinnert; der Preis steht an beiden Konstanten.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Die Spalte `removed` war in keiner Ausgabeform sichtbar**

- **Found during:** Task 3
- **Issue:** Das Verhalten von Task 3 verlangt, dass die Textzeile einer Abweisungszeile "die Anzahl" zeigt. `_line` hatte zehn Spalten und `removed` war in keiner davon, und `_document` fuehrte das Feld ebenfalls nicht. Damit waere der **einzige** inhaltliche Wert einer Abweisungszeile in keiner Ausgabeform dieses Kommandos lesbar gewesen, und Erfolgskriterium 2 der Phase (Sichtbarkeit) waere nur halb eingeloest.
- **Fix:** `removed` wird als elfte und letzte Spalte in `_line` gedruckt und als Schluessel in `_document` gefuehrt. Letzte Position, damit die zehn bestehenden Spalten ihre Indizes behalten und kein bestehender Fall umnummeriert werden musste. Ein Grabstein benutzt dieselbe Spalte mit derselben Bedeutung, also gewinnt auch die Instanz-Kette daran.
- **Files modified:** `src/mcp_connector/exapp/audit_read.py`, `tests/unit/test_exapp_audit_read.py`
- **Verification:** `LINE_COLUMNS` von 10 auf 11 gezogen (die Konstante existiert genau dafuer), neue Faelle fuer die Abweisungszeile und fuer den gewoehnlichen Aufruf mit Platzhalter, `test_an_entry_of_the_document_carries_every_field_of_the_row` um den Schluessel ergaenzt.
- **Committed in:** `c363a29`

**2. [Rule 2 - Missing Critical] Der Rueckwaertssprung des Zeitgebers**

- **Found during:** Task 2
- **Issue:** Die im Plan beschriebene Regel (`moment - fensterbeginn >= REFUSAL_WINDOW_SECONDS` schreibt, sonst zaehlt nur) haelt bei einem rueckwaerts gestellten Zeitgeber die Bremse fuer die volle Dauer des Sprungs geschlossen. Das Repo hat diese Klasse von Fehler in derselben Datei schon einmal gemessen (WR-02 des Phase-18-Reviews, `_EXPIRED_PREFIX` in `store.py`), also ist es hier kein hypothetischer Fall.
- **Fix:** Geschrieben wird, wenn die verstrichene Zeit **nicht** im halboffenen Intervall `[0, REFUSAL_WINDOW_SECONDS)` liegt. Ein aelterer Moment oeffnet damit ein neues Fenster.
- **Files modified:** `src/mcp_connector/audit/refusals.py`, `tests/unit/test_audit_refusals.py`
- **Verification:** `test_a_clock_that_stepped_back_opens_a_new_window_instead_of_closing_forever`
- **Committed in:** `7d35b7e`

**3. [Rule 3 - Blocking] Der Kontocheck-Beweis brauchte eine Testdatei ausserhalb der Plandateiliste**

- **Found during:** Task 1
- **Issue:** Das Akzeptanzkriterium verlangt einen Lauf des **Kontochecks**, nicht nur von `silent_users`. Der Kontocheck ist `record._drop_chains_without_an_account` und wird ausschliesslich in `tests/unit/test_audit_accounts.py` gefahren, das die ganze Maschinerie dafuer haelt (respx-Kontoliste, `arm_the_next_row`, der echte `@graceful`-Pfad). Die Dateiliste von Task 1 nannte nur `tests/unit/test_audit_store.py`. Den Check dort nachzubauen waere eine Kopie seiner zwei Zeilen gewesen, und eine Gegenprobe, die die Umsetzung nachbaut, beweist etwas ueber die Gegenprobe.
- **Fix:** Der Fall steht in `tests/unit/test_audit_accounts.py` und faehrt den echten Check; `tests/unit/test_audit_store.py` behaelt den engeren Fall ueber `silent_users`.
- **Files modified:** `tests/unit/test_audit_accounts.py`
- **Verification:** `test_the_refusal_chain_survives_an_account_check_that_never_heard_of_it`
- **Committed in:** `09c75e4` (RED), gruen mit `99c2fa6`

**4. [Rule 2 - Missing Critical] `known_reason` und `vulture_whitelist.py` ausserhalb der Dateiliste**

- **Found during:** Task 2
- **Issue:** Der Plan verlangt ausdruecklich, die Regel aus `record.py` herauszuziehen statt sie zu verdoppeln, nennt aber weder `record.py` noch `errors.py` in `files_modified`. Ebenso verlangt der Verifikationsteil einen Whitelist-Eintrag fuer ein Symbol ohne Aufrufer, ohne `vulture_whitelist.py` in der Liste zu fuehren.
- **Fix:** Beides umgesetzt wie verlangt; die drei Dateien stehen in der Dateiliste dieses SUMMARY.
- **Files modified:** `src/mcp_connector/errors.py`, `src/mcp_connector/audit/record.py`, `vulture_whitelist.py`
- **Verification:** `uv run vulture src scripts vulture_whitelist.py` ohne Befund, `tests/unit/test_errors_reason.py` gruen
- **Committed in:** `7d35b7e`

---

**Total deviations:** 4 auto-fixed (3 fehlende kritische Funktionalitaet, 1 blockierend)
**Impact on plan:** Kein Scope Creep. Deviation 1 loest das von Task 3 selbst formulierte Verhalten ein, Deviation 2 schliesst eine Fehlerklasse, die dieses Repo in derselben Datei schon einmal gemessen hat, Deviation 3 und 4 sind Dateien, die der Plantext verlangt und in seiner Dateiliste vergessen hat.

## An Plan 24-06 uebergeben (nicht verloren)

Die Optionsbeschreibung, die an der Konsole sagt, welche Kette `--user` liest, steht in
`src/mcp_connector/exapp/occ.py` als `OCC_AUDIT_READ_USER_DESCRIPTION` und nennt heute nur
`instance`. Der Plan (Task 3) regelt diesen Fall ausdruecklich: die Datei gehoert zu Plan
24-06, und der Eintrag gehoert ins SUMMARY, damit die Beschreibung nicht zwischen den Plaenen
verloren geht. **Konkret zu tun in 24-06:** `OCC_AUDIT_READ_USER_DESCRIPTION` um
`REFUSALS_KEYWORD` erweitern (der Import steht in `occ.py` schon bereit, `INSTANCE_KEYWORD`
kommt von dort). Bis dahin funktioniert das Wort, es steht nur in keinem `occ list`-Hilfetext.

## Issues Encountered

- Eine Erwartung des RED-Laufs war selbst falsch: der Fall des Rueckwaertssprungs erwartete
  `removed == 2` fuer die zweite Zeile. Richtig ist `1`, weil das erste Fenster nichts
  unterdrueckt hatte. Die Erwartung wurde korrigiert, die Zaehlregel nicht.
- Ein erster Kommentar in `store.py` erklaerte, warum kein `LIKE` benutzt wird, und nannte
  das Muster dabei woertlich. Damit fiel das Akzeptanzkriterium `grep -c "'u:%'" == 0` ueber
  einen Kommentar. Der Kommentar sagt die Sache jetzt in Worten.

## Verification

Alle Gates vor jedem Commit gruen:

- `uv run pytest -q` vollstaendig gruen (keine Fehler, nur die bekannten `s`-Ueberspruenge der Live-Suiten)
- `uv run ruff check .` / `uv run ruff format --check .` (265 Dateien)
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright`: 0 errors, 0 warnings
- `uv run vulture src scripts vulture_whitelist.py`: ohne Befund
- `uv run pytest tests/contract -q` gruen: `audit/` importiert weiterhin nichts aus `oauth/`
- `git diff 27ce1bb..HEAD | grep -ci "alter table"` ergibt 0
- `grep -c "'u:%'" src/mcp_connector/audit/store.py` ergibt 0
- `grep -c "from \.\.oauth\|from mcp_connector\.oauth\|import mcp_connector\.oauth" src/mcp_connector/audit/refusals.py` ergibt 0
- `grep -v '^\s*#' src/mcp_connector/audit/refusals.py | grep -c "azp"` ergibt 0
- `docs/privacy.md`: 0 Em-Dashes (U+2014), 0 En-Dashes (U+2013), `grep -c "entries"` von 10 auf 14 gestiegen

## Known Stubs

Keine. Jede in diesem Plan angelegte Funktion ist verdrahtet und von Tests gefahren.
`RefusalWriter` hat bewusst noch keinen Aufrufer in `src/` (das ist Plan 24-04) und traegt
dafuer einen begruendeten Whitelist-Eintrag, der sein eigenes Ende ankuendigt.

## Threat Flags

Keine. Dieser Plan legt keine neue Netzwerkoberflaeche, keinen neuen Auth-Pfad und keine
neue Schemaaenderung an einer Vertrauensgrenze an. Die einzige neue Schreibstelle ist die
gebremste, die der Plan selbst als Mitigation von T-24-02 fuehrt.

## Next Phase Readiness

Bereit fuer Plan 24-04. Dieser liefert:

- `CHAIN_EXCHANGE`, `KIND_REFUSAL` aus `audit/store.py`
- `RefusalWriter(store_provider=...)` mit `await writer.note_refusal(reason, moment=...)` aus `audit/refusals.py`
- `errors.known_reason` fuer jeden weiteren Schreiber einer `reason`-Spalte

Offen und ausdruecklich uebergeben: der Eintrag in `OCC_AUDIT_READ_USER_DESCRIPTION`
(Plan 24-06, siehe Abschnitt oben) und das Quelltext-Gate gegen einen Claim in der
Abweisungszeile (Plan 24-04, `tests/contract/test_no_claim_leak.py`).

## Self-Check: PASSED

Alle acht in diesem SUMMARY genannten Dateien liegen auf der Platte, alle sechs genannten
Commits stehen in `git log`. Die TDD-Tore sind vollstaendig: je Task ein `test(...)` vor dem
zugehoerigen `feat(...)`.

---
*Phase: 24-audit-anschluss-und-nachweis*
*Completed: 2026-09-24*

---
phase: 24-audit-anschluss-und-nachweis
plan: 01
subsystem: auth
tags: [audit, oauth, token-exchange, sqlite, hash-chain, rfc8693]

# Dependency graph
requires:
  - phase: 18-audit-log-kern
    provides: "die hash-verkettete Audit-Kette, CANONICAL_FIELDS, die Spalte actor (D-16) und die eine Saeuberungsregel audit/text.printable"
  - phase: 19-audit-werkzeuge
    provides: "occ mcp_connector:audit:read mit Textzeile und JSON-Dokument"
  - phase: 23-token-exchange-identitaet
    provides: "acting_party(claims), EXCHANGE_CLIENT_ID und die beiden Kontoquellen AppApiAccounts und BoundAccounts"
provides:
  - "OAuthIdentity.actor: die handelnde Partei einer fremden Realm als eigenes Feld der Identitaet"
  - "Caller.actor: das fuenfte Feld des Aufrufers, gefuellt aus der Identitaet, None ohne Delegation"
  - "audit.store.ACTOR_LIMIT und _clean_actor: der azp laeuft durch dieselbe Regel wie ein Clientname"
  - "entries.actor traegt bei call-Zeilen des Exchange-Pfads die handelnde Partei, bei switch und tombstone weiterhin unknown"
  - "occ mcp_connector:audit:read zeigt die handelnde Partei in Textzeile und JSON-Dokument"
affects: [24-02, 24-03, 24-04, audit-auswertung, token-exchange-doku]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Eine bestehende, hash-geschuetzte und bisher leere Spalte bekommt eine zweite Bedeutung, statt dass die kanonische Feldliste waechst"
    - "Fremder Text wird an jeder Schicht erneut gesaeubert und nie einer frueheren Saeuberung vertraut (R-18-06)"

key-files:
  created: []
  modified:
    - src/mcp_connector/oauth/verifier.py
    - src/mcp_connector/oauth/exchange_accounts.py
    - src/mcp_connector/oauth/exchange_appapi.py
    - src/mcp_connector/oauth/exchange_binding.py
    - src/mcp_connector/deps.py
    - src/mcp_connector/audit/record.py
    - src/mcp_connector/audit/store.py
    - src/mcp_connector/exapp/audit_read.py
    - docs/privacy.md

key-decisions:
  - "Die handelnde Partei bezieht die bestehende Spalte actor (D1 Option A der Recherche); CANONICAL_FIELDS bleibt bei siebzehn Feldern, damit keine bereits geschriebene Zeile beim naechsten verify als modified auffaellt"
  - "actor wird im Feld OAuthIdentity hinter client_name und vor credential eingefuegt, damit keine bestehende Konstruktion mit Positionsargumenten ihre Bedeutung wechselt"
  - "ACTOR_LIMIT = 64 wird in audit/store.py erneut benannt statt aus oauth/ importiert, weil audit/ nicht nach oauth/ importieren darf"
  - "Caller.actor bekommt den Vorgabewert None, damit die vier bestehenden Konstruktionsstellen unveraendert gueltig bleiben"
  - "Die leere Zeichenkette der Identitaet wird in resolve_caller zu None, weil niemand genannt und nichts gesetzt in einer Zeile dieselbe Tatsache sind"
  - "Die neue Spalte der Textausgabe steht direkt hinter client_name, damit die beiden Namen eines Aufrufs nebeneinander gelesen werden"
  - "Die Datenschutzseite bekommt keine Zahl fuer die Kappung, sondern den Verweis auf die Regel des Clientnamens, weil das Wahrheitsgate nur Zahlen aus Konstanten zulaesst"

patterns-established:
  - "Zweite Bedeutung einer Spalte: Schemakommentar und Docstring nennen beide Faelle ausdruecklich, sonst liest die naechste Person das Feld falsch"
  - "Regressionsgate gegen eine Schemaaenderung: ein Test haelt CANONICAL_FIELDS gegen das Literal, ein zweiter schreibt Zeilen und prueft sie ueber ein zweites Store-Objekt derselben Datei nach"

requirements-completed: [AUDIT-07]

# Metrics
duration: 42min
completed: 2026-09-23
---

# Phase 24 Plan 01: Die handelnde Partei als eigenes Feld Summary

**Der `azp` eines getauschten Tokens wandert von `client_name` in die bereits vorhandene, hash-geschuetzte Spalte `actor`, gesaeubert nach der einen Regel dieses Repos, ohne dass `CANONICAL_FIELDS` angefasst wird.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-09-23T00:00:00Z (Worktree-Start)
- **Completed:** 2026-09-23
- **Tasks:** 3
- **Files modified:** 15 (9 Quell- und Dokudateien, 6 Testdateien)

## Accomplishments

- Ein Werkzeugaufruf ueber den Token-Exchange-Pfad traegt die handelnde Partei jetzt in `entries.actor` und nicht mehr in `entries.client_name`; `client_name` bleibt auf diesem Weg leer, weil dort kein Client registriert ist.
- Der Wertweg ist vollstaendig verdrahtet: `OAuthIdentity.actor` -> `Caller.actor` -> `Entry.actor` -> Zeile -> beide Ausgabeformen von `occ mcp_connector:audit:read`.
- Der `azp` laeuft an zwei Schichten durch `audit/text.printable` statt durch den engeren Filter von `acting_party`: einmal in `audit/record.py` auf dem Weg in die Zeile, einmal in `audit/store.py` beim Schreiben. Ein Zeilenumbruch und ein Right-to-Left-Override sind in beiden Ausgabeformen nachweislich weg.
- `CANONICAL_FIELDS` ist unveraendert. Zwei Tests halten das fest: einer gegen das Literal der siebzehn Felder, einer schreibt Zeilen, oeffnet die Datei ueber ein zweites Store-Objekt und laesst `verify_chains` ohne Befund laufen.
- Kein Docstring und keine Seite beschreibt mehr den alten Weg ueber `client_name`.

## Task Commits

1. **Task 1: Die handelnde Partei von der Identitaet bis in die Zeile** (TDD)
   - `e5a654e` (test) - die fehlschlagenden Zusicherungen ueber `actor` in Identitaet, `Caller`, Zeile und Saeuberung
   - `7df590a` (feat) - `OAuthIdentity.actor`, `Caller.actor`, `ACTOR_LIMIT`, `_clean_actor`, `_clamped_actor`, beide Kontoquellen
2. **Task 2: Die handelnde Partei in der Ausgabe von audit:read** (TDD)
   - `6f0cfcc` (test) - Spaltenzahl, Spaltenposition, Platzhalter, Override, `switch`-Zeile
   - `90b3c67` (feat) - `_cleaned(entry.actor, ACTOR_LIMIT)` in `_line`, `actor` in `_document`
3. **Task 3: Die Docstrings und die Datenschutzseite auf den neuen Stand ziehen**
   - `a919646` (docs) - `EXCHANGE_CLIENT_ID`, `acting_party`, der Protokoll-Docstring und `docs/privacy.md`

## Files Created/Modified

- `src/mcp_connector/oauth/verifier.py` - `OAuthIdentity` bekommt `actor: str = ""` hinter `client_name`; der Docstring grenzt die beiden Namen gegeneinander ab. Der `__repr__` nimmt `actor` bewusst nicht auf (T-24-12).
- `src/mcp_connector/oauth/exchange_appapi.py` - `actor=acting_party(claims)` statt `client_name=...`, mit dem Grund als Kommentar daneben.
- `src/mcp_connector/oauth/exchange_binding.py` - dasselbe fuer die gebundene Kontoquelle des Standalone-Betriebs.
- `src/mcp_connector/oauth/exchange_accounts.py` - drei Docstrings auf den neuen Stand: `EXCHANGE_CLIENT_ID` behauptet nicht mehr, die Kette habe kein Feld bekommen; `acting_party` nennt `actor` und die zweite Saeuberung; der Protokoll-Docstring nennt das Feld beim Namen.
- `src/mcp_connector/deps.py` - `Caller` bekommt `actor: str | None = None`; "Four fields and no fifth" ist jetzt "Five fields and no sixth" mit dem Grund daneben. Der OAuth-Zweig setzt `identity.actor or None`, der AppAPI-Zweig setzt `None`.
- `src/mcp_connector/audit/record.py` - `_clamped_actor` neben `_clamped_client_name`; `note` schreibt `actor=_clamped_actor(caller.actor)` statt `actor=None`.
- `src/mcp_connector/audit/store.py` - `ACTOR_LIMIT = 64` samt Begruendung, `_clean_actor`, `entry.actor` laeuft in `_row_values` durch die Regel, der Schemakommentar der Spalte nennt beide Bedeutungen. `CANONICAL_FIELDS` unangetastet.
- `src/mcp_connector/exapp/audit_read.py` - `_line` bekommt eine Spalte hinter `client_name`, durch `_cleaned`; `_document` bekommt den Schluessel `actor`; beide Docstrings auf die neue Zahl gezogen.
- `docs/privacy.md` - eine Zeile fuer `entries.actor` in der Tabelle der gespeicherten Daten, mit beiden Bedeutungen der Spalte.
- `tests/unit/test_audit_caller.py`, `tests/unit/test_audit_record.py`, `tests/unit/test_audit_store.py`, `tests/unit/test_exapp_audit_read.py`, `tests/unit/test_oauth_exchange_appapi.py`, `tests/unit/test_oauth_exchange_binding.py` - 13 neue oder umgeschriebene Faelle.

## Decisions Made

- **Spalte statt Schema (D1 Option A).** Eine achtzehnte gehashte Spalte haette jede bereits geschriebene Zeile jeder bestehenden Installation beim naechsten `occ mcp_connector:audit:verify` als `modified` gemeldet, weil `_first_finding` ueber `row[: len(CANONICAL_FIELDS)]` nachrechnet und eine per `ALTER TABLE` ergaenzte Spalte bei jeder Altzeile ein zusaetzliches `null` in die JSON-Liste gelegt haette. Die Spalte `actor` bedeutet seit D-16 bereits "wer hat gehandelt", steht an Position 5 und war bei jeder `call`-Zeile leer.
- **Zweimal saeubern statt einmal vertrauen.** `acting_party` filtert mit `character.isprintable()` und wirft weg, `audit/text.printable` ersetzt durch ein Leerzeichen und zieht Whitespace-Laeufe zusammen. Das sind nicht dieselben Regeln. Der Wert wird deshalb in `audit/record.py` und in `audit/store.py` erneut durch die eine Regel dieses Repos geschickt, statt der frueheren Saeuberung zu vertrauen; drei Fassungen einer Regel waren R-18-06.
- **`ACTOR_LIMIT` erneut benannt, nicht importiert.** `audit/` darf nicht aus `oauth/` importieren (Schichtregel, gehalten von `tests/contract/test_module_boundaries.py`). Die Konstante traegt den Grund im Kommentar, damit die Dopplung nicht beim naechsten Aufraeumen als Versehen gelesen wird.
- **Vorgabewerte statt Pflichtfelder.** `OAuthIdentity.actor` und `Caller.actor` haben beide einen Vorgabewert, damit keine bestehende Konstruktion ihre Bedeutung wechselt. Bei `OAuthIdentity` ist die Position zusaetzlich wichtig: `actor` steht vor `credential`, nicht dahinter.
- **Die Datenschutzseite ohne neue Zahl.** `tests/unit/test_docs_audit_truth.py` haelt Zahlen der Seite gegen Konstanten des Codes. Die neue Zeile sagt "cleaned and cut the same way a registered client name is" statt "cut to 64 characters", damit keine ungegatete Zahl entsteht.

## Deviations from Plan

Keine. Der Plan wurde genau so ausgefuehrt, wie er geschrieben war.

Zwei Praezisierungen ohne Abweichung vom Auftrag:

1. **Zwei Tests des RED-Laufs waren von Anfang an gruen, und das ist beabsichtigt.** `test_the_canonical_field_list_is_the_seventeen_of_phase_eighteen` und `test_rows_written_through_one_store_verify_through_a_second_one` sind Regressionsgates gegen eine Aenderung, die dieser Plan ausdruecklich nicht machen darf (Pitfall 1). Ein solcher Test muss vor und nach der Aenderung gruen sein; waere er im RED-Lauf rot gewesen, haette er etwas anderes gemessen als das, wofuer er geschrieben wurde. Die verhaltensaendernden Faelle beider TDD-Tasks waren rot und sind belegt rot gewesen (elf Fehlschlaege im RED-Lauf von Task 1, sechs im RED-Lauf von Task 2).
2. **Der Aufruf von Task 2, unter `docs/` und in `README.md` nach einem mitzuziehenden Beispiel einer Ausgabezeile zu suchen, ergab keinen Fund.** Gesucht wurde nach `mcp_connector:audit:read` und nach dem Trennzeichen `" - "` in `docs/privacy.md`, `docs/faq.md`, `docs/uninstall.md` und `README.md`. `README.md:158` nennt das Kommando in Prosa, ohne eine Beispielzeile. Es gibt also kein Ausgabebeispiel unter `docs/` oder im `README.md`, das durch die neue Spalte falsch geworden waere.

**Total deviations:** 0
**Impact on plan:** keiner.

## TDD Gate Compliance

Beide TDD-Tasks tragen die vollstaendige Gatefolge in dieser Reihenfolge:

| Task | RED | GREEN | REFACTOR |
|------|-----|-------|----------|
| Task 1 | `e5a654e` (`test(24-01)`) | `7df590a` (`feat(24-01)`) | nicht noetig, keine Aufraeumarbeit offen |
| Task 2 | `6f0cfcc` (`test(24-01)`) | `90b3c67` (`feat(24-01)`) | nicht noetig |

## Issues Encountered

Keine. Alle Qualitaetsgates liefen vor jedem Commit lokal gruen.

## Verification

| Pruefung | Ergebnis |
|----------|----------|
| `uv run pytest -q` | 4175 passed, 33 skipped, 168 deselected (Stand vor der Phase: 4162; 13 Faelle dazugekommen) |
| `uv run pytest tests/contract -q` | gruen, die Schichtregel haelt: `audit/` importiert nichts aus `oauth/` |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 263 files already formatted |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings, 0 informations |
| `uv run vulture src scripts vulture_whitelist.py` | kein Befund, `vulture_whitelist.py` blieb unveraendert |
| `git diff 50723cd HEAD \| grep -ci "alter table"` | 0 |
| `CANONICAL_FIELDS`-Tupel im Diff | unveraendert; `"actor"` steht weiterhin genau einmal in der Liste |
| `grep -c 'actor=acting_party'` in beiden Kontoquellen | je 1, und `client_name=acting_party` je 0 |
| `grep -c 'entry.actor'` in `exapp/audit_read.py` | 2 (Textzeile und JSON-Dokument) |
| `grep -c "without the audit chain growing a new field"` | 0 |
| `grep -c "becomes \`\`client_name\`\`"` | 0 |
| `grep -c "entries.actor" docs/privacy.md` | 1 |
| Em-Dashes in `docs/privacy.md` | 0 |

## Threat Model Coverage

| Threat ID | Disposition | Wie erfuellt |
|-----------|-------------|--------------|
| T-24-01 (Log Injection) | mitigate | `actor` laeuft durch `audit/text.printable` in `store._row_values`, in `record._clamped_actor` und in `audit_read._line`/`_document`. Drei Tests mit `\n` und U+202E: in der Zeile, in der Textausgabe und im JSON-Dokument. |
| T-24-05 (Repudiation) | mitigate | `CANONICAL_FIELDS` unangetastet; `test_the_canonical_field_list_is_the_seventeen_of_phase_eighteen` haelt das Literal, `test_rows_written_through_one_store_verify_through_a_second_one` schreibt Zeilen, oeffnet die Datei neu und laesst `verify_chains` ohne Befund laufen. |
| T-24-12 (Information Disclosure) | mitigate | `actor` steht nicht im `__repr__` von `OAuthIdentity`; der `__repr__` blieb wortgleich bei `nc_user`, `principal` und den maskierten Werten. |
| T-24-13 (Spoofing, AppAPI-Zweig) | accept | Der AppAPI-Zweig von `resolve_caller` setzt `actor=None` ausdruecklich, und ein Test haelt das fest. Es gibt dort keine handelnde Partei, und ein Wert waere erfunden. |
| T-24-SC (Supply Chain) | accept | Diese Phase installiert kein Paket; `pyproject.toml` und `uv.lock` sind im Diff nicht enthalten. |

## Known Stubs

Keine. Jede in diesem Plan angefasste Stelle traegt einen echten Wert; es gibt keinen Platzhalter, keinen leeren Rueckgabewert und keinen nicht verdrahteten Pfad.

## Next Phase Readiness

Bereit fuer die uebrigen Plaene der Phase 24:

- **24-02 (Sichtbarkeit einer Abweisung, D2)** kann auf die Spalte `actor` aufsetzen. Wichtig fuer den Planer dieses Plans: eine Abweisungszeile darf den `azp` eines **ungeprueften** Claim-Satzes nicht tragen (Pitfall 4 der Recherche); dieser Plan hat die Spalte nur fuer den geprueften Fall belegt, und der Kommentar des Schemas sagt das auch so.
- **24-03 (Trockenlauf, EXCH-06)** ist von diesem Plan unberuehrt.
- **24-04 (Doku, EXCH-07 und EXCH-08)** kann `docs/privacy.md` als Muster fuer die Beschreibung der Spalte verwenden und findet dort jetzt die Wahrheit statt des Standes vor der Phase.

Keine Blocker. `.planning/STATE.md` und `.planning/ROADMAP.md` wurden von diesem Agenten bewusst nicht angefasst; sie gehoeren dem Orchestrator.

## Self-Check: PASSED

Alle in diesem Dokument genannten Dateien existieren, und alle fuenf genannten Commits stehen
in der Historie des Worktrees (`e5a654e`, `7df590a`, `6f0cfcc`, `90b3c67`, `a919646`, auf
`50723cd` aufgesetzt). Nichts fehlt.

---
*Phase: 24-audit-anschluss-und-nachweis*
*Plan: 01*
*Completed: 2026-09-23*

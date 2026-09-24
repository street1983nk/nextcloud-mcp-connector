---
phase: 24-audit-anschluss-und-nachweis
reviewed: 2026-09-24T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - src/mcp_connector/audit/refusals.py
  - src/mcp_connector/audit/store.py
  - src/mcp_connector/audit/record.py
  - src/mcp_connector/deps.py
  - src/mcp_connector/errors.py
  - src/mcp_connector/oauth/exchange_dryrun.py
  - src/mcp_connector/oauth/exchange.py
  - src/mcp_connector/oauth/chain.py
  - src/mcp_connector/oauth/jwks.py
  - src/mcp_connector/oauth/verifier.py
  - src/mcp_connector/oauth/exchange_accounts.py
  - src/mcp_connector/oauth/exchange_appapi.py
  - src/mcp_connector/oauth/exchange_binding.py
  - src/mcp_connector/exapp/exchange_check.py
  - src/mcp_connector/exapp/audit_read.py
  - src/mcp_connector/exapp/occ.py
  - src/mcp_connector/entry_exapp.py
  - src/mcp_connector/entry_oauth.py
  - scripts/exchange_evidence.py
  - docs/token-exchange.md
  - docs/exchange-evidence.md
  - docs/privacy.md
findings:
  critical: 1
  warning: 6
  info: 7
  total: 14
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-09-24
**Depth:** standard (Datei fuer Datei, sprachspezifische Pruefungen, Quervergleich Code gegen Doku)
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Die Sicherheitsschwerpunkte der Phase halten weitgehend. Ich habe die vier gefaehrlichen
Wege einzeln nachgezogen und keinen Claim-Leak gefunden:

- Das Abweisungs-Schreibwerk (`audit/refusals.py`) baut die Zeile aus sechs Konstanten, nimmt
  ausser dem Bezeichner nichts entgegen, und das AST-Gate in `tests/contract/test_no_claim_leak.py`
  prueft Feldnamen, positionelle Argumente und `**`-Spreizung gegen echte Gegenproben.
- Der Trockenlauf (`oauth/exchange_dryrun.py`) fuehrt keinen Tokenwert in eine Antwort, haelt
  die Schrittreihenfolge des laufenden Pruefers ein, benutzt `secrets.compare_digest` ohne
  fruehen Abbruch und baut seinen eigenen `KeySet`, so wie es die Recherche verlangt.
- Die occ-Route (`exapp/exchange_check.py`) ist im Manifest nicht deklariert, traegt die
  doppelte Pruefung der sechs Geschwister, begrenzt den Body und antwortet immer 200.
- Fehlermeldungen folgen ueberall dem `type(exc).__name__`-Muster; keine Fremdmeldung wird
  durchgereicht. `ruff check` und `ruff format --check` sind gruen, die Tests der Phase laufen.

Der ernste Befund liegt woanders und genau an der Stelle, die die Recherche als die
gefaehrlichste der Phase benannt hat: die Flutungsfestigkeit. Die Abweisungszeilen wurden
korrekt in eine **fegbare** Kette gelegt, aber der Schreibweg dieser Zeilen **loest den Sweep
nie aus** und verbraucht dabei Sequenznummern, auf denen der ganze Zeitplan des Sweeps haengt.
Damit ist die Zusage aus `docs/privacy.md` ("refused attempts expire after the same window and
give way to the same upper bound") betrieblich nicht gedeckt, und sie betrifft nicht nur die
Abweisungskette, sondern die Verfallsfrist des gesamten Protokolls.

Zweitschwerster Befund: die Messdatei `docs/exchange-evidence.md`, also der Nachweis, mit dem
EXCH-07 und AUDIT-07 belegt werden sollen, zitiert Rohausgaben, die der Code so nicht erzeugen
kann. Das habe ich gegen die echte Funktion nachgerechnet, nicht vermutet.

## Critical Issues

### CR-01: Abweisungszeilen loesen den Sweep nie aus und koennen ihn fuer das ganze Protokoll ueberspringen

**File:** `src/mcp_connector/audit/refusals.py:122-139`, `src/mcp_connector/audit/record.py:263`, `src/mcp_connector/audit/store.py:561-569`, `docs/privacy.md:257-262`

**Issue:**
`RefusalWriter.note_refusal` ruft `audit_store.append(Entry(...))` auf und verwirft die
zurueckgegebene Sequenznummer. Der einzige Ort im ganzen Baum, der `store.should_sweep(seq)`
fragt, ist `audit/record.py:263` auf dem Aufrufpfad; der zweite Sweep steht in
`entry_exapp._audit_startup` und laeuft nur beim Start. Daraus folgen zwei getrennte Fehler:

1. **Die Abweisungszeilen verfallen nicht, solange nichts anderes schreibt.** Auf einer
   Instanz mit eingeschaltetem Protokoll und bewaffnetem Exchange-Pfad, deren Verkehr aus den
   Versuchen eines Fremden besteht und nicht aus Werkzeugaufrufen, wird nie gefegt. Die Bremse
   deckelt das auf hoechstens sechs Zeilen je 300 Sekunden und Arbeiter, also rund 1728 Zeilen
   je Tag und Arbeiter, die bis zum naechsten Containerstart liegen bleiben. Das ist kein
   schneller Ausfall, aber es ist genau die Zusage, die `docs/privacy.md:257-262` gibt:
   "The first two of these three take the rows of the `x:exchange` chain exactly as they take
   the rows of an account." SQL-seitig stimmt das (`chain <> CHAIN_INSTANCE`), betrieblich
   nicht, weil die Anweisung nie ausgefuehrt wird.

2. **Der Zeitplan des Sweeps kann fuer das ganze Protokoll uebersprungen werden.**
   `should_sweep(seq)` ist `seq % SWEEP_EVERY == 0` mit `SWEEP_EVERY = 500`, und `seq` kommt
   aus einem gemeinsamen `AUTOINCREMENT`. Jede Abweisungszeile verbraucht eine Nummer. Faellt
   ein Vielfaches von 500 auf eine Abweisungszeile, findet dieser Sweep gar nicht statt, denn
   nur der Aufrufpfad fragt nach. Der naechste kommt 500 Zeilen spaeter. Betroffen sind damit
   auch die Nutzerketten, also personenbezogene Zeilen, deren 180-Tage-Fenster
   `docs/privacy.md` zusichert. Der Anteil uebersprungener Sweeps waechst mit dem Anteil der
   Abweisungszeilen, und diesen Anteil bestellt ein Fremder.

Die Recherche hat die Instanz-Kette als Falle erkannt und richtig vermieden. Die zweite
Haelfte der Falle, "fegbar heisst nicht gefegt", ist offen geblieben.

**Fix:**
Den Sweep an denselben Schreibweg haengen, mit derselben Fail-open-Klammer. Die Bremse
begrenzt das bereits auf hoechstens sechs Ausloeser je Fenster, ein zusaetzlicher Hebel fuer
einen Fremden entsteht also nicht.

```python
# audit/refusals.py, in note_refusal, statt des verworfenen Rueckgabewerts
try:
    audit_store = await self.store_provider()
    seq = await audit_store.append(Entry(...))
    # Der Zeitplan von D-11 haengt an der Nummer, die der Store zurueckgibt. Ein Schreiber,
    # der sie verwirft, nimmt genau die Zeilen aus dem Verfallsfenster, die von aussen
    # bestellt werden.
    if store.should_sweep(seq):
        await audit_store.sweep(
            moment=at,
            retention_days=self._retention_days,
            size_limit=self._size_limit,
        )
except Exception as exc:
    logger.error("a refused exchange attempt was not recorded: %s", type(exc).__name__)
```

Die beiden Grenzwerte muessen dafuer wie beim Recorder hereingereicht werden
(`config.audit_retention_days` / `config.audit_size_limit` in `entry_exapp.build_exapp_app`).
Variante ohne Sweep auf dem Vor-Authentisierungs-Pfad, falls die Last dort unerwuenscht ist:
`should_sweep` im Recorder nicht gegen die gerade geschriebene Nummer, sondern gegen
`MAX(seq)` der Tabelle pruefen und zusaetzlich den Satz in `docs/privacy.md` auf das
abschwaechen, was wirklich gilt. Der Satz darf nicht stehen bleiben, wie er ist.

## Warnings

### WR-01: Die Rohausgabe in der Messdatei kann so nicht aus dem Code stammen

**File:** `docs/exchange-evidence.md:254-256`, `docs/exchange-evidence.md:287-293`

**Issue:**
`docs/exchange-evidence.md:21` sagt woertlich "Everything below is the raw output of
`scripts/exchange_evidence.py`". Die zitierten Zeilen sind es nicht. Gegengerechnet mit der
echten Funktion `exapp/audit_read._line` und `FIELD_SEPARATOR = " - "`:

```
Dokument: 493 - 2026-09-24T06:14:17Z - x:exchange - - - - - rejected - exchange_issuer - - - - 1
Code:     493 - 2026-09-24T06:14:17Z - x:exchange - - - - - - - rejected - exchange_issuer - - - - - 1

Dokument: 495 - ... - u:alice - files_read - - mcp-evidence-orchestrator - ok - - 78 - path - -
Code:     495 - ... - u:alice - files_read - - - mcp-evidence-orchestrator - ok - - - 78 - path - -
```

Jeder Lauf leerer Spalten hat im Dokument mindestens einen Strich zu wenig. Das ist genau das
Artefakt, mit dem EXCH-07 und Erfolgskriterium 1 belegt werden sollen, und die Doku-Gates in
`tests/unit/test_docs_exchange_truth.py` pruefen ausschliesslich `docs/token-exchange.md`.
Fuer `docs/exchange-evidence.md` existiert kein Gate, das den Unterschied gefunden haette.
Ein Nachweis, der nachbearbeitet wurde, ist kein gemessener Nachweis mehr, und die Phase lebt
von "gemessen statt behauptet".

**Fix:**
Die Bloecke aus einem echten Lauf erneut einsetzen, unveraendert, und ein Gate ergaenzen, das
mindestens eine zitierte Zeile gegen `audit_read._line` nachrechnet:

```python
def test_the_quoted_audit_lines_are_the_lines_this_code_prints() -> None:
    row = (493, store.CHAIN_EXCHANGE, store.KIND_REFUSAL, 1790230457, None, None, None,
           None, None, None, store.OUTCOME_REJECTED, REASON_EXCHANGE_ISSUER, None, "[]", 1,
           None, None, b"\x00" * 32, b"\x11" * 32)
    assert audit_read._line(row) in EVIDENCE.read_text(encoding="utf-8")
```

### WR-02: Ein Ausfall der Kontoquelle wird als Kontoabweisung protokolliert

**File:** `src/mcp_connector/oauth/chain.py:606-609`, `src/mcp_connector/oauth/chain.py:641-650`, `src/mcp_connector/errors.py:50-53`

**Issue:**
`resolve_identity` schreibt fuer **jede** Form von "nein" aus `_exchange_identity` den
Bezeichner `REASON_EXCHANGE_ACCOUNT`. Zu diesen Formen gehoert der `except Exception`-Zweig,
also eine Nextcloud- oder AppAPI-Stoerung. `errors.py:50-51` definiert
`REASON_EXCHANGE_ACCOUNT` aber als "the mapping yields no principal, there is no account
source, or the source says no"; fuer den unerwarteten Fehler existiert eigens
`REASON_EXCHANGE_FAILED` ("an unexpected exception in the checking branch"), und
`verify_token` benutzt ihn auch korrekt.

Fuer die HTTP-Antwort ist die Gleichmacherei richtig und beabsichtigt. Fuer die Audit-Zeile
ist sie ein Diagnosefehler: Der Betreiber, fuer den AUDIT-07 gebaut wurde, sieht bei einem
Nextcloud-Ausfall "das Konto hat nein gesagt" und sucht an der falschen Stelle. Verschaerfend
wirkt die Bremse: waehrend der Stoerung ist das Fenster von `exchange_account` dauerhaft
gespannt, echte Kontoabweisungen derselben Zeit werden nur noch in `removed` gezaehlt.

**Fix:**
Den Ausnahmezweig eigenstaendig melden, so wie `verify_token` es tut.

```python
# oauth/chain.py
async def _exchange_identity(self, claims) -> tuple[OAuthIdentity | None, str | None]:
    ...
    except Exception as exc:
        logger.error("an exchanged identity could not be resolved: %s", type(exc).__name__)
        return None, REASON_EXCHANGE_FAILED
    ...
# und im Aufrufer
identity, reason = await self._exchange_identity(claims[EXCHANGE_CLAIM])
if identity is None:
    await self._note(reason or REASON_EXCHANGE_ACCOUNT)
```

### WR-03: Drei Konstanten behaupten ein Gate, das es nicht gibt

**File:** `src/mcp_connector/exapp/exchange_check.py:113-118`, `src/mcp_connector/exapp/exchange_check.py:150-155`, `src/mcp_connector/audit/store.py:161-167`

**Issue:**
`exchange_check.py:117` sagt zu `HEADER_ORIGIN_IP`: "A test holds the spellings equal."
`exchange_check.py:154` sagt zu `TRUE_WORDS`: "A test holds the lists equal." Beides ist
falsch. Die vorhandenen Gleichheitspruefungen decken nur die aelteren Geschwister ab:

```
tests/unit/test_exapp_audit_read.py:382  audit_read.HEADER_ORIGIN_IP == audit_verify.HEADER_ORIGIN_IP
tests/unit/test_exapp_audit_read.py:385  audit_read.TRUE_WORDS       == audit_verify.TRUE_WORDS
tests/unit/test_exapp_purge.py:333-334   purge.HEADER_ORIGIN_IP      == lifecycle/audit_verify
tests/unit/test_exapp_audit_verify.py:252 audit_verify.TRUE_WORDS    == purge.TRUE_WORDS
```

`exchange_check` kommt in keiner dieser Zeilen vor. Die fuenfte Abschrift des Headernamens und
die vierte der Wortliste sind ungesichert, und der Kommentar sagt das Gegenteil, was die
naechste Person davon abhaelt, das Gate nachzuruesten.

Derselbe Fall eine Ebene tiefer: `audit/store.py:161-167` begruendet `ACTOR_LIMIT = 64` mit
"The same number as ``oauth.exchange_accounts.MAX_ACTING_PARTY_LENGTH``". Beide stehen auf 64,
kein Test haelt sie gegeneinander. `tests/unit/test_oauth_exchange_identity.py:105` nagelt nur
die eine Seite auf die Zahl fest.

**Fix:**

```python
# tests/unit/test_exapp_exchange_check.py
def test_the_spellings_this_module_copies_stay_equal() -> None:
    assert exchange_check.HEADER_ORIGIN_IP == audit_verify.HEADER_ORIGIN_IP
    assert exchange_check.TRUE_WORDS == audit_verify.TRUE_WORDS

# tests/unit/test_audit_store.py
def test_the_actor_bound_is_the_bound_of_the_acting_party() -> None:
    assert store.ACTOR_LIMIT == exchange_accounts.MAX_ACTING_PARTY_LENGTH
```

### WR-04: Ein zu grosser Body meldet "kein Token vorgelegt"

**File:** `src/mcp_connector/exapp/exchange_check.py:445-483`, `src/mcp_connector/exapp/exchange_check.py:252-256`

**Issue:**
`_payload` antwortet bei angekuendigter Ueberlaenge, bei `BodyTooLarge`, bei `BodyUnreadable`
und bei ungueltigem JSON jeweils mit `None`. Der Aufrufer macht daraus
`_value(None, TOKEN_OPTION) or ""` und laesst den Trockenlauf mit dem leeren String laufen.
Die Antwort lautet dann `failed  a token was presented`, also "es wurde kein Token vorgelegt",
obwohl eines vorgelegt wurde und nur der Rahmen zu gross war.

Das trifft genau den Fall, gegen den `MAX_BODY_BYTES` laut eigenem Docstring gewaehlt wurde:
"a body bound below it would answer a token that is merely large with a form error instead of
with the rule that refused it, which is the one answer a dry run exists to avoid". Bei einem
Token zwischen etwa 16 KiB und der HaRP-Grenze von rund 15 KiB Kopf beziehungsweise bei einem
Aufruf mit zusaetzlichen Optionen ist die Antwort schlechter als ein Formfehler: sie ist
sachlich falsch. Es gibt zwar eine WARNING-Zeile im Containerlog, aber die Konsole des
Administrators sagt etwas anderes als das Log.

**Fix:**
`_payload` das "warum nicht" mitgeben und den Unterschied benennen, statt ihn in `None`
zusammenfallen zu lassen.

```python
payload, refused = await _payload(request)
if refused is not None:
    return _text(f"{refused}\n") if not as_json else json_response(
        {"checked": False, "passed": False, "outcome": refused}
    )
```
mit einem eigenen benannten Ergebnis (etwa `OUTCOME_BODY_NOT_READ`), nach dem Muster von
`OUTCOME_NOT_CONFIGURED`, das genau dieses Problem fuer den anderen Fall bereits loest.

### WR-05: Die Antwortbildung liegt ausserhalb der Fehlerklammer und kann die 200-Zusage brechen

**File:** `src/mcp_connector/exapp/exchange_check.py:252-276`, `src/mcp_connector/exapp/exchange_check.py:310`, `src/mcp_connector/exapp/exchange_check.py:331-346`

**Issue:**
`try/except Exception` umschliesst nur `await dry_run(...)`. `_report(result)` und
`_machine_readable(result)` laufen danach ungeschuetzt und greifen beide mit
`STEP_NAMES[step.step]` unmittelbar in das Woerterbuch. Erhaelt `oauth/exchange_dryrun.STEPS`
einen Schritt, der in `STEP_NAMES` fehlt, ist das ein `KeyError` im Handler, also ein 500, und
AppAPI verwirft bei jedem Status ausser 200 den Body ungelesen (die Messung steht im
Moduldocstring). Der Administrator sieht dann `command executeHandler failed` und nichts
sonst, ausgerechnet in dem Driftfall, fuer den das Gate
`tests/unit/test_exapp_exchange_check.py:229` gebaut wurde. Ein Gate im Testlauf ersetzt keine
Fail-open-Klammer zur Laufzeit; das ganze Modul argumentiert sonst genau andersherum.

**Fix:**
Die Klammer bis zur fertigen Antwort ziehen und den Namen total machen.

```python
def _name(step: str) -> str:
    # Ein Schritt ohne Namen ist ein Fehler dieses Moduls und nicht der Verlust der Antwort.
    return STEP_NAMES.get(step, step)
```
und zusaetzlich `result = await dry_run(...)`, `_report`/`_machine_readable` in denselben
`try`-Block legen.

### WR-06: Das Messskript bewaffnet den Exchange-Pfad ausserhalb seiner try/finally-Klammer

**File:** `scripts/exchange_evidence.py:712-765`

**Issue:**
`register(armed)` steht in Zeile 728, also **vor** dem `try` in Zeile 749. Zwischen beiden
liegen `probe_the_issuer()`, `trust_the_issuer()` und zwei `mint(...)`-Aufrufe, die alle
scheitern koennen (fehlender Container, `RunFailed`, `KeyError` auf `NC_MCP_TEST_USER2`).
Faellt einer davon aus, laeuft das `finally` nie, und die Entwicklungsinstanz bleibt mit
`NC_MCP_EXCHANGE_ENABLED=yes` gegen einen Testaussteller registriert, dessen privater
Schluessel im abgebrochenen Prozess lag. Das ist derselbe Endzustand, den `--keep-armed`
ausdruecklich als Ausnahme kennzeichnet, nur unbeabsichtigt.

**Fix:**

```python
register(armed)
try:
    section("assumption A6: ...")
    probe_the_issuer()
    trust_the_issuer()
    ...
    asyncio.run(measure(...))
    ...
finally:
    if not options.keep_armed:
        ...
```

## Info

### IN-01: Frozen dataclass mit veraenderlichem Zustand erzeugt ein unbrauchbares `__hash__`

**File:** `src/mcp_connector/audit/refusals.py:70-90`

**Issue:** `@dataclass(frozen=True, slots=True)` erzeugt `__eq__` und `__hash__` aus allen
Feldern mit `compare=True`, also auch aus `_windows`. `hash(writer)` wirft damit `TypeError`,
und `writer_a == writer_b` vergleicht Bremszustaende. Heute ruft das niemand auf; es ist eine
Falle fuer den naechsten, der den Schreiber in ein Set oder in einen Cache-Schluessel legt.

**Fix:** `_windows: dict[...] = field(default_factory=dict, init=False, repr=False, compare=False)`.

### IN-02: Der Kommentar zur Ausgabezeile widerspricht der Aenderung, die er beschreibt

**File:** `src/mcp_connector/exapp/audit_read.py:306-312`

**Issue:** Der Docstring sagt "The count stands last, and it is last so the ten columns that
were there before it kept their places." Zwei Aussagen stimmen nicht. Erstens waren es neun
Spalten und nicht zehn (`git show 50723cd:.../audit_read.py`). Zweitens wurde `actor` in
derselben Aenderung an Position 6 eingefuegt, wodurch `outcome`, `reason`, `duration_ms` und
`params` um eine Stelle nach hinten rutschen. Ein Skript, das die Textausgabe nach Position
liest, bricht, und der Kommentar sagt ihm das Gegenteil.

**Fix:** Satz korrigieren auf "zehn Spalten wurden zu elf, `actor` steht an sechster Stelle und
verschiebt vier Spalten dahinter; wer die Textform nach Position liest, liest ab hier
verschoben. Die Dokumentform von `_document` bleibt schluesselstabil."

### IN-03: `actor` fehlt im handgeschriebenen `__repr__` von `OAuthIdentity`

**File:** `src/mcp_connector/oauth/verifier.py:169-179`

**Issue:** Das neue Feld ist im `__repr__` nicht aufgefuehrt, `client_name` dagegen schon,
obwohl der Docstring in Zeile 145-151 beide ausdruecklich unter dieselbe Regel stellt
("Both are foreign text and both are carried unquoted, under the same rule and for the same
reason"). Weglassen ist hier die sichere Richtung, aber sie ist weder begruendet noch
getestet, und der Docstring behauptet Gleichbehandlung.

**Fix:** Entweder `actor={self.actor!r}` aufnehmen oder einen Satz ergaenzen, warum die
handelnde Partei bewusst nicht in einer Fehlersuchausgabe steht.

### IN-04: Die Exchange-Konfiguration wird fuer eine Anwendung zweimal geladen

**File:** `src/mcp_connector/exapp/exchange_check.py:229`, `src/mcp_connector/entry_exapp.py:135`

**Issue:** `build_exapp_app` liest `load_exchange_config(env)` einmal und reicht das Ergebnis
an `build_chain`; `exchange_check_routes(env)` liest es ein zweites Mal und leitet daraus
eigenstaendig ab, ob die Instanz bewaffnet ist. Zwei Leser derselben Frage in einer Anwendung,
wo einer genuegt hat, und der Docstring begruendet nur, warum der zweite Aufruf nicht werfen
kann, nicht warum es ihn gibt.

**Fix:** `exchange_check_routes(env, config=exchange_config)` mit `env` nur als Rueckfall, nach
dem Muster von `build_chain(..., config=exchange_config)`.

### IN-05: Das reservierte Wort `refusals` steht nur im Quelltext

**File:** `src/mcp_connector/exapp/audit_read.py:168-177`, `docs/privacy.md:60-62`

**Issue:** Ein Nextcloud-Konto, das wirklich `refusals` heisst, ist ueber `--user` nicht mehr
adressierbar; die Kette wird nur noch von einem Aufruf ohne `--user` mitgelesen. Der Handel
ist im Quelltext und im occ-Hilfetext benannt, aber weder `docs/privacy.md` noch
`docs/token-exchange.md` sagen es dem Betreiber, der die Zeilen sucht. Dasselbe galt fuer
`instance` bereits vorher.

**Fix:** Einen Satz in `docs/privacy.md` neben den Befehl setzen: "`instance` und `refusals`
sind reservierte Woerter dieser Option; ein Konto dieses Namens wird von einem Aufruf ohne
`--user` gelesen."

### IN-06: Das Messskript legt eine Test-CA in den Container und nimmt sie nicht zurueck

**File:** `scripts/exchange_evidence.py:310-335`

**Issue:** `trust_the_issuer()` haengt das Wurzelzertifikat des Testausstellers an den
Vertrauensspeicher des ExApp-Containers an. Im Normalfall raeumt das erneute `register` am
Ende den Container weg. Mit `--keep-armed` oder nach dem Abbruch aus WR-06 bleibt der
Container einem selbstsignierten Aussteller gegenueber vertrauensvoll, ohne dass irgendetwas
das sagt.

**Fix:** Nach dem Anhaengen eine Zeile ausgeben, die den Zustand benennt, und im Hilfetext von
`--keep-armed` ergaenzen, dass der Container danach die Test-CA traegt.

### IN-07: Eine Schichtregel, die sich selbst als ungeprueft ausweist

**File:** `src/mcp_connector/audit/refusals.py:30-35`

**Issue:** Der Moduldocstring formuliert eine Importregel ("What this module must not import.
Anything under ``..oauth``") und stellt im selben Absatz fest, dass sie von keinem Test
gehalten wird. Das ist ehrlich und gut dokumentiert, aber es ist eine ungesicherte Invariante
auf genau dem Modul, das Tokenwerte aus der Kette halten soll. Die Regel kostet als Gate fuenf
Zeilen, die dieselbe AST-Mechanik nutzen, die `tests/contract/test_no_claim_leak.py` schon
mitbringt.

**Fix:**

```python
def test_the_refusal_writer_imports_nothing_out_of_oauth() -> None:
    tree = ast.parse((SRC / REFUSALS).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert "oauth" not in (node.module or ""), f"{REFUSALS}:{node.lineno}"
            assert not (node.level and "oauth" in ast.unparse(node))
```

---

_Reviewed: 2026-09-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---
phase: quick-260926-ktw
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/mcp_connector/audit/refusals.py
  - tests/unit/test_audit_refusals.py
  - tests/contract/test_no_claim_leak.py
  - src/mcp_connector/oauth/verifier.py
  - tests/unit/test_oauth_verifier.py
  - src/mcp_connector/exapp/exchange_check.py
  - src/mcp_connector/entry_exapp.py
  - tests/unit/test_exapp_exchange_check.py
  - src/mcp_connector/exapp/audit_read.py
  - docs/privacy.md
  - scripts/exchange_evidence.py
autonomous: true
requirements: [IN-01, IN-02, IN-03, IN-04, IN-05, IN-06, IN-07]

must_haves:
  truths:
    - "hash(RefusalWriter(...)) raises no TypeError, and two writers over the same provider compare equal regardless of their brake state (IN-01)"
    - "A test fails if audit/refusals.py ever imports anything out of ..oauth, and a counter proof shows the gate sees every import spelling (IN-07)"
    - "repr(OAuthIdentity(..., actor=<value>)) never contains the actor value or the word actor, and the docstring says why (IN-03)"
    - "build_exapp_app loads the exchange configuration exactly once and hands it to exchange_check_routes; env stays the fallback (IN-04)"
    - "The docstring of the text line in audit_read.py states the column shift correctly (IN-02)"
    - "docs/privacy.md tells the operator that instance and refusals are reserved words of --user (IN-05)"
    - "--keep-armed --help says the container keeps the test CA in its trust store (IN-06)"
  artifacts:
    - path: "src/mcp_connector/audit/refusals.py"
      contains: "compare=False"
    - path: "tests/contract/test_no_claim_leak.py"
      contains: "def test_the_refusal_writer_imports_nothing_out_of_oauth"
    - path: "src/mcp_connector/exapp/exchange_check.py"
      contains: "config: ExchangeConfig | None = None"
    - path: "docs/privacy.md"
      contains: "reserved words"
  key_links:
    - from: "src/mcp_connector/entry_exapp.py"
      to: "exchange_check_routes"
      via: "config=exchange_config keyword"
      pattern: "exchange_check_routes\\(env, config=exchange_config\\)"
---

<objective>
Die sieben offenen Info-Befunde IN-01 bis IN-07 aus 24-REVIEW.md (Zeilen 430-534) abräumen. Alle Fixes sind dort vorgezeichnet; keine Design-Neuentscheidungen.

Purpose: Fallen (hash/eq, Doppel-Laden der Config), falsche oder fehlende Doku und eine ungesicherte Schichtregel beseitigen, bevor v1.6 abgeschlossen wird.
Output: Code- und Doku-Korrekturen plus drei neue/erweiterte Tests, atomar committet, alle Hausgates grün.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@.planning/milestones/v1.6-phases/24-audit-anschluss-und-nachweis/24-REVIEW.md

Repo: C:/Users/Student/nextcloud-mcp-connector (Arbeitsbaum sauber, HEAD df5d301 nach Release 0.3.0).

Hausregeln für alle Tasks:
- Docstrings, Kommentare, Doku, Hilfetexte: Englisch, im erzählenden Stil der umgebenden Texte. KEINE Em-Dashes (U+2014) und keine En-Dashes (U+2013).
- NICHT anfassen: src/mcp_connector/middleware.py, Store-Texte, appinfo/info.xml, jede Versionsstelle (pyproject.toml version, uv.lock, info.xml, __version__, CHANGELOG-Versionskopf). 0.3.0 ist gerade released.
- Commits: Autor muss street1983nk <k.cherif@outlook.de> sein (vor dem ersten Commit `git config user.email` prüfen, sonst `--author="street1983nk <k.cherif@outlook.de>"`). Keine Co-Authored-By- oder Claude-Trailer. NICHT pushen (Push-Hook blockiert main, Owner pusht).
- Hausgates, alle via uv, lokal grün VOR jedem Commit:
  - `uv run --no-sync ruff check .`
  - `uv run --no-sync ruff format --check .`
  - `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright`
  - `uv run --no-sync vulture src scripts vulture_whitelist.py`
  - `uv run --no-sync pytest -q` (vor dem letzten Commit die volle Suite; zwischendurch reichen die betroffenen Testdateien)

<interfaces>
From src/mcp_connector/audit/refusals.py (Zeile ~97):
    _windows: dict[str, tuple[int, int]] = field(default_factory=dict, init=False, repr=False)
  Klasse: @dataclass(frozen=True, slots=True) class RefusalWriter mit Feldern store_provider, retention_days, size_limit, _windows; Methode async note_refusal(reason, *, moment=None).
  Moduldocstring Zeilen 28-36: Absatz "What this module must not import." mit dem Satz "Checked on 2026-09-23: this import direction is covered by no test of this repository ..." bis "... not an accident."
  Kommentar zu REFUSAL_WINDOW_SECONDS Zeilen 58-61: "(see the module docstring, and note that no test of this repository holds that direction: checked 2026-09-23)".
  Heutige Imports: ..errors, . store, .store (kein oauth).

From tests/contract/test_no_claim_leak.py:
  SRC = Path(__file__).resolve().parents[2] / "src" / "mcp_connector"
  REFUSALS = "audit/refusals.py"
  Muster: Gate-Funktion über (relative, source) -> list[str] mit "file:line"-Befunden; Gegenproben laufen durch DIESELBE Funktion mit synthetischem Quelltext (z. B. test_the_gate_would_notice_the_acting_party_in_the_refusal_writer).

From src/mcp_connector/oauth/verifier.py (Zeilen ~145-179):
  Docstring-Absatz zu actor endet mit "Both are foreign text and both are carried unquoted, under the same rule and for the same reason. It defaults to the empty string ..."
  class OAuthIdentity: nc_user, app_password, auth_id, client_id, principal, revoked=False, client_name="", actor="", credential=CREDENTIAL_APP_PASSWORD
  __repr__ nennt nc_user, principal, auth_id, client_id, client_name, revoked, credential, app_password='***' (actor fehlt).

From src/mcp_connector/oauth/chain.py:
  def build_chain(..., config: ExchangeConfig | None = None, ...)  ->  loaded = config if config is not None else load_exchange_config(env)

From src/mcp_connector/exapp/exchange_check.py:
  Zeile 48: from ..oauth.chain import load_exchange_config
  Zeile 234: def exchange_check_routes(env: Mapping[str, str] | None = None) -> list[Route]:
  Zeile 249: config = load_exchange_config(env)
  Docstring-Absatz "The configuration is read once, here, and not per request. ..." begründet nur das Nicht-Werfen.

From src/mcp_connector/entry_exapp.py:
  Zeile 107: exchange_config = chain.load_exchange_config(env)
  Zeile 181: config=exchange_config,   (an build_chain)
  Zeile 373: *exchange_check_routes(env),

From tests/unit/test_exapp_exchange_check.py:
  ARMED = {...} (Zeile 56), client_for(env=ARMED) -> TestClient(Starlette(routes=exchange_check.exchange_check_routes(env)))

From scripts/exchange_evidence.py:
  Zeile ~697: parser.add_argument("--keep-armed", action="store_true", help="leave the exchange configuration in place (for a second look, never for a rest)")
  trust_the_issuer() gibt bereits "the test issuer root is appended to {TRUST_BUNDLE}" aus (Laufzeitzeile existiert).

From docs/privacy.md (Zeile ~60-62):
  "... `occ mcp_connector:audit:read --user=refusals` is how an administrator reads them."
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: IN-01 und IN-07, der Schreiber der Ablehnungskette (hash/eq-Falle, Importregel als Gate)</name>
  <files>src/mcp_connector/audit/refusals.py, tests/unit/test_audit_refusals.py, tests/contract/test_no_claim_leak.py</files>
  <behavior>
    - IN-01: hash(writer) wirft keinen TypeError; zwei RefusalWriter über dasselbe store_provider-Objekt sind gleich und haben gleichen Hash, auch nachdem einer von beiden per note_refusal einen Bremszustand aufgebaut hat.
    - IN-07 Gate: _oauth_imports über den echten Quelltext von audit/refusals.py liefert eine leere Liste.
    - IN-07 Gegenprobe: dieselbe Funktion meldet für synthetischen Quelltext je einen Befund mit Zeilennummer für `from ..oauth import throttle`, `from ..oauth.throttle import WINDOW`, `from .. import oauth`, `import mcp_connector.oauth.throttle`, `from mcp_connector.oauth import chain`; und keinen Befund für `from ..errors import known_reason` sowie für den Text "oauth" nur in einem Kommentar oder Docstring.
  </behavior>
  <action>
    IN-01 (per 24-REVIEW IN-01): In refusals.py das Feld _windows auf field(default_factory=dict, init=False, repr=False, compare=False) umstellen. Den bestehenden #:-Kommentar darüber um einen Satz ergänzen, dass der Bremszustand weder am Vergleich noch am Hash teilnimmt, weil ein Schreiber sonst unhashbar wäre und zwei Schreiber nach ihrem Zustand statt nach ihrer Herkunft verglichen würden. In tests/unit/test_audit_refusals.py einen Test anlegen (vorhandene Fixtures writer/writer_over nutzen, ein Provider-Objekt für beide Schreiber), der hash() aufruft und Gleichheit nach einem note_refusal auf nur einem Schreiber prüft. Test zuerst schreiben und rot sehen (TypeError), dann fixen.

    IN-07 (per 24-REVIEW IN-07): In tests/contract/test_no_claim_leak.py eine Gate-Funktion _oauth_imports(relative: str, source: str) -> list[str] nach dem Muster von _calls_of/_entry_violations bauen: ast.walk über ast.parse(source, filename=relative); Befund "relative:lineno" für jedes ast.ImportFrom, dessen module ein Pfadsegment "oauth" hat (module.split(".")) oder dessen Aliasnamen "oauth" enthalten, und für jedes ast.Import, dessen Name ein Segment "oauth" hat. Segmentvergleich statt Teilstring, damit ein künftiger Modulname wie "oauthless" kein Fehlalarm ist. Dann zwei Tests: test_the_refusal_writer_imports_nothing_out_of_oauth (liest (SRC / REFUSALS).read_text(encoding="utf-8"), erwartet []), und test_the_import_gate_would_notice_every_spelling_of_oauth (Gegenprobe durch dieselbe Funktion, Fälle aus behavior). Kurzer Kommentar über der Funktion, der auf die Regel im Moduldocstring von refusals.py verweist. Den Moduldocstring der Testdatei NICHT umschreiben, höchstens einen Satz anhängen, dass die Datei auch die Importrichtung von refusals.py hält.

    Danach in refusals.py die beiden Stellen, die die Regel als ungeprüft ausweisen, auf den neuen Stand bringen: im Moduldocstring den Satz "Checked on 2026-09-23: this import direction is covered by no test ..." bis "... not an accident." ersetzen durch: die Richtung wird seit dem Abräumen von IN-07 von test_the_refusal_writer_imports_nothing_out_of_oauth in tests/contract/test_no_claim_leak.py gehalten (Abgrenzung zu test_module_boundaries.py und record.py darf als ein Satz bleiben). Im Kommentar zu REFUSAL_WINDOW_SECONDS die Klammer "(... note that no test of this repository holds that direction: checked 2026-09-23)" durch einen Verweis auf dasselbe Gate ersetzen. Keine Em-Dashes.

    Gates für die drei Dateien grün, dann ein Commit: "fix(audit): keep the refusal brake out of eq/hash and gate its oauth import rule (IN-01, IN-07)".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector && uv run --no-sync pytest -q tests/unit/test_audit_refusals.py tests/contract/test_no_claim_leak.py && uv run --no-sync ruff check . && uv run --no-sync ruff format --check . && grep -c "covered by no test" src/mcp_connector/audit/refusals.py | grep -qx 0</automated>
  </verify>
  <done>_windows hat compare=False; hash-Test und beide Import-Tests grün; Gegenprobe meldet alle fünf Schreibweisen; refusals.py behauptet nirgends mehr, die Regel sei ungetestet; Commit ohne Claude-Trailer liegt vor.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: IN-03 und IN-04, actor im repr begründet weggelassen, Exchange-Config nur einmal geladen</name>
  <files>src/mcp_connector/oauth/verifier.py, tests/unit/test_oauth_verifier.py, src/mcp_connector/exapp/exchange_check.py, src/mcp_connector/entry_exapp.py, tests/unit/test_exapp_exchange_check.py</files>
  <behavior>
    - IN-03: repr(OAuthIdentity(..., client_name="named-here", actor="foreign-azp-7f3a")) enthält "named-here", enthält NICHT "foreign-azp-7f3a" und NICHT die Zeichenfolge "actor"; app_password bleibt als '***' maskiert.
    - IN-04: exchange_check_routes({}, config=load_exchange_config(ARMED)) verhält sich bewaffnet (ein Aufruf antwortet nicht mit OUTCOME_NOT_CONFIGURED), obwohl env leer ist; exchange_check_routes(ARMED) ohne config verhält sich unverändert (Rückfall auf env).
  </behavior>
  <action>
    IN-03 (per 24-REVIEW IN-03, Owner-akzeptierte sichere Richtung R-24-04 in 24-SECURITY.md): actor bleibt im __repr__ WEGGELASSEN, __repr__ selbst unverändert. Im Docstring von OAuthIdentity den Satz "Both are foreign text and both are carried unquoted, under the same rule and for the same reason." so fortführen, dass die Gleichbehandlung beim Tragen gilt, nicht bei der Fehlersuchausgabe: actor steht bewusst nicht im repr, weil es den Kunden eines fremden Realms benennt und eine Fehlersuchausgabe in Logs landet, die niemand als Audit-Pfad liest; wer die handelnde Partei sehen will, liest die Audit-Spalte actor. client_name steht darin, weil der Name hier registriert wurde. Ein Hinweis auf R-24-04 als Beleg der Owner-Entscheidung. Test in tests/unit/test_oauth_verifier.py neben test_the_repr_names_the_credential_way_and_still_masks_the_password: OAuthIdentity direkt konstruieren (alle Pflichtfelder mit unverwechselbaren Werten, die das Wort actor nicht enthalten), Behauptungen aus behavior. Da __repr__ schon passt, ist der Test sofort grün; das ist hier gewollt (Festschreibtest), trotzdem einmal gegen eine lokal eingefügte actor-Zeile laufen lassen, um zu zeigen, dass er rot werden kann, und die Zeile wieder entfernen.

    IN-04 (per 24-REVIEW IN-04, Muster build_chain in oauth/chain.py): Signatur auf exchange_check_routes(env: Mapping[str, str] | None = None, config: ExchangeConfig | None = None) -> list[Route] ändern; ExchangeConfig aus ..oauth.chain importieren (dort definiert oder re-exportiert; mit grep prüfen, woher build_chain es hat, und genauso importieren). Rumpf: loaded = config if config is not None else load_exchange_config(env), weiter mit dem bisherigen Namen config im Handler (oder konsequent umbenennen). None bleibt doppeldeutig (nicht übergeben oder aus). Wie bei build_chain ist das harmlos: ein aus env gelesenes None führt beim Rückfall wieder zu None. Docstring-Absatz "The configuration is read once, here, ..." umschreiben: build_exapp_app hat die Antwort beim Start schon gelesen und reicht sie herein, damit eine Anwendung genau einen Leser dieser Frage hat; env ist nur der Rückfall für Aufrufer ohne vorgelesene Antwort (die Tests); die Begründung, warum der Rückfall nicht werfen kann, bleibt als ein Satz erhalten. In entry_exapp.py Zeile ~373 auf *exchange_check_routes(env, config=exchange_config) umstellen. Test in tests/unit/test_exapp_exchange_check.py: TestClient(Starlette(routes=exchange_check.exchange_check_routes({}, config=load_exchange_config(ARMED)))), einen Aufruf nach dem Muster eines vorhandenen bewaffneten Tests (z. B. test_a_token_that_falls_still_answers_200, JSON-Form) absetzen und prüfen, dass outcome nicht OUTCOME_NOT_CONFIGURED ist. AppAPI-Header prüft _guard gegen env: falls der Guard mit leerem env ablehnt, statt {} ein env aus ARMED ohne die Exchange-Schlüssel verwenden (Schlüssel per Präfix aus ARMED herausfiltern) und das im Test kommentieren. Test zuerst schreiben (rot, weil der Parameter fehlt), dann umsetzen.

    Gates grün, dann zwei Commits: "docs(oauth): say why the acting party stays out of the identity repr (IN-03)" und "refactor(exapp): hand the loaded exchange config to the dry-run routes (IN-04)".
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector && uv run --no-sync pytest -q tests/unit/test_oauth_verifier.py tests/unit/test_exapp_exchange_check.py && grep -q "exchange_check_routes(env, config=exchange_config)" src/mcp_connector/entry_exapp.py && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright</automated>
  </verify>
  <done>__repr__ unverändert ohne actor, Docstring begründet es mit Verweis auf R-24-04, Festschreibtest grün; exchange_check_routes nimmt config, entry_exapp reicht exchange_config durch, neuer Test beweist, dass die übergebene Config Vorrang vor env hat; zwei Commits.</done>
</task>

<task type="auto">
  <name>Task 3: IN-02, IN-05, IN-06, Texte korrigieren und volle Gate-Runde</name>
  <files>src/mcp_connector/exapp/audit_read.py, docs/privacy.md, scripts/exchange_evidence.py</files>
  <action>
    IN-02 (per 24-REVIEW IN-02): Im Docstring der Textzeilen-Funktion in audit_read.py (Zeilen ~306-312) den Satz "The count stands last, and it is last so the ten columns that were there before it kept their places." ersetzen. Sinn laut Review: aus zehn Spalten wurden elf; actor steht an sechster Stelle, direkt hinter dem Client-Namen, und verschiebt die vier Spalten dahinter (outcome, reason, duration_ms, params) um eine Stelle; wer die Textform nach Position liest, liest ab dieser Version verschoben; die Dokumentform von _document bleibt schlüsselstabil und ist die Form für Skripte. Vorher mit git show 50723cd:src/mcp_connector/exapp/audit_read.py die Spaltenzahl vor der Änderung nachzählen und die im Text genannten Zahlen danach richten (Review: vorher neun Spalten; constraint-Wortlaut sagt zehn zu elf; die gemessene Zahl gewinnt, Befund in der SUMMARY vermerken). Den Rest des Absatzes (warum die Zählung existiert) sinngemäß behalten, der Zählung ihren Platz als letzte Spalte lassen.

    IN-05 (per 24-REVIEW IN-05): In docs/privacy.md direkt hinter dem Satz, der `occ mcp_connector:audit:read --user=refusals` nennt, einen Satz im Ton der Seite anfügen: `instance` and `refusals` are reserved words of the `--user` option; the chain of an account that is really called by one of these names is read by a call without `--user`. Keine weitere Umformulierung der Seite.

    IN-06 (per 24-REVIEW IN-06): In scripts/exchange_evidence.py den help-Text von --keep-armed ergänzen, etwa: "leave the exchange configuration in place (for a second look, never for a rest); the ExApp container then also keeps the test issuer's CA in its trust store until it is registered again". Die Laufzeitzeile in trust_the_issuer() existiert bereits, nicht doppeln. Optional darf diese print-Zeile den Zustand deutlicher benennen (z. B. "... the container now trusts the test issuer until it is registered again"), wenn das ohne Testbruch geht.

    Dann die volle Gate-Runde über das ganze Repo: ruff check, ruff format --check, pyright (latest), vulture src scripts vulture_whitelist.py, volle pytest-Suite. Em-Dash-Prüfung über alle geänderten Dateien. Ein Commit: "docs: correct the column note, name the reserved --user words and the kept test CA (IN-02, IN-05, IN-06)".

    Zum Schluss in 24-REVIEW.md die Zeile "_Resolved: 2026-09-24 (1 Critical und 6 Warnings behoben, 7 Info offen)_" um eine Zeile ergänzen: "_Info resolved: 2026-09-26 (IN-01 bis IN-07, quick 260926-ktw)_" und den Einleitungssatz des Info-Abschnitts entsprechend anpassen (deutsch, echte Umlaute, keine Em-Dashes); mit dem SUMMARY-Commit der Quick-Task mitcommitten.
  </action>
  <verify>
    <automated>cd C:/Users/Student/nextcloud-mcp-connector && uv run --no-sync ruff check . && uv run --no-sync ruff format --check . && PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright && uv run --no-sync vulture src scripts vulture_whitelist.py && uv run --no-sync pytest -q && uv run --no-sync python scripts/exchange_evidence.py --help | grep -qi "trust" && grep -q "reserved words" docs/privacy.md && ! grep -n "ten columns that" src/mcp_connector/exapp/audit_read.py && ! git diff HEAD~4 --unified=0 | grep -P "^\+.*[\x{2013}\x{2014}]"</automated>
  </verify>
  <done>Docstring nennt die Spaltenverschiebung korrekt, privacy.md nennt beide reservierten Wörter, --help von --keep-armed nennt die verbleibende Test-CA; alle Hausgates und die volle Suite grün; keine Em-/En-Dashes in den Diffs; keine Versionsstelle, middleware.py, info.xml oder Store-Text geändert; nichts gepusht.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| fremder Realm -> OAuthIdentity.actor | azp eines fremd ausgestellten Tokens, Fremdtext |
| Pre-Auth-Pfad -> audit/refusals.py | ungeprüfte Tokens dürfen keine Werte in die Kette tragen |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-ktw-01 | Information Disclosure | OAuthIdentity.__repr__ | mitigate | actor bleibt draußen (R-24-04), neuer Test hält fest, dass weder Wert noch Feldname im repr stehen |
| T-ktw-02 | Tampering | audit/refusals.py Importrichtung | mitigate | AST-Gate test_the_refusal_writer_imports_nothing_out_of_oauth plus Gegenprobe aller Schreibweisen |
| T-ktw-03 | Tampering | exchange_check_routes Config-Quelle | mitigate | eine geladene Config pro Anwendung; Test beweist Vorrang der übergebenen Config |
| T-ktw-04 | Spoofing | Messskript --keep-armed | accept | reines Test-Werkzeug; Hilfetext benennt die verbleibende Test-CA, Laufzeitzeile existiert |
</threat_model>

<verification>
- Alle sieben Befunde IN-01..IN-07 haben einen Commit mit ihrer ID in der Nachricht.
- `git log --format='%an <%ae>%n%b' HEAD~4..HEAD` zeigt nur street1983nk <k.cherif@outlook.de> und keine Trailer.
- `git diff df5d301 --stat` enthält keine Datei aus: middleware.py, appinfo/info.xml, pyproject.toml, uv.lock.
</verification>

<success_criteria>
- IN-01..IN-07 umgesetzt wie in 24-REVIEW vorgezeichnet, keine Design-Neuentscheidung.
- ruff check, ruff format --check, pyright (latest), vulture, volle pytest-Suite lokal grün.
- Vier atomare Commits (Task 1: 1, Task 2: 2, Task 3: 1), nicht gepusht.
</success_criteria>

<output>
Create `.planning/quick/260926-ktw-24-review-infos-in-01-bis-in-07-abraeume/260926-ktw-SUMMARY.md` when done
</output>

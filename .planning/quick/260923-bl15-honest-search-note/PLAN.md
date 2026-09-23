---
type: quick
date: 2026-09-23
task: BL-15, ehrliche Suchnote und Tool-Beschreibung von unified_search
files_modified:
  - src/mcp_connector/server/reg_search.py
  - tests/contract/test_tool_surface.py
  - .planning/BACKLOG.md
---

# BL-15: Restarbeit an der ehrlichen Suchnote (Tool-Beschreibung von unified_search)

## Ziel

Die letzte falsche Behauptung aus BL-15 entfernen: Die registrierte Tool-Beschreibung von
`unified_search` sagt weiterhin "matches names and metadata, not file contents". Sobald ein
Content-Provider (Findling) installiert ist, ist der Satz falsch, und ein Client liest ihn
VOR jedem Aufruf. Nach diesem Plan traegt keine Stelle im Tool-Surface mehr eine Behauptung,
die von der Installation abhaengt, und BL-15 ist im Backlog geschlossen.

## Ausgangslage (gemessen 2026-09-23, wichtig: der Auftragstext ist veraltet)

**Der Kern von BL-15 ist bereits umgesetzt und gemergt** (Commit `aed6bdd`, PR #3,
07.09.2026, "Ships with release 0.1.12"). Nicht erneut bauen:

- `src/mcp_connector/tools/search.py` hat `_note(selected, degraded)`: die Note haengt an
  der Laufzeit-Antwort. Kein Content-Provider hat geantwortet: die konservative Konstante
  `SEARCH_NOTE` bleibt. Einer hat geantwortet: die Note lautet
  `"matched on names, metadata and file contents; findling searched inside documents"`.
  Ein degradierter Content-Provider zaehlt als "hat nicht geantwortet".
- Erkennungsmechanismus: `CONTENT_PROVIDERS = frozenset({"findling"})`, Abgleich gegen die
  zur Laufzeit selektierten Provider-Ids minus der degradierten. Die Menge waechst laut
  Kommentar nur durch Beweis (Fidelity-Test BL-02), nie durch Vermutung. NICHT auf eine
  generische Heuristik umbauen.
- `_TERM_HINT` in `search.py` (der Fehler-Hint bei leerem Suchbegriff) ist schon ehrlich:
  "Whether words inside documents are found depends on the installed providers; the note of
  every answer says what this search actually matched."
- Beide Note-Zweige sind getestet: `tests/unit/test_unified_search.py`,
  `test_the_note_admits_content_hits_when_findling_answered` (Zeile ~398) und
  `test_the_note_stays_conservative_when_the_content_provider_broke` (Zeile ~426).
  `tests/integration/test_content_hit_fidelity.py:244` prueft `"not indexed" not in note`.
- `context.py` reicht die innere Note durch statt die Konstante zu wiederholen.

**Was noch offen ist (der Umfang dieses Plans):**

1. `src/mcp_connector/server/reg_search.py:30`: der registrierte Docstring, also die
   Tool-Beschreibung, die jeder Client vor dem Aufruf liest, sagt noch
   `(matches names and metadata, not file contents)`. Genau die Stelle, die BL-15 als die
   schlimmere bezeichnet. Der Commit `aed6bdd` hat `reg_search.py` nicht angefasst
   (per `git show --stat` verifiziert).
2. `tests/contract/test_tool_surface.py:446` pinnt die falsche Behauptung sogar fest:
   `assert "not file contents" in (tool.description or "")` innerhalb von
   `test_unified_search_is_listed_as_a_pure_read_over_all_providers`.
3. `.planning/BACKLOG.md` BL-15 traegt keinen STATUS-Block; der Eintrag liest sich als
   offen, obwohl der Kern seit `aed6bdd` gemergt ist.

## Nicht anfassen

- `src/mcp_connector/tools/files.py` und `src/mcp_connector/server/reg_files.py:28`
  ("matches names, not file contents"): WebDAV-Suche konsultiert keine Provider, der Satz
  bleibt wahr. Auch `tests/contract/test_tool_surface.py:142-148`
  (`test_files_search_says_in_its_description_that_contents_are_not_matched`) bleibt.
- `src/mcp_connector/tools/search.py`: fertig, keine Codeaenderung.
- Bestehende Unit- und Integrationstests der Note: bleiben unveraendert gruen.

## Wortlaut

Neue Tool-Beschreibung (Englisch, keine Em-Dashes, keine Emojis), wahr mit und ohne
Content-Provider, im Muster des schon gefixten `_TERM_HINT`:

    Search the whole Nextcloud across all installed search providers. The note of every answer says whether file contents were matched.

Budget-Rechnung: alte Beschreibung 110 Zeichen, neue 133 Zeichen, Delta +23 Bytes bei
1.588 Bytes Luft (16.412/18.000). Das Budget-Gate
(`scripts/check_tool_budget.py`, gehalten von `tests/contract/test_tool_surface.py`)
bleibt gruen. Einzeiler-Docstring mit `# noqa: E501` beibehalten, KEIN mehrzeiliger
Docstring: der volle Docstring ist die Beschreibung, ein Umbruch aendert den Payload.

## Tasks

### Task 1 (test-first): Contract-Pin umdrehen

**Dateien:** `tests/contract/test_tool_surface.py`

**Aenderung:** In `test_unified_search_is_listed_as_a_pure_read_over_all_providers` die
Assertion in Zeile 446-448 ersetzen durch:

    description = tool.description or ""
    assert "not file contents" not in description, (
        "the blanket claim is false the day a content provider answers (BL-15)"
    )
    assert "note" in description, (
        "the description defers to the per answer note, which carries the truth per call"
    )

Kein neuer Testname noetig: der Pin lebt in diesem Test, also wird er dort umgedreht. Das
Test-Docstring-Stichwort "expectation management is in the text" bleibt korrekt, weil die
Beschreibung weiterhin auf die Note verweist.

**Verifikation (rot):**
`uv run pytest tests/contract/test_tool_surface.py::test_unified_search_is_listed_as_a_pure_read_over_all_providers -x`
MUSS gegen den aktuellen Code fehlschlagen (alte Beschreibung enthaelt "not file contents").

**Commit:** `test(search): the tool description must not deny content hits (BL-15)`

### Task 2: Registrierten Docstring ersetzen

**Dateien:** `src/mcp_connector/server/reg_search.py`

**Aenderung:** Zeile 30, Docstring ersetzen durch den Wortlaut oben, `# noqa: E501`
beibehalten.

**Verifikation (gruen):**
`uv run pytest tests/contract/test_tool_surface.py -q` (inklusive Budget-Gate und
`test_every_tool_has_a_non_empty_description_and_only_two_have_an_output_schema`).

**Commit:** `fix(search): the tool description defers to the note instead of denying content hits (BL-15)`

### Task 3: Backlog schliessen

**Dateien:** `.planning/BACKLOG.md`

**Aenderung:** Im Abschnitt BL-15 direkt unter der Ueberschrift einen STATUS-Block im Stil
der anderen Eintraege ergaenzen, sinngemaess:

    **STATUS 2026-09-23: DONE.** Der Kern (laufzeitabhaengige Note via `_note` und
    `CONTENT_PROVIDERS`, ehrlicher `_TERM_HINT`, Durchreichen in `prepare_context`, Tests
    beider Zweige) kam mit Commit `aed6bdd` (PR #3, 0.1.12). Der Rest, die registrierte
    Tool-Beschreibung in `reg_search.py` samt Contract-Pin, kam mit diesem Quick-Fix.
    `files_search` bewusst unveraendert (WebDAV, Satz bleibt wahr). BL-01 verliert damit
    seinen zweiten Blocker.

Deutsche Umlaute im deutschen Prosa-Teil, Code-Bezeichner unveraendert englisch. Keine
weiteren Umformulierungen am Eintrag (Regel: nur die erbetene Aenderung).

**Verifikation:** Sichtpruefung; kein Test haengt am Backlog-Wortlaut.

**Commit:** `docs(backlog): close BL-15, description fix completes aed6bdd`

## Abschlussverifikation (alles gruen vor dem letzten Commit)

    uv run pytest tests/contract/test_tool_surface.py tests/unit/test_unified_search.py tests/unit/test_tools_context.py -q
    uv run ruff check .
    uv run ruff format --check .
    PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright
    uv run vulture

Integrationstest `tests/integration/test_content_hit_fidelity.py` laeuft nur mit
installiertem Findling (CI-ExApp-Job); lokal nicht Teil des Gates, bleibt unberuehrt.

## Commits (Reihenfolge)

1. `test(search): the tool description must not deny content hits (BL-15)` (rot)
2. `fix(search): the tool description defers to the note instead of denying content hits (BL-15)` (gruen)
3. `docs(backlog): close BL-15, description fix completes aed6bdd`

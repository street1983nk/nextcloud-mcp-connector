---
phase: 31-ordner-anlegen
plan: 04b
subsystem: api
tags: [webdav, mkcol, files, netzfehler, teilabbruch, tdd]

requires:
  - phase: 31-ordner-anlegen
    provides: files.create_folder mit Abbruch-Hülle _with_created (Plan 31-02), MKCOL-Nadel (Plan 31-04)
provides:
  - Netzzweig in files.create_folder (httpx.RequestError während oder nach einem MKCOL)
  - Fabrik files._cut_off (Meldung, Hinweis, reason timeout oder unreachable)
  - Ein Satz zu Netzfehlern bei D-31-02 in 31-CONTEXT.md
affects: [31-05, 31-06, 34]

tech-stack:
  added: []
  patterns:
    - "Netzfehler nach dem ersten Schreiben werden zu einem ToolError und laufen durch dieselbe Hülle wie jeder andere Abbruch"
    - "Merker under_way: nur der Ordner, dessen MKCOL gerade unterwegs ist, kann 'unbekannt' sein"

key-files:
  created:
    - .planning/phases/31-ordner-anlegen/31-04b-PLAN.md
  modified:
    - src/mcp_connector/tools/files.py
    - tests/unit/test_files_create_folder.py
    - tests/unit/test_files_create_folder_exclusion.py
    - .planning/phases/31-ordner-anlegen/31-CONTEXT.md

key-decisions:
  - "Gefangen wird httpx.RequestError (Oberklasse von TimeoutException und TransportError), dieselben zwei Klassen, die @graceful unterscheidet; reason bleibt timeout bzw. unreachable"
  - "Jeder Netzabbruch während eines MKCOL gilt als 'Zustand unbekannt', auch ein Verbindungsfehler vor dem Senden (konservative Lesart)"
  - "Der Aufruf ohne parents bekommt denselben Satz; sein Hinweis nennt den erneuten Aufruf mit demselben Pfad, nicht parents=true"

patterns-established:
  - "respx führt je Muster eine Route: eine zweite Route mit gleichem Muster ersetzt die Antwort der ersten, Zähler sind identisch"

requirements-completed: []

duration: 35min
completed: 2026-11-12
---

# Phase 31 Plan 04b: Netzfehler in der Ordnerkette Summary

**Ein Timeout oder Verbindungsabbruch während oder nach einem MKCOL von files_create_folder endet jetzt in einer Meldung, die das sicher Angelegte nennt und davon den Ordner trennt, dessen Zustand unbekannt ist; vor jedem Schreiben bleibt alles wie bisher.**

## Performance

- **Duration:** ca. 35 min
- **Completed:** 2026-11-12
- **Tasks:** 2 von 2
- **Files modified:** 3 (Code und Tests), dazu Plan und ein Satz in 31-CONTEXT.md

## Accomplishments

- `create_folder` fängt `httpx.RequestError` an zwei Stellen: um den einen MKCOL ohne `parents` und in der Schleife der Kette. Die bestehenden Zweige (`except ToolError`) sind unverändert.
- In der Kette hält `under_way` fest, ob gerade ein MKCOL unterwegs ist. Nur dann nennt die Meldung ein Segment als unbekannt.
- `_cut_off` baut die Meldung; die Liste des Angelegten hängt weiter `_with_created` an (derselbe Zusatz wie bei 403, 423, 507, 5xx).
- Ist kein MKCOL unterwegs und nichts angelegt, steigt die httpx-Ausnahme unverändert zu `@graceful` auf.
- `dav.py`, `server/reg_files.py`, `server/__init__.py`, die MKCOL-Nadel und das Budget-Skript sind unberührt.

## Wortlaut der neuen Meldungen

Auf dem Draht setzt `@graceful` wie bisher `"{message} Hint: {hint}"` zusammen.

- MKCOL unterwegs, Timeout, schon etwas angelegt:
  `Nextcloud did not respond in time while creating /A/b/c; whether that folder exists now is unknown. Already created in this call and left in place: /A/b.`
- MKCOL unterwegs, anderer Netzfehler, schon etwas angelegt:
  `Could not reach Nextcloud while creating /A/b/c/d; whether that folder exists now is unknown. Already created in this call and left in place: /A/b, /A/b/c.`
- Erster MKCOL (Kette oder ohne parents), nichts angelegt:
  `Nextcloud did not respond in time while creating /A/b; whether that folder exists now is unknown. No other folder was created in this call.` (entsprechend mit `Could not reach Nextcloud`)
- Lesezugriff zwischen zwei Segmenten bricht ab (kein MKCOL unterwegs), schon etwas angelegt:
  `Could not reach Nextcloud. Already created in this call and left in place: /A/b.` (entsprechend `Nextcloud did not respond in time.`)
- Hinweis in der Kette: `Call again with the same path and parents=true; that is safe: folders that exist are kept and only the missing ones are created.`
- Hinweis ohne parents: `Call again with the same path; that is safe: a folder that exists is kept.`
- reason: `timeout` bei `httpx.TimeoutException`, sonst `unreachable`.

## Task Commits

1. **Plan und Satz in 31-CONTEXT.md** - `c4d5c42` (docs)
2. **Task 1: Netzzweig in create_folder, testgetrieben** - `f3e5375` (feat)
3. **Task 2: Voller Lauf R1 und Diff-Prüfung** - kein eigener Commit (keine Dateiänderung)

## Files Created/Modified

- `src/mcp_connector/tools/files.py` - zwei `except httpx.RequestError`, Merker `under_way`, Fabrik `_cut_off`, Docstring-Absatz, Import von REASON_TIMEOUT und REASON_UNREACHABLE
- `tests/unit/test_files_create_folder.py` - 12 neue Testfunktionen (24 Fälle): Timeout am zweiten MKCOL, Abbruch am dritten, Abbruch am ersten, ohne parents, Lesezugriff zwischen zwei Segmenten, Zählung, Sandbox-Wurzel, 405 ohne parents, Nachlesen der Id
- `tests/unit/test_files_create_folder_exclusion.py` - 3 neue Testfunktionen (12 Fälle): getaggt, nicht beantwortbare Prüfung, Positivkontrolle ohne Tag
- `.planning/phases/31-ordner-anlegen/31-CONTEXT.md` - ein Satz bei D-31-02

## Verifikation (gesehene Ausgaben)

- RED vor der Umsetzung: `12 failed, 78 passed` in den beiden Testdateien; die roten Fälle scheiterten an der rohen httpx-Ausnahme (`httpx.ReadTimeout: Mock Error`, `httpx.ConnectError: down`). Die übrigen 24 neuen Fälle waren sofort grün, weil sie bisheriges Verhalten festhalten (Zählung, Sandbox-Wurzel, Nachlesen der Id, Ausschluss).
- GREEN: beide Dateien `90 passed`.
- Mutationsproben, je einzeln, danach Datei per Kopie wiederhergestellt (SHA-256 gleich):
  - (a) beide neuen `except`-Zweige entfernt: `12 failed, 78 passed` (auf dem Endstand wiederholt, gleiches Ergebnis)
  - (b) `under_way = None` nach dem MKCOL entfernt: `3 failed, 87 passed` (Lesezugriff zwischen zwei Segmenten würde fälschlich "unknown" melden)
  - (c) das Weiterreichen bei "nichts unterwegs, nichts angelegt" entfernt: `1 failed, 89 passed`
- Voller Lauf: `pytest tests/unit tests/contract` mit überschriebenem addopts: `5868 passed, 35 skipped`, Exit 0 (vorher 5832; 36 neue Fälle).
- `check_tool_budget.py`: Exit 0, `tools/list: 16222 bytes, 24 tools, budget 18000`.
- ruff check: Exit 0; ruff format --check: Exit 0 (373 Dateien); pyright: Exit 0 (0 Fehler); vulture: Exit 0.
- Diff-Prüfung, Positivkontrolle der Basis 91c3b51 bestanden (40 Hex, Vorfahr von HEAD, 31-01-PLAN.md liegt in ihr):
  - `git diff 620ab4e -- server/reg_files.py server/__init__.py`: 0 Zeilen (Docstring des Werkzeugs und Server-Instruktion gleich dem Stand nach 31-03); Gegentreffer in derselben Form: `+def _cut_off` in files.py 1
  - gegen die Basis: `+async def files_create_folder` 1, `+def _cut_off` 1, `+CREATE_IDEMPOTENT = ToolAnnotations` 1; geänderte Zeilen der Server-Instruktion 0
  - `dav.py`, `test_no_destructive_calls.py`, `check_tool_budget.py`: 0 geänderte Zeilen; `EXPECTED_MKCOL_CALLS = 2` unverändert
- Entfernte Zeilen in tests: nur drei Importzeilen, die erweitert wurden; kein bestehender Test geändert. Neue Zeilen in src und tests: 0 Nicht-ASCII-Zeichen, 0 Treffer `permissions`.
- Zwei Commits als street1983nk, ohne Trailer; kein Push.

## Decisions Made

- Fehlerklasse am Code geprüft: `dav.make_folder` und `dav.probe_folder` reichen httpx-Ausnahmen ungefangen durch; `@graceful` fängt `httpx.TimeoutException` und danach `httpx.RequestError`. Der neue Zweig fängt genau `httpx.RequestError` und unterscheidet darin Timeout von allem anderen.
- Die Satzanfänge sind die von `@graceful`; ein Test hält fest, dass beide Sätze dort stehen.

## Auslegungen

- **Aufruf ohne parents:** Der Entscheid spricht von der Kette. Der eine MKCOL ohne `parents` ist ebenfalls ein "erster MKCOL" mit unbekanntem Zustand und bekommt denselben Satz. Sein Hinweis nennt den erneuten Aufruf mit demselben Pfad statt `parents=true`, weil `parents=true` dort mehr täte als der ursprüngliche Aufruf (fehlende Elternordner anlegen).
- **Verbindungsfehler vor dem Senden:** Bei `ConnectError` oder `ConnectTimeout` hat der MKCOL den Server sicher nicht erreicht. Die Meldung sagt trotzdem "unknown" und unterscheidet nicht nach Unterklasse: "unbekannt" ist nie falsch, eine Zusage "nicht angelegt" je httpx-Unterklasse wäre eine Behauptung über das Innenleben des Transports.
- **Lesezugriff nach 405 am ersten Segment:** nichts angelegt, kein MKCOL unterwegs, also bisheriges Verhalten (rohe httpx-Ausnahme zu `@graceful`), auch wenn die Kette schon begonnen hat.
- **Hinweis im Fall "kein MKCOL unterwegs":** statt des Hinweises von `@graceful` ("retry with a smaller range ...") steht der Hinweis auf den gefahrlosen erneuten Aufruf.
- **Paar-Gleichheit im Netzfall:** Ein ausgeschlossener Pfad sendet keinen MKCOL, ein Netzfehler am MKCOL kann ihn also nicht treffen; die Antwort bleibt `parent_missing` bzw. `unavailable_error`. Die Gegenseite (nicht vorhandener Pfad) kann bei einem Netzabbruch des MKCOL anders antworten als die getaggte; das war schon vorher so ("Could not reach Nextcloud" gegen `parent_missing`) und wird von keinem bestehenden Paartest verlangt. Die Paartests sind unverändert grün.

## Deviations from Plan

**1. [Rule 1 - Bug] reason als bedingter Ausdruck verletzte das Reason-Gate**
- **Gefunden in:** Task 2 (voller Lauf)
- **Befund:** Die erste Fassung von `_cut_off` schrieb `reason=REASON_TIMEOUT if timed_out else REASON_UNREACHABLE`; `tests/unit/test_errors_reason.py::test_every_reason_under_src_is_one_of_the_frozen_constants` verlangt an `reason=` eine nackte REASON_*-Konstante (1 failed, 5867 passed).
- **Behoben:** zwei getrennte `ToolError`-Aufrufe mit je einer Konstante; das Gate blieb unangetastet. Danach voller Lauf grün.
- **Commit:** f3e5375 (die rote Fassung wurde nie committet)

**2. Reihenfolge der Routen in den Exklusionstests**
- respx führt je Muster eine Route; die werfende MKCOL-Route wird deshalb nach `_Files.seal()` gesetzt und ersetzt deren Antwort. Im ersten Anlauf (umgekehrte Reihenfolge) überschrieb `seal()` die werfende Route, die Positivkontrolle war aus dem falschen Grund rot ("DID NOT RAISE"). Vor dem RED-Beleg korrigiert.

**3. Ein Commit für Tests und Code**
- RED vorher gesehen, wie in 31-02 bis 31-04.

## Issues Encountered

- Der volle Lauf überschreitet 180 Sekunden und lief im Hintergrund zu Ende; das Ergebnis stammt aus der mitgeschriebenen Ausgabe samt Exit-Code von pytest.

## Offene Punkte

- Die Netzfälle sind nur per Unit-Test belegt (respx). Ein Live-Beleg (echter Abbruch gegen eine Instanz) ist in 31-05 nicht vorgesehen und wurde hier nicht ergänzt; 31-05-PLAN.md und 31-06-PLAN.md sind unverändert.
- CHANGELOG und READMEs nennen das neue Verhalten nicht; ob 31-06 einen Satz dazu bekommt, entscheidet die Hauptsitzung.
- `asyncio.TimeoutError` wird weder von `@graceful` noch vom neuen Zweig gefangen; ob sie hier auftreten kann, wurde nicht geprüft.
- STATE.md, ROADMAP.md und REQUIREMENTS.md wurden nicht angefasst; FOLD-02 ist nicht als erledigt markiert.

## Known Stubs

Keine.

## Next Phase Readiness

- 31-05 kann ohne Änderung fahren: Antwortform, Docstring und Budget sind gleich.
- Kein Docker in diesem Plan.

## Self-Check: PASSED

- 31-04b-PLAN.md, files.py und beide Testdateien vorhanden und committet
- Commits c4d5c42 und f3e5375 im Log gefunden

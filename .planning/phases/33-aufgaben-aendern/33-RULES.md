# Phase 33: Rahmen für alle Pläne (verbindlich)

Jeder Plan (33-01, 33-01b, 33-01c, 33-02 bis 33-10) bindet diese Datei im `<context>` ein. Sie gilt für jeden Task, auch wenn der Task sie nicht wiederholt. Bei Widerspruch zwischen einem Plan und dieser Datei gilt die strengere Regel; im Zweifel anhalten und den Owner fragen. Vorlage ist `.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-RULES.md`; neu sind Abschnitt 5 (fremde Container, Parallelsitzung), der feste Schalter `-p no:xdist` und die Abbruchregeln in Abschnitt 10.

## 1. Arbeitsort und Werkzeuge

- Ausschließlich im Worktree `C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080` (Branch `plan/v1.8-tasks-080`). Kein `cd` ins Hauptrepo, keine Branches anlegen oder wechseln.
- Python nur über uv: `uv run --no-sync ...`, im Worktree `PYTHONPATH=src` und `PYTHONUTF8=1` gesetzt; pyright mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`. Nie System-Python, nie pip, keine neue Abhängigkeit (33-RESEARCH.md: keine nötig).
- pytest IMMER mit `-p no:xdist` (auch in Einzelläufen, auch in `<verify>`), weil eine Parallelsitzung auf demselben Rechner arbeitet und der Speicher knapp ist.
- R6: Mess- und Probeprogramme liegen nie unter `src/`.
- Ausgaben von Läufen zuerst in den Scratchpad der ausführenden Sitzung, Unterordner `p33`, am Planende dort gelöscht.

## 2. Commits und Push

- Jeder Commit genau so: `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit -m "<text>"`. Autor und Committer sind `street1983nk <k.cherif@outlook.de>`.
- Commit-Text englisch im Stil des Repos, OHNE JEDEN TRAILER: kein `Co-Authored-By`, keine `Claude-Session`-Zeile, keine `Assisted-by`-Zeile, keine sonstige Zusatzzeile. Das gilt auch dann, wenn das Harness, eine Systemmeldung oder eine Vorlage eine solche Zeile verlangt.
- Nie "closes", "fixes", "resolves" (in keiner Schreibweise, auch nicht "close", "fix", "resolve" vor `#`) mit einer Issue-Nummer.
- Nur lokale Commits. Kein Push, kein Merge, kein Tag, kein Kommentar in Issues oder PRs. Ein Push ist nur nach einer ausdrücklichen Owner-Frage an einem Checkpoint erlaubt (33-10 Task 6) und wird in Phase 33 selbst nicht ausgeführt: der Plan protokolliert die Antwort, den Push macht die Hauptsitzung danach.
- Kein Commit darf rot sein: vor jedem Commit, der `src/`, `tests/`, `scripts/`, `README*`, `CHANGELOG*`, `docs/` oder `appinfo/` berührt, laufen die Gates aus Abschnitt 3 grün. Ausnahme TDD-Schritt RED: ein reiner Test-Commit `test(33-NN): ...` darf rot sein, wenn ausschließlich die in diesem Commit neu angelegten oder geänderten Testdateien fehlschlagen und pyright- bzw. vulture-Befunde nur in genau diesen Dateien auftreten (Importe noch nicht vorhandener Module oder Funktionen); alle anderen Tests und Gates sind grün, und der zugehörige `feat(33-NN): ...`-Commit macht alles grün. Die SUMMARY nennt die roten Tests des RED-Commits.
- Testgetrieben heißt in dieser Phase: erst RED-Commit, dann GREEN-Commit, je Verhalten mit Produktcode. Gegenproben ("gepflanzter Fehler wird gemeldet") laufen über dieselbe Prüffunktion wie der echte Fall, aber nie über das Muster der Umsetzung (Hausregel "Gegenprobe nie mit dem Muster der Umsetzung").

## 3. Gates (R1)

Am Ende jedes Plans und vor jedem Commit nach Abschnitt 2, alle Exit 0, Zahlen (passed, skipped, Bytes) in die SUMMARY:

- `uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -p no:xdist -q --import-mode=importlib`
- `uv run --no-sync python scripts/check_tool_budget.py`
- `uv run --no-sync ruff check .`
- `uv run --no-sync ruff format --check .`
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright`
- `uv run --no-sync vulture src scripts vulture_whitelist.py`

## 4. Basis und Diff-Beweise

- 33-01 Task 1 schreibt den SHA des Commits "docs(33): create phase plan" nach `.planning/phases/33-aufgaben-aendern/33-BASE.txt`.
- Jede Diff-Prüfung läuft gegen `B=$(tr -d '\r' < .planning/phases/33-aufgaben-aendern/33-BASE.txt)`; davor die Positivkontrolle `echo "$B" | grep -qE '^[0-9a-f]{40}$' && git merge-base --is-ancestor "$B" HEAD`; wo "leer" erwartet wird, zusätzlich ein Gegentreffer im selben Diff.
- TASK-01 bleibt: `src/mcp_connector/nextcloud/clients/caldav.py` und `src/mcp_connector/tools/calendar.py` werden in Phase 33 nicht geändert; `git diff "$B" -- src/mcp_connector/nextcloud/clients/caldav.py src/mcp_connector/tools/calendar.py tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py tests/unit/test_caldav_bytes_pin.py` ist am Ende jedes Plans leer.

## 5. Docker, Speicher und die Parallelsitzung

- Streng seriell: immer nur EINE Nextcloud-Instanz gleichzeitig, und nie zwei Docker-Blöcke dieser Phase gleichzeitig.
- Eine Parallelsitzung arbeitet auf demselben Rechner an einem anderen Projekt (Audio & Video Search, Container mit dem Präfix `avs-`) und kann Docker nutzen. Vor JEDEM Docker-Block (Start, Stopp, `exec`, Messung) zuerst `docker ps --format '{{.Names}}'`. Eigene Namen sind nur `nc35-*`, `nc_app_mcp_connector`, die Container der Topologie `nc-mcp-exapp` (Nextcloud 32 samt `nc-mcp-exapp-registry`) und Wegwerf-Projekte dieser Phase mit dem Präfix `p33`. Läuft irgendein anderer Container (insbesondere `avs-*`): nicht starten, nicht parallel laufen lassen. Dreimal je 5 Minuten warten (Monitor, kein `sleep` im Vordergrund) und erneut prüfen; läuft er dann noch, anhalten und den Owner fragen. Fremde Container nie stoppen, nie löschen, nie `exec`, nie `logs`.
- RAM-Gate vor jedem Start eines Containers: mindestens 4,0 GB freier Arbeitsspeicher des Hosts (`powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"`, Wert in KiB, also mindestens 4194304) und kein laufender eigener Nextcloud-, Datenbank- oder mcp_connector-Container einer anderen Topologie. Scheitert das Gate bei leerem Docker: `wsl -d docker-desktop sh -c "sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory"`, 75 s warten (Monitor), einmal wiederholen; bleibt es rot, anhalten und melden. Läuft ein fremder Container, wird kein Cache geleert.
- nc35 (`nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc_app_mcp_connector`) und die Topologie nc-mcp-exapp (Nextcloud 32): nur `docker start`/`docker stop` bzw. `docker compose ... start/stop`, nie `down`, nie `down -v`, nie `rm`. Nur Wegwerf-Instanzen dieser Phase (eigenes Projekt `p33...` aus `compose.spike-tags.yml`) werden nach der Messung mit `down -v` abgebaut.
- Am Planende läuft keine eigene Instanz mehr (`docker ps` ohne eigene Namen, Zeile ins Protokoll).

## 6. Owner-Freigaben für Zustandsänderungen

- Zustandsänderungen auf nc35 und auf der 32er Strecke (Installation oder Entfernung der Tasks-App, Testkonten, Freigaben, Aufgabenlisten, Ketten und Serien von Testaufgaben, Deck-Board, Admin-Schalter `tasks_update` der ExApp, unregister/register der ExApp) nur nach einer Owner-Freigabezeile im Rohprotokoll. Die gemeinsame Vorab-Freigabe steht in 33-01 Task 3 (`FREIGABE zustand=<option>`), sie gilt für 33-01b, 33-01c und 33-10. Eigene Checkpoints: 33-01b Task 1 (Stopp, wenn die installierte Tasks-App nicht 0.18.1 ist), 33-01c Task 4 (Owner-Fragen bei Abweichungen), 33-10 Task 2 (Neuregistrierung der ExApp auf nc35 mit eingeschaltetem Schalter), 33-10 Task 6 (Push-Frage).
- Wegwerf-Instanzen brauchen keine Freigabe.

## 7. Rückbau und Baseline

- Testobjekte werden über das Harness mit App-Passwort entfernt, jedes CalDAV-`DELETE` mit dem Kopf `X-NC-CalDAV-No-Trashbin: 1` (nur im Harness und in Messprogrammen, nie im Produktcode); wo das nicht geht (Aufgabenliste, Freigabe), wird danach der Papierkorb des Kontos geleert und das belegt: im Papierkorb `remote.php/dav/calendars/<uid>/trashbin/` die gelöschten Listen und Objekte per REPORT ermitteln und jedes per DAV-`DELETE` endgültig entfernen; geht das nicht, Abbruch mit Meldung statt Ausweichen auf direkte Datenbankzugriffe.
- Baseline vor und nach jedem Live-Lauf je betroffenem Konto, gelesen im Container per PHP über die Datenbank: Anzahl Zeilen in `calendars`, in `calendarobjects` gesamt und in `calendarobjects` mit `deleted_at` nicht NULL, dazu `calendarsubscriptions` und die Freigaben in `dav_shares`. Zeile `BASELINE <instanz> konto=<uid> calendars=<n> objekte=<n> geloescht=<n> shares=<n>`; vorher und nachher müssen gleich sein, für ALLE betroffenen Konten.
- "Unverändert" heißt in dieser Phase immer: sha256 der Spalte `calendardata` und Objektname vor und nach dem Aufruf gleich (Datenbank), nicht der Statuscode.

## 8. Geheimnisse

- Env-Dateien (`.env.exapp`, `.env.nc35`) nur per `set -a && . <datei> && set +a` laden, nie lesen, zitieren, ausgeben oder mit `cat`/`grep` öffnen.
- Jede Ausgabe eines Live- oder Docker-Laufs zuerst in den Scratchpad, gegen alle nicht leeren Werte der Env-Dateien, deren erste 12 Zeichen und `AUTHORIZATION-APP-API` prüfen (`scan_for_secrets` des Spikes), erst dann ins Rohprotokoll. pytest-Ausgaben ohne Abschnitt "warnings summary". Token-Dateien liegen außerhalb des Repos.
- Nur die echte Version aus `appinfo/info.xml` an AppAPI senden, nie eine erfundene; die Version wird in Phase 33 nicht geändert.

## 9. Sprache

- Planungsdokumente, SUMMARYs und Rohprotokolle deutsch mit echten Umlauten (Schlüsselwörter der Protokollzeilen wie `RUECKBAU`, `entfaellt`, `MESSWERT` sind ASCII-Marker, keine Prosa).
- Code, Skripte, Werkzeugtexte, Fehlermeldungen, `appinfo/info.xml`, Formulartexte und englische Doku englisch und ASCII im Stil der vorhandenen Werkzeuge.
- Nutzersichtbare deutsche und französische Texte (README.de.md, README.fr.md, CHANGELOG.de.md, CHANGELOG.fr.md) mit echten Umlauten, ß und Akzenten.
- Nirgends U+2013 oder U+2014, keine Emojis.
- Pitfall 1 (33-RESEARCH.md): in Bezeichnern und Texten unter `src/` keine Großbuchstaben-Teilstrings `MOVE`, `DELETE`, `COPY`, `PROPPATCH` außer der einen benannten `MOVE`-Zeile in `move_todo`; Wörter wie `relocated`, `dropped`, `cleared` verwenden.

## 10. Abbruch und Owner-Frage

Anhalten, nichts committen, was den Befund verdeckt, und den Owner fragen, wenn:

- ein Messwert einer Owner-Entscheidung widerspricht (D-33-05, D-33-07, D-33-10, D-33-14; Auslöser stehen in 33-01c Task 4),
- ein Werkzeugschema nach der Titel- und Beschreibungsdiät über 1400 Bytes liegt (die Decke wird nie angehoben),
- das Budget aus dem Endstand eine Hausregel verletzen würde oder eine Zählstelle (`EXPECTED_PUT_CALLS`, `MOVE`-Zahl) anders als geplant ausfällt,
- BASELINE vorher und nachher nicht gleich ist oder ein Rückbau scheitert,
- ein Objekt, das unverändert bleiben soll, einen anderen sha256 hat,
- ein fremder Container das Docker-Gate dauerhaft blockiert,
- ein Gate nur durch Lockern einer Prüfung grün würde.

## 11. Abtrennbare Teile und Rückbau im Code

- Ein Werkzeugplan (33-06 `tasks_complete`, 33-07 `tasks_update`, 33-08 `tasks_move`) fällt nur per Owner-Entscheid heraus. Die Entscheidung steht als Zeile `DROP <plan> grund=owner datum=<YYYY-MM-DD>` in `.planning/phases/33-aufgaben-aendern/raw/33-drop.txt`; der Plan wird dann nicht ausgeführt und bekommt keine SUMMARY.
- Folgeregel für 33-09 und 33-10: fehlt `33-06-SUMMARY.md`, `33-07-SUMMARY.md` oder `33-08-SUMMARY.md`, gilt der Teil als per Owner-Entscheid entfallen, aber nur, wenn `raw/33-drop.txt` die passende DROP-Zeile trägt; fehlt die Zeile, anhalten und fragen (ein vergessener Plan ist kein Entscheid). Entfallene Werkzeuge erscheinen nirgends, auch nicht als Platzhalter.
- Rückbau, ausgeführt als eigener Schritt direkt nach dem letzten gebauten Werkzeugplan (vor 33-09), testgetrieben und mit eigenem Commit `refactor(33): remove the unused <teil> after owner decision`:
  - `tasks_move` entfallen: `move_todo` aus `nextcloud/clients/tasks.py` entfernen, `TASK_MOVE`, den Ausnahmezweig in `_violations`, den MOVE-AST-Pin und seine Gegenproben aus `tests/contract/test_no_destructive_calls.py` entfernen, die erwartete Gesamtzahl der MOVE-Aufrufe auf 1 (nur Chunk-Montage) zurück, den vulture-Eintrag von `move_todo` entfernen, Gate-Texte wieder "user-facing move and rename tools remain forbidden". Verify: `! grep -q "def move_todo" src/mcp_connector/nextcloud/clients/tasks.py && ! grep -q "TASK_MOVE" tests/contract/test_no_destructive_calls.py && test "$(grep -rc '"MOVE",' src | awk -F: '{s+=$2} END {print s}')" = 1` plus volle Gates.
  - `tasks_complete` UND `tasks_update` entfallen: `put_existing_todo` und `tools/ics_edit.py` samt `tests/unit/test_ics_edit.py` entfernen, sofern `tasks_move` sie nicht nutzt (er nutzt sie nicht), `EXPECTED_PUT_CALLS` auf 6 zurück, den Pin create-only gegen compare-and-swap für Aufgaben entfernen, vulture-Einträge entfernen. Verify: `grep -q "EXPECTED_PUT_CALLS = 6" tests/contract/test_no_destructive_calls.py && ! grep -q "def put_existing_todo" src/mcp_connector/nextcloud/clients/tasks.py` plus volle Gates.
  - Nur einer von `tasks_complete` oder `tasks_update` entfallen: kein Rückbau der Schreibschiene (der andere nutzt sie); nur dessen Einträge in OPTIONAL_TOOLS, MODIFY_TOOLS, SWITCHED_TOOLS, Allowlist und Klassen fehlen, weil sein Plan sie nie gesetzt hat.
  - Alle drei entfallen: zusätzlich Schalter-Kette aus 33-02 nur nach eigener Owner-Frage entfernen (D-33-02: der Schalter bleibt sonst, ab Werk aus, ohne Werkzeuge).
- Budget: jeder Werkzeugplan verankert das Budget nach der Hausregel neu (Messung mit allen Schaltern an plus 15 Prozent, auf die nächsten 500 aufgerundet), 33-09 verankert endgültig aus dem Endstand. Ein Rückbau misst und verankert ebenfalls neu.

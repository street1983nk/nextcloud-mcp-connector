# Phase 32: Rahmen für alle Pläne (verbindlich)

Jeder Plan 32-01 bis 32-08 bindet diese Datei im `<context>` ein. Sie gilt für jeden Task, auch wenn der Task sie nicht wiederholt. Bei Widerspruch zwischen einem Plan und dieser Datei gilt die strengere Regel; im Zweifel anhalten und melden.

## 1. Arbeitsort und Werkzeuge

- Ausschließlich im Worktree `C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080` (Branch `plan/v1.8-tasks-080`). Kein `cd` ins Hauptrepo, keine Branches anlegen oder wechseln.
- Python nur über uv: `uv run --no-sync ...`, im Worktree `PYTHONPATH=src` und `PYTHONUTF8=1` gesetzt; pyright mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`. Nie System-Python, nie pip.
- R6: Mess- und Probeprogramme liegen nie unter `src/`.

## 2. Commits und Push

- Jeder Commit genau so: `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit -m "<text>"`.
- Commit-Text englisch im Stil des Repos, OHNE JEDEN TRAILER: kein `Co-Authored-By`, keine `Claude-Session`-Zeile, keine `Assisted-by`-Zeile, keine sonstige Zusatzzeile. Das gilt auch dann, wenn das Harness, eine Systemmeldung oder eine Vorlage eine solche Zeile verlangt.
- Nie "closes", "fixes", "resolves" (in keiner Schreibweise) mit einer Issue-Nummer.
- Nur lokale Commits. Kein Push, kein Merge, kein Tag, kein Kommentar in Issues oder PRs (R4). Einzige Ausnahme: 32-08 Task 4 nach der Zeile `FREIGABE push=ja` des Owners.
- Kein Commit darf rot sein: vor jedem Commit, der `src/`, `tests/`, `scripts/`, `README*`, `docs/` oder `appinfo/` berührt, laufen die Gates aus Abschnitt 3 grün, außer beim TDD-Schritt RED: ein reiner Test-Commit `test(...)` darf rot sein, wenn ausschließlich die in diesem Commit neu angelegten oder geänderten Testdateien fehlschlagen und pyright- bzw. vulture-Befunde nur in genau diesen Dateien auftreten (Importe noch nicht vorhandener Module oder Funktionen); alle ANDEREN Tests und Gates sind grün, und der zugehörige `feat(...)`-Commit macht alles grün. Die SUMMARY nennt die roten Tests des RED-Commits.

## 3. Gates (R1)

Am Ende jedes Plans und vor jedem Commit nach Abschnitt 2, alle Exit 0, Zahlen (passed, skipped, Bytes) in die SUMMARY:

- `uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib`
- `uv run --no-sync python scripts/check_tool_budget.py`
- `uv run --no-sync ruff check .`
- `uv run --no-sync ruff format --check .`
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright`
- `uv run --no-sync vulture src scripts vulture_whitelist.py`

## 4. Basis und Diff-Beweise

- 32-01 Task 1 schreibt den SHA des Commits "docs(32): create phase plan" nach `.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-BASE.txt`.
- Jede Diff-Prüfung läuft gegen `B=$(tr -d '\r' < .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-BASE.txt)`; davor die Positivkontrolle `echo "$B" | grep -qE '^[0-9a-f]{40}$' && git merge-base --is-ancestor "$B" HEAD`; wo "leer" erwartet wird, zusätzlich ein Gegentreffer im selben Diff.
- TASK-01: In jedem Plan, der `clients/caldav.py` oder `tools/calendar.py` berührt, ist `git diff "$B" -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py` leer.

## 5. Docker

- Streng seriell: immer nur EINE Nextcloud-Instanz gleichzeitig.
- RAM-Gate vor jedem Start eines Containers: mindestens 4,0 GB freier Arbeitsspeicher des Hosts (`powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"`, Wert in KiB) und kein laufender eigener Nextcloud-, Datenbank- oder mcp_connector-Container einer anderen Topologie. Scheitert das Gate bei leerem Docker: `wsl -d docker-desktop sh -c "sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory"`, 75 s warten, einmal wiederholen; bleibt es rot, anhalten und melden.
- Fremde Container (zum Beispiel `gameworld-dev-*`) nie stoppen, nie löschen.
- nc35 (`nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc_app_mcp_connector`) und die Topologie nc-mcp-exapp (Nextcloud 32): nur `docker start`/`docker stop` bzw. `docker compose ... start/stop`, nie `down`, nie `down -v`. Nur Wegwerf-Instanzen (eigenes Projekt aus `compose.spike-tags.yml`) werden nach der Messung mit `down -v` abgebaut.
- Am Planende läuft keine eigene Instanz mehr.

## 6. Owner-Freigaben für Zustandsänderungen

- Zustandsänderungen auf nc35 und auf der 32er Strecke (Installation oder Entfernung der Tasks-App, Testkonten, Freigaben, Aufgabenlisten, Serien mit 2000 Aufgaben, unregister/register von Daemon oder ExApp) nur nach einer Owner-Freigabezeile im Rohprotokoll. Die gemeinsame Vorab-Freigabe steht in 32-02 Task 2 (`FREIGABE zustand=<option>`), sie gilt für 32-02, 32-07 und 32-08. Eigene Checkpoints: 32-01 Task 4 (unregister auf 32), 32-07 Task 2 (Neuregistrierung auf nc35), 32-08 Task 3 (Push).
- Wegwerf-Instanzen brauchen keine Freigabe.

## 7. Rückbau und Baseline

- Testobjekte werden über das Harness mit App-Passwort entfernt, jedes CalDAV-`DELETE` mit dem Kopf `X-NC-CalDAV-No-Trashbin: 1`; wo das nicht geht (Aufgabenliste, Freigabe), wird danach der Papierkorb des Kontos geleert und das belegt. Weg: im Papierkorb `remote.php/dav/calendars/<uid>/trashbin/` per PROPFIND die gelöschten Listen und Objekte ermitteln und jedes per DAV-`DELETE` endgültig entfernen; geht das nicht, Abbruch mit Meldung statt Ausweichen auf direkte Datenbankzugriffe. Gilt sinngemäß für die BASELINE-Prüfung im CI (32-05b).
- Baseline vor und nach jedem Live-Lauf je betroffenem Konto, gelesen im Container per PHP über die Datenbank: Anzahl Zeilen in `calendars`, in `calendarobjects` gesamt und in `calendarobjects` mit `deleted_at` nicht NULL, dazu `calendarsubscriptions` und die Freigaben in `dav_shares`. Zeile `BASELINE <instanz> konto=<uid> calendars=<n> objekte=<n> geloescht=<n> shares=<n>`; vorher und nachher müssen gleich sein.

## 8. Geheimnisse

- Env-Dateien (`.env.exapp`, `.env.nc35`) nur per `set -a && . <datei> && set +a` laden, nie lesen, zitieren oder ausgeben.
- Jede Ausgabe eines Live- oder Docker-Laufs zuerst ins Scratchpad (`C:/Users/Student/AppData/Local/Temp/claude/.../scratchpad/p32`), gegen alle nicht leeren Werte der Env-Dateien, deren erste 12 Zeichen und `AUTHORIZATION-APP-API` prüfen, erst dann ins Rohprotokoll. pytest-Ausgaben ohne Abschnitt "warnings summary". Token-Dateien liegen außerhalb des Repos.
- Nur die echte Version aus `appinfo/info.xml` an AppAPI senden, nie eine erfundene.

## 9. Sprache

- Planungsdokumente, SUMMARYs und Rohprotokolle deutsch mit echten Umlauten (Schlüsselwörter der Protokollzeilen wie `RUECKBAU`, `entfaellt` sind ASCII-Marker, keine Prosa).
- Code, Skripte, Werkzeugtexte, Fehlermeldungen und englische Doku englisch und ASCII im Stil der vorhandenen Werkzeuge.
- Nutzersichtbare deutsche und französische Texte (README.de.md, README.fr.md, CHANGELOG.de.md, CHANGELOG.fr.md, docs/*.de.md, docs/*.fr.md) mit echten Umlauten, ß und Akzenten.
- Nirgends U+2013 oder U+2014, keine Emojis.

# Phase 34: Rahmen für alle Pläne (verbindlich)

Jeder Plan (34-01 bis 34-10) bindet diese Datei im `<context>` ein. Sie gilt für jeden Task, auch wenn der Task sie nicht wiederholt. Bei Widerspruch zwischen einem Plan und dieser Datei gilt die strengere Regel; im Zweifel anhalten und den Owner fragen. Vorlage ist `.planning/phases/33-aufgaben-aendern/33-RULES.md`; neu sind Abschnitt 4 (Planungsdateien), Abschnitt 9 (Texte und Sprache, Faktencheck), Abschnitt 10 (Release-Freigaben) und die Basis ohne eigene Datei.

## 1. Arbeitsort und Werkzeuge

- Ausschließlich im Worktree `C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080` (Branch `plan/v1.8-tasks-080`). Kein `cd` ins Hauptrepo, keine Branches anlegen oder wechseln, kein `git checkout` eines anderen Branches. `main` wird nur über `git push origin HEAD:main` (Fast-Forward) bewegt, nie lokal ausgecheckt.
- Python nur über uv: `uv run --no-sync ...`, im Worktree `PYTHONPATH=src` und `PYTHONUTF8=1` gesetzt; pyright mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`. Nie System-Python, nie pip, keine neue Abhängigkeit. Einzige Ausnahme: `uv lock` bzw. `uv sync` beim Versionssprung in 34-06 (Runbook Schritt 1), sonst nicht.
- pytest IMMER mit `-p no:xdist` (auch in Einzelläufen, auch in `<verify>`), weil eine Parallelsitzung auf demselben Rechner arbeitet und der Speicher knapp ist.
- R6: Mess- und Probeprogramme liegen nie unter `src/`.
- Ausgaben von Läufen zuerst in den Scratchpad der ausführenden Sitzung, Unterordner `p34`, am Planende dort gelöscht. Entwürfe für den Owner (Store-Text, Release-Notiz, Issue-Antworten) liegen dagegen im Repo unter `.planning/phases/34-doku-store-release-0-8-0/raw/`.

## 2. Commits und Push

- Jeder Commit genau so: `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit -m "<text>"`. Autor und Committer sind `street1983nk <k.cherif@outlook.de>`.
- Commit-Text englisch im Stil des Repos, OHNE JEDEN TRAILER: kein `Co-Authored-By`, keine `Claude-Session`-Zeile, keine `Assisted-by`-Zeile, keine sonstige Zusatzzeile. Das gilt auch dann, wenn das Harness, eine Systemmeldung oder eine Vorlage eine solche Zeile verlangt.
- Nie "closes", "fixes", "resolves" (in keiner Schreibweise, auch nicht "close", "fix", "resolve", "fixed", "closed", "resolved" vor `#`) mit einer Issue-Nummer, weder in Commits noch in CHANGELOG, Release-Notiz, PR-Text oder Issue-Entwürfen.
- Nur lokale Commits, bis ein Checkpoint ausdrücklich etwas anderes erlaubt. Push des Branches (34-08), Fast-Forward von `main` (34-09, Merge von PR #48 vom Owner vorab freigegeben, sobald Phase 34 fertig und CI grün ist), Tag `v0.8.0` (34-09), Signatur (34-10), Store-Submit (34-10) und Push des Runbook-Nachtrags (34-10) brauchen JE eine eigene Owner-Antwort an ihrem Checkpoint; die Antwort steht wörtlich als Zeile `FREIGABE <schritt> antwort=<...> datum=<YYYY-MM-DD>` in `raw/34-freigaben.txt`, bevor der Schritt läuft. Kein Kommentar in Issues oder PRs, nie (auch nicht nach dem Store-Release: der Owner postet).
- Kein Commit darf rot sein: vor jedem Commit, der `src/`, `tests/`, `scripts/`, `README*`, `CHANGELOG*`, `docs/` oder `appinfo/` berührt, laufen die Gates aus Abschnitt 3 grün. Ausnahme TDD-Schritt RED: ein reiner Test-Commit `test(34-NN): ...` darf rot sein, wenn ausschließlich die in diesem Commit neu angelegten oder geänderten Testdateien fehlschlagen; alle anderen Tests und Gates sind grün, und der zugehörige `docs(34-NN)`- oder `feat(34-NN)`-Commit macht alles grün. Die SUMMARY nennt die roten Tests des RED-Commits.
- Gegenproben ("gepflanzter Fehler wird gemeldet") laufen über dieselbe Prüffunktion wie der echte Fall, aber nie über das Muster der Umsetzung (Hausregel "Gegenprobe nie mit dem Muster der Umsetzung").

## 3. Gates (R1)

Am Ende jedes Plans und vor jedem Commit nach Abschnitt 2, alle Exit 0, Zahlen (passed, skipped, Bytes) in die SUMMARY:

- `uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -p no:xdist -q --import-mode=importlib`
- `uv run --no-sync python scripts/check_tool_budget.py`
- `uv run --no-sync ruff check .`
- `uv run --no-sync ruff format --check .`
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright`
- `uv run --no-sync vulture src scripts vulture_whitelist.py`

Ab 34-06 zusätzlich der Runbook-Lauf `uv run --no-sync pytest -q -p no:xdist` (ganze Suite ohne Live-Umgebung; Live-Tests überspringen sich selbst). Budget (26000 Bytes) und Decke je Werkzeug (1400 Bytes) werden in Phase 34 nicht geändert; ändert sich eine Zahl, anhalten.

## 4. Basis, Planungsdateien und Diff-Beweise

- Basis ist der Commit "docs(34): create phase plan": `B=$(git log --format=%H --grep='^docs(34): create phase plan$' -1)`; davor die Positivkontrolle `echo "$B" | grep -qE '^[0-9a-f]{40}$' && git merge-base --is-ancestor "$B" HEAD`.
- Produktcode bleibt in Phase 34 unberührt bis auf zwei benannte Stellen: die Server-Instruktion in `src/mcp_connector/server/__init__.py` (34-01, DOC-05) und `__version__` in `src/mcp_connector/__init__.py` (34-06). Am Ende jedes Plans: `git diff --stat "$B" -- src/ | grep -v -E 'server/__init__.py|mcp_connector/__init__.py|files? changed'` ist leer; Gegentreffer im selben Diff ab 34-01 (`server/__init__.py` erscheint).
- Werkzeugschnitt, Schemas, Annotationen und Audit-Allowlist werden nicht geändert. Der Audit-Grund `unspecified` bei veralteter ETag (33-10-SUMMARY) wird in Phase 34 NICHT im Code behoben, sondern als ehrliche Grenze dokumentiert (34-04); wer ihn beheben will, braucht einen eigenen Owner-Entscheid.
- Planungsdateien: KEIN `gsd-sdk`-Befehl, der `.planning/STATE.md`, `.planning/ROADMAP.md` oder `.planning/REQUIREMENTS.md` schreibt oder umschreibt (kein `state.*`-Schreiben, kein `roadmap.*`-Update, kein `requirements.mark-complete`, kein `phase.complete`). Diese drei Dateien pflegt die Hauptsitzung. `.planning/PROJECT.md` ändert nur 34-04, von Hand und nur an den Stellen des Inventars (DOC-05). `CLAUDE.md` wird nie geändert.

## 5. Docker, Speicher und die Parallelsitzung (nur 34-07)

- Streng seriell: immer nur EINE Nextcloud-Instanz gleichzeitig.
- Vor JEDEM Docker-Block zuerst `docker ps --format '{{.Names}}'`. Eigene Namen sind nur `nc35-*`, `nc_app_mcp_connector`, `nc-mcp-exapp-*`. Läuft irgendein anderer Container (insbesondere `avs-*`): nicht starten. Dreimal je 5 Minuten warten (Monitor, kein `sleep` im Vordergrund) und erneut prüfen; läuft er dann noch, anhalten und den Owner fragen. Fremde Container nie stoppen, nie löschen, nie `exec`, nie `logs`.
- RAM-Gate vor jedem Start: mindestens 4194304 KiB frei (`powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"`). Scheitert es bei leerem Docker: `wsl -d docker-desktop sh -c "sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory"`, 75 s warten (Monitor), einmal wiederholen; bleibt es rot, anhalten und melden.
- nc35 nur `docker start`/`docker stop`, nie `down`, nie `rm`. Am Planende läuft keine eigene Instanz mehr (Zeile ins Protokoll).
- `bootstrap_exapp.sh --nc35` braucht `HP_SHARED_KEY` aus dem laufenden `nc35-harp` (nicht ausgeben). Ein Admin-Schalter der ExApp wird mit `occ app_api:app:config:set ... --update-only` geändert (ohne `--update-only` bleibt ein vorhandener Schlüssel unverändert, 33-10), danach App aus- und einschalten, Wirkung über die Werkzeugzahl prüfen.

## 6. Geheimnisse

- Env-Dateien (`.env.exapp`, `.env.nc35`) nur per `set -a && . <datei> && set +a` laden, nie lesen, zitieren, ausgeben oder mit `cat`/`grep` öffnen.
- Jede Ausgabe eines Live-, Docker- oder Release-Laufs zuerst in den Scratchpad, gegen alle nicht leeren Werte der Env-Dateien, deren erste 12 Zeichen und `AUTHORIZATION-APP-API` prüfen, erst dann ins Rohprotokoll. pytest-Ausgaben ohne Abschnitt "warnings summary".
- Der Signaturschlüssel `~/.nextcloud/certificates/mcp_connector.key` wird nur als Pfad an `openssl` übergeben, nie gelesen, kopiert oder ausgegeben. Ein Store-Token wird nie in eine Datei, einen Commit oder ein Protokoll geschrieben.

## 7. Store-Texte und Pin

- Die sechs Store-Texte (`summary` und `description` in EN/DE/FR, direkte Kinder von `info`) ändern sich nur nach Owner-Freigabe des Entwurfs (EXAPP-13, E11). Erst nach der Freigabe wird der SHA-256-Pin in `tests/unit/test_store_texts_frozen.py` erneuert (`FROZEN_AT = "release 0.8.0"`, neuer `EXPECTED_SHA256`, neu berechnet mit `_store_texts`).
- Die Gates der Beschreibung in `tests/unit/test_exapp_env_setup.py` gelten weiter (kein Backtick, keine Tabelle, kein Bild, keine Linie, kein HTML, mindestens zwei Absätze je Sprache, `summary` unter 128 Zeichen, verbotenes Vokabular). Keine Ordnernamen von Mail in der Beschreibung.

## 8. Fakten statt Gedächtnis

- Jede Zahl und jeder Name in einem Text kommt aus der laufenden Registry oder dem Code, nie aus einer älteren SUMMARY: Werkzeugzahl im Standard (27) und mit allen Schaltern (31) über `scripts/check_tool_budget.py`, Familien (zehn) und Bundle-Namen aus `NC_MCP_DISABLED_TOOLS`-Code, Stufen aus den Annotationen. Ein Text, der eine andere Werkzeugzahl nennt, verweist auf `tests/contract/test_tool_surface.py` (Test IN-04).
- Was in Phase 30 bis 33 ungemessen blieb (zum Beispiel ein nur lesbarer externer Speicher beim Ordner-Anlegen, Unteraufgaben in fremden Listen), steht als ehrliche Grenze mit Link auf `docs/folder-evidence.md`, `docs/tasks-evidence.md` oder `docs/spike-tasks.md`, nie als Zusage.

## 9. Texte und Sprache

- Planungsdokumente, SUMMARYs und Rohprotokolle deutsch mit echten Umlauten (Schlüsselwörter der Protokollzeilen wie `ERLEDIGT`, `FREIGABE`, `BELEG` sind ASCII-Marker, keine Prosa).
- Code, Werkzeugtexte, Server-Instruktion, `appinfo/info.xml` außerhalb der DE/FR-Store-Texte, englische Doku und die GitHub-Release-Notiz englisch und ASCII im Stil des Repos.
- Nutzersichtbare deutsche und französische Texte (README.de.md, README.fr.md, CHANGELOG.de.md, CHANGELOG.fr.md, docs/*.de.md, docs/*.fr.md, Store-Texte DE/FR) mit echten Umlauten, ß und Akzenten, sauberem Französisch (Leerzeichen vor `:` `;` `?` `!` wie im vorhandenen Text, einheitliche Apostrophe je Datei). Deutsch: "das ETag" (neutrum: das ETag, des ETags, dem ETag), nie "die ETag" oder "der ETag" in nutzersichtbaren Texten.
- Nirgends U+2013 oder U+2014, keine Emojis.
- Umlaut-Audit vor jeder Abnahme: in jeder geänderten DE-Datei jede Fundstelle von `ae`, `oe`, `ue`, `ss` in hinzugefügten Zeilen gelesen und als echt (zum Beispiel "Quelle", "neue", "aktuell") oder Fehler eingestuft; Ergebnis als Zeile `UMLAUT <datei> geprueft=<n> fehler=0` in die SUMMARY.
- Kurze Produkttexte als Faktenliste (R3). Sprache der Issue-Antworten: kurz, menschlich, ohne Schließwörter.
- Pitfall 1 (33-RESEARCH.md) gilt weiter: in Texten unter `src/` keine Großbuchstaben-Teilstrings `MOVE`, `DELETE`, `COPY`, `PROPPATCH` (die Server-Instruktion sagt "moved", "deleted" klein).

## 10. Release-Reihenfolge (Runbook `docs/store-submission.md`)

- Schritte 1 bis 3 (Version, Changelog, Gates) in 34-06; Volltest in 34-07; Push des Branches nach Owner-Frage in 34-08; CI des PR #48 grün einschließlich `canary-nc35`; Fast-Forward `main` und Tag nach Owner-Frage in 34-09; Workflow `release` grün; Signatur über das HERUNTERGELADENE Asset und Submit je nach Owner-Frage in 34-10; Schritt 8 (fünf Nachweise) und Nachweiszeilen in 34-10.
- Nie ein Release-Asset löschen, nie einen Tag umschreiben. Eine Korrektur nach dem Tag braucht eine neue Patch-Version und einen Owner-Entscheid.
- Issue-Antworten in #32 und #44 liegen nur als Entwurf vor; gepostet wird nichts vor dem Store-Release, und auch danach postet der Owner selbst.

## 11. Abbruch und Owner-Frage

Anhalten, nichts committen, was den Befund verdeckt, und den Owner fragen, wenn:

- ein Text nur durch Lockern eines Tests wahr würde oder ein Gate nur durch Lockern einer Prüfung grün würde,
- Registry und eine bisherige Zusage nicht zusammenpassen (zum Beispiel ein Werkzeug ändert etwas, das kein Text nennt),
- `main` auf GitHub Commits trägt, die nicht im Branch sind (dann ist der Fast-Forward unmöglich; kein Merge-Commit, kein Rebase ohne Frage),
- ein CI-Job rot ist, insbesondere `canary-nc35`, oder der `release`-Workflow rot ist,
- die Signatur des heruntergeladenen Assets nicht `Verified OK` ergibt oder der Store nicht 201 antwortet,
- ein fremder Container das Docker-Gate dauerhaft blockiert.

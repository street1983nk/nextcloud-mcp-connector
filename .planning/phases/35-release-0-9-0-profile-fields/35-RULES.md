# Phase 35: Rahmen für alle Pläne (verbindlich)

Jeder Plan (35-01 bis 35-09) bindet diese Datei im `<context>` ein. Sie gilt für jeden Task, auch wenn der Task sie nicht wiederholt. Bei Widerspruch zwischen einem Plan und dieser Datei gilt die strengere Regel; im Zweifel anhalten und den Owner fragen. Vorlage ist `.planning/phases/34-doku-store-release-0-8-0/34-RULES.md` (alle Regeln übernommen); neu sind die Worktree-Anlage (Abschnitt 1), die Owner-Frage auch für den Fast-Forward von `main` (Abschnitt 2), zwei Instanzen NC34 und NC35 (Abschnitt 5), die Profile-Fields-Fakten (Abschnitt 8) und der Sicherheitsabschluss (Abschnitt 12).

## 1. Arbeitsort und Werkzeuge

- Ausschließlich im Worktree `C:/Users/Student/nextcloud-mcp-connector-worktrees/release-090` (Branch `plan/release-090`). Er wird genau einmal in 35-01 Task 1 angelegt, vom lokalen `main` NACH dem Commit "docs(35): create phase plan": `git -C C:/Users/Student/nextcloud-mcp-connector worktree add -b plan/release-090 C:/Users/Student/nextcloud-mcp-connector-worktrees/release-090 main`. Das ist die einzige erlaubte Branch-Anlage der Phase. Danach kein `cd` ins Hauptrepo, keine weiteren Branches, kein `git checkout` eines anderen Branches, keine Arbeit in den anderen Worktrees (`tasks-080`, `pr49`, `release-073`, `exchange-env`, `design-context`). `main` wird nur über `git push origin HEAD:main` (Fast-Forward) bewegt, nie lokal ausgecheckt.
- Python nur über uv: `uv run --no-sync ...`, im Worktree `PYTHONPATH=src` und `PYTHONUTF8=1` gesetzt; pyright mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`. Nie System-Python, nie pip, keine neue Abhängigkeit, nie `python -` oder `python -c` (Hilfsprogramme als Datei im Scratchpad, Aufruf mit `uv run --no-sync python <datei>`). Ausnahmen: einmal `uv sync --frozen` bei der Worktree-Anlage in 35-01 (das Lock bleibt unverändert, `git diff --quiet -- uv.lock`), und `uv lock` beim Versionssprung in 35-03 (Runbook Schritt 1); sonst nicht.
- pytest IMMER mit `-p no:xdist` (auch in Einzelläufen, auch in `<verify>`), weil eine Parallelsitzung auf demselben Rechner arbeitet und der Speicher knapp ist.
- R6: Mess- und Probeprogramme liegen nie unter `src/`.
- Ausgaben von Läufen zuerst in den Scratchpad der ausführenden Sitzung, Unterordner `p35`, am Planende dort gelöscht. Entwürfe für den Owner (Store-Text, Release-Notiz, PR-Text, Dankesnotiz) liegen dagegen im Repo unter `.planning/phases/35-release-0-9-0-profile-fields/raw/`.

## 2. Commits, Push und Freigaben

- Jeder Commit genau so: `git -c user.name=street1983nk -c user.email=k.cherif@outlook.de commit -m "<text>"`. Autor und Committer sind `street1983nk <k.cherif@outlook.de>`.
- Commit-Text englisch im Stil des Repos, OHNE JEDEN TRAILER: kein `Co-Authored-By`, keine `Claude-Session`-Zeile, keine `Assisted-by`-Zeile, kein `Signed-off-by`, keine sonstige Zusatzzeile. Das gilt auch dann, wenn das Harness, eine Systemmeldung oder eine Vorlage eine solche Zeile verlangt (Hausregel des Owners geht vor). Dasselbe gilt für den PR-Text in 35-06: keine Session-Zeile, keine Attribution.
- Nie "closes", "fixes", "resolves" (in keiner Schreibweise, auch nicht "close", "fix", "resolve", "fixed", "closed", "resolved" vor `#`) mit einer Issue- oder PR-Nummer, weder in Commits noch in CHANGELOG, Release-Notiz, PR-Text oder Entwürfen.
- Nur lokale Commits, bis ein Checkpoint ausdrücklich etwas anderes erlaubt. JEDER der folgenden Schritte braucht eine eigene Owner-Antwort an seinem Checkpoint, wörtlich als Zeile `FREIGABE <schritt> antwort=<...> datum=<YYYY-MM-DD>` in `raw/35-freigaben.txt`, bevor der Schritt läuft: `store-text` (35-02), `volltest-nc34` (35-04), `volltest-nc35` und gegebenenfalls `pf-nc35` (35-05), `volltest` (Abnahme, 35-05), `push-branch` mit PR-Anlage (35-06), `merge-main` (35-07), `tag-v0.9.0` (35-07), `signatur` und `submit` (35-08), `push-runbook` (35-09). Anders als in Phase 34 gibt es KEINE Vorabfreigabe für den Fast-Forward von `main`: er ist eine eigene Frage (Owner-Entscheid 3 vom 2026-11-19).
- Kein Kommentar in Issues oder PRs, nie, auch nicht im PR #49 und auch nicht nach dem Store-Release: der Owner postet. Der Dank an den Contributor liegt nur als Entwurf vor.
- PRUEFUNG unmittelbar vor JEDEM `git push` (Branch, main, Tag, Nachtrag): im Bereich `<ziel>..HEAD` `git log --format='%an <%ae>|%cn <%ce>'` nur `street1983nk <k.cherif@outlook.de>`; `git log --format=%B` ohne Trailer-Zeilen (`Co-Authored-By`, `Claude-Session`, `Assisted-by`, `Signed-off-by`) und ohne Schließwort vor `#` (`grep -inE '(close[sd]?|fix(e[sd])?|resolve[sd]?) +#[0-9]'`). Ergebnis als Zeile `PRUEFUNG vor=<schritt> bereich=<a..b> commits=<n> autor_committer_fremd=0 trailer=0 closes_woerter=0` ins Protokoll des Plans; jede Abweichung heißt: kein Push, anhalten. Der Squash-Commit 66ffa30d des PR #49 (Autor Vitor Mattos, mit Signed-off-by-Zeilen) liegt bereits auf `origin/main` und damit außerhalb jedes Prüfbereichs; taucht er doch im Bereich auf, ist der Bereich falsch gewählt: anhalten.
- Kein Commit darf rot sein: vor jedem Commit, der `src/`, `tests/`, `scripts/`, `README*`, `CHANGELOG*`, `docs/` oder `appinfo/` berührt, laufen die Gates aus Abschnitt 3 grün. Ausnahme TDD-Schritt RED wie in 34-RULES (reiner Test-Commit `test(35-NN): ...`, nur die neuen oder geänderten Testdateien rot, die SUMMARY nennt sie).
- Gegenproben ("gepflanzter Fehler wird gemeldet") laufen über dieselbe Prüffunktion wie der echte Fall, aber nie über das Muster der Umsetzung (Hausregel "Gegenprobe nie mit dem Muster der Umsetzung").

## 3. Gates (R1)

Am Ende jedes Plans und vor jedem Commit nach Abschnitt 2, alle Exit 0, Zahlen (passed, skipped, Bytes) in die SUMMARY:

- `uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -p no:xdist -q --import-mode=importlib`
- `uv run --no-sync python scripts/check_tool_budget.py`
- `uv run --no-sync ruff check .`
- `uv run --no-sync ruff format --check .`
- `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright`
- `uv run --no-sync vulture src scripts vulture_whitelist.py`

Ab 35-03 zusätzlich der Runbook-Lauf `uv run --no-sync pytest -q -p no:xdist` (ganze Suite ohne Live-Umgebung; Live-Tests überspringen sich selbst). Budget (26000 Bytes) und Decke je Werkzeug (1400 Bytes) werden in Phase 35 nicht geändert. Stand 2026-11-18 laut Kommentar in `scripts/check_tool_budget.py`: 27 Werkzeuge im Standard mit 18770 Bytes, 32 mit allen drei Schaltern mit 23109 Bytes, `profile_fields_browse` 911 Bytes. Ändert sich eine dieser Zahlen, anhalten.

## 4. Basis, Planungsdateien und Diff-Beweise

- Basis ist der Commit "docs(35): create phase plan": `B=$(git log --format=%H --grep='^docs(35): create phase plan$' -1)`; davor die Positivkontrolle `echo "$B" | grep -qE '^[0-9a-f]{40}$' && git merge-base --is-ancestor "$B" HEAD`.
- Produktcode bleibt in Phase 35 unberührt bis auf drei benannte Stellen: `__version__` in `src/mcp_connector/__init__.py` (35-03) und reine Kommentar- bzw. Docstring-Korrekturen ("seven fields/values") in `src/mcp_connector/exapp/admin_settings.py` und `src/mcp_connector/exapp/config_values.py` (35-01, AST-gleich ohne Docstrings, belegt mit einem Prüfprogramm im Scratchpad). Am Ende jedes Plans: `git diff --stat "$B" -- src/ | grep -v -E 'mcp_connector/__init__.py|exapp/admin_settings.py|exapp/config_values.py|files? changed'` ist leer.
- Werkzeugschnitt, Schemas, Werkzeugtexte, Annotationen, Admin-Formular-Texte (`src/mcp_connector/exapp/ui/strings.py`), Schalterlogik und Audit-Allowlist werden nicht geändert. Ein Fehler dort (auch ein Sprachfehler) heißt: anhalten, Owner fragen; eine Korrektur wäre ein eigener Entscheid mit eigenem Livebeweis.
- Planungsdateien: KEIN `gsd-sdk`-Befehl, der `.planning/STATE.md`, `.planning/ROADMAP.md` oder `.planning/REQUIREMENTS.md` schreibt oder umschreibt (kein `state.*`-Schreiben, kein `roadmap.*`-Update, kein `requirements.mark-complete`, kein `phase.complete`). Diese Dateien pflegt die Hauptsitzung; die Schritte `state.advance-plan`, `roadmap.update-plan-progress` und `requirements.mark-complete` aus execute-plan.md werden in jedem Plan übersprungen. `.planning/PROJECT.md` und `CLAUDE.md` werden nicht geändert.
- Zeilenenden: `README*.md`, `CHANGELOG*.md`, `appinfo/info.xml` und `pyproject.toml` sind CRLF. Änderungen byte-genau mit erhaltenen Zeilenenden; `git diff --numstat` zeigt nur die geänderten Zeilen, nie eine Umschreibung der ganzen Datei.

## 5. Docker, Speicher und die Parallelsitzung (nur 35-04 und 35-05)

- Streng seriell: immer nur EINE Nextcloud-Instanz gleichzeitig. NC34 ist der Stapel `nc-mcp-exapp` (`compose.exapp.yml`, Container `nc-mcp-exapp-caddy`, `-nc`, `-harp`, `-greenmail`, `-registry`, NC 34.0.3, ExApp heute Build 4e68000a, Admin-Sprache en, firstrunwizard aus, Profile Fields 4.0.0 aus dem Store installiert). NC35 ist der Stapel `nc35-*` (`compose.nc35.yml`). Bevor ein Stapel startet, läuft kein Container des anderen (`docker ps` zeigt weder `nc-mcp-exapp-*` noch `nc35-*` noch `nc_app_mcp_connector`).
- Vor JEDEM Docker-Block zuerst `docker ps --format '{{.Names}}'`. Eigene Namen sind nur `nc-mcp-exapp-*`, `nc35-*` und `nc_app_mcp_connector`. Läuft irgendein anderer Container (insbesondere `avs-*`): nicht starten. Dreimal je 5 Minuten warten (Monitor, kein `sleep` im Vordergrund) und erneut prüfen; läuft er dann noch, anhalten und den Owner fragen. Fremde Container nie stoppen, nie löschen, nie `exec`, nie `logs`.
- RAM-Gate vor jedem Start: mindestens 4194304 KiB frei (`powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"`). Scheitert es bei leerem Docker: `wsl -d docker-desktop sh -c "sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory"`, 75 s warten (Monitor), einmal wiederholen; bleibt es rot, anhalten und melden.
- NC34 starten nur mit `NC_EXAPP_NEXTCLOUD_IMAGE=nextcloud:34.0.3-apache docker compose -f compose.exapp.yml up -d --wait`, stoppen nur mit `docker compose -f compose.exapp.yml stop`. Nie `down`, nie `down -v`, nie `docker volume rm`. NC35 nur `docker start`/`docker stop`, nie `down`, nie `rm`. Am Planende läuft keine eigene Instanz mehr (Zeile `DOCKER ende eigene=0` ins Protokoll).
- Der ExApp-Container heißt in beiden Topologien `nc_app_mcp_connector`. Vor jeder Neuregistrierung `docker inspect nc_app_mcp_connector --format '{{json .NetworkSettings.Networks}}'` und das Image protokollieren (Zeile `EXAPP-CONTAINER netz=<...> image=<...>`), das alte Image als Rückweg taggen (`127.0.0.1:5000/mcp_connector:<alt>-vor35`, gegebenenfalls Registry des jeweiligen Stapels). Meldet `bootstrap_exapp.sh` einen Namenskonflikt oder gehört der Container zum anderen Stapel und lässt er sich nicht über `occ app_api:app:unregister mcp_connector` (ohne `--rm-data`) der eigenen Instanz lösen: anhalten, Owner fragen, nichts per `docker rm` erzwingen.
- `bootstrap_exapp.sh --nc35` braucht `HP_SHARED_KEY` aus dem laufenden `nc35-harp` (nicht ausgeben). Ein Admin-Schalter der ExApp wird mit `occ app_api:app:config:set ... --update-only` geändert (fehlt der Schlüssel nach einer Neuregistrierung, einmal ohne `--update-only` anlegen und das protokollieren, wie in 34-07), danach App aus- und einschalten, Wirkung über die Werkzeugzahl prüfen.
- Sprachumstellungen des Admin-Kontos für die Sichtprüfung (`occ user:setting admin core lang <de|fr>`) werden am Ende auf `en` zurückgestellt; firstrunwizard bleibt aus. Zeile `ADMIN-SPRACHE ende=en` ins Protokoll.

## 6. Geheimnisse

- Env-Dateien (`.env.exapp`, `.env.nc35`, `.env.test`) nur per `set -a && . <datei> && set +a` laden, nie lesen, zitieren, ausgeben, kopieren oder mit `cat`/`grep` öffnen. Variablennamen aus den `*.example`-Dateien oder, nach dem Laden, nur die NAMEN per `compgen -v | grep '^NC_'` (nie Werte, nie `env`/`set` ohne Filter). Braucht ein Programm andere Namen (zum Beispiel `NC_MCP_USER` statt `NC_MCP_TEST_USER`), wird in derselben Shell umgelegt (`export NC_MCP_USER="$NC_MCP_TEST_USER"`), ohne Ausgabe. `bootstrap_exapp.sh` schreibt die Datei in den Worktree; fehlt sie dort, wird sie aus dem Hauptrepo nur per absolutem Pfad geladen, nie kopiert. `HP_SHARED_KEY` liest `bootstrap_exapp.sh` selbst aus dem laufenden HaRP-Container; er wird nie ausgegeben.
- OAuth-Token-Dateien (`tasks_chain_evidence.py connect --token-file`) liegen nur im Scratchpad p35 und werden am Planende gelöscht (Zeile `TOKENDATEIEN geloescht=ja`).
- Jede Ausgabe eines Live-, Docker- oder Release-Laufs zuerst in den Scratchpad, gegen alle nicht leeren Werte der Env-Dateien, deren erste 12 Zeichen und `AUTHORIZATION-APP-API` prüfen, erst dann ins Rohprotokoll. pytest-Ausgaben ohne Abschnitt "warnings summary". Zufallspasswörter des Live-Tests (eigener Admin) gehen nie ins Protokoll.
- Profilwerte der Testkonten sind Testdaten, gehen aber nur als Zählung oder als Zufallsmarker ins Protokoll, nie als Klartext eines echten Feldes.
- Der Signaturschlüssel `~/.nextcloud/certificates/mcp_connector.key` wird nur als Pfad an `openssl` übergeben, nie gelesen, kopiert oder ausgegeben. Ein Store-Token wird nie in eine Datei, einen Commit oder ein Protokoll geschrieben.

## 7. Store-Texte und Pin

- Die sechs Store-Texte (`summary` und `description` in EN/DE/FR, direkte Kinder von `info`) ändern sich nur nach Owner-Freigabe des Entwurfs (35-02). Inhalt laut Owner-Entscheid 2: die Zeile "New in 0.8.0" / "Neu in 0.8.0" / "Nouveau en 0.8.0" wird ERSETZT durch eine Zeile "New in 0.9.0" zu Profile Fields (Felder der App Profile Fields lesen, nur lesend, ab Werk aus, der Admin schaltet es ein; Rechte-Aussage gegen den Code geprüft); Ordner anlegen und Aufgaben suchen, lesen, anlegen wandern in die normale Werkzeug- bzw. Fähigkeitenliste, damit nichts verloren geht.
- Erst nach der Freigabe wird der SHA-256-Pin in `tests/unit/test_store_texts_frozen.py` erneuert (`FROZEN_AT = "release 0.9.0"`, neuer `EXPECTED_SHA256`, neu berechnet mit `_store_texts`, Docstring um einen Satz mit dem Freigabedatum ergänzt).
- Die Gates der Beschreibung in `tests/unit/test_exapp_env_setup.py` gelten weiter (kein Backtick, keine Tabelle, kein Bild, keine Linie, kein HTML, mindestens zwei Absätze je Sprache, `summary` unter 128 Zeichen, verbotenes Vokabular). Keine Ordnernamen von Mail in der Beschreibung. Der Löschgrenzen-Test der Aufgaben in `tests/contract/test_write_promise_truth.py` bleibt unverändert grün; ein Entwurf, der ihn rot macht, ist falsch, nicht der Test.

## 8. Fakten statt Gedächtnis

- Jede Zahl und jeder Name in einem Text kommt aus der laufenden Registry oder dem Code, nie aus einer älteren SUMMARY oder dieser Datei: Werkzeugzahl im Standard (27), mit Profile Fields (28), mit den optionalen Schreibwerkzeugen (31) und mit allen drei Schaltern (32) über `scripts/check_tool_budget.py` und `tests/contract/test_tool_surface.py` (Test IN-04). Ein Text, der eine andere Werkzeugzahl nennt, verweist auf diesen Test.
- Profile Fields (Code `src/mcp_connector/tools/profile_fields.py`, `src/mcp_connector/server/opt_profile_fields.py`): ein Werkzeug `profile_fields_browse`, Annotation READ_ONLY, nur OCS-GET mit den Rechten des verbundenen Kontos, keine erhöhten Rechte. Ebene `me` liest die eigenen Werte; `definitions`, `values` und `search` nutzen Routen, die die App Profile Fields Administratoren vorbehält (die App prüft das selbst). Schalter `NC_MCP_PROFILE_FIELDS_READ`, ab Werk aus, ungültiger Wert lässt ihn aus. Das Audit-Log schreibt für dieses Werkzeug nur `level`, `limit`, `offset`. Die Suche (`unified_search`, `search`, `prepare_context`) erreicht den Suchanbieter der App mit und ohne Schalter und folgt den Rechten der App. Diese Aussagen werden vor jedem Text gegen den Code geprüft, nicht abgeschrieben.
- Admin-Formular (Quick 261118-ryx): zehn Felder, davon fünf Schalter; Ort EN "Administration settings, Security, MCP Connector", DE "Administrationseinstellungen, Sicherheit, MCP Connector", FR "Paramètres d'administration, Sécurité, MCP Connector" (gehalten von `tests/unit/test_docs_admin_form_truth.py`).
- Profile Fields auf Nextcloud 35: der Store führt für 35 nur einen Nightly der App (CHANGELOG [Unreleased]). Was dort ungemessen bleibt, steht als ehrliche Grenze, nie als Zusage.
- Contributor: PR #49 stammt von Vitor Mattos (GitHub `vitormattos`); er wird im CHANGELOG und in der Release-Notiz als Autor genannt (Name im Text, kein Trailer).

## 9. Texte und Sprache

- Planungsdokumente, SUMMARYs und Rohprotokolle deutsch mit echten Umlauten (Schlüsselwörter der Protokollzeilen wie `ERLEDIGT`, `FREIGABE`, `FAKT`, `VOLLTEST` sind ASCII-Marker, keine Prosa).
- Code, Werkzeugtexte, `appinfo/info.xml` außerhalb der DE/FR-Store-Texte, englische Doku, PR-Text und die GitHub-Release-Notiz englisch und ASCII im Stil des Repos; die Release-Notiz als englische Faktenliste (Hausregel).
- Nutzersichtbare deutsche und französische Texte (README.de.md, README.fr.md, CHANGELOG.de.md, CHANGELOG.fr.md, docs/*.de.md, docs/*.fr.md, Store-Texte DE/FR) mit echten Umlauten, ß und Akzenten, sauberem Französisch (Leerzeichen vor `:` `;` `?` `!` wie im vorhandenen Text, einheitliche Apostrophe je Datei). Deutsch: "das ETag"; Nextcloud-Begriff "Administrationseinstellungen".
- Nirgends U+2013 oder U+2014, keine Emojis. Dash-Prüfung immer mit UTF-8-Locale: `LC_ALL=C.UTF-8 grep -nP '[\x{2013}\x{2014}]' <dateien>; test $? -eq 1`, davor die Positivkontrolle mit gepflanztem Strich: `P=$(mktemp) && printf 'x\342\200\224x\n' > "$P" && LC_ALL=C.UTF-8 grep -qP '[\x{2013}\x{2014}]' "$P" && rm -f "$P"` (muss Exit 0 geben).
- Umlaut-Audit vor jeder Abnahme: in jeder geänderten DE-Datei jede Fundstelle von `ae`, `oe`, `ue`, `ss` in hinzugefügten Zeilen gelesen und als echt oder Fehler eingestuft; Ergebnis als Zeile `UMLAUT <datei> geprueft=<n> fehler=0`; für FR `FRANZ <datei> geprueft=<n> fehler=0`.
- Sprachfehler in DE/EN/FR sind vor einem Store-Release ein No-Go (Hausregel).
- Pitfall 1 (33-RESEARCH.md) gilt weiter: in Texten unter `src/` keine Großbuchstaben-Teilstrings `MOVE`, `DELETE`, `COPY`, `PROPPATCH`.

## 10. Release-Reihenfolge (Runbook `docs/store-submission.md`)

- Faktencheck und Doku in 35-01; Store-Text in 35-02; Runbook-Schritte 1 bis 3 (Version, Changelog, Gates) und Entwürfe (Release-Notiz, PR-Text, Dank an den Contributor) in 35-03; Volltest NC34 in 35-04; Volltest NC35, Sprachdurchsicht und Owner-Abnahme in 35-05; Sicherheitsabschluss, Push des Branches, PR und CI grün einschließlich `canary-nc35` und des Profile-Fields-Livebeweises in 35-06; Fast-Forward von `main` und Tag in 35-07 (je eigene Owner-Frage); Signatur über das HERUNTERGELADENE Asset und Submit in 35-08 (je eigene Owner-Frage); Schritt 8 (Nachweise), Runbook-Zeilen, Nachtrag im Sicherheitsvertrag und Push des Nachtrags in 35-09.
- Nie ein Release-Asset löschen, nie einen Tag umschreiben. Eine Korrektur nach dem Tag braucht eine neue Patch-Version und einen Owner-Entscheid.

## 11. Abbruch und Owner-Frage

Anhalten, nichts committen, was den Befund verdeckt, und den Owner fragen, wenn:

- ein Text nur durch Lockern eines Tests wahr würde oder ein Gate nur durch Lockern einer Prüfung grün würde,
- Registry und eine bisherige Zusage nicht zusammenpassen (andere Werkzeugzahl als 27/28/31/32, ein Werkzeug ändert etwas, das kein Text nennt),
- die Rechteprüfung ein Leck zeigt (ein Konto ohne Adminrechte sieht einen fremden oder privaten Profilwert, über das Werkzeug oder über die Suche): Sicherheitsbefund, sofort Stopp mit Beleg an den Owner, kein Release,
- Profile Fields auf NC35 nicht installierbar ist (Entscheid am Checkpoint in 35-05),
- `main` auf GitHub Commits trägt, die nicht im Branch sind (Fast-Forward unmöglich; kein Merge-Commit, kein Rebase ohne Frage),
- ein CI-Job rot ist, insbesondere `canary-nc35` oder der Profile-Fields-Schritt im Job `integration`, oder der `release`-Workflow rot ist,
- die Signatur des heruntergeladenen Assets nicht `Verified OK` ergibt oder der Store nicht 201 bzw. 200 antwortet,
- ein fremder Container das Docker-Gate dauerhaft blockiert,
- `35-SECURITY.md` einen offenen Threat (`threats_open` größer 0) trägt.

## 12. Sicherheitsabschluss (Hausregel "Security hat höchste Prio")

- Jeder Plan trägt ein `<threat_model>`. 35-06 schreibt vor dem Push `35-SECURITY.md` im Format der früheren Phasen (Frontmatter `phase`, `slug`, `status`, `threats_open`, `asvs_level: 1`, `block_on: high`, `register_authored_at_plan_time: true`, `created`, `audited_head`) aus den Registern von 35-01 bis 35-06 und einer Prüfung des mit 0.9.0 ausgelieferten Codes aus PR #49. `threats_open: 0` ist Voraussetzung für Push (35-06), Fast-Forward und Tag (35-07); ein offener Threat wird geschlossen oder vom Owner ausdrücklich als akzeptiertes Risiko eingetragen, nie still übergangen.
- 35-09 ergänzt die Register von 35-07 bis 35-09 und hält `threats_open: 0`. Danach läuft `/gsd:secure-phase 35` durch die Hauptsitzung (State A, Prüfung des vorhandenen Vertrags), bevor ROADMAP und STATE die Phase abhaken; das steht als Übergabe in der SUMMARY von 35-09.

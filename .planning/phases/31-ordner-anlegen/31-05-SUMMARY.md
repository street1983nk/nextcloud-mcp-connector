---
phase: 31-ordner-anlegen
plan: 05
subsystem: testing
tags: [live-beweis, appapi, impersonation, nextcloud-32, nextcloud-35, mkcol, kanarie, live-paar]

requires:
  - phase: 31-ordner-anlegen
    provides: Strecke Nextcloud 32 bereit (31-01, Nachmessung e9f4efa), Werkzeug files_create_folder (31-02, 31-03), Kanarie, Live-Paar und Abnahmeskript als Code (31-04), Netzfehler in der Kette (31-04b)
provides:
  - Live-Test tests/integration/test_files_create_folder_live.py (2 Kontrollen, 15 Fälle, 1 Zusatz) unter AppAPI-Impersonation
  - Rohprotokolle raw/nc35-ordner.txt und raw/nc32-ordner.txt samt früherer Läufe
  - docs/folder-evidence.md als stabiles Linkziel für 31-06 (Anker "Folder next to a tagged folder")
  - Produkt-Fix: gesperrter Name in einer Kette ergibt die Namensmeldung statt eines Serverfehlers
affects: [31-06, 34, scripts/acceptance_all_tools.py]

tech-stack:
  added: []
  patterns:
    - "Live-Test schreibt je Fall eine Zeile auf stdout; der Lauf prüft die Ausgabe gegen die Env-Werte, bevor sie ins Rohprotokoll kommt"
    - "Antwort-Hook am gemessenen Client notiert nur Methode, Pfad unter dem Home und Status"

key-files:
  created:
    - tests/integration/test_files_create_folder_live.py
    - docs/folder-evidence.md
    - .planning/phases/31-ordner-anlegen/raw/nc35-ordner.txt
    - .planning/phases/31-ordner-anlegen/raw/nc35-ordner-vorlaeufe.txt
    - .planning/phases/31-ordner-anlegen/raw/nc32-ordner.txt
    - .planning/phases/31-ordner-anlegen/raw/nc32-ordner-vorlaeufe.txt
  modified:
    - src/mcp_connector/nextcloud/clients/dav.py
    - tests/unit/test_dav_make_folder.py
    - tests/unit/test_files_create_folder.py

key-decisions:
  - "Produkt-Fix 77cab44: probe_folder liest genau den 500 mit OCP\\Files\\ForbiddenException und 'Invalid path' als abgelehnten Namen; jeder andere 500 bleibt Serverfehler"
  - "Ordnername mit Leerzeichen am Ende als Glied einer Kette: als offener Befund protokolliert, nicht behoben (ablehnen oder unterstützen ist eine Owner-Entscheidung)"
  - "Abnahmeskript nicht geändert, obwohl es mit Exit 1 endet (Skripte waren in diesem Plan tabu)"
  - "Fall geteilt-nur-lesen läuft als bob: auf beiden Instanzen besitzt alice den Freigabeordner, bob hat ihn ohne Anlegerecht"

patterns-established:
  - "Rohprotokoll je Instanz mit einer Datei der früheren Läufe daneben, damit das Hauptprotokoll je Fall genau eine Zeile trägt"

requirements-completed: []

duration: ca. 2h 30min
completed: 2026-11-12
---

# Phase 31 Plan 05: Live-Beweis von files_create_folder auf Nextcloud 35 und 32 Summary

**files_create_folder ist auf 35.0.0.10 und 32.0.15.1 unter AppAPI-Impersonation gemessen (je 18 von 18 grün, Kanarie und Live-Paar je 10 von 10 mit NC_MCP_REQUIRE_LIVE=1); die Messung fand einen Produktfehler (behoben), einen offenen Befund und ein Abnahmeskript, das aus drei Gründen außerhalb des Werkzeugs mit Exit 1 endet.**

## Performance

- **Duration:** ca. 2h 30min (mit einer Unterbrechung durch ein Nutzungslimit)
- **Completed:** 2026-11-12
- **Tasks:** 4 von 4
- **Files modified:** 9 (6 neu, 3 geändert)

## Ergebnis je Instanz

| | Nextcloud 35 (nc35) | Nextcloud 32 (nc-mcp-exapp) |
|---|---|---|
| occ status | versionstring 35.0.0, version 35.0.0.10 | versionstring 32.0.15, version 32.0.15.1 |
| Live-Test, Lauf des Protokolls | 18 passed (5. Lauf, Test f78fdd1) | 18 passed (2. Lauf, Test f78fdd1) |
| Zeilen ergebnis=ok / ergebnis=befund | 23 / 0 | 23 / 0 |
| Kanarie und Live-Paar, NC_MCP_REQUIRE_LIVE=1 | 10 passed | 10 passed |
| Kanarie | 4 Modi, je 24 von 24; files_create_folder je Modus zweimal abgewiesen; CLEANUP ordner je 404 | gleich |
| Live-Paar | normal 15 von 16 plus 1 benannte Ausnahme, 500, 412, timeout je 16 von 16; files_create_folder path je Modus gleich | gleich |
| BASELINE | alle fünf Zeilen gleich=ja; STAND nach allen Läufen gleich dem Ausgangsstand (158 Dateien, Freigaben 3, kein Tag, kein Kontingent) | alle fünf Zeilen gleich=ja; danach lässt das Abnahmeskript Objekte stehen (Wegwerf-Instanz) |
| Abnahmeskript | nicht gelaufen (Plan) | files_create_folder zweimal OK, Skript Exit 1 |
| 423 | nicht herstellbar: LOCK 200, MKCOL 201 (drei Wege) | nicht herstellbar: LOCK 501, MKCOL 201 |
| 404 bei MKCOL | nicht herstellbar: 409 | nicht herstellbar: 409 |

Auf 32 lief die ExApp als lokaler Prozess aus dem Worktree. Vor der Messung belegt: tools/list am Prozess direkt und über den Proxy der Nextcloud je 200 mit files_create_folder; ein Impersonationsaufruf mit erfundener Versionsnummer im Kopf (9.9.9 statt 0.7.2) antwortet ebenfalls 200 als alice, die registrierte Versionsnummer entscheidet dort also nicht.

Gemessene Fälle (beide Instanzen): frei, vorhanden, datei, eltern-fehlt, kette, deckel, teilabbruch-wettlauf, geteilt-nur-lesen, kein-ki, sandbox, teilabbruch-name, namen, sperre-423, mkcol-404, kontingent-knapp, dazu Kontrolle 1 und 2. Zwölf der fünfzehn Fälle, beide Kontrollen und alle sechs Namen lesen sich auf 32 und 35 gleich (Status in derselben Reihenfolge, dieselben Sätze). Unterschiede: teilabbruch-name (siehe Befund 1), oc:permissions der Freigabe für bob (SGDN auf 35, SGD auf 32), LOCK (200 auf 35, 501 auf 32).

Annahmen:

- A1 (32 liefert dieselben Status und denselben oc-fileid-Kopf): für jeden Status, den das Werkzeug als Zweig kennt, belegt; die Id kommt auf beiden Instanzen aus dem Kopf, ohne weiteres Lesen. Widerlegt für das Lesen eines gesperrten Namens (500 auf 35, 404 oder 400 auf 32).
- A5 (PROPFIND unter einer Datei): 404 auf beiden Instanzen, belegt.
- Annahme von Cleanup.add_folder aus 31-04 (einzeln gelöschter Ordner steht im Papierkorb unter seinem Basisnamen): auf beiden Instanzen belegt (Zeile PAPIERKORB).

## Befunde

**1. Produktfehler, behoben (77cab44): gesperrter Name in einer Kette wurde als Serverfehler gemeldet**
- Nextcloud 35.0.0 beantwortet den PROPFIND der Zählung auf `.htaccess` mit 500 (`OCP\Files\ForbiddenException`, `Invalid path`), nicht mit 400 wie der MKCOL. Das Werkzeug sagte mit parents=true "server error (500)" und riet zum späteren Wiederholen.
- Fix: `dav.probe_folder` liest genau diesen Body als `name_rejected`; jeder andere 500, ein 503 und ein nicht lesbarer Body bleiben Serverfehler. Unit-Tests zuerst rot (2 failed), danach grün; acht neue Unit-Tests.
- Nextcloud 32.0.15 gibt diesen 500 nicht: unter fehlenden Elternordnern 404, der Name fällt erst beim MKCOL des Glieds mit 400. Dort bleiben die zwei Elternordner stehen und die Meldung nennt sie.

**2. Offen, nicht behoben: Ordnername mit Leerzeichen am Ende als Glied einer Kette**
- `safe_path` kürzt jeden Pfad an beiden Enden. In einer Kette wird das Glied `mitte-leer ` deshalb als `mitte-leer` angelegt, das nächste Glied unter dem Namen mit Leerzeichen antwortet 409, und die Meldung nennt einen Ordner als angelegt, den es unter diesem Namen nicht gibt. Beide Instanzen gleich (Zeile ZUSATZ, befund=ja).
- Nicht im Plan vorgesehen, vom Test nur protokolliert. Ob solche Namen abgelehnt oder unterstützt werden, ist eine Owner-Entscheidung.

**3. Abnahmeskript endet mit Exit 1 (Akzeptanzkriterium "Exit 0" nicht erfüllt)**
- files_create_folder: beide Zeilen OK (created true mit created_folders, dann created false mit derselben id).
- Ursachen des Exit 1, alle außerhalb des Werkzeugs: (a) `fetch` nimmt den ersten Treffer von files_search nach dem Marker; seit eff3f55 (31-04) trägt auch der neue Ordner den Marker, fetch antwortet zu Recht "is a folder, not a file"; (b) `fetch` einer Mail scheitert am Mailserver der Testinstanz; (c) das Skript ruft files_download und files_read_as_markdown nie auf.
- Das Skript wurde nicht geändert.

**4. Nextcloud verlangt 4096 freie Bytes für einen neuen Ordner**
- Belegt plus 1024 Bytes ergibt 507, belegt plus 4096 Bytes ergibt 201 (QuotaPlugin.php, feste Größe 4096). 32.0.15 meldet die belegten Bytes eines früheren Augenblicks; der Test setzt sein knappes Kontingent deshalb auf belegt plus 8192 Bytes.

**5. `x.part` wird beantwortet, als läge dort eine Datei**
- MKCOL 405, das Lesen danach 207 mit einem Knoten ohne Ordnertyp (Datei-Id -1 auf 35), im Dateisystem liegt nichts. Das Werkzeug sagt "A file, not a folder, already exists". Nichts wird angelegt; der Satz nennt aber eine Datei, die es nicht gibt. Nicht geändert.

**6. Kontrolle 2 zeigt zwei Sätze**
- Mit falschem Secret ist die erste Anfrage des Werkzeugs die Tag-Abfrage des Ausschluss-Wächters (401); das Werkzeug meldet den Satz der unbeantworteten Prüfung, nicht den 401-Satz. Der 401-Satz von `dav._check` kommt beim bloßen Ordneraufruf des Clients. Der Plan erwartete den 401-Satz am Werkzeug.

## Task Commits

1. **Task 1: Live-Test, Gerüst, Kontrollen, zehn Kernfälle** - `ace4855` (test)
2. **Task 2: fünf Randfälle** - `f5089f9` (test)
3. **Task 3: Lauf auf Nextcloud 35, Protokoll, docs/folder-evidence.md** - `5feeba1` (docs)
4. **Task 4: Lauf auf Nextcloud 32, Abschnitt 32, voller Lauf** - `ebcc941` (docs)

Dazwischen, aus den Läufen heraus:

- `77cab44` fix(31-05): Produkt-Fix zu Befund 1
- `1f0d552` test(31-05): Korrektur des Live-Tests nach dem ersten Lauf auf 35 (Kontingent, Zusatzfall, keine Umgebung in repr)
- `ea16b9c` test(31-05): freier Text der Protokollzeilen englisch
- `0fbb224` test(31-05): Zeilen des Rückbaus auf eigener Zeile
- `f78fdd1` test(31-05): zwei Erwartungen nach dem ersten Lauf auf 32

## Files Created/Modified

- `tests/integration/test_files_create_folder_live.py` - Live-Test, 18 Testfunktionen
- `docs/folder-evidence.md` - Evidenzseite, englisch, Abschnitte Instances, Method, Nextcloud 35, Nextcloud 32, Folder next to a tagged folder, Group folder with ACL, What the run found, Not reproducible or not measured
- `.planning/phases/31-ordner-anlegen/raw/nc35-ordner.txt` - Rohprotokoll 35
- `.planning/phases/31-ordner-anlegen/raw/nc35-ordner-vorlaeufe.txt` - Protokollzeilen der Läufe 1 bis 4 auf 35
- `.planning/phases/31-ordner-anlegen/raw/nc32-ordner.txt` - Rohprotokoll 32
- `.planning/phases/31-ordner-anlegen/raw/nc32-ordner-vorlaeufe.txt` - Protokollzeilen des ersten Laufs auf 32
- `src/mcp_connector/nextcloud/clients/dav.py` - `_is_blocked_name`, ein Zweig in `probe_folder`
- `tests/unit/test_dav_make_folder.py`, `tests/unit/test_files_create_folder.py` - acht neue Tests

## Verifikation (gesehene Ausgaben)

- verify Task 1 und Task 2: je Exit 0 (Etiketten, collect-only, ruff, format, pyright, pytest tests/unit tests/contract).
- verify Task 3, Klauseln einzeln geprüft: alle 17 Zeichenketten im Protokoll, 0 Zeilen ergebnis=befund, 0 BASELINE-Zeilen gleich=nein, 0 Treffer "unexpected status", "passed" vorhanden, kein nc35-Container läuft, beide Anker in docs/folder-evidence.md, keine Gedankenstriche.
- verify Task 4, Klauseln einzeln geprüft: alle 13 Zeichenketten, 0 Zeilen ergebnis=befund, 0 Treffer "unexpected status", Platzhaltersatz weg, kein Container von nc-mcp-exapp läuft, keine .env-Datei im Status, keine Gedankenstriche.
- Gates am Ende: pytest tests/unit tests/contract 5876 passed, 35 skipped (vorher 5868; acht neue Unit-Tests); check_tool_budget.py 16222 Bytes, 24 Werkzeuge, Budget 18000; ruff check, ruff format --check (375 Dateien), pyright 0 Fehler, vulture je Exit 0.
- Jede Zeile in einem Codeblock von docs/folder-evidence.md steht wörtlich in einem der zwei Rohprotokolle (75 Zeilen geprüft, 0 fehlen).
- Geheimnisprüfung: alle fünf neuen Text-Dateien gegen APP_SECRET, HP_SHARED_KEY, beide App-Passwörter und beide Kontopasswörter aus .env.nc35 und .env.exapp, gegen die ersten 12 Zeichen der langen Werte und gegen die Zeichenkette des AppAPI-Kopfs: kein Fund.
- Am Ende läuft nur gameworld-dev-gameworld-docker-proxy-1; nc35 und nc-mcp-exapp gestoppt (stop, nie down), Volumes vorhanden, Port 23001 frei.
- Neun Commits als street1983nk, ohne Trailer; kein Push.

## Deviations from Plan

**1. Strecke 32 ohne Bootstrap (Vorgabe der Hauptsitzung)**
- `docker compose -f compose.exapp.yml start` und ExApp als lokaler Prozess aus dem Worktree statt `scripts/bootstrap_exapp.sh`; Schritt (0) von Task 4 greift nicht, weil die Nachmessung die Strecke bereit gemacht hat.

**2. Fall geteilt-nur-lesen als bob**
- Der Plan nennt alice als Messkonto. Auf beiden Instanzen gehört der Freigabeordner alice; bob ist der Empfänger ohne Anlegerecht. Der Test sucht das Konto ohne C und K und misst als dieses; die Dateisystemprobe läuft beim Eigentümer.

**3. Ausgabe über eine Zwischendatei statt direkt per tee**
- Jede Ausgabe ging zuerst in eine Datei außerhalb des Repos, wurde gegen die Env-Werte geprüft und dann angehängt. Anlass: Beim ersten Lauf druckte pytest im Fehlerteil die Argumente des Tests samt einem Anfangsstück von APP_SECRET. Diese Ausgabe kam nie ins Repo; der Test hält die Umgebung seither aus jeder Darstellung heraus.

**4. Mehr Läufe und zwei zusätzliche Rohdateien**
- 35: fünf Läufe (1 rot mit Befund, 2 ohne Abschlusszeile, 3 und 4 grün vor späteren Testkorrekturen, 5 mit dem Endstand); 32: zwei Läufe. Die Zeilen der früheren Läufe stehen in `nc35-ordner-vorlaeufe.txt` und `nc32-ordner-vorlaeufe.txt`, nicht im Plan vorgesehen. nc35 wurde dafür dreimal gestartet und gestoppt.

**5. Protokolle der Phase 28 zurückgesetzt**
- Kanarie und Live-Paar hängen an `28-10-canary.txt` und `28-11-pairs-live.txt` an. Die angehängten Zeilen stehen wörtlich in den Rohprotokollen dieses Plans; die zwei Dateien wurden danach mit `git checkout -- <Datei>` zurückgesetzt, weil sie nicht zu den Dateien des Plans gehören.

**6. Zusätze im Test**
- Dritter Sperrversuch (`X-User-Lock` der App files_lock), A5 als zweite Messung im Fall datei, Kontingent in drei Stufen, Zusatzfall Leerzeichen in der Kette, Baseline zusätzlich mit Papierkorb und Freigaben.

**7. Kanarie auf 35 ohne nc35-greenmail**
- Gestartet wurden nur die vier Container, die der Plan nennt; die Kanarie lief trotzdem grün.

**8. Kleinigkeiten**
- pytest für die Protokollläufe ohne das zweite `-q` (sonst fehlt die Abschlusszeile) und mit `--tb=line`.
- In `nc35-ordner.txt` trägt die Zeile PAPIERKORB (Abschnitt 4) und in den Dateien der früheren Läufe tragen einige Zeilen deutsche Wörter ohne Umlaute (Ausgabe früherer Fassungen); nicht nachträglich verändert, in docs/ nicht zitiert.

## Issues Encountered

- Ein versehentlich gestarteter Interpreter (`python -`) blockierte einen Befehl; die zwei Prozesse wurden an ihrer Befehlszeile erkannt und beendet.
- Der erste Versuch, den lokalen ExApp-Prozess zu beenden, fand die Prozessnummer nicht (deutsche Ausgabe von netstat); der Prozess wurde danach gezielt beendet, die Protokollzeile nennt das.

## Offene Punkte

- Befund 2 (Leerzeichen am Ende eines Glieds): Owner-Entscheidung, danach Unit-Test und Fix.
- Befund 3: `scripts/acceptance_all_tools.py` braucht drei Korrekturen (Datei-Id statt erstem Treffer, die zwei nie aufgerufenen Werkzeuge, Mailabruf klären), bevor es wieder Exit 0 liefern kann.
- Befund 5 (`x.part`): Satz nennt eine Datei, die es nicht gibt; ungeändert.
- Auf 32 steht nach der Kanarie eine Freigabe vom Typ 12 (Deck) auf dem Beispielbild von Deck mehr; Herkunft nicht untersucht, Wegwerf-Instanz.
- 423 und 404 bei MKCOL bleiben nur per Unit-Test belegt; Netzfehler in der Kette (31-04b) ebenfalls.
- Versionen 33 und 34 sind nicht gemessen.
- STATE.md, ROADMAP.md und REQUIREMENTS.md wurden nicht angefasst; FOLD-01 bis FOLD-05 sind nicht als erledigt markiert.

## Known Stubs

Keine.

## Next Phase Readiness

- 31-06 kann auf `docs/folder-evidence.md#folder-next-to-a-tagged-folder` verlinken.
- Beide Teststrecken sind gestoppt und wieder startbar: nc35 über `docker start`, die Strecke 32 über `docker compose -f compose.exapp.yml start` plus lokalem Prozess auf 127.0.0.1:23001.

## Self-Check: PASSED

- Alle neun Dateien vorhanden und committet
- Commits ace4855, f5089f9, 77cab44, 1f0d552, ea16b9c, 0fbb224, 5feeba1, f78fdd1, ebcc941 im Log gefunden

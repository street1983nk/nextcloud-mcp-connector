---
phase: 31-ordner-anlegen
plan: 05b
subsystem: files
tags: [files_create_folder, namensprüfung, leerraum, x.part, abnahmeskript, live-beweis, nextcloud-32, nextcloud-35]

requires:
  - phase: 31-ordner-anlegen
    provides: Live-Beweis 31-05 mit den Befunden 2 (Leerzeichen am Rand), 3 (Abnahmeskript Exit 1) und 5 (x.part)
provides:
  - Vorabprüfung in files.create_folder gegen Leerraum am Rand eines Segments (D-31-08)
  - Satz ohne Dateibehauptung für einen Nicht-Ordner ohne Datei-Id (D-31-09)
  - Abnahmeskript, das alle 24 Werkzeuge ruft und eine fehlende Voraussetzung der Instanz mit eigenem Exit-Code meldet
  - Rohprotokolle raw/nc35-nacharbeit.txt und raw/nc32-nacharbeit.txt, Abschnitt "Follow-up run" in docs/folder-evidence.md
affects: [31-06, 34, scripts/acceptance_all_tools.py]

tech-stack:
  added: []
  patterns:
    - "Namensablehnung nur aus dem Argument, vor dem Ausschluss-Wächter: gleich für getaggt und frei, kein Request"
    - "Abnahmeskript trennt Werkzeugfehler von fehlender Voraussetzung der Instanz durch eine Gegenfrage am Connector vorbei"

key-files:
  created:
    - .planning/phases/31-ordner-anlegen/31-05b-PLAN.md
    - .planning/phases/31-ordner-anlegen/raw/nc35-nacharbeit.txt
    - .planning/phases/31-ordner-anlegen/raw/nc32-nacharbeit.txt
  modified:
    - src/mcp_connector/tools/files.py
    - tests/unit/test_files_create_folder.py
    - tests/unit/test_files_create_folder_exclusion.py
    - tests/unit/test_pair_equality_files.py
    - tests/integration/test_files_create_folder_live.py
    - scripts/acceptance_all_tools.py
    - docs/folder-evidence.md
    - .planning/phases/31-ordner-anlegen/31-CONTEXT.md

key-decisions:
  - "D-31-08: abgelehnt wird jedes Segment mit segment != segment.strip(), also genau die Menge, die safe_path am Pfadende kürzt; keine weitere Namensregel"
  - "D-31-09: kein Umdeuten von x.part in 'Name abgelehnt'; nur ein Knoten mit positiver Datei-Id heißt Datei, jeder andere Nicht-Ordner bekommt den Satz ohne Dateibehauptung"
  - "Abnahmeskript: fehlende Mail-Voraussetzung ist Verdikt PREREQ mit Exit 3, nie Exit 0 und nie FAIL"
  - "Testpost auf der Instanz 32 nicht neu zugestellt (das macht nur bootstrap_exapp.sh, das hier nicht laufen darf)"

patterns-established:
  - "Rohprotokoll der Nachmessung als neue Datei neben dem der ersten Messung, die erste bleibt unverändert"

requirements-completed: []

duration: ca. 1h 20min
completed: 2026-11-12
---

# Phase 31 Plan 05b: Namen am Rand und Abnahmelauf Summary

**files_create_folder lehnt Ordnernamen mit Leerraum am Rand vor jedem Request ab und nennt bei x.part keine Datei mehr; beides ist auf Nextcloud 35.0.0.10 und 32.0.15.1 live nachgemessen (je 18 von 18, Kanarie und Live-Paar je 10 von 10). Das Abnahmeskript ruft alle 24 Werkzeuge, endet auf der Instanz 32 aber mit Exit 3, weil deren Mailserver nach dem Neustart leer ist.**

## Performance

- **Duration:** ca. 1h 20min
- **Completed:** 2026-11-12
- **Tasks:** 5 von 5
- **Files modified:** 11 (3 neu, 8 geändert)

## Wortlaut der Meldungen

Neu, Leerraum am Rand (ToolError, reason unspecified):

- message: `The folder name {segment!r} in {path!r} starts or ends with whitespace.`
- hint: `Remove the whitespace at the start and the end of every folder name and call again; nothing was created.`

Neu, Nicht-Ordner ohne Datei-Id (ConflictError):

- message: `{path} cannot be created as a folder: Nextcloud reports an entry there that is not a folder.`
- hint: `Choose another name, for example one that does not end in .part; this tool never replaces anything.`

Unverändert für einen Nicht-Ordner mit positiver Datei-Id: `A file, not a folder, already exists at {path}.` mit dem Hinweis `Choose another name; this tool never replaces a file.`

## Was geändert wurde

**(a) Leerraum am Rand (Befund 2 aus 31-05)**

- Am Code geprüft: `dav.safe_path` kürzt den ganzen Pfad mit `str.strip()` (Leerzeichen, Tab, Zeilenumbruch, jeder Unicode-Leerraum an beiden Enden), nie ein einzelnes Segment und nie einen Punkt; Steuerzeichen prüft es erst danach. Abweichen konnte der angelegte Name deshalb am Pfadende und in der Kette an jedem Glied.
- `_padded_name(path)` findet das erste Segment mit `segment != segment.strip()`; `create_folder` lehnt nach `safe_path` und der Wurzelprüfung und vor dem ersten `_writable` ab. Kein Request, auch keine Tag-Abfrage.
- `safe_path` und `dav.py` sind unverändert; Leerzeichen im Inneren eines Namens, ein Punkt am Ende und ein Schrägstrich am Pfadende gehen wie bisher hinaus (Positivkontrollen).
- Die Ablehnung ist eine Regel des Werkzeugs: beide Nextcloud-Fassungen legen einen Namen mit Leerzeichen am Ende selbst an (raw/nc35-ordner.txt Zeile 82 bis 85, raw/nc32-ordner.txt Zeile 138 bis 141). Der Satz lautet deshalb nicht "Nextcloud does not accept".

**(b) x.part (Befund 5 aus 31-05)**

- `_in_the_way(node)`: Id aus ASCII-Ziffern und größer 0 ergibt den bisherigen Dateisatz, sonst den neuen Satz. Alle drei Stellen (Ziel ohne parents, Knoten in der Zählung, Sandbox-Wurzel) rufen diese Fabrik.

**(c) Abnahmeskript (Befund 3 aus 31-05)**

- `fetch` der Datei nimmt den Treffer, dessen Pfad der hochgeladenen Datei gleicht.
- `files_download` auf die hochgeladene Datei; für `files_read_as_markdown` lädt das Skript eine kleinste DOCX-Datei über den Binärweg von `files_upload` hoch und verlangt den Marker im Markdown.
- Mailabruf: scheitert `fetch` einer gelisteten Mail, fragt das Skript die Mail-App am Connector vorbei mit demselben Konto. Antwortet sie selbst mit einem Serverfehler, ist der Schritt PREREQ (Exit 3, mit vollem Grund auf stderr); antwortet sie und das Werkzeug nicht, bleibt es FAIL (Exit 1).

## Ursache des Mailabrufs

Gemessen auf der Instanz 32 (raw/nc32-nacharbeit.txt, Abschnitt 5): Es ist die Testinstanz, kein Fehler des Skripts und keiner des Werkzeugs.

- GreenMail läuft, hält die Post aber nur im Arbeitsspeicher: nach dem Start der Topologie `STATUS "INBOX" (MESSAGES 0 UIDNEXT 1 ...)`.
- Die Mail-App listet weiter sechs Nachrichten aus ihrem Cache (`mail_browse` count 6).
- Der Abruf der Nachricht 1 direkt an der Mail-App, mit dem App-Passwort von alice: HTTP 500, "Could not connect to IMAP server. Please check your logs."
- Die Testpost stellt nur `scripts/bootstrap_exapp.sh` zu (`deliver_test_mail`); es lief hier nicht, und es wurde nichts von Hand zugestellt.

## Ergebnis der Live-Läufe

| | Nextcloud 35 (nc35) | Nextcloud 32 (nc-mcp-exapp) |
|---|---|---|
| occ status | version 35.0.0.10 | version 32.0.15.1 |
| Live-Test | 18 passed (erster Lauf, HEAD 95ff4da) | 18 passed (erster Lauf, HEAD bdfc685) |
| Zeilen ergebnis=ok / befund | 24 / 0 | 24 / 0 |
| NAME 'ende-leer ', ' anfang-leer' | neue Meldung, status=keine, weder der Name noch der gekürzte Name im Dateisystem | gleich |
| NAME 'x.part' | MKCOL 405, PROPFIND 207, neuer Satz, nichts im Dateisystem | gleich |
| ZUSATZ (Kette und ohne parents) | befund=nein: zweimal abgelehnt, 0 Requests, Ordner vorher und nachher leer | gleich |
| kein-ki, Zusatzpaar mit Leerzeichen | getaggt und erfunden gleich, kein Request | gleich |
| BASELINE | fünf Zeilen gleich=ja (158 Dateien, Freigaben 3) | fünf Zeilen gleich=ja (17 Dateien, Freigaben 3) |
| Kanarie und Live-Paar, NC_MCP_REQUIRE_LIVE=1 | 10 passed; je Modus 24 von 24; 8 Abweisungen von files_create_folder, 8 Zeilen CLEANUP ordner 404; Paar files_create_folder in 4 Modi gleich | gleich |
| tools/list am lokalen Prozess | entfällt (Test ruft die Funktion des Worktrees im eigenen Prozess) | direkt und über den Proxy je 200, 24 Werkzeuge, files_create_folder vorhanden |
| Abnahmeskript | nicht gelaufen (hinterlässt Objekte) | Exit 3: 24 Werkzeuge gerufen, kein FAIL, keines nie gerufen, ein PREREQ (fetch einer Mail) |

Nichts widerspricht dem Entscheid. Exit 0 des Abnahmeskripts ist NICHT gemessen: dafür braucht die Instanz neu zugestellte Testpost.

## Task Commits

1. **Plan und Kontext** - `91df8e4` (docs)
2. **Task 1: Leerraum am Rand** - `627f243` (fix)
3. **Task 2: Knoten ohne Datei-Id** - `8516e1e` (fix)
4. **Task 3: Live-Test und Abnahmeskript** - `bdfc685` (test), `95ff4da` (test, Mail-Voraussetzung nach der Messung)
5. **Task 4: Nachmessung, Rohprotokolle, Evidenzseite** - `fd5a8e0` (docs)

Task 5 (Gates) hat keine Datei geändert.

## Verifikation (gesehene Ausgaben)

- RED: vor der Umsetzung 62 failed in den drei Unit-Dateien (52 zu (a), 10 zu (b)); die Positivkontrollen waren wie erwartet schon grün.
- GREEN: nach (a) 10 failed (nur (b)), nach (b) 0.
- Mutationsproben: Zweig von (a) abgeschaltet ergibt wieder 62 failed (52 zu (a) plus die damals noch offenen 10); `_in_the_way` immer als Datei ergibt 10 failed. Beide Stände wiederhergestellt, danach grün.
- `pytest tests/unit tests/contract` mit überschriebenem addopts: 5955 passed, 35 skipped (vorher 5876; 79 neue Fälle).
- `scripts/check_tool_budget.py`: 16222 Bytes, 24 Werkzeuge, Budget 18000. ruff check, ruff format --check (375 Dateien), pyright 0 Fehler, vulture: je Exit 0.
- Diff-Prüfung, Positivkontrolle der Basis 91c3b51 bestanden: `dav.py` gegen eff0bf8 0 Zeilen, `reg_files.py` und `server/__init__.py` gegen 620ab4e 0 Zeilen, `test_no_destructive_calls.py` gegen eff0bf8 0 Zeilen (EXPECTED_MKCOL_CALLS = 2); Gegentreffer im Diff gegen die Basis je 1 (`+def _padded_name`, `+def _in_the_way`, `+async def files_create_folder`). In tests/unit und tests/contract gegen eff0bf8 keine entfernte oder geänderte Zeile.
- docs/folder-evidence.md: 87 Zeilen in Codeblöcken, jede steht wörtlich in einem Rohprotokoll; keine Gedankenstriche; bestehende Überschriften unverändert, neu "Follow-up run" am Ende.
- Geheimnisprüfung: jede Zwischendatei und die drei neuen bzw. geänderten Dateien (zwei Rohprotokolle, Evidenzseite) gegen APP_SECRET, HP_SHARED_KEY, beide App-Passwörter und beide Kontopasswörter aus .env.exapp und .env.nc35 und gegen die ersten 12 Zeichen der langen Werte: kein Fund.
- Am Ende läuft nur gameworld-dev-gameworld-docker-proxy-1; nc35 und nc-mcp-exapp gestoppt (stop, nie down), Volumes vorhanden, lokaler Prozess beendet, Port 23001 frei.
- Sechs Commits als street1983nk, ohne Trailer; kein Push.

## Geänderte Erwartungen im Live-Test

Kein Unit- oder Contract-Test wurde geändert. Im Live-Test (tests/integration/test_files_create_folder_live.py) drei Stellen, je mit Grund im Kommentar:

1. `namen`: `ende-leer ` galt als Erfolg, wenn der gekürzte Ordner angelegt war. Das schrieb das alte Kürzen fest. Jetzt verlangt: neue Meldung, kein Request, weder der Name noch der gekürzte Name im Dateisystem (D-31-08). Neu in der Liste: ` anfang-leer`.
2. `namen`: `x.part` verlangt den neuen Satz ohne das Wort "file" (D-31-09).
3. Zusatzfall: protokollierte bisher nur und prüfte nichts; jetzt geprüfte Messung mit `befund=nein` als Pflicht, mit und ohne parents.

Dazu ein Zusatz im Fall kein-ki (Paar mit Leerzeichen am Namensende).

## Auslegungen

- **(a) Menge:** "Leerzeichen" als alles gelesen, was `str.strip()` entfernt, weil genau das `safe_path` kürzt (Tab, Zeilenumbruch, geschütztes Leerzeichen, U+3000). Abgelehnt wird auch ein Segment nur aus Leerraum und Leerraum vor dem ersten Schrägstrich (`" /A/b"`).
- **(a) Reihenfolge:** Die Prüfung steht nach `safe_path` und der Wurzelprüfung, also behalten "No path was given", Wurzel, Traversal, Backslash und Steuerzeichen ihren Satz; sie steht vor dem Ausschluss-Wächter, weil sonst ein getaggter Elternordner (parent_missing) von einem erfundenen (Namensablehnung) unterscheidbar wäre. Folge: bei nicht beantwortbarem Wächter kommt für so einen Namen die Namensablehnung statt des Satzes der unbeantworteten Prüfung; geschrieben wird in beiden Fällen nichts.
- **(a) Wortlaut:** eigener Satz statt `dav.name_rejected`, weil Nextcloud den Namen annähme.
- **(b):** die konservativere Lesart. Nicht "Name abgelehnt", weil das Antwortbild nur auf 32 und 35 gemessen ist; der Hinweis nennt `.part` nur als Beispiel. Eine echte Datei, deren Id nicht lesbar wäre, bekäme denselben Satz; er bliebe wahr.
- **(c):** "klar als Voraussetzung melden, ohne still zu überspringen" als eigener Exit-Code 3 gelesen, nicht als Exit 0 mit Hinweis.

## Deviations from Plan

**1. Ein zweiter Commit zu Task 3**
- Der Mail-Teil des Skripts hing an der Messung der Ursache; er kam nach dem Live-Test auf 32 als `95ff4da`. Live-Test und Kanarie auf 32 liefen mit `bdfc685`, das Abnahmeskript mit `95ff4da`, alles auf 35 mit `95ff4da` (src zwischen beiden unverändert).

**2. Reihenfolge 32 vor 35**
- Die Instanz 32 lief zuerst, weil die Ursache des Mailabrufs nur dort messbar war.

**3. Erster Start des lokalen Prozesses brach ab**
- Mit der ganzen .env.exapp in der Umgebung will der Prozess wegen HP_SHARED_KEY einen Unix-Socket (NotImplementedError unter Windows). Zweiter Start mit genau den fünf Namen APP_ID, APP_SECRET, APP_VERSION, NC_MCP_URL, NC_MCP_PUBLIC_URL.

**4. Block "warnings summary" von pytest nicht im Rohprotokoll**
- Er trägt einen lokalen Pfad und keine Messung; im Protokoll vermerkt.

**5. Skript bekommt httpx als Import**
- Für die Gegenfrage an die Mail-App; httpx ist bereits Abhängigkeit des Projekts, nichts wurde installiert.

## Issues Encountered

- Ein `sed -i` für die erste Mutationsprobe stellte die Zeilenenden der Datei um; die Datei wurde aus der Kopie byte-gleich wiederhergestellt (cmp), danach liefen Mutationen nur noch über gezielte Edits.
- Das Schreibwerkzeug setzte ` ` und `　` in den neuen Tests als echte Zeichen; ruff meldete es, die Zeichen stehen jetzt als Escapes im Quelltext.
- Kanarie und Live-Paar auf 35 brauchten 326 Sekunden (auf 32 120 Sekunden); beide grün.

## Offene Punkte

- **Exit 0 des Abnahmeskripts ist nicht belegt.** Auf der Instanz 32 fehlt die Testpost. Nötig: `deliver_test_mail` samt `occ mail:account:sync` (Teil von bootstrap_exapp.sh, das auf 32 abbricht), danach das Skript erneut. Owner-Entscheid, ob das von Hand geschehen soll.
- **Registrierte Version auf 32 steht auf 9.9.9** statt 0.7.2 (occ app_api:app:list). In 31-05 lief dort ein Impersonationsaufruf mit der erfundenen Nummer 9.9.9 im Kopf; ob er den Eintrag geändert hat, wurde nicht untersucht. Alle Aufrufe dieses Plans (Kopf 0.7.2) antworteten 200. Nicht verändert.
- Das Antwortbild von `x.part` ist auf 33 und 34 nicht gemessen.
- Der Hinweis von `dav.name_rejected` nennt weiter "a trailing space or dot" als zu meidende Namen; ein Punkt am Ende wird aber angelegt (gemessen in 31-05). Nicht Teil des Entscheids, nicht geändert.
- Das Abnahmeskript lässt jetzt zusätzlich eine DOCX-Datei in der Wegwerf-Instanz stehen.
- STATE.md, ROADMAP.md, REQUIREMENTS.md und 31-06-PLAN.md wurden nicht angefasst; FOLD-01 und FOLD-05 sind nicht als erledigt markiert.

## Nachtrag vom 2026-11-12: Exit 0 des Abnahmeskripts belegt

Der erste offene Punkt oben ist geschlossen, der zweite geklärt. Entscheid der Hauptsitzung: Die Testpost darf in der Wegwerf-Instanz 32 von Hand neu zugestellt werden, mit genau den Schritten des Bootstrap-Skripts. Rohprotokoll: `raw/nc32-abnahme.txt`.

- **Vorher:** GreenMail läuft, INBOX von alice `MESSAGES 0, UIDNEXT 1`; die Mail-App antwortet beim Abruf der Nachrichten 1 bis 6 je HTTP 500.
- **Zustellung:** das Python-Programm aus `deliver_test_mail` unverändert aus dem Skript herausgelesen (185 Zeilen) und wie dort in einem Wegwerf-Container `python:3.13-alpine` im Netz `nc-mcp-exapp-net` gefahren (`docker run --rm`, Image lag lokal vor): "delivered 6", Schlagwort `$label1` gesetzt, Exit 0. Danach `occ mail:account:sync 1 -f`, Exit 0. `scripts/bootstrap_exapp.sh` lief nicht und ist unverändert; kein Datenbankeingriff.
- **Nachher:** INBOX `MESSAGES 6, UIDNEXT 7`; die Mail-App listet sechs Nachrichten mit denselben Ids 1 bis 6 und liefert jede mit HTTP 200.
- **Abnahmeskript (Commit 95ff4da, unverändert): Exit 0.** 24 von 24 Werkzeugen gerufen, 34 Zeilen OK, 0 FAIL, 0 PREREQ, 0 SKIP; `fetch` der Mail ist OK.
- **Version 9.9.9:** nur gelesen. `handleExAppVersionChange` in `apps/app_api/lib/Service/AppAPIService.php` (AppAPI 32.0.0) speichert bei jedem Aufruf einer ExApp die Version aus dem Kopf `EX-APP-VERSION`, wenn sie nach `version_compare` größer ist als die gespeicherte, und senkt sie nie. Der Aufruf mit der erfundenen Nummer aus 31-05 hat den Eintrag also auf 9.9.9 gehoben; Aufrufe mit 0.7.2 ändern ihn nicht zurück. Nichts daran geändert. Folge für später: Eine echte höhere Version als 9.9.9 gibt es nicht, der Eintrag dieser Wegwerf-Instanz bleibt also so, bis sie neu aufgebaut wird.
- Am Ende: lokaler Prozess beendet, Topologie gestoppt (stop), Volumes vorhanden, es läuft nur gameworld-dev-gameworld-docker-proxy-1. GreenMail ist nach dem Stopp wieder leer; vor dem nächsten Lauf des Skripts braucht es dieselbe Zustellung.

## Known Stubs

Keine.

## Next Phase Readiness

- 31-06 kann unverändert auf `docs/folder-evidence.md#folder-next-to-a-tagged-folder` verlinken; neu gibt es `#follow-up-run`.
- Beide Teststrecken sind gestoppt und wieder startbar wie in 31-05 beschrieben; für den lokalen Prozess auf 32 nur die fünf genannten Variablen setzen.

## Self-Check: PASSED

- Alle elf Dateien vorhanden und committet
- Commits 91df8e4, 627f243, 8516e1e, bdfc685, 95ff4da, fd5a8e0 im Log gefunden

# Phase 32: Tasks-Bundle suchen, lesen, anlegen - Research

**Researched:** 2026-11-13
**Domain:** CalDAV `VTODO` (RFC 5545, RFC 4791) über Nextcloud 32 bis 35, AppAPI-Impersonation, Gate-Kette des Connectors, Testtopologien
**Confidence:** HIGH für Code-Lage, Gate-Inventar, Serverquellen und Bootstrap-Befund; MEDIUM für Zeitbudgets und Erkennung der Tasks-App (gelesen, unter Impersonation ungemessen); offen ist ein Zielkonflikt in D-32-06 (siehe Befund K1)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Unteraufgaben
- **D-32-01:** `tasks_read` liefert zu einer Aufgabe die Liste ihrer direkten Unteraufgaben, je mit `task:`-Id, Titel und Status. So beantwortet der Assistent "Was ist bei Projekt X noch offen?" mit einem Aufruf. (Owner, 13.11.2026, Auswahl "Liste der Unteraufgaben")
- **D-32-02:** Die Liste geht genau eine Ebene tief. Enkel sieht der Assistent, wenn er eine Unteraufgabe selbst liest. (Owner, 13.11.2026, Auswahl "Nur direkte Kinder")
- **D-32-03:** Die zusätzliche Abfrage für die Kinder (`REPORT` mit `text-match` an `RELATED-TO`, docs/spike-tasks.md 5.3 und 9.4 Punkt 2) wird vor dem Bau gemessen, auch bei 2000 Aufgaben in einer Liste; die Kostenreihen des Spikes kennen sie nicht. Sie bekommt ein eigenes Zeitbudget. Wird es überschritten oder scheitert die Abfrage, kommt die Aufgabe trotzdem zurück, ohne Kinderliste und mit einem ehrlichen Hinweis, dass die Unteraufgaben nicht gelesen werden konnten. Eine leere Liste heißt nur dann "keine Unteraufgaben", wenn die Abfrage geantwortet hat. (Bedingung der gewählten Option, Owner 13.11.2026)
- **D-32-04:** In `tasks_search` ist jede Unteraufgabe ein eigener, normaler Treffer und nennt Id und Titel ihrer Elternaufgabe. Keine Gruppierung unter dem Elterntreffer: Sortierung, Fälligkeitsfilter und Blättern gelten für jede Aufgabe einzeln. (Owner, 13.11.2026, Auswahl "Eigene Treffer mit Elternverweis")

#### Geteilte Listen
- **D-32-05:** Nennt der Assistent keine Liste, sucht `tasks_search` in eigenen und in hineingeteilten Aufgabenlisten. Der Parameter `list` schränkt auf eine Liste ein und wird, wie beim Schreiben, nur gegen die Discovery aufgelöst. (Owner, 13.11.2026, Auswahl "Eigene und geteilte")
- **D-32-06:** Jeder Treffer und jede gelesene Aufgabe nennt ihre Liste mit drei Angaben: Name der Liste, wie Nextcloud ihn anzeigt, geteilt ja oder nein, beschreibbar ja oder nein. Der Name oder die Kennung der Person, die geteilt hat, kommt in keine Antwort des Bundles. "Beschreibbar" stammt aus der Discovery (`{http://owncloud.org/ns}read-only`, docs/spike-tasks.md 5.2), nicht aus einem Schreibversuch. (Owner, 13.11.2026, Auswahl "Listenname, geteilt, beschreibbar")

#### Suchtreffer
- **D-32-07:** Ein Treffer von `tasks_search` trägt: `task:`-Id, Titel, Status, Fälligkeit, Startdatum, Priorität, Tags, die Liste nach D-32-06, den Elternverweis nach D-32-04 und das Kennzeichen `recurring`. Die Beschreibung kommt nur über `tasks_read`, auch nicht als Anriss. (Owner, 13.11.2026, Auswahl "Mittel: ohne Beschreibung")
- **D-32-08:** Seitengröße 25 Treffer. Weitere Treffer über das Blättern aus TASK-02 (Cursor-Handles, harter Deckel, ehrliche Notiz). (Owner, 13.11.2026, Auswahl "25 je Seite")
- **D-32-09:** Der Statusfilter kennt drei Werte: offen (Standard, ohne erledigte und abgebrochene), erledigt, alle. "Alle" zeigt auch abgebrochene; jeder Treffer trägt seinen Status. Das erweitert den Wortlaut von TASK-02 ("optional alle") um "erledigt". (Owner, 13.11.2026, Auswahl "Offen, erledigt oder alle")

#### Tasks-App fehlt oder ist aus
- **D-32-10:** Ohne installierte oder eingeschaltete Tasks-App arbeiten alle drei Werkzeuge normal. `tasks_create` und der Fall "keine Aufgabenliste" (E6) nennen einmal, dass Aufgaben in der Nextcloud-Oberfläche nur mit der Tasks-App sichtbar sind. Lässt sich der Zustand der App nicht verlässlich erkennen, entfällt der Hinweis; geraten wird nicht. (Owner, 13.11.2026, Auswahl "Arbeitet, mit Hinweis")
- **D-32-11:** Testinstanz und CI messen beides: einen Lauf mit installierter Tasks-App (Suchtreffer-Link für TASK-09, Sicht der App auf angelegte Aufgaben) und einen Lauf ohne (Suchen, Lesen, Anlegen gehen; die allgemeine Suche antwortet leer statt falsch, docs/spike-tasks.md 5.4). Die Fassung der Tasks-App wird im Beleg festgehalten. (Owner, 13.11.2026, Auswahl "Beides messen")

#### Live-Beweis
- **D-32-12:** Das Bundle wird live auf Nextcloud 35 und 32 belegt, unter AppAPI-Impersonation, wie Phase 31 (D-31-06). (Owner, 13.11.2026, Auswahl "35 und 32, Reparatur als erster Plan")
- **D-32-13:** Der erste Plan der Phase repariert `scripts/bootstrap_exapp.sh` für Nextcloud 32, damit die 32er Messung per Skript wiederholbar ist statt von Hand: Daemon `manual_install` mit Host ohne Port (Zeile 1288 bis 1290) und `occ user:auth-tokens:add` ohne `--name` auf 32 (Zeile 991). Vorher messen, ob AppAPI 34 und 35 dieselbe Form vertragen; kein Verhalten für 34 und 35 ändern, das heute funktioniert. Das ersetzt den am 12.11.2026 vorgemerkten eigenen kleinen Plan. (Owner, 13.11.2026, selbe Auswahl; Befund in 31-01-SUMMARY.md und raw/nc32-strecke.txt ab Zeile 706)

#### Bereits entschieden, hier nur zur Erinnerung
- E2: eigenes Bundle `tasks`, zehnte Familie, einzeln abschaltbar über `NC_MCP_DISABLED_TOOLS`.
- E3: `task:`-Id über `fetch` und Provider `tasks` auflösbar, eigener Plan (TASK-09). Der Owner will alles in 0.8.0, kein 0.8.1; TASK-09 wird in dieser Phase gebaut, nicht verschoben.
- E4: Schreibziel ohne `list` nur bei genau einer eigenen Liste, sonst Fehler mit den Listennamen; nie still in geteilte Listen; in einen Deck-Kalender nie.
- E6: keine Aufgabenliste: `tasks_search` leer mit Hinweis, `tasks_create` Fehler mit Ausweg.
- E7: Felder von `tasks_create`: `summary`, `list`, `description`, `due`, `start`, `priority`, `tags`, `timezone`, `parent`.
- E9: Deck-Kalender (`app-generated--`) ausgeschlossen, lesend und schreibend.
- E1: Budget der Werkzeugliste nach der Hausregel neu verankern (Messung plus 15 Prozent, auf 500 gerundet), Decke je Werkzeug 1400 Bytes.
- Wiederkehrende Aufgaben erscheinen als Masteraufgabe mit `recurring: true`, ohne Expansion (TASK-02).
- Linie aus Phase 31, die hier weiter gilt: ablehnen statt still verändern (D-31-08), Meldungen sagen nur, was sicher ist (D-31-09), bei einem Abbruch wird genannt, was schon geschehen ist (D-31-02).

### Claude's Discretion
Der Owner hat am 13.11.2026 mit "Festschreiben" bestätigt, dass kleinere technische Punkte nach den bisherigen Linien entschieden und als Entscheidung der Planung gekennzeichnet werden:
- Feldnamen der Antworten und Parameter (englisch, im Stil der vorhandenen Werkzeuge; der Parameter der Elternaufgabe heißt nicht `uid`, `user` oder `owner`, TASK-05).
- Wortlaut der Hinweise und Fehlermeldungen (englisch, kurz, mit Ausweg).
- Höhe des harten Deckels beim Blättern, Zeitbudget je Liste (Vorschlag des Spikes: 1 s als Untergrenze, docs/spike-tasks.md Abschnitt 6) und Zeitbudget der Kinderabfrage (D-32-03), jeweils aus einer Messung abgeleitet.
- Deckel der Kinderliste in `tasks_read` und die Notiz, wenn er greift.
- Woran der Zustand der Tasks-App erkannt wird (D-32-10); trägt kein Weg verlässlich, entfällt der Hinweis.
- Ob die zwei Läufe aus D-32-11 zwei CI-Beine oder zwei Abschnitte eines Beins sind.
- Kappungslänge der Beschreibung in `tasks_read` (TASK-04 verlangt gekappt, ohne Marker, mit Kürzungsvermerk).
- Zuschnitt der Pläne und Wellen; fest ist nur D-32-13 (Bootstrap zuerst) und TASK-09 als eigener Plan.

### Deferred Ideas (OUT OF SCOPE)
- Aufgabenlisten anlegen: kam beim Fall "keine Aufgabenliste" als naheliegender Ausweg auf, ist aber eine neue Fähigkeit und kein Teil dieser Phase. Der Fehler nennt den Ausweg über die Tasks-App.
- Ganzer Unteraufgaben-Baum in einem Aufruf: vom Owner abgewählt (D-32-02).
- Name der Person, die eine Liste geteilt hat: vom Owner abgewählt (D-32-06).
- Anriss der Beschreibung im Suchtreffer: vom Owner abgewählt (D-32-07).
- Tag-Alias `no-ai` neben `kein-ki`: eigene kleine Phase nach 0.8.0 (Owner, 13.11.2026).
- Live-Test der Werkzeuge in einem CI-Job mit ExApp-Topologie (Lücke W3 aus Phase 31): für die Planung dieser Phase zu prüfen, sonst Phase 34.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TASK-01 | Aufgabenlisten sind Kalender mit `VTODO`, eigene und geteilte; Deck, Abos, Scheduling, Papierkorb nie; Kalender-Bundle byte-gleich | F2: eigene Discovery mit eigenem PROPFIND-Körper, Regel "resourcetype `calendar` UND `VTODO` UND kein Präfix `app-generated--`" (Spike 5.2), Byte-Pin der zwei Kalender-Körper vor der ersten Änderung, Liste der unberührbaren Funktionen in `caldav.py` |
| TASK-02 | `tasks_search`: offen im Standard, Text, Fälligkeitsgrenze ohne undatierte, Sortierung, Cursor mit Deckel, `degraded` je Liste, `recurring`, Fremdobjekt überspringen, Limit-Politik | F3: Tabelle Server gegen Connector, Hybrid-Vorfilter, Sortierschlüssel, Cursor nach `paging.py`, Deckel nach `files_search`, Überspringen je Objekt statt `parse_ics` |
| TASK-03 | Konto ohne Aufgabenliste: Fixture und live mit nur `VEVENT` | F2 (Home-404 als E6), F10 (Live-Konto per `occ user:add` plus Basic-Anmeldung, Spike 5.1), Fixture `caldav_home_fresh_account.xml` |
| TASK-04 | `tasks_read`: Felder, Kappung ohne Marker, Zeitmatrix, kein `ATTACH`, unbekannte Id | F4 (Kinder), Muster "Zeitmatrix" (schwebend nie zu UTC, anders als `caldav._value_of`), Kappung nach `mail._capped` |
| TASK-05 | `tasks_create` create-only, `DUE;VALUE=DATE`, Zone, Priorität, Start vor Fälligkeit, Parent-Name, Rücklesen | F6: icalendar 7.3.0 erzeugt `DUE;VALUE=DATE` und `RELATED-TO` ohne `RELTYPE` (lokal geprüft), generischer Schreiber statt siebtem `PUT` |
| TASK-06 | Schreibziel nie positionsabhängig, geteilte Liste nur ausdrücklich, Deck nie, 403/404 letzte Instanz | F6: Zielwahl nach `calendar._pick_target`, aber "genau eine eigene beschreibbare Liste"; Spike: nur lesbare Liste antwortet 404, Deck 403 |
| TASK-07 | Bundle, alle Gates, Kanarie mit Aufgabenliste und Deck-Beweis, Doku nachgezogen | F9: Gate-Inventar mit 30 Stellen samt Zeilen |
| TASK-08 | Budget nach Hausregel, kein Werkzeug über 1400 Bytes | F9: Prototyp gemessen, `tasks_create` 1417 Bytes (über der Decke), Summe rund 18840 Bytes (über 18000) |
| TASK-09 | `task:`-Id über `fetch`, Provider `tasks` in `PROVIDER_KINDS`, Deck nie | F8: Serverquelle des Providers (Link, Abos, nur öffentliche Objekte geteilter Listen, Deck nicht in der Datenbank), Linkformen, Prüfung gegen die Discovery |
</phase_requirements>

## Project Constraints (from CLAUDE.md und REQUIREMENTS.md)

- Python 3.13, `uv` als Werkzeugkette, httpx roh für DAV, lxml für XML-Körper, icalendar 7.x für ICS. Keine neue Abhängigkeit für diese Phase nötig. [VERIFIED: pyproject.toml, uv.lock icalendar 7.3.0, lxml 6.1.3, httpx 0.28.1]
- Code und README englisch, Projektkommunikation deutsch, keine Gedankenstriche, echte Umlaute in deutschen Texten.
- Security: der Connector sieht nie mehr als der angemeldete Nutzer; keine destruktiven Writes.
- R1: jeder Plan, der `src/`, `tests/`, `scripts/`, `README*`, `docs/` oder `appinfo/` anfasst, endet mit `pytest tests/unit tests/contract`, `scripts/check_tool_budget.py`, `ruff check`, `ruff format --check`, `pyright` (lokal mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`), `vulture src scripts vulture_whitelist.py`.
- R2: nutzersichtbare Texte dreisprachig; die drei CHANGELOGs bewegen sich im selben Plan.
- R4: vor jedem Push, Merge, Kommentar den Owner fragen; Issue-Antworten erst nach dem Store-Release.
- R5: Annahmen bleiben bis zur Messung als Annahme gekennzeichnet.
- R6: Gegenproben und Probe-Werkzeuge nie unter `src/` (jede `reg_*.py` wird Teil der Oberfläche).
- Commits als `street1983nk <k.cherif@outlook.de>`, ohne Trailer, ohne schließende Schlüsselwörter.
- GSD-Workflow: Änderungen nur über `/gsd:execute-phase`.

## Summary

Die Phase baut auf einer guten Lage auf: der Spike hat Discovery, Abfragen, create-only `PUT` und die Objekte der Tasks-App gemessen, und der Code hat für jedes Teilproblem ein Vorbild (`caldav.py` und `tools/calendar.py` für CalDAV, `paging.py` für Cursor, `mail._capped` für Kappung ohne Marker, `capabilities.load_mail` für eine App ohne Capabilities, `provider_map.py` für Provider-Links). Neu zu bauen sind eine eigene Aufgaben-Discovery mit Schreibrecht und Freigabe-Kennzeichen, ein Leser für `VTODO`, der schwebende Zeiten nicht still nach UTC kippt (anders als `caldav._value_of`), die Filter-, Sortier- und Blätterlogik im Connector, die Kinderabfrage mit eigenem Budget, das Anlegen mit sauberem `VTODO` und das Gate-Paket für drei Werkzeuge.

Drei Befunde ändern die Planung gegenüber dem bisherigen Bild. **K1:** Nextcloud setzt den Namen und die Kennung der teilenden Person selbst in jede geteilte Liste: der `displayname` lautet `<Name> (<Anzeigename des Besitzers>)` und die URI `<uri>_shared_by_<Kontokennung>` [VERIFIED: CalDavBackend.php stable32 Zeile 431 bis 433; gemessen in `tests/fixtures/caldav_home_task_lists.xml`: `spike30-b-rw (bob)`, `.../spike30-b-rw_shared_by_bob/`]. D-32-06 verlangt zugleich "Name, wie Nextcloud ihn anzeigt" und "keine Kennung der teilenden Person in irgendeiner Antwort". Damit dürfen weder der rohe Anzeigename noch eine `task:`-Id, die die Kalender-URI trägt, für geteilte Listen ausgegeben werden. **K2:** Der Suchprovider `tasks` sucht in der Datenbank über eigene Kalender, geteilte Kalender (dort nur Objekte mit `CLASS:PUBLIC`) und Abonnements, nie über Deck [VERIFIED: TasksSearchProvider.php und CalDavBackend::searchPrincipalUri stable32]. Ein Provider-Treffer kann also auf ein Abo zeigen; `fetch` muss jede `task:`-Id gegen die Discovery prüfen. **K3:** Die Elternaufgabe eines Suchtreffers ist nur billig, wenn sie in derselben Antwort steht: `RELATED-TO` trägt die UID, die `task:`-Id braucht aber den Objektnamen, und der ist nicht die UID (A2). Im Modus "offen" fehlt eine erledigte Elternaufgabe in der Serverantwort.

Für D-32-13 liegt die Ursache jetzt im Quelltext vor: `--name` gibt es in `occ user:auth-tokens:add` erst ab Nextcloud 33, und AppAPI kürzt den Port aus dem Daemon-Host erst ab dem Zweig `stable33` (`$host = explode(':', $host)[0];`). Ein Host ohne Port ist damit auf 32 bis 35 die eine Form, die überall den richtigen Heartbeat-Pfad ergibt; `--name` wird per Feature-Erkennung gesetzt, sodass 33 bis 35 unverändert bleiben.

**Primary recommendation:** Eigene Discovery- und Lesefunktionen für Aufgaben neben den unveränderten Kalenderfunktionen, ein generischer create-only-Schreiber in `caldav.py` mit genau einer `.put(`-Stelle, ein stabiler Listenschlüssel ohne Personenbezug für geteilte Listen, Messung (Kinderabfrage, Budgets, Erkennung der Tasks-App, Namensform geteilter Listen) als zweiter Plan direkt nach der Bootstrap-Reparatur und vor dem Code.

## Kernbefunde mit Folgen für die Planung

| # | Befund | Quelle | Folge |
|---|--------|--------|-------|
| K1 | Geteilte Liste: `displayname` = Originalname plus ` (` Anzeigename des Besitzers `)`, URI = `<uri>_shared_by_<uid>` | [VERIFIED: nextcloud/server stable32 `apps/dav/lib/CalDAV/CalDavBackend.php:431-433`], Fixture `caldav_home_task_lists.xml` | Name ohne Zusatz ausgeben; `task:`-Id und Listenparameter mit einem Schlüssel ohne Kennung. Owner-Rückfrage möglich (Offene Frage 1) |
| K2 | Provider `tasks`: Datenbanksuche über eigene, geteilte (nur `CLASS:PUBLIC`) Kalender und Abos; Link `linkToRoute('tasks.page.index') . 'calendars/' . <uri> . '/tasks/' . <objekt>`; leer, wenn die App für den Nutzer aus ist | [VERIFIED: `apps/dav/lib/Search/TasksSearchProvider.php` stable32 bis stable35, `CalDavBackend::searchPrincipalUri` stable32:2478-2560] | `fetch(task:)` immer gegen die Discovery prüfen (Abo, Papierkorb, Deck ablehnen wie unbekannte Id); Deck kommt über den Provider gar nicht, der Präfix-Wächter bleibt trotzdem |
| K3 | `RELATED-TO` = UID, Objektname ≠ UID; Vorfilter "offen" lässt erledigte Eltern weg | Spike 5.3, A2 | Elternverweis nur aus derselben Listenantwort; Hybrid-Vorfilter (F3) |
| K4 | `calendarQuery` filtert jede `VTODO`-Abfrage mit `prop-filter` in PHP nach (lädt und parst alle Objekte der Liste); die SQL-Abkürzung über `firstoccurence`/`lastoccurence` gilt nur für `VEVENT` | [VERIFIED: CalDavBackend.php stable32:1921-2010] | Kinderabfrage kostet etwa so viel wie Modus "offen" (Spike: 108 bis 150 ms Median bei 2000), aber ungemessen: D-32-03 verlangt die Messung |
| K5 | `text-match` ist in sabre immer "contains", Standardkollation `i;ascii-casemap` | [VERIFIED: sabre-io/dav `CalendarQueryValidator.php:238-246`, `StringUtil::textMatch`, `Xml/Filter/PropFilter.php:80-83`] | Kinder exakt im Connector nachprüfen (`RELATED-TO` gleich Eltern-UID, `RELTYPE` fehlt oder `PARENT`); `collation="i;octet"` senden |
| K6 | `--name` existiert ab `stable33`, Standardname `cli`; Ausgabeformat (`app password:` plus Tokenzeile) auf 32 und 35 gleich | [VERIFIED: `core/Command/User/AuthTokens/Add.php` stable32 bis stable35] | Feature-Erkennung per `--help` |
| K7 | AppAPI `ManualActions::resolveExAppUrl`: `stable32` hängt den Port an den Host, wie er ist; `stable33`, `stable34`, `stable35`, `main` schneiden vorher `explode(':', $host)[0]` | [VERIFIED: nextcloud/app_api `lib/DeployActions/ManualActions.php`] | Host ohne Port ist auf allen vier Fassungen richtig; bei 33+ ändert sich nichts |
| K8 | Tasks-App 0.18.1 (aktuell) unterstützt Nextcloud 31 bis 35, registriert keine Capabilities, hat einen Navigationseintrag `tasks.page.index` | [VERIFIED: nextcloud/tasks v0.18.1 `appinfo/info.xml:8,24,27-33`, `lib/AppInfo/Application.php`] | Dieselbe Fassung auf 32 und 35; Erkennung nur über Navigation oder Provider-Liste |
| K9 | Prototyp der drei Schemas: `tasks_create` 1417 Bytes, `tasks_search` 906, `tasks_read` 292; Stand heute 16222 Bytes bei 24 Werkzeugen | [VERIFIED: Messung dieser Recherche, Skript im Scratchpad, Titel-Diät des Servers angewendet] | `tasks_create` muss knapper werden; Budget sicher über 18000, Neuverankerung bei etwa 22000 |
| K10 | `docs/folder-evidence.md` nennt "24 tools" ohne Verweis auf `tests/contract/test_tool_surface.py` | [VERIFIED: grep, Gate `test_a_documented_tool_count_is_the_current_one_or_says_which_run_it_is_from` Zeile 902] | Wird bei 27 Werkzeugen rot, wenn die Seite keinen Verweis bekommt |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Rechteprüfung, Sichtbarkeit von Listen und Objekten | Nextcloud (CalDAV-Backend) | Connector (Vorab-Prüfung aus Discovery) | Der Server entscheidet; der Connector lehnt nur früher und klarer ab (403/404 bleiben letzte Instanz) |
| Discovery und Klassifikation der Listen | Connector, Client-Schicht (`nextcloud/clients/`) | kein | Reine Auswertung eines `PROPFIND`, ohne Werkzeuglogik |
| Status-, Text-, Fälligkeitsfilter, Sortierung, Blättern | Connector, Werkzeugschicht (`tools/tasks.py`) | Server-Vorfilter `COMPLETED` | Der Server kann Text nur je Eigenschaft, Fälligkeit nur mit undatierten und Status nur ohne `CANCELLED` (Spike 5.3) |
| VTODO lesen und bauen | Connector (icalendar) | kein | Zeitform, Escaping, Faltung; nie von Hand |
| Create-only-Schutz | Nextcloud (`If-None-Match: *` in derselben Anfrage) | Contract-Gate (`EXPECTED_PUT_CALLS`) | Kein Vorab-Test, kein Wettlauf (T-01-48) |
| Erkennung der Tasks-App | Nextcloud OCS (Navigation) | Connector-Cache (`capabilities._cache`) | Die App hat keine Capabilities |
| Provider-Treffer zu Id | Connector (`provider_map.py`) | Discovery-Prüfung in `fetch` | Link wird nur geparst, nie abgerufen |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| icalendar | 7.3.0 (Lock) | `VTODO` parsen und bauen | Projektstandard; lokal geprüft: `DUE;VALUE=DATE:20261120`, `DTSTART;VALUE=DATE`, `RELATED-TO:<uid>` ohne `RELTYPE`, `CATEGORIES:a\,b,wichtig`, `SUMMARY` mit `\n`, `\,`, `\;` escaped, `DUE;TZID=Europe/Berlin:...` bei zonierter Zeit [VERIFIED: lokaler Lauf] |
| lxml | 6.1.3 | `PROPFIND`- und `REPORT`-Körper bauen, Antworten über `xml.hardened_parser` lesen | Kein XML-Literal im Code (T-01-45) |
| httpx | 0.28.1 | alle Anfragen über `NcClients` | Projektstandard |
| tzdata / zoneinfo | Stack | IANA-Zonen für `timezone` | wie `calendar.resolve_zone` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | Stack (Tests) | Unit-Tests der Client- und Werkzeugschicht | jeder Statuszweig, jede Fixture |
| `scripts/tasks_spike.py` | Repo | Messprogramm (RAM-Gate, Aufbau von 2000 Aufgaben, Kostenreihe, `provider_link_parts`) | Vorlage für die Messung in Plan 32-02, nie unter `src/` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| eigener `calendar-query` | Nextclouds `{http://nextcloud.com/ns}calendar-search` | Durchsucht nur den Eigenschaftsindex (`SUMMARY`, `DESCRIPTION`, `CATEGORIES` usw., nicht `RELATED-TO`), Blättern und geteilte Listen ungemessen (Spike 11); für Status, Fälligkeit und Kinder ungeeignet. Nicht nehmen |
| `recurring-ical-events` | kein | Keine Expansion in dieser Phase (TASK-02); nicht in `pyproject.toml` und nicht nötig |
| `caldav`-Bibliothek | kein | sync, zweiter HTTP-Stack; im Projekt bewusst abgelehnt (CLAUDE.md) |

**Installation:** keine. Keine neue Abhängigkeit.

## Package Legitimacy Audit

Diese Phase installiert kein externes Paket; alle genutzten Bibliotheken stehen bereits in `uv.lock`. slopcheck wurde deshalb nicht ausgeführt.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (keines neu) | kein | kein | kein | kein | kein | kein |

**Packages removed due to slopcheck [SLOP] verdict:** keine
**Packages flagged as suspicious [SUS]:** keine

Die Tasks-App ist kein Python-Paket, sondern eine Nextcloud-App aus dem App Store (`occ app:install tasks`), Quelle github.com/nextcloud/tasks, Fassung 0.18.1 vom 2026-06-29 [VERIFIED: GitHub-Releases].

## Architecture Patterns

### System Architecture Diagram

```
MCP-Client (Claude, ChatGPT, ...)
   | tools/call tasks_search | tasks_read | tasks_create | fetch(task:...)
   v
server/reg_tasks.py  (@mcp.tool, @graceful, Audit-Zeile, Annotation READ_ONLY / CREATE_ONLY)
   v
tools/tasks.py
   |-- Eingaben prüfen (Status-Enum, Datum/Zone, Priorität 0..9, start < due, Cursor)
   |-- Discovery ----------------------------> PROPFIND Depth 1 calendars/<user>/
   |      Klassifikation: Deck? Papierkorb? Scheduling? resourcetype calendar? VTODO?
   |      -> TaskList(uri, key, name ohne Besitzerzusatz, shared, writable, own)
   |      Home 404 oder keine Liste -> Fall E6 (+ Hinweis Tasks-App, falls sicher erkennbar)
   |
   |-- search: je Liste parallel, je Liste Zeitbudget ---> REPORT calendar-query (VTODO, Vorfilter)
   |      Objekt einzeln parsen, nicht adressierbare überspringen (skipped)
   |      Status / Text / Fälligkeit im Connector, Eltern-UID -> (Objektname, Titel) aus derselben Liste
   |      fehlende Eltern im Modus offen -> zweiter REPORT dieser Liste ohne Vorfilter
   |      ausgefallene Liste -> degraded; alle ausgefallen -> Fehler
   |      sortieren, Fenster [offset, offset+25), Deckel, next-Cursor
   |
   |-- read: Id -> Liste aus Discovery (Deck/Abo/Papierkorb = unbekannte Id) -> GET Objekt
   |      VTODO lesen (Zeitmatrix), Beschreibung kappen, ATTACH nie
   |      Kinder: REPORT text-match RELATED-TO, eigenes Zeitbudget, exakt nachprüfen, Deckel
   |
   |-- create: Ziel nach E4 aus Discovery -> VTODO bauen (icalendar) -> caldav.put_new_object
   |      (If-None-Match: *) -> GET zurücklesen -> confirmed; Hinweis Tasks-App
   v
Nextcloud dav (sabre)  <-- AppAPI-Impersonation oder App-Passwort (Credentials)

Nebenweg TASK-09:
unified_search -> Provider "tasks" -> provider_map.extract_id (Link parsen) -> task:<key>:<objekt>
fetch(task:...) -> chatgpt._fetch_task -> dieselbe Lesefunktion wie tasks_read (Discovery-Prüfung)
```

### Recommended Project Structure (nur Änderungen)
```
src/mcp_connector/
├── ids.py                         # encode_task, parse-Zweig "task", _HINT um task:<list>:<object>
├── provider_map.py                # "tasks": "task", Linkparser (TASK-09, eigener Plan)
├── nextcloud/capabilities.py      # tasks_available: bool | None, Füllung über NAVIGATION_PATH
├── nextcloud/clients/caldav.py    # NUR: generischer create-only-Schreiber, put_event als Hülle
├── nextcloud/clients/tasks.py     # neu: Discovery, Klassifikation, Listenschlüssel, REPORT-Körper, GET, Statusprüfer
├── tools/tasks.py                 # neu: search, read, create, Zeitmatrix, Filter, Sortierung
├── tools/chatgpt.py               # case "task" -> _fetch_task (TASK-09)
├── server/reg_tasks.py            # neu: drei Werkzeuge
└── audit/allowlist.py             # drei Einträge
tests/unit/                        # test_tasks_client.py, test_tasks_tools.py, test_tasks_time_matrix.py, ...
tests/integration/test_tasks_live.py   # Impersonation, NC_MCP_REQUIRE_LIVE-Zweig
scripts/tasks_measure.py (oder Block in tasks_spike.py)  # Messung Plan 32-02
scripts/tasks_chain_evidence.py    # ganze Kette über die installierte ExApp (nach folder_chain_evidence.py)
docs/tasks-evidence.md             # Beleg mit stabilen Ankern
```

Ob die Client-Funktionen in einer neuen Datei `clients/tasks.py` oder in `caldav.py` stehen, ist eine Entscheidung der Planung. Empfehlung: neue Datei, weil `caldav.py` dann nur an genau einer Stelle (Schreiber) wächst und der Diff gegen die Basis für TASK-01 klein und prüfbar bleibt. Das Modulgrenzen-Gate (`tests/contract/test_module_boundaries.py`) verbietet nur Zugriffe auf private Namen von Werkzeugmodulen unter `tools/`; `tools/tasks.py` darf `calendar.parse_instant` und `calendar.resolve_zone` (öffentlich) nutzen, aber nicht `calendar._pick_target` oder `calendar._read_back`.

### Pattern 1: Eigene Discovery, Kalenderkörper unangetastet (TASK-01)

**What:** Ein zweiter `PROPFIND`-Körper nur für Aufgaben, mit `d:displayname`, `d:resourcetype`, `cal:supported-calendar-component-set`, `d:current-user-privilege-set`, `oc:read-only` und (für K1) `{http://nextcloud.com/ns}owner-displayname`. Der heutige Körper `caldav.build_discovery_body` (`caldav.py:158-169`) und `parse_calendar_home` (`:196-231`) bleiben byte-gleich.

**Klassifikation, Reihenfolge nach Spike `classify_collection`** (Kriterien des Spikes, docs/spike-tasks.md Zeile 142 bis 144):
1. Home selbst überspringen.
2. URI beginnt mit `app-generated--`: Deck, ausschließen (auch wenn Typ und Komponenten wie eine Aufgabenliste aussehen, Spike 5.2).
3. resourcetype ohne `{urn:ietf:params:xml:ns:caldav}calendar`: ausschließen. Das trifft Papierkorb (`trash-bin`), gelöschten Kalender (`deleted-calendar`), Abo (`subscribed`), Scheduling (`schedule-inbox`/`-outbox`) [VERIFIED: Spike 5.2 Tabelle].
4. Komponenten-Set ohne `VTODO`: keine Aufgabenliste.
5. `shared` = `oc:read-only` steht in einem 2xx-Propstat (eigene Liste: unter 404; Freigabe mit Schreibrecht: vorhanden und leer; ohne: `1`) [VERIFIED: A4, Spike 5.2]. Zweites Merkmal zur Gegenprobe: `_shared_by_` in der URI.
6. `writable` = `oc:read-only` fehlt oder ist leer, `0`, `false` UND das Privilegien-Set nennt `{DAV:}write` oder `{DAV:}write-content` (Deck: kein Schreibprivileg). Die Discovery ist die Quelle, nie ein Schreibversuch (D-32-06).
7. `own` = nicht `shared`.

**Home 404:** Ein Konto ohne Kalender-Home (nie mit Passwort angemeldet, Spike 5.1: "vor der Anmeldung status=404") muss als Fall E6 enden, nicht als Fehler "Nextcloud does not know ...". `caldav._check` würde 404 als unbekannt melden; der Aufgaben-Client braucht einen eigenen Prüfer. [ASSUMED A1: unter Impersonation liefert das Home eines Kontos ohne Kalender 404 statt einer leeren 207; messen]

**Byte-Beweis für das Kalender-Bundle:** Vor der ersten Änderung an `caldav.py` einen Unit-Test anlegen, der `sha256(caldav.build_discovery_body())` und `sha256(caldav.build_calendar_query(start, end))` für feste Eingaben pinnt; dazu die Prüfung "`git diff <Basis> -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py` ist leer" in jedem Plan, der `caldav.py` berührt (Muster `31-BASE.txt`).

### Pattern 2: Listenschlüssel ohne Personenbezug (K1, Entscheidung der Planung, Owner-Bestätigung empfohlen)

**What:** `task:<listenschlüssel>:<objektname>`. Für eigene Listen ist der Schlüssel die URI (lesbar, wie bei `event:`). Für geteilte Listen ein deterministischer Schlüssel aus der URI, der die Kontokennung nicht im Klartext trägt, zum Beispiel `s` plus die ersten 16 Hexzeichen von `sha256(uri)`. Auflösung immer über die Discovery (die ohnehin für TASK-01 läuft): jede Liste berechnet ihren Schlüssel, Treffer per Gleichheit.

**Warum nicht die URI:** `spike30-b-rw_shared_by_bob` nennt die Kennung `bob`; D-32-06 verbietet das in jeder Antwort des Bundles, und die Id steht in jeder Antwort.

**Grenzen, offen zu nennen:** Der Schlüssel ist pseudonym, nicht anonym (wer Basis-URI und Kennung rät, kann ihn nachrechnen). Er bleibt stabil, solange die Freigabe besteht. Eine Kollision mit einer eigenen URI der Form `s<16 hex>` ist praktisch ausgeschlossen und wird durch die Discovery-Auflösung (beide Schlüssel gleich: Fehler "mehrdeutig") abgefangen.

**Listenname (D-32-06):** Für geteilte Listen den Zusatz ` (<owner-displayname>)` am Ende genau dann entfernen, wenn der `displayname` mit genau diesem Zusatz endet; `owner-displayname` wird gelesen, aber nie ausgegeben. Passt der Zusatz nicht, ist der Ersatzname der URI-Teil vor `_shared_by_`. [ASSUMED A2: `{http://nextcloud.com/ns}owner-displayname` per `PROPFIND` abrufbar und gleich dem Text, den `userManager->getDisplayName` in den Namen setzt; messen auf 32 und 35]. Der Namensraum ist `http://nextcloud.com/ns` (Sharing-Plugin `NS_NEXTCLOUD`), nicht der `xml.NC = "http://nextcloud.org/ns"` des Projekts [VERIFIED: `apps/dav/lib/DAV/Sharing/Plugin.php:29-30`].

### Pattern 3: Generischer create-only-Schreiber (EXPECTED_PUT_CALLS bleibt 6)

**What:** Das Gate zählt `.put(`-Aufrufe im AST, nicht Aufrufer (`test_no_destructive_calls.py:476-575`). Heute gibt es genau einen `PUT` in `caldav.py` (`put_event`, Zeile 351). Der "generische create-only-Schreiber" ist diese eine Stelle, umgebaut zu einer Funktion mit Wortlaut als Parameter; `put_event` bleibt als Hülle mit exakt den heutigen Meldungen.

```python
# Skizze, caldav.py. Genau ein .put( bleibt in der Datei.
@dataclass(frozen=True, slots=True)
class WriteWording:
    replaced: str      # heute: "Nextcloud reports that the write replaced an existing event {name} (status {status})."
    exists: str        # heute: "An event object named {name} already exists."
    ...                # je Zweig von _check_write (Zeile 447-491)

EVENT_WORDING = WriteWording(...)  # die heutigen Sätze, Wort für Wort

async def put_new_object(client, creds, collection_uri, object_name, ics_bytes, wording) -> dict[str, Any]:
    response = await client.put(
        object_url(creds, collection_uri, object_name),
        content=ics_bytes,
        headers={"If-None-Match": "*", "Content-Type": "text/calendar; charset=utf-8"},
        auth=creds.auth(),
    )
    _check_new_object(response, collection_uri, object_name, wording)
    return {...}

async def put_event(client, creds, calendar_uri, object_name, ics_bytes) -> dict[str, Any]:
    return await put_new_object(client, creds, calendar_uri, object_name, ics_bytes, EVENT_WORDING)
```

Die Aufgabenseite übergibt eigenen Wortlaut. Besonderheit: eine nur lesbare geteilte Liste antwortet auf `PUT` mit **404** "could not be found", nicht 403; ein Deck-Kalender mit 403 (Spike 3.3, 5.2, 9.3). Die Vorab-Prüfung aus der Discovery macht beide Fälle zur Ausnahme; der Satz für 404 darf nicht "die Liste existiert nicht" behaupten, sondern "nicht vorhanden oder ohne Schreibrecht" (D-31-09: nur sagen, was sicher ist).

Alternative ohne Umbau: `put_event` direkt aufrufen. Dann tragen Aufgaben-Fehler Kalendersätze ("Call calendar_list_events ..."), also falsch. Nicht nehmen.

### Pattern 4: Zeitmatrix beim Lesen (TASK-04)

| Form im Objekt | Ausgabe | Hinweis |
|----------------|---------|---------|
| `DUE;VALUE=DATE:20261120` | `"due": "2026-11-20"` | nie Mitternacht, nie Folgetag |
| `DUE:20261120T090000Z` | `"due": "2026-11-20T09:00:00+00:00"` | Form der Tasks-App (A3) |
| `DUE;TZID=Europe/Berlin:20261120T090000` | `"due": "2026-11-20T09:00:00+01:00"` | Zone aus `VTIMEZONE`/IANA; von Hand gebautes Testobjekt (A3: App schreibt kein `TZID`) |
| `DUE:20261120T090000` (schwebend) | `"due": "2026-11-20T09:00:00"` plus Kennzeichen, zum Beispiel `"due_floating": true` | nie still zu UTC; `caldav._value_of` (`caldav.py:412-424`) tut genau das und darf nicht wiederverwendet werden |
| kein `DUE` | Feld fehlt | kein |

Dieselbe Matrix für `DTSTART` und `COMPLETED` (A3: `COMPLETED` immer UTC). Jede Zeile ist ein benannter Test (Erfolgskriterium 4). Feldnamen sind Entscheidung der Planung.

### Pattern 5: Anlegen (TASK-05, TASK-06)

- `due` ohne Uhrzeit (`YYYY-MM-DD`) ergibt `datetime.date` und damit `DUE;VALUE=DATE` [VERIFIED: icalendar-Lauf]. `_all_day_window` (`calendar.py:345-357`) wird nicht benutzt: es verschiebt das Ende um einen Tag.
- `due` mit Uhrzeit: `calendar.parse_instant` (Zone Pflicht, `calendar.py:129-145`). Mit `timezone`: Zeit in dieser Zone schreiben und `VTIMEZONE` erzeugen wie `calendar.build_ics` (`:404-416`); ohne `timezone`: UTC mit `Z` (wie die Tasks-App, A3).
- `start` muss denselben Werttyp haben (Datum gegen Datum, Zeit gegen Zeit) und vor `due` liegen; sonst Ablehnung vor dem Request.
- `priority` 0 bis 9 (Pydantic `ge=0, le=9` im Schema plus Prüfung in der Funktion für Python-Aufrufer).
- `tags` als `CATEGORIES` in einer Zeile; Leerwerte und Duplikate verwerfen; ein Komma im Tag escaped icalendar selbst.
- `parent`: eine `task:`-Id. Auflösen gegen die Discovery, `GET` der Elternaufgabe für ihre UID, `RELATED-TO:<uid>` ohne `RELTYPE` (A2). Die Elternaufgabe muss in der Zielliste liegen (Tasks-App-Verhalten, A2). Ob ein `parent` in einer geteilten Liste als "ausdrückliche Nennung" der Liste gilt, ist offen (Offene Frage 3); Empfehlung der Recherche: nein, die Regel aus E4 gilt unverändert, die Fehlermeldung nennt den Ausweg `list`.
- Pflichtfelder des Objekts: `UID` (frische UUID), `DTSTAMP`, `CREATED`, `LAST-MODIFIED` (UTC), `SUMMARY`; `PRODID` wie `calendar.PRODID` oder ein eigener.
- Objektname: `<uuid>.ics`, UID gleich Objektname ohne `.ics` (wie `calendar.create_event`, `calendar.py:290-291`).
- Zielwahl (E4, TASK-06): `list` gesetzt: Auflösung gegen Discovery (URI, Schlüssel oder Name ohne Besitzerzusatz, `casefold`), Mehrdeutigkeit ist ein Fehler mit Kandidaten (Name, geteilt, Schlüssel). Ohne `list`: genau eine Liste mit `own and writable`, sonst Fehler mit den Namen. Nie ein Deck-Kalender (schon von der Discovery ausgeschlossen). Ziel nicht beschreibbar: Ablehnung vor dem Request.
- Rücklesen wie `calendar._read_back` (`calendar.py:322-342`): ein Fehler beim Rücklesen macht den Schreibvorgang nie zum Fehlschlag, `confirmed: false`.

### Pattern 6: Erkennung der Tasks-App (D-32-10)

| Weg | Kosten | Fehlerbild | Status |
|-----|--------|-----------|--------|
| `GET /ocs/v2.php/core/navigation/apps`, Eintrag mit `app` oder `id` gleich `tasks` | eine OCS-Anfrage je 60 s Cache-Fenster, nur in den zwei Fällen mit Hinweis | Antwort leer oder kein Array: ungeklärt, Hinweis entfällt (wie `_navigation_lists_mail`) | Mechanismus für Mail gemessen (Nextcloud 34.0.3, `capabilities.py:51-58`); für `tasks` gelesen: Navigationseintrag `tasks.page.index` [VERIFIED: tasks info.xml]; unter Impersonation für `tasks` ungemessen |
| `GET /ocs/v2.php/search/providers`, Id `tasks` in der Liste | eine OCS-Anfrage | Provider steht nur, wenn `getOrder` für den Sitzungsnutzer `isEnabledForUser('tasks')` liefert | gemessen mit App-Passwort auf 35.0.2 (Spike 5.4: `tasks_dabei=ja/nein`) [VERIFIED: TasksSearchProvider.php `getOrder`]; unter Impersonation ungemessen |
| OCS-Capabilities | kein | die Tasks-App hat keinen Abschnitt | ausgeschlossen [VERIFIED: tasks v0.18.1 `Application::register` registriert nur Dashboard-Widget und Listener] |
| `occ` oder `/cloud/apps` | Admin-Recht | kein | für einen Nutzer-Connector ausgeschlossen |

**Empfehlung:** Navigation, im selben Cache-Eintrag wie Mail (`capabilities.load_mail` als Vorbild, dreiwertiges Feld `tasks_available: bool | None`, Eintrag in `Capabilities.has`). Kein zweiter Modulzustand (`ALLOWED_MODULE_STATE`, `test_no_destructive_calls.py:360-365`). Nie `require_app`: die Werkzeuge arbeiten ohne App (D-32-10). Fehler, Zeitüberschreitung oder deformierte Antwort heißen "nicht erkennbar", der Hinweis entfällt. Vor dem Bau messen: an, aus, nach `occ app:disable tasks` ohne Neustart und nach Neustart, auf 32 und 35 unter Impersonation [ASSUMED A3].

**Achtung Zwischenspeicher:** Die Erkennungswege aller Familien antworten nach `app:disable` die alte Wahrheit, bis der PHP-Prozess neu ist (gemessen für Talk, Tables, Mail in `tests/integration/test_srv06_degradation.py:166-185`). Der Lauf "ohne Tasks-App" braucht einen Neustart des Nextcloud-Containers oder eine Instanz, auf der die App nie installiert war.

### Anti-Patterns to Avoid
- **`parse_calendar_home` erweitern oder `build_discovery_body` um Eigenschaften ergänzen:** bricht die Byte-Gleichheit des Kalender-Bundles.
- **`caldav.parse_ics` oder `caldav._value_of` für Aufgaben:** walkt nur `VEVENT`, wirft für die ganze Liste bei einem kaputten Objekt, und macht schwebende Zeiten still zu UTC.
- **Fälligkeit per `time-range` im Server:** liefert undatierte Aufgaben mit (Spike 5.3).
- **Status "offen" allein über `COMPLETED is-not-defined`:** liefert `CANCELLED` mit (Spike 5.3).
- **Kinder ohne exakte Nachprüfung:** `text-match` ist "contains" (K5).
- **Id aus der URI einer geteilten Liste:** trägt die Kontokennung (K1).
- **Schreibrecht durch Schreibversuch feststellen:** verboten durch D-32-06; außerdem antwortet der Server mit 404.
- **Provider-Link abrufen:** nur parsen, nie anfragen (T-01-68).

## Antworten auf die zwölf Fragen des Auftrags

### F1: D-32-13, die zwei Stellen in `scripts/bootstrap_exapp.sh`

**Was die Quellen sagen**
- `occ user:auth-tokens:add`: `stable32` kennt nur `--password-from-env`; `stable33`, `stable34`, `stable35` haben `--name` ("defaults to cli"); `stable35` zusätzlich `--login-name`. Ausgabe auf allen: Zeile `app password:`, dann der Token [VERIFIED: `core/Command/User/AuthTokens/Add.php` je Zweig]. Gemessen auf 32.0.15: "The \"--name\" option does not exist." (`raw/nc32-strecke.txt`, Abschnitt N4).
- Heartbeat-URL für `manual-install`: `ManualActions::resolveExAppUrl` baut `sprintf('%s://%s:%s', $protocol, $host, $port)`; ab `stable33` steht davor `$host = explode(':', $host)[0];` [VERIFIED: nextcloud/app_api je Zweig]. Auf 32 ergibt `host.docker.internal:23001` also `host.docker.internal:23001:23001` (gemessen, "Invalid host"); ohne Port `host.docker.internal:23001` (gemessen, Registrierung im ersten Versuch). Auf 33 bis 35 ist der Host mit oder ohne Port gleichwertig. Der HaRP-Zweig (Standardmodus und CI) baut `nextcloud_url/exapps/<appid>` und ist nicht betroffen.
- Wer welche Form nutzt: CI (`exapp` auf 34.0.3, `canary-nc35` auf 35.0.1) läuft im Standardmodus über HaRP, nie mit `--manual` [VERIFIED: `.github/workflows/ci.yml`]. `--manual` und `--nc35` schließen sich aus (`bootstrap_exapp.sh:80-84`). `register_manual_install` registriert den Daemon nur, wenn er fehlt (`:1287-1297`): bestehende Volumes behalten ihren Eintrag.

**Empfehlung für den Umbau**
1. `--name` per Feature-Erkennung: `occ user:auth-tokens:add --help` lesen, `--name` nur mitgeben, wenn die Hilfe es nennt. Auf 33 bis 35 bleibt der Aufruf wörtlich wie heute (Token heißt weiter `mcp-exapp`), auf 32 heißt er `cli`. Keine Versionsnummer vergleichen. `grep` ohne `-q` auf einer Pipe (SIGPIPE mit `pipefail`, Kommentar `bootstrap_exapp.sh:275-280`).
2. Daemon-Host ohne Port: `"host.docker.internal"` statt `"host.docker.internal:${MANUAL_APP_PORT}"`. Nach der Quelle verhält sich 33 bis 35 identisch; D-32-13 verlangt trotzdem die Messung vorher.
3. Gleiche `--name`-Stelle steckt in `scripts/bootstrap_test_nc.sh:219` und `scripts/bootstrap_spike_opendesk.sh:906`. `compose.test.yml` nutzt `nextcloud:34-apache`, also nicht betroffen; nicht Teil von D-32-13, nur benennen.
4. Unit-Test im Stil von `tests/unit/test_exapp_env_setup.py`, der beide neuen Formen im Skripttext pinnt (die Datei liest das Skript bereits, Zeile 49, 1296-1312).

**Was vorher gemessen werden muss (ohne Registrierung, wenig RAM)**
- Je Fassung 32.0.15 (Volume `nc-mcp-exapp`), 34.0.x (Wegwerf-Instanz aus `compose.spike-tags.yml` wie im Spike) und 35.0.0 (`nc35`): `occ status`, `occ app:list` (Fassung von `app_api`), `occ user:auth-tokens:add --help`, und ein PHP-Einzeiler im Container, der `ManualActions::resolveExAppUrl` mit Host mit und ohne Port aufruft und die URL ausgibt. Das prüft genau die Funktion der ausgelieferten Fassung, ohne eine zweite App zu registrieren. [ASSUMED A4: die ausgelieferten AppAPI-Fassungen von 34.0.x und 35.0.0 entsprechen dem Code der Zweige; die Messung schließt das]
- Danach auf 32: `bash scripts/bootstrap_exapp.sh --manual` bis zum Ende (schreibt `.env.exapp`, stellt Testpost neu zu); lokaler Prozess mit genau den fünf Namen `APP_ID`, `APP_SECRET`, `APP_VERSION`, `NC_MCP_URL`, `NC_MCP_PUBLIC_URL` (sonst Unix-Socket wegen `HP_SHARED_KEY`, 31-05b-SUMMARY).
- CI nach dem Push: `exapp` und `canary-nc35` unverändert grün (Owner-Freigabe für Push nötig, R4).

### F2: Discovery nach TASK-01 ohne Änderung am Kalender-Bundle

Geteilt werden dürfen (unverändert, nur aufgerufen): `calendars_home_url`, `calendar_url`, `object_url`, `safe_segment`, `to_caldav_utc`, die `xml`-Helfer und der neue generische Schreiber. Nicht geteilt werden: `build_discovery_body`, `parse_calendar_home`, `_is_own_event_calendar`, `query_events`, `get_event`, `parse_ics`, `_value_of`, `_check`, `_check_write`-Wortlaut, `_NO_CALENDAR`, `_URI_HINT`. `_ok_props` (`caldav.py:234-244`) ist privat; entweder öffentlich machen (ohne Verhaltensänderung) oder in `clients/tasks.py` nachbauen. Der Rest der Discovery steht in Pattern 1 und 2.

Ableitung, nicht gemessen: Der heutige Terminfilter ließe einen gelöschten Kalender mit `VEVENT` durch (Spike 5.2, 11). TASK-01 verbietet eine Änderung; der Befund gehört als Notiz in den Beleg, nicht in diese Phase.

### F3: Abfragen für `tasks_search` (TASK-02, D-32-05 bis D-32-09)

| Merkmal | Server | Connector | Beleg |
|---------|--------|-----------|-------|
| nur `VTODO` | `comp-filter VCALENDAR/VTODO` | kein | Spike 5.3 |
| offen | Vorfilter `COMPLETED is-not-defined` spart Bytes (70274 statt 1521874 bei 2000), kaum Zeit (108 statt 148 ms) | `CANCELLED` aussortieren; Status aus `STATUS`, sonst `COMPLETED` vorhanden = erledigt | Spike 5.3, 6 |
| erledigt | Vorfilter `COMPLETED is-defined` möglich | `STATUS:COMPLETED` oder `COMPLETED` vorhanden | Spike 5.3 |
| alle | ohne Vorfilter | kein | kein |
| Text | nicht nutzen (`text-match` je Eigenschaft, `allof`, keine `anyof`-Kombination über Eigenschaften) | `casefold` über `SUMMARY`, `DESCRIPTION`, `CATEGORIES` (alle Zeilen) | Spike 11 ("TASK-02 filtert Text ohnehin im Connector") |
| Fälligkeitsgrenze | nicht nutzen (`time-range` liefert undatierte) | nur Objekte mit `DUE`; Vergleich Datum gegen Grenze in der Zone der Grenze | Spike 5.3 |
| wiederkehrend | keine Expansion | `recurring: true` bei `RRULE` oder `RDATE`; Master ist die Komponente ohne `RECURRENCE-ID` | TASK-02 |
| Elternverweis | kein | Map `UID -> (Objektname, Titel)` aus derselben Listenantwort | K3 |

**Vorfilter und Elternverweis, Varianten mit Kosten (Spike 6, 2000 Aufgaben, Median SQLite/PostgreSQL):**
- V-A, immer ohne Vorfilter: 148/186 ms, 1,52 MB je Liste und Seite; Elternverweise vollständig in jeder Antwort.
- V-B, Hybrid (Empfehlung): Modus offen mit Vorfilter (108/150 ms, 70 KB); fehlt für ein offenes Kind die Elternaufgabe in der Antwort, ein zweiter `REPORT` dieser einen Liste ohne Vorfilter. Modus erledigt und alle ohne Vorfilter, weil erledigte Kinder offener Eltern der Normalfall sind ("Was habe ich diese Woche geschafft?").
- V-C, nur UID ohne Id und Titel: verletzt D-32-04. Nicht nehmen.
- Eltern in einer anderen Liste (vom Spike nicht gemessen, Tasks-App hält sie in derselben Liste): Elternverweis ohne Id und Titel mit ehrlichem Kennzeichen, zum Beispiel `"parent": {"found": false}`; Feldform Entscheidung der Planung.

**Sortierung:** offene (inklusive `IN-PROCESS`) vor erledigten vor abgebrochenen; innerhalb nach Fälligkeit, undatierte ans Ende; Gleichstand nach Titel `casefold`, dann Id, damit das Blättern deterministisch ist. Ein Datum gegen eine Zeit: Datum als Beginn des Tages in UTC vergleichen oder als Ende des Tages ist eine Festlegung, die die Planung trifft und testet (Annahme der Recherche: Datum vor Zeiten desselben Tages).

**Blättern:** zustandsloser Cursor nach `paging.encode_cursor` mit `o` (Offset) und den Bereichsschlüsseln (`q`, Status, Grenze, Liste), geprüft mit `paging.check_scope` wie `files_search` (`tools/files.py:179-182, 227`). Jede Seite fragt die Listen neu ab. Harter Deckel nach `files_search`: Offset plus 25 höchstens `MAX_RESULTS` (Vorschlag 500, also 20 Seiten), sonst `note` "result window capped at 500 tasks; narrow with query, list or due_before" nach `SEARCH_CAP_NOTE` (`tools/files.py:91, 228-233`). Die Zahl ist Entscheidung der Planung; sie sollte aus der Messung der Antwortgröße folgen.

**Degraded und Budget:** `asyncio.gather(..., return_exceptions=True)` mit `asyncio.timeout` je Liste wie `calendar._query_one` (`calendar.py:224-249`), `degraded: [{"list": <Name ohne Besitzer>, "reason": ...}]`; alle Listen ausgefallen: Fehler wie `calendar.py:105-111`. Zeitbudget je Liste: Spike-Vorschlag 1 s ist eine Untergrenze ohne Netzwerkstrecke und ohne Impersonation; das Kalender-Bundle nutzt 20 s. Empfehlung: in Plan 32-02 unter Impersonation auf nc35 mit 2000 Aufgaben messen, Budget = doppelter Maximalwert, aufgerundet, mindestens 1 s, und mit einer Netzwerkreserve begründen.

**Nicht adressierbares Fremdobjekt:** je Objekt `try` um Parsen und Id-Bau. Gründe zum Überspringen: kein gültiges iCalendar, kein `VTODO`, Objektname mit `:` (der Codec lehnt ihn in `ids._join` ab, `ids.py:236-249`), leerer Objektname. Zählen als `skipped` wie `unified_search` (`tools/search.py:205-208`), die Liste bleibt.

**Limit-Politik vorab:** Seitengröße 25 fest (kein `limit`-Parameter spart Schemabytes), Deckel wie oben, Antwortgröße je Liste ungedeckelt unterhalb von 2000 Objekten (Ableitungsregel des Spikes), oberhalb gilt das Zeitbudget. Ein eigener Bytedeckel je Liste ist möglich (httpx-Streaming), aber ungemessen; als Entscheidung der Planung festhalten und testen.

### F4: Kinderliste in `tasks_read` (D-32-01 bis D-32-03)

**REPORT-Körper (Skizze, mit lxml zu bauen):**
```xml
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><d:getetag/><c:calendar-data/></d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VTODO">
        <c:prop-filter name="RELATED-TO">
          <c:text-match collation="i;octet">PARENT-UID</c:text-match>
        </c:prop-filter>
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>
```
Gemessen auf 32 bis 35: liefert genau die Unteraufgabe (Spike 5.3 Zeile "eltern"). Danach exakt nachprüfen: eine `RELATED-TO`-Zeile mit Wert gleich der Eltern-UID und `RELTYPE` fehlt oder `PARENT` (K5).

**Kosten:** Der Server lädt und parst bei jedem `prop-filter` alle Objekte der Liste (K4); erwartbar ist die Größenordnung des Modus offen (108 bis 150 ms bei 2000), die Antwort ist klein. Ungemessen, D-32-03 verlangt die Messung.

**Messplan (Plan 32-02):** Wegwerf-Instanz 35.0.2 mit SQLite und PostgreSQL wie MESS-04 (Aufbau 2000 Aufgaben, 1900 erledigt), zusätzlich eine Elternaufgabe mit 0, 1 und 25 Kindern; Reihe `KOSTEN kinder` mit drei Aufwärmläufen und 15 Messläufen, Wanduhr und Bytes; danach auf nc35 unter Impersonation eine kleinere Reihe, um den Aufschlag der Impersonation zu sehen. Budget nach derselben Ableitungsregel (doppelter Maximalwert, aufgerundet, mindestens 1 s).

**Zeitbudget und Hinweis:** eigener `asyncio.timeout` nur um die Kinderabfrage; bei Zeitüberschreitung, `ToolError`, `httpx.RequestError` oder Parse-Fehler: Aufgabe ohne Kinderfeld, dafür zum Beispiel `"subtasks_unavailable": "The subtasks could not be read within N seconds."`. Eine leere Liste `"subtasks": []` nur bei geantworteter Abfrage. **Deckel:** Vorschlag 50 Kinder, darüber `"subtasks_truncated": true` plus Gesamtzahl (die Antwort ist ohnehin vollständig da, die Zahl ist ehrlich). Feldnamen Entscheidung der Planung.

**Elternverweis im Suchtreffer** (D-32-04): siehe F3. Klar gesagt: nur die UID ist ohne Zusatzkosten sicher; Id und Titel kosten im Modus offen gelegentlich einen zweiten `REPORT` je betroffener Liste (V-B) oder immer die volle Liste (V-A).

### F5: Listenangaben je Treffer (D-32-06)

- `name`: `displayname` ohne Besitzerzusatz (Pattern 2), bei eigenen Listen unverändert; fehlt der `displayname`, die URI (wie `parse_calendar_home`, `caldav.py:228-230`).
- `shared`: `oc:read-only` in 2xx-Propstat vorhanden (A4); keine Personendaten nötig.
- `writable`: aus `oc:read-only` und Privilegien-Set, nie aus einem Schreibversuch.
- Fremdtext: Listenname, Titel, Beschreibung und Tags stammen bei geteilten Listen von anderen Personen; jeder dieser Texte läuft durch `marks.without_marks` (BL-09, `tools/chatgpt.py:43-52`).
- Nebenbefund: der Suchprovider `tasks` hängt auf 34 und 35 den `displayname` der Liste in Klammern an die `subline` an [VERIFIED: TasksSearchProvider.php stable34:174-176, stable35:175-176]; bei geteilten Listen steht darin der Besitzername. Das betrifft `unified_search` und `search` (Bundle `search`, `chatgpt`), nicht das Bundle `tasks`, und ist heute schon so. Benennen, nicht in dieser Phase ändern.

### F6: `tasks_create` (TASK-05, TASK-06)

Siehe Pattern 3 und 5. Ergänzungen:
- Der Werkzeugparameter heißt auf dem Draht `list` (E7). ruff wählt die Regelgruppe `A` (`pyproject.toml`), ein Python-Parameter `list` meldet A002; also `# noqa: A002` an genau dieser Stelle in `reg_tasks.py` und Weitergabe als `list_name=` an `tools/tasks.py`, oder ein Pydantic-Alias (im Projekt bisher nicht genutzt, ungeprüft). Empfehlung: `noqa` mit Begründung.
- `tasks_create` liegt im Prototyp bei 1417 Bytes (K9). Kürzere Beschreibungen sind nötig; die Decke wird nie angehoben (`check_tool_budget.py`).
- Rücklesen über `GET` (wie `calendar._read_back`), parsen mit dem Aufgabenleser; `confirmed` wahr nur, wenn das Objekt lesbar war und `UID` übereinstimmt.
- Hinweis zur Tasks-App (D-32-10) einmal in der Erfolgsantwort, nur wenn die Erkennung sicher "aus" sagt.

### F7: Tasks-App erkennen (D-32-10)

Siehe Pattern 6. Zusammengefasst: kein Capabilities-Weg; zwei Nutzerwege (Navigation, Provider-Liste), beide hängen am selben `isEnabledForUser`, beide sind unter Impersonation für `tasks` ungemessen, beide altern bis zum Neustart des PHP-Prozesses. Navigation ist der Weg, den das Projekt schon für Mail baut und testet; Empfehlung daher Navigation. Trägt die Messung in Plan 32-02 nicht (zum Beispiel falsche Antwort unter Impersonation), entfällt der Hinweis ganz.

### F8: TASK-09, `task:`-Id über `fetch` und Provider `tasks`

- `ids.py`: `encode_task(list_key, object_name)` über `_join`; Zweig `kind == "task"` mit genau zwei Segmenten wie `event` (`ids.py:213-222`); `_HINT` (`:39-43`) um `task:<list>:<object>` ergänzen. `_HINT` ist nirgends in Tests wörtlich gepinnt [VERIFIED: grep], ändert aber den Fehlertext aller Id-Ablehnungen; das betrifft nicht das Kalender-Bundle (das `ids.parse` nicht ruft).
- `provider_map.PROVIDER_KINDS`: `"tasks": "task"` mit Kommentar "Verified against nextcloud/server stable32 bis stable35 TasksSearchProvider.php" (Stil der Datei, `provider_map.py:55-85`). Linkparser: Segmentfolge `apps`, `tasks`, `calendars`, `<uri>`, `tasks`, `<objekt>` im Pfad (mit oder ohne `index.php`, gemessen ohne `index.php` auf 35.0.2, Spike 5.4) und zur Sicherheit im Fragment nach `#/` (ältere Tasks-Fassungen). Jede andere Form: `url`-Kind, nicht raten (Spike-Kriterium `provider_link_parts`). URI und Objektname per `unquote`; Schlüssel per derselben reinen Funktion wie im Bundle (Pattern 2), damit `extract_id` ohne Discovery auskommt. `canonical=True`.
- `tools/chatgpt.py`: `case "task": return await _fetch_task(...)` (`chatgpt.py:236-256`), Lesen über dieselbe Funktion wie `tasks_read` inklusive Discovery-Prüfung: Liste muss Aufgabenliste sein (kein Deck, kein Abo, kein Papierkorb), sonst dieselbe Antwort wie bei unbekannter Id. Der Präfix `app-generated--` wird zusätzlich vor jeder Anfrage abgelehnt. `text` ohne Marker (`marks.without_marks`), `metadata.kind = "task"`.
- `url` der Antwort (OpenAI verlangt nicht leer): für eigene Listen der Deep-Link `{base}/index.php/apps/tasks/calendars/<uri>/tasks/<objekt>`; für geteilte Listen trägt der Deep-Link `_shared_by_<uid>`. Empfehlung: dann `{base}/index.php/apps/tasks/` ohne Deep-Link (Offene Frage 2). [ASSUMED A5: die `index.php`-Form öffnet die Aufgabe auch auf Instanzen mit hübschen URLs; messen]
- Abos: der Provider liefert auch Objekte aus Abonnements (K2); `fetch` lehnt sie über die Discovery ab. Das ist eine ehrliche Lücke ("Treffer nicht auflösbar"), keine Fehlauflösung. Ob `extract_id` solche Treffer schon als `resolvable: false` markieren kann, ist ohne Discovery nicht entscheidbar; nicht versuchen.
- Ohne Tasks-App: der Provider fehlt in der Liste und antwortet leer (Spike 5.4); `unified_search` sagt also "nichts gefunden" statt falsch. Das ist der Lauf "ohne" aus D-32-11.
- `tests/contract/provider_classes.py` führt `tasks` bereits als `NO_FILE` [VERIFIED: Zeile mit `"tasks": "Names a task by its summary and links to the tasks app."`]; das Live-Gate `test_provider_classes_live.py` bleibt grün, wenn die App im CI installiert wird.
- `tests/contract/tool_classes.py`: Begründung von `fetch` (`FILE_READERS`) nennt die Kinds; der neue Kind `task` adressiert keine Datei, der Satz bleibt wahr, kann aber `task` als nicht-Datei-Kind nennen.

### F9: Gates nach TASK-07 und TASK-08 (Inventar)

| # | Datei:Zeile | Heute | Änderung |
|---|-------------|-------|----------|
| 1 | `src/mcp_connector/server/reg_tasks.py` | fehlt | neu: drei Werkzeuge, `READ_ONLY`/`CREATE_ONLY`, `@graceful`, `structured_output=False`; Bundle-Name `tasks` folgt aus dem Dateinamen (`server/__init__.py:179-189`) |
| 2 | `src/mcp_connector/audit/allowlist.py:45-72` | 24 Einträge | `tasks_search`: Cursor, Grenze, Liste, Suchbegriff, Status; `tasks_read`: Id-Parameter; `tasks_create`: `due`, `list`, `parent`, `priority`, `start`, `timezone`. `summary`, `description` stehen schon in `FORBIDDEN_PARAMS` (`:23-34`); Empfehlung: `tags` als Nutzlast dort ergänzen (getippter Text), Entscheidung der Planung |
| 3 | `tests/contract/test_tool_surface.py:44-69` `EXPECTED_TOOLS` | 24 | plus drei |
| 4 | `test_tool_surface.py:75-82` `CREATE_TOOLS`, `:800` `len(CREATE_TOOLS) == 6` mit Satz "stay six" | 6 | `tasks_create` aufnehmen, 7, Satz und Docstrings (`:786-792`) nachziehen. Nicht verwechseln mit `EXPECTED_PUT_CALLS = 6`, das bleibt |
| 5 | `test_tool_surface.py:568-573` | `len(tools) == 24`, "twenty-four" | 27 |
| 6 | `test_tool_surface.py:857` | "all 24 schemas" | 27; `FORBIDDEN_PROPERTIES` (`:96`) prüft automatisch, dass kein Parameter `uid`, `user`, `owner` heißt |
| 7 | `test_tool_surface.py:872-899` README-Rechtetabelle | liest nur `README.md` | drei Zeilen: `tasks_search` read, `tasks_read` read, `tasks_create` create-only |
| 8 | `tests/contract/test_tool_bundles.py:23-45, 84-96` | elf Bundles | `"tasks": frozenset({...})`, Name in der Liste |
| 9 | `tests/contract/tool_classes.py:89-119` `UNAFFECTED` | 7 | drei Einträge mit Satz und `file:line`-Anker, mindestens 20 Zeichen (`MIN_REASON`, `:121`); Inhalt: kein `ATTACH`, keine Datei |
| 10 | `tests/contract/test_tool_classes.py:19, 101-115` | `TOTAL = 24`, `(13, 4, 7)` | 27, `(13, 4, 10)` |
| 11 | `tests/contract/test_no_destructive_calls.py:480` | `EXPECTED_PUT_CALLS = 6` | unverändert; der neue Schreiber ersetzt den `PUT` in `caldav.py`, statt einen zu ergänzen. `test_every_put_carries_a_usable_precondition` prüft das Literal `If-None-Match: "*"` im Header-Dict, also das Dict nicht in eine Variable auslagern |
| 12 | `tests/contract/test_audit_surface.py` | prüft Allowlist gegen Oberfläche | grün durch #2 und `@graceful` |
| 13 | `tests/contract/test_module_boundaries.py` | AST-Gate | kein Zugriff von `tools/tasks.py` auf private Namen anderer Werkzeugmodule |
| 14 | `src/mcp_connector/ids.py:39-43, 213-222` | kein `task` | `encode_task`, Zweig, `_HINT`; Rundlauftest in `tests/unit/test_ids.py` (TASK-07) |
| 15 | `tests/unit/test_injection_corpus.py` | Datei, Termin, Mail, Chat | Aufgabe: Titel, Beschreibung (gekappt) und Tags mit `INJECTION` aus geteilter Liste kommen wörtlich und nur im Inhaltsfeld an; dazu eine gefälschte Markerfolge, die gefiltert wird |
| 16 | `tests/integration/test_canary.py:63, 76-89, 150-232` | 24, `WRITE_KINDS` 5 | 27; `tasks_create` in `WRITE_KINDS` (neue Art `task`, Buchung und Aufräumen in `canary_world.register_tool_write`), Plan-Einträge für alle drei Werkzeuge |
| 17 | `tests/integration/canary_world.py:541-566, 1193-1218, 1220-1245` | `mkcalendar` nur `VEVENT`; Deck-Karte ohne Beschreibung | `mkcalendar` mit `VTODO`, eigene Aufgabenliste der Welt mit Aufräumbeweis (`X-NC-CalDAV-No-Trashbin`, `_NO_CAL_TRASH` Zeile 108); Deck-Karte mit eigenem Beschreibungsmarker; Prüfung, dass dieser Marker in keiner Antwort der drei Aufgabenwerkzeuge steht (siehe Pitfall 9) |
| 18 | `tests/integration/test_pair_equality_live.py` | Paarfälle | keine neuen: die Werkzeuge sind `UNAFFECTED`, `PAIR_CASES` (`tool_classes.py:126`) bleibt |
| 19 | `scripts/acceptance_all_tools.py` (Kette ab Zeile ~270) | ruft jedes Werkzeug | Kette `tasks_create` (ohne `list`, Testinstanz hat `personal` mit `VEVENT,VTODO,VJOURNAL`), `tasks_search` findet sie, `tasks_read` liest sie, `fetch` liest dieselbe Id |
| 20 | `scripts/check_tool_budget.py:104-112, 113` | 16222 Bytes, Budget 18000 | Messzeile mit Datum, 27 Werkzeuge; Hausregel anwenden (Prototyp: rund 18840, plus 15 Prozent 21666, nächste 500: 22000); `MAX_TOOL_BYTES = 1400` unverändert |
| 21 | `README.md:25`, `README.de.md:28`, `README.fr.md:28` | "24 tools across nine app families" | 27, zehn Familien, "tasks" in der Aufzählung |
| 22 | `README.md:66-90` (de `:75-99`, fr `:78-102`) | Tabelle | drei Zeilen; Zeile `fetch` um "task" ergänzen (Plan TASK-09) |
| 23 | `README.md:116-131` (de ~`:127-142`, fr ~`:133-148`) | Bundle-Liste | `tasks: tasks_search, tasks_read, tasks_create` |
| 24 | `appinfo/info.xml:573` Beschreibung von `NC_MCP_DISABLED_TOOLS` | "Valid names: calendar, ..., talk" | `tasks` ergänzen; keine Store-Text-Änderung (`test_store_texts_frozen.py` pinnt nur `summary`/`description` direkt unter `info`) |
| 25 | `docs/hardening.md`, `.de.md`, `.fr.md` | keine Bundle-Liste gefunden; Abschnitt 5 sagt allgemein, dass `search`, `fetch`, `prepare_context` abgeschaltete Bundles erreichen | Satz bleibt wahr (fetch erreicht Aufgaben auch bei `tasks` aus). TASK-07 nennt "Bundle-Namen in docs/hardening*.md": vor dem Plan prüfen, welche Stelle gemeint ist |
| 26 | `docs/folder-evidence.md` | "24 tools" ohne Verweis | Verweiszeile auf `tests/contract/test_tool_surface.py` (K10), sonst Gate rot |
| 27 | `CHANGELOG.md:12`, `.de.md:13`, `.fr.md:14` `[Unreleased]` | Ordner-Eintrag | `### Added` für die drei Werkzeuge und das Bundle; `test_changelog_translations.py` hält die drei gleich |
| 28 | `src/mcp_connector/tools/chatgpt.py` Modul-Docstring (`:15-41`) | "Seven properties", sieben Leser | TASK-09: Leser für Aufgaben, Marker-Regel |
| 29 | `vulture_whitelist.py` | kein | nur falls neue öffentliche Namen nur aus Tests erreicht werden |
| 30 | `tests/integration/test_tasks_live.py` und CI | fehlt | neu, mit `NC_MCP_REQUIRE_LIVE`-Zweig (W3), siehe F10 |

Nicht anfassen: Server-Instruktion (`server/__init__.py:61-71`, Phase 34), Store-Text, `FORBIDDEN` und `CHUNK_ASSEMBLY_MOVE`, `UNCONDITIONAL_PUTS`.

### F10: Testumgebung (D-32-11, D-32-12)

**Fassungen:** Tasks 0.18.1 auf 32 und 35 (min 31, max 35) [VERIFIED: v0.18.1 info.xml]. `occ app:install tasks` braucht App-Store-Zugang (Bootstrap und CI haben ihn, `ensure_app` installiert heute schon notes, deck, tables, mail, spreed). Nach der Installation den Nextcloud-Container neu starten (Spike: Deck-REST 404 direkt nach `app:install`, Commit `57f60f6`; dasselbe Muster für den Provider-Eintrag). Rückbau: `occ app:remove tasks` oder `app:disable` plus Neustart; die Fassung per `occ app:list` ins Rohprotokoll.

**Lokal, Nextcloud 35 (`nc35`, 35.0.0):** ExApp 0.7.2 aus diesem Branch registriert (31-07). Für die ganze Kette (W2) muss das Image mit den neuen Werkzeugen neu gebaut und per `unregister` ohne `--rm-data` plus `bootstrap_exapp.sh --nc35` neu registriert werden (Weg aus 31-07, Owner-Freigabe wie dort). Messprogramm nach `scripts/folder_chain_evidence.py` über `scripts/oauth_flow_check.py`.

**Lokal, Nextcloud 32 (`nc-mcp-exapp`-Volume, 32.0.15):** nach der Reparatur per `--manual`; ExApp als lokaler Prozess (nur fünf Variablen). Version im AppAPI-Eintrag steht dort auf 9.9.9 (31-05b, `handleExAppVersionChange` senkt nie): nie wieder eine erfundene Version im Kopf senden. Eine ganze Kette über ein Image gibt es auf 32 nicht (31-07 Offene Punkte); der Live-Beweis auf 32 ist Funktionsebene unter Impersonation.

**Konto ohne Aufgabenliste live (TASK-03):** `occ user:add` mit Passwort, danach eine Basic-Anfrage an `/ocs/v2.php/cloud/user` (erzeugt `personal` nur mit `VEVENT` und `contact_birthdays`, gemessen auf 32.0.15 und 35.0.2, Spike 5.1), dann die drei Werkzeuge unter Impersonation für dieses Konto; zweiter Fall: Konto ohne jede Anmeldung (kein Kalender-Home, A1). Rückbau `occ user:delete`. Gegenprobe über die Tabelle `calendars`, wie im Spike.

**Geteilte Listen live:** `bob` teilt eine Liste mit Schreibrecht und eine nur lesbare an `alice` (DAV-Weg der Kalender-App wie im Spike, `share`-POST); Messpunkte: Name ohne Besitzerzusatz, `shared`, `writable`, kein `bob` in irgendeiner Antwort (Rohtext durchsuchen), Schreiben nur mit `list`, nur lesbare Liste vorab abgelehnt, Server-404 als letzte Instanz mit Gegenprobe. Deck-Board mit Karte samt Beschreibung: in keiner Antwort.

**CI, Form von D-32-11 (Entscheidung der Planung):** Empfehlung zwei Beine in vorhandenen Jobs statt eines neuen Jobs:
- `exapp` (34.0.3, Standardmodus, ohne Tasks-App): neuer Schritt `pytest tests/integration/test_tasks_live.py -m integration` mit `NC_MCP_REQUIRE_LIVE=1` und `.env.exapp`; belegt "ohne App" und bringt zusätzlich eine Messung auf 34, die sonst fehlt.
- `canary-nc35` (35.0.1): Schritt `occ app:install tasks` plus Neustart vor der Kanarie, dann Kanarie (ruft die drei Werkzeuge, Provider `tasks` erscheint, `test_provider_classes_live.py` kennt ihn), dann derselbe Live-Test mit Tasks-App (Provider-Link für TASK-09).
- Damit ist W3 für dieses Bundle geschlossen. W2 (ganze Kette über die installierte ExApp) liefert im CI `test_oauth_flow_exapp.py` (Zeile 235: "a token from the flow serves a tool call over the whole chain"), wenn dort ein Aufgabenwerkzeug über die Kette gerufen wird; lokal zusätzlich `tasks_chain_evidence.py` auf nc35.
- Push und CI-Lauf brauchen die Freigabe des Owners (R4).

**Folgen aus W2 und W3 für die Form des Live-Beweises:** Der Funktionsebenen-Test allein reicht nicht (W2). Der Beleg nennt daher getrennt: (a) Funktionsebene unter Impersonation auf 32 und 35, (b) ganze Kette über die installierte ExApp auf 35, (c) CI-Schritte, die (a) auf 34 und 35 bei jedem Push wiederholen.

### F11: Fallstricke aus Phase 31, die hier wieder drohen

Siehe "Common Pitfalls" Nummer 1 bis 8.

### F12: Zuschnitt der Pläne und Wellen

Siehe "Empfohlener Planschnitt".

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ICS-Ausgabe | Zeilen von Hand, eigenes Escaping, eigene Faltung | `icalendar.Todo`, `Calendar.to_ical()` | Zeilenumbruch im Titel öffnet sonst eine zweite Komponente (T-01-46); `VALUE=DATE`, `CATEGORIES`-Escaping geprüft |
| `VTIMEZONE` | eigene Zonendefinition | `icalendar.Timezone.from_tzinfo` wie `calendar.build_ics` (`:404-416`) | Windows-Zonennamen sind der klassische Interop-Fehler |
| XML-Körper | f-Strings | `lxml.etree` wie `caldav.build_calendar_query` | Einschleusung über Attribute (T-01-45) |
| XML lesen | `etree.fromstring` | `xml.parse_root` / `xml.hardened_parser` | XXE, Entitäten |
| Cursor | eigene Kodierung | `paging.encode_cursor`, `decode_cursor`, `check_scope`, `read_offset` | hostile Eingaben, Länge, Bereichsbindung |
| Kappung mit Vermerk | eigener Schnitt | Muster `mail._capped` (`tools/mail.py:548-563`), Feld `..._truncated` | UTF-8-Grenze, kein Marker im Text |
| Markerfilter | eigene Regex | `marks.without_marks` | eine Quelle für alle Leser (BL-09) |
| Id-Format | Strings zusammensetzen | `ids.encode_task`, `ids.parse` | Rundlauf, Trennzeichen-Regeln |
| Erkennung der App | Probe-Anfrage an `/apps/tasks` | Navigation über `capabilities` | Cache, keine HTML-Seiten |
| create-only | Vorab-`HEAD`/`PROPFIND` | `If-None-Match: *` in derselben Anfrage | kein Wettlauf |

## Common Pitfalls

### Pitfall 1: RAM-Gate und eine Instanz
**What goes wrong:** Zwei Nextcloud-Instanzen oder ein Start bei unter 4 GB freiem Speicher brechen Messläufe ab (31-01: 3,56 GB nach dem Start).
**How to avoid:** Vor jedem Docker-Schritt das Gate aus 31-01-PLAN (`FreePhysicalMemory`, Schwelle 4,0 GB, fremde Container nie anfassen, `drop_caches` nur bei leerem Docker); nie `down`, nur `stop`; Messung, Bootstrap, Live-Läufe streng nacheinander. Aufbau von 2000 Aufgaben auf SQLite seriell (109 s, "database is locked" bei Parallelität).

### Pitfall 2: Geheimnisse in pytest-Ausgaben
**What goes wrong:** pytest druckte im Fehlerteil Testargumente samt Anfang von `APP_SECRET` (31-05).
**How to avoid:** Umgebung aus jeder Darstellung heraushalten; jede Ausgabe erst in eine Datei außerhalb des Repos, gegen alle Werte der Env-Dateien und deren erste 12 Zeichen prüfen, dann anhängen; `warnings summary` nicht ins Rohprotokoll.

### Pitfall 3: GreenMail verliert die Post
**What goes wrong:** GreenMail hält Post nur im Speicher; nach jedem Neustart ist die INBOX leer, das Abnahmeskript endet mit `PREREQ` (31-05b).
**How to avoid:** Vor dem Abnahmeskript die Zustellung des Bootstraps laufen lassen; nach der Reparatur auf 32 tut das der Bootstrap selbst.

### Pitfall 4: `core.autocrlf` und Hexprüfungen
**What goes wrong:** Mit `autocrlf=true` bekommen Dateien im Arbeitsbaum CRLF; eine Prüfung auf genau 40 Hexzeichen (Basisdatei) scheitert (31-01-SUMMARY); `sed -i` stellte Zeilenenden um (31-05b). Die Fixtures unter `tests/fixtures/tasks_app/` und die zwei Discovery-Antworten sind per `.gitattributes` von der Umwandlung ausgenommen und tragen CRLF des Servers (Spike 5.6).
**How to avoid:** Basis-Hash mit `tr -d '\r'` lesen; Fixtures nie umschreiben; Byte-Pins auf Python-Bytes, nicht auf Dateitext.

### Pitfall 5: Unix-Socket unter Windows
**What goes wrong:** Mit der ganzen `.env.exapp` in der Umgebung will der lokale ExApp-Prozess wegen `HP_SHARED_KEY` einen Unix-Socket (NotImplementedError).
**How to avoid:** Lokalen Prozess nur mit `APP_ID`, `APP_SECRET`, `APP_VERSION`, `NC_MCP_URL`, `NC_MCP_PUBLIC_URL` starten.

### Pitfall 6: AppAPI hebt die Version aus dem Kopf
**What goes wrong:** `handleExAppVersionChange` speichert `EX-APP-VERSION`, wenn sie größer ist, und senkt nie; ein Test mit 9.9.9 hat die 32er Instanz dauerhaft auf 9.9.9 gesetzt.
**How to avoid:** In Tests und Messungen nur die echte Version aus `appinfo/info.xml` senden.

### Pitfall 7: Zwei verschiedene Sechsen
**What goes wrong:** `CREATE_TOOLS` wächst auf 7 (`tasks_create` ist ein Anlege-Werkzeug), `EXPECTED_PUT_CALLS` bleibt 6. Der Satz "the create-only paths stay six" (`test_tool_surface.py:800`) und die Kommentare zu "six" (`:72-74`) müssen bewusst nachgezogen werden.
**How to avoid:** Im Plan beide Zahlen getrennt nennen und je eine Gegenprobe (siebter `PUT` irgendwo macht das Zählgate rot).

### Pitfall 8: Zwischenspeicher der App-Erkennung
**What goes wrong:** Nach `occ app:disable tasks` antworten Navigation und Provider-Liste weiter "an", bis der PHP-Prozess neu ist (gemessen für drei Familien in SRV-06).
**How to avoid:** Lauf "ohne App" auf einer Instanz ohne die App oder nach Neustart; im Beleg vermerken.

### Pitfall 9: Kanarienmarker in Deck-Beschreibungen
**What goes wrong:** Setzt man den Kanarienmarker der Welt in eine Deck-Kartenbeschreibung, könnte er über den Deck-Suchprovider in `unified_search` landen und die Kanarie aus einem Grund rot machen, der nichts mit dem Tasks-Bundle zu tun hat. [ASSUMED A6: ob `search-deck-card-board` die Beschreibung in der `subline` trägt, ist hier nicht geprüft]
**How to avoid:** Einen eigenen Deck-Marker nutzen und ihn nur gegen die Antworten der drei Aufgabenwerkzeuge prüfen; Positivkontrolle, dass der Marker in der Deck-Karte steht (Deck-REST) und dass der Deck-Kalender in der Discovery mit dieser Beschreibung als `VTODO` existiert.

### Pitfall 10: Schwebende Zeit still zu UTC
**What goes wrong:** `caldav._value_of` macht schwebende Zeiten zu UTC (`caldav.py:417-420`); bei Terminen ist das unter Expansion richtig, bei Aufgaben (ohne Expansion) falsch.
**How to avoid:** eigener Leser; benannter Test "schwebend bleibt schwebend und ist gekennzeichnet".

### Pitfall 11: Mehrere `CATEGORIES`-Zeilen und `RELATED-TO`-Zeilen
**What goes wrong:** `component.get("CATEGORIES")` liefert bei mehreren Zeilen eine Liste von `vCategory`, bei einer einen einzelnen Wert; dasselbe für `RELATED-TO`.
**How to avoid:** beide Formen normalisieren und mit von Hand gebauten Objekten testen.

### Pitfall 12: Doku-Zählgate
**What goes wrong:** Jede Seite unter `docs/` mit "N tools" ungleich 27 ohne Verweis auf `tests/contract/test_tool_surface.py` macht `test_a_documented_tool_count_...` rot; heute betrifft das `docs/folder-evidence.md` (K10).
**How to avoid:** Verweiszeile ergänzen (Beleg bleibt wörtlich), README-Zahl auf 27.

### Pitfall 13: Home-404 als Fehler
**What goes wrong:** Ein Konto ohne Kalender-Home endet mit "Nextcloud does not know ..." statt E6.
**How to avoid:** eigener Statusprüfer im Aufgaben-Client; Test mit 404 und mit leerer 207.

## Code Examples

### Kinder exakt nachprüfen (Skizze)
```python
# Quelle der Semantik: sabre-io/dav CalendarQueryValidator.php:238-246 ("contains")
def is_direct_child(todo: Any, parent_uid: str) -> bool:
    raw = todo.get("RELATED-TO")
    values = raw if isinstance(raw, list) else [raw] if raw is not None else []
    for value in values:
        reltype = str(getattr(value, "params", {}).get("RELTYPE", "PARENT")).upper()
        if reltype == "PARENT" and str(value) == parent_uid:
            return True
    return False
```

### Ausgabe einer Fälligkeit ohne stilles UTC (Skizze)
```python
def time_field(value: date | datetime) -> tuple[str, bool]:
    """ISO string and whether it is floating. A date never grows a time."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat(), True
        return value.isoformat(), False
    return value.isoformat(), False
```

### Feature-Erkennung `--name` im Bootstrap (Skizze)
```bash
# grep without -q on a pipe: pipefail plus SIGPIPE (see the comment above occ_pw)
token_name_args=()
if occ user:auth-tokens:add --help 2>/dev/null | tr -d '\r' | grep -- '--name' >/dev/null; then
  token_name_args=(--name "$TOKEN_NAME")
fi
raw="$(occ_pw "$password" user:auth-tokens:add "$uid" --password-from-env "${token_name_args[@]}")"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `occ user:auth-tokens:add` ohne Namen | `--name` (Standard `cli`) | Nextcloud 33 (`stable33`) | Bootstrap auf 32 bricht ohne Feature-Erkennung |
| AppAPI hängt Port an den Daemon-Host | Host vor dem Port gekürzt (`explode(':')`) | AppAPI `stable33` | Host ohne Port ist die eine Form für 32 bis 35 |
| Provider-`subline` nur Fälligkeit oder Erledigt-Datum | zusätzlich `(<Listenname>)` | Nextcloud 34 (`stable34`) | Besitzername geteilter Listen in `unified_search` (nicht im Bundle `tasks`) |
| `{http://owncloud.org/ns}calendar-...` | `TasksSearchProvider` nutzt Konstanten statt statischer Felder | `master` (36.0.0 dev) | ohne Folge für das Verhalten |

**Deprecated/outdated:** Docker Socket Proxy (Entfernung in 35 angekündigt, CLAUDE.md); nichts Neues daran in dieser Phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Unter Impersonation antwortet das Kalender-Home eines Kontos ohne Kalender mit 404 (nicht 207 leer, nicht 401) | Pattern 1, F10 | Fall E6 fällt als Fehler aus; Test deckt beide Formen ab, die Messung entscheidet die Erwartung |
| A2 | `{http://nextcloud.com/ns}owner-displayname` ist per `PROPFIND` lesbar und gleich dem Klammerzusatz im `displayname` | Pattern 2, F5 | Name geteilter Listen nicht sauber zu kürzen; Ersatzname aus der URI greift |
| A3 | Navigation (und Provider-Liste) spiegeln den Zustand der Tasks-App auch unter Impersonation | Pattern 6, F7 | Hinweis entfällt (D-32-10), kein Fehlverhalten der Werkzeuge |
| A4 | Ausgelieferte AppAPI-Fassungen auf 34.0.x und 35.0.0 entsprechen dem Code ihrer Zweige | F1 | Host ohne Port bricht dort; die Messung vor dem Umbau schließt das |
| A5 | `{base}/index.php/apps/tasks/...` öffnet die Aufgabe auch auf Instanzen mit hübschen URLs | F8 | Link in `fetch` führt auf eine Fehlerseite; messen auf nc35 |
| A6 | Der Deck-Suchprovider trägt die Kartenbeschreibung nicht in der `subline` | Pitfall 9 | nur für die Wahl des Markers relevant |
| A7 | Kinderabfrage kostet bei 2000 Aufgaben etwa so viel wie Modus offen | F4 | Budget falsch; D-32-03 misst vor dem Bau |
| A8 | Eine Elternaufgabe liegt fast immer in derselben Liste wie ihre Kinder (Tasks-App) | F3, F4 | Elternverweis öfter `found: false`; ehrlich gekennzeichnet |
| A9 | Tasks 0.18.1 schreibt auf Nextcloud 32 dieselbe Objektform wie auf 35 | F10 | Fixtures stammen aus 35; Live-Beweis auf 32 mit App deckt es ab |
| A10 | Die Datumssortierung "Datum vor Zeiten desselben Tages" entspricht der Erwartung | F3 | nur Reihenfolge; Planung legt fest und testet |
| A11 | Byte-Größen der Werkzeuge (Prototyp 1417/906/292) | F9 | Budget und Decke; erst messbar mit der echten Registrierung (A10 der REQUIREMENTS) |

## Open Questions (RESOLVED)

1. **D-32-06 und die Form geteilter Listen (Owner-Entscheid möglich)**
   - What we know: Nextcloud schreibt den Besitzernamen in den `displayname` und die Kontokennung in die URI jeder geteilten Liste (K1). Beides würde ohne Eingriff in Name und `task:`-Id stehen.
   - What's unclear: ob der Owner "Name, wie Nextcloud ihn anzeigt" als "ohne den Klammerzusatz" lesen will und ob ein pseudonymer Listenschlüssel in der Id für ihn passt.
   - Recommendation: Zusatz entfernen, Schlüssel `s<16 hex>` für geteilte Listen; beides als Entscheidung der Planung festschreiben und dem Owner in einem Satz vorlegen, weil es den Wortlaut einer Owner-Entscheidung auslegt.
   - RESOLVED: D-32-14 (Owner 13.11.), Messung in 32-02, Umsetzung in 32-03.

2. **Link in `fetch` für Aufgaben aus geteilten Listen**
   - What we know: der Deep-Link braucht `_shared_by_<uid>`.
   - Recommendation: für geteilte Listen nur die Startseite der Tasks-App verlinken; Entscheidung der Planung, im Plan TASK-09 festhalten.
   - RESOLVED: D-32-15 (Owner 13.11.), Umsetzung in 32-06.

3. **`parent` in einer geteilten Liste ohne `list`**
   - What we know: E4 erlaubt das Schreiben in geteilte Listen nur bei ausdrücklicher Nennung.
   - Recommendation: `parent` zählt nicht als Nennung; Fehler mit Ausweg `list`. Owner kann es anders wollen.
   - RESOLVED: D-32-16 (Owner 13.11.), Umsetzung in 32-04b.

4. **Wo meint TASK-07 "Bundle-Namen in `docs/hardening*.md`"?**
   - What we know: die drei Dateien enthalten heute keine Liste der Bundle-Namen (grep); die Liste steht in den READMEs und in `appinfo/info.xml:573`.
   - Recommendation: im Plan prüfen und die tatsächlichen Fundstellen nachziehen; sonst Satz im Plan, warum dort nichts zu ändern ist.
   - RESOLVED: 32-06 Task 3 (Satz in Abschnitt 5 von docs/hardening*.md, drei Sprachen).

5. **Zeitbudgets und Deckel**
   - What we know: Spike-Vorschlag 1 s je Liste als Untergrenze ohne Netzwerk und ohne Impersonation; Kalender nutzt 20 s.
   - Recommendation: Messung in Plan 32-02, Werte mit Messzeile im Code begründen (wie `check_tool_budget.py`).
   - RESOLVED: Messung in 32-02, Werte in 32-04.

## Environment Availability

In dieser Recherche wurde nichts gestartet (Auftrag: nur lesen). Stand aus 31-07-SUMMARY und raw/nc32-strecke.txt:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Desktop mit WSL2 | alle Live-Läufe | ja (31-07) | kein | kein |
| uv, Python 3.13 | Gates | ja (lokaler Lauf dieser Recherche) | kein | kein |
| Instanz nc35 | Live 35, ganze Kette | ja, gestoppt | 35.0.0, ExApp 0.7.2 | kein |
| Volume nc-mcp-exapp | Live 32 | ja, gestoppt | 32.0.15, manual_install ohne Port von Hand, App-Version 9.9.9 im Eintrag | kein |
| Wegwerf-Images 32.0.15, 33.0.9, 34.0.4, 35.0.2 | Messung F1, F4 | im Spike genutzt (`compose.spike-tags.yml`, `-pg`) | kein | CI für 34/35 |
| App Store Erreichbarkeit | `occ app:install tasks` | im Spike und CI ja | Tasks 0.18.1 | kein |
| GitHub Actions | CI-Beine | ja, Push braucht Owner-Freigabe | kein | lokal |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** keine Messung auf 33 (bewusst; 33 nur über Quelltext).

## Validation Architecture

Übersprungen: `workflow.nyquist_validation` ist in `.planning/config.json` auf `false` gesetzt.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (unverändert) | AppAPI-Impersonation oder App-Passwort aus dem Auth-Kanal |
| V3 Session Management | nein | zustandslos, Cursor ohne Autorität (`paging.py`) |
| V4 Access Control | ja | Server entscheidet; Discovery-Vorprüfung (`writable`, Deck, Abo); kein Nutzerparameter (`FORBIDDEN_PROPERTIES`) |
| V5 Input Validation | ja | Pydantic-Schema plus Prüfungen in `tools/tasks.py`; `safe_segment`; `ids.parse`; Liste nur gegen Discovery |
| V6 Cryptography | nur Schlüsselbildung | `hashlib.sha256` für den Listenschlüssel, kein Geheimnis |
| V8 Data Protection | ja | keine Besitzernamen, keine Kontokennung in Antworten (D-32-06); Audit nur Parameternamen |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Fremdtext aus geteilter Liste als Prompt-Injektion | Tampering | Text nur im Inhaltsfeld, `marks.without_marks`, Beschreibung gekappt mit Vermerk; Injektionskorpus |
| Schreiben in fremdsichtbare Liste | Elevation | E4-Zielwahl, nie positionsabhängig, `writable` aus Discovery, 404/403 als letzte Instanz |
| Überschreiben einer Aufgabe | Tampering | `If-None-Match: *`, Zählgate `EXPECTED_PUT_CALLS` |
| Deck-Karte über Aufgabenweg | Information Disclosure | Präfix `app-generated--` in Discovery und vor jeder Anfrage in `fetch`/`tasks_read`; Kanarie |
| Pfadmanipulation über Id | Tampering | `ids._join`/`parse`, `safe_segment`, Auflösung nur gegen Discovery |
| Besitzerkennung im Id oder Namen | Information Disclosure | Listenschlüssel und Namenskürzung (Pattern 2) |
| Provider-Link als SSRF | Spoofing | Link nur parsen, URL aus `creds.base_url` neu bauen (T-01-68) |
| Abo-Objekt über `fetch` | Information Disclosure | Discovery-Prüfung, Abo gilt als unbekannte Id |

## Empfohlener Planschnitt (Claude's Discretion)

Fest: Plan 1 ist die Bootstrap-Reparatur, TASK-09 ist ein eigener Plan. Docker-Pläne laufen streng nacheinander (RAM-Gate).

| Plan | Inhalt | Welle | Hängt ab von | Live |
|------|--------|-------|--------------|------|
| 32-01 | D-32-13: Messung je Fassung (32.0.15, 34.0.x Wegwerf, 35.0.0) von `--help` und `resolveExAppUrl`; Umbau beider Stellen (Feature-Erkennung, Host ohne Port); Unit-Pin im Skripttest; voller `--manual`-Lauf auf 32 bis `.env.exapp`; Rohprotokoll | 1 | kein | ja (lokal) |
| 32-02 | Messung vor dem Bau: Kinderabfrage (2000, SQLite und PostgreSQL), Modi offen/alle unter Impersonation auf nc35, Zeitbudgets je Liste und für Kinder abgeleitet; Erkennung der Tasks-App (Navigation und Provider, an/aus/Neustart, 32 und 35); `owner-displayname` und Namensform geteilter Listen; Home-404 unter Impersonation; Provider-Link für geteilte Liste und Sonderzeichen; Ergebnis in `docs/spike-tasks.md` (Nachtrag) oder `docs/tasks-evidence.md` | 2 | 32-01 | ja (lokal) |
| 32-03 | Client-Schicht: Byte-Pin der Kalenderkörper zuerst; `clients/tasks.py` (Discovery, Klassifikation, Schlüssel, Namenskürzung, `REPORT`-Körper für Vorfilter und Kinder, `GET`, Statusprüfer, Home-404); generischer Schreiber in `caldav.py` mit `put_event`-Hülle; `ids.encode_task` mit Rundlauf; Unit-Tests auf den zwei Discovery-Fixtures und den acht ICS-Fixtures; Diff-Beweis Kalendertests | 3 | 32-02 (Budgets als Konstanten, Namensregel) | nein |
| 32-04 | `tools/tasks.py`: Suche (Filter, Sortierung, Cursor, Deckel, degraded, skipped, Elternverweis Hybrid), Lesen (Zeitmatrix als benannte Tests, Kappung, Kinder mit Budget und Deckel), Anlegen (Prüfungen, E4, VTODO, Rücklesen), Erkennung der Tasks-App in `capabilities`; Injektionskorpus | 4 | 32-03 | nein |
| 32-05 | Registrierung und Gate-Paket: `reg_tasks.py`, Allowlist, Gates #3 bis #13, Budget neu verankern, READMEs (Zahl, Familien, Tabelle, Bundles), `info.xml:573`, `docs/folder-evidence.md`-Verweis, drei CHANGELOGs, Kanarie-Code und Kanarienwelt, Abnahmeskript, `test_tasks_live.py` (Impersonation, `NC_MCP_REQUIRE_LIVE`), CI-Schritte im Workflow | 5 | 32-04 | nein (CI erst nach Push) |
| 32-06 | TASK-09: `provider_map` (Eintrag und Linkparser), `chatgpt._fetch_task` mit Discovery-Prüfung, README-Zeile `fetch`, Docstring, Unit-Tests der Linkformen und des Deck-Ausschlusses | 6 | 32-05 (gemeinsame README-Datei, `tool_classes.py`) | nein |
| 32-07 | Live-Beweis: nc35 (Image neu, ganze Kette mit `tasks_chain_evidence.py`, Funktionsebene, mit und ohne Tasks-App, geteilte Listen, Deck, TASK-03-Konten, Kanarie, Abnahmeskript, Provider-Treffer auf dieselbe Id), dann 32 (`--manual`, Funktionsebene, mit Tasks-App 0.18.1, TASK-03); Beleg `docs/tasks-evidence.md`; CI-Lauf nach Owner-Freigabe | 7 | 32-06 | ja (lokal, dann CI) |

Begründung der Reihenfolge: 32-02 vor dem Code, weil D-32-03 die Messung der Kinderabfrage vor dem Bau verlangt und drei Annahmen (A1, A2, A3) die Form der Client-Schicht bestimmen. 32-05 bündelt alles, was sonst den Zwischenstand rot macht (README-Tabelle, Zählgates, Bundle-Freeze). 32-06 nach 32-05, weil beide `README*.md` und `tool_classes.py` berühren. Live erst am Ende, weil das ExApp-Image alle Werkzeuge braucht. Will man parallelisieren: 32-06 ist bis auf README-Zeile und `tool_classes.py` dateigetrennt von 32-05 und kann mit klarer Dateizuteilung in Welle 5 laufen.

## Sources

### Primary (HIGH confidence)
- Repo-Code, gelesen: `src/mcp_connector/nextcloud/clients/caldav.py`, `tools/calendar.py`, `tools/chatgpt.py`, `tools/search.py`, `provider_map.py`, `ids.py`, `paging.py`, `nextcloud/capabilities.py`, `server/__init__.py`, `server/reg_calendar.py`, `audit/allowlist.py`, `tests/contract/*`, `tests/integration/test_canary.py`, `canary_world.py`, `scripts/bootstrap_exapp.sh`, `scripts/check_tool_budget.py`, `scripts/acceptance_all_tools.py`, `.github/workflows/ci.yml`, Fixtures
- `docs/spike-tasks.md` Abschnitte 5, 6, 7, 8, 9, 11; `.planning/phases/31-ordner-anlegen/` (RESEARCH, VERIFICATION, 31-01-, 31-05-, 31-05b-, 31-07-SUMMARY, `raw/nc32-strecke.txt` ab Zeile 690)
- nextcloud/server Zweige stable32 bis stable35 und master: `apps/dav/lib/Search/TasksSearchProvider.php`, `apps/dav/lib/CalDAV/CalDavBackend.php` (stable32: `getCalendarsForUser` 322-460, `calendarQuery` 1921-2010, `searchPrincipalUri` 2478-2590, `addOwnerPrincipalToCalendar` 3910-3930), `apps/dav/lib/DAV/Sharing/Plugin.php`, `core/Command/User/AuthTokens/Add.php`
- nextcloud/app_api Zweige stable32 bis stable35 und main: `lib/DeployActions/ManualActions.php::resolveExAppUrl`
- nextcloud/tasks v0.18.1: `appinfo/info.xml`, `lib/AppInfo/Application.php`, Release-Liste
- sabre-io/dav master: `lib/CalDAV/CalendarQueryValidator.php`, `lib/DAV/StringUtil.php`, `lib/CalDAV/Xml/Filter/PropFilter.php`
- Lokale Läufe dieser Recherche: `scripts/check_tool_budget.py` (16222 Bytes, Größen je Werkzeug), icalendar 7.3.0 Serialisierung, Schema-Prototyp der drei Werkzeuge

### Secondary (MEDIUM confidence)
- RFC 4791 (text-match, comp-filter, prop-filter), RFC 5545 (`DUE`, `RELATED-TO`, `RELTYPE` Standard `PARENT`, `CATEGORIES`): aus Kenntnis, in den betroffenen Punkten durch sabre-Quelle und Spike-Messung gestützt

### Tertiary (LOW confidence)
- keine

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, keine neue Abhängigkeit, Bibliotheksverhalten lokal geprüft
- Architecture: HIGH für Schichtung und Gates; MEDIUM für Elternverweis-Variante und Budgets (Messung steht aus)
- Pitfalls: HIGH, aus Phase-31-Protokollen und Quelltext
- D-32-13: HIGH aus Quelltext je Zweig plus Messung auf 32; Messung auf 34/35 steht aus (A4)

**Research date:** 2026-11-13
**Valid until:** 2026-12-13 (Nextcloud-Patchreleases und Tasks-App können Provider und Discovery ändern; vor dem Live-Beweis die Fassungen erneut festhalten)

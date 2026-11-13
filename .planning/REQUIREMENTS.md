# Requirements: Milestone v1.8 "Tasks-Bundle und Ordner anlegen" (Release 0.8.0)

**Defined:** 2026-11-11
**Core value:** Der Assistent sieht niemals mehr als der angemeldete Nutzer. Mit 0.8.0 kann er Aufgaben suchen, lesen, anlegen, eng begrenzt ändern und verschieben sowie Ordner anlegen, ohne dass eine der bestehenden Grenzen (Rechte-Durchgriff, Ausschluss `kein-ki`, Sandbox, Audit) aufweicht.
**Grundlage:** `.planning/research/v1.8-tasks-080-RESEARCH.md` (Commit 5ddaddf), Issues #32 und #44. Die Recherche deckt Suchen, Lesen, Anlegen und Ordner ab; ändernde Zugriffe, Verschieben und Löschen sind dort NICHT untersucht und stehen deshalb vollständig als Annahmen im Mess-Spike (Phase 30).

## Scope-Entscheidungen

Der Owner hat am 11.11.2026 im Claude Code Terminal alle zwölf Entscheidungen der Recherche mit den Worten "Wie empfohlen" bestätigt. Spätere Entscheide am selben Tag erweitern den Umfang (E7, E8) und entscheiden zwei in der Planung neu aufgekommene Fragen (E13, E14). E15 hat der Owner am 12.11.2026 am Checkpoint des Mess-Spikes entschieden.

| ID | Entscheidung | Konsequenz |
|----|--------------|------------|
| E1 | Größenbudget der Werkzeugliste nach der Hausregel anheben (Messung plus 15 Prozent, auf 500 gerundet); die Decke je Werkzeug (1400 Bytes) bleibt | Der Wert folgt der Messung des jeweiligen Stands, nicht der Schätzung; gerechnet wird jetzt für sieben neue Werkzeuge (das Löschen ist seit dem 12.11.2026 gestrichen) |
| E2 | Eigenes Bundle `tasks`, zehnte Familie | Neuer öffentlicher Name für `NC_MCP_DISABLED_TOOLS`, Changelog-Pflicht |
| E3 | `task:`-Id über `fetch` und Provider `tasks` auflösbar: ja, eigener Plan, verschiebbar | TASK-09 ist ein eigener, abtrennbarer Plan in Phase 32 |
| E4 | Schreibziel ohne `list`: nur bei genau einer eigenen Liste, sonst Fehler mit den Namen; nie still in geteilte Listen | TASK-06 |
| E5 | Vorhandener Ordner: Erfolg mit `created: false`, nach Prüfung, dass dort ein Ordner liegt | FOLD-03; die ehrliche Annotation ist idempotent, das Gate braucht dafür eine eigene Werkzeugklasse |
| E6 | Keine Aufgabenliste: `tasks_create` Fehler mit Ausweg, `tasks_search` leere Antwort mit Hinweis | TASK-03 |
| E7 | Bestätigt: `summary`, `list`, `description`, `due`, `priority`, `timezone`, `parent`. Geändert (Owner, 11.11.2026, "Das hatte ich übersehen am besten alles in 8.0 ziehen so dass kein 8.1 nötig ist"): zusätzlich `tags` (CATEGORIES) und Startdatum (DTSTART) | TASK-05 trägt den vollen Umfang |
| E8 | Bestätigt: kein Abhaken, Ändern, Löschen in 0.8.0. Geändert (Owner, 11.11.2026, "Warte abhacken in 8.0"): Abhaken kommt in 0.8.0. Erneut erweitert (Owner, 11.11.2026, "Das hatte ich übersehen am besten alles in 8.0 ziehen so dass kein 8.1 nötig ist"): Abhaken, Wiederöffnen und Ändern (Titel, Beschreibung, Fälligkeit, Startdatum, Priorität, Tags, Elternaufgabe) in 0.8.0; kein 0.8.1 einplanen | Eigene Phase 33 mit den Anforderungen TMOD-01 bis TMOD-06; der Store-Text sagt, was der Connector an Aufgaben ändern kann und was nicht |
| E9 | Deck-Kalender (`app-generated--`) ausschließen, lesend und schreibend | TASK-01, gilt auch für alle ändernden Zugriffe |
| E10 | Deckel für neu angelegte Ordnersegmente je Aufruf: 10 | FOLD-02 |
| E11 | Store-Text dreisprachig neu, Entwurf vor dem Release dem Owner zeigen | EXAPP-13 |
| E12 | Gruppenordner mit ACL vor dem Release MESSEN, mit Negativtest (kein Schreibrecht ergibt Ablehnung) | MESS-02 in Phase 30, weil der Melder von #44 fast nur mit Gruppenordnern und ACL arbeitet |
| E13 | Löschen einer Aufgabe: BEDINGT in 0.8.0 (Owner, 11.11.2026, "Deine Empfehlung für 1 und 2"; Punkt 1 war Löschen). GEÄNDERT (Owner, 12.11.2026, Auswahl "Löschen raus"): kein Löschen in 0.8.0, obwohl MESS-06 "wiederherstellbar" ergab. Ursprünglich: nur wenn der Mess-Spike belegt, dass eine per CalDAV gelöschte Aufgabe im Papierkorb des Kalenders landet und wiederherstellbar bleibt | MESS-06 entscheidet ohne neue Rückfrage: "nicht wiederherstellbar" oder "nicht eindeutig" heißt kein Löschen in 0.8.0, und das steht als bewusste Grenze im Store-Text. TMOD-07 ist seit dem 12.11.2026 Out of Scope; die Grenze steht im Store-Text |
| E14 | Verschieben einer Aufgabe in eine andere Liste: JA, fest in 0.8.0 (Owner, 11.11.2026, "Deine Empfehlung für 1 und 2"; Punkt 2 war Verschieben) | TMOD-08, Regeln wie bei allen ändernden Zugriffen; `MOVE` unter AppAPI-Impersonation und das Verhalten für Unteraufgaben sind Annahmen für den Spike (MESS-06) |
| E15 | Eigener Admin-Schalter für die ändernden Aufgaben-Werkzeuge, ab Werk aus, nach dem Vorbild `NC_MCP_FILES_UPDATE` (Owner, 12.11.2026, "Empfehlungen übernehmen"; vom Orchestrator übermittelt, vorgelegt war die Empfehlung aus `docs/spike-tasks.md`, Abschnitt 10.3, Auslöser S1). Mit derselben Antwort entschieden: A15 (wiederkehrende Aufgaben bleiben abgelehnt), A16 (Unteraufgaben beim Abhaken mit abhaken, wie die Tasks-App), A21 (Unteraufgaben ziehen beim Verschieben mit und werden mitgelöscht) | TMOD-01 trägt den Schalter; welche Werkzeuge er im Einzelnen umfasst, ist nicht eigens festgelegt und wird in der discuss-phase von Phase 33 geklärt. TMOD-03, TMOD-07 und TMOD-08 sind nach A16 und A21 nachgezogen. Entscheid im Wortlaut: `docs/spike-tasks.md`, Abschnitt 10.4 |

### Werkzeugschnitt für die ändernden Zugriffe (Entscheid der Planung, vom Owner delegiert)

Abhaken und Feld-Ändern sind zwei Werkzeuge statt eines: `tasks_complete` (Arbeitsname, Abhaken und Wiederöffnen über einen Wahrheitswert) und `tasks_update` (Felder ändern). Verschieben (E14) ist ein eigenes Werkzeug (Arbeitsname `tasks_move`), weil es eine andere HTTP-Methode, eine andere Annotation und einen eigenen Audit-Namen hat; das Löschen (E13, Arbeitsname `tasks_delete`) ist seit dem 12.11.2026 gestrichen. Gründe für die Trennung von Abhaken und Ändern:

- Decke je Werkzeug: `tasks_create` liegt mit `tags` und Startdatum geschätzt nahe an 1400 Bytes `[ANNAHME A10]`. Ein `tasks_update` mit denselben Feldern plus Erledigt-Zustand würde die Decke voraussichtlich reißen, und die Decke wird nie angehoben.
- Klarheit: Abhaken ist der häufigste Fall und kommt mit Id und einem Wahrheitswert aus; das Modell muss dafür kein Feldschema ausfüllen.
- Abtrennbarkeit: zeigt der Spike ein Hindernis beim Feld-Ändern, bleibt das Abhaken allein lieferbar, und umgekehrt.
- Audit: der Eintrag nennt, was geschah (`tasks_complete` gegen `tasks_update`), ohne dass Nutzlastfelder ins Log müssen.

Die Namen folgen dem Muster `<familie>_<verb>` (`files_update` existiert bereits). Sie werden mit der Registrierung eingefrorene öffentliche API; der endgültige Name von `tasks_complete` wird in der discuss-phase von Phase 33 festgelegt.

## Durchgängige Regeln (keine eigenen Requirements, gelten in jedem Plan)

- R1: Jeder Plan, der `src/`, `tests/`, `scripts/`, `README*`, `docs/` oder `appinfo/` anfasst, endet mit dem vollen Lauf `pytest tests/unit tests/contract` plus `scripts/check_tool_budget.py`, dazu `ruff check`, `ruff format --check`, `pyright`, `vulture`. Nicht mitgelaufene Contract-Tests waren der häufigste frühere Fehler (RETROSPECTIVE.md).
- R2: Alle nutzersichtbaren Texte dreisprachig DE/EN/FR. `CHANGELOG.md`, `CHANGELOG.de.md` und `CHANGELOG.fr.md` bewegen sich im selben Plan (ein Test hält sie im Gleichschritt).
- R3: Kurze Produkttexte als Faktenliste; Entwurf vor dem Release dem Owner zeigen.
- R4: Vor jedem Push, Merge oder Kommentar den Owner fragen. Tag und Submit im Store nur mit Owner-Freigabe. Issue-Antworten in #32 und #44 erst NACH dem Store-Release.
- R5: Was die Recherche oder diese Planung als Annahme führt, bleibt bis zur Messung als Annahme gekennzeichnet (Abschnitt "Annahmen").
- R6: Gegenproben und Probe-Werkzeuge nie unter `src/` anlegen (jede `reg_*.py` wird Teil der Oberfläche).

Geprüft und bewusst nicht übernommen: Die `CLAUDE.md` des Repos sieht kein eigenes Security-, Bug- oder Performance-Audit nach jeder Phase vor. Es gelten die in `.planning/config.json` eingeschalteten Schritte des Workflows (`plan_check`, `code_review`, `verifier`), nicht mehr.

## v1 Requirements

### Mess-Spike (MESS)

- [x] **MESS-01**: `MKCOL` auf `files/` unter AppAPI-Impersonation ist in der ExApp-Topologie gemessen und mit Statuscode und Rohantwort protokolliert, als ERSTER Punkt des Spikes. Dazu die Statusmatrix für freien Namen, vorhandenen Ordner, vorhandene Datei am Pfad, fehlenden Elternordner, unzulässigen Namen, geteilten Ordner ohne Schreibrecht und gesetzte `NC_MCP_FILES_ROOT`. Abbruchkriterium: liefert `MKCOL` unter Impersonation für einen freien Namen kein 201, wird Phase 31 nicht geplant; der Befund geht mit Rohantwort an den Owner, bevor eine Zeile Produktcode entsteht.
- [x] **MESS-02**: Ordner anlegen in einem Gruppenordner mit ACL ist gemessen (E12): mit Schreibrecht entsteht der Ordner, ohne Schreibrecht wird abgelehnt (Negativtest), jeweils mit Statuscode und Rohantwort im Protokoll. Ein nur lesbarer externer Speicher wird mitgemessen, soweit er in der Testinstanz herstellbar ist; andernfalls bleibt er im Protokoll ausdrücklich als ungemessene Annahme stehen.
- [x] **MESS-03**: Die Aufgaben-Discovery und echte Objekte sind auf mindestens Nextcloud 32 und 35 gemessen: ein frisches Konto (Standardkalender nur `VEVENT`) hat keine Aufgabenliste; Deck-Kalender, Papierkorb, Abonnements, geteilte und nur lesbare Listen sind in der Discovery-Antwort identifiziert; von der Tasks-App geschriebene Objekte (ganztägig, mit Uhrzeit, Unteraufgabe, wiederkehrend, mit Tags) liegen als Fixtures vor; der Link des Suchproviders `tasks` und ein create-only `PUT` eines `VTODO` unter AppAPI-Impersonation sind belegt.
- [x] **MESS-04**: Die Kosten der Aufgabensuche stehen als Zahlen im Protokoll: eine Liste mit 2000 Aufgaben (davon 1900 erledigt), Modus "offen" und Modus "alle", auf SQLite und PostgreSQL, mit Wanduhr und Antwortgröße; `calendar-search` ist einmal mitgemessen. Deckel und Zeitbudget von `tasks_search` werden aus diesen Zahlen festgelegt, nicht aus der Schätzung.
- [x] **MESS-05**: Die ändernden Zugriffe sind gemessen, bevor Phase 33 geplant wird: welche Eigenschaften die Tasks-App beim Abhaken und Wiederöffnen setzt und in welchem Zeitformat; ob `PUT` mit `If-Match` unter AppAPI-Impersonation funktioniert und eine veraltete ETag mit 412 abgelehnt wird; ob der Server beim `PUT` unbekannte `X-`Eigenschaften, `VALARM` und übrige Eigenschaften unverändert speichert; Verhalten bei wiederkehrenden Aufgaben und bei Unteraufgaben; Antwort einer nur lesbaren geteilten Liste auf `PUT`. Dazu ein Inventar mit Datei und Zeile aller Gates und Zusagen, die ein überschreibender `PUT` berührt (`EXPECTED_PUT_CALLS`, Destruktiv-Gate, create-only-Aussagen in README, `docs/threat-model.md`, Store-Text, Server-Instruktion). Abbruchkriterium: geht `If-Match` unter Impersonation nicht oder verliert der Server fremde Eigenschaften, entscheidet der Owner über Phase 33, und 0.8.0 bleibt mit den Phasen 31 und 32 releasefähig.
- [x] **MESS-06**: Löschen und Verschieben sind gemessen. Löschen (entscheidet E13): auf den Nextcloud-Versionen des Store-Fensters (32 bis 35) ist belegt, ob eine per CalDAV gelöschte Aufgabe im Papierkorb des Kalenders landet und wiederherstellbar bleibt, auch mit abgeschaltetem Papierkorb und für geteilte Listen; die Aufbewahrungsfrist und ein Weg, vor dem Löschen zu prüfen, ob der Papierkorb für das Konto wirkt, sind festgehalten; ebenso, was die Tasks-App beim Löschen einer Elternaufgabe mit den Unteraufgaben tut. Das Ergebnis steht als eines von drei Wörtern im Messbericht: "wiederherstellbar", "nicht wiederherstellbar" oder "nicht eindeutig"; nur das erste nimmt TMOD-07 in 0.8.0 auf, ohne neue Rückfrage. Verschieben (E14): ob `MOVE` zwischen zwei Aufgabenlisten unter AppAPI-Impersonation funktioniert, mit Statuscodes, UID, ETag, Verhalten bei belegtem Ziel und bei geteiltem Ziel, und was die Tasks-App mit Unteraufgaben tut, wenn die Elternaufgabe die Liste wechselt. Abbruchkriterium: geht `MOVE` unter Impersonation nicht, geht der Befund an den Owner, und TMOD-08 wird nicht geplant. Der Messbericht legt dem Owner außerdem E15 zur Entscheidung vor.

### Ordner anlegen (FOLD)

- [x] **FOLD-01**: `files_create_folder(path)` im Bundle `files` legt genau einen Ordner mit einem `MKCOL` ohne Body an und meldet `created: true`. Fehlender Elternordner, Datei am Zielpfad, fehlendes Schreibrecht, unzulässiger Name (eigener Zweig für 400), Sperre und Serverfehler ergeben je eine eigene, benannte Meldung; kein Fall endet in "unexpected status".
- [x] **FOLD-02**: Mit `parents=true` legt das Werkzeug fehlende Elternordner von oben nach unten an und nennt in der Antwort jeden wirklich angelegten Ordner. Je Aufruf entstehen höchstens 10 neue Ordner (E10). Scheitert ein Segment mittendrin, nennt die Antwort die bereits angelegten Ordner und sagt, dass sie stehen bleiben.
- [x] **FOLD-03**: Liegt am Ziel bereits ein Ordner, ist die Antwort ein Erfolg mit `created: false` (E5), aber erst nach der Prüfung, dass dort ein Ordner und keine Datei liegt; eine Datei am Pfad bleibt ein Konflikt. Die Annotation des Werkzeugs ist ehrlich (anlegend, nicht destruktiv, idempotent), und das Annotations-Gate trägt diese Klasse ausdrücklich.
- [x] **FOLD-04**: Ausschluss und Sandbox gelten wie beim Upload: in einem mit `kein-ki` ausgeschlossenen Ordner oder darunter wird nichts angelegt, die Ablehnung ist byte-gleich zu "Elternordner fehlt"; ist die Ausschlussprüfung nicht beantwortbar, wird nichts geschrieben; geprüft wird vor jedem einzelnen `MKCOL`. Mit `NC_MCP_FILES_ROOT` wird die Wurzel selbst nie angelegt, ein Ziel gleich Wurzel wird vorab abgelehnt, und es werden nur Segmente unterhalb der Wurzel angefasst.
- [x] **FOLD-05**: Der neue Schreiber der Dateifläche durchläuft die ganze v1.7-Kette: Eintrag in `FILE_WRITERS` mit Paarfall (Unit und Live), Kanarie mit `MUST_REFUSE` und echtem Aufruf, Audit-Erlaubnisliste und `@graceful`, eingefrorene Werkzeugmenge, Bundle-Zuordnung, Abnahmeskript, eine positive Nadel "`MKCOL` nur in `dav.py`, ohne Body", `EXPECTED_PUT_CALLS` unverändert, Budget der Werkzeugliste grün ohne Anhebung der Decke je Werkzeug. Der Hinweistext von `parent_missing` verweist auf das neue Werkzeug und ist an beiden Stellen (Fabrik und Test) gemeinsam geändert.
- [x] **FOLD-06**: Phase 31 ist allein releasefähig: Werkzeugliste, Rechtetabelle und Werkzeugzahl in `README.md`, `README.de.md` und `README.fr.md` nennen `files_create_folder`; `docs/exclusion.md`, `.de.md` und `.fr.md` tragen einen Satz zur neuen Grenze "Ordner neben getaggtem Ordner" mit Befundlink an einem stabilen Ort (nicht unter `.planning/phases/`); `CHANGELOG.md`, `CHANGELOG.de.md` und `CHANGELOG.fr.md` tragen den Eintrag; alle Gates sind auf dem Stand ohne Phase 32 grün.

### Tasks-Bundle: suchen, lesen, anlegen (TASK)

- [ ] **TASK-01**: Aufgabenlisten sind die Kalender, deren Komponenten-Set `VTODO` enthält, eigene und hineingeteilte. Sammlungen mit dem Präfix `app-generated--` (Deck, E9), Abonnements, Scheduling-Ein- und Ausgang und der Papierkorb gehören nie dazu, weder lesend noch schreibend. Das Verhalten des Kalender-Bundles bleibt byte-gleich: die vorhandenen Tests des Kalender-Bundles laufen unverändert grün.
- [x] **TASK-02**: `tasks_search` liefert im Standard offene Aufgaben (ohne erledigte und abgebrochene), optional alle; Textsuche ohne Rücksicht auf Groß- und Kleinschreibung über Titel, Beschreibung und Tags; eine Fälligkeitsgrenze liefert keine undatierten Aufgaben mit; Sortierung offen zuerst nach Fälligkeit, undatierte ans Ende; Blättern über Cursor-Handles mit hartem Deckel und ehrlicher Notiz; mehrere Listen mit Zeitbudget und `degraded`-Eintrag je ausgefallener Liste; wiederkehrende Aufgaben erscheinen als Masteraufgabe mit `recurring: true`, ohne Expansion; ein nicht adressierbares Fremdobjekt wird übersprungen, ohne die Liste zu verlieren; die Limit-Politik ist vorab festgelegt und getestet.
- [ ] **TASK-03**: Ein Konto ohne Aufgabenliste ist ein eigener, benannter Fall (E6): `tasks_search` antwortet leer mit einem Hinweisfeld, `tasks_create` antwortet mit einem Fehler samt Ausweg (Liste in der Tasks-App anlegen). Der Fall ist eigens getestet, mit einer Discovery-Fixture ohne `VTODO`-Liste UND live gegen ein Konto, dessen einziger Kalender nur `VEVENT` trägt, weil die Testinstanz `personal` mit `VEVENT,VTODO,VJOURNAL` anlegt und den Produktionsfall sonst nie zeigt.
- [x] **TASK-04**: `tasks_read` liefert zu einer `task:`-Id Titel, Beschreibung (gekappt, ohne Marker, mit Kürzungsvermerk), Status, Fälligkeit, Startdatum, Priorität, Tags, Erledigt-Zeitpunkt, Elternbezug und das Kennzeichen `recurring`. Die Zeitmatrix ist je als benannter Test belegt: ganztägig bleibt ein Datum ohne Mitternacht, mit Zone, UTC, schwebend (gekennzeichnet, nie still zu UTC erklärt), ohne Datum. `ATTACH` wird nie geparst. Eine gelöschte oder unbekannte Aufgabe antwortet als unbekannte Id.
- [x] **TASK-05**: `tasks_create` legt eine Aufgabe create-only an (`If-None-Match: *`) mit `summary` (Pflicht), `list`, `description`, `due`, `start`, `priority`, `tags`, `timezone`, `parent` (E7). Eine Fälligkeit ohne Uhrzeit wird als `DUE;VALUE=DATE` auf genau dem genannten Tag geschrieben (`DUE` ist kein exklusives Ende, `_all_day_window` wird nicht übernommen); mit Uhrzeit ist ISO 8601 mit Zone Pflicht; `priority` außerhalb 0 bis 9 wird abgelehnt; `start` muss denselben Werttyp wie `due` haben und davor liegen, sonst Ablehnung vor dem Request; der Parameter der Elternaufgabe heißt nicht `uid`, `user` oder `owner`. Das Rücklesen meldet `confirmed`, und ein Fehler beim Rücklesen meldet den Schreibvorgang nie als gescheitert.
- [x] **TASK-06**: Das Schreibziel ist nie positionsabhängig (E4): ein benannter Parameter `list` gewinnt und wird nur gegen die Discovery aufgelöst; ohne `list` wird genau dann geschrieben, wenn es genau eine eigene Liste gibt; sonst kommt ein Fehler mit den echten Listennamen. In eine geteilte Liste wird nur bei ausdrücklicher Nennung geschrieben, in einen Deck-Kalender nie; die Ablehnung des Servers (403) bleibt die letzte Instanz.
- [ ] **TASK-07**: Die drei Werkzeuge bilden das eigene Bundle `tasks` (zehnte Familie, E2), einzeln abschaltbar über `NC_MCP_DISABLED_TOOLS`, und erfüllen alle Gates: eingefrorene Werkzeugmenge und Bundle-Namen, `tasks_create` in den Anlege-Werkzeugen, Audit-Erlaubnisliste mit gesperrten Nutzlastfeldern, `@graceful`, Klassifikation `UNAFFECTED` mit Beleg je Werkzeug, kein Nutzerparameter, Modulgrenzen, Id-Codec mit Rundlauftest, Injektionskorpus für gekappten Fremdtext, Abnahmeskript, `EXPECTED_PUT_CALLS` bleibt 6 (ein generischer create-only-Schreiber statt eines siebten `PUT`). Die Kanarie ruft alle drei Werkzeuge wirklich auf, mit einer Aufgabenliste in der Kanarienwelt samt Aufräumbeweis, und belegt, dass keine Deck-Kartenbeschreibung über das Tasks-Bundle abfließt. Werkzeugliste, Rechtetabelle, Werkzeug- und Familienzahl in den drei READMEs und in `docs/`, Bundle-Namen in `docs/hardening*.md` und die drei Changelogs sind nachgezogen.
- [x] **TASK-08**: Das Budget der Werkzeugliste ist nach der Hausregel neu verankert (E1): gemessener Wert plus 15 Prozent, auf die nächsten 500 gerundet, im Skript mit Messdatum begründet; kein Werkzeug liegt über 1400 Bytes, und die Decke je Werkzeug ist unverändert.
- [ ] **TASK-09**: Eine `task:`-Id ist über `fetch` lesbar, und der Suchprovider `tasks` ist in `PROVIDER_KINDS` eingetragen, sodass ein Treffer der Suche ohne Raten auf dieselbe Aufgabe auflöst (E3). Eine Id, die auf einen Deck-Kalender zeigt, wird auch auf diesem Weg nicht aufgelöst. Eigener Plan; verschiebbar nur per Owner-Entscheid.

### Aufgaben ändern (TMOD)

- [ ] **TMOD-01**: Jeder ändernde Zugriff trifft genau die eine genannte Aufgabe und läuft über eine gemeinsame Schreibschiene: Objekt lesen, dann `PUT` mit `If-Match` auf die gelesene ETag; nie ohne `If-Match`, nie mit `If-Match: *`. Eine zwischenzeitliche Änderung (412) führt zur Ablehnung mit der Aufforderung, neu zu lesen, nie zum Überschreiben und nie zu einem stillen zweiten Versuch. Nur lesbare und geteilte Listen ohne Schreibrecht werden mit klarer Meldung abgelehnt, Deck-Kalender bleiben ausgeschlossen. Wiederkehrende Aufgaben werden für ändernde Zugriffe abgelehnt, sofern MESS-05 nichts anderes ergibt. Der überschreibende `PUT` hat genau eine Aufrufstelle, das Zählgate ist bewusst und begründet nachgezogen, und der create-only-Weg bleibt unverändert. Die ändernden Aufgaben-Werkzeuge stehen hinter einem eigenen Admin-Schalter, ab Werk aus, nach dem Vorbild `NC_MCP_FILES_UPDATE` (Owner-Entscheid E15 vom 12.11.2026, `docs/spike-tasks.md`, Abschnitt 10.4). Einzige Ausnahme von "genau die eine genannte Aufgabe" sind die Unteraufgaben der genannten Aufgabe beim Abhaken, Verschieben und Löschen (A16, A21; Owner-Entscheid vom 12.11.2026, ebenda).
- [ ] **TMOD-02**: Es ändern sich nur die genannten Felder. Alle übrigen Eigenschaften, Parameter, `VALARM`, `VTIMEZONE` und unbekannte `X-`Eigenschaften bleiben inhaltlich erhalten. Belegt mit Rundlauftests auf den von der Tasks-App geschriebenen Fixtures aus Phase 30: die Menge der Eigenschaften vor und nach dem Zugriff unterscheidet sich genau um die genannten Felder und die gemessenen Pflegefelder (`LAST-MODIFIED`, `SEQUENCE`, soweit nötig).
- [ ] **TMOD-03**: `tasks_complete` (Arbeitsname) hakt eine Aufgabe ab und setzt dabei nur die Felder des Abhakens (`STATUS`, `PERCENT-COMPLETE`, `COMPLETED`, dazu die Pflegefelder), in der Form, die MESS-05 an der Tasks-App abgelesen hat. Dasselbe Werkzeug öffnet eine erledigte Aufgabe wieder. Eine schon erledigte Aufgabe abzuhaken und eine offene wieder zu öffnen ist ein Erfolg ohne Schreibzugriff (null `PUT`, in der Antwort kenntlich). Das Abhaken einer Elternaufgabe hakt ihre Unteraufgaben mit ab, wie es die Tasks-App tut (MESS-05, A16; Owner-Entscheid vom 12.11.2026, `docs/spike-tasks.md`, Abschnitt 10.4).
- [ ] **TMOD-04**: `tasks_update` ändert an einer bestehenden Aufgabe Titel, Beschreibung, Fälligkeit, Startdatum, Priorität, Tags und Elternaufgabe, mit denselben Prüfungen wie `tasks_create` (Priorität 0 bis 9, Werttyp und Reihenfolge von Start und Fälligkeit, Zone, `DUE` kein exklusives Ende). Eine Elternaufgabe muss in derselben Liste existieren und darf weder die Aufgabe selbst noch einer ihrer Nachfahren sein. Ändert der Aufruf nichts, wird nicht geschrieben. Status und Liste sind über dieses Werkzeug nicht änderbar.
- [ ] **TMOD-05**: Die ändernden Werkzeuge erfüllen die Gates mit ehrlichen Annotationen (ändernd, nicht destruktiv, idempotent), wofür das Annotations-Gate eine eigene Werkzeugklasse neben den Anlege-Werkzeugen trägt: eingefrorene Werkzeugmenge, Bundle `tasks`, Audit-Erlaubnisliste mit gesperrten Nutzlastfeldern und je einem Eintrag pro Aufruf, `@graceful`, Klassifikation, Kanarie mit echtem Aufruf, Abnahmeskript, Rechtetabelle der drei READMEs mit einer eigenen Stufe für ändernde Werkzeuge, drei Changelogs. Das Budget der Werkzeugliste ist nach der Hausregel aus der Messung des Endstands verankert, kein Werkzeug über 1400 Bytes.
- [ ] **TMOD-06**: Live-Beweis gegen eine echte Nextcloud, auch unter AppAPI-Impersonation: eine über den Connector abgehakte und eine geänderte Aufgabe sind danach inhaltlich so gespeichert, wie die Tasks-App sie schreibt; eine veraltete ETag wird abgelehnt und das Objekt ist unverändert; ein zweites Konto mit nur lesender Freigabe kann weder abhaken noch ändern (Zwei-Konten-Negativbeweis, Objekt danach unverändert); eine Deck-Karte ist über keines der ändernden Werkzeuge erreichbar.
- **TMOD-07** (GESTRICHEN, Out of Scope seit dem Owner-Entscheid vom 12.11.2026, Auswahl "Löschen raus"; der folgende Wortlaut bleibt nur als Beleg stehen und wird nicht geplant): Löschen einer einzelnen Aufgabe über ein eigenes Werkzeug (Arbeitsname `tasks_delete`): nur mit gelesener ETag (`If-Match`); nur ein Objekt, das nachweislich ein `VTODO` in einer beschreibbaren Aufgabenliste ist (nie ein Termin, nie eine Sammlung, nie ein Deck-Kalender); vor dem Löschen prüft das Werkzeug, dass der Papierkorb für dieses Konto wirkt, und lehnt sonst ab; das Löschen einer Elternaufgabe löscht ihre Unteraufgaben mit, wie es die Tasks-App tut (MESS-06, A21; Owner-Entscheid vom 12.11.2026, `docs/spike-tasks.md`, Abschnitt 10.4); wiederkehrende Aufgaben werden abgelehnt wie bei allen ändernden Zugriffen. Annotation destruktiv, Audit-Eintrag, die Antwort nennt die Wiederherstellbarkeit und die Frist. Das Destruktiv-Gate trägt `DELETE` als eng benannte Ausnahme an genau einer Aufrufstelle, mit eigenem Test und Gegenprobe. Abtrennbarer Plan. Lautet das Ergebnis von MESS-06 "nicht wiederherstellbar" oder "nicht eindeutig", wandert TMOD-07 ohne Umbau und ohne neue Rückfrage nach Out of Scope, und der Store-Text nennt die Grenze.
- [ ] **TMOD-08**: Verschieben einer einzelnen Aufgabe in eine andere Liste über ein eigenes Werkzeug (Arbeitsname `tasks_move`, E14): nur mit gelesener ETag; das Ziel ist immer ausdrücklich genannt und wird gegen die Discovery aufgelöst, nie positionsabhängig und nie still eine geteilte Liste; Schreibrecht auf Quelle und Ziel, sonst Ablehnung mit klarer Meldung; nie in einen und nie aus einem Deck-Kalender; nie über ein belegtes Ziel hinweg; die UID bleibt erhalten; wiederkehrende Aufgaben werden abgelehnt. Für eine Elternaufgabe mit Unteraufgaben gilt, was MESS-06 an der Tasks-App abgelesen hat: die Kinder ziehen mit (A21; Owner-Entscheid vom 12.11.2026, `docs/spike-tasks.md`, Abschnitt 10.4). Annotation ehrlich, Audit-Eintrag. Das Destruktiv-Gate trägt `MOVE` als eng benannte Ausnahme an genau einer Aufrufstelle, mit eigenem Test und Gegenprobe. Eigener, abtrennbarer Plan.

### Doku, Store, Release

- [ ] **DOC-04**: READMEs und `docs/` sagen in drei Sprachen den Endstand: Werkzeugliste, Rechtetabelle, Werkzeug- und Familienzahl, Bundle-Namen, "What this server cannot do" um den Ordner und die Aufgaben präzisiert, `docs/threat-model.md` um die Aufgabenfamilie ergänzt (Fremdtext in geteilten Listen als Injektionsfläche), ehrliche Grenzen aus Phase 30 (zum Beispiel ungemessene externe Speicher) mit Befundlink an stabilem Ort. Die Doku-Wahrheits- und Zähltests sind grün.
- [ ] **DOC-05**: Die Zusage "create-only, keine destruktiven Writes" ist überall präzisiert, wo sie steht, und sagt genau das Ausgelieferte: `.planning/PROJECT.md` (Constraints, Out of Scope, Key Decisions), drei READMEs, `docs/threat-model.md`, `docs/hardening*.md`, Server-Instruktion und Store-Text. Benannt ist die eng begrenzte Ausnahme (eine einzelne Aufgabe abhaken, wieder öffnen und in den genannten Feldern ändern, nur mit gelesener ETag), dazu das Verschieben in eine andere Liste (E14), und ebenso deutlich, was weiterhin nicht geht. Das Löschen einer Aufgabe steht als bewusste Grenze im Text (E13, Owner 12.11.2026). Das Inventar aus MESS-05 ist vollständig abgearbeitet, und ein Test hält die Aussage gegen die Registry.
- [ ] **EXAPP-13**: Der Store-Text ist in drei Sprachen neu (E11): Aufgaben und Ordner als kurze Faktenliste, mit der Aussage, was an Aufgaben geändert werden kann und was nicht (E8, E14), einschließlich der Grenze, dass Aufgaben nicht gelöscht werden (E13, Owner 12.11.2026). Der Entwurf wird dem Owner vor dem Release gezeigt; der SHA-256-Pin wird erst nach seiner Freigabe erneuert.
- [ ] **EXAPP-14**: Release 0.8.0 ist im Store: Version an allen Stellen, die der Versionstest prüft; `CHANGELOG.md`, `CHANGELOG.de.md` und `CHANGELOG.fr.md` tragen denselben 0.8.0-Block; Gesamtlauf aller Gates lokal und im CI einschließlich `canary-nc35`; Umlaut-Audit der nutzersichtbaren Texte; Runbook mit Nachweiszeilen; Signatur über das heruntergeladene Asset. Push, Tag und Submit jeweils nur mit Owner-Freigabe.
- [ ] **EXAPP-15**: Für #32 und #44 liegen kurze Antwortentwürfe vor, ohne schließende Schlüsselwörter. Gepostet wird erst nach dem Store-Release, vom Owner oder mit seiner Freigabe.

## Future Requirements (deferred)

Keine. Der Owner hat am 11.11.2026 entschieden, dass kein 0.8.1 eingeplant wird. Was ein Abbruchkriterium des Spikes aus 0.8.0 nimmt, wird per Owner-Entscheid hierher verschoben und nicht still gestrichen; das Löschen einer Aufgabe hat der Owner am 12.11.2026 nach Out of Scope gelegt (E13), nicht hierher.

## Out of Scope

Was auch nach dem Owner-Entscheid vom 11.11.2026 draußen bleibt:

- Aufgabenlisten anlegen, umbenennen, freigeben oder löschen: Verwaltung bleibt in der Tasks-App
- Wiederkehrende Aufgaben ändern oder abhaken und jede RRULE-Expansion: bewusste Grenze des Projekts; ändernde Zugriffe auf wiederkehrende Aufgaben werden abgelehnt, sofern MESS-05 nichts anderes ergibt
- Mehrere Aufgaben in einem Aufruf ändern, ausgenommen die Unteraufgaben einer genannten Aufgabe beim Abhaken und Verschieben (Owner-Entscheid vom 12.11.2026)
- Eine Aufgabe löschen (TMOD-07): Owner-Entscheid vom 12.11.2026 (Auswahl "Löschen raus", Aufwand gegen Nutzung), obwohl MESS-06 "wiederherstellbar" ergab; Löschen bleibt in der Tasks-App, der Store-Text nennt die Grenze
- Zwischenzustände setzen (`IN-PROCESS`, `CANCELLED`, Prozentwerte zwischen 0 und 100), Erinnerungen (`VALARM`), Ort, URL, Klassifizierung, Sortierung und Anheften: nur die in E7 und E8 genannten Felder
- `ATTACH` lesen oder schreiben: das Bundle würde dateitragend
- Deck über CalDAV (`app-generated--`): Doppelung zu `deck_browse` und Abfluss der Kartenbeschreibung (E9)
- Ein Tasks-Bein in `prepare_context`
- Kalendertermine ändern oder löschen: das Kalender-Bundle bleibt create-only
- Ordner umbenennen, verschieben oder löschen
- Ein Schalter `create_parents` an `files_upload` und der Header `X-NC-WebDAV-Auto-Mkcol`: wäre ein stiller Zweitschreiber; Ordner anlegen ist ein eigener, benannter Aufruf

Nicht hier: Aufgabe verschieben (E14, fest im Umfang). Seit dem Owner-Entscheid vom 12.11.2026 ebenfalls nicht mehr hier: Unteraufgaben beim Abhaken der Elternaufgabe mit abhaken (A16, MESS-05 hat anderes ergeben; `docs/spike-tasks.md`, Abschnitt 10.4).

Stand nach dem Mess-Spike (12.11.2026): das Ergebniswort für das Löschen ist "wiederherstellbar" (`docs/spike-tasks.md`, Abschnitt 4.5), TMOD-07 wäre planbar gewesen und ist seit dem Owner-Entscheid vom 12.11.2026 Out of Scope; das Abbruchkriterium zu `MOVE` ist nicht ausgelöst, TMOD-08 ist planbar.

## Annahmen (nicht belegt, bis zur Messung als Annahme zu führen)

A1 bis A11 stammen aus der Annahmenliste der Recherche, A12 bis A21 aus den Owner-Entscheiden vom 11.11.2026 und aus dieser Planung.

| # | Annahme | Klärung in | Über |
|---|---------|------------|------|
| A1 | `calendarQuery` verhält sich in Nextcloud 33 und 34 wie in 32 und master | Phase 30 | MESS-03 |
| A2 | `RELATED-TO` trägt die UID der Elternaufgabe, Unteraufgaben liegen in derselben Liste | Phase 30 | MESS-03 |
| A3 | Die Tasks-App schreibt Zeiten mit Zone oder UTC, nicht schwebend | Phase 30 | MESS-03 |
| A4 | `{http://owncloud.org/ns}read-only` ist per PROPFIND abrufbar | Phase 30 | MESS-03 |
| A5 | Papierkorb und föderierte Kalender fallen in der Discovery heraus oder sind nur lesbar | Phase 30 | MESS-03 |
| A6 | Größenordnung der Aufgabenzahl und Laufzeit bei 2000 Aufgaben | Phase 30 | MESS-04 |
| A7 | `MKCOL` auf `files/` funktioniert unter AppAPI-Impersonation | Phase 30, erster Punkt, mit Abbruchkriterium | MESS-01 |
| A8 | Gruppenordner-ACL und nur lesbare externe Speicher antworten 403 | Phase 30 (Gruppenordner Pflicht, externer Speicher soweit herstellbar) | MESS-02 |
| A9 | `MKCOL` löst nie 507 aus | Phase 30 (Beobachtung in der Statusmatrix; der Zweig bleibt in jedem Fall) | MESS-01 |
| A10 | Byte-Größen der neuen Werkzeuge; `tasks_create` bleibt mit `tags` und `start` unter 1400 Bytes | Phase 31 (Ordner), Phase 32 (drei Werkzeuge), Phase 33 (ändernde): erst messbar, wenn die Registrierung existiert | FOLD-05, TASK-08, TMOD-05 |
| A11 | Listen mit `VEVENT` plus `VTODO` erscheinen in beiden Bundles (gewollt) | Phase 30 | MESS-03 |
| A12 | Die Tasks-App setzt beim Abhaken `STATUS`, `PERCENT-COMPLETE`, `COMPLETED` und beim Wiederöffnen das Gegenstück; Zeitformat UTC | Phase 30 | MESS-05 |
| A13 | `PUT` mit `If-Match` funktioniert unter AppAPI-Impersonation, veraltete ETag ergibt 412 | Phase 30, mit Abbruchkriterium | MESS-05 |
| A14 | Der Server speichert unbekannte `X-`Eigenschaften und übrige Eigenschaften beim `PUT` unverändert | Phase 30, mit Abbruchkriterium | MESS-05 |
| A15 | Wiederkehrende Aufgaben lassen sich nicht sinnvoll in einem Objekt abhaken; Vorgabe bis zur Messung: ablehnen | Phase 30 | MESS-05 |
| A16 | Das Abhaken einer Elternaufgabe hakt Unteraufgaben nicht mit ab (auch nicht serverseitig) | Phase 30 | MESS-05 |
| A17 | Ein überschreibender `PUT` berührt `EXPECTED_PUT_CALLS`, das Destruktiv-Gate und die create-only-Aussagen in README, `docs/threat-model.md`, Store-Text und Server-Instruktion; die Liste ist vollständig | Phase 30 (Inventar), abgearbeitet in Phase 33 und 34 | MESS-05, TMOD-01, DOC-05 |
| A18 | Eine per CalDAV gelöschte Aufgabe landet im Papierkorb des Kalenders und bleibt wiederherstellbar, auf Nextcloud 32 bis 35, auch für geteilte Listen; Verhalten bei abgeschaltetem Papierkorb unbekannt; ob sich vorab prüfen lässt, dass der Papierkorb wirkt | Phase 30, entscheidet E13 | MESS-06 |
| A19 | `MOVE` zwischen zwei Aufgabenlisten funktioniert unter AppAPI-Impersonation, erhält die UID und überschreibt kein belegtes Ziel | Phase 30, mit Abbruchkriterium | MESS-06 |
| A21 | Unteraufgaben beim Verschieben und Löschen der Elternaufgabe: Vorgabe bis zur Messung ist Ablehnen; ziehen die Kinder in der Tasks-App mit, folgt der Connector dem Gemessenen | Phase 30 | MESS-06 |
| A20 | Schätzwerte der Recherche zu Aufwand und Planzahl (35 Minuten je Plan) gelten nur für den dort untersuchten Umfang | keine Phase; steht nur im Bericht, nicht in STATE.md | |

Stand je Annahme nach dem Mess-Spike: docs/spike-tasks.md, Abschnitt 8. Zu A15, A16 und A21 hat der Owner am 12.11.2026 entschieden (Abschnitt 10.4 desselben Berichts).

## Offene Fragen für die discuss-phase

1. Phase 31: neuer Wortlaut des Hinweistexts von `parent_missing` (eine Quelle für alle Paarvergleiche).
2. Phase 32: liefert `tasks_read` Unteraufgaben gekappt mit (ein zusätzlicher REPORT je Aufruf)? Empfehlung der Recherche: ja.
3. Phase 32: Tasks-App in die Test- und CI-Instanz aufnehmen (das Bootstrap installiert sie heute nicht)?
4. Phase 33: reicht die im selben Aufruf gelesene ETag, oder muss das Modell die ETag aus `tasks_read` mitgeben (Präzedenz `files_update`)?
5. Phase 33: Felder leeren (Fälligkeit entfernen, Elternbezug lösen) über `tasks_update`, und mit welcher Schreibweise?
6. Phase 33: endgültiger Name von `tasks_complete`.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MESS-01 | Phase 30 | Complete |
| MESS-02 | Phase 30 | Complete |
| MESS-03 | Phase 30 | Complete |
| MESS-04 | Phase 30 | Complete |
| MESS-05 | Phase 30 | Complete |
| MESS-06 | Phase 30 | Complete |
| FOLD-01 | Phase 31 | Complete |
| FOLD-02 | Phase 31 | Complete |
| FOLD-03 | Phase 31 | Complete |
| FOLD-04 | Phase 31 | Complete |
| FOLD-05 | Phase 31 | Complete |
| FOLD-06 | Phase 31 | Complete |
| TASK-01 | Phase 32 | Pending |
| TASK-02 | Phase 32 | Complete |
| TASK-03 | Phase 32 | Pending |
| TASK-04 | Phase 32 | Complete |
| TASK-05 | Phase 32 | Complete |
| TASK-06 | Phase 32 | Complete |
| TASK-07 | Phase 32 | Pending |
| TASK-08 | Phase 32 | Complete |
| TASK-09 | Phase 32 | Pending |
| TMOD-01 | Phase 33 | Pending |
| TMOD-02 | Phase 33 | Pending |
| TMOD-03 | Phase 33 | Pending |
| TMOD-04 | Phase 33 | Pending |
| TMOD-05 | Phase 33 | Pending |
| TMOD-06 | Phase 33 | Pending |
| TMOD-07 | Out of Scope (Owner, 12.11.2026) | Gestrichen |
| TMOD-08 | Phase 33 | Pending |
| DOC-04 | Phase 34 | Pending |
| DOC-05 | Phase 34 | Pending |
| EXAPP-13 | Phase 34 | Pending |
| EXAPP-14 | Phase 34 | Pending |
| EXAPP-15 | Phase 34 | Pending |

**Coverage:** 33/33 v1-Requirements zugeordnet (Phase 30: 6, Phase 31: 6, Phase 32: 9, Phase 33: 7, Phase 34: 5), keine Waisen, keine Doppelungen. TMOD-07 ist seit dem 12.11.2026 Out of Scope und zählt nicht mehr mit. Anders als in v1.7 trägt der Mess-Spike eigene Requirements, weil E12 eine Messung ausdrücklich verlangt und zwei Abbruchkriterien an ihm hängen.

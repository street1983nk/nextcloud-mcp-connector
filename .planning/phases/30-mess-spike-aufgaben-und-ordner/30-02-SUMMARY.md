---
phase: 30-mess-spike-aufgaben-und-ordner
plan: 02
subsystem: messung / ändernde Zugriffe auf Aufgaben (CalDAV VTODO) auf nc35, Tasks-App, Inventar der Zusagen
tags: [spike, caldav, vtodo, if-match, etag, appapi, impersonation, tasks-app, inventar, messung]
requires:
  - 30-01 (Messskript scripts/tasks_spike.py, RAM-Gate, Baseline, Rückbau)
provides:
  - scripts/tasks_spike.py (Blöcke modify, ui-prepare, ui-snapshot, ui-log, ui-evaluate, inventory, ui-teardown)
  - docs/spike-tasks.md (Abschnitte 3 und 7, Ergänzungen in 11, Rohauszüge 12.3 bis 12.5)
  - raw/nc35-aendern.txt (ändernde Zugriffe unter Impersonation, Rückbau)
  - raw/ui-sitzung.txt, raw/ui-a/, raw/ui-b/ (Browser-Sitzung in der Tasks-App 0.18.1, je Objekt eine Datei vor und nach den Änderungen)
  - raw/inventar.txt (Inventar A17 mit Datei und Zeile, Kette zu E15)
  - 30-02-BROWSER-SCHRITTE.md (die zwölf Schritte der Sitzung)
affects: [30-03, 30-04, 30-05, 33, 34]
tech-stack:
  added: []
  patterns:
    - "überschrieben und unverändert kommen aus dem sha256 der Datenbankspalte calendardata, nie aus dem Statuscode"
    - "ein Lauf, der Konten für eine spätere Sitzung stehen lässt, endet ohne Rückbau; ui-teardown liest die Baseline aus den BASELINE-START-Zeilen desselben Protokolls"
    - "was eine App im Browser schreibt, wird dreifach belegt: Rohobjekte je UID vor und nach der Sitzung, zweiter Leseweg mit App-Passwort, Zugriffsprotokoll des Webservers mit Statuscode"
    - "Inventar: zwei Suchmuster ohne gemeinsamen Suchbegriff, eine Regel je Fundstelle, ein Treffer ohne Regel lässt den Block scheitern"
key-files:
  created:
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/nc35-aendern.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/ui-sitzung.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/ui-a/ (15 Objekte)
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/ui-b/ (15 Objekte)
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/inventar.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/30-02-BROWSER-SCHRITTE.md
  modified:
    - scripts/tasks_spike.py
    - tests/unit/test_tasks_spike.py
    - vulture_whitelist.py
    - docs/spike-tasks.md
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/deferred-items.md
decisions:
  - "A13 belegt: PUT mit If-Match auf die gelesene ETag antwortet unter AppAPI-Impersonation mit 204, eine veraltete ETag mit 412 bei unverändertem Objekt; Abbruchkriterium MESS-05 If-Match nicht ausgelöst"
  - "A14 belegt: der Server speichert ein Kalenderobjekt wörtlich und pflegt kein Feld von sich aus; Abbruchkriterium MESS-05 Eigenschaften nicht ausgelöst"
  - "Eine nur lesbare geteilte Liste lehnt PUT mit 404 ab, nicht mit 403, obwohl dasselbe Objekt lesbar ist"
  - "A12 belegt mit Präzisierung: die Tasks-App setzt beim Abhaken STATUS:COMPLETED, PERCENT-COMPLETE:100, COMPLETED in UTC und zieht LAST-MODIFIED und DTSTAMP nach; beim Wiederöffnen setzt sie STATUS:NEEDS-ACTION und entfernt COMPLETED und PERCENT-COMPLETE"
  - "A15: die Tasks-App erledigt eine wiederkehrende Aufgabe nicht, sie schiebt DUE auf den nächsten Termin; ein PUT am Master erledigt serverseitig die ganze Serie. Die Vorgabe ablehnen bleibt von der Messung her bestehen"
  - "A16: serverseitig belegt, als Aussage über die Tasks-App widerlegt: die App hakt die Unteraufgabe mit einem eigenen PUT mit ab. Ob der Connector davon abweicht, entscheidet der Owner in 30-05"
  - "A17: Inventar mit 114 berührten Fundstellen auf Commit 32b8df0, Positivkontrolle 6/6, 302 Treffer mit Grund ausgeschlossen"
metrics:
  duration: "ca. 100 min Executor-Zeit in zwei Aufträgen, dazwischen die Browser-Sitzung der Hauptsitzung"
  completed: 2026-11-11
  tasks: 3
  files: 11
---

# Phase 30 Plan 02: Ändernde Zugriffe unter Impersonation, Tasks-App im Browser, Inventar der Zusagen Summary

`PUT` mit `If-Match` trägt unter AppAPI-Impersonation (204, veraltete ETag 412), der Server speichert wörtlich und pflegt kein Feld, beide Abbruchkriterien von MESS-05 sind nicht ausgelöst. Die Tasks-App 0.18.1 wurde in einer Browser-Sitzung beobachtet und über Rohobjekte ausgewertet: sie verhält sich bei Unteraufgaben und wiederkehrenden Aufgaben anders, als A15 und A16 annahmen. Das Inventar A17 liegt mit Datei und Zeile vor.

## Befunde

Gelesene Fassungen (aus der laufenden Instanz, 2026-11-11): Nextcloud 35.0.0 (`occ status`), `app_api` 35.0.0, ExApp `mcp_connector` 0.3.2, Datenbank `sqlite3`, Tasks-App 0.18.1 (`occ app:list --output=json` nach `occ app:install tasks`, vorher nicht installiert). Browser: Chromium des Playwright-MCP, Zeitzone Europe/Berlin, Konto `spike30ui` mit Sprache Deutsch.

### Serverseite (Rohbeleg raw/nc35-aendern.txt, Bericht 3.1 bis 3.4)

| Punkt | Ergebnis |
|---|---|
| M3.1 PUT mit gelesener ETag, Impersonation | 204, neue starke ETag auch im Antwortkopf, Datenbank byte-gleich zum Gesendeten; Logzeile in `exapp_impersonation.log`, multiget mit App-Passwort gleich, falsches Secret 401 ohne Änderung |
| M3.2 veraltete ETag | 412 `PreconditionFailed`, Objekt unverändert (Hash, GET, ETag) |
| Abbruchkriterium If-Match | `ABBRUCHKRITERIUM MESS-05 IF-MATCH ausgeloest=nein grund=keiner`; mit App-Passwort dieselben vier Werte |
| M3.3 ohne If-Match, mit `If-Match: *` | beide 204, beide überschreiben |
| M3.4 fremde Eigenschaften | 37 Zeilen vorher und nachher, geändert nur `SUMMARY`; Kontrollobjekt meldet genau die entfernte X-Zeile; `PFLEGEFELDER server=keine` |
| Abbruchkriterium Eigenschaften | `ABBRUCHKRITERIUM MESS-05 EIGENSCHAFTEN ausgeloest=nein verloren=keine put_status=204 aenderung_angekommen=ja kontrolle=ok` |
| M3.5 nur lesbare geteilte Liste | GET 200, PUT 404 (`Node with name ... could not be found`), Anlegen 404, beim Eigentümer unverändert; mit Schreibrecht 204 |
| M3.6 wiederkehrend | PUT am Master 204, wörtlich gespeichert, `RRULE` bleibt, kein Folgeobjekt: die Serie steht als erledigt da |
| M3.7 Unteraufgabe | Elternaufgabe neue ETag, Unteraufgabe in ETag, Inhalt und Hash unverändert |

### Tasks-App (Rohbeleg raw/ui-sitzung.txt, raw/ui-a, raw/ui-b, Bericht 3.5 und 3.6)

| Handlung | Was die App schreibt |
|---|---|
| Abhaken | hinzu `STATUS:COMPLETED`, `PERCENT-COMPLETE:100`, `COMPLETED` in UTC mit `Z`; `LAST-MODIFIED` und `DTSTAMP` auf den Zeitpunkt; kein `SEQUENCE` |
| Wiederöffnen | `STATUS:NEEDS-ACTION`; `COMPLETED` und `PERCENT-COMPLETE` entfernt; `LAST-MODIFIED` und `DTSTAMP` nachgezogen |
| Kontrolle `s30 unberuehrt` | leere Differenz |
| Vergleichsobjekt per Skript-PUT | der Server pflegt kein Feld: `LAST-MODIFIED` und `DTSTAMP` stammen von der App |
| Zeitformen | ganztägig `DUE;VALUE=DATE`, mit Uhrzeit UTC (10:15 Berlin wird `091500Z`), nie `TZID`, nie `VTIMEZONE` |
| Wiederkehrende Aufgabe abhaken | nicht erledigt: `DUE` einen Tag weiter, `RRULE` bleibt, kein `STATUS`, kein `COMPLETED`, kein neues Objekt |
| Elternaufgabe abhaken | zwei PUT: Unteraufgabe 204 (erledigt), Elternaufgabe 500 (`database is locked`); auf dem Server ist die Unteraufgabe erledigt und die Elternaufgabe offen |
| Verschieben | `MOVE` je Objekt, 201; die Unteraufgabe wandert mit einem eigenen `MOVE` mit; Name und Inhalt unverändert |
| Löschen | `DELETE` je Objekt, 204; auch die Unteraufgabe; beide mit unverändertem Inhalt im Papierkorb des Kalenders |
| Liste anlegen | `MKCOL`, nicht `MKCALENDAR`; Komponenten-Set `VTODO`; das Konto hat daneben `personal` mit `VEVENT`, `VTODO`, `VJOURNAL` |

Der Widerspruch bei `s30 eltern-abhaken`: die Oberfläche zeigte nach dem Klick beide Aufgaben als erledigt und nach einem Neuladen die Elternaufgabe wieder als offen. Erklärt durch drei unabhängige Quellen: Rohobjekt und ETag der Elternaufgabe in Stand b unverändert, Statuscode 500 für ihren `PUT` im Zugriffsprotokoll, Ausnahme `database is locked` im Serverprotokoll. Die App zeigt den gewünschten Zustand sofort an und hat den gescheiterten `PUT` nicht gemeldet.

### Annahmen

| Annahme | Stand |
|---|---|
| A12 | belegt, mit Präzisierung (Wiederöffnen entfernt zwei Felder; `LAST-MODIFIED` und `DTSTAMP` gehören dazu) |
| A13 | belegt, Abbruchkriterium nicht ausgelöst |
| A14 | belegt, Abbruchkriterium nicht ausgelöst |
| A15 | die Vorgabe "ablehnen" bleibt bestehen; die App schreibt die Serie fort, der Server kennt nur "ganze Serie erledigt" |
| A16 | Serverseite belegt; als Aussage über die App widerlegt (die App hakt die Unteraufgabe mit ab). Entscheid beim Owner in 30-05 |
| A17 | Inventar liegt vor; vollständig im Sinn der beiden Muster, Grenze in Bericht 7.4 |
| A21 (Vorarbeit für 30-03) | Rohobjekte gesichert: die App nimmt beim Verschieben und beim Löschen die Unteraufgabe mit, je mit eigenem Aufruf; Auswertung in 30-03 |

### Inventar A17 (Rohbeleg raw/inventar.txt, Bericht Abschnitt 7)

Commit `32b8df0`. Muster 1 (Wortlaut in drei Sprachen) 242 Treffer, Muster 2 (Konstanten, Methodenliterale, Testnamen, HTTP-Wörter) 191 Treffer, zusammen 416 Zeilen. Im Inventar 114: gate 46, annotation 4, audit 10, kanarie 2, zusage-server 2, zusage-store 3, zusage-doku 47; 302 mit Grund ausgeschlossen, 0 ungeklärt. Positivkontrolle 6/6. 41 Stellen des Inventars fand nur Muster 2. Die Kette zu E15 (`NC_MCP_FILES_UPDATE`): 12 Stellen im Quelltext und in `appinfo/info.xml`, 38 Treffer in sieben Testdateien, 15 Stellen in öffentlichen Texten.

### Bedeutung für Phase 33

- Die Schreibschiene aus TMOD-01 trägt. Ohne `If-Match` und mit `If-Match: *` überschreibt der Server; das Verbot beider Formen ist begründet.
- Der Erhalt fremder Eigenschaften hängt allein am Connector, der Server ändert nichts. Pflegefelder muss der Connector selbst setzen.
- Ein 404 auf einen PUT nach erfolgreichem Lesen heißt in einer geteilten Liste "kein Schreibrecht".
- Ein 5xx auf einen PUT ist nie ein Erfolg; auf SQLite genügen zwei gleichzeitige Schreibzugriffe dafür.
- Offen für den Owner (30-05): Unteraufgaben beim Abhaken wie die App mit abhaken oder nicht; wiederkehrende Aufgaben ablehnen.

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | 916843e (Kriterien), 0b6a36e (Tests), 26a1fce und 2dc80fa (Blöcke), b1acf1f (Rohprotokoll, Bericht 3.1 bis 3.4, Schrittdatei) | Abbruchmessungen, Serverseite, Tasks-App und Konto bereitgestellt |
| 2 | Checkpoint, von der Hauptsitzung mit Playwright gefahren | zwölf Schritte in zwei Runden, Stand a dazwischen gesichert |
| 3 | b4566b6 (Tests), 98af057, 32b8df0 und f6d150b (Blöcke), cbdf791 (Rohdateien und Bericht), 142b8eb (Rohobjekte byte-genau) | Stand b, Auswertung, Inventar, Rückbau, Bericht |

Der Commit 916843e mit den Kriterien liegt vor `raw/nc35-aendern.txt`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Papierkorb des Kalenders antwortet auf PROPFIND mit 501**
- **Found during:** Vorbereitung des Checkpoints, Probelauf von ui-snapshot
- **Issue:** Die Sammlung `trashbin/objects` kennt nur den REPORT `calendar-query`.
- **Fix:** ui-snapshot liest den Papierkorb per REPORT; die Objekte heißen dort `<id>.ics`, die Zuordnung läuft deshalb über die UID.
- **Commit:** 2dc80fa

**2. [Rule 2] Dritter Beleg für die Browser-Sitzung (Block ui-log)**
- **Found during:** Task 3, Auswertung von `s30 eltern-abhaken`
- **Issue:** Die Rohobjekte zeigten eine unveränderte Elternaufgabe, die Oberfläche hatte sie als erledigt gezeigt. Aus zwei Ständen allein ist nicht zu unterscheiden, ob die App nicht geschrieben hat oder ob der Schreibzugriff scheiterte.
- **Fix:** Block ui-log liest die schreibenden Aufrufe des Kontos mit Statuscode aus dem Zugriffsprotokoll und die Serverfehler dazu; außerdem die rohe Discovery des Kontos, bevor es gelöscht wurde (für 30-04).
- **Commits:** 98af057, f6d150b

**3. [Rule 1 - Bug] Erster Entwurf von Muster 1 zu eng**
- **Found during:** Task 3, Vergleich der beiden Muster
- **Issue:** Muster 1 fand `README.md:42` ("No deleting"), die Zeilen zum Verschieben und Umbenennen und den Satz "Read and create content" der Server-Instruktion nicht.
- **Fix:** Muster 1 vor der Auswertung um diese Stämme erweitert; im Bericht (Abschnitt 7) benannt.
- **Commit:** 98af057

### Sonstiges

- **Zugangsdaten statt `.env.spike30`:** die Datei ist nicht git-ignoriert. Nach der Ausweichregel des Plans lagen Benutzername, Passwort und Basis-URL in einer Datei außerhalb des Repositorys (`--ui-file`); das Skript lehnt einen Pfad im Repository ab. ui-teardown hat die Datei gelöscht. Das Passwort wurde nie auf der Konsole ausgegeben (strenger als der Plan).
- **Listen der Sitzung nicht vorab angelegt:** `spike30-liste-1` und `-2` hat Schritt 1 in der App angelegt, weil sie Fixtures für 30-04 sind. Die Hauptsitzung war darüber informiert.
- **Reihenfolge in Runde A:** die Hauptsitzung hat erst alle Aufgaben, dann die Unteraufgaben, dann die Eigenschaften angelegt; inhaltlich wie verlangt. Datumswerte ließen sich nur über den Datumswähler setzen, dadurch mehrere Schreibvorgänge je Aufgabe.
- **Stand a erst im neunten Versuch:** acht Läufe endeten am RAM-Tor (3,87 bis 3,97 GB frei, Schwelle 4,0, der Browser lief). Sie stehen als RUN FAILED in `raw/ui-sitzung.txt` und haben nichts gelesen.
- **Vergleichsobjekt im Konto spike30a:** das per Skript abgehakte Objekt liegt in einer Liste von `spike30a`, damit das Konto der Sitzung unberührt blieb.
- **ui-log lief zweimal:** der zweite Lauf hält zusätzlich die rohe Discovery fest und ist im Protokoll als Wiederholung benannt.
- **Positivkontrolle des Inventars:** Muster 1 sucht Wortlaut und kann die Konstanten `EXPECTED_PUT_CALLS` und `FORBIDDEN` nicht nennen. Als gefunden zählt ein Treffer von Muster 1 im Gate höchstens zwölf Zeilen von der Konstante. Das Gate `tests/contract/test_no_destructive_calls.py` gehört deshalb zu den Dateien von Muster 1.
- **Zuordnung im Inventar über Regeln:** jede Fundstelle wurde gelesen; festgehalten ist die Zuordnung als Regeltabelle im Skript, nicht als Einzelentscheid je Zeile.
- **Server-Instruktion Phase 34 zugeordnet**, weil DOC-05 sie nennt, obwohl sie unter `src/` steht.
- **Sprache des Messkontos** im gemessenen Lauf von Hand gesetzt (`occ user:setting`), im Skript für künftige Läufe nachgezogen.
- **ui-teardown schon in Task 1 gebaut**, damit ein Wiederholungslauf möglich gewesen wäre; gebraucht wurde keiner.
- **TDD:** die Tests entstanden je vor dem Code und sind als eigene Commits festgehalten (0b6a36e, b4566b6). Der Test für `baseline_from_protocol` kam zusammen mit seinem Code.
- **DI-30-01 erledigt:** die Umgebung trägt das Extra `documents`; der volle Lauf ist ohne Ausnahmen grün.
- **Rohobjekte byte-genau:** git speicherte die `.ics`-Dateien zunächst mit LF statt mit dem CRLF des Servers (`* text=auto`). Eine Zeile in `.gitattributes` (`-text` für die `.ics`-Dateien unter `raw/`) hält sie jetzt byte-genau (142b8eb); die Datei stand nicht in der Dateiliste des Plans.
- `.env.nc35` wurde aus dem Hauptcheckout nur gelesen. Kein Push, kein PR, kein Kommentar.

## Zustand nach dem Rückbau

- nc35: alle zwölf BASELINE-Zeilen gleich=ja; kein Konto mit Präfix spike30; Tasks-App deaktiviert, entfernt, ihre drei Konfigurationswerte gelöscht; keine gelöschten Kalender oder Kalenderobjekte zurückgeblieben.
- Container `nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc_app_mcp_connector` gestoppt. Kein fremder Container angefasst.
- Rest, der bleibt: was `occ app:remove tasks` an Datenbankeinträgen der App stehen lässt, ist nicht geprüft (wie bei `groupfolders` in 30-01).
- Die Datei mit den Zugangsdaten des Messkontos ist gelöscht.

## Was ungemessen blieb

Vollständig in docs/spike-tasks.md, Abschnitt 11. Kurz: alles nur auf Nextcloud 35.0.0 mit SQLite und Tasks 0.18.1; Felder, die die App beim Abhaken in eine Elternaufgabe schreibt (ihr PUT scheiterte mit 500, nichts nachgestellt); Zwischenstand von `s30 wieder-oeffnen`; ob die App für eine Wiederholung ein Datum verlangt; andere Wiederholungsformen; nur lesbare Liste nur als Freigabe an ein einzelnes Konto; ETag im Antwortkopf, wenn der Server den Text verändert; Wortlaut der Konsolenfehler des Browsers; Zusagen in einem Wortlaut außerhalb beider Suchmuster.

## Known Stubs

Keine. Die Abschnitte 4 bis 6 und 8 bis 10 des Berichts tragen mit Absicht den Vermerk "offen" samt dem Plan, der sie füllt.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus. T-30-08 bis T-30-13 umgesetzt: Passwort des Messkontos nur in einer Datei außerhalb des Repositorys und über stdin, Scan vor jedem Schreiben und vor jedem Commit (37 Dateien, 0 Funde), eigene Konten mit Rückbau und Baseline-Vergleich, überschreibender PUT nur aus dem Messskript gegen Listen mit Präfix, Inventar mit zwei Mustern und Positivkontrolle, Stand a vor Runde B gesichert samt Kontroll- und Vergleichsobjekt.

## Self-Check: PASSED

- Dateien vorhanden: raw/nc35-aendern.txt, raw/ui-sitzung.txt, raw/inventar.txt, raw/ui-a (15), raw/ui-b (15), 30-02-BROWSER-SCHRITTE.md, docs/spike-tasks.md mit den Abschnitten 3.1 bis 3.6 und 7
- Commits vorhanden: 916843e, 0b6a36e, 26a1fce, 2dc80fa, b1acf1f, b4566b6, 98af057, 32b8df0, f6d150b, cbdf791, 142b8eb

# Mess-Spike Aufgaben und Ordner (MESS-01 bis MESS-06)

**Status:** läuft. Die Abschnitte 1 (MESS-01) und 2 (MESS-02) sind gemessen, das Abbruchkriterium zu MESS-01 ist nicht ausgelöst. Abschnitt 3 (MESS-05) ist gemessen, beide Abbruchkriterien zu MESS-05 sind nicht ausgelöst, und Abschnitt 7 trägt das Inventar der Gates und Zusagen (A17). Aus Abschnitt 4 (MESS-06) sind 4.1 und 4.2 gemessen: `MOVE` unter Impersonation und das Verhalten der Unteraufgaben, das Abbruchkriterium zu MESS-06 für das Verschieben ist nicht ausgelöst; das Löschen ist auf Nextcloud 32 bis 35 gemessen (4.3 bis 4.5) und trägt das Ergebniswort "wiederherstellbar". Abschnitt 4 (MESS-06) ist damit gemessen. Die Abschnitte 5, 6 und 8 bis 10 sind offen
**Messzeitraum:** ab 2026-11-11 (erster Messlauf 11:55 UTC), Ende offen
**Nextcloud:** 35.0.0 (Build 35.0.0.10), gelesen mit `occ status` am 2026-11-11 aus dem laufenden Container `nc35-nc`. Das Image heißt `nextcloud:35.0.0-apache-local` und ist lokal aus dem veröffentlichten Quellpaket gebaut (`compose.nc35.yml`, Kopfkommentar). Für die Löschmatrix (Abschnitt 4.3) liefen am 2026-11-11 nacheinander vier Wegwerf-Instanzen aus `compose.spike-tags.yml` mit den offiziellen Images; ihre Fassungen of record, je gelesen mit `occ status` in der laufenden Instanz, sind 32.0.15, 33.0.9, 34.0.4, 35.0.2 (Zeile `VERSION OF RECORD` in `raw/loeschen-32.txt` bis `raw/loeschen-35.txt`)
**AppAPI:** `app_api` 35.0.0, gelesen mit `occ app:list --output=json` derselben Instanz am 2026-11-11
**Diese ExApp:** 0.3.2, gelesen mit `occ app_api:app:list` am 2026-11-11. In der Topologie ist also ein älterer Stand registriert als der Arbeitsbaum. Für die Messung zählt das an zwei Stellen: die Impersonation läuft mit dem Secret dieser Registrierung, und der Produktionsweg (Abschnitt 1.2) läuft im Container dieses Images. Kein Werkzeug der App wird gemessen, nur ihr Zugang zu Nextcloud
**groupfolders:** 23.0.1, gelesen mit `occ app:list --output=json` am 2026-11-11 nach `occ app:install groupfolders` in der laufenden Instanz (Protokollzeile `GRUPPENORDNER version=23.0.1 installiert_vorher=nein (gelesen mit occ app:list --output=json)`). Die App wurde für die Messung aus dem App Store geladen und danach wieder entfernt. `files_external` 2.0.0-dev.0 gehört zum Server und war nur für die Messung eingeschaltet
**Tasks:** 0.18.1, gelesen mit `occ app:list --output=json` am 2026-11-11 nach `occ app:install tasks` in der laufenden Instanz (Protokollzeile `TASKS-APP version=0.18.1 installiert_vorher=nein (gelesen mit occ app:list --output=json)`). Die App war für die Messung aus dem App Store geladen und ist im Rückbau wieder entfernt worden. Die Browser-Sitzung lief am 2026-11-11 in Chromium (Playwright), Zeitzone des Browsers Europe/Berlin, Sprache des Messkontos Deutsch
**Deck:** offen, füllt Plan 30-04
**Datenbank:** `sqlite3`, gelesen mit `occ config:system:get dbtype` am 2026-11-11
**Topologie:** die vorhandene Strecke `compose.nc35.yml` (Container `nc35-nc`, `nc35-harp`, `nc35-caddy`, ExApp-Container `nc_app_mcp_connector`, Loopback `http://127.0.0.1:8082`). Sie wird nur mit `docker start` und `docker stop` bewegt, nie abgebaut. Weitere Instanzen für die Versionsbreite nennen die Pläne 30-03 und 30-04
**Messskript:** `scripts/tasks_spike.py`; der Commit, der das Skript zusammen mit diesen Kriterien festschreibt, liegt vor jeder Rohdatei unter `.planning/phases/30-mess-spike-aufgaben-und-ordner/raw/`. Das ist Commit `63ad052`; die Blöcke `mkcol`, `groupfolder` und `nachlauf` kamen danach dazu, ohne dass sich Kriterien oder Erwartungen geändert haben
**Scope:** gemessen wird gegen laufende Nextcloud-Instanzen in lokalem Docker, was die Phasen 31 bis 33 bisher nur annehmen: Ordner anlegen mit `MKCOL`, auch unter AppAPI-Impersonation und in einem Gruppenordner mit ACL, danach die Aufgaben-Zugriffe über CalDAV. Es entsteht kein Produktcode: unter `src/` ändert diese Phase nichts, und jeder schreibende Aufruf läuft aus dem Messskript.

Jede Fassungszeile im Kopfblock trägt entweder einen Wert, der aus der laufenden Instanz gelesen wurde, samt Lesebefehl und Datum, oder den Vermerk "offen" mit dem Plan, der sie füllt. Ein Wert aus der Recherche steht dort an keiner Stelle.

## Entscheidungskriterien, vorab festgelegt

Die Kriterien stehen hier, bevor der erste Messwert entsteht, damit die Zahlen sie nicht nachträglich verschieben können. Der Commit dieses Abschnitts liegt vor jeder Rohdatei der Phase.

**Gemessen** heißt: ein benannter Aufruf, ein Messwert aus genau diesem Aufruf, eine Positivkontrolle (das Verfahren greift), eine Gegenprobe mit einem anderen Muster als die Messung, und der Nutzername, unter dem der Aufruf lief. Kein Nutzername, kein Messwert.

**Gelesen** heißt: die Aussage stammt aus Quelltext, Dokumentation oder einem Hilfetext und nicht aus einem Aufruf gegen die laufende Instanz. Was nur gelesen ist, wird in diesem Bericht nie als gemessen bezeichnet.

**Ungemessen** heißt: die Messung war nicht möglich, und Grund, Datum und Rohausgabe stehen an derselben Stelle dabei. Ungemessen ist ein zulässiges Ergebnis und kein Mangel; eine nicht durchgeführte Messung widerlegt nichts.

Die Erwartung je Zeile der Statusmatrix stammt aus der Recherche (`.planning/research/v1.8-tasks-080-RESEARCH.md`, Abschnitt B2) und steht im Messskript in `mkcol_expectations()`. Weicht ein gemessener Status ab, ist das ein Befund über Nextcloud; weder die Erwartung noch der Messwert wird nachträglich angepasst.

Kriterien des Plans 30-01:

| Messung | Was als Ergebnis zählt | Positivkontrolle (das Verfahren greift) | Gegenprobe (anderes Muster) |
|---------|------------------------|------------------------------------------|------------------------------|
| M1.1 MKCOL freier Name unter Impersonation (A7) | genau Status 201; jeder andere Status löst das Abbruchkriterium aus | PROPFIND Depth 0 auf denselben Pfad vorher 404; Zeile `"method":"MKCOL"` mit dem Messnutzer in `exapp_impersonation.log`; Kontrolle a (cloud/user nennt den Messnutzer) | nicht über DAV: `test -d` auf dem Datenverzeichnis im Container zeigt den Ordner; derselbe Aufruf mit falschem APP_SECRET legt nichts an (Dateisystem leer); MKCOL in das Home eines anderen Kontos legt nichts an |
| M1.2 Statusmatrix | je Zeile der gelieferte Statuscode samt `s:exception` und `s:message`; Erwartung aus der Recherche steht daneben, eine Abweichung ist ein Befund | Zeile "freier Name" derselben Serie liefert 201 | Dateisystem-Prüfung je Zeile (angelegt ja oder nein); Vergleich Impersonation gegen App-Passwort je Zeile |
| M1.3 geteilter Ordner ohne Schreibrecht | Status ungleich 2xx und nichts angelegt | derselbe Aufruf in eine Freigabe mit Anlegerecht liefert 201 | Dateisystem beim Eigentümer; `oc:permissions` des Ordners per PROPFIND ohne `C` und `K` |
| M1.4 Sandbox-Wurzel | drei Statuscodes: Wurzel vorhanden plus Unterordner, Wurzel fehlt plus Unterordner, Wurzel selbst als Ziel | die gemessene URL ist die, die `dav.files_url` mit gesetzter Wurzel baut | Dateisystem-Prüfung |
| M1.5 Kontingent (A9) | Statuscode von MKCOL bei erschöpftem Kontingent; 507 widerlegt A9 | ein PUT von 1 KiB in dasselbe Konto liefert 507, das Kontingent wirkt also | Dateisystem-Prüfung |
| M2.1 Gruppenordner mit Schreibrecht (E12) | Status 201 und Ordner vorhanden | Gruppenordner erscheint im PROPFIND des Homes | Dateisystem unter `__groupfolders/<id>/` |
| M2.2 Gruppenordner ohne Schreibrecht, Negativtest (E12, A8) | Status ungleich 2xx und nichts angelegt; der genaue Code belegt oder widerlegt A8 (403) | zweites Konto ohne ACL-Einschränkung legt im selben Ordner an (201); nach Entzug der Regel legt auch das Messkonto an (201) | Dateisystem unter `__groupfolders/<id>/`; `oc:permissions` und, falls vorhanden, `nc:acl-list` per PROPFIND |
| M2.3 Gruppe mit reinem Leserecht | Status ungleich 2xx und nichts angelegt | M2.1 | Dateisystem |
| M2.4 nur lesbarer externer Speicher (A8) | Status ungleich 2xx und nichts angelegt; sonst ungemessen mit Grund | derselbe Speicher ohne `readonly` liefert 201 | Dateisystem im Zielverzeichnis des lokalen Speichers |

Zwei Regeln des Messskripts gehören zu den Kriterien, weil sie entscheiden, was eine Zeile bedeutet:

- "angelegt" heißt in jeder Zeile: der Ordner steht nach dem Aufruf im Dateisystem des Containers und stand vor dem Aufruf nicht dort. Ein Ordner, den es schon gab, zählt nicht als angelegt.
- Eine Ablehnung zählt nur, wenn der Status außerhalb von 2xx liegt und nichts angelegt wurde. Meldet ein Aufruf eine Ablehnung und der Ordner steht trotzdem da, bricht die Auswertung mit einem Widerspruch ab, statt die Zeile als Ablehnung zu zählen (`refused()` im Messskript).

Das Abbruchkriterium zu MESS-01 ist eine Funktion (`abort_mess01()`): jeder Status außer 201 für den freien Namen unter Impersonation löst es aus. Dann wird Phase 31 nicht geplant, und der Befund geht mit Rohantwort an den Owner.

Kriterien des Plans 30-02 (ergänzt am 2026-11-11, vor dem ersten Messwert dieses Plans; der Commit dieser Tabelle liegt vor `raw/nc35-aendern.txt`):

| Messung | Was als Ergebnis zählt | Positivkontrolle (das Verfahren greift) | Gegenprobe (anderes Muster) |
|---------|------------------------|------------------------------------------|------------------------------|
| M3.1 PUT mit If-Match auf die gelesene ETag unter Impersonation (A13) | Status 2xx, die ETag danach ist eine andere, ein GET liefert den neuen Inhalt; alles andere löst das Abbruchkriterium aus | Logzeile PUT mit dem Messnutzer in `exapp_impersonation.log`; Kontrolle a | Lesen über einen anderen Weg: REPORT calendar-multiget mit App-Passwort liefert denselben Inhalt; derselbe PUT mit falschem APP_SECRET ändert nichts |
| M3.2 PUT mit veralteter ETag (A13) | Status 412 und das Objekt ist byte-gleich zum Stand davor; ein anderer Status oder ein geändertes Objekt löst das Abbruchkriterium aus | M3.1 direkt davor hat mit der aktuellen ETag geschrieben, der Schreibweg selbst geht also | sha256 der Spalte calendardata per PHP-Einmal-Snippet vor und nach dem Versuch gleich |
| M3.3 PUT ohne If-Match und mit `If-Match: *` | nur Beobachtung: Statuscode und ob überschrieben wurde; begründet, warum TMOD-01 beide Formen verbietet | M3.1 | Datenbank-Hash |
| M3.4 Erhalt fremder Eigenschaften (A14) | die Menge der entfalteten Inhaltszeilen nach dem ändernden PUT unterscheidet sich von der Menge davor genau um die eine geänderte Zeile; jede fehlende oder veränderte andere Zeile löst das Abbruchkriterium aus | ein Kontrollobjekt, dem vor dem PUT absichtlich eine X-Zeile entfernt wurde, meldet genau diese Zeile als fehlend | sha256 der Spalte calendardata gleich sha256 des gesendeten Bodys (der Server speichert wörtlich) oder, bei Abweichung, die Differenz der beiden Texte |
| M3.5 nur lesbare geteilte Liste | Status ungleich 2xx und das Objekt beim Eigentümer unverändert | derselbe PUT in eine Freigabe mit Schreibrecht wird angenommen | Lesen als Eigentümer mit App-Passwort; Datenbank-Hash |
| M3.6 wiederkehrende Aufgabe, Serverseite (A15) | Statuscode und gespeicherter Inhalt, wenn der Master mit RRULE per PUT auf erledigt gesetzt wird | M3.1 | Datenbank-Hash |
| M3.7 Unteraufgabe, Serverseite (A16) | ETag und Inhalt der Unteraufgabe vor und nach dem Abhaken der Elternaufgabe per PUT gleich | die Elternaufgabe hat sich geändert (neue ETag) | Datenbank-Hash der Unteraufgabe |
| M3.8 Felder der Tasks-App beim Abhaken und Wiederöffnen (A12) | Differenz der Zeilenmengen desselben Objekts zwischen Stand a und Stand b: hinzugekommene, entfernte und geänderte Eigenschaften samt Wertform (UTC mit Z, TZID, schwebend, Datum) | ein in der Sitzung nicht angefasstes Objekt zeigt eine leere Differenz | derselbe Stand, gelesen unter Impersonation und mit App-Passwort, ist gleich; ein vom Skript per PUT abgehaktes Vergleichsobjekt zeigt, welche Zeilen der Server von sich aus pflegt (keine oder benannte) |
| M3.9 Tasks-App bei wiederkehrender Aufgabe (A15) und bei Elternaufgabe mit Unteraufgabe (A16) | Differenz der betroffenen Objekte zwischen Stand a und b, dazu neu entstandene oder verschwundene Objekte | M3.8-Kontrollobjekt | Auflistung der Liste per REPORT mit App-Passwort (Objektzahl vorher und nachher) |
| M3.10 Inventar (A17) | je Fundstelle Datei, Zeile, Wortlaut; vollständig heißt: beide Suchmuster liefern keine Stelle, die im Inventar fehlt | Muster 1 findet die sechs in der Recherche genannten Stellen (EXPECTED_PUT_CALLS, FORBIDDEN, README-Rechtetabelle, threat-model, Store-Text, Server-Instruktion) | Muster 2 sucht anders: nicht nach Wörtern der Zusage, sondern nach den HTTP-Methoden und Konstanten in tests/ und nach den Sprachfassungen (de, fr) der Zusage |

Drei Regeln des Messskripts gehören zu diesen Kriterien:

- Das Abbruchkriterium zu MESS-05, Teil If-Match, ist eine Funktion (`abort_if_match()`): es ist nur dann nicht ausgelöst, wenn der PUT mit der aktuellen ETag mit 2xx antwortet, die ETag danach eine andere ist, der PUT mit der veralteten ETag genau 412 liefert und das Objekt danach unverändert ist. Jede Abweichung in einem der vier Werte löst es aus.
- Das Abbruchkriterium zu MESS-05, Teil Eigenschaften, entscheidet `preserved()`: verglichen werden die entfalteten Inhaltszeilen je Komponente vor und nach dem ändernden PUT; erlaubt ist allein die absichtlich geänderte Zeile (`SUMMARY`). Pflegt der Server von sich aus Zeilen (etwa `LAST-MODIFIED`, `DTSTAMP`, `SEQUENCE`), löst das das Kriterium aus und wird in der Zeile `PFLEGEFELDER` benannt; ob das für TMOD-02 hinnehmbar ist, entscheidet dann der Owner und nicht das Skript.
- "überschrieben" und "unverändert" werden nicht aus dem Statuscode geschlossen, sondern aus dem sha256 der Datenbankspalte `calendardata` vor und nach dem Aufruf.

Kriterien des Plans 30-03 (ergänzt am 2026-11-11, vor dem ersten Messwert dieses Plans; der Commit dieser Tabelle und der Entscheidungsregel liegt vor `raw/nc35-verschieben.txt` und vor jeder Datei `raw/loeschen-*.txt`):

| Messung | Was als Ergebnis zählt | Positivkontrolle (das Verfahren greift) | Gegenprobe (anderes Muster) |
|---------|------------------------|------------------------------------------|------------------------------|
| M4.1 MOVE eigene Liste nach eigene Liste unter Impersonation (A19) | Status 201 oder 204, Quelle danach 404, Ziel lesbar, UID gleich, Inhalt gleich; alles andere löst das Abbruchkriterium aus | Logzeile `"method":"MOVE"` mit dem Messnutzer in `exapp_impersonation.log`; Kontrolle a | beide Listen per REPORT mit App-Passwort auflisten (anderer Auth-Weg, andere Methode); derselbe MOVE mit falschem APP_SECRET verschiebt nichts |
| M4.2 MOVE auf belegtes Ziel (A19) | mit `Overwrite: F`: Status 412 und beide Objekte unverändert; ohne Kopfzeile: Statuscode und die Aussage ueberschrieben=ja oder nein | M4.1 | Datenbank-Hash des Zielobjekts vor und nach dem Versuch |
| M4.3 gleiche UID schon in der Zielliste | Statuscode; Ziel- und Quellobjekt danach | M4.1 | Auflistung beider Listen mit App-Passwort |
| M4.4 MOVE in geteilte Liste mit und ohne Schreibrecht, in Deck-Kalender, in Kalender ohne VTODO | je Statuscode; bei Ablehnung Quelle unverändert | M4.1; die Freigabe mit Schreibrecht nimmt an | Lesen als Eigentümer der Zielliste mit App-Passwort |
| M4.5 MOVE mit If-Match (aktuelle und veraltete ETag) | Statuscodes; bei veralteter ETag nichts verschoben | M4.1 | Auflistung mit App-Passwort |
| M4.6 Unteraufgabe beim Verschieben und Löschen der Elternaufgabe, Serverseite (A21) | Ort, ETag und Inhalt der Unteraufgabe danach | die Elternaufgabe ist verschoben oder gelöscht | Datenbank-Hash der Unteraufgabe |
| M4.7 Unteraufgabe beim Verschieben und Löschen in der Tasks-App (A21) | aus raw/ui-a und raw/ui-b: wo liegt die Unteraufgabe nach dem Umzug der Elternaufgabe, und existiert sie nach dem Löschen der Elternaufgabe noch | "s30 umzug-einzeln" liegt in spike30-liste-2, der Umzug hat also stattgefunden; "s30 unberuehrt" unverändert | Objektzahl je Liste aus den Zeilen UI-OBJEKT (anderer Stand, andere Zählung) |
| M4.8 DELETE unter Impersonation, Papierkorb im Auslieferungszustand | Status 204, Objekt im Papierkorb, Wiederherstellung bringt es zurück | Logzeile DELETE mit dem Messnutzer | Zeile in der Datenbank mit gesetztem deleted_at per PHP-Einmal-Snippet |
| M4.9 Löschen je Version, Papierkorb an (A18, W1) | DELETE 204; das Objekt steht in der Auflistung des Papierkorbs; nach der Wiederherstellung ist es am alten Ort mit gleicher UID und gleichem sha256 des Inhalts | ein nicht gelöschtes Nachbarobjekt steht nicht im Papierkorb | Datenbankzeile mit deleted_at gesetzt, danach wieder leer (nicht über DAV gelesen) |
| M4.10 geteilte Liste (W2) | DELETE durch den Empfänger mit Schreibrecht: Statuscode, in wessen Papierkorb das Objekt steht, wer es wiederherstellen kann; Empfänger ohne Schreibrecht: Ablehnung und Objekt unverändert | M4.9 | Datenbankzeile; Lesen als Eigentümer |
| M4.11 Papierkorb aus (W3) | DELETE 204; steht das Objekt noch irgendwo, und geht die Wiederherstellung | derselbe Ablauf mit Papierkorb an hat in M4.9 wiederhergestellt | Datenbankzeile vorhanden oder nicht; der Schalter ist per `occ config:app:get` belegt und nach einem Neustart des Containers erneut gemessen |
| M4.12 Vorab-Test (W4) | je Kandidat der Wert bei Papierkorb an und bei Papierkorb aus; ein Kandidat zählt nur, wenn er beide Zustände richtig anzeigt | der Zustand ist per M4.9 und M4.11 am Verhalten belegt, nicht nur am Schalter | zweiter Kandidat anderer Art (Eigenschaft gegen Existenz der Sammlung) |
| M4.13 Aufbewahrungsfrist | der konfigurierte Wert und seine Einheit; mit auf 1 Sekunde gesetzter Frist entfernt der Aufräumlauf das gelöschte Objekt endgültig | mit der Standardfrist lässt derselbe Aufräumlauf das Objekt stehen | Datenbankzeile vor und nach dem Aufräumlauf |

Drei Regeln des Messskripts gehören zu diesen Kriterien:

- Das Abbruchkriterium zu MESS-06, Teil MOVE, ist eine Funktion (`abort_move()`): es ist nur dann nicht ausgelöst, wenn der MOVE von einer eigenen Liste in eine eigene Liste unter Impersonation mit 201 oder 204 antwortet, die Quelle danach 404 liefert, das Ziel lesbar ist und die UID gleich geblieben ist. Jede Abweichung in einem der vier Werte löst es aus. Dann wird TMOD-08 nicht geplant, und der Befund geht mit Rohantwort an den Owner.
- Ein Statuscode 5xx zählt in keiner Zeile als Erfolg und in keiner Zeile als Ablehnung im Sinn der Messung; er steht als eigener Befund da. Die Messschritte laufen nacheinander, nie gleichzeitig (Lehre aus Plan 30-02: zwei gleichzeitige Schreibzugriffe auf SQLite ergaben 500 `database is locked`).
- "überschrieben", "unverändert", "im Papierkorb" und "wiederhergestellt" werden nicht aus dem Statuscode geschlossen, sondern aus dem sha256 der Datenbankspalte `calendardata` und der Spalte `deleted_at` vor und nach dem Aufruf.

### Entscheidungsregel für das Löschen (E13), vorab festgelegt

Wörtlich aus dem Plan 30-03, als Funktion `delete_verdict()` im Messskript abgebildet und unit-getestet, bevor ein Messwert des Löschens existiert:

Lesart: MESS-06 und TMOD-07 verlangen, dass das Löschwerkzeug vor dem Löschen prüft, ob der Papierkorb für das Konto wirkt, und sonst ablehnt. Die Regel folgt dieser Lesart. Die strengere wörtliche Lesart von E13 ("wiederherstellbar bleibt, auch mit abgeschaltetem Papierkorb") ergäbe bei endgültigem Löschen im Aus-Zustand immer "nicht wiederherstellbar"; der Bericht nennt deshalb den Rohbefund des Aus-Zustands eigens, damit der Owner ihn am Checkpoint sieht.

Owner-Entscheid zur Lesart (11.11.2026, Claude Code Terminal, Antwort des Owners auf die vorgelegte Lesart: "Ok"): Es gilt die Fassung nach TMOD-07. Löschen kommt in 0.8.0, wenn ein verlässlicher Vorab-Test zeigt, ob der Papierkorb des Kalenders für dieses Konto wirkt; das Werkzeug lehnt ab, wenn nicht. Bei abgeschaltetem Papierkorb muss also nicht "wiederherstellbar" herauskommen, sondern der Vorab-Test muss den Aus-Zustand sicher erkennen. Die Regel unten bildet das mit "W3 oder W4" ab und bleibt im Wortlaut unverändert; eingetragen am 11.11.2026 vor dem ersten Messwert dieses Plans. Der Rohbefund des Aus-Zustands steht weiter eigens im Bericht (Unterabschnitt 4.4).

Je Version v aus 32, 33, 34, 35 entstehen fünf Werte: W1 (eigene Liste, Papierkorb an: gelöschte Aufgabe steht im Papierkorb, die Wiederherstellung bringt sie mit gleicher UID und gleichem Inhalt zurück), W2 (geteilte Liste mit Schreibrecht, Papierkorb an: dasselbe, wiederherstellbar durch das löschende Konto oder durch den Eigentümer; wer es kann, wird festgehalten), W3 (Papierkorb aus: die Aufgabe ist danach noch wiederherstellbar, ja oder nein), W4 (mindestens ein Vorab-Test, den ein Konto per DAV oder OCS selbst stellen kann, unterscheidet "Papierkorb an" von "Papierkorb aus" in beiden Richtungen richtig), G (jede der vier Messungen ist gemessen und ihre Positivkontrolle hat gegriffen).

- "wiederherstellbar": für alle vier Versionen gilt G und W1 und W2 und (W3 oder W4).
- "nicht wiederherstellbar": für mindestens eine Version gilt G, und W1 ist nein oder W2 ist nein oder (W3 ist nein und W4 ist nein).
- "nicht eindeutig": alle übrigen Fälle, also eine fehlende oder ungemessene Messung, eine gescheiterte Positivkontrolle oder ein Widerspruch zwischen zwei Läufen derselben Version.

Konsequenz, fest und ohne Rückfrage: nur "wiederherstellbar" lässt TMOD-07 in Phase 33 planen, mit der Auflage aus den Messwerten (welcher Vorab-Test, wer wiederherstellen kann, Frist). Bei "nicht wiederherstellbar" und bei "nicht eindeutig" gibt es in 0.8.0 kein Löschen; TMOD-07 wandert nach Out of Scope, und der Store-Text nennt die Grenze (EXAPP-13).

Wie das Messskript die fünf Werte bildet (festgelegt am 2026-11-11 mit dem Block delete-matrix, vor der ersten Datei `raw/loeschen-*.txt`):

- W1 ist nur ja, wenn `DELETE` genau 204 liefert, das Objekt in der Auflistung des Papierkorbs steht, die Datenbankzeile `deleted_at` trägt, die Wiederherstellung mit 2xx antwortet und das Objekt danach am alten Ort mit gleicher UID und gleichem sha256 steht. W2 verlangt dasselbe für die geteilte Liste mit Schreibrecht, wiederhergestellt durch das löschende Konto oder durch den Eigentümer. Ein Statuscode 5xx zählt nirgends als Erfolg.
- W3 ist nur ja, wenn im Aus-Zustand sowohl die Aufgabe der eigenen als auch die der geteilten Liste nach dem Löschen wiederherstellbar ist.
- W4: die Kandidaten des Vorab-Tests und ihre Lesart stehen vor der Messung fest (`pretest_shows()`): der Status eines `PROPFIND` auf die Papierkorb-Sammlung (207 heißt an, 404 heißt aus), die Eigenschaft der Aufbewahrungsdauer an der Papierkorb-Sammlung und am Kalender-Home (eine Zahl größer 0 heißt an, 0 heißt aus), das Kind `trashbin` im Kalender-Home (vorhanden heißt an), das Merkmal `nc-calendar-trashbin` im Antwortkopf `DAV` (vorhanden heißt an) und der Abschnitt `dav` der Capabilities (ein Schlüssel mit trash oder retention im Namen; fehlt er, ist der Kandidat unklar). Ein Kandidat zählt nur, wenn er bei eingeschaltetem Papierkorb "an" und bei abgeschaltetem "aus" zeigt; W4 ist ja, wenn mindestens einer zählt.
- G ist nur ja, wenn kein Abschnitt des Laufs als ungemessen endete und jede Positivkontrolle gegriffen hat: das Nachbarobjekt steht nicht im Papierkorb und ist lesbar (an-eigen); M4.9 hat wiederhergestellt (an-geteilt, aus-eigen) und die geteilte Liste hat bei eingeschaltetem Papierkorb wiederhergestellt (aus-geteilt); die Elternaufgabe ist gelöscht (Unteraufgabe); die beiden Zustände sind am Verhalten belegt, nämlich an durch die Wiederherstellung und aus durch die fehlende Datenbankzeile (Vorab-Test); die Standardfrist lässt das Objekt beim Aufräumlauf stehen (Aufbewahrungsfrist).
- Trägt eine Rohdatei zwei Läufe derselben Version mit verschiedenen Werten, gilt die Version als nicht entschieden, und die Regel führt zu "nicht eindeutig". Einzige Ausnahme: ein Lauf mit der Zeile `WIEDERHOLUNG Grund:` ersetzt die Läufe vor ihm in derselben Datei. Diese Zeile steht nur bei einem Werkzeugfehler des Messskripts; ein Messwert wird nie wiederholt, bis er passt.

Kriterien des Plans 30-04:

| Messung | Was als Ergebnis zählt | Positivkontrolle (das Verfahren greift) | Gegenprobe (anderes Muster) |
|---------|------------------------|------------------------------------------|------------------------------|
| M5.1 frisches Konto | nach einer echten ersten Anmeldung: Zahl der Sammlungen im Kalender-Home, deren Komponenten-Set VTODO enthält; 0 belegt die Annahme | dieselbe Auswertung findet beim vorbereiteten Konto mindestens eine Aufgabenliste; der Standardkalender des frischen Kontos existiert (die Anmeldung hat das Ereignis also ausgelöst) | `occ dav:list-calendars` und die Spalte components per PHP-Einmal-Snippet (nicht über DAV) |
| M5.2 Sammlungsarten in der Discovery (A4, A5, A11) | je Art die Merkmale aus der Rohantwort: URI-Muster, resourcetype, Komponenten-Set, read-only-Eigenschaft, Privilegien | jede vorbereitete Art taucht in der Antwort auf; fehlt eine, ist ihr Aufbau gescheitert und die Art ungemessen | die Zahl der Kalender laut `occ dav:list-calendars`; für nur lesbar zusätzlich ein Schreibversuch (Status ungleich 2xx) |
| M5.3 Abfrageverhalten je Version (A1) | je Abfrage die Menge der gelieferten Aufgabennamen; A1 ist belegt, wenn alle sechs Mengen auf 32, 33, 34 und 35 gleich sind | die Abfrage ohne Filter liefert alle vorbereiteten Aufgaben | dieselbe Menge clientseitig aus der ungefilterten Antwort berechnet (Filter im Skript statt im Server) |
| M5.4 Link des Suchproviders tasks | der Link enthält Kalender-URI und Objektname der vom Skript angelegten Aufgabe; die Form steht wörtlich im Protokoll | der Provider liefert mit eingeschalteter Tasks-App mindestens einen Treffer | mit ausgeschalteter Tasks-App liefert derselbe Aufruf keinen Treffer; GET auf die aus dem Link gebaute DAV-URL liefert das Objekt |
| M5.5 create-only PUT eines VTODO unter Impersonation | Status 201 für den ersten PUT mit `If-None-Match: *`, Status 412 für den zweiten auf denselben Namen, Objekt unverändert | Logzeile PUT mit dem Messnutzer in `exapp_impersonation.log`; Kontrolle a | Lesen mit App-Passwort über REPORT calendar-multiget; derselbe PUT mit falschem APP_SECRET legt nichts an |
| M5.6 Fixtures der Tasks-App (A2, A3) | je Art eine unveränderte Kopie eines Objekts aus raw/ui-a oder raw/ui-b; A2: RELATED-TO der Unteraufgabe gleich UID der Elternaufgabe und beide in derselben Liste; A3: Wertform der Zeitangaben | "s30 unberuehrt" ist in beiden Ständen gleich | sha256 der Fixture gleich sha256 der Rohdatei; die Wertform zusätzlich mit icalendar gelesen (Bibliothek statt Zeilenvergleich) |
| M6.1 Kosten Modus offen und Modus alle (A6) | je Modus und Datenbank: Trefferzahl, Antwortgröße in Bytes, min, Median, zweitgrößter Wert, Maximum aus 15 Läufen nach 3 Aufwärmläufen | Trefferzahl offen gleich 100 und alle gleich 2000 | Zeilenzahl der Liste in der Datenbank per PHP-Einmal-Snippet gleich 2000; clientseitige Zählung der Objekte ohne COMPLETED in der Antwort "alle" gleich 100 |
| M6.2 calendar-search | Statuscode, Trefferzahl, Antwortgröße und Wanduhr eines Aufrufs mit Suchbegriff, Limit und Offset | der Suchbegriff steht in genau 10 vorbereiteten Aufgaben | dieselben 10 Namen clientseitig aus der Antwort "alle" gefiltert |
| M6.3 Bezugsgrößen | PROPFIND der Discovery und GET /status.php als Grundrauschen, je Median | Status 207 und 200 | keine, reine Bezugswerte |

### Ableitungsregel für Deckel und Zeitbudget (Plan 30-04), vorab festgelegt

Wörtlich aus dem Plan 30-04, als Funktion `proposal()` im Messskript abgebildet und unit-getestet, bevor ein Messwert der Kosten existiert:

Der Bericht legt keine Produktwerte fest, er liefert Phase 32 die Zahlen und wendet diese Regel sichtbar an: Bezugswert ist der größere der beiden Mediane "Modus alle bei 2000 Aufgaben" aus SQLite und PostgreSQL. Liegt er bei höchstens 1,0 s, lautet der Vorschlag "eine Abfrage je Liste ohne zusätzlichen Deckel unterhalb von 2000 Objekten, Zeitbudget je Liste das Doppelte des größten gemessenen Maximalwerts, aufgerundet auf volle Sekunden". Liegt er darüber, lautet der Vorschlag "Standardmodus offen als einziger Weg ohne Hinweis; Modus alle mit ehrlicher Notiz und einem Zeitbudget je Liste in Höhe des Doppelten des gemessenen Maximalwerts; der Deckel der zurückgegebenen Aufgaben folgt der Antwortgröße, nicht der Laufzeit". In beiden Fällen nennt der Bericht die Antwortgröße in Bytes je Modus als zweite Größe, weil der Server bei jedem Filter alle Aufgaben der Liste parst und die Übertragung der einzige Teil ist, den der Vorfilter verkleinert.

Wie das Messskript die Werte dieses Plans bildet (festgelegt am 2026-11-12 mit den Blöcken discovery-matrix, cost, vtodo-create und fixtures, vor der ersten Rohdatei dieses Plans):

- Die Art einer Sammlung ist eine Funktion (`classify_collection()`), unit-getestet, in dieser Reihenfolge: URI mit Präfix `app-generated--` ist "deck"; URI `trashbin` ist "papierkorb"; `inbox` und `outbox` sind "scheduling"; resourcetype `subscribed` ist "abo"; URI mit `_shared_by_` ist "geteilt-nur-lesen", wenn die Eigenschaft `{http://owncloud.org/ns}read-only` in einem Propstat mit Status 2xx steht und weder leer noch 0 noch false ist, sonst "geteilt-schreibbar"; danach entscheidet das Komponenten-Set ("gemischt", "aufgabenliste", "terminkalender", "ohne-komponenten"). Eine Eigenschaft, die der Server unter 404 nennt, gilt als fehlend (`read_only=fehlt`), ein leerer Wert steht als `leer` da.
- Ergänzt am 2026-11-12 nach dem ersten Lauf auf 32.0.15 (Rohdatei `raw/discovery-32.txt`, der Lauf vor der zweiten Zeile `WIEDERHOLUNG Grund`), offen als Änderung der Auswertung benannt: ein gelöschter Kalender steht mit dem resourcetype `deleted-calendar` und seinem Komponenten-Set weiter im Kalender-Home. Die vorab festgelegte Reihenfolge kannte diesen Typ nicht und hat ihn als "aufgabenliste" gezählt (`POSITIVKONTROLLE aufgabenlisten_alice=5`). Die Funktion führt ihn seither als eigene Art "geloeschter-kalender", direkt nach dem Papierkorb; der Befund selbst steht in Abschnitt 5.2. An den Messwerten ändert das nichts, nur an ihrer Benennung.
- "Aufgabenliste" im Sinn von M5.1 ist, was `task_lists()` liefert: nur die Arten aufgabenliste, gemischt, geteilt-schreibbar und geteilt-nur-lesen, und nur mit `VTODO` im Komponenten-Set.
- Die Zeile `FRISCHES KONTO vor_anmeldung` stammt aus einem `PROPFIND` als admin und aus der Tabelle `calendars`: eine Anfrage im Namen des frischen Kontos wäre bereits dessen erste Anmeldung.
- Die Gegenprobe von M5.3 (`client_filter()`) ist zugleich die Menge, die TASK-02 verlangt: ein Fälligkeitsfenster nimmt nur Aufgaben, deren `DUE` oder `DTSTART` im Fenster liegt, also nie eine undatierte, und eine wiederkehrende Aufgabe zählt mit den Daten, die sie trägt, ohne Expansion. `gleich=nein` ist deshalb ein Befund über den Serverfilter und kein Messfehler. A1 hängt nicht an dieser Gegenprobe, sondern am Vergleich der Treffermengen des Servers über die vier Versionen (`same_sets()`): eine Version ohne Antwort auf eine Abfrage gilt als abweichend, nie als gleich.
- Die acht Aufgaben von M5.3 tragen alle `CREATED:20261111T100000Z`; das Fenster reicht von `20261119T000000Z` bis `20261122T000000Z`, der Suchbegriff ist `q-offen`.
- Der Link des Suchproviders wird nur in der Form `.../apps/tasks/calendars/<uri>/tasks/<name>` (mit oder ohne `#/`) aufgelöst (`provider_link_parts()`); jede andere Form ergibt "ungemessen" und wird nicht geraten.
- Kosten: je Reihe drei verworfene Aufwärmläufe und 15 Messläufe mit einem Client, davor Warten auf die ruhende Instanz (CPU laut `docker stats` unter 10 %). Der Wert `p95_zweitgroesster` ist der zweitgrößte der 15 Werte. Ein Lauf über dem Zeitlimit des Clients von 60 s bricht die Reihe ab und ist ein Messwert; danach folgt ein Einzellauf mit 300 s. Trefferzahl ist die Zahl der `response`-Elemente der Antwort, Bytes die Länge des Antwortkörpers. Der Aufbau der 2000 Aufgaben läuft auf SQLite seriell (zwei gleichzeitige Schreibzugriffe scheitern dort mit `database is locked`, gemessen in Plan 30-02), auf PostgreSQL mit vier gleichzeitigen `PUT`; ein `PUT` mit 5xx wird im Aufbau wiederholt und gezählt (`wiederholte_put`), weil der Aufbau keine Messung ist.
- Die Zeile `VORSCHLAG` einer Kostendatei wendet die Ableitungsregel (`proposal()`, unit-getestet) nur auf die Zahlen dieser einen Datenbank an. Der Bezugswert der Regel, der größere der beiden Mediane, entsteht erst im Bericht aus beiden Dateien; "größter gemessener Maximalwert" ist das Maximum über die Reihen offen und alle beider Datenbanken.
- Fixtures: die Auswahl läuft allein über die `SUMMARY` der Browser-Sitzung (`pick_fixtures()`); ganztägig, mit Uhrzeit, Unteraufgabe samt Elternaufgabe, wiederkehrend und Tags aus Stand a, abgehakt und wieder geöffnet aus Stand b. Eine Datei wird nur angelegt, wenn das Objekt das Merkmal seiner Art trägt und seine `PRODID` die Tasks-App nennt; fehlt die Art, steht sie mit Grund da und wird nicht nachgebaut. Eine Discovery-Antwort wird nur dann zur Fixture, wenn ihr sha256 der des Laufs ist und `probe_values_only()` nichts findet, das kein Probewert ist.

## 1. MKCOL unter AppAPI-Impersonation (MESS-01)

Gemessen am 2026-11-11 auf Nextcloud 35.0.0 mit SQLite, Rohprotokoll `raw/nc35-mkcol.txt` im Phasenordner (wörtliche Zeilen in Abschnitt 12.1). Jeder Aufruf lief als Messkonto `spike30a`, einmal unter AppAPI-Impersonation (`auth=appapi`, das einzige Geheimnis ist das Secret der App) und einmal mit einem App-Passwort desselben Kontos (`auth=basic`). `MKCOL` ging immer ohne Body und ohne `Content-Type` hinaus.

### 1.1 Der erste Messpunkt und das Abbruchkriterium

Der erste `MKCOL` der Phase ist der gemessene: der Basisordner `/spike30` entstand vorher über einen `PUT` mit dem Kopf `X-NC-WebDAV-Auto-Mkcol`, nicht über einen `MKCOL`.

| Schritt | Rohwert | Bedeutung |
|---------|---------|-----------|
| Positivkontrolle vorher | `KONTROLLE vorher PROPFIND Depth 0 /spike30/frei-115543 auth=appapi nutzer=spike30a status=404 erwartet=404` | den Pfad gab es nicht |
| Messung | `MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201` | 201 für einen freien Namen unter Impersonation |
| Abbruchkriterium | `ABBRUCHKRITERIUM MESS-01 ausgeloest=nein status=201` | nicht ausgelöst |
| Gegenprobe Dateisystem | `DATEISYSTEM frei vorhanden=ja pfad=/var/www/html/data/spike30a/files/spike30/frei-115543` | der Ordner liegt im Datenverzeichnis des Containers, gelesen mit `test -d`, nicht über DAV |
| Positivkontrolle Serverprotokoll | `KONTROLLE exapp_impersonation.log, MKCOL-Zeilen von spike30a seit 2026-11-11T11:55:43Z: 1` | Nextcloud selbst nennt in `exapp_impersonation.log` das Konto `spike30a` für genau diesen `MKCOL` (Zeile in 12.1) |
| Kontrolle a | `a: GET /ocs/v2.php/cloud/user (AppAPI as spike30a)`, `HTTP 200`, `id=spike30a erwartet=spike30a gleich=ja` | `cloud/user` nennt unter Impersonation das Messkonto |
| Kontrolle b | `b: GET /ocs/v2.php/cloud/user (AppAPI as spike30a, wrong APP_SECRET)`, `HTTP 401`, `abgelehnt=ja` | ein falsches Secret wird abgelehnt |
| Gegenprobe falsches Secret | `GEGENPROBE falsches-secret MKCOL /spike30/frei-115543-falsches-secret nutzer=spike30a status=401 angelegt=nein` | derselbe `MKCOL` mit einem Secret aus 64 Nullen legt nichts an |
| Gegenprobe fremdes Home | `GEGENPROBE fremdes-home MKCOL /remote.php/dav/files/spike30b/spike30-fremd nutzer=spike30a status=403 angelegt=nein` | `spike30a` kann unter Impersonation nicht in das Home von `spike30b` schreiben |

**Abbruchkriterium MESS-01: nicht ausgelöst.** A7 ist belegt: `MKCOL` auf `files/` funktioniert unter AppAPI-Impersonation. Phase 31 darf geplant werden.

### 1.2 Produktionsweg

Derselbe `MKCOL` aus dem laufenden ExApp-Container heraus, gegen `http://caddy`, mit dem Secret aus der Umgebung des Containers: `PRODUKTIONSWEG MKCOL status=201 angelegt=ja nutzer=spike30a pfad=/spike30/frei-115543-produktionsweg (aus nc_app_mcp_connector gegen http://caddy)`. Das Programm dafür steht als Konstante im Messskript, liest das Secret aus der Umgebung des Containers und druckt nur den Status. Gemessen ist damit der Netzweg und die Anmeldung der ExApp, nicht ein Werkzeug der App: das registrierte Image ist 0.3.2 und kennt kein Werkzeug zum Ordner-Anlegen.

### 1.3 Statusmatrix

"angelegt" heißt in jeder Zeile: der Ordner stand nach dem Aufruf im Dateisystem und vorher nicht.

| Befund | Aufruf | Nutzer | Rohwert | Erwartung | Deutung |
|--------|--------|--------|---------|-----------|---------|
| freier Name | MKCOL `/spike30/frei-<stempel>` | spike30a | `MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201`<br>`MKCOL frei auth=basic status=201 angelegt=ja erwartet=201` | 201 | angelegt; die Antwort hat keinen Body und trägt die Kennung des neuen Ordners im Antwortkopf `oc-fileid` |
| Ordner gibt es schon | MKCOL auf den eben angelegten Ordner | spike30a | `MKCOL ordner-vorhanden auth=appapi status=405 angelegt=nein erwartet=405`<br>`MKCOL ordner-vorhanden auth=basic status=405 angelegt=nein erwartet=405` | 405 | wie erwartet; Meldung: The resource you tried to create already exists |
| Datei am Pfad | PUT einer Datei, dann MKCOL auf denselben Pfad | spike30a | `MKCOL datei-vorhanden auth=appapi status=405 angelegt=nein erwartet=405`<br>`MKCOL datei-vorhanden auth=basic status=405 angelegt=nein erwartet=405` | 405 | wie erwartet und Wort für Wort dieselbe Antwort wie bei einem vorhandenen Ordner: 405 allein sagt nicht, ob dort ein Ordner oder eine Datei liegt |
| Elternordner fehlt | MKCOL `/spike30/fehlt-<auth>/kind` | spike30a | `MKCOL eltern-fehlt auth=appapi status=409 angelegt=nein erwartet=409`<br>`MKCOL eltern-fehlt auth=basic status=409 angelegt=nein erwartet=409` | 409 | wie erwartet; Meldung: Parent node does not exist |
| Elternknoten ist eine Datei | MKCOL `/spike30/datei-<auth>.txt/kind` | spike30a | `MKCOL eltern-ist-datei auth=appapi status=409 angelegt=nein erwartet=409`<br>`MKCOL eltern-ist-datei auth=basic status=409 angelegt=nein erwartet=409` | 409 | wie erwartet; derselbe Status wie beim fehlenden Elternordner, nur die Meldung unterscheidet: Parent node is not a collection |
| unzulässiger Name `.htaccess` | MKCOL `<frei>/.htaccess` | spike30a | `MKCOL name-htaccess auth=appapi status=400 angelegt=nein erwartet=400`<br>`MKCOL name-htaccess auth=basic status=400 angelegt=nein erwartet=400` | 400 | wie erwartet; Ausnahme `InvalidPath`, Meldung: Filename is a reserved word |
| Backslash im Namen | MKCOL `<frei>/bs%5Cx`, das Segment roh an die URL gehängt, weil `dav.safe_path` einen Backslash vor jeder Anfrage ablehnt | spike30a | `MKCOL name-backslash auth=appapi status=400 angelegt=nein erwartet=400`<br>`MKCOL name-backslash auth=basic status=400 angelegt=nein erwartet=400` | 400 | wie erwartet; Ausnahme `InvalidPath` |
| Name mit 300 Zeichen | MKCOL `<frei>/xxx...` (300 mal x) | spike30a | `MKCOL name-ueberlang auth=appapi status=400 angelegt=nein erwartet=400`<br>`MKCOL name-ueberlang auth=basic status=400 angelegt=nein erwartet=400` | 400 | wie erwartet; Ausnahme `InvalidPath`, Meldung: Filename is too long |
| geteilter Ordner ohne Anlegerecht (M1.3) | MKCOL `/spike30-share-ro/neu-<auth>`; Freigabe von spike30b mit `permissions=1` | spike30a | `MKCOL share-ro auth=appapi status=403 angelegt=nein erwartet=403`<br>`MKCOL share-ro auth=basic status=403 angelegt=nein erwartet=403` | 403 | abgelehnt, beim Eigentümer liegt nichts; die Meldung `s:message` ist leer |
| geteilter Ordner mit Anlegerecht (Positivkontrolle zu M1.3) | MKCOL `/spike30-share-rw/neu-<auth>`; Freigabe mit `permissions=15` | spike30a | `MKCOL share-rw auth=appapi status=201 angelegt=ja erwartet=201`<br>`MKCOL share-rw auth=basic status=201 angelegt=ja erwartet=201` | 201 | angelegt, im Dateisystem beim Eigentümer spike30b gefunden |
| Sandbox-Wurzel vorhanden, Unterordner (M1.4) | MKCOL auf die URL, die `dav.files_url` bei `NC_MCP_FILES_ROOT=/spike30/root` für `/unter-<auth>` baut | spike30a | `MKCOL root-vorhanden auth=appapi status=201 angelegt=ja erwartet=201`<br>`MKCOL root-vorhanden auth=basic status=201 angelegt=ja erwartet=201` | 201 | angelegt unter der Wurzel |
| Sandbox-Wurzel fehlt, Unterordner (M1.4) | dieselbe Bauweise bei `NC_MCP_FILES_ROOT=/spike30/root-fehlt` | spike30a | `MKCOL root-fehlt auth=appapi status=409 angelegt=nein erwartet=409`<br>`MKCOL root-fehlt auth=basic status=409 angelegt=nein erwartet=409` | 409 | wie ein fehlender Elternordner: eine fehlende Wurzel ist von einem fehlenden Elternordner am Status nicht zu unterscheiden |
| Sandbox-Wurzel selbst als Ziel (M1.4) | `dav.files_url` für `/` bei gesetzter Wurzel | spike30a | `MKCOL root-selbst auth=appapi status=405 angelegt=nein erwartet=405`<br>`MKCOL root-selbst auth=basic status=405 angelegt=nein erwartet=405` | 405 | wie ein vorhandener Ordner |
| erschöpftes Kontingent (M1.5, A9) | Kontingent von spike30a auf `1 KB`, dann MKCOL `/spike30/quota-<auth>` | spike30a | `MKCOL quota auth=appapi status=507 angelegt=nein erwartet=201`<br>`MKCOL quota auth=basic status=507 angelegt=nein erwartet=201` | 201 | **Abweichung von der Erwartung: 507.** Nichts angelegt. A9 ist widerlegt |

Vergleich der beiden Anmeldewege: `MKCOL GLEICH appapi_basic=ja abweichend=keine`. Unter Impersonation antwortet jede der vierzehn Zeilen mit demselben Status wie mit App-Passwort.

Gegenproben zu den Freigaben (M1.3), `oc:permissions` aus Sicht von `spike30a`: `KONTROLLE oc:permissions /spike30-share-ro (Ordner /spike30-share-ro von spike30b) aus Sicht von spike30a auth=appapi status=207 permissions=SGDN` (ohne `C` und `K`) und `KONTROLLE oc:permissions /spike30-share-rw (Ordner /spike30-share-rw von spike30b) aus Sicht von spike30a auth=appapi status=207 permissions=SGDNVCK` (mit `C` und `K`). Der Status 403 fällt also mit dem fehlenden Anlegerecht zusammen, das ein `PROPFIND` vorab zeigt.

Positivkontrolle zum Kontingent (M1.5): `KONTROLLE kontingent PUT 2048 Bytes /spike30/quota-probe-appapi.bin auth=appapi nutzer=spike30a status=507 wirkt=ja` und `KONTROLLE kontingent PUT 2048 Bytes /spike30/quota-probe-basic.bin auth=basic nutzer=spike30a status=507 wirkt=ja`. Das Kontingent wirkte also, bevor `MKCOL` gemessen wurde. Die Antwort auf `MKCOL` nennt den Grund selbst: `Sabre\DAV\Exception\InsufficientStorage Insufficient space in /spike30. Cannot create directory`. Gemessen ist der Zustand, in dem das Konto schon mehr belegt, als das Kontingent erlaubt (frisches Konto mit Beispieldateien, Kontingent `1 KB`); ein Kontingent, das knapp, aber nicht erschöpft ist, ist nicht gemessen.

### 1.4 Was das für FOLD-01 heißt

- **201** ist der einzige Erfolg. Die Antwort hat keinen Body; die Kennung des neuen Ordners steht im Antwortkopf `oc-fileid`.
- **405** heißt "am Pfad liegt schon etwas", für einen Ordner und für eine Datei mit derselben Ausnahme und derselben Meldung. Wer "Ordner gibt es schon" (Erfolg mit `created: false`) von "dort liegt eine Datei" (Konflikt) trennen will, braucht nach dem 405 einen zweiten Aufruf, der die Art des Knotens liest.
- **409** kommt in zwei Fällen: Elternordner fehlt, und Elternknoten ist eine Datei. Der Status ist gleich, nur `s:message` unterscheidet. Eine fehlende Sandbox-Wurzel antwortet ebenfalls 409.
- **400** kommt vor, für alle drei gemessenen unzulässigen Namen, immer mit der Ausnahme `OCA\DAV\Connector\Sabre\Exception\InvalidPath` und einer lesbaren Meldung. Der Zweig braucht eine eigene Meldung statt "unexpected status".
- **403** heißt keine Rechte. Bei der Freigabe ohne Anlegerecht ist `s:message` leer; die Meldung des Werkzeugs kann sich also nicht auf den Text des Servers stützen.
- **507** kommt vor. A9 ("`MKCOL` löst nie 507 aus") ist widerlegt: bei erschöpftem Kontingent lehnt Nextcloud 35 das Anlegen eines leeren Ordners mit 507 ab. Der Zweig bleibt nicht nur vorsorglich, er wird gebraucht.
- **401** kommt bei falschem Secret; das ist kein Zweig des Werkzeugs, sondern die vorhandene Behandlung der Anmeldung.
- Unter Impersonation gibt es keinen eigenen Zweig: alle vierzehn Zeilen sind statusgleich mit dem App-Passwort.

## 2. Gruppenordner mit ACL und externer Speicher (MESS-02)

Gemessen am 2026-11-11 auf derselben Instanz (Nextcloud 35.0.0, SQLite) mit `groupfolders` 23.0.1, Rohprotokoll `raw/nc35-gruppenordner.txt` im Phasenordner (wörtliche Zeilen in Abschnitt 12.2). Jede Zeile lief unter AppAPI-Impersonation und mit App-Passwort.

### 2.1 Aufbau

Die Kommandoformen stammen aus den Hilfetexten der laufenden Instanz (`occ groupfolders:create --help` und die übrigen, roh im Protokoll), nicht aus der Planung.

- Gruppe `spike30grp` mit `spike30a` und `spike30b`, Gruppe `spike30lesen` mit `spike30a`.
- Gruppenordner `spike30gf` (Id 1) für `spike30grp` mit den Rechten read, write, share, delete, erweiterte Rechte (ACL) eingeschaltet. Gruppenordner `spike30gf-lesen` (Id 2) für `spike30lesen` ohne Angabe von Rechten, also nur lesbar.
- Positivkontrolle, dass beide Ordner im Home des Messkontos erscheinen: `KONTROLLE PROPFIND Depth 1 home auth=appapi nutzer=spike30a status=207 spike30gf_sichtbar=ja spike30gf-lesen_sichtbar=ja`.
- Die Unterordner `acl-rw` und `acl-ro` hat `spike30a` selbst unter Impersonation mit `MKCOL` angelegt (beide 201, Zeilen GF-AUFBAU in 12.2). Wo sie im Datenverzeichnis liegen, ist danach von der Platte gelesen: `DATEISYSTEM gruppenordner spike30gf id=1 pfad=/var/www/html/data/__groupfolders/1/files`.
- ACL-Regel auf `acl-ro` für das Konto `spike30a`: `occ groupfolders:permissions 1 --user spike30a acl-ro -- +read -write -create -delete`. Die Instanz bestätigt die wirksamen Rechte mit `occ groupfolders:permissions 1 --user spike30a --test acl-ro -> +read, -write, -create, -delete, +share`.

### 2.2 Messung

| Befund | Aufruf | Nutzer | Rohwert | Erwartung | Deutung |
|--------|--------|--------|---------|-----------|---------|
| M2.1 Gruppenordner mit Schreibrecht | MKCOL `/spike30gf/acl-rw/neu-<auth>` | spike30a | `GF acl-rw auth=appapi nutzer=spike30a status=201 angelegt=ja`<br>`GF acl-rw auth=basic nutzer=spike30a status=201 angelegt=ja` | 201 | angelegt, im Dateisystem unter `__groupfolders/1/files/` gefunden |
| M2.2 Negativtest: ACL-Regel entzieht Schreiben, Anlegen und Löschen | MKCOL `/spike30gf/acl-ro/neu-<auth>` | spike30a | `GF acl-ro auth=appapi nutzer=spike30a status=403 angelegt=nein`<br>`GF acl-ro auth=basic nutzer=spike30a status=403 angelegt=nein` | Ablehnung, A8 erwartet 403 | abgelehnt mit 403, nichts angelegt; `s:message` ist leer |
| Positivkontrolle: Konto ohne Regel im selben Ordner | MKCOL `/spike30gf/acl-ro/neu-b-<auth>` | spike30b | `GF acl-ro-kontrolle-b auth=appapi nutzer=spike30b status=201 angelegt=ja`<br>`GF acl-ro-kontrolle-b auth=basic nutzer=spike30b status=201 angelegt=ja` | 201 | angelegt: der Ordner selbst ist beschreibbar, die Ablehnung trifft nur das Konto mit der Regel |
| Positivkontrolle: Regel entfernt, dasselbe Konto | MKCOL `/spike30gf/acl-ro/nach-<auth>` | spike30a | `GF acl-ro-nach-regelentzug auth=appapi nutzer=spike30a status=201 angelegt=ja`<br>`GF acl-ro-nach-regelentzug auth=basic nutzer=spike30a status=201 angelegt=ja` | 201 | angelegt: ohne die Regel legt auch das Messkonto an |
| M2.3 Gruppe mit reinem Leserecht | MKCOL `/spike30gf-lesen/neu-<auth>` | spike30a | `GF gruppe-nur-lesen auth=appapi nutzer=spike30a status=403 angelegt=nein`<br>`GF gruppe-nur-lesen auth=basic nutzer=spike30a status=403 angelegt=nein` | Ablehnung | abgelehnt mit 403, nichts angelegt |
| M2.4 externer Speicher, nur lesbar | MKCOL `/spike30ext/neu-ro-<auth>` | spike30a | `EXTERN ro auth=appapi nutzer=spike30a status=403 angelegt=nein`<br>`EXTERN ro auth=basic nutzer=spike30a status=403 angelegt=nein` | Ablehnung, A8 erwartet 403 | abgelehnt mit 403, im Zielverzeichnis liegt nichts |
| Positivkontrolle: derselbe Speicher ohne `readonly` | MKCOL `/spike30ext/neu-rw-<auth>` | spike30a | `EXTERN rw auth=appapi nutzer=spike30a status=201 angelegt=ja`<br>`EXTERN rw auth=basic nutzer=spike30a status=201 angelegt=ja` | 201 | angelegt, im Zielverzeichnis des lokalen Speichers gefunden |

**Negativtest E12:** `E12 NEGATIVTEST abgelehnt=ja status=403 a8_403=belegt (auth=appapi nutzer=spike30a; auth=basic status=403)`. **Positivfall E12:** `E12 POSITIV angelegt=ja status=201 (auth=appapi nutzer=spike30a)`. **Kontrollen:** `E12 KONTROLLEN kontrolle_b=201 nach_regelentzug=201 (auth=appapi)`.

Dass die Ablehnung an der ACL-Regel hängt und nicht am Ordner oder am Verfahren, zeigen die zwei Kontrollen: ein Konto ohne Regel legt im selben Ordner an, und nach `occ groupfolders:permissions 1 --user spike30a acl-ro clear` legt auch das Messkonto dort an. Die Ablehnung zählt nach der vorab festgelegten Regel (`refused()`): Status außerhalb von 2xx und im Dateisystem nichts angelegt.

Gegenproben über DAV, aus Sicht von `spike30a`: `KONTROLLE oc:permissions /spike30gf/acl-rw aus Sicht von spike30a auth=appapi status=207 permissions=RMGDNVCK` gegen `KONTROLLE oc:permissions /spike30gf/acl-ro aus Sicht von spike30a auth=appapi status=207 permissions=RMG`. Dem Ordner mit der Regel fehlen `D`, `N`, `V`, `C` und `K`; die Antwort trägt außerdem `nc:acl-enabled` mit 1 und in `nc:acl-list` genau die eine Regel (Rohantwort im Protokoll). Ein `PROPFIND` vor dem Anlegen zeigt das fehlende Recht also schon.

### 2.3 Externer Speicher

Hergestellt als lokaler Speicher: `occ files_external:create spike30ext local null::null -c datadir=/var/www/html/data/spike30ext -> Storage created with id 1`, zugewiesen nur an `spike30a`, Option `readonly` erst `true`, dann `false`. Mit `readonly`: `KONTROLLE oc:permissions /spike30ext (readonly=true) aus Sicht von spike30a auth=appapi status=207 permissions=MG`. Ergebnis: `EXTERN A8 abgelehnt=ja status=403 a8_403=belegt positivkontrolle_rw=201 (auth=appapi nutzer=spike30a)`.

### 2.4 A8 je Speicherart und was Phase 31 übernimmt

| Speicherart | A8 (Ablehnung mit 403) | Beleg |
|-------------|------------------------|-------|
| Gruppenordner, ACL-Regel gegen das Konto | belegt | Zeile E12 NEGATIVTEST |
| Gruppenordner, Gruppe mit reinem Leserecht | belegt | Zeile GF gruppe-nur-lesen, 403 |
| Externer Speicher (lokal), `readonly` | belegt | Zeile EXTERN A8 |
| Freigabe ohne Anlegerecht (Abschnitt 1) | belegt | Zeile MKCOL share-ro, 403 |

Für die Meldung "keine Rechte" übernimmt Phase 31:

- In allen vier Fällen kommt derselbe Status 403 mit derselben Ausnahme `Sabre\DAV\Exception\Forbidden` und leerem `s:message`. Der Server sagt nicht, warum abgelehnt wurde; das Werkzeug kann Freigabe, ACL-Regel, Lesegruppe und nur lesbaren Speicher an der Antwort nicht unterscheiden und braucht eine eigene, allgemeine Meldung.
- Nach einem 403 ist nichts angelegt: in jeder Zeile im Dateisystem geprüft.
- Unter Impersonation und mit App-Passwort sind alle Zeilen statusgleich.
- Die Rohantwort für den Gruppenordner mit ACL, auf die sich das Erfolgskriterium 3 der Phase 31 stützt, steht in 12.2.

Gemessen ist eine Regel gegen ein einzelnes Konto. Regeln gegen Gruppen oder Teams, geerbte Regeln in tieferen Ebenen und der Schalter für die Vorgabe ohne Rechte (`--acl-no-default-permission`) sind nicht gemessen.

## 3. Ändernde Zugriffe (MESS-05)

Gemessen am 2026-11-11 auf der Strecke nc35 (Nextcloud 35.0.0, SQLite), Blöcke nc35-up, controls, modify und ui-prepare in einem Aufruf; Rohbeleg `raw/nc35-aendern.txt`, Auszug in 12.3. Die Messkonten sind `spike30a` (schreibt und liest) und `spike30b` (Eigentümer der geteilten Listen). Jede Zeile lief unter AppAPI-Impersonation und, wo es die Kriterien verlangen, zusätzlich mit App-Passwort. Die Listen sind per `MKCALENDAR` mit dem Komponenten-Set genau `VTODO` angelegt; unter Impersonation antwortet `MKCALENDAR` mit 201, der Ersatzweg über PHP wurde nicht gebraucht.

Beide Abbruchkriterien von MESS-05 sind nicht ausgelöst:

- `ABBRUCHKRITERIUM MESS-05 IF-MATCH ausgeloest=nein grund=keiner`
- `ABBRUCHKRITERIUM MESS-05 EIGENSCHAFTEN ausgeloest=nein verloren=keine put_status=204 aenderung_angekommen=ja kontrolle=ok`

"überschrieben" und "unverändert" stammen in jeder Zeile aus dem sha256 der Datenbankspalte `calendardata` vor und nach dem Aufruf, nicht aus dem Statuscode.

### 3.1 PUT mit If-Match unter Impersonation

| Befund | Aufruf | Nutzer | Rohwert wörtlich | Deutung |
|--------|--------|--------|------------------|---------|
| M3.1: PUT mit der gelesenen ETag wird angenommen | `PUT` auf das Objekt in `spike30-a` mit `If-Match` auf die per GET gelesene ETag, nur `SUMMARY` geändert | spike30a, appapi | `IF-MATCH aktuell auth=appapi nutzer=spike30a status=204 etag_vorher=7e104de2233c etag_nachher=2ee40cb76ab8 \| antwort_etag=ja etag_art=stark inhalt_neu=ja db_hash_geaendert=ja db_gleich_gesendet=ja` | 204, neue starke ETag, sie steht auch im Antwortkopf des PUT; GET liefert den gesendeten Text, die Datenbank hält ihn byte-gleich. A13, erster Teil: belegt |
| Positivkontrolle | `exapp_impersonation.log` | spike30a | `KONTROLLE exapp_impersonation.log, PUT-Zeilen von spike30a: 2` | Nextcloud selbst nennt das Konto und die App `mcp_connector` für den PUT |
| Gegenprobe, anderer Leseweg | `REPORT calendar-multiget` mit App-Passwort | spike30a, basic | `GEGENPROBE multiget REPORT calendar-multiget auth=basic nutzer=spike30a status=207 objekte=1 inhalt_gleich_gesendet=ja` | derselbe Inhalt über einen anderen Weg und eine andere Anmeldung |
| Gegenprobe, falsches Secret | derselbe PUT mit `If-Match`, aber falschem APP_SECRET | spike30a | `GEGENPROBE falsches-secret PUT mit If-Match nutzer=spike30a status=401 db_hash_unveraendert=ja` | ohne gültige Anmeldung ändert der Aufruf nichts |
| M3.2: veraltete ETag wird abgelehnt | derselbe PUT mit der ersten, jetzt veralteten ETag | spike30a, appapi | `IF-MATCH veraltet auth=appapi nutzer=spike30a status=412 etag_vorher=2ee40cb76ab8 etag_nachher=2ee40cb76ab8 \| Sabre\DAV\Exception\PreconditionFailed An If-Match header was specified, but none of the specified ETags matched.` | 412, das Objekt ist danach unverändert (Datenbank-Hash gleich, GET byte-gleich, ETag gleich). A13, zweiter Teil: belegt. Die 412-Antwort trägt die aktuelle ETag im Kopf |
| Vergleich der Anmeldewege | dieselbe Folge mit App-Passwort | spike30a, basic | `IF-MATCH GLEICH appapi_basic=ja appapi=(204, True, 412, True) basic=(204, True, 412, True) (status aktuell, etag geaendert, status veraltet, danach unveraendert)` | Impersonation und App-Passwort verhalten sich gleich |
| M3.3: PUT ohne `If-Match` | PUT auf ein vorhandenes Objekt ohne bedingten Kopf | spike30a, appapi | `PUT ohne-if-match auth=appapi nutzer=spike30a status=204 etag_vorher=2ee40cb76ab8 etag_nachher=226402702ad7 \| ueberschrieben=ja` | der Server überschreibt ohne Rückfrage |
| M3.3: PUT mit `If-Match: *` | PUT mit `If-Match: *` | spike30a, appapi | `PUT if-match-stern auth=appapi nutzer=spike30a status=204 etag_vorher=226402702ad7 etag_nachher=432e3008ca1c \| ueberschrieben=ja` | auch der Stern schützt nicht vor einer zwischenzeitlichen Änderung |

Was Phase 33 daraus übernimmt: die Schreibschiene aus TMOD-01 (lesen, dann `PUT` mit `If-Match` auf die gelesene ETag) trägt unter Impersonation. Die beiden Beobachtungen zu M3.3 begründen das Verbot in TMOD-01: ohne `If-Match` und mit `If-Match: *` überschreibt der Server jeden Stand, ein 412 gibt es nur mit einer konkreten ETag. Die ETag ist stark und steht im Antwortkopf des angenommenen PUT; ob das auch gilt, wenn der Server den Text beim Speichern verändert, ist nicht gemessen (Abschnitt 11).

### 3.2 Erhalt fremder Eigenschaften

Das Probeobjekt trägt ein `VTIMEZONE`, ein `VALARM`, drei `X-`Eigenschaften (`X-SPIKE30-FOO`, `X-APPLE-SORT-ORDER`, `X-OC-HIDESUBTASKS`), einen unbekannten Parameter an `SUMMARY`, `CATEGORIES` mit zwei Werten, `CLASS` und eine gefaltete Beschreibung. Geändert wurde der gelesene Text an genau einer Zeile, textuell und ohne Parser.

| Befund | Aufruf | Nutzer | Rohwert wörtlich | Deutung |
|--------|--------|--------|------------------|---------|
| Der Server speichert wörtlich | create-only `PUT`, danach GET und Datenbank-Hash | spike30a, appapi | `SPEICHERUNG woertlich=ja gesendet=633a90c17a2ffd068d3b86762fd9fdf15337f4a1bfc442abcd39e40323730d81:1104 datenbank=1 633a90c17a2ffd068d3b86762fd9fdf15337f4a1bfc442abcd39e40323730d81:1104 get_gleich_gesendet=ja` | sha256 und Länge der Spalte sind die des gesendeten Bodys; die Faltung bleibt, wie gesendet |
| M3.4: ändernder PUT | `PUT` mit `If-Match`, nur `SUMMARY` geändert | spike30a, appapi | `EIGENSCHAFTEN differenz zeilen_vorher=37 zeilen_nachher=37 hinzu=keine entfernt=keine geaendert=['SUMMARY']` | die Zeilenmenge unterscheidet sich genau um die eine geänderte Zeile. A14: belegt |
| Gegenprobe | Datenbank-Hash nach dem ändernden PUT | spike30a, appapi | `SPEICHERUNG nach_aendern woertlich=ja gesendet=64989341a79f258ac32e153a1472056663c4f032b159a18c7938a02a8fdf7cdd:1104 datenbank=1 64989341a79f258ac32e153a1472056663c4f032b159a18c7938a02a8fdf7cdd:1104 get_gleich_gesendet=ja` | auch der zweite Stand liegt byte-gleich in der Datenbank |
| Positivkontrolle | zweites Objekt, dem beim Zurückschreiben eine `X-`Zeile fehlt | spike30a, appapi | `KONTROLLE eigenschaften kontrollobjekt ohne die Zeile X-SPIKE30-FOO:bar zurueckgeschrieben status=204 verloren=['entfernt VCALENDAR/VTODO:X-SPIKE30-FOO:bar'] genau_die_entfernte=ja` | das Verfahren meldet eine fehlende Zeile, und zwar genau diese |
| Pflegefelder des Servers | Differenz aus M3.4 | spike30a, appapi | `PFLEGEFELDER server=keine` | der Server fasst `LAST-MODIFIED`, `DTSTAMP` und `SEQUENCE` nicht an und fügt nichts hinzu |

Was Phase 33 daraus übernimmt: was der Connector sendet, steht danach so in der Datenbank. Der Erhalt fremder Eigenschaften hängt damit allein daran, wie der Connector den gelesenen Text ändert (TMOD-02), nicht am Server. Und weil der Server keine Pflegefelder setzt, muss der Connector `LAST-MODIFIED` und, soweit nötig, `SEQUENCE` selbst pflegen, wenn sie sich ändern sollen; ob die Tasks-App das tut, zeigt die Browser-Sitzung (3.5).

### 3.3 Nur lesbare geteilte Liste

`spike30b` hat zwei Listen an `spike30a` freigegeben, eine nur lesend und eine mit Schreibrecht (`POST` auf die Kalender-URL mit dem share-Dokument, beide Male 200). In der Discovery von `spike30a` erscheinen sie als `spike30-b-ro_shared_by_spike30b` und `spike30-b-rw_shared_by_spike30b`.

| Befund | Aufruf | Nutzer | Rohwert wörtlich | Deutung |
|--------|--------|--------|------------------|---------|
| Lesen geht | GET auf das Objekt in der nur lesbaren Liste | spike30a, appapi | `LESEN geteilt spike30-b-ro_shared_by_spike30b/s30-geteilt-ro-123635.ics auth=appapi nutzer=spike30a status=200` | das Objekt ist sichtbar und lesbar |
| M3.5: PUT wird abgelehnt, mit 404 | `PUT` mit `If-Match` auf die gelesene ETag | spike30a, appapi | `NUR-LESEN put auth=appapi nutzer=spike30a status=404 etag_vorher=180d92b53430 etag_nachher=180d92b53430 \| beim_eigentuemer_unveraendert=ja \| Sabre\DAV\Exception\NotFound Node with name 's30-geteilt-ro-123635.ics' could not be found` | abgelehnt und beim Eigentümer unverändert. Der Status ist 404 und nicht 403, obwohl dasselbe Objekt eben noch lesbar war |
| Anlegen wird abgelehnt, mit 404 | create-only `PUT` in die nur lesbare Liste | spike30a, appapi | `NUR-LESEN anlegen auth=appapi nutzer=spike30a status=404 etag_vorher=- etag_nachher=- \| angelegt=nein \| Sabre\DAV\Exception\NotFound Calendar with name 'spike30-b-ro_shared_by_spike30b' could not be found` | nichts angelegt; die Meldung nennt die Liste als nicht gefunden |
| Positivkontrolle | derselbe PUT in die Freigabe mit Schreibrecht | spike30a, appapi | `SCHREIBRECHT put auth=appapi nutzer=spike30a status=204 etag_vorher=9d8d701ca8d1 etag_nachher=f93acd4b84b2 \| beim_eigentuemer_unveraendert=nein` | mit Schreibrecht wird derselbe Aufruf angenommen und ändert das Objekt des Eigentümers |
| Gegenprobe | Lesen als Eigentümer mit App-Passwort, Datenbank-Hash | spike30b, basic | `NUR-LESEN ERGEBNIS abgelehnt=ja status=404 anlegen=404 positivkontrolle_schreibrecht=204 (auth=appapi); auth=basic: 404, 404, 204` | mit App-Passwort dieselben drei Statuscodes |

Was Phase 33 daraus übernimmt: die Ablehnung einer nur lesbaren geteilten Liste kommt als 404 mit der Meldung "could not be found", nicht als 403. Ein Werkzeug, das nach einem erfolgreichen Lesen ein 404 auf den PUT bekommt, darf daraus nicht "Aufgabe gelöscht" machen; TMOD-01 verlangt hier die klare Meldung "kein Schreibrecht". Gelesen, nicht gemessen: die Umsetzung von 403 nach 404 steht in `apps/dav/lib/Connector/Sabre/DavAclPlugin.php` (für fremde Knoten `NotFound`, für eigene `Forbidden`). Ob sich das Schreibrecht schon vor dem PUT erkennen lässt (Privilegien der Sammlung in der Discovery), gehört zu MESS-03 in Plan 30-04.

### 3.4 Wiederkehrende Aufgaben und Unteraufgaben, Serverseite

| Befund | Aufruf | Nutzer | Rohwert wörtlich | Deutung |
|--------|--------|--------|------------------|---------|
| M3.6: Master mit `RRULE` per PUT abgehakt | `PUT` mit `If-Match`, der `STATUS:COMPLETED`, `PERCENT-COMPLETE:100` und `COMPLETED` am Master setzt | spike30a, appapi | `WIEDERKEHREND server status=204 rrule_erhalten=ja status_completed_gespeichert=ja woertlich_gespeichert=ja objekte_vorher=5 objekte_nachher=5 neue_objekte=keine auth=appapi nutzer=spike30a etag_vorher=67728bfc20f9 etag_nachher=c6bc3d2796d3` | der Server nimmt den PUT an und speichert ihn wörtlich: die ganze Serie steht danach als erledigt da, die `RRULE` bleibt, es entsteht kein Folgeobjekt. Der Server kennt kein "diese eine Wiederholung abhaken" |
| M3.7: Elternaufgabe per PUT abgehakt | `PUT` mit `If-Match` auf die Elternaufgabe; Unteraufgabe mit `RELATED-TO` davor und danach gelesen | spike30a, appapi | `UNTERAUFGABE server unveraendert=ja eltern_status=204 eltern_etag_geaendert=ja kind_etag_vorher=db690a34e9bf kind_etag_nachher=db690a34e9bf kind_hash_gleich=ja auth=appapi nutzer=spike30a` | die Elternaufgabe hat eine neue ETag (Positivkontrolle), die Unteraufgabe ist in ETag, Inhalt und Datenbank-Hash unverändert. A16, Serverseite: belegt |

Für A15 heißt das: serverseitig spricht nichts dafür, wiederkehrende Aufgaben in einem Objekt abzuhaken. Ein PUT am Master beendet die Serie, statt eine Wiederholung zu erledigen. Die Vorgabe "ablehnen" bleibt von der Serverseite her bestehen; was die Tasks-App an dieser Stelle schreibt, zeigt die Browser-Sitzung (3.6).

### 3.5 Was die Tasks-App beim Abhaken und Wiederöffnen schreibt

Gemessen am 2026-11-11 mit Tasks 0.18.1 auf nc35 (Nextcloud 35.0.0, SQLite), Konto `spike30ui`. Die Hauptsitzung hat die zwölf Schritte aus `.planning/phases/30-mess-spike-aufgaben-und-ordner/30-02-BROWSER-SCHRITTE.md` in Chromium (Playwright) gefahren, Zeitzone des Browsers Europe/Berlin. Stand a (nach dem Anlegen, vor jeder Änderung) und Stand b (nach Runde B) sind je per DAV gesichert: ein GET je Objekt unter Impersonation, die Dateien liegen unter `raw/ui-a/` und `raw/ui-b/`. Verglichen wird dasselbe Objekt über seine UID. Nichts in diesem Abschnitt stammt aus dem Quelltext der App.

Drei Belege tragen jede Aussage: die Differenz der Rohobjekte, dieselben Listen noch einmal mit App-Passwort und einem REPORT gelesen (`UI-GLEICH appapi_basic=ja abweichend=keine`), und das Zugriffsprotokoll des Webservers, das jeden schreibenden Aufruf des Kontos mit Statuscode nennt (12.4). Was die Oberfläche anzeigte, ist kein Beleg; an einer Stelle widerspricht es dem Server (3.6).

Pflichtzeilen, wörtlich aus `raw/ui-sitzung.txt`:

- `ABHAKEN FELDER hinzu=COMPLETED,PERCENT-COMPLETE,STATUS entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED zeitform_completed=utc`
- `WIEDEROEFFNEN FELDER hinzu=STATUS entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED`
- `KONTROLLE unberuehrt differenz=leer`
- `UI-STAND a objekte=15`, `UI-STAND b objekte=15`

| Handlung in der App | Was danach im Objekt steht | Rohwert wörtlich |
|---------------------|----------------------------|------------------|
| `s30 abhaken` abgehakt | hinzu: `STATUS:COMPLETED`, `PERCENT-COMPLETE:100`, `COMPLETED` als UTC-Zeit mit `Z`; geändert: `LAST-MODIFIED` und `DTSTAMP`, beide auf den Zeitpunkt des Abhakens; nichts entfernt, kein `SEQUENCE` | `ABHAKEN zeilen_hinzu=['COMPLETED:20261111T125947Z', 'PERCENT-COMPLETE:100', 'STATUS:COMPLETED']` |
| `s30 wieder-oeffnen` abgehakt und wieder geöffnet | Endstand gegen Stand a: hinzu `STATUS:NEEDS-ACTION`; `COMPLETED` und `PERCENT-COMPLETE` stehen nicht mehr im Objekt (entfernt, nicht auf 0 gesetzt); geändert `LAST-MODIFIED` und `DTSTAMP` | `WIEDEROEFFNEN zeilen_hinzu=['STATUS:NEEDS-ACTION'] abhaken_felder_danach_fehlend=COMPLETED,PERCENT-COMPLETE status_danach=NEEDS-ACTION` |
| `s30 unberuehrt` nicht angefasst | leere Differenz (Positivkontrolle M3.8) | `KONTROLLE unberuehrt differenz=leer` |
| Vergleichsobjekt, vom Skript per `PUT` mit `If-Match` abgehakt | genau die drei gesendeten Zeilen, sonst nichts: der Server pflegt kein Feld | `VERGLEICH skript_put pflegefelder_server=keine anlegen=201 abhaken=204 etag_vorher=f11673e3ef94 etag_nachher=eeb5d58cd8b1 gesendet_hinzu=['COMPLETED:20261111T130535Z', 'PERCENT-COMPLETE:100', 'STATUS:COMPLETED'] vom_server_entfernt=keine woertlich_gespeichert=ja auth=appapi nutzer=spike30a liste=spike30-a objekt=s30-vergleich-130535.ics` |

Der Satz für TMOD-03: die Tasks-App setzt beim Abhaken `STATUS:COMPLETED`, `PERCENT-COMPLETE:100` und `COMPLETED` in UTC mit `Z` und zieht `LAST-MODIFIED` und `DTSTAMP` auf denselben Zeitpunkt nach. Beim Wiederöffnen setzt sie `STATUS:NEEDS-ACTION`, entfernt `COMPLETED` und `PERCENT-COMPLETE` und zieht `LAST-MODIFIED` und `DTSTAMP` nach. `SEQUENCE` schreibt sie in keinem der beiden Fälle. Weil der Server keines dieser Felder von sich aus pflegt (Vergleichsobjekt, und 3.2), stammen `LAST-MODIFIED` und `DTSTAMP` von der App; ein Werkzeug, das sich wie die App verhalten soll, muss beide selbst setzen.

A12 ist damit belegt, mit zwei Präzisierungen: das "Gegenstück" beim Wiederöffnen ist `STATUS:NEEDS-ACTION` plus das Entfernen von `COMPLETED` und `PERCENT-COMPLETE`, nicht ein Zurücksetzen auf einen Wert; und zu den Feldern des Abhakens gehören bei der App die beiden Pflegefelder `LAST-MODIFIED` und `DTSTAMP`.

Zeitformen, wie die App sie schreibt (Zeilen `ZEITFORM` in der Rohdatei): ein ganztägiges Fälligkeitsdatum als `DUE;VALUE=DATE:20261120`; ein Fälligkeitsdatum mit Uhrzeit als UTC (`DUE:20261120T091500Z` für 10:15 Uhr in Europe/Berlin), ebenso `DTSTART`; `COMPLETED`, `CREATED`, `LAST-MODIFIED` und `DTSTAMP` immer als UTC. Die App schreibt in keinem der fünfzehn Objekte ein `TZID` und kein `VTIMEZONE`.

Einschränkungen: für `s30 wieder-oeffnen` liegt nur der Endstand vor, nicht der Zwischenstand nach dem Abhaken; dass er dem von `s30 abhaken` gleicht, ist nicht gemessen. Gemessen ist eine Fassung der App (0.18.1) auf einer Fassung des Servers.

### 3.6 Wiederkehrende Aufgaben und Unteraufgaben in der Tasks-App

Pflichtzeilen, wörtlich aus `raw/ui-sitzung.txt`:

- `ELTERN ABHAKEN kind_geaendert=ja kind_differenz=hinzu=COMPLETED,PERCENT-COMPLETE,STATUS entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED | eltern_geaendert=nein eltern_differenz=leer`
- `WIEDERKEHREND app differenz hinzu=keine entfernt=keine geaendert=DTSTAMP,DUE,LAST-MODIFIED due_vorher=20261120T130000Z due_nachher=20261121T130000Z rrule_nachher=FREQ=DAILY status_nachher=fehlt completed_nachher=fehlt neue_objekte=0`

**Wiederkehrende Aufgabe (A15, App-Seite).** Die App hat `s30 wiederkehrend` selbst angelegt (`RRULE:FREQ=DAILY`, im Dialog "Aufgabe wiederholen" die Auswahl "Tag"). Beim Abhaken erledigt sie die Aufgabe nicht: sie schiebt `DUE` um einen Tag weiter (von `20261120T130000Z` auf `20261121T130000Z`), lässt die `RRULE` stehen, setzt weder `STATUS` noch `COMPLETED` und legt kein zweites Objekt an. Das ist ein einzelner `PUT` mit 204. Die App schreibt die Serie also fort, statt eine Wiederholung als erledigt festzuhalten. Zusammen mit 3.4 (ein `PUT` am Master, der `STATUS:COMPLETED` setzt, erledigt die ganze Serie) heißt das für A15: ein Abhaken, das dem Verhalten der App entspricht, verlangt die Berechnung des nächsten Termins aus der `RRULE`, und die ist als Grenze des Projekts ausgeschlossen. Die Vorgabe "ablehnen" bleibt von der Messung her bestehen; über sie entscheidet der Owner am Checkpoint in Plan 30-05.

**Elternaufgabe mit Unteraufgabe (A16, App-Seite).** Angeklickt wurde nur das Kontrollkästchen der Elternaufgabe `s30 eltern-abhaken`, die App stellte keine Rückfrage. Das Zugriffsprotokoll zeigt, was sie daraufhin tat: zwei `PUT` innerhalb einer Sekunde, einer auf die Unteraufgabe (204) und einer auf die Elternaufgabe (500). Auf dem Server steht danach die Unteraufgabe `s30 kind-abhaken` als erledigt (`ELTERN ABHAKEN kind_zeilen_hinzu=['COMPLETED:20261111T130125Z', 'PERCENT-COMPLETE:100', 'STATUS:COMPLETED'] eltern_status_stand_b=fehlt`), die Elternaufgabe ist unverändert offen: gleiche ETag wie in Stand a, leere Differenz. Die Ursache des 500 nennt das Serverprotokoll: `SQLSTATE[HY000]: General error: 5 database is locked`, also zwei gleichzeitige Schreibzugriffe auf SQLite.

Der Widerspruch zwischen Oberfläche und Server, wie ihn die Hauptsitzung gesehen hat: direkt nach dem Klick zeigte die App beide Aufgaben als erledigt; nach einem späteren Neuladen der Liste stand die Elternaufgabe wieder als offen da. Die Rohobjekte und das Zugriffsprotokoll erklären beides: die App zeigt den gewünschten Zustand sofort an und hat den gescheiterten `PUT` der Elternaufgabe nicht als Fehler gemeldet; nach dem Neuladen zeigt sie, was der Server hat. Belegt ist das durch drei voneinander unabhängige Quellen (Rohobjekt und ETag in Stand b, Statuscode 500 im Zugriffsprotokoll, Ausnahme im Serverprotokoll).

Für A16 heißt das: serverseitig ist die Annahme belegt (3.4, der Server fasst die Unteraufgabe nicht an). Als Aussage über die Tasks-App ist sie widerlegt: die App hakt die Unteraufgabe von sich aus mit ab, mit einem eigenen `PUT`. Die Vorgabe aus TMOD-03, Unteraufgaben nicht mit abzuhaken, bleibt möglich, weicht dann aber bewusst vom Verhalten der App ab; das ist eine Entscheidung für den Owner-Checkpoint in Plan 30-05. Welche Felder die App in die Elternaufgabe geschrieben hätte, ist nicht gemessen, weil dieser `PUT` scheiterte.

Zwei Nebenbefunde für Phase 33: ein 5xx auf einen `PUT` darf nie als Erfolg gemeldet werden, und auf SQLite genügen zwei gleichzeitige Schreibzugriffe desselben Kontos für einen solchen Fehler (in der Sitzung zweimal, auch in Runde A bei `s30 uhrzeit`).

**Rohmaterial für die Pläne 30-03 und 30-04** (hier nur gesichert und gezählt, nicht ausgewertet): Die App verschiebt mit `MOVE`, je Objekt ein Aufruf mit 201; beim Verschieben der Elternaufgabe `s30 eltern-umzug` hat sie die Unteraufgabe `s30 kind-umzug` mit einem eigenen `MOVE` mitgenommen; Objektname und Inhalt sind in der Zielliste unverändert (`UI-UMZUG objekte_in_liste_2=3 verschoben=3`). Beim Löschen der Elternaufgabe `s30 eltern-loeschen` hat sie auch die Unteraufgabe gelöscht, zwei `DELETE` mit 204; beide Objekte liegen mit unverändertem Inhalt im Papierkorb des Kalenders, dort unter einem Namen aus der Datenbank-Kennung (`UI-PAPIERKORB objekte=2`). Die App legt eine Liste mit `MKCOL` an, nicht mit `MKCALENDAR`, mit dem Komponenten-Set `VTODO`; das Konto hatte nach der ersten Anmeldung außerdem einen Kalender `personal` mit `VEVENT`, `VTODO` und `VJOURNAL`. Die rohe Discovery-Antwort des Kontos steht in `raw/ui-sitzung.txt` (Zeile `UI-DISCOVERY-ROH`).

## 4. Verschieben und Löschen (MESS-06)

Gemessen am 2026-11-11 auf der Strecke nc35 (Nextcloud 35.0.0, SQLite), Blöcke nc35-up, controls, move, ui-evaluate-move und nc35-stop in einem Aufruf; Rohbeleg `raw/nc35-verschieben.txt`, Auszug in 12.6. Die Messkonten sind `spike30a` (verschiebt, löscht, liest) und `spike30b` (Eigentümer der geteilten Listen). Die Listen `spike30-a` und `spike30-b` tragen das Komponenten-Set genau `VTODO`, `spike30-nur-termine` genau `VEVENT`; der Deck-Kalender gehört zu einem Board, das `spike30a` über die REST-Schnittstelle von Deck 1.19.0 angelegt hat (Fassung gelesen mit `occ app:list --output=json`, Zeile `BASELINE-START apps_an` desselben Protokolls). Die Messschritte liefen nacheinander; außer der schon aus Plan 30-02 bekannten Antwort 501 auf `PROPFIND` im Papierkorb trat in keinem Schritt ein Statuscode 5xx auf.

Bevor ein Pfad oder ein Schalter des Kalender-Papierkorbs benutzt wurde, hat der Block die Quelle der laufenden Instanz gelesen und als `QUELLE`-Zeilen ins Protokoll geschrieben (12.6). Das Ergebnis in einer Zeile: `QUELLE BESTAETIGT schluessel=calendarRetentionObligation standard_sekunden=2592000 aus_wert=0 sammlung=trashbin/objects wiederherstellung=Verschieben nach trashbin/restore/<name> eigenschaft={http://nextcloud.com/ns}trash-bin-retention-duration aufraeumen=occ dav:retention:clean-up`. Diese Werte sind gelesen; gemessen ist, was die Tabellen darunter nennen.

Das Abbruchkriterium von MESS-06 für das Verschieben ist nicht ausgelöst:

- `ABBRUCHKRITERIUM MESS-06 MOVE ausgeloest=nein grund=keiner`

TMOD-08 darf damit geplant werden. "überschrieben", "unverändert" und der Ort eines Objekts stammen in jeder Zeile aus der Tabelle `calendarobjects` (Zeile je UID mit Kalender, Objektname, `deleted_at` und sha256 des Textes), nicht aus dem Statuscode.

### 4.1 MOVE unter Impersonation

| Befund | Aufruf | Nutzer | Rohwert wörtlich | Deutung |
|--------|--------|--------|------------------|---------|
| M4.1: MOVE von eigener Liste in eigene Liste | `MOVE` auf das Objekt in `spike30-a`, `Destination` auf denselben Objektnamen in `spike30-b`, keine weitere Kopfzeile | spike30a, appapi | `MOVE eigen auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=5aa17592e862 etag_nachher=5aa17592e862 \| inhalt_gleich=ja` | 201, die Quelle antwortet danach 404, das Ziel 200, UID und Text sind byte-gleich, und auch die ETag ist dieselbe wie vor dem Umzug. A19, erster Teil: belegt |
| Positivkontrolle | `exapp_impersonation.log` | spike30a | `KONTROLLE exapp_impersonation.log, Zeilen der Methode von spike30a: 1` | Nextcloud selbst nennt das Konto und die App `mcp_connector` für den `MOVE` (Rohzeile in 12.6) |
| Gegenprobe, anderer Weg | `REPORT calendar-query` auf beide Listen mit App-Passwort, dazu die Datenbankzeile | spike30a, basic | `GEGENPROBE eigen auflistung REPORT calendar-query auth=basic nutzer=spike30a in_spike30-a=nein in_spike30-b=ja \| datenbank=spike30a/spike30-b/s30-eigen-164021.ics:deleted_at_leer:da0341633dd5 db_gleich_gesendet=ja` | die Quellliste nennt das Objekt nicht mehr, die Zielliste nennt es; in der Datenbank steht genau eine Zeile, im Zielkalender, mit dem Hash des gesendeten Textes |
| Gegenprobe, falsches Secret | derselbe `MOVE` mit falschem APP_SECRET | spike30a | `GEGENPROBE eigen falsches-secret status=401 datenbank=spike30a/spike30-a/s30-eigen-falsches-secret-164021.ics:deleted_at_leer:0f2fd581fefc \| Sabre\DAV\Exception\NotAuthenticated No public ac` | 401, das Objekt liegt weiter in der Quellliste |
| Vergleich der Anmeldewege | dieselbe Folge mit App-Passwort | spike30a, basic | `MOVE GLEICH appapi_basic=ja appapi=(201, 404, 200, 'ja', True) basic=(201, 404, 200, 'ja', True) (status, quelle danach, ziel danach, uid gleich, inhalt gleich)` | Impersonation und App-Passwort verhalten sich gleich |
| Produktionsweg | `MOVE` aus dem ExApp-Container gegen `http://caddy`, `Destination` auf `http://caddy`, `Overwrite: F` | spike30a, appapi | `PRODUKTIONSWEG MOVE status=201 verschoben=ja nutzer=spike30a datenbank=spike30a/spike30-b/s30-produktion-164021.ics:deleted_at_leer:b0b4556d51cf (aus nc_app_mcp_connector gegen http://caddy, Destination auf http://caddy, Overwrite F; lauf=164021)` | auch auf dem Weg, den die App in Produktion nimmt, 201 und verschoben |
| `Destination` nur als Pfad | wie M4.1, `Destination` ohne Schema und Host | spike30a, appapi | `MOVE ziel-nur-pfad auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=6d27080af9b7 etag_nachher=6d27080af9b7 \| inhalt_gleich=ja destination_basis=(keine, nur Pfad)` | der Server nimmt den bloßen Pfad an |
| `Destination` mit fremdem Host | wie M4.1, `Destination` auf `http://spike30.invalid` plus Pfad | spike30a, appapi | `MOVE ziel-fremder-host auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=5df513c84dc8 etag_nachher=5df513c84dc8 \| inhalt_gleich=ja destination_basis=http://spike30.invalid` | der Server wertet nur den Pfad aus, der Hostname im Kopf spielt keine Rolle; das Objekt liegt danach in der Zielliste derselben Instanz |
| M4.2: belegtes Ziel mit `Overwrite: F` | `MOVE` auf einen Namen, unter dem in der Zielliste schon ein anderes Objekt liegt, mit `Overwrite: F` | spike30a, appapi | `MOVE belegt-overwrite-f auth=appapi status=412 quelle_danach=200 ziel_danach=200 uid_gleich=nein etag_vorher=100e358f27b0 etag_nachher=b9c63f0abe75 \| inhalt_gleich=nein ueberschrieben=nein altes_ziel=unveraendert quelle_unveraendert=ja Sabre\DAV\Exception\PreconditionFailed The destination node already exists, and the overwrite header is set to false` | 412, Quelle und Ziel unverändert (Hashvergleich: `HASH ziel vorher=spike30a/spike30-b/s30-belegt-overwrite-f-164021.ics:deleted_at_leer:ffab0ee66a48 nachher=spike30a/spike30-b/s30-belegt-overwrite-f-164021.ics:deleted_at_leer:ffab0ee66a48 \| quelle vorher=spike30a/s`) |
| M4.2: belegtes Ziel ohne Kopfzeile | derselbe Aufruf ohne `Overwrite` | spike30a, appapi | `MOVE belegt-ohne-kopf auth=appapi status=204 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=d6ff3c8bf3ee etag_nachher=d6ff3c8bf3ee \| inhalt_gleich=ja ueberschrieben=ja altes_ziel=papierkorb quelle_unveraendert=nein` | 204: der Server überschreibt. Das bisherige Zielobjekt ist danach nicht mehr in der Liste, es steht mit gesetztem `deleted_at` im Papierkorb (`HASH ziel vorher=spike30a/spike30-b/s30-belegt-ohne-kopf-164021.ics:deleted_at_leer:61315ea61035 nachher=spike30a/spike30-b/s30-belegt-ohne-kopf-164021-deleted.ics:deleted_at_gesetzt:61315ea61035 \| quelle vorher=spike30a/spike30-a`). A19, dritter Teil ("überschreibt kein belegtes Ziel"): widerlegt für den Aufruf ohne Kopfzeile, belegt mit `Overwrite: F` |
| M4.3: gleiche UID schon in der Zielliste | `MOVE` eines Objekts, dessen UID in der Zielliste unter einem anderen Dateinamen schon vorkommt | spike30a, appapi | `MOVE gleiche-uid auth=appapi status=409 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=3dc5a45b4baa etag_nachher=- \| inhalt_gleich=nein datenbank_unveraendert=ja OCA\DAV\Exception\UidConflict Calendar object with uid already exists in this calendar collection.` | 409 `UidConflict`, beide Objekte unverändert (`GEGENPROBE gleiche-uid auflistung auth=basic nutzer=spike30a spike30-a=['s30-gleiche-uid-164021.ics'] spike30-b=['s30-gleiche-uid-ziel-164021.ics']`) |
| M4.4: geteilte Liste mit Schreibrecht | `MOVE` in `spike30-b-rw_shared_by_spike30b` | spike30a, appapi | `MOVE geteilt-rw auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=62145898d076 etag_nachher=62145898d076 \| inhalt_gleich=ja ziel=spike30-b-rw_shared_by_spike30b quelle_unveraendert=nein datenbank_nachher=spike30b/spike30-b-rw/s30-geteilt-rw-164021.ics:deleted_at_leer:604857aed7ea` | 201; das Objekt liegt danach im Kalender des Eigentümers `spike30b` (`GEGENPROBE geteilt-rw lesen als Eigentuemer nutzer=spike30b auth=basic liste=spike30-b-rw status=200`) |
| M4.4: geteilte Liste ohne Schreibrecht | `MOVE` in `spike30-b-ro_shared_by_spike30b` | spike30a, appapi | `MOVE geteilt-ro auth=appapi status=404 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=802d38bf8901 etag_nachher=- \| inhalt_gleich=nein ziel=spike30-b-ro_shared_by_spike30b quelle_unveraendert=ja datenbank_nachher=spike30a/spike30-a/s30-geteilt-ro-164021.ics:deleted_at_leer:b1137ca0957e Sabre\DAV\Exception\NotFound Calendar with name 'spike30-b-ro_shared_by_spike30b' could not be found` | 404 mit der Meldung, der Kalender sei nicht zu finden, nicht 403; die Quelle ist unverändert (`GEGENPROBE geteilt-ro lesen als Eigentuemer nutzer=spike30b auth=basic liste=spike30-b-ro status=404`). Dasselbe Bild wie beim `PUT` in 3.3 |
| M4.4: Deck-Kalender als Ziel | `MOVE` in `app-generated--deck--board-65` | spike30a, appapi | `MOVE deck auth=appapi status=403 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=c39b032e5bc0 etag_nachher=- \| inhalt_gleich=nein ziel=app-generated--deck--board-65 quelle_unveraendert=ja datenbank_nachher=spike30a/spike30-a/s30-deck-164021.ics:deleted_at_leer:d0298ad1d8c9 Sabre\DAV\Exception\Forbidden Access denied` | 403 `Access denied`, die Quelle ist unverändert |
| M4.4: Kalender ohne `VTODO` als Ziel | `MOVE` in `spike30-nur-termine` (Komponenten-Set genau `VEVENT`) | spike30a, appapi | `MOVE nur-termine auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=9ad966a72ca4 etag_nachher=9ad966a72ca4 \| inhalt_gleich=ja ziel=spike30-nur-termine quelle_unveraendert=nein datenbank_nachher=spike30a/spike30-nur-termine/s30-nur-termine-164021.ics:deleted_at_leer:f370e491fe3d` | 201: der Server prüft das Komponenten-Set des Ziels beim `MOVE` nicht, die Aufgabe liegt danach in einem Kalender, der nur Termine führen soll |
| M4.5: `If-Match` mit aktueller ETag | `MOVE` mit `If-Match` auf die gelesene ETag | spike30a, appapi | `MOVE if-match-aktuell auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=b0db695c5f7a etag_nachher=b0db695c5f7a \| inhalt_gleich=ja if_match=b0db695c5f7a datenbank_unveraendert=nein auflistung_basic_in_spike30-b=ja` | 201, verschoben |
| M4.5: `If-Match` mit veralteter ETag | `MOVE` mit der ETag von vor einer Änderung | spike30a, appapi | `MOVE if-match-veraltet auth=appapi status=412 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=e322ec2af6ef etag_nachher=- \| inhalt_gleich=nein if_match=20a904a9f4ec datenbank_unveraendert=ja auflistung_basic_in_spike30-b=nein Sabre\DAV\Exception\PreconditionFailed An If-Match header was specified, but none of the specified ETags matched.` | 412, nichts verschoben: `If-Match` wirkt bei `MOVE` wie bei `PUT` |

**DELETE unter Impersonation, Papierkorb im Auslieferungszustand (M4.8).** Der Schalter wurde auf nc35 nur gelesen: `PAPIERKORB zustand=leer (occ config:app:get dav calendarRetentionObligation; leer heisst Standard, laut Quelle 2592000 Sekunden; auf nc35 wird der Schalter nie veraendert)`.

| Befund | Aufruf | Nutzer | Rohwert wörtlich | Deutung |
|--------|--------|--------|------------------|---------|
| DELETE mit gelesener ETag | `DELETE` mit `If-Match` | spike30a, appapi | `DELETE impersonation status=204 auth=appapi nutzer=spike30a if_match=78c0e9fa9584 get_danach=404 \|` | 204, das Objekt antwortet danach 404 |
| Positivkontrolle | `exapp_impersonation.log` | spike30a | `KONTROLLE exapp_impersonation.log, DELETE-Zeilen von spike30a: 1` | Nextcloud nennt Konto und App für den `DELETE` |
| DELETE mit veralteter ETag | `DELETE` mit der ETag von vor einer Änderung | spike30a, appapi | `DELETE veraltet status=412 objekt_unveraendert=ja auth=appapi nutzer=spike30a \| datenbank vorher=spike30a/spike30-a/s30-loeschen-veraltet-164021.ics:deleted_at_leer:897af59ad68e nachher=spike30a/spike30-a/s30-loeschen-veraltet-164021.ics:deleted_at_leer:897af59ad68e \| Sabre\DAV\Exception\PreconditionFailed An If-Match header was specified, but none of the specified ETags matched.` | 412, das Objekt ist unverändert: `If-Match` wirkt auch bei `DELETE` |
| Auflistung des Papierkorbs | `PROPFIND` und `REPORT calendar-query` auf `trashbin/objects` | spike30a, appapi | `PAPIERKORB PROPFIND Depth 1 trashbin/objects status=501 \| Sabre\DAV\Exception\NotImplemented` und `PAPIERKORB eintrag=ja name=166.ics eintraege=3 (REPORT calendar-query, auth=appapi nutzer=spike30a) \| GEGENPROBE datenbank=spike30a/spike30-a/s30-loeschen-164021-deleted.ics:deleted_at_gesetzt:1e007df35cec` | `PROPFIND` antwortet 501 (wie in 30-02), der `REPORT` listet das Objekt unter `<id>.ics`. Gegenprobe ohne DAV: die Datenbankzeile trägt `deleted_at` und den Namen mit dem Zusatz `-deleted` |
| Wiederherstellung | `MOVE` des Papierkorb-Eintrags auf `trashbin/restore/file` | spike30a, appapi | `WIEDERHERSTELLUNG status=201 uid_gleich=ja inhalt_gleich=ja get_danach=200 auth=appapi nutzer=spike30a \| GEGENPROBE datenbank=spike30a/spike30-a/s30-loeschen-164021.ics:deleted_at_leer:1e007df35cec \|` | 201, das Objekt ist am alten Ort mit gleicher UID und byte-gleichem Text zurück; in der Datenbank ist `deleted_at` wieder leer und der alte Name wieder da |

Was Phase 33 für TMOD-08 daraus übernimmt:

- `MOVE` zwischen zwei Aufgabenlisten trägt unter Impersonation, auch auf dem Produktionsweg. UID, Text und ETag bleiben erhalten; der Objektname ist frei wählbar und blieb in der Messung derselbe.
- Der Kopf `Overwrite: F` ist Pflicht. Ohne ihn überschreibt der Server ein belegtes Ziel mit 204; das verdrängte Objekt liegt dann im Papierkorb des Kalenders. Mit `Overwrite: F` antwortet er 412 und ändert nichts.
- `If-Match` wirkt bei `MOVE`: mit einer veralteten ETag 412, nichts verschoben. Die Schreibschiene aus TMOD-01 (gelesene ETag) gilt damit auch für das Verschieben.
- Eine gleiche UID in der Zielliste beantwortet der Server selbst mit 409.
- Eine geteilte Liste ohne Schreibrecht lehnt mit 404 ab, ein Deck-Kalender mit 403. Der Connector kann sich für die Meldung "kein Schreibrecht" nicht auf 403 stützen.
- Der Server prüft beim `MOVE` nicht, ob das Ziel Aufgaben führen darf. Die Regel "Ziel ist eine beschreibbare Aufgabenliste" muss der Connector vor dem Aufruf aus der Discovery durchsetzen; der Server tut es nicht.
- Der Hostname im Kopf `Destination` wird nicht ausgewertet, nur der Pfad. Der Connector baut den Kopf aus der Basis-URL, unter der er Nextcloud erreicht.

### 4.2 Unteraufgaben beim Verschieben und Löschen

Server und Tasks-App sind getrennt belegt: die Serverseite durch Aufrufe dieses Plans unter Impersonation (M4.6), die App durch die Rohobjekte der Browser-Sitzung aus Plan 30-02, in diesem Plan nur gelesen und ausgewertet (M4.7; `APP AUSWERTUNG quelle=raw/ui-a (15 Objekte) und raw/ui-b (15 Objekte), Listen aus den Zeilen UI-OBJEKT in raw/ui-sitzung.txt; nur gelesen, kein Aufruf gegen eine Instanz`).

| Befund | Aufruf | Nutzer | Rohwert wörtlich | Deutung |
|--------|--------|--------|------------------|---------|
| M4.6 Server: nur die Elternaufgabe wird verschoben | `MOVE` der Elternaufgabe nach `spike30-b`; die Unteraufgabe (`RELATED-TO` auf die UID der Elternaufgabe) wird nicht angefasst | spike30a, appapi | `UNTERAUFGABE server-verschieben ort=spike30-a unveraendert=ja eltern_status=201 eltern_verschoben=ja kind_get=200 kind_etag_vorher=78a77dd363a6 kind_etag_nachher=78a77dd363a6 auth=appapi nutzer=spike30a \| datenbank kind vorher=spike30a` | der Server nimmt die Unteraufgabe nicht mit: sie liegt unverändert in der Quellliste (ETag, Text und Datenbankzeile gleich), die Elternaufgabe in der Zielliste |
| M4.6 Server: nur die Elternaufgabe wird gelöscht | `DELETE` der Elternaufgabe mit `If-Match` | spike30a, appapi | `UNTERAUFGABE server-loeschen vorhanden=ja unveraendert=ja eltern_status=204 eltern_geloescht=ja kind_get=200 kind_etag_vorher=c6f927905036 kind_etag_nachher=c6f927905036 auth=appapi nutzer=spike30a \| datenbank kind vorher=spike30a/spik` | der Server löscht die Unteraufgabe nicht mit: sie bleibt unverändert in der Liste und verweist auf eine Elternaufgabe, die im Papierkorb liegt |
| M4.7 App: Elternaufgabe wechselt die Liste | Stand a gegen Stand b der Browser-Sitzung | spike30ui (Browser, 30-02) | `APP VERSCHIEBEN eltern=s30 eltern-umzug kind=zieht mit eltern_uid_gleich=ja eltern_ort_danach=spike30-liste-2 kind_ort_danach=spike30-liste-2` | die Tasks-App 0.18.1 nimmt die Unteraufgabe mit; im Zugriffsprotokoll der Sitzung stehen dafür zwei `MOVE`, einer je Objekt, beide 201 (`raw/ui-sitzung.txt`, Zeilen `UI-ZUGRIFF`) |
| M4.7 App: Elternaufgabe wird gelöscht | Stand a gegen Stand b | spike30ui (Browser, 30-02) | `APP LOESCHEN eltern=s30 eltern-loeschen kind=kind im papierkorb eltern_ort_danach=trashbin kind_ort_danach=trashbin` | die App löscht die Unteraufgabe mit, zwei `DELETE` mit 204 (`raw/ui-sitzung.txt`, Zeilen `UI-ZUGRIFF`); beide liegen im Papierkorb des Kalenders |
| M4.7 App: einzelne Aufgabe | Stand a gegen Stand b | spike30ui (Browser, 30-02) | `APP VERSCHIEBEN einzeln uid_gleich=ja dateiname_gleich=ja inhalt_gleich=ja von=spike30-liste-1 nach=spike30-liste-2 positivkontrolle_umzug_stattgefunden=ja` | UID, Dateiname und Inhalt bleiben beim Umzug gleich |
| Positivkontrolle | nicht angefasstes Objekt | spike30ui (Browser, 30-02) | `KONTROLLE unberuehrt differenz=leer ort_gleich=ja` | das Verfahren meldet für ein unberührtes Objekt keine Differenz und keinen Ortswechsel |
| Gegenprobe, andere Zählung | Objektzahl je Liste aus den Zeilen `UI-OBJEKT` | spike30ui (Browser, 30-02) | `GEGENPROBE objektzahl stand=a {"spike30-liste-1": 15}` und `GEGENPROBE objektzahl stand=b {"spike30-liste-1": 10, "spike30-liste-2": 3, "trashbin": 2}` | 15 Objekte in beiden Ständen: drei sind umgezogen, zwei liegen im Papierkorb, keines ist verschwunden |

A21 ist damit für beide Seiten belegt. Der Server tut von sich aus nichts mit der Unteraufgabe, weder beim Verschieben noch beim Löschen der Elternaufgabe; die Tasks-App nimmt sie in beiden Fällen mit einem eigenen Aufruf mit. Nach dem Wortlaut von A21 ("ziehen die Kinder in der Tasks-App mit, folgt der Connector dem Gemessenen") bleibt die Vorgabe "ablehnen" also nicht bestehen: gemessen ist, dass die Kinder mitziehen und mitgelöscht werden. Gemessen ist auch der Preis: Mitnehmen heißt ein eigener Aufruf je Objekt ohne gemeinsame Transaktion, und ein Aufruf, der nur die Elternaufgabe bewegt, hinterlässt einen Zustand, den die App nie herstellt (Unteraufgabe in einer anderen Liste als ihre Elternaufgabe, oder Unteraufgabe einer gelöschten Elternaufgabe). Wie Phase 33 das Mitnehmen baut (Reihenfolge, Verhalten bei einem Teilfehler, `If-Match` je Objekt), ist dort zu planen; die Übergabe an die Phasen und an den Owner-Checkpoint steht in Plan 30-05.

### 4.3 Löschen und Papierkorb auf Nextcloud 32 bis 35

Gemessen am 2026-11-11 auf vier Wegwerf-Instanzen aus `compose.spike-tags.yml` (offizielles Image, SQLite, Loopback `http://127.0.0.1:8083`), eine nach der anderen, jede von der leeren Maschine bis `down -v`: Block delete-matrix, Rohbelege `raw/loeschen-32.txt` bis `raw/loeschen-35.txt`, Auszug in 12.7. Die Fassungen of record aus `occ status` sind 32.0.15, 33.0.9, 34.0.4, 35.0.2. Die Konten sind `alice` (löscht) und `bob` (Eigentümer der geteilten Listen), je mit App-Passwort: auf den Wegwerf-Instanzen gibt es keine ExApp, das Löschen unter Impersonation ist in 4.1 auf der Strecke nc35 gemessen (M4.8). Vor der ersten Nutzung hat jeder Lauf Schlüssel, Pfade und Aufräumkommando an der Quelle seiner Instanz gelesen (Zeilen `QUELLE`); keine Version weicht von der Erwartung ab, in keinem Lauf steht eine Zeile `QUELLE ABWEICHUNG`. Kein Abschnitt endete als ungemessen, jede Positivkontrolle hat gegriffen.

Jede Zelle zitiert die Protokollzeile bis zum ersten Trennstrich; die Gegenproben (Datenbankzeile mit `deleted_at`, sha256 vor und nach der Wiederherstellung) stehen in derselben Zeile der Rohdatei dahinter.

| Fassung of record | Papierkorb an, eigene Liste | Papierkorb an, geteilte Liste | Papierkorb aus, eigene Liste | Papierkorb aus, geteilte Liste | Vorab-Test | Frist und Einheit | Aufräumlauf | Rohdatei |
|---|---|---|---|---|---|---|---|---|
| 32.0.15 (`VERSION OF RECORD 32.0.15`) | `LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt` und `WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja` | `LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender`; der Eigentümer kann es auch: `WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja`; ohne Schreibrecht: `LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja` | `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft` | `FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden` | `FRIST AUFRAEUMEN standard=bleibt frist_1s=weg` | `raw/loeschen-32.txt` |
| 33.0.9 (`VERSION OF RECORD 33.0.9`) | `LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt` und `WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja` | `LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender`; der Eigentümer kann es auch: `WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja`; ohne Schreibrecht: `LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja` | `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft` | `FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden` | `FRIST AUFRAEUMEN standard=bleibt frist_1s=weg` | `raw/loeschen-33.txt` |
| 34.0.4 (`VERSION OF RECORD 34.0.4`) | `LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt` und `WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja` | `LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender`; der Eigentümer kann es auch: `WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja`; ohne Schreibrecht: `LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja` | `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft` | `FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden` | `FRIST AUFRAEUMEN standard=bleibt frist_1s=weg` | `raw/loeschen-34.txt` |
| 35.0.2 (`VERSION OF RECORD 35.0.2`) | `LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt` und `WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja` | `LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender`; der Eigentümer kann es auch: `WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja`; ohne Schreibrecht: `LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja` | `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich` | `VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft` | `FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden` | `FRIST AUFRAEUMEN standard=bleibt frist_1s=weg` | `raw/loeschen-35.txt` |

Was die Tabelle auf allen vier Versionen gleich zeigt:

- **Papierkorb an, eigene Liste (M4.9, W1):** `DELETE` mit `If-Match` antwortet 204, die Aufgabe steht in der Auflistung des Papierkorbs (`REPORT calendar-query` auf `trashbin/objects`) unter `<id>.ics`, die Datenbankzeile trägt `deleted_at`. Die Wiederherstellung (`MOVE` auf `trashbin/restore/file`) antwortet 201; danach steht die Aufgabe am alten Ort mit gleicher UID und gleichem sha256, `deleted_at` ist wieder leer. Positivkontrolle: das nicht gelöschte Nachbarobjekt steht nicht im Papierkorb und ist lesbar.
- **Papierkorb an, geteilte Liste (M4.10, W2):** löscht die Empfängerin mit Schreibrecht, steht die Aufgabe im Papierkorb beider Konten (`papierkorb_von=beide`). Wiederherstellen kann das löschende Konto, und an einem zweiten Objekt gemessen auch der Eigentümer. Die Empfängerin ohne Schreibrecht wird mit 404 abgelehnt, das Objekt ist unverändert.
- **Unteraufgabe (A21, Serverseite je Version):** nach dem Löschen der Elternaufgabe ist die Unteraufgabe unverändert vorhanden, zum Beispiel auf 35.0.2: `UNTERAUFGABE loeschen vorhanden=ja unveraendert=ja eltern_status=204 nutzer=alice auth=basic`.
- **Aufbewahrungsfrist (M4.13):** der Schlüssel `calendarRetentionObligation` der App `dav` ist im Auslieferungszustand nicht gesetzt; der Standard laut Quelle sind 2592000 Sekunden, also 30 Tage. Gemessen ist die Einheit so: mit dem Standard lässt `occ dav:retention:clean-up` ein gelöschtes Objekt stehen, mit dem Wert 1 ist es drei Sekunden später endgültig entfernt (`FRIST AUFRAEUMEN standard=bleibt frist_1s=weg`).

**Vorab-Test (M4.12, W4).** Sechs Kandidaten, die ein Konto selbst per DAV oder OCS stellen kann, je bei eingeschaltetem und bei abgeschaltetem Papierkorb gefragt; die Lesart stand vor der Messung fest. Die Werte von Nextcloud 35.0.2, die drei anderen Versionen zeigen dieselben:

| Kandidat | Papierkorb an | Papierkorb aus | Ergebnis |
|---|---|---|---|
| papierkorb-propfind | `VORABTEST papierkorb-propfind zustand=an wert=207 zeigt=an` | `VORABTEST papierkorb-propfind zustand=aus wert=207 zeigt=an` | zählt nicht: die Sammlung antwortet in beiden Zuständen 207 |
| frist-eigenschaft | `VORABTEST frist-eigenschaft zustand=an wert=2592000 zeigt=an` | `VORABTEST frist-eigenschaft zustand=aus wert=0 zeigt=aus` | zählt: die Eigenschaft nennt bei eingeschaltetem Papierkorb die Frist in Sekunden und bei abgeschaltetem 0 |
| frist-eigenschaft-home | `VORABTEST frist-eigenschaft-home zustand=an wert=fehlt zeigt=unklar` | `VORABTEST frist-eigenschaft-home zustand=aus wert=fehlt zeigt=unklar` | zählt nicht: am Kalender-Home gibt es die Eigenschaft nicht |
| home-kind-trashbin | `VORABTEST home-kind-trashbin zustand=an wert=ja zeigt=an` | `VORABTEST home-kind-trashbin zustand=aus wert=ja zeigt=an` | zählt nicht: die Sammlung ist in beiden Zuständen da |
| capabilities-dav | `VORABTEST capabilities-dav zustand=an wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_s` | `VORABTEST capabilities-dav zustand=aus wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_` | zählt nicht: die Capabilities nennen den Papierkorb nicht |
| dav-kopf | `VORABTEST dav-kopf zustand=an wert=ja zeigt=an` | `VORABTEST dav-kopf zustand=aus wert=ja zeigt=an` | zählt nicht: das Merkmal steht in beiden Zuständen im Antwortkopf |

Genau ein Kandidat unterscheidet die beiden Zustände in beiden Richtungen richtig, auf allen vier Versionen derselbe: ein `PROPFIND` mit `Depth: 0` auf `/remote.php/dav/calendars/<konto>/trashbin/` nach der Eigenschaft `{http://nextcloud.com/ns}trash-bin-retention-duration`. Die Positivkontrolle dazu ist das Verhalten, nicht der Schalter: bei "an" kam die Aufgabe zurück, bei "aus" war die Datenbankzeile weg (`KONTROLLE vorabtest zustand_am_verhalten_belegt=ja (an: wiederhergestellt=ja, aus: endgueltig geloescht=ja)`). Der zweite Kandidat anderer Art, die Existenz der Sammlung, taugt nicht: der Papierkorb bleibt als Sammlung sichtbar, auch wenn er abgeschaltet ist. Die Eigenschaft nennt zugleich die Frist: mit dem Wert 1 zeigt sie 1 (`VORABTEST frist-eigenschaft zustand=frist-1s wert=1 zeigt=an`), und ein so kurz gehaltener Papierkorb ist nach dem nächsten Aufräumlauf leer.

Der Schalter wurde je Lauf mit `occ config:app:set` gesetzt, mit `occ config:app:get` belegt und nach einem Neustart des Containers erneut gelesen, bevor gemessen wurde (Zeilen `SCHALTER`); auf der Strecke nc35 wurde er nie verändert.

### 4.4 Rohbefund bei abgeschaltetem Papierkorb

Dieser Unterabschnitt steht eigens da, weil die Entscheidungsregel der Lesart nach TMOD-07 folgt (Owner-Entscheid vom 11.11.2026, oben bei der Regel): im Aus-Zustand muss nicht "wiederherstellbar" herauskommen, der Vorab-Test muss den Aus-Zustand sicher erkennen. Der Rohbefund selbst ist auf allen vier Versionen derselbe: mit `calendarRetentionObligation` gleich 0 löscht ein `DELETE` endgültig.

- Nextcloud 32.0.15: nach dem `DELETE` (204) steht die Aufgabe in keinem Papierkorb, die Zeile in `calendarobjects` ist weg, eine Wiederherstellung ist nicht möglich. Eigene Liste: `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`; geteilte Liste: `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`.
- Nextcloud 33.0.9: nach dem `DELETE` (204) steht die Aufgabe in keinem Papierkorb, die Zeile in `calendarobjects` ist weg, eine Wiederherstellung ist nicht möglich. Eigene Liste: `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`; geteilte Liste: `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`.
- Nextcloud 34.0.4: nach dem `DELETE` (204) steht die Aufgabe in keinem Papierkorb, die Zeile in `calendarobjects` ist weg, eine Wiederherstellung ist nicht möglich. Eigene Liste: `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`; geteilte Liste: `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`.
- Nextcloud 35.0.2: nach dem `DELETE` (204) steht die Aufgabe in keinem Papierkorb, die Zeile in `calendarobjects` ist weg, eine Wiederherstellung ist nicht möglich. Eigene Liste: `LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`; geteilte Liste: `LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich`.

Nach der wörtlichen Lesart von E13 ("wiederherstellbar bleibt, auch mit abgeschaltetem Papierkorb") wäre das Ergebnis also "nicht wiederherstellbar". Nach der geltenden Lesart zählt, dass der Vorab-Test diesen Zustand vor dem Löschen anzeigt (W4), und das tut er auf allen vier Versionen mit dem Wert 0.

### 4.5 Ergebnis

Die Sammelzeilen der vier Läufe, darunter die beiden Zeilen, die der Block delete-verdict aus ihnen bildet (`delete_verdict()` über die Zeilen `LOESCHEN VERSION` der vier Rohdateien):

```
LOESCHEN VERSION 32.0.15 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
LOESCHEN VERSION 33.0.9 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
LOESCHEN VERSION 34.0.4 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
LOESCHEN VERSION 35.0.2 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
ERGEBNIS LOESCHEN (E13): wiederherstellbar
KONSEQUENZ: TMOD-07 ist planbar (Phase 33), mit den Auflagen aus den Messwerten: Vorab-Test vor dem Löschen, wer wiederherstellen kann, Aufbewahrungsfrist.
```

Auflagen für TMOD-07 aus den Messwerten:

- **Vorab-Test vor jedem Löschen:** `PROPFIND` mit `Depth: 0` auf die Papierkorb-Sammlung des Kontos nach `{http://nextcloud.com/ns}trash-bin-retention-duration`. Nur eine Zahl größer 0 heißt, dass der Papierkorb wirkt. Der Wert 0, eine fehlende Eigenschaft oder eine andere Antwort als 207 heißt ablehnen. Die Existenz der Sammlung, der Antwortkopf `DAV` und die Capabilities sagen nichts über den Zustand.
- **Frist nennen:** der Wert der Eigenschaft ist die Aufbewahrungsfrist in Sekunden, im Auslieferungszustand 2592000 (30 Tage). Die Antwort des Werkzeugs kann sie nennen. Ob das Werkzeug eine Mindestfrist verlangt, ist in Phase 33 zu entscheiden: gemessen ist, dass ein Papierkorb mit der Frist 1 als "an" erscheint und beim nächsten Aufräumlauf leer ist.
- **Wer wiederherstellen kann:** bei einer eigenen Liste das Konto selbst; bei einer geteilten Liste mit Schreibrecht das löschende Konto und der Eigentümer, die Aufgabe steht im Papierkorb beider.
- **Kein Schreibrecht:** das Löschen in einer nur lesbaren geteilten Liste lehnt der Server mit 404 ab, wie `PUT` (3.3) und `MOVE` (4.1).
- **ETag:** `DELETE` mit `If-Match` auf die gelesene ETag antwortet 204; mit einer veralteten ETag 412 bei unverändertem Objekt (gemessen auf nc35, 4.1).
- **Elternaufgaben:** der Server löscht eine Unteraufgabe nicht mit, sie bleibt mit einem Verweis auf die gelöschte Elternaufgabe zurück; die Tasks-App löscht sie mit einem eigenen Aufruf mit, und beide liegen dann im Papierkorb (4.2).
- **Nie senden:** die Quelle nennt eine Kopfzeile `X-NC-CalDAV-No-Trashbin`, die den Papierkorb für eine Anfrage umgeht (gelesen, nicht gemessen, Zeile `QUELLE` in 12.7). Der Connector darf sie nie setzen.

`.planning/REQUIREMENTS.md` wird in diesem Plan nicht geändert; die Übernahme des Ergebnisses in die Requirements und an den Owner-Checkpoint geschieht gesammelt in Plan 30-05.

## 5. Discovery und Objekte (MESS-03)

Offen, füllt Plan 30-04.

## 6. Kosten der Aufgabensuche (MESS-04)

Offen, füllt Plan 30-04.

## 7. Inventar der Gates und Zusagen (A17)

Erstellt am 2026-11-11 mit dem Block inventory des Messskripts, ohne Instanz. Die Zeilennummern gelten auf Commit `32b8df0` (voll: `32b8df00964e5f724ae3edc3de1796f3693159ef`); der Arbeitsbaum wich in den durchsuchten Pfaden nicht ab. Rohbeleg ist `raw/inventar.txt` mit jeder Fundstelle, Auszug in 12.5.

Zwei Suchen, die keinen Suchbegriff teilen:

- **Muster 1** sucht den Wortlaut der Zusage in Englisch, Deutsch und Französisch (create-only, never deleted, overwrite, destructive, move, rename, gelöscht, überschreiben, destruktiv, verschieben, jamais, supprimer, écraser, déplacer und ihre Stämme) in den drei READMEs, `docs/`, `appinfo/info.xml`, den Changelogs, `.planning/PROJECT.md`, `src/mcp_connector/server/` und im Destruktiv-Gate `tests/contract/test_no_destructive_calls.py`.
- **Muster 2** sucht die technische Seite: die Konstanten der Gates (`EXPECTED_PUT_CALLS`, `FORBIDDEN`, `CHUNK_ASSEMBLY_MOVE`, `CREATE_TOOLS`, `destructive_hint`, `idempotent_hint`, `MUST_REFUSE`, `FILE_WRITERS`, `PARAM_ALLOWLIST`) in `tests/` und `src/`, die Methodenliterale in `src/mcp_connector/nextcloud/clients/`, Testnamen mit create, destructive, overwrite oder readonly, und in den öffentlichen Texten aller drei Sprachen die Wörter der HTTP-Ebene (`PUT`, `DELETE`, `MOVE`, `If-Match`, Papierkorb), die von der Sprache nicht abhängen.

Ergebnis: `INVENTAR MUSTER 1 treffer=242 | MUSTER 2 treffer=191`; `INVENTAR SUMME treffer=416 gate=46 annotation=4 audit=10 kanarie=2 zusage-server=2 zusage-store=3 zusage-doku=47 ungeklaert=0 ausgeschlossen=302`. Die Positivkontrolle steht: `INVENTAR POSITIVKONTROLLE gefunden=6/6 stellen=['EXPECTED_PUT_CALLS', 'FORBIDDEN', 'README-Rechtetabelle', 'threat-model', 'Store-Text', 'Server-Instruktion'] fehlend=keine`. Die Gegenprobe hat getragen: `INVENTAR GEGENPROBE nur_muster_2_im_inventar=41 (Stellen, die Muster 1 nicht fand und die trotzdem im Inventar stehen)`.

Wie zugeordnet wurde: jede Fundstelle beider Muster wurde gelesen; die Zuordnung zu Klasse, berührenden Methoden und Phase steht als Regeltabelle im Skript (`INVENTORY_RULES`), die erste passende Regel entscheidet, und eine Fundstelle ohne Regel lässt den Block scheitern. Ein Treffer, der die Zusage nicht betrifft, ist nicht gelöscht, sondern mit Grund als ausgeschlossen geführt. "Berührt von" meint: `PUT` für den überschreibenden `PUT` (abhaken, wieder öffnen, ändern), `MOVE` für das Verschieben in eine andere Liste, `DELETE` für das bedingte Löschen. In der Tabelle ist der Wortlaut auf 160 Zeichen gekürzt, Backticks sind durch Apostrophe ersetzt und senkrechte Striche maskiert; der ungekürzte Wortlaut steht in der Rohdatei.

Zwei Dinge, die bei der Erstellung aufgefallen sind:

- Die Positivkontrolle des Plans verlangt, dass Muster 1 auch `EXPECTED_PUT_CALLS` und `FORBIDDEN` findet. Muster 1 sucht Wortlaut und kann eine Konstante nicht nennen. Als gefunden zählt deshalb ein Treffer von Muster 1 im Gate selbst, höchstens zwölf Zeilen von der Konstante entfernt: der Satz, der sagt, was die Konstante bewacht.
- Der erste Entwurf von Muster 1 fand die englische Zeile `README.md:42` ("No deleting") und die Zeilen zum Verschieben und Umbenennen nicht; Muster 2 fand die erste über das Wort `DELETE`. Muster 1 wurde daraufhin um die Stämme für löschen, verschieben und umbenennen und um "Read and create" erweitert, bevor ausgewertet wurde. Der zweite Satz der Server-Instruktion ("Read and create content ...") ist erst dadurch im Inventar.

### 7.1 Fundstellen, die ein ändernder Zugriff berührt

| Klasse | Datei:Zeile | Wortlaut | berührt von | abzuarbeiten in | Muster |
|--------|-------------|----------|-------------|-----------------|--------|
| gate | `tests/contract/test_no_destructive_calls.py:4` | never delete, overwrite or re-share anything (TOOL-09). Without a gate that sentence is a | PUT,MOVE,DELETE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:11` | its module docstring that it implements no DELETE, no MOVE, no COPY and no PROPPATCH. | MOVE,DELETE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:32` | # Destructive HTTP verbs and the one OCS route that changes who may see an object. Upper | MOVE,DELETE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:86` | FORBIDDEN: dict[str, str] = { | MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_no_destructive_calls.py:88` | "MOVE": "no tool may move or rename anything", | MOVE,DELETE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:139` | # The only MOVE in production is Nextcloud's internal chunk-assembly step. It carries | MOVE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:140` | # ''Overwrite: F'' and is therefore still create-only; user-facing move and rename tools | MOVE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:142` | CHUNK_ASSEMBLY_MOVE = "nextcloud/clients/dav.py" | MOVE | Phase 33 | 2 |
| gate | `tests/contract/test_no_destructive_calls.py:387` | destructive call is written as a string: ''client.request("DELETE", url)''. | MOVE,DELETE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:421` | for needle, why in FORBIDDEN.items(): | MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_no_destructive_calls.py:424` | if needle == "MOVE" and relative == CHUNK_ASSEMBLY_MOVE and text.strip() == '"MOVE",': | MOVE | Phase 33 | 1+2 |
| gate | `tests/contract/test_no_destructive_calls.py:440` | def test_the_production_code_contains_no_destructive_request() -> None: | MOVE,DELETE | Phase 33 | 1+2 |
| gate | `tests/contract/test_no_destructive_calls.py:447` | assert findings == [], "destructive call found:\n" + "\n".join(findings) | MOVE,DELETE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:450` | def test_file_updates_keep_create_and_compare_and_swap_puts_distinct() -> None: | PUT | Phase 33 | 2 |
| gate | `tests/contract/test_no_destructive_calls.py:451` | """A file update must stay compare-and-swap while file creation stays create-only.""" | PUT | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:470` | #: protocol writes into Nextcloud's temporary upload folder and its final MOVE carries | MOVE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:471` | #: ''Overwrite: F''; the init-progress push is the ExApp talking about itself to the | PUT | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:480` | EXPECTED_PUT_CALLS = 6 | PUT | Phase 33 | 2 |
| gate | `tests/contract/test_no_destructive_calls.py:506` | """Every PUT in ''tree'' that could overwrite without a precondition, plus the count. | PUT | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:560` | """No PUT anywhere in the production code may overwrite unconditionally.""" | PUT | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:571` | assert total == EXPECTED_PUT_CALLS, ( | PUT | Phase 33 | 2 |
| gate | `tests/contract/test_no_destructive_calls.py:573` | f"{EXPECTED_PUT_CALLS}; a new PUT is a review event, update the pin deliberately" | PUT | Phase 33 | 2 |
| gate | `tests/contract/test_no_destructive_calls.py:633` | def test_the_gate_would_notice_a_destructive_call_in_real_code() -> None: | MOVE,DELETE | Phase 33 | 1+2 |
| gate | `tests/contract/test_no_destructive_calls.py:642` | real module doubles as the counter proof for the MOVE exemption: dav.py carries the one | MOVE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:643` | exempt chunk-assembly MOVE and must still report nothing. | MOVE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:648` | assert "no DELETE, no MOVE, no COPY" not in docstring_text, ( | MOVE,DELETE | Phase 33 | 1 |
| gate | `tests/contract/test_no_destructive_calls.py:653` | "dav.py must be clean before the injected call can prove anything; its one MOVE is " | MOVE | Phase 33 | 1 |
| gate | `tests/contract/test_tool_classes.py:89` | async def test_readers_are_read_only_and_writers_are_not() -> None: | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_classes.py:95` | for name in tool_classes.FILE_WRITERS: | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_classes.py:105` | + len(tool_classes.FILE_WRITERS) | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_classes.py:111` | len(tool_classes.FILE_WRITERS), | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:73` | CREATE_TOOLS = { | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:472` | assert not (CREATE_TOOLS & {name for name in tools if name.startswith("mail")}), ( | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:749` | says so by comparing against the frozen ''CREATE_TOOLS'' rather than against a literal: | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:756` | assert CREATE_TOOLS < EXPECTED_TOOLS, "every write tool must be part of the curated set" | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:766` | assert annotations.destructive_hint is True | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:767` | assert annotations.idempotent_hint is False | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:768` | elif name in CREATE_TOOLS: | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:770` | assert annotations.destructive_hint is False, ( | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:773` | assert annotations.idempotent_hint is False, ( | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/test_tool_surface.py:842` | if name in CREATE_TOOLS | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/tool_classes.py:69` | FILE_WRITERS: dict[str, str] = { | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/tool_classes.py:152` | known = FILE_READERS.keys() \| FILE_WRITERS.keys() \| UNAFFECTED.keys() | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/tool_classes.py:177` | "FILE_WRITERS": FILE_WRITERS, | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/tool_classes.py:195` | affected = FILE_READERS.keys() \| FILE_WRITERS.keys() | PUT,MOVE,DELETE | Phase 33 | 2 |
| gate | `tests/contract/tool_classes.py:200` | for name in sorted(FILE_WRITERS.keys() - paired): | PUT,MOVE,DELETE | Phase 33 | 2 |
| annotation | `src/mcp_connector/server/__init__.py:79` | destructive_hint=False, | PUT,MOVE,DELETE | Phase 33 | 1+2 |
| annotation | `src/mcp_connector/server/__init__.py:80` | idempotent_hint=False, | PUT,MOVE,DELETE | Phase 33 | 2 |
| annotation | `src/mcp_connector/server/__init__.py:86` | destructive_hint=True, | PUT,MOVE,DELETE | Phase 33 | 1+2 |
| annotation | `src/mcp_connector/server/__init__.py:87` | idempotent_hint=False, | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `src/mcp_connector/audit/allowlist.py:45` | PARAM_ALLOWLIST: Mapping[str, frozenset[str]] = { | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `src/mcp_connector/audit/record.py:37` | from .allowlist import PARAM_ALLOWLIST | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `src/mcp_connector/audit/record.py:105` | return sorted(set(arguments.keys()) & PARAM_ALLOWLIST.get(tool, frozenset())) | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `tests/contract/test_audit_surface.py:27` | from mcp_connector.audit.allowlist import FORBIDDEN_PARAMS, PARAM_ALLOWLIST | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `tests/contract/test_audit_surface.py:56` | f"{name} has no allowlist entry" for name in sorted(surface) if name not in PARAM_ALLOWLIST | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `tests/contract/test_audit_surface.py:60` | for name in sorted(PARAM_ALLOWLIST) | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `tests/contract/test_audit_surface.py:76` | for name in sorted(PARAM_ALLOWLIST): | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `tests/contract/test_audit_surface.py:77` | for parameter in sorted(PARAM_ALLOWLIST[name] - surface.get(name, set())): | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `tests/contract/test_audit_surface.py:90` | for name in sorted(PARAM_ALLOWLIST) | PUT,MOVE,DELETE | Phase 33 | 2 |
| audit | `tests/contract/test_audit_surface.py:91` | for parameter in sorted(PARAM_ALLOWLIST[name] & FORBIDDEN_PARAMS) | PUT,MOVE,DELETE | Phase 33 | 2 |
| kanarie | `tests/integration/test_canary.py:89` | MUST_REFUSE = ("files_upload", "notes_create", "talk_send") | PUT,MOVE,DELETE | Phase 33 | 2 |
| kanarie | `tests/integration/test_canary.py:308` | if tool in MUST_REFUSE: | PUT,MOVE,DELETE | Phase 33 | 2 |
| zusage-server | `src/mcp_connector/server/__init__.py:62` | "Read and create content in the user's own Nextcloud. " | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-server | `src/mcp_connector/server/__init__.py:63` | "Files are never deleted, moved, renamed or unconditionally overwritten." | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-store | `appinfo/info.xml:69` | - Nothing destructive: no delete, no move, no share; nothing in the background, no telemetry | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-store | `appinfo/info.xml:89` | - Nichts Destruktives: kein Löschen, kein Verschieben, kein Teilen; nichts im Hintergrund, keine Telemetrie | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-store | `appinfo/info.xml:109` | - Rien de destructif : pas de suppression, pas de déplacement, pas de partage ; rien en arrière-plan, pas de télémétrie | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `.planning/PROJECT.md:24` | **Schreibzusage:** Mit Phase 33 bekommt die Zusage "create-only, keine destruktiven Writes" erstmals eine eng begrenzte Ausnahme für eine einzelne Aufgabe (ände | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `.planning/PROJECT.md:70` | - ✓ Risikoarme Writes, destruktive Ops konstruktionsbedingt ausgeschlossen , v1.0 (AST-Grep-Gate, Zwei-Konten-Negativbeweis) | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `.planning/PROJECT.md:118` | - Destruktive Operationen (Löschen, Überschreiben, Teilen/Freigaben ändern) - Sicherheitsversprechen der v1: "kann konstruktionsbedingt nichts zerstören" | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `.planning/PROJECT.md:150` | - **Security**: Der MCP darf nie mehr sehen als der angemeldete Nutzer (Berechtigungs-Durchgriff); keine destruktiven Writes in v1 | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `.planning/PROJECT.md:162` | \| Risikoarme Writes, destruktive Ops ausgeschlossen \| "Kann nichts zerstören" ist Verkaufsargument, kein Mangel \| ✓ Good , als Gate implementiert (AST-Grep), | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.de.md:48` | - Nichts löschen: kein Tool setzt ein DELETE auf Dateien, Termine, Notizen, Karten oder | DELETE | Phase 34 | 1+2 |
| zusage-doku | `README.de.md:50` | - Kein bedingungsloses Überschreiben: Schreiben legt nur neu an, und 'files_upload' lehnt einen | PUT | Phase 34 | 1 |
| zusage-doku | `README.de.md:56` | - Kein Verschieben, kein Umbenennen, keine Änderung von Freigaben oder Berechtigungen | MOVE | Phase 34 | 1 |
| zusage-doku | `README.de.md:64` | [tests/contract/test_no_destructive_calls.py](tests/contract/test_no_destructive_calls.py). | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.de.md:68` | **read** heißt, das Tool liest nur, **create-only** heißt, es kann neue Objekte anlegen, aber | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.fr.md:49` | - Rien supprimer : aucun outil n'émet de DELETE sur des fichiers, événements, notes, cartes | DELETE | Phase 34 | 1+2 |
| zusage-doku | `README.fr.md:51` | - Pas d’écrasement inconditionnel : les écritures sont en création seule, et 'files_upload' | PUT | Phase 34 | 1 |
| zusage-doku | `README.fr.md:57` | - Aucun déplacement, aucun renommage, aucune modification de partage ni de permission | MOVE | Phase 34 | 1 |
| zusage-doku | `README.fr.md:67` | [tests/contract/test_no_destructive_calls.py](tests/contract/test_no_destructive_calls.py). | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.fr.md:71` | **read** signifie que l'outil ne fait que lire, **create-only** signifie qu'il peut créer de | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.fr.md:72` | nouveaux objets mais ne modifie ni ne supprime jamais ceux qui existent. Le tableau n'est pas | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.md:42` | - No deleting: no tool issues a DELETE against files, events, notes, cards or contacts | DELETE | Phase 34 | 1+2 |
| zusage-doku | `README.md:43` | - No unconditional overwriting: 'files_upload' refuses existing paths. If the admin enables | PUT | Phase 34 | 1 |
| zusage-doku | `README.md:47` | - No user-visible moving or renaming, no share changes and no permission changes; binary | MOVE | Phase 34 | 1 |
| zusage-doku | `README.md:55` | modules and fails on the first destructive call, | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.md:56` | [tests/contract/test_no_destructive_calls.py](tests/contract/test_no_destructive_calls.py). | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `README.md:60` | **read** means the tool only reads, **create-only** means it can create new objects but never | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/client-setup.md:873` | Remember what the tools cannot do. Nothing here deletes, moves or re-shares | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/conference-demo.md:63` | the tool list has no delete and no move, and the upload tool refuses a path that exists. | MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/conference-demo.md:271` | and that run leaves a message behind. Read the names out: there is no delete, no move and no | MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/conference-talk.md:105` | - Sixteen tools in the released 0.1.2, twenty in the development tree. No delete, no move, no | MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/conference-talk.md:112` | whichever version you install. There is no delete, there is no move, and there is no share. | MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/conference-talk.md:174` | \| 6 \| Sixteen tools in 0.1.2 and twenty in the development tree, no delete, no move, no share \| 'scripts/check_tool_budget.py' and the tool table contract te | MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/conference-talk.md:208` | set deliberately cannot do: there is no delete, no move and no share, and the assistant sees | MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/exapp-install.md:240` | data: {"jsonrpc":"2.0","id":1,"result":{"capabilities":{...},"instructions":"Read and create content in the user's own Nextcloud. This server can never delete,  | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/faq.md:151` | One honest remainder stays with the switch off: the create-only writes (a file, a | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.de.md:72` | - kein Werkzeug löscht, überschreibt, verschiebt, benennt um oder ändert | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.de.md:73` | Freigaben oder Rechte; Schreiben ist nur Anlegen, und ein Contract-Test | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.de.md:74` | fällt beim ersten destruktiven Aufruf durch, | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.fr.md:72` | - aucun outil ne supprime, n'écrase, ne déplace, ne renomme ni ne modifie | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.fr.md:74` | contrat échoue au premier appel destructif, | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.md:68` | - no tool deletes, moves, renames or changes shares or | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.md:69` | permissions; 'files_upload' remains create-only. When | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/hardening.md:72` | require conditional headers on file PUT routes, | PUT,MOVE,DELETE | Phase 34 | 2 |
| zusage-doku | `docs/n8n-setup.md:40` | \| Deletes \| Node can delete files \| No delete tool exists at all \| | DELETE | Phase 34 | 1 |
| zusage-doku | `docs/privacy.md:171` | - The create-only writes ('files_upload', 'deck_create_card', 'tables_create_row') | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/privacy.md:187` | - No tool deletes, moves or re-shares files. Uploads remain create-only. | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/privacy.md:208` | 'NC_MCP_FILES_UPDATE' closes the replacement path, but not the create-only path. | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/threat-model.md:148` | - No tool deletes, moves, renames, re-shares or changes permissions. | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/threat-model.md:149` | 'files_upload' remains create-only. When 'NC_MCP_FILES_UPDATE' is | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/threat-model.md:162` | for deleting, moving, renaming or re-sharing files, optional 'files_update' | PUT,MOVE,DELETE | Phase 34 | 1 |
| zusage-doku | `docs/threat-model.md:173` | can still misuse read tools and create-only writes within the user's | PUT,MOVE,DELETE | Phase 34 | 1 |

Die Server-Instruktion steht unter `src/`, ist hier aber Phase 34 zugeordnet, weil DOC-05 sie zu den Texten der Zusage zählt; ändert Phase 33 den Text mit, ist das genauso richtig. Die Vortragsunterlagen (`docs/conference-*.md`) beschreiben den Stand eines früheren Release; sie stehen im Inventar, weil der Satz "no delete, no move" dort öffentlich steht, und ob sie nachgezogen werden, entscheidet der Owner.

### 7.2 Ausgeschlossene Treffer

Jeder ausgeschlossene Treffer steht mit Datei, Zeile und Wortlaut in `raw/inventar.txt`. Nach Grund:

| Grund | Anzahl |
|-------|--------|
| Aussage ueber ein bestehendes Werkzeug, das unveraendert bleibt | 29 |
| Datei-Upload oder Route der Einstellungsseite, kein Aufgaben-Zugriff | 6 |
| Historie eines frueheren Release, wird nicht umgeschrieben | 14 |
| Mail oder Datei-Upload, kein Aufgaben-Zugriff | 4 |
| Mail, Deinstallation, Audit-Protokoll oder anderes Thema, kein Aufgaben-Zugriff | 22 |
| Messbericht oder Anleitung zu einem anderen Thema, keine Zusage ueber Werkzeuge | 87 |
| Nadeln und Ausnahmen fuer Talk, Mail, Tables, Tags oder den Login-Flow, kein Aufgaben-Zugriff | 21 |
| Tabellenzeile eines bestehenden Werkzeugs; die Tabelle bekommt neue Zeilen, diese bleibt | 18 |
| Test eines bestehenden Werkzeugs oder eines anderen Themas, vom Aufgaben-Zugriff nicht beruehrt | 71 |
| anderes Thema, keine Aussage ueber schreibende Werkzeuge | 6 |
| beschreibt files_update, das unveraendert bleibt | 2 |
| beschreibt schon den geplanten Stand von v1.8 oder ist Verfahrenstext | 15 |
| bestehender Aufruf, den EXPECTED_PUT_CALLS zaehlt oder eine eigene Nadel haelt; selbst keine Zusage | 6 |
| die Ausnahme CHUNK_ASSEMBLY_MOVE des Datei-Uploads, bleibt | 1 |

### 7.3 Präzedenz für E15: die Kette von NC_MCP_FILES_UPDATE

Als Maß für den Aufwand eines eigenen Schalters, ohne Empfehlung (die steht in Plan 30-05). Gesucht wurden `NC_MCP_FILES_UPDATE`, `files_update_enabled` und `ENV_FILES_UPDATE`:

| Datei:Zeile | Wortlaut |
|-------------|----------|
| `src/mcp_connector/config.py:51` | ENV_FILES_UPDATE = "NC_MCP_FILES_UPDATE" |
| `src/mcp_connector/config.py:716` | def files_update_enabled(env: Mapping[str, str] \| None = None) -> bool: |
| `src/mcp_connector/config.py:723` | value = (source.get(ENV_FILES_UPDATE) or "").strip().lower() |
| `src/mcp_connector/config.py:732` | ENV_FILES_UPDATE, |
| `src/mcp_connector/entry_exapp.py:58` | # tool, and ''files_update'' registers only when ''config.files_update_enabled'' answers |
| `src/mcp_connector/entry_exapp.py:669` | if config.ENV_FILES_UPDATE in resolved: |
| `src/mcp_connector/entry_exapp.py:670` | os.environ[config.ENV_FILES_UPDATE] = resolved[config.ENV_FILES_UPDATE] |
| `src/mcp_connector/exapp/config_values.py:139` | "files_update": config.ENV_FILES_UPDATE, |
| `src/mcp_connector/exapp/ui/strings.py:802` | #: The form half of ''NC_MCP_FILES_UPDATE''. This is an opt-in write capability: an update |
| `src/mcp_connector/server/__init__.py:67` | if config.files_update_enabled() |
| `src/mcp_connector/server/reg_files.py:249` | if config.files_update_enabled(): |
| `appinfo/info.xml:566` | <name>NC_MCP_FILES_UPDATE</name> |

Dazu Tests in sieben Dateien: `tests/contract/test_tool_surface.py` (2), `tests/unit/test_config.py` (13), `tests/unit/test_exapp_config_values.py` (1), `tests/unit/test_exapp_entry.py` (12), `tests/unit/test_exapp_env_setup.py` (1), `tests/unit/test_exapp_files_update_switch.py` (4), `tests/unit/test_exapp_lifecycle.py` (5). `E15-KETTE SUMME quelltext=12 testdateien=7 testtreffer=38 oeffentliche_texte=15 dateien_oeffentlich=['CHANGELOG.md', 'RE`. Nicht erfasst ist, was den Schalter nur über den Schlüssel `files_update` anspricht, etwa das Formular in `src/mcp_connector/exapp/admin_settings.py`; die Suche nach den drei Namen findet es nicht.

### 7.4 Was das Inventar nicht ist

Es nennt die Stellen, an denen die Zusage "create-only, nichts Destruktives" steht oder bewacht wird. Es nennt nicht, was jedes neue Werkzeug ohnehin berührt, ob ändernd oder nicht: die Werkzeugzahl, das Budget (`scripts/check_tool_budget.py`), die Werkzeugtabellen der READMEs und die Changelogs. Vollständig heißt hier: beide Muster liefern auf dem genannten Commit keine Stelle, die nicht im Inventar oder mit Grund unter den Ausgeschlossenen steht. Eine Zusage in einem Wortlaut, den keines der beiden Muster trifft, findet es nicht.

## 8. Annahmen A1 bis A19 und A21

Offen, füllt Plan 30-05; die Pläne davor tragen ihre Annahmen in den eigenen Abschnitten.

## 9. Abbruchkriterien und Übergabe an die Phasen 31 bis 33

Offen, füllt Plan 30-05.

## 10. Owner-Entscheid E15

Offen, füllt Plan 30-05.

## 11. Was ungemessen blieb

Jeder Plan trägt hier seine Ungemessen-Zeilen mit Grund ein. Stand nach Plan 30-01 (2026-11-11):

| Punkt | Stand | Grund |
|-------|-------|-------|
| `MKCOL` unter Impersonation auf Nextcloud 32, 33 und 34 | ungemessen | Auf den Wegwerf-Instanzen dieser Versionen gibt es keine ExApp-Registrierung; Impersonation ist nur auf der vorhandenen Strecke mit 35.0.0 messbar. Gemessen ist damit eine Version von vier des Store-Fensters |
| Statusmatrix auf Nextcloud 32, 33 und 34 mit App-Passwort | ungemessen | Plan 30-01 misst nur die Strecke nc35; die Versionsbreite gehört zu den Plänen 30-03 und 30-04, die andere Fragen stellen |
| Gruppenordner und externer Speicher auf anderen Versionen, auf PostgreSQL oder MySQL | ungemessen | eine Instanz, 35.0.0 mit SQLite, `groupfolders` 23.0.1 |
| Produktionsweg über ein Werkzeug der App | ungemessen | Das registrierte ExApp-Image ist 0.3.2 und kennt kein Werkzeug zum Ordner-Anlegen; gemessen ist nur ein `MKCOL` aus dem Container mit dessen Secret (Abschnitt 1.2). Den Weg über das Werkzeug belegt Phase 31 |
| Kontingent knapp, aber nicht erschöpft | ungemessen | gemessen ist nur der Zustand, in dem das Konto mehr belegt als das Kontingent erlaubt (507); ob ein leerer Ordner bei knappem Rest angelegt wird, ist offen |
| Kontingent eines Gruppenordners | ungemessen | nicht Teil des Plans; die beiden Messordner hatten kein Kontingent |
| ACL-Regeln gegen Gruppen oder Teams, geerbte Regeln, Vorgabe ohne Rechte | ungemessen | gemessen ist eine Regel gegen ein einzelnes Konto auf einem Unterordner |
| Externe Speicher anderer Art (SMB, S3, SFTP, WebDAV) | ungemessen | hergestellt wurde nur ein lokaler Speicher; ob ein entfernter nur lesbarer Speicher ebenfalls 403 antwortet, ist Annahme |
| Serverseitige Verschlüsselung, LDAP- und SSO-Konten | ungemessen | in der Testinstanz nicht vorhanden; wie in `docs/spike-dav.md` benannt |
| Unzulässige Namen über die drei gemessenen hinaus | ungemessen | gemessen sind `.htaccess`, ein Backslash und 300 Zeichen; die übrigen Regeln der Namensprüfung (weitere reservierte Namen, verbotene Zeichen und Endungen) sind gelesen, nicht gemessen |

Ergänzt durch Plan 30-02 (2026-11-11):

| Punkt | Stand | Grund |
|-------|-------|-------|
| `PUT` mit `If-Match` und Erhalt fremder Eigenschaften auf Nextcloud 32, 33 und 34, auf PostgreSQL oder MySQL | ungemessen | gemessen ist eine Instanz, 35.0.0 mit SQLite; Impersonation gibt es nur auf dieser Strecke |
| ETag im Antwortkopf, wenn der Server den Text beim Speichern verändert | ungemessen | in jeder gemessenen Zeile speicherte der Server wörtlich, der Fall trat nicht ein; ein absichtlich fehlerhaftes Objekt, das der Server repariert, war nicht Teil des Plans |
| Nur lesbare Liste aus einer Freigabe an eine Gruppe oder ein Team, öffentlicher Link, Delegation | ungemessen | hergestellt wurde eine Freigabe an ein einzelnes Konto über den DAV-Weg der Kalender-App |
| Erkennen des fehlenden Schreibrechts vor dem PUT | ungemessen in diesem Plan | gemessen ist nur die Antwort auf den PUT (404); die Privilegien der Sammlung in der Discovery gehören zu MESS-03 in Plan 30-04 |
| Wiederkehrende Aufgabe mit `RECURRENCE-ID`-Ausnahmen, Abhaken einer einzelnen Wiederholung | ungemessen | gemessen ist der PUT am Master einer täglichen Serie ohne Ausnahmen |
| Unteraufgaben in einer anderen Liste als die Elternaufgabe, mehrstufige Unteraufgaben | ungemessen | gemessen ist eine Unteraufgabe in derselben Liste |
| Felder, die die Tasks-App beim Abhaken einer Elternaufgabe in die Elternaufgabe schreibt | ungemessen | der `PUT` der App auf die Elternaufgabe scheiterte am 2026-11-11 mit 500 (`database is locked`, 12.4); gesichert ist nur, dass sie ihn gesendet hat. Nicht wiederholt, weil nichts nachgestellt wird |
| Zwischenstand von `s30 wieder-oeffnen` nach dem Abhaken | ungemessen | gesichert sind Stand a und Stand b, nicht der Stand dazwischen |
| Ob die Tasks-App für eine Wiederholung ein Datum verlangt | ungemessen | in der Sitzung wurde das Fälligkeitsdatum gesetzt, bevor die Wiederholung eingestellt wurde |
| Wiederkehrende Aufgabe mit Enddatum, mit Zähler oder mit anderem Rhythmus in der App | ungemessen | gemessen ist eine tägliche Wiederholung ohne Ende, einmal abgehakt |
| Tasks-App in anderen Fassungen als 0.18.1, andere Clients (Thunderbird, DAVx5, Apple) | ungemessen | eine Fassung der App in einem Browser |
| Wortlaut der Fehler in der Konsole des Browsers | ungemessen | die Hauptsitzung hat die Zahl notiert (vier in Runde A, einer in Runde B), nicht den Text; die beiden 500 stehen im Zugriffsprotokoll |
| Zusagen in einem Wortlaut, den keines der beiden Suchmuster trifft | ungemessen | Grenze des Inventars, siehe 7.4 |

Ergänzt durch Plan 30-03 (2026-11-11):

| Punkt | Stand | Grund |
|-------|-------|-------|
| `MOVE` und `DELETE` unter Impersonation auf Nextcloud 32, 33 und 34 | ungemessen | Impersonation gibt es nur auf der Strecke nc35 (35.0.0); die Wegwerf-Instanzen haben keine ExApp. Auf 32 bis 35 ist das Löschen mit App-Passwort gemessen, auf nc35 verhielten sich beide Anmeldewege beim `MOVE` gleich |
| `DELETE` mit veralteter ETag auf Nextcloud 32, 33 und 34 | ungemessen | gemessen nur auf nc35 (412); die Löschmatrix löscht immer mit der gelesenen ETag |
| Verschieben und Löschen auf PostgreSQL oder MySQL | ungemessen | alle Instanzen dieses Plans laufen mit SQLite |
| Zustand des Papierkorbs unmittelbar nach `occ config:app:set`, ohne Neustart des Containers | ungemessen | jede Messung liegt nach einem Neustart; ob Vorab-Test und Löschverhalten in der Zwischenzeit auseinanderlaufen können, ist offen. Beide lesen laut Quelle denselben Wert in derselben Anfrage (gelesen) |
| Negativer Wert des Schalters, Kopfzeile `X-NC-CalDAV-No-Trashbin` | ungemessen | nur gelesen: ein negativer Wert ergibt laut Quelle die Frist 0 in der Eigenschaft, schaltet den Papierkorb aber nicht ab (der Vorab-Test lehnt dann ab, obwohl der Papierkorb wirkt); die Kopfzeile umgeht den Papierkorb je Anfrage |
| Hintergrundjob der Aufbewahrung | ungemessen | gemessen ist `occ dav:retention:clean-up`; dass der zeitgesteuerte Job denselben Dienst ruft, ist gelesen |
| Wiederherstellen, wenn am alten Ort inzwischen ein Objekt gleichen Namens liegt | ungemessen | laut Quelle lehnt der Server das ab (gelesen) |
| Wiederherstellen in einer Oberfläche (Kalender-App, Tasks-App) | ungemessen | gemessen ist der DAV-Weg; ob und wo ein Nutzer eine gelöschte Aufgabe in der Oberfläche zurückholt, war nicht Teil des Plans |
| Löschen in einem Kalender mit `VEVENT` und `VTODO` (etwa `personal`) | ungemessen | gemessen sind Listen mit dem Komponenten-Set genau `VTODO` |
| Geteilte Liste aus einer Freigabe an eine Gruppe oder ein Team | ungemessen | hergestellt wurde eine Freigabe an ein einzelnes Konto |
| `MOVE` aus einem Deck-Kalender heraus | ungemessen | gemessen ist der Deck-Kalender nur als Ziel (403); das Board war leer |
| `MOVE` mit `Overwrite: T`, `MOVE` einer wiederkehrenden Aufgabe, `MOVE` in die Liste eines anderen Kontos ohne Freigabe | ungemessen | nicht Teil des Plans; gemessen sind `Overwrite: F` und der Aufruf ohne Kopfzeile |
| Belegtes Ziel ohne `Overwrite` bei abgeschaltetem Papierkorb | ungemessen | auf nc35 wird der Schalter nie verändert; dort lag das verdrängte Objekt im Papierkorb. Im Aus-Zustand wäre es nach 4.4 endgültig weg (abgeleitet, nicht gemessen) |
| Unteraufgaben über mehrere Ebenen, Unteraufgabe in einer anderen Liste als die Elternaufgabe | ungemessen | gemessen ist eine Unteraufgabe in derselben Liste |
| Mitnehmen der Unteraufgaben durch den Connector (Reihenfolge, Teilfehler) | ungemessen | gemessen ist, was Server und Tasks-App tun; der Connector hat noch kein Werkzeug dafür |

Zum Rückbau gehört eine Grenze, die keine Messlücke ist, aber benannt sein muss: `occ app:remove groupfolders` nimmt den Code der App weg, nicht ihre Tabellen in der Datenbank, und auch `files_external` behält seine Tabellen nach dem Ausschalten. Die Baseline (Apps, Konten, Gruppen, Dateien, Kalender) ist nach dem Lauf in allen zwölf Feldern gleich; die leeren Tabellen beider Apps bleiben in der Instanz nc35 zurück.

Drei Vorgänge am Rand der Messung, damit der Rückbau nachvollziehbar bleibt:

- Der Rückbau des Gruppenordner-Laufs hat die beiden Gruppenordner zunächst nicht gelöscht (Werkzeugfehler: das Feld heißt in der JSON-Ausgabe `mountPoint`, das Skript suchte `mount_point`). Die App war danach entfernt, die Ordner standen noch in der Datenbank. Der Block `nachlauf` hat die App erneut installiert, beide Ordner mit `occ groupfolders:delete` gelöscht und die App wieder entfernt; das steht als zweiter Lauf in `raw/nc35-gruppenordner.txt`.
- Gemessen und im Rückbau berücksichtigt: eine einmal eingeschaltete App behält nach `occ app:disable` und sogar nach `occ app:remove` drei Konfigurationswerte (`installed_version`, `enabled`, `types`), und `occ app:list` zeigt sie dann mit dem Zusatz "installed". Der Rückbau löscht diese drei Werte für die Apps, die vor dem Lauf nie eingeschaltet waren.
- Vor dem Gruppenordner-Lauf wurden `groupfolders` und `files_external` einmal von Hand eingeschaltet, um die Hilfetexte der Kommandos zu lesen, nach denen der Block gebaut ist, und wieder zurückgenommen (App entfernt, die drei Konfigurationswerte gelöscht). Dabei ist kein Messwert entstanden; der gemessene Lauf begann mit `installiert_vorher=nein`.

## 12. Rohausgaben

Jede in diesem Abschnitt in Backticks oder in einem Codeblock zitierte Protokollzeile steht wörtlich in einer Rohdatei des Phasenordners (Unterordner raw); das Messskript prüft das im Block secret-scan. Deshalb steht in diesem Abschnitt nichts anderes in Backticks als Zitate aus den Rohdateien.

### 12.1 raw/nc35-mkcol.txt

Lauf vom 2026-11-11, Blöcke nc35-up, controls und mkcol in einem Aufruf. Die Messzeilen in der Reihenfolge des Protokolls:

```
VERSION OF RECORD 35.0.0
dbtype: sqlite3
APP app_api version=35.0.0 (occ app:list)
  mcp_connector (MCP Connector): 0.3.2 [enabled]
EXAPP-CONTAINER laeuft=ja
2026-11-11T11:55:39Z | controls | a: GET /ocs/v2.php/cloud/user (AppAPI as spike30a) | HTTP 200 | id=spike30a erwartet=spike30a gleich=ja
2026-11-11T11:55:39Z | controls | b: GET /ocs/v2.php/cloud/user (AppAPI as spike30a, wrong APP_SECRET) | HTTP 401 | abgelehnt=ja
KONTROLLE c: exapp_impersonation.log, GET-Zeilen von spike30a seit 2026-11-11T11:55:37Z: 1
2026-11-11T11:55:43Z | SETUP PUT /spike30/setup.txt mit X-NC-WebDAV-Auto-Mkcol nutzer=spike30a auth=basic status=201 basisordner_vorhanden=ja
2026-11-11T11:55:43Z | KONTROLLE vorher PROPFIND Depth 0 /spike30/frei-115543 auth=appapi nutzer=spike30a status=404 erwartet=404
2026-11-11T11:55:45Z | MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201 |
ABBRUCHKRITERIUM MESS-01 ausgeloest=nein status=201
DATEISYSTEM frei vorhanden=ja pfad=/var/www/html/data/spike30a/files/spike30/frei-115543
2026-11-11T11:55:45Z | KONTROLLE nachher PROPFIND Depth 0 /spike30/frei-115543 auth=appapi nutzer=spike30a status=207
KONTROLLE exapp_impersonation.log, MKCOL-Zeilen von spike30a seit 2026-11-11T11:55:43Z: 1
  {"reqId":"pgrDEsSFpyKVk5r8XyzE","level":2,"time":"2026-11-11T11:55:45+00:00","remoteAddr":"172.30.42.128","user":"spike30a","app":"mcp_connector","method":"MKCOL","url":"/remote.php/dav/files/spike30a/spike30/frei-115543","scriptName":"/remote.php","message":"impersonation request","userAgent":"python-httpx/0.28.1","version":"35.0.0.10","data":{"app":"mcp_connector"}}
2026-11-11T11:55:45Z | GEGENPROBE falsches-secret MKCOL /spike30/frei-115543-falsches-secret nutzer=spike30a status=401 angelegt=nein | Sabre\DAV\Exception\NotAuthenticated No public access to this resource., AppAPIAuth has not passed, This request is not for a federated calendar, No 'Authorization: Basic' header found. Either the client didn't send one, or the server is misconfigured, No 'Authorization: Bearer' header found. Either
2026-11-11T11:55:46Z | GEGENPROBE fremdes-home MKCOL /remote.php/dav/files/spike30b/spike30-fremd nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden Permission denied to create directory
2026-11-11T11:55:46Z | PRODUKTIONSWEG MKCOL status=201 angelegt=ja nutzer=spike30a pfad=/spike30/frei-115543-produktionsweg (aus nc_app_mcp_connector gegen http://caddy)
2026-11-11T11:55:47Z | MKCOL ordner-vorhanden auth=appapi status=405 angelegt=nein erwartet=405 | Sabre\DAV\Exception\MethodNotAllowed The resource you tried to create already exists
2026-11-11T11:55:47Z | MKCOL datei-vorhanden auth=appapi status=405 angelegt=nein erwartet=405 | Sabre\DAV\Exception\MethodNotAllowed The resource you tried to create already exists
2026-11-11T11:55:47Z | MKCOL eltern-fehlt auth=appapi status=409 angelegt=nein erwartet=409 | Sabre\DAV\Exception\Conflict Parent node does not exist
2026-11-11T11:55:47Z | MKCOL eltern-ist-datei auth=appapi status=409 angelegt=nein erwartet=409 | Sabre\DAV\Exception\Conflict Parent node is not a collection
2026-11-11T11:55:48Z | MKCOL name-htaccess auth=appapi status=400 angelegt=nein erwartet=400 | OCA\DAV\Connector\Sabre\Exception\InvalidPath Filename is a reserved word
2026-11-11T11:55:48Z | MKCOL name-backslash auth=appapi status=400 angelegt=nein erwartet=400 | OCA\DAV\Connector\Sabre\Exception\InvalidPath "\" is not allowed inside a file or folder name.
2026-11-11T11:55:48Z | MKCOL name-ueberlang auth=appapi status=400 angelegt=nein erwartet=400 | OCA\DAV\Connector\Sabre\Exception\InvalidPath Filename is too long
2026-11-11T11:55:48Z | MKCOL frei auth=basic status=201 angelegt=ja erwartet=201 |
2026-11-11T11:55:49Z | MKCOL ordner-vorhanden auth=basic status=405 angelegt=nein erwartet=405 | Sabre\DAV\Exception\MethodNotAllowed The resource you tried to create already exists
2026-11-11T11:55:49Z | MKCOL datei-vorhanden auth=basic status=405 angelegt=nein erwartet=405 | Sabre\DAV\Exception\MethodNotAllowed The resource you tried to create already exists
2026-11-11T11:55:49Z | MKCOL eltern-fehlt auth=basic status=409 angelegt=nein erwartet=409 | Sabre\DAV\Exception\Conflict Parent node does not exist
2026-11-11T11:55:50Z | MKCOL eltern-ist-datei auth=basic status=409 angelegt=nein erwartet=409 | Sabre\DAV\Exception\Conflict Parent node is not a collection
2026-11-11T11:55:50Z | MKCOL name-htaccess auth=basic status=400 angelegt=nein erwartet=400 | OCA\DAV\Connector\Sabre\Exception\InvalidPath Filename is a reserved word
2026-11-11T11:55:50Z | MKCOL name-backslash auth=basic status=400 angelegt=nein erwartet=400 | OCA\DAV\Connector\Sabre\Exception\InvalidPath "\" is not allowed inside a file or folder name.
2026-11-11T11:55:50Z | MKCOL name-ueberlang auth=basic status=400 angelegt=nein erwartet=400 | OCA\DAV\Connector\Sabre\Exception\InvalidPath Filename is too long
2026-11-11T11:55:51Z | SETUP POST shares path=/spike30-share-ro shareWith=spike30a permissions=1 nutzer=spike30b status=200 id=188 file_target=/spike30-share-ro
2026-11-11T11:55:51Z | SETUP POST shares path=/spike30-share-rw shareWith=spike30a permissions=15 nutzer=spike30b status=200 id=189 file_target=/spike30-share-rw
2026-11-11T11:55:51Z | MKCOL share-ro auth=appapi status=403 angelegt=nein erwartet=403 | Sabre\DAV\Exception\Forbidden
2026-11-11T11:55:51Z | MKCOL share-rw auth=appapi status=201 angelegt=ja erwartet=201 |
2026-11-11T11:55:52Z | MKCOL share-ro auth=basic status=403 angelegt=nein erwartet=403 | Sabre\DAV\Exception\Forbidden
2026-11-11T11:55:52Z | MKCOL share-rw auth=basic status=201 angelegt=ja erwartet=201 |
2026-11-11T11:55:52Z | KONTROLLE oc:permissions /spike30-share-ro (Ordner /spike30-share-ro von spike30b) aus Sicht von spike30a auth=appapi status=207 permissions=SGDN
2026-11-11T11:55:52Z | KONTROLLE oc:permissions /spike30-share-rw (Ordner /spike30-share-rw von spike30b) aus Sicht von spike30a auth=appapi status=207 permissions=SGDNVCK
FILES_ROOT root-vorhanden auth=appapi NC_MCP_FILES_ROOT=/spike30/root pfad=/unter-appapi url=/remote.php/dav/files/spike30a/spike30/root/unter-appapi
2026-11-11T11:55:52Z | MKCOL root-vorhanden auth=appapi status=201 angelegt=ja erwartet=201 |
FILES_ROOT root-fehlt auth=appapi NC_MCP_FILES_ROOT=/spike30/root-fehlt pfad=/unter-appapi url=/remote.php/dav/files/spike30a/spike30/root-fehlt/unter-appapi
2026-11-11T11:55:53Z | MKCOL root-fehlt auth=appapi status=409 angelegt=nein erwartet=409 | Sabre\DAV\Exception\Conflict Parent node does not exist
FILES_ROOT root-selbst auth=appapi NC_MCP_FILES_ROOT=/spike30/root pfad=/ url=/remote.php/dav/files/spike30a/spike30/root
2026-11-11T11:55:53Z | MKCOL root-selbst auth=appapi status=405 angelegt=nein erwartet=405 | Sabre\DAV\Exception\MethodNotAllowed The resource you tried to create already exists
FILES_ROOT root-vorhanden auth=basic NC_MCP_FILES_ROOT=/spike30/root pfad=/unter-basic url=/remote.php/dav/files/spike30a/spike30/root/unter-basic
2026-11-11T11:55:53Z | MKCOL root-vorhanden auth=basic status=201 angelegt=ja erwartet=201 |
FILES_ROOT root-fehlt auth=basic NC_MCP_FILES_ROOT=/spike30/root-fehlt pfad=/unter-basic url=/remote.php/dav/files/spike30a/spike30/root-fehlt/unter-basic
2026-11-11T11:55:53Z | MKCOL root-fehlt auth=basic status=409 angelegt=nein erwartet=409 | Sabre\DAV\Exception\Conflict Parent node does not exist
FILES_ROOT root-selbst auth=basic NC_MCP_FILES_ROOT=/spike30/root pfad=/ url=/remote.php/dav/files/spike30a/spike30/root
2026-11-11T11:55:54Z | MKCOL root-selbst auth=basic status=405 angelegt=nein erwartet=405 | Sabre\DAV\Exception\MethodNotAllowed The resource you tried to create already exists
2026-11-11T11:55:54Z | KONTROLLE kontingent PUT 2048 Bytes /spike30/quota-probe-appapi.bin auth=appapi nutzer=spike30a status=507 wirkt=ja | Sabre\DAV\Exception\InsufficientStorage Insufficient space in /spike30/quota-probe-appapi.bin
2026-11-11T11:55:55Z | MKCOL quota auth=appapi status=507 angelegt=nein erwartet=201 | Sabre\DAV\Exception\InsufficientStorage Insufficient space in /spike30. Cannot create directory
2026-11-11T11:55:55Z | KONTROLLE kontingent PUT 2048 Bytes /spike30/quota-probe-basic.bin auth=basic nutzer=spike30a status=507 wirkt=ja | Sabre\DAV\Exception\InsufficientStorage Insufficient space in /spike30/quota-probe-basic.bin
2026-11-11T11:55:55Z | MKCOL quota auth=basic status=507 angelegt=nein erwartet=201 | Sabre\DAV\Exception\InsufficientStorage Insufficient space in /spike30. Cannot create directory
MKCOL ZEILE frei appapi=201 basic=201 erwartet=201 abweichung_von_erwartung=keine
MKCOL ZEILE ordner-vorhanden appapi=405 basic=405 erwartet=405 abweichung_von_erwartung=keine
MKCOL ZEILE datei-vorhanden appapi=405 basic=405 erwartet=405 abweichung_von_erwartung=keine
MKCOL ZEILE eltern-fehlt appapi=409 basic=409 erwartet=409 abweichung_von_erwartung=keine
MKCOL ZEILE eltern-ist-datei appapi=409 basic=409 erwartet=409 abweichung_von_erwartung=keine
MKCOL ZEILE name-htaccess appapi=400 basic=400 erwartet=400 abweichung_von_erwartung=keine
MKCOL ZEILE name-backslash appapi=400 basic=400 erwartet=400 abweichung_von_erwartung=keine
MKCOL ZEILE name-ueberlang appapi=400 basic=400 erwartet=400 abweichung_von_erwartung=keine
MKCOL ZEILE share-ro appapi=403 basic=403 erwartet=403 abweichung_von_erwartung=keine
MKCOL ZEILE share-rw appapi=201 basic=201 erwartet=201 abweichung_von_erwartung=keine
MKCOL ZEILE root-vorhanden appapi=201 basic=201 erwartet=201 abweichung_von_erwartung=keine
MKCOL ZEILE root-fehlt appapi=409 basic=409 erwartet=409 abweichung_von_erwartung=keine
MKCOL ZEILE root-selbst appapi=405 basic=405 erwartet=405 abweichung_von_erwartung=keine
MKCOL ZEILE quota appapi=507 basic=507 erwartet=201 abweichung_von_erwartung=appapi,basic
MKCOL GLEICH appapi_basic=ja abweichend=keine
RUECKBAU reste_mit_praefix_spike30=keine
```

Rückbau: alle zwölf Felder der Baseline sind nach dem Lauf gleich. Die kurzen Zeilen wörtlich, die langen (App-Listen, Kalendertabellen) stehen nur in der Rohdatei:

```
BASELINE nutzer vorher={"admin":"admin","alice":"alice","bob":"bob"} nachher={"admin":"admin","alice":"alice","bob":"bob"} gleich=ja
BASELINE gruppen vorher={"admin":["admin"]} nachher={"admin":["admin"]} gleich=ja
BASELINE dateien_alice vorher=275 nachher=275 gleich=ja
BASELINE papierkorb_alice vorher=0 nachher=0 gleich=ja
BASELINE geloeschte_kalenderobjekte vorher=0 nachher=0 gleich=ja
BASELINE geloeschte_kalender vorher=0 nachher=0 gleich=ja
BASELINE calendar_retention vorher= nachher= gleich=ja
BASELINE quota_alice vorher=The setting does not exist for user "alice". nachher=The setting does not exist for user "alice". gleich=ja
```

Rohantwort der Zeile frei unter Impersonation, mit der Zeile zum Abbruchkriterium:

```
2026-11-11T11:55:45Z | MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201 | 
ABBRUCHKRITERIUM MESS-01 ausgeloest=nein status=201
  Aufruf: MKCOL /remote.php/dav/files/spike30a/spike30/frei-115543 ohne Body, nutzer=spike30a, auth=appapi
    HTTP 201 Created
    content-length: 0
    content-security-policy: default-src 'none';
    content-type: text/html; charset=UTF-8
    date: Wed, 11 Nov 2026 11:55:45 GMT
    oc-fileid: 00023274oclxpo7v8s2m
    referrer-policy: no-referrer
    server: Apache/2.4.68 (Debian)
    via: 1.1 Caddy
    x-content-type-options: nosniff
    x-frame-options: SAMEORIGIN
    x-permitted-cross-domain-policies: none
    x-powered-by: PHP/8.5.9
    x-request-id: pgrDEsSFpyKVk5r8XyzE
    x-robots-tag: noindex, nofollow
    x-user-id: spike30a
    (no body)
```

Rohantwort der Zeile share-ro unter Impersonation:

```
2026-11-11T11:55:51Z | MKCOL share-ro auth=appapi status=403 angelegt=nein erwartet=403 | Sabre\DAV\Exception\Forbidden
    HTTP 403 Forbidden
    content-length: 182
    content-security-policy: default-src 'none';
    content-type: application/xml; charset=utf-8
    date: Wed, 11 Nov 2026 11:55:51 GMT
    referrer-policy: no-referrer
    server: Apache/2.4.68 (Debian)
    via: 1.1 Caddy
    x-content-type-options: nosniff
    x-frame-options: SAMEORIGIN
    x-permitted-cross-domain-policies: none
    x-powered-by: PHP/8.5.9
    x-robots-tag: noindex, nofollow
    x-user-id: spike30a
    (body)
    <?xml version="1.0" encoding="utf-8"?>
    <d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
      <s:exception>Sabre\DAV\Exception\Forbidden</s:exception>
      <s:message/>
    </d:error>
```

Rohantwort der Zeile name-htaccess unter Impersonation:

```
2026-11-11T11:55:48Z | MKCOL name-htaccess auth=appapi status=400 angelegt=nein erwartet=400 | OCA\DAV\Connector\Sabre\Exception\InvalidPath Filename is a reserved word
    HTTP 400 Bad Request
    content-length: 373
    content-security-policy: default-src 'none';
    content-type: application/xml; charset=utf-8
    date: Wed, 11 Nov 2026 11:55:48 GMT
    referrer-policy: no-referrer
    server: Apache/2.4.68 (Debian)
    via: 1.1 Caddy
    x-content-type-options: nosniff
    x-frame-options: SAMEORIGIN
    x-permitted-cross-domain-policies: none
    x-powered-by: PHP/8.5.9
    x-robots-tag: noindex, nofollow
    x-user-id: spike30a
    (body)
    <?xml version="1.0" encoding="utf-8"?>
    <d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" xmlns:o="http://owncloud.org/ns">
      <s:exception>OCA\DAV\Connector\Sabre\Exception\InvalidPath</s:exception>
      <s:message>Filename is a reserved word</s:message>
      <o:retry xmlns:o="o:">false</o:retry>
      <o:reason xmlns:o="o:">Filename is a reserved word</o:reason>
    </d:error>
```

Rohantwort der Zeile quota unter Impersonation (die Abweichung von der Erwartung):

```
2026-11-11T11:55:55Z | MKCOL quota auth=appapi status=507 angelegt=nein erwartet=201 | Sabre\DAV\Exception\InsufficientStorage Insufficient space in /spike30. Cannot create directory
    HTTP 507 Insufficient Storage
    content-length: 258
    content-security-policy: default-src 'none';
    content-type: application/xml; charset=utf-8
    date: Wed, 11 Nov 2026 11:55:54 GMT
    referrer-policy: no-referrer
    server: Apache/2.4.68 (Debian)
    via: 1.1 Caddy
    x-content-type-options: nosniff
    x-frame-options: SAMEORIGIN
    x-permitted-cross-domain-policies: none
    x-powered-by: PHP/8.5.9
    x-robots-tag: noindex, nofollow
    x-user-id: spike30a
    (body)
    <?xml version="1.0" encoding="utf-8"?>
    <d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
      <s:exception>Sabre\DAV\Exception\InsufficientStorage</s:exception>
      <s:message>Insufficient space in /spike30. Cannot create directory</s:message>
    </d:error>
```

### 12.2 raw/nc35-gruppenordner.txt

Zwei Läufe vom 2026-11-11 in einer Datei: erst controls, groupfolder und nc35-stop, danach der Nachlauf (nc35-up, nachlauf, nc35-stop), der zwei in der Datenbank verbliebene Gruppenordner entfernt hat. Die Messzeilen und die Zeilen des Rückbaus in der Reihenfolge des Protokolls; sehr lange Zeilen (Tabellenausgaben) stehen nur in der Rohdatei:

```
occ app:install groupfolders -> groupfolders 23.0.1 installed groupfolders enabled
GRUPPENORDNER version=23.0.1 installiert_vorher=nein (gelesen mit occ app:list --output=json)
occ group:add spike30grp -> Created group "spike30grp"
occ group:adduser spike30grp spike30a -> user spike30a added
occ group:adduser spike30grp spike30b -> user spike30b added
occ group:add spike30lesen -> Created group "spike30lesen"
occ group:adduser spike30lesen spike30a -> user spike30a added
occ groupfolders:create spike30gf -> 1
occ groupfolders:create spike30gf-lesen -> 2
occ groupfolders:group 1 spike30grp read write share delete -> (keine Ausgabe)
occ groupfolders:permissions 1 --enable -> (keine Ausgabe)
occ groupfolders:group 2 spike30lesen -> (keine Ausgabe)
2026-11-11T12:03:10Z | KONTROLLE PROPFIND Depth 1 home auth=appapi nutzer=spike30a status=207 spike30gf_sichtbar=ja spike30gf-lesen_sichtbar=ja
2026-11-11T12:03:10Z | GF-AUFBAU MKCOL /spike30gf/acl-rw auth=appapi nutzer=spike30a status=201 |
2026-11-11T12:03:11Z | GF-AUFBAU MKCOL /spike30gf/acl-ro auth=appapi nutzer=spike30a status=201 |
DATEISYSTEM gruppenordner spike30gf id=1 pfad=/var/www/html/data/__groupfolders/1/files
occ groupfolders:permissions 1 --user spike30a acl-ro -- +read -write -create -delete -> (keine Ausgabe)
occ groupfolders:permissions 1 --user spike30a --test acl-ro -> +read, -write, -create, -delete, +share
occ groupfolders:permissions 1 -> +--------+---------------------------+---------------------------------+ | Path | User/Group | Permissions | +--------+---------------------------+---------------------------------+ | acl-ro | user: spike30a (spike30a) | +read, -write, -create, -delete | +--------+---------------------------+-------
2026-11-11T12:03:12Z | KONTROLLE oc:permissions /spike30gf/acl-rw aus Sicht von spike30a auth=appapi status=207 permissions=RMGDNVCK
2026-11-11T12:03:12Z | KONTROLLE oc:permissions /spike30gf/acl-ro aus Sicht von spike30a auth=appapi status=207 permissions=RMG
2026-11-11T12:03:12Z | GF acl-rw auth=appapi nutzer=spike30a status=201 angelegt=ja |
2026-11-11T12:03:12Z | GF acl-ro auth=appapi nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
2026-11-11T12:03:13Z | GF acl-ro-kontrolle-b auth=appapi nutzer=spike30b status=201 angelegt=ja |
2026-11-11T12:03:13Z | GF acl-rw auth=basic nutzer=spike30a status=201 angelegt=ja |
2026-11-11T12:03:13Z | GF acl-ro auth=basic nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
2026-11-11T12:03:13Z | GF acl-ro-kontrolle-b auth=basic nutzer=spike30b status=201 angelegt=ja |
occ groupfolders:permissions 1 --user spike30a acl-ro clear -> (keine Ausgabe)
occ groupfolders:permissions 1 -> +------+------------+-------------+ | Path | User/Group | Permissions | +------+------------+-------------+
2026-11-11T12:03:16Z | GF acl-ro-nach-regelentzug auth=appapi nutzer=spike30a status=201 angelegt=ja |
2026-11-11T12:03:17Z | GF acl-ro-nach-regelentzug auth=basic nutzer=spike30a status=201 angelegt=ja |
2026-11-11T12:03:17Z | GF gruppe-nur-lesen auth=appapi nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
2026-11-11T12:03:17Z | GF gruppe-nur-lesen auth=basic nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
GF ZEILE acl-rw appapi=201 basic=201
GF ZEILE acl-ro appapi=403 basic=403
GF ZEILE acl-ro-kontrolle-b appapi=201 basic=201
GF ZEILE acl-ro-nach-regelentzug appapi=201 basic=201
GF ZEILE gruppe-nur-lesen appapi=403 basic=403
E12 NEGATIVTEST abgelehnt=ja status=403 a8_403=belegt (auth=appapi nutzer=spike30a; auth=basic status=403)
E12 POSITIV angelegt=ja status=201 (auth=appapi nutzer=spike30a)
E12 KONTROLLEN kontrolle_b=201 nach_regelentzug=201 (auth=appapi)
EXTERN files_external an_vorher=nein
occ app:enable files_external -> files_external 2.0.0-dev.0 enabled
mkdir -p /var/www/html/data/spike30ext (als www-data) -> angelegt
occ files_external:create spike30ext local null::null -c datadir=/var/www/html/data/spike30ext -> Storage created with id 1
occ files_external:applicable 1 --add-user spike30a -> - users: - spike30a - groups:
occ files_external:option 1 readonly true -> (keine Ausgabe)
2026-11-11T12:03:21Z | EXTERN ro auth=appapi nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
2026-11-11T12:03:21Z | EXTERN ro auth=basic nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
2026-11-11T12:03:21Z | KONTROLLE oc:permissions /spike30ext (readonly=true) aus Sicht von spike30a auth=appapi status=207 permissions=MG
occ files_external:option 1 readonly false -> (keine Ausgabe)
2026-11-11T12:03:22Z | EXTERN rw auth=appapi nutzer=spike30a status=201 angelegt=ja |
2026-11-11T12:03:22Z | EXTERN rw auth=basic nutzer=spike30a status=201 angelegt=ja |
EXTERN A8 abgelehnt=ja status=403 a8_403=belegt positivkontrolle_rw=201 (auth=appapi nutzer=spike30a)
occ files_external:delete --yes 1 ->
rm -rf /var/www/html/data/spike30ext -> entfernt
rm -rf /var/www/html/data/__groupfolders (Dateien darin vorher: 0) -> entfernt
occ group:delete spike30grp -> Group "spike30grp" was removed
occ group:delete spike30lesen -> Group "spike30lesen" was removed
occ user:delete spike30a -> The specified user was deleted
occ user:delete spike30b -> The specified user was deleted
occ app:disable files_external -> files_external 2.0.0-dev.0 disabled
occ config:app:delete files_external installed_version enabled types -> config:list: { "apps": { "files_external": [] } }
occ app:disable groupfolders -> groupfolders 23.0.1 disabled
occ app:remove groupfolders -> Disabled app 'groupfolders' (uninstall steps executed).
occ config:app:delete groupfolders installed_version enabled types -> config:list: { "apps": { "groupfolders": [] } }
RUECKBAU reste_mit_praefix_spike30=keine
RUECKBAU occ user:list -> - admin: admin - alice: alice - bob: bob
RUECKBAU occ app:list groupfolders_vorhanden=nein files_external_an=nein
docker stop nc35-nc -> nc35-nc | laeuft=false
docker stop nc35-harp -> nc35-harp | laeuft=false
docker stop nc35-caddy -> nc35-caddy | laeuft=false
docker stop nc_app_mcp_connector -> nc_app_mcp_connector | laeuft=false
NACHLAUF grund=der Rueckbau des Laufs davor fand die Gruppenordner nicht (das Feld heisst mountPoint, nicht mount_point); sie blieben in der Datenbank, die App war weg
occ app:install groupfolders -> groupfolders 23.0.1 installed groupfolders enabled
GRUPPENORDNER version=23.0.1 installiert_vorher=nein (gelesen mit occ app:list --output=json)
rm -rf /var/www/html/data/spike30ext -> entfernt
occ groupfolders:delete --force 1 ->
occ groupfolders:delete --force 2 ->
occ groupfolders:list --output=json (nach dem Loeschen) -> []
rm -rf /var/www/html/data/__groupfolders (Dateien darin vorher: fehlt) -> entfernt
occ app:disable groupfolders -> groupfolders 23.0.1 disabled
occ app:remove groupfolders -> Disabled app 'groupfolders' (uninstall steps executed).
occ config:app:delete groupfolders installed_version enabled types -> config:list: { "apps": { "groupfolders": [] } }
RUECKBAU reste_mit_praefix_spike30=keine
RUECKBAU occ user:list -> - admin: admin - alice: alice - bob: bob
RUECKBAU occ app:list groupfolders_vorhanden=nein files_external_an=nein
docker stop nc35-nc -> nc35-nc | laeuft=false
docker stop nc35-harp -> nc35-harp | laeuft=false
docker stop nc35-caddy -> nc35-caddy | laeuft=false
docker stop nc_app_mcp_connector -> nc_app_mcp_connector | laeuft=false
```

Baseline nach dem Nachlauf, alle zwölf Felder gleich; die kurzen Zeilen wörtlich:

```
BASELINE nutzer vorher={"admin":"admin","alice":"alice","bob":"bob"} nachher={"admin":"admin","alice":"alice","bob":"bob"} gleich=ja
BASELINE gruppen vorher={"admin":["admin"]} nachher={"admin":["admin"]} gleich=ja
BASELINE dateien_alice vorher=275 nachher=275 gleich=ja
BASELINE papierkorb_alice vorher=0 nachher=0 gleich=ja
BASELINE geloeschte_kalenderobjekte vorher=0 nachher=0 gleich=ja
BASELINE geloeschte_kalender vorher=0 nachher=0 gleich=ja
BASELINE calendar_retention vorher= nachher= gleich=ja
BASELINE quota_alice vorher=The setting does not exist for user "alice". nachher=The setting does not exist for user "alice". gleich=ja
```

Rohantwort der Zeile acl-ro unter Impersonation (Negativtest E12):

```
2026-11-11T12:03:12Z | GF acl-ro auth=appapi nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
  Aufruf: MKCOL /remote.php/dav/files/spike30a/spike30gf/acl-ro/neu-appapi ohne Body, Dateisystem: /var/www/html/data/__groupfolders/1/files/acl-ro/neu-appapi
    HTTP 403 Forbidden
    content-length: 182
    content-security-policy: default-src 'none';
    content-type: application/xml; charset=utf-8
    date: Wed, 11 Nov 2026 12:03:12 GMT
    referrer-policy: no-referrer
    server: Apache/2.4.68 (Debian)
    via: 1.1 Caddy
    x-content-type-options: nosniff
    x-frame-options: SAMEORIGIN
    x-permitted-cross-domain-policies: none
    x-powered-by: PHP/8.5.9
    x-robots-tag: noindex, nofollow
    x-user-id: spike30a
    (body)
    <?xml version="1.0" encoding="utf-8"?>
    <d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
      <s:exception>Sabre\DAV\Exception\Forbidden</s:exception>
      <s:message/>
    </d:error>
```

Rohantwort der Zeile acl-rw unter Impersonation (Positivfall E12):

```
2026-11-11T12:03:12Z | GF acl-rw auth=appapi nutzer=spike30a status=201 angelegt=ja | 
  Aufruf: MKCOL /remote.php/dav/files/spike30a/spike30gf/acl-rw/neu-appapi ohne Body, Dateisystem: /var/www/html/data/__groupfolders/1/files/acl-rw/neu-appapi
    HTTP 201 Created
    content-length: 0
    content-security-policy: default-src 'none';
    content-type: text/html; charset=UTF-8
    date: Wed, 11 Nov 2026 12:03:12 GMT
    oc-fileid: 00023311oclxpo7v8s2m
    referrer-policy: no-referrer
    server: Apache/2.4.68 (Debian)
    via: 1.1 Caddy
    x-content-type-options: nosniff
    x-frame-options: SAMEORIGIN
    x-permitted-cross-domain-policies: none
    x-powered-by: PHP/8.5.9
    x-request-id: 3KtYmAb9gQPg72qCJID4
    x-robots-tag: noindex, nofollow
    x-user-id: spike30a
    (no body)
```

Antwort auf den PROPFIND des Ordners mit der Regel, mit der ACL-Liste:

```
<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"><d:response><d:href>/remote.php/dav/files/spike30a/spike30gf/acl-ro/</d:href><d:propstat><d:prop><oc:permissions>RMG</oc:permissions><nc:acl-enabled>1</nc:acl-enabled><nc:acl-list><nc:acl><nc:acl-mapping-type>user</nc:acl-mapping-type><nc:acl-mapping-id>spike30a</nc:acl-mapping-id><nc:acl-mapping-display-name>spike30a</nc:acl-mapping-display-name><nc:acl-mask>15</nc:acl-mask><nc:acl-permissions>1</nc:acl-permissions></nc:acl></nc:acl-list></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>
```

Rohantwort der Zeile EXTERN ro unter Impersonation:

```
2026-11-11T12:03:21Z | EXTERN ro auth=appapi nutzer=spike30a status=403 angelegt=nein | Sabre\DAV\Exception\Forbidden
  Aufruf: MKCOL /remote.php/dav/files/spike30a/spike30ext/neu-ro-appapi ohne Body
    HTTP 403 Forbidden
    content-length: 182
    content-security-policy: default-src 'none';
    content-type: application/xml; charset=utf-8
    date: Wed, 11 Nov 2026 12:03:21 GMT
    referrer-policy: no-referrer
    server: Apache/2.4.68 (Debian)
    via: 1.1 Caddy
    x-content-type-options: nosniff
    x-frame-options: SAMEORIGIN
    x-permitted-cross-domain-policies: none
    x-powered-by: PHP/8.5.9
    x-robots-tag: noindex, nofollow
    x-user-id: spike30a
    (body)
    <?xml version="1.0" encoding="utf-8"?>
    <d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
      <s:exception>Sabre\DAV\Exception\Forbidden</s:exception>
      <s:message/>
    </d:error>
```

### 12.3 raw/nc35-aendern.txt

Lauf vom 2026-11-11, Blöcke nc35-up, controls, modify und ui-prepare in einem Aufruf. Der Lauf endet ohne Rückbau, weil die Browser-Sitzung die Konten und Listen braucht; den Rückbau fährt der Block ui-teardown nach der Auswertung. Die Messzeilen in der Reihenfolge des Protokolls; die entfalteten Zeilenmengen des Probeobjekts vor und nach dem ändernden PUT stehen nur in der Rohdatei:

```
2026-11-11T12:36:37Z | MKCALENDAR auth=appapi status=201 liste=spike30-a nutzer=spike30a komponenten=VTODO |
2026-11-11T12:36:37Z | MKCALENDAR auth=appapi status=201 liste=spike30-b nutzer=spike30a komponenten=VTODO |
KONTROLLE exapp_impersonation.log, MKCALENDAR-Zeilen von spike30a: 2
2026-11-11T12:36:37Z | FREIGABE liste=spike30-b-ro an=spike30a schreibrecht=nein nutzer=spike30b auth=basic status=200 (POST mit dem share-Dokument, Namensraum http://owncloud.org/ns)
2026-11-11T12:36:37Z | FREIGABE liste=spike30-b-rw an=spike30a schreibrecht=ja nutzer=spike30b auth=basic status=200 (POST mit dem share-Dokument, Namensraum http://owncloud.org/ns)
2026-11-11T12:36:37Z | DISCOVERY PROPFIND Depth 1 auth=appapi nutzer=spike30a 207
DISCOVERY liste=spike30-a name=spike30-a komponenten=VTODO
DISCOVERY liste=spike30-b name=spike30-b komponenten=VTODO
DISCOVERY liste=spike30-b-ro_shared_by_spike30b name=spike30-b-ro (spike30b) komponenten=VTODO
DISCOVERY liste=spike30-b-rw_shared_by_spike30b name=spike30-b-rw (spike30b) komponenten=VTODO
2026-11-11T12:36:37Z | SETUP PUT create-only spike30-a/s30-ifmatch-appapi-123635.ics nutzer=spike30a auth=appapi status=201 antwort_etag=7e104de2233c |
2026-11-11T12:36:39Z | IF-MATCH aktuell auth=appapi nutzer=spike30a status=204 etag_vorher=7e104de2233c etag_nachher=2ee40cb76ab8 | antwort_etag=ja etag_art=stark inhalt_neu=ja db_hash_geaendert=ja db_gleich_gesendet=ja
KONTROLLE exapp_impersonation.log, PUT-Zeilen von spike30a: 2
2026-11-11T12:36:39Z | GEGENPROBE multiget REPORT calendar-multiget auth=basic nutzer=spike30a status=207 objekte=1 inhalt_gleich_gesendet=ja
2026-11-11T12:36:39Z | GEGENPROBE falsches-secret PUT mit If-Match nutzer=spike30a status=401 db_hash_unveraendert=ja | Sabre\DAV\Exception\NotAuthenticated No public access to this resource., AppAPIAuth has not passed, This request is not for a federated calendar, No 'Authorization: Basic' header found. Either the client didn't send one, or the server is misconfigured, No 'Authorization: Bearer' header found. Either
2026-11-11T12:36:40Z | IF-MATCH veraltet auth=appapi nutzer=spike30a status=412 etag_vorher=2ee40cb76ab8 etag_nachher=2ee40cb76ab8 | Sabre\DAV\Exception\PreconditionFailed An If-Match header was specified, but none of the specified ETags matched.
HASH calendardata vorher=1 e5384bf2c56eb3fb82cf36e9e0a11977f228d1217c94b7184ec029a9bb745865:245 nachher=1 e5384bf2c56eb3fb82cf36e9e0a11977f228d1217c94b7184ec029a9bb745865:245 gleich=ja get_byte_gleich=ja
ABBRUCHKRITERIUM MESS-05 IF-MATCH ausgeloest=nein grund=keiner
2026-11-11T12:36:40Z | SETUP PUT create-only spike30-a/s30-ifmatch-basic-123635.ics nutzer=spike30a auth=basic status=201 antwort_etag=d4d82855683e |
2026-11-11T12:36:41Z | IF-MATCH aktuell auth=basic nutzer=spike30a status=204 etag_vorher=d4d82855683e etag_nachher=6e9e2a67bdc2 | antwort_etag=ja etag_art=stark inhalt_neu=ja db_hash_geaendert=ja db_gleich_gesendet=ja
2026-11-11T12:36:42Z | IF-MATCH veraltet auth=basic nutzer=spike30a status=412 etag_vorher=6e9e2a67bdc2 etag_nachher=6e9e2a67bdc2 | Sabre\DAV\Exception\PreconditionFailed An If-Match header was specified, but none of the specified ETags matched.
HASH calendardata vorher=1 884ec15e15eb36ff483f9149eea2d6369c6d068ade57f22c362bd0cbfa903bb9:244 nachher=1 884ec15e15eb36ff483f9149eea2d6369c6d068ade57f22c362bd0cbfa903bb9:244 gleich=ja get_byte_gleich=ja
IF-MATCH GLEICH appapi_basic=ja appapi=(204, True, 412, True) basic=(204, True, 412, True) (status aktuell, etag geaendert, status veraltet, danach unveraendert)
2026-11-11T12:36:42Z | PUT ohne-if-match auth=appapi nutzer=spike30a status=204 etag_vorher=2ee40cb76ab8 etag_nachher=226402702ad7 | ueberschrieben=ja |
HASH calendardata vorher=1 e5384bf2c56eb3fb82cf36e9e0a11977f228d1217c94b7184ec029a9bb745865:245 nachher=1 31b2447eac07fb1abd802416cdcee6e8411d7de698044a2847b92f84b13d0956:251
2026-11-11T12:36:43Z | PUT if-match-stern auth=appapi nutzer=spike30a status=204 etag_vorher=226402702ad7 etag_nachher=432e3008ca1c | ueberschrieben=ja |
HASH calendardata vorher=1 31b2447eac07fb1abd802416cdcee6e8411d7de698044a2847b92f84b13d0956:251 nachher=1 b47a01d476d237d657ede209607749f28c4b7d0d97697d0b7a0b00bb82dab8db:252
2026-11-11T12:36:43Z | EIGENSCHAFTEN anlegen auth=appapi nutzer=spike30a status=201 etag_vorher=- etag_nachher=0d890eb85e85 |
SPEICHERUNG woertlich=ja gesendet=633a90c17a2ffd068d3b86762fd9fdf15337f4a1bfc442abcd39e40323730d81:1104 datenbank=1 633a90c17a2ffd068d3b86762fd9fdf15337f4a1bfc442abcd39e40323730d81:1104 get_gleich_gesendet=ja
2026-11-11T12:36:43Z | EIGENSCHAFTEN aendern auth=appapi nutzer=spike30a status=204 etag_vorher=0d890eb85e85 etag_nachher=8013d80a8066 |
SPEICHERUNG nach_aendern woertlich=ja gesendet=64989341a79f258ac32e153a1472056663c4f032b159a18c7938a02a8fdf7cdd:1104 datenbank=1 64989341a79f258ac32e153a1472056663c4f032b159a18c7938a02a8fdf7cdd:1104 get_gleich_gesendet=ja
EIGENSCHAFTEN differenz zeilen_vorher=37 zeilen_nachher=37 hinzu=keine entfernt=keine geaendert=['SUMMARY']
2026-11-11T12:36:43Z | SETUP PUT create-only spike30-a/s30-eigenschaften-kontrolle-123635.ics nutzer=spike30a auth=appapi status=201 antwort_etag=eb53a0b26d09 |
2026-11-11T12:36:43Z | KONTROLLE eigenschaften kontrollobjekt ohne die Zeile X-SPIKE30-FOO:bar zurueckgeschrieben status=204 verloren=['entfernt VCALENDAR/VTODO:X-SPIKE30-FOO:bar'] genau_die_entfernte=ja
PFLEGEFELDER server=keine
ABBRUCHKRITERIUM MESS-05 EIGENSCHAFTEN ausgeloest=nein verloren=keine put_status=204 aenderung_angekommen=ja kontrolle=ok
2026-11-11T12:36:44Z | SETUP PUT create-only spike30-b-ro/s30-geteilt-ro-123635.ics nutzer=spike30b auth=basic status=201 antwort_etag=180d92b53430 |
2026-11-11T12:36:44Z | SETUP PUT create-only spike30-b-rw/s30-geteilt-rw-123635.ics nutzer=spike30b auth=basic status=201 antwort_etag=9d8d701ca8d1 |
2026-11-11T12:36:44Z | LESEN geteilt spike30-b-ro_shared_by_spike30b/s30-geteilt-ro-123635.ics auth=appapi nutzer=spike30a status=200
2026-11-11T12:36:44Z | NUR-LESEN put auth=appapi nutzer=spike30a status=404 etag_vorher=180d92b53430 etag_nachher=180d92b53430 | beim_eigentuemer_unveraendert=ja | Sabre\DAV\Exception\NotFound Node with name 's30-geteilt-ro-123635.ics' could not be found
HASH calendardata vorher=1 1b5e67485bb48966b62b105976b7ffd3fff2dbb8c9b1b14fe965654ad9e59600:243 nachher=1 1b5e67485bb48966b62b105976b7ffd3fff2dbb8c9b1b14fe965654ad9e59600:243; etag_nachher ist als spike30b mit App-Passwort gelesen
2026-11-11T12:36:44Z | LESEN geteilt spike30-b-rw_shared_by_spike30b/s30-geteilt-rw-123635.ics auth=appapi nutzer=spike30a status=200
2026-11-11T12:36:45Z | SCHREIBRECHT put auth=appapi nutzer=spike30a status=204 etag_vorher=9d8d701ca8d1 etag_nachher=f93acd4b84b2 | beim_eigentuemer_unveraendert=nein |
HASH calendardata vorher=1 76fc316791af2682732dc0ec16384fd22dfb2bf31ff8a384deb8e2b60f84202d:243 nachher=1 fb6d58e5c3e73382298c951519c4463a8d963a576d20be855b9300c0bfe7e56a:247; etag_nachher ist als spike30b mit App-Passwort gelesen
2026-11-11T12:36:45Z | NUR-LESEN anlegen auth=appapi nutzer=spike30a status=404 etag_vorher=- etag_nachher=- | angelegt=nein | Sabre\DAV\Exception\NotFound Calendar with name 'spike30-b-ro_shared_by_spike30b' could not be found
2026-11-11T12:36:45Z | LESEN geteilt spike30-b-ro_shared_by_spike30b/s30-geteilt-ro-123635.ics auth=basic nutzer=spike30a status=200
2026-11-11T12:36:45Z | NUR-LESEN put auth=basic nutzer=spike30a status=404 etag_vorher=180d92b53430 etag_nachher=180d92b53430 | beim_eigentuemer_unveraendert=ja | Sabre\DAV\Exception\NotFound Node with name 's30-geteilt-ro-123635.ics' could not be found
HASH calendardata vorher=1 1b5e67485bb48966b62b105976b7ffd3fff2dbb8c9b1b14fe965654ad9e59600:243 nachher=1 1b5e67485bb48966b62b105976b7ffd3fff2dbb8c9b1b14fe965654ad9e59600:243; etag_nachher ist als spike30b mit App-Passwort gelesen
2026-11-11T12:36:45Z | LESEN geteilt spike30-b-rw_shared_by_spike30b/s30-geteilt-rw-123635.ics auth=basic nutzer=spike30a status=200
2026-11-11T12:36:46Z | SCHREIBRECHT put auth=basic nutzer=spike30a status=204 etag_vorher=f93acd4b84b2 etag_nachher=b118b7ab412a | beim_eigentuemer_unveraendert=nein |
HASH calendardata vorher=1 fb6d58e5c3e73382298c951519c4463a8d963a576d20be855b9300c0bfe7e56a:247 nachher=1 d383c08a0f6a76342dadef8e272ff3c4d46137da1c457cb162b959c898cadabf:246; etag_nachher ist als spike30b mit App-Passwort gelesen
2026-11-11T12:36:46Z | NUR-LESEN anlegen auth=basic nutzer=spike30a status=404 etag_vorher=- etag_nachher=- | angelegt=nein | Sabre\DAV\Exception\NotFound Calendar with name 'spike30-b-ro_shared_by_spike30b' could not be found
NUR-LESEN ERGEBNIS abgelehnt=ja status=404 anlegen=404 positivkontrolle_schreibrecht=204 (auth=appapi); auth=basic: 404, 404, 204
2026-11-11T12:36:46Z | SETUP PUT create-only spike30-a/s30-wiederkehrend-123635.ics nutzer=spike30a auth=appapi status=201 antwort_etag=67728bfc20f9 |
2026-11-11T12:36:47Z | WIEDERKEHREND server status=204 rrule_erhalten=ja status_completed_gespeichert=ja woertlich_gespeichert=ja objekte_vorher=5 objekte_nachher=5 neue_objekte=keine auth=appapi nutzer=spike30a etag_vorher=67728bfc20f9 etag_nachher=c6bc3d2796d3
WIEDERKEHREND differenz hinzu=['VCALENDAR/VTODO:COMPLETED:20261111T123646Z', 'VCALENDAR/VTODO:PERCENT-COMPLETE:100', 'VCALENDAR/VTODO:STATUS:COMPLETED'] entfernt=keine geaendert=keine; datenbank=1 4e223650e00b251e23a6dde6eda8fccd79cdeab9ccd40d6a7613595789581ffe:387
2026-11-11T12:36:47Z | SETUP PUT create-only spike30-a/s30-eltern-123635.ics nutzer=spike30a auth=appapi status=201 antwort_etag=b345eb6f049b |
2026-11-11T12:36:47Z | SETUP PUT create-only spike30-a/s30-kind-123635.ics nutzer=spike30a auth=appapi status=201 antwort_etag=db690a34e9bf |
2026-11-11T12:36:47Z | UNTERAUFGABE server unveraendert=ja eltern_status=204 eltern_etag_geaendert=ja kind_etag_vorher=db690a34e9bf kind_etag_nachher=db690a34e9bf kind_hash_gleich=ja auth=appapi nutzer=spike30a
HASH calendardata der Unteraufgabe vorher=1 908c30d699f984198d59c2ae03541cd807d749356f22ec3e09010aed88fa4f17:265 nachher=1 908c30d699f984198d59c2ae03541cd807d749356f22ec3e09010aed88fa4f17:265
occ app:install tasks -> tasks 0.18.1 installed tasks enabled
TASKS-APP version=0.18.1 installiert_vorher=nein (gelesen mit occ app:list --output=json)
2026-11-11T12:36:56Z | UI-KONTO DISCOVERY auth=basic nutzer=spike30ui status=207 listen=keine
2026-11-11T12:36:56Z | UI-KONTO DISCOVERY auth=appapi nutzer=spike30ui status=207 listen=keine
2026-11-11T12:36:56Z | UI-KONTO GET /apps/tasks/ auth=basic nutzer=spike30ui status=200 html=ja
UI-KONTO nutzer=spike30ui adresse=http://127.0.0.1:8082/apps/tasks/ zugangsdaten=in einer Datei ausserhalb des Repositorys (drei Zeilen: Nutzer, Passwort, Basis-URL)
RUECKBAU ausgesetzt: Konten, Listen und die Tasks-App bleiben fuer die Browser-Sitzung stehen; der Block ui-teardown baut zurueck und vergleicht mit den BASELINE-START-Zeilen dieses Laufs
```

Rohantwort zu M3.1 (PUT mit der gelesenen ETag unter Impersonation):

```
HTTP 204 No Content
content-security-policy: default-src 'none';
date: Wed, 11 Nov 2026 12:36:39 GMT
etag: "2ee40cb76ab8f266dfa846561bb6a513"
oc-etag: "2ee40cb76ab8f266dfa846561bb6a513"
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-request-id: b0GrTtuKbb69VATgQHi1
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(no body)
```

Rohantwort zu M3.2 (PUT mit der veralteten ETag unter Impersonation):

```
HTTP 412 Precondition Failed
content-length: 308
content-security-policy: default-src 'none';
content-type: application/xml; charset=utf-8
date: Wed, 11 Nov 2026 12:36:39 GMT
etag: "2ee40cb76ab8f266dfa846561bb6a513"
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(body)
<?xml version="1.0" encoding="utf-8"?>
<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
<s:exception>Sabre\DAV\Exception\PreconditionFailed</s:exception>
<s:message>An If-Match header was specified, but none of the specified ETags matched.</s:message>
<s:header>If-Match</s:header>
</d:error>
```

Rohantworten zu M3.5 (nur lesbare Liste: PUT und Anlegen; danach die Freigabe mit Schreibrecht), alle unter Impersonation:

```
HTTP 404 Not Found
content-length: 253
content-security-policy: default-src 'none';
content-type: application/xml; charset=utf-8
date: Wed, 11 Nov 2026 12:36:44 GMT
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-robots-tag: noindex, nofollow
(body)
<?xml version="1.0" encoding="utf-8"?>
<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
<s:exception>Sabre\DAV\Exception\NotFound</s:exception>
<s:message>Node with name 's30-geteilt-ro-123635.ics' could not be found</s:message>
</d:error>
```

```
HTTP 404 Not Found
content-length: 263
content-security-policy: default-src 'none';
content-type: application/xml; charset=utf-8
date: Wed, 11 Nov 2026 12:36:45 GMT
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(body)
<?xml version="1.0" encoding="utf-8"?>
<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
<s:exception>Sabre\DAV\Exception\NotFound</s:exception>
<s:message>Calendar with name 'spike30-b-ro_shared_by_spike30b' could not be found</s:message>
</d:error>
```

```
HTTP 204 No Content
content-security-policy: default-src 'none';
date: Wed, 11 Nov 2026 12:36:44 GMT
etag: "f93acd4b84b2471100d34b4926741fc8"
oc-etag: "f93acd4b84b2471100d34b4926741fc8"
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-request-id: retZJbJbtJoVIeTo2Bt9
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(no body)
```

### 12.4 raw/ui-sitzung.txt

Die Datei trägt mehrere Läufe vom 2026-11-11 hintereinander. Zuerst acht Versuche, Stand a zu sichern, die am RAM-Tor endeten (freier Host-Speicher 3,87 bis 3,97 GB bei einer Schwelle von 4,0, der Browser lief noch); sie haben nichts gelesen und nichts geschrieben. Dann der Lauf, der Stand a gesichert hat, der Lauf für Stand b mit dem Vergleichsobjekt, ein Lauf mit ui-log und ui-evaluate, und ein zweiter Lauf von ui-log, der zusätzlich die rohe Discovery des Kontos festhält (als Wiederholung benannt, die Zugriffszeilen sind dieselben). Die acht Abbrüche lauten alle so, nur der Wert wechselt:

```
RUN FAILED | RunFailed: RAM gate shut: 3.87 GB free (needs 4.0), foreign runs: []; nothing was stopped
RUN FAILED | RunFailed: RAM gate shut: 3.97 GB free (needs 4.0), foreign runs: []; nothing was stopped
```

Die Messzeilen ab dem gelungenen Stand a. Von den vierzig schreibenden Aufrufen des Kontos stehen hier die aus Runde B und die beiden mit Fehlerstatus; alle vierzig und die Zeilen je Objekt stehen in der Rohdatei:

```
UI-LISTE stand=a liste=personal name=Persönlich komponenten=VEVENT,VTODO,VJOURNAL
UI-LISTE stand=a liste=spike30-liste-1 name=spike30-liste-1 komponenten=VTODO
UI-LISTE stand=a liste=spike30-liste-2 name=spike30-liste-2 komponenten=VTODO
2026-11-11T12:59:26Z | UI-PAPIERKORB-LESEN stand=a REPORT calendar-query trashbin/objects auth=appapi status=207 objekte=0
UI-GLEICH appapi_basic=ja abweichend=keine
UI-STAND a objekte=15
UI-WIEDERKEHREND vorhanden=ja
UI-LISTE stand=b liste=personal name=Persönlich komponenten=VEVENT,VTODO,VJOURNAL
UI-LISTE stand=b liste=spike30-liste-1 name=spike30-liste-1 komponenten=VTODO
UI-LISTE stand=b liste=spike30-liste-2 name=spike30-liste-2 komponenten=VTODO
2026-11-11T13:05:35Z | UI-REPORT stand=b liste=personal auth=appapi status=207 objekte=0 | auth=basic status=207 objekte=0
2026-11-11T13:05:35Z | UI-REPORT stand=b liste=spike30-liste-1 auth=appapi status=207 objekte=10 | auth=basic status=207 objekte=10
2026-11-11T13:05:35Z | UI-REPORT stand=b liste=spike30-liste-2 auth=appapi status=207 objekte=3 | auth=basic status=207 objekte=3
2026-11-11T13:05:35Z | UI-PAPIERKORB-LESEN stand=b REPORT calendar-query trashbin/objects auth=appapi status=207 objekte=2
UI-STAND b objekte=15
2026-11-11T13:05:35Z | VERGLEICH skript_put pflegefelder_server=keine anlegen=201 abhaken=204 etag_vorher=f11673e3ef94 etag_nachher=eeb5d58cd8b1 gesendet_hinzu=['COMPLETED:20261111T130535Z', 'PERCENT-COMPLETE:100', 'STATUS:COMPLETED'] vom_server_entfernt=keine woertlich_gespeichert=ja auth=appapi nutzer=spike30a liste=spike30-a objekt=s30-vergleich-130535.ics
UI-ZUGRIFFE nutzer=spike30ui schreibende_anfragen=40 (Zugriffsprotokoll)
UI-ZUGRIFF 11/Nov/2026:12:53:23 +0000 PUT spike30-liste-1/FEC4C13F-9381-4D0F-8348-F6D2643BDE32.ics status=500
UI-ZUGRIFF 11/Nov/2026:13:00:01 +0000 PUT spike30-liste-1/2D4850EC-8E4C-4BDF-A1E5-58559950667D.ics status=204
UI-ZUGRIFF 11/Nov/2026:13:01:11 +0000 PUT spike30-liste-1/2D4850EC-8E4C-4BDF-A1E5-58559950667D.ics status=204
UI-ZUGRIFF 11/Nov/2026:13:01:26 +0000 PUT spike30-liste-1/231A6117-89EA-417C-952A-9BB4A2AE9A60.ics status=500
UI-ZUGRIFF 11/Nov/2026:13:01:25 +0000 PUT spike30-liste-1/7CB0DDE8-C2D1-4640-B1D0-808CA11B3E2E.ics status=204
UI-ZUGRIFF 11/Nov/2026:13:01:29 +0000 PUT spike30-liste-1/7B483532-932E-4791-B363-DD0F4E3C8FEF.ics status=204
UI-ZUGRIFF 11/Nov/2026:13:01:47 +0000 MOVE spike30-liste-1/1EA798A8-7873-43DE-B2DC-0926941B62D0.ics status=201
UI-ZUGRIFF 11/Nov/2026:13:02:43 +0000 MOVE spike30-liste-1/D9556088-A989-49E2-A64A-EB82F07F575E.ics status=201
UI-ZUGRIFF 11/Nov/2026:13:02:43 +0000 MOVE spike30-liste-1/C4CED131-CD86-49FE-86E7-1EA2956A4AF2.ics status=201
UI-ZUGRIFF 11/Nov/2026:13:03:41 +0000 DELETE spike30-liste-1/8284CF2E-FED9-40DF-B41A-31475E72DAA4.ics status=204
UI-ZUGRIFF 11/Nov/2026:13:03:41 +0000 DELETE spike30-liste-1/C67CFD08-4F41-4754-9ECF-5D64AC34BAC9.ics status=204
UI-ZUGRIFFE mit_fehlerstatus=2
UI-SERVERFEHLER 2026-11-11T12:53:23+00:00 PUT ars/spike30ui/spike30-liste-1/FEC4C13F-9381-4D0F-8348-F6D2643BDE32.ics | An exception occurred while executing a query: SQLSTATE[HY000]: General error: 5 database is locked
UI-SERVERFEHLER 2026-11-11T12:53:23+00:00 PUT ars/spike30ui/spike30-liste-1/FEC4C13F-9381-4D0F-8348-F6D2643BDE32.ics | Uncaught exception
UI-SERVERFEHLER 2026-11-11T13:01:26+00:00 PUT ars/spike30ui/spike30-liste-1/231A6117-89EA-417C-952A-9BB4A2AE9A60.ics | An exception occurred while executing a query: SQLSTATE[HY000]: General error: 5 database is locked
UI-SERVERFEHLER 2026-11-11T13:01:26+00:00 PUT ars/spike30ui/spike30-liste-1/231A6117-89EA-417C-952A-9BB4A2AE9A60.ics | Uncaught exception
UI-AUSWERTUNG stand_a_objekte=15 stand_b_objekte=15 (nach UID)
ABHAKEN FELDER hinzu=COMPLETED,PERCENT-COMPLETE,STATUS entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED zeitform_completed=utc
ABHAKEN zeilen_hinzu=['COMPLETED:20261111T125947Z', 'PERCENT-COMPLETE:100', 'STATUS:COMPLETED']
WIEDEROEFFNEN FELDER hinzu=STATUS entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED
WIEDEROEFFNEN zeilen_hinzu=['STATUS:NEEDS-ACTION'] abhaken_felder_danach_fehlend=COMPLETED,PERCENT-COMPLETE status_danach=NEEDS-ACTION
ELTERN ABHAKEN kind_geaendert=ja kind_differenz=hinzu=COMPLETED,PERCENT-COMPLETE,STATUS entfernt=keine geaendert=DTSTAMP,LAST-MODIFIED | eltern_geaendert=nein eltern_differenz=leer
ELTERN ABHAKEN kind_zeilen_hinzu=['COMPLETED:20261111T130125Z', 'PERCENT-COMPLETE:100', 'STATUS:COMPLETED'] eltern_status_stand_b=fehlt
WIEDERKEHREND app differenz hinzu=keine entfernt=keine geaendert=DTSTAMP,DUE,LAST-MODIFIED due_vorher=20261120T130000Z due_nachher=20261121T130000Z rrule_nachher=FREQ=DAILY status_nachher=fehlt completed_nachher=fehlt neue_objekte=0
KONTROLLE unberuehrt differenz=leer
UI-UMZUG objekte_in_liste_2=3 verschoben=3
UI-UMZUG objekt=s30 umzug-einzeln von=spike30-liste-1 nach=spike30-liste-2 dateiname_gleich=ja inhalt_gleich=ja
UI-UMZUG objekt=s30 eltern-umzug von=spike30-liste-1 nach=spike30-liste-2 dateiname_gleich=ja inhalt_gleich=ja
UI-UMZUG objekt=s30 kind-umzug von=spike30-liste-1 nach=spike30-liste-2 dateiname_gleich=ja inhalt_gleich=ja
UI-PAPIERKORB objekte=2
UI-PAPIERKORB objekt=s30 eltern-loeschen datei=trash-135.ics datei_stand_a=C67CFD08-4F41-4754-9ECF-5D64AC34BAC9.ics inhalt_gleich_stand_a=ja
UI-PAPIERKORB objekt=s30 kind-loeschen datei=trash-142.ics datei_stand_a=8284CF2E-FED9-40DF-B41A-31475E72DAA4.ics inhalt_gleich_stand_a=ja
UI-NEU objekte=0 uids=keine
UI-VERSCHWUNDEN objekte=0 uids=keine
ZEITFORM stand=b name=s30 abhaken COMPLETED=utc CREATED=utc LAST-MODIFIED=utc DTSTAMP=utc
ZEITFORM stand=b name=s30 ganztag DUE=date CREATED=utc LAST-MODIFIED=utc DTSTAMP=utc
ZEITFORM stand=b name=s30 uhrzeit DTSTART=utc DUE=utc CREATED=utc LAST-MODIFIED=utc DTSTAMP=utc
ZEITFORM stand=b name=s30 wiederkehrend DUE=utc CREATED=utc LAST-MODIFIED=utc DTSTAMP=utc
```

Rückbau und Stopp, angehängt an raw/nc35-aendern.txt (Lauf ui-teardown und nc35-stop); die zwölf BASELINE-Zeilen dieses Laufs enden alle auf gleich=ja und stehen in der Rohdatei:

```
RUECKBAU ausgesetzt: Konten, Listen und die Tasks-App bleiben fuer die Browser-Sitzung stehen; der Block ui-teardown baut zurueck und vergleicht mit den BASELINE-START-Zeilen dieses Laufs
UI-TEARDOWN baseline aus nc35-aendern.txt gelesen: 12 Felder
UI-TEARDOWN die Datei mit den Zugangsdaten des Browser-Kontos ist geloescht
RUECKBAU reste_mit_praefix_spike30=keine
RUECKBAU occ user:list -> - admin: admin - alice: alice - bob: bob
RUECKBAU occ app:list groupfolders_vorhanden=nein files_external_an=nein
docker stop nc35-nc -> nc35-nc | laeuft=false
docker stop nc35-harp -> nc35-harp | laeuft=false
docker stop nc35-caddy -> nc35-caddy | laeuft=false
docker stop nc_app_mcp_connector -> nc_app_mcp_connector | laeuft=false
```

### 12.5 raw/inventar.txt

Lauf vom 2026-11-11, Block inventory, ohne Instanz. Kopf und Summen, danach die Zeilen der Konstanten und der Zusagen in Server und Store-Text, danach die Kette zu E15. Alle Fundstellen samt den ausgeschlossenen stehen in der Rohdatei:

```
INVENTAR commit=32b8df00964e5f724ae3edc3de1796f3693159ef (die Zeilennummern gelten auf diesem Commit)
INVENTAR arbeitsbaum_abweichend=nein ausgelassen=['docs/spike-tasks.md'] (der Bericht dieser Phase zitiert die Zusagen selbst)
INVENTAR MUSTER 1 treffer=242 | MUSTER 2 treffer=191
INVENTAR POSITIVKONTROLLE gefunden=6/6 stellen=['EXPECTED_PUT_CALLS', 'FORBIDDEN', 'README-Rechtetabelle', 'threat-model', 'Store-Text', 'Server-Instruktion'] fehlend=keine
INVENTAR SUMME treffer=416 gate=46 annotation=4 audit=10 kanarie=2 zusage-server=2 zusage-store=3 zusage-doku=47 ungeklaert=0 ausgeschlossen=302
INVENTAR GEGENPROBE nur_muster_2_im_inventar=41 (Stellen, die Muster 1 nicht fand und die trotzdem im Inventar stehen)
INVENTAR gate tests/contract/test_no_destructive_calls.py:86 | FORBIDDEN: dict[str, str] = { | beruehrt_von=MOVE,DELETE | abzuarbeiten_in=Phase 33 | muster=2
INVENTAR gate tests/contract/test_no_destructive_calls.py:142 | CHUNK_ASSEMBLY_MOVE = "nextcloud/clients/dav.py" | beruehrt_von=MOVE | abzuarbeiten_in=Phase 33 | muster=2
INVENTAR gate tests/contract/test_no_destructive_calls.py:480 | EXPECTED_PUT_CALLS = 6 | beruehrt_von=PUT | abzuarbeiten_in=Phase 33 | muster=2
INVENTAR gate tests/contract/test_tool_surface.py:73 | CREATE_TOOLS = { | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 33 | muster=2
INVENTAR gate tests/contract/tool_classes.py:69 | FILE_WRITERS: dict[str, str] = { | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 33 | muster=2
INVENTAR annotation src/mcp_connector/server/__init__.py:79 | destructive_hint=False, | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 33 | muster=1+2
INVENTAR annotation src/mcp_connector/server/__init__.py:86 | destructive_hint=True, | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 33 | muster=1+2
INVENTAR kanarie tests/integration/test_canary.py:89 | MUST_REFUSE = ("files_upload", "notes_create", "talk_send") | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 33 | muster=2
INVENTAR zusage-server src/mcp_connector/server/__init__.py:62 | "Read and create content in the user's own Nextcloud. " | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 34 | muster=1
INVENTAR zusage-server src/mcp_connector/server/__init__.py:63 | "Files are never deleted, moved, renamed or unconditionally overwritten." | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 34 | muster=1
INVENTAR zusage-store appinfo/info.xml:69 | - Nothing destructive: no delete, no move, no share; nothing in the background, no telemetry | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 34 | muster=1
INVENTAR zusage-store appinfo/info.xml:89 | - Nichts Destruktives: kein Löschen, kein Verschieben, kein Teilen; nichts im Hintergrund, keine Telemetrie | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 34 | muster=1
INVENTAR zusage-store appinfo/info.xml:109 | - Rien de destructif : pas de suppression, pas de déplacement, pas de partage ; rien en arrière-plan, pas de télémétrie | beruehrt_von=PUT,MOVE,DELETE | abzuarbeiten_in=Phase 34 | muster=1
E15-KETTE src/mcp_connector/config.py:51 | ENV_FILES_UPDATE = "NC_MCP_FILES_UPDATE"
E15-KETTE src/mcp_connector/config.py:716 | def files_update_enabled(env: Mapping[str, str] | None = None) -> bool:
E15-KETTE src/mcp_connector/config.py:723 | value = (source.get(ENV_FILES_UPDATE) or "").strip().lower()
E15-KETTE src/mcp_connector/config.py:732 | ENV_FILES_UPDATE,
E15-KETTE src/mcp_connector/entry_exapp.py:58 | # tool, and ``files_update`` registers only when ``config.files_update_enabled`` answers
E15-KETTE src/mcp_connector/entry_exapp.py:669 | if config.ENV_FILES_UPDATE in resolved:
E15-KETTE src/mcp_connector/entry_exapp.py:670 | os.environ[config.ENV_FILES_UPDATE] = resolved[config.ENV_FILES_UPDATE]
E15-KETTE src/mcp_connector/exapp/config_values.py:139 | "files_update": config.ENV_FILES_UPDATE,
E15-KETTE src/mcp_connector/exapp/ui/strings.py:802 | #: The form half of ``NC_MCP_FILES_UPDATE``. This is an opt-in write capability: an update
E15-KETTE src/mcp_connector/server/__init__.py:67 | if config.files_update_enabled()
E15-KETTE src/mcp_connector/server/reg_files.py:249 | if config.files_update_enabled():
E15-KETTE appinfo/info.xml:566 | <name>NC_MCP_FILES_UPDATE</name>
E15-KETTE-TEST tests/contract/test_tool_surface.py treffer=2
E15-KETTE-TEST tests/unit/test_config.py treffer=13
E15-KETTE-TEST tests/unit/test_exapp_config_values.py treffer=1
E15-KETTE-TEST tests/unit/test_exapp_entry.py treffer=12
E15-KETTE-TEST tests/unit/test_exapp_env_setup.py treffer=1
E15-KETTE-TEST tests/unit/test_exapp_files_update_switch.py treffer=4
E15-KETTE-TEST tests/unit/test_exapp_lifecycle.py treffer=5
E15-KETTE SUMME quelltext=12 testdateien=7 testtreffer=38 oeffentliche_texte=15 dateien_oeffentlich=['CHANGELOG.md', 'README.de.md', 'README.fr.md', 'README.md', 'appinfo/info.xml', 'docs/client-setup.md', 'docs/hardening.md', 'docs/privacy.md', 'docs/threat-model.md']
```

### 12.6 raw/nc35-verschieben.txt

Lauf vom 2026-11-11, Blöcke nc35-up, controls, move, ui-evaluate-move und nc35-stop in einem Aufruf. Die Messzeilen in der Reihenfolge des Protokolls, ohne die Aufbauzeilen (`SETUP`) und ohne die Rohantworten; die Zeilen `QUELLE` sind die Bestätigung an der Quelle der laufenden Instanz vor dem ersten Aufruf.

```
QUELLE apps/dav/lib/CalDAV/RetentionService.php:18 | public const RETENTION_CONFIG_KEY = 'calendarRetentionObligation';
QUELLE apps/dav/lib/CalDAV/RetentionService.php:19 | private const int DEFAULT_RETENTION_SECONDS = 30 * 24 * 60 * 60;
QUELLE apps/dav/lib/CalDAV/Trashbin/TrashbinHome.php:28 | public const NAME = 'trashbin';
QUELLE apps/dav/lib/CalDAV/Trashbin/DeletedCalendarObjectsCollection.php:26 | public const NAME = 'objects';
QUELLE apps/dav/lib/CalDAV/Trashbin/DeletedCalendarObjectsCollection.php:40 | throw new NotImplemented();
QUELLE apps/dav/lib/CalDAV/Trashbin/DeletedCalendarObjectsCollection.php:111 | public function calendarQuery(array $filters) {
QUELLE apps/dav/lib/CalDAV/Trashbin/RestoreTarget.php:20 | public const NAME = 'restore';
QUELLE apps/dav/lib/CalDAV/Trashbin/RestoreTarget.php:48 | public function moveInto($targetName, $sourcePath, INode $sourceNode): bool {
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:33 | public const PROPERTY_RETENTION_DURATION = '{http://nextcloud.com/ns}trash-bin-retention-duration';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:46 | $this->disableTrashbin = $request->getHeader('X-NC-CalDAV-No-Trashbin') === '1';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:946 | $trashbinDisabled = $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1703 | public function moveCalendarObject(string $sourcePrincipalUri, int $sourceObjectId, string $targetPrincipalUri, int $targetCalendarId, string $tragetObjectUri, int $calendarType = self::CALENDAR_TYPE_CALENDAR): bool {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1768 | public function deleteCalendarObject($calendarId, $objectUri, $calendarType = self::CALENDAR_TYPE_CALENDAR, bool $forceDeletePermanently = false) {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1778 | if ($forceDeletePermanently || $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0') {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1856 | public function restoreCalendarObject(array $objectData): void {
QUELLE apps/dav/lib/CalDAV/CalendarHome.php:111 | $objects[] = new TrashbinHome($this->caldavBackend, $this->principalInfo);
QUELLE apps/dav/lib/CalDAV/CalendarHome.php:164 | return new TrashbinHome($this->caldavBackend, $this->principalInfo);
QUELLE apps/dav/lib/Command/RetentionCleanupCommand.php:21 | parent::__construct('dav:retention:clean-up');
QUELLE occ list dav | dav:retention:clean-up
QUELLE BESTAETIGT schluessel=calendarRetentionObligation standard_sekunden=2592000 aus_wert=0 sammlung=trashbin/objects wiederherstellung=Verschieben nach trashbin/restore/<name> eigenschaft={http://nextcloud.com/ns}trash-bin-retention-duration aufraeumen=occ dav:retention:clean-up
DECK-KALENDER in_der_discovery=ja uri=app-generated--deck--board-65
2026-11-11T16:40:25Z | MOVE eigen auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=5aa17592e862 etag_nachher=5aa17592e862 | inhalt_gleich=ja
ABBRUCHKRITERIUM MESS-06 MOVE ausgeloest=nein grund=keiner
KONTROLLE exapp_impersonation.log, Zeilen der Methode von spike30a: 1
{"reqId":"cFhYVptjRsQibF0cvVsZ","level":2,"time":"2026-11-11T16:40:25+00:00","remoteAddr":"172.30.42.128","user":"spike30a","app":"mcp_connector","method":"MOVE","url":"/remote.php/dav/calendars/spike30a/spike30-a/s30-eigen-164021.ics","scriptName":"/remote.php","message":"impersonation request","userAgent":"python-httpx/0.28.1","version":"35.0.0.10","data":{"app":"mcp_connector"}}
2026-11-11T16:40:25Z | GEGENPROBE eigen auflistung REPORT calendar-query auth=basic nutzer=spike30a in_spike30-a=nein in_spike30-b=ja | datenbank=spike30a/spike30-b/s30-eigen-164021.ics:deleted_at_leer:da0341633dd5 db_gleich_gesendet=ja
2026-11-11T16:40:25Z | GEGENPROBE eigen falsches-secret status=401 datenbank=spike30a/spike30-a/s30-eigen-falsches-secret-164021.ics:deleted_at_leer:0f2fd581fefc | Sabre\DAV\Exception\NotAuthenticated No public access to this resource., AppAPIAuth has not passed, This request is not for a federated calendar, No 'Authorization: Basic' header found. Either the cli
2026-11-11T16:40:26Z | MOVE eigen auth=basic status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=37aacc6ac782 etag_nachher=37aacc6ac782 | inhalt_gleich=ja
MOVE GLEICH appapi_basic=ja appapi=(201, 404, 200, 'ja', True) basic=(201, 404, 200, 'ja', True) (status, quelle danach, ziel danach, uid gleich, inhalt gleich)
2026-11-11T16:40:27Z | PRODUKTIONSWEG MOVE status=201 verschoben=ja nutzer=spike30a datenbank=spike30a/spike30-b/s30-produktion-164021.ics:deleted_at_leer:b0b4556d51cf (aus nc_app_mcp_connector gegen http://caddy, Destination auf http://caddy, Overwrite F; lauf=164021)
2026-11-11T16:40:27Z | MOVE ziel-nur-pfad auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=6d27080af9b7 etag_nachher=6d27080af9b7 | inhalt_gleich=ja destination_basis=(keine, nur Pfad)
2026-11-11T16:40:27Z | MOVE ziel-fremder-host auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=5df513c84dc8 etag_nachher=5df513c84dc8 | inhalt_gleich=ja destination_basis=http://spike30.invalid
2026-11-11T16:40:28Z | MOVE belegt-overwrite-f auth=appapi status=412 quelle_danach=200 ziel_danach=200 uid_gleich=nein etag_vorher=100e358f27b0 etag_nachher=b9c63f0abe75 | inhalt_gleich=nein ueberschrieben=nein altes_ziel=unveraendert quelle_unveraendert=ja Sabre\DAV\Exception\PreconditionFailed The destination node already exists, and the overwrite header is set to false
HASH ziel vorher=spike30a/spike30-b/s30-belegt-overwrite-f-164021.ics:deleted_at_leer:ffab0ee66a48 nachher=spike30a/spike30-b/s30-belegt-overwrite-f-164021.ics:deleted_at_leer:ffab0ee66a48 | quelle vorher=spike30a/spike30-a/s30-belegt-overwrite-f-164021.ics:deleted_at_leer:c3d8eafc4734 nachher=spike30a/spike30-a/s30-belegt-overwrite-f-164021.ics:deleted_at_leer:c3d8eafc4734
2026-11-11T16:40:29Z | MOVE belegt-ohne-kopf auth=appapi status=204 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=d6ff3c8bf3ee etag_nachher=d6ff3c8bf3ee | inhalt_gleich=ja ueberschrieben=ja altes_ziel=papierkorb quelle_unveraendert=nein
HASH ziel vorher=spike30a/spike30-b/s30-belegt-ohne-kopf-164021.ics:deleted_at_leer:61315ea61035 nachher=spike30a/spike30-b/s30-belegt-ohne-kopf-164021-deleted.ics:deleted_at_gesetzt:61315ea61035 | quelle vorher=spike30a/spike30-a/s30-belegt-ohne-kopf-164021.ics:deleted_at_leer:a29150696f89 nachher=spike30a/spike30-b/s30-belegt-ohne-kopf-164021.ics:deleted_at_leer:a29150696f89
2026-11-11T16:40:30Z | MOVE gleiche-uid auth=appapi status=409 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=3dc5a45b4baa etag_nachher=- | inhalt_gleich=nein datenbank_unveraendert=ja OCA\DAV\Exception\UidConflict Calendar object with uid already exists in this calendar collection.
DATENBANK uid=s30-gleiche-uid-164021 vorher=spike30a/spike30-a/s30-gleiche-uid-164021.ics:deleted_at_leer:4ab71018b634,spike30a/spike30-b/s30-gleiche-uid-ziel-164021.ics:deleted_at_leer:2bff0299eb13 nachher=spike30a/spike30-a/s30-gleiche-uid-164021.ics:deleted_at_leer:4ab71018b634,spike30a/spike30-b/s30-gleiche-uid-ziel-164021.ics:deleted_at_leer:2bff0299eb13
2026-11-11T16:40:30Z | GEGENPROBE gleiche-uid auflistung auth=basic nutzer=spike30a spike30-a=['s30-gleiche-uid-164021.ics'] spike30-b=['s30-gleiche-uid-ziel-164021.ics']
2026-11-11T16:40:31Z | MOVE geteilt-rw auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=62145898d076 etag_nachher=62145898d076 | inhalt_gleich=ja ziel=spike30-b-rw_shared_by_spike30b quelle_unveraendert=nein datenbank_nachher=spike30b/spike30-b-rw/s30-geteilt-rw-164021.ics:deleted_at_leer:604857aed7ea
2026-11-11T16:40:31Z | GEGENPROBE geteilt-rw lesen als Eigentuemer nutzer=spike30b auth=basic liste=spike30-b-rw status=200
2026-11-11T16:40:31Z | MOVE geteilt-ro auth=appapi status=404 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=802d38bf8901 etag_nachher=- | inhalt_gleich=nein ziel=spike30-b-ro_shared_by_spike30b quelle_unveraendert=ja datenbank_nachher=spike30a/spike30-a/s30-geteilt-ro-164021.ics:deleted_at_leer:b1137ca0957e Sabre\DAV\Exception\NotFound Calendar with name 'spike30-b-ro_shared_by_spike30b' could not be found
2026-11-11T16:40:31Z | GEGENPROBE geteilt-ro lesen als Eigentuemer nutzer=spike30b auth=basic liste=spike30-b-ro status=404
2026-11-11T16:40:32Z | MOVE deck auth=appapi status=403 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=c39b032e5bc0 etag_nachher=- | inhalt_gleich=nein ziel=app-generated--deck--board-65 quelle_unveraendert=ja datenbank_nachher=spike30a/spike30-a/s30-deck-164021.ics:deleted_at_leer:d0298ad1d8c9 Sabre\DAV\Exception\Forbidden Access denied
2026-11-11T16:40:33Z | MOVE nur-termine auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=9ad966a72ca4 etag_nachher=9ad966a72ca4 | inhalt_gleich=ja ziel=spike30-nur-termine quelle_unveraendert=nein datenbank_nachher=spike30a/spike30-nur-termine/s30-nur-termine-164021.ics:deleted_at_leer:f370e491fe3d
2026-11-11T16:40:33Z | MOVE if-match-aktuell auth=appapi status=201 quelle_danach=404 ziel_danach=200 uid_gleich=ja etag_vorher=b0db695c5f7a etag_nachher=b0db695c5f7a | inhalt_gleich=ja if_match=b0db695c5f7a datenbank_unveraendert=nein auflistung_basic_in_spike30-b=ja
2026-11-11T16:40:34Z | MOVE if-match-veraltet auth=appapi status=412 quelle_danach=200 ziel_danach=404 uid_gleich=- etag_vorher=e322ec2af6ef etag_nachher=- | inhalt_gleich=nein if_match=20a904a9f4ec datenbank_unveraendert=ja auflistung_basic_in_spike30-b=nein Sabre\DAV\Exception\PreconditionFailed An If-Match header was specified, but none of the specified ETags matched.
2026-11-11T16:40:35Z | UNTERAUFGABE server-verschieben ort=spike30-a unveraendert=ja eltern_status=201 eltern_verschoben=ja kind_get=200 kind_etag_vorher=78a77dd363a6 kind_etag_nachher=78a77dd363a6 auth=appapi nutzer=spike30a | datenbank kind vorher=spike30a/spike30-a/s30-kind-verschieben-164021.ics:deleted_at_leer:30ac349154d8 nachher=spike30a/spike30-a/s30-kind-verschieben-164021.ics:deleted_at_leer:30ac349154d8 eltern=spike30a/spike30-b/s30-eltern-verschieben-164021.ics:deleted_at_leer:a5ebb8db1c6f
2026-11-11T16:40:36Z | UNTERAUFGABE server-loeschen vorhanden=ja unveraendert=ja eltern_status=204 eltern_geloescht=ja kind_get=200 kind_etag_vorher=c6f927905036 kind_etag_nachher=c6f927905036 auth=appapi nutzer=spike30a | datenbank kind vorher=spike30a/spike30-a/s30-kind-loeschen-164021.ics:deleted_at_leer:61ffff0bc981 nachher=spike30a/spike30-a/s30-kind-loeschen-164021.ics:deleted_at_leer:61ffff0bc981 eltern=spike30a/spike30-a/s30-eltern-loeschen-164021-deleted.ics:deleted_at_gesetzt:9d57b68b41ab
PAPIERKORB zustand=leer (occ config:app:get dav calendarRetentionObligation; leer heisst Standard, laut Quelle 2592000 Sekunden; auf nc35 wird der Schalter nie veraendert)
2026-11-11T16:40:38Z | DELETE impersonation status=204 auth=appapi nutzer=spike30a if_match=78c0e9fa9584 get_danach=404 |
KONTROLLE exapp_impersonation.log, DELETE-Zeilen von spike30a: 1
{"reqId":"D8O1PCGbYtqmO4kpXwaN","level":2,"time":"2026-11-11T16:40:38+00:00","remoteAddr":"172.30.42.128","user":"spike30a","app":"mcp_connector","method":"DELETE","url":"/remote.php/dav/calendars/spike30a/spike30-a/s30-loeschen-164021.ics","scriptName":"/remote.php","message":"impersonation request","userAgent":"python-httpx/0.28.1","version":"35.0.0.10","data":{"app":"mcp_connector"}}
2026-11-11T16:40:39Z | DELETE veraltet status=412 objekt_unveraendert=ja auth=appapi nutzer=spike30a | datenbank vorher=spike30a/spike30-a/s30-loeschen-veraltet-164021.ics:deleted_at_leer:897af59ad68e nachher=spike30a/spike30-a/s30-loeschen-veraltet-164021.ics:deleted_at_leer:897af59ad68e | Sabre\DAV\Exception\PreconditionFailed An If-Match header was specified, but none of the specified ETags matched.
2026-11-11T16:40:39Z | PAPIERKORB PROPFIND Depth 1 trashbin/objects status=501 | Sabre\DAV\Exception\NotImplemented
2026-11-11T16:40:39Z | PAPIERKORB eintrag=ja name=166.ics eintraege=3 (REPORT calendar-query, auth=appapi nutzer=spike30a) | GEGENPROBE datenbank=spike30a/spike30-a/s30-loeschen-164021-deleted.ics:deleted_at_gesetzt:1e007df35cec
2026-11-11T16:40:39Z | WIEDERHERSTELLUNG status=201 uid_gleich=ja inhalt_gleich=ja get_danach=200 auth=appapi nutzer=spike30a | GEGENPROBE datenbank=spike30a/spike30-a/s30-loeschen-164021.ics:deleted_at_leer:1e007df35cec |
RUECKBAU DECK DELETE boards/65 status=200
RUECKBAU PAPIERKORB spike30a 164.ics endgueltig status=204
RUECKBAU PAPIERKORB spike30a 153.ics endgueltig status=204
RUECKBAU PAPIERKORB spike30a eintraege_vorher=2
RUECKBAU PAPIERKORB spike30b eintraege_vorher=0
APP AUSWERTUNG quelle=raw/ui-a (15 Objekte) und raw/ui-b (15 Objekte), Listen aus den Zeilen UI-OBJEKT in raw/ui-sitzung.txt; nur gelesen, kein Aufruf gegen eine Instanz
APP VERSCHIEBEN eltern=s30 eltern-umzug kind=zieht mit eltern_uid_gleich=ja eltern_ort_danach=spike30-liste-2 kind_ort_danach=spike30-liste-2
APP LOESCHEN eltern=s30 eltern-loeschen kind=kind im papierkorb eltern_ort_danach=trashbin kind_ort_danach=trashbin
APP VERSCHIEBEN einzeln uid_gleich=ja dateiname_gleich=ja inhalt_gleich=ja von=spike30-liste-1 nach=spike30-liste-2 positivkontrolle_umzug_stattgefunden=ja
KONTROLLE unberuehrt differenz=leer ort_gleich=ja
GEGENPROBE objektzahl stand=a {"spike30-liste-1": 15}
GEGENPROBE objektzahl stand=b {"spike30-liste-1": 10, "spike30-liste-2": 3, "trashbin": 2}
RUECKBAU reste_mit_praefix_spike30=keine
RUECKBAU occ app:list groupfolders_vorhanden=nein files_external_an=nein
RUECKBAU deck_boards_mit_praefix_spike30=0 (Tabelle deck_boards, per PHP)
```

Rohantwort zu `MOVE eigen auth=appapi`:

```
HTTP 201 Created
content-length: 0
content-security-policy: default-src 'none';
content-type: text/html; charset=UTF-8
date: Wed, 11 Nov 2026 16:40:25 GMT
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-request-id: cFhYVptjRsQibF0cvVsZ
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(no body)
```

Rohantwort zu `MOVE belegt-overwrite-f`:

```
HTTP 412 Precondition Failed
content-length: 312
content-security-policy: default-src 'none';
content-type: application/xml; charset=utf-8
date: Wed, 11 Nov 2026 16:40:28 GMT
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(body)
<?xml version="1.0" encoding="utf-8"?>
<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
<s:exception>Sabre\DAV\Exception\PreconditionFailed</s:exception>
<s:message>The destination node already exists, and the overwrite header is set to false</s:message>
<s:header>Overwrite</s:header>
</d:error>
```

Rohantwort zu `MOVE belegt-ohne-kopf`:

```
HTTP 204 No Content
content-security-policy: default-src 'none';
date: Wed, 11 Nov 2026 16:40:29 GMT
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-request-id: UfnOTRV011TxGpq8cMdD
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(no body)
```

Rohantwort zu `MOVE geteilt-ro`:

```
HTTP 404 Not Found
content-length: 263
content-security-policy: default-src 'none';
content-type: application/xml; charset=utf-8
date: Wed, 11 Nov 2026 16:40:31 GMT
referrer-policy: no-referrer
server: Apache/2.4.68 (Debian)
via: 1.1 Caddy
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-powered-by: PHP/8.5.9
x-robots-tag: noindex, nofollow
x-user-id: spike30a
(body)
<?xml version="1.0" encoding="utf-8"?>
<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
<s:exception>Sabre\DAV\Exception\NotFound</s:exception>
<s:message>Calendar with name 'spike30-b-ro_shared_by_spike30b' could not be found</s:message>
</d:error>
```

Rückbau: 12 von 12 Zeilen `BASELINE` enden auf `gleich=ja`, keine auf gleich=nein; die vier Container sind gestoppt.

### 12.7 raw/loeschen-32.txt bis raw/loeschen-35.txt

Vier Läufe des Blocks delete-matrix vom 2026-11-11, je Version die Messzeilen in der Reihenfolge des Protokolls, ohne die Aufbauzeilen (`SETUP`) und ohne die Rohantworten. Läufe, die schon am RAM-Tor endeten, haben nichts gemessen und stehen als `RUN FAILED` in der jeweiligen Rohdatei.

Nextcloud 32.0.15 (Rohdatei loeschen-32.txt):

```
VERSION OF RECORD 32.0.15
dbtype: sqlite3
memcache.local: \OC\Memcache\APCu
QUELLE apps/dav/lib/CalDAV/RetentionService.php:17 | public const RETENTION_CONFIG_KEY = 'calendarRetentionObligation';
QUELLE apps/dav/lib/CalDAV/RetentionService.php:18 | private const DEFAULT_RETENTION_SECONDS = 30 * 24 * 60 * 60;
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:32 | public const PROPERTY_RETENTION_DURATION = '{http://nextcloud.com/ns}trash-bin-retention-duration';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:45 | $this->disableTrashbin = $request->getHeader('X-NC-CalDAV-No-Trashbin') === '1';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:121 | return ['nc-calendar-trashbin'];
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:125 | return 'nc-calendar-trashbin';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:941 | $trashbinDisabled = $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1737 | public function deleteCalendarObject($calendarId, $objectUri, $calendarType = self::CALENDAR_TYPE_CALENDAR, bool $forceDeletePermanently = false) {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1747 | if ($forceDeletePermanently || $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0') {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1821 | public function restoreCalendarObject(array $objectData): void {
QUELLE apps/dav/lib/Command/RetentionCleanupCommand.php:20 | parent::__construct('dav:retention:clean-up');
QUELLE occ list dav | dav:retention:clean-up
QUELLE BESTAETIGT schluessel=calendarRetentionObligation standard_sekunden=2592000 aus_wert=0 sammlung=trashbin/objects wiederherstellung=Verschieben nach trashbin/restore/<name> eigenschaft={http://nextcloud.com/ns}trash-bin-retention-duration aufraeumen=occ dav:retention:clean-up
FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden (occ config:app:get dav calendarRetentionObligation; leer heisst Standard; Einheit gelesen aus der Konstante DEFAULT_RETENTION_SECONDS, gemessen im Abschnitt aufraeumen)
2026-11-11T16:56:45Z | LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt | nutzer=alice auth=basic if_match=ja papierkorb_name=7.ics datenbank=alice/spike30-eigen/s30-an-eigen-165644-deleted.ics:deleted_at_gesetzt:3da81d4d68a5
KONTROLLE an-eigen nachbar_im_papierkorb=nein nachbar_lesbar=ja gegriffen=ja
2026-11-11T16:56:45Z | WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja | get_danach=200 sha256_vorher=3da81d4d68a5 sha256_nachher=3da81d4d68a5 db_deleted_at=leer am_alten_ort=ja datenbank=alice/spike30-eigen/s30-an-eigen-165644.ics:deleted_at_leer:3da81d4d68a5
2026-11-11T16:56:46Z | GELOESCHT an-geteilt status=204 nutzer=alice auth=basic if_match=ja papierkorb_von=beide db_deleted_at=gesetzt datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-165644-deleted.ics:deleted_at_gesetzt:addc51e8f9d1
2026-11-11T16:56:46Z | WIEDERHERSTELLUNG an-geteilt versuch=loeschender status=201 uid_gleich=ja inhalt_gleich=ja | nutzer=alice get_als_eigentuemer=200 db_deleted_at=leer datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-165644.ics:deleted_at_leer:addc51e8f9d1
LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender | db_deleted_at_nach_dem_loeschen=gesetzt
2026-11-11T16:56:47Z | WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja | geloescht_von=alice (204) wiederhergestellt_von=bob get_danach=200 datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-eigentuemer-165644.ics:deleted_at_leer:52e695cb202b
2026-11-11T16:56:47Z | LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja | nutzer=alice auth=basic lesen_vorher=200 datenbank=bob/spike30-geteilt-ro/s30-an-geteilt-ro-165644.ics:deleted_at_leer:f52414e9e3fd Sabre\DAV\Exception\NotFound Calendar with name 'spike30-geteilt-ro_shared_by_bob' could not be found
VORABTEST papierkorb-propfind zustand=an wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=an wert=2592000 zeigt=an
VORABTEST frist-eigenschaft-home zustand=an wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=an wert=ja zeigt=an
VORABTEST capabilities-dav zustand=an wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=an wert=ja zeigt=an
2026-11-11T16:56:48Z | UNTERAUFGABE loeschen vorhanden=ja unveraendert=ja eltern_status=204 nutzer=alice auth=basic | datenbank kind=alice/spike30-eigen/s30-kind-165644.ics:deleted_at_leer:22a66f508753 eltern=alice/spike30-eigen/s30-eltern-165644-deleted.ics:deleted_at_gesetzt:3f49e7f6f809
SCHALTER aus occ config:app:set dav calendarRetentionObligation --value=0 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '0', stored as mixed in fast cache
SCHALTER aus occ config:app:get dav calendarRetentionObligation vor_neustart=0 nach_neustart=0 (docker restart nc-spike-tags)
2026-11-11T16:56:52Z | LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | nutzer=alice auth=basic if_match=ja get_danach=404 papierkorb_eintraege=1 datenbank=keine
2026-11-11T16:56:53Z | LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | geloescht_von=alice auth=basic get_als_eigentuemer_danach=404 papierkorb_von=keinem datenbank=keine
VORABTEST papierkorb-propfind zustand=aus wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=aus wert=0 zeigt=aus
VORABTEST frist-eigenschaft-home zustand=aus wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=aus wert=ja zeigt=an
VORABTEST capabilities-dav zustand=aus wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=aus wert=ja zeigt=an
VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft
KONTROLLE vorabtest zustand_am_verhalten_belegt=ja (an: wiederhergestellt=ja, aus: endgueltig geloescht=ja)
SCHALTER standard occ config:app:delete dav calendarRetentionObligation -> Config value calendarRetentionObligation of app dav deleted
SCHALTER standard occ config:app:get dav calendarRetentionObligation vor_neustart=leer nach_neustart=leer (docker restart nc-spike-tags)
2026-11-11T16:57:00Z | AUFRAEUMEN standardfrist geloescht=204 occ dav:retention:clean-up -> (keine Ausgabe) | datenbank vorher=alice/spike30-eigen/s30-frist-165644-deleted.ics:deleted_at_gesetzt:12b470548a20 nachher=alice/spike30-eigen/s30-frist-165644-deleted.ics:deleted_at_gesetzt:12b470548a20
SCHALTER frist-1s occ config:app:set dav calendarRetentionObligation --value=1 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '1', stored as mixed in fast cache
SCHALTER frist-1s occ config:app:get dav calendarRetentionObligation vor_neustart=1 nach_neustart=1 (docker restart nc-spike-tags)
VORABTEST papierkorb-propfind zustand=frist-1s wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=frist-1s wert=1 zeigt=an
VORABTEST frist-eigenschaft-home zustand=frist-1s wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=frist-1s wert=ja zeigt=an
VORABTEST capabilities-dav zustand=frist-1s wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=frist-1s wert=ja zeigt=an
2026-11-11T16:57:08Z | AUFRAEUMEN frist=1 nach 3 s occ dav:retention:clean-up -> (keine Ausgabe) | datenbank nachher=keine
FRIST AUFRAEUMEN standard=bleibt frist_1s=weg
KONTROLLEN {"an-eigen": "ja", "an-geteilt": "ja", "unterauftrag": "ja", "aus-eigen": "ja", "aus-geteilt": "ja", "vorabtest": "ja", "aufraeumen": "ja"} ungemessen=keine
LOESCHEN VERSION 32.0.15 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
ABBAU Container vorhanden: nein
ABBAU Volume vorhanden: nein
DAUER 67 s; ENDE 2026-11-11T16:57:12Z
```

Nextcloud 33.0.9 (Rohdatei loeschen-33.txt):

```
VERSION OF RECORD 33.0.9
dbtype: sqlite3
memcache.local: \OC\Memcache\APCu
QUELLE apps/dav/lib/CalDAV/RetentionService.php:17 | public const RETENTION_CONFIG_KEY = 'calendarRetentionObligation';
QUELLE apps/dav/lib/CalDAV/RetentionService.php:18 | private const DEFAULT_RETENTION_SECONDS = 30 * 24 * 60 * 60;
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:32 | public const PROPERTY_RETENTION_DURATION = '{http://nextcloud.com/ns}trash-bin-retention-duration';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:45 | $this->disableTrashbin = $request->getHeader('X-NC-CalDAV-No-Trashbin') === '1';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:121 | return ['nc-calendar-trashbin'];
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:125 | return 'nc-calendar-trashbin';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:941 | $trashbinDisabled = $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1737 | public function deleteCalendarObject($calendarId, $objectUri, $calendarType = self::CALENDAR_TYPE_CALENDAR, bool $forceDeletePermanently = false) {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1747 | if ($forceDeletePermanently || $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0') {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1821 | public function restoreCalendarObject(array $objectData): void {
QUELLE apps/dav/lib/Command/RetentionCleanupCommand.php:20 | parent::__construct('dav:retention:clean-up');
QUELLE occ list dav | dav:retention:clean-up
QUELLE BESTAETIGT schluessel=calendarRetentionObligation standard_sekunden=2592000 aus_wert=0 sammlung=trashbin/objects wiederherstellung=Verschieben nach trashbin/restore/<name> eigenschaft={http://nextcloud.com/ns}trash-bin-retention-duration aufraeumen=occ dav:retention:clean-up
FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden (occ config:app:get dav calendarRetentionObligation; leer heisst Standard; Einheit gelesen aus der Konstante DEFAULT_RETENTION_SECONDS, gemessen im Abschnitt aufraeumen)
2026-11-11T17:04:43Z | LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt | nutzer=alice auth=basic if_match=ja papierkorb_name=7.ics datenbank=alice/spike30-eigen/s30-an-eigen-170442-deleted.ics:deleted_at_gesetzt:0b9ef0fd9ae3
KONTROLLE an-eigen nachbar_im_papierkorb=nein nachbar_lesbar=ja gegriffen=ja
2026-11-11T17:04:46Z | WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja | get_danach=200 sha256_vorher=0b9ef0fd9ae3 sha256_nachher=0b9ef0fd9ae3 db_deleted_at=leer am_alten_ort=ja datenbank=alice/spike30-eigen/s30-an-eigen-170442.ics:deleted_at_leer:0b9ef0fd9ae3
2026-11-11T17:04:46Z | GELOESCHT an-geteilt status=204 nutzer=alice auth=basic if_match=ja papierkorb_von=beide db_deleted_at=gesetzt datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-170442-deleted.ics:deleted_at_gesetzt:613d8ca35842
2026-11-11T17:04:47Z | WIEDERHERSTELLUNG an-geteilt versuch=loeschender status=201 uid_gleich=ja inhalt_gleich=ja | nutzer=alice get_als_eigentuemer=200 db_deleted_at=leer datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-170442.ics:deleted_at_leer:613d8ca35842
LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender | db_deleted_at_nach_dem_loeschen=gesetzt
2026-11-11T17:04:47Z | WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja | geloescht_von=alice (204) wiederhergestellt_von=bob get_danach=200 datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-eigentuemer-170442.ics:deleted_at_leer:6b0b5a9c2d0c
2026-11-11T17:04:48Z | LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja | nutzer=alice auth=basic lesen_vorher=200 datenbank=bob/spike30-geteilt-ro/s30-an-geteilt-ro-170442.ics:deleted_at_leer:4dee74d3117a Sabre\DAV\Exception\NotFound Calendar with name 'spike30-geteilt-ro_shared_by_bob' could not be found
VORABTEST papierkorb-propfind zustand=an wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=an wert=2592000 zeigt=an
VORABTEST frist-eigenschaft-home zustand=an wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=an wert=ja zeigt=an
VORABTEST capabilities-dav zustand=an wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=an wert=ja zeigt=an
2026-11-11T17:04:49Z | UNTERAUFGABE loeschen vorhanden=ja unveraendert=ja eltern_status=204 nutzer=alice auth=basic | datenbank kind=alice/spike30-eigen/s30-kind-170442.ics:deleted_at_leer:4eccb10b508e eltern=alice/spike30-eigen/s30-eltern-170442-deleted.ics:deleted_at_gesetzt:979afbd6b46d
SCHALTER aus occ config:app:set dav calendarRetentionObligation --value=0 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '0', stored as mixed in fast cache
SCHALTER aus occ config:app:get dav calendarRetentionObligation vor_neustart=0 nach_neustart=0 (docker restart nc-spike-tags)
2026-11-11T17:04:55Z | LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | nutzer=alice auth=basic if_match=ja get_danach=404 papierkorb_eintraege=1 datenbank=keine
2026-11-11T17:04:56Z | LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | geloescht_von=alice auth=basic get_als_eigentuemer_danach=404 papierkorb_von=keinem datenbank=keine
VORABTEST papierkorb-propfind zustand=aus wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=aus wert=0 zeigt=aus
VORABTEST frist-eigenschaft-home zustand=aus wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=aus wert=ja zeigt=an
VORABTEST capabilities-dav zustand=aus wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=aus wert=ja zeigt=an
VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft
KONTROLLE vorabtest zustand_am_verhalten_belegt=ja (an: wiederhergestellt=ja, aus: endgueltig geloescht=ja)
SCHALTER standard occ config:app:delete dav calendarRetentionObligation -> Config value calendarRetentionObligation of app dav deleted
SCHALTER standard occ config:app:get dav calendarRetentionObligation vor_neustart=leer nach_neustart=leer (docker restart nc-spike-tags)
2026-11-11T17:05:01Z | AUFRAEUMEN standardfrist geloescht=204 occ dav:retention:clean-up -> (keine Ausgabe) | datenbank vorher=alice/spike30-eigen/s30-frist-170442-deleted.ics:deleted_at_gesetzt:999f08d14b61 nachher=alice/spike30-eigen/s30-frist-170442-deleted.ics:deleted_at_gesetzt:999f08d14b61
SCHALTER frist-1s occ config:app:set dav calendarRetentionObligation --value=1 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '1', stored as mixed in fast cache
SCHALTER frist-1s occ config:app:get dav calendarRetentionObligation vor_neustart=1 nach_neustart=1 (docker restart nc-spike-tags)
VORABTEST papierkorb-propfind zustand=frist-1s wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=frist-1s wert=1 zeigt=an
VORABTEST frist-eigenschaft-home zustand=frist-1s wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=frist-1s wert=ja zeigt=an
VORABTEST capabilities-dav zustand=frist-1s wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=frist-1s wert=ja zeigt=an
2026-11-11T17:05:10Z | AUFRAEUMEN frist=1 nach 3 s occ dav:retention:clean-up -> (keine Ausgabe) | datenbank nachher=keine
FRIST AUFRAEUMEN standard=bleibt frist_1s=weg
KONTROLLEN {"an-eigen": "ja", "an-geteilt": "ja", "unterauftrag": "ja", "aus-eigen": "ja", "aus-geteilt": "ja", "vorabtest": "ja", "aufraeumen": "ja"} ungemessen=keine
LOESCHEN VERSION 33.0.9 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
ABBAU Container vorhanden: nein
ABBAU Volume vorhanden: nein
DAUER 73 s; ENDE 2026-11-11T17:05:17Z
```

Nextcloud 34.0.4 (Rohdatei loeschen-34.txt):

```
VERSION OF RECORD 34.0.4
dbtype: sqlite3
memcache.local: \OC\Memcache\APCu
QUELLE apps/dav/lib/CalDAV/RetentionService.php:17 | public const RETENTION_CONFIG_KEY = 'calendarRetentionObligation';
QUELLE apps/dav/lib/CalDAV/RetentionService.php:18 | private const DEFAULT_RETENTION_SECONDS = 30 * 24 * 60 * 60;
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:32 | public const PROPERTY_RETENTION_DURATION = '{http://nextcloud.com/ns}trash-bin-retention-duration';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:45 | $this->disableTrashbin = $request->getHeader('X-NC-CalDAV-No-Trashbin') === '1';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:123 | return ['nc-calendar-trashbin'];
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:128 | return 'nc-calendar-trashbin';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:947 | $trashbinDisabled = $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1769 | public function deleteCalendarObject($calendarId, $objectUri, $calendarType = self::CALENDAR_TYPE_CALENDAR, bool $forceDeletePermanently = false) {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1779 | if ($forceDeletePermanently || $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0') {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1853 | public function restoreCalendarObject(array $objectData): void {
QUELLE apps/dav/lib/Command/RetentionCleanupCommand.php:20 | parent::__construct('dav:retention:clean-up');
QUELLE occ list dav | dav:retention:clean-up
QUELLE BESTAETIGT schluessel=calendarRetentionObligation standard_sekunden=2592000 aus_wert=0 sammlung=trashbin/objects wiederherstellung=Verschieben nach trashbin/restore/<name> eigenschaft={http://nextcloud.com/ns}trash-bin-retention-duration aufraeumen=occ dav:retention:clean-up
FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden (occ config:app:get dav calendarRetentionObligation; leer heisst Standard; Einheit gelesen aus der Konstante DEFAULT_RETENTION_SECONDS, gemessen im Abschnitt aufraeumen)
2026-11-11T17:15:56Z | LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt | nutzer=alice auth=basic if_match=ja papierkorb_name=3.ics datenbank=alice/spike30-eigen/s30-an-eigen-171554-deleted.ics:deleted_at_gesetzt:c645213b7f99
KONTROLLE an-eigen nachbar_im_papierkorb=nein nachbar_lesbar=ja gegriffen=ja
2026-11-11T17:15:56Z | WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja | get_danach=200 sha256_vorher=c645213b7f99 sha256_nachher=c645213b7f99 db_deleted_at=leer am_alten_ort=ja datenbank=alice/spike30-eigen/s30-an-eigen-171554.ics:deleted_at_leer:c645213b7f99
2026-11-11T17:15:57Z | GELOESCHT an-geteilt status=204 nutzer=alice auth=basic if_match=ja papierkorb_von=beide db_deleted_at=gesetzt datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-171554-deleted.ics:deleted_at_gesetzt:0dbc8d3c9507
2026-11-11T17:15:57Z | WIEDERHERSTELLUNG an-geteilt versuch=loeschender status=201 uid_gleich=ja inhalt_gleich=ja | nutzer=alice get_als_eigentuemer=200 db_deleted_at=leer datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-171554.ics:deleted_at_leer:0dbc8d3c9507
LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender | db_deleted_at_nach_dem_loeschen=gesetzt
2026-11-11T17:15:58Z | WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja | geloescht_von=alice (204) wiederhergestellt_von=bob get_danach=200 datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-eigentuemer-171554.ics:deleted_at_leer:5e6e6ab2886c
2026-11-11T17:15:58Z | LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja | nutzer=alice auth=basic lesen_vorher=200 datenbank=bob/spike30-geteilt-ro/s30-an-geteilt-ro-171554.ics:deleted_at_leer:d4732f04a995 Sabre\DAV\Exception\NotFound Calendar with name 'spike30-geteilt-ro_shared_by_bob' could not be found
VORABTEST papierkorb-propfind zustand=an wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=an wert=2592000 zeigt=an
VORABTEST frist-eigenschaft-home zustand=an wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=an wert=ja zeigt=an
VORABTEST capabilities-dav zustand=an wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=an wert=ja zeigt=an
2026-11-11T17:16:03Z | UNTERAUFGABE loeschen vorhanden=ja unveraendert=ja eltern_status=204 nutzer=alice auth=basic | datenbank kind=alice/spike30-eigen/s30-kind-171554.ics:deleted_at_leer:e697172612f0 eltern=alice/spike30-eigen/s30-eltern-171554-deleted.ics:deleted_at_gesetzt:36df225862c2
SCHALTER aus occ config:app:set dav calendarRetentionObligation --value=0 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '0', stored as mixed in fast cache
SCHALTER aus occ config:app:get dav calendarRetentionObligation vor_neustart=0 nach_neustart=0 (docker restart nc-spike-tags)
2026-11-11T17:16:07Z | LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | nutzer=alice auth=basic if_match=ja get_danach=404 papierkorb_eintraege=1 datenbank=keine
2026-11-11T17:16:07Z | LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | geloescht_von=alice auth=basic get_als_eigentuemer_danach=404 papierkorb_von=keinem datenbank=keine
VORABTEST papierkorb-propfind zustand=aus wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=aus wert=0 zeigt=aus
VORABTEST frist-eigenschaft-home zustand=aus wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=aus wert=ja zeigt=an
VORABTEST capabilities-dav zustand=aus wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=aus wert=ja zeigt=an
VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft
KONTROLLE vorabtest zustand_am_verhalten_belegt=ja (an: wiederhergestellt=ja, aus: endgueltig geloescht=ja)
SCHALTER standard occ config:app:delete dav calendarRetentionObligation -> Config value calendarRetentionObligation of app dav deleted
SCHALTER standard occ config:app:get dav calendarRetentionObligation vor_neustart=leer nach_neustart=leer (docker restart nc-spike-tags)
2026-11-11T17:16:14Z | AUFRAEUMEN standardfrist geloescht=204 occ dav:retention:clean-up -> (keine Ausgabe) | datenbank vorher=alice/spike30-eigen/s30-frist-171554-deleted.ics:deleted_at_gesetzt:68630f488585 nachher=alice/spike30-eigen/s30-frist-171554-deleted.ics:deleted_at_gesetzt:68630f488585
SCHALTER frist-1s occ config:app:set dav calendarRetentionObligation --value=1 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '1', stored as mixed in fast cache
SCHALTER frist-1s occ config:app:get dav calendarRetentionObligation vor_neustart=1 nach_neustart=1 (docker restart nc-spike-tags)
VORABTEST papierkorb-propfind zustand=frist-1s wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=frist-1s wert=1 zeigt=an
VORABTEST frist-eigenschaft-home zustand=frist-1s wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=frist-1s wert=ja zeigt=an
VORABTEST capabilities-dav zustand=frist-1s wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=frist-1s wert=ja zeigt=an
2026-11-11T17:16:23Z | AUFRAEUMEN frist=1 nach 3 s occ dav:retention:clean-up -> (keine Ausgabe) | datenbank nachher=keine
FRIST AUFRAEUMEN standard=bleibt frist_1s=weg
KONTROLLEN {"an-eigen": "ja", "an-geteilt": "ja", "unterauftrag": "ja", "aus-eigen": "ja", "aus-geteilt": "ja", "vorabtest": "ja", "aufraeumen": "ja"} ungemessen=keine
LOESCHEN VERSION 34.0.4 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
ABBAU Container vorhanden: nein
ABBAU Volume vorhanden: nein
DAUER 76 s; ENDE 2026-11-11T17:16:28Z
```

Nextcloud 35.0.2 (Rohdatei loeschen-35.txt):

```
VERSION OF RECORD 35.0.2
dbtype: sqlite3
memcache.local: \OC\Memcache\APCu
QUELLE apps/dav/lib/CalDAV/RetentionService.php:18 | public const RETENTION_CONFIG_KEY = 'calendarRetentionObligation';
QUELLE apps/dav/lib/CalDAV/RetentionService.php:19 | private const int DEFAULT_RETENTION_SECONDS = 30 * 24 * 60 * 60;
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:33 | public const PROPERTY_RETENTION_DURATION = '{http://nextcloud.com/ns}trash-bin-retention-duration';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:46 | $this->disableTrashbin = $request->getHeader('X-NC-CalDAV-No-Trashbin') === '1';
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:124 | return ['nc-calendar-trashbin'];
QUELLE apps/dav/lib/CalDAV/Trashbin/Plugin.php:129 | return 'nc-calendar-trashbin';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:946 | $trashbinDisabled = $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0';
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1768 | public function deleteCalendarObject($calendarId, $objectUri, $calendarType = self::CALENDAR_TYPE_CALENDAR, bool $forceDeletePermanently = false) {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1778 | if ($forceDeletePermanently || $this->config->getAppValue(Application::APP_ID, RetentionService::RETENTION_CONFIG_KEY) === '0') {
QUELLE apps/dav/lib/CalDAV/CalDavBackend.php:1856 | public function restoreCalendarObject(array $objectData): void {
QUELLE apps/dav/lib/Command/RetentionCleanupCommand.php:21 | parent::__construct('dav:retention:clean-up');
QUELLE occ list dav | dav:retention:clean-up
QUELLE BESTAETIGT schluessel=calendarRetentionObligation standard_sekunden=2592000 aus_wert=0 sammlung=trashbin/objects wiederherstellung=Verschieben nach trashbin/restore/<name> eigenschaft={http://nextcloud.com/ns}trash-bin-retention-duration aufraeumen=occ dav:retention:clean-up
FRIST konfiguriert=leer standard_laut_quelle=2592000 einheit=Sekunden (occ config:app:get dav calendarRetentionObligation; leer heisst Standard; Einheit gelesen aus der Konstante DEFAULT_RETENTION_SECONDS, gemessen im Abschnitt aufraeumen)
2026-11-11T17:27:23Z | LOESCHEN an-eigen status=204 im_papierkorb=ja db_deleted_at=gesetzt | nutzer=alice auth=basic if_match=ja papierkorb_name=3.ics datenbank=alice/spike30-eigen/s30-an-eigen-172721-deleted.ics:deleted_at_gesetzt:43760fa09c9b
KONTROLLE an-eigen nachbar_im_papierkorb=nein nachbar_lesbar=ja gegriffen=ja
2026-11-11T17:27:23Z | WIEDERHERSTELLUNG an-eigen status=201 uid_gleich=ja inhalt_gleich=ja | get_danach=200 sha256_vorher=43760fa09c9b sha256_nachher=43760fa09c9b db_deleted_at=leer am_alten_ort=ja datenbank=alice/spike30-eigen/s30-an-eigen-172721.ics:deleted_at_leer:43760fa09c9b
2026-11-11T17:27:24Z | GELOESCHT an-geteilt status=204 nutzer=alice auth=basic if_match=ja papierkorb_von=beide db_deleted_at=gesetzt datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-172721-deleted.ics:deleted_at_gesetzt:1040e8a23149
2026-11-11T17:27:25Z | WIEDERHERSTELLUNG an-geteilt versuch=loeschender status=201 uid_gleich=ja inhalt_gleich=ja | nutzer=alice get_als_eigentuemer=200 db_deleted_at=leer datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-172721.ics:deleted_at_leer:1040e8a23149
LOESCHEN an-geteilt status=204 papierkorb_von=beide wiederhergestellt_durch=loeschender | db_deleted_at_nach_dem_loeschen=gesetzt
2026-11-11T17:27:25Z | WIEDERHERSTELLUNG an-geteilt-eigentuemer status=201 uid_gleich=ja inhalt_gleich=ja | geloescht_von=alice (204) wiederhergestellt_von=bob get_danach=200 datenbank=bob/spike30-geteilt-rw/s30-an-geteilt-eigentuemer-172721.ics:deleted_at_leer:edf9edc5d065
2026-11-11T17:27:26Z | LOESCHEN an-geteilt-ro status=404 objekt_unveraendert=ja | nutzer=alice auth=basic lesen_vorher=200 datenbank=bob/spike30-geteilt-ro/s30-an-geteilt-ro-172721.ics:deleted_at_leer:58c6ca0c259c Sabre\DAV\Exception\NotFound Calendar with name 'spike30-geteilt-ro_shared_by_bob' could not be found
VORABTEST papierkorb-propfind zustand=an wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=an wert=2592000 zeigt=an
VORABTEST frist-eigenschaft-home zustand=an wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=an wert=ja zeigt=an
VORABTEST capabilities-dav zustand=an wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=an wert=ja zeigt=an
2026-11-11T17:27:27Z | UNTERAUFGABE loeschen vorhanden=ja unveraendert=ja eltern_status=204 nutzer=alice auth=basic | datenbank kind=alice/spike30-eigen/s30-kind-172721.ics:deleted_at_leer:31cc70d664c1 eltern=alice/spike30-eigen/s30-eltern-172721-deleted.ics:deleted_at_gesetzt:13b84850a376
SCHALTER aus occ config:app:set dav calendarRetentionObligation --value=0 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '0', stored as mixed in fast cache
SCHALTER aus occ config:app:get dav calendarRetentionObligation vor_neustart=0 nach_neustart=0 (docker restart nc-spike-tags)
2026-11-11T17:27:32Z | LOESCHEN aus-eigen status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | nutzer=alice auth=basic if_match=ja get_danach=404 papierkorb_eintraege=1 datenbank=keine
2026-11-11T17:27:33Z | LOESCHEN aus-geteilt status=204 im_papierkorb=nein db_zeile=weg wiederherstellung=nicht moeglich | geloescht_von=alice auth=basic get_als_eigentuemer_danach=404 papierkorb_von=keinem datenbank=keine
VORABTEST papierkorb-propfind zustand=aus wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=aus wert=0 zeigt=aus
VORABTEST frist-eigenschaft-home zustand=aus wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=aus wert=ja zeigt=an
VORABTEST capabilities-dav zustand=aus wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=aus wert=ja zeigt=an
VORABTEST ERGEBNIS unterscheidet=ja kandidat=frist-eigenschaft
KONTROLLE vorabtest zustand_am_verhalten_belegt=ja (an: wiederhergestellt=ja, aus: endgueltig geloescht=ja)
SCHALTER standard occ config:app:delete dav calendarRetentionObligation -> Config value calendarRetentionObligation of app dav deleted
SCHALTER standard occ config:app:get dav calendarRetentionObligation vor_neustart=leer nach_neustart=leer (docker restart nc-spike-tags)
2026-11-11T17:27:40Z | AUFRAEUMEN standardfrist geloescht=204 occ dav:retention:clean-up -> (keine Ausgabe) | datenbank vorher=alice/spike30-eigen/s30-frist-172721-deleted.ics:deleted_at_gesetzt:3fb26d28d35a nachher=alice/spike30-eigen/s30-frist-172721-deleted.ics:deleted_at_gesetzt:3fb26d28d35a
SCHALTER frist-1s occ config:app:set dav calendarRetentionObligation --value=1 -> Config value 'calendarRetentionObligation' for app 'dav' is now set to '1', stored as mixed in fast cache
SCHALTER frist-1s occ config:app:get dav calendarRetentionObligation vor_neustart=1 nach_neustart=1 (docker restart nc-spike-tags)
VORABTEST papierkorb-propfind zustand=frist-1s wert=207 zeigt=an
VORABTEST frist-eigenschaft zustand=frist-1s wert=1 zeigt=an
VORABTEST frist-eigenschaft-home zustand=frist-1s wert=fehlt zeigt=unklar
VORABTEST home-kind-trashbin zustand=frist-1s wert=ja zeigt=an
VORABTEST capabilities-dav zustand=frist-1s wert={"absence-replacement": true, "absence-supported": true, "bulkupload": "1.0", "chunking": "1.0", "public_shares_chunking": true, "search_supports_creation_time": true, "search_supports_last_activity": true, "search_supports_upload_time": true} zeigt=unklar
VORABTEST dav-kopf zustand=frist-1s wert=ja zeigt=an
2026-11-11T17:27:48Z | AUFRAEUMEN frist=1 nach 3 s occ dav:retention:clean-up -> (keine Ausgabe) | datenbank nachher=keine
FRIST AUFRAEUMEN standard=bleibt frist_1s=weg
KONTROLLEN {"an-eigen": "ja", "an-geteilt": "ja", "unterauftrag": "ja", "aus-eigen": "ja", "aus-geteilt": "ja", "vorabtest": "ja", "aufraeumen": "ja"} ungemessen=keine
LOESCHEN VERSION 35.0.2 g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender
ABBAU Container vorhanden: nein
ABBAU Volume vorhanden: nein
DAUER 69 s; ENDE 2026-11-11T17:27:52Z
```

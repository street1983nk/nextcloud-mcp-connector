# Mess-Spike Aufgaben und Ordner (MESS-01 bis MESS-06)

**Status:** läuft. Die Abschnitte 1 (MESS-01) und 2 (MESS-02) sind gemessen, das Abbruchkriterium zu MESS-01 ist nicht ausgelöst; die Abschnitte 3 bis 10 sind offen
**Messzeitraum:** ab 2026-11-11 (erster Messlauf 11:55 UTC), Ende offen
**Nextcloud:** 35.0.0 (Build 35.0.0.10), gelesen mit `occ status` am 2026-11-11 aus dem laufenden Container `nc35-nc`. Das Image heißt `nextcloud:35.0.0-apache-local` und ist lokal aus dem veröffentlichten Quellpaket gebaut (`compose.nc35.yml`, Kopfkommentar)
**AppAPI:** `app_api` 35.0.0, gelesen mit `occ app:list --output=json` derselben Instanz am 2026-11-11
**Diese ExApp:** 0.3.2, gelesen mit `occ app_api:app:list` am 2026-11-11. In der Topologie ist also ein älterer Stand registriert als der Arbeitsbaum. Für die Messung zählt das an zwei Stellen: die Impersonation läuft mit dem Secret dieser Registrierung, und der Produktionsweg (Abschnitt 1.2) läuft im Container dieses Images. Kein Werkzeug der App wird gemessen, nur ihr Zugang zu Nextcloud
**groupfolders:** 23.0.1, gelesen mit `occ app:list --output=json` am 2026-11-11 nach `occ app:install groupfolders` in der laufenden Instanz (Protokollzeile `GRUPPENORDNER version=23.0.1 installiert_vorher=nein (gelesen mit occ app:list --output=json)`). Die App wurde für die Messung aus dem App Store geladen und danach wieder entfernt. `files_external` 2.0.0-dev.0 gehört zum Server und war nur für die Messung eingeschaltet
**Tasks:** offen, füllt Plan 30-02
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

Offen, füllt Plan 30-02.

## 4. Verschieben und Löschen (MESS-06)

Offen, füllt Plan 30-03.

## 5. Discovery und Objekte (MESS-03)

Offen, füllt Plan 30-04.

## 6. Kosten der Aufgabensuche (MESS-04)

Offen, füllt Plan 30-04.

## 7. Inventar der Gates und Zusagen (A17)

Offen, füllt Plan 30-02.

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

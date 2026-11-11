# Mess-Spike Aufgaben und Ordner (MESS-01 bis MESS-06)

**Status:** läuft. Die Kriterien stehen, es gibt noch keinen Messwert; dieser Stand ist mit Absicht vor der ersten Messung festgeschrieben
**Messzeitraum:** offen, füllt Plan 30-01 mit dem ersten Messlauf
**Nextcloud:** offen, füllt Plan 30-01 (gelesen mit `occ status` aus der laufenden Instanz)
**AppAPI:** offen, füllt Plan 30-01 (gelesen mit `occ app:list` derselben Instanz)
**Diese ExApp:** offen, füllt Plan 30-01 (gelesen mit `occ app_api:app:list`)
**groupfolders:** offen, füllt Plan 30-01 (gelesen mit `occ app:list` nach der Installation in der Instanz)
**Tasks:** offen, füllt Plan 30-02
**Deck:** offen, füllt Plan 30-04
**Datenbank:** offen, füllt Plan 30-01 (gelesen mit `occ config:system:get dbtype`)
**Topologie:** die vorhandene Strecke `compose.nc35.yml` (Container `nc35-nc`, `nc35-harp`, `nc35-caddy`, ExApp-Container `nc_app_mcp_connector`, Loopback `http://127.0.0.1:8082`). Sie wird nur mit `docker start` und `docker stop` bewegt, nie abgebaut. Weitere Instanzen für die Versionsbreite nennen die Pläne 30-03 und 30-04
**Messskript:** `scripts/tasks_spike.py`; der Commit, der das Skript zusammen mit diesen Kriterien festschreibt, liegt vor jeder Rohdatei unter `.planning/phases/30-mess-spike-aufgaben-und-ordner/raw/`. Sein Hash wird mit dem ersten Messlauf nachgetragen
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

## 1. MKCOL unter AppAPI-Impersonation (MESS-01)

Offen, füllt Plan 30-01.

## 2. Gruppenordner mit ACL und externer Speicher (MESS-02)

Offen, füllt Plan 30-01.

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

Offen. Jeder Plan trägt hier seine Ungemessen-Zeilen mit Grund ein.

## 12. Rohausgaben

Offen. Jede in diesem Abschnitt in Backticks oder in einem Codeblock zitierte Protokollzeile steht wörtlich in einer Rohdatei des Phasenordners (Unterordner raw); das Messskript prüft das im Block secret-scan. Deshalb steht in diesem Abschnitt nichts anderes in Backticks als Zitate aus den Rohdateien.

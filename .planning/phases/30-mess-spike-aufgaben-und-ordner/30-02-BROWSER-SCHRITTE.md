# Plan 30-02, Task 2: Browser-Sitzung in der Tasks-App

Zwölf Schritte in zwei Runden, dazwischen ein Zwischenstand per DAV. Die Sitzung fährt die Hauptsitzung mit Playwright (oder der Owner von Hand). Der Executor von Plan 30-02 hat sie vorbereitet und führt keinen dieser Schritte selbst aus.

## Stand der Vorbereitung (2026-11-11)

| Punkt | Wert | Woher |
|-------|------|-------|
| Instanz | nc35 läuft, `http://127.0.0.1:8082`, Nextcloud 35.0.0, SQLite | `GET /status.php` 200, `occ status` |
| Tasks-App | 0.18.1, vor dem Lauf nicht installiert, aus dem App Store geladen | `occ app:list --output=json`, Protokollzeile `TASKS-APP version=0.18.1 installiert_vorher=nein` in `raw/nc35-aendern.txt` |
| Messkonto | `spike30ui`, nur für diese Messung angelegt, ohne Gruppen | `occ user:add`, `occ user:info` |
| Zugangsdaten | Datei außerhalb des Repositorys, drei Zeilen: Benutzername, Passwort, Basis-URL | den Pfad nennt der Bericht des Executors; das Passwort steht in keiner Datei des Repositorys |
| Sprache des Kontos | Deutsch (`core lang de`, `core locale de_DE`) | von Hand mit `occ user:setting` gesetzt, damit die Beschriftungen unten stimmen |
| Kommando des Zwischenstands | zweimal gegen das noch leere Konto geprobt, Exit 0, `UI-STAND a objekte=0`; die Ausgabe ging in eine Datei außerhalb des Repositorys, `raw/ui-sitzung.txt` existiert noch nicht | Probeläufe des Executors; sie haben dem Konto zwei weitere App-Passwörter hinterlassen, die mit dem Konto fallen |
| Listen des Kontos | keine: `occ dav:list-calendars spike30ui` meldet "has no calendars" | die beiden Listen der Messung legt Schritt 1 in der App an, siehe Hinweis |

Hinweis zu den Listen: Die beiden Listen `spike30-liste-1` und `spike30-liste-2` sind mit Absicht nicht vorab per Skript angelegt. Sie sind selbst Messgegenstand: Plan 30-04 wertet aus, wie eine von der Tasks-App angelegte Liste in der Discovery aussieht (A2, A3). Eine per `MKCALENDAR` vorbereitete Liste wäre keine von der App geschriebene Fixture. Nach der ersten Anmeldung legt Nextcloud dem Konto voraussichtlich selbst einen Standardkalender an (nicht gemessen, aus dem Verhalten anderer Konten der Instanz geschlossen); er wird in der Sitzung nicht benutzt.

Die Beschriftungen in Anführungszeichen stammen aus der deutschen Sprachdatei der installierten App (`custom_apps/tasks/l10n/de.json`, gelesen, nicht in der Oberfläche gesehen). Weicht die Oberfläche ab, zählt die Oberfläche; die Abweichung gehört in die Rückmeldung.

## Regeln für die Sitzung

- Die Aufgabennamen wörtlich übernehmen, klein geschrieben, mit dem Leerzeichen nach `s30`. Das Skript findet die Objekte über den Namen.
- Nichts raten und nichts ersetzen. Scheitert ein Schritt, die Fehlermeldung im Wortlaut notieren und anhalten.
- Runde B beginnt erst, wenn das Kommando des Zwischenstands die Zeile `UI-STAND a objekte=<n>` mit mindestens 14 Objekten gedruckt hat und keine Zeile `UI-FEHLT` erscheint.
- Zwischen zwei Schritten kurz warten, bis die App gespeichert hat (kein drehendes Symbol mehr am Eintrag). Die App schreibt jede Änderung sofort per CalDAV.
- Für die Rückmeldung notieren: die Zeitzone des Browsers, den Weg bei Schritt 5, 8 und 10, jede Rückfrage der App im Wortlaut samt gewählter Antwort, jede Abweichung von dieser Liste.

## Anmeldung (vor Schritt 1)

- Adresse: `http://127.0.0.1:8082/login`
- Eingeben: Benutzername und Passwort aus der Zugangsdatei (Zeile 1 und Zeile 2), dann anmelden.
- Danach sichtbar: die Startseite von Nextcloud. Zeigt sich ein Begrüßungsdialog (Erste-Schritte-Assistent), ihn schließen.
- Dann die Adresse `http://127.0.0.1:8082/apps/tasks/` öffnen. Sichtbar: die App "Aufgaben" mit der linken Leiste (Sammlungen wie "Alle", "Aktuell", darunter die Listen) und dem Eintrag "Liste hinzufügen …".

## Runde A: nur anlegen, nichts abhaken

### Schritt 1: zwei Listen anlegen

- Adresse: `http://127.0.0.1:8082/apps/tasks/`
- Klicken: in der linken Leiste "Liste hinzufügen …". Eingeben in das Feld "Neue Liste": `spike30-liste-1`, mit der Eingabetaste oder dem Haken bestätigen. Dasselbe noch einmal mit `spike30-liste-2`.
- Danach sichtbar: beide Listen in der linken Leiste, je mit dem Zähler 0.

### Schritt 2: fünf Aufgaben mit Eigenschaften in spike30-liste-1

- Adresse: in der linken Leiste `spike30-liste-1` anklicken (die Adresse wechselt auf `http://127.0.0.1:8082/apps/tasks/calendars/<kennung der liste>`; die Kennung vergibt die App).
- Anlegen: oben in das Feld "Eine Aufgabe zu "spike30-liste-1" hinzufügen…" den Namen schreiben und mit der Eingabetaste bestätigen. Eine angelegte Aufgabe anklicken öffnet rechts die Detailansicht.
- `s30 ganztag`: in der Detailansicht "Fälligkeitsdatum setzen" anklicken, den 20.11.2026 wählen, "Ganztägig" einschalten.
- `s30 uhrzeit`: "Fälligkeitsdatum setzen" auf den 20.11.2026 um 10:15 Uhr, "Startdatum setzen" auf den 19.11.2026 um 09:00 Uhr, "Ganztägig" bleibt aus.
- `s30 tags`: unter "Schlagworte auswählen" die zwei Schlagworte `spike30` und `wichtig` neu anlegen ("Dies als neues Schlagwort hinzufügen"); die Priorität auf hoch stellen (angezeigt als "Priorität 1: hoch" bis "Priorität 4: hoch"; den höchsten Wert wählen, den die Oberfläche anbietet, und ihn notieren).
- `s30 notiz`: im Reiter "Notizen" ("Hier klicken, um eine Notiz hinzuzufügen.") zwei Zeilen eingeben: `erste zeile` und darunter `zweite zeile`.
- `s30 unberuehrt`: nur anlegen, nichts weiter.
- Danach sichtbar: fünf Aufgaben in der Liste; `s30 ganztag` und `s30 uhrzeit` zeigen ein Fälligkeitsdatum, `s30 tags` zeigt beide Schlagworte, `s30 notiz` das Notiz-Symbol ("Aufgabe hat eine Notiz").

### Schritt 3: drei Elternaufgaben mit je einer Unteraufgabe

- Adresse: weiter in `spike30-liste-1`.
- `s30 eltern-abhaken` anlegen. Im Menü der Aufgabe (drei Punkte am Eintrag) "Teilaufgabe hinzufügen" wählen und in das Feld "Eine Unteraufgabe zu "s30 eltern-abhaken" hinzufügen …" den Namen `s30 kind-abhaken` schreiben, Eingabetaste.
- Ebenso `s30 eltern-umzug` mit der Unteraufgabe `s30 kind-umzug` und `s30 eltern-loeschen` mit der Unteraufgabe `s30 kind-loeschen`.
- Danach sichtbar: jede der drei Elternaufgaben zeigt ihre Unteraufgabe eingerückt darunter.

### Schritt 4: drei einfache Aufgaben

- Adresse: weiter in `spike30-liste-1`.
- Anlegen, ohne weitere Angaben: `s30 abhaken`, `s30 wieder-oeffnen`, `s30 umzug-einzeln`.
- Danach sichtbar: die Liste zeigt jetzt vierzehn Aufgaben (elf auf der obersten Ebene, drei Unteraufgaben).

### Schritt 5: wiederkehrende Aufgabe

- Adresse: weiter in `spike30-liste-1`.
- `s30 wiederkehrend` anlegen, in der Detailansicht die Wiederholung öffnen ("Aufgabe wiederholen", Vorgabe "Wiederholt sich nicht") und "Täglich" wählen, speichern. Verlangt die App dafür erst ein Fälligkeits- oder Startdatum, den 20.11.2026 setzen und das notieren.
- Danach sichtbar: die Aufgabe trägt das Wiederholungs-Symbol ("Wiederholende Aufgabe").
- Bietet die Detailansicht keine Wiederholung an: die Aufgabe nicht anlegen, das in der Rückmeldung sagen und das Kommando des Zwischenstands mit der Option `--seed-recurring` fahren (siehe unten).

### Rundengrenze: Zwischenstand a per DAV sichern

Nach Schritt 5 und vor Schritt 6. Ein Kommando im Worktree; `<zugangsdatei>` ist der Pfad aus dem Bericht des Executors:

```
cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && PYTHONPATH=src PYTHONUTF8=1 uv run --no-sync python scripts/tasks_spike.py --env-file C:/Users/Student/nextcloud-mcp-connector/.env.nc35 --block ui-snapshot --label a --ui-file <zugangsdatei> --out .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/ui-sitzung.txt
```

- Konnte Schritt 5 die Aufgabe nicht anlegen: dasselbe Kommando mit `--seed-recurring` vor `--out`. Das Skript legt `s30 wiederkehrend` dann selbst per `PUT` an (Zeile `UI-NACHGELEGT`); danach die Seite in der App neu laden und prüfen, ob die Aufgabe erscheint.
- Erwartet: Exit 0, die Zeile `UI-STAND a objekte=<n>` mit n mindestens 14 (15 mit der wiederkehrenden Aufgabe), `UI-GLEICH appapi_basic=ja`, keine Zeile `UI-FEHLT name=...`. Die Objekte liegen danach unter `raw/ui-a/`.
- Erscheint `UI-FEHLT`: den fehlenden Namen in der App prüfen (Tippfehler), korrigieren und das Kommando wiederholen; es ersetzt den Stand a.
- Das Kommando erzeugt für das Messkonto ein weiteres App-Passwort und druckt kein Geheimnis.

## Runde B: nur ändern

### Schritt 6: abhaken

- Adresse: `spike30-liste-1`.
- Klicken: das Kontrollkästchen vor `s30 abhaken`.
- Danach sichtbar: die Aufgabe ist durchgestrichen oder wandert unter die erledigten Aufgaben ("1 erledigte Aufgabe").

### Schritt 7: abhaken und wieder öffnen

- Klicken: das Kontrollkästchen vor `s30 wieder-oeffnen`, kurz warten, dann die erledigten Aufgaben einblenden und dasselbe Kontrollkästchen noch einmal anklicken.
- Danach sichtbar: `s30 wieder-oeffnen` steht wieder unter den offenen Aufgaben.

### Schritt 8: Elternaufgabe abhaken

- Klicken: nur das Kontrollkästchen vor `s30 eltern-abhaken`, nicht das der Unteraufgabe.
- Fragt die App nach den Unteraufgaben: die Frage im Wortlaut und die gewählte Antwort notieren.
- Danach sichtbar: notieren, ob `s30 kind-abhaken` in der Oberfläche mit als erledigt erscheint.

### Schritt 9: wiederkehrende Aufgabe abhaken

- Klicken: das Kontrollkästchen vor `s30 wiederkehrend`.
- Danach sichtbar: notieren, was die Oberfläche zeigt (erledigt, neues Fälligkeitsdatum, weiterhin offen, Fehlermeldung im Wortlaut).
- Zeigt die App eine vom Skript nachgelegte Aufgabe gar nicht an: nichts nachstellen, das in der Rückmeldung sagen.

### Schritt 10: zwei Aufgaben in die zweite Liste verschieben

- `s30 umzug-einzeln` nach `spike30-liste-2` verschieben, dann `s30 eltern-umzug` (nur die Elternaufgabe anfassen) nach `spike30-liste-2`.
- Weg: entweder den Eintrag auf die Liste in der linken Leiste ziehen oder in der Detailansicht die Liste wechseln ("Wähle einen Kalender"). Den genutzten Weg je Aufgabe notieren.
- Danach sichtbar: `spike30-liste-2` zeigt die verschobenen Aufgaben; notieren, ob `s30 kind-umzug` mitgewandert ist.

### Schritt 11: Elternaufgabe löschen

- Adresse: `spike30-liste-1`.
- Klicken: im Menü von `s30 eltern-loeschen` (nur die Elternaufgabe) "Aufgabe löschen".
- Danach mindestens 15 Sekunden warten: die App verzögert das Löschen und zeigt einen Rückgängig-Zähler. Nicht auf Rückgängig klicken und die Seite in dieser Zeit nicht verlassen.
- Danach sichtbar: `s30 eltern-loeschen` ist aus der Liste verschwunden; notieren, ob `s30 kind-loeschen` noch erscheint.

### Schritt 12: Kontrollobjekt

- `s30 unberuehrt` nicht anfassen: nicht anklicken, nicht öffnen, nicht verschieben. Nur prüfen, dass die Aufgabe noch offen in `spike30-liste-1` steht.

## Nach Schritt 12

Kein Kommando durch die Hauptsitzung. Den Stand b sichert der Executor in seinem zweiten Auftrag (Block ui-snapshot mit `--label b`, danach ui-evaluate, Inventar, Rückbau). Die Instanz bis dahin laufen lassen und im Konto nichts mehr ändern.

Rückmeldung an den Executor: "ui fertig", dazu

- die Zeitzone des Browsers,
- Schritt 5: von der App angelegt oder per `--seed-recurring` nachgelegt, und ob ein Datum nötig war,
- Schritt 8: Rückfrage der App im Wortlaut und gewählte Antwort, oder "keine Rückfrage",
- Schritt 10: der Weg je Aufgabe,
- der gewählte Wert der Priorität aus Schritt 2,
- jede Abweichung von dieser Liste und jede Fehlermeldung im Wortlaut.

# Plan 33-01b, Task 1: Browser-Sitzung in der Tasks-App (M-1, M-2, CANCELLED)

Neunzehn Schritte in zwei Runden, nach jedem Schritt ab Runde B ein Stand per DAV. Die Sitzung fährt die Hauptsitzung mit Playwright (Chromium, Zeitzone Europe/Berlin). Der Executor von Plan 33-01b hat sie vorbereitet und führt keinen dieser Schritte selbst aus. Vorlage: `.planning/phases/30-mess-spike-aufgaben-und-ordner/30-02-BROWSER-SCHRITTE.md`.

## Stand der Vorbereitung (2026-11-13)

| Punkt | Wert | Woher |
|-------|------|-------|
| Instanz | nc35 läuft, `http://127.0.0.1:8082`, Nextcloud 35, SQLite | `tasks_measure.py up --instance nc35`, RAM-Gate ok, kein fremder Container |
| Tasks-App | 0.18.1, vor dem Lauf nicht installiert, aus dem App Store geladen | Zeilen `TASKSAPP nc35 vorher=keine` und `TASKSAPP nc35 messung=0.18.1` |
| Messkonto | `p3301ui`, nur für diese Messung angelegt, ohne Gruppen, Sprache Deutsch (`core lang de`, `core locale de_DE`) | `occ user:add`, `occ user:setting` |
| Zugangsdaten | Datei außerhalb des Repositorys, drei Zeilen: Benutzername, Passwort, Basis-URL; das App-Passwort für die Stände in einer zweiten Datei außerhalb des Repositorys | Pfade nennt der Bericht des Executors; kein Passwort in einer Datei des Repositorys |
| Listen des Kontos | keine (`occ dav:list-calendars p3301ui`: "has no calendars"), BASELINE `calendars=0 objekte=0` | die Liste legt Schritt 1 in der App an |
| Kommando der Stände | gegen das leere Konto geprobt: Impersonation erreicht das Konto, PROPFIND auf eine nicht vorhandene Liste antwortet 404 | Probelauf des Executors |

Die Beschriftungen in Anführungszeichen stammen aus der deutschen Sprachdatei der installierten App (`apps/tasks/l10n/de.json` im Container, gelesen, nicht in der Oberfläche gesehen). Weicht die Oberfläche ab, zählt die Oberfläche; die Abweichung gehört in die Rückmeldung.

## Regeln für die Sitzung

- Die Aufgabennamen wörtlich übernehmen, klein geschrieben, mit dem Leerzeichen nach `p3301`. Die Auswertung findet die Objekte über den Namen.
- Nichts raten und nichts ersetzen. Scheitert ein Schritt, die Fehlermeldung im Wortlaut notieren und anhalten.
- Zwischen zwei Handlungen warten, bis die App gespeichert hat (kein drehendes Symbol am Eintrag). Die App schreibt jede Änderung sofort per CalDAV. Auf SQLite scheitern zwei gleichzeitige Schreibzugriffe desselben Kontos (Phase 30, 3.6: `database is locked`, die App meldet das nicht); darum nach jedem Schritt die Seite neu laden und notieren, ob der angezeigte Zustand nach dem Neuladen noch stimmt.
- Nach jedem Schritt ab Schritt 8 das Kommando des Stands mit der genannten Marke fahren, erst danach den nächsten Schritt. Jede Marke nur einmal; muss ein Schritt wiederholt werden, die Marke mit `-2` anhängen und das notieren.
- Für die Rückmeldung notieren: die Zeitzone des Browsers, jede Rückfrage der App im Wortlaut samt gewählter Antwort, den Weg bei Schritt 13, 14 und 15, jede Abweichung von dieser Liste.

## Kommandos

`<S>` ist der Scratchpad-Pfad aus dem Bericht des Executors, `<LISTE>` die Kennung der Liste aus Schritt 1.

Kennung der Liste (nach Schritt 1, einmal):

```
docker exec -u www-data nc35-nc php occ dav:list-calendars p3301ui
```

Stand mit Marke `<marke>`:

```
cd C:/Users/Student/nextcloud-mcp-connector-worktrees/tasks-080 && set -a && . "<S>/p33secret/p3301ui.env" && set +a && PYTHONPATH=src PYTHONUTF8=1 uv run --no-sync python scripts/tasks_modify_measure.py snapshot --instance nc35 --env-file .env.nc35 --account p3301ui --list <LISTE> --password-key P3301UI_APP_PASSWORD --out "<S>/p33/ui-<marke>" --protocol "<S>/p33/ui-sitzung.txt"
```

Erwartet: Exit 0, je Objekt eine Zeile `SNAPSHOT objekt=... status=200`, am Ende `SNAPSHOT gleich_appapi_basic=ja objekte=<n>`. Das Kommando druckt kein Geheimnis; die Ausgabe nicht ins Repository kopieren.

## Anmeldung (vor Schritt 1)

- Adresse: `http://127.0.0.1:8082/login`
- Eingeben: Benutzername und Passwort aus der Zugangsdatei (Zeile 1 und Zeile 2), anmelden.
- Zeigt sich ein Begrüßungsdialog, ihn schließen.
- Dann `http://127.0.0.1:8082/apps/tasks/` öffnen. Sichtbar: die App "Aufgaben" mit der linken Leiste ("Alle", "Aktuell", darunter die Listen) und dem Eintrag "Liste hinzufügen …".

## Runde A: nur anlegen

### Schritt 1: Liste anlegen

- Klicken: "Liste hinzufügen …", in das Feld "Neue Liste" `p3301-liste-1` schreiben, Eingabetaste.
- Erwartet: die Liste in der linken Leiste mit Zähler 0. Danach das Kommando "Kennung der Liste" fahren und `<LISTE>` notieren.
- Erwartete Rohzeile: keine (Liste ohne Objekte).

### Schritt 2: Elternaufgabe mit zwei Kindern (M-1)

- In `p3301-liste-1` in das Feld "Eine Aufgabe zu "p3301-liste-1" hinzufügen…" `p3301 eltern-zu` schreiben, Eingabetaste.
- Im Menü der Aufgabe (drei Punkte) "Teilaufgabe hinzufügen", `p3301 kind-1` schreiben, Eingabetaste; ebenso `p3301 kind-2`.
- Erwartet: beide Kinder eingerückt unter `p3301 eltern-zu`.
- Erwartete Rohzeilen: in beiden Kindern `RELATED-TO:<UID von p3301 eltern-zu>`.

### Schritt 3: Aufgabe mit allen Feldern (M-2)

- `p3301 felder` anlegen und anklicken (Detailansicht rechts).
- "Fälligkeitsdatum setzen": 20.11.2026, 10:15 Uhr, "Ganztägig" aus.
- "Startdatum setzen": 19.11.2026, 09:00 Uhr.
- Reiter "Notizen" ("Hier klicken, um eine Notiz hinzuzufügen."): `p3301 beschreibung` eingeben, Feld verlassen.
- "Priorität": den Wert 3 einstellen (angezeigt als "Priorität 3: hoch"); den angezeigten Text notieren.
- "Schlagworte auswählen": `p3301-eins` und `p3301-zwei` neu anlegen ("Dies als neues Schlagwort hinzufügen").
- Erwartete Rohzeilen: `DUE:20261120T091500Z`, `DTSTART:20261119T080000Z`, `DESCRIPTION:p3301 beschreibung`, `PRIORITY:3`, `CATEGORIES:p3301-eins,p3301-zwei`.

### Schritt 4: Unteraufgabe zum Lösen (M-2 parent)

- Im Menü von `p3301 felder` "Teilaufgabe hinzufügen", `p3301 kind-lösen` schreiben, Eingabetaste.
- Erwartete Rohzeile: `RELATED-TO:<UID von p3301 felder>` in `p3301 kind-lösen`.

### Schritt 5: Elternaufgabe mit offenem und abgebrochenem Kind (CANCELLED Kette)

- `p3301 eltern-ab` anlegen, darunter mit "Teilaufgabe hinzufügen" `p3301 kind-ab-offen` und `p3301 kind-ab-abgebrochen`.
- `p3301 kind-ab-abgebrochen` anklicken, in der Detailansicht "Status auswählen" auf "Abgebrochen" stellen.
- Erwartete Rohzeile: `STATUS:CANCELLED` in `p3301 kind-ab-abgebrochen`.

### Schritt 6: abgebrochene Einzelaufgabe (CANCELLED direkt)

- `p3301 abgebrochen` anlegen, Status "Abgebrochen" wie in Schritt 5.
- Erwartete Rohzeile: `STATUS:CANCELLED`.

### Schritt 7: Kontrollobjekt

- `p3301 unberuehrt` anlegen, nichts weiter. Ab jetzt nicht mehr anklicken.

### Rundengrenze: Stand a

- Seite neu laden, prüfen, dass alles wie angelegt dasteht (Status, Felder, Einrückung).
- Kommando des Stands mit Marke `a`. Erwartet: `SNAPSHOT gleich_appapi_basic=ja objekte=10`. Fehlt ein Objekt, den Namen in der App prüfen und die Marke `a-2` fahren.

## Runde B: nur ändern, nach jedem Schritt ein Stand

### Schritt 8: Elternaufgabe abhaken (Vorbereitung M-1), Marke `b1`

- Klicken: nur das Kontrollkästchen vor `p3301 eltern-zu`.
- Rückfrage der App im Wortlaut notieren. Seite neu laden; notieren, ob danach Elternaufgabe und beide Kinder erledigt sind. Steht die Elternaufgabe nach dem Neuladen wieder offen (Fehlschlag wie in Phase 30), das notieren, ihr Kontrollkästchen genau einmal erneut anklicken, neu laden, notieren.
- Stand `b1`. Erwartete Rohzeilen: in allen drei Objekten `STATUS:COMPLETED`, `PERCENT-COMPLETE:100`, `COMPLETED:...Z`.

### Schritt 9: nur die Elternaufgabe wieder öffnen (M-1), Marke `b2`

- Erledigte Aufgaben einblenden ("%n erledigte Aufgaben" bzw. "Geschlossene Teilaufgaben anzeigen"), dann nur das Kontrollkästchen vor `p3301 eltern-zu` anklicken. Kinder nicht anfassen.
- Rückfrage im Wortlaut notieren. Neu laden; notieren, ob `p3301 kind-1` und `p3301 kind-2` offen oder erledigt angezeigt werden.
- Stand `b2`. Gemessen wird: was in der Elternaufgabe steht und ob die App die Kinder mit öffnet.

### Schritt 10: Fälligkeit entfernen, Marke `m2-due`

- `p3301 felder` anklicken, beim Fälligkeitsdatum "Datum löschen" (oder "Wert löschen") wählen. Den Weg notieren.
- Stand `m2-due`. Gemessen: Zeile `DUE` weg oder leer.

### Schritt 11: Startdatum entfernen, Marke `m2-start`

- Beim Startdatum "Datum löschen". Stand `m2-start`.

### Schritt 12: Beschreibung entfernen, Marke `m2-description`

- Im Reiter "Notizen" den ganzen Text löschen, Feld verlassen. Stand `m2-description`.

### Schritt 13: Priorität auf keine, Marke `m2-priority`

- Priorität auf "Keine Priorität zugewiesen" stellen (Regler auf 0 oder "Wert löschen"); den Weg notieren. Stand `m2-priority`.

### Schritt 14: alle Schlagworte entfernen, Marke `m2-tags`

- Unter "Schlagworte" beide Schlagworte entfernen (Kreuz am Schlagwort oder Abwahl in der Auswahl); den Weg notieren. Stand `m2-tags`.

### Schritt 15: Unteraufgabe zur Hauptaufgabe machen, Marke `m2-parent`

- `p3301 kind-lösen` aus `p3301 felder` herauslösen: den Eintrag auf die oberste Ebene der Liste ziehen (zwischen andere Hauptaufgaben oder auf `p3301-liste-1` in der linken Leiste). Den Weg notieren.
- Bietet die App keinen Weg an (nichts bewegt sich, kein Menüeintrag): nichts nachstellen, "app_moeglich=nein" notieren und keinen Stand fahren.
- Sonst Stand `m2-parent`. Gemessen: Zeile `RELATED-TO` weg oder leer.

### Schritt 16: Elternaufgabe mit abgebrochenem Kind abhaken, Marke `c-kette`

- Nur das Kontrollkästchen vor `p3301 eltern-ab`. Rückfrage notieren, neu laden; notieren, wie `p3301 kind-ab-offen` und `p3301 kind-ab-abgebrochen` angezeigt werden. Bei Fehlschlag der Elternaufgabe wie in Schritt 8 genau einmal wiederholen.
- Stand `c-kette`. Gemessen: bleibt `p3301 kind-ab-abgebrochen` unberührt, wird `p3301 kind-ab-offen` erledigt.

### Schritt 17: abgebrochene Aufgabe abhaken, Marke `c-direkt-ab`

- Das Kontrollkästchen vor `p3301 abgebrochen` (abgebrochene Aufgaben stehen evtl. unter den erledigten, dann diese einblenden).
- Bietet die App für die abgebrochene Aufgabe kein Kontrollkästchen an: "app_moeglich=nein" notieren, Schritt 18 entfällt, keinen Stand fahren.
- Sonst neu laden, angezeigten Zustand notieren, Stand `c-direkt-ab`.

### Schritt 18: dieselbe Aufgabe wieder öffnen, Marke `c-direkt-auf`

- Das Kontrollkästchen vor `p3301 abgebrochen` noch einmal. Neu laden, angezeigten Status notieren (offen, "Abgebrochen", anderes). Stand `c-direkt-auf`.

### Schritt 19: Kontrollobjekt

- `p3301 unberuehrt` nicht anfassen. Nur prüfen, dass es offen in `p3301-liste-1` steht. Kein weiterer Stand nötig (der letzte Stand enthält es).

## Nach Schritt 19

Abmelden ist nicht nötig, im Konto nichts mehr ändern, die Instanz laufen lassen. Auswertung (`diff`, `UI-ZUGRIFF` aus dem Zugriffsprotokoll), Fixtures und Rückbau macht der Executor in seinem zweiten Auftrag.

Rückmeldung an den Executor: "ui fertig", dazu

- die Zeitzone des Browsers und die Kennung `<LISTE>`,
- die Liste der gefahrenen Marken (mit `-2`-Wiederholungen),
- je Schritt 8, 9, 16, 17, 18: Rückfrage im Wortlaut oder "keine Rückfrage", angezeigter Zustand nach dem Neuladen,
- der Weg bei Schritt 10, 13, 14 und 15, bei 15 und 17 gegebenenfalls "app_moeglich=nein",
- der angezeigte Text der Priorität aus Schritt 3,
- jede Abweichung von dieser Liste und jede Fehlermeldung im Wortlaut.

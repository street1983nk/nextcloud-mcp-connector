---
phase: 30-mess-spike-aufgaben-und-ordner
plan: 03
subsystem: messung / Verschieben und Löschen von Aufgaben (CalDAV VTODO), Papierkorb des Kalenders auf Nextcloud 32 bis 35
tags: [spike, caldav, vtodo, move, delete, papierkorb, trashbin, appapi, impersonation, messung]
requires:
  - 30-01 (Messskript scripts/tasks_spike.py, RAM-Gate, Baseline, Rückbau)
  - 30-02 (Block modify für den Listenaufbau, Rohobjekte raw/ui-a und raw/ui-b, raw/ui-sitzung.txt)
provides:
  - scripts/tasks_spike.py (Blöcke move, ui-evaluate-move, delete-matrix, delete-verdict; Funktionen abort_move, delete_verdict, consequence, pretest_shows)
  - docs/spike-tasks.md (Abschnitt 4 mit 4.1 bis 4.5, Kriterien und Entscheidungsregel, Ergänzungen in 11, Rohauszüge 12.6 und 12.7)
  - raw/nc35-verschieben.txt (MOVE und DELETE unter Impersonation, Unteraufgaben, Rückbau)
  - raw/loeschen-32.txt bis raw/loeschen-35.txt (Löschmatrix je Version)
affects: [30-04, 30-05, 33, 34]
tech-stack:
  added: []
  patterns:
    - "Ort, Papierkorb-Marke und Hash eines Kalenderobjekts kommen aus der Tabelle calendarobjects je UID, nicht aus DAV und nicht aus dem Statuscode"
    - "Pfade und Schalter des Kalender-Papierkorbs werden vor der Nutzung per grep an der Quelle der laufenden Instanz gelesen (QUELLE-Zeilen); ohne Bestätigung bricht der Block ab"
    - "Ergebniswort als reine, getestete Funktion über Sammelzeilen der Rohdateien; der Bericht übernimmt die Ausgabe wörtlich"
    - "ein Vorab-Test-Kandidat zählt nur, wenn seine vorab festgelegte Lesart in beiden Zuständen stimmt"
key-files:
  created:
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/nc35-verschieben.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/loeschen-32.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/loeschen-33.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/loeschen-34.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/loeschen-35.txt
  modified:
    - scripts/tasks_spike.py
    - tests/unit/test_tasks_spike.py
    - docs/spike-tasks.md
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/30-03-PLAN.md
decisions:
  - "A19 belegt mit Einschränkung: MOVE zwischen zwei eigenen Aufgabenlisten antwortet unter AppAPI-Impersonation mit 201, UID, Text und ETag bleiben; ohne Overwrite-Kopf überschreibt der Server ein belegtes Ziel (204), mit Overwrite F 412. Abbruchkriterium MESS-06 MOVE nicht ausgelöst"
  - "Der Server prüft beim MOVE das Komponenten-Set des Ziels nicht (201 in einen Kalender nur für VEVENT); geteilte Liste ohne Schreibrecht 404, Deck-Kalender 403, gleiche UID im Ziel 409"
  - "A21 belegt: der Server nimmt eine Unteraufgabe weder beim Verschieben noch beim Löschen der Elternaufgabe mit; die Tasks-App 0.18.1 tut beides mit je einem eigenen Aufruf. Nach dem Wortlaut von A21 folgt der Connector dem Gemessenen"
  - "A18: auf 32.0.15, 33.0.9, 34.0.4 und 35.0.2 landet eine gelöschte Aufgabe im Papierkorb und ist wiederherstellbar, auch in einer geteilten Liste; mit abgeschaltetem Papierkorb löscht DELETE endgültig; der Vorab-Test über die Eigenschaft trash-bin-retention-duration erkennt den Aus-Zustand (Wert 0)"
  - "ERGEBNIS LOESCHEN (E13): wiederherstellbar; TMOD-07 ist für Phase 33 planbar, mit Auflagen"
metrics:
  duration: "ca. 75 min, davon ca. 25 min Warten am RAM-Tor"
  completed: 2026-11-11
  tasks: 3
  files: 9
---

# Phase 30 Plan 03: MOVE unter Impersonation, Unteraufgaben, Löschen mit Papierkorb auf Nextcloud 32 bis 35 Summary

`MOVE` zwischen zwei Aufgabenlisten trägt unter AppAPI-Impersonation (201, UID, Text und ETag bleiben), das Abbruchkriterium für TMOD-08 ist nicht ausgelöst. Das Löschen ist auf vier Versionen gemessen und trägt nach der vorab festgelegten Regel das Wort "wiederherstellbar": mit eingeschaltetem Papierkorb kommt die Aufgabe zurück, mit abgeschaltetem löscht der Server endgültig, und genau ein Vorab-Test zeigt diesen Zustand vorher an.

## Befunde

Gelesene Fassungen (aus der laufenden Instanz, 2026-11-11): nc35 mit Nextcloud 35.0.0 (`occ status`), `app_api` 35.0.0, ExApp `mcp_connector` 0.3.2, Deck 1.19.0 (`occ app:list --output=json`), SQLite. Wegwerf-Instanzen aus `compose.spike-tags.yml`: 32.0.15, 33.0.9, 34.0.4, 35.0.2 (je `occ status`), SQLite, `memcache.local` APCu. Tasks-App 0.18.1 nur über die Rohobjekte aus 30-02.

### MOVE unter Impersonation (raw/nc35-verschieben.txt, Bericht 4.1)

| Punkt | Ergebnis |
|---|---|
| M4.1 eigene Liste nach eigene Liste | 201, Quelle danach 404, Ziel 200, UID gleich, Text byte-gleich, ETag gleich; Logzeile `MOVE` in `exapp_impersonation.log`; Auflistung mit App-Passwort und Datenbankzeile bestätigen den Ort; falsches Secret 401, nichts verschoben |
| Abbruchkriterium | `ABBRUCHKRITERIUM MESS-06 MOVE ausgeloest=nein grund=keiner` |
| App-Passwort | dieselben fünf Werte (`MOVE GLEICH appapi_basic=ja`) |
| Produktionsweg | aus dem ExApp-Container gegen `http://caddy`: 201, verschoben |
| `Destination` | bloßer Pfad 201; fremder Hostname 201: der Server wertet nur den Pfad aus |
| M4.2 belegtes Ziel | mit `Overwrite: F` 412, beide unverändert; ohne Kopfzeile 204, überschrieben, das verdrängte Objekt liegt im Papierkorb |
| M4.3 gleiche UID im Ziel | 409 `UidConflict`, beide unverändert |
| M4.4 Ziele | geteilt mit Schreibrecht 201 (Objekt beim Eigentümer); geteilt ohne Schreibrecht 404; Deck-Kalender 403; Kalender nur für `VEVENT` 201 |
| M4.5 `If-Match` | aktuelle ETag 201, veraltete 412 und nichts verschoben |
| M4.8 DELETE | mit gelesener ETag 204, veraltete 412; im Papierkorb per `REPORT` (PROPFIND 501); Wiederherstellung 201, UID und Inhalt gleich; Datenbank bestätigt `deleted_at` gesetzt und wieder leer |

### Unteraufgaben (Bericht 4.2)

| Seite | Verschieben der Elternaufgabe | Löschen der Elternaufgabe |
|---|---|---|
| Server (M4.6, gemessen) | Unteraufgabe bleibt unverändert in der Quellliste | Unteraufgabe bleibt unverändert, verweist auf eine gelöschte Elternaufgabe |
| Tasks-App 0.18.1 (M4.7, aus raw/ui-a und raw/ui-b gelesen) | `kind=zieht mit`, eigener `MOVE` je Objekt | `kind im papierkorb`, eigener `DELETE` je Objekt |

Kontrolle `s30 unberuehrt`: Differenz leer, Ort gleich. Objektzahl 15 in beiden Ständen.

### Löschen auf Nextcloud 32 bis 35 (raw/loeschen-32.txt bis -35.txt, Bericht 4.3 bis 4.5)

Auf allen vier Versionen gleich:

| Punkt | Ergebnis |
|---|---|
| Papierkorb an, eigene Liste (W1) | `DELETE` 204, im Papierkorb, `deleted_at` gesetzt; Wiederherstellung 201, alter Ort, UID und sha256 gleich |
| Papierkorb an, geteilte Liste (W2) | 204, im Papierkorb beider Konten; wiederhergestellt durch das löschende Konto, an einem zweiten Objekt auch durch den Eigentümer; ohne Schreibrecht 404, Objekt unverändert |
| Papierkorb aus (W3) | 204, in keinem Papierkorb, Datenbankzeile weg, Wiederherstellung nicht möglich, eigene und geteilte Liste |
| Vorab-Test (W4) | genau ein Kandidat von sechs unterscheidet: `PROPFIND` Depth 0 auf `calendars/<konto>/trashbin/` nach `{http://nextcloud.com/ns}trash-bin-retention-duration` (an: 2592000, aus: 0, Frist 1: 1). Existenz der Sammlung, Kind im Home, `DAV`-Kopf und Capabilities unterscheiden nicht |
| Aufbewahrungsfrist | Schlüssel `calendarRetentionObligation` nicht gesetzt, Standard laut Quelle 2592000 Sekunden (30 Tage); `occ dav:retention:clean-up` lässt das Objekt mit dem Standard stehen und entfernt es mit dem Wert 1 nach drei Sekunden |
| Unteraufgabe | bleibt nach dem Löschen der Elternaufgabe unverändert |
| Sammelzeilen | je `g=ja w1=ja w2=ja w3=nein w4=ja wer=loeschender` |

```
ERGEBNIS LOESCHEN (E13): wiederherstellbar
KONSEQUENZ: TMOD-07 ist planbar (Phase 33), mit den Auflagen aus den Messwerten: Vorab-Test vor dem Löschen, wer wiederherstellen kann, Aufbewahrungsfrist.
```

Lesart: es gilt die Fassung nach TMOD-07 (Owner-Entscheid vom 11.11.2026, "Ok" auf die vorgelegte Lesart, vor dem ersten Messwert in Plan und Bericht eingetragen). Nach der wörtlichen Lesart von E13 wäre das Ergebnis "nicht wiederherstellbar"; der Rohbefund steht in Bericht 4.4.

### Annahmen

| Annahme | Stand |
|---|---|
| A18 | belegt für Papierkorb an, eigene und geteilte Liste, 32 bis 35; Aus-Zustand: endgültig gelöscht, vorab erkennbar |
| A19 | belegt für Impersonation und UID; "überschreibt kein belegtes Ziel" nur mit `Overwrite: F` |
| A21 | belegt für Server und Tasks-App; die Vorgabe "ablehnen" bleibt nach dem Wortlaut von A21 nicht bestehen |

### Bedeutung für Phase 33

- TMOD-08: planbar. `Overwrite: F` und `If-Match` sind Pflicht; das Ziel muss der Connector selbst als beschreibbare Aufgabenliste aus der Discovery prüfen, der Server tut es nicht; 404 heißt in einer geteilten Liste "kein Schreibrecht".
- TMOD-07: planbar, mit Auflagen: Vorab-Test wie oben (nur eine Zahl größer 0 erlaubt das Löschen), Frist in der Antwort, Entscheid über eine Mindestfrist (Frist 1 erscheint als "an"), Kopfzeile `X-NC-CalDAV-No-Trashbin` nie senden (gelesen).
- Unteraufgaben: Mitnehmen heißt ein Aufruf je Objekt ohne Transaktion; Umsetzung und Teilfehler sind in Phase 33 zu planen, Übergabe in 30-05.
- `.planning/REQUIREMENTS.md` ist in diesem Plan nicht geändert (geschieht in 30-05).

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| Vorab | 8016484 | Kriterientabelle, Entscheidungsregel und Owner-Lesart in Bericht und Plan, vor jedem Messwert |
| 1 | 5febe98 (Tests), 24b0c3d (Blöcke move, ui-evaluate-move), 7eb48a5 (Rohprotokoll, Bericht 4.1, 4.2, 12.6) | Abbruchmessung MOVE, alle Zielarten, Unteraufgaben, DELETE unter Impersonation |
| 2 | 0a7561f (Tests), dd7a569 (delete-matrix, delete-verdict, Wertbildung im Bericht) | Werkzeug und Regel, vor der ersten Datei raw/loeschen-*.txt |
| 3 | a98dfff | vier Läufe, Bericht 4.3 bis 4.5, 11, 12.7, Ergebniswort |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2] `abort_move` prüft zusätzlich den Inhalt**
- **Found during:** Task 1
- **Issue:** Die Kriterientabelle (M4.1) nennt "Inhalt gleich" als Teil des Abbruchkriteriums, die Verhaltensliste der Funktion nur vier Werte.
- **Fix:** fünfter Wert `content_same` mit Vorgabe wahr; die vier getesteten Fälle gelten unverändert.
- **Commit:** 24b0c3d

**2. [Rule 2] Wertbildung und Wiederholungsregel vorab festgeschrieben**
- **Found during:** Task 2
- **Issue:** Der Plan legt W1 bis W4 und G fest, aber nicht, wie das Skript sie aus den Abschnitten bildet, und nicht, wie ein Wiederholungslauf nach einem Werkzeugfehler gegen den ersten zählt.
- **Fix:** Absatz "Wie das Messskript die fünf Werte bildet" im Bericht, mit dem Commit des Blocks und vor jeder Rohdatei; `version_rows()` lässt nur einen Lauf mit der Zeile `WIEDERHOLUNG Grund:` frühere Läufe ersetzen. Gebraucht wurde die Regel nicht: kein Messlauf wurde wiederholt.
- **Commit:** dd7a569

**3. [Rule 3] `--env-file` für die Wegwerf-Blöcke entbehrlich gemacht**
- `main` las die Umgebungsdatei bisher immer; delete-matrix und delete-verdict laufen jetzt ohne sie, wie der Plan es verlangt.

### Sonstiges

- **RAM-Tor:** drei Läufe endeten am Tor, ohne etwas zu starten oder zu messen (33 einmal mit 3,44 GB, 34 zweimal mit 3,45 und 2,48 GB frei). Sie stehen als `RUN FAILED` in `raw/loeschen-33.txt` und `raw/loeschen-34.txt`. Nach dem Abbau einer Instanz gab die Docker-VM den Speicher erst nach mehreren Minuten zurück; gewartet, nichts beendet, Schwelle unverändert.
- **Zusätzliche Zeilen über den Plan hinaus:** `MOVE ziel-nur-pfad` und `MOVE ziel-fremder-host` (welche Basis der Server im `Destination`-Kopf annimmt), `WIEDERHERSTELLUNG an-geteilt-eigentuemer` (zweites Objekt, vom Eigentümer wiederhergestellt), Vorab-Test im Zustand Frist 1, Kandidaten `frist-eigenschaft-home` und `dav-kopf`.
- **`papierkorb_von=beide`:** der Plan sah nur drei Werte vor; gemessen steht die Aufgabe im Papierkorb beider Konten.
- **W3** ist als "eigene und geteilte Liste im Aus-Zustand wiederherstellbar" gebildet (strenger als nur die eigene Liste).
- **Befund am Rand:** `occ user:auth-tokens:add --name` scheitert auf 32.0.15 (Option fehlt) und auf 33.0.9 (`login-name`); der Block fällt auf `GET /ocs/v2.php/core/getapppassword` zurück (wie in Phase 25).
- **Quelltext vorab gelesen:** vor dem Bau der Blöcke wurden die Papierkorb-Dateien der vier Images mit `docker run --rm --entrypoint sh` gelesen (keine Nextcloud-Instanz, kein Messwert). Die Bestätigung, die zählt, steht je Lauf als `QUELLE`-Zeilen aus der laufenden Instanz im Protokoll.
- **Lint-Nachzug:** der Test-Commit 0a7561f trug zwei überlange Zeilen; behoben im folgenden Commit dd7a569, bevor ein Tor über das ganze Repository lief.
- **TDD:** die Tests entstanden je vor dem Code (5febe98, 0a7561f, RED gesehen). Die Tests zu `parse_trash_source` und `parse_db_rows` kamen mit dem Code beziehungsweise im ersten Test-Commit.
- **Skript bleibt ASCII:** der Wortlaut "kein Löschen in 0.8.0, ohne Rückfrage" steht im Quelltext mit Unicode-Escapes.
- `vulture_whitelist.py` blieb unverändert (kein Eintrag nötig). `.env.nc35` wurde aus dem Hauptcheckout nur gelesen. Kein Push, kein PR, kein Kommentar.

## Zustand nach dem Rückbau

- nc35: alle zwölf BASELINE-Zeilen gleich=ja; kein Konto mit Präfix spike30; kein Deck-Board mit Präfix (`RUECKBAU deck_boards_mit_praefix_spike30=0`); keine gelöschten Kalenderobjekte zurückgeblieben; `calendarRetentionObligation` nie gesetzt. Container `nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc_app_mcp_connector` gestoppt.
- Wegwerf-Instanzen: nach jedem der vier Läufe `ABBAU Container vorhanden: nein` und `ABBAU Volume vorhanden: nein`; am Planende kein Container und kein Volume mit `nc-spike-tags`. Nie liefen zwei Instanzen gleichzeitig, nie eine neben nc35.
- Es läuft nur der fremde Container `gameworld-dev-gameworld-docker-proxy-1`, unberührt.

## Was ungemessen blieb

Vollständig in docs/spike-tasks.md, Abschnitt 11. Kurz: `MOVE` und `DELETE` unter Impersonation nur auf 35.0.0 (auf 32 bis 35 ist das Löschen mit App-Passwort gemessen); nur SQLite; `DELETE` mit veralteter ETag nur auf nc35; Zustand des Papierkorbs direkt nach einer Änderung des Schalters ohne Neustart; negativer Schalterwert und Kopfzeile `X-NC-CalDAV-No-Trashbin` (gelesen); Hintergrundjob der Aufbewahrung (gemessen ist das occ-Kommando); Wiederherstellen bei belegtem altem Ort und in einer Oberfläche; Kalender mit `VEVENT` und `VTODO`; Freigaben an Gruppen; `MOVE` aus einem Deck-Kalender, mit `Overwrite: T`, einer wiederkehrenden Aufgabe; belegtes Ziel ohne Kopfzeile bei abgeschaltetem Papierkorb; mehrstufige Unteraufgaben; das Mitnehmen der Unteraufgaben durch den Connector.

## Known Stubs

Keine. Die Abschnitte 5, 6 und 8 bis 10 des Berichts tragen mit Absicht den Vermerk "offen" samt dem Plan, der sie füllt.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus. T-30-14 bis T-30-19 umgesetzt: `MOVE` und `DELETE` nur aus dem Messskript auf Listen mit Präfix, nichts unter `src/`; Messkonten mit Rückbau und Baseline; Regel und Wertbildung vor der Messung committet, Ergebniszeile wortgleich mit delete-verdict; Positivkontrollen und Datenbank-Gegenprobe; Wegwerf-Instanzen nur auf Loopback, Zufallspasswörter über Umgebung und stdin, `down -v` im finally; RAM-Tor vor jedem Lauf. Secret-Scan vor jedem Commit mit Rohdateien: 42 Dateien, 0 Funde.

## Self-Check: PASSED

- Dateien vorhanden: raw/nc35-verschieben.txt, raw/loeschen-32.txt, -33.txt, -34.txt, -35.txt; docs/spike-tasks.md mit 4.1 bis 4.5, 12.6, 12.7
- Commits vorhanden: 8016484, 5febe98, 24b0c3d, 7eb48a5, 0a7561f, dd7a569, a98dfff
- Voller Lauf nach R1: `pytest tests/unit tests/contract` Exit 0, `check_tool_budget.py` Exit 0, `ruff check .`, `ruff format --check .`, `pyright` (0 Fehler), `vulture` grün; `git status --porcelain src` leer

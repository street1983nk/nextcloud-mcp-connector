---
phase: 30-mess-spike-aufgaben-und-ordner
plan: 04
subsystem: messung / Aufgaben-Discovery, Abfrageverhalten auf Nextcloud 32 bis 35, Kosten der Aufgabensuche, Fixtures der Tasks-App
tags: [spike, caldav, vtodo, discovery, calendar-query, calendar-search, deck, postgresql, fixtures, messung]
requires:
  - 30-01 (Messskript scripts/tasks_spike.py, RAM-Gate, Baseline, Rückbau)
  - 30-02 (Rohobjekte raw/ui-a und raw/ui-b, raw/ui-sitzung.txt)
  - 30-03 (Lebenszyklus der Wegwerf-Instanz, Datenbank-Gegenprobe je UID)
provides:
  - scripts/tasks_spike.py (Blöcke discovery-matrix, cost, vtodo-create, fixtures; Funktionen classify_collection, task_lists, build_todo_filter, client_filter, same_sets, provider_link_parts, proposal, pick_fixtures)
  - docs/spike-tasks.md (Abschnitte 5 und 6, Kriterien und Ableitungsregel, Ergänzungen in 11, Rohauszüge 12.8 bis 12.10)
  - raw/discovery-32.txt bis raw/discovery-35.txt, raw/kosten-sqlite.txt, raw/kosten-pg.txt, raw/nc35-vtodo-anlegen.txt, raw/fixtures.txt
  - tests/fixtures/tasks_app/ (acht Objekte der Tasks-App, PROVENANCE.md)
  - tests/fixtures/caldav_home_fresh_account.xml, tests/fixtures/caldav_home_task_lists.xml
affects: [30-05, 32, 33]
tech-stack:
  added: []
  patterns:
    - "eine Rohantwort steht mit sha256 im Protokoll und wird nur dann zur Fixture, wenn der zurückgelesene Körper denselben Hash trägt und nur Probewerte enthält"
    - "die Gegenprobe einer Server-Abfrage ist derselbe Filter im Skript über die ungefilterte Antwort; eine Abweichung ist ein Befund über den Serverfilter"
    - "nach occ app:install oder app:disable den Webserver neu starten, bevor die App über HTTP gefragt wird"
    - "eine Ableitungsregel für Produktwerte steht als getestete Funktion vor der Messung fest"
key-files:
  created:
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/discovery-32.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/discovery-33.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/discovery-34.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/discovery-35.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/kosten-sqlite.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/kosten-pg.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/nc35-vtodo-anlegen.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/fixtures.txt
    - tests/fixtures/tasks_app/ (8 .ics, PROVENANCE.md)
    - tests/fixtures/caldav_home_fresh_account.xml
    - tests/fixtures/caldav_home_task_lists.xml
  modified:
    - scripts/tasks_spike.py
    - tests/unit/test_tasks_spike.py
    - docs/spike-tasks.md
    - .gitattributes
decisions:
  - "TASK-03: ein Konto nach echter Erstanmeldung hat auf 32.0.15 und 35.0.2 die Kalender personal und contact_birthdays, beide nur VEVENT, und keine Aufgabenliste; die Rohantwort von 35.0.2 ist die Fixture"
  - "TASK-01 braucht eine engere Regel als das Komponenten-Set: resourcetype calendar UND VTODO im Set UND kein Präfix app-generated--; ein gelöschter Kalender (resourcetype deleted-calendar) und ein Abonnement (subscribed) tragen VTODO im Set und Schreibprivileg"
  - "A1 belegt: sechs calendar-query-Filter liefern auf 32.0.15, 33.0.9, 34.0.4 und 35.0.2 dieselben Treffermengen"
  - "Der time-range-Filter des Servers liefert undatierte Aufgaben mit; die Fälligkeitsgrenze filtert der Connector selbst. Der Vorfilter offen liefert CANCELLED mit"
  - "A4 belegt: {http://owncloud.org/ns}read-only ist per PROPFIND abrufbar (fehlt bei eigener Liste, leer bei Freigabe mit Schreibrecht, 1 bei nur lesbarer)"
  - "A5 teils widerlegt: der Papierkorb steht als erkennbare Sammlung ohne Komponenten-Set in der Discovery; gelöschte Kalender stehen mit Komponenten-Set und Schreibprivileg weiter im Home. Föderiert ungemessen"
  - "A6 belegt: Modus alle bei 2000 Aufgaben Median 148 ms (SQLite) und 186 ms (PostgreSQL), 1 521 874 Bytes; Vorschlag nach der Ableitungsregel: eine Abfrage je Liste ohne zusätzlichen Deckel unter 2000 Objekten, Zeitbudget je Liste 1 s"
  - "Der Link des Suchproviders tasks hat die Form <Instanz>/apps/tasks/calendars/<uri>/tasks/<name> und löst ohne Raten auf; ohne Tasks-App antwortet der Provider 200 mit leerer Liste"
  - "A2 und A3 belegt für Tasks 0.18.1: RELATED-TO gleich UID der Elternaufgabe ohne RELTYPE, gleiche Liste; Zeiten nur UTC und Datum, nie schwebend, nie TZID"
metrics:
  duration: "ca. 3 h Executor-Zeit in drei Aufträgen, davon ca. 25 min Messläufe; zwei Unterbrechungen (Docker Desktop beendet, Speichermangel)"
  completed: 2026-11-12
  tasks: 3
  files: 23
---

# Phase 30 Plan 04: Aufgaben-Discovery, Abfrageverhalten auf 32 bis 35, Kosten der Suche, Fixtures der Tasks-App Summary

Ein frisches Konto hat auf Nextcloud 32.0.15 und 35.0.2 keine Aufgabenliste, sechs `calendar-query`-Filter liefern auf vier Versionen dieselben Treffer, und 2000 Aufgaben kosten im Modus alle im Median 148 ms (SQLite) und 186 ms (PostgreSQL). Die Discovery zeigt zwei Sammlungsarten, die TASK-01 über das Komponenten-Set allein fälschlich als Aufgabenliste nähme: den gelöschten Kalender und das Abonnement.

## Befunde

Gelesene Fassungen (je aus der laufenden Instanz, 2026-11-12): Wegwerf-Instanzen 32.0.15, 33.0.9, 34.0.4, 35.0.2 (`occ status`), SQLite, dazu 35.0.2 mit PostgreSQL 17.11 (`select version()`); Deck 1.16.9 auf 32.0.15 und 1.19.2 auf 35.0.2, Tasks 0.18.1 auf 35.0.2 (`occ app:list --output=json`); nc35 mit Nextcloud 35.0.0, Deck 1.19.0, ExApp 0.3.2.

### Frisches Konto (M5.1, Bericht 5.1)

```
ERSTANMELDUNG weg=basic
FRISCHES KONTO aufgabenlisten=0 kalender=personal(VEVENT),contact_birthdays(VEVENT)
```

Beide Zeilen wortgleich auf 32.0.15 und 35.0.2. Vor der Anmeldung: `status=404 sammlungen=0 kalender_db=0`. Gegenprobe über die Tabelle `calendars`: `kalender_db=2 personal:VEVENT:leer contact_birthdays:VEVENT:leer aufgabenlisten_db=0`. Am Rand beobachtet: ein Konto, das nur mit App-Passwort aus occ oder unter Impersonation arbeitet, hat nicht einmal `personal` (alice auf 35.0.2, spike30a auf nc35).

### Sammlungsarten (M5.2, Bericht 5.2), gleich auf 32.0.15 und 35.0.2

| Art | Merkmal | Folge |
|---|---|---|
| eigene Aufgabenliste | `calendar`, Set `VTODO` | Aufgabenliste |
| Kalender mit `VEVENT` und `VTODO` | `calendar`, beide | in beiden Bundles (A11 belegt) |
| Deck | URI `app-generated--deck--board-<n>`, `calendar`, Set `VTODO`, kein Schreibprivileg | nur am Präfix auszuschließen |
| Papierkorb | URI `trashbin`, Typ `trash-bin`, kein Set | keine Aufgabenliste |
| gelöschter Kalender | Typ `deleted-calendar`, Set `VTODO`, Schreibprivileg | über den resourcetype auszuschließen |
| Abonnement | Typ `subscribed`, Set `VTODO,VEVENT`, Schreibprivileg | über den resourcetype auszuschließen |
| geteilt mit Schreibrecht | `<uri>_shared_by_<konto>`, `read-only` leer; PUT 201 | Aufgabenliste |
| geteilt ohne Schreibrecht | `read-only` 1, kein Schreibprivileg; PUT 404 | lesbare Aufgabenliste |
| föderiert | ungemessen | zweite Instanz nötig |

### Abfragen (M5.3, Bericht 5.3)

`A1 alle_sechs_abfragen_auf_allen_versionen_gleich=ja versionen=32.0.15,33.0.9,34.0.4,35.0.2 vollstaendig=ja`. Fünf der sechs Abfragen liefern die Menge, die der Connector will. Das Zeitfenster nicht: `ABFRAGE fenster client=q-in-arbeit,q-offen-im-fenster gleich=nein nur_server=['q-abgebrochen', 'q-kind', 'q-offen-undatiert'] nur_client=[]`.

### Provider-Link (M5.4), create-only PUT (M5.5)

```
PROVIDER tasks treffer=3 link=http://127.0.0.1:8083/apps/tasks/calendars/spike30-aufgaben/tasks/s30-q-offen-undatiert-011745.ics
PROVIDER aufloesung status=200 uid_gleich=ja kalender=spike30-aufgaben objekt=s30-q-offen-undatiert-011745.ics
PROVIDER tasks app_aus treffer=0 status=200
VTODO anlegen auth=appapi status=201 nutzer=spike30a If-None-Match=* objekt=spike30-anlegen/s30-anlegen-appapi-012915.ics etag=stark
VTODO anlegen zweiter status=412 objekt_unveraendert=ja auth=appapi
VTODO anlegen falsches_secret status=401 angelegt_db=nein
VTODO GLEICH appapi_basic=ja appapi=201/412/ja basic=201/412/ja
```

### Kosten (M6.1 bis M6.3, Bericht 6)

| | SQLite | PostgreSQL |
|---|---|---|
| offen | `KOSTEN offen status=207 treffer=100 bytes=70274 min=106 median=108 p95_zweitgroesster=112 max=148 (n=15)` | `KOSTEN offen status=207 treffer=100 bytes=70274 min=129 median=150 p95_zweitgroesster=168 max=185 (n=15)` |
| alle | `KOSTEN alle status=207 treffer=2000 bytes=1521874 min=146 median=148 p95_zweitgroesster=257 max=337 (n=15)` | `KOSTEN alle status=207 treffer=2000 bytes=1521874 min=172 median=186 p95_zweitgroesster=205 max=225 (n=15)` |
| calendar-search | `status=207 treffer=10 bytes=7364 ms=77` | `status=207 treffer=10 bytes=7364 ms=110` |
| Bezug | Discovery 44 ms, status.php 13 ms | Discovery 80 ms, status.php 20 ms |

Ableitungsregel angewandt: Bezugswert 186 ms (größerer Median, höchstens 1,0 s), also erster Zweig; größter Maximalwert 337 ms, doppelt 674 ms, aufgerundet 1 s. Beide `VORSCHLAG`-Zeilen nennen "eine Abfrage je Liste ohne zusätzlichen Deckel unterhalb von 2000 Objekten, Zeitbudget je Liste 1 s". Der Vorfilter offen spart Übertragung (Faktor 21), kaum Zeit. Grenzen in Bericht 6: Einzelhost ohne Netzwerkstrecke, frische Instanz, eine Liste mit kleinen Objekten, nur 35.0.2, kein MySQL.

### Fixtures (M5.6, Bericht 5.6)

Acht Dateien, alle `sha256_gleich=ja`, keine Art fehlt. `A2 related_to_gleich_eltern_uid=ja gleiche_liste=ja reltype=fehlt`. `A3 zeitform due=date+utc dtstart=utc completed=utc`, Gegenprobe mit icalendar `gleich=ja`, `A3 schwebend_vorhanden=nein tzid_vorhanden=nein`. Zwei Discovery-Fixtures von 35.0.2 (`aufgabenlisten=0` und `aufgabenlisten=4`, `nur_probewerte=ja`).

### Annahmen

| Annahme | Stand |
|---|---|
| A1 | belegt, 32.0.15 bis 35.0.2 |
| A2 | belegt für Tasks 0.18.1 |
| A3 | belegt für Tasks 0.18.1 (UTC und Datum; nichts schwebend, kein TZID) |
| A4 | belegt auf 32.0.15 und 35.0.2 |
| A5 | Papierkorb: erkennbar, kein Komponenten-Set. Gelöschte Kalender: widerlegt, sie bleiben mit Set und Schreibprivileg im Home. Föderiert: ungemessen, zweite Instanz nötig |
| A6 | belegt als Größenordnung (Zahlen oben) |
| A11 | belegt auf 32.0.15 und 35.0.2 |

### Bedeutung für Phase 32

- TASK-01: Regel "resourcetype `calendar` UND `VTODO` im Set UND kein Präfix `app-generated--`". Der heutige Terminfilter prüft den resourcetype `calendar` nicht; ein gelöschter Terminkalender käme durch (abgeleitet, nicht gemessen). Gehört in die Übergabe 30-05.
- TASK-02: Fälligkeitsgrenze und `CANCELLED` filtert der Connector; Zahlen für Deckel und Zeitbudget liegen vor.
- TASK-03: Fixture `tests/fixtures/caldav_home_fresh_account.xml`; daneben existiert der Fall "gar kein Kalender".
- TASK-04: für "mit Zone" und "schwebend" gibt es keine von der App geschriebenen Objekte.
- TASK-09: Linkmuster belegt; eine leere Provider-Antwort kann "Tasks-App nicht aktiv" heißen.
- `.planning/REQUIREMENTS.md` ist in diesem Plan nicht geändert (geschieht in 30-05).

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | 0414658 (Tests, RED), 90aec5e (Blöcke, Kriterien, Ableitungsregel) | Werkzeug und Kriterien, vor jeder Rohdatei dieses Plans |
| 2 | 57f60f6 (Werkzeugfix), cab2d62 (sieben Rohprotokolle) | sieben Läufe nacheinander |
| 3 | 8b75c70 | Fixtures, Bericht 5, 6, 11, 12.8 bis 12.10 |

## Wiederholungen

Kein Messwert wurde wiederholt, bis er passte. Vorgänge an Lauf 1 (32.0.15), alle in `raw/discovery-32.txt` sichtbar:

1. Abbruch am RAM-Tor, nichts gestartet: `RAM frei_host_gb=3.65 schwelle=4.0 ergebnis=zu wenig`.
2. Ein Startversuch wurde vom Harness wegen Speichermangel beendet, bevor etwas gemessen oder geschrieben war; der verwaiste Container samt Volume wurde von Hand abgebaut. Der nächste Lauf trägt `WIEDERHOLUNG Grund: Lauf wurde vom Harness wegen Speichermangel beendet, kein Messwert`.
3. Dieser Lauf hat gemessen, mit einem Werkzeugfehler: Deck-REST 404 direkt nach `occ app:install deck`. Fix 57f60f6 (Neustart nach Installation), dann kompletter Neulauf auf frischem Volume mit `WIEDERHOLUNG Grund: Werkzeugfehler im Lauf davor ...`. Alle gemeinsamen Werte beider Läufe sind gleich.

Der Block fixtures lief zweimal: einmal vor den Läufen (Docker stand still, nur die Objekte der App), einmal danach mit Zeile `WIEDERHOLUNG Grund` (Discovery-Fixtures und A1).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Deck-REST antwortete nach `occ app:install` mit 404**
- **Found during:** Task 2, Lauf 1
- **Issue:** Der Webserver las die App-Liste noch aus APCu; das Board entstand nicht, die Art deck fehlte.
- **Fix:** `restart_instance()` nach `occ app:install deck`, nach `occ app:install tasks` und nach `occ app:disable tasks`.
- **Commit:** 57f60f6

**2. [Rule 1 - Bug] Auswertung kannte den resourcetype `deleted-calendar` nicht**
- **Found during:** Task 2, Lauf 1
- **Issue:** `classify_collection()` zählte den gelöschten Kalender als Aufgabenliste (`POSITIVKONTROLLE aufgabenlisten_alice=5`).
- **Fix:** eigene Art "geloeschter-kalender"; die Änderung der vorab festgelegten Auswertung steht offen im Bericht bei den Kriterien, der alte Lauf bleibt in der Rohdatei. Der Befund selbst (A5) ist dadurch nicht verändert, nur benannt.
- **Commit:** 57f60f6

**3. [Rule 2] Fixtures byte-genau halten**
- `.gitattributes`: `-text` für `tests/fixtures/tasks_app/*.ics` und die beiden Discovery-Antworten; stand nicht in der Dateiliste des Plans. Geprüft: sha256 des Blobs in git gleich sha256 der Datei.

**4. [Rule 2] Wertbildung vorab festgeschrieben**
- Absatz "Wie das Messskript die Werte dieses Plans bildet" im Bericht, mit dem Kriterien-Commit.

### Sonstiges

- **`FRISCHES KONTO vor_anmeldung`** per PROPFIND als admin plus Tabelle `calendars`: eine Anfrage im Namen des frischen Kontos wäre schon dessen Erstanmeldung.
- **Aufbau der 2000 Aufgaben** auf SQLite seriell statt vierfach (`database is locked` aus 30-02), auf PostgreSQL vierfach; kein PUT musste wiederholt werden.
- **`VORSCHLAG` je Kostendatei** gilt für die eine Datenbank; der Bezugswert über beide steht im Bericht.
- **Zusätzliche Rohdatei `raw/fixtures.txt`** (Protokoll des Blocks fixtures samt A1-Vergleich).
- **Zusätzliche getestete Helfer:** parse_home, probe_values_only, raw_body_from_protocol, time_form, summarize, series_line.
- **Zusätzliche Zeilen:** Provider vor der Installation der Tasks-App und Liste der Provider-Ids; Schreibversuch auch in die schreibbare Freigabe (Positivkontrolle); `TERMINFILTER heute liefert=`.
- **vtodo-create** fährt die Deck-Discovery auf nc35 immer, nicht nur bei Fehlschlag auf der Wegwerf-Instanz.
- **Seitencache der Docker-VM** vor jedem Lauf geleert (`drop_caches`, bei abgebauter Instanz, danach 75 s gewartet), auf Anweisung des Orchestrators; das Gate blieb unverändert.
- **Vorab aus dem Image gelesen** (kein Instanzlauf, kein Messwert): Elementnamen von `calendar-search`, Linkform in `TasksSearchProvider.php`, `components => 'VEVENT'` beim ersten Login.
- **TDD:** Tests vor dem Code (0414658, RED gesehen); die Tests zu raw_body_from_protocol und time_form kamen mit dem Code.
- **Dauer der Läufe** weit unter der Planungsschätzung: 40 bis 70 s je Discovery-Lauf, 167 s und 164 s je Kostenlauf.
- `vulture_whitelist.py` blieb unverändert. `.env.nc35` wurde aus dem Hauptcheckout nur gelesen. Kein Push, kein PR, kein Kommentar.

## Zustand nach dem Rückbau

- Wegwerf-Instanzen: nach jedem der sechs Läufe `ABBAU Container vorhanden: nein` und `ABBAU Volume vorhanden: nein`; am Planende kein Container und kein Volume mit `nc-spike-tags`.
- nc35: alle zwölf BASELINE-Zeilen gleich=ja, `RUECKBAU deck_boards_mit_praefix_spike30=0`, kein Konto mit Präfix; die vier Container gestoppt.
- Es läuft nur der fremde Container `gameworld-dev-gameworld-docker-proxy-1`, unberührt.

## Was ungemessen blieb

Vollständig in docs/spike-tasks.md, Abschnitt 11. Kurz: föderierte Kalender; Discovery der Sammlungsarten auf 33 und 34; Discovery und Abfragen unter Impersonation auf 32 bis 34; welche Anmeldewege den Standardkalender auslösen; Erstanmeldung über das Web-Formular; gelöschter Terminkalender im heutigen Terminfilter; Freigaben an Gruppen; Textsuche mit anderer Schreibweise; undatierte Aufgabe ohne `CREATED`; Provider-Link für geteilte Listen, Deck und Sonderzeichen; create-only PUT unter Impersonation auf 32 bis 34; von der App geschriebene Objekte mit Zone oder schwebender Zeit; Kosten auf MySQL und MariaDB, auf 32 bis 34, über mehrere oder geteilte Listen, über eine Netzwerkstrecke; `calendar-search` als Reihe.

## Known Stubs

Keine. Die Abschnitte 8 bis 10 des Berichts tragen mit Absicht den Vermerk "offen" (Plan 30-05). Die neuen Fixtures liest noch kein Test; sie sind Vorarbeit für die Phasen 32 und 33.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus. T-30-20 bis T-30-25 umgesetzt: Zufallspasswörter je Lauf über Umgebung und stdin, psql über den lokalen Socket; Fixtures nur mit Probewerten (`probe_values_only`, `nur_probewerte=ja`); Abonnement-Quelle `http://127.0.0.1:9/keine.ics`; RAM-Tor vor jedem Lauf, nichts lief daneben; Ableitungsregel als getestete Funktion vor der Messung; nc35 mit Rückbau und Baseline. T-30-SC: `deck` und `tasks` aus dem App Store nur in Wegwerf-Instanzen, kein Image neu gezogen, kein Paket installiert. Secret-Scan vor jedem Commit mit Rohdateien: 50 Dateien, 0 Funde, 1245 Zitate geprüft.

## Self-Check: PASSED

- Dateien vorhanden: sieben Rohprotokolle und raw/fixtures.txt; tests/fixtures/tasks_app/ mit acht .ics und PROVENANCE.md; beide Discovery-Fixtures; docs/spike-tasks.md mit 5.1 bis 5.6, 6, 12.8 bis 12.10
- Commits vorhanden: 0414658, 90aec5e, 57f60f6, cab2d62, 8b75c70
- verify Task 1, Task 2 und Task 3: je Exit 0 (voller Lauf nach R1 grün, `git status --porcelain src` leer)

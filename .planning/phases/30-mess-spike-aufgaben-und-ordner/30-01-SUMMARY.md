---
phase: 30-mess-spike-aufgaben-und-ordner
plan: 01
subsystem: messwerkzeug / MKCOL und Gruppenordner auf nc35
tags: [spike, mkcol, webdav, appapi, impersonation, groupfolders, acl, files_external, messung]
requires: []
provides:
  - scripts/tasks_spike.py (Blöcke nc35-up, controls, mkcol, groupfolder, nachlauf, nc35-stop, secret-scan; RAM-Gate, Baseline, Rückbau; Helfer für 30-02 bis 30-05)
  - docs/spike-tasks.md (Kopfblock, vorab festgelegte Kriterien, Abschnitte 1, 2, 11 und 12.1, 12.2; feste Überschriften 1 bis 12 als Linkziele)
  - raw/nc35-mkcol.txt (erster Messpunkt, Statusmatrix unter Impersonation und mit App-Passwort)
  - raw/nc35-gruppenordner.txt (Gruppenordner mit ACL, Negativtest, externer Speicher, Nachlauf des Rückbaus)
affects: [30-02, 30-03, 30-04, 30-05, 31]
tech-stack:
  added: []
  patterns:
    - "Messskript nach scripts/tag_spike.py: guarded-Unterblöcke, Rückbau im finally, Baseline-Vergleich als letzte Zeilen, Protokoll erst nach scan_for_secrets"
    - "RAM-Gate vor jedem Block mit Nextcloud: mindestens 4 GB freier Host-Speicher, kein fremder Nextcloud-, Datenbank- oder Connector-Container; stoppt nie etwas Fremdes"
    - "angelegt = im Dateisystem des Containers nach dem Aufruf vorhanden und vorher nicht; Ablehnung zählt nur ohne angelegten Ordner (refused wirft bei Widerspruch)"
    - "jede im Bericht unter Rohausgaben zitierte Zeile wird im Block secret-scan gegen die Rohdateien geprüft"
key-files:
  created:
    - scripts/tasks_spike.py
    - tests/unit/test_tasks_spike.py
    - docs/spike-tasks.md
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/nc35-mkcol.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/raw/nc35-gruppenordner.txt
    - .planning/phases/30-mess-spike-aufgaben-und-ordner/deferred-items.md
  modified:
    - vulture_whitelist.py
decisions:
  - "A7 belegt: MKCOL auf files/ antwortet unter AppAPI-Impersonation mit 201 (Nextcloud 35.0.0, SQLite); das Abbruchkriterium MESS-01 ist nicht ausgelöst"
  - "A9 widerlegt: MKCOL antwortet bei erschöpftem Kontingent mit 507; der Zweig in FOLD-01 wird gebraucht"
  - "A8 belegt für Gruppenordner mit ACL-Regel, Gruppe mit reinem Leserecht, nur lesbaren lokalen externen Speicher und Freigabe ohne Anlegerecht: immer 403 mit leerem s:message"
  - "405 unterscheidet nicht zwischen vorhandenem Ordner und vorhandener Datei, 409 nicht zwischen fehlendem Elternordner und Datei als Elternknoten; FOLD-01 braucht dafür einen zweiten Aufruf oder die Meldung"
  - "Rückbau auf nc35 löscht auch die drei App-Konfigurationswerte, die eine einmal eingeschaltete App nach app:disable und app:remove behält"
metrics:
  duration: "ca. 30 min"
  completed: 2026-11-11
  tasks: 3
  files: 7
---

# Phase 30 Plan 01: Messwerkzeug, MKCOL unter Impersonation, Gruppenordner mit ACL Summary

Messskript `scripts/tasks_spike.py` mit getesteten Helfern und RAM-Gate gebaut, die Kriterien vor dem ersten Messwert committet und damit auf nc35 (Nextcloud 35.0.0, SQLite) gemessen: `MKCOL` auf `files/` liefert unter AppAPI-Impersonation 201, alle vierzehn Zeilen der Statusmatrix sind statusgleich mit dem App-Passwort, ein Gruppenordner mit ACL legt mit Schreibrecht an und lehnt ohne Schreibrecht mit 403 ab. Eine Erwartung der Recherche ist widerlegt: bei erschöpftem Kontingent antwortet `MKCOL` mit 507.

## Befunde

Gelesene Fassungen (aus der laufenden Instanz, 2026-11-11): Nextcloud 35.0.0 (Build 35.0.0.10, `occ status`), `app_api` 35.0.0 (`occ app:list`), ExApp `mcp_connector` 0.3.2 (`occ app_api:app:list`), `groupfolders` 23.0.1 (`occ app:list` nach `occ app:install`), `files_external` 2.0.0-dev.0, Datenbank `sqlite3`.

### MESS-01 (Rohbeleg: raw/nc35-mkcol.txt)

| Punkt | Ergebnis |
|---|---|
| erster Messpunkt | `MKCOL frei auth=appapi status=201 angelegt=ja erwartet=201`, davor PROPFIND 404; `ABBRUCHKRITERIUM MESS-01 ausgeloest=nein status=201` |
| Positivkontrollen | Kontrolle a (cloud/user nennt spike30a, 200), Kontrolle b (falsches Secret 401), Zeile `"method":"MKCOL"` mit `"user":"spike30a"` in exapp_impersonation.log |
| Gegenproben | Dateisystem `vorhanden=ja`; falsches Secret 401, nichts angelegt; fremdes Home 403, nichts angelegt |
| Produktionsweg | MKCOL aus dem ExApp-Container gegen http://caddy: 201, angelegt |
| Matrix (appapi und basic gleich) | frei 201, ordner-vorhanden 405, datei-vorhanden 405, eltern-fehlt 409, eltern-ist-datei 409, name-htaccess 400, name-backslash 400, name-ueberlang 400, share-ro 403, share-rw 201, root-vorhanden 201, root-fehlt 409, root-selbst 405, **quota 507 (erwartet 201)** |
| Vergleich | `MKCOL GLEICH appapi_basic=ja abweichend=keine` |

### MESS-02 (Rohbeleg: raw/nc35-gruppenordner.txt)

| Punkt | Ergebnis |
|---|---|
| Gruppenordner mit Schreibrecht | `E12 POSITIV angelegt=ja status=201` |
| Negativtest (ACL-Regel gegen spike30a) | `E12 NEGATIVTEST abgelehnt=ja status=403 a8_403=belegt`, nichts im Dateisystem |
| Kontrollen | Konto ohne Regel im selben Ordner 201; nach Entfernen der Regel legt auch spike30a an (201) |
| Gegenproben | `oc:permissions` RMGDNVCK gegen RMG, `nc:acl-list` nennt die Regel |
| Gruppe mit reinem Leserecht | 403, nichts angelegt |
| externer Speicher (lokal) | mit `readonly` 403 und nichts angelegt, ohne `readonly` 201: `EXTERN A8 abgelehnt=ja status=403 a8_403=belegt positivkontrolle_rw=201` |

Alle Zeilen laufen je einmal unter Impersonation und mit App-Passwort und sind statusgleich.

### Bedeutung für Phase 31

- Das Abbruchkriterium MESS-01 ist nicht ausgelöst: Phase 31 darf geplant werden. MESS-01 und MESS-02, von denen Phase 31 abhängt, sind gemessen.
- FOLD-01 braucht eigene Zweige für 201, 405, 409, 400, 403 und 507; 400 und 507 kommen vor.
- 403 kommt in vier Fällen mit derselben Ausnahme und leerem `s:message`; die Meldung "keine Rechte" kann sich nicht auf den Text des Servers stützen.
- Die 201-Antwort hat keinen Body, die Kennung des neuen Ordners steht im Antwortkopf `oc-fileid`.

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | 5d13281 (Tests), 63ad052 (Skriptgerüst und Kriterien) | Helfer-Tests, Skript mit RAM-Gate, Baseline, Rückbau, Berichtskopf mit vorab festgelegten Kriterien |
| 2 | dec1c3e (Block mkcol), 8c81a7c (Rohprotokoll und Abschnitt 1) | erster Messpunkt, Statusmatrix |
| 3 | 69ec2a8 (Block groupfolder und nachlauf), 38d8c6a (Rohprotokoll, Abschnitte 2, 11, 12.2) | Gruppenordner mit ACL, externer Speicher, Rückbau |

Der Commit 63ad052 mit den Kriterien liegt vor jeder Rohdatei.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rückbau fand die Gruppenordner nicht**
- **Found during:** Task 3, nach dem gemessenen Lauf
- **Issue:** `occ groupfolders:list --output=json` nennt das Feld `mountPoint`, der Rückbau suchte `mount_point`. Die beiden Gruppenordner wurden nicht gelöscht; die App war danach entfernt, die Ordner standen noch in der Datenbank. Die Baseline zeigte trotzdem zwölfmal gleich=ja, weil sie Gruppenordner nicht erfasst.
- **Fix:** Feldname korrigiert; neuer Block `nachlauf` (App erneut installieren, Ordner mit `occ groupfolders:delete` löschen, App entfernen, Baseline vergleichen). Als zweiter Lauf an `raw/nc35-gruppenordner.txt` angehängt; `occ groupfolders:list --output=json` danach: `[]`.
- **Files modified:** scripts/tasks_spike.py
- **Commit:** 69ec2a8

**2. [Rule 1 - Bug] Eine einmal eingeschaltete App hinterlässt Konfigurationswerte**
- **Found during:** Task 3, Lesen der Hilfetexte
- **Issue:** Nach `occ app:disable` und selbst nach `occ app:remove` bleiben `installed_version`, `enabled` und `types` stehen; `occ app:list` zeigt `files_external` dann als "(installed ...)", die Baseline wäre ungleich.
- **Fix:** `restore_apps` löscht diese drei Werte für Apps, die vor dem Lauf nie eingeschaltet waren.
- **Commit:** 69ec2a8

**3. [Rule 2] Absicherungen im Skript über den Plan hinaus**
- `note()` ersetzt einen bekannten Secret-Wert schon vor der Ausgabe auf der Konsole; der Scan in `write_protocol` bleibt die zweite Sperre.
- Rohantworten lassen neben Authorization-Zeilen auch Cookie-Zeilen weg.
- Der Zeitstempel für die Suche im Impersonationsprotokoll kommt von der Uhr des Containers, nicht des Hosts.
- Block `secret-scan` prüft zusätzlich, dass jedes Zitat unter "12. Rohausgaben" wörtlich in einer Rohdatei steht.

### Sonstiges

- **Voller Lauf nach R1 nicht grün, Ursache außerhalb des Plans (DI-30-01):** Der Umgebung des Worktrees fehlt das Extra `documents`. `pytest tests/unit tests/contract` bricht beim Einsammeln von vier Modulen ab; ohne diese vier scheitern sieben Tests mit "needs the documents extra, which is not installed", alle übrigen bestehen. `pyright` über das ganze Repository meldet 19 Importfehler in denselben Dateien; für die Dateien des Plans 0 Fehler. `ruff check .`, `ruff format --check .`, `vulture`, `scripts/check_tool_budget.py`, die Tests des Plans, die Contract-Tests und der Vokabeltest sind grün. Nichts installiert, weil der Plan `--no-sync` vorschreibt.
- **Hilfetexte vorab gelesen:** `groupfolders` und `files_external` wurden vor dem gemessenen Lauf einmal von Hand eingeschaltet, um die Kommandoformen an der laufenden Instanz zu bestätigen, und wieder zurückgenommen. Kein Messwert daraus; der gemessene Lauf begann mit `installiert_vorher=nein`.
- **Erster MKCOL der Phase ist der gemessene:** der Basisordner `/spike30` entsteht über einen `PUT` mit `X-NC-WebDAV-Auto-Mkcol`, nicht über einen `MKCOL`. Der Plan ließ offen, wie der Ordner entsteht.
- **Block nc35-stop** ruft das RAM-Gate nur protokollierend auf: ein Stopp gibt Speicher frei und darf vom Gate nicht aufgehalten werden.
- **Zusätzlicher Block `nachlauf`** und Option `--repeat-reason` (nicht gebraucht: kein Messlauf musste wiederholt werden).
- **Commits je Task getrennt** in Skript (feat) und Messergebnis (docs), statt je eines Commits; Task 1 zusätzlich mit eigenem Test-Commit.
- **TDD:** die Tests entstanden vor dem Skript; der RED-Lauf ist nicht als eigener Beleg festgehalten (der erste Aufruf scheiterte an einer unbekannten pytest-Option, bevor er Tests einsammelte).
- `.env.nc35` wurde aus dem Hauptcheckout nur gelesen.

## Zustand nach dem Rückbau

- nc35: alle zwölf BASELINE-Zeilen gleich=ja nach jedem der drei Läufe; keine Konten, Gruppen, Gruppenordner oder externen Speicher mit Präfix spike30; `groupfolders` entfernt, `files_external` aus.
- Container `nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc_app_mcp_connector` gestoppt, wie vor dem Plan. Kein fremder Container wurde angefasst.
- Rest, der bleibt: die leeren Datenbanktabellen von `groupfolders` und `files_external` (`occ app:remove` und `occ app:disable` nehmen sie nicht weg).

## Was ungemessen blieb

Vollständig in docs/spike-tasks.md, Abschnitt 11. Kurz: Impersonation und Matrix nur auf 35.0.0 (auf 32 bis 34 gibt es keine ExApp-Registrierung); nur SQLite; Produktionsweg nur als roher `MKCOL` aus dem Container, nicht über ein Werkzeug der App (registriertes Image 0.3.2); Kontingent nur im erschöpften Zustand; ACL-Regeln nur gegen ein einzelnes Konto; externer Speicher nur lokal; weitere unzulässige Namen nur gelesen.

## Known Stubs

Keine. Die Abschnitte 3 bis 10 des Berichts tragen mit Absicht den Vermerk "offen" samt dem Plan, der sie füllt (30-02 bis 30-05).

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus (T-30-01 bis T-30-07 umgesetzt: Passwörter nur über stdin, Scan vor dem Schreiben und vor jedem Commit, ExApp-Programm druckt nur den Status, eigene Messkonten mit Präfix und Rückbau im finally, externer Speicher nur für das Messkonto, Kontrollen a, b, c und Gegenprobe mit falschem Secret, RAM-Gate und nc35-stop).

## Self-Check: PASSED

- Dateien vorhanden: scripts/tasks_spike.py, tests/unit/test_tasks_spike.py, docs/spike-tasks.md, raw/nc35-mkcol.txt, raw/nc35-gruppenordner.txt, deferred-items.md
- Commits vorhanden: 5d13281, 63ad052, dec1c3e, 8c81a7c, 69ec2a8, 38d8c6a

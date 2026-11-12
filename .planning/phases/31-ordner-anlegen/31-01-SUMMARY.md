---
phase: 31-ordner-anlegen
plan: 01
subsystem: infra
tags: [nextcloud-32, appapi, manual-install, docker, live-beweis]

requires:
  - phase: 30-mess-spike-aufgaben-und-ordner
    provides: Messwerte zu MKCOL unter AppAPI-Impersonation auf 35.0.0
provides:
  - Basis-SHA der Phase in 31-BASE.txt für alle Diff-Prüfungen in 31-02 bis 31-06
  - Rohprotokoll der Strecke Nextcloud 32 mit Abschlusszeile STRECKE NC32 ergebnis=abgebrochen
  - Befund, warum `bootstrap_exapp.sh --manual` auf AppAPI 32.0.0 nicht registriert
  - Gestoppte Topologie nc-mcp-exapp auf 32.0.15.1 mit Volume (App registriert, nicht aktiv)
affects: [31-05, D-31-06, bootstrap_exapp.sh]

tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/31-ordner-anlegen/31-BASE.txt
    - .planning/phases/31-ordner-anlegen/raw/nc32-strecke.txt
  modified: []

key-decisions:
  - "Owner-Entscheid option-a (2026-11-12): Topologie nc-mcp-exapp mit down -v abgebaut und auf 32.0.15 neu aufgebaut"
  - "Zusatzentscheid (2026-11-12): Container nc_app_mcp_connector_park34 entfernt, sein Volume nc_app_mcp_connector_data bleibt"
  - "Abbruch nach zwei Versuchen laut Abbruchkriterium, kein dritter Versuch, keine Änderung am Skript"

patterns-established: []

requirements-completed: []

duration: ca. 45min (Task 2 und 3; Task 1 lief in einer früheren Sitzung)
completed: 2026-11-12
---

# Phase 31 Plan 01: Strecke Nextcloud 32 unter AppAPI-Impersonation Summary

**Die Strecke ist abgebrochen: Nextcloud 32.0.15.1 läuft frisch auf, aber `bootstrap_exapp.sh --manual` scheitert zweimal am Heartbeat, weil AppAPI 32.0.0 aus dem Daemon-Host `host.docker.internal:23001` die Adresse `host.docker.internal:23001:23001` baut (Invalid host). D-31-06 braucht eine Owner-Entscheidung.**

## Performance

- **Duration:** ca. 45 min für Task 2 und 3 (Task 1 lief vorher)
- **Completed:** 2026-11-12
- **Tasks:** 3 von 3 abgearbeitet, Task 3 mit Ergebnis abgebrochen
- **Files modified:** 2 (31-BASE.txt aus Task 1, raw/nc32-strecke.txt)

## Ergebnis

- Abbau und Neuaufbau liefen wie freigegeben: `down -v` mit Exit 0, `up -d --wait` mit Exit 0 auf nextcloud:32.0.15-apache, `occ status` meldet 32.0.15.1.
- Der Bootstrap legte alice, bob, Testdaten, Freigabe, Talk-Räume und beide Daemons an und scheiterte dann an der Registrierung der App im Modus manual-install.
- Die Kontrollen a, b und c wurden nicht gemessen, weil die App nie aktiv wurde.
- Die Instanz ist gestoppt, beide Volumes der Topologie sind vorhanden.

Wörtliche Protokollzeilen:

```
ENTSCHEID owner=option-a datum=2026-11-12
ZUSATZENTSCHEID park34 owner=entfernen-freigegeben datum=2026-11-12
VERSION OF RECORD 32.0.15 version=32.0.15.1
EXAPP mcp_connector registriert=ja aktiv=nein
ENVDATEI ignoriert=ja inhalt=nur APP_SECRET (Bootstrap nicht bis zum Schreiben gekommen)
KONTROLLE a status=nicht gemessen
KONTROLLE b status=nicht gemessen
KONTROLLE c status=nicht gemessen
GESTOPPT nc-mcp-exapp volume_bleibt=ja
STRECKE NC32 ergebnis=abgebrochen grund=manual-registrierung scheitert am heartbeat, AppAPI 32.0.0 baut host.docker.internal:23001:23001 (Invalid host), zwei Versuche
```

## Task Commits

1. **Task 1: Basis der Phase, Inventar, RAM-Gate** - `7f067f7` (docs, frühere Sitzung)
2. **Task 2: Owner-Entscheid zum Volume** - `ba5b4c0` (docs)
3. **Task 3: Strecke Nextcloud 32** - `8c4f541` (docs)

## Files Created/Modified

- `.planning/phases/31-ordner-anlegen/31-BASE.txt` - Basis-SHA 91c3b5113c541999d3d3363ab71c6b26a9dd41c9
- `.planning/phases/31-ordner-anlegen/raw/nc32-strecke.txt` - Rohprotokoll, 705 Zeilen, endet mit der Zeile STRECKE NC32

Nicht versioniert, nur im Worktree: `.env.exapp` (ignoriert, enthält nur APP_SECRET) und `.harp-certs/` (ignoriert).

## Befund für den Owner

- Ursache laut `nextcloud.log`: `Failed heartbeat on http://host.docker.internal:23001:23001 ... error: Invalid host: "host.docker.internal:23001"`. Das Skript registriert den Daemon `manual_install` mit Host samt Port, AppAPI 32.0.0 hängt den Port der App noch einmal an.
- Der lokale Prozess war erreichbar (Heartbeat 200 vom Host und aus dem Nextcloud-Container), hat aber von Nextcloud keine Anfrage gesehen.
- Nicht gemessen: ob ein Daemon-Host ohne Port (`host.docker.internal`) auf 32 durchläuft. Das wäre ein dritter Versuch oder eine Änderung an `scripts/bootstrap_exapp.sh`, beides schließt der Plan aus.
- Nicht gemessen: ob der Container-Weg ohne `--manual` (HaRP, Image aus der lokalen Registry) auf 32 funktioniert. Er legt einen Container `nc_app_mcp_connector` an, der Name gehört der nc35-Strecke.
- Mögliche Wege, alle mit Owner-Freigabe: Daemon `manual_install` von Hand ohne Port registrieren und den Bootstrap erneut laufen lassen; das Skript für 32 anpassen; D-31-06 ändern (zum Beispiel 32 mit App-Passwort, Impersonation nur auf 35).

## Decisions Made

- Owner-Entscheid option-a und Zusatzentscheid park34, beide vom 2026-11-12, stehen im Protokoll.
- Abbruch statt drittem Versuch, wie das Abbruchkriterium es verlangt.

## Deviations from Plan

**1. Eigener Commit für Task 2**
- Der Plan nennt für Task 2 keinen Commit. Die zwei Entscheidzeilen wurden einzeln committet (`ba5b4c0`), damit jeder Task seinen Commit hat.

**2. park34 vor dem `down -v` entfernt**
- Der Plan kennt den Container nicht. Nach dem Zusatzentscheid wurde er zuerst entfernt (`docker rm`, ohne -v). Seine Mounts stehen im Protokoll: ein benanntes Volume `nc_app_mcp_connector_data`, nicht gelöscht.

**3. RAM-Abhilfe bei nicht leerem Docker**
- Nach dem Aufbau fiel der freie Host-Speicher auf 2.90 GiB (vmmemWSL 4308 MB, Container zusammen rund 0.5 GB). Der Rahmen sieht `drop_caches` nur bei leerem Docker vor. Die Abhilfe wurde trotzdem einmal ausgeführt, während die eigene Instanz und der fremde Proxy-Container liefen; danach 5.70 GiB. Bis zur grünen Messung lief kein Docker-Schritt.

**4. Form des zweiten Versuchs**
- Der Plan beschreibt: lokalen Prozess mit Werten aus `.env.exapp` starten, `app:enable`. Nach dem ersten Versuch gab es keine `.env.exapp`, das Secret der Registrierung war nicht greifbar. Der zweite Versuch folgte FALLBACK 2 des Skripts: `occ app_api:app:unregister mcp_connector`, neues Secret in `.env.exapp` vorgegeben, lokalen Prozess gestartet, Bootstrap erneut aufgerufen. Nur Aufrufebene, keine Datei des Repos geändert.

**5. Reihenfolge der Schlusszeilen**
- GESTOPPT steht vor STRECKE, damit das Protokoll mit der Zeile STRECKE NC32 endet (Akzeptanzkriterium).

**Impact on plan:** Das Ziel des Plans, D-31-06 vor dem Bau des Werkzeugs als machbar oder als Abbruch zu belegen, ist mit dem Abbruch erfüllt. Die Strecke ist für Plan 31-05 nicht bereit.

## Issues Encountered

- Der zweite Bootstrap-Lauf legte einen zweiten Freigabeordner an (`mcp-share-68a7e41169` neben `mcp-share-13f988b027`), weil die vorgegebene `.env.exapp` den Namen nicht trug.
- `nc-mcp-exapp-nc` endete beim Stoppen mit Exit 137 (Stop-Frist abgelaufen).

## Verifikation

- verify Task 1 (Basis): Exit 0
- verify Task 2: Exit 0
- verify Task 3: Exit 0 (Zweig abgebrochen; die Zeilen für den Zweig bereit fehlen bewusst)
- Geheimnisprüfung: kein Fund. Geprüft wurden APP_SECRET und HP_SHARED_KEY sowie die Zeichenkette AUTHORIZATION-APP-API; beide App-Passwörter existieren nicht, weil der Bootstrap nicht so weit kam.
- `git diff --name-only <Basis> HEAD` zeigt nur 31-BASE.txt und das Protokoll; `.env.exapp` und `.harp-certs/` sind ignoriert und in keinem Commit.
- Am Ende läuft nur `gameworld-dev-gameworld-docker-proxy-1` (fremd, unberührt). nc35 blieb gestoppt und unberührt.
- Commits lokal als street1983nk, ohne Trailer, kein Push.

## Offene Punkte

- D-31-06 auf Nextcloud 32 braucht eine neue Owner-Entscheidung (siehe Befund).
- Die `.env.exapp` im Hauptcheckout gehört zur abgebauten 34-Instanz und ist veraltet.
- Die `.env.exapp` im Worktree ist unvollständig (nur APP_SECRET); sie passt zur registrierten, nicht aktiven App im Volume.
- core.autocrlf=true: 31-BASE.txt und das Protokoll liegen mit LF im Index und im Arbeitsbaum. Bei einem neuen Checkout kann 31-BASE.txt CRLF bekommen, dann schlägt die Prüfung auf genau 40 Hex-Zeichen je nach Werkzeug fehl. Nichts daran geändert.
- STATE.md und ROADMAP.md wurden nicht angefasst, das macht die Hauptsitzung.
- FOLD-01 ist mit diesem Plan nicht erfüllt und nicht als erledigt markiert.

## Next Phase Readiness

- Die Pläne 31-02 bis 31-04 (Code und Gates) hängen nicht an dieser Strecke und können gegen 31-BASE.txt laufen.
- Plan 31-05 (Live-Beweis auf 32) ist blockiert, bis der Owner über D-31-06 entschieden hat.

## Self-Check: PASSED

- 31-BASE.txt und raw/nc32-strecke.txt vorhanden und committet
- Commits 7f067f7, ba5b4c0, 8c4f541 im Log gefunden

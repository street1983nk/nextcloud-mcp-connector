---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 07
subsystem: tasks-live-beweis
tags: [live-beweis, ganze-kette, oauth, harp, exapp, impersonation, tasks-app, nextcloud-35, nextcloud-32]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-01 (Strecke 32 bereit), 32-02 (FREIGABE zustand=option-a), 32-05 (Bundle registriert), 32-06 (fetch und Provider tasks), 32-05b (test_tasks_live.py, Kanarie, Abnahmeskript)
provides:
  - scripts/tasks_chain_evidence.py (connect, tools, call, same)
  - raw/32-07-nc35.txt (ganze Kette, Funktionsebene ohne und mit Tasks-App, Kanarie, Rückbau)
  - raw/32-07-nc32.txt (Funktionsebene ohne und mit Tasks-App, Abnahmeskript, Rückbau)
  - docs/tasks-evidence.md mit den Abschnitten der Live-Läufe
  - nc35 trägt die ExApp jetzt als Image dieses Branches (0.7.2, sha256:00a2e4b0...)
affects: [32-08, 33, 34]

tech-stack:
  added: []
  patterns:
    - "Vergleichsantworten über die alte Kette als Datei aufnehmen, nach dem Image-Wechsel bytegenau vergleichen (same)"
    - "Altes Image vor dem Wechsel lokal unter eigenem Tag sichern (0.7.2-vor32), weil der Bootstrap denselben Tag neu belegt"

key-files:
  created:
    - scripts/tasks_chain_evidence.py
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-07-nc35.txt
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-07-nc32.txt
  modified:
    - docs/tasks-evidence.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Owner-Entscheid (13.11.2026, 'Ok, wie deine Empfehlung'): Ein Provider-Treffer mit fremdem Ursprung bleibt eine task:-Id, wie überall im Modul (32-06, Abweichung 1)"
  - "Owner-Freigabe Task 2: FREIGABE owner=option-a datum=2026-11-13, nc35-ExApp neu registriert (unregister ohne --rm-data, bootstrap --nc35)"
  - "Abnahmeskript nicht auf nc35, sondern auf der 32er Strecke: es legt Objekte an, die es nicht löscht (Regel aus 31-05, strengere Regel gilt)"
  - "Familienzählung im Messprogramm wie in der README: neun App-Präfixe, alles andere (unified_search, search, fetch, prepare_context) ist die Familie Suche"

patterns-established:
  - "X-NC-CalDAV-No-Trashbin wirkt auf das Löschen einer Sammlung, nicht eines einzelnen Objekts; Papierkorb danach per REPORT calendar-query auf trashbin/objects/ prüfen und leeren"

requirements-completed: [TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-06, TASK-07, TASK-09]

duration: ca. 90min
completed: 2026-11-13
---

# Phase 32 Plan 07: Live-Beweis des Tasks-Bundles auf Nextcloud 35 und 32 Summary

**Das Bundle lief auf nc35 als ganze Kette (OAuth-Client, Caddy, HaRP, ExApp-Image dieses Branches, Impersonation: 27 Werkzeuge in zehn Familien, Termin-Antworten vor und nach dem Image-Wechsel bytegleich) und auf 35 und 32 je ohne und mit Tasks-App 0.18.1 auf Funktionsebene grün (4 x 17 passed), dazu Kanarie auf 35 (4 passed) und Abnahmeskript auf 32 (alle Aufgabenschritte OK). Kein Produktfehler, kein Produktcode geändert.**

## Ergebnis je Erfolgskriterium

| Kriterium | nc35 ohne Tasks-App | nc35 mit Tasks-App 0.18.1 | nc32 ohne Tasks-App | nc32 mit Tasks-App 0.18.1 |
|---|---|---|---|---|
| 1 TASK-03, zwei Konten (nur VEVENT nach Anmeldung; nie angemeldet) | ok | ok | ok | ok |
| 2 Standard nur offen, due_by ohne undatierte, keine Deck-Karte, degraded, kein Besitzername; Termin-Werkzeuge byte-gleich | ok; Kette: `KALENDER bytegleich=ja` | ok | ok | ok |
| 3 DUE;VALUE=DATE, Start, Tags, Priorität, Eltern; ohne list nur bei genau einer eigenen Liste; geteilt nur bei Nennung | ok; Kette: ROHOBJEKT mit `DUE;VALUE=DATE:20261120`, Ablehnung ohne list bei zwei Listen | ok | ok | ok; Abnahme schrieb ohne list in die einzige eigene Liste |
| 4 tasks_read und fetch gleiche Id, Provider-Treffer auf diese Id; ohne Tasks-App allgemeine Suche leer | ok; Kette: `count 0` mit degraded | ok; Kette: Treffer `task:p3207-aufgaben:3ef34ffe...` = Id von tasks_read/fetch | ok | ok |
| 5 (Release ohne Phase 33, CI) | nicht Teil dieses Plans; CI-Läufe folgen in 32-08 | | | |

Ganze Kette nur auf 35 (`KETTE nc32 entfaellt grund=manual-install`).

## Byte-Vergleich der Termin-Werkzeuge (nc35, über die Kette)

- `calendar_list_events`, Fenster 2026-11-25 UTC: `GLEICH ja bytes=304/304`
- `calendar_list_events`, Fenster November mit `timezone=Europe/Berlin`: `GLEICH ja bytes=324/324`
- Vorher über das Image cf01fc50 (Stand 31-07, 24 Werkzeuge), nachher über 00a2e4b0 (27 Werkzeuge). `calendar_create_event` wurde nicht über die Kette verglichen (zweiter Aufruf schreibt einen zweiten Termin); dort tragen der Unit-Pin der Kalenderkörper und `git diff` gegen die Basis über die drei Kalender-Testdateien (0 Zeilen, Gegentreffer 206 Zeilen im Messprogramm).

## Stand der nc35-ExApp und Rückweg

| | vorher | nachher |
|---|---|---|
| `occ app_api:app:list` | mcp_connector 0.7.2 [enabled] | mcp_connector 0.7.2 [enabled] |
| Image | 127.0.0.1:5000/mcp_connector:0.7.2, sha256:cf01fc50812e... (31-07) | 127.0.0.1:5000/mcp_connector:0.7.2, sha256:00a2e4b0bfb7... (HEAD ce5b173, src seit 32-06 unverändert) |
| tools/list über die Kette | 24, tasks=nein, familien=9 | 27, tasks=ja, familien=10 |
| APP_SECRET | | gleich (Hash-Vergleich ohne Ausgabe) |
| Volume nc_app_mcp_connector_data | vorhanden | vorhanden (ohne --rm-data) |
| Audit-Log | Schlüssel nicht gesetzt | für die Messung an, danach gelöscht; 649 Einträge, Kette ohne Bruch |

Die alte OAuth-Verbindung (vor dem Wechsel aufgebaut) antwortete danach mit 27 Werkzeugen.

**Rückweg (nicht ausgeführt):** Das alte Image liegt lokal als `127.0.0.1:5000/mcp_connector:0.7.2-vor32` (sha256:cf01fc50...). Nötig wären: nc35 und `nc-mcp-exapp-registry` starten, `docker tag ...:0.7.2-vor32 127.0.0.1:5000/mcp_connector:0.7.2` und `docker push`, ExApp-Container starten (AppAPI braucht zum Abmelden einen laufenden Prozess), `occ app_api:app:unregister mcp_connector` ohne `--rm-data`, dann neu registrieren. Achtung: `bootstrap_exapp.sh --nc35` baut das Image aus dem Checkout neu und überschreibt den Tag; für ein byte-gleiches Zurück braucht es einen Registrierungsweg ohne Neubau (nicht erprobt). Die Version in info.xml war vorher und nachher 0.7.2.

## Live-Läufe

| Lauf | Ergebnis |
|---|---|
| `LAUF nc35 tasksapp=keine` | 17 passed |
| `LAUF nc35 tasksapp=0.18.1` | 17 passed |
| `KANARIE nc35` (mit Tasks-App) | 4 passed, 27 von 27 je Fall, Aufräumen 21 von 21 Zeilen ok je Fall |
| `ABNAHME nc35` | lokal=nein, siehe Abweichung 1 |
| `LAUF nc32 tasksapp=keine` | 17 passed |
| `LAUF nc32 tasksapp=0.18.1` | 17 passed |
| `ABNAHME nc32` (mit Tasks-App) | exit 3: alle Aufgabenschritte OK, einziger Nicht-OK-Schritt `PREREQ fetch` einer Mail (GreenMail nach Neustart leer, wie 31-05b) |

Alle Läufe mit `NC_MCP_REQUIRE_LIVE=1`, ohne Abschnitt "warnings summary" (`-p no:warnings`).

## BASELINE (vorher = nachher)

| Instanz | Konto | Werte |
|---|---|---|
| nc35 | alice | calendars=1 objekte=31 geloescht=0 shares=0 abos=0, gleich=ja |
| nc35 | bob | calendars=2 objekte=1 geloescht=0 shares=0 abos=0, gleich=ja |
| nc32 | alice | calendars=1 objekte=3 geloescht=0 shares=0 abos=0, gleich=ja |
| nc32 | bob | calendars=2 objekte=1 geloescht=0 shares=0 abos=0, gleich=ja |

Dazu je Live-Lauf die BASELINE des Tests selbst (alice, bob, beide TASK-03-Konten) mit `gleich=ja`. Tasks-App auf beiden Instanzen zurück auf `keine` (App entfernt, Konfigurationsschlüssel gelöscht, `config:list tasks` leer).

## Anforderungen

- Abgehakt: TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-06, TASK-07, TASK-09 (REQUIREMENTS.md, Checkbox und Tabelle).
- Teile, die nur per Unit-Test belegt sind und live nicht gemessen wurden (bereits in 32-03 bis 32-06 als Code mit Tests geliefert): Blättern mit Deckel 500, wiederkehrende Aufgaben (`recurring`), übersprungenes Fremdobjekt, Zeitmatrix außer Datum, Abonnements und Scheduling-Sammlungen in der Discovery, 403 des Servers in eine geteilte Liste (live gab der Server für das Harness-PUT 404).
- TASK-07: CI-Läufe folgen in 32-08; das Abnahmeskript lief nur auf 32 und dort mit Exit 3 (Mail-Voraussetzung), alle Aufgabenschritte OK.

## Befunde

1. **No-Trashbin wirkt nur auf Sammlungen.** DELETE eines einzelnen Objekts mit `X-NC-CalDAV-No-Trashbin: 1` legt das Objekt trotzdem in den Papierkorb (nc32: 2 Objekte, 2 Einträge; nc35: 1 Eintrag). Papierkorb per REPORT gefunden und per DELETE geleert; BASELINE gleich. Der Live-Test löscht Listen und ist nicht betroffen.
2. **Audit:** `summary`/`description` stehen nicht in der Allowlist (gewollt). Ein Aufruf, den die Argumentprüfung des SDK ablehnt (Liste statt String bei `providers`), erzeugt keine Audit-Zeile.
3. **Links mit interner Adresse:** Über die Kette tragen `fetch`- und Suchtreffer-Links die Adresse, unter der die ExApp Nextcloud erreicht (`http://caddy`). Gilt für alle Id-Arten, Eigenschaft der Topologie, nicht des Bundles.
4. **Bootstrap baut neu:** Das vorab gebaute Image (2ecca8db) wurde vom Bootstrap durch einen eigenen Bau ersetzt (00a2e4b0); registriert ist das Image des Bootstraps.
5. Die Kanarie schreibt ihr Protokoll nach `.planning/phases/28-gates-und-beweise/raw/28-10-canary.txt`; der Block dieses Laufs wurde in raw/32-07-nc35.txt übernommen und die Datei aus Phase 28 zurückgesetzt.

## Task Commits

1. **Task 1: Messprogramm** - `5057987` (feat)
2. **Task 2: Owner-Freigabe** - `ce5b173` (docs)
3. **Task 3: Nextcloud 35** - `ce6c3bf` (docs)
4. **Task 4: Nextcloud 32, Beleg** - `b480ae1` (docs)

## Gates (32-RULES.md Abschnitt 3)

Vor `5057987` und vor `b480ae1`, alle Exit 0:
- pytest unit+contract: 6344 passed, 35 skipped
- check_tool_budget: `tools/list: 18747 bytes, 27 tools, budget 22000`
- ruff check: All checks passed; ruff format --check: 392 files already formatted
- pyright (latest): 0 errors, 0 warnings, 0 informations
- vulture: leer, kein Eintrag in vulture_whitelist.py nötig

TASK-01: Basis-Positivkontrolle grün; `git diff "$B"` über die drei Kalender-Testdateien leer, Gegentreffer im selben Diff (scripts/tasks_chain_evidence.py, 206 Zeilen). `src/` seit 32-06 unverändert.

docs/tasks-evidence.md: 171 Zeilen in Codeblöcken, jede wörtlich in einem Rohprotokoll (0 fehlen); kein `bob`, kein U+2013/U+2014. Geheimnisprüfung beider Protokolle, des Belegs und des Kanarien-Blocks gegen .env.nc35 und .env.exapp des Worktrees und .env.nc35 des Hauptcheckouts: Treffer nur auf öffentliche Werte.

## Deviations from Plan

**1. Abnahmeskript auf 32 statt auf nc35**
- Plan nennt nc35. 31-05 hält fest: "Nicht auf nc35: das Skript hinterlässt Objekte, die der Connector nicht löschen kann." Strengere Regel angewandt; Zeile `ABNAHME nc35 lokal=nein grund=hinterlaesst-objekte-auf-langzeitstrecke`, Lauf auf der 32er Strecke. Dort blieben Datei, Ordner, Notiz, Deck-Karte, Tabellenzeile und Talk-Nachricht des Laufs stehen (wie in 31-05b); Termin und Aufgabe per Harness entfernt.

**2. Zusätzliche Aufrufe über die Kette**
- Zweites Termin-Fenster mit Zone; `tasks_create` ohne list (Ablehnung, zwei Listen); `unified_search` und `search` mit und ohne Tasks-App (Provider-Treffer = task:-Id). Ein Fehlaufruf (falscher Typ, Zeitangabe ohne Zone) steht mit im Protokoll.

**3. Rückweg-Tag `0.7.2-vor32`** lokal angelegt, weil der Bootstrap denselben Tag 0.7.2 neu belegt.

**4. Papierkorbprüfung nachgeschärft**
- Erste Prüfung per PROPFIND war untauglich (501); ersetzt durch REPORT calendar-query (steht so im Protokoll). Welches Objekt der eine Eintrag auf nc35 war, wurde vor dem Löschen nicht protokolliert; nach Befund 1 auf 32 sehr wahrscheinlich der Termin p3207.

**5. Neustarts per `docker restart`** des Nextcloud-Containers für die Tasks-App (wie 32-02); `nc-mcp-exapp-nc` endete bei `compose stop` mit Exit 137 (Stopp-Frist überschritten), keine Folge sichtbar.

## Docker-Zustand am Ende

Kein Container läuft (`docker ps` leer). nc35 (`nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc35-greenmail`, `nc_app_mcp_connector`) und `nc-mcp-exapp-registry` per `docker stop` gestoppt; Strecke 32 per `docker compose -f compose.exapp.yml stop`. Lokaler Prozess beendet, Port 23001 frei. Keine fremden Container angefasst. nc35-ExApp bleibt auf dem neuen Stand registriert (so freigegeben).

## Known Stubs

Keine. Der CHANGELOG-Punkt "Measured ... docs/tasks-evidence.md" aus 32-05 ist mit diesem Plan gedeckt.

## Threat Flags

Keine neue Fläche. Token nur im Scratchpad (gelöscht), Ausgaben vor dem Protokoll geprüft (T-32-07-01); Owner-Checkpoint vor unregister, ohne --rm-data, Rückweg oben (T-32-07-02).

## Self-Check: PASSED

- Fünf Dateien vorhanden; Commits 5057987, ce5b173, ce6c3bf, b480ae1 im Verlauf, Autor street1983nk, ohne Trailer, ohne closes/fixes/resolves; nichts gepusht.
- Scratchpad p3207 (Token-Dateien, Zwischenausgaben, h.py) nach dem Plan gelöscht.

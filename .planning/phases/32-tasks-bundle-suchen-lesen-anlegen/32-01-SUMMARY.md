---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 01
subsystem: infra
tags: [nextcloud-32, appapi, manual-install, bootstrap, docker, live-beweis]

requires:
  - phase: 31-ordner-anlegen
    provides: Befund N4 und Daemon-Host (raw/nc32-strecke.txt ab Zeile 706), Strecke nc-mcp-exapp auf 32.0.15 mit Handeintrag
provides:
  - Basis-SHA der Phase in 32-BASE.txt für alle Diff-Prüfungen in 32-02 bis 32-08
  - Messung je Fassung 32/34/35 von `--name` und der Heartbeat-URL von resolveExAppUrl
  - scripts/bootstrap_exapp.sh läuft auf Nextcloud 32 mit --manual ohne Handeingriff (Erkennung der Option --name, Daemon-Host ohne Port)
  - Strecke nc-mcp-exapp auf 32.0.15 gestoppt und bereit, mcp_connector 0.7.2 registriert und aktiv am Daemon manual_install ohne Port
affects: [32-02, 32-07, D-32-12, D-32-13, bootstrap_exapp.sh]

tech-stack:
  added: []
  patterns:
    - "Feature-Erkennung aus occ --help statt Versionsvergleich"

key-files:
  created:
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-BASE.txt
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-01-bootstrap.txt
  modified:
    - scripts/bootstrap_exapp.sh
    - tests/unit/test_exapp_env_setup.py

key-decisions:
  - "D-32-13 umgesetzt: --name nur nach Treffer in der Hilfe von occ user:auth-tokens:add, Daemon manual_install mit Host host.docker.internal ohne Port; HaRP-Zweig unverändert"
  - "Owner-Freigabe FREIGABE unregister=option-a (2026-11-13): ExApp und Daemon auf der 32er Strecke abgemeldet und per Skript neu angelegt"
  - "Erster Anlauf abgebrochen (AppAPI verweigerte app:unregister ohne laufenden lokalen Prozess); zweiter Anlauf auf Aufrufebene mit laufendem Prozess, kein --force"

patterns-established:
  - "AppAPI manual-install: vor app:unregister muss der lokale Prozess laufen, sonst scheitert das Deaktivieren (cURL error 7) und die App bleibt [disabled] stehen"

requirements-completed: []

duration: ca. 75min
completed: 2026-11-13
---

# Phase 32 Plan 01: Bootstrap für Nextcloud 32 repariert Summary

**`bootstrap_exapp.sh --manual` legt auf Nextcloud 32.0.15 Daemon und ExApp ohne Handeingriff an: `--name` nur nach Erkennung in der occ-Hilfe, Daemon-Host ohne Port; auf 34 und 35 gemessen unverändert.**

## Performance

- **Dauer:** ca. 75 min (inklusive Owner-Checkpoint und zweitem Anlauf)
- **Beginn:** 2026-11-13T11:11:25Z
- **Ende:** 2026-11-13, nach dem Stopp der Strecke
- **Tasks:** 5 von 5 (Task 4 Owner-Checkpoint)
- **Geänderte Dateien:** 4 (2 neu in .planning, Skript, Test)

## Messung vor dem Umbau (Task 1)

| Fassung | occ status | app_api | `--name` | Heartbeat mit Port | Heartbeat ohne Port |
|---|---|---|---|---|---|
| nc32 | 32.0.15 | 32.0.0 | nein | `http://host.docker.internal:23001:23001` | `http://host.docker.internal:23001` |
| nc34 (Wegwerf 34.0.4) | 34.0.4 | 34.0.0 | ja, Standard "cli" | `http://host.docker.internal:23001` | `http://host.docker.internal:23001` |
| nc35 | 35.0.0 | 35.0.0 | ja, Standard "cli" | `http://host.docker.internal:23001` | `http://host.docker.internal:23001` |

`ENTSCHEID UMBAU name_erkennung=ok host_ohne_port=ok`. Ursache im Quelltext: `ManualActions::resolveExAppUrl` schneidet erst ab 34 mit `explode(':', $host)[0]` den Port ab.

## Accomplishments

- 32-BASE.txt: `b40f7623a5111b95a3fe3cf6e5295c4965ca7056` ("docs(32): create phase plan").
- `app_password`: lokales Array `token_name_args`, gefüllt nur bei Treffer von `occ user:auth-tokens:add --help | tr -d '\r' | grep -- '--name' >/dev/null`; Aufruf mit `${token_name_args[@]+"${token_name_args[@]}"}`. Auf 33 bis 35 bleibt der Aufruf wörtlich (Token mcp-exapp).
- `register_manual_install`: Host-Argument `"host.docker.internal"`. `git diff "$B" -- scripts/bootstrap_exapp.sh` berührt nur diese zwei Funktionen.
- Zwei Pins mit je zwei Gegenproben (`check_token_name_detection`, `check_portless_manual_daemon_host`).
- Lauf `--manual` auf 32.0.15: `daemon manual_install: registered`, `exapp mcp_connector: registered against the local process on port 23001`, `wrote .env.exapp`, Verifikation `mcp_connector (MCP Connector): 0.7.2 [enabled]`. AppAPI rief beim Prozess `/init`, `/heartbeat` und `PUT /enabled?enabled=1` mit 200 auf.
- `NACHHER daemon_manual=host.docker.internal app_version=0.7.2 registriert=ja aktiv=ja`, `ENVDATEI ignoriert=ja`.
- Kontrollen unter Impersonation: `KONTROLLE a status=200 id=alice`, `KONTROLLE b status=401`, `KONTROLLE c status=207`.
- `BOOTSTRAP NC32 ergebnis=bereit`.

## Gesicherter Zustand vor dem Eingriff (Task 3)

- `VORHER daemon_manual=host.docker.internal app_version=9.9.9 registriert=ja` (App war [enabled])
- `RUECKWEG daemon:register manual_install "Manual Install" manual-install http host.docker.internal http://caddy`
- Freigabe: `FREIGABE unregister=option-a datum=2026-11-13`

## Task Commits

1. **Task 1: Basis und Messung** - `118de59` (docs)
2. **Task 2: Umbau** - `b21bf78` (test, RED), `201e1ad` (fix, GREEN)
3. **Task 3: Zustand gesichert** - `52cffad` (docs)
4. **Task 4: Owner-Freigabe** - `d387bf6` (docs)
5. **Task 5: Lauf --manual** - `293b04b` (erster Anlauf abgebrochen), `fb205f6` (Protokollzeile ohne Kopfnamen), `326240d` (zweiter Anlauf, bereit)

## Gates (32-RULES.md Abschnitt 3, Stand fix-Commit 201e1ad)

- pytest unit+contract: 5965 passed, 35 skipped, Exit 0
- check_tool_budget: `tools/list: 16222 bytes, 24 tools, budget 18000`, Exit 0
- ruff check: All checks passed; ruff format --check: 376 files already formatted
- pyright (latest): 0 errors, 0 warnings, 0 informations
- vulture: Exit 0
- `bash -n scripts/bootstrap_exapp.sh` Exit 0
- Nach 201e1ad wurden nur Dateien unter .planning geändert; die Gates gelten unverändert.

## TDD Gate Compliance

- RED `b21bf78`: rot waren genau `test_the_bootstrap_detects_the_token_name_option` und `test_the_manual_daemon_is_registered_without_a_port`; die Gegenproben und alle übrigen 5963 Tests grün, ruff/pyright/vulture grün.
- GREEN `201e1ad`: alles grün.

## Deviations from Plan

**1. Messung und Zustandssicherung nur mit dem Nextcloud-Container**
- In Task 1 (nc32, nc35) und Task 3 wurde je nur der Nextcloud-Container per `docker start` gestartet statt der ganzen Topologie; für occ und den PHP-Aufruf genügt er, er spart RAM und braucht HP_SHARED_KEY nicht. 32-RULES.md Abschnitt 5 erlaubt `docker start`.

**2. PHP-Aufruf per stdin statt `php -r`**
- Gleichwertig: Skript aus dem Scratchpad an `php` im Container (www-data, `require '/var/www/html/lib/base.php'`), nur lesend.

**3. Erster Anlauf von Task 5 abgebrochen, zweiter Anlauf auf Aufrufebene**
- `occ app_api:app:unregister mcp_connector` endete mit exit=1 ("Error during disabling mcp_connector ExApp."): AppAPI ruft vorher `/enabled?enabled=0` beim lokalen Prozess, der nicht lief (cURL error 7). Folge: `daemon:unregister` verweigert ("contains 1 ExApps").
- Zwischenzustand: die App stand danach auf `9.9.9 [disabled]` statt `[enabled]`; Daemon unverändert. Der Plan hielt an (`BOOTSTRAP NC32 ergebnis=abgebrochen`), Topologie gestoppt, gemeldet.
- Nach Vorgabe des Orchestrators (Vorschlag 1, gedeckt durch option-a, kein --force) zweiter Anlauf: lokaler Prozess mit den fünf Variablen aus 31-05b, dann unregister (direkt erfolgreich, kein erneutes Aktivieren nötig), daemon:unregister, Skript. Zeile `WIEDERHOLUNG grund=app-unregister-braucht-laufenden-lokalen-prozess`. Das Protokoll enthält deshalb beide Abschlusszeilen; die letzte ist `BOOTSTRAP NC32 ergebnis=bereit`.

**4. RAM-Gate vor nc35 zunächst rot**
- 3,0 GB frei nach dem Abbau der Wegwerf-34; Abhilfe des Rahmens (drop_caches, 75 s) ergab 5,3 GB.

**5. Geheimnisprüfung: Treffer nur auf öffentliche Werte**
- Die Prüfung gegen alle Werte der Env-Dateien trifft APP_ID, APP_VERSION, URLs, Testkonten und Fixture-Namen. Kein Treffer aus APP_SECRET, Passwort-Variablen, HP_SHARED_KEY oder dem Kopfnamen. Eine eigene Beschreibung der Prüfung nannte den Kopfnamen wörtlich; in `fb205f6` umformuliert.

## Hinweise

- Nicht geändert (außerhalb von D-32-13): `scripts/bootstrap_test_nc.sh:219` und `scripts/bootstrap_spike_opendesk.sh:906` rufen `user:auth-tokens:add` weiter mit festem `--name "$TOKEN_NAME"` auf und würden auf 32 genauso scheitern.
- APP_SECRET wurde nicht erneuert: `app_secret` im Skript übernimmt den vorhandenen Wert aus .env.exapp (anders als der Nachteil in option-a vermutete).
- Auf 32 trägt das neue App-Passwort von alice den Standardnamen "cli".

## Docker-Zustand am Ende

- Kein Container läuft. nc-mcp-exapp gestoppt (stop, nie down), Volumes `nc-mcp-exapp_nextcloud-exapp-data` und `nc-mcp-exapp_registry-exapp-data` vorhanden. nc35 gestoppt. Wegwerf-34 mit `down -v` abgebaut. Lokaler Prozess beendet, Port 23001 frei.
- Der fremde Container gameworld-dev-gameworld-docker-proxy-1 wurde von der Hauptsitzung auf Anweisung des Owners gestoppt, nicht von diesem Plan.

## Next Phase Readiness

- Strecke 32 steht für 32-02 und 32-07 bereit: Start mit `docker compose -f compose.exapp.yml start` (HP_SHARED_KEY aus nc-mcp-exapp-harp), lokaler Prozess mit den fünf Variablen aus .env.exapp.

## Self-Check: PASSED

Alle fünf Dateien vorhanden, alle acht Commits (118de59, b21bf78, 201e1ad, 52cffad, d387bf6, 293b04b, fb205f6, 326240d) im Verlauf.

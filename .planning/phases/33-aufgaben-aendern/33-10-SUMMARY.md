---
phase: 33-aufgaben-aendern
plan: 10
subsystem: tasks-modify-live
tags: [tasks, tasks_complete, tasks_update, tasks_move, live, nc35, nc32, kette, audit, kanarie, beleg]
requires: ["33-09"]
provides:
  - "Live-Fälle der ändernden Werkzeuge in tests/integration/test_tasks_live.py (28 FALL-Zeilen je Lauf, nur Ja/Nein-Merkmale und sha256 der Spalte calendardata)"
  - "tasks_chain_evidence.py: Zeile WERKZEUGE mit aendernd=<liste|keine>"
  - "Rohprotokolle raw/33-10-nc35.txt, raw/33-10-nc32.txt, raw/33-10-push.txt"
  - "docs/tasks-evidence.md: Abschnitt 'Modifying tools on Nextcloud 35 and 32' (79 Zitate, alle wörtlich in den Rohprotokollen), Ergänzung 'Not measured'"
  - "nc35-ExApp auf dem Stand dieses Branches (Image sha256:fc08a65f...), Schalter tasks_update aus"
affects: [34]
key-files:
  created:
    - .planning/phases/33-aufgaben-aendern/raw/33-10-nc35.txt
    - .planning/phases/33-aufgaben-aendern/raw/33-10-nc32.txt
    - .planning/phases/33-aufgaben-aendern/raw/33-10-push.txt
  modified:
    - tests/integration/test_tasks_live.py
    - scripts/tasks_chain_evidence.py
    - docs/tasks-evidence.md
decisions:
  - "FALL-Zeilen tragen nie Objekt-, Listen- oder Kontonamen, damit der Beleg sie wörtlich zitieren kann; die AUFGABE-Zeile mit Konto bleibt im Rohprotokoll"
  - "Unverändert heißt im Live-Test sha256 der Spalte calendardata per PHP im Container, nie Statuscode"
  - "Kette mit Teilfehler über einen httpx-Request-Hook, der den zweiten Nachfahren direkt vor seinem PUT per Harness ändert"
  - "Owner: Push option-a (2026-11-14), gepusht wird durch die Hauptsitzung"
metrics:
  completed: 2026-11-14
  tasks: 6
---

# Phase 33 Plan 10: Live-Beweis der ändernden Aufgabenwerkzeuge Summary

`tasks_complete`, `tasks_update` und `tasks_move` sind live unter AppAPI-Impersonation auf Nextcloud 35 und 32, je ohne und mit Tasks-App 0.18.1, belegt (je 58 passed, 28 FALL-Zeilen ok), auf nc35 zusätzlich über die ganze Kette der installierten ExApp mit eingeschaltetem Schalter und genau einem Audit-Eintrag je Aufruf; BASELINE überall gleich, kein Container läuft.

## Commits

| Task | Commit | Inhalt |
|------|--------|--------|
| 1 | 02bf368 | test(33-10): live cases for the modifying task tools |
| 2 | c44be4a | docs(33-10): owner release for re-registering the ExApp on nc35 |
| 3 | 7e99c18 | docs(33-10): modifying task tools proven live on Nextcloud 35 |
| 4 | 2c63ffa | docs(33-10): modifying task tools proven live on Nextcloud 32 |
| 5 | 17429f6 | docs(33-10): evidence for the modifying task tools |
| 6 | e3458cb | docs(33-10): owner question on push |

Alle als `street1983nk <k.cherif@outlook.de>`, ohne Trailer, ohne closes-Wörter, nur lokal. STATE, ROADMAP und REQUIREMENTS nicht angefasst (Vorgabe der Hauptsitzung).

## Freigaben und Push-Frage (wörtlich)

```
FREIGABE zustand=option-a datum=2026-11-13 umfang=nc35+nc32 quelle=owner-antwort-checkpoint-33-01-task-3
FREIGABE owner=option-a datum=2026-11-14 quelle=owner-antwort-checkpoint-33-10-task-2 (ExApp auf nc35 neu registrieren, Schalter tasks_update vorübergehend an, altes Image vorher als 0.7.2-vor33 sichern, danach Schalter aus und App neu gestartet)
PUSHFRAGE antwort=option-a datum=2026-11-14 quelle=owner-antwort-checkpoint-33-10-task-6 (gepusht wird durch die Hauptsitzung, nicht in diesem Plan)
```

Prüfung vor der Push-Frage (raw/33-10-push.txt): 72 lokale Commits gegen `origin/plan/v1.8-tasks-080`, `PRUEFUNG autor_committer_fremd=0 trailer=0 closes_woerter=0`. Kein Push durch diesen Plan.

## Läufe

```
LIVE nc35 tasksapp=keine passed=58 failed=0
LIVE nc35 tasksapp=0.18.1 passed=58 failed=0
LIVE nc32 tasksapp=keine passed=58 failed=0
LIVE-ROT nc32 tasksapp=0.18.1 passed=57 failed=1 lauf=1
LIVE nc32 tasksapp=0.18.1 passed=58 failed=0 lauf=2
KANARIE nc35 passed=4 schalter=an tasksapp=0.18.1
```

Tasks-App auf beiden Instanzen gemessen 0.18.1 (`TASKSAPP nc35 messung=0.18.1`, `TASKSAPP nc32 messung=0.18.1`), danach wieder entfernt (`RUECKBAU nc35/nc32 tasksapp=wie-vorher vorher=keine nachher=keine`). BASELINE alice und bob vorher gleich nachher auf beiden Instanzen (nc35: calendars=1 objekte=31 / calendars=2 objekte=1; nc32: calendars=1 objekte=3 / calendars=2 objekte=1), dazu je Testlauf die BASELINE des Tests mit `gleich=ja`.

## Je Erfolgskriterium die Rohzeile (nc35 ohne Tasks-App; dieselben Fälle in allen vier Läufen ok)

**1. Abhaken wie die Tasks-App, wieder öffnen, schon erledigt ohne PUT, Unteraufgaben mit (CRLF bleibt):**

```
FALL aendern-abhaken nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204 ergebnis=ok | felder_wie_phase30=ja form_wie_completed_ics=ja eine_sekunde=ja ein_put=ja crlf=ja antwort=ja sha_vorher=31750f1ad5d1 sha_nachher=1aa9c9c29b09
FALL aendern-kinder nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204,PUT:204,PUT:204,PUT:204 ergebnis=ok | puts_nachordnung=ja alle_erledigt=ja changed_nachordnung=ja kinder_crlf=ja eltern_crlf=ja puts=4
```

**2. Genau die genannten Felder plus Pflegefelder, reiches Objekt unverändert bis auf die Felder, kein Unterschied ohne Schreiben:**

```
FALL aendern-felder nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=beschreibung-entfernen felder_wie_app=ja antwort_changed=ja ein_put=ja sha_vorher=75b0caf5ed8b sha_nachher=c66246834b24
FALL aendern-reich nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | vorher_gefaltet=ja felder=ja unberuehrte_zeilen_woertlich=ja valarm_gleich=ja vtimezone_gleich=ja x_zeilen_gleich=ja parameter_summary=ja antwort=ja sha_vorher=8eb376e276bc sha_nachher=2515e6f8c444
FALL aendern-ohne-unterschied nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | kein_put=ja changed_leer=ja sha_gleich=ja sha=550288e93330
```

**3. Veraltete ETag, nur lesende Freigabe (samt Server-Gegenprobe), wiederkehrend, Deck, je Werkzeug (hier tasks_update):**

```
FALL aendern-veraltet nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | harness_aenderung=ja abgelehnt=ja kein_schreiben=ja sha_gleich_nach_harness=ja nicht_im_ziel=ja sha=a41bf2f8e2d2
FALL aendern-nur-lesend nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207 ergebnis=ok | abgelehnt_nur_lesend=ja kein_schreiben=ja sha_beim_eigentuemer_gleich=ja sha=1bd11e32b22c
FALL aendern-nur-lesend-server nc=35.0.0.10 werkzeug=harness status=keine ergebnis=ok | get_lesbar=ja put_abgelehnt=ja move_abgelehnt=ja sha_beim_eigentuemer_gleich=ja nicht_im_ziel=ja put_status=404 move_status=404
FALL aendern-wiederkehrend nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | abgelehnt_wiederkehrend=ja kein_schreiben=ja sha_gleich=ja sha=c473bcb83740
FALL aendern-deck nc=35.0.0.10 werkzeug=tasks_update status=keine ergebnis=ok | wie_unbekannt=ja keine_anfrage=ja keine_deck_marke=ja
```

**4. Verschieben in eine genannte Liste mit gleicher UID, belegtes Ziel unverändert, Unteraufgaben ziehen mit:**

```
FALL verschieben-genannt nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,MOVE:201 ergebnis=ok | ziel=geteilt-schreibbar quelle_leer=ja im_ziel=ja text_gleich=ja gleiche_uid=ja neue_id=ja ein_move=ja sha=324fe49d1252
FALL verschieben-belegt nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207 ergebnis=ok | abgelehnt=ja kein_move=ja quelle_gleich=ja ziel_gleich=ja sha_quelle=e35f1a383cff sha_ziel=db398a1e4de9
```

**5. Audit je Aufruf über die ganze Kette, Kette mit 412 beim zweiten Nachfahren:**

```
AUDIT werkzeug=tasks_update parameter=etag,tags,task_id ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_complete parameter=completed,etag,task_id ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_move parameter=etag,list,task_id ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_update parameter=etag,task_id ergebnis=rejected anzahl=1
FALL kette-teilfehler nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204,PUT:412 ergebnis=ok | harness_aenderte_den_zweiten=ja gestoppt=ja grund_412=ja changed_genau_erster=ja puts=ja eltern_sha_gleich=ja zweiter_sha_wie_harness=ja dritter_sha_gleich=ja erster_erledigt=ja sha_eltern=819d97fe0518
```

## Ganze Kette auf nc35 und Rückweg

```
RUECKWEG image=0.7.2-vor33 image_id=sha256:00a2e4b0bfb7f283a22c944c14141b8de6b27f1faf64902ae2c23f9498782c02
EXAPP nachher image=127.0.0.1:5000/mcp_connector:0.7.2 image_id=sha256:fc08a65ff0d61cf08373dbcd5908805c0dfbde233dfdd5c358378584e9089df4 created=2026-11-14T03:50:53.348399522Z status=running
WERKZEUGE anzahl=30 tasks=ja familien=10 aendernd=tasks_complete,tasks_update,tasks_move
SCHALTER aus app_neu_gestartet=ja wert=off
WERKZEUGE nach_aus anzahl=27 tasks=ja familien=10 aendernd=keine
```

Version in appinfo/info.xml unverändert 0.7.2. `audit_log` nach dem Lauf gelöscht, `tasks_update` steht auf off (ab Werk aus).

**Rückweg zum alten ExApp-Stand (nicht ausgeführt):** nc35 und `nc-mcp-exapp-registry` starten, `docker tag 127.0.0.1:5000/mcp_connector:0.7.2-vor33 127.0.0.1:5000/mcp_connector:0.7.2` und `docker push`, ExApp-Container starten, `occ app_api:app:unregister mcp_connector` ohne `--rm-data`, dann neu registrieren. `bootstrap_exapp.sh --nc35` baut das Image aus dem Checkout neu und überschreibt den Tag; für ein byte-gleiches Zurück braucht es eine Registrierung ohne Neubau (nicht erprobt, wie in 32-07).

## Gates (Endstand, alle Exit 0)

- pytest unit+contract: 8162 passed, 35 skipped
- check_tool_budget: `tools/list with every switch on: 22198 bytes, 31 tools, budget 26000`
- ruff check grün; ruff format --check: 403 Dateien
- pyright (latest): 0 errors, 0 warnings
- vulture: Exit 0 (vulture_whitelist.py brauchte keinen Eintrag)
- TASK-01: Basis-Positivkontrolle grün, Diff über caldav.py, calendar.py und die vier Kalendertests 0 Zeilen; Gegentreffer test_tasks_live.py (982 Einfügungen gegen die Basis)
- Beleg: Abschnitt ohne alice/bob, kein U+2013/U+2014, 79 zitierte Zeilen, 0 fehlen in den Rohprotokollen
- Geheimnisprüfung beider Protokolle und des neuen Belegabschnitts gegen .env.nc35 und .env.exapp (Worktree und Hauptcheckout): nur öffentliche Werte (APP_ID, APP_VERSION, Nutzernamen, URLs)

## Deviations from Plan

1. **[Rule 3] Bootstrap braucht HP_SHARED_KEY.** Der erste Anlauf von `bootstrap_exapp.sh --nc35` scheiterte an der Compose-Interpolation (wartete 60 Zyklen, keine Zustandsänderung). Zweiter Anlauf mit dem Schlüssel aus dem laufenden Container `nc35-harp` (nicht ausgegeben). Der Bootstrap schrieb `.env.nc35` im Worktree neu (neue App-Passwörter für alice und bob, Datei git-ignoriert).
2. **[Rule 1, Bedienung] Schalter aus brauchte `--update-only`.** `occ app_api:app:config:set` ohne `--update-only` ändert einen vorhandenen Schlüssel nicht; der erste Ausschaltversuch blieb wirkungslos (`SCHALTER aus-versuch-1 wirkung=keine`, `WERKZEUGE nach_aus anzahl=30 ...`), der zweite griff.
3. **Eine unveränderte Wiederholung auf Nextcloud 32.** Erster Lauf mit Tasks-App rot im Phase-32-Fall `geteilt-namen` (5 statt 6 REPORT-Antworten, die nur lesbare Liste fehlte in der ersten Suche direkt nach dem Container-Neustart); Rückbau und BASELINE sauber, alle 28 FALL-Zeilen des Laufs ok. Wiederholung ohne Codeänderung grün. Beide Läufe ehrlich im Protokoll.
4. **Harness-Hilfe ohne NC_MCP_E2E-Variablen** übersprang beim ersten Versuch das Anlegen der Kettenlisten; ein erster `tasks_create` lief deshalb gegen eine fehlende Liste und wurde abgelehnt (steht als Audit-Zeile `ergebnis=rejected` im Protokoll).
5. **RAM-Gate auf 32** zunächst rot (2,9 GB bei leerem Docker); Cache in docker-desktop geleert, nach 75 s 4,5 GB, weiter.
6. Abnahmeskript nicht gelaufen (nicht Teil dieses Plans; Kette und Kanarie decken die drei Werkzeuge).

## Offene Punkte und Befunde

- **OFFEN (Hauptsitzung, Owner-Entscheid "Vor 0.8.0 klären"):** die einmalige Wiederholung auf NC 32. Ein kleiner Folgeplan misst die Suche beim Kaltstart (erste Suche direkt nach dem Neustart, Listenbudget `PER_LIST_TIMEOUT=2 s`) und prüft, dass die Antwort eine fehlende Liste ehrlich meldet (`degraded`) statt sie still wegzulassen.
- **Admin-Doku (Phase 34):** `occ app_api:app:config:set` braucht `--update-only`, um einen vorhandenen Schalter (z. B. `tasks_update`) zu ändern; danach App aus- und einschalten.
- **Audit-Grund:** Die Ablehnung einer veralteten ETag steht im Audit als `rejected` mit Grund `unspecified` statt eines eigenen Grundes.
- **Bootstrap:** `bootstrap_exapp.sh --nc35` braucht `HP_SHARED_KEY` in der Umgebung, sonst hängt er an der Compose-Interpolation.

## Docker-Zustand am Ende

Kein Container läuft. nc35 (`nc35-nc`, `nc35-harp`, `nc35-caddy`, `nc35-greenmail`, `nc_app_mcp_connector`) und `nc-mcp-exapp-registry` per `docker stop`, Strecke 32 per `docker compose -f compose.exapp.yml stop`; lokaler Prozess beendet, Port 23001 frei. Keine fremden Container gesehen oder angefasst. Scratchpad p33 gelöscht (Token-Dateien eingeschlossen).

## Known Stubs

Keine.

## Threat Flags

Keine neue Fläche. T-33-10-01 (Freigaben, Rückbau ohne Papierkorb, BASELINE, Schalter wieder aus), -02 (Geheimnisprüfung, keine Kontonamen im Beleg), -03 (alice gegen nur lesbare Freigabe je Werkzeug, Server-Gegenprobe 404), -04 (Container-Prüfung, RAM-Gate, eine Instanz), -05 (kein Push, PUSHFRAGE protokolliert) umgesetzt.

## Self-Check: PASSED

Commits 02bf368, c44be4a, 7e99c18, 2c63ffa, 17429f6, e3458cb im Log; raw/33-10-nc35.txt, raw/33-10-nc32.txt, raw/33-10-push.txt und der Abschnitt in docs/tasks-evidence.md vorhanden; jede zitierte Rohzeile oben steht wörtlich in den Rohprotokollen.

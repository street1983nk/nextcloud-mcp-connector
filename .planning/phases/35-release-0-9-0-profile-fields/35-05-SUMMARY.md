---
phase: 35-release-0-9-0-profile-fields
plan: 05
subsystem: release-test
tags: [volltest, nc35, nc34, profile-fields, rechte, stdio, abnahme]
requires: [35-04, 35-12]
provides:
  - raw/35-05-volltest-nc35.txt (PF-Installierbarkeit, Kette mit Schaltern, PF-FEHLT, stdio an/aus, 403-Versuche, Rückbau, ABGLEICH, Nachmessung NC34-Rechte)
  - Owner-Abnahme des Volltests beider Instanzen (FREIGABE volltest)
affects: [35-06]
tech-stack:
  added: []
  patterns: [Registry des NC34-Stapels als Bildquelle für den nc35-Bootstrap, Nachmessung der Rechte nach Meldungsänderungen auf dem finalen Image]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-05-volltest-nc35.txt
  modified:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-freigaben.txt
decisions:
  - "FREIGABE volltest-nc35 antwort=option-a (Owner: Ja, starten)"
  - "FREIGABE pf-nc35 antwort=luecke (Owner: Messen statt warten); FREIGABE nc35-aufraeumen antwort=entfernen"
  - "Befund PF-FEHLT (unklare 998-Meldung) führte zu 35-12, Owner-Entscheid (a) Klare Meldung"
  - "FREIGABE volltest antwort=abgenommen screenshot=entfaellt nachmessung=nc34-rechte"
metrics:
  duration: ca. 3 h (mit Unterbrechung für 35-12)
  completed: 2026-11-20
---

# Phase 35 Plan 05: Volltest 0.9.0 auf Nextcloud 35 und Owner-Abnahme Summary

0.9.0 lief auf NC 35.0.0 als installierte ExApp mit der Werkzeugfolge 27/28/27/32/27 und über stdio mit 32/27 ohne FAIL. Profile Fields gibt es für 35 nur als Nightly, deshalb ist die Rechte-Strecke dort eine vom Owner entschiedene Lücke. Ohne die App sagt das Werkzeug jetzt klar, was fehlt (Befund aus diesem Plan, umgesetzt in 35-12). Auf NC34 ist die Rechteprüfung mit dem finalen Image nachgemessen und grün. Der Owner hat den Volltest abgenommen.

## Tasks

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 | FREIGABE volltest-nc35 antwort=option-a | edf795e5 docs(35-05): owner approval of the full test on Nextcloud 35 |
| 2 | PF auf nc35 nicht stabil installierbar, Owner-Entscheid luecke, Lauf bis zum Befund PF-FEHLT | aa995882 docs(35-05): Nextcloud 35 run up to the Profile Fields missing-app finding |
| (35-12) | klare Meldung bei fehlender App und Gruppen-Fall, eigener Plan | 79cefab1 bis e9a68cba |
| 3 | Kette, stdio, 403, Rückbau, ABGLEICH auf dem finalen Image | 3cec88d5 docs(35-05): full live test of 0.9.0 on Nextcloud 35 |
| 4 | Owner-Abnahme und Nachmessung NC34-Rechte | 1c93cec2 docs(35-05): owner acceptance of the full test |

## Messzeilen NC35 (geprüft, Image f5264023 aus e9a68cba)

- `PF nc35 installierbar=nein` mit occ-Meldung `Error: App "Profile fields" cannot be installed because it is not compatible with this version of the server.`
- `PF store nc35 stabil=nein nightly=ja` (Store für 35.0.0: nur 5.0.0 Nightly; für 34.0.3: 4.0.0 stabil `>=34 <=34`)
- Aufräumen: `occ app:remove profile_fields` entfernte das vom Installer geladene Archiv 4.0.0; `app_list_profile_fields=0`
- WERKZEUGE Kette: s1 alles aus 27, s2 pf an (ohne App) 28, s3 pf=vielleicht 27 mit Warnung im Log, s4 alles an 32, s5 aus 27
- PF-FEHLT (Kette und stdio, alle vier Ebenen): `Profile Fields is not installed or not enabled on this Nextcloud. Hint: Ask an administrator to install the app Profile Fields or to switch off profile_fields_read.`; kein 500, kein Traceback, kein Hängen; files_list, unified_search, search, prepare_context fehlerfrei
- STDIO: an tools_list=32 exit=3 (nur `profile_fields_browse urteil=PREREQ`, laut Plan erwartet), aus tools_list=27 exit=0; 59 VOLLTEST-Zeilen, kein FAIL
- `ZAEHLUNG an=32 erwartet_an=32 aus=27 erwartet_aus=27 gleich=ja`
- BASELINE alice (1/31/0/0/0) und bob (2/1/0/0/0) vorher gleich nachher; vier Laufobjekte gelöscht und Papierkorb geleert
- `ABGLEICH nc35-aussage changelog=stimmt notiz=stimmt`

## Nachmessung NC34-Rechte (geprüft, Image 5f486c5f aus 3cec88d5)

- PF nc34 4.0.0 aktiv; Rechte-Livetest 10 passed, 0 failed, 0 skipped, 0 deselected
- `PROFILE-FIELDS tools without switch=27 with switch=28`, `search without switch: private value admin=1 bob=0, shared value bob=1`
- Kette: alice `level=me` OK (count=2), `level=definitions` ABGELEHNT mit `No permission for the Profile Fields admin catalog. Nextcloud says: "Logged in account must be an admin". Hint: Ask the owner of the item or an administrator in Nextcloud for the missing permission.`
- Schalter off, 27; BASELINE und PROFILFELDER (2/2/3) gleich

## Lücken auf NC35 (benannt, Owner-Entscheid)

1. `LUECKE nc35 profile_fields_rechte=ungemessen`: Profile Fields für 35 nur als Nightly (FREIGABE pf-nc35 antwort=luecke). Belegt auf NC34 (35-04, Nachmessung oben) und in CI.
2. `LUECKE nc35 meldung_403=ungemessen`: ohne Profile Fields keine Admin-Route; Tables antwortet für fremde Tabellen 404 (verrät nichts), Talk prüft den Nur-lesen-Raum vorher. Der 403-Wortlaut ist auf NC34 live belegt (35-12 und Nachmessung).

## Nachprüfung, sobald Profile Fields für NC35 stabil im Store ist

Offener Punkt für die Hauptsitzung:

1. Katalog lesen: `curl -s https://apps.nextcloud.com/api/v1/platform/35.0.0/apps.json`, nur `id=profile_fields`; weiter erst bei einem Release mit `isNightly=false` und einer Plattform, die 35 einschließt.
2. Docker- und RAM-Gate, nc35 und Registry starten, `occ app:install profile_fields` ohne `--allow-unstable`, `occ app:list`; Zeile `PF nc35 version=<v> aktiv=ja quelle=store-stabil`.
3. Bootstrap `--nc35` (der Container gehört derzeit NC34), Kette: Schalter an 28; alice `level=me` OK, `level=definitions` ABGELEHNT mit dem 403-Wortlaut.
4. Rechte-Livetest: `NC_MCP_E2E_NEXTCLOUD=nc35-nc NC_MCP_EXPECT_PROFILE_FIELDS=1 NC_MCP_PROFILE_FIELDS_READ=on uv run --no-sync pytest tests/integration/test_profile_fields_live.py -m integration -s -p no:xdist` mit APP_ID und APP_SECRET aus der Shell entfernt; erwartet `privat_admin=1 privat_bob=0 geteilt_bob=1`, failed, skipped und deselected 0; ein Leck ist ein Sicherheitsstopp.
5. stdio Lauf A mit `profile_fields_browse urteil=OK` statt PREREQ, ZAEHLUNG 32/27.
6. Rückbau: Testfelder und Wegwerf-Admin weg (macht der Test), Schalter off, Container stoppen.
7. CHANGELOG-Satz zu NC35 in DE/EN/FR in einem Patch-Release oder unter [Unreleased] durch "Measured on Nextcloud 35 with Profile Fields <v>" ersetzen, mit Sprachprüfung und Gates.

## Gates (Stand e9a68cba, in 35-05 kein Code und kein CHANGELOG geändert)

unit+contract 8374 passed, 35 skipped; check_tool_budget exit 0; ruff check ok; ruff format 418 Dateien; pyright 0 errors; vulture exit 0.

## Deviations from Plan

1. [Rule 3] Die Registry `nc-mcp-exapp-registry` lief für den nc35-Bootstrap mit (compose.nc35.yml hat keine eigene Registry; wie 34-07, vom Orchestrator akzeptiert).
2. Der fehlgeschlagene `occ app:install profile_fields` hat ein Archiv 4.0.0 auf nc35 hinterlassen; auf Owner-Antwort `entfernen` per `occ app:remove` beseitigt.
3. Befund PF-FEHLT: die erste NC35-Meldung bei fehlender App war unklar (Kerntext 998 mit URL und "\n", irreführender Hinweis). Ich habe angehalten; der Owner hat (a) gewählt, umgesetzt in 35-12 (eigener Plan, eigene Commits). Task 3 lief danach auf dem finalen Image erneut.
4. Die vom Orchestrator genannte Stichprobe "files_browse" gibt es nicht; ich habe files_list genommen.
5. Die 403-Meldung ließ sich auf NC35 nicht sinnvoll erzeugen und steht als Lücke (siehe oben).
6. Zwei RAM-Gates waren knapp: einmal rot (4113308 KiB), nach drop_caches 5355564 KiB.
7. Der ExApp-Container wechselte mehrmals zwischen den Stapeln (Unregister ohne `--rm-data`, akzeptiert). Rückweg-Tags: `03c3fe04-vor35`, `7e7efda4-vor35`, `f5264023-vor-nachmessung`.
8. Nachmessung NC34-Rechte auf Wunsch des Owners zusätzlich zum Plan.

## Geprüft und angenommen

Geprüft: alle Messzeilen oben, die Texte im jeweils laufenden Image (grep im Container), Store-Katalog für 35 und 34, Schalterwerte per config:get am Ende.

Angenommen, nicht gemessen:
- Dass die Rückweg-Tags funktionieren; getaggt, nicht eingespielt.
- Dass sich Profile Fields 5.x auf NC35 wie 4.0.0 auf NC34 verhält; das prüft die Nachprüfung oben.

## Endzustand

- Docker: kein Container läuft (`DOCKER ende eigene=0`); kein down, keine Volumes gelöscht; fremde Container nicht angefasst.
- Registrierung: NC34 trägt die ExApp 0.9.0 (Image 5f486c5f) mit dem Container nc_app_mcp_connector, Schalter off. nc35 führt die ExApp 0.9.0 in der Liste, ihr Container ist abgelöst; vor dem nächsten nc35-Einsatz `bootstrap_exapp.sh --nc35`. Profile Fields ist auf nc35 nicht installiert.
- `.env.nc35` und `.env.exapp` hat der Bootstrap in den Worktree geschrieben (git-ignoriert, nicht committet).
- Testkonto alice auf nc35 enthält Dateien, Notizen, Karten, Tabellenzeilen und Talk-Nachrichten der stdio-Läufe (nicht in der BASELINE).
- Scratchpad p35 gelöscht, Tokendateien gelöscht.

## Known Stubs

Keine.

## Threat Flags

Keine neuen; T-35-05-01 bis 05 umgesetzt (SCAN gesamt treffer=0, Lücke nur mit Owner-Entscheid, kein Nightly installiert, Gates vor jedem Start, ABGLEICH-Zeile).

## Self-Check: PASSED

- raw/35-05-volltest-nc35.txt und diese SUMMARY vorhanden; Commits edf795e5, aa995882, 3cec88d5, 1c93cec2 vorhanden; Verify von Task 1 bis 4 grün; kein Container läuft.

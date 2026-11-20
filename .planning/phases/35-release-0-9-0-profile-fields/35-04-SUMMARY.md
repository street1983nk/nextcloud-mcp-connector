---
phase: 35-release-0-9-0-profile-fields
plan: 04
subsystem: release-test
tags: [volltest, nc34, profile-fields, rechte, stdio, sprache]
requires: [35-03]
provides:
  - raw/35-04-volltest-nc34.txt (Kette mit Schaltern, stdio an/aus, Rechte live, Rückbau, Sprachdurchsicht)
  - Sprachkorrekturen in CHANGELOG.md, CHANGELOG.fr.md, README.fr.md, docs/hardening.md, docs/hardening.fr.md, docs/privacy.md, docs/threat-model.md
affects: [35-05, 35-06]
tech-stack:
  added: []
  patterns: [Geheimnisprüfung mit Positivkontrolle vor jeder Übernahme ins Protokoll, Trashbin-Liste per REPORT statt PROPFIND]
key-files:
  created:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-04-volltest-nc34.txt
  modified:
    - .planning/phases/35-release-0-9-0-profile-fields/raw/35-freigaben.txt
    - CHANGELOG.md
    - CHANGELOG.fr.md
    - README.fr.md
    - docs/hardening.md
    - docs/hardening.fr.md
    - docs/privacy.md
    - docs/threat-model.md
decisions:
  - "Owner-Antwort 'Ok' (2026-11-20) als FREIGABE volltest-nc34 antwort=option-a eingetragen"
  - "Zwei Texte unter src/ und eine Store-Summary-Eigenheit nur als HINWEIS, nicht als Fehler gewertet; Owner-Entscheid in 35-05"
metrics:
  duration: ca. 45 min
  completed: 2026-11-20
---

# Phase 35 Plan 04: Volltest 0.9.0 auf Nextcloud 34 Summary

0.9.0 lief als installierte ExApp auf NC 34.0.3 mit Profile Fields 4.0.0: Werkzeugzahlen über die ganze Kette 27/28/27/32/27, alice wird der Admin-Katalog verweigert, der Rechte-Livetest ist grün (10 passed), stdio mit allen Schaltern an (32) und aus (27) ohne FAIL. Bei der Sprachdurchsicht kamen 10 Fehler in CHANGELOG, README.fr und docs heraus, alle behoben. Am Ende läuft kein Container mehr.

## Tasks

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 | FREIGABE volltest-nc34 antwort=option-a (Owner "Ok") | 86b39f6f docs(35-04): owner approval of the full test on Nextcloud 34 |
| 2 bis 4 | Kette mit Schaltern, stdio, Rechte live, Rückbau, Scan | ac2900d0 docs(35-04): full live test of 0.9.0 on Nextcloud 34 |
| 5a | Sprachkorrekturen (7 Dateien, 14 Zeilen) | f3697f9e docs(35-04): language fixes from the full test |
| 5b | Sprachprotokoll | 7ecbaf1b docs(35-04): language review of every user-visible text |

## Messzeilen (geprüft)

- `PF nc34 version=4.0.0 aktiv=ja`, `EXAPP vorher version=0.8.0` (Build 4e68000a, Rückweg-Tag `127.0.0.1:5000/mcp_connector:4e68000a-vor35`), `EXAPP nachher version=0.9.0 image_id=sha256:03c3fe04... status=running`
- WERKZEUGE: s1 alle aus 27, s2 pf=an 28 (genau profile_fields_browse dazu), s3 pf=vielleicht 27 mit Warnung im Containerlog, s4 alle an 32, s5 nach_aus 27
- RECHTE Kette: alice `level=me` OK (count=2), alice `level=definitions` ABGELEHNT ("No permission for Profile Fields admin catalog ... must be an admin")
- RECHTE live: `tools without switch=27 with switch=28`, `search without switch: private value admin=1 bob=0, shared value bob=1`, 10 passed, 0 failed, 0 skipped, 0 deselected
- STDIO: an tools_list=32 exit=0, aus tools_list=27 exit=0; 59 VOLLTEST-Zeilen, kein FAIL, kein PREREQ; `ZAEHLUNG an=32 erwartet_an=32 aus=27 erwartet_aus=27 gleich=ja`
- BASELINE alice (1/0/0/0/0) und bob (2/1/0/0/0) vorher gleich nachher; PROFILFELDER definitionen=2 werte=2 konten=3 vorher gleich nachher
- Ende: Schalter alle off (per config:get geprüft), ADMIN-SPRACHE en, firstrunwizard aus, `DOCKER ende eigene=0`, `TOKENDATEIEN geloescht=ja`, `SCAN gesamt treffer=0`

## Gates (35-RULES Abschnitt 3, vor f3697f9e)

unit+contract 8338 passed, 35 skipped; check_tool_budget exit 0 (Standard 18606 Bytes, 27 Werkzeuge); ruff check ok; ruff format 417 Dateien; pyright 0 errors; vulture exit 0; Runbook-Lauf `pytest -q -p no:xdist` exit 0 (die Zusammenfassungszeile fehlt durch das doppelte -q, in der Fortschrittsanzeige 0 F und 0 E). Dash-Prüfung mit Positivkontrolle: 0 Treffer. src/ in 35-04 unverändert.

## Sprache

Behoben (geprüft gegen den Text, jeweils nur die Zeile):
- EN: "the own ..." (Germanismus) in CHANGELOG.md, docs/hardening.md, docs/privacy.md, docs/threat-model.md; "on two ways" -> "in two ways" (privacy.md)
- FR: "Un changement prend effet après avoir désactivé puis réactivé l'application" (Infinitivsatz mit anderem Subjekt) -> "une fois l'application désactivée puis réactivée" in README.fr, CHANGELOG.fr, hardening.fr; "ses propres valeurs/champs" ohne Bezugswort (README.fr-Tabelle, CHANGELOG.fr); "les propres valeurs du compte" -> "les valeurs propres au compte" (hardening.fr)
- Store-Texte unverändert (`STORETEXT unveraendert`), Pin unberührt.
- tools/list (32 Werkzeuge, 152 Texte): `zusicherungen=0`, Schreibcharakter 12 von 12.

Offen beim Owner (HINWEIS, nicht als Fehler gewertet, nichts geändert):
1. `files_download`: "Download any-size file in chunks" (Telegrammstil ohne Artikel). Text unter src/.
2. 403-Meldung von profile_fields_browse: "... Nextcloud says: Logged in account must be an admin Hint: Ask the owner ...". Der Nextcloud-Text hat keinen Schlusspunkt, und "the owner" passt hier nicht, gemeint ist ein Administrator. Allgemeine Formulierung in `nextcloud/clients/ocs.py`, gab es schon vor Phase 35.
3. Store-Summary: in DE "MCP Server" ohne Bindestrich steht so mit Absicht (Suchwort), in FR fehlt "connecté" in "comme l'utilisateur". Beides ist freigegebener Text.

## Deviations from Plan

1. [Rule 3] Der erste Lauf von `bootstrap_exapp.sh` hing in "waiting for the Nextcloud installation", weil compose.exapp.yml ohne `HP_SHARED_KEY` in der Umgebung nicht interpoliert. Ich habe ihn abgebrochen und ein zweites Mal gestartet, mit `HP_SHARED_KEY` aus dem laufenden HaRP (nicht ausgegeben) und `NC_EXAPP_NEXTCLOUD_IMAGE=nextcloud:34.0.3-apache`.
2. [Rule 3] Der erste Lauf des Rechte-Livetests endete mit 2 passed und 8 errors. Grund war die Umgebung: `.env.exapp` setzt APP_ID und APP_SECRET, und damit verweigert der Standalone-HTTP-Server den Start. Im zweiten Lauf waren die beiden Variablen aus der Shell entfernt, Ergebnis 10 passed. Seine Welt hat der Test auch im ersten Lauf wieder abgebaut, die PROFILFELDER-Zählung war danach unverändert.
3. Die Warnung zum ungültigen Wert kommt im ExApp-Weg aus `exapp/config_values.py` ("the admin value for profile_fields_read is neither on nor off ..."). Die im Plan genannte Meldung aus `config.py` gehört zum Umgebungsweg.
4. Zu `DOCKER fremd=0 laufend=6`: Der NC34-Stapel lief schon, deshalb war kein `compose up` nötig.
5. Ich habe docs/threat-model.md mit korrigiert, obwohl die Datei in Phase 35 nicht geändert wurde. Dort stand derselbe Germanismus im Profile-Fields-Absatz.
6. Der Papierkorb von alice ließ sich nicht per PROPFIND lesen (501), deshalb habe ich ihn per REPORT gelistet. Gelöscht wurden genau die vier Objekte der Läufe: vorher war geloescht=0, danach waren es 4.
7. Den Text der SCAN-Zeile habe ich umformuliert, weil der Headername darin einen Selbsttreffer im Scan auslöste. Dafür wurde der letzte Commit per amend geändert, lokal und ohne Push.
8. Task 2 bis 4 liegen wie geplant in einem Protokoll-Commit. Die Freigabezeile aus Task 1 hat zusätzlich einen eigenen Commit bekommen (86b39f6f).

## Geprüft und angenommen

Geprüft: alle Messzeilen oben, die Rechte live auf NC34, der Schlüsselname der Schalter (`app_api:app:config:list`). Die Log-Warnung "a decision arrived from a browser that is not the account that signed in" ist die eingebaute CR-01-Gegenprobe von `oauth_flow_check.py` (im Code nachgelesen).

Angenommen, nicht gemessen:
- Dass der Wiederherstellungsweg über das getaggte Image 4e68000a-vor35 funktioniert. Das Image ist getaggt, eingespielt habe ich es nicht.
- Die Admin-Formulartexte habe ich nur im Code gelesen (strings.py), die Oberfläche selbst habe ich mir nicht angesehen.

## Endzustand

- Docker: es läuft kein Container. Gestoppt sind nc_app_mcp_connector und der Stapel nc-mcp-exapp. Ein `down` gab es nicht, die Volumes bleiben.
- ExApp 0.9.0 ist auf NC34 registriert und aktiviert, alle drei Schalter stehen auf off. Profile Fields steht damit anders als vor dem Lauf, da war profile_fields_read=on aus dem PR-49-Lauf.
- `.env.exapp` hat der Bootstrap in den Worktree geschrieben. Sie ist git-ignoriert und wurde nicht committet.
- Testkonto alice enthält zusätzlich Dateien, Ordner, Notizen, Deck-Karten, Tabellenzeilen und Talk-Nachrichten der stdio-Läufe sowie einen neuen Freigabeordner des Bootstraps. Nichts davon zählt zur BASELINE.

## Known Stubs

Keine.

## Self-Check: PASSED

- raw/35-04-volltest-nc34.txt vorhanden und sauber committet; Commits 86b39f6f, ac2900d0, f3697f9e, 7ecbaf1b vorhanden; Verify-Prüfungen von Task 2 bis 5 grün.

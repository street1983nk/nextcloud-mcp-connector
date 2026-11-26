---
quick_id: 261126-i60
type: live-proof
date: 2026-11-26
---

# Live-Nachweis Issue 60: Konto-ID in DAV-Pfaden

Alle Werte gemessen am 26.11.2026 auf dem lokalen ExApp-Stapel `compose.exapp.yml` (Nextcloud 34.0.3, HaRP, Caddy, lokale Registry `127.0.0.1:5000`). Passwörter, App-Passwörter, Tokens, Client-Secrets und der HaRP-Schlüssel sind nicht abgebildet.

## Wichtiger Befund vorab: Basis des Fixes

Lokales `main` (HEAD 6d94c913) steht 65 Commits hinter `origin/main` und enthält v0.9.0 nicht (`git merge-base --is-ancestor v0.9.0 HEAD` ist falsch, `HEAD..v0.9.0` sind 48 Commits). Die Fix-Commits sitzen auf 9ac9f50f (vor 0.9.0, `appinfo/info.xml` 0.8.0).

Deshalb ist der Kandidat nicht das Image aus HEAD, sondern **origin/main (db4cbf63, enthält v0.9.0) plus die drei Code-Commits per cherry-pick**, in einem Wegwerf-Worktree:

```
git worktree add --detach <scratch>/wt091 origin/main
git cherry-pick fbbab53a 6ee89ea5 7bfb19e7     # konfliktfrei
# -> a6725ef0, 4f8a46ed, 9d0c32ac
docker buildx build --platform linux/amd64 --load -t 127.0.0.1:5000/mcp_connector:i60-cand .
# digest sha256:1e0b95d9ca32222fbc12cdb4e700fce1e520cd3284f23fa07247b01ceca84710
```

Begründung: Ein HEAD-Image wäre gegenüber dem vorhandenen 0.9.0-Datenvolume ein Downgrade (älteres Store-Schema, Version 0.8.0) und hätte 48 fremde Änderungen in den Vergleich gemischt. Der Patch ist derselbe. Unit und Contract im Worktree: rc 0, rund 8410 passed, 35 skipped, 0 failed.

Für 0.9.1 muss `main` vor dem Release auf `origin/main` gebracht werden (Rebase der fünf lokalen Commits). Das ist nicht passiert, weil es nicht beauftragt war.

## Images

| Rolle | Tag in der lokalen Registry | Quelle |
|---|---|---|
| Gegenprobe | `i60-v090` | `ghcr.io/street1983nk/mcp_connector:0.9.0` (Store-Release), umgetaggt |
| Kandidat | `i60-cand` | origin/main + Fix (siehe oben) |

Tausch: `occ app_api:app:unregister mcp_connector --silent --force` (Daten bleiben), dann `occ app_api:app:register mcp_connector harp_proxy_docker --json-info ... --force-scopes --wait-finish` mit derselben JSON wie `scripts/bootstrap_exapp.sh` (`json_info`), nur `image-tag` variabel. Admin-Wert `files_update=on` gesetzt (`occ app_api:app:config:set mcp_connector files_update --value=on --update-only`), damit Update und Versionen messbar sind.

## Weg zum abweichenden Login-Namen

### 1. Login per E-Mail (Nutzer `ivan`, E-Mail `ivan@example.test`)

```
occ user:add --password-from-env --email ivan@example.test --display-name "Ivan Test" ivan
```

Login Flow v2 direkt gemessen (Anmeldung mit der E-Mail, dann Poll):

```
POST /index.php/login/v2                              -> 200
POST <poll>                                           -> 200 loginName='ivan@example.test'
GET  /ocs/v2.php/cloud/user                           -> 200 id='ivan'
PROPFIND /remote.php/dav/files/ivan@example.test/     -> 207 (10 Einträge, hrefs unter /files/ivan@example.test/)
PROPFIND /remote.php/dav/files/ivan/                  -> 207 (10 Einträge)
PROPFIND /remote.php/dav/calendars/ivan@example.test/ -> 207
PROPFIND /remote.php/dav/addressbooks/users/ivan@example.test/ -> 207
```

Ergebnis: Login Flow v2 liefert die E-Mail als `loginName`. Nextcloud 34 löst die E-Mail im DAV-Pfad aber selbst auf, es gibt also **kein 404**. Gegenkontrolle Groß-/Kleinschreibung (`IVAN`): `loginName='IVAN'`, ebenfalls überall 207.

### 2. LDAP mit UUID als Nutzer-ID (Nutzer `lena`, wie objectGUID gegen sAMAccountName)

Wegwerf-Container `i60-openldap` (osixia/openldap:1.5.0) im Netz `nc-mcp-exapp-net`, Eintrag `uid=lena,ou=people,dc=example,dc=test`. user_ldap-Konfiguration `s01`: Login-Filter `(&(objectClass=inetOrgPerson)(uid=%uid))`, `ldapExpertUUIDUserAttr=entryUUID`, kein Expert-Username-Attribut. Damit ist die Nextcloud-ID die entryUUID:

```
occ ldap:test-config s01   -> The configuration is valid and the connection could be established!
occ ldap:search lena       -> Lena Ldap (5cc85fa0-7e2f-1041-992d-67739c5eca49)
```

Login Flow v2:

```
POST <poll>                                                    -> 200 loginName='lena'
GET  /ocs/v2.php/cloud/user                                    -> 200 id='5cc85fa0-7e2f-1041-992d-67739c5eca49'
PROPFIND /remote.php/dav/files/lena/                           -> 404
PROPFIND /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/ -> 207 (10 Einträge)
PROPFIND /remote.php/dav/calendars/lena/                       -> 404
PROPFIND /remote.php/dav/addressbooks/users/lena/              -> 404
```

Das ist genau der Fehler aus Issue 60.

## Testdaten je Konto

Per DAV mit Basic-Login angelegt (`seed_ivan.py`, `mk_tasks.py` im Scratchpad): `/i60/notiz-i60.md` (zweimal geschrieben, also mit Version), `/i60/geheim-i60.md` mit Systemtag `kein-ki` (`occ tag:add kein-ki public`, Tag-ID 1, Zuordnung `PUT /remote.php/dav/systemtags-relations/files/<id>/1 -> 201`), ein Termin in `personal`, eine Aufgabe in einem VTODO-Kalender `aufgaben` (`MKCALENDAR -> 201`), ein Kontakt "Kontakt Ivanov i60".

## Messweg

`live_i60.py` (Scratchpad) nutzt `scripts/oauth_flow_check.connect()`: DCR, `/authorize` mit PKCE, Nextcloud-Anmeldung im Login Flow v2 mit dem angegebenen Login-Namen, Zustimmung aus der Browser-Session, Code-Tausch. Dann ruft es die Werkzeuge über die volle Kette (Caddy, HaRP, ExApp, Nextcloud) und liest die Zeilen des Nextcloud-Access-Logs (`docker logs nc-mcp-exapp-nc`), die die Aufrufe verursacht haben. Am Ende `/revoke -> 200`.

```
LIVE_PW=<redacted> uv run python live_i60.py <label> <login>
```

## Gegenprobe v0.9.0 (`i60-v090`)

### LDAP, Login `lena`

| Werkzeug | Ergebnis |
|---|---|
| files_list `/` und `/i60` | count 0, degraded: "The exclusion check (tag kein-ki) could not be answered" |
| files_search `i60` | count 0, gleicher degraded-Hinweis |
| unified_search `i60` | count 0, Dateitreffer zurückgehalten (exclusion) |
| files_read | Fehler: kein-ki-Prüfung nicht beantwortbar |
| files_upload, files_create_folder | Fehler: kein-ki-Prüfung nicht beantwortbar |
| calendar_list_events, calendar_create_event | Fehler: "Nextcloud does not know the calendar list" |
| tasks_search | leer, "This account has no task list yet" (falsch, sie existiert) |
| tasks_create | Fehler: "This account has no task list" |
| contacts_search | Fehler: "Nextcloud does not know the address book list" |

Access-Log (Auszug, Nutzerfeld = Login-Name):

```
404 PROPFIND /remote.php/dav/files/lena/ user=lena
404 REPORT /remote.php/dav/files/lena/ user=lena
404 PROPFIND /remote.php/dav/files/lena/i60 user=lena
404 SEARCH /remote.php/dav/ user=lena
404 PROPFIND /remote.php/dav/files/lena/i60/notiz-i60.md user=lena
404 PROPFIND /remote.php/dav/files/lena/i60/geheim-i60.md user=lena
404 PROPFIND /remote.php/dav/calendars/lena/ user=lena
404 PROPFIND /remote.php/dav/addressbooks/users/lena/ user=lena
```

Der Fehler ist mit dem Store-Image reproduziert.

### E-Mail, Login `ivan@example.test`

Alle DAV-Pfade tragen die E-Mail (`/remote.php/dav/files/ivan%40example.test/...`, `/calendars/ivan%40example.test/...`, `/versions/ivan%40example.test/versions/575`) und antworten 207/201/204, weil Nextcloud 34 die E-Mail auflöst. Ein Werkzeug ist trotzdem kaputt:

```
TOOL files_search {"query": "i60"} -> OK {"count": 0, ...}     (zwei Läufe, beide 0)
207 SEARCH /remote.php/dav/ user=ivan@example.test
```

Dieselbe Suche liefert beim Kandidaten 2 Treffer (siehe unten). Alle übrigen Werkzeuge liefen mit E-Mail-Login auch unter v0.9.0.

## Kandidat (`i60-cand`)

### LDAP, Login `lena` (Nutzer-ID `5cc85fa0-7e2f-1041-992d-67739c5eca49`)

| Werkzeug | Ergebnis |
|---|---|
| files_list `/` | ok, 10 Einträge |
| files_list `/i60` | ok, nur `notiz-i60.md`; `geheim-i60.md` (kein-ki) fehlt |
| files_search `i60` | ok, 2 Treffer (`notiz-i60.md`, Ordner `i60`), kein `geheim` |
| unified_search `i60` | ok, 2 Treffer, kein `geheim` |
| files_read `notiz-i60.md` | ok, Inhalt "Version zwei" |
| files_read `geheim-i60.md` | verweigert ("File not found"), obwohl Nextcloud `PROPFIND .../geheim-i60.md -> 207` antwortet: kein-ki-Ausschluss greift |
| files_upload | ok, `created: true` |
| files_create_folder | ok, `created: true` |
| files_update (Versionen) | ok, `versioned: true`, `PROPFIND /versions/<id>/versions/657 -> 207` |
| calendar_list_events | ok, 2 Termine inkl. "Termin i60" |
| calendar_create_event | ok, `created: true` |
| tasks_search | ok, "Aufgabe i60" |
| tasks_read | ok |
| tasks_create | ok, `created: true` |
| contacts_search `ivanov` | ok, 1 Kontakt |

Access-Log (alle DAV-Zeilen der Werkzeuge, Pfade tragen die Nutzer-ID, Basic-Login weiter der Login-Name):

```
207 PROPFIND /remote.php/dav/systemtags/ user=lena
207 PROPFIND /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/ user=lena
207 REPORT /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/ user=lena
207 PROPFIND /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/i60 user=lena
207 SEARCH /remote.php/dav/ user=lena
207 PROPFIND /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/i60/notiz-i60.md user=lena
206 GET /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/i60/notiz-i60.md user=lena
207 PROPFIND /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/i60/geheim-i60.md user=lena
201 PUT /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/i60/upload-cand-225402.md user=lena
201 MKCOL /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/i60/ordner-cand-225402 user=lena
207 PROPFIND /remote.php/dav/versions/5cc85fa0-7e2f-1041-992d-67739c5eca49/versions/657 user=lena
204 PUT /remote.php/dav/files/5cc85fa0-7e2f-1041-992d-67739c5eca49/i60/notiz-i60.md user=lena
207 PROPFIND /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/ user=lena
207 REPORT /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/contact_birthdays/ user=lena
207 REPORT /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/personal/ user=lena
201 PUT /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/personal/<uid>.ics user=lena
200 GET /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/personal/<uid>.ics user=lena
207 REPORT /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/aufgaben/ user=lena
200 GET /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/aufgaben/i60-task.ics user=lena
201 PUT /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/aufgaben/<uid>.ics user=lena
200 GET /remote.php/dav/calendars/5cc85fa0-7e2f-1041-992d-67739c5eca49/aufgaben/<uid>.ics user=lena
207 PROPFIND /remote.php/dav/addressbooks/users/5cc85fa0-7e2f-1041-992d-67739c5eca49/ user=lena
207 REPORT /remote.php/dav/addressbooks/users/5cc85fa0-7e2f-1041-992d-67739c5eca49/contacts/ user=lena
```

Kein einziger 404.

### E-Mail, Login `ivan@example.test` (Nutzer-ID `ivan`)

Alle 15 Aufrufe wie bei `lena` ok, `files_search i60` jetzt 2 Treffer (v0.9.0: 0), `geheim-i60.md` ausgeblendet und verweigert. Access-Log: alle Pfade unter `/files/ivan/`, `/versions/ivan/versions/575`, `/calendars/ivan/`, `/addressbooks/users/ivan/`, Nutzerfeld `ivan@example.test`, Statuscodes 207/206/201/204/200, kein 404.

## Regression: Login gleich ID (`alice`)

Gleiche Testdaten, gleiche 15 Aufrufe mit dem Kandidaten: alle ok (files_list `/` 22 Einträge, files_search 2, unified_search 2, geheim verweigert, Upload, Ordner, Update `versioned: true`, Kalender, Aufgaben, Kontakte). Access-Log: alle Pfade unter `/files/alice/`, `/versions/alice/versions/671`, `/calendars/alice/`, `/addressbooks/users/alice/`, kein 404.

## Integrationstests

### Job `integration` der CI (compose.test.yml, Nextcloud 34.0.2, lokales `main` HEAD 6d94c913)

Wegwerf-Kopie der Compose-Datei mit eigenem Projekt (`nc-mcp-i60`) und Containernamen (`nc-mcp-i60-test`), damit der alte Stapel `nc-mcp-test` unberührt bleibt; danach `down -v`.

```
docker compose -f compose.i60test.yml up -d --wait          -> healthy
bash scripts/bootstrap_test_nc.sh                           -> Ready
uv run pytest -m integration                                -> 67 passed, 222 skipped, 0 failed
modern_client_check.py http://127.0.0.1:8765/mcp            -> 27 tools, rc 0
legacy_client_check.py (mcp>=1.29,<2)                       -> 27 tools, rc 0
occ app:install profile_fields                              -> 4.0.0 installed
pytest tests/integration/test_profile_fields_live.py        -> 10 passed
  PROFILE-FIELDS tools without switch=27 with switch=28
  PROFILE-FIELDS search without switch: private value admin=1 bob=0, shared value bob=1
uv run pytest -m matrix                                     -> 8 passed
```

Die 222 Skips sind die Dateien, die eine ExApp-Topologie oder Findling brauchen (wie in der CI).

### Job `exapp` der CI (gegen den Kandidaten `i60-cand`, Tests aus dem Worktree)

```
test_exapp_dav_matrix.py             -> 13 passed
test_permission_fidelity_exapp.py    -> 15 passed
test_oauth_flow_exapp.py             ->  6 passed
test_appapi_users_list.py            ->  4 passed
test_tasks_live.py (NC_MCP_REQUIRE_LIVE=1, NC_MCP_EXPECT_TASKS_APP=0) -> 58 passed
```

Nicht gelaufen: die Findling-Schritte (`install_findling.sh`, `test_content_hit_fidelity`, `test_findling_sandbox`), weil der Findling-Stapel gestoppt bleiben sollte, und der Job `canary` (eigenes Nextcloud-Image).

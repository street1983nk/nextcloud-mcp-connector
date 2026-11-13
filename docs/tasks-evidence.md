# Evidence for the tasks bundle against real Nextcloud

**Date:** 2026-11-13
**Subject:** what the tasks bundle (`tasks_search`, `tasks_read`, `tasks_create`) rests on,
measured before any product code existed, and how the built bundle answered live
**Status:** measured on two throwaway instances (Nextcloud 35.0.2 with SQLite and with
PostgreSQL) and under AppAPI impersonation on Nextcloud 35.0.0 and Nextcloud 32.0.15; every
value below is derived from these runs. Plan 32-07 then ran the built bundle live on both
standing instances, each without and with the Tasks app 0.18.1, and on Nextcloud 35 over the
whole chain through the installed app. The CI runs follow in plan 32-08.

Unit tests say what the code does with an answer. They cannot say which answer a real
Nextcloud gives, how long it takes, or whether an assumption of the research holds. This page
records what was run before the build, so the constants and rules of the bundle can be checked
rather than believed. Every quoted line is copied from the raw protocol:

- all runs of plan 32-02:
  [raw/32-02-messung.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-02-messung.txt)
- the program that wrote the lines:
  [scripts/tasks_measure.py](../scripts/tasks_measure.py), which loads its helpers from
  [scripts/tasks_spike.py](../scripts/tasks_spike.py)
- the live runs of plan 32-07 on Nextcloud 35, including the whole chain:
  [raw/32-07-nc35.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-07-nc35.txt)
- the live runs of plan 32-07 on Nextcloud 32:
  [raw/32-07-nc32.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-07-nc32.txt)
- the programs of those runs:
  [tests/integration/test_tasks_live.py](../tests/integration/test_tasks_live.py) (function level
  under impersonation) and [scripts/tasks_chain_evidence.py](../scripts/tasks_chain_evidence.py)
  (whole chain)

The number of tools is not held by this page; `tests/contract/test_tool_surface.py` holds it.

## Instances

| | Throwaway, SQLite | Throwaway, PostgreSQL | Nextcloud 35 | Nextcloud 32 |
|---|---|---|---|---|
| `occ status` | versionstring 35.0.2 | versionstring 35.0.2 | versionstring 35.0.0 | versionstring 32.0.15 |
| Database | sqlite3 | pgsql (PostgreSQL 17.11) | sqlite3 | sqlite3 |
| Topology | `compose.spike-tags.yml`, removed with `down -v` | `compose.spike-tags-pg.yml`, removed with `down -v` | `compose.nc35.yml`: `nc35-nc`, `nc35-harp`, `nc35-caddy` (app container stopped) | `compose.exapp.yml`: `nc-mcp-exapp-nc`, `nc-mcp-exapp-caddy` |
| Tasks app | 0.18.1 | 0.18.1 | 0.18.1, installed for the run and removed again | 0.18.1, installed for the run and removed again |
| Requests | app password | app password | AppAPI impersonation, `mcp_connector` 0.7.2 | AppAPI impersonation, `mcp_connector` 0.7.2 |

Only one instance ran at a time. Each measured list held 2000 tasks, 1900 of them done, with
parents of 0, 1 and 25 sub tasks. The two standing instances were brought back to their state
before the run: lists deleted with `X-NC-CalDAV-No-Trashbin: 1`, shares removed, both test
accounts deleted, the Tasks app removed. A baseline read from the database (calendars,
calendar objects, deleted calendar objects, subscriptions, shares) was equal before and after
for every account on both instances; the raw protocol holds those lines.

Runs of plan 32-07, one instance at a time, each with a baseline before and after:

| Run | Instance | Tasks app | App under test | Result |
|---|---|---|---|---|
| Whole chain | Nextcloud 35.0.0 | none, then 0.18.1 for the provider hit | ExApp container, image of this branch (`sha256:00a2e4b0...`) | 27 tools, calendar answer byte equal |
| `test_tasks_live.py` | Nextcloud 35.0.0 | none | tool functions of this branch, impersonation | 17 passed |
| `test_tasks_live.py` and canary | Nextcloud 35.0.0 | 0.18.1 | tool functions of this branch, impersonation | 17 passed, canary 4 passed |
| `test_tasks_live.py` | Nextcloud 32.0.15 | none | tool functions of this branch, impersonation | 17 passed |
| `test_tasks_live.py` and acceptance | Nextcloud 32.0.15 | 0.18.1 | tool functions of this branch, impersonation; acceptance over stdio | 17 passed; every task step OK |

## Measurements before the build

### Time budget per list for `tasks_search`

```
KOSTEN suche modus=offen impersonation=ja db=nc35 status=207 median_ms=91 max_ms=98 min_ms=86 p95_zweitgroesster_ms=96 bytes=70218 treffer=100 (n=15)
KOSTEN suche modus=alle impersonation=ja db=nc35 status=207 median_ms=108 max_ms=113 min_ms=103 p95_zweitgroesster_ms=113 bytes=1514508 treffer=2000 (n=15)
KOSTEN suche modus=alle impersonation=nein db=pg status=207 median_ms=150 max_ms=255 min_ms=137 p95_zweitgroesster_ms=248 bytes=1514508 treffer=2000 (n=15)
MESSWERT per_list_timeout_s=1 regel=max(1,ceil(2*max)) max_s=0.113 quelle=nc35-impersonation modus=alle aufgaben=2000 (offen max 0,098 s); Wegwerf-Reihen höchstens 0,255 s (pg, alle); Netzwerkreserve: gemessen über Loopback ohne Netzlaufzeit, die Untergrenze 1 s lässt gegenüber dem größten Wert aller Reihen den Faktor 3,9 und damit rund 0,7 s Netzlaufzeit je Anfrage
```

### Sub task query and its budget (D-32-03)

```
KOSTEN kinder impersonation=ja kinder=25 collation=ohne db=nc35 status=207 median_ms=87 max_ms=89 min_ms=85 p95_zweitgroesster_ms=88 bytes=19004 treffer=25 (n=6)
KOSTEN kinder impersonation=ja kinder=25 collation=i;octet db=nc35 status=207 median_ms=88 max_ms=92 min_ms=86 p95_zweitgroesster_ms=89 bytes=19004 treffer=25 (n=6)
KOSTEN eltern-uid impersonation=ja collation=i;octet db=nc35 status=207 median_ms=89 max_ms=91 min_ms=86 p95_zweitgroesster_ms=90 bytes=949 treffer=1 (n=6)
KOSTEN kinder kinder=25 collation=i;octet db=pg status=207 median_ms=113 max_ms=121 min_ms=107 p95_zweitgroesster_ms=115 bytes=19004 treffer=25 (n=15) impersonation=nein
MESSWERT subtask_timeout_s=1 regel=max(1,ceil(2*max)) max_s=0.107 quelle=nc35-impersonation (kinder 0/1/25 und eltern-uid, beide Formen, 2000 Aufgaben); Wegwerf-Reihen höchstens 0,172 s (pg); dieselbe Netzwerkreserve wie per_list_timeout_s
```

The sub task query costs about as much as the mode `offen` (assumption A7 holds). The parent
lookup by `UID` for `tasks_read` costs the same.

### Cap of the results

```
MESSWERT max_results=500 bestaetigt: Antwort alle bei 2000 Aufgaben 1514508 Bytes (rund 757 Bytes je Aufgabe, 500 Aufgaben rund 0,38 MB) in höchstens 0,113 s; Deckel des Blätterns 500 Treffer gesamt, das sind 20 Seiten zu 25 (D-32-08), danach ehrliche Notiz
```

### Form of the text-match (deviation H)

```
GEGENPROBE collation db=sqlite treffer_gleich=ja erwartete_anzahl=ja kinder0=0/0 kinder1=1/1 kinder25=25/25 eltern=1/1 (Mengen der Objekt-Hrefs, ohne/i;octet; erwartet kinder0=0 kinder1=1 kinder25=25 eltern=1)
GEGENPROBE collation db=pg treffer_gleich=ja erwartete_anzahl=ja kinder0=0/0 kinder1=1/1 kinder25=25/25 eltern=1/1 (Mengen der Objekt-Hrefs, ohne/i;octet; erwartet kinder0=0 kinder1=1 kinder25=25 eltern=1)
GEGENPROBE collation db=nc35 treffer_gleich=ja erwartete_anzahl=ja kinder0=0/0 kinder1=1/1 kinder25=25/25 eltern=1/1 (Mengen der Objekt-Hrefs, ohne/i;octet; erwartet kinder0=0 kinder1=1 kinder25=25 eltern=1)
ENTSCHEID collation=i;octet (beide Formen liefern dieselben Treffer auf sqlite, pg und nc35: GEGENPROBE collation treffer_gleich=ja erwartete_anzahl=ja; i;octet vergleicht Bytes ohne Kleinschreibung, die Nachprüfung im Connector bleibt, Abweichung H erledigt)
```

### Names of shared lists (A2, D-32-14)

The lines carry yes/no marks only, never a name or an account id.

```
NAMEN nc35 sammlung=rw owner_displayname_lesbar=ja zusatz_passt=ja name_ohne_zusatz_gleich_original=ja owner_gleich_eigenem_owner=nein read_only=leer privilegien=bind,read,read-acl,read-current-user-privilege-set,read-free-busy,unbind,unlock,write,write-acl,write-content,write-properties schreibrecht_spike_menge=ja shared_by_in_uri=ja komponenten=VTODO
NAMEN nc35 sammlung=ro owner_displayname_lesbar=ja zusatz_passt=ja name_ohne_zusatz_gleich_original=ja owner_gleich_eigenem_owner=nein read_only=1 privilegien=read,read-acl,read-current-user-privilege-set,read-free-busy,write-properties schreibrecht_spike_menge=nein shared_by_in_uri=ja komponenten=VTODO
NAMEN nc32 sammlung=rw owner_displayname_lesbar=ja zusatz_passt=ja name_ohne_zusatz_gleich_original=ja owner_gleich_eigenem_owner=nein read_only=leer privilegien=bind,read,read-acl,read-current-user-privilege-set,read-free-busy,unbind,unlock,write,write-acl,write-content,write-properties schreibrecht_spike_menge=ja shared_by_in_uri=ja komponenten=VTODO
NAMEN nc32 sammlung=ro owner_displayname_lesbar=ja zusatz_passt=ja name_ohne_zusatz_gleich_original=ja owner_gleich_eigenem_owner=nein read_only=1 privilegien=read,read-acl,read-current-user-privilege-set,read-free-busy,write-properties schreibrecht_spike_menge=nein shared_by_in_uri=ja komponenten=VTODO
ENTSCHEID namensregel=owner-displayname (auf 32 und 35 zeigt jede geteilte Sammlung, rw und ro, owner_displayname_lesbar=ja und zusatz_passt=ja, der Name ohne Zusatz ist gleich dem Originalnamen; eigene Listen tragen keinen Zusatz)
```

### Write permission ahead of a write

```
ENTSCHEID writable_privilegien=write,write-content,bind,all (mindestens eines; ordnet alle Sammlungen der Fixture und der Messung auf 32 und 35 richtig ein: eigen, gemischt und rw ja, ro, Deck und Geburtstage nein; write-properties zählt nicht, es steht auch bei nur lesbaren Sammlungen)
```

### Calendar home of an account without any login (A1, TASK-03)

```
HOME nc35 konto=nie status=207 vtodo_listen=0 kalender=0 nur_vevent=nein zweiter_status=207 kalender_db_vorher=0 kalender_db_danach=0 fehler=(root {DAV:}multistatus)
HOME nc32 konto=nie status=207 vtodo_listen=0 kalender=0 nur_vevent=nein zweiter_status=207 kalender_db_vorher=0 kalender_db_danach=0 fehler=(root {DAV:}multistatus)
HOME nc35 konto=frisch status=207 vtodo_listen=0 kalender=2 nur_vevent=ja zweiter_status=207 kalender_db_vorher=2 kalender_db_danach=2 fehler=(root {DAV:}multistatus)
HOME nc32 konto=frisch status=207 vtodo_listen=0 kalender=2 nur_vevent=ja zweiter_status=207 kalender_db_vorher=2 kalender_db_danach=2 fehler=(root {DAV:}multistatus)
ENTSCHEID home404=e6 (gemessen auf 32 und 35: das Kalender-Home eines Kontos ohne jede Anmeldung antwortet unter Impersonation 207 mit null Sammlungen, kein 404, A1 widerlegt; die leere 207 ist Fall E6, ein 404 wird im Client ebenfalls als E6 behandelt)
```

Impersonation does not create a calendar for an account that never logged in. An account after
one login has two calendars, both VEVENT only, and no task list.

### State of the Tasks app (A3, D-32-10)

```
APPSTATE nc35 zustand=disable-ohne-neustart navigation=nein provider=nein app_list=aus-0.18.1 (installed 0.18.1) nav_status=200 provider_suche_status=200 provider_treffer=0
APPSTATE nc35 zustand=disable-nach-neustart navigation=nein provider=nein app_list=aus-0.18.1 (installed 0.18.1) nav_status=200 provider_suche_status=200 provider_treffer=0
APPSTATE nc32 zustand=disable-ohne-neustart navigation=ja provider=ja app_list=aus-0.18.1 (installed 0.18.1) nav_status=200 provider_suche_status=200 provider_treffer=3
APPSTATE nc32 zustand=disable-nach-neustart navigation=nein provider=nein app_list=aus-0.18.1 (installed 0.18.1) nav_status=200 provider_suche_status=200 provider_treffer=0
APPSTATE nc32 zustand=enable-ohne-neustart navigation=nein provider=nein app_list=0.18.1 nav_status=200 provider_suche_status=200 provider_treffer=0
ENTSCHEID erkennung=keine (auf 35 spiegeln Navigation und Provider-Liste jeden Zustand sofort, auf 32 nach app:disable ohne Neustart weiter ja und nach app:enable ohne Neustart weiter nein, also falsch und nicht unklar; der Hinweis aus D-32-10 entfällt)
```

### Link form for `fetch` (A5, D-32-15)

```
LINK nc35 form=index.php auth=impersonation status=200 ziel=aufgabe location=-
LINK nc35 form=ohne auth=impersonation status=200 ziel=aufgabe location=-
LINK nc32 form=index.php auth=impersonation status=200 ziel=aufgabe location=-
PROVIDERLINK nc35 fall=geteilt form=pfad index_php=nein aufloesbar=ja shared_by_im_link=ja prozentkodiert=nein link={base}/apps/tasks/calendars/p3202-rw_shared_by_<konto>/tasks/p3202-link-geteilt-120124.ics
PROVIDERLINK nc35 fall=sonderzeichen form=pfad index_php=nein aufloesbar=ja shared_by_im_link=nein prozentkodiert=nein link={base}/apps/tasks/calendars/p3202-sonder-äö/tasks/p3202-link-sonder-ä&+ 120124.ics
ENTSCHEID linkform=index.php (auf 32 und 35 unter Impersonation öffnen beide Formen die Seite der Tasks-App mit Status 200; die Form mit index.php hängt nicht an hübschen URLs; der Provider selbst liefert die Form ohne index.php und ohne Prozentkodierung)
```

`ziel=aufgabe` means a 200 that loads the script of the Tasks app; whether its router then
opens the very task was not measured, that needs a browser. The provider link of a shared list
carries the account id of the owner in the path (here replaced), which is why `fetch` links a
task in a shared list only to the start page of the app (D-32-15). Special characters in list
and object name come back unencoded and still resolve with `provider_link_parts`.

## Not measured

- Nextcloud 33 and 34: only through the source, as in the spike of phase 30.
- The owner name with brackets of its own: covered by the unit tests of `owner_suffix_strip`,
  not by an instance, because changing the display name of a test account was not part of the
  owner release.
- Nothing fell away through the owner release: `FREIGABE zustand=option-a` covered nc35 and
  Nextcloud 32.
- The time budgets come from loopback requests on one host; a real network adds latency, which
  the floor of 1 s absorbs as stated in the lines above.

## Nextcloud 35 without the Tasks app

Plan 32-07, `tests/integration/test_tasks_live.py` with `NC_MCP_REQUIRE_LIVE=1` and
`NC_MCP_EXPECT_TASKS_APP=0`, Nextcloud 35.0.0, the ExApp on the image of this branch. Every
measured call runs under AppAPI impersonation; the app password of the test account is only
used by the harness (counter checks, scaffolding, removal).

```
TASKSAPP nc35 vorher=keine
VERSION nc=35.0.0.10 versionstring=35.0.0 (occ status)
TASKSAPP erwartet=0 occ_app_list=keine passt=ja
KONTROLLE b nc=35.0.0.10 nutzer=alice status=PROPFIND:401 ergebnis=ok | tool: ToolError reason=unspecified message='Nextcloud rejected the app password.'; calendarobjects p32live-e3578d01-a vorher=4 nachher=4
AUFGABE anlegen-mit-list nc=35.0.0.10 nutzer=alice status=PROPFIND:207,PUT:201,GET:200,PROPFIND:207,GET:200,PUT:201,GET:200 ergebnis=ok | GET 200 with the app password; DUE;VALUE=DATE:20261203 in the raw object; no 20261204 anywhere in the raw object; DTSTART;VALUE=DATE:20261201; CATEGORIES 'CATEGORIES:p32live-e3578d01-x,p32live-e3578d01-y'; PRIORITY:3; RELATED-TO the UID of the parent 6b84bc3a-04e5-420e-aa25-01d814f82ef5; {"confirmed": true, "created": true, "due": "2026-12-03", "id": "task:p32live-e3578d01-a:84a822e7-d719-4b97-8cc3-0260579033f4.ics", "list": {"name": "p32live-e3578d01-a", "shared": false, "writable": true}, "start": "2026-12-01", "summary": "p32live-e3578d01-kind"}; no hint (erkennung=keine)
AUFGABE ohne-list-zwei-listen nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=unspecified message='This account has more than one task list to write to, so list has to be named.'; hint 'Name the list with list=<name>. Writable task lists: p3207-aufgaben, p32live-e3578d01-a, p32live-e3578d01-b, p32live-e3578d01-rw (shared, key sfd3bf5132324e07f), personal.'; no PUT; calendarobjects vorher={'a': 6, 'b': 1} nachher={'a': 6, 'b': 1}
AUFGABE geteilt-namen nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | roher displayname mit zusatz in der discovery: 2 von 2; the server really adds the owner, so stripping is proven; rw: {'name': 'p32live-e3578d01-rw', 'shared': True, 'writable': True}; ro: {'name': 'p32live-e3578d01-ro', 'shared': True, 'writable': False}; a: {'name': 'p32live-e3578d01-a', 'shared': False, 'writable': True}; the task of the rw share is a hit
AUFGABE geteilt-rw-mit-list nc=35.0.0.10 nutzer=alice status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | the id carries the hashed key: True; GET by the owner 200; calendarobjects vorher=1 nachher=2; PUT [201]
AUFGABE geteilt-ro-vorab nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The task list 'p32live-e3578d01-ro' is read only for this account."; The task list 'p32live-e3578d01-ro' is read only for this account.; the hook saw no PUT; calendarobjects vorher=1 nachher=1
AUFGABE geteilt-ro-server nc=35.0.0.10 nutzer=alice status=keine ergebnis=ok | harness PUT with the app password of alice, not the connector; PUT 404; calendarobjects vorher=1 nachher=1
AUFGABE d-32-16 nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message='The parent task lives in a shared list, and a shared list is only written to when it is named.'; no PUT; calendarobjects vorher=2 nachher=2
AUFGABE suche-standard-und-faellig nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207 ergebnis=ok | open task in the default search; completed task not in it; completed task with status=completed; due 2026-12-04 within due_by 2026-12-10; due 2026-12-20 outside; an undated task is not due by a day
AUFGABE ausfall-liste nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | REPORT of p32live-e3578d01-b held back 3.0 s in the client hook; degraded [{'list': 'p32live-e3578d01-b', 'reason': 'The task list did not answer within 1 second.'}]; the other lists still answer
AUFGABE fetch-gleich-read nc=35.0.0.10 nutzer=alice status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207,REPORT:207 ergebnis=ok | id task:p32live-e3578d01-a:84a822e7-d719-4b97-8cc3-0260579033f4.ics; title p32live-e3578d01-kind; status open; deep link of an own list
AUFGABE deck nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | positive control: app-generated--deck--board-86 with VTODO in the discovery of alice; positive control: Deck REST 200; no hit for the card title: set(); ToolError reason=unknown_id message="Nextcloud does not know the task 'task:app-generated--deck--board-86:card-135.ics'."; deck marker in no answer
AUFGABE task-03-mit-anmeldung nc=35.0.0.10 nutzer=p32live-e3578d01-frisch status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; Basic cloud/user 200; BASELINE calendars=2 objekte=2 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE task-03-ohne-anmeldung nc=35.0.0.10 nutzer=p32live-e3578d01-nie status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; BASELINE calendars=0 objekte=0 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE provider-tasksapp-0 nc=35.0.0.10 nutzer=alice status=ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,PUT:201,GET:200 ergebnis=ok | tasksapp occ=keine ENTSCHEID erkennung=keine; provider tasks listed=False hits=[]; the provider is not listed; no task hit; no hit of kind task from anywhere; tasks_create created=True hint=nein
17 passed in 20.38s
LAUF nc35 tasksapp=keine ergebnis=passed 17
```

The last case of the run scans every kept answer (22) for the account id and the display
name of the account that shared the two lists, and for the marker of a shared URI: none was
found. The line names that account and is therefore not quoted here.

## Nextcloud 35 with the Tasks app

The same run after `occ app:install tasks` and a restart of the Nextcloud container, with
`NC_MCP_EXPECT_TASKS_APP=1`. The canary ran in the same state.

```
TASKSAPP nc35 lauf=0.18.1
VERSION nc=35.0.0.10 versionstring=35.0.0 (occ status)
TASKSAPP erwartet=1 occ_app_list=0.18.1 passt=ja
KONTROLLE b nc=35.0.0.10 nutzer=alice status=PROPFIND:401 ergebnis=ok | tool: ToolError reason=unspecified message='Nextcloud rejected the app password.'; calendarobjects p32live-f3f4e896-a vorher=4 nachher=4
AUFGABE anlegen-mit-list nc=35.0.0.10 nutzer=alice status=PROPFIND:207,PUT:201,GET:200,PROPFIND:207,GET:200,PUT:201,GET:200 ergebnis=ok | GET 200 with the app password; DUE;VALUE=DATE:20261203 in the raw object; no 20261204 anywhere in the raw object; DTSTART;VALUE=DATE:20261201; CATEGORIES 'CATEGORIES:p32live-f3f4e896-x,p32live-f3f4e896-y'; PRIORITY:3; RELATED-TO the UID of the parent 94f426f6-8bb6-4eee-9965-c4d127e858d0; {"confirmed": true, "created": true, "due": "2026-12-03", "id": "task:p32live-f3f4e896-a:58c908c1-8ff3-413c-8bb5-244ca9e4e0ea.ics", "list": {"name": "p32live-f3f4e896-a", "shared": false, "writable": true}, "start": "2026-12-01", "summary": "p32live-f3f4e896-kind"}; no hint (erkennung=keine)
AUFGABE ohne-list-zwei-listen nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=unspecified message='This account has more than one task list to write to, so list has to be named.'; hint 'Name the list with list=<name>. Writable task lists: p3207-aufgaben, p32live-f3f4e896-a, p32live-f3f4e896-b, p32live-f3f4e896-rw (shared, key s6e58b5aedbf4679e), personal.'; no PUT; calendarobjects vorher={'a': 6, 'b': 1} nachher={'a': 6, 'b': 1}
AUFGABE geteilt-namen nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | roher displayname mit zusatz in der discovery: 2 von 2; the server really adds the owner, so stripping is proven; rw: {'name': 'p32live-f3f4e896-rw', 'shared': True, 'writable': True}; ro: {'name': 'p32live-f3f4e896-ro', 'shared': True, 'writable': False}; a: {'name': 'p32live-f3f4e896-a', 'shared': False, 'writable': True}; the task of the rw share is a hit
AUFGABE geteilt-rw-mit-list nc=35.0.0.10 nutzer=alice status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | the id carries the hashed key: True; GET by the owner 200; calendarobjects vorher=1 nachher=2; PUT [201]
AUFGABE geteilt-ro-vorab nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The task list 'p32live-f3f4e896-ro' is read only for this account."; The task list 'p32live-f3f4e896-ro' is read only for this account.; the hook saw no PUT; calendarobjects vorher=1 nachher=1
AUFGABE geteilt-ro-server nc=35.0.0.10 nutzer=alice status=keine ergebnis=ok | harness PUT with the app password of alice, not the connector; PUT 404; calendarobjects vorher=1 nachher=1
AUFGABE d-32-16 nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message='The parent task lives in a shared list, and a shared list is only written to when it is named.'; no PUT; calendarobjects vorher=2 nachher=2
AUFGABE suche-standard-und-faellig nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207 ergebnis=ok | open task in the default search; completed task not in it; completed task with status=completed; due 2026-12-04 within due_by 2026-12-10; due 2026-12-20 outside; an undated task is not due by a day
AUFGABE ausfall-liste nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | REPORT of p32live-f3f4e896-b held back 3.0 s in the client hook; degraded [{'list': 'p32live-f3f4e896-b', 'reason': 'The task list did not answer within 1 second.'}]; the other lists still answer
AUFGABE fetch-gleich-read nc=35.0.0.10 nutzer=alice status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207,REPORT:207 ergebnis=ok | id task:p32live-f3f4e896-a:58c908c1-8ff3-413c-8bb5-244ca9e4e0ea.ics; title p32live-f3f4e896-kind; status open; deep link of an own list
AUFGABE deck nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | positive control: app-generated--deck--board-87 with VTODO in the discovery of alice; positive control: Deck REST 200; no hit for the card title: set(); ToolError reason=unknown_id message="Nextcloud does not know the task 'task:app-generated--deck--board-87:card-136.ics'."; deck marker in no answer
AUFGABE task-03-mit-anmeldung nc=35.0.0.10 nutzer=p32live-f3f4e896-frisch status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; Basic cloud/user 200; BASELINE calendars=2 objekte=2 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE task-03-ohne-anmeldung nc=35.0.0.10 nutzer=p32live-f3f4e896-nie status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; BASELINE calendars=0 objekte=0 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE provider-tasksapp-1 nc=35.0.0.10 nutzer=alice status=ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,GET:200,REPORT:207,PROPFIND:207,PUT:201,GET:200 ergebnis=ok | tasksapp occ=0.18.1 ENTSCHEID erkennung=keine; provider tasks listed=True hits=['task:p32live-f3f4e896-a:p32live-f3f4e896-faellig-edc2e9.ics']; the provider is listed; hit id == task:p32live-f3f4e896-a:p32live-f3f4e896-faellig-edc2e9.ics; tasks_read of that id; tasks_create created=True hint=nein
17 passed in 20.51s
LAUF nc35 tasksapp=0.18.1 ergebnis=passed 17
KANARIE normal geprüft 27 von 27
.KANARIE ausfall-500 geprüft 27 von 27
.KANARIE ausfall-412 geprüft 27 von 27
.KANARIE ausfall-timeout geprüft 27 von 27
4 passed in 76.91s (0:01:16)
KANARIE nc35 ergebnis=passed 4 tasksapp=0.18.1
```

## Nextcloud 32 without the Tasks app

Route `compose.exapp.yml` on 32.0.15, the ExApp as a local process of this working tree at
the daemon `manual_install`, started with the five variables of plan 31-05b only.

```
TASKSAPP nc32 vorher=keine
PROZESS lokal gestartet port=23001 heartbeat_vom_host=200 heartbeat_aus_nc={"status":"ok"} kommando=uv run --no-sync nc-mcp-exapp (im Worktree, PYTHONPATH=src)
KETTE nc32 entfaellt grund=manual-install (auf 32 läuft die ExApp als lokaler Prozess am Daemon manual_install; eine Kette über ein Image gibt es dort nicht, 31-07 offene Punkte)
VERSION nc=32.0.15.1 versionstring=32.0.15 (occ status)
TASKSAPP erwartet=0 occ_app_list=keine passt=ja
KONTROLLE b nc=32.0.15.1 nutzer=alice status=PROPFIND:401 ergebnis=ok | tool: ToolError reason=unspecified message='Nextcloud rejected the app password.'; calendarobjects p32live-2dc3b0e4-a vorher=4 nachher=4
AUFGABE anlegen-mit-list nc=32.0.15.1 nutzer=alice status=PROPFIND:207,PUT:201,GET:200,PROPFIND:207,GET:200,PUT:201,GET:200 ergebnis=ok | GET 200 with the app password; DUE;VALUE=DATE:20261203 in the raw object; no 20261204 anywhere in the raw object; DTSTART;VALUE=DATE:20261201; CATEGORIES 'CATEGORIES:p32live-2dc3b0e4-x,p32live-2dc3b0e4-y'; PRIORITY:3; RELATED-TO the UID of the parent 658e5521-2128-487a-b6b3-9383cf02181c; {"confirmed": true, "created": true, "due": "2026-12-03", "id": "task:p32live-2dc3b0e4-a:2e63e778-77f7-4306-801b-737f6ea71276.ics", "list": {"name": "p32live-2dc3b0e4-a", "shared": false, "writable": true}, "start": "2026-12-01", "summary": "p32live-2dc3b0e4-kind"}; no hint (erkennung=keine)
AUFGABE ohne-list-zwei-listen nc=32.0.15.1 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=unspecified message='This account has more than one task list to write to, so list has to be named.'; hint 'Name the list with list=<name>. Writable task lists: p32live-2dc3b0e4-a, p32live-2dc3b0e4-b, p32live-2dc3b0e4-rw (shared, key sf5ca01922474da16), personal.'; no PUT; calendarobjects vorher={'a': 6, 'b': 1} nachher={'a': 6, 'b': 1}
AUFGABE geteilt-namen nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | roher displayname mit zusatz in der discovery: 2 von 2; the server really adds the owner, so stripping is proven; rw: {'name': 'p32live-2dc3b0e4-rw', 'shared': True, 'writable': True}; ro: {'name': 'p32live-2dc3b0e4-ro', 'shared': True, 'writable': False}; a: {'name': 'p32live-2dc3b0e4-a', 'shared': False, 'writable': True}; the task of the rw share is a hit
AUFGABE geteilt-rw-mit-list nc=32.0.15.1 nutzer=alice status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | the id carries the hashed key: True; GET by the owner 200; calendarobjects vorher=1 nachher=2; PUT [201]
AUFGABE geteilt-ro-vorab nc=32.0.15.1 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The task list 'p32live-2dc3b0e4-ro' is read only for this account."; The task list 'p32live-2dc3b0e4-ro' is read only for this account.; the hook saw no PUT; calendarobjects vorher=1 nachher=1
AUFGABE geteilt-ro-server nc=32.0.15.1 nutzer=alice status=keine ergebnis=ok | harness PUT with the app password of alice, not the connector; PUT 404; calendarobjects vorher=1 nachher=1
AUFGABE d-32-16 nc=32.0.15.1 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message='The parent task lives in a shared list, and a shared list is only written to when it is named.'; no PUT; calendarobjects vorher=2 nachher=2
AUFGABE suche-standard-und-faellig nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207 ergebnis=ok | open task in the default search; completed task not in it; completed task with status=completed; due 2026-12-04 within due_by 2026-12-10; due 2026-12-20 outside; an undated task is not due by a day
AUFGABE ausfall-liste nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | REPORT of p32live-2dc3b0e4-b held back 3.0 s in the client hook; degraded [{'list': 'p32live-2dc3b0e4-b', 'reason': 'The task list did not answer within 1 second.'}]; the other lists still answer
AUFGABE fetch-gleich-read nc=32.0.15.1 nutzer=alice status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207,REPORT:207 ergebnis=ok | id task:p32live-2dc3b0e4-a:2e63e778-77f7-4306-801b-737f6ea71276.ics; title p32live-2dc3b0e4-kind; status open; deep link of an own list
AUFGABE deck nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | positive control: app-generated--deck--board-20 with VTODO in the discovery of alice; positive control: Deck REST 200; no hit for the card title: set(); ToolError reason=unknown_id message="Nextcloud does not know the task 'task:app-generated--deck--board-20:card-35.ics'."; deck marker in no answer
AUFGABE task-03-mit-anmeldung nc=32.0.15.1 nutzer=p32live-2dc3b0e4-frisch status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; Basic cloud/user 200; BASELINE calendars=2 objekte=2 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE task-03-ohne-anmeldung nc=32.0.15.1 nutzer=p32live-2dc3b0e4-nie status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; BASELINE calendars=0 objekte=0 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE provider-tasksapp-0 nc=32.0.15.1 nutzer=alice status=ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,PUT:201,GET:200 ergebnis=ok | tasksapp occ=keine ENTSCHEID erkennung=keine; provider tasks listed=False hits=[]; the provider is not listed; no task hit; no hit of kind task from anywhere; tasks_create created=True hint=nein
17 passed in 20.36s
LAUF nc32 tasksapp=keine ergebnis=passed 17
```

## Nextcloud 32 with the Tasks app

The same run after `occ app:install tasks` and a restart, then the acceptance script over
stdio with the code of this working tree. Its only non-OK step is the full text of a mail,
a missing prerequisite of the test instance (GreenMail keeps mail in memory and was empty
after the restart), not a tool failure; every task step is OK.

```
TASKSAPP nc32 lauf=0.18.1
VERSION nc=32.0.15.1 versionstring=32.0.15 (occ status)
TASKSAPP erwartet=1 occ_app_list=0.18.1 passt=ja
KONTROLLE b nc=32.0.15.1 nutzer=alice status=PROPFIND:401 ergebnis=ok | tool: ToolError reason=unspecified message='Nextcloud rejected the app password.'; calendarobjects p32live-e9921be7-a vorher=4 nachher=4
AUFGABE anlegen-mit-list nc=32.0.15.1 nutzer=alice status=PROPFIND:207,PUT:201,GET:200,PROPFIND:207,GET:200,PUT:201,GET:200 ergebnis=ok | GET 200 with the app password; DUE;VALUE=DATE:20261203 in the raw object; no 20261204 anywhere in the raw object; DTSTART;VALUE=DATE:20261201; CATEGORIES 'CATEGORIES:p32live-e9921be7-x,p32live-e9921be7-y'; PRIORITY:3; RELATED-TO the UID of the parent baf5a1ae-6d8e-4701-8c79-d2e05d68d679; {"confirmed": true, "created": true, "due": "2026-12-03", "id": "task:p32live-e9921be7-a:1c6f0713-6e91-4fee-b171-edf15e650f02.ics", "list": {"name": "p32live-e9921be7-a", "shared": false, "writable": true}, "start": "2026-12-01", "summary": "p32live-e9921be7-kind"}; no hint (erkennung=keine)
AUFGABE ohne-list-zwei-listen nc=32.0.15.1 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=unspecified message='This account has more than one task list to write to, so list has to be named.'; hint 'Name the list with list=<name>. Writable task lists: p32live-e9921be7-a, p32live-e9921be7-b, p32live-e9921be7-rw (shared, key sbc949da3f5b041b4), personal.'; no PUT; calendarobjects vorher={'a': 6, 'b': 1} nachher={'a': 6, 'b': 1}
AUFGABE geteilt-namen nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | roher displayname mit zusatz in der discovery: 2 von 2; the server really adds the owner, so stripping is proven; rw: {'name': 'p32live-e9921be7-rw', 'shared': True, 'writable': True}; ro: {'name': 'p32live-e9921be7-ro', 'shared': True, 'writable': False}; a: {'name': 'p32live-e9921be7-a', 'shared': False, 'writable': True}; the task of the rw share is a hit
AUFGABE geteilt-rw-mit-list nc=32.0.15.1 nutzer=alice status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | the id carries the hashed key: True; GET by the owner 200; calendarobjects vorher=1 nachher=2; PUT [201]
AUFGABE geteilt-ro-vorab nc=32.0.15.1 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The task list 'p32live-e9921be7-ro' is read only for this account."; The task list 'p32live-e9921be7-ro' is read only for this account.; the hook saw no PUT; calendarobjects vorher=1 nachher=1
AUFGABE geteilt-ro-server nc=32.0.15.1 nutzer=alice status=keine ergebnis=ok | harness PUT with the app password of alice, not the connector; PUT 404; calendarobjects vorher=1 nachher=1
AUFGABE d-32-16 nc=32.0.15.1 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message='The parent task lives in a shared list, and a shared list is only written to when it is named.'; no PUT; calendarobjects vorher=2 nachher=2
AUFGABE suche-standard-und-faellig nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207 ergebnis=ok | open task in the default search; completed task not in it; completed task with status=completed; due 2026-12-04 within due_by 2026-12-10; due 2026-12-20 outside; an undated task is not due by a day
AUFGABE ausfall-liste nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | REPORT of p32live-e9921be7-b held back 3.0 s in the client hook; degraded [{'list': 'p32live-e9921be7-b', 'reason': 'The task list did not answer within 1 second.'}]; the other lists still answer
AUFGABE fetch-gleich-read nc=32.0.15.1 nutzer=alice status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207,REPORT:207 ergebnis=ok | id task:p32live-e9921be7-a:1c6f0713-6e91-4fee-b171-edf15e650f02.ics; title p32live-e9921be7-kind; status open; deep link of an own list
AUFGABE deck nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | positive control: app-generated--deck--board-21 with VTODO in the discovery of alice; positive control: Deck REST 200; no hit for the card title: set(); ToolError reason=unknown_id message="Nextcloud does not know the task 'task:app-generated--deck--board-21:card-36.ics'."; deck marker in no answer
AUFGABE task-03-mit-anmeldung nc=32.0.15.1 nutzer=p32live-e9921be7-frisch status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; Basic cloud/user 200; BASELINE calendars=2 objekte=2 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE task-03-ohne-anmeldung nc=32.0.15.1 nutzer=p32live-e9921be7-nie status=PROPFIND:207,PROPFIND:207 ergebnis=ok | occ user:add exit=0; BASELINE calendars=0 objekte=0 geloescht=0 shares=0 abos=0; {"hint": "This account has no task list yet. Create one in the Nextcloud Tasks app; tasks_search finds its tasks from then on.", "tasks": []}; ToolError reason=unspecified message='This account has no task list.'; hint 'Create a list in the Nextcloud Tasks app, then try again.'; no PUT; occ user:delete ok
AUFGABE provider-tasksapp-1 nc=32.0.15.1 nutzer=alice status=ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,GET:200,REPORT:207,PROPFIND:207,PUT:201,GET:200 ergebnis=ok | tasksapp occ=0.18.1 ENTSCHEID erkennung=keine; provider tasks listed=True hits=['task:p32live-e9921be7-a:p32live-e9921be7-faellig-93e07c.ics']; the provider is listed; hit id == task:p32live-e9921be7-a:p32live-e9921be7-faellig-93e07c.ics; tasks_read of that id; tasks_create created=True hint=nein
17 passed in 20.03s
LAUF nc32 tasksapp=0.18.1 ergebnis=passed 17
OK      tasks_create           {"id":"task:personal:22a53e7f-387a-4255-bb7d-6768c858afbe.ics","summary":"Abnahme abnahme34d11c0ced","list":{"
OK      tasks_search           {"tasks":[{"id":"task:personal:22a53e7f-387a-4255-bb7d-6768c858afbe.ics","summary":"Abnahme abnahme34d11c0ced"
OK      tasks_read             {"id":"task:personal:22a53e7f-387a-4255-bb7d-6768c858afbe.ics","summary":"Abnahme abnahme34d11c0ced","status":
OK      fetch                  { "id": "task:personal:22a53e7f-387a-4255-bb7d-6768c858afbe.ics", "title": "Abnahme abnahme34d11c0ced", "text"
PREREQ  fetch                  the Mail app of this instance itself answers HTTP 500 for mail:1: its mail server does not hand out a message it lists
exit=3
ABNAHME nc32 ergebnis=incomplete exit=3 tasks_create=OK tasks_search=OK tasks_read=OK fetch_task=OK prereq=fetch-mail (GreenMail nach dem Neustart leer, wie 31-05b) tasksapp=0.18.1
```

## Whole chain through the installed app

Nextcloud 35 only (owner release `FREIGABE owner=option-a`): MCP client of the SDK
(`scripts/oauth_flow_check.py`, loaded by [scripts/tasks_chain_evidence.py](../scripts/tasks_chain_evidence.py)),
Caddy, HaRP, the ExApp container, AppAPI impersonation, sign in through the OAuth flow of the
connector. Before the switch the registered app was the image of plan 31-07; the answers of
`calendar_list_events` were taken over that old chain first, then the app was unregistered
without `--rm-data` and registered again by `bootstrap_exapp.sh --nc35` with an image of this
branch.

```
EXAPP vorher container=/nc_app_mcp_connector image=127.0.0.1:5000/mcp_connector:0.7.2 image_id=sha256:cf01fc50812e4e0c89c713a9cd6866ca0274942ef85ab9b23ba949977a4c21d0 created=2026-11-13T03:01:24.34086982Z status=running
WERKZEUGE anzahl=24 tasks=nein familien=9
KETTE kalender-vorher werkzeug=calendar_list_events nutzer=alice argumente={"end": "2026-11-26T00:00:00Z", "start": "2026-11-25T00:00:00Z"} fehler=nein | {"count": 1, "events": [{"all_day": false, "calendar": "personal", "end": "2026-11-25T11:00:00+00:00", "id": "event:personal:p3207-termin.ics", "start": "2026-11-25T10:00:00+00:00", "summary": "p3207-termin", "uid": "p3207-termin"}], "range": {"end": "2026-11-26T00:00:00Z", "start": "2026-11-25T00:00:00Z", "timezone": "UTC"}}
EXAPP nachher container=/nc_app_mcp_connector image=127.0.0.1:5000/mcp_connector:0.7.2 image_id=sha256:00a2e4b0bfb7f283a22c944c14141b8de6b27f1faf64902ae2c23f9498782c02 created=2026-11-13T14:56:00.011142535Z status=running mounts=nc_app_mcp_connector_data:/nc_app_mcp_connector_data 
APP_SECRET gleich vor und nach dem Bootstrap=ja
WERKZEUGE anzahl=27 tasks=ja familien=10
WERKZEUGE anzahl=27 tasks=ja familien=10
KETTE kalender-nachher werkzeug=calendar_list_events nutzer=alice argumente={"end": "2026-11-26T00:00:00Z", "start": "2026-11-25T00:00:00Z"} fehler=nein | {"count": 1, "events": [{"all_day": false, "calendar": "personal", "end": "2026-11-25T11:00:00+00:00", "id": "event:personal:p3207-termin.ics", "start": "2026-11-25T10:00:00+00:00", "summary": "p3207-termin", "uid": "p3207-termin"}], "range": {"end": "2026-11-26T00:00:00Z", "start": "2026-11-25T00:00:00Z", "timezone": "UTC"}}
GLEICH ja bytes=304/304
GLEICH ja bytes=324/324
KALENDER bytegleich=ja fenster=2 (UTC-Fenster 304/304 Bytes, Fenster mit Europe/Berlin 324/324 Bytes)
```

**Calendar tools byte for byte:** `calendar_list_events` answered the same window before the
image switch (the state of the base of this phase) and after it with the same bytes, in UTC
(304 bytes) and in the zone Europe/Berlin (324 bytes). `calendar_create_event` was not
compared over the chain, because a second call would write a second event; its byte pin is
the unit test of the calendar bodies.

The three task tools and `fetch` over the chain, as alice, with the audit log switched on for
the run and one audit line per call (parameter names only, never a value):

```
KETTE anlegen werkzeug=tasks_create nutzer=alice argumente={"due": "2026-11-20", "priority": 3, "start": "2026-11-18", "summary": "p3207-eltern", "tags": ["p3207", "kette"]} fehler=ja | Error executing tool tasks_create: This account has more than one task list to write to, so list has to be named. Hint: Name the list with list=<name>. Writable task lists: p3207-aufgaben, personal.
  AUDIT 638 - 2026-11-13T14:57:07Z - u:alice - tasks_create - OAuth flow check - - - rejected - unspecified - 51 - due,priority,start,tags - -
KETTE anlegen-liste werkzeug=tasks_create nutzer=alice argumente={"due": "2026-11-20", "list": "p3207-aufgaben", "priority": 3, "start": "2026-11-18", "summary": "p3207-eltern", "tags": ["p3207", "kette"]} fehler=nein | {"confirmed": true, "created": true, "due": "2026-11-20", "id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "start": "2026-11-18", "summary": "p3207-eltern"}
  AUDIT 639 - 2026-11-13T14:57:16Z - u:alice - tasks_create - OAuth flow check - - - ok - - - 138 - due,list,priority,start,tags - -
  CATEGORIES:p3207,kette
  DTSTART;VALUE=DATE:20261118
  DUE;VALUE=DATE:20261120
  PRIORITY:3
KETTE unteraufgabe werkzeug=tasks_create nutzer=alice argumente={"list": "p3207-aufgaben", "parent": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "summary": "p3207-kind"} fehler=nein | {"confirmed": true, "created": true, "id": "task:p3207-aufgaben:3c79d6f8-d2f0-4447-8bf0-d419b920d5c3.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "summary": "p3207-kind"}
  AUDIT 640 - 2026-11-13T14:57:26Z - u:alice - tasks_create - OAuth flow check - - - ok - - - 175 - list,parent - -
KETTE suche-standard werkzeug=tasks_search nutzer=alice argumente={"query": "p3207"} fehler=nein | {"tasks": [{"due": "2026-11-20", "id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "priority": 3, "start": "2026-11-18", "status": "open", "summary": "p3207-eltern", "tags": ["p3207", "kette"]}, {"id": "task:p3207-aufgaben:3c79d6f8-d2f0-4447-8bf0-d419b920d5c3.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "parent": {"id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "summary": "p3207-eltern"}, "status": "open", "summary": "p3207-kind"}]}
  AUDIT 641 - 2026-11-13T14:57:29Z - u:alice - tasks_search - OAuth flow check - - - ok - - - 98 - query - -
KETTE suche-alle werkzeug=tasks_search nutzer=alice argumente={"query": "p3207", "status": "all"} fehler=nein | {"tasks": [{"due": "2026-11-20", "id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "priority": 3, "start": "2026-11-18", "status": "open", "summary": "p3207-eltern", "tags": ["p3207", "kette"]}, {"id": "task:p3207-aufgaben:3c79d6f8-d2f0-4447-8bf0-d419b920d5c3.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "parent": {"id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "summary": "p3207-eltern"}, "status": "open", "summary": "p3207-kind"}]}
  AUDIT 642 - 2026-11-13T14:57:33Z - u:alice - tasks_search - OAuth flow check - - - ok - - - 98 - query,status - -
KETTE suche-due-by werkzeug=tasks_search nutzer=alice argumente={"due_by": "2026-11-21", "query": "p3207"} fehler=nein | {"tasks": [{"due": "2026-11-20", "id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "priority": 3, "start": "2026-11-18", "status": "open", "summary": "p3207-eltern", "tags": ["p3207", "kette"]}]}
  AUDIT 643 - 2026-11-13T14:57:37Z - u:alice - tasks_search - OAuth flow check - - - ok - - - 103 - due_by,query - -
KETTE lesen werkzeug=tasks_read nutzer=alice argumente={"task_id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics"} fehler=nein | {"due": "2026-11-20", "id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "list": {"name": "p3207-aufgaben", "shared": false, "writable": true}, "priority": 3, "start": "2026-11-18", "status": "open", "subtasks": [{"id": "task:p3207-aufgaben:3c79d6f8-d2f0-4447-8bf0-d419b920d5c3.ics", "status": "open", "summary": "p3207-kind"}], "summary": "p3207-eltern", "tags": ["p3207", "kette"]}
  AUDIT 644 - 2026-11-13T14:57:41Z - u:alice - tasks_read - OAuth flow check - - - ok - - - 129 - task_id - -
KETTE fetch werkzeug=fetch nutzer=alice argumente={"id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics"} fehler=nein | {"id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "metadata": {"kind": "task", "list": "p3207-aufgaben", "shared": "false", "status": "open"}, "text": "p3207-eltern\nStatus: open\nDue: 2026-11-20\nStart: 2026-11-18\nPriority: 3\nTags: p3207, kette\nList: p3207-aufgaben", "title": "p3207-eltern", "url": "http://caddy/index.php/apps/tasks/calendars/p3207-aufgaben/tasks/3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics"}
  AUDIT 645 - 2026-11-13T14:57:45Z - u:alice - fetch - OAuth flow check - - - ok - - - 127 - id - -
  RELATED-TO:3ef34ffe-a615-4a5e-a54b-85d51928cf08
ROHOBJEKT due=DUE;VALUE=DATE:20261120 start=DTSTART;VALUE=DATE:20261118 categories=CATEGORIES:p3207,kette priority=PRIORITY:3 related_to=ja (Unteraufgabe RELATED-TO:3ef34ffe-a615-4a5e-a54b-85d51928cf08 = UID der Elternaufgabe)
KETTE allgemeine-suche-ohne-tasksapp werkzeug=unified_search nutzer=alice argumente={"providers": "tasks", "query": "p3207-eltern"} fehler=nein | {"count": 0, "degraded": [{"provider": "tasks", "reason": "This Nextcloud has no search provider with that id."}], "note": "matched on names and metadata; file contents are not indexed", "query": "p3207-eltern", "results": []}
  AUDIT 646 - 2026-11-13T14:58:21Z - u:alice - unified_search - OAuth flow check - - - ok - - - 110 - providers,query - -
KETTE allgemeine-suche-mit-tasksapp werkzeug=unified_search nutzer=alice argumente={"providers": "tasks", "query": "p3207-eltern"} fehler=nein | {"count": 1, "cursors": {"tasks": 1}, "note": "matched on names and metadata; file contents are not indexed", "query": "p3207-eltern", "results": [{"id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "kind": "task", "provider": "tasks", "subline": "Due on Nov 20, 2026 (p3207-aufgaben)", "title": "p3207-eltern", "url": "http://caddy/apps/tasks/calendars/p3207-aufgaben/tasks/3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics"}]}
  AUDIT 647 - 2026-11-13T14:59:18Z - u:alice - unified_search - OAuth flow check - - - ok - - - 437 - providers,query - -
KETTE suche-ohne-provider werkzeug=search nutzer=alice argumente={"query": "p3207-eltern"} fehler=nein | {"results": [{"id": "task:p3207-aufgaben:3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics", "text": "Due on Nov 20, 2026 (p3207-aufgaben)", "title": "p3207-eltern", "url": "http://caddy/apps/tasks/calendars/p3207-aufgaben/tasks/3ef34ffe-a615-4a5e-a54b-85d51928cf08.ics"}]}
  AUDIT 648 - 2026-11-13T14:59:26Z - u:alice - search - OAuth flow check - - - ok - - - 4037 - query - -
```

The hit of the provider `tasks` carries the same `task:` id that `tasks_read` and `fetch`
resolve. Without the Tasks app the cloud wide search answers empty with an honest
`degraded` entry instead of a wrong hit. The app was registered with the same version string
as before (`appinfo/info.xml` unchanged) and the same `APP_SECRET`.


## What the run found

No answer contradicted TASK-01 to TASK-07 or TASK-09; no product code was changed in plan 32-07.

- **Removal without the trash bin works for lists, not for single objects.** A `DELETE` of one
  calendar object with `X-NC-CalDAV-No-Trashbin: 1` still put the object into the calendar
  trash bin (Nextcloud 32: two objects of the acceptance script, two entries found by a
  `calendar-query` on `trashbin/objects/`; Nextcloud 35: one entry after the removal of the run).
  Deleting a whole list with the header leaves nothing behind. Every entry was removed for good
  with a DAV `DELETE`, and the baseline was equal before and after on both instances.
- **The audit log keeps parameter names only, and not all of them.** `summary` and `description`
  of `tasks_create` are not on the allow list, by design. A call refused by the argument
  validation of the SDK (a list where a string is expected) left no audit line at all.
- **Links carry the address the app uses to reach Nextcloud.** On the Nextcloud 35 topology the
  ExApp talks to `http://caddy`, so `fetch` and the search hits link there. That holds for every
  kind of id, not only for tasks, and is a property of the topology rather than of this bundle.
- **One own list or a named one.** On Nextcloud 35 the personal calendar of the test account takes
  `VTODO`, so `tasks_create` without `list` was refused over the chain and named both writable
  lists; on Nextcloud 32 the account holds exactly one own list, and the acceptance script wrote
  there without naming it.
- **A connection survives the image switch.** The OAuth connection made against the old image
  answered `tools/list` with 27 tools after the switch, without a new sign in.

## Not reproducible or not measured

- Nextcloud 32 has no whole chain: the app runs there as a local process at the daemon
  `manual_install`, not as an image behind HaRP.
- The outage of one list is produced in the client (a response hook holds the `REPORT` back for
  3 s), not by a slow server.
- The CI runs of both cases (job `exapp` without the Tasks app, job `canary-nc35` with it) follow
  in plan 32-08.
- Nextcloud 33 and 34: only through the source.
- The acceptance script did not run on Nextcloud 35: it leaves a file, a note, an event, a Deck
  card, a table row and a Talk message behind and deletes nothing, which the standing instance
  does not take. On Nextcloud 32 its mail step met a missing prerequisite (GreenMail empty after
  the restart).
- `calendar_create_event` was not compared byte for byte over the chain, because a second call
  writes a second event.
- Side finding of the research, not about this bundle: on Nextcloud 34 and 35 the search
  provider `tasks` appends the list name together with its owner to the subline of a hit of a
  shared list. That concerns `unified_search`, which passes the subline on.
- Whether the router of the Tasks app opens the very task behind a link needs a browser and
  was not measured.

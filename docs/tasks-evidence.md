# Evidence for the tasks bundle against real Nextcloud

**Date:** 2026-11-13
**Subject:** what the tasks bundle (`tasks_search`, `tasks_read`, `tasks_create`) rests on,
measured before any product code existed
**Status:** measured on two throwaway instances (Nextcloud 35.0.2 with SQLite and with
PostgreSQL) and under AppAPI impersonation on Nextcloud 35.0.0 and Nextcloud 32.0.15; every
value below is derived from these runs

Unit tests say what the code does with an answer. They cannot say which answer a real
Nextcloud gives, how long it takes, or whether an assumption of the research holds. This page
records what was run before the build, so the constants and rules of the bundle can be checked
rather than believed. Every quoted line is copied from the raw protocol:

- all runs of plan 32-02:
  [raw/32-02-messung.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-02-messung.txt)
- the program that wrote the lines:
  [scripts/tasks_measure.py](../scripts/tasks_measure.py), which loads its helpers from
  [scripts/tasks_spike.py](../scripts/tasks_spike.py)

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

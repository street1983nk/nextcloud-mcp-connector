# Evidence for the tasks bundle against real Nextcloud

**Date:** 2026-11-13
**Subject:** what the tasks bundle (`tasks_search`, `tasks_read`, `tasks_create`) rests on,
measured before any product code existed, and how the built bundle answered live
**Status:** measured on two throwaway instances (Nextcloud 35.0.2 with SQLite and with
PostgreSQL) and under AppAPI impersonation on Nextcloud 35.0.0 and Nextcloud 32.0.15; every
value below is derived from these runs. Plan 32-07 then ran the built bundle live on both
standing instances, each without and with the Tasks app 0.18.1, and on Nextcloud 35 over the
whole chain through the installed app. Plan 32-08 added the owner acceptance of the task view in
the Tasks app and one CI run of both cases. Plan 32-09 measured how an own list the account
shares itself and the provider subline of a shared list look, and proved the gap closure live
on both standing instances.

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
- the owner acceptance of plan 32-08:
  [raw/32-08-abnahme.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-08-abnahme.txt)
- the CI run of plan 32-08:
  [raw/32-08-ci.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-08-ci.txt)
- the measurement and the live runs of plan 32-09 (gap closure):
  [raw/32-09-messung.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-messung.txt),
  [raw/32-09-nc35.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-nc35.txt),
  [raw/32-09-nc32.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-nc32.txt)
- the live proof of the modifying tools of plan 33-10:
  [raw/33-10-nc35.txt](../.planning/phases/33-aufgaben-aendern/raw/33-10-nc35.txt),
  [raw/33-10-nc32.txt](../.planning/phases/33-aufgaben-aendern/raw/33-10-nc32.txt)

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

### Lists the account shares itself (D-32-18)

Plan 32-09, before the build, on Nextcloud 35 and 32, each with the app password and under
impersonation: one own task list, first private, then shared with the second test account read
only and read write, then published by link, then withdrawn. Four candidate properties were
asked for; the lines carry the state of the propstat and a count, never a name or an href.
Raw protocol:
[raw/32-09-messung.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-messung.txt).

```
HINAUS nc35 zustand=privat auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=nein eintraege=0
HINAUS nc35 zustand=an-bob-ro auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=ja eintraege=1
HINAUS nc35 zustand=an-bob-rw auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=ja eintraege=1
HINAUS nc35 zustand=veroeffentlicht auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=ja eintraege=1
HINAUS nc35 zustand=veroeffentlicht auth=appapi prop={http://calendarserver.org/ns/}publish-url status=2xx belegt=ja eintraege=1
HINAUS nc35 zustand=zurueckgenommen auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=nein eintraege=0
HINAUS nc35 zustand=hineingeteilt auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=nein eintraege=0
HINAUS nc32 zustand=privat auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=nein eintraege=0
HINAUS nc32 zustand=an-bob-ro auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=ja eintraege=1
HINAUS nc32 zustand=an-bob-rw auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=ja eintraege=1
HINAUS nc32 zustand=veroeffentlicht auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=ja eintraege=1
HINAUS nc32 zustand=veroeffentlicht auth=appapi prop={http://calendarserver.org/ns/}publish-url status=2xx belegt=ja eintraege=1
HINAUS nc32 zustand=zurueckgenommen auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=nein eintraege=0
HINAUS nc32 zustand=hineingeteilt auth=appapi prop={http://owncloud.org/ns}invite status=2xx belegt=nein eintraege=0
```

The same values stand under the app password. `cs:invite` and `DAV:share-access` answered 404
in every state on both instances. The decisions:

```
ENTSCHEID erkennung_hinaus={http://owncloud.org/ns}invite (Begründung: auf nc35 und nc32, unter App-Passwort und Impersonation gleich, steht oc:invite in einem 2xx-propstat; leer mit eintraege=0 bei privat und zurueckgenommen, belegt mit eintraege=1 bei an-bob-ro und an-bob-rw; cs:invite und DAV:share-access tragen nicht, sie antworten immer 404; auf der hineingeteilten Liste ist oc:invite leer, die Regel gilt ohnehin nur für eigene Listen)
ENTSCHEID erkennung_link={http://owncloud.org/ns}invite (Begründung: veroeffentlicht ist auf beiden Instanzen und unter beiden Anmeldearten in oc:invite belegt; cs:publish-url ist dort zusätzlich belegt und sonst 404, sie wird als zweites Merkmal mitgefragt: belegt eines von beiden, gilt die Liste als hinausgeteilt)
ENTSCHEID punkt6=unlesbar-gilt-als-hinausgeteilt (Begründung: eine nicht geteilte eigene Liste meldet oc:invite auf 32 und 35 lesbar im 2xx-propstat; fehlt die Eigenschaft dort, gilt eine eigene Liste als hinausgeteilt)
```

A published list shows one entry in `oc:invite` even after the share with the second account
was withdrawn: Nextcloud keeps the public link as an entry there. The entries are only counted
by the bundle, never kept.

### Subline of the provider for shared lists (D-32-17)

The same run, with the Tasks app 0.18.1: one task with a due date in an own list and one in a
list the second test account shares with the first; the search provider `tasks` asked with
the app password of the first account.

```
SUBLINE nc35 liste=eigen endet_mit_rohname=ja enthaelt_besitzer=nein bereinigt_moeglich=nein enthaelt_kennung=nein leer=nein owner_displayname_gleich_anzeigename=ja
SUBLINE nc35 liste=geteilt endet_mit_rohname=ja enthaelt_besitzer=ja bereinigt_moeglich=ja enthaelt_kennung=ja leer=nein owner_displayname_gleich_anzeigename=ja
SUBLINE nc32 liste=eigen endet_mit_rohname=nein enthaelt_besitzer=nein bereinigt_moeglich=nein enthaelt_kennung=nein leer=nein owner_displayname_gleich_anzeigename=ja
SUBLINE nc32 liste=geteilt endet_mit_rohname=nein enthaelt_besitzer=nein bereinigt_moeglich=nein enthaelt_kennung=nein leer=nein owner_displayname_gleich_anzeigename=ja
ENTSCHEID sublineregel=ersetzen (Begründung: auf nc35 endet die subline der geteilten Liste mit dem Rohnamen samt Besitzerzusatz, der Zusatz passt zu owner-displayname und ist nach dem Ersetzen weg; auf nc32 endet die subline nicht mit dem Rohnamen und enthält den Besitzer nicht, sie bleibt nach der Regel wie geliefert; die eigene Liste enthält auf beiden keinen Besitzer. Die Form entspricht der Regel der Planung, kein Anhalten nötig)
```

The display name of the second test account equals its account id on both instances, so on
Nextcloud 35 the raw subline also carries the id; after the replacement both are gone. The
live run found one more form on Nextcloud 35, see
[Gap closure 32-09](#gap-closure-32-09-on-nextcloud-35-and-32).

## Measurements before the modifying tools

Plans 33-01b and 33-01c, before any code of `tasks_complete`, `tasks_update` or `tasks_move`
existed. Owner release for the state changes on both standing instances:

```
FREIGABE zustand=option-a datum=2026-11-13 umfang=nc35+nc32 quelle=owner-antwort-checkpoint-33-01-task-3
```

Raw protocol:
[raw/33-01-messung.txt](../.planning/phases/33-aufgaben-aendern/raw/33-01-messung.txt).
Every run had a baseline per account before and after, equal on both instances; every test
object was dropped without trash bin.

### Behaviour of the Tasks app 0.18.1 (plan 33-01b, Nextcloud 35)

The Tasks app was installed for the run and removed afterwards; the steps ran in a browser on
a throwaway account, every state read under impersonation and compared line by line.

```
TASKSAPP nc35 vorher=keine
TASKSAPP nc35 messung=0.18.1
RUECKBAU nc35 tasksapp=wie-vorher vorher=keine nachher=keine
ENTSCHEID wiederoeffnen_kinder=bleiben quelle=M1 (D-33-05 bestätigt, kein Auslöser für 33-01c Task 4)
ENTSCHEID entfernen_due=zeile-weg quelle=M2
ENTSCHEID entfernen_start=zeile-weg quelle=M2
ENTSCHEID entfernen_description=leer quelle=M2 rohzeile=DESCRIPTION:
ENTSCHEID entfernen_parent=zeile-weg quelle=M2
ENTSCHEID entfernen_priority=zeile-weg quelle=M2 (wie D-33-07)
ENTSCHEID entfernen_tags=zeile-weg quelle=M2 (wie D-33-07)
ENTSCHEID pflegefelder_entfernen=DTSTAMP,LAST-MODIFIED
ENTSCHEID cancelled_kette=unberuehrt quelle=CANCELLED kette (wie D-33-14)
ENTSCHEID cancelled_direkt=abhaken-und-oeffnen abhaken=STATUS:COMPLETED,PERCENT-COMPLETE:100,COMPLETED(UTC) oeffnen=STATUS:NEEDS-ACTION,COMPLETED und PERCENT-COMPLETE entfernt pflegefelder=DTSTAMP,LAST-MODIFIED (wie D-33-14)
ABWEICHUNG D-33-05/D-33-07/D-33-14 keine
```

Reopening a parent leaves its done children done. A removed field goes as a whole line, only
the description stays as an empty `DESCRIPTION:`. A cancelled child stays untouched when its
parent is checked off; a cancelled task can be checked off and reopened, and reopening makes it
`NEEDS-ACTION`, not `CANCELLED` again. Side finding: two parallel writes of the app itself
failed with `SQLSTATE[HY000]: General error: 5 database is locked` (status 500) on SQLite.

### Cost of a chain of 50 descendants (M-3, D-33-10)

One `REPORT` plus 51 conditional writes under impersonation, descendants in post order and the
root last: `PUT` with `If-Match`, or `MOVE` with `Overwrite: F` and `If-Match` into a second
list. Five runs per row, depth 1 (all children of the root) and depth 3.

```
KETTE nc35 modus=put tiefe=1 min_ms=2037 median_ms=2080 max_ms=2164 laeufe=5
KETTE nc35 modus=put tiefe=3 min_ms=2051 median_ms=2074 max_ms=2199 laeufe=5
KETTE nc35 modus=move tiefe=1 min_ms=2063 median_ms=2095 max_ms=2173 laeufe=5
KETTE nc35 modus=move tiefe=3 min_ms=2077 median_ms=2103 max_ms=2466 laeufe=5
KETTE nc32 modus=put tiefe=1 min_ms=1935 median_ms=1947 max_ms=1964 laeufe=5
KETTE nc32 modus=put tiefe=3 min_ms=1920 median_ms=1961 max_ms=2454 laeufe=5
KETTE nc32 modus=move tiefe=1 min_ms=1961 median_ms=1991 max_ms=3688 laeufe=5
KETTE nc32 modus=move tiefe=3 min_ms=2016 median_ms=2043 max_ms=2135 laeufe=5
CAP chain_cap=50 max_gesamt_s=3.688 budget_s=8 regel=33-01c-task-1
MESSWERT kette_max_gesamt_s=3.688 quelle=KETTE nc32 modus=move tiefe=1 lauf=1 (über nc35 und nc32, beide Modi, beide Tiefen, je 5 Läufe; größter Wert auf nc35: 2.466 s, move tiefe=3)
MESSWERT chain_cap=50 regel=derive_budget(max_gesamt_s)<=30 budget_s=8 quelle=nc35+nc32 (D-33-10 bestätigt)
MESSWERT kette_antwort_ids=50 (gleich chain_cap)
```

Every write answered 204 (`PUT`) or 201 (`MOVE`). The rule was fixed before the measurement:
the cap of 50 stays if twice the slowest whole chain, rounded up, is at most 30 s, half of a
usual client wait of 60 s. The slowest chain took 3.688 s, the budget is 8 s, so the cap of 50
holds. Depth does not change the cost; a chain costs about 40 ms per write.

### ETag after a text the server altered (M-4)

```
ETAGFORM nc35 fall=ohne-prodid status=204 etag_im_kopf=nein text_gleich_gesendet=nein etag_gleich_get=-
ETAGFORM nc35 fall=lf status=204 etag_im_kopf=ja text_gleich_gesendet=ja etag_gleich_get=ja
ETAGFORM nc35 fall=uid-case status=204 etag_im_kopf=ja text_gleich_gesendet=ja etag_gleich_get=ja
ENTSCHEID etag_nach_veraendertem_text=fehlt quelle=ETAGFORM nc35 (fall=ohne-prodid: der Server ändert den Text beim Speichern, text_gleich_gesendet=nein, die Antwort 204 trägt keine ETag; fall=lf und fall=uid-case speichert er unverändert und antwortet mit ETag gleich GET)
```

When the server changes the text on storing it (here: a calendar without `PRODID`), the
accepted `PUT` answers without an ETag. A tool that needs the new ETag has to read the object
again; it must not assume one comes back.

## Not measured

- Nextcloud 33 and 34: only through the source, as in the spike of phase 30.
- The owner name with brackets of its own: covered by the unit tests of `owner_suffix_strip`,
  not by an instance, because changing the display name of a test account was not part of the
  owner release.
- Nothing fell away through the owner release: `FREIGABE zustand=option-a` covered nc35 and
  Nextcloud 32.
- The time budgets come from loopback requests on one host; a real network adds latency, which
  the floor of 1 s absorbs as stated in the lines above.
- Lists the account shares itself (plan 32-09): a share with a group was not measured, it was
  not part of the owner release (`HINAUS ... zustand=gruppe entfaellt`), so whether a group
  share shows in `oc:invite` is open. The subline was measured with a due date only; the form
  without one came up in the live run.
- Measurements before the modifying tools (plans 33-01b and 33-01c): nothing fell away through
  the owner release, `FREIGABE zustand=option-a` covered nc35 and Nextcloud 32. By plan, the
  behaviour of the Tasks app and the ETag after an altered text (M-4) were measured on
  Nextcloud 35 only; the cost of a chain on both. The chains ran on loopback, a real network
  adds latency per write, which the budget of 8 s against the limit of 30 s absorbs.
- Live proof of the modifying tools (plan 33-10): nothing fell away through the owner releases,
  both instances ran each without and with the Tasks app, and Nextcloud 35 over the whole
  chain. Not measured: the whole chain on Nextcloud 32 (local process at `manual_install`), a
  chain of more than three descendants live (the cap of 50 rests on the measurement of
  plan 33-01c and the unit tests), a cancelled descendant live (unit tests and plan 33-01b),
  a 403 of the server for a read only share (the server answered 404 to the harness, the tools
  refuse before any write), and a stale write through the chain other than `tasks_update`
  (the function level covers all three tools).

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


## Owner acceptance

Plan 32-08, Nextcloud 35.0.0 with the Tasks app 0.18.1, account alice. Both tasks were created
over the whole chain (OAuth, Caddy, HaRP, the ExApp image of plan 32-07, impersonation), the
subtask with `parent`, `due` 2026-11-20, `start` 2026-11-18, two tags and priority 3, without
`list`: the account holds one own writable list, `personal`, and the connector took it. The
owner then opened the Tasks app as alice together with Claude in Playwright, at three widths
in light and dark mode; the screenshots stay outside the repository.

```
TASKSAPP nc35 abnahme=0.18.1
BASELINE nc35 konto=alice calendars=1 objekte=31 geloescht=0 shares=0 abos=0 phase=vorher
KETTE eltern werkzeug=tasks_create nutzer=alice argumente={"summary": "p3208 Projekt Abnahme"} fehler=nein | {"confirmed": true, "created": true, "id": "task:personal:25f505ce-7330-41d7-91eb-999f753c539e.ics", "list": {"name": "personal", "shared": false, "writable": true}, "summary": "p3208 Projekt Abnahme"}
KETTE unteraufgabe werkzeug=tasks_create nutzer=alice argumente={"due": "2026-11-20", "parent": "task:personal:25f505ce-7330-41d7-91eb-999f753c539e.ics", "priority": 3, "start": "2026-11-18", "summary": "p3208 Teilschritt", "tags": ["abnahme", "p3208"]} fehler=nein | {"confirmed": true, "created": true, "due": "2026-11-20", "id": "task:personal:280e2532-3c76-4367-8e47-45d91f602ea5.ics", "list": {"name": "personal", "shared": false, "writable": true}, "start": "2026-11-18", "summary": "p3208 Teilschritt"}
KETTE lesen-unteraufgabe werkzeug=tasks_read nutzer=alice argumente={"task_id": "task:personal:280e2532-3c76-4367-8e47-45d91f602ea5.ics"} fehler=nein | {"due": "2026-11-20", "id": "task:personal:280e2532-3c76-4367-8e47-45d91f602ea5.ics", "list": {"name": "personal", "shared": false, "writable": true}, "parent": {"id": "task:personal:25f505ce-7330-41d7-91eb-999f753c539e.ics", "summary": "p3208 Projekt Abnahme"}, "priority": 3, "start": "2026-11-18", "status": "open", "subtasks": [], "summary": "p3208 Teilschritt", "tags": ["abnahme", "p3208"]}
ABNAHME owner=abgenommen datum=2026-11-13 | Tasks 0.18.1 auf nc35, alice, Liste personal: "p3208 Teilschritt" eingerückt unter "p3208 Projekt Abnahme"; "Beginnt am 18. November 2026" und "Fällig am 20. November 2026", ganztägig (kein Folgetag); Tags abnahme und p3208; "Priorität 3: hoch"; Screenshots außerhalb des Repos unter <scratch>/abnahme/ (hell-1440, hell-1024, hell-390, dunkel-1440, dunkel-1024, dunkel-390 .png)
```

**Result:** accepted. The Tasks app shows the subtask indented under its parent, due on
20 November 2026 as an all day date (not the day after), starting on 18 November 2026, with
both tags and as priority 3 ("hoch"), in the list `personal`. This is success criterion 3 seen
from the app, not only from the connector.

Removal followed section 7 of the phase rules: both objects deleted with
`X-NC-CalDAV-No-Trashbin: 1`, which again left them in the trash bin (two entries, the same
finding as in plan 32-07), so the trash bin was emptied with a DAV `DELETE` per entry, and the
Tasks app was removed with its config keys:

```
BASELINE nc35 konto=alice calendars=1 objekte=33 geloescht=2 shares=0 abos=0 phase=geloescht
BASELINE nc35 konto=alice calendars=1 objekte=31 geloescht=0 shares=0 abos=0 phase=nachher
BASELINE-VERGLEICH nc35 konto=alice gleich=ja
RUECKBAU nc35 tasksapp=wie-vorher vorher=keine nachher=keine
TASKSAPP nc35 nachher=keine
```

## CI run

One run of the workflow `CI` on commit `dcda6c8`, pushed after the owner release
`FREIGABE push=ja` (fast forward, no force); the security scans ran on the same commit. The job
`exapp` holds the case without the Tasks app (Nextcloud 34.0.3, the step "Tasks bundle live
without the Tasks app"), the job `canary-nc35` the case with it (Nextcloud 35.0.1, the steps
"Install the Tasks app and restart Nextcloud" and "Tasks bundle live with the Tasks app"). Both
jobs kept every step they had before this phase and stayed green, so the bootstrap change of
plan 32-01 did not alter the setup on 34 and 35.

```
CI lauf=43453276557 workflow=CI commit=dcda6c8590a209fba6f84e6854f7e7bc80bfc159 status=completed ergebnis=success
CI job=exapp ergebnis=success lauf=43453276557
CI job=integration ergebnis=success lauf=43453276557
CI job=canary-nc35 ergebnis=success lauf=43453276557
CI job=image ergebnis=success lauf=43453276557
CI job=unit ergebnis=success lauf=43453276557
CI lauf=43453276506 workflow=Security-scans commit=dcda6c8590a209fba6f84e6854f7e7bc80bfc159 ergebnis=success
CI job=REUSE licensing lint ergebnis=success lauf=43453276506
CI job=pip-audit over the locked set ergebnis=success lauf=43453276506
CI job=CodeQL (python) ergebnis=success lauf=43453276506
exapp | Tasks bundle live without the Tasks app (TASK-03, D-32-11) | LAUF aufgaben32 stempel=de322cbe kopf=p32live-de322cbe container=nc-mcp-exapp-nc
exapp | Tasks bundle live without the Tasks app (TASK-03, D-32-11) | VERSION nc=34.0.3.2 versionstring=34.0.3 (occ status)
exapp | Tasks bundle live without the Tasks app (TASK-03, D-32-11) | TASKSAPP erwartet=0 occ_app_list=keine passt=ja
exapp | Tasks bundle live without the Tasks app (TASK-03, D-32-11) | BASELINE nc34.0.3.2 konto=alice calendars=1 objekte=0 geloescht=0 shares=0 abos=0 phase=vorher
exapp | Tasks bundle live without the Tasks app (TASK-03, D-32-11) | BASELINE nc34.0.3.2 konto=alice calendars=1 objekte=0 geloescht=0 shares=0 abos=0 phase=nachher gleich=ja
exapp | Tasks bundle live without the Tasks app (TASK-03, D-32-11) | 17 passed, 1 warning in 16.63s
canary-nc35 | Install the Tasks app and restart Nextcloud (D-32-11) |   - tasks: 0.18.1
canary-nc35 | Tasks bundle live with the Tasks app (TASK-09, D-32-11) | LAUF aufgaben32 stempel=c257a8b9 kopf=p32live-c257a8b9 container=nc-mcp-exapp-nc
canary-nc35 | Tasks bundle live with the Tasks app (TASK-09, D-32-11) | VERSION nc=35.0.1.1 versionstring=35.0.1 (occ status)
canary-nc35 | Tasks bundle live with the Tasks app (TASK-09, D-32-11) | TASKSAPP erwartet=1 occ_app_list=0.18.1 passt=ja
canary-nc35 | Tasks bundle live with the Tasks app (TASK-09, D-32-11) | BASELINE nc35.0.1.1 konto=alice calendars=1 objekte=0 geloescht=0 shares=0 abos=0 phase=vorher
canary-nc35 | Tasks bundle live with the Tasks app (TASK-09, D-32-11) | BASELINE nc35.0.1.1 konto=alice calendars=1 objekte=0 geloescht=0 shares=0 abos=0 phase=nachher gleich=ja
canary-nc35 | Tasks bundle live with the Tasks app (TASK-09, D-32-11) | 17 passed, 1 warning in 19.34s
```

Run: https://github.com/street1983nk/nextcloud-mcp-connector/actions/runs/43453276557 (CI) and
https://github.com/street1983nk/nextcloud-mcp-connector/actions/runs/43453276506 (security
scans). Lines are filtered from the log of the three new steps only; the timestamps are cut
and no environment line is kept.

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

## Gap closure 32-09 on Nextcloud 35 and 32

Plan 32-09 closed the warnings of the first verification of phase 32. Two of them changed
behaviour and were proven live, at function level under AppAPI impersonation, with
`tests/integration/test_tasks_live.py` on Nextcloud 35.0.0 and 32.0.15, each without and with
the Tasks app 0.18.1, one instance at a time, a baseline before and after for every account:

- **D-32-17:** `unified_search` and `search` give a hit of the provider `tasks` from a shared
  list without the owner. The raw subline is read first with the app password (positive
  control: on Nextcloud 35 it names the owner), then the same task through the connector.
- **D-32-18:** an account with exactly one own task list. Private, `tasks_create` without
  `list` writes there (positive control); shared with the second test account or published by
  link, it refuses without a `PUT`, also for a `parent` in that list; named, it writes;
  withdrawn, it writes again without `list`. "Nothing written" is checked with the rows of
  `calendarobjects` read by PHP in the container.

The live run found a second form of the subline on Nextcloud 35: a task without a due date
has the bare `(<list name> (<owner>))`, with no leading space. The first run therefore dropped
that subline (no name left the connector, but the line was lost); a unit test and a fix
followed, and the case with a due date was added so both forms are proven. The raw protocols
keep the earlier runs:
[raw/32-09-nc35.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-nc35.txt),
[raw/32-09-nc32.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-09-nc32.txt).

Nextcloud 35 with the Tasks app:

```
AUFGABE d-32-17-geteilt nc=35.0.0.10 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207 ergebnis=ok | the provider finds the task of the rw share; roh_mit_besitzer=ja; positive control: the raw subline names the owner on 34+; subline_vorhanden=ja text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; bereinigt='(p32live-ec5b284e-rw)'; the subline ends with the list name without the owner; search text equals the subline
AUFGABE d-32-17-geteilt-faellig nc=35.0.0.10 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:500,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207 ergebnis=ok | the provider finds the task of the rw share; roh_mit_besitzer=ja; positive control: the raw subline names the owner on 34+; subline_vorhanden=ja text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; bereinigt='Fällig am 04.12.2026 (p32live-ec5b284e-rw)'; the subline ends with the list name without the owner; search text equals the subline
AUFGABE d-32-17-eigen nc=35.0.0.10 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200 ergebnis=ok | the subline is the raw one; search text equals the raw subline
AUFGABE d-32-18-privat nc=35.0.0.10 nutzer=p32liveec5b284eaus status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | PUT [201]; calendarobjects vorher=0 nachher=1; raw object GET 200 with the password of the account; list {'name': 'p32live-ec5b284e-aus', 'shared': False, 'writable': True}
AUFGABE d-32-18-geteilt nc=35.0.0.10 nutzer=p32liveec5b284eaus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-ec5b284e-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-ec5b284e-aus.'; the hook saw no PUT; calendarobjects vorher=0 nachher=0; neither the id nor the display name of bob; no share marker
AUFGABE d-32-18-mit-list nc=35.0.0.10 nutzer=p32liveec5b284eaus status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | PUT [201]; calendarobjects vorher=0 nachher=1; raw object GET 200 with the password of the account; list {'name': 'p32live-ec5b284e-aus', 'shared': False, 'writable': True}
AUFGABE d-32-18-parent nc=35.0.0.10 nutzer=p32liveec5b284eaus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message='The parent task lives in a list that is shared with others, and such a list is only written to when it is named.'; shared with others in the message; hint "To create the subtask there, name that list with list='p32live-ec5b284e-aus'."; the hook saw no PUT; calendarobjects vorher=1 nachher=1; neither the id nor the display name of bob; no share marker
AUFGABE d-32-18-link nc=35.0.0.10 nutzer=p32liveec5b284eaus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-ec5b284e-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-ec5b284e-aus.'; the hook saw no PUT; calendarobjects vorher=1 nachher=1; neither the id nor the display name of bob; no share marker
AUFGABE d-32-18-zurueckgenommen nc=35.0.0.10 nutzer=p32liveec5b284eaus status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | PUT [201]; calendarobjects vorher=1 nachher=2; raw object GET 200 with the password of the account; list {'name': 'p32live-ec5b284e-aus', 'shared': False, 'writable': True}
AUFGABE keine-kennung nc=35.0.0.10 nutzer=alice status=keine ergebnis=ok | 35 answers scanned for the id and the display name of bob; answers kept: 35; found 0 of 2 names; no _shared_by_ in any answer
BASELINE nc35.0.0.10 konto=p32liveec5b284eaus calendars=0 objekte=0 geloescht=0 shares=0 abos=0 phase=nachher gleich=ja
```

Nextcloud 35 without the Tasks app:

```
TASKSAPP erwartet=0 occ_app_list=keine passt=ja
AUFGABE d-32-18-geteilt nc=35.0.0.10 nutzer=p32live3ac5b8a4aus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-3ac5b8a4-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-3ac5b8a4-aus.'; the hook saw no PUT; calendarobjects vorher=0 nachher=0; neither the id nor the display name of bob; no share marker
AUFGABE d-32-17-geteilt nc=35.0.0.10 nutzer=alice status=keine ergebnis=entfaellt | without the Tasks app the provider tasks does not exist
21 passed in 30.24s
```

Nextcloud 32 with the Tasks app (its subline carries the due date only and no owner, so it
passes as delivered):

```
AUFGABE d-32-17-geteilt nc=32.0.15.1 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200 ergebnis=ok | the provider finds the task of the rw share; roh_mit_besitzer=nein; subline_vorhanden=nein text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; without an owner the subline is the raw one; search text equals the subline
AUFGABE d-32-17-geteilt-faellig nc=32.0.15.1 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207 ergebnis=ok | the provider finds the task of the rw share; roh_mit_besitzer=nein; subline_vorhanden=ja text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; without an owner the subline is the raw one; search text equals the subline
AUFGABE d-32-17-eigen nc=32.0.15.1 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200 ergebnis=ok | the subline is the raw one; search text equals the raw subline
AUFGABE d-32-18-geteilt nc=32.0.15.1 nutzer=p32live7c9842bfaus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-7c9842bf-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-7c9842bf-aus.'; the hook saw no PUT; calendarobjects vorher=0 nachher=0; neither the id nor the display name of bob; no share marker
AUFGABE d-32-18-link nc=32.0.15.1 nutzer=p32live7c9842bfaus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-7c9842bf-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-7c9842bf-aus.'; the hook saw no PUT; calendarobjects vorher=1 nachher=1; neither the id nor the display name of bob; no share marker
AUFGABE keine-kennung nc=32.0.15.1 nutzer=alice status=keine ergebnis=ok | 35 answers scanned for the id and the display name of bob; answers kept: 35; found 0 of 2 names; no _shared_by_ in any answer
```

Nextcloud 32 without the Tasks app:

```
TASKSAPP erwartet=0 occ_app_list=keine passt=ja
AUFGABE d-32-18-geteilt nc=32.0.15.1 nutzer=p32livea4ff82e2aus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-a4ff82e2-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-a4ff82e2-aus.'; the hook saw no PUT; calendarobjects vorher=0 nachher=0; neither the id nor the display name of bob; no share marker
21 passed in 30.75s
```

On both instances every baseline was equal before and after, the calendar trash bin of every
account was emptied of the run (the one entry of the test account is the object deleted after
the positive control), the test account was deleted and the Tasks app was removed again.

## Gap closure 32-10 on Nextcloud 35 and 32

Plan 32-10 answered the open points of the re-verification of phase 32: a list shared with a
group (out of the account and into it), a recurring task live, the cap of 500 live with the
budget of one list, and an owner whose display name differs from the account id. First
measured with `scripts/tasks_measure.py` (steps `gruppe`, `wieder`, `deckel`, [raw/32-10-messung.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-10-messung.txt)), then
proven with `tests/integration/test_tasks_live.py` on Nextcloud 35.0.0 and 32.0.15, each
without and with the Tasks app 0.18.1, one instance at a time, at function level under AppAPI
impersonation, a baseline before and after for every account ([raw/32-10-nc35.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-10-nc35.txt), [raw/32-10-nc32.txt](../.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-10-nc32.txt)). Every run
used a test group `p32live<stamp>grp` with bob and alice as members; it did not exist before
and was deleted after every run.

```
34 passed in 71.06s (0:01:11)
34 passed in 86.41s (0:01:26)
34 passed in 71.00s (0:01:11)
34 passed in 78.61s (0:01:18)
```

### Group shares (D-32-18, D-32-14, D-32-15, D-32-17, E4)

The measurement: on both instances, under the app password and under impersonation,
`oc:invite` of an own list shared with a group holds exactly one `oc:user` entry whose href
names `principals/groups/`. The unchanged `parse_task_home` marks it `shared_out` for read only
and read-write and clears the mark once the share is taken back. A list bob shared with a
group that holds alice looks to alice like a share with a person: `_shared_by_` in the URI,
`oc:read-only` in the 2xx propstat, `owner-displayname` equal to the display name of bob. No
code changed for groups; the measured discovery is pinned as
`tests/fixtures/caldav_home_group_share.xml`, with regression tests such as
`test_an_own_list_shared_with_a_group_is_shared_out` and
`test_the_only_own_list_shared_with_a_group_is_no_default_target`.

```
GRUPPE nc35 name=p3210grp vorhanden=nein shares=0 phase=vorher
GRUPPE-HINAUS nc35 zustand=privat auth=appapi invite_status=2xx eintraege=0 kinder=keine principal_art=keine shared_out=nein
GRUPPE-HINAUS nc35 zustand=an-gruppe-ro auth=appapi invite_status=2xx eintraege=1 kinder=user principal_art=groups shared_out=ja
GRUPPE-HINAUS nc35 zustand=an-gruppe-rw auth=appapi invite_status=2xx eintraege=1 kinder=user principal_art=groups shared_out=ja
GRUPPE-HINAUS nc35 zustand=zurueckgenommen auth=appapi invite_status=2xx eintraege=0 kinder=keine principal_art=keine shared_out=nein
GRUPPE-HINAUS nc32 zustand=an-gruppe-ro auth=appapi invite_status=2xx eintraege=1 kinder=user principal_art=groups shared_out=ja
GRUPPE-HINAUS nc32 zustand=an-gruppe-rw auth=appapi invite_status=2xx eintraege=1 kinder=user principal_art=groups shared_out=ja
GRUPPE-SELBST nc35 zustand=an-gruppe-ro auth=appapi eigene_liste_doppelt=nein
GRUPPE-REIN nc35 liste=rw auth=appapi sichtbar=ja eintraege=1 uri_mit_marker=ja read_only_2xx=ja owner_displayname_passt=ja shared=ja writable=ja name_ohne_besitzer=ja
GRUPPE-REIN nc35 liste=ro auth=appapi sichtbar=ja eintraege=1 uri_mit_marker=ja read_only_2xx=ja owner_displayname_passt=ja shared=ja writable=nein name_ohne_besitzer=ja
GRUPPE-REIN nc32 liste=rw auth=appapi sichtbar=ja eintraege=1 uri_mit_marker=ja read_only_2xx=ja owner_displayname_passt=ja shared=ja writable=ja name_ohne_besitzer=ja
GRUPPE-REIN nc32 liste=ro auth=appapi sichtbar=ja eintraege=1 uri_mit_marker=ja read_only_2xx=ja owner_displayname_passt=ja shared=ja writable=nein name_ohne_besitzer=ja
GRUPPE-SUBLINE nc35 liste=rw faellig=nein endet_mit_rohname=ja enthaelt_besitzer=ja clean_subline=bereinigt clean_subline_ohne_besitzer=ja
GRUPPE-SUBLINE nc35 liste=rw faellig=ja endet_mit_rohname=ja enthaelt_besitzer=ja clean_subline=bereinigt clean_subline_ohne_besitzer=ja
GRUPPE-SUBLINE nc32 liste=rw faellig=nein endet_mit_rohname=nein enthaelt_besitzer=nein clean_subline=unveraendert clean_subline_ohne_besitzer=ja
GRUPPE-SUBLINE nc32 liste=rw faellig=ja endet_mit_rohname=nein enthaelt_besitzer=nein clean_subline=unveraendert clean_subline_ohne_besitzer=ja
GRUPPE nc35 name=p3210grp vorhanden=nein shares=0 phase=nachher
GRUPPE nc32 name=p3210grp vorhanden=nein shares=0 phase=nachher
ENTSCHEID gruppe_hinaus=erkannt (Begründung: auf nc35 und nc32, unter App-Passwort und Impersonation gleich, trägt oc:invite einer an die Gruppe geteilten eigenen Liste genau ein Kind-Element mit dem lokalen Namen user und einem href auf principals/groups/; die unveränderte parse_task_home liefert für an-gruppe-ro und an-gruppe-rw shared_out=ja, für privat und zurueckgenommen nein; _shares_itself bleibt unverändert)
ENTSCHEID gruppe_rein=geteilt-erkannt (Begründung: auf nc35 und nc32 trägt die per Gruppe hineingeteilte Liste den Marker _shared_by_ in der URI und oc:read-only im 2xx-propstat; parse_task_home liefert shared=ja, writable=ja für rw und nein für ro, den Namen ohne Besitzer; owner-displayname passt zum Anzeigenamen von bob)
ENTSCHEID gruppe_subline=bereinigt (Begründung: auf nc35 enthält die rohe subline aller vier Aufgaben den Besitzer, clean_subline ersetzt ihn mit und ohne DUE; auf nc32 enthält sie ihn nicht und bleibt unverändert; in keinem Fall bleibt der Besitzer stehen)
```

Live on Nextcloud 35 with the Tasks app. The account of D-32-18 shares its only own list with
the group (it is no member itself): without `list` nothing is written, also not for a `parent`
there; taken back, it is written again. As alice, the two group shares of bob carry their name
without the owner and the right `writable`; they are written only when named, the read only
one is refused before any `PUT`, a `parent` there is no naming, `fetch` links the start page of
the Tasks app only, and the provider subline loses the owner with and without a due date:

```
AUFGABE d-32-18-gruppe-privat nc=35.0.0.10 nutzer=p32live5f3e61c4aus status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | PUT [201]; calendarobjects vorher=2 nachher=3; raw object GET 200 with the password of the account; list {'name': 'p32live-5f3e61c4-aus', 'shared': False, 'writable': True}
AUFGABE d-32-18-gruppe-ro nc=35.0.0.10 nutzer=p32live5f3e61c4aus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-5f3e61c4-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-5f3e61c4-aus.'; the hook saw no PUT; calendarobjects vorher=3 nachher=3; neither the id nor the display name of bob; no share marker; no group id
AUFGABE d-32-18-gruppe-rw nc=35.0.0.10 nutzer=p32live5f3e61c4aus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-5f3e61c4-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-5f3e61c4-aus.'; the hook saw no PUT; calendarobjects vorher=3 nachher=3; neither the id nor the display name of bob; no share marker; no group id
AUFGABE d-32-18-gruppe-parent nc=35.0.0.10 nutzer=p32live5f3e61c4aus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message='The parent task lives in a list that is shared with others, and such a list is only written to when it is named.'; shared with others in the message; hint "To create the subtask there, name that list with list='p32live-5f3e61c4-aus'."; the hook saw no PUT; calendarobjects vorher=3 nachher=3; neither the id nor the display name of bob; no share marker; no group id
AUFGABE d-32-18-gruppe-zurueck nc=35.0.0.10 nutzer=p32live5f3e61c4aus status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | PUT [201]; calendarobjects vorher=3 nachher=4; raw object GET 200 with the password of the account; list {'name': 'p32live-5f3e61c4-aus', 'shared': False, 'writable': True}
AUFGABE gruppe-rein-flags nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | roher displayname mit zusatz in der discovery: 2 von 2; positive control: the server adds the owner to both; grw: {'name': 'p32live-5f3e61c4-grw', 'shared': True, 'writable': True}; gro: {'name': 'p32live-5f3e61c4-gro', 'shared': True, 'writable': False}; the task of grw is a hit; the task of gro is a hit; no group id in the answer
AUFGABE gruppe-rein-ohne-list nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=unspecified message='This account has more than one task list to write to, so list has to be named.'; hint offers the rw group share: 'Name the list with list=<name>. Writable task lists: p32live-5f3e61c4-a, p32live-5f3e61c4-b, p32live-5f3e61c4-grw (shared, key s6c34d4418e76d6a3), p32live-5f3e61c4-rw (shared, key scf5c72498ae63223), personal.'; the read only group share is not offered; the hook saw no PUT; calendarobjects vorher={'grw': 2, 'gro': 1} nachher={'grw': 2, 'gro': 1}; neither the id nor the display name of bob; no group, no marker
AUFGABE gruppe-rein-rw-mit-list nc=35.0.0.10 nutzer=alice status=PROPFIND:207,PUT:201,GET:200 ergebnis=ok | the id carries the hashed key: True; GET by the owner 200; calendarobjects vorher=2 nachher=3; PUT [201]; list {'name': 'p32live-5f3e61c4-grw', 'shared': True, 'writable': True}
AUFGABE gruppe-rein-ro-vorab nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The task list 'p32live-5f3e61c4-gro' is read only for this account."; The task list 'p32live-5f3e61c4-gro' is read only for this account.; the hook saw no PUT; calendarobjects vorher=1 nachher=1; no group id
AUFGABE gruppe-rein-parent nc=35.0.0.10 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message='The parent task lives in a shared list, and a shared list is only written to when it is named.'; hint "To create the subtask there, name that list with list='p32live-5f3e61c4-grw'."; no PUT; calendarobjects vorher=3 nachher=3
AUFGABE gruppe-rein-fetch nc=35.0.0.10 nutzer=alice status=PROPFIND:207,GET:200,REPORT:207 ergebnis=ok | url='/index.php/apps/tasks/'; the link is the start page of the Tasks app; no owner in the link; metadata shared=true; title p32live-5f3e61c4-gruppeohne
AUFGABE d-32-17-gruppe nc=35.0.0.10 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207 ergebnis=ok | the provider finds the task of the grw share; roh_mit_besitzer=ja; positive control: the raw subline names the owner on 34+; subline_vorhanden=ja text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; bereinigt='(p32live-5f3e61c4-grw)'; the subline ends with the list name without the owner; search text equals the subline
AUFGABE d-32-17-gruppe-faellig nc=35.0.0.10 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207 ergebnis=ok | the provider finds the task of the grw share; roh_mit_besitzer=ja; positive control: the raw subline names the owner on 34+; subline_vorhanden=ja text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; bereinigt='Fällig am 04.12.2026 (p32live-5f3e61c4-grw)'; the subline ends with the list name without the owner; search text equals the subline
GRUPPE nc35.0.0.10 name=p32live5f3e61c4grp vorhanden=nein shares=0 phase=nachher
```

Nextcloud 32 with the Tasks app (its subline carries no owner and passes as delivered):

```
AUFGABE d-32-18-gruppe-ro nc=32.0.15.1 nutzer=p32livec408b127aus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-c408b127-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-c408b127-aus.'; the hook saw no PUT; calendarobjects vorher=3 nachher=3; neither the id nor the display name of bob; no share marker; no group id
AUFGABE d-32-18-gruppe-rw nc=32.0.15.1 nutzer=p32livec408b127aus status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The only own task list to write to, 'p32live-c408b127-aus', is shared with others, and a list others can see is only written to when it is named."; shared with others in the message; hint 'Name the list with list=<name>. Writable task lists: p32live-c408b127-aus.'; the hook saw no PUT; calendarobjects vorher=3 nachher=3; neither the id nor the display name of bob; no share marker; no group id
AUFGABE gruppe-rein-flags nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207,REPORT:207 ergebnis=ok | roher displayname mit zusatz in der discovery: 2 von 2; positive control: the server adds the owner to both; grw: {'name': 'p32live-c408b127-grw', 'shared': True, 'writable': True}; gro: {'name': 'p32live-c408b127-gro', 'shared': True, 'writable': False}; the task of grw is a hit; the task of gro is a hit; no group id in the answer
AUFGABE gruppe-rein-ro-vorab nc=32.0.15.1 nutzer=alice status=PROPFIND:207 ergebnis=ok | ToolError reason=guard_tripped message="The task list 'p32live-c408b127-gro' is read only for this account."; The task list 'p32live-c408b127-gro' is read only for this account.; the hook saw no PUT; calendarobjects vorher=1 nachher=1; no group id
AUFGABE d-32-17-gruppe nc=32.0.15.1 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:500,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200 ergebnis=ok | the provider finds the task of the grw share; roh_mit_besitzer=nein; subline_vorhanden=nein text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; without an owner the subline is the raw one; search text equals the subline
AUFGABE d-32-17-gruppe-faellig nc=32.0.15.1 nutzer=alice status=ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:500,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207,ocs.GET:200,systemtags.PROPFIND:207,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,ocs.GET:200,PROPFIND:207 ergebnis=ok | the provider finds the task of the grw share; roh_mit_besitzer=nein; subline_vorhanden=ja text_gleich=True; subline without bob; subline without the share marker; text without bob; text without the share marker; without an owner the subline is the raw one; search text equals the subline
GRUPPE nc32.0.15.1 name=p32livec408b127grp vorhanden=nein shares=0 phase=nachher
```

### Recurring tasks (TASK-02)

Three forms in one own list, built from the form the Tasks app writes (`DUE` and
`RRULE:FREQ=DAILY` on the master): unchanged (`app`), with a completed override of the second
occurrence in the same object (`instanz-erledigt`), and with the master completed
(`master-erledigt`). The server prefilter keeps an object as long as one of its VTODOs has no
`COMPLETED`, so the first two stay open; each form is one hit without expansion with
`recurring: true`, and the status is the one of the master. Regression tests:
`test_a_recurring_task_with_a_completed_instance_stays_one_open_hit` and
`test_a_recurring_task_with_a_completed_master_is_one_completed_hit`.

```
WIEDER nc35 form=app filter_offen=ja treffer_offen=1 treffer_erledigt=0 treffer_alle=1 recurring=ja status=open lesen_recurring=ja lesen_status=open
WIEDER nc35 form=instanz-erledigt filter_offen=ja treffer_offen=1 treffer_erledigt=0 treffer_alle=1 recurring=ja status=open lesen_recurring=ja lesen_status=open
WIEDER nc35 form=master-erledigt filter_offen=nein treffer_offen=0 treffer_erledigt=1 treffer_alle=1 recurring=ja status=completed lesen_recurring=ja lesen_status=completed
WIEDER nc32 form=app filter_offen=ja treffer_offen=1 treffer_erledigt=0 treffer_alle=1 recurring=ja status=open lesen_recurring=ja lesen_status=open
WIEDER nc32 form=instanz-erledigt filter_offen=ja treffer_offen=1 treffer_erledigt=0 treffer_alle=1 recurring=ja status=open lesen_recurring=ja lesen_status=open
WIEDER nc32 form=master-erledigt filter_offen=nein treffer_offen=0 treffer_erledigt=1 treffer_alle=1 recurring=ja status=completed lesen_recurring=ja lesen_status=completed
ENTSCHEID wiederkehrend=wie-erwartet (Begründung: auf nc35 und nc32 gleich: app und instanz-erledigt passieren den Vorfilter des Servers und sind je ein Treffer in open und all, keiner in completed, Status open, recurring=ja, tasks_read recurring=ja; master-erledigt fällt aus dem Vorfilter, ist keiner in open und je einer in completed und all, Status completed, recurring=ja)
```

Live, Nextcloud 35 with and Nextcloud 32 without the Tasks app:

```
AUFGABE wiederkehrend-app nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207 ergebnis=ok | treffer_open=1 treffer_completed=0 treffer_all=1; open: 1; done: 0; all: one hit without expansion, 1; the hit is the object of the harness; recurring True; status open; lesen status=open recurring=True; tasks_read recurring=true; tasks_read status open; the master and not the override; DUE as written 2026-11-20T13:00:00+00:00
AUFGABE wiederkehrend-instanz-erledigt nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207 ergebnis=ok | treffer_open=1 treffer_completed=0 treffer_all=1; open: 1; done: 0; all: one hit without expansion, 1; the hit is the object of the harness; recurring True; status open; lesen status=open recurring=True; tasks_read recurring=true; tasks_read status open; the master and not the override; DUE as written 2026-11-20T13:00:00+00:00
AUFGABE wiederkehrend-master-erledigt nc=35.0.0.10 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207 ergebnis=ok | treffer_open=0 treffer_completed=1 treffer_all=1; open: 0; done: 1; all: one hit without expansion, 1; the hit is the object of the harness; recurring True; status completed; lesen status=completed recurring=True; tasks_read recurring=true; tasks_read status completed; the master and not the override; DUE as written 2026-11-20T13:00:00+00:00
AUFGABE wiederkehrend-app nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207 ergebnis=ok | treffer_open=1 treffer_completed=0 treffer_all=1; open: 1; done: 0; all: one hit without expansion, 1; the hit is the object of the harness; recurring True; status open; lesen status=open recurring=True; tasks_read recurring=true; tasks_read status open; the master and not the override; DUE as written 2026-11-20T13:00:00+00:00
AUFGABE wiederkehrend-instanz-erledigt nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207 ergebnis=ok | treffer_open=1 treffer_completed=0 treffer_all=1; open: 1; done: 0; all: one hit without expansion, 1; the hit is the object of the harness; recurring True; status open; lesen status=open recurring=True; tasks_read recurring=true; tasks_read status open; the master and not the override; DUE as written 2026-11-20T13:00:00+00:00
AUFGABE wiederkehrend-master-erledigt nc=32.0.15.1 nutzer=alice status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,GET:200,REPORT:207 ergebnis=ok | treffer_open=0 treffer_completed=1 treffer_all=1; open: 0; done: 1; all: one hit without expansion, 1; the hit is the object of the harness; recurring True; status completed; lesen status=completed recurring=True; tasks_read recurring=true; tasks_read status completed; the master and not the override; DUE as written 2026-11-20T13:00:00+00:00
```

How the Tasks app itself checks off one occurrence needs a browser and was not measured.

### Cap of 500 and the budget per list

One own list with 600, then 2000 open tasks. The cap held: 20 pages of 25, 500 distinct hits,
the last page `truncated` with the note and without `next`. The budget did not: with 2000
open tasks a whole call (discovery, `REPORT` and parsing) took up to 0.831 s, and on
Nextcloud 35 the budget of 1 s cut the first page off, so the call was refused. The rule of
plan 32-02, `max(1, ceil(2 * max))`, gives 2 s. RED first
(`test_limit_policy_constants_are_the_measured_values` expecting 2, commit ed22627), then
`PER_LIST_TIMEOUT = 2.0` with its measuring line (commit 0f98fd4). The calls of the measurement
ran with a budget of 60 s, so the budget could not cut them short; the walk through the pages
ran with the budget of the product.

```
AUFBAU nc35 aufgaben=2000 neu=1400 erledigt=0 mit_faelligkeit=1000 dauer_s=63 gleichzeitig=1 wiederholte_put=0 GEGENPROBE datenbank_zeilen=2000 gleich=ja
KOSTEN deckel-report aufgaben=600 impersonation=ja status=207 median_ms=70 max_ms=84 min_ms=67 p95_zweitgroesster_ms=79 bytes=424754 treffer=600 (n=15)
KOSTEN deckel-aufruf aufgaben=600 median_ms=265 max_ms=277 beantwortet=ja budget_waehrend_messung_s=60 (n=10)
KOSTEN deckel-report aufgaben=2000 impersonation=ja status=207 median_ms=177 max_ms=220 min_ms=166 p95_zweitgroesster_ms=208 bytes=1415254 treffer=2000 (n=15)
KOSTEN deckel-aufruf aufgaben=2000 median_ms=754 max_ms=819 beantwortet=ja budget_waehrend_messung_s=60 (n=10)
KOSTEN deckel-report aufgaben=600 impersonation=ja status=207 median_ms=68 max_ms=77 min_ms=64 p95_zweitgroesster_ms=70 bytes=424754 treffer=600 (n=15)
KOSTEN deckel-aufruf aufgaben=600 median_ms=250 max_ms=259 beantwortet=ja budget_waehrend_messung_s=60 (n=10)
KOSTEN deckel-report aufgaben=2000 impersonation=ja status=207 median_ms=170 max_ms=176 min_ms=160 p95_zweitgroesster_ms=175 bytes=1415254 treffer=2000 (n=15)
KOSTEN deckel-aufruf aufgaben=2000 median_ms=722 max_ms=831 beantwortet=ja budget_waehrend_messung_s=60 (n=10)
DECKEL nc35 aufgaben=600 seiten=20 je_seite=25 treffer=500 eindeutig=500 letzte_note=ja letzte_next=nein note_gleich=ja degraded=nein max_seite_ms=310 median_seite_ms=270 budget_s=1
DECKEL nc35 aufgaben=2000 seiten=0 je_seite=0 treffer=0 eindeutig=0 letzte_note=nein letzte_next=nein note_gleich=nein degraded=ja max_seite_ms=1056 median_seite_ms=1056 budget_s=1
DECKEL nc32 aufgaben=600 seiten=20 je_seite=25 treffer=500 eindeutig=500 letzte_note=ja letzte_next=nein note_gleich=ja degraded=nein max_seite_ms=316 median_seite_ms=256 budget_s=1
DECKEL nc32 aufgaben=2000 seiten=20 je_seite=25 treffer=500 eindeutig=500 letzte_note=ja letzte_next=nein note_gleich=ja degraded=nein max_seite_ms=814 median_seite_ms=707 budget_s=1
MESSWERT per_list_timeout_s=2 max_s=0.819 quelle=nc35-impersonation
MESSWERT per_list_timeout_s=2 max_s=0.831 quelle=nc32-impersonation
ENTSCHEID deckel_budget=anheben-auf-2 (Begründung: größtes max von deckel-aufruf 0.831 s auf nc32 und 0.819 s auf nc35 bei 2000 offenen Aufgaben, Regel max(1,ceil(2*max)) ergibt 2; auf nc35 brach das bisherige Budget von 1 s den Deckel bei 2000 offenen Aufgaben live ab; max_s liegt unter der Abbruchgrenze von 5 s; der Deckel selbst hielt bei 600 auf beiden und bei 2000 auf nc32: 20 Seiten zu 25, 500 eindeutige Treffer, letzte Seite mit Notiz und ohne next)
```

Live with 520 open tasks in one list of bob, after the fix (budget 2 s), as bob under
impersonation:

```
SETUP deckel-500 aufgaben=520 fehlgeschlagen=0 wiederholt=0 dauer_s=25 GEGENPROBE datenbank_zeilen=520 gleich=ja
AUFGABE deckel-500 nc=35.0.0.10 nutzer=bob status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207 ergebnis=ok | seiten=20 je_seite=[25] treffer=500 eindeutig=500 letzte_truncated=True letzte_next=False max_seite_ms=203 median_seite_ms=193 budget_s=2; 20 pages, got 20; pages of 25: [25]; 500 distinct hits; last page truncated; no next on the last page; note 'result window capped at 500 tasks; narrow with query, list or due_by'; no degraded list
AUFGABE deckel-500 nc=32.0.15.1 nutzer=bob status=PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207,PROPFIND:207,REPORT:207 ergebnis=ok | seiten=20 je_seite=[25] treffer=500 eindeutig=500 letzte_truncated=True letzte_next=False max_seite_ms=197 median_seite_ms=186 budget_s=2; 20 pages, got 20; pages of 25: [25]; 500 distinct hits; last page truncated; no next on the last page; note 'result window capped at 500 tasks; narrow with query, list or due_by'; no degraded list
```

### Owner with a display name other than the account id

In the runs with the Tasks app the display name of bob was set to a name with an umlaut and
brackets of its own (`occ user:setting <bob> settings display_name`, read back with
`occ user:info`) and put back before the closing baseline; the runs without the Tasks app left
it alone. The name rule of D-32-14 and `clean_subline` held with it, and the scan for the owner
over every answer of the run found neither the id nor that name:

```
ANZEIGENAME bob gesetzt=ja zurueck=ja gleich_vorher=ja weg=occ
AUFGABE keine-kennung nc=35.0.0.10 nutzer=alice status=keine ergebnis=ok | 62 answers scanned for the id and the display name of bob; answers kept: 62; found 0 of 2 names; no _shared_by_ in any answer
ANZEIGENAME bob gesetzt=ja zurueck=ja gleich_vorher=ja weg=occ
AUFGABE keine-kennung nc=32.0.15.1 nutzer=alice status=keine ergebnis=ok | 62 answers scanned for the id and the display name of bob; answers kept: 62; found 0 of 2 names; no _shared_by_ in any answer
ANZEIGENAME bob gesetzt=nein zurueck=entfaellt gleich_vorher=ja
```


## Modifying tools on Nextcloud 35 and 32

Plan 33-10: `tasks_complete`, `tasks_update` and `tasks_move` called as functions under AppAPI
impersonation (`tests/integration/test_tasks_live.py`, `NC_MCP_REQUIRE_LIVE=1`), on both standing
instances, each without and with the Tasks app 0.18.1; on Nextcloud 35 also over the whole chain
through the installed app with the switch `NC_MCP_TASKS_UPDATE` on. Owner releases:

```
FREIGABE zustand=option-a datum=2026-11-13 umfang=nc35+nc32 quelle=owner-antwort-checkpoint-33-01-task-3
FREIGABE owner=option-a datum=2026-11-14 quelle=owner-antwort-checkpoint-33-10-task-2 (ExApp auf nc35 neu registrieren, Schalter tasks_update vorübergehend an, altes Image vorher als 0.7.2-vor33 sichern, danach Schalter aus und App neu gestartet)
```

Raw protocols: [raw/33-10-nc35.txt](../.planning/phases/33-aufgaben-aendern/raw/33-10-nc35.txt),
[raw/33-10-nc32.txt](../.planning/phases/33-aufgaben-aendern/raw/33-10-nc32.txt). Every case writes one
line `FALL <case> nc=<version> werkzeug=<tool> status=<calls> ergebnis=<ok|befund> | <marks>` with
yes/no marks and the first 12 hex digits of the sha256 of the column `calendardata`, read by PHP
in the container; "unchanged" always means the same hash, never a status code. The runs:

```
LIVE nc35 tasksapp=keine passed=58 failed=0
LIVE nc35 tasksapp=0.18.1 passed=58 failed=0
LIVE nc32 tasksapp=keine passed=58 failed=0
LIVE-ROT nc32 tasksapp=0.18.1 passed=57 failed=1 lauf=1
LIVE nc32 tasksapp=0.18.1 passed=58 failed=0 lauf=2
```

The red first run with the Tasks app on Nextcloud 32 failed in a case of phase 32
(`geteilt-namen`, the read only list missing from the first search right after the restart of
the container), not in a case of this plan; all 28 lines `FALL` of that run read `ergebnis=ok`.
The unchanged second run was green. Baseline per account before equal after in every run.

### Success criterion 1: Completing, reopening, already done, subtasks (TMOD-03, D-33-00b)

| Instance | Tasks app | Case | Lines `FALL` with `ergebnis=ok` | Raw protocol |
|---|---|---|---|---|
| Nextcloud 35 | none | `aendern-abhaken` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-wiederoeffnen` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-schon-erledigt` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-kinder` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-abhaken` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-wiederoeffnen` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-schon-erledigt` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-kinder` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 32 | none | `aendern-abhaken` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-wiederoeffnen` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-schon-erledigt` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-kinder` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-abhaken` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-wiederoeffnen` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-schon-erledigt` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-kinder` | 1 of 1 | raw/33-10-nc32.txt |

Quoted from the run on Nextcloud 35 without the Tasks app:

```
FALL aendern-abhaken nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204 ergebnis=ok | felder_wie_phase30=ja form_wie_completed_ics=ja eine_sekunde=ja ein_put=ja crlf=ja antwort=ja sha_vorher=31750f1ad5d1 sha_nachher=1aa9c9c29b09
FALL aendern-wiederoeffnen nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | felder=ja form_wie_reopened_ics=ja ein_put=ja antwort=ja sha_vorher=18c62111a3c1 sha_nachher=1e0cbc46fe0f
FALL aendern-schon-erledigt nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200 ergebnis=ok | kein_put=ja already=ja sha_gleich=ja sha=30ffa7ec4244
FALL aendern-kinder nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204,PUT:204,PUT:204,PUT:204 ergebnis=ok | puts_nachordnung=ja alle_erledigt=ja changed_nachordnung=ja kinder_crlf=ja eltern_crlf=ja puts=4
```

And from the run on Nextcloud 32 with the Tasks app 0.18.1:

```
FALL aendern-abhaken nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204 ergebnis=ok | felder_wie_phase30=ja form_wie_completed_ics=ja eine_sekunde=ja ein_put=ja crlf=ja antwort=ja sha_vorher=9aacfee2c4c4 sha_nachher=8d6ff9b126bf
FALL aendern-wiederoeffnen nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | felder=ja form_wie_reopened_ics=ja ein_put=ja antwort=ja sha_vorher=480263394fc0 sha_nachher=98f48ce2f3d2
FALL aendern-schon-erledigt nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207,GET:200 ergebnis=ok | kein_put=ja already=ja sha_gleich=ja sha=1c46fed989ad
FALL aendern-kinder nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204,PUT:204,PUT:204,PUT:204 ergebnis=ok | puts_nachordnung=ja alle_erledigt=ja changed_nachordnung=ja kinder_crlf=ja eltern_crlf=ja puts=4
```

### Success criterion 2: Exactly the named fields, nothing written without a difference (TMOD-02, TMOD-04)

| Instance | Tasks app | Case | Lines `FALL` with `ergebnis=ok` | Raw protocol |
|---|---|---|---|---|
| Nextcloud 35 | none | `aendern-felder` | 4 of 4 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-reich` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-ohne-unterschied` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-felder` | 4 of 4 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-reich` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-ohne-unterschied` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 32 | none | `aendern-felder` | 4 of 4 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-reich` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-ohne-unterschied` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-felder` | 4 of 4 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-reich` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-ohne-unterschied` | 1 of 1 | raw/33-10-nc32.txt |

Quoted from the run on Nextcloud 35 without the Tasks app:

```
FALL aendern-felder nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=setzen felder_wie_app=ja antwort_changed=ja ein_put=ja due_form_wie_with_time_ics=ja tags_eine_zeile_wie_tags_ics=ja sha_vorher=da0ae0c8eeef sha_nachher=6eb3c0b67abc
FALL aendern-felder nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=due-entfernen felder_wie_app=ja antwort_changed=ja ein_put=ja form_zeile_weg_wie_app=ja sha_vorher=6eb3c0b67abc sha_nachher=f19ec50446c8
FALL aendern-felder nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=tags-entfernen felder_wie_app=ja antwort_changed=ja ein_put=ja sha_vorher=f19ec50446c8 sha_nachher=75b0caf5ed8b
FALL aendern-felder nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=beschreibung-entfernen felder_wie_app=ja antwort_changed=ja ein_put=ja sha_vorher=75b0caf5ed8b sha_nachher=c66246834b24
FALL aendern-reich nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | vorher_gefaltet=ja felder=ja unberuehrte_zeilen_woertlich=ja valarm_gleich=ja vtimezone_gleich=ja x_zeilen_gleich=ja parameter_summary=ja antwort=ja sha_vorher=8eb376e276bc sha_nachher=2515e6f8c444
FALL aendern-ohne-unterschied nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | kein_put=ja changed_leer=ja sha_gleich=ja sha=550288e93330
```

And from the run on Nextcloud 32 with the Tasks app 0.18.1:

```
FALL aendern-felder nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=setzen felder_wie_app=ja antwort_changed=ja ein_put=ja due_form_wie_with_time_ics=ja tags_eine_zeile_wie_tags_ics=ja sha_vorher=74a81deb844f sha_nachher=875fd524a0ab
FALL aendern-felder nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=due-entfernen felder_wie_app=ja antwort_changed=ja ein_put=ja form_zeile_weg_wie_app=ja sha_vorher=875fd524a0ab sha_nachher=84ac0ebc941e
FALL aendern-felder nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=tags-entfernen felder_wie_app=ja antwort_changed=ja ein_put=ja sha_vorher=84ac0ebc941e sha_nachher=e545733a0ea1
FALL aendern-felder nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | schritt=beschreibung-entfernen felder_wie_app=ja antwort_changed=ja ein_put=ja sha_vorher=e545733a0ea1 sha_nachher=4308d0f86d4b
FALL aendern-reich nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200,PUT:204 ergebnis=ok | vorher_gefaltet=ja felder=ja unberuehrte_zeilen_woertlich=ja valarm_gleich=ja vtimezone_gleich=ja x_zeilen_gleich=ja parameter_summary=ja antwort=ja sha_vorher=d4ae451be2e6 sha_nachher=89430ddb3d02
FALL aendern-ohne-unterschied nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | kein_put=ja changed_leer=ja sha_gleich=ja sha=e32650042f4c
```

### Success criterion 3: Stale ETag, read only share, recurring task, Deck card (TMOD-01, TMOD-05)

| Instance | Tasks app | Case | Lines `FALL` with `ergebnis=ok` | Raw protocol |
|---|---|---|---|---|
| Nextcloud 35 | none | `aendern-veraltet` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-nur-lesend` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-nur-lesend-server` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-wiederkehrend` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `aendern-deck` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-veraltet` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-nur-lesend` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-nur-lesend-server` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-wiederkehrend` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `aendern-deck` | 3 of 3 | raw/33-10-nc35.txt |
| Nextcloud 32 | none | `aendern-veraltet` | 3 of 3 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-nur-lesend` | 3 of 3 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-nur-lesend-server` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-wiederkehrend` | 3 of 3 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `aendern-deck` | 3 of 3 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-veraltet` | 3 of 3 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-nur-lesend` | 3 of 3 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-nur-lesend-server` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-wiederkehrend` | 3 of 3 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `aendern-deck` | 3 of 3 | raw/33-10-nc32.txt |

Quoted from the run on Nextcloud 35 without the Tasks app:

```
FALL aendern-veraltet nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200 ergebnis=ok | harness_aenderung=ja abgelehnt=ja kein_schreiben=ja sha_gleich_nach_harness=ja nicht_im_ziel=ja sha=4ed1c1096a37
FALL aendern-veraltet nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | harness_aenderung=ja abgelehnt=ja kein_schreiben=ja sha_gleich_nach_harness=ja nicht_im_ziel=ja sha=a41bf2f8e2d2
FALL aendern-veraltet nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200 ergebnis=ok | harness_aenderung=ja abgelehnt=ja kein_schreiben=ja sha_gleich_nach_harness=ja nicht_im_ziel=ja sha=fedd8e124936
FALL aendern-nur-lesend nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207 ergebnis=ok | abgelehnt_nur_lesend=ja kein_schreiben=ja sha_beim_eigentuemer_gleich=ja sha=1864bac09f9b
FALL aendern-nur-lesend nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207 ergebnis=ok | abgelehnt_nur_lesend=ja kein_schreiben=ja sha_beim_eigentuemer_gleich=ja sha=1bd11e32b22c
FALL aendern-nur-lesend nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207 ergebnis=ok | abgelehnt_nur_lesend=ja kein_schreiben=ja sha_beim_eigentuemer_gleich=ja sha=035e1b9c3641
FALL aendern-nur-lesend-server nc=35.0.0.10 werkzeug=harness status=keine ergebnis=ok | get_lesbar=ja put_abgelehnt=ja move_abgelehnt=ja sha_beim_eigentuemer_gleich=ja nicht_im_ziel=ja put_status=404 move_status=404
FALL aendern-wiederkehrend nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200 ergebnis=ok | abgelehnt_wiederkehrend=ja kein_schreiben=ja sha_gleich=ja sha=c473bcb83740
FALL aendern-wiederkehrend nc=35.0.0.10 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | abgelehnt_wiederkehrend=ja kein_schreiben=ja sha_gleich=ja sha=c473bcb83740
FALL aendern-wiederkehrend nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200 ergebnis=ok | abgelehnt_wiederkehrend=ja kein_schreiben=ja sha_gleich=ja sha=c473bcb83740
FALL aendern-deck nc=35.0.0.10 werkzeug=tasks_complete status=keine ergebnis=ok | wie_unbekannt=ja keine_anfrage=ja keine_deck_marke=ja
FALL aendern-deck nc=35.0.0.10 werkzeug=tasks_update status=keine ergebnis=ok | wie_unbekannt=ja keine_anfrage=ja keine_deck_marke=ja
FALL aendern-deck nc=35.0.0.10 werkzeug=tasks_move status=keine ergebnis=ok | wie_unbekannt=ja keine_anfrage=ja keine_deck_marke=ja deck_ziel_abgelehnt=ja deck_ziel_keine_marke=ja
```

And from the run on Nextcloud 32 with the Tasks app 0.18.1:

```
FALL aendern-veraltet nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207,GET:200 ergebnis=ok | harness_aenderung=ja abgelehnt=ja kein_schreiben=ja sha_gleich_nach_harness=ja nicht_im_ziel=ja sha=e3df2488514c
FALL aendern-veraltet nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | harness_aenderung=ja abgelehnt=ja kein_schreiben=ja sha_gleich_nach_harness=ja nicht_im_ziel=ja sha=3271937fab51
FALL aendern-veraltet nc=32.0.15.1 werkzeug=tasks_move status=PROPFIND:207,GET:200 ergebnis=ok | harness_aenderung=ja abgelehnt=ja kein_schreiben=ja sha_gleich_nach_harness=ja nicht_im_ziel=ja sha=a0324ecc86d4
FALL aendern-nur-lesend nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207 ergebnis=ok | abgelehnt_nur_lesend=ja kein_schreiben=ja sha_beim_eigentuemer_gleich=ja sha=b65686804d87
FALL aendern-nur-lesend nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207 ergebnis=ok | abgelehnt_nur_lesend=ja kein_schreiben=ja sha_beim_eigentuemer_gleich=ja sha=dec9f968d33f
FALL aendern-nur-lesend nc=32.0.15.1 werkzeug=tasks_move status=PROPFIND:207 ergebnis=ok | abgelehnt_nur_lesend=ja kein_schreiben=ja sha_beim_eigentuemer_gleich=ja sha=2055277546b6
FALL aendern-nur-lesend-server nc=32.0.15.1 werkzeug=harness status=keine ergebnis=ok | get_lesbar=ja put_abgelehnt=ja move_abgelehnt=ja sha_beim_eigentuemer_gleich=ja nicht_im_ziel=ja put_status=404 move_status=404
FALL aendern-wiederkehrend nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207,GET:200 ergebnis=ok | abgelehnt_wiederkehrend=ja kein_schreiben=ja sha_gleich=ja sha=5ef20612599d
FALL aendern-wiederkehrend nc=32.0.15.1 werkzeug=tasks_update status=PROPFIND:207,GET:200 ergebnis=ok | abgelehnt_wiederkehrend=ja kein_schreiben=ja sha_gleich=ja sha=5ef20612599d
FALL aendern-wiederkehrend nc=32.0.15.1 werkzeug=tasks_move status=PROPFIND:207,GET:200 ergebnis=ok | abgelehnt_wiederkehrend=ja kein_schreiben=ja sha_gleich=ja sha=5ef20612599d
FALL aendern-deck nc=32.0.15.1 werkzeug=tasks_complete status=keine ergebnis=ok | wie_unbekannt=ja keine_anfrage=ja keine_deck_marke=ja
FALL aendern-deck nc=32.0.15.1 werkzeug=tasks_update status=keine ergebnis=ok | wie_unbekannt=ja keine_anfrage=ja keine_deck_marke=ja
FALL aendern-deck nc=32.0.15.1 werkzeug=tasks_move status=keine ergebnis=ok | wie_unbekannt=ja keine_anfrage=ja keine_deck_marke=ja deck_ziel_abgelehnt=ja deck_ziel_keine_marke=ja
```

### Success criterion 4: Relocating into a named list (TMOD-08)

| Instance | Tasks app | Case | Lines `FALL` with `ergebnis=ok` | Raw protocol |
|---|---|---|---|---|
| Nextcloud 35 | none | `verschieben-genannt` | 2 of 2 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `verschieben-belegt` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | none | `verschieben-kinder` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `verschieben-genannt` | 2 of 2 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `verschieben-belegt` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `verschieben-kinder` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 32 | none | `verschieben-genannt` | 2 of 2 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `verschieben-belegt` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | none | `verschieben-kinder` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `verschieben-genannt` | 2 of 2 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `verschieben-belegt` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `verschieben-kinder` | 1 of 1 | raw/33-10-nc32.txt |

Quoted from the run on Nextcloud 35 without the Tasks app:

```
FALL verschieben-genannt nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,MOVE:201 ergebnis=ok | ziel=geteilt-schreibbar quelle_leer=ja im_ziel=ja text_gleich=ja gleiche_uid=ja neue_id=ja ein_move=ja sha=324fe49d1252
FALL verschieben-genannt nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,MOVE:201 ergebnis=ok | ziel=eigene quelle_leer=ja im_ziel=ja text_gleich=ja gleiche_uid=ja neue_id=ja ein_move=ja sha=b37c40d0b1de
FALL verschieben-belegt nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207 ergebnis=ok | abgelehnt=ja kein_move=ja quelle_gleich=ja ziel_gleich=ja sha_quelle=e35f1a383cff sha_ziel=db398a1e4de9
FALL verschieben-kinder nc=35.0.0.10 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,MOVE:201,MOVE:201,MOVE:201 ergebnis=ok | quelle_leer=ja alle_im_ziel_unveraendert=ja moves_nachordnung=ja moved=ja moves=3
```

And from the run on Nextcloud 32 with the Tasks app 0.18.1:

```
FALL verschieben-genannt nc=32.0.15.1 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,MOVE:201 ergebnis=ok | ziel=geteilt-schreibbar quelle_leer=ja im_ziel=ja text_gleich=ja gleiche_uid=ja neue_id=ja ein_move=ja sha=f001936169b6
FALL verschieben-genannt nc=32.0.15.1 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,MOVE:201 ergebnis=ok | ziel=eigene quelle_leer=ja im_ziel=ja text_gleich=ja gleiche_uid=ja neue_id=ja ein_move=ja sha=c3ae598e8a96
FALL verschieben-belegt nc=32.0.15.1 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207 ergebnis=ok | abgelehnt=ja kein_move=ja quelle_gleich=ja ziel_gleich=ja sha_quelle=9cbfae958c0d sha_ziel=050bf9db46e3
FALL verschieben-kinder nc=32.0.15.1 werkzeug=tasks_move status=PROPFIND:207,GET:200,REPORT:207,REPORT:207,MOVE:201,MOVE:201,MOVE:201 ergebnis=ok | quelle_leer=ja alle_im_ziel_unveraendert=ja moves_nachordnung=ja moved=ja moves=3
```

### Success criterion 5: A chain that meets 412 at its second descendant (D-33-09)

| Instance | Tasks app | Case | Lines `FALL` with `ergebnis=ok` | Raw protocol |
|---|---|---|---|---|
| Nextcloud 35 | none | `kette-teilfehler` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 35 | 0.18.1 | `kette-teilfehler` | 1 of 1 | raw/33-10-nc35.txt |
| Nextcloud 32 | none | `kette-teilfehler` | 1 of 1 | raw/33-10-nc32.txt |
| Nextcloud 32 | 0.18.1 | `kette-teilfehler` | 1 of 1 | raw/33-10-nc32.txt |

Quoted from the run on Nextcloud 35 without the Tasks app:

```
FALL kette-teilfehler nc=35.0.0.10 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204,PUT:412 ergebnis=ok | harness_aenderte_den_zweiten=ja gestoppt=ja grund_412=ja changed_genau_erster=ja puts=ja eltern_sha_gleich=ja zweiter_sha_wie_harness=ja dritter_sha_gleich=ja erster_erledigt=ja sha_eltern=819d97fe0518
```

And from the run on Nextcloud 32 with the Tasks app 0.18.1:

```
FALL kette-teilfehler nc=32.0.15.1 werkzeug=tasks_complete status=PROPFIND:207,GET:200,REPORT:207,PUT:204,PUT:412 ergebnis=ok | harness_aenderte_den_zweiten=ja gestoppt=ja grund_412=ja changed_genau_erster=ja puts=ja eltern_sha_gleich=ja zweiter_sha_wie_harness=ja dritter_sha_gleich=ja erster_erledigt=ja sha_eltern=e5d0bd687e79
```

### Whole chain through the installed app on Nextcloud 35

The ExApp was unregistered without `--rm-data` and registered again with an image of this
branch (`bootstrap_exapp.sh --nc35`); the version in `appinfo/info.xml` stayed 0.7.2. The image
before is kept locally under its own tag as the way back. Then the switch went on, one OAuth
connection called the chain create, read, update, complete, relocate and an update with the
first ETag, and every call left exactly one audit entry with parameter names only:

```
RUECKWEG image=0.7.2-vor33 image_id=sha256:00a2e4b0bfb7f283a22c944c14141b8de6b27f1faf64902ae2c23f9498782c02
SCHALTER an app_neu_gestartet=ja
WERKZEUGE anzahl=30 tasks=ja familien=10 aendernd=tasks_complete,tasks_update,tasks_move
AUDIT werkzeug=tasks_create parameter=due,list,priority,tags ergebnis=rejected anzahl=1
AUDIT werkzeug=tasks_create parameter=due,list,priority,tags ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_read parameter=task_id ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_update parameter=etag,tags,task_id ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_complete parameter=completed,etag,task_id ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_move parameter=etag,list,task_id ergebnis=ok anzahl=1
AUDIT werkzeug=tasks_update parameter=etag,task_id ergebnis=rejected anzahl=1
```

The last call was refused (`changed since it was read`) and the stored object stayed as it was
(`HARNESS GET` before and after in the raw protocol). `description` is not in the audit
allowlist, so it never shows among the parameter names. The audit records the refusal of the
stale ETag with the reason `unspecified`.

Afterwards the switch went off again. The first attempt did not take: `occ app_api:app:config:set`
without `--update-only` leaves an existing key as it is, so the tools stayed registered. With
`--update-only`, and the app disabled and enabled, the three tools are gone:

```
SCHALTER aus-versuch-1 wirkung=keine (config:set ohne --update-only, Wert blieb on; nicht gezählt)
WERKZEUGE nach_aus anzahl=30 tasks=ja familien=10 aendernd=tasks_complete,tasks_update,tasks_move
SCHALTER aus app_neu_gestartet=ja wert=off
WERKZEUGE nach_aus anzahl=27 tasks=ja familien=10 aendernd=keine
```

The canary ran against Nextcloud 35 with the switch on and the Tasks app 0.18.1:

```
KANARIE nc35 passed=4 schalter=an tasksapp=0.18.1
```

Nextcloud 32 has no whole chain (the app runs as a local process at the daemon
`manual_install`):

```
KETTE nc32 entfaellt grund=manual-install (wie 32-07: auf 32 läuft die ExApp als lokaler Prozess am Daemon manual_install, eine Kette über ein Image gibt es dort nicht)
```

## Not reproducible or not measured

- Nextcloud 32 has no whole chain: the app runs there as a local process at the daemon
  `manual_install`, not as an image behind HaRP.
- The outage of one list is produced in the client (a response hook holds the `REPORT` back for
  3 s), not by a slow server.
- CI measured each case once on a single commit (see [CI run](#ci-run)); the job `exapp` runs
  on Nextcloud 34.0.3, not 35, so the case without the Tasks app on 35 rests on plan 32-07 only.
- Nextcloud 33 and 34: only through the source.
- The acceptance script did not run on Nextcloud 35: it leaves a file, a note, an event, a Deck
  card, a table row and a Talk message behind and deletes nothing, which the standing instance
  does not take. On Nextcloud 32 its mail step met a missing prerequisite (GreenMail empty after
  the restart).
- `calendar_create_event` was not compared byte for byte over the chain, because a second call
  writes a second event.
- Side finding of the research, not about this bundle: on Nextcloud 34 and 35 the search
  provider `tasks` appends the list name together with its owner to the subline of a hit of a
  shared list. That concerns `unified_search`, which passes the subline on. **Settled by
  D-32-17 in plan 32-09:** `unified_search` and `search` pass that subline on without the
  owner, or drop it (see [Gap closure 32-09](#gap-closure-32-09-on-nextcloud-35-and-32)).
- Whether the router of the Tasks app opens the very task behind a link needs a browser and
  was not measured.
- The cap of 500 results (`MAX_RESULTS = 500` in `src/mcp_connector/tools/tasks.py`) is now
  measured live: plan 32-10 paged a list with 520 open tasks on both instances to the end (see
  [Gap closure 32-10](#gap-closure-32-10-on-nextcloud-35-and-32)); the unit tests
  `test_the_ceiling_stops_paging_with_an_honest_note` and
  `test_limit_policy_constants_are_the_measured_values` stay. The series of 2000 open tasks
  ran only in the measuring program, not in the live test.
- `recurring` is now met live (plan 32-10, three forms, see
  [Gap closure 32-10](#gap-closure-32-10-on-nextcloud-35-and-32)), beside the unit tests
  `test_rrule_or_rdate_marks_the_master_as_recurring` and
  `test_a_recurring_task_is_one_hit_without_expansion`. What remains: how the Tasks app itself
  checks off one occurrence needs a browser and was not measured.
- 403 against 404 for a list that can only be read: live, the server answered a direct `PUT`
  of the harness into the read only share with 404 on both instances, for example
  `AUFGABE geteilt-ro-server nc=35.0.0.10 nutzer=alice status=keine ergebnis=ok | harness PUT with the app password of alice, not the connector; PUT 404; calendarobjects vorher=1 nachher=1`
  from raw/32-07-nc35.txt. The bundle refuses before any `PUT` (`geteilt-ro-vorab`), so the
  branch for a 403 of the server was never reached live; it rests on the unit test
  `test_403_of_the_server_names_the_list_without_its_uri`.
- Limits of plan 32-09: no share with a group (not released by the owner), and no whole chain
  through the installed app; D-32-17 and D-32-18 are proven at function level under AppAPI
  impersonation, as in plan 32-07.
- State after plan 32-10: shares with a group are measured and proven live in both directions;
  still no whole chain through the installed app (function level under AppAPI impersonation);
  Nextcloud 33 and 34 only through the source. The display name of bob differed from the
  account id only in the two runs with the Tasks app; CI keeps the display name as it is and
  does not build the series of 520 tasks (both switches are unset there).

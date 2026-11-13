---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 02
subsystem: messung
tags: [caldav, vtodo, messung, impersonation, nextcloud-32, nextcloud-35, wegwerf, tasks-app]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-01 (Basis-SHA, Strecke 32 bereit, Bootstrap für 32)
provides:
  - scripts/tasks_measure.py, Messprogramm mit getesteten Helfern (children_filter, uid_filter, owner_suffix_strip, derive_budget, navigation_lists)
  - raw/32-02-messung.txt mit allen Messreihen, MESSWERT- und ENTSCHEID-Zeilen
  - docs/tasks-evidence.md, Abschnitt "Measurements before the build"
  - gemeinsame Owner-Freigabe FREIGABE zustand=option-a für 32-02, 32-07, 32-08
affects: [32-03, 32-04, 32-04b, 32-06, 32-07, 32-08]

tech-stack:
  added: []
  patterns:
    - "Messprogramm lädt die Helfer des Spikes per Dateipfad statt sie zu kopieren"
    - "Rückbau auf Langzeitstrecken: Listen per DELETE mit X-NC-CalDAV-No-Trashbin, BASELINE je Konto per PHP vor und nach dem Lauf"

key-files:
  created:
    - scripts/tasks_measure.py
    - tests/unit/test_tasks_measure.py
    - docs/tasks-evidence.md
    - .planning/phases/32-tasks-bundle-suchen-lesen-anlegen/raw/32-02-messung.txt
  modified: []

key-decisions:
  - "per_list_timeout_s=1 und subtask_timeout_s=1 nach der Spike-Regel (Maxima unter Impersonation 0,113 s und 0,107 s bei 2000 Aufgaben)"
  - "max_results=500 bestätigt, Deckel des Blätterns 500 Treffer (20 Seiten zu 25)"
  - "text-match mit collation i;octet (gleiche Treffer wie ohne collation auf SQLite, PostgreSQL und nc35)"
  - "Schreibrecht vorab über write, write-content, bind oder all; write-properties zählt nicht"
  - "Kalender-Home ohne Anmeldung antwortet 207 leer (A1 widerlegt); Fall E6"
  - "Erkennung der Tasks-App: keine (auf 32 bleiben Navigation und Provider bis zum Neustart falsch); Hinweis aus D-32-10 entfällt"
  - "Linkform für fetch: index.php"
  - "Namensregel owner-displayname: der Zusatz lässt sich auf 32 und 35 sicher erkennen; keine Owner-Frage (Task 7 entfällt)"

patterns-established:
  - "AppAPI-Impersonation braucht auf 32 keinen laufenden lokalen Prozess, nur die registrierte, aktive ExApp"
  - "occ app:remove auf 32.0.15 verweigert eine deaktivierte App; zum Entfernen erst aktivieren"

requirements-completed: []

duration: ca. 37min
completed: 2026-11-13
---

# Phase 32 Plan 02: Messungen vor dem Bau Summary

**Kinderabfrage, Suchbudgets, Namensform geteilter Listen, Kalender-Home, Erkennung der Tasks-App und Linkform auf Wegwerf-35.0.2 (SQLite, PostgreSQL) und unter Impersonation auf 35.0.0 und 32.0.15 gemessen; alle Folgewerte als MESSWERT/ENTSCHEID im Rohprotokoll und in docs/tasks-evidence.md.**

## Werte für die Folgepläne

```
FREIGABE zustand=option-a datum=2026-11-13
MESSWERT per_list_timeout_s=1 regel=max(1,ceil(2*max)) max_s=0.113 quelle=nc35-impersonation modus=alle aufgaben=2000 (offen max 0,098 s); Wegwerf-Reihen höchstens 0,255 s (pg, alle); Netzwerkreserve: gemessen über Loopback ohne Netzlaufzeit, die Untergrenze 1 s lässt gegenüber dem größten Wert aller Reihen den Faktor 3,9 und damit rund 0,7 s Netzlaufzeit je Anfrage
MESSWERT subtask_timeout_s=1 regel=max(1,ceil(2*max)) max_s=0.107 quelle=nc35-impersonation (kinder 0/1/25 und eltern-uid, beide Formen, 2000 Aufgaben); Wegwerf-Reihen höchstens 0,172 s (pg); dieselbe Netzwerkreserve wie per_list_timeout_s
MESSWERT max_results=500 bestaetigt: Antwort alle bei 2000 Aufgaben 1514508 Bytes (rund 757 Bytes je Aufgabe, 500 Aufgaben rund 0,38 MB) in höchstens 0,113 s; Deckel des Blätterns 500 Treffer gesamt, das sind 20 Seiten zu 25 (D-32-08), danach ehrliche Notiz
ENTSCHEID collation=i;octet (beide Formen liefern dieselben Treffer auf sqlite, pg und nc35: GEGENPROBE collation treffer_gleich=ja erwartete_anzahl=ja; i;octet vergleicht Bytes ohne Kleinschreibung, die Nachprüfung im Connector bleibt, Abweichung H erledigt)
ENTSCHEID writable_privilegien=write,write-content,bind,all (mindestens eines; ordnet alle Sammlungen der Fixture und der Messung auf 32 und 35 richtig ein: eigen, gemischt und rw ja, ro, Deck und Geburtstage nein; write-properties zählt nicht, es steht auch bei nur lesbaren Sammlungen)
ENTSCHEID home404=e6 (gemessen auf 32 und 35: das Kalender-Home eines Kontos ohne jede Anmeldung antwortet unter Impersonation 207 mit null Sammlungen, kein 404, A1 widerlegt; die leere 207 ist Fall E6, ein 404 wird im Client ebenfalls als E6 behandelt)
ENTSCHEID erkennung=keine (auf 35 spiegeln Navigation und Provider-Liste jeden Zustand sofort, auf 32 nach app:disable ohne Neustart weiter ja und nach app:enable ohne Neustart weiter nein, also falsch und nicht unklar; der Hinweis aus D-32-10 entfällt)
ENTSCHEID linkform=index.php (auf 32 und 35 unter Impersonation öffnen beide Formen die Seite der Tasks-App mit Status 200; die Form mit index.php hängt nicht an hübschen URLs; der Provider selbst liefert die Form ohne index.php und ohne Prozentkodierung)
ENTSCHEID namensregel=owner-displayname (auf 32 und 35 zeigt jede geteilte Sammlung, rw und ro, owner_displayname_lesbar=ja und zusatz_passt=ja, der Name ohne Zusatz ist gleich dem Originalnamen; eigene Listen tragen keinen Zusatz)
OWNERFRAGE entfaellt
```

## Messergebnisse je Annahme

| Annahme | Ergebnis |
|---|---|
| Kinderabfrage bei 2000 Aufgaben (D-32-03, A7) | Median 88 bis 95 ms (SQLite), 113 bis 120 ms (PostgreSQL), 83 bis 93 ms unter Impersonation auf nc35; Maximum 107 ms (nc35), 172 ms (pg). A7 trägt: so teuer wie Modus offen |
| Eltern-UID (`prop-filter UID`) | Median 89 bis 95 ms, genau 1 Treffer |
| text-match (Abweichung H) | ohne collation und `i;octet` liefern auf sqlite, pg, nc35 dieselben Hrefs, Anzahlen 0/1/25/1 wie erwartet |
| Suche offen/alle unter Impersonation | offen Median 91 ms, max 98 ms, 70218 Bytes, 100 Treffer; alle Median 108 ms, max 113 ms, 1514508 Bytes, 2000 Treffer |
| Namensform (A2, D-32-14) | 32 und 35: rw und ro mit lesbarem owner-displayname, Zusatz passt genau, Name ohne Zusatz gleich dem Original; Deck-Kalender ohne owner-displayname, nicht geteilt |
| Kalender-Home ohne Anmeldung (A1) | 32 und 35: 207 mit 0 Sammlungen, kein Kalender angelegt; frisches Konto nach einer Anmeldung: 2 Kalender, nur VEVENT, 0 Aufgabenlisten |
| Erkennung der Tasks-App (A3) | 35: Navigation und Provider sofort richtig; 32: ohne Neustart veraltet (disable zeigt weiter ja, enable weiter nein), nach Neustart richtig |
| Linkform (A5) | 32 und 35: `index.php/apps/tasks/...` und `apps/tasks/...` unter Impersonation 200 mit Tasks-App; anonym 401. Provider-Link: Pfadform ohne index.php, ohne Prozentkodierung, geteilt mit `_shared_by_<konto>`, alle drei auflösbar |

## Accomplishments

- Messprogramm mit Unterbefehlen throwaway, up, live, teardown, stop, privileges, scan; Helfer des Spikes per Pfad geladen.
- Wegwerf-Instanzen 35.0.2 SQLite und PostgreSQL mit Tasks-App 0.18.1, je mit `down -v` abgebaut (keine Container, keine Volumes übrig).
- nc35 (35.0.0) und 32 (32.0.15) unter Impersonation gemessen, Tasks-App 0.18.1 installiert und wieder entfernt, BASELINE je Konto vorher gleich nachher.

## Task Commits

1. **Task 1: Messprogramm** - `51481ff` (test, RED), `96e0516` (feat, GREEN)
2. **Task 2: Owner-Freigabe** - `2de2b8b` (docs)
3. **Task 3: Wegwerf-Instanzen** - `a4c72e8` (docs)
4. **Task 4: nc35** - `4e5765a` (docs)
5. **Task 5: Nextcloud 32** - `e471507` (docs), `6768dc0` (fix, Rückbau der Tasks-App auf 32)
6. **Task 6: Werte und Beleg** - `d4d2630` (docs)
7. **Task 7: Owner-Frage** - `022364c` (docs, OWNERFRAGE entfaellt)

## BASELINE-Vergleich

| Instanz | Konto | vorher = nachher |
|---|---|---|
| nc35 | alice | calendars=1 objekte=31 geloescht=0 shares=0 abos=0, gleich=ja |
| nc35 | bob | calendars=2 objekte=1 geloescht=0 shares=0 abos=0, gleich=ja |
| nc35 | p3202frisch, p3202nie | alles 0, gleich=ja |
| nc32 | alice | calendars=1 objekte=3 geloescht=0 shares=0 abos=0, gleich=ja |
| nc32 | bob | calendars=2 objekte=1 geloescht=0 shares=0 abos=0, gleich=ja |
| nc32 | p3202frisch, p3202nie | alles 0, gleich=ja |

Tasks-App: nc35 `RUECKBAU nc35 tasksapp=wie-vorher vorher=keine nachher=keine`; nc32 nach dem zweiten Lauf `tasksapp=wie-vorher vorher=keine nachher=keine`, App-Verzeichnis entfernt. Papierkorb leer (0 Einträge), keine Listen mit Präfix p3202 übrig, Testkonten gelöscht.

## Gates (32-RULES.md Abschnitt 3, Stand d4d2630)

- pytest unit+contract: 5996 passed, 35 skipped, Exit 0 (31 neue Tests in test_tasks_measure.py)
- check_tool_budget: `tools/list: 16222 bytes, 24 tools, budget 18000`, Exit 0
- ruff check: All checks passed; ruff format --check: 379 files already formatted
- pyright (latest): 0 errors, 0 warnings, 0 informations
- vulture: Exit 0, keine Einträge in vulture_whitelist.py nötig

## TDD Gate Compliance

- RED `51481ff`: rot war nur `tests/unit/test_tasks_measure.py` (FileNotFoundError beim Laden des fehlenden Skripts, Sammelfehler); mit `--continue-on-collection-errors` alle übrigen 5965 Tests grün, ruff, pyright, vulture grün.
- GREEN `96e0516`: alles grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rückbau der Tasks-App auf Nextcloud 32**
- **Found during:** Task 5
- **Issue:** `occ app:disable` gefolgt von `occ app:remove` entfernt die App auf 35, auf 32.0.15 verweigert `app:remove` eine deaktivierte App ("tasks is not enabled"); der erste Rückbau endete mit `tasksapp=abweichend`.
- **Fix:** `restore_tasks_app` ruft `app:remove` im aktiven Zustand auf (aktiviert vorher, falls nötig); `teardown --tasks-before keine` stellte den Zustand auf 32 her (wie-vorher, BASELINE gleich).
- **Files modified:** scripts/tasks_measure.py
- **Commit:** 6768dc0

### Andere Abweichungen

**2. Unterbefehle anders geschnitten als im Plan genannt**
- Statt einzelner Prozesse `children`, `search`, `names`, `home`, `appstate`, `link`, `baseline` gibt es `live --steps search,children,names,link,home,appstate` (ein Prozess, Rückbau und BASELINE im `finally`) und `throwaway --db`; die Wegwerf-Instanz lebt nur innerhalb eines Prozesses. Inhaltlich sind alle genannten Messungen enthalten.

**3. Zusätzliche Messungen**
- Suche offen/alle auch auf den Wegwerf-Instanzen; LINK und PROVIDERLINK auch auf 32; Zustand `enable-ohne-neustart` in der APPSTATE-Reihe (zeigte auf 32 den zweiten Fehlweg).

**4. Kleinere Reihe unter Impersonation**
- Kinder und Eltern-UID auf nc35 mit 1 Aufwärm- und 6 Messläufen (n=6), Suche mit 3 und 15 wie im Spike.

**5. RAM-Gate zweimal zunächst rot**
- Vor PostgreSQL 3,15 GB und vor nc35 3,51 GB; nach drop_caches und 75 s 5,34 GB, je zweiter Anlauf. Beide roten Anläufe stehen im Rohprotokoll, es wurde nichts gestartet.

**6. Start der 32er Strecke nur mit Nextcloud und Caddy**
- `docker start nc-mcp-exapp-nc nc-mcp-exapp-caddy` statt compose start; Impersonation lief ohne lokalen Prozess (KONTROLLE 200).

## Hinweise

- `ziel=aufgabe` belegt nur, dass die Seite der Tasks-App lädt; ob deren Router die Aufgabe öffnet, braucht einen Browser (offen für 32-07).
- Der Provider-Link mit Sonderzeichen kommt unkodiert (`ä&+ ` im Pfad); `provider_link_parts` löst ihn trotzdem auf.
- alice hat auf 32 und 35 einen Deck-Kalender mit VTODO-Komponente; er fällt nur über den URI-Präfix `app-generated--` heraus (E9).

## Docker-Zustand am Ende

- Kein Container läuft. nc35 (`nc35-nc`, `nc35-harp`, `nc35-caddy`) per docker stop gestoppt, `nc_app_mcp_connector` nie gestartet. 32er Strecke (`nc-mcp-exapp-nc`, `nc-mcp-exapp-caddy`) gestoppt, harp, greenmail, registry nie gestartet. Wegwerf-Instanzen mit `down -v` entfernt (keine Container, keine Volumes `nc-spike-tags*`). Kein lokaler Prozess gestartet. Fremde Container nicht angefasst.

## Next Phase Readiness

- 32-03 übernimmt `collation=i;octet`, `writable_privilegien`, `home404=e6`, `namensregel=owner-displayname` und den Listenschlüssel; 32-04 die Budgets und `max_results`; 32-06 `linkform=index.php`; D-32-10 ohne Hinweis (`erkennung=keine`).

## Self-Check: PASSED

Vier Dateien vorhanden (scripts/tasks_measure.py, tests/unit/test_tasks_measure.py, docs/tasks-evidence.md, raw/32-02-messung.txt), alle neun Commits (51481ff, 96e0516, 2de2b8b, a4c72e8, 4e5765a, e471507, 6768dc0, d4d2630, 022364c) im Verlauf, jede Zeile im Block "Werte für die Folgepläne" wörtlich im Rohprotokoll.

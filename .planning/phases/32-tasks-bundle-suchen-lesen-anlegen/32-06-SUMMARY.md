---
phase: 32-tasks-bundle-suchen-lesen-anlegen
plan: 06
subsystem: tasks-fetch
tags: [provider, fetch, unified-search, datenschutz, doku, tdd]

requires:
  - phase: 32-tasks-bundle-suchen-lesen-anlegen
    provides: 32-02 (ENTSCHEID linkform=index.php, PROVIDERLINK-Zeilen), 32-03 (ids.task_list_key, ids.encode_task), 32-04 (tasks.read_task), 32-05 (Bundle tasks registriert, CHANGELOG-Block)
provides:
  - PROVIDER_KINDS "tasks": "task" mit Linkleser _tasks_target (Pfad und Fragment, unquote, Deck abgelehnt)
  - hit_url verlinkt Treffer geteilter Listen nur auf die Startseite der Tasks-App
  - fetch(task:...) über tasks.read_task mit Discovery-Prüfung, Deep-Link für eigene Listen, Startseite für geteilte
  - README-Zeile fetch, ein Added-Punkt je CHANGELOG, Satz in docs/hardening*.md Abschnitt 5 (drei Sprachen)
affects: [32-05b, 32-07, 32-08]

tech-stack:
  added: []
  patterns:
    - "Linkleser trennt Pfad und Fragment (urlsplit), App-Route per search, damit ein Webroot im Unterpfad trägt"
    - "fetch-Metadaten bleiben dict[str, str]: shared als \"true\"/\"false\" wie sender_trusted"

key-files:
  created: []
  modified:
    - src/mcp_connector/provider_map.py
    - tests/unit/test_provider_map.py
    - src/mcp_connector/tools/chatgpt.py
    - tests/unit/test_chatgpt_fetch.py
    - tests/contract/tool_classes.py
    - README.md
    - README.de.md
    - README.fr.md
    - CHANGELOG.md
    - CHANGELOG.de.md
    - CHANGELOG.fr.md
    - docs/hardening.md
    - docs/hardening.de.md
    - docs/hardening.fr.md

key-decisions:
  - "Fremder Ursprung im Provider-Link wird verworfen, die Id bleibt task: (Regel des Moduls und Vorbild Tables), statt den Treffer zur url-Id zu machen"
  - "Auch der Suchtreffer einer geteilten Liste (hit_url) zeigt nur die Startseite der Tasks-App, nicht nur fetch (D-32-15 sinngemäß)"
  - "Deep-Link nur bei eigener Liste, deren Schlüssel nicht die Hash-Form s+16 hex hat; sonst Startseite"

requirements-completed: []

duration: ca. 50min
completed: 2026-11-13
---

# Phase 32 Plan 06: fetch für task:-Ids und Suchprovider tasks Summary

**Code fertig: Der Suchprovider `tasks` übersetzt seine Links ohne Abruf in `task:<schlüssel>:<objekt>`, `fetch` liest diese Id über `tasks.read_task` mit Discovery-Prüfung, und geteilte Listen bekommen nur die Startseite der Tasks-App als Link. Der Live-Beweis folgt in 32-05b und 32-07.**

## Ergebnis je Task

| Task | Ergebnis | Commits |
|---|---|---|
| 1: Provider tasks mit Linkleser | `"tasks": "task"` mit Quellenkommentar; `_tasks_target` liest Pfad (mit/ohne index.php, auch hinter einem Webroot) und Fragment `#/`, `unquote`, lehnt `app-generated--`, Doppelpunkt, `/` im Segment, Query und jede andere Form ab; Schlüssel über `ids.task_list_key`; Docstring-Absatz zu Abos, nicht öffentlichen Objekten und Deck (K2, E9) | `26cc417` (RED), `3739c7e` (GREEN) |
| 2: fetch liest task:-Ids | `case "task"` vor dem Standardzweig, `_fetch_task` über `tasks_tools.read_task`; Text mit Status, Fälligkeit, Start, Priorität, Erledigt, Tags, Liste und Beschreibung (gekappt vom Leser, ohne Marker); url eigener Liste `{base}/index.php/apps/tasks/calendars/<key>/tasks/<objekt>` (quote), geteilter Liste `{base}/index.php/apps/tasks/`; metadata kind, list, shared, status; Modul-Docstring auf acht Leser/Eigenschaften; Anker in tool_classes.py `tools/chatgpt.py:258-282` mit "task is a kind without a file" | `26b488d` (RED), `b5f09a6` (GREEN) |
| 3: Doku drei Sprachen | README-Zeile fetch (task/Aufgabe/tâche), je ein Added-Punkt vor dem Punkt "Measured ... tasks-evidence.md", Satz in hardening Abschnitt 5 | `69be35d` |

## RED-Commits (nach 32-RULES Abschnitt 2)

- `26cc417`: 12 rote Tests, alle in `tests/unit/test_provider_map.py` (fünf Linkformen, geteilte Liste Schlüssel und Link, zwei Sonderzeichenfälle, fremder Ursprung, kein Abruf, Tabellen-Pin). Alle anderen 6317 Tests grün, ruff, format, pyright, vulture, Budget grün.
- `26b488d`: 10 rote Tests, alle in `tests/unit/test_chatgpt_fetch.py` (eigene Liste, Marker, geteilte Liste, Deck, vier unbekannte Listen, zweimal gleiche Aufgabe über fetch und tasks_read). Alle anderen 6330 Tests grün, übrige Gates grün.

## Gate-Zahlen

Vor `3739c7e`, `b5f09a6` und `69be35d` jeweils alle Exit 0:

- pytest unit+contract: 6330 passed, 35 skipped (nach Task 1), 6340 passed, 35 skipped (nach Task 2 und Task 3)
- check_tool_budget.py: `tools/list: 18747 bytes, 27 tools, budget 22000` (unverändert, kein neues Werkzeug)
- ruff check: All checks passed; ruff format --check: 390 files already formatted
- pyright: 0 errors, 0 warnings, 0 informations
- vulture: leer

Verify-Befehl aus Task 3 wörtlich gelaufen (`VERIFY3 OK`): Basis-Positivkontrolle grün; Sprach-Grep über die Diff-Zeilen gegen die Basis: DE 0 Treffer, FR 0 Treffer, U+2013/U+2014 0 Treffer. Positivkontrolle: 13 von 27 DE-Diffzeilen mit Umlaut oder ß, 23 von 27 FR-Diffzeilen mit Akzent (Diff gegen die Basis, also 32-05 und 32-06 zusammen). Zusätzlich 0 Gedankenstriche in allen Zeilen, die 32-06 hinzufügt (auch Code und Tests).

Kalender-Bundle unverändert: `git diff 6c5568c HEAD` über `clients/caldav.py`, `tools/calendar.py`, `server/reg_calendar.py` leer. Kein Docker.

## Deviations from Plan

**1. [Auslegung] Fremder Ursprung bleibt eine task:-Id**
- **Gefunden in:** Task 1
- **Plan:** Behavior nennt "fremder Ursprung: url-Id ... nie task".
- **Entscheid:** Der Ursprung wird wie überall im Modul verworfen (`absolute_url`, Vorbild `test_a_foreign_origin_in_a_tables_fragment_never_reaches_the_id`, PATTERNS Z. 966 "fremder Ursprung erreicht die Id nie"); die Id ist `task:tasks:a.ics`, weder Id noch Link enthalten den fremden Host. Grund: Der Provider liefert absolute Links mit der öffentlichen Adresse der Instanz, und die ExApp spricht Nextcloud oft über eine andere `base_url` an; ein Abgleich des Hosts hätte echte Treffer live zu url-Ids gemacht. Eine manipulierte Id kann nichts Fremdes lesen, weil `fetch` sie nur gegen die eigene Aufgaben-Discovery auflöst (T-32-06-01, -03).
- **Test:** `test_a_foreign_origin_in_a_tasks_link_never_reaches_the_id`. Bitte in 32-07 bestätigen oder per Owner-Entscheid umkehren.

**2. [Rule 2 - Datenschutz] Auch der Suchtreffer einer geteilten Liste verlinkt nur die Startseite**
- **Gefunden in:** Task 1
- **Problem:** `hit_url` hätte den Provider-Link mit `_shared_by_<konto>` in `unified_search` und `search` weitergereicht; D-32-15 nennt genau diesen Link als Grund.
- **Fix:** In `hit_url` für `kind == "task"` mit `_shared_by_` im Link `{base}/index.php/apps/tasks/`. Tests `test_a_tasks_hit_of_a_shared_list_links_only_the_start_page_of_the_tasks_app`, Gegenprobe `test_a_tasks_hit_of_an_own_list_keeps_its_deep_link`.
- **Commit:** `3739c7e`

**3. [Rule 1] Webroot im Unterpfad**
- Die App-Route wird per `search` statt `match` gesucht, damit `/nextcloud/index.php/apps/tasks/...` trägt; zusätzlicher Testfall im GREEN-Commit `3739c7e`.

**4. metadata als Zeichenketten**
- `FetchResult.metadata` ist `dict[str, str]`; `shared` steht deshalb als `"true"`/`"false"` (wie `sender_trusted` bei Mail), nicht als Boolean.

## Hinweis W2 (Umfang 32-05 und 32-06)

Der Umfang (14 Dateien, davon neun Doku-Dateien mit je ein bis fünf Zeilen) hat keine Probleme gemacht: Kontext reichte, keine Konflikte mit 32-05. Die Fortführung des CHANGELOG-Blocks war durch den Hinweis im 32-05-SUMMARY eindeutig (neuer Punkt vor "Measured ... tasks-evidence.md", in allen drei Sprachen an derselben Stelle). Die README-fetch-Zeile war von 32-05 unberührt. Einziger Zeitfaktor: vier volle Gate-Läufe zu je gut drei Minuten Testlaufzeit.

## Erfüllte Anforderungen

- TASK-09: **Code fertig**, nicht abgehakt. Der Live-Nachweis (Provider-Treffer führt auf dieselbe Aufgabe wie tasks_read) folgt in 32-05b und 32-07.
- TASK-07: Teil `docs/hardening*.md` erledigt; Kanarie, Abnahmeskript und CI stehen in 32-05b aus, daher nicht abgehakt.

## Known Stubs

Keine neuen. Der CHANGELOG-Punkt "Measured on ... `docs/tasks-evidence.md`" aus 32-05 bleibt bis 32-07 offen.

## Threat Flags

Keine neue Angriffsfläche: kein neuer Endpunkt, keine neue Anfrage; der Provider-Link wird nur geparst (T-32-06-01), Deck vor jeder Anfrage abgelehnt (T-32-06-02), Abo als unbekannte Id (T-32-06-03), geteilte Liste ohne Kontokennung in fetch und im Suchtreffer (T-32-06-04).

## Self-Check: PASSED

- Commits 26cc417, 3739c7e, 26b488d, b5f09a6, 69be35d im Log, alle mit Autor street1983nk, ohne Trailer, ohne closes/fixes/resolves.
- Alle 14 Dateien aus key-files geändert; nichts gepusht.

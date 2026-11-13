---
phase: 32-tasks-bundle-suchen-lesen-anlegen
verified: 2026-11-13T17:10:00Z
status: human_needed
score: 5/5 Erfolgskriterien verifiziert (9/9 Anforderungen TASK-01 bis TASK-09 gedeckt)
overrides_applied: 0
human_verification:
  - test: "Owner-Entscheid zur Untertitelzeile (subline) des Suchproviders tasks bei geteilten Listen"
    expected: "Owner entscheidet, ob search und unified_search die subline eines Treffers aus einer hineingeteilten Aufgabenliste weiterreichen dürfen. Nextcloud 34 und 35 hängen dort laut docs/tasks-evidence.md den Listennamen samt Besitzer an; der Link desselben Treffers wird seit 32-06 auf die Startseite gekürzt (D-32-15), die subline nicht."
    why_human: "D-32-06 begrenzt das Verbot auf Antworten des Bundles tasks; search und unified_search gehören zu anderen Bundles, das Verhalten bestand schon vor der Phase. Ob es trotzdem in Phase 32 oder später behoben wird, ist eine Produktentscheidung."
  - test: "Owner bestätigt die Lesart von fremdsichtbar im Phasenziel"
    expected: "Eine eigene Liste, die der Nutzer selbst an andere geteilt hat, gilt nach E4 als eigene Liste: tasks_create schreibt ohne list hinein, wenn sie die einzige eigene beschreibbare ist. Owner bestätigt das oder verlangt eine Erkennung hinausgeteilter Listen."
    why_human: "Das Goal sagt ohne je in eine fremdsichtbare Liste zu schreiben, E4 und TASK-06 sprechen von eigenen und geteilten (hineingeteilten) Listen. Der Code folgt E4; die Discovery fragt keine Freigaben eigener Listen ab. Der Wortlaut lässt beide Lesarten zu."
  - test: "fetch einer task:-Id mit langer Beschreibung oder schwebender Zeit"
    expected: "Owner entscheidet, ob fetch den Kürzungsvermerk (description_truncated) und das Kennzeichen *_floating aus tasks_read weitergeben soll, wie fetch es für Datei, Mail, Tabelle und Talk mit metadata.truncated tut."
    why_human: "Kein Erfolgskriterium verlangt die Flags in fetch, und die Zeit wird nicht zu UTC umgedeutet. Ob die stille Kürzung in fetch hinnehmbar ist, ist eine Qualitätsentscheidung."
---

# Phase 32: Tasks-Bundle suchen, lesen, anlegen, Verifikationsbericht

**Phase Goal:** Ein Assistent kann Nextcloud-Aufgaben suchen, lesen und anlegen, als zehnte Familie `tasks`, ohne je in eine fremdsichtbare Liste zu schreiben, ohne Deck-Karten zu zeigen und ohne das Verhalten des Kalender-Bundles zu ändern; die Phase ist ohne Phase 33 releasefähig
**Verified:** 2026-11-13T17:10:00Z
**Status:** human_needed
**Re-verification:** Nein, erste Verifikation

Geprüft im Worktree `tasks-080`, Branch `plan/v1.8-tasks-080`, HEAD `669748e`. Der CI-Stand `dcda6c8` unterscheidet sich von HEAD nur in `.planning/` und `docs/tasks-evidence.md` (`git diff --stat dcda6c8 HEAD`), kein Code.

## Goal Achievement

### Observable Truths (Erfolgskriterien aus ROADMAP.md)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Konto ohne Aufgabenliste eigens getestet, Fixture und live gegen ein Konto mit nur `VEVENT`: `tasks_search` leer mit Hinweis, `tasks_create` Fehler mit Ausweg | VERIFIED | Code: `tools/tasks.py:268-270` gibt `{"tasks": [], "hint": NO_LIST_HINT}`, `:766-768` wirft `NO_LIST_MESSAGE` mit `NO_LIST_WAY_OUT`; `clients/tasks.py:175-176` behandelt 404 als E6. Unit: `test_an_account_without_a_task_list_gets_an_empty_list_and_a_hint`, `test_a_home_that_answers_404_is_the_same_empty_answer`, `test_an_account_without_a_task_list_gets_an_error_with_a_way_out`. Live: `docs/tasks-evidence.md` Zeilen `AUFGABE task-03-mit-anmeldung` (BASELINE calendars=2, beide nur VEVENT laut 32-02 `HOME ... nur_vevent=ja`) und `task-03-ohne-anmeldung` auf NC 35 und 32, je mit und ohne Tasks-App; CI-Job `exapp` (NC 34) |
| 2 | Gegen echte Nextcloud mit Deck-Board und geteilter Liste: Standard nur offene, Fälligkeitsgrenze ohne undatierte, keine Deck-Karte, ausgefallene Liste als `degraded`, Termin-Werkzeuge byte-gleich | VERIFIED | Code: Statusfilter `tools/tasks.py:448-453`, `_due_within` gibt für fehlendes `DUE` False (`:469-471`), Deck vor allem anderen ausgeschlossen (`clients/tasks.py:259-260`, `tools/tasks.py:569-571`, `:911-913`), `degraded` je Liste (`:280-283`). Live: `AUFGABE suche-standard-und-faellig`, `deck` (Positivkontrolle Deck-Kalender mit VTODO in der Discovery, kein Treffer), `ausfall-liste` (degraded mit Listenname ohne Besitzer), `geteilt-namen`. Kalender: `git diff 32-BASE -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py src/mcp_connector/tools/calendar.py` leer (Gegenprobe: derselbe Befehl auf `clients/caldav.py` zeigt 126 Zeilen); Byte-Pin von mir unabhängig nachgerechnet: `build_discovery_body` und `build_calendar_query` liefern auf dem Basis-Commit und auf HEAD dieselben sha256 (`d330153d...`, `2352e0a2...`); `put_event` behält Wortlaut und Rückgabeschlüssel (Diff gelesen); Kette `KALENDER bytegleich=ja` 304/304 und 324/324 Bytes |
| 3 | "fällig am 20." steht am 20. (`DUE;VALUE=DATE`), Start, Tags, Priorität, Eltern wie von der Tasks-App gelesen; ohne `list` nur bei genau einer eigenen Liste, sonst Fehler mit Namen; in geteilte Liste nichts ohne Nennung | VERIFIED | Code: Datum bleibt `date` (`_parse_task_time`, `_in_zone` lässt Daten unberührt), VTODO nur über icalendar (`_build_todo`), Zielwahl `_pick_target` (`tools/tasks.py:924-964`): genannte Liste gewinnt, sonst Elternliste nur wenn eigen (D-32-16, `:944-951`), sonst genau eine eigene beschreibbare, sonst Fehler mit echten Namen. Unit: 30 Tests in `test_tasks_create.py`, darunter `test_a_due_date_is_that_very_day`, `test_a_parent_in_a_shared_list_without_list_is_an_error`. Live: Kette `ROHOBJEKT due=DUE;VALUE=DATE:20261120`, `AUFGABE anlegen-mit-list` ("no 20261204 anywhere"), `ohne-list-zwei-listen`, `d-32-16` (kein PUT, Zähler gleich), `geteilt-ro-vorab`; Owner-Abnahme in der Tasks-App 0.18.1 (`raw/32-08-abnahme.txt`: eingerückt, "Fällig am 20. November 2026", ganztägig, Tags, "Priorität 3") |
| 4 | `tasks_read` und `fetch` lösen dieselbe `task:`-Id; Treffer des Providers `tasks` führt auf diese Id; Zeitmatrix je als benannter Test; Fremdtext aus geteilter Liste gekappt und ohne Marker | VERIFIED | Code: `chatgpt._fetch_task` ruft `tasks_tools.read_task` (eine Auflösung), `provider_map.PROVIDER_KINDS["tasks"] = "task"` und `_tasks_target` mit `ids.task_list_key`. Unit: 15 benannte Matrixtests `test_matrix_{due,start,completed}_{all_day,zoned,utc,floating,without_a_date}` in `test_tasks_time_matrix.py`, `test_injection_corpus.py`, `test_description_cap_value`. Live: `fetch-gleich-read`, `provider-tasksapp-1` (Treffer-Id == gelesene Id), Kette `allgemeine-suche-mit-tasksapp` und `search` mit `task:`-Id. Einschränkung siehe Warnung W2 (fetch reicht Kürzungsvermerk und Schwebe-Kennzeichen nicht weiter) |
| 5 | Registry 27 Werkzeuge in zehn Familien; `EXPECTED_PUT_CALLS` 6; Budget nach Hausregel neu verankert, kein Werkzeug über 1400 Bytes; Kanarie ruft die drei Werkzeuge; READMEs, `docs/`, drei Changelogs nachgezogen; alle Gates grün | VERIFIED | Selbst gelaufen: `check_tool_budget.py` "tools/list: 18747 bytes, 27 tools, budget 22000", größtes Werkzeug `files_upload` 1377, `tasks_create` 1364; Rechnung 18747 x 1,15 = 21560, auf 500 gerundet 22000 (Kommentar im Skript mit Messdatum). `EXPECTED_PUT_CALLS = 6` in `tests/contract/test_no_destructive_calls.py:480`; im Code genau ein CalDAV-`PUT` (`caldav.py:408`, `put_new_object`), `tasks_create` nutzt ihn. `test_tool_surface.py` führt die drei Namen und `tasks_create` in `CREATE_TOOLS`. Kanarie: `test_canary.py:96` `TASK_TOOLS`, Live `KANARIE normal geprüft 27 von 27` (4 passed). READMEs de/en/fr "27 ... zehn/ten/dix", Changelogs je 2 Treffer `tasks_create`, `docs/hardening*.md` nennen Bundle `tasks`. CI 43453276557 auf `dcda6c8`: exapp, integration, canary-nc35, image, unit success; Security 43453276506 success (per `gh run view` bestätigt) |

**Score:** 5/5 Erfolgskriterien verifiziert

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mcp_connector/nextcloud/clients/tasks.py` | Discovery, VTODO-Abfragen, Wortlaut | VERIFIED | 451 Zeilen, eigene Discovery, Deck/Trash/Abos/Scheduling raus, Name ohne Besitzer, `writable` aus Discovery |
| `src/mcp_connector/tools/tasks.py` | search, read, create | VERIFIED | 1078 Zeilen, substanziell, alle Eingaben vor dem ersten Request geprüft |
| `src/mcp_connector/server/reg_tasks.py` | Registrierung, `@graceful`, Annotations | VERIFIED | READ_ONLY, READ_ONLY, CREATE_ONLY; kein Nutzerparameter |
| `src/mcp_connector/nextcloud/clients/caldav.py` | generischer create-only-Schreiber, Kalender unverändert | VERIFIED | `put_new_object` + `WriteWording`; `EVENT_WORDING` wortgleich zum alten Text |
| `src/mcp_connector/ids.py` | `task:`-Codec, neutraler Schlüssel | VERIFIED | `task_list_key` = `s` + 16 Hex von sha256 bei `_shared_by_` |
| `src/mcp_connector/provider_map.py` / `tools/chatgpt.py` | TASK-09 | VERIFIED | Provider `tasks`, Startseitenlink bei geteilter Liste, `fetch` über `read_task` |
| `tests/unit/test_caldav_bytes_pin.py` | Byte-Pin | VERIFIED | Hashes von mir auf dem Basis-Commit nachgerechnet, gleich |
| `docs/tasks-evidence.md` | Beleg | VERIFIED | Rohzeilen aus `raw/32-02`, `32-07`, `32-08` |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `reg_tasks.py` | `tools/tasks.py` | `search_tasks`, `read_task`, `create_task` | WIRED |
| `tools/tasks.create_task` | `caldav.put_new_object` | `If-None-Match: *`, `TASK_WORDING`, Label = Listenname | WIRED |
| `chatgpt.fetch` | `tools/tasks.read_task` | `case "task"` | WIRED |
| `search`/`unified_search` | `provider_map.extract_id` | `PROVIDER_KINDS["tasks"]` | WIRED (live: Treffer-Id `task:p3207-aufgaben:...`) |
| `audit/allowlist.py` | drei Werkzeuge | Parameternamen, `summary`/`description` gesperrt | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real Data | Status |
|----------|------|--------|-----------|--------|
| `tasks_search` | `tasks` | PROPFIND Discovery + REPORT je Liste | ja, live 207 mit Treffern | FLOWING |
| `tasks_read` | Aufgabe + `subtasks` | GET + REPORT `RELATED-TO` | ja, live Unteraufgabe gelistet | FLOWING |
| `tasks_create` | neues Objekt | PUT 201 + Rücklesen | ja, Rohobjekt per App-Passwort gelesen | FLOWING |

### Behavioral Spot-Checks (selbst gelaufen)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit + Contract | `uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib` | 6344 passed, 35 skipped | PASS |
| Budget | `uv run --no-sync python scripts/check_tool_budget.py` | 18747 bytes, 27 tools, budget 22000, max 1377 | PASS |
| ruff check / format | `ruff check .`, `ruff format --check .` | All checks passed; 392 files already formatted | PASS |
| pyright | `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright` | 0 errors, 0 warnings | PASS |
| vulture | `uv run --no-sync vulture src scripts vulture_whitelist.py` | keine Ausgabe | PASS |
| Byte-Pin unabhängig | Basis `b40f762` per `git archive` ins Scratchpad, sha256 der beiden Körper dort und auf HEAD | identisch | PASS |
| fetch mit 5000-Byte-Beschreibung und schwebendem `DUE` | Wegwerftest im Scratchpad mit den Fixtures von `test_chatgpt_fetch.py` | `read_task`: `description_truncated=True`, `due_floating=True`; `fetch`: metadata ohne `truncated`, Zeile `Due: 2026-11-20T09:00:00` ohne Kennzeichen | Befund W2 |

### Probe Execution

Keine Probe-Skripte deklariert; Live-Läufe sind Docker-gebunden (laut Auftrag kein Docker). Live-Belege stammen aus `raw/32-07-*.txt`, `raw/32-08-*.txt` und CI 43453276557 (Jobs per `gh run view` bestätigt, headSha `dcda6c8590a2...`).

### Requirements Coverage

| Requirement | Description (kurz) | Status | Evidence |
|-------------|--------------------|--------|----------|
| TASK-01 | Listen = VTODO-Kalender, Deck/Abos/Scheduling/Papierkorb nie; Kalender byte-gleich | SATISFIED | `_is_task_list`, leerer Diff der Kalendertests, Byte-Pin |
| TASK-02 | Suche: offen/alle, Text, Fälligkeit, Sortierung, Cursor mit Deckel 500 und Notiz, degraded, recurring, Fremdobjekt übersprungen | SATISFIED | Unit; live nur Standard, Fälligkeit, degraded (Rest siehe Lücken) |
| TASK-03 | Konto ohne Liste | SATISFIED | Kriterium 1 |
| TASK-04 | read mit Feldern, Zeitmatrix, ATTACH nie, unbekannte Id | SATISFIED | 15 Matrixtests, `test_attach_appears_in_no_field` |
| TASK-05 | create-only mit E7-Feldern, `DUE;VALUE=DATE`, Prüfungen vor dem Request, `confirmed` | SATISFIED | Kriterium 3, `test_a_failing_read_back_never_fails_the_write` |
| TASK-06 | Schreibziel nie positionsabhängig | SATISFIED | `_pick_target`, live `d-32-16`, `geteilt-ro-vorab` |
| TASK-07 | Bundle, Gates, Kanarie, Doku | SATISFIED | Kriterium 5 |
| TASK-08 | Budget neu verankert | SATISFIED | 22000, Rechnung geprüft |
| TASK-09 | `fetch` + Provider | SATISFIED | Kriterium 4 |

Die neun Haken `[x]` in REQUIREMENTS.md sind durch Code und Tests gedeckt. Keine verwaisten Anforderungen: REQUIREMENTS.md ordnet Phase 32 genau TASK-01 bis TASK-09 zu.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/mcp_connector/server/reg_tasks.py` | 23 | Beschreibung von `query`: "Words in title, tags or list"; der Code (`tools/tasks.py:456-458`) sucht in Titel, Beschreibung und Tags, nicht im Listennamen | Warning (W3) | Modell kann eine Listensuche über `query` erwarten, die leer bleibt; Beschreibung fehlt im Text |
| `src/mcp_connector/tools/chatgpt.py` | 538-582 | `_fetch_task` übernimmt weder `description_truncated` noch `*_floating` | Warning (W2) | gekappte Beschreibung kommt über `fetch` ohne Vermerk an |

Keine `TBD`, `FIXME`, `XXX`, `TODO` oder `HACK` in den geänderten Dateien (Treffer nur auf `VTODO`).

### Ehrlich benannte Lücken (live nicht gemessen)

| Lücke | Wo benannt | Bewertung |
|-------|-----------|-----------|
| Deckel 500 beim Blättern | 32-07-SUMMARY.md Zeile 113 | nur Unit (`test_the_ceiling_stops_paging_with_an_honest_note`, `test_limit_policy_constants_are_the_measured_values`); Größe aus 32-02 gemessen (2000 Aufgaben, 1,5 MB, 0,113 s) |
| `recurring` | 32-07-SUMMARY.md Zeile 113 | nur Unit (`test_rrule_or_rdate_marks_the_master_as_recurring`, `test_a_recurring_task_is_one_hit_without_expansion`) |
| 403 statt 404 bei nur lesbarer Liste | 32-07-SUMMARY.md Zeile 113 | live antwortete der Server 404 (Harness-PUT); 403-Zweig nur Unit (`test_403_of_the_server_names_the_list_without_its_uri`); 404-Wortlaut behauptet nicht, die Liste fehle |
| NC 35 ohne Tasks-App | `docs/tasks-evidence.md`, Abschnitt "Not reproducible" | nur aus 32-07; CI-Job `exapp` läuft auf NC 34.0.3 |

Die ersten drei stehen nur in der SUMMARY, nicht im Abschnitt "Not reproducible or not measured" von `docs/tasks-evidence.md` (Warnung W4). Gemessen ist dagegen alles, was die fünf Erfolgskriterien wörtlich verlangen.

### Human Verification Required

### 1. subline des Providers `tasks` bei geteilten Listen

**Test:** Owner entscheidet, ob `search` (Feld `text`) und `unified_search` (Feld `subline`) die subline eines Treffers aus einer hineingeteilten Aufgabenliste weiterreichen dürfen.
**Expected:** Entweder bewusst hingenommen (D-32-06 gilt nur für das Bundle `tasks`, Verhalten bestand vor der Phase) oder Folgeplan, der die subline für `kind == "task"` mit `_shared_by_`-Link verwirft oder säubert.
**Why human:** `docs/tasks-evidence.md` Zeile 494 bis 496 nennt den Befund (Listenname samt Besitzer auf NC 34 und 35). Phase 32 hat den Link desselben Treffers bereinigt, die subline nicht; live nur für eine eigene Liste gesehen (`Due on Nov 20, 2026 (p3207-aufgaben)`).

### 2. Lesart von "fremdsichtbar"

**Test:** Owner bestätigt, dass eine selbst hinausgeteilte eigene Liste als eigene Liste nach E4 gilt.
**Expected:** Bestätigung, oder Auftrag, hinausgeteilte Listen (etwa über `oc:invite`) wie geteilte zu behandeln.
**Why human:** Goal und E4 lassen zwei Lesarten zu; der Code folgt E4 und TASK-06.

### 3. Flags in `fetch`

**Test:** `fetch` einer Aufgabe mit mehr als 4096 Bytes Beschreibung oder schwebender Fälligkeit.
**Expected:** Owner entscheidet, ob `metadata.truncated` und ein Schwebe-Hinweis nachgezogen werden.
**Why human:** Kein Kriterium verletzt (gekappt, ohne Marker, nicht zu UTC umgedeutet), aber anders als die übrigen fetch-Leser ohne Vermerk.

### Gaps Summary

Keine Blocker. Alle fünf Erfolgskriterien sind am Code, an den Tests, an selbst gelaufenen Gates und an den Rohprotokollen belegt; der Kalender ist per leerem Diff und unabhängig nachgerechnetem Byte-Pin unverändert; `EXPECTED_PUT_CALLS` steht bei 6, 27 Werkzeuge, größtes 1377 Bytes. Kein Besitzername und kein `_shared_by_` in Antworten des Bundles `tasks` (Unit `test_shared_lists_named_by_owner_display_name_leak_nothing`, live Scan über 22 Antworten). Kein stilles Schreiben in geteilte Listen (D-32-16 im Code, Unit und live mit Zählern). Schwebende Zeiten bleiben schwebend und gekennzeichnet in `tasks_search` und `tasks_read`.

Warnungen:

- W1 (Owner-Entscheid): subline mit Besitzer in `search`/`unified_search` für Treffer geteilter Listen, außerhalb des Bundles, dokumentiert, nicht behoben.
- W2: `fetch` verliert `description_truncated` und `*_floating` (Spot-Check bestätigt).
- W3: Parameterbeschreibung von `query` nennt "list" statt "description".
- W4: drei live nicht gemessene Teile (Deckel 500, `recurring`, 403) nur in 32-07-SUMMARY, nicht in `docs/tasks-evidence.md`.
- W5 (Owner-Entscheid): Lesart "fremdsichtbar" gegen E4.

Info: Zeile 31 der Fortschrittstabelle in ROADMAP.md steht noch auf `0/6 Planned`, obwohl Phase 31 abgeschlossen ist (nicht Gegenstand dieser Verifikation, nicht geändert).

---

_Verified: 2026-11-13T17:10:00Z_
_Verifier: Claude (gsd-verifier)_

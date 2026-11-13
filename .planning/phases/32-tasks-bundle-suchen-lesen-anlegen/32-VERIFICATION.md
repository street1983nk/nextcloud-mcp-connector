---
phase: 32-tasks-bundle-suchen-lesen-anlegen
verified: 2026-11-13T17:25:00Z
status: human_needed
score: 5/5 Erfolgskriterien verifiziert (9/9 Anforderungen TASK-01 bis TASK-09 gedeckt); Lücken W1 bis W5 geschlossen
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "W1 / D-32-17: subline und text von Treffern geteilter Aufgabenlisten in unified_search und search ohne Besitzer"
    - "W2: fetch einer task:-Id trägt metadata.truncated und <feld>_floating samt Zeilenvermerk"
    - "W3: Beschreibung von query nennt title, description, tags"
    - "W4: Deckel 500, recurring und 403 stehen im Abschnitt 'Not reproducible or not measured' von docs/tasks-evidence.md"
    - "W5 / D-32-18 streng: hinausgeteilte oder per Link veröffentlichte eigene Liste ist ohne list kein Schreibziel"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Gruppenfreigaben messen (geplanter Messplan 32-10): eigene Liste an eine Gruppe teilen und eine Liste per Gruppe hineinteilen, auf Nextcloud 35 und 32"
    expected: "oc:invite einer an eine Gruppe geteilten eigenen Liste enthält ein oc:user-Element (Gruppen-Principal), sodass _shares_itself True liefert und tasks_create ohne list ablehnt; eine per Gruppe hineingeteilte Liste trägt _shared_by_ in der URI, ihr Name und ihre subline bleiben ohne Besitzer"
    why_human: "Bisher nicht gemessen (32-09-SUMMARY Grenzen, docs/tasks-evidence.md). Der Code zählt nur Kindelemente mit lokalem Namen 'user' in oc:invite (clients/tasks.py _shares_itself). Erscheint eine Gruppenfreigabe dort anders, gälte eine an eine Gruppe geteilte eigene Liste als privat, und D-32-18 wäre für diesen Fall verletzt. Braucht Docker und Owner-Freigabe für Zustandsänderungen."
  - test: "Wiederkehrende Aufgabe und Deckel 500 live (geplanter Messplan 32-10)"
    expected: "recurring: true als ein Treffer ohne Expansion; Blättern endet bei 500 Treffern mit ehrlicher Notiz"
    why_human: "Beides bisher nur per Unit belegt (W4 dokumentiert es jetzt ehrlich). Hauptsitzung hat den Messplan dem Owner vorgeschlagen; Phase 32 wird erst danach abgehakt."
  - test: "Security-Gate pip-audit rot auf 4b88a65 (Run 43471388436): opentelemetry-api 1.45.1, CVE-2026-126360, Fix 1.45.2"
    expected: "Owner entscheidet über ein Lock-Update (opentelemetry-api auf 1.45.2, transitiv) vor Push/Release; danach Security scans grün"
    why_human: "Keine Regression von Phase 32: uv.lock ist seit dcda6c8 (dort Security grün) unverändert, origin/main pinnt dieselbe Version. Neue Advisory zwischen den Läufen. Erfolgskriterium 5 verlangt aber alle Gates grün; ohne Lock-Update ist der Stand nicht releasefähig."
---

# Phase 32: Tasks-Bundle suchen, lesen, anlegen, Verifikationsbericht (Re-Verifikation)

**Phase Goal:** Ein Assistent kann Nextcloud-Aufgaben suchen, lesen und anlegen, als zehnte Familie `tasks`, ohne je in eine fremdsichtbare Liste zu schreiben, ohne Deck-Karten zu zeigen und ohne das Verhalten des Kalender-Bundles zu ändern; die Phase ist ohne Phase 33 releasefähig
**Verified:** 2026-11-13T17:25:00Z
**Status:** human_needed
**Re-verification:** Ja, nach Gap-Closure-Plan 32-09 (Vorstand: human_needed, Befunde W1 bis W5)

Geprüft im Worktree `tasks-080`, Branch `plan/v1.8-tasks-080`, HEAD `4b88a65`. Code-Änderungen von 32-09 gelesen per `git diff 669748e HEAD` (22 Dateien, davon fünf in `src/`).

## Lücken der Vorverifikation

| Lücke | Geschlossen | Beleg (Code, Test, live) |
|-------|-------------|--------------------------|
| W1 / D-32-17: subline mit Besitzer in `search`/`unified_search` | ja | `tools/search.py` `_normalise`: Treffer `kind == "task"` mit `_shared_by_` in der rohen `resourceUrl` (dieselbe Regel wie der Link nach D-32-15) gibt seine subline nicht direkt aus, sondern nach `held`; `_clean_task_sublines` macht eine Discovery je Aufruf, nur wenn etwas zurückgehalten ist, und setzt nur `clients/tasks.clean_subline(...)` ein; `None` oder fehlgeschlagene Discovery heißt: subline entfällt, Treffer bleibt (fail closed). `clean_subline` ersetzt das Ende ` (<Rohname>)` und die nackte Form `(<Rohname>)` (Fix 39c1be9) und verwirft jede Zeile, in der der Besitzer (casefold) oder `_shared_by_` noch steht. `chatgpt.search` nimmt `text` aus derselben subline (`chatgpt.py:228`). Unit: 10 Tests `test_clean_subline_*`, `test_a_shared_task_list_hit_keeps_its_subline_without_the_owner`, `test_a_failed_discovery_drops_only_the_subline_of_the_shared_hit`, `test_a_shared_hit_whose_list_is_not_in_the_discovery_loses_its_subline`, `test_the_text_of_a_shared_task_hit_never_names_the_owner`. Live (`raw/32-09-nc35.txt` Z. 112 bis 116): Positivkontrolle "raw subline names the owner", bereinigt `(p32live-ec5b284e-rw)` und `Fällig am 04.12.2026 (p32live-ec5b284e-rw)`, text gleich subline, ohne bob und ohne Marker; nc32 roh ohne Besitzer, unverändert |
| W2: fetch ohne Kürzungsvermerk und Schwebe-Kennzeichen | ja | `chatgpt._fetch_task`: `metadata["truncated"]="true"` bei `description_truncated`, je Zeitfeld `<feld>_floating` in metadata und ` (floating, no time zone)` in der Zeile. Unit `test_a_cut_task_description_is_marked_truncated`, `test_a_short_task_description_carries_no_truncated_key`, `test_a_floating_task_time_is_marked_in_the_text_and_the_metadata`, `test_a_zoned_or_all_day_task_time_carries_no_floating_mark` (Positiv und Negativ) |
| W3: `query`-Beschreibung nennt "list" | ja | `reg_tasks.py:23` "Words in title, description or tags; default: all"; Unit `test_the_query_parameter_names_title_description_and_tags_not_the_list`, `test_a_word_of_the_description_finds_a_task_and_the_list_name_does_not` |
| W4: nicht gemessene Teile nur in der SUMMARY | ja | `docs/tasks-evidence.md` Abschnitt "Not reproducible or not measured" (ab Z. 620): Deckel 500 (Z. 642), `recurring` (Z. 647 mit beiden Unit-Testnamen), 403 gegen 404 (Z. 651 bis 656) |
| W5 / D-32-18 streng: hinausgeteilte eigene Liste | ja | `clients/tasks.py`: Discovery fragt `oc:invite` und `cs:publish-url`; `_shares_itself` liefert True bei `oc:user` in `oc:invite`, bei belegter `publish-url` und wenn `oc:invite` nicht im 2xx-propstat steht (Punkt 6); für hineingeteilte Listen immer False. `tools/tasks._pick_target`: einzige eigene Liste hinausgeteilt, Fehler mit `list=`-Ausweg (Punkt 1); Elternliste hinausgeteilt, Fehler (Punkt 4); mehrere eigene bleiben "more than one" (Punkt 2); `list` genannt, wird geschrieben. Kein neues Ausgabefeld, `shared_out` und `owner_suffix` mit `repr=False`, außerhalb des Moduls nur in `_pick_target` gelesen; kein `asdict` in `tools/`. Messung `raw/32-09-messung.txt` Z. 286 bis 288 (ENTSCHEID-Zeilen, 32 und 35, App-Passwort und Impersonation). Unit: 8 Tests zu `shared_out`, 8 zur Zielwahl. Live auf 35 (`raw/32-09-nc35.txt` Z. 100 bis 110 und 205 bis 215) und 32: privat geschrieben (Positivkontrolle), geteilt an bob abgelehnt ohne PUT, mit `list` geschrieben, parent abgelehnt, öffentlicher Link abgelehnt, nach Rücknahme wieder geschrieben; Zähler vorher/nachher passend. Grenze: Gruppenfreigabe nicht gemessen (siehe unten) |

## Goal Achievement

### Observable Truths (Erfolgskriterien aus ROADMAP.md)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Konto ohne Aufgabenliste (Fixture und live, nur `VEVENT`) | VERIFIED | Unverändert seit Vorverifikation; Tests in diesem Lauf grün; live in 32-09 erneut `21 passed` je Instanz |
| 2 | Standard offen, Fälligkeit ohne undatierte, keine Deck-Karte, `degraded`, Termin-Werkzeuge byte-gleich | VERIFIED | `git diff --stat b40f7623 HEAD -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py src/mcp_connector/tools/calendar.py` leer; Gegenprobe auf `clients/caldav.py` zeigt 126 Zeilen (Diff wirkt). `caldav.py`, `ids.py`, `provider_map.py`, `test_caldav_bytes_pin.py` in 32-09 unverändert (`git diff --stat 669748e HEAD` leer), Byte-Pin-Test im Lauf grün. Die geänderte Discovery ist `build_task_discovery_body`, ein eigener Körper, nicht der Kalenderkörper |
| 3 | "fällig am 20." am 20., Felder wie Tasks-App, ohne `list` nur genau eine eigene Liste, nichts in fremdsichtbare Liste ohne Nennung | VERIFIED | Wie zuvor; dazu D-32-18 (W5) geschlossen. Offene Messung Gruppenfreigabe siehe Human Verification 1 |
| 4 | `tasks_read`/`fetch` gleiche Id, Provider-Treffer, Zeitmatrix, Fremdtext gekappt ohne Marker | VERIFIED | Wie zuvor; W2 geschlossen, `text` weiter durch `marks.without_marks` |
| 5 | 27 Werkzeuge, `EXPECTED_PUT_CALLS` 6, Budget, kein Werkzeug über 1400, Kanarie, Doku, alle Gates grün | VERIFIED (Code), Gate-Warnung | Selbst gelaufen: `tools/list: 18770 bytes, 27 tools, budget 22000`, größtes `tasks_create` 1380 (< `MAX_TOOL_BYTES = 1400`); `EXPECTED_PUT_CALLS = 6` (`test_no_destructive_calls.py:480`); alle lokalen Gates grün (unten). Rechnung mit neuem Wert: 18770 x 1,15 = 21585,5, auf 500 gerundet 22000, Budget bleibt richtig. CI 43471388563 auf 4b88a65: alle fünf Jobs success; Security scans rot durch neue Advisory (Human Verification 3) |

**Score:** 5/5 Erfolgskriterien verifiziert; W1 bis W5 geschlossen

### Required Artifacts (32-09)

| Artifact | Status | Details |
|----------|--------|---------|
| `src/mcp_connector/nextcloud/clients/tasks.py` | VERIFIED | `owner_suffix`, `shared_out`, `_shares_itself`, `clean_subline`; nichts davon im repr |
| `src/mcp_connector/tools/search.py` | VERIFIED | `held`, `_clean_task_sublines`, eine Discovery nur bei Bedarf |
| `src/mcp_connector/tools/chatgpt.py` | VERIFIED | `truncated`, `<feld>_floating`, Zeilenvermerk |
| `src/mcp_connector/tools/tasks.py` | VERIFIED | `_pick_target` mit zwei neuen Ablehnungen |
| `src/mcp_connector/server/reg_tasks.py` | VERIFIED | `query`-Text, `list`- und Werkzeugtext "a list others can see" |
| `tests/fixtures/caldav_home_shared_out.xml` | VERIFIED | genutzt von den `shared_out`-Tests |
| `tests/integration/test_tasks_live.py` | VERIFIED | Fälle `d-32-17-*`, `d-32-18-*`, Läufe in `raw/32-09-nc35.txt`, `raw/32-09-nc32.txt` |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `search._normalise` | `_clean_task_sublines` | Liste `held`, Aufruf nach der Schleife in `unified_search` | WIRED |
| `_clean_task_sublines` | `tasks_client.discover_task_lists`, `clean_subline` | `by_key[parts[0]]` aus der `task:`-Id | WIRED |
| `chatgpt.search` | `unified_search` | `text = hit["subline"]` | WIRED |
| `parse_task_home` | `TaskList.shared_out` | `_shares_itself(props)` nur für eigene Listen | WIRED |
| `_pick_target` | `shared_out` | Parent-Zweig und Einzellisten-Zweig | WIRED |
| `_fetch_task` | `read_task` | `description_truncated`, `<feld>_floating` | WIRED |

### Behavioral Spot-Checks (selbst gelaufen)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit + Contract, ohne Parallelisierung (freier RAM vorher 5,23 GB) | `uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib -p no:xdist` | 6399 passed, 35 skipped, Exit 0 (190 s) | PASS |
| Budget | `uv run --no-sync python scripts/check_tool_budget.py` | 18770 bytes, 27 tools, budget 22000; `tasks_create` 1380, `files_upload` 1377 | PASS |
| ruff | `ruff check .`, `ruff format --check .` | All checks passed; 392 files already formatted | PASS |
| pyright | `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run --no-sync pyright` | 0 errors, 0 warnings | PASS |
| vulture | `uv run --no-sync vulture src scripts vulture_whitelist.py` | keine Ausgabe, Exit 0 | PASS |
| Kalender unverändert | Diff gegen 32-BASE `b40f7623` (vier Dateien) plus Gegenprobe | leer / 126 Zeilen | PASS |

### CI zu 4b88a65

| Lauf | Ergebnis |
|------|----------|
| CI 43471388563 | success: unit, image, integration, canary-nc35, exapp (per `gh run view` bestätigt, headSha `4b88a656...`) |
| Security scans 43471388436 | failure: Job "pip-audit over the locked set", `opentelemetry-api 1.45.1 CVE-2026-126360`, Fix 1.45.2. CodeQL und REUSE success. `uv.lock` seit `dcda6c8` (Security dort grün) unverändert, `origin/main` pinnt dieselbe Version: neue Advisory, keine Regression von 32-09 |

### Requirements Coverage

TASK-01 bis TASK-09 bleiben SATISFIED (Begründung wie in der Vorverifikation). 32-09 stärkt TASK-06 (fremdsichtbar streng nach D-32-18) und TASK-09 (fetch-Vermerke). Keine verwaisten Anforderungen.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/check_tool_budget.py` | 116 bis 120 | Messkommentar nennt noch 18747 Bytes und `tasks_create` 1364; gemessen jetzt 18770 und 1380 | Info | Budget 22000 bleibt nach der Hausregel richtig (21585,5 aufgerundet); nur die Begründungszahl ist veraltet, nachzuziehen bei der nächsten Neuverankerung (Phase 33, TMOD-05) |

Keine `TBD`, `FIXME`, `XXX`, `TODO` oder `HACK` in den in 32-09 geänderten Quelldateien.

### Nicht gemessen (offen, Messplan 32-10 vorgeschlagen)

| Punkt | Bedeutung |
|-------|-----------|
| Gruppenfreigaben in beide Richtungen | Für D-32-18 relevant: ob `oc:invite` Gruppen-Principals als `oc:user` zeigt. `_shares_itself` zählt nur Kinder mit lokalem Namen `user`; erscheint eine Gruppenfreigabe anders, gälte eine an eine Gruppe geteilte eigene Liste als privat. Ebenso offen: Name und subline einer per Gruppe hineingeteilten Liste. Steht als offen in `docs/tasks-evidence.md` und 32-09-SUMMARY (Grenzen) |
| `recurring` live | nur Unit |
| Deckel 500 live | nur Unit |
| Besitzer mit Anzeigename ungleich Kennung | live war bobs Anzeigename gleich der Kennung (`raw/32-09-messung.txt` Nebenbefunde); Unit deckt den Fall über `owner-displayname` |

### Human Verification Required

### 1. Gruppenfreigaben (Messplan 32-10)

**Test:** Eigene Liste an eine Gruppe teilen sowie eine Liste per Gruppe hineinteilen, Discovery und `tasks_create` ohne `list` auf 35 und 32.
**Expected:** Hinausgeteilt per Gruppe gilt als fremdsichtbar (Ablehnung ohne PUT); hineingeteilt per Gruppe ohne Besitzer in Name und subline.
**Why human:** Docker und Owner-Freigabe nötig; bisher nicht gemessen.

### 2. recurring und Deckel 500 live (Messplan 32-10)

**Test:** Wiederkehrende Aufgabe anlegen und suchen; mehr als 500 Aufgaben blättern.
**Expected:** ein Treffer mit `recurring: true`; Ende bei 500 mit Notiz.
**Why human:** Live-Instanz nötig.

### 3. pip-audit rot

**Test:** Lock-Update `opentelemetry-api` 1.45.1 auf 1.45.2 entscheiden.
**Expected:** Security scans grün.
**Why human:** Abhängigkeitsentscheid außerhalb des Phasencodes; betrifft auch `main`.

### Gaps Summary

Keine Blocker im Code der Phase. Alle fünf Lücken W1 bis W5 sind am Code, an Unit-Tests mit Positiv- und Negativfällen und an Live-Läufen auf 35 und 32 geschlossen. Keine Regression: Kalender-Diff leer, `caldav.py` und Byte-Pin in 32-09 unberührt, `EXPECTED_PUT_CALLS` 6, 27 Werkzeuge, größtes 1380 Bytes unter 1400, Budget 22000; kein Besitzername und kein `_shared_by_` in Antworten, Links oder subline (Unit und live); der Fix 39c1be9 deckt die subline ohne Fälligkeit und ist per RED-Test (e672187) und live belegt.

Status `human_needed`, nicht `passed`: Gruppenfreigaben sind für D-32-18 ungemessen, `recurring` und Deckel 500 nur Unit (Messplan 32-10 vorgeschlagen), Security-Gate auf 4b88a65 rot durch neue Advisory (der CI-Lauf selbst ist grün). Phase 32 wird auf Anweisung der Hauptsitzung erst nach 32-10 abgehakt; ROADMAP und STATE bleiben unverändert.

---

_Verified: 2026-11-13T17:25:00Z_
_Verifier: Claude (gsd-verifier)_

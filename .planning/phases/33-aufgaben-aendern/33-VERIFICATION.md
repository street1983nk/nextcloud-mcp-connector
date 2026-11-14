---
phase: 33-aufgaben-aendern
verified: 2026-11-14T12:00:00Z
status: passed
score: 5/5 Erfolgskriterien verifiziert (7/7 Requirements, 16/16 Entscheide)
overrides_applied: 0
deferred:
  - truth: "READMEs nennen beim Verschieben keine Ausnahme für tasks_move (README.md:52 'No user-visible moving', README.de.md:62 'Kein Verschieben', README.fr.md:63 'Aucun déplacement')"
    addressed_in: "Phase 34"
    evidence: "DOC-05: Zusage überall präzisiert, 'dazu das Verschieben in eine andere Liste (E14)', drei READMEs ausdrücklich genannt"
  - truth: "Admin-Doku: occ app_api:app:config:set braucht --update-only, um den vorhandenen Schalter tasks_update umzustellen"
    addressed_in: "Phase 34"
    evidence: "Phase 34 Ziel: Doku in drei Sprachen sagt den Endstand; 33-10-SUMMARY 'Admin-Doku (Phase 34)'"
---

# Phase 33: Aufgaben ändern, Verifikationsbericht

**Phase Goal:** Ein Assistent kann eine einzelne Aufgabe abhaken, wieder öffnen, in den genannten Feldern ändern und in eine andere Liste verschieben, ohne je eine zwischenzeitliche Änderung zu überschreiben und ohne etwas außer den genannten Feldern zu verlieren; kein Löschen.
**Verified:** 2026-11-14 (HEAD f464455, Branch plan/v1.8-tasks-080)
**Status:** passed
**Re-verification:** Nein, Erstprüfung

## Eigene Läufe des Prüfers

| Prüfung | Ergebnis |
| ------- | -------- |
| `uv run --no-sync pytest -q -p no:xdist tests/unit tests/contract` | Exit 0 |
| `scripts/check_tool_budget.py` | `tools/list with every switch on: 22198 bytes, 31 tools, budget 26000`; größtes Werkzeug tasks_create 1380, tasks_update 1324 (< 1400); Standard 18770 / 27 |
| `ruff check .` / `ruff format --check .` | grün / 403 Dateien formatiert |
| `pyright src` (latest) | 0 errors, 0 warnings |
| Docker/Live | nicht erneut gefahren (Vorgabe); Live-Beleg aus raw/33-10-nc35.txt und raw/33-10-nc32.txt gezählt und gelesen |

## Observable Truths (ROADMAP-Erfolgskriterien)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Abhaken wie die Tasks-App, Wiederöffnen mit demselben Werkzeug, schon erledigt = Erfolg ohne PUT, Unteraufgaben mit abgehakt | VERIFIED | `tools/tasks.py:1429-1439` Felder STATUS/PERCENT-COMPLETE/COMPLETED bzw. NEEDS-ACTION und Entfernen, LAST-MODIFIED+DTSTAMP, kein SEQUENCE (D-33-08); `:1594-1595` Zielzustand -> `already: True` ohne Schreiben; `:1604-1614` Nachfahren in Nachordnung, erledigte übersprungen, abgebrochene `left_alone` (D-33-14); Wiederöffnen nur die genannte (D-33-05). Live: `aendern-abhaken`, `aendern-wiederoeffnen`, `aendern-schon-erledigt`, `aendern-kinder` ok auf nc35 (2 Läufe) und nc32 (3 Läufe) |
| 2 | Nach tasks_update unterscheidet sich das Objekt genau um die genannten Felder plus Pflegefelder; VALARM, X- und Rest bleiben; ohne Unterschied kein Schreiben | VERIFIED | Zeilen-Editor `tools/ics_edit.py:279-331` kopiert jede unberührte Zeile roh, `verify` `:364-374` prüft UID und Sollwerte vor dem PUT; `tools/tasks.py:1891-1900` `changed` leer -> Rückgabe ohne PUT; HTML-Fassung als benannte Ausnahme `:1912-1917` (D-33-13); Rundlauf über 16 Tasks-App-Fixtures `tests/unit/test_ics_edit.py` (APP_PAIRS, MATRIX). Live: `aendern-reich` (valarm_gleich, vtimezone_gleich, x_zeilen_gleich, unberuehrte_zeilen_woertlich), `aendern-ohne-unterschied` (kein_put) ok |
| 3 | Veraltete ETag abgelehnt und Objekt unverändert; nur lesende Freigabe kann weder abhaken, ändern noch verschieben (auch unter Impersonation); wiederkehrend und Deck unerreichbar | VERIFIED | `_read_for_change` `tools/tasks.py:1517-1549` (read only, ETag-Vergleich, wiederkehrend, mehrere VTODO); If-Match immer über `dav.normalize_etag` (`clients/dav.py:943-962`, lehnt `*`, leer, W/, Listen ab); 412 -> ConflictError ohne Wiederholung `clients/tasks.py:629-647`; Deck-Schlüssel vor jeder Anfrage `tools/tasks.py:1460-1475`, Deck-Ziel `:1957-1964`. Live je Werkzeug (complete/update/move): `aendern-veraltet`, `aendern-nur-lesend`, `aendern-wiederkehrend`, `aendern-deck` ok, dazu Server-Gegenprobe `aendern-nur-lesend-server` (PUT 404, MOVE 404); `KONTROLLE ... mode=appapi`, Credential APP_SECRET, kein App-Passwort |
| 4 | Verschieben in eine ausdrücklich genannte beschreibbare Liste, gleiche UID, kein belegtes Ziel überschrieben, Unteraufgaben ziehen mit; kein Löschen | VERIFIED | `move_task` `tools/tasks.py:2053-2166`: Ziel per Name/Schlüssel aufgelöst, nie positionsabhängig, beschreibbar (`:1967-1985`); Vorprüfung Name und UID im Ziel (`:2019-2045`); Nachfahren zuerst (`run_chain`); `move_todo` `clients/tasks.py:555-586` mit `Overwrite: F` + `If-Match`, nur 201 ist Erfolg, 204 laut gemeldet. Kein DELETE im Code (Destruktiv-Gate). Live: `verschieben-genannt` (gleiche_uid, text_gleich), `verschieben-belegt` (quelle_gleich, ziel_gleich), `verschieben-kinder` ok |
| 5 | Ehrliche Annotationen, Audit je Aufruf, PUT und MOVE je genau eine Aufrufstelle mit Gegenprobe, Budget aus Endstand, alle Gates grün | VERIFIED | `MODIFY_EXISTING` `server/__init__.py:117-122` (destructive_hint True, idempotent_hint True, D-33-12); Audit-Erlaubnisliste `audit/allowlist.py:69-74` ohne summary/description; `test_audit_surface.py:386-444` echte Aufrufe mit Schalter an; `test_no_destructive_calls.py:500` `EXPECTED_PUT_CALLS = 7`, MOVE-Pin `:825-977` mit `MOVE_HOMES` (dav.finish_chunked_upload, tasks.move_todo) und gepflanzten Umgehungen `:1043ff`; Budget `scripts/check_tool_budget.py:168-183` (22198 + 15 % -> 26000); Live `AUDIT ... anzahl=1` je Werkzeug, `KANARIE nc35 passed=4 schalter=an` |

**Score:** 5/5

## Required Artifacts

| Artifact | Status | Details |
| -------- | ------ | ------- |
| `src/mcp_connector/tools/tasks.py` (complete/update/move, Kette) | VERIFIED | substanziell (Zeilen 1135-2166), über reg_tasks.py verdrahtet |
| `src/mcp_connector/tools/ics_edit.py` | VERIFIED | 374 Zeilen, von complete_task und update_task genutzt |
| `src/mcp_connector/nextcloud/clients/tasks.py` (`get_todo`, `put_existing_todo`, `move_todo`) | VERIFIED | je eine HTTP-Aufrufstelle |
| `src/mcp_connector/server/reg_tasks.py` | VERIFIED | drei Werkzeuge nur unter `config.tasks_update_enabled()` (`:106`) |
| Schalterkette `NC_MCP_TASKS_UPDATE` | VERIFIED | `config.py:52,740-764` (ab Werk aus, Unbekanntes = aus), `entry_exapp.py:678-679`, `exapp/config_values.py:141`, `exapp/admin_settings.py:221-222`, `exapp/ui/strings.py:818-826`, `appinfo/info.xml:571`, Server-Instruktion `server/__init__.py:72-77` |
| READMEs (Rechtetabelle Stufe "modify") und drei Changelogs | VERIFIED | README.md:86-88, README.fr.md:100-102, README.de.md analog; CHANGELOG*.md je 2 Treffer |

## Key Links

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| reg_tasks.tasks_complete/update/move | tools/tasks.complete_task/update_task/move_task | direkter Aufruf | WIRED |
| complete_task, update_task | clients/tasks.put_existing_todo | If-Match auf normalisierte ETag | WIRED |
| move_task | clients/tasks.move_todo | run_chain-Write | WIRED |
| tasks_read | ETag | `get_todo` ETag aus derselben GET-Antwort | WIRED |
| Admin-Formular / info.xml | os.environ NC_MCP_TASKS_UPDATE -> Registrierung | entry_exapp | WIRED (live: WERKZEUGE anzahl=30 an, 27 aus) |

## Requirements Coverage

| Requirement | Status | Evidence |
| ----------- | ------ | -------- |
| TMOD-01 | SATISFIED | Schreibschiene, If-Match nie `*`, 412 ohne Wiederholung, Schalter ab Werk aus, eine PUT-Aufrufstelle, create-only-Weg unverändert (TASK-01-Diff 0 Zeilen laut 33-10) |
| TMOD-02 | SATISFIED | Zeilen-Editor + Fixture-Rundlauf + Live `aendern-reich` |
| TMOD-03 | SATISFIED | complete_task, null PUT im Zielzustand (`already`), Kinder mit |
| TMOD-04 | SATISFIED | Felder und Leeren nach D-33-15, Prüfungen wie tasks_create, Elternaufgabe gleiche Liste/kein Nachfahre (`:1803-1822`, `:1871-1879`), kein Status-/Listenparameter |
| TMOD-05 | SATISFIED | Annotationen, Audit, Kanarie, Budget 26000 aus Endstand, kein Werkzeug > 1400 |
| TMOD-06 | SATISFIED | Live nc35 und nc32, je ohne und mit Tasks-App 0.18.1, Impersonation, BASELINE gleich |
| TMOD-08 | SATISFIED | move_task, MOVE-Pin |
| TMOD-07 | Out of Scope | Owner 12.11.2026; kein DELETE im Code |

## Entscheide

D-33-00a bis D-33-00d, D-33-01 bis D-33-15 im Code wiedergefunden; D-33-06, D-33-07, D-33-14 durch ENTSCHEID-Zeilen in raw/33-01-messung.txt gedeckt (wiederoeffnen_kinder=bleiben, entfernen_*, cancelled_kette=unberuehrt, cancelled_direkt), D-33-10 durch `MESSWERT chain_cap=50` (33-01c, max. 3,688 s).

## Anti-Patterns / Befunde

| Datei | Zeile | Befund | Schwere |
| ----- | ----- | ------ | ------- |
| `src/mcp_connector/tools/tasks.py` | 1534 | Veraltete ETag als `ConflictError` ohne eigenen `reason`, Audit schreibt `rejected` mit Grund `unspecified` | Info (Ablehnung selbst korrekt; nur Audit-Feinheit) |
| `README.md` / `README.de.md` / `README.fr.md` | 52 / 62 / 63 | "kein Verschieben" ohne Ausnahme tasks_move | deferred, Phase 34 DOC-05 |
| Phase-32-Suche (`tools/tasks.py:64` `PER_LIST_TIMEOUT = 2.0`) | - | NC 32 mit Tasks-App, Lauf 1: nur lesbare geteilte Liste fehlte in der ersten Suche nach Container-Neustart (`DEVIATION ro: None`), Lauf 2 grün ohne Codeänderung | Warning, nicht Phase 33 (Lesepfad Phase 32); Owner-Entscheid "vor 0.8.0 klären" im eigenen Folgeplan |

Keine TBD/FIXME/XXX, keine Stubs in den Phase-33-Dateien gefunden.

## Human Verification Required

Keine für Phase 33. Der Live-Beweis ist in den Rohprotokollen belegt (nc35: 56 FALL-Zeilen, nc32: 84, alle `ergebnis=ok`).

## Gaps Summary

Keine Lücke in Phase 33. Offene Punkte außerhalb des Phasenumfangs: (1) Kaltstart-Suche NC 32 (Phase-32-Code, Folgeplan vor 0.8.0 per Owner-Entscheid), (2) README-Aussage zum Verschieben und (4) `--update-only` in der Admin-Doku gehören zu Phase 34, (3) Audit-Grund `unspecified` bei veralteter ETag ist eine kosmetische Lücke im Audit, kein Verstoß gegen TMOD-01.

---

_Verified: 2026-11-14_
_Verifier: Claude (gsd-verifier)_

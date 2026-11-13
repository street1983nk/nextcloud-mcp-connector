# Phase 33: Aufgaben ändern - Pattern Map

**Mapped:** 2026-11-13
**Files analyzed:** 46 (neu oder geändert, Sprachvarianten als eine Zeile gezählt)
**Analogs found:** 43 / 46 (ohne echtes Vorbild: Editor auf logischen Zeilen `tools/ics_edit.py`, Kettenlogik über Nachfahren in Nachordnung, Gate-Begriff "optionale Werkzeuge" in Audit und Klassen)

Leitvorbild ist `files_update` (Phase 15/Issue #9): Schalter `NC_MCP_FILES_UPDATE`, ETag als Pflichtparameter, `If-Match`-PUT in `dav.update_file`, eigene Annotationsklasse, Registrierung hinter `if config.files_update_enabled():`. Für die Aufgabenseite ist Phase 32 das Vorbild (`clients/tasks.py`, `tools/tasks.py`, `reg_tasks.py`), für das `MOVE` die Chunk-Montage in `dav.py`, für das AST-Gate des `MOVE` das MKCOL-Gate aus Phase 31. Alle Zeilenangaben sind am Worktree `tasks-080` auf HEAD `0e7427c` gelesen, nicht aus 33-RESEARCH.md übernommen; Abweichungen stehen am Ende.

## File Classification

Planzuordnung nach dem Vorschlag in 33-RESEARCH.md ("Empfohlener Planschnitt").

| Neue/geänderte Datei | Plan | Rolle | Data Flow | Nächstes Vorbild | Match |
|---|---|---|---|---|---|
| `scripts/tasks_measure.py` (Blöcke M-1 bis M-4) oder neues `scripts/tasks_modify_measure.py` | 33-01 | Script (Messprogramm) | batch, request-response | `scripts/tasks_measure.py`: `main` Z. 2247-2303, `derive_budget` Z. 365-368, `NO_TRASHBIN` Z. 113, `PHP_BASELINE` Z. 171, `recurring_todo` Z. 446 | exact |
| `docs/tasks-evidence.md` oder Nachtrag `docs/spike-tasks.md` | 33-01, 33-07 | Doku (Beleg) | kein | `docs/tasks-evidence.md`: Gliederung `## Measurements before the build` Z. 71, `## Nextcloud 35 with the Tasks app` Z. 276, `## Whole chain through the installed app` Z. 377, `## Not measured` Z. 227 | exact |
| `tests/fixtures/tasks_app/*.ics` (neu aus M-2) und `PROVENANCE.md` | 33-01 | Fixture | file-I/O | `tests/fixtures/tasks_app/PROVENANCE.md` Z. 1-33 (Tabelle mit Rohdatei und sha256) | exact |
| `src/mcp_connector/config.py` (`ENV_TASKS_UPDATE`, `tasks_update_enabled`) | 33-02 | Config | kein | dieselbe Datei Z. 51, Z. 716-736 | exact |
| `src/mcp_connector/entry_exapp.py` | 33-02 | Config (Start) | kein | dieselbe Datei Z. 662-670 | exact |
| `src/mcp_connector/exapp/config_values.py` | 33-02 | Config | kein | `CONFIG_KEYS` Z. 118-127, `KEY_TO_ENV` Z. 131-140, `SWITCH_KEYS` Z. 147-149 | exact |
| `src/mcp_connector/exapp/admin_settings.py` | 33-02 | Config (Formular) | kein | Entpacken Z. 124-133, Checkbox Z. 211-217 | exact |
| `src/mcp_connector/exapp/ui/strings.py` | 33-02 | Config (Texte) | kein | `__all__` Z. 47-48, Label/Beschreibung Z. 800-814 | exact |
| `appinfo/info.xml` | 33-02 | Config (Manifest) | kein | `<variable>` `NC_MCP_FILES_UPDATE` Z. 565-569 | exact |
| `src/mcp_connector/nextcloud/clients/tasks.py` (`TodoObject.etag`, `get_todo` mit ETag, `put_existing_todo`, `move_todo`, Prüfer, Docstring) | 33-02 | Client | request-response (GET, PUT, MOVE, REPORT) | `dav.update_file` Z. 1038-1073, `dav._check_update` Z. 965-999, `dav.finish_chunked_upload` Z. 1212-1240, `caldav.put_new_object` Z. 391-419, eigenes `get_todo` Z. 472-482, `query_todos` Z. 432-469, `_check` Z. 485-532 | exact (PUT), role-match (MOVE) |
| `src/mcp_connector/tools/ics_edit.py` (neu) | 33-02 | Utility (reine Funktionen) | transform | nur Teilvorbilder: `tools/tasks._build_todo` Z. 1032-1086 (Werte über icalendar), `_read_todo` Z. 133-154 (Vor- und Nachprüfung), `_parents` Z. 224-233 (RELTYPE-Regel) | partial |
| `tests/unit/test_ics_edit.py` (neu) | 33-02 | Test (Rundlauf) | transform | `tests/unit/test_tasks_create.py` Z. 44, 65-86 (`FIXTURES`, `fixture`, `vtodo`), Positivkontrolle nach `test_the_put_gate_flags_each_planted_bypass` | role-match |
| `tests/unit/test_tasks_client.py` | 33-02 | Test (Unit) | request-response | dieselbe Datei (Discovery, Statuszweige, create-only-PUT) plus `Store` aus `test_tasks_create.py` Z. 156-219 | exact |
| `src/mcp_connector/tools/tasks.py` (`read_task` mit `etag`) | 33-02 | Service/Tool-Logik | request-response | dieselbe Datei `read_task` Z. 554-644 | exact |
| `tests/unit/test_tasks_read.py` | 33-02 | Test (Unit) | request-response | dieselbe Datei | exact |
| `tests/unit/test_chatgpt_fetch.py` (nur Gegenprobe: `fetch` trägt keine ETag) | 33-02 | Test (Unit) | request-response | `tools/chatgpt.py` `_fetch_task` Z. 544-567 | exact |
| `src/mcp_connector/server/__init__.py` (Klasse `MODIFY_EXISTING`, Instruktionssatz) | 33-02, 33-06 | Config (Server) | kein | Instruktion Z. 59-74, Klassen Z. 77-101, `__all__` Z. 42-51 | exact |
| `tests/contract/test_no_destructive_calls.py` | 33-02 | Contract-Gate (AST) | kein | `CHUNK_ASSEMBLY_MOVE` Z. 139-142, `_violations` Z. 413-437, `test_file_updates_keep_create_and_compare_and_swap_puts_distinct` Z. 450-466, `EXPECTED_PUT_CALLS` Z. 478-480, `_HONEST_PUTS` Z. 588-591, MKCOL-Gate Z. 606-716 | exact |
| `tests/contract/test_tool_surface.py` | 33-02 bis 33-06 | Contract-Gate | kein | `CREATE_TOOLS` Z. 74-87, `IDEMPOTENT_CREATE_TOOLS` Z. 89-93, `_check_annotations` Z. 757-789, Gegenprobe Z. 816-837, README-Tabelle Z. 877-905, Schalter-Test Z. 943-969 | exact |
| `tests/contract/test_audit_surface.py` | 33-02 | Contract-Gate | kein | `_measured_surface` Z. 43-47, Mengen-Tests Z. 50-83; Subprozess-Muster `test_tool_bundles._run` Z. 48-81 | role-match |
| `tests/contract/tool_classes.py`, `tests/contract/test_tool_classes.py` | 33-02 bis 33-05 | Test-Tabelle, Contract-Gate | kein | `UNAFFECTED` Z. 89-130, `freeze_findings` Z. 185-226, `probe_tool` Z. 229-244; `TOTAL = 27` Z. 20 | exact |
| `tests/contract/test_tool_bundles.py` | 33-02 bis 33-05 | Contract-Gate | kein | `BUNDLE_TOOLS["tasks"]` Z. 45, `test_the_optional_update_tool_goes_off_with_the_files_bundle` Z. 135-147 | exact |
| `scripts/check_tool_budget.py` | 33-02, 33-06 | Script (Gate) | kein | Messzeilen Z. 116-124, `main` Z. 161-198 | exact (Messung mit Schaltern: neu) |
| `src/mcp_connector/tools/tasks.py` (`complete_task` samt Kette) | 33-03 | Service/Tool-Logik | request-response, batch (Kette) | `create_task` Z. 726-820, `read_task` Z. 554-644, `_search_one` Z. 384-423, `_parse_objects` Z. 426-448, `_status` Z. 187-195 | role-match |
| `src/mcp_connector/tools/tasks.py` (`update_task`) | 33-04 | Service/Tool-Logik | request-response | `create_task` Z. 754-762 (Prüfungen), `_parse_task_time` Z. 837-850, `_check_times` Z. 853-869, `_check_priority` Z. 881-888, `_clean_tags` Z. 891-900, `_parse_parent` Z. 903-917, `_parent_uid` Z. 1016-1029; `tools/files.update` Z. 1183-1250 | role-match |
| `src/mcp_connector/tools/tasks.py` (`move_task`) | 33-05 | Service/Tool-Logik | request-response, batch | `_resolve_list` Z. 345-369, `_pick_target` Z. 979-984 (writable), `read_task` Z. 564-580 (Deck vorab) | role-match |
| `src/mcp_connector/server/reg_tasks.py` | 33-03 bis 33-05 | Registrierung | request-response | `server/reg_files.py` Z. 264-291, dieselbe Datei Z. 54-103 | exact |
| `src/mcp_connector/audit/allowlist.py` | 33-03 bis 33-05 | Config | kein | `PARAM_ALLOWLIST` Z. 45-75, `FORBIDDEN_PARAMS` Z. 23-34 | exact |
| `vulture_whitelist.py` | 33-03 bis 33-05 | Config | kein | Werkzeugliste ab Z. 19 (`files_update` Z. 24) | exact |
| `tests/unit/test_tasks_modify.py` (neu, oder je Werkzeug eine Datei) | 33-03 bis 33-05 | Test (Unit) | request-response | `tests/unit/test_tasks_create.py` Z. 1-298 (respx, `Store`, `REFUSED`, "vor jeder Anfrage") | exact |
| `tests/unit/test_config.py`, `test_exapp_config_values.py`, `test_exapp_admin_settings.py`, `test_exapp_entry.py`, `test_exapp_lifecycle.py`, `test_exapp_env_setup.py` | 33-02 | Test (Unit) | kein | je die `files_update`-Fälle: `test_config.py` Z. 373-419, `test_exapp_admin_settings.py` Z. 342-354, `test_exapp_entry.py` Z. 1854-1928, `test_exapp_lifecycle.py` Z. 728-788, `test_exapp_env_setup.py` Z. 2505 | exact |
| `tests/unit/test_exapp_tasks_update_switch.py` (neu) | 33-02 | Test (Subprozess) | kein | `tests/unit/test_exapp_files_update_switch.py` Z. 55-121 | exact |
| `tests/integration/test_canary.py` | 33-06 | Test (Live) | kein | `EXPECTED_TOOLS = 27` Z. 69, `WRITE_KINDS` Z. 86-93, `TASK_TOOLS` Z. 96, `MUST_REFUSE` Z. 99, `plan()` Z. 243-249, Deck-Prüfung Z. 334-343, `sweep` Z. 387-410 | exact |
| `tests/integration/canary_world.py` | 33-06 | Test-Harness | kein | Aufgabe der Welt `world.task_id` (wie in `plan()` genutzt) | exact |
| `scripts/acceptance_all_tools.py` | 33-06 | Script | request-response | `_tasks` Z. 445-501, `TASKS_MORE_THAN_ONE` Z. 440-442 | exact |
| `README.md`, `README.de.md`, `README.fr.md` | 33-06 | Doku | kein | Rechtetabelle (Stufe `conditional-update` für `files_update`), gegen `test_tool_surface.py` Z. 877-905 | exact |
| `CHANGELOG.md`, `.de.md`, `.fr.md` | 33-06 | Doku | kein | `## [Unreleased]`, `### Added` | exact |
| `.planning/REQUIREMENTS.md` (TMOD-05 nachziehen, D-33-12) | 33-02 | Doku | kein | Wortlaut TMOD-05 | exact |
| `tests/integration/test_tasks_live.py` | 33-07 | Test (Live, Impersonation) | request-response | `refusal` Z. 895-903, `raw_object` Z. 923-927, `list_objects` Z. 283, `test_a_read_only_shared_list_is_refused_before_any_put` Z. 1093-1105, Server-Gegenprobe Z. 1108-1125, `run()` mit BASELINE Z. 732-803 | exact |
| `scripts/tasks_chain_evidence.py` | 33-07 | Script (Beleg) | request-response | `TASK_TOOLS` Z. 48, Kopf Z. 1-34 | exact |

## Pattern Assignments

### `src/mcp_connector/config.py` (Plan 33-02, D-33-00d, D-33-01)

**Analog:** dieselbe Datei, Konstante Z. 51 und Lesefunktion Z. 716-736. Wörtlich nachbauen, nur Name und Logtext ändern:
```python
def files_update_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Whether the files_update tool is available at all (Issue #9).

    The shipped state is off. An unset, blank or unrecognised value therefore keeps
    the capability disabled. Only an explicitly understood true value enables it.
    """
    source = os.environ if env is None else env
    value = (source.get(ENV_FILES_UPDATE) or "").strip().lower()
    if not value:
        return False
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    logger.warning(
        "%s is neither on nor off, so files_update stays disabled (understood are %s and %s).",
        ENV_FILES_UPDATE,
        ...
    )
    return False
```
Neu: `ENV_TASKS_UPDATE = "NC_MCP_TASKS_UPDATE"` direkt unter Z. 51, `tasks_update_enabled()` direkt unter Z. 736. Tests nach `tests/unit/test_config.py` Z. 373-419 (Name, An-Schreibweisen, Aus-Schreibweisen, Groß/Klein und Leerraum, fehlend, leer, unbekannt, Prozessumgebung).

---

### `src/mcp_connector/entry_exapp.py` (Plan 33-02)

**Analog:** Z. 662-670. Ein zweiter Block gleicher Form direkt darunter, vor `config.exapp_settings(resolved)` Z. 672 und damit vor `build_exapp_app`:
```python
    if config.ENV_FILES_UPDATE in resolved:
        os.environ[config.ENV_FILES_UPDATE] = resolved[config.ENV_FILES_UPDATE]
```
Reihenfolge-Pin: `tests/unit/test_exapp_entry.py` Z. 1896-1928 sucht `os.environ[config.ENV_FILES_UPDATE] =` im Quelltext und prüft `resolved < files_update < built`; denselben Pin für `ENV_TASKS_UPDATE` anlegen. Fälle "gespeicherter Wert gewinnt" Z. 1854-1887 spiegeln.

---

### `src/mcp_connector/exapp/config_values.py`, `admin_settings.py`, `ui/strings.py`, `appinfo/info.xml` (Plan 33-02)

**Analog:** die `files_update`-Einträge.
- `config_values.py`: `"tasks_update"` hinten an `CONFIG_KEYS` (Z. 118-127), `"tasks_update": config.ENV_TASKS_UPDATE` in `KEY_TO_ENV` (Z. 131-140), in `SWITCH_KEYS` (Z. 147-149). Kommentar über `SWITCH_KEYS` zählt die Schalter ("Five since phase 18"), mitziehen.
- `admin_settings.py`: Das Tupel-Entpacken Z. 124-133 bricht mit `ValueError`, wenn `CONFIG_KEYS` wächst; um `tasks_update_field` erweitern. Checkbox nach Z. 211-217:
```python
            {
                "id": files_update_field,
                "title": strings.ADMIN_FIELD_FILES_UPDATE_LABEL,
                "description": strings.ADMIN_FIELD_FILES_UPDATE_DESCRIPTION,
                "type": "checkbox",
                "default": False,
            },
```
- `strings.py`: `ADMIN_FIELD_TASKS_UPDATE_LABEL`, `ADMIN_FIELD_TASKS_UPDATE_DESCRIPTION` nach Z. 800-814 (englisch, ASCII; Satz "A change takes effect after you disable and enable this app again." übernehmen), in `__all__` Z. 47-48 alphabetisch.
- `info.xml`: `<variable>` nach Z. 565-569, Text nach dem Muster "Off unless set to on. When enabled, ...". Die Zeile `Valid names: ...` Z. 573 bleibt, es kommt kein Bundle hinzu.
- Tests: `test_exapp_config_values.py` Z. 95, 109, 162; `test_exapp_admin_settings.py` Z. 165 und Z. 342-354 (Checkbox, `default is False`, kein `sensitive`); `test_exapp_lifecycle.py` Z. 728-788; `test_exapp_env_setup.py` Z. 2505.

---

### `src/mcp_connector/nextcloud/clients/tasks.py` (Plan 33-02, TMOD-01, TMOD-08)

**Analog PUT:** `dav.update_file` (`clients/dav.py` Z. 1038-1073), Kopf als Literal-Dict, damit `_usable_precondition` ihn lesen kann:
```python
    response = await client.put(
        files_url(creds, target),
        content=data,
        headers={
            "If-Match": etag,
            "Content-Type": content_type,
        },
        auth=creds.auth(),
    )
    _check_update(response, target)
    ...
    new_etag = response.headers.get("oc-etag", "") or response.headers.get("etag", "")
```
URL wie `caldav.put_new_object` (`caldav.py` Z. 408-413): `caldav.object_url(creds, task_list.uri, object_name)`, `Content-Type: text/calendar; charset=utf-8`. Neue ETag nur aus `etag` (CalDAV sendet kein `oc-etag`); leer heißt "Server hat den Text verändert", Werkzeug meldet dann keine ETag (Pitfall 10).

**Analog Statusprüfer:** `dav._check_update` Z. 965-999 (412/404 als `ConflictError`, dann 403, 5xx, unerwartet). Für Aufgaben getrennt halten: 404 nach erfolgreichem Lesen heißt "nicht gefunden oder kein Schreibrecht" (nur lesbare Freigabe antwortet 404, Docstring Z. 34-36), nie "gelöscht". Formulierungen nur mit Listenname, nie URI (Z. 488-490). Kein zweiter Versuch ("No retry, ever", Z. 486).

**Analog MOVE:** `dav.finish_chunked_upload` Z. 1212-1240:
```python
    response = await client.request(
        "MOVE",
        f"{uploads_url(creds, upload_id, path=target)}/.file",
        headers={
            "Destination": files_url(creds, target),
            "OC-Total-Length": str(total_size),
            "Overwrite": "F",
        },
        auth=creds.auth(),
    )
    # As with a direct PUT, only 201 proves that this was a new destination. A 204
    # means the server ignored Overwrite: F and must not be reported as a safe create.
    if response.status_code in (200, 204):
        _check_write(response, target)
```
Für `move_todo`: `Destination` aus `caldav.object_url(creds, target.uri, object_name)`, Literal `"Overwrite": "F"`, `"If-Match": etag`. Die Zeile `"MOVE",` muss als exakter Zeilentext stehen (Gate `_violations` Z. 424 vergleicht `text.strip() == '"MOVE",'`).

**Analog ETag aus GET:** eigenes `get_todo` Z. 472-482 gibt heute nur `response.content` zurück. Erweitern auf `(content, response.headers.get("etag", ""))` oder kleinen Datentyp; Aufrufer `tools/tasks.py` Z. 583, 1021, 1094 nachziehen. `TodoObject` Z. 122-127 um `etag: str = ""` erweitern; `query_todos` Z. 456-468 liest `getetag` aus `_collect_props(entry)` wie heute `calendar-data` (Z. 464), der Körper fragt ihn schon ab (`_todo_query_root` Z. 424).

**ETag-Prüfung vor jeder Anfrage:** `dav.normalize_etag` Z. 943-962 wiederverwenden, nicht nachbauen.

**Docstring Z. 1-39 nachziehen:** Z. 6-7 sagt "only calls the URL builders and the one create-only writer of ``caldav.py``"; neu: eigener überschreibender `PUT` mit `If-Match` und eigenes `MOVE` mit `Overwrite: F` in diesem Modul, `caldav.py` bleibt unberührt (TASK-01, `tests/unit/test_caldav_bytes_pin.py`). Keine Teilstrings `MOVE`, `DELETE`, `COPY`, `PROPPATCH` in Bezeichnern oder Texten außer der einen Zeile (Pitfall 1).

---

### `src/mcp_connector/tools/ics_edit.py` (neu, Plan 33-02, TMOD-02)

**Kein echtes Vorbild** im Repo: es gibt keinen Editor auf logischen Zeilen. Teilvorbilder:
- Neue Zeilen über icalendar, nie von Hand: `_build_todo` Z. 1032-1086 (Docstring Z. 1044-1050 "Never by string concatenation"); Skizze `new_lines` in 33-RESEARCH.md Pattern 2, aber mit `to_ical(sorted=False)` (anders als `_build_todo` Z. 1086, das `ics.to_ical()` ohne Argument ruft; für ein neues Objekt egal, für Zeilen eines bestehenden Pflicht).
- Elternbezug nur bei fehlendem `RELTYPE` oder `PARENT` (Z. 224-233):
```python
        reltype = str(params.get("RELTYPE", "PARENT")).strip().upper()
```
- Vor- und Nachprüfung über `_read_todo` Z. 133-154 (parst, Master-VTODO), ergänzt um "genau ein VTODO, gleiche UID".
- Keine Abhängigkeit auf `tools/tasks.py` nötig; reine Funktionen, damit `test_ics_edit.py` ohne Netz läuft. Modulgrenzen-Gate `tests/contract/test_module_boundaries.py` beachten.

---

### `tests/unit/test_ics_edit.py` (neu, Plan 33-02)

**Analog Fixtures:** `tests/unit/test_tasks_create.py` Z. 44 und 65-66:
```python
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
```
Achtung: `read_text` macht aus CRLF ein LF (universelle Zeilenenden); für den Byte-Beweis `read_bytes()` nehmen (Fixtures sind CRLF, PROVENANCE Z. 3-6).

**Analog Positivkontrolle:** Muster "geplantes Fehlverhalten muss gemeldet werden" aus `test_no_destructive_calls.py` Z. 594-603 (`_PLANTED_PUTS` gegen `_HONEST_PUTS`, dieselbe Prüffunktion für beide). Für TMOD-02: ein absichtlich falscher Editor, der eine `X-`Zeile fallen lässt, muss in beiden Beweisen genau diese Zeile melden.

---

### `src/mcp_connector/tools/tasks.py`, `read_task` mit ETag (Plan 33-02, D-33-03, D-33-04)

**Analog:** dieselbe Funktion Z. 554-644. Die ETag kommt aus dem einen `GET` Z. 583; Feld neben `id` in `result` (Z. 606) oder nach `list` (Z. 626). `fetch` übernimmt nur benannte Felder (`tools/chatgpt.py` `_fetch_task` Z. 544-567), dort keine Änderung; Test in `test_chatgpt_fetch.py`, dass `etag` nicht in `fetch` erscheint, ist eine sinnvolle Gegenprobe. Budget-Mehrbytes nur aus der Werkzeugbeschreibung in `reg_tasks.py` Z. 60 messen.

---

### `src/mcp_connector/tools/tasks.py`, `complete_task`, `update_task`, `move_task` (Pläne 33-03 bis 33-05)

**Analog Gerüst:** `create_task` Z. 726-820. Alle Prüfungen vor der ersten Anfrage, dann Discovery, dann Ziel, dann ein Schreibzugriff:
```python
    if not summary or not summary.strip():
        raise _refused("A task needs a summary.", "Give a short title, for example 'Angebot'.")
    zone = _task_zone(timezone)
    due_value = _parse_task_time(due, "due")
    start_value = _parse_task_time(start, "start")
    _check_times(due_value, start_value, zone)
    _check_priority(priority)
    categories = _clean_tags(tags)
    parent_key, parent_object = _parse_parent(parent)
    ...
    lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
```
**Analog Auflösen der Id und Deck vorab:** `read_task` Z. 564-580:
```python
    kind, parts = ids.parse(task_id)
    if kind != "task":
        raise ToolError(... reason=REASON_GUARD_TRIPPED)
    list_key, object_name = parts
    if list_key.startswith(tasks_client.DECK_PREFIX):
        # A Deck board is never asked, not even through the discovery (E9).
        raise _unknown_task(task_id)

    lists = await tasks_client.discover_task_lists(clients.client, clients.creds)
    matches = [entry for entry in lists if entry.key == list_key]
    if len(matches) != 1:
        raise _unknown_task(task_id)
```
Danach `writable` prüfen wie `_pick_target` Z. 979-983 (`_refused(... "is read only for this account.", _writable_hint(lists))`).

**Analog ETag-Vergleich vor dem Schreiben:** `tools/files.update` Z. 1207-1219:
```python
    wanted = dav.normalize_etag(etag)
    ...
    if info["etag"] and wanted != info["etag"]:
        raise _update_conflict(target)
```
Konfliktsatz nach `_update_conflict` Z. 1170-1180 (`ConflictError`, Hinweis "neu lesen"), für Aufgaben mit `tasks_read` im Hinweis.

**Analog Nachfahren (D-33-09 bis D-33-11):** ein REPORT ohne Vorfilter wie `_search_one` Z. 408-410 (`tasks_client.build_todo_query(None)`), unter `asyncio.timeout(PER_LIST_TIMEOUT)` nur um den Leseweg (Z. 395); `_parse_objects` Z. 426-448 liefert `uid`, `parents`, `status`, `recurring`, `id` und zählt `skipped`. Kinderkarte und exakter Vergleich wie `_children` Z. 673-677:
```python
    return [
        entry
        for entry in entries
        if uid in entry["parents"] and entry["uid"] != uid and entry["id"] != own_id
    ]
```
Nachordnung, besuchte Menge, Obergrenze: Skizze `descendants_post_order` in 33-RESEARCH.md "Code Examples". Kein `asyncio.gather` über Schreibzugriffe (Pitfall 7); `read_task` Z. 596-604 nutzt `gather` nur für Lesewege. Obergrenze als Modulkonstante mit `MESSWERT`-Kommentar nach Z. 52-54 und 69-70.

**Analog Zielzustand:** `_status` Z. 187-195 (`cancelled` vor `completed`, `COMPLETED` allein zählt als erledigt). "Schon im Zielzustand" heißt null Schreibzugriffe, in der Antwort kenntlich.

**Analog Prüfungen auf dem Endstand (TMOD-04):** `_check_times` Z. 853-869 und `_before` Z. 872-878 auf die zusammengeführten Werte anwenden (vorhandenes `_due_value`/`_start_value` aus `_fields` Z. 167-170 plus neue Werte). `_check_times` lehnt `timezone` ohne Zeit ab; `tasks_update` hat keinen `timezone` (D-33-15), also mit `zone=None` aufrufen.

**Analog Elternaufgabe:** `_parse_parent` Z. 903-917 und `_parent_uid` Z. 1016-1029; zusätzlich "gleiche Liste", "nicht selbst", "kein Nachfahr" aus derselben Kinderkarte.

**Analog Liste beim Verschieben:** `_resolve_list` Z. 345-369 (Name oder Schlüssel, casefold, Mehrdeutigkeit mit Schlüsseln, nie URI).

**Antwortform:** `create_task` Z. 809-820 (`id`, `summary`, `list` über `_list_info` Z. 530, Status-Flags). Unter 1400 Bytes je Werkzeug gilt für das Schema, nicht für die Antwort.

---

### `src/mcp_connector/server/reg_tasks.py` (Pläne 33-03 bis 33-05)

**Analog:** `server/reg_files.py` Z. 264-291:
```python
if config.files_update_enabled():

    @mcp.tool(annotations=UPDATE_EXISTING, structured_output=False)
    @graceful
    async def files_update(
        path: Annotated[str, Field(description="Existing text file path; must already exist")],
        content: Annotated[str, Field(description="Complete replacement content as UTF-8 text")],
        etag: Annotated[str, Field(description="ETag returned when the file was read")],
        ctx: Context | None = None,
    ) -> str:
```
Import in `reg_tasks.py` Z. 14-16 um `config` (aus `..`) und die neue Klasse erweitern. Parameter `list` mit `# noqa: A002` und Weitergabe als `list_name=` wie Z. 32-34, 69-72. Schema-Diät: Beschreibungen kurz wie Z. 57, 68-85; `tasks_update` liegt laut Prototyp bei 1368 Bytes, jede zusätzliche Silbe zählt. D-33-15 "leer heißt entfernen" in der Beschreibung des Werkzeugs, nicht je Feld.

---

### `src/mcp_connector/server/__init__.py` (Plan 33-02, D-33-12)

**Analog Klasse:** `UPDATE_EXISTING` Z. 96-101 und der Begründungskommentar von `CREATE_IDEMPOTENT` Z. 85-94:
```python
UPDATE_EXISTING = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=False,
)
```
Neu `MODIFY_EXISTING` mit `destructive_hint=True`, `idempotent_hint=True`, Kommentar warum eigene Klasse; in `__all__` Z. 42-51.

**Analog Instruktion:** Z. 62-71, Satz nur bei Schalter an:
```python
        + (
            " Existing UTF-8 text files can be replaced with files_update, "
            "and only with a matching ETag."
            if config.files_update_enabled()
            else ""
        )
```

---

### `tests/contract/test_no_destructive_calls.py` (Plan 33-02, F6, F7)

**PUT-Zählung:** Z. 478-480 `EXPECTED_PUT_CALLS = 6` auf 7, Kommentar mit Grund. `_usable_precondition` Z. 483-502 akzeptiert `{"If-Match": etag}` mit Variable bereits (Beleg `_HONEST_PUTS` Z. 588-591); kein Eintrag in `UNCONDITIONAL_PUTS` Z. 473-476.

**Getrennte Schreiber-Pin:** nach `test_file_updates_keep_create_and_compare_and_swap_puts_distinct` Z. 450-466:
```python
    path = SRC / "nextcloud" / "clients" / "dav.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    create = ast.unparse(functions["put_new_file"])
    update = ast.unparse(functions["update_file"])
    assert "If-None-Match" in create
    ...
    assert "If-Match" in update
```
Neu für `caldav.put_new_object` (bleibt `If-None-Match: *`) gegen `tasks.put_existing_todo` (`If-Match` mit Variable `etag`).

**MOVE-Ausnahme:** Kommentar und Konstante Z. 139-142 ("user-facing move and rename tools remain forbidden") umschreiben; zweite Konstante `TASK_MOVE = "nextcloud/clients/tasks.py"`, Zweig in `_violations` Z. 424:
```python
            if needle == "MOVE" and relative == CHUNK_ASSEMBLY_MOVE and text.strip() == '"MOVE",':
                continue
```
Diese Ausnahme gilt je Datei und Zeilentext und ließe eine zweite gleiche Zeile durch, darum zusätzlich ein AST-Pin nach dem MKCOL-Gate Z. 606-716 (`_mkcol_findings` Z. 624-656: Ort, `method=`-Schreibweise, entpackte Keywords, Zählung; `test_every_mkcol_lives_in_dav_and_carries_no_body` Z. 696-716 mit `home_literals == total`). Für `MOVE`: genau ein `.request("MOVE", ...)` in `move_todo`, Literal `"Overwrite": "F"`, `"If-Match"` auf Nicht-Konstante; Gesamtzahl 2. Gegenproben nach `test_the_mkcol_gate_flags_each_planted_bypass` Z. 771. Modul-Docstring Z. 1-11 ("never delete, overwrite", "no MOVE") nachziehen; `test_the_gate_would_notice_a_destructive_call_in_real_code` Z. 821-848 prüft den Docstring-Satz von `dav.py` und den sauberen Zustand der echten Datei, für `clients/tasks.py` gleich halten.

---

### `tests/contract/test_tool_surface.py` (Pläne 33-02 bis 33-06, TMOD-05)

**Klasse im Annotations-Gate:** `_check_annotations` Z. 757-789 hat heute einen Namenszweig:
```python
    if name == "files_update":
        assert annotations.read_only_hint is False
        assert annotations.destructive_hint is True
        assert annotations.idempotent_hint is False
    elif name in IDEMPOTENT_CREATE_TOOLS:
```
Neu: Menge `MODIFY_TOOLS` neben `CREATE_TOOLS` Z. 79-87 und `IDEMPOTENT_CREATE_TOOLS` Z. 93, eigener Zweig mit `destructive_hint is True`, `idempotent_hint is True`. Positiv- und Gegenprobe nach Z. 816-837 (`test_the_live_class_of_files_create_folder_passes_the_gate`, parametrisierte gepflanzte Klassen). Da die drei nicht in der Standard-Registry stehen (Schalter aus), braucht `test_every_tool_carries_honest_annotations` Z. 792-813 eine Variante mit Schalter an (Subprozess, Annotationen als JSON).

**Schalter-Test:** nach `test_files_update_registration_respects_feature_flag` Z. 943-969 (Subprozess, `env.pop`, dann `"true"`); für alle drei Namen und mit Gegenprobe, dass `tasks_search`/`tasks_read`/`tasks_create` unabhängig vom Schalter bleiben.

**README-Tabelle:** Z. 877-905, `optional_tools = {"files_update"}` Z. 892 um die drei erweitern, neue Stufe (Vorschlag `modify`) in Z. 888 und im `expected`-Ausdruck Z. 898-904.

**Zählstellen:** Z. 573, 578 ("27 tools"), Z. 863 bleiben 27 (Standard). Doku-Zählgate Z. 908-932: wo 30 genannt wird, Verweis auf `tests/contract/test_tool_surface.py`.

---

### `tests/contract/test_audit_surface.py`, `audit/allowlist.py` (Pläne 33-02 bis 33-05, F9)

**Analog:** `_measured_surface` Z. 43-47 misst nur die Standard-Registry; `test_every_registered_tool_has_an_allowlist_entry` Z. 55-62 meldet "has an allowlist entry but is not registered". Einträge für die drei (nach `allowlist.py` Z. 69-71, alphabetisch, `summary`/`description` bleiben gesperrt Z. 23-34) machen den Test rot, solange die Messung den Schalter nicht setzt. Muster für die Messung mit Schalter: `test_tool_bundles._run` Z. 62-75 (Subprozess, `env.update(more)`, JSON auf stdout). `files_update` hat heute keinen Eintrag; ob es mitgezogen wird, entscheidet der Plan.

---

### `tests/contract/tool_classes.py`, `test_tool_classes.py` (Pläne 33-02 bis 33-05)

**Analog:** `UNAFFECTED` Z. 89-130, Eintrag je Werkzeug mit Begründung ab 20 Zeichen, einzeilig, mit Punkt (`_reason_problem` Z. 173-182), z. B.:
```python
    "tasks_create": (
        "Answers id, summary, list, created, confirmed, due and start of its own task and "
        "takes no file argument (tools/tasks.py:806-817)."
    ),
```
`freeze_findings` Z. 206-207 meldet `stale:` für Einträge ohne Registrierung; dieselbe Behandlung optionaler Werkzeuge wie im Audit. `TOTAL = 27` in `test_tool_classes.py` Z. 20 bleibt für die Standard-Registry. Zeilenverweise in `tasks_read` Z. 122-125 nach dem Umbau von `read_task` neu ziehen.

---

### `tests/contract/test_tool_bundles.py` (Pläne 33-02 bis 33-05)

**Analog:** Z. 135-147:
```python
    enabled = _tools(None, NC_MCP_FILES_UPDATE="true")
    assert enabled == EXPECTED_TOOLS | {"files_update"}

    without_files = _tools("files", NC_MCP_FILES_UPDATE="true")
    assert without_files == EXPECTED_TOOLS - BUNDLE_TOOLS["files"]
```
Gleicher Test für `NC_MCP_TASKS_UPDATE` und das Bundle `tasks`. `BUNDLE_TOOLS["tasks"]` Z. 45 bleibt die Standardmenge (Abdeckungstest Z. 101-107 vergleicht mit `EXPECTED_TOOLS`).

---

### `scripts/check_tool_budget.py` (Pläne 33-02, 33-06, D-33-04)

**Analog:** Messzeilen Z. 116-124, Format "Measurement <Datum>, ...: <n> bytes" und "Budget <n> + 15 percent = ..., rounded up to the next 500". `main` Z. 161-198 misst mit `from mcp_connector.server import mcp` (Z. 14) im Zustand der Umgebung beim Import. Für den maßgeblichen Endstand mit `NC_MCP_FILES_UPDATE=on` und `NC_MCP_TASKS_UPDATE=on` die Umgebung vor dem Import setzen (Import wandert dann in `main` oder Subprozess); die Standardmessung bleibt als Kontrolle. `MAX_TOOL_BYTES = 1400` Z. 158 bleibt (Kommentar Z. 142-145: kürzen, nie anheben). CI-Aufruf `.github/workflows/ci.yml` Z. 46 laut Recherche.

---

### `tests/unit/test_tasks_modify.py` (neu, Pläne 33-03 bis 33-05)

**Analog:** `tests/unit/test_tasks_create.py`. Wichtig: die Aufgaben-Tests nutzen **respx**, nicht `httpx.MockTransport` (Recherche sagt MockTransport). Bausteine:
- Kopf und Fixture `clients` Z. 13-62, Discovery-Bauer `home_entry`/`home` Z. 89-118, `mock_discovery` Z. 146-153.
- `Store` Z. 156-205 nimmt `PUT` und `GET` auf; für Phase 33 um `If-Match`-Auswertung (412 bei falscher ETag), `ETag`-Kopf im `GET`, `REPORT`-Route und `MOVE`-Route (Kopf `Overwrite`, `Destination`) erweitern.
- `mock_stores` Z. 208-219 (`url__startswith=list_url(uri)`, `side_effect=store.put`).
- "Vor jeder Anfrage abgelehnt" Z. 246-298:
```python
    with respx.mock(assert_all_called=False) as mock:
        discovery = mock_discovery(mock)
        stores = mock_stores(mock)
        with pytest.raises(ToolError) as caught:
            await tasks_tools.create_task(clients, **kwargs)
    assert caught.value.reason == REASON_GUARD_TRIPPED
    assert discovery.call_count == 0
    assert puts(stores) == 0
```

---

### `tests/unit/test_exapp_tasks_update_switch.py` (neu, Plan 33-02)

**Analog:** `tests/unit/test_exapp_files_update_switch.py` Z. 55-121: Treiber im Subprozess, `TEST_ADMIN_OVERLAY`, Tabelle `(deploy, admin, expected)` Z. 99-113 mit den fünf Fällen; Prüfung für alle drei Werkzeugnamen.

---

### `tests/integration/test_canary.py`, `canary_world.py` (Plan 33-06)

**Analog:** Kanarie mit Schalter an, Registry 30 statt 27 (`EXPECTED_TOOLS = 27` Z. 69, Assertion Z. 409; `plan()` muss dieselbe Menge haben, Z. 393). Aufrufe in `plan()` nach Z. 243-249 (`world.task_id` mit ETag aus einem vorherigen `tasks_read`), Deck-Fall wie Z. 246-247. `TASK_TOOLS` Z. 96 um die drei erweitern, damit die Deck-Prüfung Z. 334-343 greift. `WRITE_KINDS` Z. 86-93 nur für Werkzeuge, die etwas Neues hinterlassen; Ändern erzeugt kein Objekt, Rückbau läuft über die Welt.

---

### `scripts/acceptance_all_tools.py` (Plan 33-06)

**Analog:** `_tasks` Z. 445-501 (Anlegen ohne Liste, Treffer per Id, `tasks_read` gegen `fetch`, `report.add(tool, "FAIL", ...)`). Kette verlängern: `tasks_read` (ETag) -> `tasks_update` -> `tasks_complete` -> `tasks_move`, alte ETag muss Ablehnung bringen. Nur wenn der Schalter in der Abnahmeumgebung an ist; sonst die drei als nicht registriert ausweisen.

---

### `tests/integration/test_tasks_live.py` (Plan 33-07, TMOD-06)

**Analog:** dieselbe Datei.
- Ablehnung mit Beleg "kein Schreibzugriff, Objekt unverändert": Z. 1093-1105:
```python
    before = list_objects(run.bob, LISTS["ro"][1])
    with Case(run, "geteilt-ro-vorab") as case:
        async with measured(case) as clients:
            exc = await refusal(run, tasks_tools.create_task(clients, ...))
        after = list_objects(run.bob, LISTS["ro"][1])
        case.expect(exc.reason == REASON_GUARD_TRIPPED, told(exc))
        case.expect(not methods(case.seen, "PUT"), "the hook saw no PUT")
        case.expect(before == after, ...)
```
- Server als letzte Wand: Z. 1108-1125 (Harness-PUT, 403/404). Für Phase 33 mit `If-Match` und `MOVE`.
- Rohobjekt vorher/nachher: `raw_object` Z. 923-927 (unfolded); für den Byte-Beweis sha256 der Spalte `calendardata` per `php()` Z. 256 wie `PHP_BASELINE` Z. 129.
- BASELINE vor und nach dem Lauf: `run()` Z. 732-803; Rückbau mit `NO_TRASHBIN` Z. 120.
- Tasks-App mit und ohne: `ENV_EXPECT_TASKS_APP` Z. 103, `tasks_app_state` Z. 296.

---

### `scripts/tasks_chain_evidence.py` (Plan 33-07)

**Analog:** dieselbe Datei. `TASK_TOOLS` Z. 48 um die drei erweitern; Aufrufform `call --case ... --tool ... --args ...` und `same <a> <b>` (Docstring Z. 13-25) tragen die Kette ohne neue Unterbefehle. Der Lauf braucht die ExApp mit gesetztem Schalter (Admin-Formular oder Deploy-Variable).

---

### `scripts/tasks_measure.py` (Plan 33-01, M-1 bis M-4)

**Analog:** dieselbe Datei. Unterbefehle Z. 2247-2303 (`up`, `stop`, `live --steps`, `teardown`, `throwaway`), Protokoll über `spike.write_protocol`, Abbruch `spike.RunFailed`. Budgetregel für die Kettenobergrenze:
```python
def derive_budget(max_seconds: float) -> int:
    """The derivation rule of the spike: twice the largest maximum, rounded up, at least 1 s."""
    return max(1, math.ceil(2 * max_seconds - 1e-9))
```
Rückbau mit `NO_TRASHBIN` Z. 113 nur hier und im Harness, nie im Produktcode. Wiederkehrende Probeobjekte: `recurring_todo` Z. 446 auf Basis von `tests/fixtures/tasks_app/recurring.ics` (Z. 439). Präfix-Muster `PREFIX`/`PREFIXES` Z. 100-122 für eigene Laufnamen (z. B. `p3301`).

## Shared Patterns

### ETag-Disziplin
**Source:** `src/mcp_connector/nextcloud/clients/dav.py` Z. 943-962 (`normalize_etag`), `tools/files.py` Z. 1207-1219
**Apply to:** alle drei ändernden Werkzeuge
Prüfen vor jeder Anfrage, vergleichen nach dem `GET`, trotzdem als `If-Match` senden; nie `*`, nie `W/`, nie leer.

### Prüfung vor der ersten Anfrage, Ablehnung mit Grund
**Source:** `tools/tasks.py` `_refused` Z. 823-825, `create_task` Z. 754-762
**Apply to:** `complete_task`, `update_task`, `move_task`
```python
def _refused(message: str, hint: str) -> ToolError:
    """A refusal before the first request."""
    return ToolError(message=message, hint=hint, reason=REASON_GUARD_TRIPPED)
```

### Eine Antwort für alles Unbekannte (E9)
**Source:** `tools/tasks.py` `_unknown_task` Z. 647-653
**Apply to:** Deck-Präfix, unbekannter Schlüssel, 404 beim Lesen

### Kein Listenbesitzer in Texten
**Source:** `tools/tasks.py` `_quoted` Z. 377-381, `_list_name` Z. 526, `clients/tasks.py` Docstring Z. 16-23
**Apply to:** jede Meldung und Antwort der drei Werkzeuge; nie `TaskList.uri` ausgeben.

### Zeitbudget nur um Lesewege
**Source:** `tools/tasks.py` `_search_one` Z. 395, `_children` Z. 665, `_reason` Z. 539-547, `_side_reason` Z. 705-711
**Apply to:** REPORT der Liste und der Zielliste; nie um `PUT`/`MOVE` (Pitfall 4).

### Registrierung hinter Schalter mit `@graceful`
**Source:** `server/reg_files.py` Z. 264-291
**Apply to:** alle drei; `@graceful` ist Pflicht (`test_audit_surface.py` Z. 128-149 prüft die Marke), Funktionsname gleich Werkzeugname (Z. 152-172).

### Gate mit Gegenprobe aus derselben Prüffunktion
**Source:** `test_no_destructive_calls.py` `_violations` Docstring Z. 413-418, `tool_classes.freeze_findings` Z. 185-190, `test_tool_surface._check_annotations` Z. 757-762
**Apply to:** MOVE-Pin, PUT-Pin, Annotationsklasse, Rundlauf-Beweis

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/mcp_connector/tools/ics_edit.py` | Utility | transform | Kein Editor auf logischen Zeilen im Repo; Phase 32 erzeugt Objekte nur neu (`_build_todo`). Planer folgt 33-RESEARCH.md Pattern 2 |
| Kettenlogik in `tools/tasks.py` | Service | batch (seriell, Stopp beim ersten Fehler) | Kein Werkzeug schreibt bisher mehr als ein Objekt je Aufruf; Skizze `descendants_post_order` in 33-RESEARCH.md |
| Begriff "optionale Werkzeuge" in `test_audit_surface.py` und `tool_classes.py` | Contract-Gate | kein | Beide Gates kennen nur die Standard-Registry; nur `test_tool_bundles.py` Z. 135-147 und `test_tool_surface.py` Z. 892, 943-969 behandeln `files_update` als optional |

## Abweichungen zwischen Recherche und Code

- Unit-Tests der Aufgaben laufen mit **respx** (`test_tasks_create.py` Z. 21, 233), nicht mit `httpx.MockTransport` wie in 33-RESEARCH.md "Validation Architecture".
- Kanarie: die Zahl 27 steht als Konstante in `test_canary.py` Z. 69 und in der Assertion Z. 409; Z. 16 ist nur der Docstring.
- `tool_classes.py`: `UNAFFECTED` reicht bis Z. 130 (Recherche Phase 32: Z. 89-118); die Zeilenverweise der drei Aufgabeneinträge zeigen auf den Stand vor Phase 33 und müssen nach dem Umbau von `read_task` neu gezogen werden.
- `get_todo` hat drei Aufrufer in `tools/tasks.py` (Z. 583, 1021, 1094); ändert sich der Rückgabetyp, ändern sich alle drei.
- `_build_todo` Z. 1086 ruft `ics.to_ical()` ohne `sorted=False`; für neue Objekte unschädlich, für den Zeilen-Editor nicht übernehmen.

## Metadata

**Analog search scope:** `src/mcp_connector/` (clients, tools, server, exapp, audit, config), `tests/contract/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/tasks_app/`, `scripts/`, `appinfo/info.xml`, `docs/tasks-evidence.md`
**Files scanned:** 31
**Pattern extraction date:** 2026-11-13 (HEAD `0e7427c`)

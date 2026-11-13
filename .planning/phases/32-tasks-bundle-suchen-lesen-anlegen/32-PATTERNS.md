# Phase 32: Tasks-Bundle suchen, lesen, anlegen - Pattern Map

**Mapped:** 2026-11-13
**Files analyzed:** 44 (neu oder geändert, Sprachvarianten als eine Zeile gezählt)
**Analogs found:** 41 / 44 (ohne echtes Vorbild: Hybrid-Vorfilter mit Elternverweis, Listenschlüssel für geteilte Listen, CI-Schritt "Store-App installieren und Nextcloud neu starten")

Leitvorbild ist das Kalender-Bundle: Client `nextcloud/clients/caldav.py`, Werkzeuglogik `tools/calendar.py`, Registrierung `server/reg_calendar.py`. Für das Gate-Paket ist Phase 31 (`files_create_folder`) das Vorbild, für die Messprogramme `scripts/tasks_spike.py` und `scripts/folder_chain_evidence.py`. Alle Zeilenangaben sind am Stand des Worktrees `tasks-080` vom 13.11.2026 gelesen, nicht aus 32-RESEARCH.md übernommen; wo beide abweichen, steht es im Abschnitt "Abweichungen zwischen Recherche und Code".

## File Classification

Planzuordnung nach dem Vorschlag in 32-RESEARCH.md ("Empfohlener Planschnitt").

| Neue/geänderte Datei | Plan | Rolle | Data Flow | Nächstes Vorbild | Match |
|---|---|---|---|---|---|
| `scripts/bootstrap_exapp.sh` (`app_password`, `register_manual_install`) | 32-01 | Script (Infrastruktur) | batch | dieselbe Datei: `app_password` Z. 989-1002, `register_manual_install` Z. 1285-1307, grep-Regel Z. 275-286 | exact |
| `tests/unit/test_exapp_env_setup.py` (Pin beider neuen Formen) | 32-01 | Test (Skripttext-Pin) | file-I/O | `shell_function` Z. 337-349, `test_no_grep_q_on_a_pipe_in_the_shell_scripts` Z. 1501-1528, `test_every_registration_validator_runs_before_json_info_is_built` Z. 1303-1312 | exact |
| `scripts/tasks_measure.py` (neu) oder Block in `scripts/tasks_spike.py` | 32-02 | Script (Messprogramm) | batch, request-response | `scripts/tasks_spike.py`: `ram_gate` Z. 1096-1118, `throwaway_preconditions` Z. 6613-6626, `build_todo_filter` Z. 6292-6329, `cost_series` Z. 7564-7642, `proposal` Z. 6426-6449 | exact |
| `tests/unit/test_tasks_measure.py` (neu, nur falls reine Helfer entstehen) | 32-02 | Test (Unit) | transform | `tests/unit/test_tasks_spike.py` Z. 1-31 (Laden per Dateipfad), Abschnitt ab Z. 1000 | exact |
| `docs/spike-tasks.md` (Nachtrag) oder `docs/tasks-evidence.md` | 32-02, 32-07 | Doku (Beleg) | kein | `docs/folder-evidence.md` Z. 1-41 (Kopf, Rohprotokoll-Links, Instanztabelle) | exact |
| `src/mcp_connector/nextcloud/clients/tasks.py` (neu) | 32-03 | Client | request-response (PROPFIND, REPORT, GET) | `clients/caldav.py`: `build_discovery_body` Z. 158-169, `parse_calendar_home` Z. 196-231, `_ok_props` Z. 234-244, `build_calendar_query` Z. 130-155, `query_events` Z. 271-313, `_check` Z. 494-537; Klassifikation `scripts/tasks_spike.py` Z. 6245-6289 | role-match (eigene Körper, eigener Prüfer) |
| `src/mcp_connector/nextcloud/clients/caldav.py` (generischer create-only-Schreiber) | 32-03 | Client | request-response (PUT) | dieselbe Datei: `put_event` Z. 338-363, `_check_write` Z. 447-491 | exact |
| `src/mcp_connector/ids.py` (`encode_task`, Zweig `task`, `_HINT`) | 32-03 | Utility (Codec) | transform | `encode_event` Z. 112-113, Zweig `event` Z. 213-222, `_HINT` Z. 39-43, Formatliste im Docstring Z. 7-26 | exact |
| `tests/unit/test_caldav_bytes_pin.py` (neu, Name frei) | 32-03 | Test (Byte-Pin) | transform | `tests/unit/test_caldav_client.py` Z. 99-134 (`test_the_query_body_...`), Pin-Stil `tests/unit/test_dav_fileid_paths.py` Z. 26-27 | role-match |
| `tests/unit/test_tasks_client.py` (neu) | 32-03 | Test (Unit) | request-response | `tests/unit/test_caldav_client.py` Z. 1-60 (Kopf), Z. 163-246 (Discovery), Z. 404-459 (Statuszweige), Z. 461-500 (PUT) | exact |
| `tests/unit/test_ids.py` | 32-03 | Test (Rundlauf) | transform | `test_roundtrip_for_all_eight_kinds` Z. 20-36, `test_encoded_prefixes_are_stable` Z. 39-48, `test_the_hint_every_tool_prints_names_all_eight_forms` Z. 167-170 | exact |
| `src/mcp_connector/tools/tasks.py` (neu) | 32-04 | Service/Tool-Logik | request-response, batch (Fan-out) | `tools/calendar.py`: `list_events` Z. 65-126, `_select` Z. 161-184, `_pick_target` Z. 187-221, `_query_one` Z. 224-238, `_reason` Z. 241-249, `create_event` Z. 252-319, `_read_back` Z. 322-342, `build_ics` Z. 383-430; Cursor `tools/files.py` Z. 177-182, 217-233; Kappung `tools/mail.py` Z. 547-563; `skipped` `tools/search.py` Z. 205-208 | role-match |
| `src/mcp_connector/nextcloud/capabilities.py` (`tasks_available`) | 32-04 | Service (Erkennung) | request-response, Cache | `load_mail` Z. 168-195, `_navigation_lists_mail` Z. 220-245, Feld `mail_available` Z. 124-128 | role-match (darf nicht werfen) |
| `tests/unit/test_tasks_tools.py` (neu) | 32-04 | Test (Unit) | request-response | `tests/unit/test_calendar_tools.py` Z. 1-75 (Kopf, `mock_calendars`), Z. 212-226 (degraded), Z. 336-349 (alle ausgefallen), Z. 591-612 (Rücklesen), Z. 699-802 (Zielwahl) | exact |
| `tests/unit/test_tasks_time_matrix.py` (neu) | 32-04 | Test (Zeitmatrix) | transform | `tests/unit/test_caldav_client.py` Z. 248-335 (`test_matrix_a` bis `test_matrix_d`), Z. 337-360 | role-match |
| `tests/unit/test_ocs_capabilities.py` | 32-04 | Test (Unit) | request-response | Mail-Navigation Z. 562-715 | exact |
| `tests/unit/test_injection_corpus.py` | 32-04 | Test (Korpus) | request-response | Kalenderfall Z. 137-181, `everything_but` Z. 88-96 | exact |
| `src/mcp_connector/server/reg_tasks.py` (neu) | 32-05 | Registrierung | request-response | `server/reg_calendar.py` Z. 1-87 (ganz) | exact |
| `src/mcp_connector/audit/allowlist.py` | 32-05 | Config | kein | `PARAM_ALLOWLIST` Z. 45-72, `FORBIDDEN_PARAMS` Z. 23-34 | exact |
| `tests/contract/test_tool_surface.py` | 32-05 | Contract-Gate | kein | `EXPECTED_TOOLS` Z. 44-69, `CREATE_TOOLS` Z. 71-82, Zahlen Z. 568-573, 789, 800, 857, README-Tabelle Z. 872-899, Doku-Zählgate Z. 902-934 | exact |
| `tests/contract/test_tool_bundles.py` | 32-05 | Contract-Gate | kein | `BUNDLE_TOOLS` Z. 23-45, `test_the_bundle_names_are_frozen` Z. 83-96 | exact |
| `tests/contract/tool_classes.py` | 32-05, 32-06 | Test-Tabelle | kein | `UNAFFECTED` Z. 89-118, `MIN_REASON` Z. 121, `fetch` in `FILE_READERS` Z. 58-61 | exact |
| `tests/contract/test_tool_classes.py` | 32-05 | Contract-Gate | kein | `TOTAL` Z. 19, Meldung Z. 33-36, Aufteilung Z. 103-115 | exact |
| `tests/contract/test_no_destructive_calls.py` | 32-03, 32-05 | Contract-Gate (AST) | kein | `EXPECTED_PUT_CALLS = 6` Z. 480, `_usable_precondition` Z. 483-502, `ALLOWED_MODULE_STATE` Z. 360-365 | unverändert, nur einhalten |
| `tests/unit/test_disabled_tools.py` | 32-05 | Test (Unit) | kein | `KNOWN` Z. 13-25 | exact |
| `vulture_whitelist.py` | 32-05 | Config | kein | Werkzeugliste Z. 14-28 (jede Werkzeugfunktion namentlich) | exact |
| `scripts/check_tool_budget.py` | 32-05 | Script (Gate) | kein | Messzeilen Z. 105-114, `BUDGET_BYTES` Z. 115, `MAX_TOOL_BYTES` Z. 149 | exact |
| `scripts/acceptance_all_tools.py` | 32-05 | Script | request-response | Block `# --- calendar` Z. 269-291, Doppelaufruf mit Prüfung Z. 209-219 | exact |
| `tests/integration/test_canary.py` | 32-05 | Test (Live) | kein | `EXPECTED_TOOLS` Z. 63, `WRITE_KINDS` Z. 80-86, `plan()` Z. 197-211, `book_write` Z. 277-286 | exact |
| `tests/integration/canary_world.py` | 32-05 | Test-Harness | kein | `mkcalendar` Z. 541-554, `_NO_CAL_TRASH` Z. 108, `WRITE_KINDS` Z. 774, `_add_tool_write` Z. 937-998, `_build_calendar` Z. 1193-1217, `_build_deck` Z. 1220-1244 | exact |
| `tests/integration/test_tasks_live.py` (neu) | 32-05, 32-07 | Test (Live, Impersonation) | request-response | `tests/integration/test_files_create_folder_live.py` Z. 1-41 (Kopf), Z. 269-276, 296-327 (Lauf), Z. 330-360 (`Case`), Z. 363-398 (`appapi_clients`); Schalter `canary_world.skip_or_fail` Z. 113-120 | exact (Schalter: role-match) |
| `.github/workflows/ci.yml` | 32-05 | Config (CI) | kein | Schritt `exapp` Z. 102-106, Schritt `canary-nc35` Z. 201-219, Versionsprüfung Z. 188-194 | role-match |
| `tests/unit/test_live_requirement.py` | 32-05 | Test (CI-Pin) | file-I/O | `test_the_ci_step_of_the_gates_sets_the_switch` Z. 39-48, `test_the_gates_run_on_nextcloud_35_only` Z. 56-74 | exact |
| `README.md`, `README.de.md`, `README.fr.md` | 32-05, 32-06 | Doku | kein | README.md Z. 25 (Zahl, Familien), Z. 72 (Tabellenzeile), Z. 90 (`fetch`), Z. 116-129 (Bundle-Liste); de/fr Z. 28 | exact |
| `appinfo/info.xml` | 32-05 | Config (Manifest) | kein | Z. 573 (`Valid names: ...`) | exact |
| `docs/folder-evidence.md` (Verweiszeile) | 32-05 | Doku | kein | Vorbild der Verweiszeile: `docs/nc35-evidence.md` Z. 97, `docs/n8n-setup.md` Z. 258-259 | exact |
| `CHANGELOG.md`, `.de.md`, `.fr.md` | 32-05, 32-06 | Doku | kein | `## [Unreleased]` Z. 12, `### Added` Z. 14-33 | exact |
| `docs/hardening.md`, `.de.md`, `.fr.md` | 32-05 | Doku | kein | Z. 54 (de/fr Z. 57), keine Bundle-Liste vorhanden | prüfen, voraussichtlich unverändert |
| `src/mcp_connector/provider_map.py` | 32-06 | Utility (Übersetzung) | transform | `PROVIDER_KINDS` Z. 55-85, `extract_id` Z. 127-173, `_tables_node` Z. 242-253, `_message_target` Z. 211-239; Regex `scripts/tasks_spike.py` Z. 6126, 6414-6423 | exact |
| `src/mcp_connector/tools/chatgpt.py` (`_fetch_task`, Docstring) | 32-06 | Service/Tool-Logik | request-response | `fetch` Z. 236-256, `_fetch_event` Z. 475-511, Docstring Z. 15-52 | role-match (Leser nicht übernehmen) |
| `tests/unit/test_provider_map.py` | 32-06 | Test (Unit) | transform | Tables-Fälle Z. 253-300, Talk-Fälle Z. 191-250, Tabellen-Pin Z. 312-330 | exact |
| `tests/unit/test_chatgpt_fetch.py` | 32-06 | Test (Unit) | request-response | `test_an_event_id_is_read_from_caldav` Z. 648-662, Docstring Z. 1 ("all eight id kinds") | exact |
| `scripts/tasks_chain_evidence.py` (neu) | 32-07 | Script (Beleg) | request-response | `scripts/folder_chain_evidence.py` Z. 1-157 (ganz) | exact |
| `docs/tasks-evidence.md` (neu) | 32-07 | Doku (Beleg) | kein | `docs/folder-evidence.md` (Gliederung Z. 31, 43, 72, 157, 301, 348, 493) | exact |

## Pattern Assignments

### `scripts/bootstrap_exapp.sh` (Plan 32-01, D-32-13)

**Analog:** dieselbe Datei.

**Stelle 1, Token anlegen** (Z. 989-1002). Heute steht `--name` fest im Aufruf; auf Nextcloud 32 gibt es die Option nicht (K6: erst ab `stable33`):
```bash
app_password() {
  local uid="$1" password="$2" raw token
  raw="$(occ_pw "$password" user:auth-tokens:add "$uid" --password-from-env --name "$TOKEN_NAME")"
  # The command prints a label line and the token on the next line. The CR strip is the
  # Windows guard: Git Bash keeps the CR from the container output otherwise.
  token="$(printf '%s\n' "$raw" | tr -d '\r' | sed '/^[[:space:]]*$/d' | tail -n1 |
    sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
```
Zu übernehmen: die Token-Auswertung bleibt wörtlich (Ausgabeform auf 32 und 35 gleich, K6). Neu ist nur die Feature-Erkennung vor dem Aufruf (Skizze in 32-RESEARCH.md "Feature-Erkennung `--name` im Bootstrap"). Auf 33 bis 35 muss der Aufruf wörtlich wie heute bleiben (`TOKEN_NAME="mcp-exapp"`, Z. 135).

**Stelle 2, Daemon registrieren** (Z. 1285-1296). Der Port im Host ist auf 32 falsch (K7: AppAPI kürzt erst ab `stable33`):
```bash
register_manual_install() {
  local output
  if ! occ app_api:daemon:list 2>/dev/null | grep "${MANUAL_DAEMON_NAME}" >/dev/null; then
    if ! output="$(occ app_api:daemon:register \
      "${MANUAL_DAEMON_NAME}" "Manual Install" manual-install http \
      "host.docker.internal:${MANUAL_APP_PORT}" "${NC_DAEMON_URL}" 2>&1)"; then
```
Zu beachten: der Daemon wird nur registriert, wenn er fehlt (Z. 1287). Ein bestehendes Volume behält den alten Eintrag; die Reparatur wirkt dort nicht von selbst. Der Plan muss sagen, was mit dem von Hand gesetzten Eintrag im Volume `nc-mcp-exapp` geschieht.

**Pflichtmuster grep auf einer Pipe** (Z. 275-286, Gate `test_no_grep_q_on_a_pipe_in_the_shell_scripts`, `tests/unit/test_exapp_env_setup.py` Z. 1501-1528): nie `grep -q` hinter einer Pipe, immer `grep ... >/dev/null`. Das Gate liest alle `scripts/*.sh` und erkennt auch `-Eq`.
```bash
    if occ status 2>/dev/null | grep "installed: true" >/dev/null; then
```

**Formregel für neue Shell-Funktionen:** `name() {` allein auf einer Zeile, schließendes `}` in Spalte eins. Sonst schneidet `shell_function` (`tests/unit/test_exapp_env_setup.py` Z. 337-349) die Funktion nicht sauber aus.

**Nicht Teil von D-32-13, nur benennen:** dieselbe `--name`-Stelle steht in `scripts/bootstrap_test_nc.sh:219` und `scripts/bootstrap_spike_opendesk.sh:906`.

**Tasks-App im Bootstrap (D-32-11):** `ensure_app` (Z. 302-316) ist das Muster, Aufrufe Z. 1326-1337. Ein `ensure_app tasks` an dieser Stelle würde die App in JEDEM Lauf installieren, auch im CI-Job `exapp`, der nach der Empfehlung der Recherche das Bein "ohne Tasks-App" ist. Die Installation gehört deshalb in einen eigenen Schritt (CI) oder hinter einen Schalter, nicht in die feste Liste.

---

### `tests/unit/test_exapp_env_setup.py` (Plan 32-01)

**Analog:** dieselbe Datei. Skripttext lesen, Funktion ausschneiden, Text prüfen:
```python
def shell_function(name: str, path: Path | None = None) -> str:
    text = (path or BOOTSTRAP).read_text(encoding="utf-8")
    opening = f"\n{name}() {{\n"
    start = text.index(opening)
    end = text.index("\n}\n", start)
    return text[start + 1 : end + 3]
```
Neu: zwei Tests im Stil von Z. 1303-1312, die im Körper von `app_password` die Feature-Erkennung (`--help`, kein festes `--name` im Aufruf) und im Körper von `register_manual_install` den Host ohne `:${MANUAL_APP_PORT}` pinnen. Je eine Gegenprobe auf einer manipulierten Kopie mit `function_body` (Z. 352-364), wie es die Share-Gates der Datei tun.

---

### `scripts/tasks_measure.py` oder Block in `scripts/tasks_spike.py` (Plan 32-02)

**Analog:** `scripts/tasks_spike.py` (8782 Zeilen, nur gezielt lesen).

**RAM-Gate, nie fremde Container anfassen** (Z. 1096-1118):
```python
def ram_gate(own_containers: Iterable[str], *, enforce: bool = True) -> None:
    own = set(own_containers)
    free = free_host_memory_gb(host_memory_probe())
    enough = "ok" if free >= MIN_FREE_HOST_GB else "zu wenig"
    note(f"RAM frei_host_gb={free:.2f} schwelle={MIN_FREE_HOST_GB} ergebnis={enough}")
    ...
    if enforce and not ram_gate_ok(free, foreign):
        raise RunFailed(...)
```
Dazu `throwaway_preconditions` (Z. 6613-6626: nie neben nc35, kein altes Volume) und `throwaway_instance` (Z. 6650 ff., Passwörter per `secrets.token_urlsafe`, sofort `remember_secret`).

**REPORT-Körper mit lxml, Modus `eltern`** (Z. 6292-6329). Das ist der gemessene Körper der Kinderabfrage:
```python
    elif mode in ("text", "eltern"):
        name, needle = ("SUMMARY", term) if mode == "text" else ("RELATED-TO", parent_uid)
        ...
        matched = etree.SubElement(todo, f"{{{xml.CAL}}}prop-filter", name=name)
        match = etree.SubElement(
            matched, f"{{{xml.CAL}}}text-match", attrib={"match-type": "contains"}
        )
        match.text = needle
```
Abweichung zur Recherche: gemessen ist `match-type="contains"` OHNE `collation`. Die Recherche (K5, F4) empfiehlt `collation="i;octet"`. Diese Form ist ungemessen und gehört als eigene Messzeile in Plan 32-02 (beide Formen, Trefferzahl und Status vergleichen), bevor sie in `clients/tasks.py` wandert.

**Messreihe und Ableitungsregel** (`cost_series` Z. 7564-7642, `proposal` Z. 6426-6449): `measure_series` mit Aufwärm- und Messläufen, Zeilen `KOSTEN <modus>`, `GEGENPROBE`, `BEZUG`, `VORSCHLAG`. Budget = doppelter Maximalwert, aufgerundet, mindestens 1 s:
```python
    budget = max(1, math.ceil(2 * max_seconds - 1e-9))
```
Für D-32-03 eine Reihe `KOSTEN kinder` nach demselben Muster ergänzen, mit Elternaufgabe ohne, mit einem und mit 25 Kindern.

**Geheimnisse:** `remember_secret` (Z. 836), `scan_for_secrets` (Z. 842-857), `write_protocol` (Z. 859): jede Ausgabe wird vor dem Schreiben gegen alle bekannten Werte geprüft. `.env*`-Dateien nur über `read_env_file` (Z. 984) plus `remember_env_secrets` (Z. 998), nie zitieren.

**Listen anlegen und teilen im Harness:** `mkcalendar_body(name, components=("VTODO",))` Z. 2405-2414 und `share_body(user, writable=...)` Z. 2416 ff., beide mit lxml.

**R6:** Messprogramme und Probe-Werkzeuge liegen nie unter `src/`. `vulture` läuft über `scripts`; geparkte Helfer ohne Aufrufer brauchen einen begründeten Eintrag in `vulture_whitelist.py` (Abschnitt Z. 351-362 zeigt, wie Phase 30 das dokumentiert hat).

---

### `src/mcp_connector/nextcloud/clients/tasks.py` (neu, Plan 32-03)

**Analog:** `clients/caldav.py`. Aufrufen statt kopieren: `calendars_home_url` (Z. 91-93), `calendar_url` (Z. 96-98), `object_url` (Z. 101-104), `safe_segment` (Z. 107-127), `to_caldav_utc` (Z. 79-88). Nachbauen mit eigenem Inhalt: Discovery-Körper, Parser, Prüfer.

**Imports** (caldav.py Z. 30-47), dieselbe Konvention mit relativen Importen:
```python
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
from icalendar import Calendar as IcsCalendar
from lxml import etree

from ... import config, ids
from ...errors import (
    REASON_PERMISSION_DENIED,
    REASON_UNKNOWN_ID,
    ConflictError,
    ToolError,
)
from ..credentials import Credentials
from . import xml
```

**Discovery-Körper mit lxml** (Z. 158-169). Form übernehmen, Eigenschaften erweitern, in einer EIGENEN Funktion; `build_discovery_body` bleibt byte-gleich:
```python
def build_discovery_body() -> bytes:
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "c": xml.CAL, "cs": xml.CS},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.DAV}}}displayname")
    etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    etree.SubElement(prop, f"{{{xml.CS}}}getctag")
    etree.SubElement(prop, f"{{{xml.CAL}}}supported-calendar-component-set")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")
```
Namensräume: `xml.OC = "http://owncloud.org/ns"` (xml.py Z. 17) trägt `read-only`. Der Namensraum für `owner-displayname` ist `http://nextcloud.com/ns`; `xml.NC` ist `http://nextcloud.org/ns` (xml.py Z. 18) und passt NICHT. Die neue Konstante gehört in `clients/tasks.py`, nicht in `xml.py` (Modulregel xml.py Z. 8-9: "Request builders stay in the client module that owns the request").

**PROPFIND-Aufruf** (Z. 179-187):
```python
    response = await client.request(
        "PROPFIND",
        home,
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=build_discovery_body(),
        auth=creds.auth(),
    )
    _check(response, "the calendar list")
```

**Multi-Status lesen** (Z. 203-231): `xml.parse_root` (gehärtet), Wurzel prüfen, Home überspringen, nur 2xx-Propstat, URI per `unquote` aus dem letzten Pfadsegment, `displayname` mit Rückfall auf die URI:
```python
    root = xml.parse_root(body)
    if root.tag != f"{{{xml.DAV}}}multistatus":
        raise ToolError(
            message="Expected a DAV Multi-Status response for the calendar list.",
            hint="Check that the base URL points at Nextcloud itself and not at a login page.",
        )
    home = (home_path or "").rstrip("/")
    for response in root.findall(f"{{{xml.DAV}}}response"):
        ...
        path = urlsplit(href).path.rstrip("/")
        if not path or (home and path == home):
            continue
        props = _ok_props(response)
        ...
        uri = unquote(path.rsplit("/", 1)[-1])
        ...
        found.append(CalendarRef(uri=uri, display_name=display_name or uri))
```
Achtung `_ok_props` (Z. 234-244): liefert nur DAS ERSTE 2xx-Propstat und ist privat. Für Aufgaben reicht das nicht: `oc:read-only` unterscheidet "steht im 2xx-Propstat" (geteilt) von "steht im 404-Propstat" (eigen). Vorbild für das Einsammeln je Propstat ist der Spike (`scripts/tasks_spike.py` Z. 6207-6213):
```python
        for propstat in response.findall(f"{{{xml.DAV}}}propstat"):
            if " 2" not in (propstat.findtext(f"{{{xml.DAV}}}status") or ""):
                continue
            for child in propstat.findall(f"{{{xml.DAV}}}prop/*"):
                if isinstance(child.tag, str):
                    props[child.tag] = child
```

**Klassifikation, gemessene Reihenfolge** (`scripts/tasks_spike.py` Z. 6245-6275). Das ist die Vorlage, nicht `_is_own_event_calendar` (caldav.py Z. 247-268, kennt weder Deck noch Papierkorb noch gelöschte Kalender):
```python
    if entry.uri.startswith("app-generated--"):
        return "deck"
    if entry.uri == TRASH or "trash-bin" in entry.types:
        return "papierkorb"
    if "deleted-calendar" in entry.types:
        return "geloeschter-kalender"
    if entry.uri in ("inbox", "outbox") or {"schedule-inbox", "schedule-outbox"} & set(entry.types):
        return "scheduling"
    if "subscribed" in entry.types:
        return "abo"
    if "_shared_by_" in entry.uri:
        read_only = entry.read_only is not None and entry.read_only.lower() not in ("", "0", "false")
        return "geteilt-nur-lesen" if read_only else "geteilt-schreibbar"
```
Schreibrecht im Spike (Z. 6287-6289): `{"write", "write-content", "bind", "all"} & set(entry.privileges)`. Siehe Abweichungen: die Recherche nennt nur `write` und `write-content` und nimmt `oc:read-only` statt `_shared_by_` als Hauptmerkmal für "geteilt".

**REPORT-Körper** (caldav.py Z. 144-155 für die Form, Spike Z. 6304-6313 für den Inhalt): `calendar-query` mit `comp-filter VCALENDAR/VTODO`, ohne `expand`, ohne `time-range`.

**REPORT-Aufruf und Objektname aus dem href** (Z. 288-303):
```python
    response = await client.request(
        "REPORT",
        url,
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=body,
        auth=creds.auth(),
    )
    _check(response, f"the calendar {calendar_uri}")
    for href, props in xml.parse_multistatus(response.content):
        ics = props.get(f"{{{xml.CAL}}}calendar-data")
        if not ics:
            continue
        object_name = unquote(urlsplit(href).path.rstrip("/").rsplit("/", 1)[-1])
        if not object_name:
            continue
```
Der Objektname kommt aus dem href, nie aus der UID (Test `test_the_object_name_comes_from_the_href_and_not_from_the_uid`, test_caldav_client.py Z. 374).

**GET eines Objekts** (Z. 324-329): `headers={"Accept": "text/calendar"}`, `auth=creds.auth()`, danach Prüfer.

**Statusprüfer, Vorbild für den eigenen Prüfer** (Z. 494-537). Reihenfolge der Zweige übernehmen (200/207, 3xx mit `config.REDIRECT_HINT`, 401, 403 mit `REASON_PERMISSION_DENIED`, 404 mit `REASON_UNKNOWN_ID`, 429, 5xx, Rest), Wortlaut NICHT:
```python
    if status == 404:
        raise ToolError(
            message=f"Nextcloud does not know {what}.",
            hint="Call calendar_list_events once to see the calendars of this account.",
            reason=REASON_UNKNOWN_ID,
        )
```
Der Hinweis nennt ein Kalenderwerkzeug, das bei abgeschaltetem Bundle `calendar` nicht existiert. Außerdem braucht die Aufgaben-Discovery den Fall "Home 404" als E6 statt als Fehler (Pitfall 13, Annahme A1). `reason` nur an den Statuszweigen (Kommentar Z. 472-474).

**ANTI-MUSTER, ausdrücklich nicht übernehmen:**

1. `caldav._value_of` (Z. 412-424) setzt schwebende Zeiten still auf UTC:
```python
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # A floating time only appears when the server did not expand, which it does
            # for every query this client sends. UTC matches the expansion default.
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
```
Die Begründung im Kommentar gilt nur unter Server-Expansion. Aufgaben werden nie expandiert (TASK-02), dort ist das eine stille Falschaussage (TASK-04: "schwebend, gekennzeichnet, nie still zu UTC erklärt"). Auch der zweite Zweig (`astimezone(UTC)`) ist für Aufgaben falsch: eine zonierte Fälligkeit soll ihre Zone behalten (Zeitmatrix der Recherche, Pattern 4). Der Aufgabenleser bekommt eine eigene Funktion nach der Skizze "Ausgabe einer Fälligkeit ohne stilles UTC" und einen benannten Test "schwebend bleibt schwebend und ist gekennzeichnet".
2. `caldav.parse_ics` (Z. 366-409): walkt nur `VEVENT`, wirft bei einem unlesbaren Objekt für die ganze Liste (Z. 379-385) und verwirft Komponenten ohne `DTSTART` (Z. 390-393). TASK-02 verlangt Überspringen je Objekt mit Zählung.
3. `caldav.discover_calendars` (Z. 172-193) wirft bei leerer Liste `_NO_CALENDAR`. Für Aufgaben ist "keine Liste" ein Ergebnis (E6), kein Fehler der Client-Schicht.
4. `parse_calendar_home` erweitern oder `build_discovery_body` um Eigenschaften ergänzen: bricht TASK-01 (byte-gleich).

---

### `src/mcp_connector/nextcloud/clients/caldav.py` (generischer Schreiber, Plan 32-03)

**Analog:** `put_event` (Z. 338-363) und `_check_write` (Z. 447-491). Genau ein `.put(` bleibt in der Datei.

**Der eine PUT** (Z. 351-356):
```python
    response = await client.put(
        object_url(creds, calendar_uri, object_name),
        content=ics_bytes,
        headers={"If-None-Match": "*", "Content-Type": "text/calendar; charset=utf-8"},
        auth=creds.auth(),
    )
    _check_write(response, calendar_uri, object_name)
    return {
        "calendar": calendar_uri,
        "object_name": object_name,
        "etag": response.headers.get("etag", ""),
        "created": True,
    }
```
Zwang aus dem Gate (`tests/contract/test_no_destructive_calls.py` Z. 483-502): `headers=` muss ein Dict-LITERAL im Aufruf sein, mit Konstante `"If-None-Match"` und Konstante `"*"`. Ein in eine Variable ausgelagertes Dict oder ein zusammengebauter Kopf zählt als "ohne Vorbedingung".
```python
    headers = next((kw.value for kw in call.keywords if kw.arg == "headers"), None)
    if not isinstance(headers, ast.Dict):
        return False
```

**Wortlaut je Zweig, heute fest verdrahtet** (Z. 449-491): 200/204 (ersetzt statt abgelehnt), 412 `ConflictError`, 403 mit `REASON_PERMISSION_DENIED`, 404/409 mit `REASON_UNKNOWN_ID`, 415, Rest über `_check`, danach "unexpected status". Diese Sätze werden zu `EVENT_WORDING` und müssen Wort für Wort bleiben; die Tests Z. 461-500 in `test_caldav_client.py` und Z. 557-590 in `test_calendar_tools.py` halten sie und dürfen nicht angefasst werden (TASK-01).

Aufgabenseite, eigener Wortlaut: eine nur lesbare geteilte Liste antwortet auf `PUT` mit 404, ein Deck-Kalender mit 403 (Spike 3.3, 5.2). Der heutige 404-Satz "The calendar {calendar_uri} does not exist." wäre dort eine Behauptung, die nicht sicher ist (D-31-09); außerdem darf im Aufgabenwortlaut für geteilte Listen nicht die URI stehen (`_shared_by_<Kennung>`, D-32-14), sondern Name oder Schlüssel.

**Beweis TASK-01:** vor der ersten Änderung Byte-Pin anlegen (siehe nächste Datei), danach in jedem Plan, der `caldav.py` berührt: `git diff <Basis> -- tests/unit/test_caldav_client.py tests/unit/test_calendar_tools.py tests/integration/test_calendar_roundtrip.py` ist leer (Muster `31-BASE.txt`, Basis-Hash mit `tr -d '\r'` lesen, Pitfall 4).

---

### `tests/unit/test_caldav_bytes_pin.py` (neu, Plan 32-03, zuerst)

**Analog:** `tests/unit/test_caldav_client.py` Z. 99-134 (prüft den Körper strukturell). Neu ist der Hash-Pin auf Python-Bytes für feste Eingaben: `sha256(caldav.build_discovery_body())` und `sha256(caldav.build_calendar_query(start, end))`. Nicht in `test_caldav_client.py` ergänzen, sonst ist dessen Diff gegen die Basis nicht mehr leer. Pin auf Bytes der Funktion, nicht auf Dateitext (Pitfall 4, `core.autocrlf`).

---

### `src/mcp_connector/ids.py` (Plan 32-03)

**Analog:** `encode_event` und der Zweig `event`.

**Encode** (Z. 112-113):
```python
def encode_event(calendar_uri: str, object_name: str) -> str:
    return _join("event", calendar_uri, object_name)
```

**Parse-Zweig mit vollem Split** (Z. 213-222):
```python
    elif kind == "event":
        # A full split instead of ``maxsplit=1``: ``_join`` refuses the separator in the
        # calendar uri and in the object name alike, so ``event:a:b:c`` is an id the encode
        # side can never have built ...
        parts = tuple(rest.split(SEPARATOR))
        if len(parts) != 2:
            raise ToolError(
                message=f"{raw!r} is not a valid event id.", hint=_HINT, reason=REASON_GUARD_TRIPPED
            )
```
Jede Ablehnung trägt `reason=REASON_GUARD_TRIPPED` (Kommentar Z. 35-38). `_join` (Z. 235-249) lehnt `:` in jedem Segment ab; das ist der Grund, warum ein Fremdobjekt mit `:` im Namen übersprungen werden muss (TASK-02) statt die Liste zu kippen. `_HINT` (Z. 39-43) und die Formatliste im Modul-Docstring (Z. 7-26) um `task:<list>:<object>` ergänzen.

Der Codec darf die Client-Schicht nicht importieren (Kommentar Z. 51-54). Die Berechnung des Listenschlüssels für geteilte Listen (D-32-14) muss deshalb eine reine Funktion an einer Stelle sein, die sowohl `clients/tasks.py` als auch `provider_map.py` (importiert heute nur `ids`, Z. 51) erreichen, ohne Zyklus.

---

### `tests/unit/test_ids.py` (Plan 32-03)

**Analog** (Z. 20-36, 39-48, 167-170). Drei Stellen wachsen von acht auf neun Formen, samt Testnamen:
```python
def test_the_hint_every_tool_prints_names_all_eight_forms() -> None:
    """The hint is contract: it is what a caller reads after any id was refused anywhere."""
    for form in ("file:", "note:", "card:", "event:", "mail:", "message:", "table:", "url:"):
        assert form in ids._HINT, form
```
Neu dazu: Rundlauf für eigene Liste (URI) und geteilte Liste (Schlüssel), Ablehnung von `task:a:b:c` und `task:a` nach dem Muster Z. 227-235.

---

### `src/mcp_connector/tools/tasks.py` (neu, Plan 32-04)

**Analog:** `tools/calendar.py`, ergänzt um Cursor, Kappung und Zählung aus drei anderen Modulen.

**Modulgrenze** (`tests/contract/test_module_boundaries.py`, AST-Gate): erlaubt sind öffentliche Namen anderer Werkzeugmodule (`calendar.parse_instant` Z. 129-145, `calendar.resolve_zone` Z. 148-158, `calendar.PRODID` Z. 48). Verboten ist jeder Zugriff auf `calendar._pick_target`, `calendar._read_back`, `calendar._select`, `calendar._reason`, `mail._capped`: diese Muster werden in `tools/tasks.py` nachgebaut, nicht importiert.

**Fan-out mit Zeitbudget und `degraded`** (Z. 92-111, 224-249):
```python
    results = await asyncio.gather(
        *(_query_one(clients, entry, window_start, window_end) for entry in selected),
        return_exceptions=True,
    )
    for entry, outcome in zip(selected, results, strict=True):
        if isinstance(outcome, BaseException):
            degraded.append({"calendar": entry.display_name, "reason": _reason(outcome)})
            continue
        events.extend(outcome)

    if degraded and not events and len(degraded) == len(selected):
        raise ToolError(
            message="None of the calendars could be read.",
            hint="; ".join(item["reason"] for item in degraded),
        )
```
```python
async def _query_one(...):
    async with asyncio.timeout(PER_CALENDAR_TIMEOUT):
        return await caldav.query_events(...)

def _reason(exc: BaseException) -> str:
    """One sentence per failed calendar. Unknown failures are bugs and stay loud."""
    if isinstance(exc, ToolError):
        return exc.message
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return f"The calendar did not answer within {PER_CALENDAR_TIMEOUT:.0f} seconds."
    if isinstance(exc, httpx.RequestError):
        return "The calendar could not be reached."
    raise exc
```
Anpassungen: der `degraded`-Eintrag nennt den Listennamen OHNE Besitzerzusatz (D-32-14); `exc.message` eines `ToolError` aus dem Client darf deshalb keine URI einer geteilten Liste tragen. Die Bedingung "alle ausgefallen" prüft bei Aufgaben `len(degraded) == len(selected)` ohne `not events`-Abkürzung über Treffer aus anderen Listen. `PER_CALENDAR_TIMEOUT = 20.0` (Z. 52) ist nicht zu übernehmen; das Budget kommt aus der Messung in Plan 32-02 und steht mit Messzeile im Code.

**Liste gegen die Discovery auflösen** (Z. 161-184), nie in eine URL ohne Prüfung:
```python
    needle = wanted.strip().casefold()
    matches = [
        entry
        for entry in calendars
        if entry.uri.casefold() == needle or entry.display_name.casefold() == needle
    ]
    if matches:
        return matches
    available = ", ".join(sorted({entry.display_name for entry in calendars}))
    raise ToolError(
        message=f"This account has no calendar called {wanted!r}.",
        hint=f"Available calendars: {available}.",
    )
```
Für Aufgaben: Vergleich gegen URI (eigene Liste), Schlüssel (geteilte Liste) und Name ohne Besitzerzusatz; die Fehlermeldung nennt Namen und bei Mehrdeutigkeit die Schlüssel, nie eine URI mit `_shared_by_`.

**Zielwahl beim Schreiben** (`_pick_target`, Z. 187-221). Struktur übernehmen (benannter Parameter gewinnt, Mehrdeutigkeit ist ein Fehler mit Kandidaten, sonst Fehler mit den echten Namen), Regel ersetzen:
```python
    if wanted is not None and wanted.strip():
        matches = _select(calendars, wanted)
        if len(matches) > 1:
            candidates = ", ".join(
                sorted(f"{entry.display_name} ({entry.uri})" for entry in matches)
            )
            raise ToolError(
                message=f"{wanted!r} matches more than one calendar.",
                hint=f"Pick one by its uri. Matching calendars: {candidates}.",
            )
        return matches[0]

    for entry in calendars:
        if entry.uri.casefold() == DEFAULT_CALENDAR_URI:
            return entry
    if len(calendars) == 1:
        return calendars[0]
```
NICHT übernehmen: der Rückfall auf `personal` (Z. 209-211) und "genau ein Kalender insgesamt" (Z. 212-213). E4 und TASK-06 verlangen "genau eine EIGENE BESCHREIBBARE Liste"; `discover_calendars` unterscheidet eigene und geteilte Kalender gar nicht. Ebenso gilt D-32-16: `parent` in einer geteilten Liste ist keine Nennung der Liste.

**Anlegen: Reihenfolge und Objektname** (Z. 274-319): Eingaben prüfen, dann Discovery, dann Ziel, dann Objekt bauen, dann schreiben, dann rücklesen.
```python
    object_name = f"{uuid.uuid4()}.ics"
    uid = object_name.removesuffix(".ics")
    ...
    await caldav.put_event(clients.client, clients.creds, target.uri, object_name, ics)

    confirmed = await _read_back(clients, target, object_name)
    ...
    result["created"] = True
    result["confirmed"] = confirmed is not None
```

**Rücklesen, nie ein Fehlschlag** (Z. 322-342):
```python
    try:
        events = await caldav.get_event(...)
    except ToolError:
        return None
    except (TimeoutError, httpx.TimeoutException, httpx.RequestError):
        return None
    return events[0] if events else None
```
Für Aufgaben zusätzlich: `confirmed` nur wahr, wenn das Objekt lesbar war UND die `UID` stimmt (Recherche F6).

**Objekt bauen, immer über icalendar** (`build_ics`, Z. 383-430). `VTIMEZONE` aus der zoneinfo-Datenbank:
```python
    if tzid is not None and isinstance(start, datetime) and start.tzinfo is not None:
        year = start.year
        component = IcsTimezone.from_tzinfo(
            start.tzinfo,
            tzid=tzid,
            first_date=date(year - 1, 1, 1),
            last_date=date(year + 5, 1, 1),
        )
        component.pop("COMMENT", None)
        calendar.add_component(component)
```
Für `VTODO`: `icalendar.Todo` statt `IcsEvent`, Pflichtfelder `UID`, `DTSTAMP`, `CREATED`, `LAST-MODIFIED`, `SUMMARY`.

**ANTI-MUSTER in `tools/calendar.py`:**
- `_all_day_window` (Z. 345-357) verschiebt das Ende um einen Tag (`finish = begin + timedelta(days=1)`). `DUE` ist kein exklusives Ende (TASK-05); ein `due` ohne Uhrzeit wird als `datetime.date` übergeben und ergibt `DUE;VALUE=DATE` auf genau dem genannten Tag.
- `_format` (Z. 457-461) und `_as_output` rechnen jede Zeit in die Anzeigezone um (`value.astimezone(zone)`). Auf eine schwebende Zeit angewandt nimmt Python die lokale Zone des Servers an: derselbe stille Fehler wie `caldav._value_of`. Die Zeitausgabe der Aufgaben läuft über die eigene Funktion der Zeitmatrix.
- `_sort_key` (Z. 433-437) setzt ein Datum auf Mitternacht UTC. Für Aufgaben ist die Ordnung "Datum gegen Zeit desselben Tages" eine eigene, getestete Festlegung (Annahme A10).
- `DEFAULT_LIMIT`/`MAX_LIMIT` mit hartem Abschneiden ohne Cursor (Z. 113-123): Aufgaben blättern (D-32-08).

**Cursor mit Bereichsbindung** (`tools/files.py` Z. 177-182 und 217-233):
```python
    offset = 0
    if cursor:
        state = paging.decode_cursor(cursor)
        paging.check_scope(state, "q", term, "search")
        paging.check_scope(state, "f", target_folder, "search")
        offset = paging.read_offset(state)
    ...
    window = hits[offset : offset + capped]
    ...
    if len(hits) > offset + capped:
        result["truncated"] = True
        result["next"] = paging.encode_cursor({"o": offset + capped, "q": term, "f": target_folder})
    elif at_ceiling:
        result["truncated"] = True
        result["note"] = f"{SEARCH_NOTE}; {SEARCH_CAP_NOTE}"
```
Konstanten-Stil (Z. 82, 91): `MAX_SEARCH_FETCH = 500` und `SEARCH_CAP_NOTE = f"result window capped at {MAX_SEARCH_FETCH} hits; narrow the folder or the term"`. `paging.check_scope` (paging.py Z. 99-111) vergleicht mit `!=` gegen einen `str`; jeder Bereichsschlüssel (Suchbegriff, Status, Grenze, Liste) wird einzeln geprüft. Ein leerer Wert muss auf beiden Seiten derselbe sein (zum Beispiel `""`), sonst lehnt die zweite Seite ihren eigenen Cursor ab. `MAX_CURSOR_CHARS = 512` (paging.py Z. 27) begrenzt, wie viel Bereich in den Cursor passt.

**Kappung ohne Marker im Text** (`tools/mail.py` Z. 547-563, Feldname Z. 493-504):
```python
def _capped(text: str) -> tuple[str, bool]:
    blob = text.encode("utf-8")
    if len(blob) <= MAX_PREVIEW_BYTES:
        return text, False
    return blob[:MAX_PREVIEW_BYTES].decode("utf-8", errors="ignore"), True
```
Der Vermerk ist ein Feld NEBEN dem Text mit eigenem Namen (`preview_truncated`, nicht `truncated`), weil `truncated` eine Ebene höher "diese Seite ist abgeschnitten" heißt. Für Aufgaben also zum Beispiel `description_truncated`, eigene Konstante statt `MAX_PREVIEW_BYTES`.

**Fremdtext ohne Marker** (`tools/marks.py` Z. 68-76, Aufrufe in `tools/chatgpt.py` Z. 409-410): `marks.without_marks(...)` auf Titel, Beschreibung, Tags und Listenname, bevor gekappt wird.

**Übersprungene Objekte zählen** (`tools/search.py` Z. 205-208):
```python
    if skipped:
        # Named, not swallowed: "some hits were unusable" is a sentence the model can pass
        # on, a shorter list without a word about it is not.
        result["skipped"] = skipped
```

**Leere Felder weglassen** (`tools/calendar.py` Z. 451-453): "Omitted when empty: every key costs tokens in every event of every answer."

---

### `src/mcp_connector/nextcloud/capabilities.py` (Plan 32-04, D-32-10)

**Analog:** `load_mail` (Z. 168-195) und das dreiwertige Feld (Z. 124-128).

**Nachfüllen in denselben Cache-Eintrag, mit dem ursprünglichen Zeitstempel:**
```python
    result = await load(clients)
    if result.mail_available is not None:
        return result

    response = await ocs.ocs_get(clients.client, clients.creds, NAVIGATION_PATH)
    filled = dataclasses.replace(
        result,
        mail_available=_navigation_lists_mail(ocs.parse_ocs(response, what=_NAVIGATION_WHAT)),
    )

    key = (clients.creds.base_url, clients.creds.user)
    cached = _cache.get(key)
    if cached is not None:
        _cache[key] = (cached[0], filled)
    return filled
```
Kein zweiter Modulzustand: `ALLOWED_MODULE_STATE` (`tests/contract/test_no_destructive_calls.py` Z. 360-365) nennt genau drei Stellen, darunter `("nextcloud/capabilities.py", "_cache")`.

**Eintrag erkennen** (Z. 242-245): `"mail" in (entry.get("app"), entry.get("id"))`, also `app` ODER `id`.

**Abweichung, die der Plan festhalten muss:** `_navigation_lists_mail` WIRFT bei leerer oder deformierter Antwort (Z. 234-241), und `ocs.ocs_get`/`parse_ocs` werfen bei Transportfehlern. D-32-10 verlangt das Gegenteil: "nicht erkennbar" heißt, der Hinweis entfällt, das Werkzeug arbeitet weiter. Die Aufgaben-Erkennung fängt `ToolError`, `httpx.TimeoutException` und `httpx.RequestError` und liefert `None`. Nie `require_app("tasks")` (Z. 203-217): das würde ohne App einen `AppMissingError` werfen. `Capabilities.has` (Z. 130-147) wirft `ValueError` für unbekannte Namen; ein Eintrag `tasks` dort ist nur nötig, wenn jemand `has("tasks")` ruft. `__all__` (Z. 37-47) um die neue Funktion ergänzen.

---

### `src/mcp_connector/server/reg_tasks.py` (neu, Plan 32-05)

**Analog:** `server/reg_calendar.py` (ganze Datei, 87 Zeilen). Der Bundle-Name `tasks` folgt aus dem Dateinamen (`server/__init__.py` Z. 179-189, `bundle_names`), der Import geschieht in `_load_registrations` (Z. 241-257); keine weitere Stelle anfassen.

**Imports** (Z. 8-15):
```python
from typing import Annotated

from mcp.server.mcpserver import Context
from pydantic import Field

from .. import deps
from ..tools import calendar as calendar_tools
from . import CREATE_ONLY, READ_ONLY, compact, graceful, mcp
```

**Lesendes Werkzeug** (Z. 18-48), Reihenfolge der Dekoratoren fest: `@mcp.tool` außen, `@graceful` innen, `ctx` als letzter Parameter, `deps.resolve_clients(ctx)`, `compact(...)`:
```python
@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def calendar_list_events(
    start: Annotated[
        str,
        Field(description="Window start, ISO 8601 with zone, e.g. 2026-09-01T00:00:00+02:00"),
    ],
    ...
    timezone: Annotated[
        str | None, Field(description="IANA zone for the output times, default UTC")
    ] = None,
    ctx: Context | None = None,
) -> str:
    """List calendar events in a time range (start and end are required, both with timezone)."""
    clients = deps.resolve_clients(ctx)
    return compact(await calendar_tools.list_events(clients, start=start, ...))
```

**Anlegendes Werkzeug** (Z. 51-87): `@mcp.tool(annotations=CREATE_ONLY, structured_output=False)`. `CREATE_ONLY` (`server/__init__.py` Z. 78-83) ist richtig für `tasks_create`: ein zweiter Aufruf ist eine zweite Aufgabe. NICHT `CREATE_IDEMPOTENT` (Z. 85-94, nur für `files_create_folder`).

**Audit-Zeile:** entsteht allein durch `@graceful` (Z. 109-176): `record.note(ctx, fn.__name__, outcome, reason, dauer)` im `finally`, Marker `wrapper.__mcp_audited__ = True`. In `reg_tasks.py` ist dafür nichts zu schreiben, aber der Funktionsname IST der Werkzeugname im Protokoll und in der Allowlist. `@graceful` liest `ctx` aus `kwargs` (Z. 140), deshalb heißt der Parameter immer `ctx`.

**Fehlerübersetzung:** ebenfalls `@graceful` (Z. 145-162): `ToolError` wird zu `"{message} Hint: {hint}"`, `httpx.TimeoutException` und `httpx.RequestError` zu festen Sätzen. In der Werkzeuglogik also `ToolError(message=..., hint=..., reason=...)` werfen, nie selbst Text formatieren.

**Impersonation:** `deps.resolve_clients(ctx)` liefert `NcClients` mit `Credentials`, deren `auth()` je nach Modus App-Passwort oder AppAPI-Kopf setzt. Jeder Request der Client-Schicht trägt `auth=creds.auth()` (caldav.py Z. 185, 293, 327, 355). Die Werkzeuglogik kennt den Modus nicht und nimmt nie einen Nutzerparameter.

**Budget (K9, TASK-08):** Der Prototyp von `tasks_create` misst 1417 Bytes und liegt über `MAX_TOOL_BYTES = 1400`. Vergleich: `calendar_create_event` mit acht Parametern steht bei 1351 Bytes (check_tool_budget.py Z. 118-119, 140). Die Decke wird nie angehoben ("a tool that reaches it gets a shorter description and never a higher limit", Z. 134-136); `mail_browse` wurde von 1585 gekürzt, nicht ausgenommen. Hebel im Stil der Datei: kurze `description` je Feld mit einem Beispiel nur dort, wo das Format sonst geraten wird (reg_calendar.py Z. 3-5), kein `limit`-Parameter in `tasks_search` (Seitengröße 25 fest, D-32-08). Die Titel-Diät (`_diet_tool_schemas`, `server/__init__.py` Z. 226-238) greift automatisch.

**Parametername `list`:** ruff wählt die Regelgruppe `A` (`pyproject.toml` Z. 82), ein Python-Parameter `list` meldet A002. Vorbild für "Drahtname ungleich Python-Name" ist `fetch` (`tools/chatgpt.py` Z. 214-215: `resource_id` im Paket, `id` auf dem Draht). In `reg_tasks.py` also `# noqa: A002` mit Begründung an genau dieser Stelle und Weitergabe als `list_name=`.

**Kein Nutzerparameter:** `FORBIDDEN_PROPERTIES = {"user", "username", "uid", "userid", "owner"}` (`test_tool_surface.py` Z. 96) prüft alle Schemas automatisch. Der Parameter der Elternaufgabe heißt deshalb `parent` (E7), und kein Antwortfeld sollte `owner` heißen (D-32-06).

---

### `src/mcp_connector/audit/allowlist.py` (Plan 32-05)

**Analog** (Z. 45-72), alphabetisch einsortiert; die drei Einträge kommen nach `"tables_create_row"` und vor `"talk_browse"`:
```python
    "calendar_create_event": frozenset({"all_day", "calendar", "end", "start", "timezone"}),
    "calendar_list_events": frozenset({"calendar", "end", "limit", "start", "timezone"}),
    ...
    "files_search": frozenset({"cursor", "folder", "limit", "query"}),
```
`summary` und `description` stehen schon in `FORBIDDEN_PARAMS` (Z. 23-34) und dürfen in keinem Eintrag auftauchen (`test_no_allowlisted_name_is_on_the_block_list`, `test_audit_surface.py` Z. 86). `query` ist bei `files_search`, `notes_search`, `contacts_search` erlaubt, also auch bei `tasks_search`. Jeder erlaubte Name muss im Schema des Werkzeugs existieren (Z. 71 des Tests), jedes Werkzeug braucht einen Eintrag (Z. 51). Ob `tags` in `FORBIDDEN_PARAMS` wandert, ist eine Entscheidung der Planung; wenn ja, greift `test_the_block_list_names_parameters_that_really_exist` (Z. 102) erst, sobald `tasks_create` registriert ist, also im selben Plan.

---

### Contract-Gates (Plan 32-05)

**`tests/contract/test_tool_surface.py`**
- `EXPECTED_TOOLS` (Z. 44-69): drei Namen ergänzen. Kommentar Z. 38 ("a twenty-fifth tool") nachziehen.
- `CREATE_TOOLS` (Z. 75-82): `tasks_create` aufnehmen; Kommentar Z. 71-74 ("stays six") und Z. 789, 800 nachziehen:
```python
    assert len(CREATE_TOOLS) == 6, "the create-only paths stay six; a folder is not a seventh"
```
wird 7. Auch Z. 481 ("the six write tools are unchanged") lesen. NICHT `IDEMPOTENT_CREATE_TOOLS` (Z. 84-88).
- Zahlen: Z. 568 und 573 (`len(tools) == 24`, "twenty-four"), Z. 857 ("all 24 schemas").
- Annotationen: `_check_annotations` (Z. 752-784) braucht keinen neuen Zweig; `tasks_create` fällt über `CREATE_TOOLS` in den vorhandenen, die zwei Leser in `else` (`read_only_hint is True`).
- README-Tabelle (Z. 872-899): liest nur `README.md`, Zeilen der Form ``| `name` | read | ...`` bzw. `create-only`; `set(documented) - {"files_update"} == set(tools)`.

**`tests/contract/test_tool_bundles.py`** (Z. 23-45, 83-96): `"tasks": frozenset({"tasks_search", "tasks_read", "tasks_create"})` und `"tasks"` in der sortierten Namensliste zwischen `"tables"` und `"talk"`.

**`tests/unit/test_disabled_tools.py`** (Z. 13-25): das Tupel `KNOWN` führt die Bundle-Namen ein zweites Mal; `"tasks"` ergänzen. Diese Stelle fehlt im Gate-Inventar der Recherche (F9).

**`tests/contract/tool_classes.py`** (Z. 89-118): drei Einträge in `UNAFFECTED`, je ein Satz mit `file:line`-Anker, mindestens 20 Zeichen, endet mit Punkt:
```python
    "calendar_list_events": (
        "Answers id, uid, summary, start, end, all_day, calendar and location only; ATTACH and "
        "DESCRIPTION are never parsed (tools/calendar.py:440-455, clients/caldav.py:391-406)."
    ),
```
Für Aufgaben trägt der Satz "ATTACH is never parsed" (TASK-04); `DESCRIPTION` wird hier anders als bei Terminen gelesen, der Satz muss das ehrlich sagen (Beschreibung ist Fremdtext, keine Datei). `PAIR_CASES` (Z. 126-143) bleibt unverändert; ein Paarfall für ein `UNAFFECTED`-Werkzeug macht das Gate rot (`test_a_pair_case_of_an_unaffected_tool_turns_the_freeze_red`). In Plan 32-06: der Anker im Satz von `fetch` (Z. 58-61, `tools/chatgpt.py:236-257`) verschiebt sich durch den neuen `case`.

**`tests/contract/test_tool_classes.py`**: Z. 19 `TOTAL = 24` auf 27, Meldung Z. 33-36, Docstring Z. 104, Aufteilung Z. 111-115 `(13, 4, 7)` auf `(13, 4, 10)`, Kommentar Z. 17-18.

**`tests/contract/test_no_destructive_calls.py`**: nichts ändern. `EXPECTED_PUT_CALLS = 6` (Z. 480) bleibt; ein siebter `.put(` irgendwo unter `src/` macht `test_every_put_carries_a_usable_precondition` rot. Zwei verschiedene Sechsen (Pitfall 7): `CREATE_TOOLS` wird 7, `EXPECTED_PUT_CALLS` bleibt 6.

**`vulture_whitelist.py`** (Z. 14-28): die Datei führt JEDE Werkzeugfunktion namentlich (`calendar_list_events`, `calendar_create_event`, `files_create_folder`, ...), weil der Dekorator sie registriert und kein eigener Code sie ruft. `tasks_search`, `tasks_read`, `tasks_create` dort ergänzen. Die Recherche (F9 Zeile 29) nennt die Datei nur bedingt.

---

### `scripts/check_tool_budget.py` (Plan 32-05, TASK-08)

**Analog:** Messzeilen Z. 105-114. Die letzte Zeile kündigt die Neuverankerung dieser Phase schon an:
```python
#   Measurement 2026-11-12, all 24 curated tools registered (files_create_folder of
#               FOLD-01): 16222 bytes. ...
#   Budget      stays at 18000 for now: re-anchored by the house rule on the measured end
#               state of the milestone (E1, TASK-08 in phase 32), and this measurement fits
#               below it. The 19000 above is the arithmetic of today and not a decision: ...
BUDGET_BYTES = 18_000
```
Neue Zeile im selben Stil anhängen: Datum, "all 27 curated tools registered (tasks_search, tasks_read, tasks_create of TASK-07)", gemessene Bytes, Rechnung "N + 15 percent = M, rounded up to the next 500 = B". Mit dem Prototyp der Recherche (rund 18840 Bytes) ergäbe das 21666 und damit 22000; verankert wird auf der ECHTEN Messung nach der Registrierung, nicht auf dem Prototyp (Annahme A11). Alte Zeilen bleiben stehen ("a regression is only attributable when the number it regressed from is still readable", Z. 70-71). `MAX_TOOL_BYTES = 1400` (Z. 149) unverändert. Ob Phase 33 (ändernde Werkzeuge) das Budget noch einmal bewegt, entscheidet der Plan; die Zeile Z. 110-114 sagt "once, at the end".

---

### `scripts/acceptance_all_tools.py` (Plan 32-05)

**Analog:** Block `# --- calendar` (Z. 269-291) und die Folgeprüfung des Ordner-Blocks (Z. 209-219):
```python
    folder = {"path": f"/{marker}-{stamp}-ordner/a/b", "parents": True}
    await call(client, report, "files_create_folder", folder)
    again = await call(client, report, "files_create_folder", folder)
    if again and loads(again).get("created") is not False:
        report.add(
            "files_create_folder",
            "FAIL",
            f"the second call did not answer created false: {again.splitlines()[0]}",
        )
```
Neu: Block `# --- tasks` mit `tasks_create` (Titel mit `marker`), `tasks_search` findet sie (Treffer per Id, nie per Position, vgl. Z. 221-228), `tasks_read` liest sie, `fetch` liest dieselbe Id (Plan 32-06). Die erwartete Werkzeugmenge liest das Skript aus `tools/list` (Z. 183-199), keine Zahl im Skript.

---

### `tests/integration/test_canary.py` und `canary_world.py` (Plan 32-05)

**Zahl und Schreibarten** (`test_canary.py` Z. 63, 80-86):
```python
EXPECTED_TOOLS = 24
WRITE_KINDS: dict[str, str] = {
    "calendar_create_event": "event",
    "deck_create_card": "card",
    "tables_create_row": "row",
    "notes_create": "note",
    "talk_send": "message",
}
```
27, plus `"tasks_create": "task"`. `book_write` (Z. 277-286) liest `data.get("id")` aus der Antwort: `tasks_create` muss die `task:`-Id im Feld `id` liefern.

**Zwei weitere Stellen für die neue Art `task`:**
- `canary_world.WRITE_KINDS = ("event", "card", "row", "note", "message")` (Z. 774), geprüft in `register_tool_write` (Z. 903-914).
- `_add_tool_write` (Z. 937-998): die Arten werden per `if/elif` behandelt, und der letzte `else`-Zweig (Z. 992-998) ist stillschweigend "message". Eine Art `task` ohne eigenen Zweig würde als Talk-Nachricht aufgeräumt. Vorbild ist der Zweig `event` (Z. 943-949):
```python
    if kind == "event":
        url = f"{harness.calendar_url(parts[0])}{quote(parts[-1], safe='')}"
        cleanup.add(
            f"tool {entry}",
            lambda: harness.delete_calendar_url(url),
            lambda: str(harness.status_of(url)),
        )
```
`harness.delete_calendar_url` sendet `X-NC-CalDAV-No-Trashbin: 1` (Z. 108, 556-557); der Lesebeweis ist ein `PROPFIND`, erwartet 404.

**Plan-Einträge** (`test_canary.py` Z. 197-211): je Werkzeug eine Liste von Argument-Dicts, Kalender über `world.stamm` benannt. Für Aufgaben drei Einträge; `tasks_create` mit `"list": world.stamm`, weil die Testinstanz mehr als eine eigene Liste hat (`personal` trägt `VEVENT,VTODO,VJOURNAL`).

**Kalender der Welt** (`canary_world.py` Z. 541-554, 1193-1217): `mkcalendar` baut den Körper per f-String und nur mit `VEVENT`:
```python
            '<c:supported-calendar-component-set><c:comp name="VEVENT"/>'
```
Entweder um `VTODO` erweitern (ändert die Kanarienwelt des Kalender-Bundles) oder eine zweite Sammlung nur für Aufgaben anlegen. Besser lesbares Vorbild für den Körper: `mkcalendar_body` im Spike (`scripts/tasks_spike.py` Z. 2405-2414, lxml, `components=("VTODO",)`). Aufräumbeweis nach `_build_calendar` (Z. 1197-1201): `cleanup.add(was, undo, read)`.

**Deck-Beweis** (`_build_deck`, Z. 1220-1244): die Karte wird heute ohne Beschreibung angelegt (`{"title": world.stamm, "type": "plain", "order": 999}`). Für TASK-07 eine Beschreibung mit EIGENEM Marker setzen (nicht `world.marker`, Pitfall 9) und nur gegen die Antworten der drei Aufgabenwerkzeuge prüfen, mit Positivkontrolle über `harness.deck("GET", ...)` (Z. 569-575) und `world.proof[...]` (Z. 1243).

**Kontrollerwartung:** `control_expected` (`test_canary.py` Z. 233-247) nennt die Leser, die den Kontrollmarker zeigen müssen; `tasks_search` gehört nur hinein, wenn die Welt eine Aufgabe mit Kontrollmarker anlegt.

---

### `tests/integration/test_tasks_live.py` (neu, Plan 32-05 und 32-07)

**Analog:** `tests/integration/test_files_create_folder_live.py`.

**Kopf** (Z. 1-41): Frage, Form der Protokollzeile, Laufanleitung für beide Topologien (die Env-Dateien werden nur per `set -a && . <datei> && set +a` geladen, nie gelesen oder zitiert).

**Umgebung und Impersonation** (Z. 77-87, 363-398):
```python
REQUIRED = {
    "base_url": "NC_MCP_URL",
    "app_id": "APP_ID",
    "app_secret": "APP_SECRET",
    "app_version": "APP_VERSION",
    "alice": "NC_MCP_TEST_USER",
    ...
}
```
```python
    return NcClients(
        client=httpx.AsyncClient(
            follow_redirects=False, timeout=30.0, event_hooks={"response": [hook]}
        ),
        creds=Credentials(
            base_url=run.env["base_url"],
            user=user,
            secret=secret or run.env["app_secret"],
            mode=MODE_APPAPI,
            app_id=run.env["app_id"],
            app_version=run.env["app_version"],
            aa_version=run.env["aa_version"],
        ),
    )
```
`app_version` kommt aus der Umgebung der Topologie; nie eine erfundene Version senden (Pitfall 6: AppAPI hebt die gespeicherte Version und senkt sie nie). Der Response-Hook (Z. 371-383) notiert Methode, Bereich und Status; für Aufgaben den Präfix `remote.php/dav/calendars/<user>` statt `dav.DAV_FILES_PREFIX`.

**Erst protokollieren, dann prüfen** (`Case`, Z. 330-360): `__exit__` schreibt die Zeile `ORDNER <fall> nc=<version> nutzer=<uid> status=<calls> ergebnis=<ok|befund> | ...` und assertet danach. Für Aufgaben ein eigenes Zeilenwort (zum Beispiel `AUFGABE`).

**Lauf mit Vorher/Nachher** (Z. 296-327): `cw.live_env()`, `cw.Harness`, `baseline` vor und nach, Aufräumen im `finally` über das Harness, nie über den Connector; Caches vor jedem Fall leeren (`capabilities.clear_cache()`, Z. 406-407), sonst antwortet die Erkennung der Tasks-App aus dem Zwischenspeicher.

**Kontrollen zuerst** (Z. 434-490): "der Messprozess hält kein App-Passwort" und "falsches `APP_SECRET` legt nichts an". Ohne sie ist der Rest wertlos (Überschrift Z. 434).

**Gegenprobe mit unabhängigem Muster** (Z. 18-19): "nichts angelegt" wird im Dateisystem des Containers geprüft, nicht mit dem Weg der Umsetzung. Für Aufgaben: Gegenprobe über die Tabelle `calendarobjects` per `occ`/PHP im Container (Vorbild `scripts/tasks_spike.py`, `PHP_OBJECT_ROWS` Z. 4016 ff., `db_rows` Z. 4186) oder ein Harness-`PROPFIND` mit App-Passwort.

**Schalter für CI, Abweichung vom Vorbild:** die Ordner-Datei überspringt hart (Z. 269-273):
```python
    if missing:
        pytest.skip(f"no ExApp topology configured (missing: {', '.join(missing)})")
```
Sie kennt `NC_MCP_REQUIRE_LIVE` nicht; das ist die Lücke W3 aus Phase 31. Der Schalter liegt in `canary_world.py` Z. 113-120:
```python
ENV_REQUIRE_LIVE = "NC_MCP_REQUIRE_LIVE"

def skip_or_fail(reason: str) -> NoReturn:
    """Skip without a live setup; fail when the run demands one (:data:`ENV_REQUIRE_LIVE`)."""
    if (os.environ.get(ENV_REQUIRE_LIVE) or "").strip() == "1":
        pytest.fail(f"{ENV_REQUIRE_LIVE}=1 but {reason}", pytrace=False)
    pytest.skip(reason)
```
`test_tasks_live.py` ruft an der Stelle von `pytest.skip` also `cw.skip_or_fail(...)`. Der Schalter darf nur am SCHRITT gesetzt sein, nie am Job: der Job `integration` (`ci.yml` Z. 268-271) läuft mit `uv run pytest -m integration` über alle Integrationsdateien ohne ExApp-Variablen, dort muss die Datei weiter überspringen.

---

### `.github/workflows/ci.yml` und `tests/unit/test_live_requirement.py` (Plan 32-05, D-32-11)

**Analog Schritt im Job `exapp`** (Z. 102-106, 34.0.3, Bein "ohne Tasks-App"):
```yaml
      - name: DAV impersonation matrix over the full chain (AUTH-05)
        # The bootstrap wrote .env.exapp with the deploy identity and both app passwords.
        run: |
          set -a && . ./.env.exapp && set +a
          uv run pytest tests/integration/test_exapp_dav_matrix.py -m integration
```

**Analog Schritt im Job `canary-nc35`** (Z. 201-219, mit Schalter):
```yaml
        env:
          PYTHONUTF8: "1"
          NC_MCP_REQUIRE_LIVE: "1"
        run: |
          set -a && . ./.env.exapp && set +a
          uv run pytest tests/integration/test_canary.py tests/integration/test_pair_equality_live.py tests/integration/test_provider_classes_live.py -m integration -s
```

**Analog "Zustand der Instanz als Schritt beweisen"** (Z. 188-194, `occ status` plus `grep` ohne `-q`): dieselbe Form für `occ app:list` mit der Fassung der Tasks-App.

**Zwänge aus `tests/unit/test_live_requirement.py`:**
- Z. 39-48: es gibt GENAU EINEN Schritt, der `tests/integration/test_canary.py` nennt, und er trägt `NC_MCP_REQUIRE_LIVE: "1"`, `test_pair_equality_live.py` und `test_provider_classes_live.py`. Der Live-Test der Aufgaben ist deshalb ein eigener Schritt oder wird an die Kommandozeile dieses einen Schritts angehängt, nie ein zweiter Schritt mit `test_canary.py`.
- Z. 56-74: der Kanarien-Schritt liegt im Job `canary-nc35`; im Job `exapp` darf `test_canary.py` nicht vorkommen.
- Vorbild für einen Pin der neuen Schritte: `test_the_ci_step_of_the_gates_sets_the_switch` (Schritte per `re.split(r"\n      - name: ", workflow)` trennen, dann Text prüfen).

**Kein Vorbild:** ein Schritt "Store-App installieren, Nextcloud-Container neu starten, warten". Nächste Verwandte sind `bash scripts/install_findling.sh` (Z. 113-119, installiert eine App in die laufende Topologie) und der Neustart-Test in `tests/integration/test_oauth_flow_exapp.py` (wartet nach einem Container-Neustart auf die erste gute Antwort, Schleife bis Z. 232). Der Neustart ist nötig, weil Provider-Liste und Navigation nach `app:install`/`app:disable` bis zum neuen PHP-Prozess die alte Wahrheit zeigen (Pitfall 8, gemessen in `tests/integration/test_srv06_degradation.py`).

`test_provider_classes_live.py` bleibt mit Tasks-App grün: `provider_classes.py` Z. 57 führt `tasks` bereits.

---

### Doku (Plan 32-05, 32-06)

**`README.md`** (de/fr gleichlaufend, R2):
- Z. 25: "24 tools across nine app families: files, calendar, notes, Deck, contacts, Tables, Talk, ..." wird 27 und zehn Familien mit "tasks" (de Z. 28 "24 Tools über neun App-Familien", fr Z. 28 "24 outils répartis sur neuf familles d'applications").
- Tabellenzeile, Vorbild Z. 72 (Stufe exakt `read` oder `create-only`, nur `README.md` wird vom Test gelesen):
```markdown
| `files_create_folder` | create-only | A new folder, optionally with its missing parents (at most 10 per call); an existing folder answers created false, nothing is overwritten |
```
- Z. 90, Zeile `fetch` (Plan 32-06): "resolves an id to a file, note, card, event, mail, Talk message or table" um "task" ergänzen.
- Bundle-Liste Z. 116-129, alphabetisch zwischen `tables` und `talk`:
```markdown
  - `tables`: `tables_browse`, `tables_create_row`
  - `talk`: `talk_browse`, `talk_send`
```
- Die neun Punkte aus `31-06-SUMMARY.md` (README-Faktencheck für Phase 34) nicht verschlimmern.

**`appinfo/info.xml` Z. 573:** "Valid names: calendar, chatgpt, contacts, context, deck, files, mail, notes, search, tables, talk." um `tasks` ergänzen. Kein Store-Text (`test_store_texts_frozen.py` pinnt nur `summary` und `description` direkt unter `info`).

**`docs/folder-evidence.md` (K10, Pitfall 12):** Z. 461 und 484 nennen "all 24 tools" ohne Verweis. Heute grün, weil 24 die aktuelle Zahl ist; bei 27 macht `test_a_documented_tool_count_is_the_current_one_or_says_which_run_it_is_from` (`test_tool_surface.py` Z. 902-926) die Seite rot. Das Gate prüft nur, ob der String `tests/contract/test_tool_surface.py` irgendwo in der Seite steht:
```python
        explained = holder in text
        for number, line in _counted_tools(text):
            if number != current and not explained:
                unexplained.append(f"{page.name}: {line.strip()}")
```
Vorbild für die Verweiszeile: `docs/n8n-setup.md` Z. 258-259 ("the number is not held by this page. `tests/contract/test_tool_surface.py` holds it"), `docs/nc35-evidence.md` Z. 97. Die zitierten Belegzeilen bleiben wörtlich. Alle anderen Seiten unter `docs/` mit abweichender Zahl tragen den Verweis schon (geprüft: client-setup, conference-demo, n8n-setup, nc35-evidence, oauth-setup, spike-discovery, spike-opendesk, spike-tasks, store-submission). Die neue `docs/tasks-evidence.md` braucht den Verweis von Anfang an, weil Phase 33 die Zahl wieder bewegt.

**`docs/hardening*.md`:** keine Liste der Bundle-Namen vorhanden (einziger Treffer der Namensliste im Repo außerhalb der Tests ist `appinfo/info.xml:573` und die READMEs). TASK-07 nennt die Dateien trotzdem; der Plan hält fest, dass dort nichts zu ändern ist, oder benennt die gemeinte Stelle (Offene Frage 4 der Recherche).

**`CHANGELOG.md`, `.de.md`, `.fr.md`:** unter `## [Unreleased]` (Z. 12) steht schon ein `### Added` (Z. 14-33) mit dem Ordner-Eintrag; die Aufgaben-Punkte kommen in denselben Abschnitt. Stil: ein Punkt je Aussage, Werkzeugname in Backticks, letzter Punkt verweist auf den Beleg ("Measured on Nextcloud 32 and 35 under AppAPI impersonation, see `docs/folder-evidence.md`."). `tests/unit/test_changelog_translations.py` hält die drei Sprachen gleich. Keine schließenden Schlüsselwörter.

---

### `src/mcp_connector/provider_map.py` (Plan 32-06, TASK-09)

**Analog:** Eintrag mit Quellenkommentar (Z. 81-84) und ein eigener Linkleser (Z. 242-253).
```python
    # Verified against nextcloud/tables lib/Search/SearchTablesProvider.php, class
    # SearchTablesProvider: it sets no attributes at all, and getInternalLink builds
    # "#/" . $nodeType . "/" . $nodeId with $nodeType being "table" or "view".
    "tables-search-tables": "table",
```
```python
def _tables_node(url: str) -> tuple[str, str] | None:
    match = _TABLES_NODE.fullmatch(urlsplit(url).fragment)
    if match is None:
        return None
    return match.group(1), match.group(2)
```
**Zweig in `extract_id`** (Z. 164-173): Kind aus der Tabelle, Leser liefert die Teile oder `None`, sonst ehrlicher Rückfall auf `url`:
```python
    elif kind == "table":
        node = _tables_node(url)
        if node is not None and node[0] == "table":
            return "table", ids.encode_table(node[1]), True

    if not url:
        return None
    return UNKNOWN_KIND, ids.encode_url(url), False
```
**Gemessene Linkform** (`scripts/tasks_spike.py` Z. 6126, 6414-6423):
```python
_PROVIDER_LINK = re.compile(r"/apps/tasks/(?:#/)?calendars/([^/?#]+)/tasks/([^/?#]+)$")
```
Die Regex läuft im Spike über den ganzen Link; `provider_map` arbeitet mit `urlsplit` und liest Pfad und Fragment getrennt (Z. 121-124, 250). Der Linkleser der Aufgaben muss beide Orte prüfen und `unquote` anwenden. Die URL wird nur geparst, nie abgerufen, und immer auf `base_url` neu gebaut (`absolute_url`, Z. 112-124, T-01-68). Der Modul-Docstring (Z. 1-44) erklärt jede bewusste Lücke; ein Absatz für Aufgaben gehört dazu (Abo-Treffer und Deck sind nicht auflösbar, K2).

---

### `src/mcp_connector/tools/chatgpt.py` (Plan 32-06)

**Analog Routing** (Z. 236-256): ein `case` je Kind, Teile aus dem Codec:
```python
    kind, parts = ids.parse(resource_id)
    match kind:
        ...
        case "event":
            return await _fetch_event(clients, parts[0], parts[1])
```
**Analog Antwortform** (`_fetch_event`, Z. 475-511): `id` aus dem Codec, `title`, `text` über `marks.without_marks`, nicht leere `url` auf `clients.creds.base_url`, `metadata` mit `kind`:
```python
    return {
        "id": ids.encode_event(calendar_uri, object_name),
        "title": str(event["summary"]),
        "text": marks.without_marks("\n".join(lines)),
        "url": f"{clients.creds.base_url}{CALENDAR_WEB_PREFIX}/{start[:10]}",
        "metadata": metadata,
    }
```
**Nicht übernehmen:** `_fetch_event` liest über `caldav.get_event` und damit über `parse_ics` und `_value_of` (Anti-Muster oben). Außerdem reicht es `calendar_uri` ohne Discovery-Prüfung durch und schreibt die URI in `metadata["calendar"]`. `_fetch_task` ruft dieselbe öffentliche Lesefunktion wie `tasks_read` (Discovery-Prüfung inklusive: Deck, Abo, Papierkorb antworten wie eine unbekannte Id), gibt nie die URI einer geteilten Liste aus und verlinkt für geteilte Listen nur die Startseite der Tasks-App (D-32-15). Zugriff nur auf ÖFFENTLICHE Namen von `tools/tasks.py` (Modulgrenzen-Gate).

**Docstring** (Z. 15-52): "Seven properties of that routing are load bearing" und "Every one of the seven readers" zählen die Leser; beide Stellen nachziehen.

---

### Tests zu Plan 32-06

- `tests/unit/test_provider_map.py`: Tables-Fälle Z. 253-300 als Vorbild (Treffer aus dem Fragment, View bleibt `url`, nicht numerisch bleibt `url`, fremder Ursprung erreicht die Id nie). Für Aufgaben: Pfadform, Fragmentform, mit `index.php`, Sonderzeichen in URI und Objektname, geteilte Liste ergibt den Schlüssel statt der URI, jede andere Form bleibt `url`. `test_every_provider_id_in_the_readmes_is_one_that_exists` (Z. 362) liest Provider-Ids aus den READMEs.
- `tests/unit/test_chatgpt_fetch.py`: `test_an_event_id_is_read_from_caldav` (Z. 648-662) als Vorbild; Docstring Z. 1 "all eight id kinds" wird neun. Negativtests: `task:`-Id auf `app-generated--...` und auf ein Abo antworten wie eine unbekannte Id, ohne Request an das Objekt.

---

### `scripts/tasks_chain_evidence.py` (neu, Plan 32-07)

**Analog:** `scripts/folder_chain_evidence.py` (157 Zeilen, ganz übernehmen und verallgemeinern).

**Client-Hälfte laden statt wiederholen** (Z. 57-66):
```python
def _load_flow_check() -> ModuleType:
    path = REPO_ROOT / "scripts" / "oauth_flow_check.py"
    spec = importlib.util.spec_from_file_location("oauth_flow_check", path)
    ...
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
```
**Token nie im Repo** (Z. 77-82):
```python
    path = Path(raw).resolve()
    if path.is_relative_to(REPO_ROOT):
        raise SystemExit("--token-file has to lie outside the repository")
```
**Eine Zeile je Aufruf, Ablehnung ist eine Messung** (Z. 125-137):
```python
    result = asyncio.run(flow_check.tool_call(base, token, TOOL, arguments))
    answer = " ".join(_one_line(text) for text in flow_check.texts_of(result))
    failed = "ja" if result.is_error else "nein"
    sent = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    print(f"{args.label} {args.case} nutzer={user} argumente={sent} fehler={failed} | {answer}")
    return 0
```
Unterbefehle `connect`, `tools`, `call` (Z. 140-153). Anpassung: `TOOL` ist heute eine Konstante (Z. 46) und `call` kennt nur `--path`/`--parents`; für drei Werkzeuge plus `fetch` braucht `call` ein `--tool` und Argumente als JSON. Der Git-Bash-Hinweis (Z. 30-31, führender Schrägstrich) gilt für Pfade, nicht für `task:`-Ids. Das Skript fasst Docker nie an und löscht nichts (Z. 21-24): Aufbau, Gegenprobe und Rückbau sind getrennte Schritte.

---

### `docs/tasks-evidence.md` (neu, Plan 32-07)

**Analog:** `docs/folder-evidence.md`. Kopf (Z. 1-10: Date, Subject, Status), Liste der Rohprotokolle mit relativen Links nach `../.planning/phases/<phase>/raw/` (Z. 16-29), Instanztabelle mit `occ status`, Topologie, AppAPI-Fassung, registrierter App und Konten (Z. 31-39), danach Method, je Fassung ein Abschnitt, "What the run found", "Not reproducible or not measured", "Whole chain through the installed app". Stabile Anker entstehen aus den Überschriften (`#whole-chain-through-the-installed-app`). Zusätzlich für diese Phase: Fassung der Tasks-App (D-32-11), getrennte Abschnitte "mit Tasks-App" und "ohne", der Verweis auf `tests/contract/test_tool_surface.py` (Zählgate). Jede zitierte Zeile steht wörtlich im Rohprotokoll.

## Shared Patterns

### Fehlerklassen und Gründe
**Quelle:** `src/mcp_connector/errors.py` Z. 34-39, 97-115; Anwendung `clients/caldav.py` Z. 468-481
**Gilt für:** `clients/tasks.py`, `tools/tasks.py`, `_fetch_task`
`ToolError(message, hint, reason=...)`, `ConflictError` für 412, `REASON_PERMISSION_DENIED` (403), `REASON_UNKNOWN_ID` (404, 409), `REASON_GUARD_TRIPPED` für jede Ablehnung vor dem ersten Request. `reason` nur an den Statuszweigen. Kein Servertext in Meldungen. Jede Meldung hat einen Ausweg im `hint`; der Ausweg nennt nur Werkzeuge des eigenen Bundles (`tasks_search`), weil andere Bundles abgeschaltet sein können.

### Audit, Fehlerübersetzung, Impersonation
**Quelle:** `server/__init__.py` Z. 109-176 (`graceful`), `audit/allowlist.py`, `deps.resolve_clients`
**Gilt für:** `reg_tasks.py`
Nichts davon wird im Bundle neu gebaut. Pflicht sind: `@graceful` direkt unter `@mcp.tool`, Parameter `ctx`, ein Allowlist-Eintrag je Werkzeug, `auth=creds.auth()` an jedem Request.

### Request-Körper und Antworten
**Quelle:** `clients/caldav.py` Z. 12-14 (Modulregel), Z. 144-155; `clients/xml.py` Z. 28-62
**Gilt für:** jeden PROPFIND- und REPORT-Körper, auch im Messprogramm
Kein XML-Literal im Produktcode (T-01-45): Körper mit `lxml.etree`, Antworten über `xml.parse_root`. Der f-String-Körper in `canary_world.Harness.mkcalendar` ist Test-Harness und kein Vorbild für `src/`.

### Antwortform
**Quelle:** `server/__init__.py` Z. 104-106 (`compact`), `tools/calendar.py` Z. 440-454
**Gilt für:** alle drei Werkzeuge
Kompaktes JSON, leere Felder weglassen, Kürzungsvermerke als eigenes Feld neben dem Text, `degraded` als Liste von `{"<was>": name, "reason": satz}`, `skipped` als Zahl, `note` für den Deckel.

### Geteilte Listen ohne Personenbezug (D-32-06, D-32-14, D-32-15)
**Quelle:** kein Vorbild im Code; nächste Verwandte ist die Regel "nie einen fremden Ursprung behalten" in `provider_map.py` Z. 18-21
**Gilt für:** jede Ausgabe von `clients/tasks.py`, `tools/tasks.py`, `_fetch_task`, jede Fehlermeldung, jeden `degraded`-Eintrag, `metadata` in `fetch`
Die URI einer geteilten Liste (`<uri>_shared_by_<Kennung>`) und der rohe `displayname` (`<Name> (<Besitzer>)`) verlassen die Client-Schicht nur als Request-URL, nie als Antworttext. Prüfmuster für Tests und Live-Beweis: Rohtext der ganzen Antwort nach der Kennung und dem Anzeigenamen des Besitzers durchsuchen (wie `everything_but` in `test_injection_corpus.py` Z. 88-96 und `result_shapes.leaks`, `tests/contract/result_shapes.py` Z. 93-95).

### Testaufbau Unit
**Quelle:** `tests/unit/test_calendar_tools.py` Z. 1-75, `tests/unit/test_caldav_client.py` Z. 1-60
**Gilt für:** `test_tasks_client.py`, `test_tasks_tools.py`, `test_tasks_time_matrix.py`
```python
BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
CALENDAR_HOME = f"{BASE}/remote.php/dav/calendars/alice/"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )

def mock_discovery(mock: respx.MockRouter) -> respx.Route:
    return mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
        return_value=dav_response(fixture("caldav_calendars_207.xml"))
    )
```
`respx.mock(assert_all_called=True)`, Routen per `method=` und `url=`, `@pytest.mark.anyio`, Zählung über `route.call_count`. "Abgelehnt vor dem Request" wird über eine nicht gerufene Route belegt (Testnamen `..._is_refused_before_any_request`, test_calendar_tools.py Z. 158-210).
Fixtures dieser Phase: `tests/fixtures/caldav_home_fresh_account.xml` (TASK-03), `tests/fixtures/caldav_home_task_lists.xml` (eigene, geteilte, Deck), `tests/fixtures/tasks_app/*.ics` (acht Objekte, `PROVENANCE.md`). Sie tragen die CRLF des Servers und sind per `.gitattributes` (`-text`) von der Umwandlung ausgenommen: nie umschreiben, als Bytes lesen, wenn es auf Bytes ankommt. Formen, die die Tasks-App nicht schreibt (`TZID`, schwebend, mehrere `CATEGORIES`- oder `RELATED-TO`-Zeilen), werden im Test von Hand gebaut (Pitfall 11).

### Benannte Matrix-Tests
**Quelle:** `tests/unit/test_caldav_client.py` Z. 1-14 (Docstring nennt die Fälle), Z. 248-335 (`test_matrix_a_...` bis `test_matrix_d_...`)
**Gilt für:** Zeitmatrix TASK-04 (ganztägig, mit Zone, UTC, schwebend, ohne Datum)
Jede Zeile der Matrix ist ein Test mit dem Fall im Namen; der Modul-Docstring zählt die Fälle auf.

### Injektionskorpus
**Quelle:** `tests/unit/test_injection_corpus.py` Z. 137-181
**Gilt für:** Titel, Beschreibung (gekappt), Tags aus einer geteilten Liste
```python
    assert result["events"][0]["summary"] == INJECTION, "character for character, as data"
    assert INJECTION not in everything_but(result, "events")
```
`INJECTION` kommt aus `test_tools_context.py` (Import Z. 28). Dazu der Fall "gefälschte Markerfolge wird gefiltert" nach `tests/unit/test_truncation_marks.py`.

### Gate-Lauf am Ende jedes Plans (R1)
**Quelle:** `.github/workflows/ci.yml` Z. 29-46
`uv run pytest tests/unit tests/contract`, `uv run python scripts/check_tool_budget.py`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright` (lokal mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`), `uv run vulture src scripts vulture_whitelist.py`. `pytest` läuft mit `--import-mode=importlib` und `pythonpath = ["tests/integration", "tests/unit", "tests/contract"]` (`pyproject.toml` Z. 58, 71): Hilfsmodule wie `canary_world`, `topology`, `guard_routes`, `tool_classes` werden ohne Paketpfad importiert.

### Rohprotokoll und Geheimnisse
**Quelle:** `scripts/tasks_spike.py` Z. 836-871, `scripts/folder_chain_evidence.py` Z. 26-28, 77-82
**Gilt für:** Pläne 32-01, 32-02, 32-07
Rohprotokolle unter `raw/` des Phasenordners; jede Ausgabe erst außerhalb des Repos schreiben, gegen alle Werte der Env-Dateien und deren erste 12 Zeichen prüfen, dann anhängen (Pitfall 2). Token-Dateien liegen außerhalb des Repos. Env-Dateien werden geladen, nie gelesen oder zitiert.

## Abweichungen zwischen Recherche und Code

Befunde aus dem Lesen des Codes, die 32-RESEARCH.md anders oder gar nicht nennt. Der Planer sollte sie vor dem Zuschnitt prüfen.

| # | Stelle | Recherche sagt | Code zeigt | Folge |
|---|---|---|---|---|
| A | `tests/unit/test_ids.py` Z. 167-170 | F8: "`_HINT` ist nirgends in Tests wörtlich gepinnt" | `test_the_hint_every_tool_prints_names_all_eight_forms` prüft acht Präfixe in `ids._HINT`; `test_roundtrip_for_all_eight_kinds` Z. 20 | Nicht wörtlich, aber als Vertrag gepinnt. Tests auf neun Formen heben, samt Namen. Auch `test_chatgpt_fetch.py` Z. 1 |
| B | `vulture_whitelist.py` Z. 14-28 | F9 Zeile 29: "nur falls neue öffentliche Namen nur aus Tests erreicht werden" | jede Werkzeugfunktion steht namentlich in der Liste | drei Einträge sind Pflicht, sonst ist `vulture` rot |
| C | `tests/unit/test_disabled_tools.py` Z. 13-25 | nicht im Gate-Inventar | `KNOWN` listet die elf Bundle-Namen | `tasks` ergänzen (Stelle 31 des Inventars) |
| D | `tests/integration/canary_world.py` Z. 774, 937-998 | F9 Zeile 16/17 nennt `register_tool_write` | `WRITE_KINDS` steht zweimal (Tupel in `canary_world`, Dict in `test_canary`), und `_add_tool_write` endet in einem `else`, das "message" meint | neue Art `task` braucht einen eigenen `elif`-Zweig, sonst wird sie als Talk-Nachricht aufgeräumt |
| E | `tests/integration/test_files_create_folder_live.py` Z. 269-273 | F9 Zeile 30: "neu, mit `NC_MCP_REQUIRE_LIVE`-Zweig" (Vorbild Phase 31) | das Vorbild kennt den Schalter nicht, es ruft `pytest.skip` | Schalter aus `canary_world.skip_or_fail` (Z. 113-120) übernehmen; nur am CI-Schritt setzen, nie am Job |
| F | `tests/unit/test_live_requirement.py` Z. 39-74 | nicht genannt | pinnt "genau ein CI-Schritt mit `test_canary.py`", Job `canary-nc35`, `exapp` ohne `test_canary.py` | CI-Schritte für D-32-11 daran ausrichten; eigener Pin für die neuen Schritte nach demselben Muster |
| G | `scripts/tasks_spike.py` Z. 6264-6270, 6287-6289 | Pattern 1 Schritt 5 und 6: "geteilt" = `oc:read-only` im 2xx-Propstat (URI nur Gegenprobe); Schreibrecht = `write` oder `write-content` | der Spike klassifiziert "geteilt" über `_shared_by_` in der URI und liest `read-only` nur für lesbar/schreibbar; `writable` akzeptiert `write`, `write-content`, `bind`, `all` | beide Merkmale gegen `tests/fixtures/caldav_home_task_lists.xml` prüfen und die Regel im Plan festschreiben; Privilegienmenge begründen |
| H | `scripts/tasks_spike.py` Z. 6325-6327 | K5/F4: `text-match` mit `collation="i;octet"` senden | gemessen ist `match-type="contains"` ohne `collation` | Form mit `collation` ist ungemessen: Messzeile in Plan 32-02 |
| I | `capabilities.py` Z. 234-241 | Pattern 6: "Fehler oder deformierte Antwort heißen nicht erkennbar (wie `_navigation_lists_mail`)" | `_navigation_lists_mail` wirft in diesem Fall einen `ToolError` | Aufgaben-Erkennung fängt und liefert `None`; kein blindes Kopieren von `load_mail` |
| J | `clients/caldav.py` Z. 234-244 | F2: `_ok_props` öffentlich machen oder nachbauen | `_ok_props` liefert nur das erste 2xx-Propstat und kennt keine 404-Propstats | nachbauen nach dem Spike (Z. 6207-6213), nicht öffentlich machen: das hielte `caldav.py` unverändert und liefert, was die Aufgaben-Discovery braucht |
| K | Zeilenangaben | `check_tool_budget.py:113` für `BUDGET_BYTES`; `mail._capped` Z. 548-563; README-Bundle-Liste Z. 116-131 | `BUDGET_BYTES` Z. 115, `MAX_TOOL_BYTES` Z. 149; `_capped` Z. 547-563; Bundle-Liste Z. 116-129 | nur Verweise in den Plänen korrigieren |
| L | `scripts/check_tool_budget.py` Z. 105-114 | K9: "Neuverankerung bei etwa 22000" | die Datei rechnet für 24 Werkzeuge 19000 vor und verschiebt die Entscheidung ausdrücklich auf TASK-08 ("once, at the end") | Zahl erst aus der echten Messung; im Plan klären, ob Phase 33 die Verankerung noch einmal bewegt |
| M | `scripts/bootstrap_exapp.sh` Z. 1326-1337 | F10: "`ensure_app` installiert heute schon notes, deck, tables, mail, spreed" | richtig, aber die Liste läuft in jedem Modus und in beiden CI-Jobs | `tasks` nicht in die feste Liste, sonst gibt es kein Bein "ohne Tasks-App" |
| N | `tools/chatgpt.py` Z. 475-511 | F8: `_fetch_task` nach dem Muster der Leser | `_fetch_event` gibt die Kalender-URI in `metadata` aus und liest über `parse_ics`/`_value_of` | Form übernehmen, Leser und `metadata`-Inhalt nicht |

Bestätigt und unverändert übernommen: K1 (`tests/fixtures/caldav_home_task_lists.xml`, Namensraum `xml.NC` passt nicht), K9 (Decke 1400, größtes Werkzeug `calendar_create_event` 1351), K10 (`docs/folder-evidence.md` Z. 461, 484 ohne Verweis), K6/K7 (Stellen Z. 991 und Z. 1288-1290 in `bootstrap_exapp.sh`), `EXPECTED_PUT_CALLS = 6` mit genau einem `.put(` in `caldav.py` (Z. 351), `provider_classes.py` Z. 57 kennt `tasks`.

## No Analog Found

| Datei oder Baustein | Rolle | Data Flow | Grund |
|---|---|---|---|
| Hybrid-Vorfilter mit Elternverweis in `tools/tasks.py` (zweiter `REPORT` einer Liste, wenn die Elternaufgabe in der gefilterten Antwort fehlt) | Tool-Logik | batch | Kein Werkzeug fragt dieselbe Sammlung bedingt ein zweites Mal ab. Bausteine existieren (`_query_one`, Fan-out); Vorlage ist 32-RESEARCH.md F3, Variante V-B |
| Listenschlüssel für geteilte Listen (`s` plus 16 Hexzeichen) und Entfernen des Besitzerzusatzes | Utility | transform | Kein Id-Segment im Code ist abgeleitet statt übernommen. Vorlage ist 32-RESEARCH.md Pattern 2 und D-32-14; die Messung in Plan 32-02 entscheidet, ob es trägt |
| CI-Schritt "Store-App installieren, Nextcloud neu starten, warten" | Config (CI) | kein | Kein Job startet den Nextcloud-Container nach dem Bootstrap neu. Nächste Verwandte: `scripts/install_findling.sh` und der Neustart-Test in `test_oauth_flow_exapp.py` |
| Kinderabfrage mit eigenem Zeitbudget, die bei Ausfall das Hauptergebnis behält (`tasks_read`) | Tool-Logik | request-response | Nächstes Muster ist `_read_back` (`tools/calendar.py` Z. 322-342: Nebenabfrage darf scheitern, Hauptergebnis bleibt); ein eigenes `asyncio.timeout` um eine Nebenabfrage plus ehrliches Hinweisfeld gibt es noch nicht |

## Metadata

**Analog search scope:** `src/mcp_connector/{nextcloud,nextcloud/clients,tools,server,audit}`, `src/mcp_connector/{ids,paging,provider_map}.py`, `tests/{unit,contract,integration}`, `scripts/`, `.github/workflows/ci.yml`, `docs/`, READMEs, CHANGELOG, `appinfo/info.xml`, `vulture_whitelist.py`, `pyproject.toml`, `.gitattributes`
**Files scanned:** 46 (davon ganz gelesen: caldav.py, calendar.py, reg_calendar.py, server/__init__.py, allowlist.py, ids.py, paging.py, provider_map.py, capabilities.py, xml.py, folder_chain_evidence.py, ci.yml, test_tool_classes.py, test_live_requirement.py; die übrigen gezielt)
**Nicht gelesen:** `.env*`-Dateien (Regel des Auftrags)
**Pattern extraction date:** 2026-11-13

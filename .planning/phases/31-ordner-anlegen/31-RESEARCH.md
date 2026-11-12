# Phase 31: Ordner anlegen - Research

**Researched:** 2026-11-12
**Domain:** WebDAV `MKCOL` in Nextcloud 32 bis 35, neuer Schreiber der Dateifläche hinter der v1.7-Gate-Kette (Ausschluss `kein-ki`, Sandbox, Paartest, Kanarie, Audit)
**Confidence:** HIGH für Code-Befunde und Gate-Inventar (alles im Repo gelesen), HIGH für Statuscodes auf 35.0.0 (Phase-30-Rohdaten), MEDIUM für 32 unter Impersonation (ungemessen, Topologie fehlt)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Deckel für neue Ordner (E10, FOLD-02)
- **D-31-01:** Bräuchte ein Aufruf mit `parents=true` mehr als 10 neue Ordner, lehnt das Werkzeug VORAB ab und legt nichts an. Es zählt dazu vor dem ersten `MKCOL` die fehlenden Segmente. Die Meldung nennt die gezählte Zahl und den Deckel 10. Es bleibt keine halbe Kette stehen, die allein der Deckel verursacht hat. (Owner, 12.11.2026, Auswahl "Vorab ablehnen")
- **D-31-02:** Der Satz aus FOLD-02 "scheitert ein Segment mittendrin, nennt die Antwort die bereits angelegten Ordner" gilt unverändert für alle anderen Abbrüche (Rechte, Sperre, Serverfehler, Kontingent, Wettlauf mit einem anderen Schreiber).

#### Antwortinhalt
- **D-31-03:** Die Erfolgsantwort trägt Pfad, `created` und die Datei-Id des Zielordners, in derselben Form wie `files_upload` sie liefert. Bei `parents=true` kommt die Liste der wirklich neu angelegten Pfade dazu. (Owner, 12.11.2026, Auswahl "Pfad, created, Datei-Id")
- **D-31-04:** Bei einem schon vorhandenen Ordner (`created: false`, E5) kommt die Datei-Id aus derselben Abfrage, die prüft, dass am Pfad ein Ordner und keine Datei liegt. Kein zusätzlicher Aufruf nur für die Id.

#### Schreibrecht
- **D-31-05:** Keine Vorprüfung des Schreibrechts. Das Werkzeug wertet die Ablehnung des Servers aus: 403 ergibt die Meldung "keine Rechte" und nennt, was in diesem Aufruf schon angelegt wurde. (Owner, 12.11.2026, Auswahl "Nur Ablehnung auswerten")

#### Live-Beweis
- **D-31-06:** Der Live-Beweis des Werkzeugs läuft auf Nextcloud 32 und 35 (unteres und oberes Ende des Store-Fensters), unter AppAPI-Impersonation. (Owner, 12.11.2026, Auswahl "32 und 35, ACL aus Phase 30")
- **D-31-07:** Für den Gruppenordner mit ACL gilt die Rohantwort aus Phase 30 (docs/spike-tasks.md, Abschnitte 2.2, 2.4 und 12.2). Der Gruppenordner wird in dieser Phase nicht erneut live aufgebaut. Der geteilte Ordner ohne Schreibrecht wird live belegt, wie Erfolgskriterium 3 es verlangt.

#### Bereits entschieden, hier nur zur Erinnerung
- E5: vorhandener Ordner ist ein Erfolg mit `created: false`, erst nach der Prüfung, dass dort ein Ordner liegt; eine Datei am Pfad ist ein Konflikt.
- E10: höchstens 10 neue Ordner je Aufruf.
- E1: Das Gesamtbudget der Werkzeugliste folgt der Messung plus 15 Prozent; die Decke je Werkzeug (1400 Bytes) bleibt.
- Ablehnung im ausgeschlossenen Ordner ist byte-gleich zu "Elternordner fehlt" (FOLD-04, D-27-01).

### Claude's Discretion
- Wie die fehlenden Segmente vor dem ersten `MKCOL` gezählt werden (eine Abfrage je Segment von oben oder von unten, oder ein anderer Weg), solange D-31-01 gilt und die Ausschlussprüfung vor jedem einzelnen `MKCOL` bleibt.
- Wortlaut der Meldungen je Zweig (400, 403, 405, 409, 423, 507, 5xx), solange jeder Zweig eine eigene, benannte Meldung hat und keiner in "unexpected status" endet.
- Name des Feldes für die Liste der neu angelegten Pfade.
- Aufteilung in Pläne und Wellen.

### Deferred Ideas (OUT OF SCOPE)
- Verhalten der Unteraufgaben beim Wiederöffnen einer Elternaufgabe: discuss-phase von Phase 33.
- Umfang des Admin-Schalters aus E15 (welche Werkzeuge er umfasst): discuss-phase von Phase 33.
- Mindestfrist des Papierkorbs für TMOD-07: Phase 33.

Zur Phase 31 selbst kam nichts außerhalb des Umfangs auf.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOLD-01 | `files_create_folder(path)` im Bundle `files` legt genau einen Ordner mit einem `MKCOL` ohne Body an und meldet `created: true`; je Fehlerfall eine eigene, benannte Meldung, nie "unexpected status" | Statusmatrix Phase 30 (Abschnitt "MKCOL-Statusmatrix"), Zweigtabelle in "Pattern 2", neuer Prüfer `_check_mkcol` nach Vorbild `_check_write` (`dav.py:1100-1158`) |
| FOLD-02 | `parents=true` legt fehlende Elternordner von oben nach unten an, nennt jeden angelegten Ordner, höchstens 10, Teilabbruch nennt das Angelegte | "Pattern 3: Kette mit Vorab-Zählung" (Zählung von unten, Anlegen von oben), Abbruch-Hülle "Pattern 4" |
| FOLD-03 | Vorhandener Ordner ist Erfolg mit `created: false` nach Prüfung Ordner gegen Datei; Annotation anlegend, nicht destruktiv, idempotent; Annotations-Gate trägt die Klasse | 405 ist für Ordner und Datei wortgleich (Phase 30, 1.4) => `dav.stat` nach 405; neue Konstante `CREATE_IDEMPOTENT` in `server/__init__.py`, neue Menge im Annotations-Gate `test_tool_surface.py:745-777` |
| FOLD-04 | Ausschluss und Sandbox wie beim Upload; byte-gleich zu "Elternordner fehlt"; fail-closed; Prüfung vor jedem `MKCOL`; Wurzel nie anlegen, Ziel gleich Wurzel vorab ablehnen | `_writable` (`tools/files.py:1081-1101`), `ExclusionGuard` ein REPORT je Aufruf (`exclusion.py:322-359`), `safe_path`/`within` (`dav.py:125-162, 703-709`), Paartests Unit/Live |
| FOLD-05 | Ganze v1.7-Kette: `FILE_WRITERS` mit Paarfall, Kanarie mit `MUST_REFUSE`, Audit-Erlaubnisliste und `@graceful`, Werkzeugmenge, Bundle, Abnahmeskript, positive Nadel `MKCOL` nur in `dav.py` ohne Body, `EXPECTED_PUT_CALLS` unverändert, Budget grün; Hinweis von `parent_missing` an beiden Stellen | Vollständiges Gate-Inventar mit Datei:Zeile im Abschnitt "Gate-Inventar" |
| FOLD-06 | READMEs (Liste, Rechtetabelle, Zahl), `docs/exclusion*.md` je ein Satz mit Befundlink an stabilem Ort, drei CHANGELOGs, alle Gates grün ohne Phase 32 | Doku-Inventar; Konflikt mit `test_docs_exclusion_truth.py` (verlangt `../.planning/phases/`) aufgelöst über eigenen Anker-Typ |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.13, `uv` als Toolchain; lokal `.venv/Scripts/python.exe` (System-Python defekt). [VERIFIED: CLAUDE.md, `.venv` vorhanden, Python 3.13.13]
- httpx roh für WebDAV, keine DAV-Bibliothek; lxml für XML-Bodies (hier nicht nötig: `MKCOL` ohne Body). [VERIFIED: CLAUDE.md, `dav.py`]
- Code und README Englisch, Projektkommunikation Deutsch; keine Em-Dashes, echte Umlaute in deutschen Texten. Die drei Sprachfassungen (README, exclusion, CHANGELOG) sind Pflicht.
- Security: der MCP darf nie mehr sehen als der angemeldete Nutzer; "keine destruktiven Writes". `MKCOL` ist anlegend und steht nicht in `FORBIDDEN` (`test_no_destructive_calls.py:86-90`).
- Qualitätstore lokal (CI-gleich, `.github/workflows/ci.yml:25-51`): `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run vulture src scripts vulture_whitelist.py`, `uv run pytest tests/unit tests/contract`, `uv run python scripts/check_tool_budget.py`. Memory-Regel: pyright lokal mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`.
- ROADMAP-Regel R1: jeder Plan endet mit vollem Lauf `pytest tests/unit tests/contract` plus Budget-Skript plus Qualitätstoren. R4: vor Push, Merge, Kommentar den Owner fragen.
- GSD-Workflow: Änderungen nur über `/gsd-execute-phase`.
- Commits: Autor laut Memory-Regel; keine "closes #N"-Wörter in Commit-Texten (Issue #44 sonst automatisch geschlossen).

## Summary

`files_create_folder` ist technisch klein, aber ein neuer Schreiber der Dateifläche. Alles, was er braucht, liegt im Repo schon als Baustein vor: `dav.safe_path` (Pfad und Sandbox), `files._writable` (Ausschluss `kein-ki` mit fail-closed und `parent_missing` als Ablehnung), `dav.stat` (Ordner oder Datei, `oc:fileid`), `@graceful` (Audit) und der bestehende `MKCOL`-Aufruf in `dav.start_chunked_upload` als Muster. Neu zu bauen sind genau drei Dinge: ein `MKCOL` auf `files/` mit eigenem Statusprüfer in `dav.py`, die Kettenlogik mit Vorab-Zählung im Werkzeug, und eine dritte Annotationsklasse (anlegend, nicht destruktiv, idempotent), weil das Annotations-Gate `CREATE_TOOLS` heute auf `idempotent_hint False` festnagelt.

Die Phase-30-Messung (NC 35.0.0, Impersonation und App-Passwort statusgleich) gibt die Zweige vor: 201 ist der einzige Erfolg, ohne Body, die Id steht im Kopf `oc-fileid` im Format `00023274oclxpo7v8s2m` (Ziffern plus Instanz-Id, nicht die nackte `oc:fileid`); 405 gilt wortgleich für Ordner und Datei und braucht ein `PROPFIND`; 409 für fehlenden Elternordner, Datei als Elternknoten und fehlende Sandbox-Wurzel; 400 (`InvalidPath`) für unzulässige Namen; 403 mit leerem `s:message` für Freigabe, ACL, Lesegruppe und nur lesbaren Speicher; 507 kommt vor (A9 widerlegt). Die Gate-Kette ist vollständig inventarisiert: 14 Dateien müssen angefasst werden, mehrere Zahlen sind festgenagelt (23 Werkzeuge an vier Stellen, Klassenaufteilung 13/3/7, Anker 21).

Zwei Befunde muss der Planner kennen: (1) `files_upload` liefert heute **keine** Datei-Id (`dav.put_new_file` gibt `path`, `etag`, `created` zurück); D-31-03 "in derselben Form wie `files_upload`" ist wörtlich nicht erfüllbar, die einzige im Projekt etablierte Id-Form ist `"id": "file:<fileid>"` aus `files_list`/`files_search` (`ids.encode_file`). (2) Auf Nextcloud 32 gibt es lokal keine ExApp-Topologie; der Live-Beweis unter Impersonation auf 32 (D-31-06) braucht einen eigenen Aufbau über `compose.exapp.yml` mit `NC_EXAPP_NEXTCLOUD_IMAGE=nextcloud:32.0.15-apache`, der in diesem Projekt noch nie gelaufen ist.

**Primary recommendation:** `MKCOL` als `dav.make_folder` neben `start_chunked_upload` bauen, die Kette im Werkzeug als "von unten zählen, von oben anlegen" mit `_writable(clients, target)` vor jedem `MKCOL`, jede Ablehnung ohne bisher Angelegtes exakt als `dav.parent_missing(target)` bzw. benannter Zweig; Antwort `{"path", "created", "id": "file:<n>"}` plus `created_folders` bei `parents=true`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pfadprüfung, Sandbox-Abbildung | API / Backend (Connector, `dav.safe_path`) | Nextcloud (400 `InvalidPath`) | Läuft vor jedem Request (T-01-09); Namensregeln kennt nur der Server |
| Ausschlussprüfung `kein-ki` | API / Backend (`ExclusionGuard`, `_writable`) | Nextcloud (systemtags REPORT) | Connector entscheidet fail-closed; Daten kommen aus Nextcloud |
| Schreibrecht, ACL, Kontingent, Sperre | Nextcloud (Database / Storage) | Connector bildet Status ab | D-31-05: keine eigene Rechte-Logik, Server kennt Freigabe, Gruppenordner, ACL |
| Ordner anlegen (`MKCOL`) | Nextcloud WebDAV | Connector `dav.py` | Einziger Schreibaufruf; liegt nach Gate-Regel nur in `dav.py` |
| Kette, Zählung, Deckel, Teilabbruch | API / Backend (`tools/files.py`) | , | Geschäftslogik des Werkzeugs |
| Identität (Impersonation) | Nextcloud AppAPI | Connector `Credentials.auth` | Kein Nutzerparameter am Werkzeug (Confused-Deputy-Gate) |
| Audit-Eintrag | API / Backend (`@graceful`, `record.note`) | , | Einziger Ort, der jeden Aufruf mit Ausgang sieht |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 (installiert) | `client.request("MKCOL", url, auth=...)` | Projektstandard für alle DAV-Aufrufe; `MKCOL` läuft schon so in `dav.start_chunked_upload` [VERIFIED: `.venv`, `dav.py:989-994`] |
| mcp | 2.x (installiert) | Registrierung `@mcp.tool(annotations=...)`, `ToolAnnotations` | Projektstandard [VERIFIED: `server/__init__.py`] |
| pydantic | installiert | `Annotated[..., Field(description=...)]` | Schema-Diät wie bei den übrigen Werkzeugen |

### Supporting (Test)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | 0.23.1 (installiert) | `MKCOL`/`PROPFIND`-Routen im Unit-Test | Unit- und Paartests, mit `guard_routes` für den Guard [VERIFIED: `.venv`] |
| pytest, anyio-Marker | installiert | Tests | `@pytest.mark.anyio`, `asyncio`-Backend (`tests/conftest.py:13-16`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| eigener `MKCOL`-Loop | Kopf `X-NC-WebDAV-Auto-Mkcol` | Wirkt nur auf `PUT`, wäre ein stiller Zweitschreiber unter dem Audit-Namen `files_upload`; verworfen in v1.8-Recherche B4 [CITED: .planning/research/v1.8-tasks-080-RESEARCH.md:209-222] |
| Rechte-Vorprüfung per `oc:permissions` | , | D-31-05 verbietet sie; Phase 30 zeigt, dass sie ginge (fehlendes `C`/`K`), aber der Owner hat "nur Ablehnung auswerten" gewählt |
| nc_py_api `nc.files.mkdir` | , | Zweiter HTTP-Stack, umgeht Gates und Nadel; nicht verwenden |

**Installation:** keine. Die Phase installiert kein Paket.

## Package Legitimacy Audit

Die Phase installiert keine externen Pakete; alle genutzten Bibliotheken (httpx, mcp, pydantic, respx, pytest) sind bereits in `uv.lock` und in `.venv` installiert. slopcheck wurde deshalb nicht ausgeführt.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (keins neu) | , | , | , | , | , | , |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Assistent ──tools/call files_create_folder(path, parents)──▶ MCP-Server (@graceful: Audit-Zeile im finally)
                                                              │
                                                              ▼
                                              deps.resolve_clients(ctx) ─▶ NcClients (Basic | Bearer | AppAPI-Impersonation)
                                                              │
                                                              ▼
                                   dav.safe_path(path) ── unsicher? ─▶ ToolError (kein Request)
                                                              │
                                        Ziel == config.files_root()? ─▶ ToolError "Wurzel" (kein Request)
                                                              │
                                                              ▼
                              _writable(clients, target)  ◀── ExclusionGuard: 1 REPORT je Aufruf (gecacht)
                                 │ unverifiable ─▶ withhold.unavailable_error()   (kein PROPFIND, kein MKCOL)
                                 │ excludes      ─▶ dav.parent_missing(target)      (kein PROPFIND, kein MKCOL)
                                 ▼
                 parents=false ─────────────────────────────┐        parents=true
                                                            │          │
                                                            │          ▼
                                                            │   Zählen von unten: dav.stat(target), dann Eltern
                                                            │   bis erster vorhandener Knoten (nie über die Wurzel)
                                                            │     Ziel ist Ordner ─▶ Erfolg created=false, id aus stat
                                                            │     Ziel/Vorfahr ist Datei ─▶ ConflictError
                                                            │     Wurzel fehlt ─▶ parent_missing(target)
                                                            │     fehlend > 10 ─▶ ToolError "n Ordner, Deckel 10"
                                                            │          │
                                                            ▼          ▼  je fehlendes Segment von oben:
                                       _writable(clients, target); dav.make_folder(segment)  [MKCOL ohne Body]
                                                            │
                     201 ─▶ angelegt (id aus oc-fileid) │ 405 ─▶ dav.stat: Ordner = vorhanden, Datei = Konflikt
                     409/404 ─▶ parent_missing │ 403 ─▶ keine Rechte │ 400 ─▶ Name unzulässig
                     423 ─▶ gesperrt │ 507 ─▶ Kontingent │ 3xx/401/429/5xx ─▶ dav._check
                                                            │
                         Fehler nach mindestens einem angelegten Segment ─▶ gleiche Meldung + "bereits angelegt: ..."
                                                            ▼
                         {"path", "created", "id": "file:<n>"[, "created_folders": [...]]}  ─▶ compact() ─▶ Assistent
```

### Recommended Project Structure (nur Änderungen)
```
src/mcp_connector/
├── nextcloud/clients/dav.py   # make_folder() + _check_mkcol() + parse von oc-fileid; _PARENT_HINT neu
├── tools/files.py             # create_folder(): Kette, Zählung, Deckel, Abbruch-Hülle
├── server/__init__.py         # CREATE_IDEMPOTENT + __all__
├── server/reg_files.py        # @mcp.tool files_create_folder
└── audit/allowlist.py         # "files_create_folder": {"parents", "path"}
tests/
├── unit/test_files_create_folder.py          # neu: Zweige, Kette, Deckel, Abbruch, Sandbox, id-Parsing
├── unit/test_files_create_folder_exclusion.py # neu (oder in test_files_upload_exclusion.py): Paar, fail-closed, kein MKCOL
├── unit/test_pair_equality_files.py          # COVERED + Paarfall
├── unit/test_dav_fileid_paths.py             # PARENT_HINT neu
├── unit/test_canary_refusals.py              # files_create_folder-Fälle
├── unit/test_docs_exclusion_truth.py         # neuer Anker mit stabilem Beleg
├── contract/{tool_classes,test_tool_classes,test_tool_surface,test_tool_bundles,test_no_destructive_calls,test_audit_surface}.py
└── integration/{test_canary,canary_world,test_pair_equality_live}.py + neu test_files_create_folder_live.py
docs/folder-evidence.md        # neu: stabiler Ort für Live-Beleg (FOLD-06)
```

### Pattern 1: `MKCOL` im Client, Statusprüfer nach Vorbild `_check_write`

**What:** Eine Funktion in `dav.py`, die genau einen `MKCOL` ohne Body schickt, 201 mit Id zurückgibt, 405 als "belegt" meldet und jeden anderen Status benannt übersetzt.
**When to use:** Für jedes Segment, ob mit oder ohne `parents`.

```python
# Skizze, angelehnt an dav.start_chunked_upload (dav.py:981-999) und _check_write (dav.py:1100-1158)
_OC_FILEID = re.compile(r"([0-9]+)(oc[0-9a-z]+)")  # Format gemessen: "00023274oclxpo7v8s2m"

async def make_folder(client, creds, path: str) -> dict[str, Any]:
    """MKCOL one folder, no body. Returns {"created": True, "fileid": str} or {"created": False}."""
    target = safe_path(path)
    response = await client.request("MKCOL", files_url(creds, target), auth=creds.auth())
    if response.status_code == 405:
        return {"created": False, "fileid": ""}   # Ordner ODER Datei: Aufrufer liest per stat
    _check_mkcol(response, target)                 # wirft für alles außer 201
    match = _OC_FILEID.fullmatch(response.headers.get("oc-fileid", "").strip())
    return {"created": True, "fileid": str(int(match[1])) if match else ""}
```

Kein `content=`, `data=`, `json=`, `files=` und kein `Content-Type`: ein Body ohne XML-Typ ergibt laut sabre 415 [CITED: v1.8-RESEARCH B2], und die neue Nadel verlangt das.

### Pattern 2: Zweige von `_check_mkcol` (FOLD-01)

| Status | Gemessen (35.0.0) | Meldung (Vorschlag, Englisch) | Klasse / reason |
|--------|-------------------|-------------------------------|-----------------|
| 201 | ja | Erfolg | , |
| 405 | ja, wortgleich Ordner/Datei | kein Fehler in `make_folder`; Werkzeug liest `dav.stat` | , |
| 409, 404 | 409 ja (Eltern fehlt, Eltern ist Datei, Wurzel fehlt); 404 ungemessen | `parent_missing(target)` (aus der einen Fabrik) | `ToolError`, `unknown_id` |
| 403 | ja, `s:message` leer, vier Speicherarten | "No permission to create a folder at {path}." Hinweis: Freigabe, Gruppenordner oder Speicher erlauben dort kein Anlegen | `ToolError`, `permission_denied` |
| 400 | ja, `InvalidPath` | "Nextcloud does not accept the folder name in {path}." Hinweis: reservierte Namen wie .htaccess, Backslash, sehr lange Namen | `ToolError`, Standard-reason |
| 423 | ungemessen | "{path} is locked in Nextcloud." | `ToolError` |
| 507 | ja (erschöpftes Kontingent) | "Not enough space in Nextcloud to create {path}." | `ToolError` |
| 3xx, 401, 429, 5xx | 401 ja (falsches Secret) | über `dav._check` (Redirect, App-Passwort, Ratelimit, Serverfehler) | wie bisher |
| sonst | , | `_check` plus letzte Zeile "unexpected status" bleibt nur als technischer Rest | , |

Den Servertext (`s:message`) nicht in die Antwort übernehmen: bei 403 ist er leer, und das Projekt reicht nirgends Servertext durch.

### Pattern 3: Kette mit Vorab-Zählung (FOLD-02, D-31-01)

**Empfehlung (Claude's Discretion): von unten zählen, von oben anlegen.**

1. `target = dav.safe_path(path)`; `root = config.files_root()`; `target == root` wird vorab abgelehnt (FOLD-04).
2. `await _writable(clients, target)`: ein getaggtes Ziel oder ein Ziel unter einem getaggten Ordner endet hier mit `parent_missing(target)`, bevor irgendein `PROPFIND` hinausgeht. Ein `PROPFIND` vor der Prüfung wäre selbst ein Existenzorakel (Docstring von `_writable`, `files.py:1095`).
3. Ohne `parents`: direkt `make_folder(target)`, kein `PROPFIND` vorher. 405 löst `dav.stat(target)` aus (D-31-04: dieselbe Abfrage liefert Art und `fileid`).
4. Mit `parents`: `dav.stat` auf `target`, dann auf jeden Elternpfad, bis ein vorhandener Knoten kommt oder die Wurzel erreicht ist. Kandidaten sind nur Pfade mit `dav.within(p, root)` und `p != root` (die Wurzel selbst wird höchstens gelesen, nie angelegt). Ein 404 von `dav.stat` erkennt man an `ToolError.reason == REASON_UNKNOWN_ID` (Muster `_visible_stat`, `files.py:1150`).
   - Ziel vorhanden, Ordner: Erfolg `created: false`, `id` aus diesem `stat`, `created_folders: []`.
   - Ziel oder erster vorhandener Vorfahr ist eine Datei: `ConflictError`.
   - Wurzel nicht vorhanden: `parent_missing(target)`, kein `MKCOL`.
   - Zahl der fehlenden Segmente > 10: `ToolError` mit Zahl und Deckel, kein `MKCOL`. Bei Abbruch nach dem 11. fehlenden Segment wäre die Zahl nur "mindestens 11"; D-31-01 verlangt "die gezählte Zahl", also bis zum ersten vorhandenen Knoten weiterzählen (eine `PROPFIND` je Segment, begrenzt durch die Pfadtiefe).
5. Für jedes fehlende Segment von oben nach unten: `await _writable(clients, target)` (dieselbe gecachte Antwort, kein zweiter REPORT; deckt jedes Segment, weil jedes Segment Vorfahr des Ziels ist, `exclusion.ancestors`), dann `make_folder(segment)`.
   - 201: Segment in `created_folders`.
   - 405 (Wettlauf, ein anderer Schreiber war schneller): `dav.stat(segment)`; Ordner: weiter, nicht in `created_folders`; Datei: Abbruch mit Konflikt.
   - jeder andere Fehler: Abbruch über die Hülle aus Pattern 4.

Warum von unten zählen: der Normalfall (Ziel oder Eltern existieren) kostet ein bis zwei `PROPFIND`; die Zählung liefert die exakte Zahl, und die Id des vorhandenen Ziels fällt nebenbei an.

### Pattern 4: Abbruch-Hülle (D-31-02)

```python
# Skizze: die Meldung des Zweigs bleibt unverändert, nur angehängt wird das Angelegte
def _with_created(err: ToolError, created: list[str]) -> ToolError:
    if not created:
        return err                       # byte-gleich zum Zweig, wichtig für die Paartests
    kept = ", ".join(created)
    return type(err)(
        message=f"{err.message} Already created in this call and left in place: {kept}.",
        hint=err.hint,
        reason=err.reason,
    )
```

Regel für die Byte-Gleichheit: Solange in diesem Aufruf nichts angelegt wurde, ist jede 409/404-Ablehnung exakt `dav.parent_missing(target)` (des **Ziels**, nicht des Segments). Grund: `normalised` ersetzt nur Präfixe des Arguments durch `<ID>`, ein Segment direkt unter `/` hätte "The parent folder / of ..." und wiche ab (`tests/contract/result_shapes.py:32-71`).

### Pattern 5: Antwortform (D-31-03, D-31-04)

```json
{"path":"/Projekte/2026","created":true,"id":"file:23274"}
{"path":"/Projekte/2026/Q1","created":true,"id":"file:23277","created_folders":["/Projekte/2026","/Projekte/2026/Q1"]}
{"path":"/Projekte","created":false,"id":"file:120","created_folders":[]}
```

- `path` wie bei `files_upload` der absolute Home-Pfad aus `safe_path` (mit Wurzelpräfix bei gesetzter Sandbox) [VERIFIED: `dav.py:795-799`].
- `id` in der Form `ids.encode_file(fileid)` wie in `files_list`/`files_search` (`files.py:346-347`); `fetch` und die Leser verstehen sie. Fehlt `oc-fileid` oder ist es unlesbar: ein `dav.stat` hinterher, und scheitert auch das, `id` weglassen statt Fehler (Regel aus `update_file`: nach angenommenem Schreiben macht kein Folgelesen die Antwort zum Fehler, `dav.py:941-944`).
- `created_folders` (Feldname: Claude's Discretion, Vorschlag) nur bei `parents=true`, auch leer.

### Pattern 6: Registrierung

```python
# server/__init__.py
CREATE_IDEMPOTENT = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False,
)
# reg_files.py
@mcp.tool(annotations=CREATE_IDEMPOTENT, structured_output=False)
@graceful
async def files_create_folder(
    path: Annotated[str, Field(description="Folder path to create, e.g. /Projects/2026")],
    parents: Annotated[bool, Field(description="Also create missing parent folders, at most 10")] = False,
    ctx: Context | None = None,
) -> str:
    """Create a folder; an existing folder answers created false. Never overwrites, moves or deletes."""
    clients = deps.resolve_clients(ctx)
    return compact(await files_tools.create_folder(clients, path=path, parents=parents))
```

Gemessen in dieser Sitzung mit einem Probe-Registrat dieser Form: rund 510 Bytes für das Werkzeug, Gesamtliste 16261 Bytes (mit einem überzähligen Testparameter) gegen Budget 18000 und Decke 1400 [VERIFIED: lokale Messung, Skript im Scratchpad]. Eine Anhebung des Budgets ist in Phase 31 nicht nötig; die Messzeile im Kopf von `scripts/check_tool_budget.py` ergänzen (Hausregel: jede neue Messung wird dort notiert).

### Anti-Patterns to Avoid
- **`PROPFIND` vor der Ausschlussprüfung:** würde vorhanden gegen fehlend unter einem getaggten Ordner unterscheiden. Immer erst `_writable`.
- **`excludes(path=segment)` mit `parent_missing(segment)`:** bricht die Byte-Gleichheit; immer gegen das Ziel prüfen und mit dem Ziel antworten.
- **405 als Erfolg ohne `stat`:** eine Datei am Pfad würde als `created: false` durchgehen (FOLD-03).
- **`oc-fileid` ungeprüft als Id:** der Kopf ist `00023274oclxpo7v8s2m`, nicht `23274`; `file:00023274oc...` adressiert nichts.
- **Wurzel anlegen:** fehlt `NC_MCP_FILES_ROOT` auf dem Server, darf die Kette sie nicht erzeugen.
- **`X-NC-WebDAV-Auto-Mkcol` an `files_upload`:** stiller Zweitschreiber, verworfen.
- **Rechte vorab per `oc:permissions`:** D-31-05.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pfadnormalisierung, Traversal, Sandbox | eigene Split-Logik | `dav.safe_path`, `dav.within` | eine Segmentregel für Sandbox und Ausschluss (`dav.py:703-709`) |
| Ausschlussprüfung | eigene REPORT-Aufrufe | `files._writable` (oder `clients.exclusion.scope`) | Single-Flight je Aufruf, drei Zustände, fail-closed |
| Satz "Elternordner fehlt" | neuen Text | `dav.parent_missing(target)` | eine Quelle (D-27-01), Paartests vergleichen gegen sie |
| "Prüfung nicht beantwortbar" | eigene Meldung | `withhold.unavailable_error()` | ein Wortlaut für alle Familien (D-27-05) |
| Ordner oder Datei, `fileid` | eigenes PROPFIND | `dav.stat` | liefert `is_collection` und `fileid` |
| Id-Form | eigenes Präfix | `ids.encode_file` | `fetch`-kompatibel |
| Audit | eigene Zeile | `@graceful` | Gate `test_every_registered_tool_carries_the_recording_marker` |
| Namensprüfung | Regelkatalog im Client | 400 des Servers | Regeln sind serverseitig konfigurierbar; gemessen nur drei Namen |
| Rechteprüfung | ACL-Logik | 403 des Servers | D-31-05 |

**Key insight:** Jede Grenze ist schon einmal für den Upload gebaut und belegt. Die Kette darf nur Bausteine aufrufen; jede eigene Variante wäre eine zweite Wahrheit, die die Paartests nicht sehen.

## Gate-Inventar (FOLD-05, FOLD-06): was wo eingetragen wird

| # | Datei:Zeile | Heute | Änderung |
|---|-------------|-------|----------|
| 1 | `src/mcp_connector/nextcloud/clients/dav.py:55` `_PARENT_HINT` | "Create the folder in Nextcloud first, or upload into a folder that exists." | Verweis auf `files_create_folder`; Vorschlag: "Create the folder first with files_create_folder (parents=true creates the whole chain), or check that no file stands in the path." Gleichzeitig `tests/unit/test_dav_fileid_paths.py:27` `PARENT_HINT` |
| 2 | `dav.py:1-13` Modul-Docstring | nennt create-only Uploads | Ordner anlegen ergänzen; Achtung: `test_the_gate_would_notice_a_destructive_call_in_real_code` verlangt, dass "no DELETE, no MOVE, no COPY" nur im Docstring steht |
| 3 | `src/mcp_connector/server/__init__.py:42-89` | `CREATE_ONLY`, `UPDATE_EXISTING` | `CREATE_IDEMPOTENT` plus `__all__` |
| 4 | `src/mcp_connector/server/reg_files.py` | 6 (+1 optional) Werkzeuge | `files_create_folder` |
| 5 | `src/mcp_connector/audit/allowlist.py:45-70` | 23 Einträge | `"files_create_folder": frozenset({"parents", "path"})` |
| 6 | `tests/contract/tool_classes.py:69-81` `FILE_WRITERS` | 3 Schreiber | Eintrag mit Satz und `file:line`-Anker, Endpunkt-Punkt, mind. 20 Zeichen, einzeilig |
| 7 | `tool_classes.py:122-138` `PAIR_CASES` | 15 Fälle | `("files_create_folder", "path"): "files"` (ohne `parents`, siehe Pitfall 6) |
| 8 | `tests/contract/test_tool_classes.py:18, 101-114` | `TOTAL = 23`, `(13, 3, 7)` | `24`, `(13, 4, 7)`; Docstring-Zahlen |
| 9 | `tests/contract/test_tool_surface.py:43-80, 161-185, 559-565, 745-777, 803, 818-845` | `EXPECTED_TOOLS` 23, `CREATE_TOOLS` 6, "six file tools", `len(tools) == 23`, README-Rechtetabelle | Werkzeug in `EXPECTED_TOOLS`; neue Menge `IDEMPOTENT_CREATE_TOOLS = {"files_create_folder"}` mit eigenem Zweig (read False, destructive False, idempotent **True**); README-Stufe `create-only` auch für diese Menge; "seven file tools"; 24 |
| 10 | `tests/contract/test_tool_bundles.py:28-37` | Bundle `files` mit 6 | plus `files_create_folder` |
| 11 | `tests/contract/test_no_destructive_calls.py` | keine `MKCOL`-Nadel; `EXPECTED_PUT_CALLS = 6` (Z. 480) | neue AST-Nadel: jeder `.request("MKCOL", ...)` liegt in `nextcloud/clients/dav.py`, ohne `content`/`data`/`json`/`files`; Zählpin `EXPECTED_MKCOL_CALLS = 2` (Chunk-Ordner plus neuer); Gegenproben mit gepflanztem Body und gepflanzter Datei außerhalb `dav.py`. `EXPECTED_PUT_CALLS` bleibt 6 (kein neuer `PUT`) |
| 12 | `tests/contract/test_audit_surface.py` | prüft Allowlist und Marker | grün durch #5 und `@graceful`; Gegenprobe läuft über die Registry |
| 13 | `tests/unit/test_pair_equality_files.py:57-66, 600-606` | `COVERED` 8 Fälle | Paarfall plus Test über `GUARD_MODES` (5 Zustände): getaggt `/Projekt/neu` gegen erfunden `/erfunden-1/neu` mit `MKCOL` 409; Fragment `PARENT_MISSING` |
| 14 | `tests/integration/test_pair_equality_live.py:160-195` `CASES` | 15 | Live-Paar: `f"{w.locked_dir}/neu-ordner"` gegen `f"{_missing(w)}/neu-ordner"`; `test_every_pair_case_is_measured_live` erzwingt es |
| 15 | `tests/integration/test_canary.py:63, 89, 150-223` | `EXPECTED_TOOLS = 23`, `MUST_REFUSE` 3 | 24; `MUST_REFUSE` plus `files_create_folder`; Plan mit `{"path": f"{world.locked_dir}/ordner-{world.h}"}` und `{"path": f"{world.locked_dir}/a-{world.h}/b", "parents": True}` |
| 16 | `tests/integration/canary_world.py:217-228` `refusal_problem` | upload und notes | `files_create_folder` auf `PARENT_MISSING_FRAGMENTS`; Unit-Spiegel `tests/unit/test_canary_refusals.py` |
| 17 | `scripts/acceptance_all_tools.py:146-160` | ruft jedes Werkzeug | `files_create_folder` mit `parents=true` unter `/{marker}-{stamp}-ordner/...`, zweiter Aufruf erwartet `created:false`; sonst "never called" |
| 18 | `scripts/check_tool_budget.py:89-104` | Messzeile 23 Werkzeuge | neue Messzeile 24 Werkzeuge, Budget unverändert, solange < 18000 |
| 19 | `README.md:25, 62-87, 121-122`, `README.de.md:28, 7x, Bundles`, `README.fr.md:28, 8x, Bundles` | 23 Werkzeuge, Tabelle, Bundle-Liste | Zahl 24, Zeile `files_create_folder` mit Stufe `create-only`, Bundle-Liste; `test_the_readme_permission_table_matches_the_live_registry` liest nur `README.md` |
| 20 | `docs/exclusion.md`, `.de.md`, `.fr.md` | Anker `tech-upload-oracle` (Z. 310) | neuer Abschnitt mit Anker, z. B. `tech-folder-oracle`, Satz "Ordner neben getaggtem Ordner", Beleglink auf `folder-evidence.md` |
| 21 | `tests/unit/test_docs_exclusion_truth.py:84-114, 229-238` | `EVIDENCE_ANCHORS` müssen auf `../.planning/phases/` zeigen | Konflikt mit FOLD-06; Lösung: neues Tupel `STABLE_EVIDENCE_ANCHORS = ("tech-folder-oracle",)` mit eigener Prüfung "Link unter `docs/`, Datei existiert, nicht unter `.planning/`", Anker in `ALL_ANCHORS` (21 auf 22, Docstrings) |
| 22 | `CHANGELOG.md`, `.de.md`, `.fr.md` unter `## [Unreleased]` | leer | `### Added` mit Werkzeug; `tests/unit/test_changelog_translations.py` hält Abschnitte gleich |
| 23 | `docs/n8n-setup.md:36, 258`, `docs/store-submission.md:206` | "23 tools" | Gate `test_a_documented_tool_count_...` bleibt grün, weil beide Seiten auf `tests/contract/test_tool_surface.py` verweisen; inhaltlich Phase 34 (DOC), nicht hier |

Nicht anfassen in Phase 31: Server-Instruktion (`server/__init__.py:61-70`, Phase 34 laut Inventar 7.1), `appinfo/info.xml` Store-Text (Phase 34, Pin `test_store_texts_frozen.py`), `FORBIDDEN` und `CHUNK_ASSEMBLY_MOVE`.

## Common Pitfalls

### Pitfall 1: `oc-fileid` ist nicht die `oc:fileid`
**What goes wrong:** Die Antwort trägt `file:00023274oclxpo7v8s2m`; `fetch` findet nichts.
**Why it happens:** Nextcloud schreibt die Id achtstellig aufgefüllt plus Instanz-Id in den Kopf (gemessen: `oc-fileid: 00023274oclxpo7v8s2m`, `raw/nc35-mkcol.txt:87`).
**How to avoid:** `([0-9]+)(oc[0-9a-z]+)` vollständig matchen, `int()` der Ziffern; sonst Rückfall auf `dav.stat`.
**Warning signs:** Unit-Test mit echtem Kopfwert aus der Rohdatei; Live-Test vergleicht mit `oc:fileid` aus `PROPFIND`.

### Pitfall 2: 405 sagt nicht, was dort liegt
**What goes wrong:** Datei am Pfad wird als `created: false` gemeldet.
**How to avoid:** nach 405 immer `dav.stat`; `is_collection` entscheidet. Fehlt der Knoten beim `stat` (Wettlauf, gelöscht), eine eigene Konflikt-Meldung "changed concurrently", nie Erfolg.

### Pitfall 3: Byte-Gleichheit bricht an Kleinigkeiten
**What goes wrong:** Paartest rot, weil die getaggte Seite `parent_missing(segment)` oder eine angehängte Liste trägt, oder weil das Werkzeug vor der Prüfung ein `PROPFIND` schickt und der catch-all im Paartest es als unerwarteten Request meldet.
**How to avoid:** Reihenfolge `safe_path`, Wurzel, `_writable`, dann erst Netz; Ablehnung immer `parent_missing(target)`; Liste nur anhängen, wenn sie nicht leer ist. In allen fünf `GUARD_MODES` testen (unverifiable: beide Seiten `unavailable_error`).

### Pitfall 4: Wurzel-Sonderfälle der Sandbox
**What goes wrong:** Kette legt die fehlende `NC_MCP_FILES_ROOT` an, oder `files_create_folder("/")` legt die Wurzel an.
**Why it happens:** `safe_path("/")` liefert bei gesetzter Wurzel die Wurzel selbst (`dav.py:162`); MKCOL auf die vorhandene Wurzel antwortet 405 (gemessen), auf eine fehlende Wurzel antwortet ein Unterordner 409 (gemessen).
**How to avoid:** `target == config.files_root()` vorab ablehnen (wie `files.py:639`); Kandidaten der Kette nur `within(p, root) and p != root`; Wurzel 404 beim Zählen ergibt `parent_missing(target)`.

### Pitfall 5: Ausschlussprüfung "vor jedem MKCOL" falsch verstanden
**What goes wrong:** ein zweiter REPORT je Segment (teuer, SQLite bis 240 s) oder ein frischer Guard je Segment, der zwischen zwei Segmenten einen anderen Stand liest.
**How to avoid:** `_writable(clients, target)` vor jedem `MKCOL`; `ExclusionGuard` cacht je Werkzeugaufruf (`exclusion.py:322-359`), wie beim Chunk-Upload (`files.py:1037-1044`). Unit-Test: REPORT `call_count == 1` bei einer Kette von drei Segmenten.

### Pitfall 6: Paarfall mit `parents=true` hat keine natürliche Gegenseite
**What goes wrong:** Live ist die "nicht existierende" Gegenseite mit `parents=true` ein Erfolg (die Kette entsteht), also kein Paar.
**How to avoid:** `PAIR_CASES` nur mit `parents=false` (Live und Unit). Den Fall `parents=true` getaggt deckt ein eigener Unit-Test (Ergebnis exakt `parent_missing(target)`, kein `PROPFIND`, kein `MKCOL`) und die Kanarie (`MUST_REFUSE` mit zweitem Argumentsatz). Im Unit-Paar lässt sich zusätzlich eine Gegenseite bauen (Wurzel-`PROPFIND` 404 oder erstes `MKCOL` 409), weil dort beides `parent_missing(target)` ist.

### Pitfall 7: Annotations-Gate kennt keine idempotente Anlage
**What goes wrong:** `files_create_folder` in `CREATE_TOOLS` macht `test_every_tool_carries_honest_annotations` rot (verlangt `idempotent_hint False`), ohne Eintrag fällt es in den Lese-Zweig (verlangt `read_only_hint True`).
**How to avoid:** eigene Menge und eigener Zweig; README-Rechtetabelle-Test (`test_tool_surface.py:836-845`) muss die Menge auf `create-only` abbilden.

### Pitfall 8: Hinweistext von `parent_missing` gilt auch für Notes
**What goes wrong:** `notes_create` nutzt dieselbe Fabrik (`notes.py:283`); ist das Bundle `files` über `NC_MCP_DISABLED_TOOLS` aus, verweist der Hinweis auf ein Werkzeug, das es nicht gibt.
**How to avoid:** Hinweis so formulieren, dass er auch ohne das Werkzeug trägt ("..., or create it in Nextcloud"); bewusst hinnehmen und im Plan nennen.

### Pitfall 9: Live-Tests laufen heute mit App-Passwort, nicht mit Impersonation
**What goes wrong:** Kanarie und Live-Paar gelten als "Live-Beweis", belegen aber Basic-Auth (`canary_world.py:184-203`).
**How to avoid:** eigener Live-Test mit `Credentials(mode=MODE_APPAPI, secret=APP_SECRET)` nach `tests/integration/test_exapp_dav_matrix.py:60-78` (Fixture `exapp_env`, `tests/conftest.py:39-68`), Kontrollen "kein App-Passwort im Prozess" und "falsches Secret 401" mitnehmen.

### Pitfall 10: Nextcloud 32 hat keine ExApp-Strecke
**What goes wrong:** D-31-06 verlangt 32 unter Impersonation; alle Impersonationsmessungen des Projekts liefen auf 34.0.3 (CI `exapp`) und 35 (`compose.nc35.yml`, CI `canary-nc35`). Phase 30 nennt 32 bis 34 unter Impersonation ausdrücklich ungemessen (`docs/spike-tasks.md`, Abschnitt 11).
**How to avoid:** Aufbau über `compose.exapp.yml` mit `NC_EXAPP_NEXTCLOUD_IMAGE=nextcloud:32.0.15-apache` (Patch-Tag, nie schwimmend, Kommentar `compose.exapp.yml:50-57`) plus `bash scripts/bootstrap_exapp.sh`; `occ status` als Versionsnachweis wie im CI-Schritt "The instance is Nextcloud 35.0.1". Als eigener, früher Task mit Abbruchkriterium planen (siehe Open Question 2). RAM-Regel des Owners: nicht parallel zur laufenden nc35-Strecke, wenn der Docker-VM-Speicher knapp ist.

### Pitfall 11: Aufräumen nach Live-Läufen
**What goes wrong:** Kanarie und Live-Paar prüfen ihren Rückbau (`assert_cleanup`); ein fälschlich angelegter Ordner bliebe stehen, und der Connector kann nicht löschen.
**How to avoid:** Testharness löscht über den eigenen Admin-Weg (wie `cleanup_uploads`), Live-Test legt nur unter einem Präfix mit Lauf-Stempel an.

## Code Examples

### Positive Nadel `MKCOL` (Skizze, im Stil von `_unconditional_puts`)
```python
# tests/contract/test_no_destructive_calls.py, Muster aus Z. 505-556
EXPECTED_MKCOL_CALLS = 2  # chunk staging folder + files_create_folder
MKCOL_HOME = "nextcloud/clients/dav.py"
_BODY_KEYWORDS = {"content", "data", "json", "files"}

def _mkcol_findings(relative: str, tree: ast.AST) -> tuple[list[str], int]:
    findings, seen = [], 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "request" and node.args
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == "MKCOL"):
            continue
        seen += 1
        if relative != MKCOL_HOME:
            findings.append(f"{relative}:{node.lineno}: MKCOL outside {MKCOL_HOME}")
        if any(kw.arg in _BODY_KEYWORDS for kw in node.keywords):
            findings.append(f"{relative}:{node.lineno}: MKCOL with a body")
    return findings, seen
```
Dazu: eine Zeilen-Nadel auf das Literal `"MKCOL"` außerhalb `dav.py` (fängt `method="MKCOL"` und Variablen), und Gegenproben mit gepflanztem Quelltext (Body, fremde Datei, Schlüsselwort `method=`), wie `_PLANTED_PUTS` (Z. 577-603).

### Unit-Paar (Skizze, nach `test_files_upload_text_into_a_tagged_target_answers_like_an_invented_folder`)
```python
def _mkcol(path: str, status: int) -> Mocks:
    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="MKCOL", url=f"{FILES}{path}").mock(return_value=httpx.Response(status))
    return mocks

@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_create_folder_in_a_tagged_folder_answers_like_an_invented_parent(mode, unexpected):
    tagged_path, invented = "/Projekt/neu", f"{INVENTED_FOLDER}/neu"
    tagged, unknown = await pair(
        "files_create_folder", {"path": tagged_path}, {"path": invented},
        tagged_path, invented, _mkcol(tagged_path, 201), _mkcol(invented, 409), mode, unexpected,
    )
    _assert_equal(tagged, unknown, mode, PARENT_MISSING)
```
Die getaggte Seite registriert eine 201-Route, die nie getroffen werden darf; zusätzlich `call_count == 0` prüfen (Muster `_Writes.count`, `test_files_upload_exclusion.py:68-88`).

## MKCOL-Statusmatrix (Messgrundlage, Phase 30)

Quelle: `docs/spike-tasks.md` 1.3, 1.4, 2.2, 2.4, 9.1; Rohdaten `.planning/phases/30-mess-spike-aufgaben-und-ordner/raw/nc35-mkcol.txt`, `nc35-gruppenordner.txt`. Instanz 35.0.0, SQLite, `groupfolders` 23.0.1; jede Zeile unter Impersonation und mit App-Passwort statusgleich. [VERIFIED: Rohdaten gelesen]

| Fall | Status | `s:exception` / `s:message` |
|------|--------|------------------------------|
| freier Name | 201, kein Body, Kopf `oc-fileid` | , |
| Ordner vorhanden | 405 | `MethodNotAllowed` / "The resource you tried to create already exists" |
| Datei am Pfad | 405 | identisch zu Ordner vorhanden |
| Eltern fehlt | 409 | `Conflict` / "Parent node does not exist" |
| Eltern ist Datei | 409 | `Conflict` / "Parent node is not a collection" |
| `.htaccess`, Backslash, 300 Zeichen | 400 | `InvalidPath` / "Filename is a reserved word", "\"\\\" is not allowed ...", "Filename is too long" |
| Freigabe ohne Anlegerecht (`permissions=1`) | 403 | `Forbidden` / leer |
| Gruppenordner, ACL-Regel gegen Konto | 403 | `Forbidden` / leer (Rohantwort 12.2, Beleg für Erfolgskriterium 3 nach D-31-07) |
| Gruppe nur lesend, externer Speicher `readonly` | 403 | `Forbidden` / leer |
| Sandbox-Wurzel vorhanden, Unterordner | 201 | , |
| Sandbox-Wurzel fehlt | 409 | wie Eltern fehlt |
| Sandbox-Wurzel selbst | 405 | wie vorhanden |
| Kontingent erschöpft | 507 | `InsufficientStorage` |
| falsches Secret | 401 | , |
| fremdes Home unter Impersonation | 403 | , |

Ungemessen und in Phase 31 zu schließen oder als Grenze zu nennen: 423 (Sperre), 404 bei `MKCOL`, alles auf 32 bis 34, knappes (nicht erschöpftes) Kontingent, weitere unzulässige Namen.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hinweis "Create the folder in Nextcloud first" | Verweis auf `files_create_folder` | Phase 31 | Text an zwei Stellen gleichzeitig (FOLD-05) |
| zwei Annotationsklassen für Schreiber | drei (plus anlegend-idempotent) | Phase 31 | Gate-Zweig, README-Stufe |
| 23 Werkzeuge | 24 | Phase 31 | vier Pins, drei READMEs |
| A9 "MKCOL nie 507" | widerlegt | Phase 30 | 507-Zweig ist Pflicht |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Nextcloud 32 liefert bei `MKCOL` denselben `oc-fileid`-Kopf und dieselben Statuscodes wie 35 | Pattern 1, Statusmatrix | Id fehlt (Rückfall `stat` fängt es) oder ein Zweig weicht ab; Live-Test auf 32 deckt es auf |
| A2 | `compose.exapp.yml` mit `nextcloud:32.0.15-apache` und `bootstrap_exapp.sh` ergibt eine lauffähige ExApp-Strecke (HaRP ab 32) | Pitfall 10 | D-31-06 auf 32 nicht erfüllbar; Owner-Entscheid nötig |
| A3 | `id` in der Form `file:<n>` erfüllt D-31-03, obwohl `files_upload` keine Id liefert | Pattern 5 | Owner wollte evtl. `files_upload` ebenfalls um eine Id erweitern (nicht im Umfang) |
| A4 | 423 und 404 bei `MKCOL` verhalten sich wie bei `PUT` | Pattern 2 | nur Meldungstext; Zweig existiert trotzdem |
| A5 | Ein `PROPFIND` unter einer Datei (`/datei.txt/x`) antwortet 404 | Pattern 3 | Zählung von unten müsste 409/anderes behandeln; Unit- und Live-Test |
| A6 | Probe-Messung rund 510 Bytes entspricht der finalen Registrierung | Pattern 6 | Budget-Skript misst ohnehin, Decke 1400 weit entfernt |

## Open Questions (RESOLVED)

1. **D-31-03 "in derselben Form wie `files_upload`"**
   - What we know: `files_upload` antwortet `{"path","etag","created"}` ohne Id (`dav.py:795-799, 822-826, 1051-1055`). Die etablierte Id-Form ist `"id": "file:<fileid>"`.
   - What's unclear: ob der Owner "dieselbe Form" als `id: file:<n>` liest oder `files_upload` mit erweitert haben will.
   - Recommendation: `id` als `file:<n>` (wie `files_list`), `files_upload` unverändert lassen (nicht im Umfang, ändert Budget und Paartests des Uploads). Im Plan als Annahme mit Owner-Hinweis führen.
   - RESOLVED: durch D-31-03 (Owner, 12.11.2026, "Ok"): `id` als `file:<n>` aus `ids.encode_file`, `files_upload` bleibt unverändert; umgesetzt in 31-02 Task 2.

2. **NC 32 unter Impersonation**
   - What we know: keine ExApp-Strecke für 32 im Repo erprobt; CI kennt 34.0.3 und 35.0.1.
   - What's unclear: ob `bootstrap_exapp.sh` gegen 32.0.15 ohne Änderung durchläuft.
   - Recommendation: früher Task "Strecke 32 aufbauen, `occ status` und `app_api:app:list` belegen"; scheitert er, Befund zum Owner, ohne den Rest der Phase zu blockieren (Code und Gates hängen nicht daran). Optional einen CI-Job analog `canary-nc35` mit 32 nicht in dieser Phase.
   - RESOLVED: durch Plan 31-01 (früher Aufbau der Strecke 32 mit `--manual`, Kontrollen a bis c und festem Abbruchkriterium `STRECKE NC32 ergebnis=abgebrochen` mit Befund an den Owner); 31-05 Task 4 hält an, wenn die Strecke abgebrochen ist.

3. **Weg über das Werkzeug im ExApp-Container**
   - What we know: Phase 30 belegte `MKCOL` aus dem Container (Image 0.3.2), nicht das Werkzeug; Live-Tests der Familie rufen Werkzeugfunktionen mit `MODE_APPAPI`-Credentials.
   - Recommendation: Live-Test ruft `files_tools.create_folder` mit AppAPI-Credentials (gleiche Naht wie Produktion, `Credentials.auth`); ein Aufruf über das neu gebaute ExApp-Image ist mit `bootstrap_exapp.sh` ohnehin Teil der Strecke und kann als zusätzlicher Beleg über `scripts/acceptance_all_tools.py` oder einen MCP-HTTP-Aufruf laufen.
   - RESOLVED: durch den Live-Test `tests/integration/test_files_create_folder_live.py` mit `MODE_APPAPI`-Credentials (31-05 Tasks 1 und 2, Läufe in Tasks 3 und 4), dazu das Abnahmeskript auf der Strecke 32 (31-05 Task 4).

4. **Wortlaut 409 bei Datei als Elternknoten**
   - What we know: ohne `parents` wird es `parent_missing` (Status allein), mit `parents` erkennt die Zählung die Datei.
   - Recommendation: Hinweistext deckt "eine Datei steht im Pfad" mit ab (Gate-Inventar #1); kein Auswerten von `s:message`.
   - RESOLVED: durch den neuen Hinweistext von `parent_missing` ("... and check that no file stands in the path."), wortgleich in dav.py und tests/unit/test_dav_fileid_paths.py (31-02 Task 1); kein `s:message` in Meldungen.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python in `.venv` | alle Tests, Gates | ✓ | 3.13.13 | , |
| uv | CI-gleiche Läufe | ✓ | 0.11.7 | `.venv/Scripts/python.exe -m ...` |
| httpx, respx, mcp | Unit, Contract | ✓ | 0.28.1, 0.23.1 | , |
| Docker CLI | Live-Beweis | ✓ | 29.5.2 (Engine/Container in dieser Sitzung nicht geprüft, bewusst nicht angefasst) | , |
| `.env.nc35`, `.env.exapp` im Worktree | Live-Tests | ✗ | , | aus dem Hauptcheckout bzw. per `bootstrap_exapp.sh` erzeugen (gitignored) |
| ExApp-Strecke Nextcloud 35 | D-31-06 | vermutlich (nc35-Topologie der Phase 30) | 35.0.0 | CI-Job `canary-nc35` (35.0.1) |
| ExApp-Strecke Nextcloud 32 | D-31-06 | ✗ | , | Aufbau nach Pitfall 10; sonst Owner-Entscheid |
| Live-Gruppenordner mit ACL | Erfolgskriterium 3 | nicht nötig | , | Rohantwort Phase 30 (D-31-07) |

**Missing dependencies with no fallback:** ExApp-Strecke auf Nextcloud 32 (muss aufgebaut werden).
**Missing dependencies with fallback:** `.env`-Dateien im Worktree.

Lokale Gate-Probe in dieser Sitzung: `tests/contract/test_tool_classes.py` und `tests/unit/test_files_upload_exclusion.py` grün (23 passed, 1,3 s); `scripts/check_tool_budget.py`: 15706 Bytes, 23 Werkzeuge, größtes `files_upload` 1377 Bytes.

## Validation Architecture

Übersprungen: `workflow.nyquist_validation` ist in `.planning/config.json` ausdrücklich `false`. Die Testzuordnung je Anforderung steht im Gate-Inventar und in den Pitfalls.

## Security Domain

`security_enforcement` aktiv (ASVS L1, Block ab high).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (unverändert) | bestehende Anmeldewege, 401 nie wiederholt (`dav._check`) |
| V3 Session Management | nein | , |
| V4 Access Control | ja | Impersonation/Credentials aus dem Auth-Kanal, kein Nutzerparameter (Gate `test_no_input_schema_accepts_a_user_parameter`); Rechte entscheidet Nextcloud (403); Ausschluss `kein-ki` fail-closed; Sandbox `NC_MCP_FILES_ROOT` |
| V5 Input Validation | ja | `dav.safe_path` (Traversal, Backslash, Steuerzeichen), `quote()` in `files_url`, Namensprüfung des Servers (400), `parents` als `bool` |
| V6 Cryptography | nein | , |
| V7 Error Handling and Logging | ja | `@graceful`: Fehlertext ohne URL/Traceback (`from None`), Audit-Zeile nur mit Parameternamen (`path`, `parents`), nie Werten |
| V12 Files and Resources | ja | kein Body, kein Überschreiben (`MKCOL` kann nicht ersetzen), Wurzel nie angelegt |

### Known Threat Patterns (Grundlage für `<threat_model>` je Plan)

| ID-Vorschlag | Pattern | STRIDE | Standard Mitigation | Restrisiko |
|--------------|---------|--------|---------------------|-----------|
| T-31-01 | Pfadausbruch (`..`, Backslash, kodierte Trenner) | Tampering | `safe_path` vor jedem Request; Segmente nur `within(root)` | keins bekannt |
| T-31-02 | Anlegen in oder unter getaggtem Ordner | Information Disclosure / Tampering | `_writable` vor jedem `MKCOL`, Ablehnung `parent_missing(target)` | Restorakel wie `tech-upload-oracle`: getaggter Ordner neben sichtbarem antwortet "Eltern fehlt"; dokumentieren (FOLD-06) |
| T-31-03 | Ausschlussprüfung nicht beantwortbar | Elevation (Umgehung) | fail-closed `unavailable_error`, kein `PROPFIND`, kein `MKCOL` | keins |
| T-31-04 | Existenzorakel über `PROPFIND` vor der Prüfung | Information Disclosure | Reihenfolge Guard vor Netz; Paartest mit catch-all-Route | Anzahl Requests unterscheidet sich (dokumentierte Grenze `limit-timing`) |
| T-31-05 | Tag wird zwischen REPORT und `MKCOL` gesetzt | Tampering | ein Scope je Aufruf, wie Upload | akzeptiert, gleiche Klasse wie Chunk-Upload |
| T-31-06 | Sandbox-Wurzel angelegt oder überschritten | Elevation | Ziel gleich Wurzel vorab ablehnen; Kandidaten `p != root`; fehlende Wurzel ergibt `parent_missing` | keins |
| T-31-07 | Datei am Pfad als Erfolg gemeldet | Tampering (Integrität der Aussage) | `stat` nach 405, `is_collection` | keins |
| T-31-08 | Ordnerflut durch ein Modell | Denial of Service | Deckel 10 vorab (D-31-01), Audit je Aufruf | viele Aufrufe hintereinander bleiben möglich; Audit macht sie sichtbar |
| T-31-09 | Halbe Kette bleibt unbemerkt stehen | Repudiation | Abbruch nennt angelegte Pfade (D-31-02), Audit-Zeile | Connector kann nicht aufräumen (by design) |
| T-31-10 | Body/Header-Injektion in `MKCOL` | Tampering | kein Body, kein `Content-Type`; AST-Nadel; Pfad via `quote` | keins |
| T-31-11 | Confused Deputy (fremdes Home) | Elevation | kein `user`-Parameter; gemessen 403 auf fremdes Home unter Impersonation | keins |
| T-31-12 | Servertext oder URL in Fehlermeldung | Information Disclosure | eigene Meldungen, kein `s:message`; `graceful` mit `from None` | keins |
| T-31-13 | Redirect leitet Auth-Kopf um | Spoofing | `follow_redirects=False`, `_check` lehnt 3xx ab | keins |
| T-31-14 | Falsche Annotation (idempotent/destruktiv) täuscht Client | Spoofing | eigene Klasse `CREATE_IDEMPOTENT`, Gate | keins |

## Empfohlener Planschnitt (Claude's Discretion)

| Plan | Inhalt | Welle |
|------|--------|-------|
| 31-01 | `dav.make_folder` + `_check_mkcol` + `oc-fileid`-Parsing, `_PARENT_HINT` (beide Stellen), `files.create_folder` mit Kette/Zählung/Deckel/Abbruch, Unit-Tests aller Zweige und der Exklusion (5 Guard-Zustände, kein Request nach Ablehnung, REPORT einmal) | 1 |
| 31-02 | Registrierung, `CREATE_IDEMPOTENT`, Allowlist, Freeze/Klassen/Paarfall Unit, Werkzeugmenge und Annotations-Gate, Bundle, `MKCOL`-Nadel mit Gegenproben, Budget-Messzeile, Kanarie- und Live-Paar-Einträge (Code), Kanarie-Refusal-Unit, Abnahmeskript, README-Tabelle/Zahl/Bundles (weil `test_the_readme_permission_table...` sonst rot) | 2 |
| 31-03 | Live: Strecke 32 aufbauen (eigener erster Task mit Abbruchkriterium), Live-Test unter Impersonation auf 35 und 32 (frei, vorhanden, Datei, Eltern fehlt, Kette, Deckel, Teilabbruch per Freigabe ohne Recht, `kein-ki` mit Paar, Sandbox-Wurzel), geteilter Ordner ohne Recht live, Kanarie und Live-Paar auf 35, Abnahmeskript; Belege nach `docs/folder-evidence.md` | 3 |
| 31-04 | `docs/exclusion*.md` mit neuem Anker und Beleglink auf `folder-evidence.md`, Truth-Test-Erweiterung, README.de/fr Feinschliff, drei CHANGELOGs, voller Lauf aller Gates | 4 (nach 31-03, wegen Beleg) |

README-Änderungen müssen in 31-02 mit der Registrierung kommen, weil der Rechtetabellen-Test sonst den Zwischenstand rot macht.

## Sources

### Primary (HIGH confidence)
- Repo-Code: `src/mcp_connector/nextcloud/clients/dav.py`, `tools/files.py`, `server/__init__.py`, `server/reg_files.py`, `nextcloud/exclusion.py`, `tools/withhold.py`, `audit/allowlist.py`, `ids.py`, `errors.py`
- Gates: `tests/contract/tool_classes.py`, `test_tool_classes.py`, `test_tool_surface.py`, `test_tool_bundles.py`, `test_no_destructive_calls.py`, `result_shapes.py`; `tests/unit/test_pair_equality_files.py`, `test_files_upload_exclusion.py`, `test_canary_refusals.py`, `test_docs_exclusion_truth.py`, `test_dav_fileid_paths.py`; `tests/integration/test_canary.py`, `canary_world.py`, `test_pair_equality_live.py`, `test_exapp_dav_matrix.py`; `tests/conftest.py`
- Messbericht `docs/spike-tasks.md` (1, 2, 7, 9, 11, 12) und Rohdaten `raw/nc35-mkcol.txt`, `raw/nc35-gruppenordner.txt` der Phase 30
- `scripts/check_tool_budget.py` (lokal ausgeführt), `scripts/acceptance_all_tools.py`, `.github/workflows/ci.yml`, `compose.exapp.yml`, `compose.nc35.yml`, `scripts/bootstrap_exapp.sh`
- `.planning/REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `31-CONTEXT.md`

### Secondary (MEDIUM confidence)
- `.planning/research/v1.8-tasks-080-RESEARCH.md` (B1 bis B4, Gate-Liste, Ablaufskizze), zitiert sabre `CorePlugin.php` und Nextcloud `UploadAutoMkcolPlugin.php`

### Tertiary (LOW confidence)
- keine Websuche nötig; alle tragenden Aussagen stammen aus Repo und Messdaten

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, keine neuen Pakete, alles installiert und gelesen
- Architecture: HIGH, Bausteine existieren, Muster vom Upload übertragbar
- Pitfalls: HIGH für Code-Pitfalls, MEDIUM für NC 32 (ungemessen)

**Research date:** 2026-11-12
**Valid until:** 2026-12-12 (Code-Befunde gelten bis zur nächsten Änderung der genannten Dateien)

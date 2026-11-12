# Phase 31: Ordner anlegen - Context

**Gathered:** 2026-11-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Ein Assistent kann über `files_create_folder` einen Ordner anlegen, auf Wunsch samt fehlender Elternordner (`parents=true`). Der neue Schreiber der Dateifläche hält jede Grenze, die der Upload hält (Ausschluss `kein-ki`, Sandbox `NC_MCP_FILES_ROOT`, Audit, Kanarie, Klassifikations-Freeze). Die Phase ist für sich allein releasefähig (Rückfallschnitt, falls Phase 32 klemmt).

Nicht in dieser Phase: Ordner umbenennen, verschieben oder löschen; alles zum Bundle `tasks` (Phasen 32 und 33); Store-Text und Release (Phase 34).

Die Anforderungen FOLD-01 bis FOLD-06 und die fünf Erfolgskriterien in ROADMAP.md sind fest. Diese Datei hält nur die Entscheidungen fest, die dort offen waren.

</domain>

<decisions>
## Implementation Decisions

### Deckel für neue Ordner (E10, FOLD-02)
- **D-31-01:** Bräuchte ein Aufruf mit `parents=true` mehr als 10 neue Ordner, lehnt das Werkzeug VORAB ab und legt nichts an. Es zählt dazu vor dem ersten `MKCOL` die fehlenden Segmente. Die Meldung nennt die gezählte Zahl und den Deckel 10. Es bleibt keine halbe Kette stehen, die allein der Deckel verursacht hat. (Owner, 12.11.2026, Auswahl "Vorab ablehnen")
- **D-31-02:** Der Satz aus FOLD-02 "scheitert ein Segment mittendrin, nennt die Antwort die bereits angelegten Ordner" gilt unverändert für alle anderen Abbrüche (Rechte, Sperre, Serverfehler, Kontingent, Wettlauf mit einem anderen Schreiber). Seit dem Owner-Entscheid vom 2026-11-12 gehören Netzfehler (Timeout, Verbindungsabbruch) dazu: die Antwort trennt "angelegt" (sicher in diesem Aufruf angelegte Ordner) von "Zustand unbekannt" (das Segment, dessen MKCOL beim Abbruch unterwegs war) und nennt den erneuten Aufruf mit `parents=true` als gefahrlos (Plan 31-04b).

### Antwortinhalt
- **D-31-03:** Die Erfolgsantwort trägt Pfad, `created` und die Datei-Id des Zielordners, in derselben Form wie `files_upload` sie liefert. Bei `parents=true` kommt die Liste der wirklich neu angelegten Pfade dazu. (Owner, 12.11.2026, Auswahl "Pfad, created, Datei-Id") Präzisierung nach der Recherche: `files_upload` liefert keine Id (nur `path`, `etag`, `created`); die Id kommt als `id: "file:<n>"` in der Form von `files_list` und `files_search` (`ids.encode_file`), `files_upload` bleibt unverändert. (Owner, 12.11.2026, wörtlich "Ok" auf diese Empfehlung)
- **D-31-04:** Bei einem schon vorhandenen Ordner (`created: false`, E5) kommt die Datei-Id aus derselben Abfrage, die prüft, dass am Pfad ein Ordner und keine Datei liegt. Kein zusätzlicher Aufruf nur für die Id.

### Schreibrecht
- **D-31-05:** Keine Vorprüfung des Schreibrechts. Das Werkzeug wertet die Ablehnung des Servers aus: 403 ergibt die Meldung "keine Rechte" und nennt, was in diesem Aufruf schon angelegt wurde. (Owner, 12.11.2026, Auswahl "Nur Ablehnung auswerten")

### Namen am Rand
- **D-31-08:** Trägt ein Segment des Zielpfads Leerraum am Anfang oder Ende, lehnt `files_create_folder` VORAB ab, vor jedem Schreiben und ohne etwas anzulegen, statt den Namen still zu kürzen; das gilt für jedes Segment, mit und ohne `parents`, und `safe_path` bleibt für alle anderen Werkzeuge, wie es ist. (Owner, 2026-11-12, wörtlich "Ok" auf diese Empfehlung nach Befund 2 aus 31-05; Plan 31-05b)
- **D-31-09:** Antwortet Nextcloud auf einen Namen wie `x.part` mit 405 und danach mit einem Knoten, der kein Ordner ist und keine gültige Datei-Id trägt, sagt das Werkzeug nur, dass der Name als Ordner nicht anlegbar und von einem Nicht-Ordner belegt ist, und nennt keine Datei, die es nicht gibt. (Owner, 2026-11-12, wörtlich "Ok" auf diese Empfehlung nach Befund 5 aus 31-05; Plan 31-05b)

### Live-Beweis
- **D-31-06:** Der Live-Beweis des Werkzeugs läuft auf Nextcloud 32 und 35 (unteres und oberes Ende des Store-Fensters), unter AppAPI-Impersonation. (Owner, 12.11.2026, Auswahl "32 und 35, ACL aus Phase 30")
- **D-31-07:** Für den Gruppenordner mit ACL gilt die Rohantwort aus Phase 30 (docs/spike-tasks.md, Abschnitte 2.2, 2.4 und 12.2). Der Gruppenordner wird in dieser Phase nicht erneut live aufgebaut. Der geteilte Ordner ohne Schreibrecht wird live belegt, wie Erfolgskriterium 3 es verlangt.

### Bereits entschieden, hier nur zur Erinnerung
- E5: vorhandener Ordner ist ein Erfolg mit `created: false`, erst nach der Prüfung, dass dort ein Ordner liegt; eine Datei am Pfad ist ein Konflikt.
- E10: höchstens 10 neue Ordner je Aufruf.
- E1: Das Gesamtbudget der Werkzeugliste folgt der Messung plus 15 Prozent; die Decke je Werkzeug (1400 Bytes) bleibt.
- Ablehnung im ausgeschlossenen Ordner ist byte-gleich zu "Elternordner fehlt" (FOLD-04, D-27-01).

### Claude's Discretion
- Wie die fehlenden Segmente vor dem ersten `MKCOL` gezählt werden (eine Abfrage je Segment von oben oder von unten, oder ein anderer Weg), solange D-31-01 gilt und die Ausschlussprüfung vor jedem einzelnen `MKCOL` bleibt.
- Wortlaut der Meldungen je Zweig (400, 403, 405, 409, 423, 507, 5xx), solange jeder Zweig eine eigene, benannte Meldung hat und keiner in "unexpected status" endet.
- Name des Feldes für die Liste der neu angelegten Pfade.
- Aufteilung in Pläne und Wellen.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Anforderungen und Erfolgskriterien
- `.planning/REQUIREMENTS.md` (FOLD-01 bis FOLD-06, Scope-Entscheidungen E1, E5, E10, E12, Tabelle Annahmen A7, A8, A9)
- `.planning/ROADMAP.md` (Abschnitt "Phase 31: Ordner anlegen": Ziel, fünf Erfolgskriterien, Rückfallschnitt)
- `.planning/PROJECT.md` (Constraints, Out of Scope, Key Decisions zur Dateifläche)

### Messwerte aus Phase 30
- `docs/spike-tasks.md` Abschnitt 1 (MKCOL unter AppAPI-Impersonation, Statusmatrix 1.3 und 1.4)
- `docs/spike-tasks.md` Abschnitt 2 (Gruppenordner mit ACL und externer Speicher, 2.2 und 2.4)
- `docs/spike-tasks.md` Abschnitt 9.1 (Was Phase 31 übernimmt: Statuscodes je Zweig, 400 und 507 kommen vor, kein eigener Zweig für Impersonation)
- `docs/spike-tasks.md` Abschnitt 12.2 (Rohantwort Gruppenordner, Beleg für Erfolgskriterium 3)
- `docs/spike-tasks.md` Abschnitt 7 (Inventar der Gates und Zusagen, A17)

### Recherche des Milestones
- `.planning/research/v1.8-tasks-080-RESEARCH.md`
- `.planning/research/PITFALLS.md`
- `.planning/research/ARCHITECTURE.md`

### Vorbild v1.7-Kette
- `.planning/phases/29-pr-fkommando-und-doku/29-CONTEXT.md` (Muster der Gates und der Doku-Pflichten für einen Schreiber der Dateifläche)
- `docs/exclusion.md`, `docs/exclusion.de.md`, `docs/exclusion.fr.md` (bekommen den Satz zur Grenze "Ordner neben getaggtem Ordner")

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mcp_connector/nextcloud/clients/dav.py`: `parent_missing(path)` ist die eine Quelle des Satzes "Elternordner fehlt" (D-27-01); der Hinweistext bekommt den Verweis auf `files_create_folder` und wird an beiden Stellen (Fabrik und Test) gemeinsam geändert (FOLD-05). `not_found` daneben folgt demselben Muster.
- `src/mcp_connector/server/reg_files.py`: Registrierung von `files_upload` und `files_update`, Antwortmodell mit `file_id`; Vorbild für die Antwortform nach D-31-03.
- `src/mcp_connector/tools/files.py`: Schreibpfad des Uploads mit Ausschlussprüfung und Sandbox; dieselben Prüfungen gelten vor jedem `MKCOL`.
- `scripts/tasks_spike.py`: gemessene `MKCOL`-Aufrufe aus Phase 30 als Referenz für Kopfzeilen und Statuscodes (kein Produktivcode).

### Established Patterns
- Alle `MKCOL` liegen in `dav.py` und gehen ohne Body hinaus; eine positive Nadel hält das fest, `EXPECTED_PUT_CALLS` bleibt unverändert.
- Jeder Schreiber der Dateifläche steht in `FILE_WRITERS` mit Paarfall (`tests/contract/tool_classes.py`, `tests/contract/test_tool_classes.py`), in `MUST_REFUSE` der Kanarie (`tests/integration/test_canary.py`) und im Destruktiv-Gate (`tests/contract/test_no_destructive_calls.py`).
- Die Annotation des Werkzeugs ist anlegend, nicht destruktiv, idempotent; das Annotations-Gate braucht dafür eine eigene Werkzeugklasse (E5, FOLD-03).
- `scripts/acceptance_all_tools.py` ist das Abnahmeskript, das jedes Werkzeug kennt.

### Integration Points
- Bundle `files` (Bundle-Zuordnung, eingefrorene Werkzeugmenge, Audit-Erlaubnisliste, `@graceful`).
- Budget der Werkzeugliste (`scripts/check_tool_budget.py`).
- Drei READMEs (Werkzeugliste, Rechtetabelle, Werkzeugzahl) und drei CHANGELOG-Dateien.

</code_context>

<specifics>
## Specific Ideas

- Die Antwort soll einem Assistenten erlauben, direkt weiterzuarbeiten, so wie nach `files_upload`: deshalb die Datei-Id.
- Der Melder von #44 arbeitet fast nur mit Gruppenordnern und ACL; der Beleg dafür ist die Rohantwort aus Phase 30, nicht ein neuer Aufbau.
- Reichweite der Messung aus Phase 30 war eine Instanz (35.0.0, SQLite); der Weg über ein Werkzeug der App ist erst mit dieser Phase belegt.

</specifics>

<deferred>
## Deferred Ideas

- Verhalten der Unteraufgaben beim Wiederöffnen einer Elternaufgabe: discuss-phase von Phase 33.
- Umfang des Admin-Schalters aus E15 (welche Werkzeuge er umfasst): discuss-phase von Phase 33.
- Mindestfrist des Papierkorbs für TMOD-07: Phase 33.

Zur Phase 31 selbst kam nichts außerhalb des Umfangs auf.

</deferred>

---

*Phase: 31-Ordner anlegen*
*Context gathered: 2026-11-12*

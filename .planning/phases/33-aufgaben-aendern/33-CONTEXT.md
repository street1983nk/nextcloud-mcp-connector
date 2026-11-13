# Phase 33: Aufgaben ändern - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Ein Assistent kann eine einzelne Aufgabe abhaken und wieder öffnen (`tasks_complete`), in den genannten Feldern ändern (`tasks_update`) und in eine andere, ausdrücklich genannte Liste verschieben (`tasks_move`). Nie wird eine zwischenzeitliche Änderung überschrieben, nie geht etwas außer den genannten Feldern verloren. Anforderungen TMOD-01 bis TMOD-06 und TMOD-08 (`.planning/REQUIREMENTS.md`). Löschen (TMOD-07) ist nicht im Umfang (Owner, 12.11.2026, "Löschen raus").

Abtrennbare Teile, je ein eigener Plan: Abhaken und Wiederöffnen (TMOD-03), Felder ändern (TMOD-04), Verschieben (TMOD-08). Ein Teil fällt nur per Owner-Entscheid heraus.

</domain>

<decisions>
## Implementation Decisions

### Bereits entschieden (Phase 30, Owner 12.11.2026, docs/spike-tasks.md 10.4)
- **D-33-00a:** Wiederkehrende Aufgaben werden von allen drei ändernden Werkzeugen abgelehnt (A15).
- **D-33-00b:** Abhaken einer Elternaufgabe hakt ihre Unteraufgaben mit ab, wie die Tasks-App (A16).
- **D-33-00c:** Verschieben einer Elternaufgabe nimmt ihre Unteraufgaben mit, wie die Tasks-App (A21).
- **D-33-00d:** Eigener Admin-Schalter für die ändernden Aufgaben-Werkzeuge, ab Werk aus, nach dem Vorbild `NC_MCP_FILES_UPDATE` samt Admin-Settings-Kette (`CONFIG_KEYS`, Formular, `info.xml`), E15.

### Schalter (Owner 13.11.2026, "Alle drei")
- **D-33-01:** Der Schalter umfasst alle drei Werkzeuge: `tasks_complete`, `tasks_update`, `tasks_move`. Ist er aus, werden die drei nicht registriert (wie `files_update`); `tasks_search`, `tasks_read`, `tasks_create` bleiben davon unberührt. Ein Schalter, kein zweiter. Name und Texte des Schalters legt die Planung nach dem Muster von `NC_MCP_FILES_UPDATE` fest (Vorschlag `NC_MCP_TASKS_UPDATE`), in DE/EN/FR.
- **D-33-02:** Owner-Hinweis bei der Entscheidung zur Kenntnis genommen: der ursprüngliche Auslöser S1 (Löschen) ist entfallen; der Schalter bleibt trotzdem, ab Werk aus.

### ETag (Owner 13.11.2026, "Aus tasks_read")
- **D-33-03:** `tasks_read` gibt die ETag der Aufgabe aus. Alle drei ändernden Werkzeuge verlangen diese ETag als Pflichtparameter (Präzedenz `files_update`) und schreiben mit `If-Match` genau darauf; nie ohne `If-Match`, nie `If-Match: *`. 412 heißt Ablehnung mit der Aufforderung, neu zu lesen; kein stiller zweiter Versuch.
- **D-33-04:** Die Mehrbytes in `tasks_read` gehen in das Budget, das nach der Hausregel aus dem Endstand gemessen wird.

### Wiederöffnen einer Elternaufgabe (Owner 13.11.2026, "Kinder bleiben erledigt")
- **D-33-05:** Wiederöffnen öffnet nur die genannte Aufgabe; erledigte Unteraufgaben bleiben erledigt, kein Massen-Schreibzugriff.
- **D-33-06:** Vor dem Bau wird gemessen, was die Tasks-App 0.18.1 beim Wiederöffnen einer Elternaufgabe mit erledigten Kindern tut. Weicht sie ab (öffnet sie die Kinder mit), wird der Owner gefragt, bevor gebaut wird; sonst gilt D-33-05 ohne Rückfrage.

### Felder leeren und Name (Owner 13.11.2026, "Leeren ja, tasks_complete")
- **D-33-07:** `tasks_update` darf Fälligkeit, Startdatum, Beschreibung und Elternaufgabe entfernen. Die Form im Schema (null oder leerer Wert) wählt die Planung so, dass "nicht genannt" und "entfernen" eindeutig unterscheidbar sind. Titel ist nicht leerbar; Priorität entfernen heißt Zeile weg (gleichbedeutend mit 0). Tags leeren heißt `CATEGORIES` entfernen. Was die Tasks-App beim Entfernen schreibt (Zeile weg oder leerer Wert), wird gemessen und übernommen (offener Punkt aus spike-tasks.md Abschnitt 11).
- **D-33-08:** Das Abhak-Werkzeug heißt `tasks_complete`, mit einem Parameter `completed` (true: abhaken, false: wieder öffnen). Felder wie gemessen (spike-tasks.md 3.5): abhaken setzt `STATUS:COMPLETED`, `PERCENT-COMPLETE:100`, `COMPLETED` in UTC mit `Z`; wieder öffnen setzt `STATUS:NEEDS-ACTION` und entfernt `COMPLETED` und `PERCENT-COMPLETE`; beide ziehen `LAST-MODIFIED` und `DTSTAMP` nach, kein `SEQUENCE`. Schon im Zielzustand: Erfolg ohne `PUT`, in der Antwort kenntlich.

### Ketten mit Unteraufgaben (Owner 13.11.2026)
- **D-33-09:** Beim Abhaken und Verschieben einer Elternaufgabe werden zuerst alle Nachfahren (Kinder, Enkel, ...) bearbeitet, die Elternaufgabe zuletzt. Jedes Objekt mit eigener `If-Match` auf eine im selben Aufruf frisch gelesene ETag; nur die Elternaufgabe trägt die ETag des Assistenten (D-33-03). Beim ersten Fehler stoppt das Werkzeug, die Elternaufgabe bleibt unverändert, und die Antwort nennt genau, welche Nachfahren schon geändert sind. Kein automatisches Zurückdrehen. Nachfahren, die schon im Zielzustand sind, werden ohne `PUT` übersprungen.
- **D-33-10:** Obergrenze 50 Nachfahren je Aufruf; darüber lehnt das Werkzeug vor dem ersten Schreibzugriff mit klarer Meldung ab. Der Wert wird durch eine Messung bestätigt (Kosten und Laufzeit einer Kette mit 50 Objekten auf 35 und 32); weicht die Messung deutlich ab, legt die Planung den Wert nach der Hausregel aus dem Messwert fest und nennt ihn dem Owner.
- **D-33-11:** Eine wiederkehrende Aufgabe oder ein Objekt ohne Schreibrecht unter den Nachfahren führt zur Ablehnung vor dem ersten Schreibzugriff (Vorprüfung aus den bereits gelesenen Daten), damit der häufige Fall keine halbe Kette hinterlässt.

### Claude's Discretion
- Antwortform der drei Werkzeuge (Felder, Kurztexte), solange ehrlich und unter 1400 Bytes je Werkzeug.
- Reihenfolge der Nachfahren untereinander (Tiefe zuerst), Zielname beim `MOVE` (gleicher Objektname, `Overwrite: F` Pflicht).
- Wie die eine Aufrufstelle für überschreibenden `PUT` und die eine für `MOVE` im Code geschnitten sind, solange das Destruktiv-Gate sie als eng benannte Ausnahmen mit eigener Gegenprobe führt.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Anforderungen und Entscheide
- `.planning/REQUIREMENTS.md` , TMOD-01 bis TMOD-06, TMOD-08, E8, E13 bis E15, A10, A15 bis A17, A21
- `.planning/ROADMAP.md` Phase 33 , Ziel, fünf Erfolgskriterien, abtrennbare Teile, Research flag
- `.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-CONTEXT.md` , D-32-01 bis D-32-18 (Discovery, Schreibrecht, D-32-18 streng für selbst geteilte Listen, Namen ohne Besitzer)
- `.planning/phases/32-tasks-bundle-suchen-lesen-anlegen/32-RULES.md` , Hausregeln (seriell Docker, RAM-Gate, `-p no:xdist`, Commits ohne Trailer, Push nur mit Owner)

### Messbericht Phase 30
- `docs/spike-tasks.md` §3 , PUT mit If-Match, Erhalt fremder Eigenschaften, nur lesbare Listen, Abhaken/Wiederöffnen der Tasks-App
- `docs/spike-tasks.md` §4.1, §4.2 , MOVE (Overwrite: F Pflicht, If-Match wirkt, 409 UidConflict, 404 ro, 403 Deck, Ziel-Komponenten prüft der Server nicht), Unteraufgaben
- `docs/spike-tasks.md` §7 , Inventar A17 (62 Fundstellen Phase 33)
- `docs/spike-tasks.md` §7.3, §10 , Kette von `NC_MCP_FILES_UPDATE`, E15
- `docs/spike-tasks.md` §9.3, §9.4, §11 , Übergabe an Phase 33, Ungemessenes
- `docs/tasks-evidence.md` , Belege Phase 32

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/mcp_connector/nextcloud/clients/tasks.py`: Discovery (`parse_task_home`, `_shares_itself`, Schreibrecht, Deck-Ausschluss), Aufgaben lesen.
- `src/mcp_connector/nextcloud/clients/caldav.py:391` `put_new_object`: create-only PUT; Vorbild für die neue Schreibschiene mit `If-Match`.
- `src/mcp_connector/tools/tasks.py`: `tasks_search`, `tasks_read`, `tasks_create` (Prüfungen für Priorität, Datum, Zone, `DUE` kein exklusives Ende wiederverwenden), `PER_LIST_TIMEOUT = 2.0`.
- `src/mcp_connector/server/reg_tasks.py`, `reg_files.py:271` (`files_update` mit ETag-Parameter als Muster).
- `src/mcp_connector/config.py:51,723` (`ENV_FILES_UPDATE`), `entry_exapp.py:669`, `exapp/config_values.py:139`, `exapp/admin_settings.py:213`, `exapp/ui/strings.py`: Schalter-Kette.
- `tests/fixtures/tasks_app/`: von der Tasks-App geschriebene Objekte für Rundlauftests (TMOD-02).

### Established Patterns
- `tests/contract/test_no_destructive_calls.py:480` `EXPECTED_PUT_CALLS = 6`: neuer PUT und MOVE sind Review-Ereignisse, eng benannte Ausnahmen mit Gegenprobe.
- Budget der Werkzeugliste aus dem gemessenen Endstand (`scripts/check_tool_budget.py`, derzeit 18770 von 22000).
- Live-Tests auf nc35 und NC 32 je mit und ohne Tasks-App, BASELINE vorher gleich nachher, Rückbau.

### Integration Points
- Bundle `tasks`, Audit-Erlaubnisliste, Annotations-Gate (neue Klasse "ändernd"), Kanarie, Rechtetabelle der READMEs (Phase 34 für Texte).

</code_context>

<specifics>
## Specific Ideas

- Owner-Prio (13.11.2026): "Prio ist das beste Tool für die User und testen ist ein Muss".
- Tasks-App 0.18.1 ist der Maßstab für die geschriebene Form.

</specifics>

<deferred>
## Deferred Ideas

- Löschen einer Aufgabe (TMOD-07), Owner 12.11.2026 gestrichen.
- Tag-Alias `no-ai` neben `kein-ki`: eigene Phase nach 0.8.0 (Owner 13.11.2026).

</deferred>

---

*Phase: 33-aufgaben-aendern*
*Context gathered: 2026-11-13*

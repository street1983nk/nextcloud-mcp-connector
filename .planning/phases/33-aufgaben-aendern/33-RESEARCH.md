# Phase 33: Aufgaben ändern - Research

**Researched:** 2026-11-13
**Domain:** ändernde CalDAV-Zugriffe auf VTODO (überschreibender `PUT` mit `If-Match`, `MOVE` mit `Overwrite: F`), Erhalt fremder Eigenschaften mit icalendar 7.3.0, Ketten über Unteraufgaben, Admin-Schalter, Gates für optionale Werkzeuge
**Confidence:** HIGH für Bibliotheksverhalten (lokal gemessen), Schreibschiene und Gates (Code gelesen, Spike-Messwerte); MEDIUM für Kettenkosten und Tasks-App-Verhalten beim Leeren und Wiederöffnen (ungemessen, als Messschritte ausgewiesen)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Bereits entschieden (Phase 30, Owner 12.11.2026, docs/spike-tasks.md 10.4)
- **D-33-00a:** Wiederkehrende Aufgaben werden von allen drei ändernden Werkzeugen abgelehnt (A15).
- **D-33-00b:** Abhaken einer Elternaufgabe hakt ihre Unteraufgaben mit ab, wie die Tasks-App (A16).
- **D-33-00c:** Verschieben einer Elternaufgabe nimmt ihre Unteraufgaben mit, wie die Tasks-App (A21).
- **D-33-00d:** Eigener Admin-Schalter für die ändernden Aufgaben-Werkzeuge, ab Werk aus, nach dem Vorbild `NC_MCP_FILES_UPDATE` samt Admin-Settings-Kette (`CONFIG_KEYS`, Formular, `info.xml`), E15.

#### Schalter (Owner 13.11.2026, "Alle drei")
- **D-33-01:** Der Schalter umfasst alle drei Werkzeuge: `tasks_complete`, `tasks_update`, `tasks_move`. Ist er aus, werden die drei nicht registriert (wie `files_update`); `tasks_search`, `tasks_read`, `tasks_create` bleiben davon unberührt. Ein Schalter, kein zweiter. Name und Texte des Schalters legt die Planung nach dem Muster von `NC_MCP_FILES_UPDATE` fest (Vorschlag `NC_MCP_TASKS_UPDATE`), in DE/EN/FR.
- **D-33-02:** Owner-Hinweis bei der Entscheidung zur Kenntnis genommen: der ursprüngliche Auslöser S1 (Löschen) ist entfallen; der Schalter bleibt trotzdem, ab Werk aus.

#### ETag (Owner 13.11.2026, "Aus tasks_read")
- **D-33-03:** `tasks_read` gibt die ETag der Aufgabe aus. Alle drei ändernden Werkzeuge verlangen diese ETag als Pflichtparameter (Präzedenz `files_update`) und schreiben mit `If-Match` genau darauf; nie ohne `If-Match`, nie `If-Match: *`. 412 heißt Ablehnung mit der Aufforderung, neu zu lesen; kein stiller zweiter Versuch.
- **D-33-04:** Die Mehrbytes in `tasks_read` gehen in das Budget, das nach der Hausregel aus dem Endstand gemessen wird.

#### Wiederöffnen einer Elternaufgabe (Owner 13.11.2026, "Kinder bleiben erledigt")
- **D-33-05:** Wiederöffnen öffnet nur die genannte Aufgabe; erledigte Unteraufgaben bleiben erledigt, kein Massen-Schreibzugriff.
- **D-33-06:** Vor dem Bau wird gemessen, was die Tasks-App 0.18.1 beim Wiederöffnen einer Elternaufgabe mit erledigten Kindern tut. Weicht sie ab (öffnet sie die Kinder mit), wird der Owner gefragt, bevor gebaut wird; sonst gilt D-33-05 ohne Rückfrage.

#### Felder leeren und Name (Owner 13.11.2026, "Leeren ja, tasks_complete")
- **D-33-07:** `tasks_update` darf Fälligkeit, Startdatum, Beschreibung und Elternaufgabe entfernen. Die Form im Schema (null oder leerer Wert) wählt die Planung so, dass "nicht genannt" und "entfernen" eindeutig unterscheidbar sind. Titel ist nicht leerbar; Priorität entfernen heißt Zeile weg (gleichbedeutend mit 0). Tags leeren heißt `CATEGORIES` entfernen. Was die Tasks-App beim Entfernen schreibt (Zeile weg oder leerer Wert), wird gemessen und übernommen (offener Punkt aus spike-tasks.md Abschnitt 11).
- **D-33-08:** Das Abhak-Werkzeug heißt `tasks_complete`, mit einem Parameter `completed` (true: abhaken, false: wieder öffnen). Felder wie gemessen (spike-tasks.md 3.5): abhaken setzt `STATUS:COMPLETED`, `PERCENT-COMPLETE:100`, `COMPLETED` in UTC mit `Z`; wieder öffnen setzt `STATUS:NEEDS-ACTION` und entfernt `COMPLETED` und `PERCENT-COMPLETE`; beide ziehen `LAST-MODIFIED` und `DTSTAMP` nach, kein `SEQUENCE`. Schon im Zielzustand: Erfolg ohne `PUT`, in der Antwort kenntlich.

#### Ketten mit Unteraufgaben (Owner 13.11.2026)
- **D-33-09:** Beim Abhaken und Verschieben einer Elternaufgabe werden zuerst alle Nachfahren (Kinder, Enkel, ...) bearbeitet, die Elternaufgabe zuletzt. Jedes Objekt mit eigener `If-Match` auf eine im selben Aufruf frisch gelesene ETag; nur die Elternaufgabe trägt die ETag des Assistenten (D-33-03). Beim ersten Fehler stoppt das Werkzeug, die Elternaufgabe bleibt unverändert, und die Antwort nennt genau, welche Nachfahren schon geändert sind. Kein automatisches Zurückdrehen. Nachfahren, die schon im Zielzustand sind, werden ohne `PUT` übersprungen.
- **D-33-10:** Obergrenze 50 Nachfahren je Aufruf; darüber lehnt das Werkzeug vor dem ersten Schreibzugriff mit klarer Meldung ab. Der Wert wird durch eine Messung bestätigt (Kosten und Laufzeit einer Kette mit 50 Objekten auf 35 und 32); weicht die Messung deutlich ab, legt die Planung den Wert nach der Hausregel aus dem Messwert fest und nennt ihn dem Owner.
- **D-33-11:** Eine wiederkehrende Aufgabe oder ein Objekt ohne Schreibrecht unter den Nachfahren führt zur Ablehnung vor dem ersten Schreibzugriff (Vorprüfung aus den bereits gelesenen Daten), damit der häufige Fall keine halbe Kette hinterlässt.

### Claude's Discretion
- Antwortform der drei Werkzeuge (Felder, Kurztexte), solange ehrlich und unter 1400 Bytes je Werkzeug.
- Reihenfolge der Nachfahren untereinander (Tiefe zuerst), Zielname beim `MOVE` (gleicher Objektname, `Overwrite: F` Pflicht).
- Wie die eine Aufrufstelle für überschreibenden `PUT` und die eine für `MOVE` im Code geschnitten sind, solange das Destruktiv-Gate sie als eng benannte Ausnahmen mit eigener Gegenprobe führt.

### Deferred Ideas (OUT OF SCOPE)
- Löschen einer Aufgabe (TMOD-07), Owner 12.11.2026 gestrichen.
- Tag-Alias `no-ai` neben `kein-ki`: eigene Phase nach 0.8.0 (Owner 13.11.2026).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TMOD-01 | Gemeinsame Schreibschiene: lesen, dann `PUT` mit `If-Match` auf die gelesene ETag; nie ohne, nie `*`; 412 heißt neu lesen; nur lesbare Listen und Deck abgelehnt; wiederkehrende abgelehnt; genau eine Aufrufstelle für den überschreibenden `PUT`, Zählgate nachgezogen; create-only bleibt; eigener Schalter ab Werk aus | Pattern 1 (Schreibschiene in `clients/tasks.py`), Pattern 5 (Schalter-Kette mit Fundstellen), F6 (Gate-Umbau `EXPECTED_PUT_CALLS` 6 auf 7), Pitfalls 1 bis 4 |
| TMOD-02 | Nur die genannten Felder ändern sich, Rest inhaltlich erhalten, belegt mit Rundlauf auf den Fixtures | Abschnitt "icalendar 7.3.0 gemessen" (Rundlauf byte-gleich nur mit `sorted=False`, Kanonisierung bei VTIMEZONE-RRULE, Faltung, `\N`, Kleinschreibung), Pattern 2 (Editor auf logischen Zeilen), Validation: zwei unabhängige Beweise |
| TMOD-03 | `tasks_complete` abhaken und wieder öffnen, Felder wie gemessen, Zielzustand ohne `PUT`, Kinder mit abhaken | Pattern 3 (Kette), Code Example "Abhaken", Messung M-1 (D-33-06) |
| TMOD-04 | `tasks_update` Felder mit Prüfungen wie `tasks_create`, Elternaufgabe gleiche Liste, nicht selbst, kein Nachfahr; ohne Unterschied kein Schreiben; Status und Liste nicht änderbar | Pattern 4 (Prüfung auf dem zusammengeführten Stand), F4 (Schema leer heißt entfernen), Messung M-2 (D-33-07), Größenprototyp 1368 Bytes |
| TMOD-05 | Ehrliche Annotationen, eigene Klasse, Freeze, Bundle, Audit, `@graceful`, Klassifikation, Kanarie, Abnahmeskript, Rechtetabelle, Changelogs, Budget aus Endstand | F6 bis F9 (optionale Werkzeuge fallen heute durch drei Gates), Open Question 1 (MCP-Spezifikation zu `destructiveHint`), Pitfall 6 (Budget misst heute nur den Standardzustand) |
| TMOD-06 | Live-Beweis inkl. Impersonation, veraltete ETag, Zwei-Konten-Negativbeweis, Deck unerreichbar | Abschnitt "Messungen der Pläne" M-3, M-4, Environment, Planschnitt 33-07 |
| TMOD-08 | `tasks_move`: ETag, Ziel genannt und gegen Discovery aufgelöst, Schreibrecht auf Quelle und Ziel, nie Deck, nie über belegtes Ziel, UID bleibt, wiederkehrende abgelehnt, Kinder ziehen mit, `MOVE` als eng benannte Ausnahme | Pattern 3 und 6 (Vorabprüfung des Ziels per einem REPORT, Mehrdeutigkeit von 412), F7 (MOVE-Ausnahme mit AST-Pin) |
</phase_requirements>

## Project Constraints (from CLAUDE.md, 32-RULES.md und REQUIREMENTS.md)

- Python 3.13, nur über `uv run --no-sync ...`, im Worktree `PYTHONPATH=src`, `PYTHONUTF8=1`; pyright mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`; nie System-Python, nie pip. Mess- und Probeprogramme nie unter `src/` (R6).
- Keine neue Abhängigkeit nötig; Stack bleibt httpx roh, lxml für Körper, icalendar 7.x für ICS (CLAUDE.md "Supporting Libraries").
- Gates aus 32-RULES Abschnitt 3 vor jedem Commit grün: pytest unit+contract mit `-m "not integration and not matrix"`, `check_tool_budget.py`, `ruff check`, `ruff format --check`, pyright, vulture. pytest bei knappem RAM nur mit `-p no:xdist`.
- Commits als `street1983nk <k.cherif@outlook.de>`, ohne jeden Trailer, nie "closes/fixes/resolves #N"; kein Push, Merge, Tag, Kommentar ohne Owner-Freigabe.
- Docker streng seriell, RAM-Gate 4,0 GB, nc35 und nc-mcp-exapp nur start/stop, nie `down`; Zustandsänderungen auf nc35 und 32 nur mit Owner-Freigabezeile; BASELINE vor und nach jedem Live-Lauf gleich; Rückbau mit `X-NC-CalDAV-No-Trashbin: 1` (nur im Harness, nie im Produktcode).
- Env-Dateien nie lesen oder zitieren; Ausgaben vor dem Protokoll gegen Geheimnisse prüfen.
- Sprache: Planungsdokumente deutsch mit echten Umlauten; Code, Werkzeugtexte, Fehlermeldungen englisch und ASCII; nirgends U+2013 oder U+2014, keine Emojis.
- Security-Leitsatz: der Connector sieht und tut nie mehr als der angemeldete Nutzer; jede Ausnahme von "create-only" ist eng benannt und vom Gate bewacht (TOOL-09, A17).
- TASK-01 bleibt: das Kalender-Bundle ändert sich um kein Byte (`tests/unit/test_caldav_bytes_pin.py`, `git diff` auf die drei Kalendertests leer, wenn `caldav.py` berührt wird).

## Summary

Die Schreibschiene ist durch den Spike belegt und braucht keine neue Bibliothek: `PUT` mit `If-Match` auf eine gelesene starke ETag wird unter Impersonation angenommen (204, neue ETag im Antwortkopf), eine veraltete ETag gibt 412 bei unverändertem Objekt, ohne Kopf oder mit `*` überschreibt der Server; `MOVE` mit `Overwrite: F` und `If-Match` verhält sich ebenso, eine belegte Zielposition gibt aber ebenfalls 412. Der Server speichert wörtlich und pflegt kein Feld, der Erhalt fremder Eigenschaften liegt also allein am Connector. [VERIFIED: docs/spike-tasks.md 3.1, 3.2, 4.1]

Der wichtigste neue Befund betrifft icalendar 7.3.0 (lokal gemessen): `Calendar.from_ical(b).to_ical()` sortiert die Eigenschaften alphabetisch; nur `to_ical(sorted=False)` gibt die acht Tasks-App-Fixtures byte-gleich zurück. Auf einem reicheren Objekt kanonisiert die Bibliothek trotzdem: sie ordnet die Teile einer `RRULE` im `VTIMEZONE` um (`BYMONTH=3;BYDAY=-1SU` wird `BYDAY=-1SU;BYMONTH=3`), faltet neu auf 75 Oktette, schreibt `\N` als `\n` und Namen in Großbuchstaben, und ein kaputter Wert in einer bekannten Eigenschaft (`DUE:notadate`) lässt das ganze Objekt nicht parsen. Inhaltlich bleibt alles erhalten (Parameter, `VALARM`, `VTIMEZONE`, `X-`Eigenschaften, unbekannte Komponenten), aber ein strenger Beweis "die Menge der Eigenschaften unterscheidet sich genau um die genannten Felder" hält auf Textebene nur, wenn unberührte Zeilen gar nicht durch den Serialisierer gehen. [VERIFIED: lokale Läufe dieser Recherche]

**Primary recommendation:** Den Text der Aufgabe auf der Ebene logischer Zeilen ändern: unberührte Zeilen bleiben byte-gleich samt ihrer Faltung, nur die Zeilen der genannten Felder im einen `VTODO` werden ersetzt, entfernt oder vor der ersten Unterkomponente eingefügt, und jede neue Zeile erzeugt icalendar (Wegwerf-`Todo` plus `to_ical(sorted=False)`), nie eigene Escape- oder Faltlogik. icalendar dient zusätzlich als Vorprüfung (Objekt muss parsen, genau ein `VTODO`, keine Wiederholung) und als Nachprüfung (das geänderte Objekt parst und trägt die gewollten Werte), bevor der eine `PUT` mit `If-Match` rausgeht. Schreibschiene, `MOVE` und Kettenlogik gehören nach `clients/tasks.py` und `tools/tasks.py`, `caldav.py` bleibt unangetastet.

## Kernbefunde mit Folgen für die Planung

1. **Drei Gates kennen keine optionalen Werkzeuge.** `files_update` steht heute in keiner Audit-Erlaubnisliste und in keiner Klasse von `tool_classes.py`; die Gates prüfen nur die Standard-Registry (Schalter aus). Trägt Phase 33 Einträge für `tasks_complete`, `tasks_update`, `tasks_move` ein, wird `test_every_registered_tool_has_an_allowlist_entry` rot ("has an allowlist entry but is not registered", `tests/contract/test_audit_surface.py:57-61`), ebenso `freeze_findings` in `tool_classes.py` ("stale"). Die Gates brauchen einen Begriff "optionale Werkzeuge" und eine Messung mit eingeschaltetem Schalter (Subprozess, wie `test_files_update_registration_respects_feature_flag`). [VERIFIED: Code gelesen]
2. **Das Budget misst heute nur den Standardzustand.** `scripts/check_tool_budget.py` importiert `mcp` mit der Umgebung, wie sie ist; im CI ist kein Schalter gesetzt, also sind `files_update` und die drei neuen Werkzeuge nicht in den 18770 Bytes und auch nicht unter der Decke von 1400 Bytes je Werkzeug. Das Budget nach TMOD-05 muss mit allen Schaltern an gemessen werden, sonst prüft die Decke die drei Werkzeuge nie. [VERIFIED: Code gelesen, `.github/workflows/ci.yml:46`]
3. **`tasks_update` passt knapp unter 1400 Bytes, aber nur ohne `timezone`.** Ein Prototyp mit `task_id`, `etag`, `summary`, `description`, `due`, `start`, `priority`, `tags`, `parent` misst 1368 Bytes (Messweg wie das Gate, Titel-Diät angewandt); `tasks_complete` 596, `tasks_move` 564. Mit einem Parameter `timezone` reißt `tasks_update` die Decke. Die Tasks-App schreibt Zeiten ohnehin nur in UTC (A3), also schreibt `tasks_update` Zeiten in UTC mit `Z`, Daten bleiben Daten. [VERIFIED: Prototyp in dieser Recherche]
4. **Annotation "nicht destruktiv" widerspricht dem Wortlaut der MCP-Spezifikation.** `destructiveHint` false heißt dort "performs only additive updates"; `tasks_update` überschreibt Titel und Felder, `files_update` ist im selben Repo mit `destructive_hint=True` annotiert. TMOD-05 verlangt "ändernd, nicht destruktiv, idempotent". Das ist eine Owner-Frage vor dem Bau (Open Question 1). [CITED: modelcontextprotocol.io/specification/2025-06-18/schema, ToolAnnotations]
5. **412 bei `MOVE` ist mehrdeutig.** Veraltete ETag und belegter Zielname geben beide 412 (M4.2, M4.5). Ein REPORT auf die Zielliste vor dem ersten `MOVE` prüft Namen und UIDs aller zu verschiebenden Objekte (D-33-11 sinngemäß), dann ist ein späteres 412 fast immer "geändert". [VERIFIED: docs/spike-tasks.md 4.1]
6. **Ohne ETag im `PUT`-Antwortkopf hat der Server den Text verändert.** sabre setzt `$etag = null`, wenn ein Plugin den Inhalt beim Schreiben verändert hat. Das Werkzeug meldet dann keine neue ETag und bittet um erneutes Lesen. [VERIFIED: sabre-io/dav master `lib/DAV/Server.php::updateFile`]
7. **Unteraufgaben findet ein REPORT der ganzen Liste am billigsten.** Der vorhandene `calendar-query` fragt `getetag` und `calendar-data` schon ab (`_todo_query_root`), `query_todos` wirft die ETag nur weg. Ein REPORT im Modus alle kostet bei 2000 Aufgaben im Median 148 bis 186 ms und rund 1,5 MB (MESS-04) und liefert für jede Unteraufgabe Inhalt und frische ETag im selben Aufruf; rekursive `text-match`-REPORTs bräuchten bis zu einen Aufruf je Ebene und Knoten. [VERIFIED: Code gelesen, docs/spike-tasks.md 6]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schalter `NC_MCP_TASKS_UPDATE` lesen | API / Backend (`config.py`, `server/reg_tasks.py`) | ExApp-Admin-Formular (`exapp/admin_settings.py`, `config_values.py`, `entry_exapp.py`) | Registrierung entscheidet einmal beim Import, wie bei `files_update` |
| Rechte, Konflikte, Komponenten-Set | Database / Storage (Nextcloud CalDAV, sabre) | API / Backend (Discovery-Vorprüfung) | der Server entscheidet mit 412/404/403; die Vorprüfung gibt nur bessere Meldungen und verhindert halbe Ketten |
| Text der Aufgabe ändern | API / Backend (neues Modul für den Zeilen-Editor) | - | reine Funktion, unit-testbar ohne Netz |
| Schreibschiene `PUT`/`MOVE` | API / Backend (`nextcloud/clients/tasks.py`) | - | genau eine Aufrufstelle je Methode, vom Gate gezählt |
| Kettenlogik, Prüfungen, Antwortform | API / Backend (`tools/tasks.py`) | - | wie `create_task`: alle Prüfungen vor dem ersten Schreibzugriff |
| Audit je Aufruf | API / Backend (`@graceful`, `audit/allowlist.py`) | - | ein Eintrag je Werkzeugaufruf, nur Parameternamen |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| icalendar | 7.3.0 (uv.lock, Spezifikation `>=7.2,<8`) | Vorprüfung, Nachprüfung, Erzeugen neuer Zeilen | schon im Projekt; `Todo.add` und `to_ical(sorted=False)` erzeugen Escape, Faltung und `VALUE=DATE` korrekt [VERIFIED: uv.lock, lokale Läufe] |
| httpx | wie im Lock | `GET`, `PUT`, `REQUEST("MOVE")`, `REPORT` | ein Client für alles, MockTransport für Tests [VERIFIED: Code] |
| lxml | wie im Lock | REPORT-Körper | vorhandene Bauer in `clients/tasks.py` [VERIFIED: Code] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `icalendar.parser.Contentline` | 7.3.0 | Parameter einer zu ersetzenden Zeile lesen (`Contentline(line).parts()[1]`) | nur beim Ersetzen von `SUMMARY`/`DESCRIPTION`, um Parameter wie `LANGUAGE` zu behalten [VERIFIED: lokal] |

Nicht verwenden: `icalendar.parser.foldline` (meldet `DeprecationWarning`, "will be removed in icalendar 8") und `Contentline.from_parts` mit schon kodiertem Wert (escapt doppelt). Beides lokal beobachtet. [VERIFIED: lokale Läufe mit `-W error`]

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Editor auf logischen Zeilen | icalendar-Objektmodell (`from_ical`, Komponente ändern, `to_ical(sorted=False)`) | einfacher, Inhalt bleibt erhalten; aber `VTIMEZONE`-RRULE umgeordnet, Neufaltung, `\N` zu `\n`, Namen groß: der Textbeweis für TMOD-02 braucht dann eine Normalisierung, und jede Kanonisierung einer künftigen icalendar-Fassung wird zu einer stillen Änderung fremder Zeilen |
| Ein REPORT der ganzen Liste | `text-match` auf `RELATED-TO` je Knoten | weniger Bytes je Aufruf, aber ein Aufruf je Ebene und Knoten; Kosten bei 2000 Aufgaben ungemessen (spike 11) |
| Zeiten in UTC schreiben | Parameter `timezone` mit `VTIMEZONE`-Pflege | Zone bliebe erhalten, aber `tasks_update` reißt 1400 Bytes und der Editor müsste `VTIMEZONE` einfügen und verwaiste Zonen bewerten |

**Installation:** keine. 

## Package Legitimacy Audit

Keine neue Abhängigkeit. slopcheck nicht ausgeführt, weil nichts installiert wird.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| keins | - | - | - | - | - | - |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
MCP-Client
   | tasks_complete(task_id, etag, completed) / tasks_update(task_id, etag, felder) / tasks_move(task_id, etag, list)
   v
@graceful (Audit: ein Eintrag, nur Parameternamen)   [nur registriert, wenn NC_MCP_TASKS_UPDATE an]
   v
tools/tasks.py: Eingaben prüfen (vor jeder Anfrage) --Fehler--> Ablehnung, kein Request
   v
Discovery PROPFIND --> Liste per Schlüssel; Deck-Präfix vorher abgelehnt; writable? --nein--> Ablehnung
   v
GET Objekt (Text + ETag) --> ETag == gegebene? --nein--> Ablehnung "neu lesen"
   v
Vorprüfung icalendar: parst? genau ein VTODO? recurring? --nein--> Ablehnung
   v
[complete=true oder move oder parent-Änderung] REPORT ganze Liste (getetag+calendar-data)
   |    --> Baum aus RELATED-TO (PARENT/ohne RELTYPE), Zyklenschutz, Nachfahren in Tiefe-zuerst-Nachordnung
   |    --> Vorprüfung: >50? recurring darunter? (move: REPORT Zielliste, Name/UID frei?) --ja--> Ablehnung
   v
Zielzustand schon erreicht / kein Unterschied? --ja--> Erfolg ohne PUT/MOVE
   v
für jeden Nachfahren, dann die genannte Aufgabe, streng nacheinander:
   Zeilen-Editor (nur genannte Felder + LAST-MODIFIED/DTSTAMP) -> Nachprüfung icalendar
   -> clients/tasks.py: PUT If-Match:<etag> | MOVE Destination/Overwrite:F/If-Match:<etag>
   -> 204/201 weiter | 412/404/403/5xx/Timeout: Stopp, Antwort nennt geänderte Nachfahren
   v
Antwort: id, Ergebnis, neue ETag (falls im Kopf), geänderte/übersprungene Nachfahren
```

### Recommended Project Structure (nur Änderungen)

```
src/mcp_connector/
├── config.py                      # ENV_TASKS_UPDATE, tasks_update_enabled()
├── entry_exapp.py                 # Wert aus Admin-Settings vor build_exapp_app in os.environ
├── exapp/config_values.py         # CONFIG_KEYS, KEY_TO_ENV, SWITCH_KEYS + "tasks_update"
├── exapp/admin_settings.py        # Checkbox, default False (Entpacken von CONFIG_KEYS!)
├── exapp/ui/strings.py            # ADMIN_FIELD_TASKS_UPDATE_LABEL/DESCRIPTION
├── nextcloud/clients/tasks.py     # TodoObject.etag, get_todo mit ETag, put_existing_todo, move_todo, Wording
├── tools/ics_edit.py              # (neu) Editor auf logischen Zeilen, reine Funktionen
├── tools/tasks.py                 # read_task + etag, complete_task, update_task, move_task, Kettenlogik
├── server/__init__.py             # neue Annotationsklasse, Satz der Server-Instruktion bei Schalter an
└── server/reg_tasks.py            # if config.tasks_update_enabled(): drei Werkzeuge
appinfo/info.xml                   # <variable> NC_MCP_TASKS_UPDATE
scripts/check_tool_budget.py       # Messung mit allen Schaltern an, Verankerung
tests/contract/...                 # optionale Werkzeuge in Surface, Klassen, Audit, Bundles, Destruktiv-Gate
tests/unit/test_ics_edit.py        # Rundlauf-Beweise (neu)
tests/unit/test_tasks_modify.py    # Werkzeuglogik mit MockTransport (neu)
```

`caldav.py` bleibt unberührt: der Modul-Docstring von `clients/tasks.py` sagt schon, dass das Aufgabenmodul eigene Anfragen hat und nur URL-Bauer und den create-only-Schreiber von `caldav.py` nutzt; so bleibt TASK-01 ohne Diff-Beweis an den Kalendertests erfüllt.

### Pattern 1: Schreibschiene mit genau einer Aufrufstelle je Methode

**What:** zwei Funktionen in `clients/tasks.py`, jede mit einem einzigen httpx-Aufruf, Kopf als Literal-Dict, damit das AST-Gate sie lesen kann.
**When to use:** jeder ändernde Zugriff, auch jedes Kind einer Kette.

```python
# Skizze, nicht Produktcode. Muster: dav.update_file und dav.py MOVE der Chunk-Montage.
async def put_existing_todo(client, creds, task_list, object_name, ics_bytes, etag):
    response = await client.put(
        caldav.object_url(creds, task_list.uri, object_name),
        content=ics_bytes,
        headers={"If-Match": etag, "Content-Type": "text/calendar; charset=utf-8"},
        auth=creds.auth(),
    )
    _check_modify(response, ...)          # 204/200 ok, 412 Konflikt, 404 "nicht gefunden oder kein Schreibrecht"
    return response.headers.get("etag", "")  # leer heißt: Server hat den Text verändert (sabre)

async def move_todo(client, creds, source, target, object_name, etag):
    response = await client.request(
        "MOVE",
        caldav.object_url(creds, source.uri, object_name),
        headers={
            "Destination": caldav.object_url(creds, target.uri, object_name),
            "Overwrite": "F",
            "If-Match": etag,
        },
        auth=creds.auth(),
    )
    # nur 201 ist ein Umzug auf einen freien Namen; 204 hieße "überschrieben" und ist ein lauter Fehler
```

`etag` kommt immer durch `dav.normalize_etag` (eine starke ETag, kein `*`, kein `W/`, keine Liste), bevor eine Anfrage rausgeht. [VERIFIED: `src/mcp_connector/nextcloud/clients/dav.py:943-962`]

### Pattern 2: Editor auf logischen Zeilen (TMOD-02)

**What:** Text in logische Zeilen zerlegen und dabei den physischen Originaltext jeder Zeile (samt Faltung) behalten; Komponentenstapel über `BEGIN:`/`END:` (Groß/Klein egal) führen; nur Zeilen mit Stapel genau `[VCALENDAR, VTODO]` sind Kandidaten.
**Regeln, gemessen am Prototyp dieser Recherche:**
- Ersetzen: an der Stelle der ersten Zeile des Namens; weitere Zeilen desselben Namens fallen weg (`CATEGORIES`, Eltern-`RELATED-TO`). Einwertige Felder (`SUMMARY`, `DESCRIPTION`, `DUE`, `DTSTART`, `PRIORITY`, `STATUS`, `COMPLETED`, `PERCENT-COMPLETE`) mehrfach vorhanden: ablehnen statt raten.
- `RELATED-TO`: nur Zeilen ohne `RELTYPE` oder mit `RELTYPE=PARENT` gelten als Elternbezug (dieselbe Regel wie `_parents`, `tools/tasks.py:224-233`); `CHILD`/`SIBLING` bleiben.
- Einfügen: vor der ersten Unterkomponente des `VTODO` (`BEGIN:VALARM`) oder vor `END:VTODO`; RFC 5545 verlangt Eigenschaften vor Alarmen. Das icalendar-Objektmodell tut dasselbe (lokal beobachtet). [VERIFIED: lokal; CITED: RFC 5545 3.6.2 `todoc`]
- Neue Zeilen erzeugt icalendar: Wegwerf-`Todo`, `add(name, value, parameters=...)`, `to_ical(sorted=False)`, die Zeilen zwischen `BEGIN:VTODO` und `END:VTODO` übernehmen. Lief mit `-W error` ohne Warnung; Umlaut, Komma, Semikolon und Zeilenumbruch kamen korrekt escapt und auf 75 Oktette gefaltet heraus.
- Zeilenende: das des Originals übernehmen (Fixtures CRLF, `.gitattributes` schützt sie); neue Zeilen im selben Zeilenende.
- Nachprüfung vor dem `PUT`: das Ergebnis muss mit icalendar parsen, genau ein `VTODO` mit derselben UID haben, und `_read_todo` muss die gewollten Werte zeigen; sonst Ablehnung, nie ein kaputtes Objekt schreiben.

```python
# Skizze (gemessen in scratchpad/p33/rt3.py dieser Recherche)
def new_lines(name, value, params=None) -> list[str]:
    todo = Todo()
    todo.add(name, value, parameters=params)
    return todo.to_ical(sorted=False).decode("utf-8").split("\r\n")[1:-2]
# new_lines("DUE", date(2026, 11, 20))       -> ['DUE;VALUE=DATE:20261120']
# new_lines("CATEGORIES", ["a,b", "c"])      -> ['CATEGORIES:a\\,b,c']
# new_lines("COMPLETED", datetime(..., UTC)) -> ['COMPLETED:20261113T120000Z']
```

### Pattern 3: Ketten über Nachfahren (D-33-09 bis D-33-11)

1. Ein REPORT der Liste ohne Vorfilter (`build_todo_query(None)`), `TodoObject` um `etag` erweitern (`getetag` steht schon im Körper). Unter einem Zeitbudget nach der Hausregel (vorhanden: `PER_LIST_TIMEOUT = 2.0` für 2000 offene Aufgaben samt Discovery).
2. Kinderkarte `parent_uid -> [objekt]` aus `_parents`; exakter Vergleich der UID, nie "contains". Nachfahren der genannten UID mit besuchter Menge (fremde Daten können Zyklen haben, auch über die genannte Aufgabe selbst).
3. Reihenfolge: Tiefe zuerst, Nachordnung (Enkel vor Kind, Kind vor Eltern), Geschwister stabil nach Objektname. So ist jeder Elternknoten erst dran, wenn sein ganzer Teilbaum durch ist; beim Stopp bleibt die genannte Aufgabe sicher unverändert.
4. Vorprüfung vor dem ersten Schreiben: Zahl der Nachfahren > 50 ablehnen; ein Nachfahr mit `recurring` oder mehreren `VTODO` ablehnen; beim Verschieben zusätzlich ein REPORT der Zielliste: Objektname oder UID schon dort, ablehnen (409 `UidConflict` und 412 vorweggenommen). Schreibrecht: Nachfahren in derselben Liste haben dasselbe `writable` wie die Liste.
5. Schreiben streng nacheinander, nie parallel (auf SQLite gaben zwei gleichzeitige `PUT` desselben Kontos 500 "database is locked", spike 3.6). Nachfahren im Zielzustand ohne Aufruf überspringen und zählen.
6. Antwort bei Stopp: welches Objekt scheiterte, warum (412: "geändert, neu lesen"; 404: "nicht gefunden oder kein Schreibrecht"; 5xx: "Serverfehler"), Liste der schon geänderten Nachfahren als `task:`-Ids.

Nur die genannte Aufgabe trägt die ETag des Assistenten; die Nachfahren tragen die ETag aus dem REPORT desselben Aufrufs (D-33-09). Objekte, die der REPORT nicht parsen konnte, können Nachfahren sein, ohne dass der Connector es weiß; die Antwort nennt ihre Zahl (`skipped`), wie `tasks_search`.

### Pattern 4: Prüfungen auf dem zusammengeführten Stand (TMOD-04)

Die Prüfungen von `create_task` (`_parse_task_time`, `_check_times`, `_check_priority`, `_clean_tags`, `_parse_parent`, `tools/tasks.py:828-917`) wiederverwenden, aber auf den Stand **nach** der Änderung anwenden: wer nur `due` setzt, muss gegen das vorhandene `DTSTART` geprüft werden (Werttyp gleich, Start vor Fälligkeit). Ein vorhandener schwebender oder zonierter Wert lässt sich mit einem neuen UTC-Wert nicht ohne Annahme vergleichen (`TypeError` bei naiv gegen aware): ablehnen mit dem Hinweis, beide zu setzen. `DURATION` neben `DUE`/`DTSTART`: Änderung von `due` oder `start` ablehnen (RFC 5545: `DUE` und `DURATION` schließen sich aus, `DURATION` verlangt `DTSTART`). Kein Unterschied zum gelesenen Stand (gleicher Text, gleiche Tags in gleicher Reihenfolge, gleiche Zeit als Zeitpunkt und gleiche Werttyp-Form): Erfolg ohne `PUT`.

### Pattern 5: Schalter-Kette nach `NC_MCP_FILES_UPDATE` (Fundstellen auf HEAD 63221a9)

| Station | Fundstelle heute | Neu |
|---------|------------------|-----|
| Konstante, Lesefunktion | `config.py:51`, `config.py:716-737` | `ENV_TASKS_UPDATE = "NC_MCP_TASKS_UPDATE"`, `tasks_update_enabled()` gleich gebaut (leer/unbekannt heißt aus, Warnung) |
| Übernahme aus Admin-Settings | `entry_exapp.py:663-670` | zweiter Block vor `build_exapp_app` |
| Schlüssel | `exapp/config_values.py:126,139,148` | `"tasks_update"` in `CONFIG_KEYS`, `KEY_TO_ENV`, `SWITCH_KEYS` |
| Formular | `exapp/admin_settings.py:132,212-217` | Tupel-Entpacken von `CONFIG_KEYS` erweitern, Checkbox `default: False` |
| Texte | `exapp/ui/strings.py:800-814`, `__all__` 47-48 | `ADMIN_FIELD_TASKS_UPDATE_LABEL`, `..._DESCRIPTION` |
| Registrierung | `server/reg_files.py:264` | `if config.tasks_update_enabled():` in `reg_tasks.py` |
| Server-Instruktion | `server/__init__.py:62-71` | Satz nur bei Schalter an (Phase 34 darf den Rest der Zusage präzisieren) |
| Store-Manifest | `appinfo/info.xml:565-569` | `<variable>` `NC_MCP_TASKS_UPDATE` |
| Tests | 7 Dateien laut spike 7.3 (`test_config.py`, `test_exapp_config_values.py`, `test_exapp_entry.py`, `test_exapp_env_setup.py`, `test_exapp_files_update_switch.py`, `test_exapp_lifecycle.py`, `test_tool_surface.py`) plus `test_tool_bundles.py:135-147` | je ein Gegenstück |

Die Formulartexte sind heute nur englisch (`strings.py`); "DE/EN/FR" aus D-33-01 heißt für das Formular englisch und für READMEs und Changelogs drei Sprachen. [VERIFIED: Suche nach dem Label findet es nur in `strings.py` und `CHANGELOG.md`]

### Pattern 6: `tasks_move`

- Ziel ist Pflichtparameter `list` (Name oder Schlüssel wie `tasks_search`), aufgelöst mit `_resolve_list` gegen die Discovery; `writable` für Quelle und Ziel; Ziel gleich Quelle: Erfolg ohne `MOVE`.
- Deck ist in der Discovery nie eine Aufgabenliste (`_is_task_list`), ein Schlüssel mit `app-generated--` wird wie in `read_task` vor jeder Anfrage als unbekannt abgelehnt.
- `Destination` aus `caldav.object_url(creds, target.uri, object_name)`, also aus `creds.base_url`; der Server wertet nur den Pfad aus (M4.1). Gleicher Objektname.
- 201 ist Erfolg, 204 hieße "überschrieben" (darf mit `Overwrite: F` nicht vorkommen) und ist ein lauter Fehler, 409 `UidConflict`, 412 nach der Vorprüfung "geändert oder Ziel inzwischen belegt, neu lesen", 404 auf ein Ziel ohne Schreibrecht, 403 Deck.
- ETag bleibt beim Umzug gleich (M4.1); die Antwort kann sie und die neue Id `task:<zielschlüssel>:<objekt>` nennen.

### Anti-Patterns to Avoid
- **`to_ical()` ohne `sorted=False`:** sortiert jede Eigenschaft alphabetisch um (lokal an allen acht Fixtures gemessen).
- **Regex auf den Rohtext ohne Komponentenstapel:** `DESCRIPTION` im `VALARM`, `DTSTART` und `RRULE` im `VTIMEZONE` würden mitgetroffen.
- **`asyncio.timeout` um einen `PUT` oder `MOVE`:** ein abgebrochener Schreibaufruf kann trotzdem angekommen sein; die Antwort muss dann "vielleicht geschrieben, neu lesen" sagen, nie "nicht geschrieben".
- **404 nach erfolgreichem Lesen als "gelöscht" melden:** eine nur lesbare Freigabe antwortet 404 (spike 3.3).
- **Zweiter Versuch nach 412 oder 5xx:** verboten (D-33-03, `_check` "No retry, ever").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Escapen und Falten neuer Zeilen | eigene Escape-Tabelle, eigenes Falten | Wegwerf-`icalendar.Todo` plus `to_ical(sorted=False)` | Komma, Semikolon, Umbruch, Mehrbyte-Grenzen; `foldline` ist veraltet |
| Parameter einer Zeile lesen | Split an `;` und `:` | `icalendar.parser.Contentline(line).parts()` | gequotete Werte mit `:` (lokal geprüft: `X-P="q:v"`) |
| ETag prüfen | eigener Vergleich | `dav.normalize_etag` | `*`, `W/`, Listen, leere Werte schon abgefangen |
| Liste auflösen | neue Suche | `_resolve_list`, `discover_task_lists` | Freigabe-Schlüssel ohne Besitzer, Mehrdeutigkeit |
| Zeitprüfungen | neue Parser | `_parse_task_time`, `_check_times`, `_check_priority`, `_clean_tags` | dieselben Prüfungen wie `tasks_create` (TMOD-04) |
| Wiederholung erkennen | eigene RRULE-Logik | `_fields(...)["recurring"]` plus "genau ein VTODO" | A15 lehnt ab, keine Berechnung |

**Key insight:** Unfalten (Zeilenumbruch gefolgt von Leerzeichen oder Tab) und das Führen des Komponentenstapels sind die einzigen Stücke eigener Logik; alles, was Werte kodiert, kommt aus icalendar.

## icalendar 7.3.0 gemessen (Rundlauf und Bearbeitung)

Läufe dieser Recherche mit `uv run --no-sync python -I`, Skripte unter dem Scratchpad (`p33/rt1.py`, `rt2.py`, `rt3.py`, `size.py`), nichts unter `src/`.

| Probe | Ergebnis | Folge |
|-------|----------|-------|
| 8 Fixtures, `to_ical()` | alle ungleich, gleiche Länge: alphabetisch sortiert | nie ohne `sorted=False` |
| 8 Fixtures, `to_ical(sorted=False)` | alle byte-gleich | Objektmodell trägt für die Form der Tasks-App |
| Probeobjekt des Spikes (VTIMEZONE, VALARM, 3 X-Eigenschaften, Parameter an SUMMARY, gefaltete DESCRIPTION, zwei CATEGORIES-Zeilen, RELATED-TO mit SIBLING) | Inhalt erhalten; `RRULE` im VTIMEZONE umgeordnet (`BYDAY` vor `BYMONTH`), DESCRIPTION neu gefaltet | textuell nicht byte-gleich |
| Faltung auf 40 Zeichen | zu einer Zeile zusammengezogen, dann auf 75 Oktette | Faltung fremder Clients geht verloren |
| `DESCRIPTION:zeile1\Nzeile2` | wird `\n` | gleichbedeutend, textuell anders |
| `uid:o`, `summary:klein` | wird `UID:`, `SUMMARY:` | gleichbedeutend, textuell anders |
| `TZID=/mozilla.org/20050126_1/Europe/Berlin`, `TZID=W. Europe Standard Time` | Zeilen unverändert, Warnung `GloballyUniqueTZIDGuessed` | Warnung im Log möglich, Wert bleibt |
| unbekannte Komponente `X-THING` in VTODO | erhalten | gut |
| `X-ALT-DESC;FMTTYPE=text/html`, `X-EMPTY:`, `EXDATE` mit zwei Werten, `ORGANIZER;CN="Doe, Jane"`, `GEO`, `ATTACH`, `SEQUENCE` | erhalten (nur `ATTENDEE`-Zeile neu gefaltet) | gut |
| `DUE:notadate` | `ValueError` beim Parsen des ganzen Objekts | Werkzeug lehnt ab; `_read_todo` liefert heute schon `None` |
| Objektmodell: `todo["SUMMARY"] = vText(..., params=alt.params)`, `pop("DUE")`, `add("STATUS")` | Position von SUMMARY bleibt, Parameter bleiben, neue Felder vor `BEGIN:VALARM` | Alternative wäre lauffähig |
| Editor-Prototyp auf logischen Zeilen | unberührte Zeilen byte-gleich (auch VTIMEZONE-RRULE und gefaltete Zeilen), VALARM-DESCRIPTION unberührt, Ergebnis parst | empfohlener Weg |

## Antworten auf die Fragen des Auftrags

### F1: Objektmodell oder Zeilen-Edit?
Zeilen-Edit auf logischen Zeilen, Werte von icalendar erzeugt (Pattern 2). Begründung: (a) der strenge Textbeweis aus TMOD-02 gilt ohne Normalisierung, (b) eine spätere icalendar-Fassung kann fremde Zeilen nicht still kanonisieren, (c) die Hausregel "Gegenprobe nie mit dem Muster der Umsetzung" lässt sich einhalten: der Beweis läuft über Substring-Vergleich der physischen Originalzeilen und über einen icalendar-Semantikvergleich, beides nicht der Weg des Editors.

### F2: Wie beweist man "Menge der Eigenschaften unterscheidet sich genau um die genannten Felder"?
Zwei voneinander unabhängige Beweise je Fixture und Änderungsart:
1. **Byte-Beweis ohne Unfalten:** jede physische Zeile (samt Faltung) jeder unberührten Eigenschaft des Originals steht wörtlich im Ergebnis, in derselben Reihenfolge; alle Zeilen außerhalb des `VTODO` sind byte-gleich.
2. **Semantik-Beweis mit icalendar:** beide Texte parsen, je Komponentenpfad die Multimenge `(NAME, Parameter, to_ical(Wert))` bilden; Differenz ist genau `{genannte Felder} ∪ {LAST-MODIFIED, DTSTAMP}` (beim Abhaken `STATUS`, `PERCENT-COMPLETE`, `COMPLETED`).
Positivkontrolle: ein absichtlich falscher Editor, der eine `X-`Zeile fallen lässt, muss in beiden Beweisen genau diese Zeile melden (Muster aus spike 3.2, `KONTROLLE eigenschaften`). Objekte: die acht Fixtures plus von Hand gebaute reiche Objekte (Probeobjekt aus `scripts/tasks_spike.py:604-650`, eine LF-Variante, Faltung bei 40, Kleinschreibung, mehrere `CATEGORIES`, `RELATED-TO;RELTYPE=SIBLING`, unbekannte Komponente); die Fixtures enthalten selbst kein `VALARM`, kein `VTIMEZONE` und keine `X-`Eigenschaft.

### F3: Woher kommt die ETag in `tasks_read`?
`get_todo` liest heute nur den Körper; der `ETag`-Kopf des `GET` ist im Spike für `If-Match` belegt (`get_object` in `scripts/tasks_spike.py:2471-2474`, M3.1). `get_todo` gibt künftig Körper und ETag zurück; `read_task` legt `etag` in die Antwort. `fetch` übernimmt nur benannte Felder (`tools/chatgpt.py:555-567`), dort ändert sich nichts. Form: so wie der Server sie sendet, mit Anführungszeichen, gleich wie bei den Dateiwerkzeugen; `normalize_etag` nimmt auch die nackte Form an.

### F4: Schema für "nicht genannt" gegen "entfernen" (D-33-07)
Empfehlung: `null` oder fehlend heißt unverändert, leerer Wert heißt entfernen: `description=""`, `due=""`, `start=""`, `parent=""`, `tags=[]`, `priority=0` (Zeile weg). `summary=""` wird abgelehnt (Titel nicht leerbar). Grund: Modelle senden für nicht gemeinte Parameter oft `null`; ein leerer Wert ist dagegen eine ausdrückliche Handlung. Der Prototyp mit diesen Beschreibungen misst 1368 Bytes. Ob die Tasks-App beim Entfernen die Zeile löscht oder leer schreibt, entscheidet die Messung M-2; die Schemaform hängt davon nicht ab.

### F5: Was heißt "im Zielzustand" bei `tasks_complete`?
- `completed=true`: Status `completed` nach `_status` (`STATUS:COMPLETED` oder `COMPLETED` vorhanden) heißt null `PUT`, auch wenn darunter offene Unteraufgaben stehen (Erfolgskriterium 1 verlangt null `PUT`).
- `completed=false`: Status `open` oder `in_progress` heißt null `PUT`.
- `cancelled`: siehe Open Question 3.
Felder: `STATUS:COMPLETED`, `PERCENT-COMPLETE:100`, `COMPLETED`, `LAST-MODIFIED`, `DTSTAMP` mit demselben UTC-Zeitpunkt (Sekunden, `Z`); beim Wiederöffnen `STATUS:NEEDS-ACTION`, `COMPLETED` und `PERCENT-COMPLETE` entfernen. `SEQUENCE` nie anfassen. Fehlen `LAST-MODIFIED` oder `DTSTAMP`, werden sie eingefügt.

### F6: Gate für den überschreibenden `PUT`
`EXPECTED_PUT_CALLS` 6 auf 7 (`tests/contract/test_no_destructive_calls.py:480`), Kommentar mit Grund; `_usable_precondition` akzeptiert `{"If-Match": etag}` mit Variable schon heute (`_HONEST_PUTS`). Dazu ein Test nach dem Muster `test_file_updates_keep_create_and_compare_and_swap_puts_distinct` (`:450-466`): `caldav.put_new_object` bleibt `If-None-Match: *`, die neue Funktion in `clients/tasks.py` trägt `If-Match` mit der Variable `etag`. Kein Eintrag in `UNCONDITIONAL_PUTS`.

### F7: Gate für `MOVE`
`FORBIDDEN["MOVE"]` trifft jeden Code mit dem Teilstring `MOVE` (`:420-425`), auch Bezeichner wie `REMOVED`. Die heutige Ausnahme gilt je Datei und exaktem Zeilentext `"MOVE",` und würde eine zweite gleiche Zeile in derselben Datei auch durchlassen. Empfehlung: zweite benannte Ausnahme `TASK_MOVE = "nextcloud/clients/tasks.py"` plus ein neuer AST-Test: genau ein `.request("MOVE", ...)` in diesem Modul, in der Funktion `move_todo`, mit Literal-Kopf `"Overwrite": "F"` und `"If-Match"` auf eine Nicht-Konstante; Gesamtzahl der `MOVE`-Aufrufe im Code 2. Gegenproben: gepflanztes `MOVE` ohne `Overwrite`, mit `"T"`, mit `If-Match: "*"`, zweites `MOVE` in `tasks.py`, `MOVE` in einer anderen Datei. Die Kommentare `:139-142` ("user-facing move and rename tools remain forbidden") und der Modul-Docstring (`:3-6`, "never delete, overwrite") sind nachzuziehen (Inventar A17).

### F8: Annotationen und Klassen
Neue Klasse in `server/__init__.py` (Arbeitsname `MODIFY_EXISTING`), eigene Menge `MODIFY_TOOLS` in `test_tool_surface.py` mit eigenem Zweig in `_check_annotations` (`:757-789`) und Gegenprobe "gepflanzte Klasse wird abgelehnt" wie `:822-837`. Werte siehe Open Question 1. Werte gleich `CREATE_IDEMPOTENT` (falls der Owner bei "nicht destruktiv" bleibt) sind kein Widerspruch, aber die Mengen bleiben getrennt, weil die Fehlermeldungen andere Versprechen prüfen. Rechtetabelle der READMEs: neue Stufe (Vorschlag `modify`) in `test_the_readme_permission_table_matches_the_live_registry` (`:877-905`), `optional_tools` um die drei erweitern.

### F9: Optionale Werkzeuge in Audit, Klassen, Kanarie, Budget
- Audit: `PARAM_ALLOWLIST` bekommt die drei (z. B. `tasks_complete: {completed, etag, task_id}`, `tasks_update: {due, etag, parent, priority, start, tags, task_id}`, `tasks_move: {etag, list, task_id}`; `summary` und `description` stehen auf `FORBIDDEN_PARAMS`). Die beiden Mengen-Tests in `test_audit_surface.py` messen dann die Oberfläche mit Schalter an (Subprozess) oder tragen eine Menge `OPTIONAL_TOOLS`. Dasselbe für `files_update`, das heute ohne Eintrag ist (Audit zeichnet dafür keine Parameternamen auf).
- Klassen: die drei gehören zu `UNAFFECTED` (Antwort nennt keine Datei), `freeze_findings` und `test_the_three_classes_add_up_to_the_frozen_surface` brauchen dieselbe Behandlung optionaler Werkzeuge.
- Kanarie: Lauf mit Schalter an, Registry dann 30 statt 27 (`test_canary.py:16` "n == 27"); echter Aufruf der drei auf der Aufgabe der Welt, die Deck-Marke darf in keiner Antwort stehen (`TASK_TOOLS` erweitern).
- Abnahmeskript: Kette `tasks_create` → `tasks_read` (ETag) → `tasks_update` → `tasks_complete` → `tasks_move`, alte ETag muss 412-Ablehnung bringen.
- Budget: Messung mit `NC_MCP_FILES_UPDATE=on` und `NC_MCP_TASKS_UPDATE=on` als maßgeblicher Endstand (Umgebung vor dem Import von `mcp_connector.server` setzen oder Subprozess), dazu die Standardmessung zur Kontrolle; neu verankern nach Hausregel (Messung plus 15 Prozent, auf 500 aufrunden). Grobe Erwartung aus dem Prototyp: 18770 + 2676 + `tasks_read`-Mehrbytes + `files_update`, also um 21500 bis 22000, Budget dann 25000.

### F10: Kosten und Messung der Obergrenze 50 (D-33-10)
Ungemessen sind die Kosten einer Kette. Gemessen: REPORT 2000 Aufgaben Modus alle 148/186 ms Median (MESS-04), ein `PUT` je Objekt ohne Wert. Messung M-3 unten. Ableitung nach Hausregel aus `PER_LIST_TIMEOUT` (`max(1, ceil(2 * max))`) für die Gesamtlaufzeit der Kette; liegt die gemessene Laufzeit von 50 Objekten deutlich über einem für MCP-Clients üblichen Aufruf (Zielwert vorab im Plan festlegen), Wert senken und dem Owner nennen.

## Common Pitfalls

### Pitfall 1: Teilstring-Nadeln des Destruktiv-Gates
**What goes wrong:** ein Bezeichner `_REMOVED_FIELDS` oder ein Text `"MOVED"` macht das Gate rot; ebenso `DELETE`, `COPY`, `PROPPATCH` und Pfadnadeln wie `/read`, `/share`.
**How to avoid:** Bezeichner und Texte ohne diese Großbuchstaben-Teilstrings (z. B. `dropped`, `relocated`); vor dem Commit `test_the_production_code_contains_no_destructive_request` laufen lassen.

### Pitfall 2: 412 ohne Unterscheidung
**What goes wrong:** beim `MOVE` heißt 412 "ETag veraltet" oder "Zielname belegt".
**How to avoid:** Zielliste vorab per REPORT prüfen (Pattern 6); die Meldung nach 412 nennt beide Möglichkeiten und verlangt neues Lesen.

### Pitfall 3: Prüfung nur der Eingaben statt des Endstands
**What goes wrong:** `due` als Datum neben vorhandenem `DTSTART` mit Uhrzeit wird geschrieben.
**How to avoid:** Pattern 4.

### Pitfall 4: Timeout um Schreibaufrufe
**What goes wrong:** `asyncio.timeout` bricht einen angekommenen `PUT` ab, das Werkzeug meldet "nicht geschrieben", das Modell wiederholt.
**How to avoid:** Zeitbudget nur um Lesewege (REPORT, GET); bei `httpx.TimeoutException` auf einem Schreibaufruf "Ausgang unbekannt, mit tasks_read neu lesen".

### Pitfall 5: Optionale Werkzeuge außerhalb der Gates
**What goes wrong:** Allowlist-Eintrag für ein nicht registriertes Werkzeug macht den Mengen-Test rot; ohne Eintrag prüft niemand die drei.
**How to avoid:** F9; jeder Gate-Test, der eine Registry liest, braucht eine Variante mit Schalter an.

### Pitfall 6: Budget ohne die neuen Werkzeuge
**What goes wrong:** CI misst 27 Werkzeuge, `tasks_update` liegt unbemerkt über 1400.
**How to avoid:** F9, Budget mit allen Schaltern an.

### Pitfall 7: SQLite-Sperre bei parallelen Schreibzugriffen
**What goes wrong:** `asyncio.gather` über die Kinder gibt 500.
**How to avoid:** streng nacheinander; 5xx ist Stopp, nie Erfolg (spike 3.6).

### Pitfall 8: Zyklen und fremde Formen in `RELATED-TO`
**What goes wrong:** Endlosschleife oder falsche Kinder durch "contains"-Treffer, `RELTYPE=CHILD` als Eltern gedeutet.
**How to avoid:** exakter UID-Vergleich, besuchte Menge, nur `PARENT` oder ohne `RELTYPE`.

### Pitfall 9: `X-ALT-DESC` und `ALTREP` nach einer Beschreibungsänderung
**What goes wrong:** ein Client mit HTML-Beschreibung zeigt nach der Änderung weiter den alten Text.
**How to avoid:** Open Question 2; mindestens `ALTREP` am ersetzten `DESCRIPTION` nicht übernehmen.

### Pitfall 10: Antwort ohne ETag nach erfolgreichem `PUT`
**What goes wrong:** das Modell nimmt eine leere ETag für den nächsten Aufruf.
**How to avoid:** Feld weglassen und Hinweis "mit tasks_read neu lesen" (sabre `updateFile` setzt `$etag = null` bei verändertem Text).

### Pitfall 11: Zählstellen in Doku und Tests
**What goes wrong:** "27 tools" in `test_tool_surface.py:573-578`, `test_canary.py:16`, READMEs; der Doku-Zähltest (`:908-932`) verlangt die aktuelle Zahl oder einen Verweis.
**How to avoid:** Standard-Registry bleibt 27 (Schalter aus); wo 30 genannt wird, steht "mit Schalter an" und der Verweis auf `tests/contract/test_tool_surface.py`.

### Pitfall 12: Zeilennummern des Inventars
**What goes wrong:** spike 7.1 nennt Zeilen von Commit `32b8df0`; Phase 32 hat verschoben (z. B. `CREATE_TOOLS` jetzt `:79` statt `:73`, `MUST_REFUSE` jetzt `test_canary.py:99` und mit `files_create_folder`, Annotationen in `server/__init__.py:77-101`).
**How to avoid:** Inventar im ersten Plan auf HEAD neu ziehen (Block `inventory` von `scripts/tasks_spike.py` oder dieselben zwei Muster), Phase-33-Zeilen abhaken.

## Code Examples

### Nachfahren in Nachordnung (Skizze)
```python
def descendants_post_order(root_uid, entries):
    children = {}
    for entry in entries:
        for parent in entry["parents"]:            # RELTYPE fehlt oder PARENT, exakt
            children.setdefault(parent, []).append(entry)
    order, seen = [], {root_uid}
    def walk(uid):
        for child in sorted(children.get(uid, []), key=lambda e: e["id"]):
            if child["uid"] in seen:
                continue                            # Zyklus oder doppelte Kante
            seen.add(child["uid"])
            walk(child["uid"])
            order.append(child)                     # Kind nach seinen Kindern
    walk(root_uid)
    return order
```
Rekursion bis Tiefe 50 ist unbedenklich, weil die Obergrenze vorher greift; wer sicher gehen will, schreibt sie iterativ.

### Abhaken als Zeilenänderung (Skizze)
```python
stamp = datetime.now(UTC).replace(microsecond=0)
changes = {
    "STATUS": "COMPLETED", "PERCENT-COMPLETE": 100, "COMPLETED": stamp,
    "LAST-MODIFIED": stamp, "DTSTAMP": stamp,
}
new_text = ics_edit.apply(old_text, set_=changes, drop=())
# wieder öffnen:
# ics_edit.apply(old_text, set_={"STATUS": "NEEDS-ACTION", "LAST-MODIFIED": stamp, "DTSTAMP": stamp},
#                drop=("COMPLETED", "PERCENT-COMPLETE"))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `icalendar.parser.foldline` | Faltung beim `to_ical` der Komponente | icalendar 7.x meldet Abkündigung für 8 | nicht direkt aufrufen |
| `to_ical()` Standard | `to_ical(sorted=False)` für ordnungstreue Ausgabe | Standard ist `sorted=True` in 7.3.0 | bei jeder Serialisierung bewusst wählen |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Thunderbird und andere Clients nutzen `ALTREP` an `DESCRIPTION` oder `X-ALT-DESC` für HTML-Beschreibungen und zeigen nach einer Textänderung sonst den alten Inhalt | Pitfall 9, Open Question 2 | gering bis mittel: veraltete Anzeige in einem Fremdclient |
| A2 | Die Tasks-App zeigt Unteraufgaben nur in derselben Liste; Nachfahren in anderen Listen ignoriert der Connector | Pattern 3 | gering: A2 aus dem Spike belegt "gleiche Liste" für die App-Objekte |
| A3 | Die Zeitreihe einer Kette von 50 `PUT` bleibt im Bereich weniger Sekunden | F10 | mittel: Obergrenze wäre zu senken (Messung M-3 entscheidet) |
| A4 | Die Wortlaute der MCP-Spezifikation 2026-07-28 zu `destructiveHint` gleichen denen von 2025-06-18 | Kernbefund 4 | gering: Frage an den Owner bleibt dieselbe |

## Open Questions (RESOLVED)

Alle fünf Fragen sind entschieden oder an eine Messung mit Owner-Frage gebunden (Stand 13.11.2026):

- Frage 1: RESOLVED durch D-33-12 (`destructive_hint=True`, `idempotent_hint=True`, TMOD-05 nachgezogen), umgesetzt in 33-02.
- Frage 2: RESOLVED durch D-33-13 (`X-ALT-DESC` und `ALTREP` werden bei geänderter Beschreibung entfernt, die Antwort sagt es), umgesetzt in 33-04 und 33-07.
- Frage 3: RESOLVED durch D-33-14. Die Empfehlung dieser Recherche ("`completed=false` auf `cancelled` als Zielzustand ohne PUT") ist überholt: direkt aufgerufen darf `tasks_complete` eine abgebrochene Aufgabe abhaken und wieder öffnen; abgebrochene Nachfahren bleiben beim Abhaken der Elternaufgabe unberührt. Gemessen in 33-01b, Owner-Frage bei Abweichung in 33-01c Task 4, umgesetzt in 33-06.
- Frage 4: RESOLVED als Messung M-1 in 33-01b mit Owner-Frage in 33-01c Task 4 (D-33-05, D-33-06).
- Frage 5: RESOLVED als Messung M-2 in 33-01b, Form als ENTSCHEID-Zeilen, Owner-Frage für Priorität und Tags in 33-01c Task 4 (D-33-07).

Ursprünglicher Wortlaut der Fragen:

1. **Annotation von `tasks_update` (und `tasks_complete`, `tasks_move`): "nicht destruktiv" laut TMOD-05 oder `destructiveHint=true` laut MCP-Wortlaut?**
   - What we know: Spezifikation: false heißt "only additive updates"; `files_update` ist im Repo `destructive_hint=True`. Abhaken ist umkehrbar, Ändern überschreibt alte Werte, Verschieben ändert den Ort.
   - Recommendation: Owner vor dem Planabschluss fragen; Empfehlung `destructive_hint=True` für `tasks_update`, für `tasks_complete` und `tasks_move` ebenfalls `True` aus Ehrlichkeit nach Wortlaut, `idempotent_hint=True` für alle drei (zweiter gleicher Aufruf ändert nichts mehr: veraltete ETag oder Zielzustand). Die eigene Klasse im Gate bleibt in beiden Fällen.
2. **`ALTREP` und `X-ALT-DESC` bei geänderter Beschreibung.**
   - Recommendation: `ALTREP` am ersetzten `DESCRIPTION` fallen lassen; `X-ALT-DESC` nach TMOD-02 behalten und in der Antwort nicht erwähnen, oder Owner fragen, ob es beim Ändern der Beschreibung mit entfernt wird. Messung mit Thunderbird gibt es nicht.
3. **Abgebrochene (`CANCELLED`) Aufgaben.**
   - What's unclear: was die Tasks-App mit einem abgebrochenen Kind beim Abhaken der Elternaufgabe tut, und was `completed=false` auf einer abgebrochenen Aufgabe heißen soll.
   - Recommendation: in Messung M-1 mitnehmen, falls die App den Status setzen lässt; bis dahin abgebrochene Nachfahren überspringen und zählen, `completed=false` auf `cancelled` als Zielzustand ohne `PUT` mit Status in der Antwort.
4. **Ergebnis von M-1 (D-33-06).** Öffnet die App beim Wiederöffnen die Kinder mit, fragt der Plan den Owner, bevor `tasks_complete` gebaut wird.
5. **Ergebnis von M-2 (D-33-07).** Schreibt die App beim Entfernen einen leeren Wert statt die Zeile zu löschen, übernimmt der Editor diese Form; das ändert nur `ics_edit`, nicht das Schema.

## Messungen, die die Pläne machen müssen (nicht in dieser Recherche gelaufen, kein Docker)

| Nr | Was | Wo | Gate oder Folge |
|----|-----|----|-----------------|
| M-1 | Tasks-App 0.18.1: Elternaufgabe mit zwei erledigten Kindern wieder öffnen; Stand vor und nach per DAV-GET, Zugriffsprotokoll des Webservers | nc35, Browser-Sitzung (Playwright wie 30-02), Owner-Freigabe für Tasks-App-Installation | Weicht ab: Owner-Frage vor dem Bau von `tasks_complete` (D-33-06) |
| M-2 | Tasks-App 0.18.1: Fälligkeit, Startdatum, Beschreibung entfernen, Elternbezug lösen (Unteraufgabe zur Hauptaufgabe machen), Priorität auf keine, Tags leeren; Rohdifferenz je Objekt | dieselbe Sitzung wie M-1 | Form des Entfernens (Zeile weg oder leer) und ob `LAST-MODIFIED`/`DTSTAMP` nachziehen; neue Fixtures unter `tests/fixtures/tasks_app/` mit PROVENANCE |
| M-3 | Kette mit 50 Nachfahren (Tiefe 1 und Tiefe 3): Gesamtzeit von REPORT plus 51 `PUT`, ebenso 51 `MOVE`, min/median/max über mehrere Läufe | nc35 (Impersonation) und NC 32 (`nc-mcp-exapp`), seriell, RAM-Gate | bestätigt oder ersetzt 50 nach Hausregel (D-33-10), Wert dem Owner nennen |
| M-4 | `PUT` auf ein Objekt, das der Server beim Speichern verändert (z. B. ohne `PRODID`), ETag-Kopf vorhanden? | Wegwerf-Instanz oder nc35 | bestätigt Pitfall 10 live (spike 11 offen) |
| M-5 | Live-Beweis TMOD-06: abhaken, ändern, verschieben; alte ETag 412 und Objekt unverändert (sha256 der Spalte `calendardata`); zweites Konto mit nur lesender Freigabe: alle drei abgelehnt, Objekt unverändert; Deck-Karte über keines erreichbar; mit und ohne Tasks-App; BASELINE vorher gleich nachher | nc35 ganze Kette (`scripts/tasks_chain_evidence.py`) und Funktionsebene (`tests/integration/test_tasks_live.py`), dann NC 32 | Abschluss TMOD-06 |

## Environment Availability

In dieser Recherche wurde kein Container gestartet. Stand laut STATE.md (13.11.2026): keine Instanz läuft.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv, Python 3.13 | Gates, Prototypen | ja (Läufe dieser Recherche) | 3.13.13 | kein |
| icalendar | Editor | ja | 7.3.0 | kein |
| Docker Desktop mit WSL2 | M-1 bis M-5 | ja (Phase 32) | - | kein |
| Instanz nc35 (35.0.0, ExApp) | M-1, M-3, M-5 | ja, gestoppt | Image muss für M-5 neu gebaut werden | kein |
| Strecke nc-mcp-exapp (NC 32.0.15) | M-3, M-5 | ja, gestoppt | - | kein |
| Tasks-App 0.18.1 aus dem Store | M-1, M-2, M-5 | in Phase 32 installiert und wieder entfernt | 0.18.1 | kein |
| Playwright/Chromium | M-1, M-2 | in 30-02 genutzt | - | Hauptsitzung führt die Schritte |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** keine.

## Validation Architecture

`workflow.nyquist_validation` steht in `.planning/config.json` auf `false`; der Auftrag verlangt den Abschnitt trotzdem, darum hier als Testkarte.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest mit anyio, httpx MockTransport, In-Memory `Client(mcp)` |
| Config file | `pyproject.toml` (`addopts` mit `-m 'not integration and not matrix'`) |
| Quick run command | `uv run --no-sync pytest tests/unit/test_ics_edit.py tests/unit/test_tasks_modify.py -o addopts="" -p no:xdist -q --import-mode=importlib` |
| Full suite command | `uv run --no-sync pytest tests/unit tests/contract -o addopts="" -m "not integration and not matrix" -q --import-mode=importlib` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TMOD-01 | `If-Match` immer gesetzt, nie `*`; 412 ohne zweiten Versuch; Schalter aus heißt nicht registriert | unit, contract | `pytest tests/unit/test_tasks_modify.py tests/contract/test_no_destructive_calls.py tests/contract/test_tool_surface.py -k "put or switch or tasks_update"` | neu (Wave 0) |
| TMOD-02 | Byte-Beweis und Semantik-Beweis je Fixture und Änderungsart, Positivkontrolle | unit | `pytest tests/unit/test_ics_edit.py` | neu (Wave 0) |
| TMOD-03 | Felder beim Abhaken/Wiederöffnen, null `PUT` im Zielzustand, Kette in Nachordnung, Stopp beim ersten Fehler, Obergrenze, Vorprüfung | unit | `pytest tests/unit/test_tasks_modify.py -k complete` | neu |
| TMOD-04 | Prüfungen auf Endstand, leer heißt entfernen, kein Unterschied kein `PUT`, Eltern gleiche Liste, kein Zyklus | unit | `pytest tests/unit/test_tasks_modify.py -k update` | neu |
| TMOD-05 | Annotationsklasse, Freeze mit Schalter an, Allowlist, Klassen, Bundles, Budget | contract | `pytest tests/contract -k "annotation or allowlist or classes or bundle or budget"` plus `python scripts/check_tool_budget.py` | anpassen |
| TMOD-06 | Live-Beweis | integration (manuell gestartet) | `pytest tests/integration/test_tasks_live.py -m integration -s` mit Env | anpassen |
| TMOD-08 | Ziel aus Discovery, Vorprüfung Name/UID, `Overwrite: F`, 201 sonst Fehler, Kinder zuerst, Gate-Pin `MOVE` | unit, contract | `pytest tests/unit/test_tasks_modify.py -k move tests/contract/test_no_destructive_calls.py -k move` | neu |

### Sampling Rate
- **Per task commit:** Quick run plus `ruff check`, `ruff format --check`.
- **Per wave merge:** Gates aus 32-RULES Abschnitt 3.
- **Phase gate:** volle Suite grün, Budget mit Schaltern an, Live-Beweis M-5 protokolliert.

### Wave 0 Gaps
- [ ] `tests/unit/test_ics_edit.py`: Rundlauf-Beweise, reiche Handobjekte, Positivkontrolle
- [ ] `tests/unit/test_tasks_modify.py`: Werkzeuglogik mit MockTransport (Sequenz der Anfragen, Köpfe, Statuszweige)
- [ ] Hilfsfunktion für Gate-Tests mit Schalter an (Subprozess, gibt Namen, Annotationen und Schemas als JSON aus)
- [ ] Fixtures aus M-2 (Tasks-App-Form beim Entfernen) mit PROVENANCE

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (unverändert) | AppAPI-Impersonation oder App-Passwort |
| V3 Session Management | nein | zustandslos; ETag ist keine Sitzung |
| V4 Access Control | ja | Server entscheidet (412/404/403); Vorprüfung `writable` aus Discovery; Deck nie; kein Nutzerparameter (`FORBIDDEN_PROPERTIES`); Schalter ab Werk aus |
| V5 Input Validation | ja | Pydantic-Schema; `ids.parse`, `safe_segment`, `normalize_etag`; Prüfungen von `tasks_create` auf dem Endstand; icalendar-Vor- und Nachprüfung |
| V6 Cryptography | nein | - |
| V8 Data Protection | ja | Audit nur Parameternamen, `summary`/`description` gesperrt; keine Besitzerkennung in Antworten |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Überschreiben einer zwischenzeitlichen Änderung | Tampering | `If-Match` auf die gelesene ETag, Vergleich vor dem `PUT`, kein Retry |
| Halbe Kette nach Fehler | Tampering (Integrität) | Vorprüfung vor dem ersten Schreiben, Nachordnung, ehrliche Liste der Geänderten |
| Verlust fremder Eigenschaften | Tampering | Zeilen-Editor, zwei unabhängige Beweise |
| Verschieben über ein belegtes Ziel | Tampering | `Overwrite: F` als Literal, AST-Pin, Vorabprüfung der Zielliste |
| Zeilen- oder Komponenten-Injektion über Titel/Beschreibung | Tampering | Werte nur über icalendar kodiert; Nachprüfung "genau ein VTODO, gleiche UID" |
| Schreiben in fremde nur lesbare Liste | Elevation | `writable`-Vorprüfung, 404 als letzte Instanz, Zwei-Konten-Negativbeweis |
| Deck-Karte ändern | Information Disclosure/Tampering | Präfix vor jeder Anfrage, Discovery schließt Deck aus, Kanarie |

## Empfohlener Planschnitt (Claude's Discretion)

| Plan | Inhalt | Welle | Hängt ab von | Live |
|------|--------|-------|--------------|------|
| 33-01 | Messung vor dem Bau: M-1 und M-2 (Browser-Sitzung Tasks 0.18.1 auf nc35, Owner-Freigabe Installation, Owner-Checkpoint bei Abweichung von D-33-05), M-3 (Kette 50 auf nc35 und NC 32, App-Passwort und Impersonation), M-4; Inventar A17 auf HEAD neu ziehen; Beleg in `docs/tasks-evidence.md` oder Nachtrag zu `docs/spike-tasks.md`; neue Fixtures | 1 | kein | ja |
| 33-02 | Gemeinsamer Unterbau: Schalter-Kette `NC_MCP_TASKS_UPDATE` vollständig (Pattern 5), `tasks_read` mit ETag, `TodoObject.etag`, `get_todo` mit ETag, `put_existing_todo`, `move_todo`, `ics_edit` mit beiden Beweisen, Gate-Umbau (`EXPECTED_PUT_CALLS` 7, `MOVE`-Pin, optionale Werkzeuge in Audit/Klassen/Surface/Bundles, neue Annotationsklasse nach Owner-Antwort zu Open Question 1), Budget-Messung mit Schaltern an | 2 | 33-01 (Form des Entfernens, Obergrenze) | nein |
| 33-03 | `tasks_complete` (TMOD-03) samt Kette, Registrierung, Allowlist-Eintrag, Klassifikation, Tests | 3 | 33-02 | nein |
| 33-04 | `tasks_update` (TMOD-04), Registrierung, Tests | 3 | 33-02 | nein |
| 33-05 | `tasks_move` (TMOD-08), Registrierung, Tests | 3 | 33-02 | nein |
| 33-06 | Abschluss: Budget aus dem Endstand verankern, READMEs (Rechtetabelle mit eigener Stufe, Schalter, drei Sprachen), drei Changelogs, Server-Instruktion bei Schalter an, Kanarie und Abnahmeskript mit Schalter an | 4 | 33-03 bis 33-05 | nein |
| 33-07 | Live-Beweis M-5 auf nc35 (ganze Kette und Funktionsebene) und NC 32 | 5 | 33-06 | ja |

33-03 bis 33-05 sind dateigleich in `tools/tasks.py`, `reg_tasks.py`, `allowlist.py`, `tool_classes.py`; parallel nur mit klarer Abschnittsteilung, sonst nacheinander. Jeder der drei kann per Owner-Entscheid herausfallen, ohne 33-02 umzubauen, weil 33-02 nur Unterbau und Gate-Mechanik liefert; die konkreten Werkzeugnamen tragen erst 33-03 bis 33-05 in die Mengen ein.

## Sources

### Primary (HIGH confidence)
- Repo-Code auf HEAD 63221a9, gelesen: `nextcloud/clients/caldav.py`, `nextcloud/clients/tasks.py`, `nextcloud/clients/dav.py` (`normalize_etag`, `update_file`, Chunk-`MOVE`), `tools/tasks.py`, `tools/files.py::update`, `tools/chatgpt.py`, `server/__init__.py`, `server/reg_tasks.py`, `server/reg_files.py`, `config.py`, `entry_exapp.py`, `exapp/config_values.py`, `exapp/admin_settings.py`, `exapp/ui/strings.py`, `audit/allowlist.py`, `appinfo/info.xml`, `tests/contract/test_no_destructive_calls.py`, `test_tool_surface.py`, `tool_classes.py`, `test_tool_classes.py`, `test_audit_surface.py`, `test_tool_bundles.py`, `tests/integration/test_canary.py`, `scripts/check_tool_budget.py`, `scripts/acceptance_all_tools.py`, `scripts/tasks_spike.py`, Fixtures `tests/fixtures/tasks_app/`
- `docs/spike-tasks.md` Abschnitte 3, 4.1, 4.2, 5.6, 6, 7, 9.3, 9.4, 10, 11
- Lokale Läufe dieser Recherche mit icalendar 7.3.0 und Python 3.13.13 (Rundlauf, Bearbeitung, Zeilen-Editor-Prototyp, Größenprototyp der drei Schemas)
- sabre-io/dav master `lib/DAV/Server.php::updateFile` (`$modified` setzt `$etag = null`), `lib/DAV/CorePlugin.php::httpPut`

### Secondary (MEDIUM confidence)
- MCP-Spezifikation 2025-06-18, Schema `ToolAnnotations` (modelcontextprotocol.io/specification/2025-06-18/schema)
- RFC 5545 3.6.2 (Eigenschaften vor `VALARM`), `RELATED-TO` mit Standard `PARENT`, `DUE`/`DURATION` exklusiv: aus Kenntnis, durch icalendar-Ausgabe und vorhandenen Code gestützt

### Tertiary (LOW confidence)
- Verhalten von Thunderbird mit `ALTREP`/`X-ALT-DESC` (A1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, keine neue Abhängigkeit, Bibliotheksverhalten lokal gemessen
- Architecture: HIGH für Schreibschiene, Editor und Gates; MEDIUM für Kettenkosten (M-3 steht aus)
- Pitfalls: HIGH, aus Code und Spike-Rohwerten

**Research date:** 2026-11-13
**Valid until:** 2026-12-13 (Tasks-App-Fassung, Nextcloud-Patchreleases und eine neue icalendar-Fassung können das Gemessene ändern; vor M-5 die Fassungen festhalten)

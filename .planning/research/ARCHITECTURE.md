# Architecture Research

**Domain:** Ausschluss-Tag `kein-ki` in einer ausgelieferten MCP-ExApp: ein kollaboratives System-Tag auf einer Datei oder einem Ordner (Subtree) hält diese Inhalte aus jeder Tool-Antwort heraus, fail-closed, mit einer gebatchten Tag-Abfrage je Antwort (v1.7, BL-16)
**Researched:** 2026-09-26
**Confidence:** HIGH für alle Aussagen über die eigene Codebasis (Datei und Zeile gelesen, nicht erinnert); HIGH für die Findling-Trefferform (`php/lib/Search/Provider.php:384` im lokalen Repo gelesen); MEDIUM für das Verhalten von `REPORT oc:filter-files` mit `oc:systemtag` (Server-Quelltext `FilesReportPlugin.php` über WebFetch gelesen, nicht gemessen); MEDIUM für `nc:system-tags` als Datei-Property mit Sichtbarkeitsfilter (`SystemTagPlugin.php` gelesen); LOW bis zur Messung für "Notes-Id gleich Datei-Id" (Trainingswissen, nicht verifiziert) und für das Verhalten bei geteilten Ordnern mit getaggtem Vorfahren beim Eigentümer

**Kernaussage in fünf Sätzen.** Der Filter gehört weder in den `graceful`-Wrapper (der sieht fertige, heterogene Antworten, `server/__init__.py:103-133`) noch in 22 Registrierungen, sondern an sechs Engstellen, durch die nachweislich jede dateiabgeleitete Antwort läuft: `files.search`, `files.list_dir`, den Einzelzugriff hinter `dav.stat`/`find_by_fileid`, `search._normalise`, und die beiden Notes-Leser; `prepare_context`, `search` (ChatGPT) und `fetch` erben ihn, weil sie ausschließlich über diese Stellen gehen. Der Tag-Blick wird pro Tool-Aufruf genau einmal geladen und hängt an `NcClients`, das `deps.resolve_clients` (`deps.py:116-118`) genau einmal je Aufruf baut; damit ist "eine Abfrage je Antwort" Bauform statt Disziplin, und die Invalidierung ist trivial, weil der Blick mit dem Aufruf stirbt. Für die Subtree-Semantik schlägt "getaggte Menge einmal holen, Pfade per Präfix testen" die Ahnenketten-Prüfung klar: WebDAV hat kein gebatchtes Primitiv für Vorfahren, wohl aber `REPORT oc:filter-files` mit `oc:systemtag`, das alle getaggten Knoten des Nutzers in einem Roundtrip liefert, und deren hrefs laufen durch dieselbe Normalisierung wie die Sandbox (`dav._home_path_of`, `dav.py:493-502`). Die Sandbox aus PR #8 ist die richtige Vorlage für die Pfadnormalisierung und den Segmenttest (`dav.in_files_root`, `dav.py:483-490`), aber nicht für den Einbauort: sie ist statische Konfiguration ohne I/O und sitzt deshalb synchron in `parse_entries`, der Tag-Blick braucht einen Netzabruf und damit eine asynchrone, request-gebundene Stelle. Zwei Befunde gehen über das Feature hinaus und sollten in die Roadmap: Findling-Treffer tragen nur `fileId` und keinen `path` und passieren deshalb heute die Sandbox ungeprüft (`search.py:246-252`), und Notes laufen über die Notes-REST-API komplett an der Sandbox vorbei; derselbe Pfad-Resolver, den der Ausschluss für pfadlose Treffer braucht, schließt beide Lücken mit.

---

## Teil 0: Die Randbedingungen, die dieses Feature erbt

| # | Randbedingung | Beleg |
|---|---------------|-------|
| R1 | Genau ein `NcClients` je Tool-Aufruf, gebaut in `deps.resolve_clients`; alle 22 Registrierungen rufen es als erste Zeile | `deps.py:116-118`, z.B. `reg_files.py:33,52,66,88,141` |
| R2 | `NcClients` ist `frozen=True, slots=True` mit zwei Feldern, 34 Testdateien bauen es direkt | `nextcloud/__init__.py:16-21`; `grep -rl "NcClients(" tests` = 34 |
| R3 | Komponierende Tools reichen dasselbe `NcClients` durch: `prepare_context` an `unified_search` und an `chatgpt.fetch` für Auszüge, `chatgpt.search` an `unified_search`, `fetch(file)` an `files.read` | `context.py:249,775`; `chatgpt.py:165,252,281` |
| R4 | Die Sandbox filtert DAV-Ergebnisse synchron beim Parsen und Suchtreffer über `attributes.path`; Nicht-files-Provider ohne `path` passieren | `dav.py:477`; `search.py:214,240-255` |
| R5 | Rückgegebene Pfade sind absolute Pfade im Nutzer-Home (nicht die virtuelle Wurzel), URL-dekodiert, ohne Schluss-Slash | `dav.py:493-502`; `safe_path` bildet nur Eingaben auf die Wurzel ab, `dav.py:115-122` |
| R6 | Zwei Degradations-Formen: `unified_search` schreibt `{"provider", "reason"}`, `prepare_context` schreibt `{"source", "reason"}` und reicht die inneren Einträge unverändert durch | `search.py:101,114,176`; `context.py:513,518,800-805` |
| R7 | Die Datei-Familie kennt kein `degraded`; eine leere Erfolgsantwort, wo eigentlich "nicht lesbar" gilt, vermeidet die Codebasis ausdrücklich (T-11-17-Muster) | `files.py:139-155,189-197`; `chatgpt.py:612-613,693-697` |
| R8 | Refusal-Gründe sind eingefroren (12 Stück); ein dreizehnter ist eine Review-Entscheidung, ein Test läuft `src/` ab. `guard_tripped` ("a guard of this server stopped the call") existiert bereits | `errors.py:39,56-58` |
| R9 | Modulweite Caches nur für Nicht-Nutzerdaten mit TTL, Schlüssel `(base_url, user)`; Nutzerdaten nie über den Aufruf hinaus (D-20) | `capabilities.py:62,151-165`; `chatgpt.py:27-28`, `search.py:3-5` |
| R10 | Suchanfragen mit mehr als 100 Operatoren lehnt Nextcloud ab; der DAV-Client baut deshalb flache Bäume | `dav.py:266-268` |

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│ server/reg_*.py (22 Tools)   @graceful: ToolError -> Satz, Audit-Zeile    │
│   jede Registrierung: clients = deps.resolve_clients(ctx)   (R1)          │
│                                   │                                       │
│                                   ▼                                       │
│   NcClients(client, creds, exclusion=ExclusionGuard())   NEU: 3. Feld     │
├──────────────────────────────────────────────────────────────────────────┤
│ tools/ (Familien)                                                         │
│  ┌──────────────┐ ┌───────────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ files.py     │ │ search.py     │ │ notes.py │ │ chatgpt.py/context.py│ │
│  │ E1 search    │ │ E4 _normalise │ │ E5 search│ │ erben E1..E6, eigene │ │
│  │ E2 list_dir  │ │  (+paralleler │ │ E6 read  │ │ Prüfung nur als      │ │
│  │ E3 read/dl   │ │   Tag-Abruf)  │ │          │ │ Tiefenverteidigung   │ │
│  └──────┬───────┘ └──────┬────────┘ └────┬─────┘ └──────────┬───────────┘ │
│         └────────────────┴───── await clients.exclusion.view(clients) ──┘ │
├──────────────────────────────────────────────────────────────────────────┤
│ nextcloud/exclusion.py  NEU                                               │
│   ExclusionGuard: single-flight je Aufruf, Ergebnis = View | Unchecked    │
│   ExclusionView:  tagged_ids, tagged_prefixes, excludes(path, fileid)     │
│   _tag_ids-Cache: (base_url,user) -> Tag-Ids, TTL, nur positiv            │
├──────────────────────────────────────────────────────────────────────────┤
│ nextcloud/clients/                                                        │
│   systemtags.py NEU: PROPFIND /dav/systemtags (Name -> Id)                │
│                      REPORT oc:filter-files auf /dav/files/<user>         │
│   dav.py GEÄNDERT:  home_entries() (parse_entries ohne Sandbox-Drop),     │
│                      paths_for_fileids() (gebatchtes SEARCH über fileid)  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Komponente | Verantwortung | Neu / geändert |
|------------|---------------|----------------|
| `nextcloud/clients/systemtags.py` | Roh-HTTP: Tag-Name auf Tag-Id(s) auflösen (PROPFIND `/remote.php/dav/systemtags/`, `oc:display-name`, `oc:user-visible`, `oc:user-assignable`); getaggte Knoten holen (`REPORT oc:filter-files` mit `<oc:systemtag>`-Regel, Props nur `oc:fileid` + `d:resourcetype`). Statusübersetzung nach dem `_check`-Muster, kein Retry | NEU |
| `nextcloud/clients/dav.py` | `home_entries(body, creds)`: `parse_entries` ohne den `in_files_root`-Drop, `parse_entries` ruft es und filtert danach (Verhalten unverändert). `paths_for_fileids(ids)`: ein SEARCH mit flachem `<d:or>` über `<d:eq oc:fileid>`, gestückelt unter R10 | GEÄNDERT (additiv) |
| `nextcloud/exclusion.py` | Policy: `ExclusionView` (rein, ohne I/O, testbar), `ExclusionGuard` (per Aufruf, `asyncio.Lock`, merkt sich View oder Fehlschlag), Tag-Id-Cache nach dem `capabilities`-Muster, `withhold`-Hilfen, die Degradationssätze | NEU |
| `nextcloud/__init__.py` `NcClients` | drittes Feld `exclusion: ExclusionGuard = field(default_factory=ExclusionGuard)`; der Default hält die 34 Test-Konstruktionen gültig (R2) | GEÄNDERT |
| `tools/files.py` | E1 bis E3, plus die Entscheidung zu Uploads (siehe Offene Fragen) | GEÄNDERT |
| `tools/search.py` | E4: Tag-Abruf parallel zur Provider-Auffächerung starten, in `_normalise` jeden dateitragenden Treffer prüfen, pfadlose Treffer über `paths_for_fileids` auflösen, Fail-closed als `degraded` je betroffenem Provider | GEÄNDERT |
| `tools/notes.py` | E5/E6: Notiz-Ids als Datei-Ids prüfen (nach Messung), pfadlos -> Resolver | GEÄNDERT |
| `tools/chatgpt.py`, `tools/context.py` | keine eigene Logik; erben. Höchstens eine Zeile in `_fetch_file` als Tiefenverteidigung (kostet dank Guard keinen Roundtrip) | minimal |
| `config.py` + `entry_*.py` | optional `NC_MCP_EXCLUDE_TAG` (Default `kein-ki`), Validierung beim Start nach dem Muster `config.files_root(env)` (`entry_http.py:91`, `entry_exapp.py:93`, `entry_oauth.py:250`, `entry_stdio.py:29`) | GEÄNDERT, falls Owner einen Schalter will |
| `tests/contract/` | NEU: Klassifikations-Gate über alle registrierten Tools (dateiabgeleitet ja/nein), rot bei jedem 23. Tool ohne Eintrag | NEU |

---

## Frage 1: Die Sandbox aus PR #8 als nächste Analogie

**Wo sie einhakt (gelesen):**

| Stelle | Datei:Zeile | Was passiert |
|--------|-------------|--------------|
| Eingabepfade | `dav.py:85-122` `safe_path` | normalisiert, bildet `/x` auf `<root>/x` ab; läuft vor jedem Request |
| Suchbereich | `dav.py:229-249` `search_scope` | Scope der DAV-Suche ist nie außerhalb der Wurzel |
| DAV-Ergebnisse | `dav.py:466-480` `parse_entries`, Zeile 477 | jeder href außerhalb von Home oder Wurzel wird verworfen; trifft `search` (426), `propfind_children` (455), `find_by_fileid` (390) |
| Unified Search | `search.py:214` in `_normalise`, Logik `search.py:240-255` | prüft `attributes.path`; `files` ohne Pfad wird verworfen, jeder andere Provider ohne Pfad passiert |
| Nicht erfasst | `dav.py:143-172` `stat` | parst selbst, nicht über `parse_entries`; geschützt nur, weil der Eingabepfad schon durch `safe_path` lief |

**Kann der Ausschluss auf denselben Engstellen reiten?** Auf denselben Pfaden ja, an derselben Codezeile nein.

- `parse_entries` ist synchron und bekommt nur `body` und `creds`. Der Tag-Blick braucht einen Netzabruf, der nicht in einen Parser gehört, und er muss vor dem Fenstern und Paginieren wirken (`files.py:138`, `files.py:186-187`), sonst lügen `count`, `truncated` und `next`. Die Filterung gehört deshalb eine Ebene höher in die Tool-Funktionen, direkt nach dem DAV-Aufruf und vor dem Schnitt. Der DAV-Client bleibt policy-frei, genau wie er heute nichts über Talk oder Notes weiß.
- `_normalise` (`search.py:201-237`) ist ebenfalls synchron, bekommt aber schon heute Kontext (`clients`). Die richtige Form: `unified_search` startet den Tag-Abruf als weitere Aufgabe im bestehenden `asyncio.gather` (`search.py:104-107`), sodass er keine Wanduhrzeit kostet, und reicht den fertigen Blick an `_normalise` weiter. Die Prüfung sitzt direkt neben Zeile 214.
- **Wiederverwenden, nicht kopieren:** `_home_path_of` (`dav.py:493-502`) für die hrefs aus dem REPORT, und die Segmentregel `path == p or path.startswith(p + "/")` aus `in_files_root` (`dav.py:490`) als eine gemeinsame Funktion. Zwei Schreibweisen derselben Präfixregel sind genau der Fehler, den `ids.py` als "einzige Quelle" in v1.3 abgeschafft hat.
- **Nicht wiederverwenden:** `parse_entries` selbst für die getaggte Menge. Es verwirft alles außerhalb von `NC_MCP_FILES_ROOT`, und ein getaggter Vorfahr der Wurzel (Wurzel `/Shared/KI`, Tag auf `/Shared`) muss gerade drinbleiben. Deshalb `home_entries` als ungefilterte Hälfte herauslösen.

**Nebenbefund, sandboxrelevant:** Findling setzt nur `fileId`, keinen `path` (`nextcloud-search/php/lib/Search/Provider.php:384`), und ist nicht in `PROVIDER_KINDS` (`provider_map.py:55-85`), läuft also als `url`-Treffer mit `provider != "files"` durch `_entry_in_files_root` und passiert (`search.py:249,252`). Notes gehen über `/apps/notes/api/v1` und berühren `parse_entries` nie. Beide sind heute Sandbox-Lücken; der Pfad-Resolver aus diesem Feature schließt sie mit, wenn der Owner das in den Scope nimmt.

---

## Frage 2: Ehrliche Scope-Liste über alle 22 Tools

Gezählt aus den `@mcp.tool`-Stellen in `server/reg_*.py`.

| # | Tool | Registrierung | Liefert dateiabgeleiteten Inhalt? | Engstelle | Anmerkung |
|---|------|---------------|-----------------------------------|-----------|-----------|
| 1 | `files_search` | `reg_files.py:23` | JA (Namen, Pfade, Ids) | E1 `files.py:136-138` | Filtern vor dem Fenster; Suchordner selbst prüfen |
| 2 | `files_list` | `reg_files.py:43` | JA | E2 `files.py:179-187` | Zielordner prüfen, Kinder vor Sortierung filtern |
| 3 | `files_read` | `reg_files.py:60` | JA (Inhalt) | E3 `files.py:243-244` | nach `stat`, vor `get_range` |
| 4 | `files_download` | `reg_files.py:72` | JA (Bytes) | E3 `files.py:323-324` | dito |
| 5 | `files_upload` | `reg_files.py:108` | nein, aber Schreibziel und Existenz-Orakel (`ConflictError` "A file already exists at ...", `dav.py:644-647,704-707`) | E3-Variante `files.py:390,435` | Owner-Frage: in `kein-ki`-Ordner schreiben verbieten? |
| 6 | `unified_search` | `reg_search.py:20` | JA (files, findling, notes; Titel, Subline) | E4 `search.py:201-237` | provider-agnostisch per `fileId`/`/f/<id>` prüfen, nicht nur `files` |
| 7 | `search` (ChatGPT) | `reg_chatgpt.py:27` | JA | erbt E4 über `chatgpt.py:165` | keine eigene Prüfung |
| 8 | `fetch` | `reg_chatgpt.py:36` | JA für `file:` und `note:`; nein für `card`, `event`, `mail`, `message`, `table` | `file`: `chatgpt.py:240` + erbt E3 über `files.read` (252); `note`: erbt E6 (281) | sieben Id-Arten, zwei betroffen |
| 9 | `prepare_context` | `reg_context.py:37` | JA (Suchtreffer, Auszüge) | erbt E4 (`context.py:249`) und E3/E6 über `fetch` (775) | Kalender-, Talk-, Mail-Bein unberührt |
| 10 | `notes_search` | `reg_notes.py:21` | JA, sofern Notiz = Datei (Notes speichert Markdown-Dateien) | E5 `notes.py:63-90` | Messpunkt: Notiz-Id == Datei-Id |
| 11 | `notes_read` | `reg_notes.py:33` | JA | E6 `notes.py:105` | dito |
| 12 | `notes_create` | `reg_notes.py:44` | nein (Antwort ist das eigene Geschriebene) | keine | Grenzfall: Kategorie-Ordner getaggt |
| 13 | `calendar_list_events` | `reg_calendar.py:20` | nein | keine | CalDAV, keine ATTACH-Projektion gefunden |
| 14 | `calendar_create_event` | `reg_calendar.py:53` | nein | keine | |
| 15 | `contacts_search` | `reg_contacts.py:20` | nein | keine | CardDAV |
| 16 | `deck_browse` | `reg_deck.py:25` | nein | keine | Deck-API 1.0 ohne Anhänge (`clients/deck.py:14,41`) |
| 17 | `deck_create_card` | `reg_deck.py:52` | nein | keine | |
| 18 | `tables_browse` | `reg_tables.py:25` | nein (Zellinhalt; ein Link-Zelltyp kann einen Dateinamen tragen) | keine | als Restrisiko benennen |
| 19 | `tables_create_row` | `reg_tables.py:54` | nein | keine | |
| 20 | `talk_browse` | `reg_talk.py:39` | **Referenz, kein Inhalt**: eine in den Chat geteilte Datei erscheint als Name über `messageParameters` (`talk.py:574-604`) | optional | Parameter vom Typ `file` tragen `id` und `path`, wären mit demselben Blick billig maskierbar |
| 21 | `talk_send` | `reg_talk.py:74` | nein | keine | |
| 22 | `mail_browse` | `reg_mail.py:51` | nein (nur `has_attachments`, `mail.py:505-506`) | keine | Mail liest keine Anhänge |

**Ergebnis:** 11 von 22 Tools liefern dateiabgeleiteten Inhalt (1 bis 11), einer ist ein Schreibpfad mit Orakel (5, in der Zählung enthalten), einer trägt Dateireferenzen (20), elf sind unbetroffen. Die 11 betroffenen laufen über **sechs** Engstellen (E1 bis E6); nur diese werden angefasst. Das Klassifikations-Gate hält die Tabelle als Test fest, damit ein 23. Tool nicht ungeprüft durchrutscht.

**Ehrlich zu benennen, auch wenn nicht gebaut:** Talk-Dateiparameter (Name, keine Bytes), Tables-Linkzellen, Unified-Search-Provider Dritter, die eine Datei weder per `attributes.fileId` noch per `/f/<id>`-URL kenntlich machen (dann ist die Datei für uns nicht erkennbar und der Treffer passiert; das ist die Grenze eines Filters, der nur sieht, was Nextcloud meldet).

---

## Frage 3: Wo der Cache lebt und welche Invalidierung er braucht

**Zwei Ebenen, getrennt nach Datenart:**

| Ebene | Inhalt | Ort | Lebensdauer | Invalidierung |
|-------|--------|-----|-------------|---------------|
| Per Aufruf | `ExclusionView` (getaggte fileids und Ordnerpräfixe) oder der Fehlschlag | `NcClients.exclusion`, gebaut in `deps.py:118` | genau ein Tool-Aufruf | keine nötig, stirbt mit dem Aufruf; eine Tag-Änderung wirkt ab dem nächsten Aufruf |
| Prozessweit | Tag-Name -> Tag-Id(s) | Modul-Dict in `exclusion.py`, Schlüssel `(base_url, user)` wie `capabilities.py:151` | TTL, Vorschlag 60 s wie `capabilities.TTL_SECONDS` | **nur positive Treffer cachen**; bei `412` aus dem REPORT (Tag gelöscht, laut `FilesReportPlugin` "Cannot filter by non-existing tag") Eintrag löschen, einmal neu auflösen, dann fail-closed |

**Warum die getaggte Menge nicht prozessweit:** Sie ist Nutzerdatum (welche Ordner jemand für sensibel hält), und R9/D-20 verbieten genau das. Außerdem würde jede TTL ein Fenster öffnen, in dem ein frisch getaggter Ordner noch ausgeliefert wird; das ist das eine Versprechen des Features.

**Warum kein negativer Cache der Tag-Id:** "Tag existiert nicht" heißt korrekt "nichts ausgeschlossen". Gecacht würde ein Admin, der `kein-ki` anlegt und sofort vergibt, bis zu 60 s lang nicht wirken. Die PROPFIND auf `/systemtags` ist billig; ohne Tag wird sie je Aufruf wiederholt, mit Tag entfällt sie warm.

**Single-flight je Aufruf:** `prepare_context` holt den Blick in der Suche und danach bis zu drei Auszüge parallel (`context.py:752-754`). `ExclusionGuard` hält ein `asyncio.Lock` und merkt sich das erste Ergebnis, sodass drei parallele `fetch` genau null zusätzliche Abrufe machen. Das Muster ist dasselbe, das `oauth/jwks.py` für den Schlüsselsatz in v1.6 eingeführt hat (Single-Flight, fail-closed).

**Lazy statt eager:** Der Guard lädt erst, wenn eine Engstelle fragt. Die elf unbetroffenen Tools zahlen damit nichts, und das Klassifikations-Gate beweist, dass sie nie fragen.

**Kosten je Antwort (Hypothese, BL-16-Messung vor der Designentscheidung):**
- warm, Tag existiert: 1 Roundtrip (REPORT), parallel zur eigentlichen Arbeit in `unified_search`/`prepare_context`, seriell vor dem Lesen in `files_read`/`download`.
- kalt: +1 PROPFIND.
- nur wenn pfadlose Treffer (Findling, Notes) im Ergebnis sind: +1 SEARCH `paths_for_fileids`, gestückelt je 49 Ids (49 `eq` + 48 `or` bleibt unter 100 Operatoren, R10).

---

## Frage 4: Subtree-Semantik, Ahnenkette gegen getaggte Menge

| Kriterium | A: Ahnenkette je Ergebnis prüfen | B: getaggte Menge einmal holen, Präfix testen |
|-----------|----------------------------------|-----------------------------------------------|
| Roundtrips | Vorfahren-fileids liefert DAV nicht; je Vorfahr ein PROPFIND Depth 0 mit `nc:system-tags`, also N Treffer mal Tiefe | 1 REPORT unabhängig von der Trefferzahl |
| Batchbar | nein, SEARCH kann nicht über Pfade verodern, nur über Props | ja, Ergebnis ist eine Menge |
| Latenz im Budget | reißt `prepare_context` (25 Treffer x Tiefe) | parallelisierbar zur Provider-Auffächerung |
| Pfadnormalisierung | jeder Vorfahrpfad separat | hrefs durch `_home_path_of`, dieselbe Form wie alle anderen Pfade (R5) |
| Größenrisiko | klein je Abfrage | wächst mit der Zahl getaggter Knoten (siehe Pitfalls) |

**Empfehlung: B.** Ablauf:

1. REPORT auf `/remote.php/dav/files/<user>` (Home-Wurzel, **nicht** die Sandbox-Wurzel, sonst fehlen getaggte Vorfahren der Wurzel; `FilesReportPlugin` schränkt auf den Teilbaum des Ziels ein).
2. hrefs über `home_entries` -> absolute Home-Pfade plus fileid plus `is_collection`.
3. `ExclusionView.excludes(path, fileid)`: `fileid in tagged_ids` **oder** der Pfad liegt segmentgenau unter einem getaggten Ordner (`p == t or p.startswith(t + "/")`, `t == "/"` deckt alles).
4. Getaggte Dateien (keine Ordner) gehen nur in `tagged_ids`, nicht in die Präfixe: eine Datei hat keinen Teilbaum, und ein Präfixeintrag für sie wäre nur unnötige Arbeit je Test.

**Warum die fileid zusätzlich zum Pfad:** Die fileid ist über Umbenennen und Verschieben stabil, der Pfad nicht, und Findling/Notes liefern überhaupt nur die Id. Direkt getaggte Treffer erkennt die Id-Menge ohne Pfadauflösung; nur für den Subtree-Test braucht ein pfadloser Treffer seinen Pfad.

**Die ehrliche Grenze von B (und von A genauso):** Beide sehen nur, was der Nutzer sieht. Taggt Alice `/Projekte` und teilt `/Projekte/Sub` an Bob, liegt Bobs Sicht unter `/Sub` (oder `/Shared/Sub`), und `/Projekte` ist für Bob nicht erreichbar; der REPORT findet es für Bob nicht, Bob bekommt `Sub` ausgeliefert. Das ist keine Implementierungsschwäche, sondern die Nutzer-API: der Connector sieht nie mehr als der Nutzer (Core Value), also auch keine Tags auf Knoten, die der Nutzer nicht sieht. Messen, dokumentieren, und als Enterprise-Governance-Thema (zentrale Policy) benennen. Konfidenz LOW bis gemessen, weil `searchBySystemTag` über Mounts hinweg auch anders auflösen könnte.

**Wechselwirkung mit der Sandbox-Normalisierung:** Vergleiche immer zwischen absoluten Home-Pfaden. `safe_path` bildet Eingaben auf die virtuelle Wurzel ab (`dav.py:118-122`), zurückgegebene Pfade sind aber absolut (R5); die getaggten Pfade kommen aus demselben `_home_path_of`, also passt die Form. Unified-Search-Pfade kommen als `attributes.path` ohne führenden Slash und werden heute schon mit `"/" + raw_path.lstrip("/")` normalisiert (`search.py:255`); dieselbe Normalisierung, eine Funktion.

---

## Frage 5: Fail-closed in die bestehende Degradationsbenennung

**Was als "nicht prüfbar" gilt:** PROPFIND `/systemtags` scheitert (systemtags-App aus: 404/405), REPORT scheitert (Timeout, 5xx, 412 nach erneuter Auflösung), `httpx.RequestError`, oder die Antwort ist nicht parsebar. **Kein** Fehler: der Tag existiert nicht (dann ist nichts ausgeschlossen). Der Guard speichert den Fehlschlag als Wert (`Unchecked(reason: str)`), nicht als Exception, damit jede Engstelle ihn in ihrer eigenen Form ausspricht.

| Antwortform | Tools | Fail-closed-Verhalten | Begründung aus dem Code |
|-------------|-------|------------------------|-------------------------|
| Einzelzugriff | `files_read`, `files_download`, `fetch(file)`, `fetch(note)`, `notes_read` | `ToolError` mit `reason=REASON_GUARD_TRIPPED`; `graceful` macht daraus Satz plus Audit-Zeile (`server/__init__.py:111-113,133`) | ein Treffer, keine Teilantwort möglich; `guard_tripped` existiert, kein 13. Grund nötig (R8) |
| Liste einer Familie | `files_search`, `files_list`, `notes_search` | ebenfalls `ToolError`: jeder Eintrag ist betroffen, eine leere Liste mit Randnotiz wäre die "leere Erfolgsantwort", die die Codebasis meidet (R7) | es gibt in dieser Familie kein `degraded`, und es für einen Totalausfall einzuführen, kostet Schema ohne Nutzen |
| Gemischte Quellen | `unified_search`, `search`, `prepare_context` | dateitragende Treffer zurückhalten, der Rest (Karten, Nachrichten, Tabellen, Termine, Talk, Mail) bleibt; je betroffenem Provider ein Eintrag `{"provider": "<id>", "reason": "<n> hits withheld: the kein-ki exclusion could not be checked (...)"}` | exakt die bestehende Form (R6); `prepare_context` reicht sie über `_degraded_of` (`context.py:518`) unverändert durch, eine Form für ein Problem |

**Ausgeschlossene Treffer im Normalfall (Tag prüfbar):** werden weggelassen. Ob sie gezählt werden (in `skipped`, `search.py:133-136`, oder eigener Schlüssel) oder stumm fehlen, ist eine FEATURES/Owner-Frage; architektonisch geht beides an derselben Zeile. Hinweis: `skipped` heißt heute "unbrauchbar", eine zweite Bedeutung im selben Schlüssel widerspräche TOOL-17 ("eine Bedeutung je Antwortschlüssel").

**Explizit benannte Ziele** (Pfad an `files_read`, `files_list`, `files_search(folder=...)`, Id an `fetch`) sind ausgeschlossen: `ToolError` mit `guard_tripped` und einem Satz, der den Tag nennt, statt "nicht gefunden". Eine Lüge über Nicht-Existenz würde den Nutzer, dessen Agent das ist, falsch informieren; er sieht die Datei im Web ohnehin.

**Audit:** Der Wrapper schreibt heute schon jede Ablehnung mit ihrem Grund; `guard_tripped` erscheint dort ohne weitere Änderung. Ob die Audit-Zeile zwischen "ausgeschlossen" und "nicht prüfbar" unterscheiden soll, ist die einzige Stelle, an der ein 13. Grund diskutiert werden müsste.

---

## Architectural Patterns

### Pattern 1: Request-gebundener Guard am Parameterobjekt

**What:** Der Tag-Blick hängt an `NcClients`, dem einzigen Objekt, das jede Tool-Funktion bekommt ("the seam where phase 2 hooks in the AppAPI impersonation without touching tool code", `nextcloud/__init__.py:3-4`).
**When to use:** Jede request-gebundene, nutzerspezifische Vorabinformation, die mehrere komponierte Tools teilen sollen.
**Trade-offs:** Ein veränderlicher Zustand in einem `frozen`-Dataclass (das Feld selbst ist unveränderlich, sein Inhalt nicht); dafür keine ContextVar-Magie, die bei `asyncio.gather` und `create_task` Kopiersemantik hat.

```python
@dataclass(frozen=True, slots=True)
class NcClients:
    client: httpx.AsyncClient
    creds: Credentials
    exclusion: ExclusionGuard = field(default_factory=ExclusionGuard)

class ExclusionGuard:
    __slots__ = ("_lock", "_state")
    async def view(self, clients: "NcClients") -> ExclusionView | Unchecked:
        async with self._lock:
            if self._state is None:
                self._state = await _load(clients)   # nie raise: Fehlschlag wird Unchecked
            return self._state
```

### Pattern 2: Filtern vor dem Fenster

**What:** Jede Liste wird gefiltert, bevor `offset`/`capped` geschnitten und `truncated`/`next` berechnet wird.
**When to use:** `files.search` (zwischen 136 und 138), `files.list_dir` (zwischen 179 und 186), `_normalise`.
**Trade-offs:** Eine Seite kann kürzer als `limit` werden, wenn viele Treffer ausgeschlossen sind; bei `files.search` (Holen mit `offset + capped + 1`, `files.py:135`) muss die Wächterzeile "gibt es mehr" nach dem Filtern gezählt werden, sonst wird ein ausgeschlossener Sentinel zur falschen Aussage "nichts mehr".

### Pattern 3: Parallel statt davor

**What:** Wo die Antwort ohnehin auf Netz wartet, startet der Tag-Abruf im selben `gather`.
**When to use:** `unified_search` (`search.py:104-107`); `prepare_context` erbt es über das Suchbein.
**Trade-offs:** Bei Einzelzugriffen (`files_read`) gibt es nichts zu parallelisieren außer `stat`; dort `stat` und Tag-Abruf per `gather` gemeinsam starten und erst vor `get_range` entscheiden. Die Bytes werden nie geholt, bevor die Prüfung durch ist.

### Pattern 4: Klassifikations-Gate statt Handverdrahtung

**What:** Ein Contract-Test listet alle registrierten Tools (aus der aktiven Registry, wie `test_tool_surface.py:532,564`) und verlangt für jedes einen Eintrag "dateiabgeleitet: ja/nein/Referenz". Für die Ja-Tools läuft ein Negativbeweis mit getaggtem Fixture (Datei direkt, Ordner als Vorfahr, Vorfahr der Sandbox-Wurzel, Guard-Fehlschlag).
**When to use:** Genau hier: es beantwortet "jede Antwort genau einmal, ohne 22 Tools zu verdrahten" mit einem Beweis statt einer Zusicherung.

---

## Data Flow

### Ein gefilterter `prepare_context`-Aufruf (detail=full)

```
reg_context.prepare_context
  -> deps.resolve_clients(ctx)            NcClients(..., exclusion=Guard(leer))
  -> context.prepare_context
       gather(
         search.unified_search ──┬─ ocs.list_search_providers
                                 ├─ gather(_ask(files), _ask(findling), _ask(notes), ...,
                                 │         clients.exclusion.view(clients))      <- 1 REPORT (+PROPFIND kalt)
                                 └─ _normalise(je Provider, view)
                                      files:    attributes.path -> excludes(path, fileId)
                                      findling: nur fileId -> id-Test; pfadlose sammeln
                                      notes:    Notiz-Id -> id-Test; pfadlose sammeln
                                    paths_for_fileids(pfadlose)                  <- 0 oder 1 SEARCH
                                    Unchecked? -> Dateitreffer zurückhalten + degraded{provider}
         _events, _talk, _mail                     unberührt
       )
  -> _bundle(...)                                 nur überlebende Treffer
  -> _excerpts -> gather(chatgpt.fetch(file:..)) -> _fetch_file -> find_by_fileid
                                                  -> files.read -> view()      <- Cache-Treffer, 0 Roundtrips
  -> Antwort mit degraded (inkl. durchgereichter Ausschluss-Einträge)
graceful: Audit-Zeile ok
```

### Ein `files_read` auf eine Datei unter einem getaggten Ordner

```
reg_files.files_read -> files.read
  target = dav.safe_path(path)                 /Projekte/Geheim/plan.md
  gather(dav.stat(target), exclusion.view())   1 PROPFIND + 1 REPORT parallel
  view.excludes("/Projekte/Geheim/plan.md", fileid)  -> True ("/Projekte/Geheim" getaggt)
  raise ToolError(..., reason=REASON_GUARD_TRIPPED)   get_range wird nie gerufen
graceful: ValueError-Satz an das Modell, Audit-Zeile rejected/guard_tripped
```

---

## Scaling Considerations

| Größe | Anpassung |
|-------|-----------|
| wenige getaggte Ordner (erwarteter Normalfall) | REPORT-Antwort klein, ein Roundtrip, nichts zu tun |
| hunderte einzeln getaggte Dateien | REPORT mit minimalen Props (`oc:fileid`, `d:resourcetype`); Größe messen (BL-16) |
| tausende getaggte Knoten | `{DAV:}nresults` des REPORT als Obergrenze setzen; ist sie erreicht, ist die Menge unvollständig und damit **Unchecked** (fail-closed), nicht "reicht schon" |

### Scaling Priorities

1. **Erster Engpass:** Größe der REPORT-Antwort bei massenhaft getaggten Einzeldateien. Gegenmittel: Obergrenze plus fail-closed, Doku "Ordner taggen statt Dateien".
2. **Zweiter Engpass:** `paths_for_fileids` bei 100 Treffern von `unified_search` (drei Stücke à 49 Ids); nur relevant, wenn Findling/Notes viele Treffer liefern. Parallel stückeln.

---

## Anti-Patterns

### Anti-Pattern 1: Nachfilter im `graceful`-Wrapper

**What people do:** Die fertige Antwort nach `file:`-Ids und `path`-Feldern durchsuchen und streichen.
**Why it's wrong:** Die Antworten sind heterogen (JSON-Strings, zwei Pydantic-Modelle, `EmbeddedResource` mit Base64 in `reg_files.py:91-103`); `count`, `truncated`, `next`, `skipped` und Bucket-Degradationen (`context.py:537-545`) wären danach falsch; und der Inhalt wäre bereits geholt, bevor er gestrichen wird.
**Do this instead:** Prüfen an den sechs Engstellen, vor dem Holen des Inhalts und vor dem Fenster.

### Anti-Pattern 2: Prüfung in `parse_entries` einbauen

**What people do:** Den Ausschluss neben Zeile 477 in `dav.py` hängen, weil die Sandbox dort sitzt.
**Why it's wrong:** Parser mit Netzabruf, Credentials-Durchgriff ohne `NcClients`, und die getaggte Menge selbst wird mit `parse_entries` geparst, würde sich also durch die Sandbox selbst beschneiden.
**Do this instead:** `home_entries` herauslösen, Policy in `exclusion.py`, Anwendung in `tools/`.

### Anti-Pattern 3: Nur `provider == "files"` prüfen

**What people do:** Das Sandbox-Muster aus `search.py:249,252` spiegeln.
**Why it's wrong:** Findling liefert Dateiinhalte als `url`-Art mit `fileId` (Provider.php:384); genau der Inhaltsprovider, der Dokumentinhalte in die Antwort bringt, bliebe ungefiltert.
**Do this instead:** Jeden Treffer mit `attributes.fileId` oder `/f/<id>` in der URL als dateitragend behandeln, provider-agnostisch; `provider_map._file_id` (`provider_map.py:197-208`) als öffentliche Funktion für alle Provider nutzbar machen (Boundary-Gate beachten, `test_module_boundaries.py:170`).

### Anti-Pattern 4: Getaggte Menge prozessweit cachen

**What people do:** Die REPORT-Antwort 60 s cachen wie die Capabilities.
**Why it's wrong:** Nutzerdatum über den Aufruf hinaus (D-20) und ein Zeitfenster, in dem ein frisch getaggter Ordner ausgeliefert wird.
**Do this instead:** Nur die Tag-Id prozessweit, positiv, mit 412-Invalidierung.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| `PROPFIND /remote.php/dav/systemtags/` | Name -> Id(s), Depth 1, Props `oc:id`, `oc:display-name`, `oc:user-visible`, `oc:user-assignable` | mehrere Tags gleichen Namens mit unterschiedlicher Sichtbarkeit sind möglich; Vereinigung aller für den Nutzer sichtbaren nehmen |
| `REPORT /remote.php/dav/files/<user>` mit `oc:filter-files`/`oc:systemtag` | getaggte Knoten, rekursiv im Ziel-Teilbaum; `{DAV:}nresults`/`nc:firstresult` für Paging; 412 bei unbekanntem Tag (FilesReportPlugin, MEDIUM) | Ziel ist die Home-Wurzel, nie `NC_MCP_FILES_ROOT` |
| `SEARCH /remote.php/dav/` mit `oc:fileid`-Oder | Pfad je fileid für pfadlose Treffer | Vorlage `build_fileid_body` (`dav.py:316-365`), Operatorgrenze R10 |
| `nc:system-tags` auf Dateiknoten | Alternative/Ergänzung für direkte Tags in `stat`/`propfind_children` ohne Extra-Roundtrip; filtert per `canUserSeeTag` | ein **unsichtbar** gestelltes Tag verschwindet hier still: nie allein darauf bauen |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `tools/*` -> `nextcloud/exclusion.py` | `await clients.exclusion.view(clients)`, dann `view.excludes(path, fileid)` rein synchron | eine öffentliche Fläche, keine Privat-Durchgriffe (AST-Gate) |
| `exclusion.py` -> `clients/systemtags.py`, `clients/dav.py` | direkte Aufrufe, wie `capabilities.py` -> `ocs` | Client-Schicht bleibt policy-frei |
| `tools/context.py`, `tools/chatgpt.py` -> Engstellen | unverändert über `unified_search`, `files.read`, `notes.read` | keine zweite Prüfung nötig; optional eine Zeile in `_fetch_file` |

---

## Suggested Build Order

| Schritt | Inhalt | Hängt ab von | Warum hier |
|---------|--------|--------------|------------|
| 0 | **Mess-Spike (BL-16-Kostennotiz):** REPORT-Kosten bei 1/100/5000 getaggten Knoten; 412-Verhalten; unsichtbares Tag; systemtags-App aus; geteilter Ordner mit getaggtem Vorfahr beim Eigentümer; Notiz-Id == Datei-Id; `nc:system-tags` in SEARCH selektierbar | nichts | Die Spec verlangt "vor der Designentscheidung gemessen"; drei Annahmen oben stehen auf LOW/MEDIUM |
| 1 | `clients/systemtags.py` + `dav.home_entries` + `dav.paths_for_fileids`, reine Unit-Tests mit MockTransport | 0 | unterste Schicht, keine Policy |
| 2 | `nextcloud/exclusion.py` (View rein, Guard, Tag-Id-Cache) + `NcClients`-Feld + gemeinsame Präfixfunktion mit `in_files_root` | 1 | danach existiert der Blick, aber niemand fragt ihn; Bestandstests bleiben grün |
| 3 | Test-Infrastruktur: `conftest`-Standard, der den Guard in Bestandstests stumm "nichts getaggt" antworten lässt | 2 | sonst brechen dutzende MockTransport-Tests an einem unerwarteten REPORT (siehe PITFALLS) |
| 4 | Datei-Familie E1 bis E3 inklusive Upload-Entscheidung | 2, 3, Owner-Antwort zu Uploads | kleinste Fläche, direkteste Beweise, und `fetch(file)`/Auszüge erben sie |
| 5 | `unified_search` E4 (parallel, provider-agnostisch, Degradation) | 2, 3 | erbt nach `search` und `prepare_context` |
| 6 | Notes E5/E6 + pfadlose Auflösung, optional Sandbox-Parität für Findling und Notes | 0 (Notiz-Id-Messung), 5 | hängt an der unsichersten Annahme |
| 7 | Klassifikations-Gate über 22 Tools + Integrationsbeweis gegen die Test-Nextcloud (Zwei-Konten-Muster, getaggter Ordner, Guard-Ausfall per abgeschalteter systemtags-App) | 4, 5, 6 | beweist "jede Antwort", nicht nur "die Stellen, an die wir dachten" |
| 8 | Optional: Talk-Dateiparameter maskieren | 2, Owner-Scope | Referenz statt Inhalt, bewusst zuletzt |
| 9 | Doku EN/DE/FR (Semantik, Grenze bei geteilten Ordnern, fail-closed-Verhalten, "Ordner taggen statt Dateien") | 7 | Doku sagt das Gemessene |

Schritte 4 und 5 sind nach 3 parallelisierbar (getrennte Dateien, `reg_*`-Prinzip).

---

## Offene Fragen für die discuss-phase

1. **Uploads in `kein-ki`-Ordner** (`files.py:390,435`): verbieten (konsequent, kostet den Roundtrip auch auf Schreibpfaden) oder erlauben (Antwort enthält nur Eigenes)? Das Existenz-Orakel über `ConflictError` spricht für Verbieten.
2. **Zählen oder schweigen** bei ausgeschlossenen Treffern; wenn zählen, eigener Schlüssel statt `skipped` (TOOL-17).
3. **systemtags-App aus = alles Dateiabgeleitete verweigern:** PROJECT.md sagt fail-closed; betrieblich heißt das, der Connector liefert auf so einer Instanz keine Datei mehr. Braucht es einen Admin-Schalter (`NC_MCP_EXCLUDE_TAG=` leer = Feature aus), und ist "aus" dann eine Sicherheitsgrenze, die ein Admin bewusst abschaltet?
4. **Ordner-Tag zugleich freie Ordner-Ausschlussliste** (Owner 04.09.): architektonisch dasselbe Präfix-Set; eine Env-Liste wäre eine zweite Quelle für `tagged_prefixes`, ohne neue Engstelle.
5. **Sandbox-Parität für Findling und Notes** mitnehmen oder als eigenen Backlog-Punkt führen.

## Sources

- Eigener Code, gelesen am 2026-09-26: `src/mcp_connector/nextcloud/clients/dav.py`, `tools/files.py`, `tools/search.py`, `tools/chatgpt.py`, `tools/context.py`, `tools/notes.py`, `tools/talk.py` (574-604), `provider_map.py`, `deps.py` (80-160), `nextcloud/__init__.py`, `server/__init__.py`, `server/reg_*.py`, `errors.py` (20-94), `config.py` (270-313), `nextcloud/capabilities.py`, `tests/contract/test_module_boundaries.py`, `tests/contract/test_tool_surface.py` (HIGH)
- Findling-Provider: `C:/Users/Student/nextcloud-search/php/lib/Search/Provider.php:377-447` (HIGH)
- https://raw.githubusercontent.com/nextcloud/server/master/apps/dav/lib/Connector/Sabre/FilesReportPlugin.php , systemtag-Filter, 412 bei unbekanntem Tag, `nresults`/`firstresult`, Teilbaum-Einschränkung (MEDIUM, gelesen, nicht gemessen)
- https://raw.githubusercontent.com/nextcloud/server/master/apps/dav/lib/SystemTag/SystemTagPlugin.php , `nc:system-tags` auf Dateiknoten mit `canUserSeeTag`-Filter, `nc:object-ids` auf Tag-Knoten (MEDIUM)
- https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html , REPORT `oc:filter-files` (dokumentiert nur `oc:favorite`; systemtag nur im Quelltext) (MEDIUM)
- https://github.com/nextcloud/server/pull/64298 , Vorladen der System-Tag-Properties je PROPFIND (Leistungshinweis für `nc:system-tags`) (LOW, nur Suchtreffer)

---
*Architecture research for: kein-ki Ausschluss-Tag (v1.7, BL-16)*
*Researched: 2026-09-26*

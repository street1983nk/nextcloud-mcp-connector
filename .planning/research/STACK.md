# Stack Research

**Domain:** Nextcloud MCP-only ExApp, Milestone v1.7 "Ausschluss-Tag kein-ki" (BL-16)
**Researched:** 2026-09-26
**Confidence:** HIGH (Quellcode nextcloud/server stable32 bis stable35 gelesen und gedifft, Kernaussagen live gegen die lokale NC 35.0.0 gemessen; einzige MEDIUM-Stelle: AppAPI-Impersonation auf der REPORT-Route, siehe unten)

## Kurzfassung (entscheidungsrelevant)

- **Keine neue Abhängigkeit.** httpx + lxml reichen. Alles läuft über WebDAV (Sabre in `apps/dav`), es gibt **keine OCS-API für System-Tags**.
- **Die gebatchte Route ist `REPORT oc:filter-files` mit `oc:systemtag`** auf `/remote.php/dav/files/{user}/`: ein Roundtrip liefert *alle* direkt getaggten Dateien und Ordner im Sichtbereich des Nutzers, mit Pfad und fileid. Das kostet unabhängig von der Anzahl N der Einträge in der Antwort. Tag-zuerst schlägt Antwort-zuerst.
- **Keine API liefert vererbte Tags.** Weder `nc:system-tags` noch der REPORT noch `nc:object-ids` noch Unified Search kennen Vorfahren (gemessen). Subtree-Semantik baut der Client: Präfixvergleich der Antwortpfade gegen die Pfade der getaggten Ordner. Einen Vorfahren-Walk braucht es dank Tag-zuerst nicht.
- **App systemtags aus: die DAV-API antwortet weiter** (gemessen auf NC 35: REPORT, `nc:system-tags` und Tag-Liste liefern unverändert). Weg sind nur die Capability `systemtags.enabled` und der Unified-Search-Provider `systemtags`. "App aus" ist also kein Fehlerfall der Abfrage.
- **Nichts filtert serverseitig.** Unified Search (`files`, `systemtags`, `notes` ...) liefert getaggte Einträge ungefiltert aus (gemessen). Der Provider `systemtags` liefert sogar genau die getaggten Dateien, wenn jemand nach dem Tag-Namen sucht.
- **Zwei harte Grenzen, die kein Client-Code schließt:** (1) Ein Tag mit Sichtbarkeit `invisible` ist für Nicht-Admins komplett unsichtbar, dann wirkt er stillschweigend nicht (fail-open, gemessen). (2) An Freigabegrenzen reißt die Subtree-Semantik: Wer nur einen Unterordner eines getaggten Ordners geteilt bekommt, sieht den getaggten Vorfahren nicht, und der REPORT ist für ihn leer (gemessen mit bob).

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| httpx | 0.28.x (unverändert) | `PROPFIND` auf `/remote.php/dav/systemtags/`, `REPORT` auf `/remote.php/dav/files/{user}/` | Dieselben Methoden-Aufrufe (`client.request("REPORT", ...)`) wie das vorhandene `SEARCH`/`PROPFIND` in `dav.py`; gleiche Auth (`creds.auth()`), gleiche Statusregeln (`_check`: kein Retry, kein stiller Redirect) |
| lxml | vorhanden | Request-Bodies bauen, Antworten härtet `xml.parse_root` | Body-Bau mit `etree.SubElement` wie bei `build_search_body` (Tag-Id wird Element-Text, nie f-String); `parse_root` trägt XXE/DTD-Schutz |
| Nextcloud WebDAV (Sabre, App `dav`) | NC 32 bis 35 | Einzige API-Fläche für System-Tags | `dav` ist in `core/shipped.json` `alwaysEnabled` (32 und 35 geprüft); `SystemTagPlugin` wird in `apps/dav/lib/Server.php` bedingungslos registriert, `FilesReportPlugin` immer, sobald ein Nutzer angemeldet ist |

### Die Nextcloud-API-Fläche im Detail

Alle Klassen in `apps/dav/lib/SystemTag/` und `apps/dav/lib/Connector/Sabre/FilesReportPlugin.php` sind zwischen stable32 und stable35 **semantisch identisch** (Diff zeigt nur `#[\Override]`, `strict_types`, String-Casts, strikte `in_array`). Eine Implementierung trägt das ganze Versionsfenster.

#### 1. Tag-Namen zu Id auflösen: `PROPFIND /remote.php/dav/systemtags/`

```
PROPFIND /remote.php/dav/systemtags/    Depth: 1
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:prop><oc:id/><oc:display-name/><oc:user-visible/><oc:user-assignable/><d:getetag/></d:prop>
</d:propfind>
```
Antwort (gemessen NC 35): pro Tag ein `d:response` mit href `/remote.php/dav/systemtags/{id}/`, `oc:id` = `1`, `oc:display-name` = `kein-ki-probe`, `oc:user-visible`/`oc:user-assignable` = `true|false`, `d:getetag`. Der erste `d:response` ist die Collection selbst mit 404-propstat (von `parse_multistatus` schon korrekt übersprungen).

- Nicht-Admins sehen nur `visibility=1` (`SystemTagsByIdCollection::getChildren` -> `getAllTags(true)`), Admins alle.
- Namen sind seit `createTag` case-insensitiv eindeutig (`mb_strtolower`-Vergleich, 32 und 35). Instanzen mit Altbestand können trotzdem Dubletten haben. **Regel:** case-insensitiv vergleichen und *alle* passenden Ids einsammeln.
- Kein OCS-Weg: `apps/systemtags/appinfo/routes.php` hat genau eine Route (`/apps/systemtags/lastused`, Index-Route, kein OCS). "OCS systemtags-relations" gibt es nicht, `systemtags-relations` ist eine DAV-Collection.

#### 2. Die gebatchte Route: `REPORT oc:filter-files` mit `oc:systemtag`

```
REPORT /remote.php/dav/files/{user}/    Content-Type: application/xml
<oc:filter-files xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
  <d:prop><oc:fileid/><d:resourcetype/></d:prop>
  <oc:filter-rules><oc:systemtag>{id}</oc:systemtag></oc:filter-rules>
</oc:filter-files>
```
Antwort: `207` Multi-Status, ein `d:response` je **direkt** getaggtem Knoten, href `/remote.php/dav/files/{user}/{pfad}` (Ordner ohne abschließenden Slash im gemessenen Fall), `oc:fileid`, `d:resourcetype` mit `d:collection` für Ordner. Genau diesen Aufruf macht das Nextcloud-Frontend selbst (`apps/systemtags/src/services/systemtags.ts`, `formatReportPayload`).

Verhalten aus Quelle und Messung:
- **Nur direkte Zuordnung.** Getaggter Ordner `/probe-kk/tagged`: der REPORT liefert nur diesen Ordner, nicht `direct.txt` oder `sub/deep.txt` darunter (gemessen).
- **Zielordner wird für systemtag ignoriert.** `processFilterRulesForFileNodes` ruft `userFolder->searchBySystemTag()` über den ganzen Nutzerbaum; ein REPORT auf `/probe-kk/tagged/sub` lieferte trotzdem `/probe-kk/tagged` (gemessen). Immer auf die Home-Wurzel schicken und lokal filtern.
- **Freigaben inklusive**, in der Pfadsicht des Empfängers (Suche läuft über alle Mounts des Nutzers).
- **Mehrere `oc:systemtag`-Regeln = UND (Schnittmenge)**, nicht ODER. Bei mehreren passenden Ids: ein REPORT je Id (parallel mit `asyncio.gather`).
- **Unbekannte oder für den Nutzer unsichtbare Id -> `412`**, Body `<s:message>Cannot filter by non-existing tag</s:message>` (gemessen, Id 999 und `invisible`). Kein Treffer = `207` mit leerem Multi-Status.
- **Ohne `d:limit` keine Kappung** (dbLimit 0). Das ist hier gewollt: eine gekappte Tag-Menge wäre fail-open.
- Kosten gemessen (NC 35 lokal, 6 Läufe): REPORT 0,24 bis 0,26 s, identisch zum PROPFIND-Depth-1 der Home-Wurzel (0,25 bis 0,27 s). Der Boden ist der PHP-Bootstrap pro Request, nicht die Tag-Abfrage. Kleiner Datenbestand, Messung mit realistischer Tag-Menge gehört in die Phase (BL-16-Kostennotiz).

#### 3. `nc:system-tags` als PROPFIND-/SEARCH-Eigenschaft

```
<nc:system-tags>
  <nc:system-tag oc:can-assign="true" oc:id="1" oc:user-assignable="true"
                 oc:user-visible="true" nc:color="">kein-ki-probe</nc:system-tag>
</nc:system-tags>
```
- Liefert **nur die eigenen Tags** des Eintrags (Kinder des getaggten Ordners: leeres `<nc:system-tags/>`, gemessen).
- Im PROPFIND Depth 1 serverseitig gebatcht (`preloadCollection` holt Ordner plus Kinder in einem `getTagIdsForObjects`), in SEARCH-Antworten ebenfalls wählbar (gemessen), dort pro Treffer ein DB-Lookup, aber weiterhin ein HTTP-Roundtrip. Messbar teurer war es nicht.
- **Parser-Falle:** `xml.parse_multistatus` flacht strukturierte Properties zu Kind-Tag-Namen ab (`_value_of`), Namen und `oc:id`-Attribute gingen verloren. Wer die Eigenschaft liest, braucht einen eigenen Leser auf `xml.parse_root`.
- **Nicht als Kernmechanismus verwenden** (keine Vorfahren). Höchstens als billige Gegenprobe in Listings, falls die discuss-phase Verteidigung in der Tiefe will.

#### 4. Weitere Routen, die es gibt, die wir aber nicht brauchen

| Route | Liefert | Warum nicht |
|-------|---------|-------------|
| `PROPFIND /remote.php/dav/systemtags/{id}/files` mit `nc:object-ids` (NC 31+) | Liste von fileids, serverseitig per `getFirstNodeById` auf den Nutzer gefiltert | Nur Ids, keine Pfade, also keine Subtree-Prüfung ohne N weitere Lookups. Serialisierung ist zudem verschachtelt gleichnamig (`<nc:object-ids><nc:object-ids><nc:id>681</nc:id><nc:type>files</nc:type></nc:object-ids></nc:object-ids>`, gemessen) |
| `PROPFIND /remote.php/dav/systemtags-relations/files/{fileid}` Depth 1 | Tags einer einzelnen Datei | Ein Roundtrip pro Datei, genau das Muster, das das Latenzbudget reißt |
| DAV `SEARCH` mit `where systemtag` | nichts | `FileSearchBackend::getPropertyDefinitionsForScope` exponiert keine System-Tag-Eigenschaft (nur `oc:tags`/Favoriten der Nutzer-Tags); intern kann `SearchBuilder` `systemtag`, DAV reicht es nicht durch |
| Unified Search Provider `systemtags` (`/ocs/v2.php/search/providers/systemtags/search?term=kein-ki`) | getaggte Dateien mit `fileId`/`path` | LIKE-Suche auf den Namen, paginiert, verschwindet mit der App; als Tag-Quelle unzuverlässig. **Aber:** als Leck relevant, siehe unten |
| Capability `systemtags.enabled` (`/ocs/v2.php/cloud/capabilities`) | `{"enabled": true}` oder fehlt | Sagt nur, ob die UI-App an ist; die DAV-API antwortet auch ohne sie. Höchstens Hinweistext |

### Antworten auf die sieben Fragen

| Frage | Antwort | Beleg |
|-------|---------|-------|
| (1) OCS systemtags / systemtags-relations | Existiert nicht als OCS. Beides sind DAV-Collections unter `/remote.php/dav/` (`systemtags`, `systemtags-relations`, `systemtags-assigned`), registriert in `apps/dav/lib/RootCollection.php` ohne App-Prüfung. Auth = normale DAV-Auth des Nutzers | Quelle 32/35, live |
| (2) PROPFIND `nc:system-tags` + `oc:fileid` | Funktioniert, nur direkte Tags, Form siehe oben; Depth 1 serverseitig gebatcht | Quelle, live |
| (3) REPORT files-by-tag | `oc:filter-files` + `oc:systemtag`, ganzer Nutzerbaum, direkte Zuordnungen, 412 bei unbekannter Id | Quelle, Frontend-Code, live |
| (4) Batching | **REPORT tag-zuerst**: 1 Roundtrip je Tool-Antwort (plus einmalige, cachebare Namensauflösung), unabhängig von N | live gemessen |
| (5) Subtree | Keine API vererbt. Vererbung existiert nur intern in `workflowengine/lib/Check/FileSystemTags.php` (läuft die Eltern im Storage-Cache ab, für Zugriffsregeln), nicht als Lese-API. Client prüft Präfixe | Quelle, live |
| (6) systemtags aus | DAV-API unverändert (Tag-Manager/Mapper sind Core, `OC\SystemTag`); Capability und Suchprovider `systemtags` weg | Quelle, live NC 35 |
| (7) Filtert Unified Search? | Nein. `FilesSearchProvider` hat keinen Tag-Filter (Filter: term, since, until, person, min/max-size, mime, type, path, is-favorite, title-only); getaggte und darunterliegende Dateien kommen mit `attributes.fileId`/`attributes.path` zurück | Quelle, live |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (keine neue) | | | Alles Nötige ist in `dav.py`/`xml.py` angelegt |

### Integrationspunkte im vorhandenen Code

- `clients/dav.py`: zwei neue Funktionen im Stil von `build_fileid_body`/`find_by_fileid`:
  - `resolve_tag_ids(client, creds, name) -> list[str]`: PROPFIND Depth 1 auf `f"{creds.base_url}/remote.php/dav/systemtags/"`, Body per lxml, `xml.parse_multistatus` genügt hier (alle Werte sind Blätter), case-insensitiver Namensvergleich.
  - `tagged_paths(client, creds, tag_id) -> list[(path, fileid, is_collection)]`: REPORT auf `files_url(creds, "/")`-Wurzel (**ohne** `safe_path`-Umbiegung auf `NC_MCP_FILES_ROOT`), Body per lxml, Tag-Id vorher gegen `_DIGITS` geprüft.
- **Nicht `parse_entries` für die Tag-Menge nehmen**: es verwirft alles außerhalb von `in_files_root`. Liegt der getaggte Ordner *oberhalb* der konfigurierten Sandbox-Wurzel (z. B. `/` oder `/Arbeit` bei Root `/Arbeit/Projekte`), fiele genau der entscheidende Vorfahr heraus: fail-open. Die Tag-Menge braucht `_home_path_of` ohne Sandbox-Filter; Hrefs außerhalb des eigenen Homes bleiben verworfen.
- `_check` für die neuen Aufrufe erweitern oder eigene Übersetzung: `412` beim REPORT heißt "Tag unbekannt oder unsichtbar" und ist **kein** leerer Treffer.
- `clients/ocs.py` (`provider_search`): keine API-Änderung; die Filterung passiert auf `attributes.path`/`attributes.fileId` der Einträge nach dem Aufruf. Der Provider `systemtags` (falls die Registry ihn zulässt) muss mitgefiltert werden, sonst listet eine Suche nach "kein-ki" die geschützten Dateien.
- Notes sind Dateien (Note-Id = fileid, liegen im Notes-Ordner): der fileid-Satz aus dem REPORT deckt sie direkt ab, der Pfad-Präfix deckt getaggte Kategorie-Ordner ab.
- Timeout/Degradation: dieselbe Budget- und `degraded`-Mechanik wie die anderen Beine von `prepare_context`; fällt der REPORT aus (Timeout, 5xx, 405, unerwarteter Body), werden alle dateibezogenen Einträge der Antwort zurückgehalten.

## Installation

```bash
# Nichts zu installieren. pyproject.toml und uv.lock bleiben unverändert.
uv sync
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| REPORT tag-zuerst (1 Roundtrip, ganze Tag-Menge) | `nc:system-tags` in jede vorhandene PROPFIND/SEARCH-Abfrage mitnehmen (0 zusätzliche Roundtrips) | Nur als Zusatz für direkte Tags. Allein reicht es nicht: Vorfahren fehlen, ein Vorfahren-Walk kostet einen PROPFIND pro Pfadebene |
| Tag-Menge pro Tool-Antwort frisch holen | Tag-Menge über Aufrufe cachen, validiert per `d:getetag` von `/systemtags/{id}` | Der Tag-ETag ändert sich bei Zuordnen/Entfernen (`updateEtagForTags`), **nicht** beim Verschieben/Umbenennen eines getaggten Ordners. Ein Pfad-Cache würde nach einem Rename fail-open. Cachen nur die Namensauflösung Name -> Id (kurze TTL, bei 412 neu auflösen) |
| Client-seitige Filterung im Connector | Serverseitige Durchsetzung über `files_accesscontrol` (Regel "System-Tag kein-ki" + Bedingung) | Sperrt den Zugriff auch für den Nutzer selbst bzw. braucht Admin-Regelwerk und eine Fremd-App; passt eher zur späteren Enterprise-Governance als zur freien Grundfunktion |
| Roh-httpx | `nc_py_api` (`nc.files` bietet Tag-Listen und Kriterien-Listing über denselben REPORT, LOW confidence, nicht geprüft) | Nie im Hot Path; gleiche Route, zusätzliche Abhängigkeit, Projektregel "kein nc_py_api im Hot Path" |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Pro-Datei-Lookups über `systemtags-relations/files/{fileid}` | N Roundtrips je Antwort, sprengt das Latenzbudget | Ein REPORT je Tag-Id |
| Capability `systemtags` als Schalter "Tag-Prüfung möglich ja/nein" | Die DAV-API antwortet auch bei deaktivierter App (gemessen); ein Fail-closed auf die Capability würde auf solchen Instanzen jede Datei-Antwort leeren, obwohl die Prüfung beantwortbar ist | Erfolg oder Misserfolg des REPORT selbst entscheidet |
| `parse_multistatus` für `nc:system-tags` oder `nc:object-ids` | Flacht strukturierte Werte ab | Eigener Leser auf `xml.parse_root` |
| Mehrere `oc:systemtag` in einem REPORT | UND-Verknüpfung, liefert die Schnittmenge | Ein REPORT je Id |
| REPORT mit `d:limit` | Gekappte Tag-Menge = unerkannt ungeschützte Dateien | Ohne Limit abfragen; bei unplausibler Größe degradieren statt kappen |
| Unified-Search-Provider `systemtags` als Tag-Quelle | App-abhängig, LIKE-Suche, paginiert | REPORT |
| Tag-Schreibpfade (POST `/systemtags/`, PUT/DELETE auf `systemtags-relations`) | Ein Agent, der den Tag entfernen kann, hebelt die Grenze aus; gehört nicht in den Connector | Nur lesen; AST-Grep-Gate um diese Pfade erweitern |

## Stack Patterns by Variant

**Tag hat Sichtbarkeit `public` (kollaborativ) oder `restricted`:**
- REPORT und Tag-Liste funktionieren für alle Nutzer (beide gemessen; `restricted` = sichtbar, nur Admins/Gruppen dürfen zuordnen)
- `restricted` ist für Organisationen die bessere Wahl: Nutzer können den Tag nicht selbst entfernen

**Tag hat Sichtbarkeit `invisible`:**
- Für Nicht-Admins fehlt der Tag in der Liste, `nc:system-tags` ist leer, REPORT antwortet 412 (gemessen). Der Connector kann ihn nicht sehen, der Schutz wirkt nicht
- Doku muss das als Admin-Regel nennen; der Connector kann "kein Tag namens kein-ki sichtbar" nicht von "Tag existiert unsichtbar" unterscheiden

**Kein Tag `kein-ki` sichtbar vorhanden:**
- Niemand kann etwas getaggt haben, das der Nutzer sieht (bis auf `invisible`): kein Ausschluss nötig, kein Degradationsfall. Ob die Antwort das benennt, ist eine discuss-phase-Frage

**ExApp-Modus (AppAPI-Impersonation) vs. App-Passwort:**
- Beide nutzen denselben Sabre-Server; `FilesReportPlugin` wird registriert, sobald eine Nutzersitzung existiert. Die Messung lief mit App-Passwort; **den REPORT einmal im ExApp-Container über AppAPI verproben** (MEDIUM, bis gemessen)

## Version Compatibility

| Komponente | Kompatibel mit | Notes |
|------------|----------------|-------|
| `oc:filter-files` + `oc:systemtag` | NC 32, 33, 34, 35 | `FilesReportPlugin.php` 32 vs 35: nur Attribute/strikte Vergleiche geändert |
| `nc:system-tags`, `/systemtags/`, `systemtags-relations` | NC 32 bis 35 | `SystemTagPlugin.php` 32 vs 35: Casts, `sanitizeWordsAndEmojis` beim Anlegen (NC 35), sonst gleich |
| `nc:object-ids` | NC 31+ | Nicht genutzt |
| Case-insensitive Namenseindeutigkeit | NC 32 bis 35 (in `createTag`) | Altbestände können Dubletten haben |
| Tag-ETag ändert bei Zuordnung | NC 32 bis 35 (`SystemTagObjectMapper::updateEtagForTags`) | Nicht bei Move/Rename |

## Sources

- github.com/nextcloud/server, Branches stable32, stable33, stable34, stable35 (per `gh api` geladen und gedifft), HIGH:
  - `apps/dav/lib/SystemTag/SystemTagPlugin.php` (Property-Namen, `preloadCollection`, `object-ids`)
  - `apps/dav/lib/SystemTag/SystemTagList.php`, `SystemTagsObjectList.php` (XML-Form)
  - `apps/dav/lib/SystemTag/SystemTagsByIdCollection.php`, `SystemTagsRelationsCollection.php`, `SystemTagsObjectTypeCollection.php`, `SystemTagsObjectMappingCollection.php`, `SystemTagNode.php`, `SystemTagObjectType.php`
  - `apps/dav/lib/Connector/Sabre/FilesReportPlugin.php` (REPORT-Logik, 412, UND-Semantik, Scope)
  - `apps/dav/lib/Server.php`, `apps/dav/lib/RootCollection.php` (bedingungslose Registrierung)
  - `apps/dav/lib/Files/FileSearchBackend.php` (keine systemtag-Eigenschaft in SEARCH)
  - `lib/private/SystemTag/SystemTagManager.php`, `SystemTagObjectMapper.php`, `lib/private/Files/Cache/QuerySearchHelper.php`, `SearchBuilder.php`, `lib/private/Files/Node/Folder.php`
  - `apps/systemtags/appinfo/routes.php`, `lib/Capabilities.php`, `lib/Search/TagSearchProvider.php`, `src/services/systemtags.ts`, `src/services/api.ts`
  - `apps/files/lib/Search/FilesSearchProvider.php`, `apps/workflowengine/lib/Check/FileSystemTags.php`
  - `core/shipped.json` (`dav` alwaysEnabled, `systemtags` nur defaultEnabled)
- Live-Messung 2026-09-26 gegen lokale NC 35.0.0 (`nc35-nc`, via Caddy :8082), Konten alice/bob, Wegwerf-Tag `kein-ki-probe`, Wegwerf-App-Passwörter; alles danach entfernt (Share, Tag, Dateien, Tokens), App systemtags wieder aktiv. HIGH für NC 35, für 32 bis 34 über den Quell-Diff abgesichert
- https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html: dokumentiert `oc:filter-files` nur für Favoriten und `oc:fileid`; System-Tag-Filter und `nc:system-tags` stehen nicht in der Entwicklerdoku (Quellcode ist die Referenz), MEDIUM
- https://docs.nextcloud.com/server/stable/user_manual/en/files/tagging.html und help.nextcloud.com-Threads zu Tag-Vererbung: Vererbung existiert nur über Workflow/Automated Tagging, nicht als API, MEDIUM

---
*Stack research for: kein-ki-Ausschluss-Tag im Nextcloud MCP Connector*
*Researched: 2026-09-26*

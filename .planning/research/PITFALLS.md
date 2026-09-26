# Pitfalls Research

**Domain:** Einem bestehenden MCP-Server mit Berechtigungs-Durchgriff ("der Assistent sieht nie mehr als der angemeldete Nutzer"), vorhandener Sandbox (`NC_MCP_FILES_ROOT`, PR #8), Graceful-Degradation-Konvention (`degraded`-Einträge), Tool-Byte-Budget (15712/18000) und hash-verkettetem Audit-Log einen Ausschlussfilter über das System-Tag `kein-ki` beibringen (v1.7, BL-16)
**Researched:** 2026-09-26
**Confidence:** HIGH für alles, was den Code-Stand dieses Repos betrifft (`nextcloud/clients/dav.py`, `tools/search.py`, `tools/chatgpt.py`, `tools/context.py`, `tools/files.py`, `tools/talk.py`, `tests/contract/*` direkt gelesen). MEDIUM-HIGH für das Nextcloud-Tag-Verhalten: aus der Server-Quelle `master` gelesen (`SystemTagManager.php`, `SystemTagPlugin.php`, `SystemTagNode.php`, `SystemTagMappingNode.php`, `SystemTagsObjectMappingCollection.php`, `FilesReportPlugin.php`, `apps/systemtags/lib/Search/TagSearchProvider.php`, `apps/dav/lib/Server.php`), aber NICHT gegen NC 32 bis 35 gemessen; `master` kann vom Store-Fenster abweichen. MEDIUM für Speicher-Sonderfälle (Group-/Team-Folders, External Storage, speicherübergreifendes Verschieben): Allgemeinwissen über fileid-gebundene Metadaten, nicht gemessen. LOW, wo ausdrücklich markiert.

## Vorbemerkung: drei Quellbefunde, die mehrere Pitfalls tragen

1. **Tags hängen an der fileid, nicht am Pfad, und vererben nicht.** Nextcloud kennt keine Subtree-Semantik. "Ein Tag auf einem Ordner deckt alles darunter" ist reine Connector-Logik und muss für jede Antwort die Vorfahren prüfen.
2. **Der `oc:filter-files`-REPORT mit `oc:systemtag` löst die Tag-Id auf und sucht dann über den Tag-NAMEN im ganzen Nutzerbaum** (`$this->userFolder->searchBySystemTag($tagName, ...)`), unabhängig vom Zielpfad des REPORT. Eine unbekannte oder unsichtbare Tag-Id wirft `PreconditionFailed` ("Cannot filter by non-existing tag", HTTP 412), liefert also KEINE leere Liste.
3. **Der DAV-Tag-Plugin ist in `apps/dav` unbedingt registriert** (`Server.php`: `addPlugin(SystemTagPlugin)`). "App systemtags aus" versteckt UI und Unified-Search-Provider, die Zuordnungen bleiben in der Datenbank und sind per DAV vermutlich weiter lesbar. MEDIUM, in der Messphase zu belegen.

---

## Critical Pitfalls

### Pitfall 1: Der Filter sitzt im Tool statt an der Datenkante, und die zweite Familie vergisst ihn

**What goes wrong:**
Der Ausschluss wird in `files_list` und `files_read` eingebaut, und dann liefert ein anderer Weg dieselbe Datei doch aus. In diesem Repo gibt es mindestens neun solche Wege:
- `fetch` im ChatGPT-Profil (`reg_chatgpt.py`, `chatgpt._fetch_file`): `file:<fileid>` löst über `dav.find_by_fileid` auf, eine vor dem Taggen gemerkte fileid kommt also an jedem Listing-Filter vorbei.
- `search` im ChatGPT-Profil und `unified_search`: Titel, Subline und URL eines Treffers sind schon Inhalt (Dateiname, Ordnerpfad).
- `prepare_context`: `_excerpts` ruft `chatgpt.fetch` auf. Das ist gut (eine Stelle), aber die Trefferliste mit Titel und Subline steht VOR dem Excerpt schon in der Antwort, und ein abgelehnter Excerpt erscheint heute als `degraded`-Eintrag mit `source: "file:123"`. Die Existenz des Treffers wäre damit bestätigt.
- Der Unified-Search-Provider **`systemtags`** (Quelle `TagSearchProvider.php`): eine Suche nach "kein" liefert das Tag selbst UND alle Dateien mit diesem Tag, mit den Attributen `fileId` und `path`. Ohne Gegenmaßnahme ist `unified_search("kein-ki")` die bequemste Liste genau der ausgeschlossenen Dateien.
- Der Content-Provider **`findling`** (`CONTENT_PROVIDERS = {"findling"}`): liefert Inhaltsausschnitte aus einem Index, der die getaggten Dateien schon enthält.
- **Notes**: Notizen sind Dateien unter `/Notes`, die Notes-REST-API umgeht jede Datei-Logik. Ein getaggter Ordner `/Notes/Privat` wäre über `notes_read` vollständig lesbar. (Die Notes-Id ist nach Allgemeinwissen die fileid; LOW, in der Messphase belegen.)
- **Talk**: `tools/talk.py` setzt `messageParameters` in Platzhalter ein; eine im Chat geteilte Datei erscheint mit Namen (und ggf. Pfad/Link).
- `files_download` (Embedded Resource) und `files_search` (DAV SEARCH).
- Später: `files_update` aus dem Community-PR (Design-Issue #9, Daniel/simul8). Ein Update auf eine unsichtbare Datei wäre ein Schreibzugriff auf Inhalt, den der Assistent nicht sehen darf.

**Why it happens:**
Der Filter wird dort gebaut, wo das Feature beschrieben ist ("Datei-Listings"), nicht dort, wo Dateidaten den Server verlassen. Jede Familie hat ihren eigenen Client (`notes.py`, `talk.py`, `ocs.py`), und die Sandbox aus PR #8 zeigt das Muster schon: `in_files_root` wirkt in `parse_entries` und separat in `_entry_in_files_root`, also an zwei Stellen, die man beide kennen muss.

**How to avoid:**
- Ein eigenes Modul (Vorschlag `exclusion.py`) mit genau einer Entscheidungsfunktion pro Antwort, z. B. `ExclusionSet.excludes(path, fileid) -> bool`, gebaut einmal pro Tool-Aufruf.
- Anwendung an der Datenkante: `parse_entries`-Ergebnisse, `find_by_fileid`, Unified-Search-Normalisierung (`_normalise`), Notes-Einträge, Talk-Dateiparameter. Nicht in den Tool-Funktionen.
- Provider `systemtags` in `unified_search` entweder komplett abwählen oder jeden Eintrag mit `fileId`/`path` durch den Filter schicken und die Tag-Einträge selbst verwerfen. Jeder Provider, der `attributes.path` oder `attributes.fileId` trägt, ist ein Datei-Provider, gleich wie er heißt.
- **Contract-Gate "Kanarienvogel" über die aktive Registry** (unabhängiges Prüfmuster, nicht das Muster der Umsetzung): MockTransport-Nextcloud, in der JEDE Datei und JEDER Ordner `kein-ki` trägt und Name wie Inhalt ein eindeutiges Kanarienwort enthalten (`CANARY-7f3a` im Dateinamen, im Ordnernamen, im Inhalt, in einer Notiz, in einem Talk-Dateiparameter, in einem Findling- und einem systemtags-Treffer). Jedes registrierte Tool wird mit plausiblen Argumenten aufgerufen (Listing, Suche nach dem Kanarienwort, fetch mit bekannter fileid, prepare_context). Assertion: das Kanarienwort steht in keiner Antwort und in keinem Fehlertext, auch nicht in `degraded`.
- **Klassifikations-Freeze wie `test_tool_surface.py`**: eine Tabelle "Tool -> datei-tragend ja/nein, Guard-Stelle". Ein neues Tool ohne Zeile lässt den Test scheitern. Damit fällt `files_update` automatisch in das Gate, sobald der Community-PR es registriert.
- Optional AST-Gate nach dem Muster von `test_no_destructive_calls.py`: Aufrufe von `dav.parse_entries`, `find_by_fileid`, `propfind_children`, `dav.search` außerhalb der zugelassenen Module schlagen fehl. Kommentare und Docstrings vorher entfernen wie im bestehenden Gate.

**Warning signs:**
- Ein PR ändert `tools/files.py`, aber nicht `tools/chatgpt.py`, `tools/search.py`, `tools/notes.py`.
- Tests für den Ausschluss liegen nur in `test_files_list.py`.
- Der Kanarientest braucht pro Tool eine Sonderregel ("hier nicht prüfen").

**Phase to address:** Guard-Kern-Phase (Modul + Datenkante) und eine eigene Gate-Phase VOR der Doku; der Kanarientest ist das Abnahmekriterium des Milestones.

---

### Pitfall 2: Integration mit der Sandbox, der Tag auf dem Vorfahren des Roots geht verloren

**What goes wrong:**
Mit `NC_MCP_FILES_ROOT=/Team/Projekt` und `kein-ki` auf `/Team`: die Tag-Abfrage liefert den Eintrag `/Team`, er läuft durch das vorhandene `parse_entries`, und das wirft alles außerhalb des Roots weg (`if path is None or not in_files_root(path): continue`). Der Vorfahr verschwindet, der ganze Root gilt als ungeschützt. Fail-open, und zwar genau in der Konfiguration, die Admins als "zusätzlich abgesichert" empfinden.
Zweiter Fall: `_entry_in_files_root` beginnt mit `if root == "/": return True`. Wer die Tag-Prüfung dort anhängt, prüft im Standardbetrieb (Root `/`) nie.
Dritter Fall: Pfadformen. `safe_path` bildet virtuelle Pfade (`/scan.pdf` meint `/Team/Projekt/scan.pdf`), `in_files_root` prüft absolute Home-Pfade. Ein Präfixvergleich zwischen einem virtuellen Kandidaten und absoluten Tag-Pfaden trifft nie.

**Why it happens:**
Wiederverwendung des vorhandenen Parsers ist der naheliegende Weg, und dessen Sandbox-Kontrakt ("was außerhalb liegt, ist keine Antwort") ist für die Tag-Menge falsch: dort sind gerade die Vorfahren relevant.

**How to avoid:**
- Die Tag-Abfrage bekommt einen eigenen Parser, der absolute Home-Pfade liefert und nur fremde Konten verwirft (`_home_path_of`), nicht Vorfahren des Roots.
- Alle Vergleiche auf absoluten Home-Pfaden, mit Segmentgrenze (`p == t or p.startswith(t + "/")`; `/Team2` ist nicht unter `/Team`).
- Reihenfolge fest: erst Sandbox, dann Ausschluss; beide unabhängig, keiner verlässt sich auf eine Frühausstiegsbedingung des anderen.
- Tests als Matrix: Root `/` und Root `/A/B`; Tag auf `/A`, `/A/B`, `/A/B/C`, `/A/B/C/datei`, `/A2`. Erwartung je Zelle explizit.

**Warning signs:**
- Die Tag-Logik ruft `parse_entries` oder `in_files_root` auf.
- Es gibt keinen Test mit gesetztem `NC_MCP_FILES_ROOT` und Tag oberhalb des Roots.

**Phase to address:** Guard-Kern-Phase; die Matrix gehört in dieselbe Phase wie der Parser.

---

### Pitfall 3: Fail-open durch den Normalfall "kein Tag gefunden"

**What goes wrong:**
Mehrere Zustände sehen für den Connector aus wie "niemand hat `kein-ki` vergeben", sind es aber nicht:
- **Unsichtbares Tag**: `canUserSeeTag` liefert für Nicht-Admins `false`, `getTagsForFile` filtert es aus `nc:system-tags`, der REPORT wirft 412. Ein Admin, der `kein-ki` als "invisible" anlegt (weil es ja nur eine Markierung sein soll), schützt für niemanden etwas.
- **Veraltete Tag-Id aus einem Cache**: Tag gelöscht und neu angelegt hat eine neue Id; der REPORT auf die alte wirft 412. Wer 412 wie "leer" behandelt oder die alte Id weiter nutzt, filtert nichts.
- **Negatives Caching**: "Tag existiert nicht" wird gemerkt, jemand legt es an und taggt, der Connector filtert bis zum Ablauf nichts.
- **App `systemtags` deaktiviert**: Capability fehlt, aber (laut Quelle) die Zuordnungen und der DAV-Plugin nicht. Wer "App aus" als "Feature aus, alles zeigen" liest, gibt früher getaggte Dateien wieder frei.
- **Mehrere gleichnamige Tags** aus Altbeständen (siehe Pitfall 7): der Connector nimmt das erste, die Nutzer haben das zweite vergeben.

**Why it happens:**
"Nichts gefunden" und "nicht abfragbar" landen im selben leeren Ergebnis, weil beide Wege die Menge der ausgeschlossenen Einträge leer lassen.

**How to avoid:**
- Drei Zustände explizit modellieren: `NO_TAG` (Tag existiert sichtbar nicht, nichts auszuschließen), `SET(ids, paths)` (ermittelt), `UNKNOWN(reason)` (nicht abfragbar). Nur `UNKNOWN` löst Degradation aus; 412 auf eine Id ist `UNKNOWN` bzw. Anlass zur Neuauflösung im selben Aufruf, nie `NO_TAG`.
- Kein Cache über Aufrufe hinweg für die Ausschlussmenge, kein negatives Caching für die Tag-Existenz. Ein Id-Cache nur, wenn 412 ihn im selben Aufruf invalidiert und neu auflöst (Budget beachten).
- Nicht auf die Capability `systemtags` gaten. Immer per DAV fragen; ein DAV-Fehler ist `UNKNOWN`.
- Alle sichtbaren Tags mit normalisiertem Namen `kein-ki` einsammeln (Vereinigungsmenge), nicht das erste.
- Unsichtbare Tags sind aus Nutzersicht nicht erkennbar; das ist eine Doku- und Prüfaufgabe: `occ mcp_connector:exclusion:check` (nach dem Muster von `exchange:check`) läuft mit Admin-Sicht und meldet "kein-ki existiert als unsichtbares Tag, wirkt für niemanden".

**Warning signs:**
- Code wie `if response.status_code == 412: return frozenset()`.
- Ein Modul-Dict als Tag-Cache (fällt übrigens schon unter das Gate "kein modulweiter veränderlicher Zustand", D-20, in `test_no_destructive_calls.py`).
- Kein Test für "Tag unsichtbar", "Tag neu angelegt", "App aus".

**Phase to address:** Messphase (412-Verhalten, App-aus-Verhalten auf NC 32 und 35 messen) und Guard-Kern-Phase (Drei-Zustands-Modell); `occ`-Check in der Doku-/Betriebsphase.

---

### Pitfall 4: Fail-closed zu breit oder zu schmal, und prepare_context kippt ganz

**What goes wrong:**
- Zu breit: bei `UNKNOWN` wird die ganze Antwort zum Fehler, auch Termine, Mail-Zähler, Talk-Digest. `prepare_context` hat eine Bedingung "alle Beine leer und degradiert -> Fehler" (`context.py`, Zeile ~265); wenn der Datei-Ausfall die Suchtreffer leert und die anderen Beine zufällig leer sind, wird aus einer Teil-Degradation ein Totalausfall.
- Zu schmal: bei `UNKNOWN` werden nur die Einträge zurückgehalten, die "verdächtig" aussehen, oder nur die Dateitreffer, während Notizen, Talk-Dateinamen und Findling-Ausschnitte weiterlaufen.
- Existenz-Orakel im Ausfall: `fetch("file:999")` (existiert nicht) antwortet "no file with the id", `fetch("file:123")` (existiert) antwortet "exclusion check unavailable". Der Ausfall verrät, welche Ids existieren.

**Why it happens:**
Die Reihenfolge "erst auflösen, dann prüfen" ist natürlich, erzeugt aber zwei verschiedene Fehler je nach Existenz.

**How to avoid:**
- Regel: bei `UNKNOWN` werden ALLE datei-tragenden Einträge zurückgehalten (Dateien, Notizen, Findling, systemtags-Provider, Talk-Dateiparameter werden geschwärzt), alle anderen Familien bleiben unberührt. Das ist "nur betroffene Einträge", weil ohne Antwort jede Datei betroffen ist.
- `degraded`-Eintrag nach bestehender Form (`{"source": ..., "reason": ...}`, ein Satz, "was passiert ist, nie wer wir sind"), z. B. `source: "exclusion"`, Grund ohne Pfade, ohne Ids, ohne Zahl ausgeschlossener Einträge.
- Die Ausschlussabfrage läuft VOR bzw. unabhängig von der Existenzauflösung; bei `UNKNOWN` antwortet `fetch` für jede Datei-Id (existent, getaggt, nicht existent) byte-gleich.
- In `prepare_context` zählt der Datei-Ausschluss-Ausfall als eigenes `degraded`-Bein und nicht in die "alles leer"-Bedingung (der Code-Kommentar dort sagt schon: ein später hinzugefügtes Bein gehört unter `degraded`, nicht in diese Bedingung).
- Eigenes Zeitbudget für die Ausschlussabfrage, parallel zu Suche/Terminen gestartet, nicht davor.

**Warning signs:**
- Ein Test "systemtags-Ausfall" prüft nur `files_list`.
- `fetch` ruft `find_by_fileid` vor der Ausschlussabfrage auf und hat zwei verschiedene Fehlertexte.
- `prepare_context` wird im Ausfalltest zum `ToolError`.

**Phase to address:** Degradations-/Integrationsphase (Suche, prepare_context, ChatGPT-Profil); Byte-Gleichheitstests für den Ausfall in derselben Phase.

---

### Pitfall 5: Informationslecks, die zeigen, dass es eine ausgeschlossene Datei gibt

**What goes wrong:**
Der Inhalt ist weg, aber die Existenz nicht:
- **Zähler**: `unified_search` führt `skipped` (Sandbox-Abwürfe und kaputte Einträge). Zählt man Ausschlüsse dort mit, sagt `skipped: 1` bei der Suche "Gehalt", dass es eine passende, ausgeschlossene Datei gibt.
- **Paging**: `files_list`/`files_search` schneiden `children[offset : offset + capped]` und prüfen "one more than the window". Filtert man NACH dem Fenster, hat Seite 1 weniger als `limit` Einträge trotz `next`, oder `count` passt nicht zum Rest; filtert man VOR, aber DAV SEARCH hat selbst ein Limit, wirkt die Suche erschöpft, obwohl weitere ungetaggte Treffer existieren.
- **Fehlertexte**: `fetch` auf ausgeschlossene Id mit eigenem Text ("excluded by tag") statt dem vorhandenen "This account has no file with the id {fileid}." samt Hint; `files_read`/`files_list` auf ausgeschlossenen Pfad mit anderem Text als bei 404; `files_search` mit ausgeschlossenem `folder`.
- **Upload-Orakel**: `files_upload` ist create-only; ein Upload auf den Namen einer ausgeschlossenen Datei endet mit "A file already exists at {path}" (412). Das ist systembedingt und nicht vollständig vermeidbar, ohne Schreiben in fremde Namen zu verbieten.
- **excerpt-degraded**: siehe Pitfall 1, `source: "file:123"`.
- **Byte-Budget/Beschreibungen**: eine Tool-Beschreibung, die dynamisch sagt "3 Dateien ausgeblendet", ist ein Leck und kostet Budget.
- **Timing** (gering): ausgeschlossene Pfade kosten einen Roundtrip mehr als nicht existierende.

**Why it happens:**
Die Degradationskonvention des Projekts ("jede Kappung wird benannt, fünf ist nie alle") ist richtig für Ausfälle und Kappungen, aber falsch für einen erfolgreichen Ausschluss. Wer sie mechanisch anwendet, benennt den Ausschluss.

**How to avoid:**
- Leitsatz nach der Byte-gleich-401-Disziplin des Exchange-Pfads: **ein erfolgreicher Ausschluss ist byte-gleich zur Nichtexistenz.** Benannt wird nur `UNKNOWN`.
- Testbar als Paartest pro datei-tragendem Tool: Fixture A (Datei existiert, getaggt), Fixture B (Datei existiert nicht); JSON-Antworten und Fehlertexte müssen byte-gleich sein. Für Ordner: getaggter Ordner vs. nicht existierender Ordner.
- Der Ausschluss wirkt, bevor ein Fehlertext entsteht: `find_by_fileid` liefert für eine ausgeschlossene Datei `None`, dadurch kommt der Text aus demselben Zweig wie heute. Kein neuer Fehlertext für den Ausschluss.
- `skipped` zählt Ausschlüsse NICHT. (Offene Frage für die discuss-phase: zählt `skipped` heute schon Sandbox-Abwürfe? Ja, `_normalise` zählt sie mit. Ob das seinerseits ein Leck ist, ist ein Nachzieher, kein v1.7-Umbau.)
- Filtern vor dem Fenstern; bei `files_search` so lange nachfordern, bis das Fenster gefüllt ist oder DAV erschöpft ist (Obergrenze an Roundtrips, sonst `degraded`-Kappung wie bei den anderen Familien). Test: die ersten `limit` Treffer sind alle getaggt, der `limit+1`-te ist sichtbar und muss erscheinen.
- Upload-Orakel: als akzeptiertes Restrisiko dokumentieren (Owner-Entscheid, Muster R-24-05) oder Schreiben in ausgeschlossene Ordner mit dem Wortlaut "parent folder does not exist" (404/409-Zweig) ablehnen. Das Zweite macht Ordner-Uploads in `kein-ki`-Bereiche unmöglich; beides ist vertretbar, aber es muss entschieden und getestet sein.
- Tool-Beschreibungen statisch; die Erklärung gehört in Doku und ggf. Server-Instructions, gemessen gegen das Budget-Gate.

**Warning signs:**
- Ein neuer Fehlertext mit "excluded", "kein-ki", "tag" im Code.
- Ein neuer Schlüssel `withheld`/`excluded` in einer Erfolgsantwort.
- Kein Paartest "getaggt vs. nicht existent".

**Phase to address:** Guard-Kern-Phase (Fehlerpfad über `None`), Gate-Phase (Paartests), discuss-phase (Upload-Orakel-Entscheid).

---

### Pitfall 6: Latenz, N+1 und riesige Ordner

**What goes wrong:**
- N+1: pro Treffer eine PROPFIND Depth 0 auf `nc:system-tags`, dazu pro Vorfahr eine weitere. Bei `unified_search` mit 20 Treffern in Tiefe 4 sind das bis zu 100 Roundtrips.
- `nc:system-tags` im vorhandenen Listing-PROPFIND: der Server lädt die Zuordnungen zwar gebündelt vor (`preloadCollection`, nur Depth <= 1), baut die Tag-Objekte aber pro Datei. Gemessen in nextcloud/server PR #64298: Ordner mit 10.279 Dateien und 385.684 Tag-Zuordnungen, PROPFIND `fileid + system-tags` 6,4 s bei ~2.000 Queries; nach dem Fix 2,1 s. **Der PR ist offen**, also auf allen Store-Zielversionen (32 bis 35) der langsame Pfad. Recognize erzeugt real Hunderte maschineller Tags (cbcoutinho-PR #1393: 337 Tags auf einer Produktivinstanz), also sind viele Zuordnungen je Datei realistisch.
- `nc:system-tags` deckt Vorfahren nicht ab: für `/A/B/C` braucht es trotzdem die Tags von `/A`, `/A/B`, `/A/B/C`. Das ist der versteckte zweite Roundtrip, der das "ein Roundtrip je Antwort"-Ziel bricht.
- REPORT-Weg: ein Roundtrip unabhängig von der Ordnergröße, aber Id-Auflösung per Name vorher (zweiter Roundtrip, siehe Pitfall 3) und Kosten proportional zur Zahl der getaggten Objekte; der Server prüft je Objekt `getFirstNodeById` bzw. sucht über den Namen im ganzen Nutzerbaum.

**Why it happens:**
Kleine Testinstanzen haben 30 Dateien und 0 Tags; N+1 fällt dort nicht auf.

**How to avoid:**
- BL-16-Kostennotiz VOR der Designentscheidung messen, auf einer Instanz mit (a) 10.000 Dateien in einem Ordner, (b) Tiefe 6, (c) 300 Tags inkl. Recognize-artiger Massenzuordnung, (d) 1 und 500 `kein-ki`-Objekten. Messgrößen: Roundtrips pro Tool (Zähler im MockTransport UND echte Instanz), Wandzeit p50/p95.
- Vorzugskandidat nach Quelllage: eine Ausschlussmenge je Aufruf per REPORT (getaggte Objekte mit Pfad und fileid), dann rein lokale Präfix-/Id-Prüfung für alle Kandidaten und Vorfahren. Das ist O(1) Roundtrips pro Antwort. Die Id-Auflösung kostet einen zweiten; ob der sich über ein im selben Aufruf invalidierbares Merken sparen lässt, entscheidet die Messung.
- Roundtrip-Zähler als Test: "unified_search mit 20 Dateitreffern verursacht höchstens K Ausschluss-Requests", K fest aus der Messung.
- Harte Kappe für die Ausschlussmenge (Bytes/Objekte); bei Überschreitung `UNKNOWN` -> fail-closed, nicht abschneiden.

**Warning signs:**
- Ausschlussprüfung in einer Schleife über Treffer mit `await`.
- Messung nur auf der Dev-Instanz ohne Recognize.
- Das Design ist vor der Kostennotiz gewählt.

**Phase to address:** Messphase als erste Phase des Milestones (BL-16 verlangt das ausdrücklich); Roundtrip-Zählertest in der Guard-Kern-Phase.

---

### Pitfall 7: Tag-Governance, wer darf `kein-ki` anlegen, vergeben, entfernen, umbenennen

**What goes wrong:**
Quelllage (`master`, auf 32 bis 35 zu verifizieren):
- **Anlegen**: jeder Nutzer, solange `systemtags/restrict_creation_to_admin` nicht gesetzt ist (`canUserCreateTag`).
- **Namen**: beim Anlegen und Umbenennen prüft Nextcloud case-insensitiv (`mb_strtolower`) auf Dubletten und entfernt Steuer- und Unsichtbarzeichen (`Util::sanitizeWordsAndEmojis`: `\p{C}` raus, Leerraum normalisiert). Homoglyphen bleiben erlaubt: `kеin-ki` mit kyrillischem `е` ist ein anderes, legales Tag. Ältere Installationen können aus Zeiten vor der case-insensitiven Prüfung Dubletten wie `Kein-KI` und `kein-ki` tragen (LOW, Einführungsversion der Prüfung nicht ermittelt).
- **Vergeben/Entfernen**: kollaborative Tags (sichtbar + zuweisbar) darf jeder zuweisen und entfernen, der **UPDATE-Recht auf die Datei** hat (`childWriteAccessFunction` prüft `PERMISSION_UPDATE`). Folgen: (1) ein Mitbearbeiter einer geteilten Datei kann das `kein-ki` des Eigentümers entfernen; (2) ein Empfänger mit reiner Leseberechtigung kann eine geteilte Datei für seinen eigenen Assistenten NICHT schützen.
- **Eingeschränkte Tags** (sichtbar, nicht zuweisbar): nur Admins und freigegebene Gruppen dürfen zuweisen und entfernen; für alle sichtbar, also für den Connector lesbar. Das ist die Governance-Variante für Behörden.
- **Unsichtbare Tags**: für Nicht-Admins unsichtbar, also für den Connector wirkungslos (Pitfall 3).
- **Umbenennen/Löschen per DAV**: nur Admin (`SystemTagNode::update/delete` prüfen `isAdmin`). Löschen entfernt alle Zuordnungen auf einmal, der Schutz fällt instanzweit ohne Spur im Connector.
- Das Tag gilt pro Datei, nicht pro Nutzer: Alices `kein-ki` auf einer geteilten Datei blendet sie auch in Bobs Assistenten aus. Das ist die sichere Richtung, überrascht aber.

**Why it happens:**
"Kollaboratives System-Tag" klingt nach Nutzerhoheit, ist aber eine instanzweite, von allen Bearbeitern veränderbare Markierung.

**How to avoid:**
- Namensabgleich im Connector: Unicode NFKC, `\p{C}` entfernen, casefold, dann exakt `kein-ki`. Nicht auf `user-assignable` filtern: kollaborativ UND eingeschränkt zählen beide.
- Homoglyphen: nicht selbst "ähnliche" Tags ausschließen (unscharfe Treffer machen das Verhalten unvorhersagbar), aber im `occ`-Check Tags melden, deren Confusable-Skelett `kein-ki` ergibt, aber nicht normalisiert gleich sind ("Tag 17 sieht aus wie kein-ki, wirkt aber nicht").
- Doku: welche Tag-Klasse für welchen Zweck (kollaborativ = Selbstschutz, eingeschränkt = Organisationsrichtlinie), dass Bearbeiter das Tag entfernen können, dass Leser nicht taggen können, dass Admin-Löschen alles freigibt.
- Kein Tool zum Taggen oder Entfernen im Connector (cbcoutinho hat seit 15.09.2026 `tag_file`/`untag_file`, das ist genau die Fläche, über die ein Assistent seinen eigenen Ausschluss aufheben könnte). Als Nadel ins Destruktiv-Gate: jede Route unter `systemtags-relations` und `systemtags` außer lesendem PROPFIND/REPORT.
- Name im Code als eine Konstante; falls später konfigurierbar (Enterprise), Startprüfung, dass der Name als sichtbares Tag existiert oder bewusst noch nicht existiert.

**Warning signs:**
- Vergleich `tag["name"] == "kein-ki"` ohne Normalisierung.
- Filter auf `user-assignable == true`.
- Doku sagt "nur der Eigentümer kann das Tag entfernen".

**Phase to address:** Guard-Kern-Phase (Normalisierung), Doku-/Betriebsphase (`occ`-Check, Governance-Abschnitt dreisprachig), Destruktiv-Gate-Nadel in der Gate-Phase.

---

### Pitfall 8: Subtree-Semantik bricht an Freigaben, Verschieben und Speichergrenzen

**What goes wrong:**
- **Freigabe eines Unterordners**: Alice taggt `/Projekte`, gibt `/Projekte/Sub` an Bob frei. In Bobs Sicht heißt der Ordner `/Sub`, der getaggte Vorfahr existiert in seinem Baum nicht. Der REPORT läuft über Bobs `userFolder` und findet `/Projekte` nicht. Bobs Assistent sieht alles unter `/Sub`, Alices Assistent nichts. Das ist mit Connector-Mitteln (Nutzerrechte, keine Admin-Sicht) nicht lösbar.
- **Mehrere Pfade für eine fileid**: dieselbe Datei eigen und zusätzlich über eine Freigabe oder einen Team-Folder eingehängt. `find_by_fileid` nimmt `entries[0]`; liegt der erste Pfad außerhalb des getaggten Ordners, läuft der Ordnerschutz ins Leere.
- **Verschieben**: innerhalb eines Speichers bleiben fileid und Tag erhalten; verschoben aus einem getaggten Ordner heraus ist die Datei ab dem nächsten Aufruf sichtbar (gewollt, aber unbemerkt). Speicherübergreifend (Home -> External Storage oder Team-Folder) ist ein Verschieben technisch Kopieren plus Löschen mit neuer fileid; ein direkt an der Datei hängendes Tag geht verloren (MEDIUM, nicht gemessen). Kopien tragen das Tag nach Allgemeinwissen nicht (LOW).
- **Umbenennen eines Vorfahren**: harmlos, solange die Ausschlussmenge pro Aufruf frisch gebaut wird; schädlich, sobald Pfade über Aufrufe gecacht werden.
- **External Storage**: Tags hängen an der fileid des Filecache. Nicht gescannte Dateien (direkt auf SMB/S3 abgelegt) haben keine fileid und sind nicht taggbar; ein neu angelegter oder umkonfigurierter Mount bekommt eine neue Storage-Id und neue fileids, alle Tags sind weg (MEDIUM). Suche und REPORT sehen je nach Scan-Stand andere Mengen.
- **Team-Folders (groupfolders)**: fileids stabil, Tags funktionieren nach Allgemeinwissen; ACLs können aber dazu führen, dass ein Nutzer den getaggten Vorfahren nicht lesen darf, wohl aber ein Kind (gleicher Effekt wie bei der Unterordner-Freigabe). LOW.

**Why it happens:**
Subtree ist Connector-Logik über Pfade, Tags sind Nextcloud-Logik über fileids; beide Modelle decken sich nur im einfachen Home-Speicher.

**How to avoid:**
- Semantik festschreiben und dokumentieren: "Der Ordnerschutz wirkt im Baum des jeweiligen Nutzers. Wer einen Unterordner freigibt, taggt den freigegebenen Ordner selbst." Als ehrlich markierte Grenze in der Doku, nicht wegschweigen.
- Ausschluss prüft fileid UND alle bekannten Pfade: eine Datei ist ausgeschlossen, wenn ihre fileid getaggt ist ODER irgendein Pfad unter einem getaggten Ordner liegt. `find_by_fileid` wertet dafür alle Einträge aus, nicht `entries[0]`.
- Keine Pfad-Caches über Aufrufe.
- Messung in der Messphase: Unterordner-Freigabe, Team-Folder, External Storage (lokaler Mount reicht), speicherübergreifendes Verschieben; Ergebnis als Tabelle in der Doku (Muster `docs/exchange-evidence.md`).

**Warning signs:**
- Ordnerschutz nur mit Home-Speicher getestet.
- Doku verspricht "alles darunter" ohne Freigabe-Einschränkung.
- `find_by_fileid` bleibt bei `entries[0]`.

**Phase to address:** Messphase (Speicher-Matrix), Guard-Kern-Phase (fileid-UND-Pfad-Regel), Doku-Phase (ehrliche Grenze).

---

### Pitfall 9: TOCTOU, Tag zwischen Nachschlagen und Antwort

**What goes wrong:**
Ausschlussmenge wird um t0 gebaut, der Inhalt um t1 gelesen, dazwischen setzt jemand `kein-ki`. Oder: `prepare_context` baut die Menge, dann laufen fünf Excerpts parallel über mehrere Sekunden. Außerdem: was der Assistent VOR dem Taggen gelesen hat, steht im Chatverlauf des Clients, im Client-Gedächtnis oder in einem Findling-Index; der Connector kann es nicht zurückholen.

**Why it happens:**
Jeder Filter über eine externe, veränderliche Markierung hat ein Fenster; das Problem ist nicht das Fenster, sondern ein Versprechen, das kein Fenster zugibt.

**How to avoid:**
- Fenster minimieren: Ausschlussabfrage parallel zum Inhaltsabruf starten und die Antwort erst nach beiden zusammensetzen, sodass jede Tag-Setzung vor Abschluss der Abfrage greift. Eine Ausschlussmenge pro Aufruf, nie über Aufrufe.
- Wirkung in Doku und Store-Text ehrlich: "wirkt ab dem nächsten Aufruf; was ein Assistent vorher gelesen hat, kann dieser Connector nicht zurücknehmen".
- Test mit einem MockTransport, der das Tag zwischen erster und zweiter Anfrage "setzt": der zweite Aufruf darf nichts liefern; der erste darf, das ist dokumentiert.
- Findling (eigenes Produkt, Content-Provider hier): eigenes Backlog-Item, dass Findling `kein-ki` beim Indexieren respektiert; sonst widersprechen sich die zwei Produkte des Owners.

**Warning signs:**
- Doku formuliert "getaggte Dateien werden nie gesehen" ohne Zeitbezug.
- Ausschlussmenge in einem Objekt, das länger lebt als ein Tool-Aufruf.

**Phase to address:** Guard-Kern-Phase (Lebensdauer pro Aufruf), Doku-Phase (Formulierung), Findling-Backlog-Eintrag bei Milestone-Abschluss.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Filter nur in `files_*`-Tools | Schnell grün | Bypass über fetch, Suche, Notes, Talk, systemtags-Provider, Findling | Nie |
| `nc:system-tags` ins Listing-PROPFIND, Vorfahren ignorieren | Kein Extra-Roundtrip für Listings | Subtree-Versprechen gebrochen; 6 s bei 10k Dateien bis PR #64298 landet | Nie ohne Vorfahrenprüfung |
| Tag-Id modulweit cachen | Ein Roundtrip gespart | Fail-open nach Löschen/Neuanlegen; verletzt D-20-Gate | Nur pro Aufruf, 412 invalidiert |
| Eigener Fehlertext "excluded by kein-ki" | Ehrlich wirkend | Existenz-Orakel, bricht Byte-Gleichheit | Nie für Erfolgsausschluss; nur für `UNKNOWN` |
| Ausschlüsse in `skipped` mitzählen | Transparenz | Zählt, dass es passende geheime Dateien gibt | Nie |
| Env-Schalter zum Abschalten des Ausschlusses | Debug bequem | Bypass per Konfiguration, "Sicherheitsgrenzen nie bezahlt" wird verwässert | Nie in v1.7 |
| Withheld-Zähler ins Audit-Log | Enterprise-Beweis vorbereitet | Ändert die Zeilenform der Hash-Kette, greift der Enterprise-Governance vor (Scope-Fence) | Erst im Enterprise-Milestone, additiv |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `oc:filter-files` REPORT | 412 als "keine Treffer" lesen; Zielpfad für Scope halten (Server sucht über den Tag-Namen im ganzen Nutzerbaum) | 412 = `UNKNOWN` oder Neuauflösung; eigene Pfadfilterung auf absoluten Home-Pfaden |
| `nc:system-tags` (PROPFIND) | Annehmen, es enthalte Vorfahren oder unsichtbare Tags | Nur eigene, sichtbare Tags der Datei; Vorfahren separat |
| DAV SEARCH | Tag-Bedingung in `where` erwarten | `FileSearchBackend` kennt kein systemtag-Kriterium (Quelle); SEARCH-Ergebnisse nachfiltern |
| Unified Search `systemtags` | Als harmlosen Nicht-Datei-Provider behandeln | Liefert getaggte Dateien mit `fileId`/`path`; abwählen oder filtern |
| Unified Search `findling` | Content-Ausschnitte ungeprüft durchreichen | Nur mit fileid/Pfad filterbar; prüfen, ob Findling-Treffer die Attribute tragen (offen) |
| Notes-REST | Als eigene Familie ohne Dateibezug sehen | Notizen sind Dateien; Einträge über fileid/Pfad filtern |
| Talk `messageParameters` | Dateiparameter ungeprüft in den Text einsetzen | Dateiparameter mit getaggter fileid schwärzen (gleicher Platzhaltertext wie für unbekannte Dateien) |
| Capability `systemtags` | Als Schalter "Feature an/aus" nehmen | Ignorieren; immer DAV fragen |
| Sandbox `parse_entries` | Für die Tag-Menge wiederverwenden | Eigener Parser, der Vorfahren des Roots behält |
| Community-PR `files_update` (#9) | Annehmen, Flächen überschneiden sich nicht | Update auf ausgeschlossene Datei = Antwort wie "existiert nicht"; in den Maßnahmenkatalog des Design-Issues aufnehmen |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Tag-Abfrage pro Treffer | Roundtrip-Zahl wächst mit `limit` | Eine Ausschlussmenge je Aufruf | Ab ~10 Treffern spürbar, bei prepare_context sofort |
| Tag-Abfrage pro Vorfahr | Tiefe Ordner langsam | Lokale Präfixprüfung gegen die Menge | Ab Tiefe 3 |
| `nc:system-tags` im großen Listing | `files_list` im Riesenordner mehrere Sekunden | Nicht als einzige Quelle; Messung | ~10.000 Dateien / viele Tag-Zuordnungen (PR #64298: 6,4 s) |
| Sequentielle Ausschlussabfrage vor Suche | prepare_context-Wandzeit = Summe statt Maximum | Parallel starten, eigenes Budget | Immer |
| Nachfordern in `files_search` ohne Kappe | Endlosschleife bei fast komplett getaggten Ordnern | Roundtrip-Kappe + `degraded`-Kappung | Wenn > 90 % der Treffer getaggt sind |
| Große Ausschlussmenge | Antwortzeit wächst mit Zahl getaggter Objekte | Kappe, bei Überschreitung fail-closed | LOW-Schätzung: > einige tausend getaggte Objekte |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Ausschluss per fileid-Fetch umgehbar | Inhalt einer bekannten Datei trotz Tag | Filter in `find_by_fileid`-Ergebnis, Kanarientest mit fetch |
| systemtags-Provider in unified_search | Liste aller geschützten Dateinamen | Provider abwählen oder filtern |
| Unsichtbares `kein-ki` | Schutz wirkt für niemanden | `occ`-Check, Doku |
| Tag-Schreibtool ergänzt | Assistent entfernt eigenen Ausschluss | Destruktiv-Gate-Nadel auf `systemtags-relations` |
| Existenz-Orakel im Ausfall | Ausfall verrät vorhandene Ids | Ausschlussabfrage vor Existenzauflösung, byte-gleicher Ausfalltext |
| Ausgeschlossene Pfade ins Audit-Log | Admin-Log speichert genau die Metadaten, die der Nutzer ausnehmen wollte | Audit bleibt bei Tool + Parameterschlüsseln (Allowlist), keine Pfade |
| `files_update` ohne Guard (Community-PR) | Schreiben in unsichtbaren Inhalt | Klassifikations-Freeze erzwingt Guard für jedes neue Tool |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Name `kein-ki` verspricht "keine KI überhaupt" | Nutzer glauben, Nextcloud Assistant/Context Chat, Recognize, Findling respektieren es auch | Doku und Store-Text: "wirkt in diesem Connector"; andere Produkte ausdrücklich nennen |
| Stiller Ausschluss ohne jeden Hinweis | Assistent behauptet, eine Datei existiere nicht; Nutzer verwirrt | Doku/Server-Instructions erklären das Verhalten allgemein, nie pro Antwort |
| Leser können nicht taggen | Empfänger einer Nur-Lesen-Freigabe kann sich nicht schützen | Doku; Governance über eingeschränktes Tag durch Admin |
| Mitbearbeiter entfernt Tag | Schutz verschwindet unbemerkt | Doku; eingeschränktes Tag für Richtlinien |
| Unterordner-Freigabe | Empfänger-Assistent sieht, was beim Eigentümer ausgeschlossen ist | Ehrliche Grenze: freigegebenen Ordner selbst taggen |
| Ausfall degradiert Dateien, Nutzer sieht nur "no results" | Glaubt, es gebe nichts | `degraded`-Eintrag im Ausfall benennt die zurückgehaltene Kategorie |

## "Looks Done But Isn't" Checklist

- [ ] **fetch:** `file:<id>` einer VOR dem Taggen gemerkten Datei liefert byte-gleich "This account has no file with the id ..."
- [ ] **prepare_context:** getaggter Treffer erscheint weder in `results` noch als `degraded`-`source`
- [ ] **unified_search:** Suche nach "kein" oder "kein-ki" liefert keine getaggte Datei über den systemtags-Provider
- [ ] **Findling-Provider:** Ausschnitte getaggter Dateien fehlen (oder Grenze dokumentiert, falls Findling keine Pfadattribute liefert)
- [ ] **Notes:** Notiz in getaggtem Unterordner von `/Notes` fehlt in `notes_list`, `notes_read`, `notes_search`
- [ ] **Talk:** Dateiparameter einer getaggten Datei ist geschwärzt
- [ ] **Sandbox:** Root `/A/B`, Tag auf `/A` schließt alles aus
- [ ] **Paging:** erste `limit` Suchtreffer getaggt, der nächste sichtbare erscheint auf Seite 1
- [ ] **Ausfall:** DAV-Tag-Abfrage 500/Timeout: Dateien zurückgehalten, Termine/Mail/Talk-Text da, ein `degraded`-Eintrag, kein `ToolError` aus prepare_context
- [ ] **Ausfall-Orakel:** fetch existent/getaggt/nicht existent im Ausfall byte-gleich
- [ ] **412:** veraltete Tag-Id führt nicht zu "nichts ausgeschlossen"
- [ ] **Alle Einstiegspunkte:** stdio, HTTP, OAuth-Standalone, ExApp, Exchange-Pfad nutzen denselben Guard
- [ ] **Budget-Gate:** Beschreibungsänderungen gemessen, Gate nicht angehoben ohne Messung
- [ ] **Kanarientest** läuft über die aktive Registry, nicht über eine handgepflegte Liste

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Bypass nach Release entdeckt | HIGH (Vertrauensbruch bei Behörden-Zielgruppe) | Security-Advisory, Patch-Release, Kanarientest um den Weg erweitern, Store-Text prüfen |
| Existenz-Orakel entdeckt | MEDIUM | Fehlertext angleichen, Paartest ergänzen |
| Latenz reißt Budget | MEDIUM | Auf REPORT-Menge umstellen, Roundtrip-Zählertest nachziehen |
| Tag-Governance falsch dokumentiert | LOW | Doku dreisprachig korrigieren, Store-Text im nächsten Release |
| Fail-open durch Cache | HIGH | Cache entfernen, D-20-Gate prüfen, Regressionstest "Tag neu angelegt" |

## Pitfall-to-Phase Mapping

Phasenvorschlag (Nummern ab 25 als Annahme, der Roadmapper entscheidet):

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 6 Latenz/N+1 | Phase 25 Messung (BL-16-Kostennotiz) | Messprotokoll mit 10k-Ordner, Tiefe 6, 300 Tags; Roundtrips pro Tool |
| 3 Fail-open-Zustände (412, App aus, unsichtbar) | Phase 25 Messung + Phase 26 Guard-Kern | Gemessene 412-/App-aus-Antworten auf NC 32 und 35; Drei-Zustands-Tests |
| 8 Subtree/Speicher | Phase 25 Messung + Phase 26 Guard-Kern | Speicher-Matrix; fileid-UND-Pfad-Test; `find_by_fileid` wertet alle Einträge |
| 2 Sandbox-Integration | Phase 26 Guard-Kern | Root-/Tag-Matrix grün |
| 7 Namensnormalisierung | Phase 26 Guard-Kern | Tests für Groß/Klein, Nullbreitenzeichen, NFKC, Homoglyph (bewusst NICHT ausgeschlossen) |
| 9 TOCTOU (Lebensdauer) | Phase 26 Guard-Kern | Mock setzt Tag zwischen zwei Aufrufen |
| 1 Bypass-Routen | Phase 27 Familien-Anschluss (Suche, prepare_context, ChatGPT-Profil, Notes, Talk, Provider systemtags/findling) | Kanarientest über die Registry |
| 4 Fail-closed-Breite | Phase 27 Familien-Anschluss | Ausfalltests je Familie; prepare_context bleibt Antwort |
| 5 Informationslecks | Phase 26 (Fehlerpfad) + Phase 28 Gates | Paartests getaggt vs. nicht existent, auch im Ausfall; Paging-Test |
| 1 Vergessen künftiger Tools | Phase 28 Gates | Klassifikations-Freeze, Destruktiv-Gate-Nadel `systemtags-relations` |
| 7 Governance, 9 Doku-Ehrlichkeit, UX | Phase 29 Doku + Betrieb | Doku EN/DE/FR mit Grenzen; `occ mcp_connector:exclusion:check`; Doku-Wahrheitstest wie `test_docs_exchange_truth.py` |
| 5 Upload-Orakel | discuss-phase vor Phase 26 | Owner-Entscheid dokumentiert (akzeptiert oder abgelehnt mit 404-Wortlaut), Test hält ihn |
| `files_update` | Design-Issue #9 (extern) | Guard-Pflicht im Maßnahmenkatalog; Freeze erzwingt es technisch |

## Sources

- nextcloud/server `master`, direkt gelesen (HIGH für `master`, auf 32 bis 35 zu messen):
  - https://github.com/nextcloud/server/blob/master/lib/private/SystemTag/SystemTagManager.php (case-insensitive Dubletten, `sanitizeWordsAndEmojis`, `restrict_creation_to_admin`, `canUserAssignTag`, `canUserSeeTag`)
  - https://github.com/nextcloud/server/blob/master/apps/dav/lib/SystemTag/SystemTagPlugin.php (`nc:system-tags`, `preloadCollection` nur Depth <= 1, Sichtbarkeitsfilter)
  - https://github.com/nextcloud/server/blob/master/apps/dav/lib/SystemTag/SystemTagList.php (Attribute id, can-assign, user-visible, user-assignable)
  - https://github.com/nextcloud/server/blob/master/apps/dav/lib/SystemTag/SystemTagNode.php (Umbenennen/Löschen nur Admin)
  - https://github.com/nextcloud/server/blob/master/apps/dav/lib/SystemTag/SystemTagMappingNode.php und SystemTagsObjectMappingCollection.php (Zuweisen/Entfernen braucht PERMISSION_UPDATE)
  - https://github.com/nextcloud/server/blob/master/apps/dav/lib/Connector/Sabre/FilesReportPlugin.php (412 bei unbekanntem Tag, Suche über Tag-Namen im Nutzerbaum)
  - https://github.com/nextcloud/server/blob/master/apps/systemtags/lib/Search/TagSearchProvider.php (Provider `systemtags` mit `fileId`/`path`)
  - https://github.com/nextcloud/server/blob/master/apps/dav/lib/Server.php (Tag-Plugin unbedingt registriert)
- https://github.com/nextcloud/server/pull/64298 (Messwerte 10.279 Dateien / 385.684 Zuordnungen, Status offen) (MEDIUM, PR-Beschreibung)
- https://github.com/cbcoutinho/nextcloud-mcp-server/pull/1393 (Tag-Tools inkl. untag beim Platzhirsch, 337 Recognize-Tags, gemergt 15.09.2026) (MEDIUM)
- Repo-Code: `src/mcp_connector/nextcloud/clients/dav.py`, `tools/search.py`, `tools/chatgpt.py`, `tools/context.py`, `tools/files.py`, `tools/talk.py`, `tests/contract/test_no_destructive_calls.py`, `tests/contract/test_tool_surface.py` (HIGH)
- `.planning/PROJECT.md` (Milestone v1.7, BL-16, Byte-gleich-Disziplin v1.6, R-24-05-Muster) (HIGH)
- Allgemeinwissen, nicht verifiziert (LOW bis MEDIUM, als solches markiert): Notes-Id = fileid, speicherübergreifendes Verschieben erzeugt neue fileid, Kopien tragen keine Tags, External-Storage-Neumount erzeugt neue fileids, groupfolders-ACL-Verhalten

---
*Pitfalls research for: Ausschluss-Tag kein-ki im Nextcloud MCP Connector (v1.7)*
*Researched: 2026-09-26*

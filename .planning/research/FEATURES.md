# Feature Research

**Domain:** Inhaltsausschluss für KI-Werkzeuge über ein Nextcloud-System-Tag (`kein-ki`), fail-closed, mit Subtree-Semantik, im bestehenden MCP-Connector (v1.7, BL-16)
**Researched:** 2026-09-26
**Confidence:** HIGH für das Nextcloud-Tag-Rechtemodell (Quellcode `nextcloud/server` master gelesen) und für den Konkurrenz-Connector (Quellcode + Doku geklont), HIGH für Microsoft 365 (Microsoft Learn, Stand 09/2026), MEDIUM für Google Workspace (offizielle Hilfe, UX-Details fehlen dort), MEDIUM bis LOW für die Übertragbarkeit der Nutzererwartungen

Scope: nur das neue Ausschluss-Tag. Die 22 Werkzeuge, unified_search, prepare_context, Audit-Log und OAuth gelten als vorhanden und werden nur als Abhängigkeit genannt.

---

## 0. Präzedenzfälle: was vergleichbare Produkte tatsächlich tun

| Produkt | Mechanismus | Granularität | Wer setzt es | Was der Nutzer sieht | Fehler-/Verzögerungsverhalten | Confidence |
|---|---|---|---|---|---|---|
| **cbcoutinho/nextcloud-mcp-server** (direkter Konkurrent, seit v0.80.0 vom 2026-05-06) | `EXCLUDED_TAGS=confidential,no-ai,private` (Env, frei konfigurierbare Namensliste), Auflösung Name → Tag-Id → REPORT der getaggten Pfade, je Tool-Aufruf | Datei und Ordner, Ordner per Pfad-Präfix auf alle Nachfahren | Admin legt den Tag per `occ tag:add 'no-ai' --user-visible=true --user-assignable=false` an; Doku empfiehlt ausdrücklich **nicht zuweisbar**, weil sonst der Nutzer selbst enttaggen kann | Listings/Suchen: **still weggelassen**; read/write/delete: `ToolError` "access denied" | **Fail-open je Tag** (Endpoint-Fehler → Warnung im Log, Dateien sichtbar), 2 Requests je Tag und Aufruf, kein Cache; **nur WebDAV-Werkzeuge**, Notes/Deck/Kalender ausdrücklich nicht gefiltert | HIGH (Quelle `server/tag_exclusion.py`, `docs/configuration.md`) |
| **Nextcloud context_chat, PR #277** (offen seit 2026-09-09, nicht gemergt) | Gegenpolarität: **Allow-List**-Tag "AI knowledge"; Admin-Schalter "alles indexieren" (Default) vs. "nur Getaggtes" | Datei und Ordner, Vererbung "walks up the file's ancestor folders" | Admin schaltet den Modus; Tag ist ein normales System-Tag | Nicht Getaggtes fehlt im Index, keine Anzeige | Moduswechsel räumt den Index im Hintergrund auf bzw. indexiert voll neu | MEDIUM (PR-Text, Status offen) |
| **Nextcloud files_accesscontrol** | Admin-Regelgruppen verweigern den Zugriff, wenn alle Bedingungen gelten (Tag, User-Agent, IP, Gruppe, MIME, ...) | Tag auf Datei **oder auf einem Elternordner des Datei-Eigentümers** | Nur Admin (Regeln); Doku warnt: "Unrestricted tags allow users to bypass controls by removing them" | Harte Zugriffsverweigerung (Erstellen, Ändern, Löschen, Download, Sync) | Serverseitig; Context Chat ignoriert die Regeln laut Doku | HIGH (Admin-Manual) |
| **Microsoft 365 Copilot, Purview-DLP mit Sensitivity Labels** | DLP-Regel "Prevent Copilot from processing content" auf Labels | Datei/E-Mail je Label | Compliance-/AI-Admin-Rollen | **Getaggte Elemente erscheinen weiter in den Zitaten**, nur ihr Inhalt wird nicht genutzt; beim Ausschluss externer Mails sieht der Nutzer "some content was excluded by an organizational policy" | Richtlinienänderungen bis zu 4 Stunden; in Word/Excel/PowerPoint erst beim nächsten Öffnen | HIGH (Microsoft Learn, aktualisiert 2026-09-17) |
| **Microsoft SharePoint Restricted Content Discovery** | Site-Schalter "Restrict content from Microsoft Copilot" | Nur ganze SharePoint-Sites, **nicht OneDrive**; keine Datei-/Ordnerebene | SharePoint-Admin, delegierbar an Site-Admins **mit Pflichtbegründung und Audit-Event** | Sichtbarer "Restricted"-Marker an der Site, Copilot-Einstiege verschwinden | Propagation dauert, bei >500.000 Elementen "more than a week"; eigener Besitz und zuletzt Genutztes bleiben auffindbar | HIGH (Microsoft Learn, aktualisiert 2026-09-22) |
| **Google Workspace, DLP for Gemini** | DLP-Regeln (Datentypen, Regex, **Klassifizierungslabels**) mit Aktion "Block data access" oder "Audit only" | Drive-Dateien, derzeit nur Drive | Workspace-Admin | Offizielle Doku sagt nicht, ob der Nutzer eine Meldung sieht | Änderungen bis zu 24 Stunden; gilt nicht für Gemini Enterprise und Gemini in Chrome | MEDIUM (Workspace-Hilfe) |
| **GitHub Copilot Content Exclusion** | fnmatch-Pfadlisten je Repo/Org/Enterprise | Pfad-Glob inkl. `/**` | Repo-Admin, Org-/Enterprise-Owner | Completion im Editor aus | Bis 30 Minuten; **Agent Mode unterstützt die Ausschlüsse nicht** (dokumentiert) | HIGH (GitHub Docs) |
| **robots.txt / TDMRep / `noai`** | Maschinenlesbares Opt-out-Signal, Pfad-Präfix-Matching | Pfad, Verzeichnis | Inhaber der Ressource | Nichts | Rein freiwillig: bindet nur, wer es beachtet | HIGH (W3C-CG-Report) |

**Drei Lehren aus den Präzedenzfällen:**

1. **Fail-open ist der Branchenstandard, und das ist unser Differenzierer.** Der direkte Konkurrent entscheidet sich dokumentiert für fail-open ("a Nextcloud-side outage of the systemtags API should not take down all WebDAV tools"). GitHub lässt den Agent Mode ohne Ausschluss laufen. Ein Connector, der bei nicht beantwortbarer Tag-Abfrage zurückhält und das benennt, ist in diesem Markt ungewöhnlich.
2. **Alle Großen haben Minuten bis Tage Verzögerung** (GitHub 30 min, Microsoft bis 4 h bzw. über eine Woche, Google bis 24 h). Ein Tag, das beim nächsten Werkzeugaufruf wirkt, ist ein echter, belegbarer Unterschied, solange nicht gecacht wird.
3. **Sichtbarkeit des Ausschlusses ist uneinheitlich.** Microsoft zeigt ausgeschlossene Elemente sogar in den Zitaten (Existenz offen, Inhalt zu), der Konkurrent lässt still weg. Die Frage "Zähler oder Leck" ist also nicht vom Markt entschieden, sondern muss aus unserem Bedrohungsmodell beantwortet werden (Abschnitt 2).

---

## 1. Das Nextcloud-Tag-Rechtemodell (entscheidet die Tag-Klassen-Frage)

Aus dem Quellcode `nextcloud/server` master (`lib/private/SystemTag/SystemTagManager.php`, `apps/dav/lib/SystemTag/*`, Migration `Version13000Date20170718121200`), Confidence HIGH:

| Fakt | Beleg | Folge für kein-ki |
|---|---|---|
| Drei Klassen: **öffentlich/kollaborativ** (sichtbar, zuweisbar), **eingeschränkt** (sichtbar, nur Admin oder freigegebene Gruppen weisen zu), **unsichtbar** (nur Admin sieht und weist zu) | `canUserAssignTag`, `canUserSeeTag`; User-Manual "System tags" | Klassenwahl ist eine Admin-Entscheidung beim Anlegen, der Connector muss mit allen sichtbaren Klassen umgehen |
| Zuweisen **und Entfernen** eines Tags an einer Datei verlangt `PERMISSION_UPDATE` auf der Datei | `SystemTagsObjectMappingCollection::createFile`, `SystemTagMappingNode::delete`, `SystemTagsRelationsCollection` | Nur-Lese-Empfänger einer Freigabe können kein-ki weder setzen noch entfernen; jeder Mitbearbeiter kann es bei kollaborativer Klasse entfernen |
| **Umbenennen** eines Tags per DAV nur durch Admins ("only admin is able to update system tags") | `SystemTagNode::update` | Umbenennungs-Spoofing durch normale Nutzer ist ausgeschlossen; ein Admin-Rename lässt einen namensbasierten Ausschluss aber still enden |
| Tag-Anlage durch Nutzer ist ab Werk erlaubt, abschaltbar per `systemtags restrict_creation_to_admin` (seit NC 31 vereinheitlicht) | `canUserCreateTag`, PR #51288 | Jeder Nutzer kann `kein-ki` anlegen, falls es fehlt, auch in falscher Schreibweise |
| Eindeutigkeit gilt für **(name, visibility, editable)**, nicht für den Namen allein | Unique-Index `tag_ident` | `kein-ki` kann **bis zu dreimal** existieren (öffentlich, eingeschränkt, unsichtbar). Der Connector muss alle gleichnamigen Tags vereinigen, sonst ist der Ausschluss vom Zufall der Anlage abhängig |
| Eingeschränkte Tags lassen sich an Gruppen delegieren (DAV-Property `oc:groups`, nicht in der Web-UI) | Nextcloud-Portal "Managing tags by group"; `getTagGroups` | Organisationen können "nur Datenschutz-Team setzt kein-ki" abbilden, ohne dass wir etwas bauen |
| Unsichtbare Tags sieht ein Nicht-Admin nicht | `canUserSeeTag` | Der Connector fragt im Kontext des Nutzers; ein unsichtbares `kein-ki` ist für ihn nicht lesbar und damit **wirkungslos** |
| Freigaben: files_accesscontrol wertet "any of the file **owner's** parent folders" aus | Admin-Manual Access Control | Ein Tag auf einem Ordner **oberhalb** der Freigabewurzel sieht der Empfänger nicht. Ein nutzerseitiger Connector kann diese Vorfahren nicht abfragen (siehe PITFALLS/ARCHITECTURE) |
| Der Konkurrent dokumentiert: das Tag eines Eigentümers erscheint im Tag-REPORT des Empfängers nur, wenn es `userVisible` ist | cbcoutinho `docs/configuration.md` "Shared files" | Bestätigt: nur sichtbare Klassen taugen |

### Tag-Klasse: kollaborativ oder eingeschränkt?

| | Kollaborativ (öffentlich) | Eingeschränkt | Unsichtbar |
|---|---|---|---|
| Wer setzt | Jeder mit Schreibrecht an der Datei | Admin + delegierte Gruppen | Admin |
| Wer entfernt | Jeder mit Schreibrecht, also auch Mitbearbeiter und der Nutzer, dessen KI eingeschränkt werden soll | Admin + delegierte Gruppen | Admin |
| Selbstbedienung | Ja, genau die Milestone-Absicht ("Nutzer schützt eigene Datei") | Nein | Nein |
| Manipulationsfest | Nein: ein Mitbearbeiter kann den Schutz für alle aufheben (fail-open durch Menschen) | Ja | Ja, aber für den Connector nicht lesbar |
| Passt zu | Selfhoster, Einzelnutzer, Teams mit Vertrauen | Behörden, Unternehmen, Compliance | nichts (für uns) |

**Empfehlung (opinionated):** Der Connector **erzwingt keine Klasse**, sondern wertet jedes für den Nutzer sichtbare Tag mit dem Namen `kein-ki` aus (kollaborativ und eingeschränkt, vereinigt). Die Doku nennt zwei Betriebsarten ehrlich:
- **Selbstbedienung (Default, kollaborativ):** schützt vor Versehen, nicht vor Mitbearbeitern. Das ist das Bedrohungsmodell des Konkurrenten ("accidental exfiltration") und reicht für die v1-Zielgruppe.
- **Organisationsmodus (eingeschränkt, Gruppe delegiert):** Admin legt `kein-ki` eingeschränkt an und delegiert per `oc:groups`; dann kann weder der Nutzer noch ein Mitbearbeiter den Schutz stillschweigend entfernen. Kostet uns nur Doku, weil Nextcloud die Mechanik schon hat.
- **Unsichtbar:** ausdrücklich als "wirkt nicht" dokumentieren.

Der Unterschied zum Konkurrenten: der empfiehlt pauschal `--user-assignable=false`, verliert damit aber die Selbstbedienung. Wir lassen beides zu und sagen, was jede Wahl kostet. Die Zentralvorgabe "Klasse X erzwingen" gehört in die Enterprise-Governance (Dossier-Regel), nicht in v1.

---

## 2. Die Kernfrage: sichtbarer "n Einträge zurückgehalten"-Zähler oder Informationsleck?

**Bedrohungsmodell:** Der Empfänger der Werkzeugantwort ist ein Modell, das Prompt-Injection ausgesetzt sein kann (Lethal Trifecta ist im Projekt bereits benannt, SEC-01). Wer das Modell steuert, darf aus der Antwort nichts über getaggte Inhalte lernen. Zusätzlich setzt bei kollaborativen Tags oft ein **anderer** Nutzer das Tag (Kollege schützt einen geteilten Ordner vor meiner KI); dann ist schon die Existenz eine Information, die der Kollege der KI vorenthalten wollte.

| Variante | Was sie verrät | Urteil |
|---|---|---|
| Zähler je Antwort ("2 Treffer zurückgehalten") bei Suchwerkzeugen | **Suchorakel:** `unified_search("Gehalt Müller")` → "1 zurückgehalten" beweist, dass ein getaggtes Dokument zu dieser Anfrage existiert. Mit wiederholten Anfragen lässt sich der Inhalt eingrenzen | **Anti-Feature** |
| Zähler je Antwort bei Listings | Zeigt die Existenz und Zahl versteckter Einträge in einem Ordner | Anti-Feature, schwächer, aber gleiche Klasse |
| Namen/Pfade der zurückgehaltenen Einträge | Alles, was der Dateiname verrät (häufig viel) | Anti-Feature |
| `fetch`/`read` einer getaggten Datei antwortet anders als eine nicht existierende Id ("ist durch kein-ki geschützt") | Existenzorakel über Ids und Pfade | Anti-Feature: **gleiche Antwort wie "nicht gefunden"** |
| Schreibwerkzeug in einen getaggten Ordner antwortet mit "Datei existiert bereits" | Existenzorakel über Konflikte | Anti-Feature: Schreiben ins ausgeschlossene Subtree mit derselben Ablehnung wie "Ziel nicht gefunden" |
| **Statischer Hinweis** in Werkzeugbeschreibung/Server-Instructions: "Dateien und Ordner mit dem Tag kein-ki werden nie angezeigt" | Nur, dass es den Mechanismus gibt, unabhängig von jeder Anfrage | **Table Stake**: erklärt dem Modell und damit dem Nutzer, warum etwas fehlt, ohne Orakel |
| **Degradationseintrag**, wenn die Tag-Abfrage scheitert ("Dateitreffer zurückgehalten: Tag-Prüfung nicht verfügbar") | Nur den Zustand des Connectors, nichts über Tags (der Connector weiß in dem Fall selbst nichts) | **Table Stake**, genau die Milestone-Vorgabe |
| Zähler im Audit-Log (Admin-seitig, ohne Namen) | Nichts ans Modell | Differenzierer, P3 |

**Empfehlung:** Im Normalbetrieb ist eine gefilterte Antwort **nicht unterscheidbar** von einer Antwort, in der die Einträge nie existierten. Das ist die bewusste Ausnahme von der Hausregel aus prepare_context ("every cap writes its own degraded entry, so five is never mistaken for all"). Diese Ausnahme muss als Entscheidung im Code und in der Doku stehen, sonst "repariert" sie ein späterer Review-Durchgang. Ein degraded-Eintrag erscheint **nur**, wenn die Prüfung selbst nicht beantwortbar war, und er nennt Grund und betroffene Familie, keine Zahl, die an Tag-Zustände gekoppelt ist.

Warum wir von Microsoft abweichen (dort bleiben Label-Elemente in den Zitaten): Copilot läuft in einer geschlossenen Microsoft-Oberfläche, deren Zitatliste nur der Mensch sieht. Bei uns geht jede Antwort an ein beliebiges, fremdes Modell, oft mit Web- und Schreibwerkzeugen daneben. Das Risiko liegt beim Empfänger, nicht beim Menschen. Confidence MEDIUM (eigene Ableitung aus dokumentiertem Verhalten).

---

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes / Abhängigkeit |
|---------|--------------|------------|-------|
| **T1 Datei mit `kein-ki` fehlt in allen dateiliefernden Antworten**: `files` search/list/read/download, `unified_search`, ChatGPT-`search`/`fetch`, prepare_context-Suchbein | Der Name des Features; der Konkurrent filtert nur WebDAV-Werkzeuge, Nutzer erwarten "überall" | MEDIUM: eine gemeinsame Filterstelle, aber sechs Aufrufer | Hängt am Id-Codec als einziger Quelle (TOOL-18) und an fetchs sieben Id-Arten; ein Filter je Werkzeug wäre der sichere Weg zu einer vergessenen Lücke |
| **T2 Subtree-Semantik**: Tag auf Ordner deckt alle Nachfahren | Alle Präzedenzfälle (context_chat-PR, files_accesscontrol, Konkurrent, robots.txt-Präfix) arbeiten so | MEDIUM: Pfad-Präfix gegen die Menge getaggter Ordner, Achtung Pfadnormalisierung und Groß/Klein | Wiederverwendbares Muster: `NC_MCP_FILES_ROOT`-Sandbox aus PR #8 (`normalize_files_root`) prüft bereits "bleibt im Teilbaum" |
| **T3 Fail-closed**: Tag-Abfrage nicht beantwortbar (systemtags aus, OCS/DAV-Fehler, Timeout) → **alle** Dateieinträge der Antwort zurückhalten, nicht nur "vermutlich betroffene" | Milestone-Vorgabe; Sicherheitsversprechen "sieht nie mehr als erlaubt" | LOW bis MEDIUM | Dependency: bestehende `degraded`-Konvention der Familien. Achtung: auch "systemtags deaktiviert" ist nicht "nichts getaggt", die Zuordnungen bleiben in der Datenbank stehen |
| **T4 Benannte Degradation** im Muster der anderen Familien (Grund + Familie, ohne tagbezogene Zahl) | Hausstil seit v1.2; Microsoft macht es ähnlich ("some content was excluded by an organizational policy") | LOW | Wortlaut in Abstimmung mit dem Vokabular-Gate (SEC-02/03) |
| **T5 Ununterscheidbarkeit im Normalbetrieb**: kein Zähler, keine Namen; `fetch`/`read` einer getaggten Id = gleiche Antwort wie unbekannte Id | Abschnitt 2 | LOW im Code, MEDIUM im Test (Gleichheit der Antworten byte-genau beweisen) | Kollidiert bewusst mit der Cap-Hausregel, Ausnahme dokumentieren |
| **T6 Wirkt beim nächsten Aufruf**: kein oder nur sehr kurzer Cache | Nutzer taggt und fragt sofort nach; ein Cache mit Minuten-TTL ist ein Fenster, in dem frisch Getaggtes noch rausgeht | LOW, aber zieht ein Latenzkostenproblem nach sich | Milestone: ein gebatchter Roundtrip je Antwort, vorher gemessen (BL-16-Kostennotiz) |
| **T7 Alle gleichnamigen sichtbaren Tags vereinigt** (öffentlich + eingeschränkt) | Folgt aus dem Unique-Index (name, visibility, editable) | LOW | Sonst entscheidet die Anlagereihenfolge über den Schutz |
| **T8 Schreibwerkzeuge respektieren das Subtree**: `files.upload`, `upload_binary`, `notes.create` in einen getaggten Ordner werden abgelehnt, mit derselben Antwort wie "Ziel nicht gefunden" | Konkurrent blockt write/move/copy in ausgeschlossene Pfade; sonst Existenzorakel über Konflikte und die KI legt Material in einen Ordner, den sie nicht lesen darf | LOW bis MEDIUM | Hängt an den risikoarmen Writes (v1.0) und an PR #8 (Chunk-Upload) |
| **T9 Notizen folgen dem Tag**: Notizen sind Dateien (Notes-Ids sind Datei-Ids), ein getaggter Notes-Ordner oder eine getaggte Notizdatei fehlt in `notes.search`/`notes.read`/`fetch(note)` | Nutzer denkt in Dateien und taggt im Files-Browser den Notes-Ordner; dass Notizen "anders" sind, erwartet niemand | MEDIUM: Notes-API liefert Id und Kategorie, der Pfad muss abgeleitet werden | Konkurrent filtert Notes ausdrücklich nicht, also auch ein Differenzierer. Pfadableitung vor dem Bau verproben |
| **T10 Doku dreisprachig**: wie taggen, was es bewirkt, was nicht, Grenzen | Milestone-Vorgabe; README-Regeln des Projekts | LOW | Store-Text erst mit dem nächsten Release |
| **T11 Ehrliche Grenze "bindet nur diesen Connector"** | robots.txt-Lehre: ein Signal bindet nur, wer es beachtet. Context Chat, Assistant, Sync-Clients und fremde MCP-Server ignorieren `kein-ki` | LOW (Doku) | Verhindert das gefährlichste Missverständnis: "kein-ki" klingt nach instanzweiter Garantie |
| **T12 Freigabe-Grenze benannt**: ein Tag oberhalb der Freigabewurzel des Eigentümers wirkt beim Empfänger nicht | files_accesscontrol wertet Eigentümer-Vorfahren serverseitig aus, ein nutzerseitiger Connector kann das nicht | LOW (Doku), die Lösung wäre HIGH | Faustregel für die Doku: "Tagge den freigegebenen Ordner selbst, nicht nur seinen Elternordner". Vor dem Festschreiben live messen (MEDIUM) |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes / Abhängigkeit |
|---------|-------------------|------------|-------|
| **D1 Fail-closed statt fail-open** | Der direkte Konkurrent ist dokumentiert fail-open, GitHub Agent Mode ignoriert Ausschlüsse; "im Zweifel nichts" passt zur Behörden-Zielgruppe und zum Core Value | Bereits T3 | Kommunikation: ein Satz im README-Vergleich reicht, keine Konkurrenten-Nennung nötig |
| **D2 Alle Familien, die Dateien tragen**, nicht nur WebDAV-Werkzeuge | Konkurrent: "Notes, Calendar, Contacts, Deck, etc. are not filtered" | Bereits T1 + T9 | unified_search schließt Findling-Treffer (Volltext-Provider) ein, weil er Datei-Ids liefert |
| **D3 Sofortwirkung** | Microsoft bis 4 h/über eine Woche, Google bis 24 h, GitHub 30 min | Bereits T6 | Mit einer Messung belegen (Tag setzen, nächster Aufruf), dann im Doku-Text als Zahl, nicht als Behauptung |
| **D4 Latenzbudget gehalten**: ein gebatchter Roundtrip je Antwort | Konkurrent: 2 Requests **je Tag und Aufruf**, dokumentiert als Last-Treiber | MEDIUM: Messung vor Designentscheidung laut Milestone | Hängt an den Zeitbudgets je Bein in prepare_context (v1.2) |
| **D5 Betriebsarten-Doku** Selbstbedienung vs. Organisationsmodus (eingeschränkt + Gruppen-Delegation) | Nextcloud kann das schon, niemand erklärt es; kostet uns keine Zeile Code | LOW | Einziger Ort, an dem die `oc:groups`-Delegation für Nicht-Kunden beschrieben wird (Portal-Artikel ist Subscriber-Inhalt) |
| **D6 Prüfkommando** (`occ mcp_connector:...:check`-Stil wie beim Exchange): meldet, ob `kein-ki` existiert, in welchen Klassen, ob eine unsichtbare Variante wirkungslos herumliegt, ob systemtags an ist | Erkennt die typischen Fail-open-Konfigurationen durch Menschen (falsche Klasse, Tippfehler-Tag, fehlendes Tag) | MEDIUM | Wiederverwendet das Muster `exchange:check` aus v1.6. Kandidat für v1.7, falls Budget, sonst v1.x |
| **D7 Case-insensitiver Namensabgleich** (`Kein-KI`, `KEIN-KI` zählen mit) | Nutzer tippen Tags frei; Irrtum soll in Richtung "mehr ausgeschlossen" fallen | LOW | Nur Groß/Klein und Randleerzeichen normalisieren, keine Unicode-Ähnlichkeitssuche (siehe Anti-Features) |
| **D8 Audit-Anschluss**: Zahl gefilterter Einträge je Aufruf ins bestehende hash-verkettete Audit-Log, ohne Namen | Beweisbarkeit für Enterprise ("die Grenze hat gegriffen") | LOW bis MEDIUM | Audit-Log ist ab Werk aus (v1.5); Zahl nur admin-seitig, nie ans Modell. P3, eher Enterprise-Governance |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **"n Einträge zurückgehalten"-Zähler je Antwort** | Transparenz, Hausregel "Caps benennen sich" | Such- und Existenzorakel für ein injiziertes Modell (Abschnitt 2) | Statischer Mechanismus-Hinweis + degraded nur bei gescheiterter Prüfung |
| **Eigene Fehlermeldung "durch kein-ki geschützt"** bei fetch/read | Nutzer soll verstehen, warum | Existenzorakel über Ids | Gleiche Antwort wie unbekannte Id; die Erklärung steht statisch in der Werkzeugbeschreibung und der Doku |
| **Frei konfigurierbarer Tag-Name / Tag-Liste in v1** (Konkurrent: `EXCLUDED_TAGS`) | Internationales Publikum, bestehende Tags wie "vertraulich" | Jede Konfigurationsstelle ist eine Fail-open-Stelle (Tippfehler = nichts ausgeschlossen, ohne Fehler); mehr Test- und Doku-Fläche; "Konfiguration" ist laut Dossier Enterprise-Governance | Fester Name `kein-ki` in v1. Ein Admin-Alias ist v1.x-Kandidat, falls Nachfrage kommt, dann mit Prüfkommando (D6) |
| **Aliase `no-ai`, `noai`, `keine-ki`** | Internationalität | Vergrößert die Spoofing-Fläche und die Doku; Nutzer wissen nie, welcher gilt | Ein Name, dreisprachig erklärt |
| **Unicode-Ähnlichkeitsabgleich** (Homoglyphen `kein-kі`) | Schutz vor Versehen | Unvorhersehbar, falsch-positive Ausschlüsse, schwer testbar | Prüfkommando listet ähnlich aussehende Tags als Warnung (D6); Doku empfiehlt, dass der Admin `kein-ki` einmal anlegt und `restrict_creation_to_admin` erwägt |
| **Allow-Modus** ("nur Getaggtes sichtbar", wie context_chat-PR "AI knowledge") | Sicherere Voreinstellung für Behörden | Kehrt das Produktversprechen um, macht die Installation ab Werk nutzlos; laut Dossier ausdrücklich Enterprise-Governance | Später in Connector Enterprise; v1.7 nur Deny |
| **Ausnahme im ausgeschlossenen Ordner** ("ki-erlaubt" im kein-ki-Ordner, robots.txt-`Allow`) | Feinsteuerung | Präzedenzregeln, schwer erklärbar, Fehlerquelle fail-open | Datei aus dem Ordner verschieben |
| **Ausschluss für Kalender, Kontakte, Mail, Tables, Deck-Karten über andere Mittel** (Kategorien, Labels) | "kein-ki überall" | Diese Objekte haben keine System-Tags; eigene Markierungsmechanik je Familie = Scope-Explosion | v1.7 nur Datei-Objekte; Doku sagt klar, welche Familien betroffen sind |
| **Eigene Tag-UI, Kontextmenü, Einstellungsseite** | Komfort | Nextcloud hat Tag-Picker, Massen-Tagging und Tag-Verwaltung; eigener Code wäre Wartung ohne Mehrwert | Doku mit Screenshot-freiem Klickpfad |
| **Längerer Cache der getaggten Menge** | Latenz | Frisch Getaggtes geht bis zum Ablauf raus: fail-open im Zeitfenster; zerstört D3 | Gebatchter Roundtrip je Antwort, gemessen (D4) |
| **Inhaltsbasierte Auto-Klassifizierung** (DLP-Scan wie Purview/Gemini) | "Automatisch sensible Dateien erkennen" | Eigener Index/Scanner widerspricht "kein eigener LLM/RAG-Index"; Falsch-Negative erzeugen Scheinsicherheit | Nextcloud-Workflow "Automated tagging" (files_automatedtagging) kann `kein-ki` regelbasiert setzen, in der Doku erwähnen |
| **Admin-Schalter "kein-ki-Prüfung aus"** | Instanzen mit abgeschaltetem systemtags verlieren sonst alle Dateitreffer | Macht eine Sicherheitsgrenze abschaltbar; Dossier: Sicherheitsgrenzen sind nie bezahlt und nie optional | **Offene Frage für die discuss-phase** (siehe unten); Default wäre in jedem Fall an |
| **Persönliche Tags / Favoriten (`oc:tags`) als Ausschlussquelle** | Nutzer verwechseln "Tags" und "Favoriten" | Anderer Mechanismus, anderes Rechtemodell | Doku: "kollaboratives Tag im Tag-Feld der Seitenleiste", nicht Favorit |

## Feature Dependencies

```
[T7 Tag-Auflösung: alle sichtbaren kein-ki-Tags vereinigt]
    └──requires──> [systemtags-Abfrage im Nutzerkontext, gebatcht (D4, Messung zuerst)]

[T2 Subtree-Semantik]
    └──requires──> [T7] + [Pfadnormalisierung, Muster NC_MCP_FILES_ROOT-Sandbox]

[T1 Filter in allen Dateiantworten]
    └──requires──> [T2]
    └──requires──> [Id-Codec als einzige Quelle (v1.3 TOOL-18)] für unified_search/fetch
    └──requires──> [T3 Fail-closed] + [T4 degraded-Eintrag]

[T9 Notizen] ──requires──> [T1] + [Pfadableitung Note-Id → Datei (verproben)]
[T8 Schreibwerkzeuge] ──requires──> [T2]
[T5 Ununterscheidbarkeit] ──conflicts──> [prepare_context-Hausregel "jeder Cap benennt sich"] (bewusste Ausnahme dokumentieren)
[D6 Prüfkommando] ──enhances──> [T7] (findet Fail-open-Konfigurationen)
[D8 Audit-Zähler] ──requires──> [Audit-Log v1.5, ab Werk aus]
[T10/T11/T12 Doku] ──requires──> [T1..T9 gemessen] (Doku sagt das Gemessene)
[files_update-Community-PR (#9)] ──must respect──> [T8] (Schnittstelle vorab im Design-Issue benennen)
```

### Dependency Notes

- **T1 requires Id-Codec:** unified_search liefert Treffer mehrerer Provider (inkl. Findling). Nur über die zentrale Id-Auflösung lässt sich jeder Treffer, der auf eine Datei zeigt, einheitlich prüfen; ein Filter je Provider vergisst den nächsten Provider.
- **T3 und T5 zusammen:** Die Antwort kennt genau zwei Zustände: "gefiltert, unsichtbar" (Normalbetrieb) und "Dateien zurückgehalten, Prüfung nicht verfügbar" (degraded). Einen dritten Zustand "teilweise geprüft" darf es nicht geben.
- **T8 und files_update:** Der Community-PR (Daniel/simul8) überschneidet sich laut PROJECT.md nicht in der Fläche, aber ein künftiges `files_update` muss dieselbe Subtree-Prüfung nutzen. Das gehört als Hinweis ins Design-Issue #9, nicht in diesen Milestone-Code.
- **T12 (Freigaben) begrenzt T2:** Subtree-Semantik gilt verlässlich für den eigenen Baum des Nutzers und für Tags ab der Freigabewurzel abwärts. Darüber hinaus nicht, weil der Connector die Vorfahren des Eigentümers nicht sehen kann. Das ist eine Architekturfrage (ARCHITECTURE/PITFALLS), feature-seitig wird sie als dokumentierte Grenze behandelt.

## MVP Definition

### Launch With (v1.7)

- [ ] T7 Tag-Auflösung (alle sichtbaren `kein-ki`, case-insensitiv nach D7): Grundlage für alles
- [ ] T2 Subtree-Semantik: Milestone-Vorgabe
- [ ] T1 Filter in files, unified_search, ChatGPT-search/fetch, prepare_context-Suchbein: Milestone-Vorgabe
- [ ] T3 + T4 Fail-closed mit benannter Degradation: Milestone-Vorgabe, Differenzierer D1
- [ ] T5 Ununterscheidbarkeit inkl. gleicher Antwort bei fetch/read: sonst ist das Feature ein Orakel
- [ ] T6/D4 ein gebatchter Roundtrip je Antwort, vorher gemessen: Milestone-Vorgabe
- [ ] T8 Schreibwerkzeuge ins ausgeschlossene Subtree abgelehnt: kleines Delta, schließt das Konflikt-Orakel
- [ ] T9 Notizen: falls die Pfadableitung billig verprobt ist; sonst als dokumentierte Grenze in v1.x
- [ ] T10 bis T12 Doku dreisprachig inkl. Betriebsarten (D5) und ehrlicher Grenzen

### Add After Validation (v1.x)

- [ ] D6 Prüfkommando: sobald der erste Nutzer ein wirkungsloses Tag (unsichtbar, Tippfehler) meldet oder als Aufwärmer, wenn in v1.7 Budget übrig ist
- [ ] Admin-Alias für den Tag-Namen: nur bei nachgewiesener Nachfrage aus nicht-deutschsprachigen Instanzen, zusammen mit D6
- [ ] Anhänge in Talk/Deck/Mail, die auf getaggte Dateien zeigen: Auslöser ist ein konkreter Fall; Talk-Nachrichten mit geteilter Datei tragen Datei-Ids und wären technisch erreichbar

### Future Consideration (v2+ / Connector Enterprise)

- [ ] Allow-Modus, zentrale Policies, erzwungene Tag-Klasse, Vier-Augen beim Entfernen: Governance, laut Dossier bezahlt
- [ ] D8 Audit-Zähler als "Beweis, dass die Grenze gegriffen hat": Enterprise-Beweisbaustein
- [ ] Eigentümer-Vorfahren bei Freigaben auswerten (serverseitige Hilfe nötig): nur wenn T12 in der Praxis schmerzt

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| T7 Tag-Auflösung vereinigt | HIGH | LOW | P1 |
| T2 Subtree | HIGH | MEDIUM | P1 |
| T1 Filter über alle Dateiantworten | HIGH | MEDIUM | P1 |
| T3/T4 Fail-closed + degraded | HIGH | LOW | P1 |
| T5 Ununterscheidbarkeit | HIGH | LOW (Test MEDIUM) | P1 |
| T6/D4 gebatcht, ohne Cache | HIGH | MEDIUM | P1 |
| T8 Schreibwerkzeuge | MEDIUM | LOW | P1 |
| T10 bis T12 Doku + Grenzen | HIGH | LOW | P1 |
| T9 Notizen | MEDIUM | MEDIUM | P1/P2 (nach Verprobung) |
| D5 Betriebsarten-Doku | MEDIUM | LOW | P1 (Teil von T10) |
| D7 case-insensitiv | MEDIUM | LOW | P1 |
| D6 Prüfkommando | MEDIUM | MEDIUM | P2 |
| Admin-Alias Tag-Name | LOW | MEDIUM | P3 |
| D8 Audit-Zähler | LOW (v1), HIGH (Enterprise) | LOW | P3 |

## Erwartete UX für die Person, die taggt

Nichts zu bauen, aber die Konventionen entscheiden, ob das Feature im Alltag trägt:

- **Name:** `kein-ki`, klein, mit Bindestrich, ohne Umlaut (Umlautregel gilt nur für Prosa, nicht für Bezeichner). In englischer und französischer Doku den Namen unverändert lassen und einmal übersetzen ("kein-ki, German for no-AI"). Das context_chat-Gegenstück heißt "AI knowledge", der Konkurrent zeigt `no-ai` als Beispiel; ein deutscher Name ist für die Behörden-Zielgruppe ein Plus, für internationale Selfhoster eine Hürde, die nur Doku löst.
- **Klickpfad in der Doku:** Datei/Ordner → Seitenleiste → Tags → `kein-ki` wählen oder anlegen; Mehrfachauswahl → "Tags verwalten" für Massen-Tagging (NC 31+). Hinweis: kollaboratives Tag, nicht Favorit.
- **Was der Nutzer wissen muss (Pflichtabsätze):**
  1. Wirkung ab dem nächsten Werkzeugaufruf (mit gemessener Zahl).
  2. Das Tag ist global an der Datei: es schützt die Datei vor **jedem** Konto, das sie über diesen Connector sieht, und jeder Mitbearbeiter sieht das Tag (das Tag selbst signalisiert "sensibel").
  3. Wer es entfernen kann (Mitbearbeiter bei kollaborativer Klasse) und wie der Admin das verhindert (eingeschränkte Klasse, Gruppen-Delegation).
  4. Was nicht geschützt ist: andere KI-Apps in Nextcloud, Sync-Clients, fremde MCP-Server; Kalender, Kontakte, Mail, Tables, Deck-Karten; Tags oberhalb einer Freigabewurzel.
  5. Wie man es selbst prüft: den Assistenten den Ordner auflisten lassen; das getaggte Element fehlt ohne Kommentar.
  6. Dass die KI den Grund nicht nennt, und warum (ein Satz zum Orakel-Risiko).
- **Automatisierung erwähnen:** Mit der Nextcloud-App "Automated tagging" kann ein Admin `kein-ki` regelbasiert setzen (z. B. alles in einer Gruppenordner-Struktur); dort sind auch eingeschränkte Tags ohne Nutzerrechte zuweisbar.

## Wie Wettbewerber fail-closed-Degradation kommunizieren

| Anbieter | Kommunikation im Fehler-/Ausschlussfall | Lehre |
|---|---|---|
| Microsoft Copilot (externe Mail) | "some content was excluded by an organizational policy", pauschal, ohne Zahl | Pauschaler Satz ohne Details ist der akzeptierte Industriestandard |
| Microsoft Copilot (Prompt-DLP, Office-Apps, Preview) | Doku räumt ein, dass die Meldung "might not clearly state that the interaction is blocked" | Schlechte Degradationsmeldung wird als Mangel dokumentiert: Nutzer erwarten eine Meldung |
| SharePoint RCD | Sichtbarer "Restricted"-Marker an der Site, Copilot-Einstiege ausgeblendet | Markierung an der Quelle statt in der Antwort (bei uns: das Tag selbst ist der Marker) |
| Google Gemini DLP | Offizielle Doku schweigt zur Nutzer-Meldung | Nicht belegbar, nicht nachahmen |
| cbcoutinho | Kein Fail-closed; Warnung nur im Server-Log | Der Nutzer erfährt nie, dass der Schutz gerade nicht wirkte |
| GitHub Copilot | Agent Mode unterstützt Ausschluss nicht, steht nur in der Doku | Eine dokumentierte Lücke ist besser als keine, aber schlechter als fail-closed |

**Empfehlung für den degraded-Wortlaut:** ein Satz, Grund als feste Kategorie (`tag-check-unavailable` mit Unterart deaktiviert / Fehler / Zeitüberschreitung), Aussage "Dateitreffer in dieser Antwort zurückgehalten", Handlungshinweis "später erneut versuchen oder Admin fragen". Keine Zahl der zurückgehaltenen Einträge, damit der Satz in allen Werkzeugen gleich bleibt und später nicht versehentlich im Normalbetrieb auftaucht.

## Offene Fragen für die discuss-phase

1. **Ordner-Tag = freie Ordner-Ausschlussliste?** (aus PROJECT.md) Feature-seitig ja: ein getaggter Ordner *ist* die Ausschlussliste, jede zweite Liste (Env/Admin-Setting) wäre eine zweite Wahrheit und eine zusätzliche Fail-open-Stelle. Empfehlung: keine separate Liste.
2. **Instanzen mit deaktiviertem systemtags:** Fail-closed heißt dort "Dateifamilien liefern nie etwas". Admin-Schalter zum Abschalten (Grenze abschaltbar) oder bewusst nicht (Admin muss systemtags einschalten)? Empfehlung: kein Schalter, klare Fehlermeldung im degraded und im Prüfkommando; systemtags ist ab Werk an.
3. **Notizen (T9) in v1.7 oder v1.x:** hängt an der Verprobung, ob sich der Dateipfad einer Notiz ohne Zusatz-Roundtrip bestimmen lässt.

## Competitor Feature Analysis

| Feature | cbcoutinho/nextcloud-mcp-server | Microsoft 365 Copilot | Our Approach |
|---------|--------------|--------------|--------------|
| Markierung | Frei konfigurierbare Tag-Namensliste | Sensitivity Label bzw. Site-Schalter | Fester Tag-Name `kein-ki` |
| Granularität | Datei + Ordner-Präfix | Datei (Label), Site (RCD) | Datei + Ordner-Subtree |
| Wer setzt | Admin legt nicht zuweisbares Tag an (empfohlen) | Compliance-Admin; RCD delegierbar mit Begründung | Selbstbedienung ab Werk, Organisationsmodus per eingeschränkter Klasse dokumentiert |
| Reichweite | Nur WebDAV-Werkzeuge | Copilot-Oberflächen, nicht alle Office-Erlebnisse | Alle dateitragenden Antworten inkl. Suche, fetch, prepare_context, Schreibziele, Notizen |
| Fehlerverhalten | Fail-open je Tag, Log-Warnung | Richtlinie serverseitig, Details nicht offen | Fail-closed mit benanntem degraded-Eintrag |
| Sichtbarkeit des Ausschlusses | Still in Listen, "access denied" beim Lesen | Element bleibt in Zitaten; pauschaler Hinweis bei Mail | Normalbetrieb ununterscheidbar, auch beim Lesen; Hinweis nur statisch und im Fehlerfall |
| Wirkungsverzögerung | Keine (kein Cache) | bis 4 h (DLP), über eine Woche (RCD) | Keine, gemessen belegt |
| Last | 2 Requests je Tag und Aufruf | n/a | 1 gebatchter Roundtrip je Antwort |

## Sources

- nextcloud/server master, Quellcode: `lib/private/SystemTag/SystemTagManager.php` (canUserAssignTag/UpdateTag/CreateTag/SeeTag), `apps/dav/lib/SystemTag/SystemTagNode.php` (Rename nur Admin), `SystemTagsObjectMappingCollection.php` + `SystemTagMappingNode.php` + `SystemTagsRelationsCollection.php` (PERMISSION_UPDATE für Zuweisen/Entfernen), `core/Migrations/Version13000Date20170718121200.php` (Unique-Index name/visibility/editable) (HIGH)
- https://docs.nextcloud.com/server/stable/user_manual/en/files/tagging.html (Tag-Klassen, HIGH)
- https://docs.nextcloud.com/server/stable/admin_manual/file_workflows/access_control.html (files_accesscontrol, Eigentümer-Vorfahren, Context-Chat-Bypass, HIGH)
- https://docs.nextcloud.com/server/stable/admin_manual/file_workflows/automated_tagging.html (Automated tagging, HIGH)
- https://portal.nextcloud.com/article/Collaboration/Managing-tags-by-group (`oc:groups`, MEDIUM, Subscriber-Inhalt nur teilweise lesbar)
- https://github.com/nextcloud/server/pull/51288 (restrict_creation_to_admin, NC 31 Backport, HIGH)
- https://github.com/nextcloud/server/issues/64662 (Zuweisungsbug NC 34, geschlossen, MEDIUM)
- https://github.com/nextcloud/context_chat/pull/277 und https://github.com/nextcloud/assistant/issues/638 (Allow-List "AI knowledge", offen, MEDIUM)
- https://github.com/cbcoutinho/nextcloud-mcp-server (`nextcloud_mcp_server/server/tag_exclusion.py`, `docs/configuration.md`, CHANGELOG v0.80.0 vom 2026-05-06, HIGH)
- https://learn.microsoft.com/en-us/purview/dlp-microsoft365-copilot-location-learn-about (aktualisiert 2026-09-17, HIGH)
- https://learn.microsoft.com/en-us/sharepoint/restricted-content-discovery (aktualisiert 2026-09-22, HIGH)
- https://knowledge.workspace.google.com/admin/security/about-dlp-for-gemini (MEDIUM, UX-Details fehlen)
- https://docs.github.com/en/copilot/how-tos/configure-content-exclusion/exclude-content-from-copilot (HIGH)
- https://www.w3.org/community/reports/tdmrep/CG-FINAL-tdmrep-20240510/ und https://github.com/w3c/tdm-reservation-protocol/blob/main/docs/robots.md (HIGH für Semantik, freiwillige Bindung)
- Projektkontext: `.planning/PROJECT.md`, `src/mcp_connector/tools/*.py` (Werkzeugliste), `src/mcp_connector/config.py` (`NC_MCP_FILES_ROOT`-Sandbox), `tools/context.py` (degraded-Hausregel)

---
*Feature research for: KI-Ausschluss-Tag kein-ki im Nextcloud-MCP-Connector*
*Researched: 2026-09-26*

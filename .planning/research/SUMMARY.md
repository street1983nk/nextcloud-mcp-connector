# Project Research Summary

**Project:** Nextcloud MCP Connector, Milestone v1.7 "Ausschluss-Tag kein-ki" (BL-16)
**Domain:** Sicherheitsgrenze in einem bestehenden MCP-Server: ein System-Tag auf Datei oder Ordner hält Inhalte fail-closed aus allen dateitragenden Werkzeugantworten heraus
**Researched:** 2026-09-26
**Confidence:** MEDIUM-HIGH (siehe Aufschlüsselung unten; die eigene Codebasis ist HIGH belegt, das Server-Verhalten von Nextcloud ist teils gemessen/HIGH, teils nur aus dem Quelltext gelesen/MEDIUM)

## Executive Summary

Dieses Feature ist kein neues Werkzeug, sondern eine Sicherheitsgrenze quer durch einen bereits produktiven Connector mit 22 registrierten Tools. Alle vier Recherchen kommen unabhängig zum selben Kern: Es gibt keine OCS- oder Batch-API für System-Tags, aber es gibt genau eine gebatchte Route, REPORT oc:filter-files mit oc:systemtag auf /remote.php/dav/files/{user}/, die in einem einzigen Roundtrip alle direkt getaggten Dateien und Ordner des Nutzers liefert, unabhängig von der Trefferzahl. Weil Nextcloud keine Vererbung von Tags an Unterordner kennt, muss der Connector die Subtree-Semantik selbst bauen: getaggte Menge einmal holen, Pfade und fileids lokal per Präfixvergleich prüfen. Das schlägt jede Alternative (Ahnenkette pro Treffer, nc:system-tags pro Datei), weil nur dieser Weg mit einem Roundtrip auskommt und weil ein Vorfahren-Walk bei tiefen Ordnerbäumen das Latenzbudget von prepare_context sprengen würde.

Der empfohlene Ansatz in einem Satz: Ein request-gebundener ExclusionGuard hängt am ohnehin einmal pro Aufruf gebauten NcClients-Objekt, lädt beim ersten Zugriff genau einmal die getaggte Menge (Tag-Id-Auflösung + REPORT, parallel zur eigentlichen Arbeit gestartet), und liefert entweder eine prüfbare ExclusionView oder einen expliziten Unchecked-Zustand. Nur Unchecked löst Fail-closed aus (alle dateitragenden Einträge der Antwort werden mit einem benannten degraded-Eintrag zurückgehalten); ein erfolgreicher Ausschluss dagegen ist im Normalbetrieb absichtlich nicht von Nichtexistenz zu unterscheiden, byte-gleich bis in den Fehlertext. Das ist die bewusste Ausnahme von der sonstigen Hausregel "jede Kappung benennt sich", weil ein Zähler oder ein eigener Fehlertext für eine ausgeschlossene Datei ein Such- und Existenzorakel für ein potenziell durch Prompt-Injection gesteuertes Modell wäre. Alle vier Recherchen halten das übereinstimmend für den entscheidenden Sicherheitspunkt des gesamten Features.

Die größten Risiken sind, in dieser Reihenfolge: (1) Bypass über die neun bis elf Wege, auf denen Dateiinhalt heute schon aus dem Connector kommt (fetch per fileid, Notes, Talk-Dateiparameter, die Unified-Search-Provider systemtags und findling), wenn der Filter nur an den offensichtlichen Datei-Tools hängt; (2) Fail-open durch Fehlinterpretation von Nextcloud-Zuständen, die wie "nichts getaggt" aussehen, es aber nicht sind (unsichtbares Tag, veraltete Tag-Id nach 412, deaktivierte systemtags-App, mehrere gleichnamige Tags); (3) Latenz durch N+1-Abfragen bei naiver Umsetzung, besonders bei tiefen Ordnerbäumen oder Instanzen mit vielen (z. B. durch Recognize automatisch gesetzten) Tag-Zuordnungen; (4) die harte, nicht lösbare Grenze, dass Subtree-Schutz an Freigabegrenzen zerbricht, weil der Connector nur sieht, was der jeweilige Nutzer sieht. Mitigation für alle vier: ein Klassifikations-Gate/Contract-Test über die aktive Tool-Registry plus ein Kanarientest, ein Drei-Zustandsmodell (NO_TAG/SET/UNKNOWN) statt eines binären Caches, ein Mess-Spike vor der Architekturentscheidung, und eine ehrlich dokumentierte Grenze statt eines falschen Vollständigkeitsversprechens.

## Key Findings

### Recommended Stack

Keine neue Abhängigkeit nötig. httpx und lxml, die im Projekt bereits für WebDAV-SEARCH/PROPFIND genutzt werden, reichen für die zwei zusätzlichen Aufrufe komplett aus.

**Core technologies:**
- httpx (unverändert, 0.28.x): PROPFIND auf /remote.php/dav/systemtags/ und REPORT auf /remote.php/dav/files/{user}/, gleiche Methodenaufrufe, Auth und Statusregeln wie das vorhandene dav.py
- lxml (vorhanden): Request-Bodies bauen, Antworten härten, gleiches Baumuster wie build_search_body, parse_root trägt bereits XXE-Schutz
- Nextcloud WebDAV/Sabre, App dav: einzige API-Fläche für System-Tags, dav ist alwaysEnabled, SystemTagPlugin und FilesReportPlugin werden bedingungslos registriert, unabhängig davon, ob die UI-App systemtags aktiv ist

Zwei neue Client-Funktionen im Stil der vorhandenen (resolve_tag_ids, tagged_paths/home_entries) reichen als Integrationsfläche; die Route ist von NC 32 bis 35 semantisch identisch (Quelldiff zeigt nur Cast-/Strict-Änderungen).

### Expected Features

**Must have (table stakes):**
- Tag-Auflösung über alle sichtbaren, gleichnamigen kein-ki-Tags vereinigt (case-insensitiv), weil der Unique-Index auf (Name, Sichtbarkeit, Zuweisbarkeit) bis zu drei gleichnamige Tags zulässt
- Subtree-Semantik: Tag auf Ordner deckt alle Nachfahren, per Präfixvergleich gegen die einmal geholte getaggte Menge
- Filter in allen dateiliefernden Antworten (files, unified_search, ChatGPT search/fetch, prepare_context), nicht nur in den offensichtlichen Files-Tools
- Fail-closed mit benannter Degradation ausschließlich dann, wenn die Tag-Prüfung selbst nicht beantwortbar ist
- Ununterscheidbarkeit im Normalbetrieb: kein Zähler, keine Namen, fetch/read einer ausgeschlossenen Id antwortet byte-gleich wie eine unbekannte Id
- Ein gebatchter Roundtrip je Antwort, kein oder nur sehr kurzlebiger (single-flight, pro Aufruf) Cache, damit das Tag ab dem nächsten Aufruf wirkt
- Schreibwerkzeuge respektieren das Subtree (Ablehnung mit gleichem Wortlaut wie "Ziel nicht gefunden")
- Dreisprachige Doku mit ehrlichen Grenzen (bindet nur diesen Connector, Freigabegrenze, unsichtbares Tag wirkt nicht)

**Should have (competitive):**
- Fail-closed statt fail-open als expliziter Differenzierer gegenüber dem direkten Konkurrenten (cbcoutinho, dokumentiert fail-open) und gegenüber GitHub Copilot (Agent Mode ignoriert Ausschlüsse)
- Sofortwirkung ohne Cache-Fenster, gemessen und als Zahl in der Doku belegt, gegenüber Microsoft (bis 4 Std./über eine Woche) und Google (bis 24 Std.)
- Betriebsarten-Doku (Selbstbedienung vs. Organisationsmodus mit eingeschränkter Tag-Klasse und Gruppen-Delegation), ohne dass dafür Code nötig ist
- Prüfkommando (occ ...:exclusion:check) nach dem Muster von exchange:check, das wirkungslose Konfigurationen (unsichtbares Tag, Tippfehler, systemtags aus) meldet

**Defer (v2+ / Connector Enterprise):**
- Frei konfigurierbarer Tag-Name/Alias-Liste, Allow-Modus, zentrale erzwungene Tag-Klasse, Audit-Zähler als Enterprise-Beweisbaustein, Vier-Augen-Prinzip beim Entfernen

### Architecture Approach

Der Filter gehört an sechs Engstellen, durch die nachweislich jede dateiabgeleitete Antwort läuft (files.search, files.list_dir, Einzelzugriff hinter stat/find_by_fileid, search._normalise, zwei Notes-Leser), nicht in den generischen graceful-Wrapper und nicht in 22 Einzelregistrierungen verdrahtet. Der Tag-Blick hängt an einem neuen dritten Feld von NcClients (exclusion: ExclusionGuard), das genau einmal pro Tool-Aufruf gebaut wird; ein asyncio.Lock sorgt für Single-Flight, sodass parallele Teilaufrufe (z. B. drei gleichzeitige Excerpt-Abrufe in prepare_context) nur einen Netzabruf auslösen. Die getaggte Menge selbst wird NICHT wie parse_entries durch die Sandbox-Wurzel gefiltert, weil ein getaggter Vorfahre oberhalb der NC_MCP_FILES_ROOT-Sandbox sonst fälschlich herausfällt.

**Major components:**
1. nextcloud/clients/systemtags.py (neu): rohe HTTP-Auflösung Name-zu-Id und REPORT der getaggten Knoten, policy-frei
2. nextcloud/exclusion.py (neu): ExclusionView (rein, ohne I/O, testbar) und ExclusionGuard (request-gebunden, Drei-Zustandsmodell NO_TAG/SET/UNKNOWN)
3. tools/files.py, tools/search.py, tools/notes.py (geändert): Anwendung des Guards an den sechs Engstellen, vor dem Fenstern/Paginieren
4. tests/contract/ (neu): Klassifikations-Gate über alle registrierten Tools plus Kanarientest gegen die aktive Registry

### Critical Pitfalls

1. **Bypass über vergessene Wege**: der Filter wird nur in den offensichtlichen Files-Tools gebaut, während fetch-per-fileid, Notes, Talk-Dateiparameter und die Unified-Search-Provider systemtags/findling weiterhin ungefiltert liefern. Vermeidung: ein Klassifikations-Freeze-Test über die aktive Registry plus ein Kanarientest mit eindeutigem Kanarienwort in Datei, Ordner, Notiz, Talk-Parameter und Suchprovidern.
2. **Fail-open durch falsch gedeutete Normalzustände**: 412 nach gelöschter/neu angelegter Tag-Id, unsichtbares Tag, deaktivierte systemtags-App und mehrere gleichnamige Tags sehen alle wie "nichts getaggt" aus, sind es aber nicht. Vermeidung: explizites Drei-Zustandsmodell, kein negatives Caching, Vereinigung aller sichtbaren gleichnamigen Tags.
3. **Latenz durch N+1**: eine Prüfung pro Treffer oder pro Vorfahr sprengt das Budget bei tiefen Bäumen oder Instanzen mit vielen Tag-Zuordnungen (Recognize kann hunderte automatisch setzen). Vermeidung: ein REPORT je Antwort, lokale Präfixprüfung, Mess-Spike vor der Designentscheidung.
4. **Informationslecks im Erfolgsfall**: ein Zähler, ein eigener Fehlertext oder eine dynamische Toolbeschreibung verrät die Existenz einer ausgeschlossenen Datei. Vermeidung: byte-gleiche Antworten zwischen "ausgeschlossen" und "existiert nicht", Paartests dafür.
5. **Subtree bricht an Freigabegrenzen und Speicherwechseln**: ein Tag auf einem Ordner oberhalb der Freigabewurzel des Eigentümers ist für den Empfänger unsichtbar und wirkt für ihn nicht; das ist eine Nutzer-API-Grenze, keine Implementierungsschwäche. Vermeidung: als ehrliche Grenze dokumentieren, nicht versuchen technisch zu lösen.

## Widersprüche zwischen den Recherchedateien

Diese vier Punkte sehen auf den ersten Blick nach Widerspruch aus, sind aber vor allem ein Unterschied in der Evidenzstärke. Massgeblich ist jeweils die Datei mit der stärkeren Beleglage (gemessen schlägt aus dem Quelltext gelesen).

1. **Verhalten bei abgeschalteter systemtags-App.** STACK.md hat es live gegen eine laufende NC 35.0.0 gemessen (HIGH): Die DAV-API antwortet unverändert weiter, REPORT und nc:system-tags liefern korrekt, nur die Capability systemtags.enabled und der Unified-Search-Provider systemtags verschwinden. PITFALLS.md und ARCHITECTURE.md kommen inhaltlich zum selben Schluss, stufen ihn aber als MEDIUM ein ("laut Quelle", "in der Messphase zu belegen"), weil beide nur den Servercode gelesen haben. Die "Schutz fällt weg"-Lesart, vor der PITFALLS ausdrücklich warnt, wäre also ein Fehlschluss, der durch STACKs Messung bereits widerlegt ist: Massgeblich für "ist die Prüfung beantwortbar" ist der Erfolg des REPORT-Aufrufs selbst, nicht die Capability. Für die Roadmap heißt das: kein Gaten auf die Capability, aber die Messphase (Schritt 0) sollte diesen Befund zusätzlich gegen NC 32 bis 34 verifizieren, weil STACK nur NC 35 tatsächlich gemessen hat.

2. **Ob der REPORT-Zielpfad die Trefferauswahl beeinflusst.** STACK.md hat gemessen, dass oc:filter-files mit oc:systemtag den Zielordner des REPORT komplett ignoriert und stattdessen immer über searchBySystemTag() den gesamten Nutzerbaum durchsucht (ein REPORT auf einen Unterordner lieferte trotzdem einen weiter oben liegenden getaggten Ordner). ARCHITECTURE.md begründet die Empfehlung "REPORT auf die Home-Wurzel schicken, nicht die Sandbox-Wurzel" dagegen mit der (MEDIUM, nur aus dem Quelltext gelesenen) Annahme, FilesReportPlugin schränke "auf den Teilbaum des Ziels" ein. Das widerspricht STACKs Messung direkt. Die praktische Empfehlung selbst (Home-Wurzel als Ziel verwenden) bleibt trotzdem richtig, aber aus einem anderen Grund: nicht weil der Zielpfad das Suchergebnis einschränkt, sondern weil Konsistenz und Einfachheit dafür sprechen, immer denselben, garantiert erreichbaren Pfad als Ziel zu nehmen. Der Mess-Spike (Architektur-Schritt 0) sollte diese Annahme explizit klarstellen, damit kein Code auf eine tatsächlich nicht existierende Zielpfad-Einschränkung setzt.

3. **Notiz-Id gleich Datei-Id.** FEATURES.md und STACK.md (Integrationsabschnitt) behandeln "Notes-Id = fileid" als gegebene Tatsache, ohne Vorbehalt. ARCHITECTURE.md und PITFALLS.md markieren genau dieselbe Aussage ausdrücklich als LOW/"Allgemeinwissen, nicht verifiziert" und verlangen eine Messung vor dem Bau von T9 (Notizen-Unterstützung). Für die Roadmap gilt die vorsichtigere Einstufung: T9 hängt am Mess-Spike, nicht an der in FEATURES/STACK unterstellten Tatsache. Fällt die Annahme in der Messung durch, verschiebt sich T9 nach v1.x (das sieht auch die MVP-Definition in FEATURES.md bereits als Fallback vor).

4. **Ist "Zählen oder Schweigen bei ausgeschlossenen Treffern" noch offen?** FEATURES.md beantwortet diese Frage in Abschnitt 2 bereits ausführlich und eindeutig mit "schweigen" (Zähler = Anti-Feature, konkretes Orakel-Risiko durchgerechnet). ARCHITECTURE.md führt dieselbe Frage trotzdem noch als offene Frage 2 für die discuss-phase, PITFALLS.md bestätigt in seinen Vermeidungshinweisen ebenfalls "skipped zählt Ausschlüsse NICHT". Der Widerspruch ist also keiner in der Sache, sondern ein Synchronisationsstand: ARCHITECTURE wurde offenbar vor oder unabhängig von FEATURES' Abschnitt 2 geschrieben. Empfehlung: discuss-phase behandelt dies als Ratifizierung einer bereits getroffenen, gut begründeten Entscheidung, nicht als offene Frage.

## Implications for Roadmap

Basierend auf allen vier Recherchen, insbesondere dem in ARCHITECTURE.md vorgeschlagenen Build Order und dem PITFALLS.md Pitfall-zu-Phase-Mapping, ergibt sich folgende Phasenstruktur:

### Phase 1: Mess-Spike (BL-16-Kostennotiz)
**Rationale:** Mehrere Architekturentscheidungen (Batch-Strategie, Notes-Unterstützung, Cache-Verhalten) hängen an Annahmen, die nur MEDIUM oder LOW belegt sind (siehe Widersprüche oben). Die Milestone-Vorgabe verlangt ausdrücklich Messung vor Designentscheidung.
**Delivers:** Ein Messprotokoll: REPORT-Kosten bei 1/100/5000 getaggten Knoten, 412-Verhalten, unsichtbares Tag, systemtags-App aus (auch auf NC 32/33/34, nicht nur 35), geteilter Unterordner mit getaggtem Vorfahr beim Eigentümer, Notiz-Id gleich Datei-Id, nc:system-tags in SEARCH selektierbar, REPORT im AppAPI-Impersonation-Modus.
**Addresses:** Klärt die Widersprüche 1 bis 3 oben und die MEDIUM/LOW-Lücken der Confidence-Tabelle.
**Avoids:** Pitfall 6 (Latenz/N+1), Pitfall 3 (Fail-open-Zustände), Pitfall 8 (Subtree/Speicher).

### Phase 2: Guard-Kern
**Rationale:** Bevor irgendein Tool angefasst wird, muss die Policy-Schicht stehen und unabhängig testbar sein (reine ExclusionView, request-gebundener ExclusionGuard).
**Delivers:** nextcloud/clients/systemtags.py, nextcloud/exclusion.py, drittes NcClients-Feld, gemeinsame Präfixfunktion mit in_files_root, Drei-Zustandsmodell NO_TAG/SET/UNKNOWN.
**Uses:** httpx/lxml (Stack), keine neue Abhängigkeit.
**Implements:** Architecture-Komponenten 1 und 2 (Pattern 1: Request-gebundener Guard).

### Phase 3: Familien-Anschluss
**Rationale:** Kleinste Fläche zuerst (Dateifamilie), danach Anschluss der Composer-Tools, die die Engstellen erben; Notes hängt an der Mess-Spike-Erkenntnis aus Phase 1.
**Delivers:** E1-E3 (files) inkl. Upload-Entscheidung, E4 (unified_search, provider-agnostisch, parallel zur Provider-Auffächerung), E5/E6 (Notes, falls Phase 1 die Annahme bestätigt) mit benannter Fail-closed-Degradation.
**Addresses:** T1, T2, T3/T4, T5, T8, T9 (bedingt) aus FEATURES.md.
**Avoids:** Pitfall 1 (Bypass), Pitfall 2 (Sandbox-Integration), Pitfall 4 (Fail-closed-Breite), Pitfall 9 (TOCTOU).

### Phase 4: Gates und Verifikation
**Rationale:** "Jede Antwort genau einmal" ist eine Behauptung, die ein Beweis braucht, kein Vertrauen; ein 23. Tool darf nicht ungeprüft durchrutschen.
**Delivers:** Klassifikations-Freeze-Test über die aktive Registry, Kanarientest mit eindeutigem Kanarienwort in allen betroffenen Familien, Paartests (getaggt vs. nicht existent, byte-gleich, auch im Ausfall), Destruktiv-Gate-Nadel auf systemtags-relations/systemtags-Schreibpfade.
**Addresses:** Pitfall 1, Pitfall 5 (Informationslecks) vollständig.

### Phase 5: Doku und Betrieb
**Rationale:** Doku darf nur das Gemessene behaupten (Projektregel: Doku sagt das Gemessene); optionales Prueftooling erkennt Fehlkonfigurationen früh.
**Delivers:** Dreisprachige Doku (Betriebsarten, ehrliche Grenzen bei Freigaben und unsichtbaren Tags, "bindet nur diesen Connector"), optional occ ...:exclusion:check nach dem exchange:check-Muster.
**Addresses:** T10-T12, D5, D6 (falls Budget).

### Phase Ordering Rationale

- Die Messphase steht zuerst, weil drei der vier Recherchen (Stack teils, Architecture, Pitfalls) explizit auf noch unbelegten Annahmen (MEDIUM/LOW) aufbauen, die Designentscheidungen in Phase 2 und 3 direkt beeinflussen (siehe Widersprüche 2 und 3).
- Guard-Kern vor Familien-Anschluss, weil sonst Bestandstests durch unerwartete REPORT-Aufrufe brechen (Architecture nennt das explizit als Build-Order-Grund für eine eigene Test-Infrastruktur-Stufe).
- Familien-Anschluss vor Gates, weil das Klassifikations-Gate erst sinnvoll ist, wenn es echte Guard-Stellen gibt, die es prüfen kann.
- Doku zuletzt, weil sie das Gemessene und Gebaute beschreibt, nicht umgekehrt.

### Research Flags

Phasen, die während der Planung vermutlich vertiefte Recherche brauchen:
- **Phase 1 (Mess-Spike):** braucht Live-Zugriff auf mehrere NC-Versionen (32-35) und präparierte Testdaten (grosse Ordner, viele Tag-Zuordnungen, geteilte Unterordner); technisch anspruchsvoll, keine reine Codierarbeit.
- **Phase 3 (Notes-Teil):** hängt vollständig am Ergebnis von Phase 1; falls die Annahme "Notiz-Id = fileid" nicht hält, braucht dieser Teil eine eigene kurze Recherche zur Notes-REST-API.

Phasen mit etablierten Mustern (Research-Phase kann übersprungen werden):
- **Phase 2 (Guard-Kern):** folgt 1:1 dem bereits im Projekt etablierten Muster (capabilities.py-Cache, oauth/jwks.py-Single-Flight, NcClients-Erweiterung); alle vier Recherchen sind sich hier einig und HIGH auf die eigene Codebasis gestützt.
- **Phase 4 (Gates):** folgt dem vorhandenen Contract-Test-Muster (test_tool_surface.py, test_no_destructive_calls.py).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Quellcode nextcloud/server stable32-35 gelesen und gedifft, Kernaussagen live gegen eine laufende NC 35.0.0 gemessen; einzige MEDIUM-Stelle ist die AppAPI-Impersonation-Variante des REPORT, die noch nicht verprobt wurde |
| Features | MEDIUM-HIGH | Nextcloud-Tag-Rechtemodell und der direkte Konkurrent sind quellcodebelegt (HIGH); Microsoft 365 HIGH (aktuelle Microsoft-Learn-Doku); Google Workspace MEDIUM (UX-Details fehlen in der offiziellen Doku); die eigene Bedrohungsmodell-Ableitung (Zähler = Orakel) ist eine begründete, aber nicht extern validierte Schlussfolgerung |
| Architecture | MEDIUM | Alle Aussagen zur eigenen Codebasis sind HIGH (Datei und Zeile gelesen); das Server-Verhalten von REPORT oc:filter-files ist nur über WebFetch aus dem Quelltext gelesen, nicht gemessen (siehe Widerspruch 2 oben); Notiz-Id-Annahme ist LOW |
| Pitfalls | MEDIUM-HIGH | Eigener Code HIGH; Nextcloud-Tag-Verhalten aus master gelesen (HIGH für master, aber nicht gegen NC 32-35 gemessen, also MEDIUM-HIGH in der Praxis); Speicher-Sonderfälle (Groupfolders, External Storage, speicherübergreifendes Verschieben) sind ausdrücklich MEDIUM bis LOW und als Allgemeinwissen markiert |

**Overall confidence:** MEDIUM-HIGH. Der Kernmechanismus (REPORT tag-zuerst, ein Roundtrip, Drei-Zustandsmodell, byte-gleiche Erfolgsantworten) ist auf hohem Niveau abgesichert und in allen vier Dateien konsistent. Die verbleibende Unsicherheit betrifft Details (Notiz-Id, Verhalten auf älteren NC-Versionen, Speicher-Randfälle), die genau deshalb als erste Phase (Mess-Spike) vor der Architekturfestlegung eingeplant sind.

### Gaps to Address

- **Notiz-Id gleich Datei-Id** (Widerspruch 3): vor Bau von T9 im Mess-Spike verifizieren; sonst T9 nach v1.x verschieben (FEATURES.md hält diesen Fallback bereits offen).
- **REPORT-Zielpfad-Verhalten** (Widerspruch 2): Architecture-Begründung für "Home-Wurzel statt Sandbox-Wurzel" im Mess-Spike klarstellen; Empfehlung bleibt unverändert, Begründung muss korrigiert werden.
- **systemtags-App-aus-Verhalten auf NC 32-34** (Widerspruch 1): nur NC 35 ist tatsächlich gemessen; auf dem gesamten unterstützten Versionsfenster (32-35) verifizieren.
- **AppAPI-Impersonation vs. App-Passwort beim REPORT:** Stack markiert dies MEDIUM; einmal im ExApp-Container verproben, bevor der ExApp-Modus als gleichwertig behandelt wird.
- **Speicher-Randfälle** (Groupfolders-ACL, External-Storage-Neumount, speicherübergreifendes Verschieben): PITFALLS markiert dies LOW/MEDIUM und ausdrücklich nicht gemessen; als Tabelle in der Doku nachziehen, sobald Zeit im Milestone bleibt, sonst als bekannte Grenze benennen.
- **Zwei offene Owner-Entscheidungen ohne technische Präferenz aus der Recherche:** Upload-Verhalten in kein-ki-Ordnern (verbieten vs. erlauben, Existenz-Orakel spricht für Verbieten) und Admin-Schalter zum Abschalten der Prüfung bei deaktivierter systemtags-App (alle drei Feature-/Architektur-/Pitfalls-Recherchen neigen zu "kein Schalter", aber keine trifft die finale Entscheidung).
- **Ordner-Tag als generelle Ausschlussliste per Env-Variable** (vom Owner am 04.09. aufgeworfen): Feature- und Architektur-Recherche empfehlen unabhängig voneinander, keine zweite Liste einzuführen, weil sie eine zweite Fail-open-Stelle wäre; Owner-Bestätigung noch ausstehend.

### Dedupliziert: Offene Fragen für die discuss-phase

1. **Uploads in kein-ki-Ordner:** verbieten (konsequent, schließt das Existenz-Orakel über ConflictError) oder erlauben? (Architecture, Pitfalls)
2. **Admin-Schalter zum Abschalten der Prüfung**, wenn systemtags deaktiviert ist: Default wäre in jedem Fall an; braucht es überhaupt einen Schalter, oder ist eine Sicherheitsgrenze nie optional? (Features, Architecture, Pitfalls, alle tendieren zu "kein Schalter")
3. **Ordner-Tag zugleich freie Ordner-Ausschlussliste per Konfiguration:** eine zweite, konfigurierbare Liste wäre architektonisch identisch zu den tagged_prefixes, aber eine zweite Wahrheitsquelle und Fail-open-Stelle. Empfehlung beider Recherchen: nein. (Features, Architecture, ursprünglich Owner-Frage vom 04.09.)
4. **Notizen (T9) in v1.7 oder v1.x:** hängt vollständig an der Mess-Spike-Verifikation von "Notiz-Id = fileid". (Features, Architecture, Pitfalls)
5. **Sandbox-Parität für Findling und Notes** (beide passieren die bestehende NC_MCP_FILES_ROOT-Sandbox heute ungeprüft, unabhängig vom kein-ki-Feature): in diesem Milestone mitnehmen oder als eigenen Backlog-Punkt führen? (Architecture, Stack-Nebenbefund, Pitfalls-Integration-Gotcha)
6. **Zählen oder schweigen bei ausgeschlossenen Treffern:** bereits in FEATURES.md klar mit "schweigen" beantwortet (Orakel-Risiko); discuss-phase sollte dies ratifizieren, nicht neu aufrollen (siehe Widerspruch 4).

## Sources

### Primary (HIGH confidence)
- github.com/nextcloud/server, Branches stable32-stable35 (per gh api geladen und gedifft): SystemTagPlugin.php, FilesReportPlugin.php, SystemTagManager.php, SystemTagsByIdCollection.php, RootCollection.php, Server.php, FileSearchBackend.php, apps/systemtags/*, core/shipped.json
- Live-Messung 2026-09-26 gegen lokale NC 35.0.0 (nc35-nc), Konten alice/bob, Wegwerf-Tag und App-Passwörter, danach vollständig zurückgebaut
- Eigener Code, gelesen 2026-09-26: nextcloud/clients/dav.py, tools/files.py, tools/search.py, tools/chatgpt.py, tools/context.py, tools/notes.py, tools/talk.py, provider_map.py, deps.py, nextcloud/__init__.py, server/reg_*.py, errors.py, config.py, nextcloud/capabilities.py, tests/contract/*
- nextcloud/server master, direkt gelesen: SystemTagManager.php, SystemTagNode.php, SystemTagMappingNode.php, SystemTagsObjectMappingCollection.php, TagSearchProvider.php
- github.com/cbcoutinho/nextcloud-mcp-server (Quellcode tag_exclusion.py, docs/configuration.md, PR #1393)
- learn.microsoft.com (Purview-DLP für Copilot, SharePoint Restricted Content Discovery, beide aktualisiert 09/2026)
- Nextcloud Findling-Provider C:/Users/Student/nextcloud-search/php/lib/Search/Provider.php

### Secondary (MEDIUM confidence)
- FilesReportPlugin.php/SystemTagPlugin.php per WebFetch gelesen, nicht gemessen (Architecture)
- nextcloud/server PR #64298 (Performance-Messwerte 10.279 Dateien/385.684 Zuordnungen, Status offen)
- github.com/nextcloud/context_chat PR #277, github.com/nextcloud/assistant Issue #638 (Allow-List "AI knowledge", offen)
- portal.nextcloud.com "Managing tags by group" (Subscriber-Inhalt, nur teilweise lesbar)
- knowledge.workspace.google.com (DLP for Gemini, UX-Details fehlen)
- docs.nextcloud.com Developer-Manual WebDAV (dokumentiert nur Favoriten-Filter, System-Tag-Filter nicht erwähnt)

### Tertiary (LOW confidence)
- Notiz-Id gleich Datei-Id (Allgemeinwissen, nicht verifiziert, Messung nötig)
- Speicherübergreifendes Verschieben erzeugt neue fileid, Kopien tragen keine Tags, External-Storage-Neumount, Groupfolders-ACL-Verhalten (alle als Allgemeinwissen markiert, nicht gemessen)

---
*Research completed: 2026-09-26*
*Ready for roadmap: yes*

# Requirements: Milestone v1.7 "Ausschluss-Tag kein-ki"

**Defined:** 2026-09-26
**Core value:** Der Assistent sieht niemals mehr als der angemeldete Nutzer, und ab v1.7 auf Wunsch weniger: was `kein-ki` traegt, sieht er gar nicht.

## Scope-Entscheidungen

| ID | Entscheidung | Konsequenz |
|----|--------------|------------|
| D-v1.7-01 | Fester Tag-Name `kein-ki`, nicht konfigurierbar, Gross-/Kleinschreibung egal, alle gleichnamigen Tag-Varianten zusammen ausgewertet | Jede Konfigurationsstelle waere eine Fail-open-Stelle; ein Irrtum wirkt in Richtung "mehr ausgeschlossen" (Research FEATURES) |
| D-v1.7-02 | Kein "n zurueckgehalten"-Zaehler in Antworten | Ein Zaehler ist ein Existenz-Orakel; erlaubt sind der statische Hinweis in der Tool-Beschreibung und der degraded-Eintrag nur bei gescheiterter Pruefung. Bewusste, dokumentierte Ausnahme von der prepare_context-Hausregel "jeder Cap benennt sich" |
| D-v1.7-03 | Alle vier optionalen Bausteine im Scope (Owner 26.09.): Sandbox-Paritaet, Notes-Anschluss, Pruefkommando, Talk-Dateinamen | 14 Requirements in 4 Kategorien |

Extern getaktet, kein Blocker: nichts. Der Milestone ist vollstaendig ohne fremde Antworten baubar; einzig EXCL-05 traegt eine benannte Messbedingung.

## v1 Requirements

### Ausschlussfilter (EXCL)

- [ ] **EXCL-01**: Eine Datei oder ein Ordner mit dem Tag `kein-ki` (Gross-/Kleinschreibung egal, alle gleichnamigen Tag-Varianten zusammen) erscheint in keiner Antwort der Datei-Werkzeuge (files_list, files_search, files_read, files_download); auch ein Upload auf einen ausgeschlossenen Pfad verraet nicht, ob dort etwas existiert
- [ ] **EXCL-02**: Subtree-Semantik: ein Tag auf einem Ordner deckt alles darunter; die getaggte Menge wird einmal je Antwort geholt (REPORT oc:filter-files) und per Praefixvergleich nach der bestehenden Segmentregel geprueft, nie ueber den Aufruf hinaus gecacht (nur die Aufloesung Name zu Tag-Id darf prozessweit gecacht werden, 412 loest einmal neu auf)
- [ ] **EXCL-03**: unified_search, fetch (alle Id-Arten, auch eine vor dem Taggen bekannte fileid) und prepare_context liefern keine getaggten Treffer, Ausschnitte oder Digests; der systemtags-Suchprovider verraet die getaggte Menge nicht
- [ ] **EXCL-04**: Fail-closed mit drei Zustaenden: kein Tag vorhanden = kein Filter; Menge ermittelt = Filter aktiv; Pruefung nicht beantwortbar = betroffene Eintraege zurueckgehalten und die Degradation benannt (nur dann); Erfolgsantworten sind byte-gleich zu "existiert nicht". Massgeblich ist der Erfolg des REPORT, nicht die systemtags-Capability
- [ ] **EXCL-05**: Notes respektieren den Tag (Notizen sind Dateien); Bedingung: der Mess-Spike belegt den Weg Notiz-Id zu fileid; bei negativem Befund wird der Notes-Anschluss dokumentiert vertagt und die Doku nennt die Luecke
- [ ] **EXCL-06**: talk_browse setzt keine Dateinamen getaggter Dateien mehr in den Nachrichtentext ein
- [ ] **EXCL-07**: Die Tag-Schreibpfade (systemtags-relations) stehen als Nadel im AST-Gate gegen destruktive Aufrufe: der Connector kann den Tag konstruktionsbedingt nie setzen oder entfernen

### Sandbox-Paritaet (SBX)

- [ ] **SBX-01**: Findling-Treffer, die nur eine fileId und keinen Pfad tragen, laufen durch dieselbe Sandbox- (NC_MCP_FILES_ROOT) und Ausschlusspruefung wie Pfad-Treffer
- [ ] **SBX-02**: Notes laufen durch Sandbox- und Ausschlusspruefung (heute umgehen sie die Sandbox vollstaendig)

### Gates und Beweise (GATE)

- [ ] **GATE-01**: Klassifikations-Freeze ueber die aktive Registry: jedes Tool ist als betroffen oder nicht betroffen eingetragen, ein neues Tool ohne Eintrag macht das Gate rot (deckt auch ein kuenftiges files_update aus dem Community-PR)
- [ ] **GATE-02**: Kanarien-Integrationstest: eine getaggte Datei mit eindeutigem Marker in Name und Inhalt; der Marker taucht in keiner Antwort und keinem Fehlertext irgendeines Tools der aktiven Registry auf
- [ ] **GATE-03**: Byte-gleiche Paartests "getaggt gegen nicht existent" fuer Einzelzugriffe, auch im Ausfallfall der Pruefung

### Betrieb und Doku

- [ ] **OPS-01**: `occ mcp_connector:exclusion:check` prueft Tag-Existenz, Sichtbarkeit und gleichnamige Varianten gegen die Instanz und benennt je Pruefschritt das Ergebnis, ohne Sitzung und ohne Nextcloud-Zustandsaenderung (Muster exchange:check)
- [ ] **DOC-03**: Eine dreisprachige Doku (docs/ + README-Erwaehnung) beschreibt Einrichtung und ehrliche Grenzen: Freigabe-Grenze (Tag oberhalb der Freigabe-Wurzel wirkt beim Empfaenger nicht), unsichtbares Tag wirkt nicht, App-aus-Verhalten, Betriebsarten Selbstbedienung (kollaborativ) vs. Organisationsmodus (eingeschraenktes Tag per Gruppen-Delegation)

## Future Requirements (deferred)

- **EXCL-F01**: Enterprise-Governance obendrauf: instanzweite Policies, Allow-Mode, Blocked-Access-Beweis im Audit-Log, Vier-Augen fuer Policy-Aenderungen (bezahlte Schicht, nach dem Fabrice-Call)
- **EXCL-F02**: Store-Text-Erwaehnung des Tags in drei Sprachen (reist erst mit dem naechsten Release, Muster BL-01)

## Out of Scope

- Konfigurierbarer Tag-Name oder Aliase: jede Konfigurationsstelle ist eine Fail-open-Stelle (Research FEATURES)
- "n Eintraege zurueckgehalten"-Zaehler: Existenz-Orakel (D-v1.7-02)
- Schliessung der Freigabe-Grenze: plattformseitig, der Connector sieht nur, was der Nutzer sieht; wird als Grenze dokumentiert (DOC-03)
- Allow-Mode ("nur Getaggtes ist sichtbar"): Enterprise (EXCL-F01)

## Offene Fragen fuer die discuss-phase

1. Ist das Ordner-Tag zugleich die freie Ordner-Ausschlussliste (Empfehlung: ja, keine zweite Liste)?
2. Admin-Schalter fuer den Filter (Empfehlung: nein, klare Meldung statt Schalter)?
3. Upload-Orakel: Verhalten von files_upload auf einen ausgeschlossenen Pfad im Detail (ConflictError verraet Existenz)
4. Zaehlen-vs-Schweigen im Detail je Tool-Familie (eigener Schluessel statt skipped, oder ganz schweigen)

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXCL-01 | Phase 27 | Pending |
| EXCL-02 | Phase 26 | Pending |
| EXCL-03 | Phase 27 | Pending |
| EXCL-04 | Phase 26 | Pending |
| EXCL-05 | Phase 27 (Messbedingung aus Phase 25) | Pending |
| EXCL-06 | Phase 27 | Pending |
| EXCL-07 | Phase 28 | Pending |
| SBX-01 | Phase 27 | Pending |
| SBX-02 | Phase 27 | Pending |
| GATE-01 | Phase 28 | Pending |
| GATE-02 | Phase 28 | Pending |
| GATE-03 | Phase 28 | Pending |
| OPS-01 | Phase 29 | Pending |
| DOC-03 | Phase 29 | Pending |

**Coverage:** 14/14 v1-Requirements zugeordnet, keine Waisen, keine Doppelungen. Phase 25 (Mess-Spike) trägt kein eigenes Requirement, sie liefert die Messvorbedingungen für EXCL-02, EXCL-04 und EXCL-05.

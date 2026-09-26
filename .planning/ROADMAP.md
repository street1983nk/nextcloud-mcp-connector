# Roadmap: MCP Connector für Nextcloud

## Milestones

- **v1.0 MVP im Store**: Phasen 1-5 (shipped 2026-08-20, Release 0.1.2 live im Nextcloud App Store)
- **v1.1 Verwaltungs-Clients und Härtungs-Reste**: Phase 6 (shipped 2026-08-20; Phase 7 deferred, extern getaktet)
- **v1.2 Kuratierte Breite**: Phasen 8-11 (shipped 2026-08-25, Release 0.1.8 live im Store; Talk, Tables und Mail dazu, ohne das Sicherheitsversprechen oder die Schlankheit aufzugeben)
- **v1.3 Pflege und 0.1.9**: Phasen 12-13 (shipped 2026-08-26, Release 0.1.9 live im Store; Konsistenz- und Härtungs-Schulden abgeräumt, CIMD live nachgemessen, Enterprise-Fake-Door)
- **v1.4 Pflege und 0.1.10**: Phasen 14-15 (shipped 2026-08-28, Release 0.1.10 live im Store; gekürzter Enterprise-Text und Kontaktwechsel zu admin@infranode.dev, Doku-Reste aus v1.3 abgeräumt)
- **v1.5 Vorlauf openDesk**: Phasen 16-19 (shipped 2026-08-31, Abschluss nachgetragen 2026-09-18; Release 0.1.11, openDesk-Spike, Audit-Log als erster Enterprise-Baustein)
- **v1.6 F13 Token Exchange Identity Mapper**: Phasen 20-24 (shipped 2026-09-26; ein zweiter, ab Werk ausgeschalteter Prüfpfad nimmt ein nach RFC 8693 getauschtes Keycloak-Token an und handelt unter dem gemappten Nextcloud-Konto; die vier F13-Entscheidungen bleiben extern getaktet)
- **v1.7 Ausschluss-Tag kein-ki**: Phasen 25-29 (in Arbeit seit 2026-09-26; eine Datei oder ein Ordner mit dem System-Tag `kein-ki` erscheint in keiner Tool-Antwort mehr, fail-closed, ein Roundtrip je Antwort)

## Phases

<details>
<summary>v1.0 MVP im Store (Phasen 1-5), SHIPPED 2026-08-20</summary>

- [x] Phase 1: Server-Kern (14/14 Pläne), completed 2026-08-14
- [x] Phase 2: ExApp-Shell (7/7 Pläne), completed 2026-08-15
- [x] Phase 3: OAuth 2.1 (9/9 Pläne), completed 2026-08-16
- [x] Phase 4: Per-User-Verwaltung und prepare_context (4/4 Pläne), completed 2026-08-17
- [x] Phase 5: Hardening und Store-Einreichung (16/16 Pläne inkl. Gap-Closure), completed 2026-08-20

Volle Phasendetails: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
Audit: [milestones/v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md) (passed, 27/27 Requirements)

</details>

<details>
<summary>v1.1 Verwaltungs-Clients und Härtungs-Reste (Phase 6), SHIPPED 2026-08-20</summary>

- [x] Phase 6: Härtung, Eigennachweise und Conference-Reife (11/11 Pläne inkl. Gap-Closure), completed 2026-08-20
- [ ] Phase 7: Verwaltungs-Clients live verprobt, DEFERRED per Owner-Entscheid 2026-08-20 (extern getaktet: it@M-Antwort, Owner-Kontakte; CLIENT-01..03 als Future Requirements vorgemerkt, Protokoll in docs/client-setup.md bleibt einlösbar)

Volle Phasendetails: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
Audit: [milestones/v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md) (passed, 7/7 Requirements)

</details>

<details>
<summary>v1.2 Kuratierte Breite (Phasen 8-11), SHIPPED 2026-08-25</summary>

- [x] Phase 8: Erreichbarkeits-Spike und Tables (5/5 Pläne), completed 2026-08-21
- [x] Phase 9: Talk (5/5 Pläne), completed 2026-08-21
- [x] Phase 10: Mail strikt lesend und die Trifecta-Grenze (8/8 Pläne), completed 2026-08-24
- [x] Phase 11: Bündelung, Budget und Release 0.1.8 (10/10 Pläne; der Phasentitel "0.1.6" war überholt), completed 2026-08-25

Volle Phasendetails: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
Audit: [milestones/v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md) (passed, 17/17 Requirements)

</details>

<details>
<summary>v1.3 Pflege und 0.1.9 (Phasen 12-13), SHIPPED 2026-08-26</summary>

- [x] Phase 12: Konsistenz und Härtungs-Nachzieher (4/4 Pläne), completed 2026-08-25
- [x] Phase 13: CIMD-Nachmessung und Release 0.1.9 (6/6 Pläne, davon 2 mit Owner-Gate), completed 2026-08-25

Volle Phasendetails: [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
Audit: [milestones/v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md) (passed, 6/6 Requirements)

</details>

<details>
<summary>v1.4 Pflege und 0.1.10 (Phasen 14-15), SHIPPED 2026-08-28</summary>

- [x] Phase 14: Doku-Reste und Gate-Entscheid (2/2 Pläne), completed 2026-08-27
- [x] Phase 15: Release 0.1.10 (4/4 Pläne, davon 2 mit Owner-Gate), completed 2026-08-28

Volle Phasendetails: [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
Audit: [milestones/v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md) (passed, 4/4 Requirements)

</details>

<details>
<summary>v1.5 Vorlauf openDesk (Phasen 16-19), SHIPPED 2026-08-31 (Abschluss nachgetragen 2026-09-18)</summary>

- [x] Phase 16: Release 0.1.11 (4/4 Pläne), completed 2026-08-28
- [x] Phase 17: openDesk-Spike (9/9 Pläne), completed 2026-08-29
- [x] Phase 18: Audit-Log Kern (10/10 Pläne), completed 2026-08-29
- [x] Phase 19: Audit-Log Bedienung und Textnachzug (9/9 Pläne), completed 2026-08-31

Volle Phasendetails: [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
Kein Milestone-Audit: `/gsd:complete-milestone` lief erst am 2026-09-18 nach, das Audit wurde nicht nachgefahren (siehe MILESTONES.md).

</details>

<details>
<summary>v1.6 F13 Token Exchange Identity Mapper (Phasen 20-24), SHIPPED 2026-09-26</summary>

- [x] Phase 20: JWKS-Schicht und PyJWT-Stand (2/2 Pläne), completed 2026-09-19
- [x] Phase 21: Exchange-Verifier (2/2 Pläne), completed 2026-09-19
- [x] Phase 22: Konfiguration, Kette und Drosselung (3/3 Pläne), completed 2026-09-19
- [x] Phase 23: Konto-Mapping und Credential-Wege (6/6 Pläne), completed 2026-09-23
- [x] Phase 24: Audit-Anschluss und Nachweis (9/9 Pläne), completed 2026-09-24, secure-phase 2026-09-26 (38/38)

Volle Phasendetails: [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
Kein Milestone-Audit (wie v1.5): Aussagen aus den fünf Phase-Verifikationen, dem Phase-24-Review und der secure-phase 24; siehe MILESTONES.md.

</details>

### v1.7 Ausschluss-Tag kein-ki (Phasen 25-29), IN ARBEIT

- [ ] **Phase 25: Mess-Spike Tag-Abfrage** - Die unbelegten Annahmen der Recherche werden gemessen, bevor eine Designentscheidung fällt (BL-16-Kostennotiz)
- [ ] **Phase 26: Guard-Kern** - Eine request-gebundene Prüfschicht mit drei Zuständen, einem Roundtrip je Antwort und Subtree-Präfixregel, ohne dass ein Werkzeug angefasst wird
- [ ] **Phase 27: Familien-Anschluss und Sandbox-Parität** - Jede dateitragende Antwort läuft durch den Guard; Findling-fileIds und Notes laufen zusätzlich durch die Sandbox
- [ ] **Phase 28: Gates und Beweise** - Klassifikations-Freeze, Kanarientest, byte-gleiche Paartests und die Destruktiv-Nadel auf die Tag-Schreibpfade machen die Grenze zu einem Gate
- [ ] **Phase 29: Prüfkommando und Doku** - `occ mcp_connector:exclusion:check` meldet wirkungslose Konfigurationen, die dreisprachige Doku sagt das Gemessene samt ehrlicher Grenzen

## Phase Details

### Phase 25: Mess-Spike Tag-Abfrage
**Goal**: Jede Annahme, auf der die Architektur des Filters ruht, ist gegen echte Nextcloud-Instanzen gemessen statt aus dem Quelltext gelesen; das Messprotokoll entscheidet Batch-Strategie, Notes-Anschluss und Fail-closed-Auslöser
**Depends on**: Nothing (erste Phase des Milestones; baut auf v1.6 auf)
**Requirements**: keine eigenen; die Phase liefert die Messvorbedingungen für EXCL-02, EXCL-04 und die benannte Messbedingung von EXCL-05
**Success Criteria** (what must be TRUE):
  1. Auf NC 32, 33 und 34 (35 als Bestätigung der vorhandenen Messung) ist gemessen und mit Statuscode und Trefferliste protokolliert, was REPORT oc:filter-files mit oc:systemtag bei ausgeschalteter systemtags-App liefert und ob nur Capability und Suchprovider verschwinden
  2. REPORT unter AppAPI-Impersonation in der ExApp-Topologie liefert für dasselbe Konto dieselbe Menge an fileids wie mit App-Passwort; die Abweichung ist, falls vorhanden, als Befund mit Rohantwort benannt
  3. Die Kosten des REPORT stehen als Zahlen im Protokoll: Wanduhr und Antwortgröße bei 1, 100 und 5000 getaggten Knoten, dazu die Referenz-Wanduhr von prepare_context, sodass die Batch-Entscheidung auf einer Messung steht
  4. Ob die Notiz-Id der fileid entspricht, ist mit Beleg aus einer echten Notiz beantwortet (ja oder nein), und das Ergebnis entscheidet ausdrücklich über den Notes-Weg in Phase 27
  5. Das Verhalten bei 412 nach gelöschter und neu angelegter Tag-Id, bei unsichtbarem Tag, bei gleichnamigen Varianten, beim REPORT-Zielpfad (Unterordner gegen Home-Wurzel) und bei geteiltem Unterordner mit getaggtem Vorfahr beim Eigentümer ist je als gemessener Einzelbefund festgehalten
**Plans**: TBD
**Research flag**: ja (Live-Zugriff auf NC 32 bis 35, präparierte Testdaten mit großen Ordnern, vielen Tag-Zuordnungen und geteilten Unterordnern)

### Phase 26: Guard-Kern
**Goal**: Eine policy-freie Tag-Abfrage und ein request-gebundener Guard stehen unabhängig testbar bereit, beantworten je Tool-Aufruf mit genau einem Roundtrip, ob ein Pfad oder eine fileid ausgeschlossen ist, und unterscheiden "nichts getaggt" hart von "nicht prüfbar"
**Depends on**: Phase 25
**Requirements**: EXCL-02, EXCL-04
**Success Criteria** (what must be TRUE):
  1. Die drei Zustände sind je mit Test belegt: kein `kein-ki`-Tag vorhanden ergibt keinen Filter und eine Antwort byte-gleich zum Stand vor v1.7; ermittelte Menge ergibt aktiven Filter; REPORT-Fehler, Timeout und ein zweiter 412 ergeben den Zustand "nicht prüfbar"; die Capability systemtags.enabled wird dabei nicht befragt (Test: Capability false, REPORT erfolgreich, Filter aktiv)
  2. Je Tool-Aufruf geht genau ein REPORT hinaus, auch bei parallelen Teilaufrufen (per respx call_count gemessen, Single-Flight nach dem Muster von oauth/jwks.py); ein zweiter Tool-Aufruf holt die Menge neu, nur die Auflösung Name zu Tag-Id bleibt prozessweit gecacht (Muster capabilities.py), und ein 412 löst genau einmal neu auf
  3. Die Subtree-Prüfung nutzt die bestehende Segmentregel: ein getaggter Ordner `/A/kein` deckt `/A/kein/x`, aber nicht `/A/keine`; ein getaggter Vorfahr oberhalb von NC_MCP_FILES_ROOT wirkt, weil die getaggte Menge nicht durch die Sandbox gefiltert wird
  4. Alle gleichnamigen Varianten von `kein-ki` werden ohne Rücksicht auf Groß- und Kleinschreibung vereinigt ausgewertet (Test mit drei Varianten unterschiedlicher Sichtbarkeit und Schreibweise)
**Plans**: TBD
**Offene Punkte für die discuss-phase (nicht entschieden)**:
  - Ist das Tag auf einem Ordner zugleich die freie Ordner-Ausschlussliste, oder braucht es eine zweite, konfigurierbare Liste (Recherche-Empfehlung: keine zweite Liste, zweite Fail-open-Stelle)?
  - Admin-Schalter für den Filter ja oder nein (Recherche-Empfehlung: nein, klare Meldung statt Schalter)?

### Phase 27: Familien-Anschluss und Sandbox-Parität
**Goal**: Was `kein-ki` trägt oder unter einem getaggten Ordner liegt, erscheint in keiner Antwort eines dateitragenden Werkzeugs mehr, weder als Treffer noch als Inhalt, Ausschnitt, Digest oder eingesetzter Dateiname; Findling-Treffer ohne Pfad und Notes laufen durch dieselbe Sandbox- und Ausschlussprüfung wie Pfad-Treffer
**Depends on**: Phase 26
**Requirements**: EXCL-01, EXCL-03, EXCL-05, EXCL-06, SBX-01, SBX-02
**Success Criteria** (what must be TRUE):
  1. Gegen eine echte Nextcloud gemessen: eine getaggte Datei und eine Datei unter einem getaggten Ordner fehlen in files_list, files_search, files_read und files_download, und ein Upload auf einen ausgeschlossenen Pfad lässt nicht erkennen, ob dort etwas existiert
  2. unified_search, search/fetch (alle Id-Arten, auch eine vor dem Taggen bekannte fileid) und prepare_context liefern keinen getaggten Treffer, keinen Ausschnitt und keinen Digest; der systemtags-Suchprovider verrät die getaggte Menge nicht; die Wanduhr von prepare_context liegt gemessen im Rahmen der Phase-25-Referenz
  3. Ein Findling-Treffer, der nur eine fileId trägt, und eine Notiz außerhalb von NC_MCP_FILES_ROOT verschwinden aus den Antworten wie ein Pfad-Treffer außerhalb der Sandbox; eine getaggte Notiz verschwindet, sofern Phase 25 den Weg Notiz-Id zu fileid belegt hat, andernfalls ist der Notes-Ausschluss dokumentiert vertagt und die Lücke benannt
  4. talk_browse setzt den Dateinamen einer getaggten Datei nicht mehr in den Nachrichtentext ein (gemessen an einer Nachricht mit geteilter getaggter Datei)
  5. Ist die Prüfung nicht beantwortbar, hält jede betroffene Familie ihre dateitragenden Einträge zurück und benennt die Degradation in einem degraded-Eintrag; im Erfolgsfall trägt keine Antwort einen Zähler oder Hinweis auf zurückgehaltene Einträge
**Plans**: TBD
**Research flag**: Notes-Teil hängt vollständig an Phase 25; fällt "Notiz-Id = fileid" durch, braucht der Teil eine kurze eigene Recherche zur Notes-REST-API
**Offene Punkte für die discuss-phase (nicht entschieden)**:
  - Upload-Orakel: Verhalten von files_upload auf einen ausgeschlossenen Pfad im Detail (ConflictError verrät heute Existenz; verbieten oder erlauben, und mit welchem Wortlaut)
  - Zählen oder Schweigen im Detail je Tool-Familie (eigener Schlüssel statt skipped, oder ganz schweigen); D-v1.7-02 steht, die Ausgestaltung je Familie ist offen

### Phase 28: Gates und Beweise
**Goal**: Die Aussage "keine Tool-Antwort zeigt Getaggtes" ist ein roter oder grüner Test statt eines Versprechens: jedes Werkzeug der aktiven Registry ist klassifiziert, ein Kanarienwort taucht nirgends auf, getaggt und nicht existent sind byte-gleich, und der Connector kann den Tag konstruktionsbedingt nie setzen oder entfernen
**Depends on**: Phase 27
**Requirements**: GATE-01, GATE-02, GATE-03, EXCL-07
**Success Criteria** (what must be TRUE):
  1. Der Klassifikations-Freeze über die aktive Registry trägt jedes Werkzeug als betroffen oder nicht betroffen ein; ein hinzugefügtes Probe-Werkzeug ohne Eintrag macht das Gate rot (Gegenprobe im Test, deckt auch ein künftiges files_update)
  2. Der Kanarien-Integrationstest legt eine getaggte Datei mit eindeutigem Marker in Name und Inhalt an und ruft jedes Werkzeug der aktiven Registry auf; der Marker kommt in null Antworten und null Fehlertexten vor, und die Zahl der geprüften Werkzeuge steht in der Testausgabe
  3. Für jeden Einzelzugriff ist die Antwort auf eine getaggte Id byte-gleich zur Antwort auf eine nicht existente Id, im Normalbetrieb und im Ausfallfall der Prüfung
  4. Das AST-Gate gegen destruktive Aufrufe trägt Nadeln für die systemtags-relations- und systemtags-Schreibpfade, jede mit Gegenprobe, die ohne die Nadel rot würde
**Plans**: TBD

### Phase 29: Prüfkommando und Doku
**Goal**: Eine Administration erkennt ohne Live-Sitzung, ob ihr `kein-ki`-Tag wirkt, und die Doku in drei Sprachen beschreibt Einrichtung, Betriebsarten und ehrliche Grenzen ausschließlich aus den gemessenen Befunden
**Depends on**: Phase 28
**Requirements**: OPS-01, DOC-03
**Success Criteria** (what must be TRUE):
  1. `occ mcp_connector:exclusion:check` benennt je Prüfschritt das Ergebnis (Tag existiert, ist sichtbar, gleichnamige Varianten) gegen eine echte Instanz, auch für die Fehlkonfigurationen unsichtbares Tag und Tippfehler im Namen
  2. Das Kommando läuft ohne Sitzung und ändert nichts an der Nextcloud: ein Vorher-nachher-Vergleich der Tag- und Zuordnungstabellen ist leer (Muster exchange:check)
  3. Die Doku unter docs/ und die README-Erwähnung liegen in allen drei Sprachen vor und nennen Freigabe-Grenze, unsichtbares Tag, App-aus-Verhalten und die Betriebsarten Selbstbedienung (kollaborativ) und Organisationsmodus (eingeschränktes Tag per Gruppen-Delegation); jede Grenzaussage verweist auf ihren Befund aus Phase 25
  4. Die Store-Beschreibungen sind unverändert (EXCL-F02 reist mit dem nächsten Release), belegt durch einen leeren Diff der drei Store-Texte
**Plans**: TBD
**Offene Punkte für die discuss-phase (nicht entschieden)**:
  - Was das Prüfkommando meldet, hängt an den Entscheiden aus Phase 26 (Admin-Schalter, Ordner-Tag als Ausschlussliste)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Server-Kern | v1.0 | 14/14 | Complete | 2026-08-14 |
| 2. ExApp-Shell | v1.0 | 7/7 | Complete | 2026-08-15 |
| 3. OAuth 2.1 | v1.0 | 9/9 | Complete | 2026-08-16 |
| 4. Per-User-Verwaltung und prepare_context | v1.0 | 4/4 | Complete | 2026-08-17 |
| 5. Hardening und Store-Einreichung | v1.0 | 16/16 | Complete | 2026-08-20 |
| 6. Härtung, Eigennachweise und Conference-Reife | v1.1 | 11/11 | Complete | 2026-08-20 |
| 7. Verwaltungs-Clients live verprobt | v1.1 | 0/0 | Deferred (extern getaktet) | - |
| 8. Erreichbarkeits-Spike und Tables | v1.2 | 5/5 | Complete | 2026-08-21 |
| 9. Talk | v1.2 | 5/5 | Complete | 2026-08-21 |
| 10. Mail strikt lesend und die Trifecta-Grenze | v1.2 | 8/8 | Complete | 2026-08-24 |
| 11. Bündelung, Budget und Release 0.1.8 | v1.2 | 10/10 | Complete | 2026-08-25 |
| 12. Konsistenz und Härtungs-Nachzieher | v1.3 | 4/4 | Complete | 2026-08-25 |
| 13. CIMD-Nachmessung und Release 0.1.9 | v1.3 | 6/6 | Complete | 2026-08-25 |
| 14. Doku-Reste und Gate-Entscheid | v1.4 | 2/2 | Complete | 2026-08-27 |
| 15. Release 0.1.10 | v1.4 | 4/4 | Complete | 2026-08-28 |
| 16. Release 0.1.11 | v1.5 | 4/4 | Complete | 2026-08-28 |
| 17. openDesk-Spike | v1.5 | 9/9 | Complete | 2026-08-29 |
| 18. Audit-Log Kern | v1.5 | 10/10 | Complete | 2026-08-29 |
| 19. Audit-Log Bedienung und Textnachzug | v1.5 | 9/9 | Complete | 2026-08-31 |
| 20. JWKS-Schicht und PyJWT-Stand | v1.6 | 2/2 | Complete   | 2026-09-19 |
| 21. Exchange-Verifier | v1.6 | 2/2 | Complete   | 2026-09-19 |
| 22. Konfiguration, Kette und Drosselung | v1.6 | 3/3 | Complete   | 2026-09-19 |
| 23. Konto-Mapping und Credential-Wege | v1.6 | 6/6 | Complete | 2026-09-23 |
| 24. Audit-Anschluss und Nachweis | v1.6 | 9/9 | Complete    | 2026-09-24 |
| 25. Mess-Spike Tag-Abfrage | v1.7 | 0/TBD | Not started | - |
| 26. Guard-Kern | v1.7 | 0/TBD | Not started | - |
| 27. Familien-Anschluss und Sandbox-Parität | v1.7 | 0/TBD | Not started | - |
| 28. Gates und Beweise | v1.7 | 0/TBD | Not started | - |
| 29. Prüfkommando und Doku | v1.7 | 0/TBD | Not started | - |

## Coverage v1.7

| Requirement | Phase |
|-------------|-------|
| EXCL-01 | Phase 27 |
| EXCL-02 | Phase 26 |
| EXCL-03 | Phase 27 |
| EXCL-04 | Phase 26 |
| EXCL-05 | Phase 27 (Messbedingung aus Phase 25) |
| EXCL-06 | Phase 27 |
| EXCL-07 | Phase 28 |
| SBX-01 | Phase 27 |
| SBX-02 | Phase 27 |
| GATE-01 | Phase 28 |
| GATE-02 | Phase 28 |
| GATE-03 | Phase 28 |
| OPS-01 | Phase 29 |
| DOC-03 | Phase 29 |

Zugeordnet: 14/14, keine Waisen, keine Doppelungen. Phase 25 trägt bewusst kein eigenes Requirement: sie liefert die Messvorbedingungen, auf denen EXCL-02, EXCL-04 und EXCL-05 stehen.

---
*Roadmap created: 2026-08-14 (granularity: coarse, mode: mvp); v1.0 abgeschlossen: 2026-08-20; v1.1 abgeschlossen: 2026-08-20 (Phase 7 deferred); v1.2 abgeschlossen: 2026-08-25 (Release 0.1.8 live); v1.3 abgeschlossen: 2026-08-26 (Release 0.1.9 live); v1.4 abgeschlossen: 2026-08-28 (Release 0.1.10 live); v1.5 abgeschlossen: 2026-08-31 (Release 0.1.11, openDesk-Spike, Audit-Log; Abschluss nachgetragen 2026-09-18); v1.6 aufgesetzt: 2026-09-18 (Phasen 20-24, 15 Requirements, granularity coarse); v1.6 abgeschlossen: 2026-09-26 (Token-Exchange-Pfad komplett, 15/15 Requirements, kein Release); v1.7 aufgesetzt: 2026-09-26 (Phasen 25-29, 14 Requirements, granularity coarse)*

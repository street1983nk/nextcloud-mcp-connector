# Roadmap: MCP Connector für Nextcloud

## Milestones

- **v1.0 MVP im Store**: Phasen 1-5 (shipped 2026-08-20, Release 0.1.2 live im Nextcloud App Store)
- **v1.1 Verwaltungs-Clients und Härtungs-Reste**: Phase 6 (shipped 2026-08-20; Phase 7 deferred, extern getaktet)
- **v1.2 Kuratierte Breite**: Phasen 8-11 (shipped 2026-08-25, Release 0.1.8 live im Store; Talk, Tables und Mail dazu, ohne das Sicherheitsversprechen oder die Schlankheit aufzugeben)
- **v1.3 Pflege und 0.1.9**: Phasen 12-13 (shipped 2026-08-26, Release 0.1.9 live im Store; Konsistenz- und Härtungs-Schulden abgeräumt, CIMD live nachgemessen, Enterprise-Fake-Door)
- **v1.4 Pflege und 0.1.10**: Phasen 14-15 (shipped 2026-08-28, Release 0.1.10 live im Store; gekürzter Enterprise-Text und Kontaktwechsel zu admin@infranode.dev, Doku-Reste aus v1.3 abgeräumt)
- **v1.5 Vorlauf openDesk**: Phasen 16-19 (shipped 2026-08-31, Abschluss nachgetragen 2026-09-18; Release 0.1.11, openDesk-Spike, Audit-Log als erster Enterprise-Baustein)
- **v1.6 F13 Token Exchange Identity Mapper**: Phasen 20-24 (shipped 2026-09-26; ein zweiter, ab Werk ausgeschalteter Prüfpfad nimmt ein nach RFC 8693 getauschtes Keycloak-Token an und handelt unter dem gemappten Nextcloud-Konto; die vier F13-Entscheidungen bleiben extern getaktet)
- **v1.7 Ausschluss-Tag kein-ki**: Phasen 25-29 (shipped 2026-10-01; eine Datei oder ein Ordner mit dem System-Tag `kein-ki` erscheint in keiner Tool-Antwort mehr, fail-closed, ein REPORT je Antwort; noch nicht released, reist mit 0.4.0)
- **v1.8 Tasks-Bundle und Ordner anlegen**: Phasen 30-34 (shipped 2026-11-14, Release 0.8.0 live im Store; Ordner anlegen nach Issue #44, Aufgaben suchen, lesen, anlegen, abhaken, ändern und verschieben nach Issue #32, kein Löschen; nebenläufig 0.7.0 bis 0.7.3)

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

<details>
<summary>v1.7 Ausschluss-Tag kein-ki (Phasen 25-29), SHIPPED 2026-10-01</summary>

- [x] Phase 25: Mess-Spike Tag-Abfrage (5/5 Pläne), completed 2026-09-27
- [x] Phase 26: Guard-Kern (2/2 Pläne), completed 2026-09-27
- [x] Phase 27: Familien-Anschluss und Sandbox-Parität (10/10 Pläne inkl. zwei Lückenplänen), completed 2026-09-28, SBX-01 per CI 2026-10-01
- [x] Phase 28: Gates und Beweise (12/12 Pläne), gebaut 2026-09-28, completed 2026-10-01
- [x] Phase 29: Prüfkommando und Doku (9/9 Pläne), completed 2026-10-01

Volle Phasendetails: [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md)
Phasenordner bleiben unter .planning/phases/ (Doku und Tests verlinken die Befunde dorthin).
Kein Milestone-Audit (wie v1.5 und v1.6): Aussagen aus den fünf Phase-Verifikationen (alle passed), den Code-Reviews und den fünf secure-phase-Läufen (alle threats_open 0); siehe MILESTONES.md.

</details>

<details>
<summary>v1.8 Tasks-Bundle und Ordner anlegen (Phasen 30-34), SHIPPED 2026-11-14</summary>

- [x] Phase 30: Mess-Spike Aufgaben und Ordner (5/5 Pläne), completed 2026-11-12
- [x] Phase 31: Ordner anlegen (9/9 Pläne inkl. drei Zusatzplänen), completed 2026-11-13
- [x] Phase 32: Tasks-Bundle suchen, lesen, anlegen (12/12 Pläne inkl. zwei Lückenplänen), completed 2026-11-13
- [x] Phase 33: Aufgaben ändern (13/13 Pläne inkl. Zusatzplan 33-11), completed 2026-11-14
- [x] Phase 34: Doku, Store, Release 0.8.0 (11/11 Pläne), completed 2026-11-14, Release 0.8.0 im Store

Volle Phasendetails: [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md)
Requirements: [milestones/v1.8-REQUIREMENTS.md](milestones/v1.8-REQUIREMENTS.md) (33/33 erledigt, TMOD-07 seit 2026-11-12 Out of Scope)
Phasenordner bleiben unter .planning/phases/ (Doku, Tests und Skripte verlinken Befunde und Rohprotokolle dorthin).
Kein Milestone-Audit (wie v1.5 bis v1.7): Aussagen aus den Phase-Verifikationen 31 bis 33 (passed) und 34 (48/48 must-haves, human_needed nur für eine Runbook-Zeile), dem Messbericht der Phase 30 und den CI-Läufen; siehe MILESTONES.md.

</details>

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
| 25. Mess-Spike Tag-Abfrage | v1.7 | 5/5 | Complete    | 2026-09-27 |
| 26. Guard-Kern | v1.7 | 2/2 | Complete    | 2026-09-27 |
| 27. Familien-Anschluss und Sandbox-Parität | v1.7 | 10/10 | Complete    | 2026-09-28 |
| 28. Gates und Beweise | v1.7 | 12/12 | Complete    | 2026-10-01 |
| 29. Prüfkommando und Doku | v1.7 | 9/9 | Complete    | 2026-10-01 |
| 30. Mess-Spike Aufgaben und Ordner | v1.8 | 5/5 | Complete    | 2026-11-12 |
| 31. Ordner anlegen | v1.8 | 9/9 | Complete    | 2026-11-13 |
| 32. Tasks-Bundle suchen, lesen, anlegen | v1.8 | 12/12 | Complete    | 2026-11-13 |
| 33. Aufgaben ändern | v1.8 | 13/13 | Complete    | 2026-11-14 |
| 34. Doku, Store, Release 0.8.0 | v1.8 | 11/11 | Complete    | 2026-11-14 |

## Next

Kein aktiver Milestone. v1.8 ist abgeschlossen, Release 0.8.0 steht seit 2026-11-14 im Store. Der nächste Zyklus startet mit `/gsd:new-milestone`, sobald das Owner-Thema feststeht. Vorgemerkt: Tag-Alias `no-ai` neben `kein-ki` als eigene kleine Phase (Schreibweise beim Owner erfragen), Audit-Grund "unspecified" bei veraltetem ETag. files_update-Weiterentwicklung und die F13-Spur bleiben außerhalb (milestones/v1.6-REQUIREMENTS.md).

---
*Roadmap created: 2026-08-14 (granularity: coarse, mode: mvp); v1.0 abgeschlossen: 2026-08-20; v1.1 abgeschlossen: 2026-08-20 (Phase 7 deferred); v1.2 abgeschlossen: 2026-08-25 (Release 0.1.8 live); v1.3 abgeschlossen: 2026-08-26 (Release 0.1.9 live); v1.4 abgeschlossen: 2026-08-28 (Release 0.1.10 live); v1.5 abgeschlossen: 2026-08-31 (Release 0.1.11, openDesk-Spike, Audit-Log; Abschluss nachgetragen 2026-09-18); v1.6 aufgesetzt: 2026-09-18 (Phasen 20-24, 15 Requirements, granularity coarse); v1.6 abgeschlossen: 2026-09-26 (Token-Exchange-Pfad komplett, 15/15 Requirements, kein Release); v1.7 aufgesetzt: 2026-09-26 (Phasen 25-29, 14 Requirements, granularity coarse); v1.7 abgeschlossen: 2026-10-01 (kein-ki-Filter komplett, 14/14 Requirements, kein Release; Release 0.4.0 nach PR #14); v1.8 Roadmap geschrieben: 2026-11-11 (Phasen 30-34, 34 Requirements, granularity coarse; Owner-Entscheide E1 bis E14); v1.8 abgeschlossen: 2026-11-14 (Ordner anlegen und Tasks-Bundle, 33/33 Requirements, TMOD-07 Out of Scope; Release 0.8.0 live)*
